import re, sys
from pathlib import Path

ROOT = Path(".")
LOADER_TAG = '<script src="/assets/js/analytics-loader.js" defer></script>'


def script_block(needle):
    """匹配含 needle 的单个 <script>...</script>（不跨 script 边界）。"""
    return re.compile(
        r"<script[^>]*>((?:(?!</script>).)*?" + re.escape(needle) + r"(?:(?!</script>).)*?)</script>",
        re.S,
    )


pat_ga_async = re.compile(
    r'<script[^>]*src=["\']https://www\.googletagmanager\.com/gtag/js\?id=G-BWLGRVRRGN["\'][^>]*></script>'
)
pat_ga_inline = script_block("G-BWLGRVRRGN")
pat_baidu = script_block("hm.baidu.com/hm.js")

files = sorted(str(p) for p in ROOT.rglob("*.html"))
contain_ga = 0
contain_baidu = 0
targets = []
for fn in files:
    s = open(fn, encoding="utf-8", errors="ignore").read()
    if "G-BWLGRVRRGN" in s:
        contain_ga += 1
    if "hm.baidu.com/hm.js" in s:
        contain_baidu += 1
    before = s
    s2 = pat_ga_async.sub("", s)
    s2 = pat_ga_inline.sub("", s2)
    s2 = pat_baidu.sub("", s2)
    if s2 != before:
        if LOADER_TAG not in s2:
            if "</head>" in s2:
                s2 = s2.replace("</head>", LOADER_TAG + "\n</head>", 1)
            elif "</body>" in s2:
                s2 = s2.replace("</body>", LOADER_TAG + "\n</body>", 1)
        targets.append((fn, s2))

print("扫描 HTML 文件:", len(files))
print("含 G-BWLGRVRRGN 文件:", contain_ga, "| 含 hm.js 文件:", contain_baidu)
print("将被规范化(删除内联+注入loader)的文件数:", len(targets))

remain_ga = sum(1 for fn, s2 in targets if "G-BWLGRVRRGN" in s2)
remain_baidu = sum(1 for fn, s2 in targets if "hm.baidu.com/hm.js" in s2)
print("模拟去除后残留 GA 内联:", remain_ga, "| 残留百度内联:", remain_baidu)

# 样本：index.html
for fn, s2 in targets:
    if fn == "index.html":
        j = s2.find("analytics-loader.js")
        print("\n=== index.html loader 注入点(前后) ===\n", s2[j - 60 : j + 120])
        break

if "--apply" not in sys.argv:
    print("\n[DRY-RUN] 未写入。加 --apply 执行。")
else:
    for fn, s2 in targets:
        open(fn, "w", encoding="utf-8").write(s2)
    print("\n[APPLIED] 已写入", len(targets), "个文件。")
