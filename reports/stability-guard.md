# 网站稳定性自检 · 检测项清单、触发条件与处理流程

> 模块：`scripts/stability_guard.py`　|　强制关卡：发布前第二道闸门（quality_gate 之后、原子推送之前）
>
> 本文档由检测项注册表自动生成，与代码单一真相源同步。

## 一、总览

本模块拦截「会让用户秒关页面、拉高跳出率」的低级硬伤，覆盖用户反馈的
**空白页 / 加载失败 / 内容错乱 / 链接失效 / 品牌回退 / 导航错乱** 六大类。

| 编号 | 检测项 | 类别 | 严重级 | 阻断发布 |
|------|--------|------|--------|----------|
| S1-BLANK | 空白页检测 | 呈现完整性 | BLOCKER | 是 |
| S2-GARBLED | 乱码 / 编码损坏检测 | 呈现完整性 | BLOCKER | 是 |
| S3-STRUCTURE | 结构损坏检测（标签未闭合） | 内容错乱 | BLOCKER | 是 |
| S4-LEAK | 组件泄漏检测（GEO 胶囊错置） | 内容错乱 | BLOCKER | 是 |
| S5-ASSET | 资源加载失败检测 | 加载失败 | BLOCKER | 是 |
| S6-LINK | 内部链接失效检测 | 链接失效 | BLOCKER | 是 |
| S7-BRAND | 品牌色回退检测 | 专业性 | BLOCKER | 是 |
| S8-NAV | 导航顺序错乱检测 | 专业性 | BLOCKER | 是 |
| S9-INSECURE | 不安全外链检测 | 真实性 / 安全 | WARN | 否（告警） |

**严重级约定**
- `BLOCKER`：必然破坏专业形象或可用性 → 进程返回非 0，publish.py 中止推送，零远程写入。
- `WARN`：需复核但不阻断发布（如缺失导航项、http 外链）。

## 二、检测项明细（触发条件 + 处理流程）

### S1-BLANK · 空白页检测

- **类别**：呈现完整性
- **严重级**：BLOCKER
- **触发条件**：页面 <body> 可见文本（去除 script/style/标签后）非空白字符数 < 200；或主内容容器（article/main）为空。重定向桩页（含 http-equiv=refresh）豁免。
- **处理流程**：拦截发布。定位为空根因：模板未渲染 / 内容注入失败 / 批量脚本误删正文。修复后重跑，直到可见文本达标。
- **自动修复**：否（人工修复）

### S2-GARBLED · 乱码 / 编码损坏检测

- **类别**：呈现完整性
- **严重级**：BLOCKER
- **触发条件**：页面出现 Unicode 替换符（U+FFFD）或 UTF-8 被 latin1 误解码的典型残影（如 Ã© / â€ / Â° 等）。
- **处理流程**：拦截发布。根因为文件以错误编码写入（如 UTF-8 文本被按 latin1 保存/读取）。统一以 UTF-8 重写文件，重跑确认零替换符。
- **自动修复**：否（人工修复）

### S3-STRUCTURE · 结构损坏检测（标签未闭合）

- **类别**：内容错乱
- **严重级**：BLOCKER
- **触发条件**：HTML 解析后，关键容器（html/head/body/article/main/section/table/ul/ol/nav/header/footer/aside/figure/form/blockquote）在文末仍未闭合 → BLOCKER；div 开闭不平衡差 > 3 → WARN（注：桩页豁免）。
- **处理流程**：拦截发布。根因为批量 HTML 注入误删了闭合标签。用手术式注入铁律修复，重跑直到关键容器全部闭合。
- **自动修复**：否（人工修复）

### S4-LEAK · 组件泄漏检测（GEO 胶囊错置）

- **类别**：内容错乱
- **严重级**：BLOCKER
- **触发条件**：GEO 答案胶囊（geo-answer-capsule）出现在文章列表页 articles/index.html → BLOCKER；出现在其它 index.html 列表页 → WARN；胶囊正文文本 < 10 字（注入失败）→ BLOCKER。（hub / 测评内容页允许含胶囊，非泄漏。）
- **处理流程**：拦截发布。列表页不得承载文章级内容组件。删除列表页误注入的胶囊块，或补全空胶囊正文。重跑确认 articles/index.html 无胶囊。
- **自动修复**：否（人工修复）

### S5-ASSET · 资源加载失败检测

- **类别**：加载失败
- **严重级**：BLOCKER
- **触发条件**：本地 CSS（link[rel=stylesheet]）、JS（script[src]）、图片（img/source[src]、og:image、style 中 url()）引用了不存在的文件；或 src 为空。
- **处理流程**：拦截发布。缺失 CSS/JS 导致整页白屏或无样式；缺失图片破坏专业形象。补齐资源或修正路径后重跑。
- **自动修复**：否（人工修复）

### S6-LINK · 内部链接失效检测

- **类别**：链接失效
- **严重级**：BLOCKER
- **触发条件**：本地超链接（a[href] 指向站内 .html / 目录）解析后文件不存在 → BLOCKER；指向页内锚点 #id 但目标页无该 id → WARN。
- **处理流程**：拦截发布。死链直接拉高跳出率。修正链接目标或补全锚点 id 后重跑。
- **自动修复**：否（人工修复）

### S7-BRAND · 品牌色回退检测

- **类别**：专业性
- **严重级**：BLOCKER
- **触发条件**：页面内联样式或 CSS 源文件中复现旧引擎蓝 token（#228be6/#1c7ed6/#1971c2/#3b5bdb/#2f49c2/#e7f5ff/#d0ebff/#a5d8ff/#eef1fe/#f0f4fa及对应 rgba）→ BLOCKER。
- **处理流程**：拦截发布。品牌升级后任何旧蓝复现都破坏视觉一致性。可用 --autofix 按既定映射一键替换为森林绿系。
- **自动修复**：支持（--autofix）

### S8-NAV · 导航顺序错乱检测

- **类别**：专业性
- **严重级**：BLOCKER
- **触发条件**：主导航 <nav class="site-nav"> 中规范项（首页/文章/资源库/测评/策展/关于，其中「全部文章」归一为「文章」）的相对顺序被颠倒 → BLOCKER；缺失规范项 → WARN。verify / 设计系统页豁免。
- **处理流程**：拦截发布。导航顺序错乱让用户找不到入口、秒关。可用 --autofix 按规范顺序重排。重跑确认全站主导航顺序一致。
- **自动修复**：支持（--autofix）

### S9-INSECURE · 不安全外链检测

- **类别**：真实性 / 安全
- **严重级**：WARN
- **触发条件**：外链使用 http://（非 https）或 javascript: 伪协议 → WARN（不阻断发布，但须复核）。
- **处理流程**：不阻断发布，但告警。https 缺失会产生混合内容警告并损害信任；javascript: 链接多为残留脚本。逐一复核改为 https 或移除。
- **自动修复**：否（人工修复）

## 三、统一预警与拦截机制

1. **发布前强制双闸**：`publish.py` 先跑 `quality_gate.py --all`，
   通过后再跑 `stability_guard.py --all`；任一 BLOCKER → 立即中止，
   本次发布**零远程写入**，绝不带病上线。
2. **实时守护**：`python3 scripts/stability_guard.py --serve` 监听工作区
   `.html/.css` 变更，作者保存即扫，发现 BLOCKER 即时终端告警。
3. **CI 门禁**：`--json` 输出供流水线消费；BLOCKER 计数 > 0 即非零退出。
4. **误报护栏**：列表页豁免桩页（refresh）、verify 页、设计系统页；
   品牌色仅锁定 unambiguous 的旧引擎蓝 token，避免误伤中性灰。

## 四、使用命令

```bash
python3 scripts/stability_guard.py --all            # 全站扫描
python3 scripts/stability_guard.py --files a.html b.css
python3 scripts/stability_guard.py --serve          # 实时守护
python3 scripts/stability_guard.py --autofix --all   # 安全项自动修复
python3 scripts/stability_guard.py --json --all     # CI 机器可读
```
