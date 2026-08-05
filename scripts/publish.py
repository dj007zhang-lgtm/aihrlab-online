#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py —— 网站唯一强制发布入口（MANDATORY PUBLISHING GATEWAY）

职责：
  1. 发布前强制跑 scripts/quality_gate.py --all（含 Gate 0 二维码唯一关）。
  2. 任一质量门 FAIL 则**中止推送**，绝不带病上线。
  3. 质量门全绿后，调用 scripts/git_atomic.py 原子提交到远程 main。

为什么必须有这个入口：
  - 把「流程＝跑质量门→通过才推送」从『建议』变成『代码强制』，
    任何绕过 quality_gate 的手动原子推送都属违规。
  - 禁止行为：直接调用 git_atomic.atomic_commit 而不先过 quality_gate。

用法：
  python3 scripts/publish.py "feat: 提交说明" file1.html file2.png ...
  python3 scripts/publish.py "fix: ..." --dry-run path/to/x.html   # 只跑质量门+演练提交
"""
import sys
import os
import subprocess

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SITE_ROOT, "scripts"))

import git_atomic as g


def run_quality_gate():
    print("=" * 60)
    print("STEP 1/2  运行质量门 scripts/quality_gate.py --all")
    print("=" * 60)
    proc = subprocess.run(
        [sys.executable, "scripts/quality_gate.py", "--all"],
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

    # STEP 1: 质量门（强制）
    if not run_quality_gate():
        print("\n❌ 质量门未全部通过 —— 推送已中止，禁止带病上线。")
        print("   请修复上述 FAIL 后重试。本次未做任何远程写入。")
        sys.exit(1)
    print("\n✅ 质量门全部通过（含 Gate 0 二维码唯一关）。")

    # STEP 2: 原子推送
    print("\n" + "=" * 60)
    print(f"STEP 2/2  原子推送 {len(files)} 个文件到远程 main" + ("（DRY-RUN）" if dry_run else ""))
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
    print("STEP 3  远程校验")
    v = g.verify_remote(files, needle="article-footer-qr")
    all_ok = True
    for f, ok in v.items():
        if not ok:
            all_ok = False
        print(("OK  " if ok else "FAIL ") + f)
    if not all_ok:
        print("\n⚠️ 部分文件远程校验失败，请人工复核。")
        sys.exit(1)
    print("\n✅ 发布完成：质量门通过 + 原子推送 + 远程校验全绿。")


if __name__ == "__main__":
    main()
