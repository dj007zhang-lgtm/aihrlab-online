/**
 * AIHR 数智引擎 · 站内知识库问答中继（Cloudflare Worker）
 * ------------------------------------------------------------------
 * 职责：纯静态 GitHub Pages 站没有后端，本 Worker 充当「无服务器中继」：
 *   1. 冷启动拉取并内存缓存知识库 assets/qa/kb.json（构建期由 build_qa_kb.py 生成）
 *   2. 中文 bigram + BM25 召回与用户问题最相关的 top-k 段落（标题/标签/类目加权）
 *   3. 组装「仅依据资料、未知则答未收录、返回引用 URL」的系统提示词
 *   4. SSE 流式转发 LLM 接口（agnes-ai 默认 / 腾讯元器可切换），回传 answer + sources
 *   [元器路径架构] 答案由元器知识库 RAG 生成（稳）；元器 openapi 不返回引用（前提 A 未过），
 *      故「来源卡片」由本地 KB 召回兜底（可点击站内文章），答案流完后发送，确保「答案先于参考源」。
 *   5. 限速 + 日预算护栏；API key 仅存环境变量（绝不进前端/仓库）
 *
 * 安全护栏（参考 @wshuyi 长文三道防线）：
 *   - API key 不进前端、不进仓库，仅存 Worker 环境变量/Secret
 *   - 本中继持密钥，前端只发 question
 *   - 公网服务必须访问控制（CORS 白名单）+ 配额上限（限速/预算）
 *
 * 正见正念纪律：资料未覆盖则明说「未收录」，零虚构、不营销、不渲染焦虑。
 *
 * 部署：wrangler deploy（见同目录 wrangler.toml 与交付说明）
 */

// ---------- 可配置项（环境变量覆盖） ----------
// AGNES_API_KEY     : agnes-ai API key（Secret，必填）
// KB_URL            : 知识库 JSON 地址，默认 https://aihrlab.online/assets/qa/kb.json
// AGNES_MODEL       : 默认 agnes-2.0-flash
// ALLOWED_ORIGINS   : 逗号分隔的允许跨域来源，默认 https://aihrlab.online,https://www.aihrlab.online
// TOP_K             : 召回段落数，默认 6
// RATE_LIMIT_PER_MIN: 每 IP 每分钟请求上限，默认 20
// DAILY_TOKEN_BUDGET: 每日输出 token 预算（best-effort 内存计数），默认 200000（≈数十元）
// MAX_TOKENS        : 单次回答最大输出 token，默认 800

// 注意：env 绑定仅在 fetch(request, env, ctx) 的 env 参数里可用，模块顶层读不到。
// 故默认值放此处，真实取值在 fetch 内从 env 覆盖（见下方 fetch 顶部）。
let KB_URL = 'https://aihrlab.online/assets/qa/kb.json';
let ALLOWED_ORIGINS = ['https://aihrlab.online', 'https://www.aihrlab.online'];

// BM25 参数
const K1 = 1.5;
const B = 0.75;

// 多轮对话：前端最多回传最近 N 轮历史（2N 条消息），避免 token 膨胀
const MAX_HISTORY_TURNS = 10;

// 内存态知识库（同一 isolate 复用，冷启动后常驻）
let KB = null;
const KB_TTL_MS = 60 * 60 * 1000; // 1 小时，过后下次请求重新拉取

// 限速 / 预算（best-effort：依赖 isolate 复用；如需持久可接入 Workers KV）
const rateBuckets = new Map(); // ip -> {ts, count}
let dayTokenUsed = 0;
let dayTokenStamp = newDateStamp();

// agnes-ai 出口限流保护：同一 isolate 内控制连续调用最小间隔，降低 Cloudflare 1015 概率
let lastAgnesRequestAt = 0;
const MIN_AGNES_INTERVAL_MS = 600;

function newDateStamp() {
  const d = new Date();
  return d.getUTCFullYear() * 10000 + (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
}

// ---------- 中文分词：CJK 二元 + ASCII 词 ----------
function tokenize(text) {
  if (!text) return [];
  const t = String(text).toLowerCase();
  const tokens = [];
  // CJK 连续段 → 二元组（覆盖中文检索，无需 jieba）
  const cjkRe = /[一-鿿]+/g;
  let m;
  while ((m = cjkRe.exec(t)) !== null) {
    const run = m[0];
    for (let i = 0; i < run.length - 1; i++) tokens.push(run.substr(i, 2));
    if (run.length === 1) tokens.push(run); // 单字也保留
  }
  // ASCII 字母数字串（≥2）
  const asciiRe = /[a-z0-9][a-z0-9+#.@/_\-]{1,}/g;
  while ((m = asciiRe.exec(t)) !== null) tokens.push(m[0]);
  return tokens;
}

// ---------- 加载并构建索引 ----------
async function loadKB() {
  if (KB && Date.now() - KB.loadedAt < KB_TTL_MS) return KB;
  const resp = await fetch(KB_URL, { cf: { cacheTtl: 3600, cacheEverything: true } });
  if (!resp.ok) throw new Error('KB fetch failed: ' + resp.status);
  const data = await resp.json();
  const chunks = data.chunks || [];
  const df = new Map(); // token -> 含该 token 的 chunk 数
  let totalLen = 0;
  for (const ch of chunks) {
    const toks = tokenize(ch.text || '');
    ch._textTok = toks;          // 预存 token 数组，检索期直接统计 tf，避免重复分词
    ch._tokSet = new Set(toks);
    ch._len = toks.length;
    totalLen += toks.length;
    // 字段 token（标题/标签/类目）用于加权
    ch._titleTok = new Set(tokenize(ch.title || ''));
    ch._tagTok = new Set(tokenize((ch.tags || []).join(' ')));
    ch._catTok = new Set(tokenize(ch.category || ''));
    for (const tk of ch._tokSet) df.set(tk, (df.get(tk) || 0) + 1);
  }
  const N = chunks.length;
  const avgdl = N > 0 ? totalLen / N : 0;
  KB = {
    chunks,
    df,
    N,
    avgdl,
    articles: data.articles_indexed || 0,
    loadedAt: Date.now(),
  };
  return KB;
}

function idf(term, kb) {
  const df = kb.df.get(term) || 0;
  return Math.log(1 + (kb.N - df + 0.5) / (df + 0.5));
}

// ---------- 检索：BM25 + 字段加权 ----------
function retrieve(question, kb, topK) {
  const qtoks = tokenize(question);
  if (qtoks.length === 0) return [];
  // query 词频（同一词重复出现不重复加权）
  const qfreq = new Map();
  for (const tk of qtoks) qfreq.set(tk, (qfreq.get(tk) || 0) + 1);
  const scored = [];
  for (const ch of kb.chunks) {
    // 早退：chunk 完全不含任何 query token 则无分
    let anyMatch = false;
    for (const tk of qfreq.keys()) {
      if (ch._tokSet.has(tk)) { anyMatch = true; break; }
    }
    if (!anyMatch) continue;
    const arr = ch._textTok;
    // 单次遍历统计 query token 在本文档的 tf
    const tfMap = new Map();
    for (let i = 0; i < arr.length; i++) {
      const tk = arr[i];
      if (qfreq.has(tk)) tfMap.set(tk, (tfMap.get(tk) || 0) + 1);
    }
    let score = 0;
    for (const tk of qfreq.keys()) {
      const tf = tfMap.get(tk) || 0;
      if (tf === 0) continue;
      const idfV = idf(tk, kb);
      score += idfV * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * (ch._len / (kb.avgdl || 1))));
      // 字段加权（提升标题/标签/类目命中的片段）
      if (ch._titleTok.has(tk)) score += 1.5 * idfV;
      if (ch._tagTok.has(tk)) score += 0.8 * idfV;
      if (ch._catTok.has(tk)) score += 0.4 * idfV;
    }
    if (score > 0) scored.push({ ch, score });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}

// ---------- 构造系统提示词与资料上下文 ----------
// 关键教训（实测多轮）：模型会把 user message 里的「参考资料」「格式要求」「输出步骤」
// 原样复述进输出。所以：
//  1) 资料单独放一条 user 消息，并明确标注「仅供作答依据，不是你的输出内容」；
//  2) 用一条 assistant 确认 + 一条 few-shot 干净答案做格式锚点，引导模型直接输出连贯段落；
//  3) system 把「禁止复述检索格式 / 思考语句 / 格式要求 / 编号列表」写死；
//  4) 元器侧：不能传 system role，所以规则必须极简、命令式，避免任何「1. 2. 3.」结构；
//  5) 流式侧再用 makeCoTFilter 做硬兜底（见下），覆盖截图实测吐出来的所有复述模式。
function buildMessages(chunks, question) {
  const parts = chunks.map((c, i) => {
    const ch = c.ch; // retrieve 返回的是 {ch, score}
    const heading = ch.heading ? `（小节：${ch.heading}）` : '';
    return `[${i + 1}] ${ch.title}｜${ch.url}${heading ? '｜' + heading : ''}\n${ch.text}`;
  });
  const system = [
    '你是「AIHR数智引擎」网站的知识库问答助手，由资深 HR/OD 专家视角作答。',
    '你只能依据下方「参考资料」作答，不得编造事实、数据或结论，不得引入资料之外的信息。',
    '若参考资料中完全没有相关信息，只回答：「本站资料暂未收录该问题的相关内容」，并建议换一种问法或留言补充。',
    '若参考资料中有相关信息，直接给出整合后的最终答案。',
    '',
    '【绝对禁止】你的输出中不得出现以下任何内容，一旦发现立即整段删除：',
    '1. 参考资料原文、检索格式（如「[1] 来源：…」「来源：…」「资料片段」「片段N」）、对资料的要点罗列或复述；',
    '2. 任何思考 / 过渡语句：「我需要…」「让我分析…」「根据资料…」「以下是…」「首先 / 其次 / 最后」「用户询问…」；',
    '3. 对问题或格式要求的复述（如「我需要按照格式要求回答…」「回答格式要求…」）；',
    '4. 数字编号列表（1. 2. 3.）或分点清单、对称排比等 AI 腔。',
    '',
    '你的输出只能是：',
    '① 1-2 段连贯的中文正文，直接以答案第一句话开头；句中在观点或关键事实后用 [N] 标注来源编号，与参考资料中的 [N] 一一对应；',
    '② 正文结束后另起一行写「参考来源：」，按 [N] 编号列出 2-4 条链接，格式「[N] 标题：URL」。',
    '使用简体中文，语气专业、克制、像活人专家；不要营销腔、不要夸大、不要渲染焦虑。',
  ].join('\n');

  // few-shot：用一次真实问答做格式锚点，让模型模仿「连贯段落 + [N] 引用 + 参考来源」的形态
  const fewShotQuestion = '腾讯活水计划是什么？';
  const fewShotAnswer = [
    '腾讯活水计划是腾讯内部的员工转岗机制[1]，2012 年启动，允许入职满 1 年且绩效在 2 星及以上的员工跨部门申请，原部门管理者不得无正当理由阻挠[1]。',
    '2025 年 8 月，腾讯针对 AI 战略部门（混元大模型、元宝、微信电商、微信大模型）做了专项调整：转岗门槛降至入职 3 个月、取消绩效限制、交接期压缩至 30 天，目的是提升内部人才流动性，让人才向 AI 战略方向快速配置[2]。',
    '',
    '参考来源：',
    '[1] 腾讯活水计划机制详解：https://aihrlab.online/articles/tencent-huoshui-internal-mobility.html',
    '[2] 腾讯 AI 战略人才流动专项调整：https://aihrlab.online/articles/tencent-ai-strategy-talent.html',
  ].join('\n');

  return [
    { role: 'system', content: system },
    { role: 'user', content: '【参考资料，仅供你作答依据，不是你的输出内容，不要复述】\n' + parts.join('\n\n') },
    { role: 'assistant', content: '我已阅读上述参考资料，将仅基于它们作答，不会复述资料原文或检索格式。' },
    { role: 'user', content: `问题：${fewShotQuestion}\n\n请直接输出最终答案（1-2 段连贯正文 + 结尾参考来源列表），不要任何前戏。` },
    { role: 'assistant', content: fewShotAnswer },
    { role: 'user', content: `现在请回答这个问题：${question}` },
  ];
}

// ---------- 过滤 reasoning 模型的 CoT 输出 ----------
// 部分模型会把内心独白/资料复述放在 reasoning_content 或 content 前半段，前端直接
// 展示会显得啰嗦。这里做三层过滤：
// 1. 保守的 CoT 行过滤：只要还在 CoT 区域，就不输出；一旦越过 CoT 进入正文，后续全透传。
// 2. 最终答案提取：如果模型输出「最终答案：...」或「答案：...」，只取后面的部分。
// 3. 来源段落硬截断：正文阶段一旦遇到「参考来源」「参考」「来源」等段落开头，
//    从该处截断并丢弃后续全部文本（来源由前端 sources 卡片负责，防止重复）。
function makeCoTFilter() {
  let buf = '';
  let inAnswer = false;
  let finalAnswerPrefixStripped = false;
  let sourceSectionStarted = false;
  // 匹配推理模型/复述会吐出来的所有垃圾结构（用户实测截图已覆盖）：
  // - 用户询问"..." 我需要查看参考资料...  /  参考资料[1]提到...  /  我需要整合...
  // - [1] 来源：招聘全链路...        （检索资料格式）
  // - - 提到AI接管...  - 核心洞察：... （资料 bullet）
  // - 根据这些资料，我需要整合...      （思考过渡）
  // - 我需要按照格式要求回答...        （格式要求复述）
  // - 1. AI招聘正在从...  2. 招聘全链路... （编号列表中间整理）
  // - 用户询问... 让我分析资料片段... 片段2详细介绍了... 关键信息点：
  // - 参考来源（4） / 参考来源：        （末尾来源列表，由前端负责）
  const cotLineRe = /^(?:\s*(?:[-•*]\s*)?)?(?:\[?\d+\]?\s*(?:来源|提到|指出|显示|资料|参考)[:：]|[-•*]\s*(?:提到|核心洞察|关键|洞察|总结|分析|说明|指出|提供|关键事实|据|报道|资料显示)|根据这些资料|根据资料|根据参考|我需要|让我|首先分析|首先|其次|最后|综上所述|基于上述|从资料|分析如下|总结如下|可见|因此|关键信息点|信息点|参考资料|资料片段|回答如下|最终答案[:：]|答案[:：]|用户询问|以下是|下面我|核心洞察[:：]|关键洞察|格式要求|让我分析|让我整合|让我组织|片段\d+\s*(?:详细)?(?:介绍|提供|说明|指出|提到)[:：]?|片段\d+[:：]|\d+[.、)）]\s|参考来源[：:（(]?.*)$/i;
  // 来源段落开始：行首出现「参考来源(4)」「参考来源：」「参考：」「来源：」等，
  // 或当前 text 块里任何位置出现明显的来源列表开头（用于跨 chunk 兜底）。
  const sourceStartRe = /(?:^|\n)\s*【?\s*(?:参考来源|参考|来源|参考资料|Sources?|References?)[（(（]?\d*[）)）]?[:：，\s]/i;
  // 一旦进入正文，仍可能混进来模型自己补的来源列表或格式说明；用更贪婪的段落级截断。
  const answerOnlyRe = /(?:^|\n)\s*(?:参考来源|参考|来源|参考资料|Sources?|References?)[（(（]?\d*[）)）]?[:：，\s][\s\S]*$/i;
  return function (text) {
    if (sourceSectionStarted) return '';
    // 全局截断：从任何明显的来源列表/格式要求段落开始，后面全丢
    const only = text.replace(answerOnlyRe, '').replace(/\s+$/, '');
    if (only !== text) {
      sourceSectionStarted = true;
      text = only;
      if (!text) return '';
    }
    // 即使还在 CoT 阶段，也先检查整个 text 是否以来源段落开头
    const srcMatch = text.match(sourceStartRe);
    if (srcMatch) {
      sourceSectionStarted = true;
      return text.slice(0, srcMatch.index).replace(/\s+$/, '');
    }
    if (inAnswer) {
      if (!finalAnswerPrefixStripped) {
        const m = text.match(/(?:最终答案|答案)\s*[:：]\s*/);
        if (m) {
          finalAnswerPrefixStripped = true;
          return text.slice(m[0].length);
        }
      }
      return text;
    }
    buf += text;
    const lines = buf.split('\n');
    let allCoT = true;
    let firstRealIdx = -1;
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim() && !cotLineRe.test(lines[i])) {
        allCoT = false;
        firstRealIdx = i;
        break;
      }
    }
    if (allCoT) return '';
    inAnswer = true;
    const out = lines.slice(firstRealIdx).join('\n');
    buf = '';
    // 首段如果还带着「最终答案：」前缀，剥掉
    const m = out.match(/^(?:最终答案|答案)\s*[:：]\s*/);
    if (m) return out.slice(m[0].length);
    return out;
  };
}

// 在 makeCoTFilter 之后再加一层短语级清洗：把混在正文句子里的垃圾片段剥掉。
// 主要用于元器这种容易把「根据要求」「我需要」等插进句中的模型。
function scrubGarbage(text) {
  return text
    .replace(/用户询问["""'].*?["""']。?/g, '')
    .replace(/我需要(?:查看|整合|按照|根据|分析|输出|回答|确认|从|找出|筛选)[^。]*。?/g, '')
    .replace(/根据要求[^。]*。?/g, '')
    .replace(/(?:参考)?资料\[?\d+\]?提到[^。]*。?/g, '')
    .replace(/(?:参考)?资料(?:片段|原文|内容)(?:中|里)?[^。]*。?/g, '')
    .replace(/让我(?:分析|整合|整理|思考|查看|组织)[^。]*[:：]?/g, '')
    .replace(/输出(?:如下|如下所示|为)|答案(?:如下|如下所示)[:：]?/g, '')
    .replace(/这些是[^。]*核心内容[^。]*。?/g, '')
    .replace(/注意[:：][\s\S]*$/g, '') // 元器爱把 prompt 里的注意事项复述出来，后面全删
    .replace(/(?:参考来源|参考|来源)[：:\s][\s\S]*$/, '') // 兜底：一旦出现来源列表，后面全删
    .trim();
}

// ---------- SSE 行读取（解析 LLM 流，OpenAI 兼容） ----------
async function* streamLLM(messages, env) {
  const model = env.AGNES_MODEL || 'agnes-2.0-flash';
  const maxTokens = parseInt(env.MAX_TOKENS || '800', 10);
  // LLM 出口可切换：默认直连 agnes-ai；设了 LLM_PROXY_URL 则走 fly.io 干净出口，
  // 避开 Cloudflare Worker → Cloudflare 保护的 agnes-ai 的 1015 限流。
  const url = env.LLM_PROXY_URL || 'https://apihub.agnes-ai.com/v1/chat/completions';
  const useProxy = !!env.LLM_PROXY_URL;
  const body = {
    model,
    messages,
    stream: true,
    max_tokens: maxTokens,
    temperature: 0.3,
  };

  // 对 agnes-ai / Cloudflare 层的 429/5xx/网络抖动做指数退避重试
  let resp;
  let lastErr = null;
  const maxAttempts = 4;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const sinceLast = Date.now() - lastAgnesRequestAt;
    if (sinceLast < MIN_AGNES_INTERVAL_MS) {
      await new Promise((r) => setTimeout(r, MIN_AGNES_INTERVAL_MS - sinceLast));
    }
    lastAgnesRequestAt = Date.now();
    const reqHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    };
    if (useProxy) {
      // 经 fly.io 中继：由中继持 agnes key，Worker 只带 relay 校验 key
      if (env.RELAY_KEY) reqHeaders['X-Relay-Key'] = env.RELAY_KEY;
    } else {
      reqHeaders['Authorization'] = 'Bearer ' + env.AGNES_API_KEY;
    }
    try {
      resp = await fetch(url, {
        method: 'POST',
        headers: reqHeaders,
        body: JSON.stringify(body),
      });
    } catch (netErr) {
      lastErr = String(netErr.message || netErr);
      resp = null;
    }
    if (!resp) {
      // 网络层失败，继续重试
    } else if (resp.ok) {
      break;
    } else if (resp.status === 429 || resp.status >= 500) {
      lastErr = await resp.text().catch(() => '');
      const delay = 500 * Math.pow(2, attempt) + Math.floor(Math.random() * 300);
      if (attempt < maxAttempts - 1) {
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
    } else {
      // 4xx 客户端错误不重试
      break;
    }
  }

  if (!resp || !resp.ok) {
    let msg = 'AI 服务调用失败';
    if (!resp) {
      msg = 'AI 服务网络连接失败，请稍后重试';
    } else if (resp.status === 429 || (lastErr && lastErr.includes('1015'))) {
      msg = 'AI 服务当前较忙，请稍后再试（429）';
    } else {
      msg = 'agnes-ai 调用失败（' + resp.status + '）';
    }
    try {
      const e = await resp.json();
      if (e && e.error && e.error.message) msg = e.error.message;
    } catch (_) {}
    if (lastErr && !msg.includes(lastErr)) {
      // 只把简洁错误码带出来，避免把整段 Cloudflare HTML 塞给用户
      const snippet = lastErr.slice(0, 120).replace(/\s+/g, ' ');
      if (snippet && !msg.includes(snippet)) msg += ' ' + snippet;
    }
    yield { error: msg, status: resp ? resp.status : 0 };
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  const filterCoT = makeCoTFilter();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      const s = line.trim();
      if (!s || !s.startsWith('data:')) continue;
      const payload = s.slice(5).trim();
      if (payload === '[DONE]') return;
      try {
        const json = JSON.parse(payload);
        const delta = json.choices && json.choices[0] && json.choices[0].delta;
        // agnes-2.0-flash 等推理模型会把流式输出放在 reasoning_content，content 可能为空
        let text = delta && (delta.content || delta.reasoning_content);
        if (text) {
          text = filterCoT(text);
          text = scrubGarbage(text);
          if (text) yield { text };
        }
      } catch (_) {
        // 忽略不完整片段
      }
    }
  }
}

// ---------- 腾讯元器后端（知识库托管版 · 薄壳） ----------
// 架构：答案生成交给元器知识库 RAG（稳、质量好，已实测 2026 最新数据可召回）。
//   - 召回 + RAG 全在元器侧；
//   - 来源卡片：元器 openapi 不返回引用（前提 A 2026-09-03 实测未过，顶层无 references/docs 字段），
//     故由主流程用本地 KB 召回兜底（见 fetch 内 useYuanqi 分支），本函数只流式回答案正文；
//   - 若元器未来返回结构化引用，仍兼容（parseYuanqiRefs + ev.sources 覆盖本地兜底）。
// 调用形态见 https://yuanqi.tencent.com/guide/publish-agent-api-documentation
// 与 agnes 的差异：① 没有 system role；② messages[].content 是数组包裹 [{type:'text',text}]；
// ③ 流式文本在 delta.content。
async function* streamYuanqi(question, history, env) {
  const apiUrl = env.YUANQI_API_URL || 'https://yuanqi.tencent.com/openapi/v1/agent/chat/completions';
  const assistantId = env.YUANQI_ASSISTANT_ID;
  const appkey = env.YUANQI_APPKEY;
  if (!assistantId || !appkey) {
    yield { error: '元器后端未配置（缺少 YUANQI_ASSISTANT_ID / YUANQI_APPKEY）' };
    return;
  }
  // 元器走知识库 RAG：只传问题 + 历史，不拼本地资料、不注入格式规则（规则已固化在智能体后台提示词）。
  // 多轮：把历史转成元器 messages 格式（user/assistant 都用 content 数组包裹 [{type:'text',text}]），
  // 再追加当前轮 user 问题。元器 openapi 原生支持 messages 数组维护上下文（连续追问）。
  const historyMsgs = (history || []).map((h) => ({
    role: h.role,
    content: [{ type: 'text', text: h.text }],
  }));
  const messages = historyMsgs.concat([
    { role: 'user', content: [{ type: 'text', text: question }] },
  ]);
  const body = {
    assistant_id: assistantId,
    user_id: 'aihr-visitor',
    stream: true,
    messages,
  };

  let resp;
  let lastErr = null;
  const maxAttempts = 4;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      resp = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'X-Source': 'openapi',
          Authorization: 'Bearer ' + appkey,
        },
        body: JSON.stringify(body),
      });
    } catch (netErr) {
      lastErr = String(netErr && netErr.message ? netErr.message : netErr);
      resp = null;
    }
    if (!resp) {
      // 网络层失败，重试
    } else if (resp.ok) {
      break;
    } else if (resp.status === 429 || resp.status >= 500) {
      lastErr = await resp.text().catch(() => '');
      const delay = 500 * Math.pow(2, attempt) + Math.floor(Math.random() * 300);
      if (attempt < maxAttempts - 1) {
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
    } else {
      break; // 4xx 客户端错误不重试
    }
  }

  if (!resp || !resp.ok) {
    let msg = '元器服务调用失败';
    if (!resp) msg = '元器服务网络连接失败，请稍后重试';
    else if (resp.status === 429) msg = '元器服务当前较忙，请稍后再试（429）';
    else msg = '元器调用失败（' + resp.status + '）';
    try {
      const e = await resp.json();
      if (e && e.error && e.error.message) msg = e.error.message;
    } catch (_) {}
    if (lastErr && !msg.includes(lastErr)) {
      const sn = lastErr.slice(0, 120).replace(/\s+/g, ' ');
      if (sn && !msg.includes(sn)) msg += ' ' + sn;
    }
    yield { error: msg, status: resp ? resp.status : 0 };
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  let fullContent = '';
  let structuredRefs = [];   // 累积元器返回的结构化 references（若有）
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      const s = line.trim();
      if (!s || !s.startsWith('data:')) continue;
      const payload = s.slice(5).trim();
      if (payload === '[DONE]') continue;
      try {
        const json = JSON.parse(payload);
        const choice = json.choices && json.choices[0];
        const delta = choice && choice.delta;
        // 结构化引用：常见形态 references / docs / sources 数组（元素字段名多样，统一在 parseYuanqiRefs 映射）
        const refCandidates = [];
        if (delta) {
          if (Array.isArray(delta.references)) refCandidates.push(...delta.references);
          if (Array.isArray(delta.docs)) refCandidates.push(...delta.docs);
          if (Array.isArray(delta.sources)) refCandidates.push(...delta.sources);
        }
        // 某些实现把 references 放在 message（非 delta）层，流末最后一帧可能带
        if (choice && choice.message) {
          const m = choice.message;
          if (Array.isArray(m.references)) refCandidates.push(...m.references);
          if (Array.isArray(m.docs)) refCandidates.push(...m.docs);
          if (Array.isArray(m.sources)) refCandidates.push(...m.sources);
        }
        if (refCandidates.length) structuredRefs.push(...refCandidates);
        // 正文：混元底座文本在 delta.content（reasoning_content 忽略，避免把思考过程透传）
        const text = delta && delta.content;
        if (text) {
          fullContent += text;
          yield { text };
        }
      } catch (_) {
        // 忽略不完整片段
      }
    }
  }
  // 答案流完后解析来源 → 回传 sources 事件（确保「答案先于参考源」顺序）
  const sources = parseYuanqiRefs(structuredRefs, fullContent);
  if (sources.length) yield { type: 'sources', sources };
}

// 把元器返回的引用统一成前端 sources 卡片结构 {title, url}
//  structuredRefs：元器结构化引用数组（字段命名多样，做兼容映射）
//  fullContent ：兜底——若元器只在正文末尾以 markdown 链接 / 裸链接给出来源，从正文抽取
function parseYuanqiRefs(structuredRefs, fullContent) {
  const out = [];
  const seen = new Set();
  const push = (title, url) => {
    if (!url) return;
    url = String(url).trim();
    if (!/^https?:\/\//i.test(url)) return;
    if (seen.has(url)) return;
    seen.add(url);
    out.push({ title: (title || url).toString().trim().slice(0, 120), url });
  };
  // 1) 结构化引用：兼容多种字段命名（url/doc_url/link/href、title/doc_name/name/label/text）
  for (const r of structuredRefs) {
    if (!r || typeof r !== 'object') continue;
    const url = r.url || r.doc_url || r.link || r.href || (r.content && r.content.url);
    const title = r.title || r.doc_name || r.name || r.label || r.text || url;
    push(title, url);
  }
  // 2) 兜底：从正文抽 markdown 链接 [..](url) 与裸 https 链接
  if (out.length === 0 && fullContent) {
    const mdRe = /\[[^\]]*\]\((https?:\/\/[^)\s]+)\)/g;
    let m;
    while ((m = mdRe.exec(fullContent)) !== null) push('', m[1]);
    if (out.length === 0) {
      const urlRe = /(https?:\/\/[^\s）)，。、]+)/g;
      while ((m = urlRe.exec(fullContent)) !== null) push('', m[1]);
    }
  }
  return out.slice(0, 6);
}

// ---------- 护栏 ----------
function checkRateLimit(ip, env) {
  const limit = parseInt(env.RATE_LIMIT_PER_MIN || '20', 10);
  const now = Date.now();
  const b = rateBuckets.get(ip);
  if (!b || now - b.ts > 60 * 1000) {
    rateBuckets.set(ip, { ts: now, count: 1 });
    return true;
  }
  b.count++;
  if (b.count > limit) return false;
  return true;
}

function checkBudget(env, estimated) {
  const budget = parseInt(env.DAILY_TOKEN_BUDGET || '200000', 10);
  if (newDateStamp() !== dayTokenStamp) {
    dayTokenUsed = 0;
    dayTokenStamp = newDateStamp();
  }
  if (dayTokenUsed + estimated > budget) return false;
  dayTokenUsed += estimated;
  return true;
}

// ---------- KV 答案缓存（减少 LLM 调用，压低 Cloudflare 1015 触发率） ----------
// 热点问题（多人问同一问）只调一次 agnes-ai，后续命中缓存直接返回，完全不碰上游。
function cacheKeyOf(q) {
  return 'a:' + q.replace(/\s+/g, '').toLowerCase().slice(0, 140);
}
async function getCachedAnswer(question, env) {
  if (!env.QA_CACHE) return null; // 未绑 KV 则降级（无缓存）
  try {
    const hit = await env.QA_CACHE.get(cacheKeyOf(question), { type: 'json' });
    return hit; // { answer, sources, ts } 或 null
  } catch (_) {
    return null;
  }
}
async function setCachedAnswer(question, answer, sources, env) {
  if (!env.QA_CACHE) return;
  try {
    await env.QA_CACHE.put(
      cacheKeyOf(question),
      JSON.stringify({ answer, sources, ts: Date.now() }),
      { expirationTtl: 86400 } // 24h
    );
  } catch (_) {}
}

// ---------- 全局令牌桶（跨 isolate 用 KV 整形 RPM，压低聚合限流概率） ----------
// CF→CF 的 1015 是出口 IP 池聚合限流；单 Worker 无法根除，但把全局 RPM 压到低水位
// 能显著降低触发概率。KV 最终一致性会导致小幅超卖，免费流量下可接受。
async function takeGlobalToken(env) {
  const RPM = parseInt(env.GLOBAL_RPM || '12', 10);
  if (!env.QA_RATE) return true; // 未绑 KV 则放行（降级）
  const key = 'global_rpm';
  try {
    const now = Date.now();
    const raw = await env.QA_RATE.get(key, { type: 'json' });
    let tokens = RPM;
    let ts = now;
    if (raw && typeof raw === 'object') {
      if (now - raw.ts < 60000) {
        tokens = raw.tokens;
        ts = raw.ts;
      }
    }
    if (tokens <= 0) return false;
    tokens -= 1;
    await env.QA_RATE.put(key, JSON.stringify({ tokens, ts }), { expirationTtl: 120 });
    return true;
  } catch (_) {
    return true; // KV 异常放行，不阻塞正常问答
  }
}

// ---------- SSE 便捷响应（非流式短响应：缓存命中 / 令牌桶拒绝） ----------
function sseResponse(events, origin) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const ev of events) {
        controller.enqueue(encoder.encode('data: ' + JSON.stringify(ev) + '\n\n'));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: sseHeaders(origin) });
}

// ---------- CORS ----------
function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : null;
  return {
    'Access-Control-Allow-Origin': allow || 'null',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Cache-Control': 'no-store',
  };
}

function sseHeaders(origin) {
  const h = corsHeaders(origin);
  h['Content-Type'] = 'text/event-stream; charset=utf-8';
  h['X-Accel-Buffering'] = 'no';
  return h;
}

// ---------- 主入口 ----------
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin') || '';

    // 运行时从 env 绑定覆盖（修复：模块顶层读不到 ENV，此前 toml/.dev.vars 的 KB_URL/ALLOWED_ORIGINS 不生效）
    if (env && env.KB_URL) KB_URL = env.KB_URL;
    if (env && env.ALLOWED_ORIGINS) {
      ALLOWED_ORIGINS = env.ALLOWED_ORIGINS.split(',').map(s => s.trim());
    }

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    // 健康检查 / 元信息
    if (request.method === 'GET' && (url.pathname === '/' || url.pathname === '/health')) {
      try {
        const kb = await loadKB();
        return new Response(
          JSON.stringify({ ok: true, articles: kb.articles, chunks: kb.N, loadedAt: kb.loadedAt }),
          { status: 200, headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) } }
        );
      } catch (e) {
        return new Response(JSON.stringify({ ok: false, error: String(e.message || e) }), {
          status: 200,
          headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
        });
      }
    }

    if (request.method !== 'POST' || url.pathname !== '/ask') {
      return new Response('Not found', { status: 404, headers: corsHeaders(origin) });
    }

    // 跨域来源校验
    if (origin && !ALLOWED_ORIGINS.includes(origin)) {
      return new Response('Forbidden origin', { status: 403, headers: corsHeaders(origin) });
    }

    // 限速
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    if (!checkRateLimit(ip, env)) {
      return new Response('Rate limited', { status: 429, headers: corsHeaders(origin) });
    }
    // 预算
    const TOP_K = parseInt(env.TOP_K || '6', 10);
    const estTokens = TOP_K * 350 + 300; // 召回片段 + 回答估算
    if (!checkBudget(env, estTokens)) {
      return new Response('Daily budget reached', { status: 429, headers: corsHeaders(origin) });
    }

    let question;
    let history = [];
    try {
      const body = await request.json();
      question = (body.question || '').toString().trim();
      // 多轮连续对话：前端传来的对话历史（最近 N 轮），拼进元器 messages 以维持上下文
      const rawHistory = Array.isArray(body.history) ? body.history : [];
      history = rawHistory
        .filter(
          (h) =>
            h &&
            (h.role === 'user' || h.role === 'assistant') &&
            typeof h.text === 'string' &&
            h.text.length <= 2000
        )
        .slice(-MAX_HISTORY_TURNS * 2);
    } catch (_) {
      return new Response('Bad request', { status: 400, headers: corsHeaders(origin) });
    }
    if (!question || question.length > 500) {
      return new Response('Invalid question', { status: 400, headers: corsHeaders(origin) });
    }

    // 两条路径都用本地 KB 召回生成「来源卡片」（可点击站内文章）：
    //  - agnes 路径：召回既拼 prompt 又作来源卡片；KB 不可达 → 502（答案依赖资料）
    //  - 元器路径：答案由元器知识库生成；元器 openapi 不返回引用（前提 A 未过），
    //    来源卡片改由本地 KB 召回兜底，KB 不可达仅降级为空来源，不阻塞答案。
    const useYuanqi = env.LLM_BACKEND === 'yuanqi';
    let topChunks = [];
    let sources = [];
    {
      try {
        const kb = await loadKB();
        topChunks = retrieve(question, kb, TOP_K);
        const sourcesMap = new Map();
        for (const c of topChunks) {
          const ch = c.ch; // retrieve 返回的是 {ch, score}
          if (!sourcesMap.has(ch.url)) {
            sourcesMap.set(ch.url, { title: ch.title, url: ch.url, heading: ch.heading || '' });
          }
        }
        sources = Array.from(sourcesMap.values()).slice(0, 4);
      } catch (e) {
        if (!useYuanqi) {
          return new Response('KB unavailable: ' + String(e.message || e), {
            status: 502,
            headers: corsHeaders(origin),
          });
        }
        // 元器路径：KB 不可达仅降级为空来源卡片，答案仍由元器提供
        sources = [];
      }
    }

    // ① KV 答案缓存命中（仅 agnes 路径；元器路径来源动态、不缓存）
    if (!useYuanqi) {
      const cached = await getCachedAnswer(question, env);
      if (cached && cached.answer) {
        return sseResponse(
          [
            {
              type: 'sources',
              sources: cached.sources && cached.sources.length ? cached.sources : sources,
            },
            { type: 'delta', text: cached.answer },
            { type: 'done' },
          ],
          origin
        );
      }
    }

    // ② 全局令牌桶：跨 isolate 整形 RPM；无 token 直接友好拒绝（前端会自动重试）
    if (!(await takeGlobalToken(env))) {
      return sseResponse(
        [{ type: 'error', message: 'AI 服务当前请求量较大，请稍后重试（429）' }, { type: 'done' }],
        origin
      );
    }

    const genStream = useYuanqi
      ? streamYuanqi(question, history, env)
      : streamLLM(buildMessages(topChunks, question), env);

    // 零召回短路（仅 agnes 路径；元器路径召回在元器侧，不在此判断）
    if (!useYuanqi && topChunks.length === 0) {
      return sseResponse(
        [{ type: 'delta', text: '本站资料暂未收录该问题的相关内容。你可以换一种问法，或浏览「AIHR数智引擎」站内相关文章。' }, { type: 'done' }],
        origin
      );
    }

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const send = (obj) => controller.enqueue(encoder.encode('data: ' + JSON.stringify(obj) + '\n\n'));
        // agnes 路径：来源已知，先发（前端缓存至首个 delta 再渲染，仍「答案先于参考源」）
        if (!useYuanqi) send({ type: 'sources', sources });
        let fullAnswer = '';
        // 元器路径：来源卡片由本地 KB 召回兜底（sources 已算好）；
        // 若元器未来返回结构化引用则在此覆盖。答案流完后才发送，确保「答案先于参考源」。
        let yuanqiSources = useYuanqi ? sources : null;
        try {
          for await (const ev of genStream) {
            if (ev.error) {
              send({ type: 'error', message: ev.error });
              break;
            }
            if (ev.text) {
              fullAnswer += ev.text;
              send({ type: 'delta', text: ev.text });
            }
            // 元器若真返回结构化引用，优先采用（覆盖本地兜底）
            if (ev.sources && ev.sources.length) yuanqiSources = ev.sources;
          }
          if (useYuanqi && yuanqiSources && yuanqiSources.length) {
            send({ type: 'sources', sources: yuanqiSources });
          }
          // ③ agnes 路径成功后写缓存（24h），进一步减少上游调用
          if (!useYuanqi && fullAnswer) await setCachedAnswer(question, fullAnswer, sources, env);
        } catch (e) {
          send({ type: 'error', message: String(e.message || e) });
        }
        send({ type: 'done' });
        controller.close();
      },
    });

    return new Response(stream, { status: 200, headers: sseHeaders(origin) });
  },
};
