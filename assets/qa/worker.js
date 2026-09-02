/**
 * AIHR 数智引擎 · 站内知识库问答中继（Cloudflare Worker）
 * ------------------------------------------------------------------
 * 职责：纯静态 GitHub Pages 站没有后端，本 Worker 充当「无服务器中继」：
 *   1. 冷启动拉取并内存缓存知识库 assets/qa/kb.json（构建期由 build_qa_kb.py 生成）
 *   2. 中文 bigram + BM25 召回与用户问题最相关的 top-k 段落（标题/标签/类目加权）
 *   3. 组装「仅依据资料、未知则答未收录、返回引用 URL」的系统提示词
 *   4. SSE 流式转发 agnes-ai chat 接口，回传 answer + sources
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

// 内存态知识库（同一 isolate 复用，冷启动后常驻）
let KB = null;
const KB_TTL_MS = 60 * 60 * 1000; // 1 小时，过后下次请求重新拉取

// 限速 / 预算（best-effort：依赖 isolate 复用；如需持久可接入 Workers KV）
const rateBuckets = new Map(); // ip -> {ts, count}
let dayTokenUsed = 0;
let dayTokenStamp = newDateStamp();

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
// 把资料放在 user message 里，system 只放角色与硬规则。实测若资料放在 system
// prompt 中，模型容易把「复述片段」当成答案；拆到 user message 后更听话。
function buildMessages(chunks, question) {
  const parts = chunks.map((c, i) => {
    const ch = c.ch; // retrieve 返回的是 {ch, score}
    const heading = ch.heading ? `（小节：${ch.heading}）` : '';
    return `[${i + 1}] 来源：${ch.title}｜${ch.url}${heading ? '｜' + heading : ''}\n${ch.text}`;
  });
  const system = [
    '你是「AIHR数智引擎」网站的知识库问答助手，由资深 HR/OD 专家视角作答。',
    '你只能依据用户提供的「参考资料」作答，不得编造事实、数据或结论，不得引入资料之外的信息。',
    '若参考资料中完全没有相关信息，明确回答：「本站资料暂未收录该问题的相关内容」，并建议换一种问法或留言补充。',
    '若参考资料中有相关信息，必须直接给出整合后的最终答案，不要复述资料、不要罗列片段、不要输出思考过程。',
    '使用简体中文，语气专业、克制、像活人专家；不要营销腔、不要夸大、不要渲染焦虑、不要使用对称排比等 AI 腔。',
    '回答要有信息密度，直给结论与依据，避免空泛铺垫。',
  ].join('\n');
  const user = [
    `问题：${question}`,
    '',
    '参考资料（按相关度排序，已提供来源编号 [1]、[2]…，直接基于它们回答）：',
    parts.join('\n\n'),
    '',
    '回答格式要求（必须遵守）：',
    '1. 用编号列表组织最终答案（1. 2. 3. …），每一点讲清楚一个观点或事实。',
    '2. 每个观点或关键事实后用 [N] 标注来源编号，与参考资料中的 [N] 一一对应（例如「腾讯活水计划 2012 年启动[1]」「2025 年 8 月门槛降至 3 个月[2]」）。',
    '3. 不要复述「片段N详细介绍了…」「关键信息点」等中间结构；直接输出最终答案本身。',
    '4. 答案正文结束后，另起一行写「参考来源：」，按 [N] 编号列出 2-4 条参考链接，格式：「[N] 标题：https://…URL」。',
  ].join('\n');
  return { system, user };
}

// ---------- 过滤 reasoning 模型的 CoT 输出 ----------
// 部分模型会把内心独白/资料复述放在 reasoning_content 或 content 前半段，前端直接
// 展示会显得啰嗦。这里做两层过滤：
// 1. 保守的 CoT 行过滤：只要还在 CoT 区域，就不输出；一旦越过 CoT 进入正文，后续全透传。
// 2. 最终答案提取：如果模型输出「最终答案：...」或「答案：...」，只取后面的部分。
function makeCoTFilter() {
  let buf = '';
  let inAnswer = false;
  let finalAnswerPrefixStripped = false;
  // 匹配用户截图里出现的 CoT/复述结构：
  // - 片段2详细介绍了...
  // 片段2详细介绍了...
  // 关键信息点：
  // 我需要整合...
  // 用户询问...
  const cotLineRe = /^\s*(?:[-•*]\s*)?(?:用户|让我|我需要|我首先|首先|接下来|然后|最后|综上所述|基于|从|分析|总结|可见|因此|关键信息点|信息点|参考资料|资料片段|回答如下|最终答案[:：]|答案[:：]|片段\d+\s*(?:详细)?(?:介绍|提供|说明|指出|提到)[:：]?|片段\d+[:：]).*$/;
  return function (text) {
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

// ---------- SSE 行读取（解析 LLM 流，OpenAI 兼容） ----------
async function* streamLLM(messages, env) {
  const model = env.AGNES_MODEL || 'agnes-2.0-flash';
  const maxTokens = parseInt(env.MAX_TOKENS || '800', 10);
  const url = 'https://apihub.agnes-ai.com/v1/chat/completions';
  const body = {
    model,
    messages,
    stream: true,
    max_tokens: maxTokens,
    temperature: 0.3,
  };

  // 对 agnes-ai 的 429 做一次退避重试（Cloudflare Worker IP 池可能触发瞬时限流）
  let resp;
  let lastErr = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        Authorization: 'Bearer ' + env.AGNES_API_KEY,
      },
      body: JSON.stringify(body),
    });
    if (resp.ok || resp.status !== 429) break;
    lastErr = await resp.text().catch(() => '');
    if (attempt === 0) {
      await new Promise((r) => setTimeout(r, 800));
    }
  }

  if (!resp.ok) {
    let msg = 'agnes-ai 调用失败（' + resp.status + '）';
    try {
      const e = await resp.json();
      if (e && e.error && e.error.message) msg = e.error.message;
    } catch (_) {}
    if (lastErr && !msg.includes(lastErr)) msg += ' ' + lastErr.slice(0, 200);
    yield { error: msg, status: resp.status };
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
          if (text) yield { text };
        }
      } catch (_) {
        // 忽略不完整片段
      }
    }
  }
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
    try {
      const body = await request.json();
      question = (body.question || '').toString().trim();
    } catch (_) {
      return new Response('Bad request', { status: 400, headers: corsHeaders(origin) });
    }
    if (!question || question.length > 500) {
      return new Response('Invalid question', { status: 400, headers: corsHeaders(origin) });
    }

    let kb;
    try {
      kb = await loadKB();
    } catch (e) {
      return new Response('KB unavailable: ' + String(e.message || e), {
        status: 502,
        headers: corsHeaders(origin),
      });
    }

    const topChunks = retrieve(question, kb, TOP_K);

    // 去重来源（用于引用展示）
    const sourcesMap = new Map();
    for (const c of topChunks) {
      const ch = c.ch; // retrieve 返回的是 {ch, score}
      if (!sourcesMap.has(ch.url)) {
        sourcesMap.set(ch.url, { title: ch.title, url: ch.url, heading: ch.heading || '' });
      }
    }
    const sources = Array.from(sourcesMap.values()).slice(0, 4);

    const messages = buildMessages(topChunks, question);

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const send = (obj) => controller.enqueue(encoder.encode('data: ' + JSON.stringify(obj) + '\n\n'));
        // 先发来源，再流回答
        send({ type: 'sources', sources });
        // 零召回短路：直接走「未收录」兜底，省一次 LLM 调用
        if (topChunks.length === 0) {
          send({
            type: 'delta',
            text: '本站资料暂未收录该问题的相关内容。你可以换一种问法，或浏览「AIHR数智引擎」站内相关文章。',
          });
          send({ type: 'done' });
          controller.close();
          return;
        }
        try {
          for await (const ev of streamLLM(messages, env)) {
            if (ev.error) {
              send({ type: 'error', message: ev.error });
              break;
            }
            if (ev.text) send({ type: 'delta', text: ev.text });
          }
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
