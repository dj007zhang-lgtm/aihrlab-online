# 部署 AIHR 问答中继到腾讯云 SCF（Web 函数）

## 为什么是 SCF
原 Cloudflare Workers 的 `*.workers.dev` 子域在中国网络被 RST/连接关闭，且 `aihrlab.online` 托管在 DNSPod（腾讯），无法走 Cloudflare 自定义域。
SCF Web 函数是真 HTTP 服务，原生支持 SSE 流式；函数 URL 可绑自定义域 `qa.aihrlab.online`，全程腾讯基础设施，国内可达、稳定，且主站 DNS（GitHub Pages）完全不动。

## 本地自测（已通过）
```bash
cd assets/qa/scf
chmod +x scf_bootstrap
PORT=9100 YUANQI_ASSISTANT_ID=2095344629909220416 \
  YUANQI_APPKEY=<YUANQI_APPKEY_FROM_CONSOLE> node index.js
# 另开终端：
curl -s http://127.0.0.1:9100/health
curl -N -X POST http://127.0.0.1:9100/ask -H 'Content-Type: application/json' \
  -d '{"question":"腾讯活水计划","history":[]}'
```

## 云端部署步骤
1. **打包**（在本目录执行，确保 `scf_bootstrap` 有可执行位）：
   ```bash
   cd assets/qa/scf
   chmod +x scf_bootstrap
   zip -r ../aihr-qa-scf.zip index.js scf_bootstrap kb.json package.json
   ```
2. **建函数**：腾讯云控制台 → 云函数 SCF → 新建「**Web 函数**」→ 运行环境选 **Node.js 18** → 上传上面的 `aihr-qa-scf.zip`。
   - 启动命令保持默认（SCF 会自动执行包内的 `scf_bootstrap`）；若要求手动指定，填 `bash scf_bootstrap`。
3. **环境变量**（函数配置 → 环境变量）：
   | Key | Value |
   |---|---|
   | `YUANQI_ASSISTANT_ID` | `2095344629909220416` |
   | `YUANQI_APPKEY` | `<YUANQI_APPKEY_FROM_CONSOLE>`（机密，勿外泄；以元器后台「API管理」当前显示的为准） |
   | `YUANQI_API_URL` | 留空（默认 `https://yuanqi.tencent.com/openapi/v1/agent/chat/completions`） |
   | `TOP_K` | 留空（默认 6） |
   | `PORT` | 留空（SCF 注入 9000） |
4. **函数 URL**：函数配置 → 触发管理 → 开启「函数 URL」，拿到形如 `https://<id>.apigw.tencentcs.com/...` 的地址，先 `curl` 验证（见下）。
5. **绑自定义域**：函数 URL → 自定义域名 → 添加 `qa.aihrlab.online`。
   - SCF 会给你一个 CNAME 目标（通常形如 `<function-id>.apigw.tencentcs.com`）；
   - 到 **DNSPod** 给 `qa.aihrlab.online` 加一条 **CNAME** 记录指向该目标；
   - 等待 DNS 生效（几分钟到几小时）。
6. **改前端端点**：把 `assets/js/qa-config.js` 里的 `AIHR_QA_ENDPOINT` 改为
   `https://qa.aihrlab.online/ask`，然后 `git` 推（见下方「最终上线顺序」）。

## 验证
```bash
curl -s https://qa.aihrlab.online/health
# 期望：{"ok":true,"articles":222,"chunks":2089}

curl -N -X POST https://qa.aihrlab.online/ask -H 'Content-Type: application/json' \
  -d '{"question":"腾讯活水计划"}'
# 期望：流式 data: {"type":"delta","text":...} → data: {"type":"sources",...} → data: {"type":"done"}
```

## 最终上线顺序（与前端发布配合）
1. 完成上面 SCF 部署 + 自定义域 `qa.aihrlab.online` 生效。
2. 改 `assets/js/qa-config.js` 端点为 `https://qa.aihrlab.online/ask`。
3. 原子推送 `qa-config.js`（及此前未推的 `search.js` / `widget.js` / `kb.json` 若需更新）。
4. 等 GitHub Pages 刷新 + 强刷首页验证「问 AI」。

## 运维注意
- **内容更新**：`kb.json` 由 `scripts/build_qa_kb.py` 生成（源在 `assets/qa/kb.json`）。
  站内新增文章后，需重新生成 `kb.json` 并**重新打包部署 SCF**（SCF 不自动拉取）。
- **冷启动**：首请求会读 kb.json 建索引（2MB，约百毫秒级），之后内存常驻。
- **密钥轮换**：若 `av1gm9S...` 泄露或元器后台重置，仅在 SCF 环境变量改 `YUANQI_APPKEY` 即可，前端无需改动。
- **降级**：元器不可达时返回友好错误事件，来源卡片照常由本地 KB 兜底发送，不丢引用。
