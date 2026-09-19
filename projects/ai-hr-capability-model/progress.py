#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CM-2026 进展生成器

产出 06-PROGRESS.md 的「机器段」。设计原则只有一条：
    **进展不得手写。** 凡机器能判定的状态，必须由本脚本产出；
    人只写「为什么」和「下一步」。

用法：
    python3 projects/ai-hr-capability-model/progress.py            # 打印机器段
    python3 projects/ai-hr-capability-model/progress.py --write    # 写回 06-PROGRESS.md
"""
import os
import re
import io
import sys
import json
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(os.path.dirname(ROOT))
PROGRESS = os.path.join(ROOT, "06-PROGRESS.md")
BASELINE = os.path.join(SITE, "ci", "baseline", "health_baseline.json")
CJK = re.compile(r"[\u4e00-\u9fff]")


def read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def run_validate():
    """实跑校验脚本，直接取结构化结果。

    不用 subprocess + 正则解析 stdout：validate.py 的表格是按内容宽度对齐的，
    实测列过长时会把「期望」列挤掉，正则必漏——首版就因此产出了一张空表。
    改为 import 后读 RESULTS，与 CLI 走的是同一套断言，但拿到的是结构化数据。
    """
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        import validate as v
        buf, old = io.StringIO(), sys.stdout
        try:
            sys.stdout = buf
            code = v.main()
        finally:
            sys.stdout = old
        rows = [(r["id"], r["name"], r["status"], str(r["actual"]))
                for r in v.RESULTS]
        return code, buf.getvalue(), rows
    except Exception as e:
        return None, f"运行失败：{e}", []


def scan_articles():
    A = os.path.join(SITE, "articles")
    if not os.path.isdir(A):
        return {}
    total = flagship = thin = 0
    words = []
    for fn in os.listdir(A):
        if not fn.endswith(".html") or fn == "index.html":
            continue
        h = read(os.path.join(A, fn))
        if 'name="robots" content="noindex' in h or 'http-equiv="refresh"' in h:
            continue
        m = re.search(r"<article\b[^>]*>(.*?)</article>", h, re.S | re.I)
        t = re.sub(r"<[^>]+>", "", m.group(1) if m else h)
        n = len(CJK.findall(t))
        total += 1
        words.append(n)
        if n >= 5000:
            flagship += 1
        elif n < 500:
            thin += 1
    words.sort()
    med = words[len(words) // 2] if words else 0
    return {"total": total, "flagship": flagship, "thin": thin, "median": med}


def baseline():
    d = read(BASELINE)
    if not d:
        return {}
    try:
        return json.loads(d)
    except Exception:
        return {}


def pending_h():
    """统计 H 类未决项（解析决策台账）。"""
    t = read(os.path.join(ROOT, "02-DECISIONS.md"))
    ids = []
    for m in re.finditer(r"^\|\s*(D-\d+)\s*\|([^|]*)\|([^|]*)\|\s*H\s*\|\s*未决", t, re.M):
        ids.append(m.group(1))
    return ids


def mirror_state():
    t = read(os.path.join(ROOT, "MIRROR-LEXIANG.md"))
    st = re.search(r"mirror_status:\s*(\S+)", t)
    sid = re.search(r"mirror_space_id:\s*(\S+)", t)
    return (st.group(1) if st else "缺失"), (sid.group(1) if sid else "缺失")


def render():
    code, _out, rows = run_validate()
    art = scan_articles()
    bl = baseline()
    gates = bl.get("gates", {}) if isinstance(bl, dict) else {}
    hid = pending_h()
    mst, msid = mirror_state()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    L = []
    L.append(f"> 本段由 `progress.py` 于 {now} 自动生成，**禁止手改**。")
    L.append("> 人写的部分在本文件下半部「判断与下一步」。")
    L.append("")
    L.append("### 校验（实跑 `validate.py`）")
    L.append("")
    L.append(f"退出码 `{code}`（0=全过） · 共 {len(rows)} 项")
    L.append("")
    L.append("| ID | 检查项 | 状态 | 实测 |")
    L.append("|---|---|---|---|")
    for cid, name, st, actual in rows:
        a = actual if len(actual) <= 60 else actual[:57] + "…"
        L.append(f"| {cid} | {name} | {st} | {a} |")
    L.append("")
    L.append("### 站点内容结构")
    L.append("")
    L.append("| 指标 | 值 |")
    L.append("|---|---|")
    L.append(f"| 可索引文章 | {art.get('total', 0)} 篇 |")
    L.append(f"| 中位字数 | {art.get('median', 0)} 字 |")
    L.append(f"| 5000+ 字旗舰 | {art.get('flagship', 0)} 篇 |")
    L.append(f"| <500 字薄内容 | {art.get('thin', 0)} 篇 |")
    L.append(f"| qa_guardian 基线克隆集群 | {gates.get('clone_detection', {}).get('clone_clusters', '—')} |")
    L.append(f"| qa_guardian 基线薄内容 | {gates.get('stub_detector', {}).get('thin_block', '—')} |")
    L.append("")
    L.append("### 阻塞与未决")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| H 类未决（主理人独占） | {len(hid)} 项：{', '.join(hid) if hid else '无'} |")
    L.append(f"| 镜像落点 | {mst} / space_id={msid} |")
    return "\n".join(L)


def main():
    body = render()
    if "--write" in sys.argv:
        t = read(PROGRESS)
        if not t:
            print("06-PROGRESS.md 不存在，请先创建"); return 1
        pat = re.compile(r"(<!-- MACHINE:START -->)(.*?)(<!-- MACHINE:END -->)", re.S)
        if not pat.search(t):
            print("06-PROGRESS.md 缺少 MACHINE 标记区间"); return 1
        new = pat.sub(lambda m: m.group(1) + "\n\n" + body + "\n\n" + m.group(3), t)
        with open(PROGRESS, "w", encoding="utf-8") as f:
            f.write(new)
        print("已写回 06-PROGRESS.md 的机器段")
        return 0
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
