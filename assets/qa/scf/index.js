'use strict';
// ============================================================
// AIHR 数智引擎 · 站内问答中继（腾讯云 SCF Web 函数版）
// ------------------------------------------------------------
// 职责：纯静态 GitHub Pages 站没有后端，本函数充当「无服务器中继」。
//   - 冷启动读取并内存缓存本地打包的 kb.json（构建期由 build_qa_kb.py 生成，随包部署）
//   - 中文 bigram + BM25 召回与用户问题最相关的 top-k 段落（标题/标签/类目加权）
//   - 答案生成交给腾讯元器知识库 RAG（稳、质量好），本地 KB 兜底「来源卡片」；元器不可用时自动降级为本地资料整理作答（保证 Copilot 始终有回应）
//   - SSE 流式回传 answer(delta) + sources，前端按事件渲染
//
// 为什么迁 SCF：原 Cloudflare Workers 的 *.workers.dev 子域在中国网络被 RST/连接关闭，
//   而 aihrlab.online 域名托管在 DNSPod（腾讯），无法走 Cloudflare 自定义域。
//   SCF Web 函数是真 HTTP 服务，原生支持 SSE 流式；函数 URL 可绑自定义域 qa.aihrlab.online，
//   全程腾讯基础设施，国内可达、稳定。
//
// 部署：SCF 控制台建「Web 函数 / Node.js 18」，上传本目录（含 kb.json），
//   环境变量：YUANQI_ASSISTANT_ID / YUANQI_APPKEY（机密）/ YUANQI_API_URL（可选）/ TOP_K（可选），
//   函数 URL 绑自定义域 qa.aihrlab.online（DNSPod 加 CNAME）。
//   详见同目录 DEPLOY-SCF.md。
// ============================================================

const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

// ---------- 配置（环境变量覆盖） ----------
const PORT = parseInt(process.env.PORT || '9000', 10);
const ALLOWED_ORIGINS = ['https://aihrlab.online', 'https://www.aihrlab.online'];
const KB_PATH = process.env.KB_PATH || path.join(__dirname, 'kb.json');
const YUANQI_API_URL =
  process.env.YUANQI_API_URL || 'https://yuanqi.tencent.com/openapi/v1/agent/chat/completions';
const ASSISTANT_ID = process.env.YUANQI_ASSISTANT_ID;
const APPKEY = process.env.YUANQI_APPKEY;
const TOP_K = parseInt(process.env.TOP_K || '6', 10);
const MAX_HISTORY_TURNS = 10;
const K1 = 1.5;
const B = 0.75;
const SITE_BASE = 'https://www.aihrlab.online';

// ---------- 生成提示词：约束元器从文章开头/核心论点讲起 ----------
// 元器知识库 RAG 容易从文章中段直接摘抄，导致答案突兀、缺少引言。
// 通过 system prompt 强制结构：先总述 → 逐篇从核心论点展开 → 引用上标。
const SYSTEM_PROMPT = `你是 AIHR 数智引擎的站内研究助手，回答需符合公众号「正念正见」风格：事实为本、清冷克制、不营销。
回答结构纪律：
1. 开头先给一句直接、克制的总述，回答用户问题本身，不要绕弯。
2. 按参考文章逐篇展开：每篇先说明它的核心问题与开头论点，再进入支撑细节；禁止直接从文章中段抛出结论。
3. 使用小标题分块，一事一议，段落之间要有清晰推进，不要堆叠摘抄。
4. 只陈述事实与因果，不夸大、不使用「必然」「颠覆」等强断言、不出现对称营销句式、不使用口号。
5. 引用站内文章时使用 [N] 上标，N 从 1 开始按参考来源顺序编号。`;

// ---------- 中文分词：CJK 二元 + ASCII 词 ----------
function tokenize(text) {
  if (!text) return [];
  const t = String(text).toLowerCase();
  const tokens = [];
  const cjkRe = /[一-鿿]+/g;
  let m;
  while ((m = cjkRe.exec(t)) !== null) {
    const run = m[0];
    for (let i = 0; i < run.length - 1; i++) tokens.push(run.substr(i, 2));
    if (run.length === 1) tokens.push(run);
  }
  const asciiRe = /[a-z0-9][a-z0-9+#.@/_\-]{1,}/g;
  while ((m = asciiRe.exec(t)) !== null) tokens.push(m[0]);
  return tokens;
}

// ---------- 加载并构建索引（内存缓存，冷启动一次） ----------
let KB = null;
function loadKB() {
  if (KB) return KB;
  const data = JSON.parse(fs.readFileSync(KB_PATH, 'utf-8'));
  const chunks = data.chunks || [];
  const df = new Map();
  let totalLen = 0;
  for (const ch of chunks) {
    const toks = tokenize(ch.text || '');
    ch._textTok = toks;
    ch._tokSet = new Set(toks);
    ch._len = toks.length;
    totalLen += toks.length;
    ch._titleTok = new Set(tokenize(ch.title || ''));
    ch._tagTok = new Set(tokenize((ch.tags || []).join(' ')));
    ch._catTok = new Set(tokenize(ch.category || ''));
    for (const tk of ch._tokSet) df.set(tk, (df.get(tk) || 0) + 1);
  }
  KB = {
    chunks,
    df,
    N: chunks.length,
    avgdl: chunks.length ? totalLen / chunks.length : 1,
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
  const qfreq = new Map();
  for (const tk of qtoks) qfreq.set(tk, (qfreq.get(tk) || 0) + 1);
  const scored = [];
  for (let idx = 0; idx < kb.chunks.length; idx++) {
    const ch = kb.chunks[idx];
    let anyMatch = false;
    for (const tk of qfreq.keys()) {
      if (ch._tokSet.has(tk)) {
        anyMatch = true;
        break;
      }
    }
    if (!anyMatch) continue;
    const arr = ch._textTok;
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
      score += idfV * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * (ch._len / kb.avgdl)));
      if (ch._titleTok.has(tk)) score += 1.5 * idfV;
      if (ch._tagTok.has(tk)) score += 0.8 * idfV;
      if (ch._catTok.has(tk)) score += 0.4 * idfV;
    }
    if (score > 0) scored.push({ ch, score, idx });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}

// 把 kb chunk 的 slug 拼成规范文章 URL
function chunkToSource(ch) {
  const raw = (ch.url || '').trim();
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw)) return { title: ch.title, url: raw };
  const slug = raw.replace(/\.html?$/i, '');
  return { title: ch.title, url: SITE_BASE + '/articles/' + slug + '.html' };
}

// 把本地召回的 top chunks 聚合成「文章标题 + 开头片段」上下文，
// 塞进元器 system/user prompt，强制它从每篇的开头论点讲起。
function buildContext(recallTop) {
  if (!recallTop || !recallTop.length) return '';
  const byArticle = new Map();
  for (const c of recallTop) {
    const ch = c.ch;
    const key = ch.slug || ch.url || ch.id || ch.title;
    if (!byArticle.has(key)) byArticle.set(key, { title: ch.title, chunks: [] });
    byArticle.get(key).chunks.push({ ch, idx: c.idx });
  }
  let ctx = '以下是你可引用的站内参考文章（按相关度排序）。回答时请从每篇的「核心问题 / 开头论点」讲起，再进入细节，禁止直接从中段抛出结论：\n\n';
  let n = 1;
  for (const art of byArticle.values()) {
    if (n > 4) break;
    // 取该文章在 kb.json 中最早出现的 chunk（即文章开头片段）
    art.chunks.sort((a, b) => a.idx - b.idx);
    const firstChunk = art.chunks[0].ch;
    let text = (firstChunk.text || '').replace(/\s+/g, ' ').trim();
    if (text.length > 280) text = text.slice(0, 280) + '…';
    ctx += `[${n}]《${art.title}》：${text}\n\n`;
    n++;
  }
  return ctx.trim();
}

// ---------- 元器流式转发 ----------
async function* streamYuanqi(question, history, recallTop) {
  if (!ASSISTANT_ID || !APPKEY) {
    yield { error: '元器后端未配置（缺少 YUANQI_ASSISTANT_ID / YUANQI_APPKEY）' };
    return;
  }
  const historyMsgs = (history || []).map((h) => ({
    role: h.role,
    content: [{ type: 'text', text: h.text }],
  }));
  // 用本地 KB 召回的 top 文章开头片段做上下文，强制元器从每篇核心论点讲起
  const ctx = buildContext(recallTop);
  const systemContent = SYSTEM_PROMPT + (ctx ? '\n\n' + ctx : '');
  const messages = [
    { role: 'system', content: [{ type: 'text', text: systemContent }] },
    ...historyMsgs,
    { role: 'user', content: [{ type: 'text', text: question }] },
  ];
  const body = {
    assistant_id: ASSISTANT_ID,
    user_id: 'aihr-visitor',
    stream: true,
    messages,
  };

  let resp;
  let lastErr = null;
  const maxAttempts = 3;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      resp = await fetch(YUANQI_API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'X-Source': 'openapi',
          Authorization: 'Bearer ' + APPKEY,
        },
        body: JSON.stringify(body),
      });
    } catch (netErr) {
      lastErr = String(netErr && netErr.message ? netErr.message : netErr);
      resp = null;
    }
    if (!resp) continue;
    if (resp.ok) break;
    if (resp.status === 429 || resp.status >= 500) {
      lastErr = await resp.text().catch(() => '');
      const delay = 500 * Math.pow(2, attempt) + Math.floor(Math.random() * 300);
      if (attempt < maxAttempts - 1) {
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
    } else {
      break;
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
    yield { error: msg };
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
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
        const delta = json.choices && json.choices[0] && json.choices[0].delta;
        const text = delta && delta.content;
        if (text) yield { text };
      } catch (_) {}
    }
  }
}

// ---------- 本地降级作答（元器不可用时） ----------
// 用召回 top chunks 聚合到文章级，拼一段「站内资料整理」答案，保证 Copilot 始终有回应。
function* localAnswer(question, top) {
  if (!top || !top.length) {
    yield '暂时没有在站内资料中找到与「' + question + '」直接相关的内容。可以换个更具体的问法，或浏览文章列表。';
    return;
  }
  yield '以下内容整理自 AIHR 数智引擎站内资料（AI 生成接口暂不可用，以下为相关原文摘录）：\n\n';
  const byArticle = new Map();
  for (const c of top) {
    const ch = c.ch;
    const key = ch.slug || ch.url || ch.id;
    if (!byArticle.has(key)) byArticle.set(key, { title: ch.title, text: ch.text });
  }
  let i = 0;
  for (const art of byArticle.values()) {
    if (i >= 4) break;
    let t = (art.text || '').replace(/\s+/g, ' ').trim();
    if (t.length > 160) t = t.slice(0, 160) + '…';
    yield '■ ' + art.title + '\n' + t + '\n\n';
    i++;
  }
}

// ---------- CORS ----------
function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : 'null';
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

// ---------- 读取请求体 ----------
function readBody(req, limit = 1e6) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (c) => {
      data += c;
      if (data.length > limit) {
        reject(new Error('body too large'));
        req.destroy();
      }
    });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

// ---------- 主服务 ----------
const server = http.createServer(async (req, res) => {
  const origin = req.headers.origin || '';
  const cors = corsHeaders(origin);

  // 预检
  if (req.method === 'OPTIONS') {
    res.writeHead(204, cors);
    res.end();
    return;
  }

  const url = new URL(req.url, 'http://localhost');

  // 健康检查 / 元信息
  if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/health')) {
    try {
      const kb = loadKB();
      res.writeHead(200, { 'Content-Type': 'application/json', ...cors });
      res.end(JSON.stringify({ ok: true, articles: kb.articles, chunks: kb.chunks.length }));
    } catch (e) {
      res.writeHead(200, { 'Content-Type': 'application/json', ...cors });
      res.end(JSON.stringify({ ok: false, error: String(e.message || e) }));
    }
    return;
  }

  if (req.method !== 'POST' || url.pathname !== '/ask') {
    res.writeHead(404, cors);
    res.end('Not found');
    return;
  }

  // 跨域来源校验
  if (origin && !ALLOWED_ORIGINS.includes(origin)) {
    res.writeHead(403, cors);
    res.end('Forbidden origin');
    return;
  }

  let body;
  try {
    body = JSON.parse(await readBody(req));
  } catch (_) {
    res.writeHead(400, cors);
    res.end('Bad request');
    return;
  }

  const question = (body.question || '').toString().trim();
  let history = Array.isArray(body.history) ? body.history : [];
  history = history
    .filter(
      (h) =>
        h &&
        (h.role === 'user' || h.role === 'assistant') &&
        typeof h.text === 'string' &&
        h.text.length <= 2000
    )
    .slice(-MAX_HISTORY_TURNS * 2);
  if (!question || question.length > 500) {
    res.writeHead(400, cors);
    res.end('Invalid question');
    return;
  }

  // SSE 响应头
  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Accel-Buffering': 'no',
    ...cors,
  });

  const send = (obj) => {
    res.write('data: ' + JSON.stringify(obj) + '\n\n');
    if (res.flush) res.flush();
  };

  // 本地 KB 召回（既用于来源卡片，也用于元器不可用时的降级作答）
  let sources = [];
  let recallTop = [];
  try {
    const kb = loadKB();
    const top = retrieve(question, kb, TOP_K);
    recallTop = top;
    const seen = new Set();
    for (const c of top) {
      const src = chunkToSource(c.ch);
      if (!src) continue;
      const key = src.url;
      if (seen.has(key)) continue;
      seen.add(key);
      sources.push(src);
    }
    sources = sources.slice(0, 4);
  } catch (e) {
    sources = [];
    recallTop = [];
  }

  try {
    let degraded = false;
    for await (const ev of streamYuanqi(question, history, recallTop)) {
      if (ev.error) {
        // 元器不可用（未配置 / token 失败 / 网络异常）→ 降级为本地资料整理作答
        degraded = true;
        break;
      }
      if (ev.text) send({ type: 'delta', text: ev.text });
    }
    if (degraded) {
      for (const text of localAnswer(question, recallTop)) {
        send({ type: 'delta', text });
      }
    }
    if (sources.length) send({ type: 'sources', sources });
  } catch (e) {
    send({ type: 'error', message: '服务异常：' + String(e.message || e) });
  }
  send({ type: 'done' });
  res.end();
});

server.listen(PORT, () => {
  console.log('[AIHR-QA] listening on ' + PORT);
});
