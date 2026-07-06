/* =====================================================================
 * AI 替代风险测评 · 计分引擎 (Scoring Engine)
 * 指数衰减风险公式 / 四大聚合指数 / 四象限分类 / 动态文案生成
 * 此文件定义 window.Engine
 * ===================================================================== */
(function () {
  'use strict';
  const D = window.APP_DATA;

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const round = Math.round;

  /* 取某维度原始得分（0-10） */
  function dim(answers, n) {
    const v = answers['dim_' + n];
    return (typeof v === 'number') ? v : 0;
  }
  /* 反向题集合：标了 reverse:true 的题目，计分前自动翻转（10 - raw） */
  const reverseSet = new Set((D.questions || []).filter(q => q.reverse).map(q => q.n));
  /* 计分时使用的得分（已处理反向题） */
  function scoreOf(answers, n) {
    let v = dim(answers, n);
    if (reverseSet.has(n)) v = 10 - v;
    return v;
  }
  /* 多个维度平均（返回 0-10，已处理反向题） */
  function avgDims(answers, ns) {
    if (!ns.length) return 0;
    const s = ns.reduce((a, n) => a + scoreOf(answers, n), 0);
    return s / ns.length;
  }

  /* ---------- 1. 职位基线匹配 ---------- */
  function matchBaseline(jobRaw) {
    const job = (jobRaw || '').trim();
    if (!job) return { base: 60, group: 'mid', matched: false, needsChoice: false };

    // ── 优先级1：精确岗位库全名匹配 ──
    if (D.jobLibrary) {
      for (const entry of D.jobLibrary) {
        for (const j of entry.jobs) {
          // 精确匹配或 "XXX专员/经理/总监" 后缀组合
          if (job === j || job === j.replace(/[\(（].*?[\)）]/, '')) {
            const group = entry.base <= 40 ? 'low' : (entry.base >= 70 ? 'high' : 'mid');
            return { base: entry.base, group, matched: true, needsChoice: false, kw: '[精确]', source: 'library' };
          }
        }
        // 模糊包含：用户输入的 job 包含某个标准岗位名
        for (const j of entry.jobs) {
          const core = j.replace(/[\(（].*?[\)）]/, '');
          if (job.includes(core) && core.length >= 3) {
            const group = entry.base <= 40 ? 'low' : (entry.base >= 70 ? 'high' : 'mid');
            return { base: entry.base, group, matched: true, needsChoice: false, kw: core, source: 'library' };
          }
        }
      }
    }

    // ── 优先级2：词根模糊匹配 ──
    for (const row of D.baselineDict) {
      for (const kw of row.kw) {
        if (job.indexOf(kw) !== -1) {
          const group = row.base <= 40 ? 'low' : (row.base >= 80 ? 'high' : 'mid');
          return { base: row.base, group, matched: true, needsChoice: false, kw, source: 'keyword' };
        }
      }
    }

    // 未命中 → 触发三选一
    return { base: 60, group: 'mid', matched: false, needsChoice: true };
  }

  /* ---------- 2. 替代风险公式（指数衰减，分数不穿透为负） ----------
   * Risk = R_base * (1 - 0.4*S_ai/100 - 0.3*S_collab/100 - 0.1*S_agile/100)
   */
  function computeRisk(rBase, sAi, sCollab, sAgile) {
    const factor = 1
      - 0.4 * (sAi / 100)
      - 0.3 * (sCollab / 100)
      - 0.1 * (sAgile / 100);
    return clamp(round(rBase * factor), 0, 100);
  }

  /* 原始三因子（0-100）：由维度得分换算 */
  function factors(answers) {
    return {
      ai:     round(avgDims(answers, [7, 8, 9, 10]) * 10),
      collab: round(avgDims(answers, [15, 16, 17]) * 10),
      agile:  round(avgDims(answers, [18, 19, 20]) * 10)
    };
  }

  /* ---------- 3. 四大聚合指数（降维） ---------- */
  function indices(answers) {
    // 基础壁垒：RIASEC 最高两项 + 抗脆弱性(19)
    const riasec = [1, 2, 3, 4, 5, 6].map(n => scoreOf(answers, n));
    const top2 = riasec.slice().sort((a, b) => b - a).slice(0, 2);
    const def = round(((top2[0] + top2[1] + scoreOf(answers, 19)) / 3) * 10);

    // 数字驾驭：AI认知(7) Prompt(8) 模型选择(9) 数据洞察(11) 工具敏捷(13)
    const digital = round(avgDims(answers, [7, 8, 9, 11, 13]) * 10);

    // 协同演化：任务解构(15) 协同共创(16) 反馈迭代(17) 系统重构(14) 敏捷迭代(13)
    const coev = round(avgDims(answers, [15, 16, 17, 14, 13]) * 10);

    // 流程脆弱度：常规型(6) 正向；AI伦理(10) 反向（越高越安全）
    const c = scoreOf(answers, 6) * 10;
    const ethics = scoreOf(answers, 10) * 10;
    const fragility = clamp(round(c - (ethics - 50) / 2), 0, 100);
    const danger = (c > 80) && (coev < 50);

    return { def, digital, coev, fragility, danger };
  }

  /* ---------- 4. 四象限分类 ---------- */
  function classify(answers, idx) {
    const c = scoreOf(answers, 6) * 10;
    const r = scoreOf(answers, 1) * 10, a = scoreOf(answers, 3) * 10, s = scoreOf(answers, 4) * 10;
    const sysRe = scoreOf(answers, 14) * 10;

    if (idx.def > 75 && idx.digital > 75 && idx.coev > 75) return 'D';
    if (c > 75 && idx.digital < 50 && idx.coev < 50)        return 'A';
    if ((r > 80 || a > 80 || s > 80) && idx.digital < 50)   return 'B';
    if (idx.digital > 80 && idx.coev < 50 && sysRe < 40)    return 'C';
    return 'X';
  }

  /* ---------- 5. 最高 / 最低维度 ---------- */
  function extremes(answers) {
    /* 初始带完整 fallback 字段，防止 undefined */
    let hi = { n: -1, score: -1, code: '', title: '未知' };
    let lo = { n: -1, score: 999, code: '', title: '未知' };
    for (const q of D.questions) {
      const sc = scoreOf(answers, q.n);
      if (sc > hi.score) hi = { n: q.n, score: sc, code: q.code || q.title, title: q.title || ('维度' + q.n) };
      if (sc < lo.score) lo = { n: q.n, score: sc, code: q.code || q.title, title: q.title || ('维度' + q.n) };
    }
    return { hi, lo };
  }

  /* ---------- 6. 雷达图 5 轴（0-100） ---------- */
  function radar(answers) {
    return {
      RIASEC:  round(avgDims(answers, [1, 2, 3, 4, 5, 6]) * 10),
      AI素养:   round(avgDims(answers, [7, 8, 9, 10]) * 10),
      协作:     round(avgDims(answers, [15, 16, 17]) * 10),
      数字技能: round(avgDims(answers, [11, 12, 13, 14]) * 10),
      突围力:   round(avgDims(answers, [18, 19, 20]) * 10)
    };
  }

  /* ---------- 7. 沙盘实时推演 ----------
   * 干预滑块(0-100) 把对应因子推向目标值：eff = orig + (100-orig)*slider/100
   */
  function simulate(rBase, f, sliders) {
    const eff = {
      ai:     round(f.ai     + (100 - f.ai)     * (sliders.ai / 100)),
      collab: round(f.collab + (100 - f.collab) * (sliders.collab / 100)),
      agile:  round(f.agile  + (100 - f.agile)  * (sliders.agile / 100))
    };
    const risk = computeRisk(rBase, eff.ai, eff.collab, eff.agile);
    return { eff, risk };
  }

  /* ---------- 8. 完整报告生成 ---------- */
  function generate(answers, userJob, rBase) {
    const f = factors(answers);
    const idx = indices(answers);
    const baseRisk = computeRisk(rBase, f.ai, f.collab, f.agile);
    const qKey = classify(answers, idx);
    const qRaw = D.quadrants[qKey];
    const ex = extremes(answers);
    const rd = radar(answers);

    /* 统一变量替换函数 */
    const job = userJob || '职场人';
    const fill = (t) => (t || '')
      .replace(/\{job\}/g, job)
      .replace(/\{highest\}/g, ex.hi.title || '综合能力')
      .replace(/\{lowest\}/g, ex.lo.title || '待提升维度');

    /* 对象级深 fill：把象限模板中所有含占位符的字段都替换掉 */
    const q = {
      key: qRaw.key, name: qRaw.name,
      tagline: fill(qRaw.tagline),
      headline: fill(qRaw.headline),
      body: fill(qRaw.body),
      advice: fill(qRaw.advice)
    };

    const riskColor = baseRisk >= 60 ? D.palette.danger
      : (baseRisk >= 35 ? D.palette.warn : D.palette.safe);

    const freePreview =
      `你的初始替代风险为 ${rBase}%，完成 20 维扫描后实时测算为 ` +
      `【${baseRisk}%】。当前最薄弱的环节是「${ex.lo.title}」（${ex.lo.score}/10），` +
      `它是你最大的被替代敞口；而你最强的优势是「${ex.hi.title}」（${ex.hi.score}/10）。` +
      `完整报告中，我们已为你的 3 个弱项定制了 21 天提升计划与专属 Prompt 资产库。`;

    /* ---- 排序出最弱 3 个维度 ---- */
    const sortedWeak = D.questions
      .map(qu => ({ n: qu.n, code: qu.code || '', title: qu.title || ('维度' + qu.n), score: dim(answers, qu.n), group: qu.group || '' }))
      .sort((a, b) => a.score - b.score)
      .slice(0, 3);

    /* ---- 3 条跃迁路径（根据象限动态组合）---- */
    const paths = buildPaths(qKey, ex, idx, job);

    /* ---- 高阶 Prompt 资产库（根据职位+弱项动态生成）---- */
    const prompts = buildPrompts(job, sortedWeak);

    /* ---- 21 天专项计划（按弱项生成）---- */
    const plan21 = buildPlan(sortedWeak, job);

    const paywall =
      `了解风险只是第一步。基于你「${job}」的 20 维度深度扫描已完成。\n` +
      `解锁完整报告，你将获得：\n` +
      `1. 针对你当前 3 个弱势维度的 21 天专项提升计划；\n` +
      `2. 你的岗位在 AI 时代的 3 条高价值跃升 / 转行路径；\n` +
      `3. 一份专属于你职业的高阶 Prompt 资产库。`;

    /* ---- 解锁后的完整报告 ---- */
    const fullReport =
      `📋 ${q.name} · 深度诊断报告\n` +
      `═════════════════════\n\n` +
      `【画像定位】${q.tagline}\n\n` +
      `${q.headline}\n\n${q.body}\n\n` +
      `━━━ 突围建议 ━━━\n${q.advice}\n\n` +
      `━━━ 数据总览 ━━━\n` +
      `· 基础壁垒指数：${idx.def}${idx.def >= 70 ? ' ✅ 强' : ' ⚠️ 需加固'}\n` +
      `· 数字驾驭指数：${idx.digital}${idx.digital >= 70 ? ' ✅ 强' : ' ⚠️ 需提升'}\n` +
      `· 协同演化指数：${idx.coev}${idx.coev >= 70 ? ' ✅ 强' : ' ⚠️ 需强化'}\n` +
      `· 替代风险指数：${baseRisk}% → 干预后最低可降至 ${computeRisk(rBase, 100, 100, 100)}%\n\n` +
      `━━━ 21天提升计划 ━━━\n${plan21}\n\n` +
      `━━━ 3条跃迁路径 ━━━\n${paths}\n\n` +
      `━━━ 专属Prompt资产库 ━━━\n${prompts}`;

    return {
      rBase, baseRisk, factors: f, indices: idx, radar: rd,
      quadrantKey: qKey, quadrant: q, extremes: ex,
      riskColor, freePreview, paywall, fullReport,
      weakThree: sortedWeak,
      minRisk: computeRisk(rBase, 100, 100, 100)
    };
  }

  /* ---------- 9. 21 天提升计划生成（按维度号 n 映射，稳定不随 title 变化）---------- */
  function buildPlan(weak, job) {
    return weak.map((w, i) => {
      const week1 = getPlanWeek1(w.n);
      const week2_3 = getPlanWeek23(w.n);
      return (
        `📌 第 ${i + 1} 弱项：${w.title}（当前 ${w.score}/10）\n` +
        `第 1 周：${week1}\n` +
        `第 2-3 周：${week2_3}\n`
      );
    }).join('\n');
  }
  function getPlanWeek1(n) {
    const m = {
      1: '主动争取一次现场/实操类任务，记录机器无法替代的物理判断瞬间，强化"现实型"护城河。',
      2: '本周每次收到报告/结论时，强制交叉验证 1 个数据源，养成"研究型"质疑肌肉。',
      3: '挑一个产出，刻意注入个人风格与非常规结构，拒绝模板化，巩固审美壁垒。',
      4: '主动认领一次跨部门冲突调解，练习用共情而非规则破局，沉淀人际信任资产。',
      5: '在一个受限项目中主动游说 1 项资源并担责结果，锻炼"企业型"资源整合力。',
      6: '梳理你岗位的核心 SOP，标注哪些步骤已被 AI 工具覆盖。每天花 20 分钟试用 1 个新工具（如 ChatGPT / Claude）处理一个真实任务。',
      7: '系统学习 LLM 原理（推荐吴恩达 AI For Everyone 或李宏毅课程），每天 30 分钟。用通俗语言向一位非技术同事解释一次。',
      8: '从零开始练 Prompt 工程。第 1-3 天只做"角色设定+上下文"，第 4-5 天加 Few-shot 示例，第 6-7 天尝试 Chain-of-Thought。',
      9: '注册并对比 GPT-4、Claude、国产大模型在同一任务上的表现差异。记录每种模型擅长的场景类型。',
      10: '整理一份你岗位的"数据脱敏清单"。列出哪些信息绝不能输入公有 AI，练习用假名/脱敏数据做 Prompt 测试。',
      11: '拿一份真实业务数据，手动做一次端到端分析（清洗→可视化→结论），然后让 AI 做同样的事，对比两者的差异点。',
      12: '注册 Make/Zapier 免费版，搭建第一个自动化流（如"收到邮件→提取附件→存到文件夹"）。',
      13: '选一款你没用过的效率软件（Notion/飞书/Cursor），强迫自己在 7 天内用它完成一个完整工作项目。',
      14: '画出你部门当前交付流程图，标出每个环节中"人做的"和"可以交给 AI 的"，识别至少 3 个重构切入点。',
      15: '挑一个大目标（如写月报），强制拆成 ≥10 个子 Prompt，逐条执行并验收结果质量。',
      16: '与 AI 进行一轮"观点碰撞"——提出你的方案，要求 AI 找漏洞，你再反驳，来回至少 3 轮。',
      17: '拿 AI 初稿，用"红笔批注法"逐段标记问题，给 AI 发送精准迭代指令，直到打磨到 90 分以上。',
      18: '列出你过去 3 年学的核心技能，评估每项在 AI 时代的折旧率。选择折旧最快的一项，制定替代学习路径。',
      19: '写一份"假设被替代后"的 B 计划：如果岗位消失，你能靠什么能力在 30 天内找到新位置？',
      20: '重新写一版 JD（职位描述），但这次是从"审核者/策略官"视角来定义这个角色的新形态。'
    };
    return m[n] || `针对该维度进行系统性输入输出训练，每日记录进步。`;
  }
  function getPlanWeek23(n) {
    const m = {
      1: '把"现场判断"经验整理成可传授的案例库，成为团队中机器无法替代的实操顾问。',
      2: '阅读 2-3 篇关于 AI 在你所在行业的落地案例报告，形成自己的判断框架，不盲信任何一方。',
      3: '建立个人风格手册（含禁忌与偏好），让 AI 在协作时也能稳定输出你的"声音"。',
      4: '发起一次跨团队共情工作坊，把你的人际处理经验产品化，扩大影响力半径。',
      5: '输出一份《资源撬动复盘》，沉淀你游说与担责的方法论，争取更大项目主导权。',
      6: '开始主动承担跨部门沟通类工作，在 SOP 执行之外注入"人际判断"要素。每周复盘一次非标准化工作的占比变化。',
      7: '阅读 2-3 篇关于 AI 在你所在行业的落地案例论文/深度报告，形成自己的判断框架，不盲信任何一方。',
      8: '建立个人 Prompt 模板库（≥10 个高频场景模板）。加入一个 Prompt Engineering 社区，每周分享 1 个优化案例。',
      9: '根据你的任务类型制作一张"模型选择决策树"：什么任务用什么模型、为什么。固化成团队可复用的标准。',
      10: '推动团队制定"AI 使用规范"，包含数据分级、审批流程、审计日志。成为团队内的 AI 安全倡导者。',
      11: '建立一个自动化看板（Excel/Notion/飞书多维表格），让关键指标自动更新。培养"看到数字就问 so what"的习惯。',
      12: '把你日常重复最多的 3 件事全部自动化。计算节省的时间成本，向上汇报 ROI。',
      13: '将新工具融入核心工作流，写一篇"工具上手指南"分享给同事，巩固学习成果。',
      14: '发起一个小型流程改造试点（1-2 周），用 A/B 对比"改造前 vs 改造后"的交付效率数据。',
      15: '将拆解方法论沉淀为团队 SOP，培训 1-2 名同事使用同样的方法，验证其可复制性。',
      16: '完成一个由 AI 辅助的中型项目（如方案/报告/设计），全程保留对话记录作为"协作过程资产"。',
      17: '统计你的"迭代轮次 vs 质量提升"数据，找出最高效的迭代模式，固化下来。',
      18: '开始实践学到的全新技能（哪怕是小项目），在朋友圈/社群公开分享学习进度，建立外部反馈回路。',
      19: '拓展 2-3 个"平行生态位"——不完全脱离现有专业，但在相邻领域建立可迁移的能力储备。',
      20: '向直属上级提交一份《岗位 AI 升级提案》，用数据论证升级后的价值增量，争取资源支持。'
    };
    return m[n] || `持续深化该维度，寻找实战机会验证学习成果。`;
  }

  /* ---------- 10. 跃迁路径生成 ---------- */
  function buildPaths(qKey, ex, idx, job) {
    const templates = {
      A: [
        `路径 ① 流程架构师转型：利用你对现有 SOP 的深刻理解，转型为"流程自动化架构师"。你的优势是知道哪些环节可以被机器接管，这是纯技术人员不具备的领域知识。`,
        `路径 ② 客户管理岗迁移：向需要重度人际沟通的岗位迁移（客户成功/客户经理），利用常规型的规则敏感度 + 注入社会型(S)共情力。`,
        `路径 ③ 内部咨询/培训师：将你积累的流程经验产品化，成为组织内部"流程优化顾问"或"新人培训师"，从执行者变为赋能者。`
      ],
      B: [
        `路径 ① AI增强型专家：保持核心专业深度不变，将低价值环节全面外包给 AI。定位为"${job} + AI助理"的超高效个体，产能提升 3-5 倍。`,
        `路径 ② 专业内容策展人：利用你的审美/共情/手感，转型为"内容审核者"或"创意总监"——AI 出初稿，你负责把关和注入灵魂。`,
        `路径 ③ 垂直领域教育者：将你的隐性知识显性化，通过课程/咨询/社群变现。"手艺人的经验"恰恰是最难被 AI 快速复制的。`
      ],
      C: [
        `路径 ① 业务解构专家：停止追逐工具参数，转向业务侧。学会在下达指令前先画"问题树"，成为团队中"最会提问的人"。`,
        `路径 ② AI 产品/项目经理：你有工具理解力 + 缺业务深度 → 补齐业务短板后，成为连接技术与业务的桥梁角色。`,
        `路径 ³ Prompt 架构师：把你的 Prompt 能力产品化，为企业定制"提示词工程解决方案"，从使用者变为供给者。`
      ],
      D: [
        `路径 ① 组织级 AI 工作流设计师：构建部门/团队的标准化 AI 协作 SOP，将个人先发优势转化为组织能力。`,
        `路径 ② AI 转型顾问/教练：向外输出你的方法论，帮助其他团队/公司完成 AI 时代的能力升级。`,
        `路径 ³ 创业/独立顾问：以"超级个体"身份接项目，杠杆率远高于传统雇佣模式。`
      ],
      X: [
        `路径 ① 强化最强项「${ex.hi.title}」：将其打造为个人品牌标签，在同赛道中建立差异化认知。`,
        `路径 ² 补齐最大短板「${ex.lo.title}」：这是你当前最大的敞口，21 天专项突破后整体防御力显著提升。`,
        `路径 ³ 人机混合岗探索：关注你所在行业中 newly created 的"人机协作型"岗位，提前布局。`
      ]
    };
    return (templates[qKey] || templates.X).map((p, i) => `${p}`).join('\n');
  }

  /* ---------- 11. Prompt 资产库生成（按维度号 n 映射）---------- */
  function buildPrompts(job, weak) {
    const base =
      `# 🎯 「${job}」专属 Prompt 资产库\n\n` +
      `## 一、通用高阶框架\n` +
      `### C.O.S.T.A 角色设定模板\n` +
      '```\n' +
      `你是一位 [Context 背景] 领域的 [Role 角色]，拥有 [Skill 技能] 年经验。\n` +
      `你的任务是 [Task 任务]。\n` +
      `约束条件：[Constraint 1]；[Constraint 2]。\n` +
      `输出格式：[Output Format]。\n` +
      '```\n\n' +
      `### Chain-of-Thought 推理引导\n` +
      '```\n' +
      `请按以下步骤思考并回答：\n` +
      `1. 先明确问题的核心矛盾是什么。\n` +
      `2. 列出至少 3 种可能的解决路径。\n` +
      `3. 对比各路径的优劣和适用场景。\n` +
      `4. 给出最终建议及理由。\n` +
      '```\n\n';
    const specific = weak.map(w => {
      const promptsByDim = {
        1: `### 现场判断沉淀 Prompt\n\`\`\`\n我在 [场景] 遇到了一个机器/远程无法处理的物理判断问题：[描述]。\n请帮我：\n1. 提炼出这个判断背后的隐性经验规则\n2. 写出一条可传授给新人的"决策树"\n3. 指出哪些环节仍必须人工、不可外包\n\`\`\`\n`,
        2: `### 交叉验证 Prompt\n\`\`\`\n我收到一份结论：[粘贴结论/报告摘要]。\n请扮演严谨的审稿人，帮我：\n1. 列出支撑该结论所需的 3 个关键数据源\n2. 指出其中任何未经证实的跳跃\n3. 给出 2 个反例或边界条件\n\`\`\`\n`,
        3: `### 风格注入 Prompt\n\`\`\`\n请学习以下我的作品样本：[粘贴 1-2 段]。\n提炼我的：\n- 用词偏好与禁忌\n- 句式与节奏\n- 情绪基调\n之后按此"声音"帮我起草 [新任务]，保持人味、避免 AI 腔。\n\`\`\`\n`,
        4: `### 共情破局 Prompt\n\`\`\`\n[对象] 正处于 [冲突/情绪] 状态，我的目标是 [目标]。\n请帮我设计一段对话：\n1. 先用共情复述对方的真实诉求\n2. 再给出不靠规则压人的解决方案\n3. 标注哪一步最依赖真人信任\n\`\`\`\n`,
        5: `### 资源整合提案 Prompt\n\`\`\`\n我手上有 [资源A]、[资源B]，但缺 [缺口]。\n请帮我写一份 1 页游说材料：\n- 为什么这事值得做（ROI/风险）\n- 我愿担哪些责任\n- 需要对方提供什么\n语气：自信、具体、可落地。\n\`\`\`\n`,
        6: `### SOP 解构 & 自动化 Prompt\n\`\`\`\n请分析以下工作流程，识别出：\n1. 可被 AI/RPA 全自动化的步骤（标注置信度 High/Med/Low）\n2. 必须人工判断的关键决策点\n3. 推荐的自动化工具链路\n\n我的工作流程描述：[粘贴你的日常流程]\n\`\`\`\n`,
        7: `### AI 原理通俗解释 Prompt\n\`\`\`\n请用"给 [目标受众，如产品经理] 讲课"的方式，解释以下 AI 概念：\n[概念名称]\n\n要求：\n- 用类比而非公式\n- 给出 2 个实际应用场景\n- 指出 1 个常见误区\n\`\`\`\n`,
        8: `### Few-shot 优化 Prompt\n\`\`\`\n我需要你帮我 [具体任务]。以下是 2 个优秀示例和 1 个差示例，请模仿优秀示例的风格和质量来完成新任务。\n\n✅ 示例 1：[输入→输出]\n✅ 示例 2：[输入→输出]\n❌ 差示例：[输入→输出]\n\n📥 新任务：[你的输入]\n\`\`\`\n`,
        9: `### 模型选型 Prompt\n\`\`\`\n我有一个任务：[任务描述]。候选模型：GPT-4 / Claude / 国产大模型 / 专有小模型。\n请帮我：\n1. 给出推荐模型及理由\n2. 指出每个模型的短板\n3. 设计一个 fallback 链路（主模型失败时用谁）\n\`\`\`\n`,
        10: `### 数据脱敏 Prompt\n\`\`\`\n下面这段文字含敏感信息，请在不改变语义和结构的前提下，把公司名、人名、金额、客户名替换为占位符（如 [公司A]、[客户X]），并列出"已脱敏字段清单"，便于我确认后再喂给公有 AI。\n\n原文：[粘贴文本]\n\`\`\`\n`,
        11: `### 数据洞察 Prompt\n\`\`\`\n这是一份业务数据表（字段说明）：[粘贴字段]。\n请帮我：\n1. 找出 3 个异常点\n2. 给出 2 条相关性假设\n3. 提炼 1 句可行动的商业结论（so what）\n\`\`\`\n`,
        12: `### 自动化搭建 Prompt\n\`\`\`\n我想把 [A 系统] 的数据定期同步到 [B 系统] 并生成报告。\n请给我一个零代码的实现方案：\n- 推荐工具（Zapier/Make/飞书）\n- 触发器与步骤清单\n- 需要规避的失败点\n\`\`\`\n`,
        13: `### 工具上手 Prompt\n\`\`\`\n我要在一周内吃透 [工具名] 并重构工作流。\n请给我一份 7 天上手计划：每天一个最小可用任务，逐步替换老习惯。\n\`\`\`\n`,
        14: `### 流程重构 Prompt\n\`\`\`\n这是我们部门当前的交付流程：[粘贴流程]。\n请帮我 redesign 端到端链路：\n- 标出每个环节"人做/AI做"\n- 提出 ≥3 个重构切入点\n- 估算改造后的效率增益\n\`\`\`\n`,
        15: `### 任务拆解委派 Prompt\n\`\`\`\n我将给你一个大目标，请你：\n1. 将其拆解为 ≤10 个原子级子任务\n2. 标注每个子任务的：难度(Easy/Med/Hard)、预计耗时、是否可交给 AI\n3. 推荐执行顺序（考虑依赖关系）\n\n我的目标是：[粘贴目标]\n\`\`\`\n`,
        16: `### 观点碰撞 Prompt\n\`\`\`\n我有一个方案：[简述方案]\n\n请你扮演"魔鬼代言人"，找出其中：\n- 2 个逻辑漏洞\n- 1 个被我忽略的风险\n- 1 个更好的替代思路\n\n然后我会在你的反馈基础上继续完善。\n\`\`\`\n`,
        17: `### 迭代打磨 Prompt\n\`\`\`\n这是我的初稿：[粘贴]。请用"红笔批注法"：\n1. 逐段标出具体问题（不是泛泛的"可以更好"）\n2. 给我一句可直接使用的迭代指令\n3. 给出 90 分版本应达到的具体标准\n\`\`\`\n`,
        18: `### 技能折旧 Prompt\n\`\`\`\n我赖以生存的技能是：[技能]。请评估它在 AI 时代的折旧率（高/中/低），并推荐 1 项可迁移的替代学习路径，附 3 个入门资源。\n\`\`\`\n`,
        19: `### 抗脆弱 B 计划 Prompt\n\`\`\`\n假设我的岗位在 1 年内消失。请基于我现有的能力：[列出]，帮我规划：\n- 2-3 个平行生态位\n- 30 天内可落地的求职/变现动作\n- 需要补的最小能力缺口\n\`\`\`\n`,
        20: `### 战略升维 Prompt\n\`\`\`\n请帮我重写我的职位描述（JD），但视角从"执行者"升级为"审核者/策略官"：\n- 保留核心价值\n- 重写职责为"指挥 AI"的形态\n- 给出升级后的价值增量论证\n\`\`\`\n`
      };
      return (promptsByDim[w.n] || (`### ${w.title} 提升 Prompt\n\`\`\`\n[针对该维度的定制化 Prompt 模板]\n\`\`\`\n`));
    }).join('\n');

    return base + `## 二、针对你的弱项定制的 Prompt\n\n` + specific;
  }

  window.Engine = {
    matchBaseline, computeRisk, factors, indices, classify,
    extremes, radar, simulate, generate, clamp
  };
})();
