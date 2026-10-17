#!/usr/bin/env python3
"""P1：把 bridge/index.html 从「招聘撮合桥」改写为「CM-2026 能力标准项目对外页」

纪律：
  - 只替换 head 元数据 + article-content 主体 + breadcrumb 末项，不动页头与页脚。
  - 所有数字取自项目真源（01-capability-model-v1.md / 06-PROGRESS.md），不杜撰。
  - 幂等：检测到新 H1 已存在则跳过。

用法：python3 scripts/rewrite_bridge_p1.py [--apply]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "bridge", "index.html")

H1 = "AI 转型期 HR 能力模型（CM-2026）"
DESC = ("AI 转型期 HR 能力模型标准项目：5 个能力域、20 个能力项、每项含熟练度层级与常见误判。"
        "它回答的不是 HR 该学什么，而是组织凭什么把哪些事交给 HR。不撮合、不建库、不用性格测评分数作证据。")

CSS = """
.cm-lede{font-size:1.05rem;line-height:1.8;color:var(--text);margin:0 0 1.4rem}
.cm-section{margin:0 0 1.8rem}
.cm-section h2{font-size:1.15rem;font-weight:700;margin:0 0 .6rem;color:var(--text)}
.cm-section p{margin:0 0 .7rem;line-height:1.85}
.cm-domain{display:grid;grid-template-columns:auto 1fr;gap:.4rem 1rem;margin:.6rem 0 0;font-size:.95rem;line-height:1.7}
.cm-domain dt{font-weight:700;color:var(--accent)}
.cm-domain dd{margin:0}
.cm-redline{list-style:none;padding:0;margin:.5rem 0 0}
.cm-redline li{position:relative;padding-left:1.2rem;margin:0 0 .35rem;line-height:1.7}
.cm-redline li::before{content:"—";position:absolute;left:0;color:var(--accent)}
.cm-table{width:100%;border-collapse:collapse;margin:.6rem 0 0;font-size:.95rem}
.cm-table th,.cm-table td{border:1px solid var(--line-strong);padding:.5rem .7rem;text-align:left;line-height:1.6}
.cm-table th{background:var(--bg-subtle);font-weight:700}
.cm-status{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.8rem;margin:.8rem 0 0}
.cm-card{border:1px solid var(--line-strong);border-radius:8px;padding:.8rem 1rem;background:var(--bg-card)}
.cm-card .k{font-size:.78rem;color:var(--text-muted);display:block;margin-bottom:.2rem}
.cm-card .v{font-size:1.05rem;font-weight:700;color:var(--text)}
.cm-more{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1rem}
.cm-more a{display:inline-block;padding:.45rem .9rem;border:1px solid var(--line-strong);border-radius:999px;font-size:.9rem;color:var(--text);text-decoration:none}
.cm-more a:hover{border-color:var(--accent);color:var(--accent)}
html[data-theme="dark"] .cm-card{border-color:rgba(236,234,228,.14)}
"""

BODY = """<div class="article-content">
<h1>{h1}</h1>
<p class="cm-lede">这个页面记录一项正在进行的工作：把「AI 转型期 HR 应该具备什么能力」从观点变成一套可核验的标准。它要回答的不是 HR 该学什么，而是组织凭什么把哪些事交给 HR。</p>

<section class="cm-section">
<h2>为什么是标准，不是课程</h2>
<p>现有数据指向的不是技能缺口，而是权威真空。把 SHRM 相关数据核到一手之后，更硬的一条是：在最应该由 HR 主导的技能再造上，只有 28% 由 HR 主导，低于跨职能团队的 29%。</p>
<p>所以问题不是「HR 不会做」，而是「HR 拿不到席位与授权」。能力清单解决不了授权问题——清单只会让 HR 更努力地自证。标准的作用是把「哪些事该由 HR 主导」写成可核验的条款，让讨论从能力水平转移到职责边界。</p>
</section>

<section class="cm-section">
<h2>标准层结构</h2>
<dl class="cm-domain">
<dt>D1</dt><dd>工作与组织重构：工作怎么被重新切分，结构与决策权怎么跟着动</dd>
<dt>D2</dt><dd>能力架构与人才供给：组织需要什么能力，从哪来，怎么验证</dd>
<dt>D3</dt><dd>数据与技术判断：技术能做什么、不能做什么，人怎么复核</dd>
<dt>D4</dt><dd>变革与利益重构：谁失去什么，怎么让他们不拦</dd>
<dt>D5</dt><dd>治理、伦理与合规：谁为算法决策负责，出事了怎么办</dd>
</dl>
<p>五个域下面共 20 个能力项，每项都带熟练度层级与「常见误判」——后者是本模型刻意保留的部分：知道一项能力被误认成什么样，往往比知道它是什么更能防止错判。</p>
</section>

<section class="cm-section">
<h2>这个项目不做的事</h2>
<ul class="cm-redline">
<li>不撮合、不接收简历、不做人才对接——人才市场不是这个项目的对象</li>
<li>不抓取招聘平台的岗位数据建库</li>
<li>不把人格或性格测评的分数计入能力证据</li>
<li>不在线生成个人能力画像</li>
<li>每个判断都写成可执行断言，由脚本判定；不接受「我觉得完成了」</li>
</ul>
</section>

<section class="cm-section">
<h2>当前状态（含未决）</h2>
<div class="cm-status">
<div class="cm-card"><span class="k">最近一次实跑校验</span><span class="v">12 项全过</span></div>
<div class="cm-card"><span class="k">能力项 / 层级 / 误判</span><span class="v">20 / 20 / 20</span></div>
<div class="cm-card"><span class="k">待主理人拍板的决策</span><span class="v">5 项</span></div>
</div>
<p>两项真阻塞如实记录：五项决策未拍板前，第二阶段不会启动；另有一项被广泛引用的数据在官方原文中核不到，因此在拿到报告全文之前不会对外使用。这两条不是待办清单，是动不了的地方。</p>
</section>

<section class="cm-section">
<h2>与本站点其他内容的关系</h2>
<p>本站点有三条内容线：文章负责判断与论证，测评负责自我认知，策展负责外部信号。能力标准是第四条线，也是把它们串起来的那一层——文章提供论证，标准提供刻度，测评提供自检，策展提供外部证据的更新。</p>
</section>

<div class="cm-more">
<a href="/articles/index.html">全部文章</a>
<a href="/resources/index.html">资源库</a>
<a href="/tools/index.html">在线测评</a>
<a href="/brief/index.html">策展</a>
<a href="/hub/index.html">专题枢纽</a>
</div>
</div>
""".format(h1=H1) + "\n\n"


def main():
    apply = "--apply" in sys.argv
    t = open(TARGET, encoding="utf-8").read()
    if H1 in t:
        print("已改写，跳过（幂等）")
        return
    orig_len = len(t)

    # 1) head 元数据
    t = re.sub(r"<title>.*?</title>", "<title>%s | AIHR数智引擎</title>" % H1, t, count=1, flags=re.S)
    t = re.sub(r'(<meta\s+name="description"\s+content=")[^"]*(")', r"\g<1>%s\g<2>" % DESC, t, count=1)
    t = re.sub(r'(<meta\s+property="og:title"\s+content=")[^"]*(")', r"\g<1>%s\g<2>" % H1, t, count=1)
    t = re.sub(r'(<meta\s+property="og:description"\s+content=")[^"]*(")', r"\g<1>%s\g<2>" % DESC, t, count=1)
    t = re.sub(r'(<meta\s+name="twitter:title"\s+content=")[^"]*(")', r"\g<1>%s\g<2>" % H1, t, count=1)
    t = re.sub(r'(<meta\s+name="twitter:description"\s+content=")[^"]*(")', r"\g<1>%s\g<2>" % DESC, t, count=1)

    # 2) 追加组件样式到首个 style 块
    m = re.search(r"</style>", t)
    if m:
        t = t[:m.start()] + CSS + "\n" + t[m.start():]

    # 3) breadcrumb 末项更名
    t = t.replace(">招聘的桥</span>", ">能力标准项目</span>")

    # 4) 主体整块替换
    i = t.find('<div class="article-content">')
    j = t.find("<footer")
    if i < 0 or j < 0 or j < i:
        print("锚点缺失，未改动"); sys.exit(1)
    t = t[:i] + BODY + t[j:]

    if apply:
        open(TARGET, "w", encoding="utf-8").write(t)
        print("已改写 bridge/index.html：%d → %d 字节" % (orig_len, len(t)))
        print("  H1:", H1)
    else:
        print("干跑：将改为 %d 字节（原 %d）" % (len(t), orig_len))


if __name__ == "__main__":
    main()
