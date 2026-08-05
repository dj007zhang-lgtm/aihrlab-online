# 公众号二维码 broken image 致命 Bug 排查与修复报告

**日期**：2026-08-05  
**报告人**：AIHR 数智引擎 · 工程化维护  
**关联 commit**：`1d22a9fa`  
**严重程度**：P0（直接影响转化入口与品牌观感）

---

## 1. 现象概述

用户在浏览文章 `https://www.aihrlab.online/articles/ai-flattening-management-guide` 时，页面底部「关注公众号」区块的二维码图片**渲染失败**，浏览器直接显示 alt 文本：

> AIHR数智引  
> 擎公众号二维  
> 码

下方 CTA 文案「扫码关注，获取完整工具与深度长文」正常显示，但二维码缺失，导致公众号转化路径断裂。

---

## 2. Debug 时间线

| 时间 | 动作 | 结果 |
|---|---|---|
| 11:17 | 收到截图反馈 | 确认页面底部 QR 图片未渲染 |
| 11:18 | 全代码库搜索 `二维码 / qrcode / wechat-qr` | 定位到 4 个实际 QR 文件 + 169 处引用 |
| 11:19 | 检查本地 QR 文件 `qrcode-wechat.webp` | 文件存在且有效（7444 bytes，WebP） |
| 11:20 | 检查远程 GitHub `main` 分支同名文件 | 远程文件同样存在且有效 |
| 11:21 | 精确比对截图中的 HTML 结构 | 发现失效的是**站点页脚** `<footer>` 内的 `<img src="/assets/images/wechat-qr.png">`，而非文章内 `article-footer-qr` 的 `/assets/images/qrcode-wechat.webp` |
| 11:22 | 验证 `/assets/images/wechat-qr.png` | **本地与远程均不存在**，404 |
| 11:23 | 扫描全站引用 | 发现 6 个 HTML 文件引用该不存在的 PNG，1 个文件引用命名不一致的 `wechat-qrcode.webp` |
| 11:24 | 还发现 2 个与 `qrcode-wechat.*` 完全重复的 `wechat-qrcode.*` 文件 | MD5 一致，属于冗余资产 |
| 11:25 | 执行修复：统一改为 `/assets/images/qrcode-wechat.webp`，删除重复文件 | 7 个 HTML 文件更新，2 个冗余文件删除 |
| 11:27 | 运行 `scripts/quality_gate.py --all` | **13/13 通过** |
| 11:28 | 原子推送 HTML 修复 + 远程删除冗余文件 | commit `1d22a9fa`，7 文件远程验证 OK |
| 11:30 | 二次验证远程资产 | 只剩 canonical `qrcode-wechat.webp`（7444 bytes），其余 404 |

---

## 3. 根因分析

### 3.1 直接原因

站点页脚（site footer）中硬编码了一张**从未存在过的图片**：

```html
<img src="/assets/images/wechat-qr.png" alt="AIHR数智引擎公众号二维码" ...>
```

浏览器请求该 URL 返回 404，因此回退显示 alt 文本，出现截图中的「文字二维码」效果。

### 3.2 深层原因

1. **命名不统一**：仓库中同时存在 `qrcode-wechat.*` 与 `wechat-qrcode.*` 两组文件，且互为重复（MD5 相同）。新页面作者无法判断哪一个是 canonical。
2. **模板漂移**：文章正文模板 `templates/article-v2.html` 使用正确的 `/assets/images/qrcode-wechat.webp`；但站点页脚没有统一模板，近期新页面复制页脚时写错为 `wechat-qr.png`。
3. **无静态资源引用检查**：13 道质量门未覆盖「引用的图片/静态资源是否真实存在」，导致 404 图片进入生产环境。
4. **无单一名片资产**：公众号二维码作为关键转化资产，没有唯一的文件名与存放规范，造成多头引用。

### 3.3 影响面

- **6 篇新文章**的站点页脚 QR 全部 404。
- `about.html` 使用另一组命名 `wechat-qrcode.webp`，虽未 404，但增加维护成本。
- 冗余文件占用仓库约 49 KB（jpg+webp 各一份重复）。

---

## 4. 受影响模块清单

### 4.1 修复的文件（7 个）

| 文件 | 问题 | 修复后 |
|---|---|---|
| `articles/ai-flattening-management-guide.html` | 页脚引用 `wechat-qr.png` | `qrcode-wechat.webp` |
| `articles/ai-layoff-compliance-guide.html` | 同上 | 同上 |
| `articles/ai-performance-management.html` | 同上 | 同上 |
| `articles/ai-interview-compliance-2026.html` | 同上 | 同上 |
| `articles/ai-hr-2026-h2-outlook.html` | 同上 | 同上 |
| `articles/hr-three-pillar-ai.html` | 同上 | 同上 |
| `about.html` | 引用命名不一致的 `wechat-qrcode.webp` | `qrcode-wechat.webp` |

### 4.2 删除的冗余文件（2 个）

| 文件 | MD5 | 与 canonical 关系 |
|---|---|---|
| `assets/images/wechat-qrcode.jpg` | `b64296b5d27c80e54b049dd08f36c01c` | 与 `qrcode-wechat.jpg` 完全相同 |
| `assets/images/wechat-qrcode.webp` | `1c5ad7f5264ba436c7c5fed13dc06f16` | 与 `qrcode-wechat.webp` 完全相同 |

### 4.3 未受影响但需关注的模块

| 模块 | 说明 | 风险等级 |
|---|---|---|
| `tools/bigfive/index.html` | 使用 base64 内嵌 QR 图片 | 中（更新 QR 时需手动替换） |
| `tools/mbti/index.html` | 使用 base64 内嵌 QR 图片 | 中 |
| `tools/ai-risk-test/index.html` | 使用相对路径 `assets/qrcode_oa.jpg` | 低（文件存在） |
| `tools/dri-self-assessment.html` | 使用相对路径 `../assets/images/qrcode-wechat.webp` | 低 |
| `assets/js/main.js` | 内嵌 article-index，含 `qrcode-wechat.jpg` 引用 | 低（jpg 仍存在） |

---

## 5. 问题分布统计

```
公众号二维码相关引用总数：约 169 处
├── /assets/images/qrcode-wechat.webp  169 处  ✅ canonical
├── /assets/images/qrcode-wechat.jpg     2 处  ✅ 文件存在（可作为 fallback）
├── /assets/images/wechat-qrcode.webp    1 处  ⚠️  已统一为 canonical
├── /assets/images/wechat-qr.png         6 处  ❌ 文件不存在，已修复
├── tools/ai-risk-test/assets/qrcode_oa.jpg  1 处  ✅ 独立工具内使用
└── base64 data-URI（bigfive/mbti）      2 处  ⚠️  需手动维护

实际 QR 文件：
├── assets/images/qrcode-wechat.webp  7444 bytes  ✅ 保留
├── assets/images/qrcode-wechat.jpg  41816 bytes  ✅ 保留（fallback）
├── assets/images/wechat-qrcode.webp  7444 bytes  ❌ 已删除（重复）
└── assets/images/wechat-qrcode.jpg  41816 bytes  ❌ 已删除（重复）
```

---

## 6. 修复验证

### 6.1 本地验证

```bash
python3 scripts/quality_gate.py --all
# → 13/13 通过 🟢
```

### 6.2 远程验证

- commit `1d22a9fa` 已推送至 `main`。
- 7 个修复文件均远程验证包含 `qrcode-wechat.webp`。
- 远程只剩 canonical `qrcode-wechat.webp`（7444 bytes），其余 3 个问题文件均为 404。

---

## 7. 后续规避策略

### 7.1 立即执行（本周）

1. **新增质量门 Gate 14**：静态资源存在性检查。
   - 扫描所有 HTML/CSS/JS 中的 `src` / `url()` / `href`（图片、字体、CSS、JS）。
   - 检查引用的相对路径文件是否真实存在于磁盘。
   - 对 `wechat-qr.png` 等历史错误路径加入 deny-list，防止回潮。
2. **统一 QR 资产规范**：
   - Canonical 路径：`/assets/images/qrcode-wechat.webp`
   - Fallback 路径：`/assets/images/qrcode-wechat.jpg`
   - 禁止新增 `wechat-qrcode.*`、`wechat-qr.*` 等命名。
3. **模板收敛**：将站点页脚的 QR 区块抽入统一 include / 模板片段，避免各页面手写路径。

### 7.2 中期（本月）

1. **base64 QR 替换**：`tools/bigfive/index.html` 与 `tools/mbti/index.html` 当前使用 base64 内嵌，建议改为引用 canonical 外部文件，减少 HTML 体积并统一维护。
2. **图片完整性 CI**：在 GitHub Actions 中增加 `find-broken-assets` 步骤，push 前自动拦截 404 资源。
3. **资产去重脚本**：定期扫描 `assets/images` 下 MD5 重复文件并提示清理。

### 7.3 长期

1. **建立「关键转化资产清单」**：二维码、logo、核心 CSS/JS 等必须唯一命名、单点维护。
2. **视觉回归测试**：对文章页、首页、about 页做截图对比，关键 CTA 区域（含二维码）必须命中像素存在检测。
3. **监控告警**：在 404 日志（或百度统计/Google Analytics）中监控 `/assets/images/*.png` 等图片 404，触发即时告警。

---

## 8. 经验教训

- **小资产也能致命**：一个 7 KB 的二维码图片 404，直接切断公众号转化路径，且影响品牌专业感。
- **命名即契约**：当同一资产出现多种命名时，出错只是时间问题。必须指定 canonical 文件名并写入检查。
- **页脚也是产品**：站点页脚与文章正文同样面向用户，应纳入与正文同等级的质量门检查。
- **13 门质量门仍有盲区**：本次事件说明需要补充静态资源存在性检查，而非仅关注 HTML 结构与内容质量。

---

## 9. 附录：关键命令与输出

### 9.1 发现 broken 引用的扫描脚本

```bash
python3 - <<'PY'
import re, os
from pathlib import Path
refs = {}
for ext in ['html','css','js']:
    for p in Path('.').rglob(f'*.{ext}'):
        if 'node_modules' in str(p): continue
        txt = p.read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r'(?:src|url)\s*=\s*["\']([^"\']*(?:qr|wechat)[^"\']*)["\']', txt, re.I):
            refs.setdefault(m.group(1), []).append(str(p))
for ref in sorted(refs):
    if not ref.startswith('/') or os.path.exists(ref.lstrip('/')): continue
    print('BROKEN:', ref, 'in', len(refs[ref]), 'files')
PY
```

### 9.2 修复命令摘要

```bash
# 1. 统一 7 个 HTML 中的 QR 引用为 canonical webp
# 2. 删除本地重复文件 wechat-qrcode.jpg / wechat-qrcode.webp
# 3. 远程删除同名重复文件
# 4. 原子推送 7 个 HTML 文件
# 5. 运行 quality_gate.py --all（13/13 通过）
```

---

**结论**：本次二维码失效问题已修复，全站 QR 引用已统一至 `/assets/images/qrcode-wechat.webp`，冗余重复文件已清理，13 道质量门全部通过并已原子推送至 `main`。建议本周内新增 Gate 14 静态资源存在性检查，防止类似问题再次发生。
