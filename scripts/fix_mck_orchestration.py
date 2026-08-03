# -*- coding: utf-8 -*-
"""
一次性修复：articles/mckinsey-human-ai-orchestration.html
原文把「私有评估集/爬山机器」（纳德拉 Build 2026 原创概念）错误包装成
一份不存在的麦肯锡报告《2026 AI 组织变革全景图》，并编造 412 家样本 /
312% / 47% / 12% / 80%传统企业出局 等数据。

本脚本用两个真实信源重建数据脊梁：
  1. McKinsey & Company,《The State of Organizations 2026》
     （15国/16行业/逾1万名高管；第二章「人类与AI智能体：构建人机协作新世界」）
  2. Satya Nadella, Microsoft Build 2026（No Priors × Latent Space 特辑）
     + Stratechery（Ben Thompson）访谈 2026-06
"""
import io
import sys

P = 'articles/mckinsey-human-ai-orchestration.html'
h = io.open(P, encoding='utf-8').read()
orig_len = len(h)

OLD_TITLE = "麦肯锡2026断言：人机编排是组织唯一出路"
NEW_TITLE = "麦肯锡2026：70%岗位技能横跨人机边界，人机编排怎么做"

NEW_DESC = ("麦肯锡《组织现状报告2026》调研15国16行业逾1万名高管发现：超过70%的岗位技能同时存在于"
            "「可被自动化」与「不可被自动化」的任务中。人机分工不能按岗位切，只能按任务编排。"
            "本文拆解麦肯锡的任务级分工框架，与纳德拉「私有评估集」「爬山机器」的度量机制。")
NEW_OGDESC = ("麦肯锡《组织现状报告2026》：超过70%的岗位技能同时横跨可自动化与不可自动化任务。"
              "大多数技能不会消失，但会换一种用法——人机分工必须落到任务级。")
NEW_SHORT = ("麦肯锡《组织现状报告2026》发现：超过70%的岗位技能同时横跨「可被自动化」与"
             "「不可被自动化」的任务，因此人机分工必须落到任务级而非岗位级。")

missing = []


def rep(old, new, tag):
    global h
    if old not in h:
        print("  MISS[%s]" % tag)
        missing.append(tag)
        return
    h = h.replace(old, new)
    print("  ok  %s" % tag)


# ---------------- 1. head / schema ----------------
rep('<title>' + OLD_TITLE + '</title>',
    '<title>' + NEW_TITLE + '</title>', 'title')

rep('<meta name="description" content="麦肯锡2026最新报告断言：未来3年，80%的传统企业将在AI变革中出局。'
    '胜出关键不是AI使用量，而是人机编排能力。本文详解「私有评估集」和「爬山机器」两大核心概念。">',
    '<meta name="description" content="' + NEW_DESC + '">', 'meta-desc')

rep('<meta content="麦肯锡,人机编排,AI组织,私有评估集,爬山机器,组织竞争力" name="keywords"/>',
    '<meta content="麦肯锡组织现状报告2026,人机编排,任务级分工,私有评估集,爬山机器,AI智能体,组织设计" name="keywords"/>',
    'keywords')

rep('<meta content="麦肯锡2026最新报告断言：未来3年，80%的传统企业将在AI变革中出局。'
    '生存下来的组织，不是用AI最多的，而是把人和AI编排得最好的。" property="og:description"/>',
    '<meta content="' + NEW_OGDESC + '" property="og:description"/>', 'og-desc')

rep('<meta content="' + OLD_TITLE + '" property="og:title"/>',
    '<meta content="' + NEW_TITLE + '" property="og:title"/>', 'og-title')

rep('<meta name="short-answer" content="麦肯锡2026年6月最新报告给出了一记重锤：'
    '未来3年，80%的传统企业将在AI变革中出局。">',
    '<meta name="short-answer" content="' + NEW_SHORT + '">', 'short-answer')

rep('<meta content="' + OLD_TITLE + '" name="twitter:title"/>',
    '<meta content="' + NEW_TITLE + '" name="twitter:title"/>', 'tw-title')

rep('<meta name="twitter:description" content="麦肯锡2026最新报告断言：未来3年，80%的传统企业将在AI变革中出局。'
    '生存下来的组织，不是用AI最多的，而是把人和AI编排得最好的。"/>',
    '<meta name="twitter:description" content="' + NEW_OGDESC + '"/>', 'tw-desc')

rep('"headline": "' + OLD_TITLE + '",',
    '"headline": "' + NEW_TITLE + '",', 'schema-headline')

OLD_SCHEMA_DESC = ('"description": "麦肯锡2026最新报告断言：未来3年，80%的传统企业将在AI变革中出局。'
                   '胜出关键不是AI使用量，而是人机编排能力。本文详解「私有评估集」和「爬山机器」两大核心概念。 '
                   '麦肯锡2026年6月最新报告给出了一记重锤： 未来3年，80%的传统企业将在AI变革中出局 。'
                   '但出局的原因不是「不用AI」——而是「",')
rep(OLD_SCHEMA_DESC, '"description": "' + NEW_DESC + '",', 'schema-desc')

# ---------------- 2. 首屏 ----------------
rep('<p class="article-subtitle"> 麦肯锡2026最新报告断言：未来3年，80%的传统企业将在AI变革中出局。'
    '胜出关键不是AI使用量，而是人机编排能力。本文详解「私有评估集」和「爬山机器」两大核心概念。 </p>',
    '<p class="article-subtitle"> 麦肯锡《组织现状报告2026》调研15国16行业逾1万名高管：'
    '超过70%的岗位技能同时横跨可自动化与不可自动化任务。这意味着「哪些岗位会被取代」是个问错的问题'
    '——真正要回答的是每个任务节点上谁做判断、谁做执行。 </p>', 'subtitle')

rep('<p class="geo-answer-capsule__text">麦肯锡：未来 3 年 80% 传统企业将在 AI 变革中出局，'
    '原因不是不用 AI，而是人机编排（Orchestration）能力不行。'
    '胜出者不是用 AI 最多的，而是把人和 AI 编排得最好的组织。</p>',
    '<p class="geo-answer-capsule__text">麦肯锡《组织现状报告2026》发现：超过 70% 的岗位技能同时存在于'
    '「可被自动化」与「不可被自动化」的任务中——大多数技能不会消失，只会换一种用法。'
    '因此人机分工无法按岗位切割，只能落到任务级编排：每个节点上明确谁做判断、谁做执行、谁来监督。</p>',
    'capsule')

rep('<cite>—— 麦肯锡《2026 AI 组织变革全景图》</cite>',
    '<cite>—— 萨提亚·纳德拉，微软 Build 2026（No Priors × Latent Space 特辑）</cite>', 'quote-cite')

# ---------------- 3. 核心洞察 ----------------
rep('<div class="key-insight"><h3>⚡ 核心洞察</h3><p>麦肯锡2026年6月最新报告给出了一记重锤：'
    '<strong>未来3年，80%的传统企业将在AI变革中出局</strong>。但出局的原因不是「不用AI」'
    '——而是「用AI的方式不对」。胜出的组织，不是用AI最多的，而是把<strong>人和AI编排得最好</strong>的。</p></div>',
    '<div class="key-insight"><h3>⚡ 核心洞察</h3><p>麦肯锡《组织现状报告2026》里有一个容易被跳过的发现：'
    '<strong>超过70%的岗位技能，同时存在于「可被自动化」和「不可被自动化」的任务中</strong>。'
    '这句话堵死了两条捷径——既不能整岗替换，也不能整岗保留。分工线不在岗位之间，而在任务之内。</p></div>',
    'key-insight')

# ---------------- 4. 报告章节 + 真实数据 ----------------
rep('<h2>一个被误读的报告</h2><p>麦肯锡这份报告的标题很吸引眼球：《2026年'
    '<a href="/articles/ai-hr-2026-midyear-three-signals.html" class="ilink">AI组织</a>变革全景图》。'
    '但大多数人只看到了「AI」和「变革」，却忽略了报告中最重要的一个词：<strong>编排（Orchestration）</strong>。</p>'
    '<p>报告调研了412家在AI转型中「自认为成功」的企业，发现了一个反直觉的事实：</p>'
    '<p><strong>AI使用量最高的企业，组织效能提升反而最慢。</strong></p>'
    '<p>相反，那些AI使用量中等、但「人机协作流程」设计得最精细的企业，组织效能提升了2-5倍。</p>',
    '<h2>被跳过的那一章</h2><p>麦肯锡《组织现状报告2026》（The State of Organizations 2026）'
    '梳理了九大行动主题，样本覆盖15个国家、16个行业、超过1万名高级管理者。'
    '大多数解读停在第一章「打造AI赋能型组织」，而与'
    '<a href="/articles/ai-hr-2026-midyear-three-signals.html" class="ilink">AI组织</a>落地关系最紧的，'
    '是另一章：<strong>人类与AI智能体：构建人机协作新世界</strong>。</p>'
    '<p>这一章的操作指令写得很直白——企业固然可以把AI嵌进现有流程，但要真正释放潜力，'
    '往往需要从零重新设计流程：把工作拆解成具体任务，然后逐一判断，哪些适合交给AI，'
    '哪些必须由人完成，哪些需要人机协同。判断依据不只是效率，还有成本、伦理和技术成熟度。</p>'
    '<p>报告同时提醒：AI智能体还不具备人类的判断力和责任感，因此需要被监督。</p>'
    '<p>把这两段放在一起，人机协作环境里最基础的三个问题就浮出来了：'
    '<strong>谁来决策？谁来执行？人和AI各自负责什么？</strong></p>', 'sec-report')

rep('<div class="data-callout"><h4>📊 麦肯锡的核心数据</h4><p>在412家样本企业中：</p>'
    '<ul><li>AI使用量前25%的企业：平均效能提升 <strong>12%</strong></li>'
    '<li>AI使用量中间50%但人机编排得分前25%的企业：平均效能提升 <strong>47%</strong></li>'
    '<li>人机编排得分最高的单一企业：效能提升 <strong>312%</strong></li></ul>'
    '<p class="source">来源：麦肯锡2026年AI组织变革报告，样本覆盖北美/欧洲/亚太412家企业</p></div>',
    '<div class="data-callout"><h4>📊 麦肯锡《组织现状报告2026》：管理者眼里的AI红利</h4>'
    '<ul><li><strong>55%</strong> 的受访者相信，员工熟练掌握AI可带来指数级生产力增长</li>'
    '<li><strong>48%</strong> 认为可改善信息获取</li>'
    '<li><strong>47%</strong> 认为可减少行政工作</li>'
    '<li><strong>46%</strong> 认为可提升决策质量</li>'
    '<li>超过 <strong>70%</strong> 的岗位技能，同时存在于「可被自动化」与「不可被自动化」的任务中</li></ul>'
    '<p class="source">来源：McKinsey &amp; Company,《The State of Organizations 2026》，'
    '样本覆盖15个国家、16个行业、逾1万名高级管理者</p></div>'
    '<h2>相信的人很多，兑现的人很少</h2>'
    '<p>同一份报告里还有一组数字，和上面那组放在一起才有意思。</p>'
    '<div class="data-callout"><h4>📊 同一批高管的另一面</h4>'
    '<ul><li><strong>43%</strong> 的领导者将生产率列为最重要议题，<strong>61%</strong> 感受到较大压力</li>'
    '<li>约 <strong>2/3</strong> 的受访者认为，自己组织的结构过于复杂、效率不足</li>'
    '<li>AI落地的阻力排序：<strong>46%</strong> 担忧AI本身（偏见、版权、是否取代自己），'
    '<strong>44%</strong> 指向监管、伦理与法律，<strong>39%</strong> 指向组织层面'
    '——变革管理困难与部门壁垒</li></ul>'
    '<p class="source">来源：McKinsey &amp; Company,《The State of Organizations 2026》</p></div>'
    '<p>55%的人相信AI能带来指数级生产力，可43%的人仍把生产率列为头号难题，61%的人正在承压。'
    '<strong>相信与兑现之间的这道差，就是编排能力的差。</strong>'
    '而排在阻力第三位的「部门壁垒」透露了更具体的信息：'
    '卡住转型的往往不是模型不够强，是没人说得清哪个任务归谁。</p>', 'data-callout')

# ---------------- 5. 概念归属修正 ----------------
rep('<p>麦肯锡对「人机编排」的定义是：<strong>设计一套流程，让人类的判断力和AI的计算力'
    '在每个任务节点上都能找到最优分工</strong>。</p>',
    '<p>综合麦肯锡这一章的表述，人机编排可以这样定义：<strong>把工作拆到任务级，'
    '让人类的判断力和AI的执行力在每个节点上各就各位，并且有人为结果负责</strong>。</p>', 'def')

rep('<p>麦肯锡报告引用了纳德拉在Build 2026的定义：</p>',
    '<p>麦肯锡的报告告诉你「要按任务重新分工」，却没有回答一个更要命的问题：'
    '<strong>你怎么知道分对了？</strong>这个缺口，微软CEO纳德拉在Build 2026上给出了自己的答案：</p>',
    'nadella-attr')

rep('<div class="analogy-box"><p>🔧 <strong>举个栗子：</strong>两个HR都在用AI写JD（职位描述）。'
    'A直接用AI输出；B先用AI生成草稿，然后用自己公司的「好JD标准」（私有评估集）来修改。'
    '三个月后，B招到的人留存率比A高40%。这就是<strong>私有评估集的威力</strong>。</p></div>',
    '<div class="analogy-box"><p>🔧 <strong>一个真实的分界线：</strong>'
    '麦肯锡报告里的安联（Allianz）案例给出了HR场景的标准答案。'
    '安联把AI用进了承保、理赔和产品设计，招聘环节也让AI快速筛选最匹配的人——但最终拍板的依然是人。'
    '集团首席人力与文化官贝蒂娜·迪切（Bettina Dietsche）的理由很具体：'
    '偏见、文化、感觉这些复杂的人性变量，算法还替代不了。'
    '<strong>这条线不是靠感觉画的，而是靠一套伦理机制反复讨论出来的：什么该交给机器，什么必须留给人。</strong>'
    '同一位高管还有一句更狠的判断：五年内，安联所需的三分之二技能都会被重写，而五年几乎就是明天。</p></div>',
    'analogy')

rep('<p>麦肯锡把这个概念扩展到了组织层面：</p>'
    '<p><strong>AI原生组织 = collective hill-climbing machine</strong></p>'
    '<p>每个人都在用自己的私有评估集，持续爬自己的那座山。AI负责加速，人类负责定方向。</p>',
    '<p>纳德拉给出的判定标准非常锋利：如果你能把A模型换成B模型，'
    '仍能用自己的私有评估集继续向上攀登，主控权就在你手上；如果做不到，主控权在别人手上。</p>'
    '<p>麦肯锡没有用「爬山机器」这个词，但给出的是同一套机制——报告要求企业建立'
    '「<strong>测试—学习—调整</strong>」的循环，并明确写道：像训练模型一样，组织本身也要不断迭代。'
    '<strong>一个说的是模型怎么变强，一个说的是组织怎么变强，落到操作上是同一件事：'
    '把每一次协作的结果变成下一次的输入。</strong></p>', 'hill-climb')

rep('<p>80%的企业卡在第一步——他们根本没有认真梳理过「哪些事其实AI已经能做了」。</p>',
    '<p>多数组织卡在这一步，原因写在麦肯锡的阻力排序里：39%的受访者把「变革管理困难和部门壁垒」'
    '列为组织级障碍。任务清单一旦要跨部门拆，碰到的就是谁让权的问题。</p>', 'step1')

# ---------------- 6. 参考来源 ----------------
REFS = ('<p style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--line); '
        'color: var(--text-muted); font-size: 0.95rem;">'
        '<strong>参考来源：</strong>McKinsey &amp; Company,《The State of Organizations 2026》；'
        '麦肯锡中国,《2026麦肯锡组织现状报告：改变组织未来的三股力量与9大主题》；'
        'Satya Nadella, No Priors × Latent Space Crossover Special at Microsoft Build 2026；'
        'Satya Nadella 接受 Stratechery（Ben Thompson）访谈，2026年6月</p>')
rep('</a></div></div><!-- 相关阅读 -->', '</a></div>' + REFS + '</div><!-- 相关阅读 -->', 'refs')

if missing:
    print("\nFAILED, missing anchors: %s" % missing)
    sys.exit(1)

io.open(P, 'w', encoding='utf-8').write(h)
print("\nWROTE %s  (%d -> %d bytes)" % (P, orig_len, len(h)))

print("\n虚构数据残留自检：")
for token in ['412', '312%', '全景图', '80%的传统企业', 'collective hill-climbing',
              '留存率比A高40%', '2-5倍', OLD_TITLE]:
    n = h.count(token)
    print("  %-28s %s" % (token, ("RESIDUE x%d" % n) if n else "clean"))
