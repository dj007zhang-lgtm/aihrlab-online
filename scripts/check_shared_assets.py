#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_shared_assets.py —— Gate 15：共享资源完整性门（前置架构健壮性护栏）

为什么需要这扇门：
  stability_guard.py 的 S5 资源检查只扫 .html/.css，JS 完全不在任何闸门扫描范围；
  quality_gate.py 也无 JS 语法校验。于是「写出坏 main.js」会被两道闸门全绿放行，
  导致全站交互静默崩溃（最致命的架构盲区）。

本门覆盖：
  1. 每个 HTML 必须引用 style.min.css 与 main.js（防止 13 页缺 main.js 类回归）。
  2. assets/js/ 下每个 .js 必须通过 node --check（语法校验，拦住坏 JS）。
  3. assets/js/ 下每个 .json 必须可被 json 解析（拦住坏索引/坏数据）。
  4. 规范共享资源 main.js 与 style.min.css 在磁盘上真实存在（拦住误删/改名）。

node 不可用时（罕见 CI 环境）仅跳过 JS 语法检查并给出 WARNING，不阻断发布。

用法：
  python3 scripts/check_shared_assets.py                 # 以仓库根目录为 site_root 扫描
  python3 scripts/check_shared_assets.py /path/to/site  # 指定 site_root
  python3 scripts/check_shared_assets.py --selftest     # 自检（负样本证伪 + 正样本证真）
"""
import os
import sys
import re
import json
import shutil
import subprocess

THRESH = re.compile(r"(log|_log)\.json$", re.IGNORECASE)


def _find_node():
    if os.environ.get("AIHR_NODE") and os.path.exists(os.environ["AIHR_NODE"]):
        return os.environ["AIHR_NODE"]
    p = shutil.which("node")
    if p:
        return p
    managed = "/Users/andyzhang/.workbuddy/binaries/node/versions/22.22.2/bin/node"
    if os.path.exists(managed):
        return managed
    return None


def _all_html(site_root):
    out = []
    for root, dirs, files in os.walk(site_root):
        if ".git" in dirs:
            dirs.remove(".git")
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        for f in files:
            if f.endswith(".html"):
                out.append(os.path.join(root, f))
    return out


# 这些页面不要求加载规范共享资源（main.js / style.min.css）：
#  - 搜索引擎站点验证文件（google/baidu verify）：必须是极简 meta 页；
#  - seo-monitor.html：监控页；
#  - tools/ 下独立工具页：自带样式与脚本；
#  - 重定向桩页（迁移占位）：迟早下线，不应被强制注入主站 JS。
_STUB_MARK = ("window.location.replace", "本页面已迁移")
_VERIFY_RE = re.compile(r"(google|baidu).*(verif|验证|verify)", re.IGNORECASE)


def _is_exempt(path, site_root):
    name = os.path.basename(path)
    rel = os.path.relpath(path, site_root)
    # 搜索引擎站点验证文件：google<hex>.html / baidu_verify_<code>.html
    if re.search(r"(google[a-z0-9]{4,}\.html$|baidu_verify)", name, re.I):
        return True
    if "seo-monitor" in name:
        return True
    # 独立资源/工具页：tools/ 与 assets/ 下的 HTML 不套用主站 chrome
    if rel.startswith("tools" + os.sep) or ("/tools/" in rel):
        return True
    if rel.startswith("assets" + os.sep) or ("/assets/" in rel):
        return True
    try:
        t = open(path, encoding="utf-8", errors="ignore").read()
        if any(m in t for m in _STUB_MARK):
            return True
        # 内容含搜索引擎验证 meta 的文件（极简验证页）
        if "google-site-verification" in t or "baidu-site-verification" in t:
            return True
    except Exception:
        pass
    return False


def run(site_root):
    """返回 (passed: bool, details: list[str])。"""
    details = []
    node = _find_node()

    # ---- 1) 每个（非豁免）HTML 必须引用 style.min.css 与 main.js ----
    html_files = _all_html(site_root)
    missing_css = []
    missing_js = []
    for p in html_files:
        if _is_exempt(p, site_root):
            continue
        try:
            html = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        rel = os.path.relpath(p, site_root)
        if not re.search(r'href=["\'][^"\']*style\.min\.css', html):
            missing_css.append(rel)
        if not re.search(r'src=["\'][^"\']*main\.js', html):
            missing_js.append(rel)
    if missing_css:
        details.append("以下页面未引用 style.min.css（规范共享样式缺失）：" + ", ".join(missing_css[:20]))
    if missing_js:
        details.append("以下页面未引用 main.js（交互/导航/搜索将失效）：" + ", ".join(missing_js[:20]))

    # ---- 2) assets/js/*.js 必须通过 node --check ----
    js_dir = os.path.join(site_root, "assets", "js")
    if os.path.isdir(js_dir):
        if node:
            for f in sorted(os.listdir(js_dir)):
                if not f.endswith(".js"):
                    continue
                fp = os.path.join(js_dir, f)
                try:
                    r = subprocess.run([node, "--check", fp],
                                       capture_output=True, text=True, timeout=60)
                    if r.returncode != 0:
                        details.append("JS 语法错误 %s：%s" % (f, (r.stderr or r.stdout).strip().splitlines()[-1]))
                except Exception as e:
                    details.append("node --check 执行失败 %s：%s" % (f, e))
        else:
            details.append("WARNING: 未找到 node，跳过 JS 语法检查（请在 CI/本地确保 node 可用）")

    # ---- 3) assets/js/*.json 必须可解析 ----
    if os.path.isdir(js_dir):
        for f in sorted(os.listdir(js_dir)):
            if not f.endswith(".json"):
                continue
            if THRESH.search(f):
                continue  # 跳过推送日志等易变文件
            fp = os.path.join(js_dir, f)
            try:
                json.load(open(fp, encoding="utf-8"))
            except Exception as e:
                details.append("JSON 解析失败 %s：%s" % (f, e))

    # ---- 4) 规范共享资源必须存在 ----
    for rel in ("assets/js/main.js", "assets/css/style.min.css"):
        if not os.path.exists(os.path.join(site_root, rel)):
            details.append("规范共享资源缺失（全站依赖）：%s" % rel)

    return (len(details) == 0), details


def _selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="csg_selftest_")
    try:
        os.makedirs(os.path.join(tmp, "assets", "js"))
        os.makedirs(os.path.join(tmp, "assets", "css"))
        # 规范资源
        open(os.path.join(tmp, "assets", "js", "main.js"), "w").write("console.log('ok');")
        open(os.path.join(tmp, "assets", "css", "style.min.css"), "w").write("/* ok */")
        # 坏 JS（语法错误：未闭合括号 + 非法赋值）
        open(os.path.join(tmp, "assets", "js", "bad.js"), "w").write("function x({ return 1; }")
        # 坏 JSON
        open(os.path.join(tmp, "assets", "js", "broken.json"), "w").write("{not valid")
        # 一个缺 main.js 的 HTML
        open(os.path.join(tmp, "bad.html"), "w").write(
            '<html><head><link rel="stylesheet" href="/assets/css/style.min.css"></head><body>x</body></html>')
        open(os.path.join(tmp, "ok.html"), "w").write(
            '<html><head><link rel="stylesheet" href="/assets/css/style.min.css">'
            '<script src="/assets/js/main.js" defer></script></head><body>x</body></html>')

        ok, det = run(tmp)
        assert ok is False, "负样本应判定 FAIL，但得到 PASS: %s" % det
        assert any("bad.js" in d for d in det), "应检出坏 JS：%s" % det
        assert any("broken.json" in d for d in det), "应检出坏 JSON：%s" % det
        assert any("bad.html" in d for d in det), "应检出缺 main.js 的页面：%s" % det

        # 修正为全绿
        open(os.path.join(tmp, "assets", "js", "bad.js"), "w").write("function x(){ return 1; }")
        open(os.path.join(tmp, "assets", "js", "broken.json"), "w").write('{"a":1}')
        open(os.path.join(tmp, "bad.html"), "w").write(
            '<html><head><link rel="stylesheet" href="/assets/css/style.min.css">'
            '<script src="/assets/js/main.js" defer></script></head><body>x</body></html>')
        ok2, det2 = run(tmp)
        assert ok2 is True, "修正后应 PASS，但得到 FAIL: %s" % det2
        print("check_shared_assets selftest: PASS")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if _selftest() else 1)
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok, details = run(root)
    for d in details:
        print(("  • " + d))
    print("Gate 15 (shared assets): " + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
