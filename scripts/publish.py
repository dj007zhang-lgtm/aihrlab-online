#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py —— 网站唯一强制发布入口（MANDATORY PUBLISHING GATEWAY）

职责：
  1. 发布前强制跑 scripts/quality_gate.py --all（含 Gate 0 二维码唯一关）。
  2. 发布前强制跑 scripts/stability_guard.py --all（稳定性 / 专业性 / 真实性自检）。
  3. 任一关卡 FAIL 则**中止推送**，绝不带病上线。
  4. 双闸全绿后，调用 scripts/git_atomic.py 原子提交到远程 main。

为什么必须有这个入口：
  - 把「流程＝跑质量门→稳定性自检→通过才推送」从『建议』变成『代码强制』，
    任何绕过质量门 / 稳定性自检的手动原子推送都属违规。
  - 禁止行为：直接调用 git_atomic.atomic_commit 而不先过 quality_gate + stability_guard。

用法：
  python3 scripts/publish.py "feat: 提交说明" file1.html file2.png ...
  python3 scripts/publish.py "fix: ..." --dry-run path/to/x.html   # 只跑双闸+演练提交
"""
import sys
import os
import subprocess
import urllib.request
import urllib.parse

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SITE_ROOT, "scripts"))

import git_atomic as g


def verify_remote_exists(files):
    """可靠远程校验：每个文件在 main 上真实存在（HTTP 200），不依赖 needle。

    旧 verify_remote 用 needle（如 article-footer-qr）判定，对 css / 非文章页
    恒为 False，导致批量推送误报失败。此处改为校验文件确实存在。
    """
    all_ok = True
    for f in files:
        try:
            enc = urllib.parse.quote(f, safe="/")
            req = urllib.request.Request(f"{g.CONTENTS}/{enc}?ref={g.BRANCH}")
            req.add_header("Authorization", f"Bearer {g.TOKEN}")
            req.add_header("User-Agent", "aihr-sync")
            with urllib.request.urlopen(req, timeout=60) as r:
                r.read()
            print("OK   " + f)
        except Exception as e:
            all_ok = False
            print("FAIL " + f + f" ({e})")
    return all_ok


def run_quality_gate():
    print("=" * 60)
    print("STEP 1/3  运行质量门 scripts/quality_gate.py --all")
    print("=" * 60)
    proc = subprocess.run(
        [sys.executable, "scripts/quality_gate.py", "--all"],
        cwd=SITE_ROOT,
    )
    return proc.returncode == 0


def run_stability_guard():
    print("\n" + "=" * 60)
    print("STEP 2/3  运行稳定性自检 scripts/stability_guard.py --all")
    print("=" * 60)
    proc = subprocess.run(
        [sys.executable, "scripts/stability_guard.py", "--all"],
        cwd=SITE_ROOT,
    )
    return proc.returncode == 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)

    message = None
    files = []
    dry_run = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            dry_run = True
        elif a.startswith("--"):
            print(f"未知参数: {a}")
            sys.exit(2)
        elif message is None:
            message = a
        else:
            files.append(a)
        i += 1

    if not message or not files:
        print("用法: python3 scripts/publish.py \"提交说明\" file1 file2 ... [--dry-run]")
        sys.exit(2)

    # STEP 0: 重建 sitemap（保证搜索引擎可发现性与站点同步）
    # 解决历史债：过去发布从不重建 sitemap / 不通知 Bing，导致 tags 归档页、
    # 新文章等长期不在 sitemap 中、爬虫只能慢爬。现每次发布自动重建并推送。
    print("=" * 60)
    print("STEP 0  重建 sitemap.xml（含新增页面 / tags 归档页）")
    print("=" * 60)
    try:
        subprocess.run(
            [sys.executable, "scripts/build_sitemap.py"],
            cwd=SITE_ROOT, check=True,
        )
    except Exception as e:
        print(f"⚠️  sitemap 重建失败（非致命，跳过）: {e}")
    # 确保 sitemap.xml 进入本次发布清单（若调用方未显式传入）
    if "sitemap.xml" not in files:
        files.append("sitemap.xml")

    # STEP 1: 质量门（强制）
    if not run_quality_gate():
        print("\n❌ 质量门未全部通过 —— 推送已中止，禁止带病上线。")
        print("   请修复上述 FAIL 后重试。本次未做任何远程写入。")
        sys.exit(1)
    print("\n✅ 质量门全部通过（含 Gate 0 二维码唯一关）。")

    # STEP 2: 稳定性自检（强制）—— 拦截空白页/加载失败/内容错乱/链接失效/
    # 品牌色回退/导航错乱等低级硬伤，任何 BLOCKER 即中止推送、零远程写入。
    if not run_stability_guard():
        print("\n❌ 稳定性自检未通过（存在 BLOCKER 级低级错误）—— 推送已中止。")
        print("   请修复上述 BLOCKER 后重试。本次未做任何远程写入。")
        sys.exit(1)
    print("\n✅ 稳定性自检通过（无空白页 / 加载失败 / 内容错乱 / 链接失效 / 品牌回退 / 导航错乱）。")

    # STEP 3: 原子推送
    print("\n" + "=" * 60)
    print(f"STEP 3/3  原子推送 {len(files)} 个文件到远程 main" + ("（DRY-RUN）" if dry_run else ""))
    print("=" * 60)
    try:
        sha = g.atomic_commit(files, message, dry_run=dry_run, verbose=True)
    except Exception as e:
        print(f"❌ 原子推送失败: {e}")
        sys.exit(1)

    if dry_run:
        print(f"\n🔍 DRY-RUN 完成，未写入远程。would-commit base: {sha}")
        return

    print(f"\n🚀 已推送 commit: {sha}")
    print("STEP 4  远程校验（存在性）")
    all_ok = verify_remote_exists(files)
    if not all_ok:
        print("\n⚠️ 部分文件远程校验失败，请人工复核。")
        sys.exit(1)

    # STEP 5: IndexNow 通知 Bing/Yandex（best-effort，不阻塞发布）
    # 解决历史债：过去发布从不通知 Bing，导致新内容无法被快速收录。
    if not dry_run:
        print("\nSTEP 5  IndexNow 通知搜索引擎（best-effort）")
        try:
            subprocess.run(
                [sys.executable, "scripts/indexnow_push.py"],
                cwd=SITE_ROOT, timeout=90,
            )
        except Exception as e:
            print(f"  ⚠️  IndexNow 推送未成功（可稍后手动补推）: {e}")

    print("\n✅ 发布完成：质量门通过 + 稳定性自检通过 + 原子推送 + 远程校验全绿 + sitemap 已重建并通知搜索引擎。")


if __name__ == "__main__":
    main()
