#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
release_preflight.py — 发布/部署前置对账闸（强制，非零即阻断）

防三类复发故障（详见项目记忆 2026-09-23 复盘）：
  RC1 真相源失守: 环境依赖(如 node 路径)与"上次构建"陈旧快照被当成权威。
  RC2 交付对账闸缺失: 质量门审内容, 无门审"这批文件是不是发往此目的地的正确集合"。
  RC3 双管线混淆: GP 公网发布 与 SCF 云函数上传 被混成一回事 → 清单污染。

用法:
  # GP 公网发布清单对账
  python3 scripts/release_preflight.py --gp .p0_2_publish_files.txt
  # SCF 云函数部署包完整性
  python3 scripts/release_preflight.py --scf assets/qa/aihr-qa-scf-20260922.zip --expected-articles 246

退出码: 0=通过; 1=阻断(逐条打印违规)。
设计纪律: 仅 Python 标准库, 零外部依赖。
"""
import argparse
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SCF 私有资产：绝不允许进入 GP 公网发布清单
SCF_PRIVATE_PATTERNS = (
    "kb.json",
    "build_qa_kb.py",
    "assets/qa/scf/",
    "scf_bootstrap",
    "scf/index.js",
)
# 凭证/敏感文件：任何发布清单都禁带
SECRET_PATTERNS = (".github_token", "credentials", ".env", "secret")
# Node 内置模块白名单（SCF index.js 只允许这些 require）
NODE_BUILTINS = {
    "assert", "buffer", "child_process", "cluster", "crypto", "dgram", "dns",
    "domain", "events", "fs", "http", "http2", "https", "net", "os", "path",
    "perf_hooks", "process", "punycode", "querystring", "readline", "stream",
    "string_decoder", "timers", "tls", "tty", "url", "util", "v8", "vm",
    "worker_threads", "zlib",
}


def fail(msg):
    print(f"  [BLOCK] {msg}")
    return False


def ok(msg):
    print(f"  [OK]    {msg}")
    return True


def resolve_node():
    """glob 扫 versions/*/bin/node，返回最新可用路径或 None。"""
    versions_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(ROOT))),
        ".workbuddy", "binaries", "node", "versions")
    candidates = []
    if os.path.isdir(versions_dir):
        for name in os.listdir(versions_dir):
            p = os.path.join(versions_dir, name, "bin", "node")
            if os.path.exists(p):
                candidates.append(p)
    return sorted(candidates)[-1] if candidates else None


def check_node_env():
    """RC1: 环境指纹。真实 node 必须可解析；脚本不得硬编码失配的绝对路径。"""
    print("[RC1] 环境真相源核验")
    node = resolve_node()
    if not node:
        return fail("未找到任何 node 二进制 (glob versions/*/bin/node 为空)")
    ok(f"node 真实路径: {node}")

    bad = []
    scripts_dir = os.path.join(ROOT, "scripts")
    if os.path.isdir(scripts_dir):
        for fn in os.listdir(scripts_dir):
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(scripts_dir, fn), encoding="utf-8") as f:
                txt = f.read()
            for m in re.finditer(r"(/Users/[^ \"'\n]*?/bin/node)", txt):
                p = m.group(1)
                if not os.path.exists(p):
                    bad.append(f"{fn}: 硬编码 node 路径失配 {p}")
    if bad:
        for b in bad:
            fail(b)
        return False
    ok("scripts 内无失配的硬编码 node 路径")
    return True


def check_gp(list_path):
    """RC2+RC3: GP 公网发布清单对账。"""
    print(f"\n[RC2/RC3] GP 发布清单对账: {list_path}")
    if not os.path.exists(list_path):
        return fail(f"清单文件不存在: {list_path}")
    with open(list_path, encoding="utf-8") as f:
        raw = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    all_ok = True
    seen = set()
    for p in raw:
        # 越界绝对路径
        if os.path.isabs(p):
            all_ok &= fail(f"绝对路径越界(应相对仓库根): {p}")
            continue
        full = os.path.join(ROOT, p)
        if not os.path.exists(full):
            all_ok &= fail(f"路径不存在于仓库: {p}")
            continue
        # 重复
        if p in seen:
            all_ok &= fail(f"重复条目: {p}")
            seen.add(p)
            continue
        seen.add(p)
        # SCF 私有资产串味
        low = p.replace("\\", "/")
        for pat in SCF_PRIVATE_PATTERNS:
            if pat in low:
                all_ok &= fail(f"混入 SCF 私有资产(禁止进 GP): {p}")
                break
        # 凭证文件
        for pat in SECRET_PATTERNS:
            if pat in low:
                all_ok &= fail(f"混入敏感/凭证文件(禁止发布): {p}")
                break
    if all_ok:
        ok(f"清单 {len(seen)} 条全部通过: 存在/无重复/无 SCF 串味/无凭证")
    return all_ok


def check_scf(pkg_path, expected_articles=None):
    """RC1+RC2: SCF 部署包完整性 + 知识库与线上真相对齐。"""
    print(f"\n[RC1/RC2] SCF 部署包完整性: {pkg_path}")
    if not os.path.exists(pkg_path):
        return fail(f"部署包不存在: {pkg_path}")

    names = []
    is_zip = pkg_path.endswith(".zip")
    if is_zip:
        with zipfile.ZipFile(pkg_path) as z:
            names = z.namelist()
    else:
        for dp, _, fns in os.walk(pkg_path):
            for fn in fns:
                names.append(os.path.relpath(os.path.join(dp, fn), pkg_path))

    def has(sub):
        return any(sub in n.replace("\\", "/") for n in names)

    all_ok = True
    # SCF 平台契约：必需文件必须在 zip 根级（平台按根级文件名 unzip 抽取 scf_bootstrap，
    # 嵌套目录会报 "filename not matched: scf_bootstrap"，2026-09-23 上传失败实证）。
    required = {
        "index.js": "函数入口(监听 process.env.PORT)",
        "scf_bootstrap": "云独有启动脚本(必须随包且在根级)",
        "package.json": "零依赖声明(必须随包)",
        "kb.json": "知识库(BM25 召回真相源)",
    }
    names_norm = {n.replace("\\", "/") for n in names}
    for req, why in required.items():
        if req in names_norm:
            ok(f"根级含 {req}")
            continue
        nested = sorted(n for n in names_norm if n.endswith("/" + req))
        if nested:
            all_ok &= fail(
                f"{req} 不在 zip 根级(现嵌于 {nested[0]}) — SCF 将报 filename not matched")
        else:
            all_ok &= fail(f"缺必需文件 {req} — {why}")

    # bootstrap 必须可执行(权限位 0755)
    boot = next((n for n in names_norm if n == "scf_bootstrap"), None)
    if boot:
        if is_zip:
            mode = (zipfile.ZipFile(pkg_path).getinfo(boot).external_attr >> 16) & 0o777
        else:
            mode = os.stat(os.path.join(pkg_path, boot)).st_mode & 0o777
        if mode & 0o111:
            ok(f"scf_bootstrap 可执行(mode={oct(mode)})")
        else:
            all_ok &= fail(f"scf_bootstrap 无可执行权限位(mode={oct(mode)})")

    # kb.json 条数须对齐线上文章数（RC1 真相源）
    kb_name = next((n for n in names if n.replace("\\", "/") == "kb.json"), None)
    if kb_name and expected_articles:
        try:
            if is_zip:
                with zipfile.ZipFile(pkg_path) as z:
                    data = json.loads(z.read(kb_name))
            else:
                with open(os.path.join(pkg_path, kb_name), encoding="utf-8") as f:
                    data = json.load(f)
            arts = data.get("articles_indexed")
            if arts is None:
                arts = data.get("articles") or data.get("docs") or []
            n = arts if isinstance(arts, int) else len(arts)
            if n != expected_articles:
                all_ok &= fail(
                    f"kb.json 文章数 {n} ≠ 线上 {expected_articles} (真相源未对齐)")
            else:
                ok(f"kb.json 文章数 {n} == 线上 {expected_articles}")
        except Exception as e:  # noqa
            all_ok &= fail(f"kb.json 解析失败: {e}")

    # index.js 仅允许 Node 内置模块
    ij = next((n for n in names if n.replace("\\", "/") == "index.js"), None)
    if ij:
        try:
            src = (zipfile.ZipFile(pkg_path).read(ij) if is_zip
                   else open(os.path.join(pkg_path, ij), "rb").read()).decode("utf-8", "ignore")
            foreign = set(re.findall(r"require\(['\"]([^'\"]+)['\"]\)", src)) - NODE_BUILTINS
            if foreign:
                all_ok &= fail(f"index.js 引入非内置模块(SCF 不可用): {sorted(foreign)}")
            else:
                ok("index.js 仅依赖 Node 内置模块")
        except Exception as e:  # noqa
            all_ok &= fail(f"index.js 读取失败: {e}")
    return all_ok


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--gp", metavar="LIST_TXT", help="GP 公网发布清单路径")
    g.add_argument("--scf", metavar="PKG", help="SCF 部署包(zip 或目录)路径")
    ap.add_argument("--expected-articles", type=int, default=None,
                    help="SCF kb.json 应含文章数(对齐线上真相)")
    args = ap.parse_args()

    passed = True
    passed &= check_node_env()
    if args.gp:
        passed &= check_gp(args.gp)
    if args.scf:
        passed &= check_scf(args.scf, args.expected_articles)

    print("\n" + ("=== PREFLIGHT PASS ===" if passed else "=== PREFLIGHT BLOCKED ==="))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
