#!/usr/bin/env python3
# scripts/patch_publish_2026.py
# Consolidated publish for A (genai article refresh) + C (new org-redesign article) + B (geo batch).
# SEO/GEO intent: A fixes METR single-point reliance with larger-sample 2026 evidence;
# C is a new org-restructuring asset (BCG + McKinsey 2026); B extends GEO capsules to high in-link articles.
#
# Publish is now ATOMIC: all changed files land in ONE commit (git_atomic.atomic_commit),
# so main is never observed in an inconsistent intermediate state and the CI quality gate
# no longer fails on in-progress commits.
#
# Usage:
#   python3 scripts/patch_publish_2026.py            # push for real
#   python3 scripts/patch_publish_2026.py --dry-run  # build commit objects, do NOT update ref
import os, sys, subprocess, importlib.util
import git_atomic

ROOT = git_atomic.ROOT
DRY = "--dry-run" in sys.argv

# Files changed by A + C (sitemap.xml shared)
CHANGED = [
    "articles/genai-productivity-evidence-2026.html",
    "articles/ai-org-redesign-2026.html",
    "assets/js/article-index.json",
    "articles/index.html",
    "sitemap.xml",
    "llms-full.txt",
]

COMMIT_MSG = "publish: refresh genai evidence + new org-redesign article (atomic)"


def run_quality_gate(tag):
    print(f"\n=== quality_gate.py --all ({tag}) ===")
    try:
        out = subprocess.run([sys.executable, "scripts/quality_gate.py", "--all"],
                              cwd=ROOT, capture_output=True, text=True, timeout=300)
    except Exception as e:
        print("  gate run error:", e); return False
    print(out.stdout[-1500:] if len(out.stdout) > 1500 else out.stdout)
    if out.stderr:
        print("STDERR:", out.stderr[-800:])
    return ("质量门全部通过" in out.stdout) or ("🟢" in out.stdout and "全部通过" in out.stdout)


def main():
    # 1) quality gate on current repo state (A + C merged)
    ok = run_quality_gate("pre-push")
    if not ok:
        print("\n[ABORT] quality gate did not report all-pass. Inspect output above; fix before pushing.")
        sys.exit(1)

    # 2) push A + C changed files ATOMICALLY (single commit)
    print("\n=== pushing A + C changed files (atomic) ===")
    git_atomic.atomic_commit(CHANGED, COMMIT_MSG, dry_run=DRY)

    # 3) B: geo capsule batch (dry-run first to review, then apply)
    print("\n=== B: geo capsule batch (apply) ===")
    sys.argv = ["patch_geo_batch_2026.py", "--apply"] + (["--dry-run"] if DRY else [])
    try:
        spec = importlib.util.spec_from_file_location(
            "geo_batch", os.path.join(ROOT, "scripts", "patch_geo_batch_2026.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    except Exception as e:
        print("  B batch error:", repr(e))

    # 4) final quality gate
    run_quality_gate("post-push")

    # 5) remote verify A + C
    print("\n=== remote verify A + C ===")
    res = git_atomic.verify_remote(
        ["articles/genai-productivity-evidence-2026.html",
         "articles/ai-org-redesign-2026.html"],
        needle="geo-answer-capsule")
    for k, v in res.items():
        print(f"  {k}: capsule={v}")
    print("\n[DONE]" + (" (dry-run, ref not updated)" if DRY else ""))


if __name__ == "__main__":
    main()
