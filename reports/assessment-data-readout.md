# 测评数据读数链（口径与操作）

**建立日**：2026-11-05　**归属**：测评完成事件 `assessment_complete` 上线配套
**配套脚本**：`scripts/assessment_readout.py`　**事件字典**：`reports/events.md`

---

## 一、上线前的事实（先把话说死）

在 2026-11-05 之前，站点**没有「多少用户做完测评」这个度量**：

| 曾被认为是数据 | 实际是什么 | 能不能当完成人数 |
|---|---|---|
| 测评结果写进 `localStorage` | 只存在用户自己浏览器，服务端零回传 | 不能 |
| 事件字典里的 `assessment_start` | 站内点击 → `/tools/` 的点击数，不是开始答题，更不是完成 | 不能 |
| GA4 旧窗口（2026-07-20~08-16）测评页 24 次浏览 | 页面浏览量；15 是各页活跃用户**之和**、非去重 | 不能 |
| 百度统计既有导出 | 只有来源 / 搜索词 / 新老访客 / 外部链接 / 入口页面 / 网站概况，**没有事件分析** | 不能 |
| `reports/assessment-matrix-audit-2026-09-25.md` 的「匿名数据资产化」 | 报告里明确写的是**理论状态，未落地** | 不能 |

**历史完成数无法回溯**。埋点上线前的行为从未上报，任何后台导出都不会包含。本次建设拿到的是「从上线那一刻起的新数据」，不是补一份历史台账。

---

## 二、已建好的链路

```
8 套 tools/ 测评页
  → 结果生成时机调用 window.aihrAssessmentComplete(id, type, runKey)
  → assets/js/assessment-tracking.js 清洗类别 + 会话内去重
  → window.aihrTrack('assessment_complete', { label: '<ID>:<类别>' })
  → 百度统计 _hmt.push(['_trackEvent', 'conversion', 'assessment_complete', label])
  → 百度统计「访问分析 → 事件分析」按 label 分组
  → scripts/assessment_readout.py 读导出 CSV → 完成次数 + 类型分布
```

零后端、零数据库、不采答卷、不采分数明细、不采用户标识。`aihrTrack` 同时双发 GA4，但 **CN 访客真相源是百度统计**，两份数据不可同框比较。

### 8 套测评的匿名类别口径

| 测评 ID | 结果类别来源 | 是否参与类型分布 |
|---|---|---|
| `bigfive` | `computeArchetype(results).name` 职业人格原型 | 是 |
| `disc` | `res.primary`（D/I/S/C） | 是 |
| `holland` | `res.code`（RIASEC 主导代码） | 是 |
| `mbti` | `res.type`（如 INTJ） | 是 |
| `dri-quiz` | `L0`–`L3` 四档（按 pct 分档，不传分数） | 是 |
| `dri-self` | `leader` / `explorer` / `awakening` / `start` 四档 | 是 |
| `ai-risk` | 固定 `completed` | **否**，只计完成次数 |
| `tarot` | 固定 `completed` | **否**，只计完成次数 |

后两套没有稳定可枚举的结果类别，硬造一个只会把噪声当分布，因此只贡献完成数。`dri` 两档刻意用档位码而非原始分数：档位是可枚举的匿名类别，分数是明细，后者不采。

### 去重口径

同一浏览器会话内，按 `测评ID + runKey` 只计一次，防刷新结果页 / 重复点结果按钮虚增。未传 `runKey` 时退化为结果类别（同会话同类型重做不重复计入，偏保守）；塔罗每次重新洗牌传 `GEN`，允许「再抽一次」另计。

这个口径意味着完成数是**偏保守的下界**，不是精确独立人数。对外表述用「完成次数」，不用「完成人数」。

---

## 三、你要做的一次人工动作

本地没有百度统计后台直读权限，也没有任何事件分析导出文件。上线后请导出一次：

1. 百度统计后台 →「访问分析」→「事件分析」
2. 事件类别选 `conversion`，事件动作选 `assessment_complete`
3. 展开到**事件标签（label）**层级，选一个明确起止日期的窗口
4. 导出 CSV，放进 `aihr-data-inbox/AIHR网站数据/百度统计/<窗口>/`
5. 告诉我文件路径和窗口，我跑读数脚本出结果

**首次导出必须校准列名**：目前没有真实样本，脚本用「事件标签 / label」「事件数 / 次数」「事件名称 / action」做表头匹配。若表头不同，脚本会打印真实表头并退出，用 `--label-col` / `--count-col` / `--action-col` 显式指定，**不按列位置猜数字**。校准后把实际列名补记到本节。

数据通常次日汇总，上线当天查不到是正常的，不要因此判定埋点失效。判断埋点是否生效用 `?aihr_debug=1` 看 `window.__aihrEvents`，不要用后台当日数据。

---

## 四、读数命令

```bash
# 工具自检（注入已知缺陷，须全部命中，否则工具视为失效）
python3 scripts/assessment_readout.py --self-test

# 正式读数
python3 scripts/assessment_readout.py \
  "aihr-data-inbox/AIHR网站数据/百度统计/<窗口>/事件分析.csv" \
  --window "2026-11-05~2026-11-12" \
  --out reports/assessment-data-latest.md
```

若导出已按 `assessment_complete` 筛好、表里没有事件名称列，必须显式声明：
`--assume-complete`。不加就拒绝推断。

---

## 五、口径纪律（对外汇报前逐条过）

1. **测量范围必须等于表述范围**。事件数是「次」，不是人数；`completed` 类别不进类型分布；档位码不代表分数。
2. **分母不在导出里，就不报比率**。`assessment_start` 是站内点击、`assessment_complete` 是结果生成，两者粒度不同，禁止相除算「完成率」。
3. **比率字段回算自洽**。脚本给出的「占该测评」必须能由分项次数加总回算，不能拿后台给的百分比混用。
4. **完成次数 > 测评页浏览量时先修数据**，不要直接解读为「用户反复测评」。
5. **覆盖率对账**：若某测评在站点有入口却零事件，先判是「埋点没生效」还是「窗口内确实没人完成」，不能当 0 写进结论。覆盖率 <60% 时禁用绝对量表述。
6. **不同窗口禁止同框**；>105% 判为不同窗口或不同口径，先停下对账。跨表联合只用表内相对排名。
7. **样本量 caveat**：任一测评完成次数 < 30 时，类型占比只作定性观察，不写进结论、不做趋势判断。旧窗口合计仅 24 次浏览，量级摆在这里，短期内不要期待有统计意义的分布。
8. **AI 引用与搜索是部分重叠的两个渠道**（corr(log)≈0.56），测评数据不得拿来代言任一渠道效果。

---

## 六、验收证据（2026-11-05 本地实测）

- 共享函数级：8/8 页 `window.aihrAssessmentComplete` 可用，事件名 `assessment_complete`、label 格式、params 字段、清洗（emoji/标点剔除）、会话幂等全部通过。
- 真实结果函数触发：8/8 通过。其中 `ai-risk` 走完整 20 题答题交互，第 20 次「下一题」后发出 `ai-risk:completed` 并进入结果页，无页面报错。
- 类别取值：`bigfive:定海神针TheAnchor`、`disc:D`、`holland:RIA`、`mbti:ESTJ`、`dri-quiz:L2`、`dri-self:explorer`、`tarot:completed`、`ai-risk:completed`，无 `undefined` / `unknown`。
- 门禁：质量门 22/22、稳定性 11 项、`qa_guardian` GREEN、视觉门 BLOCK 0、`check_analytics_coverage.py` A1–A7 全绿。
- 覆盖核验已从装饰性工具升为 `publish.py` STEP 2.8 阻断门；同批修复了 5 个 `brief/` 页缺统计装载、`cta_click` 字典漂移两项存量债。

> 以上全部是**本地真实结果**，不是线上真实用户数据。线上是否有完成事件、有多少，只能由百度统计导出回答。
