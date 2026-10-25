#!/usr/bin/env python3
"""生成发布清单：本地 vs 远程 main 的差集，按发布规则过滤。

规则（写死在这里，避免每轮靠临场判断）：
  发 · 站点运行资产       : html / js / css / sitemap.xml / assets/js|css|images
  发 · 索引与数据资产     : assets/js/article-index.json 等站点引用到的 JSON
  发 · 治理与工具脚本     : scripts/ 下**无日期戳**的通用脚本、ci/ 下 json|py
  发 · 治理留痕           : reports/*.json、compliance/*.json、*.md(excluded by gitignore anyway)
  不发 · 一次性日期戳脚本 : scripts/ 内含 yyyymmdd 或以 _ 开头且带日期的脚本
  不发 · 发布临时清单     : .gp_* / .p0_* / .p0_1_* / .next_path_files.txt / .analytics_* / .bing_*
  不发 · 备份与部署包     : *.bak / *.zip / assets/qa/scf/**（SCF 走独立管线，命名 *.scf_）
  不发 · 本站无关产物     : outputs/**、本地分析 CSV
  不发 · 知识库大包       : assets/qa/kb.json（3.4MB，属 SCF 管线，不在 GP 批次）

用法: python3 scripts/build_publish_list.py > /tmp/publish_list.txt
"""
import csv, os, re, sys, subprocess

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()
CSV_PATH = os.path.join("outputs", "local-vs-remote-main.csv")

# E-017 护栏：曾因「先跑 mutate 脚本（回填 published_time），再读上一轮生成的 CSV」
# 导致 26 篇被回填过的文章压根没进发布清单——清单来自快照，不是现状。
# 铁律：**清单必须从当次现状重算**，不允许复用上一次的分类结果。
print("[0/2] 重新比对本地 vs %s（强制重算，不复用旧 CSV）..." % (
    os.environ.get("REMOTE_REF", "origin/main")), file=sys.stderr)
subprocess.run([sys.executable, "scripts/classify_local_vs_remote.py"],
               cwd=ROOT, check=True,
               stdout=subprocess.DEVNULL)
print("[1/2] 按发布规则过滤 ...", file=sys.stderr)
DATE_STAMP = re.compile(r"(20\d{6}|\d{8})")
ONE_OFF_PREFIX = re.compile(r"^(drive_publish|gen_.*banner)")
TEMP_MANIFEST = re.compile(r"^\.(gp_|p0|p1|next_path|analytics|bing|scf)")

rows = list(csv.DictReader(open(CSV_PATH)))
cand = [r["path"] for r in rows if r["status"] in ("DIFFER", "NEW")]

# 本轮新增脚本也要带上（不在旧 CSV 里）
EXTRA = [
    "scripts/backfill_published_time.py",
    "scripts/site_container_audit.py",
    "scripts/verify_kpi_caliber.py",
    "scripts/align_og_title.py",
    "scripts/fix_meta_hygiene.py",
    "scripts/close_all_clusters.py",
    "scripts/dedupe_meta_descriptions.py",
    "scripts/release_preflight.py",
    "scripts/kb_bridge.py",
    "scripts/kb_precheck.py",
    "scripts/classify_local_vs_remote.py",
    "scripts/build_publish_list.py",
    "ci/escape-ledger.json",
    "ci/meta-variant-allowlist.json",
]

publish, skipped = [], []
seen = set()


def decide(p):
    base = os.path.basename(p)
    if TEMP_MANIFEST.match(base):
        return False, "发布临时清单"
    if p.startswith("outputs/"):
        return False, "本站无关产物"
    if p.startswith("assets/qa/scf/") or base.startswith("aihr-qa-scf") or base.endswith((".bak", ".zip")):
        return False, "备份/部署包（SCF 独立管线）"
    if p == "assets/qa/kb.json":
        return False, "知识库大包（SCF 管线）"
    if p.startswith("scripts/"):
        # 只按「一次性」这一个性质过滤：文件名带日期戳 / 明确的一次性驱动脚本。
        # `_` 前缀本身不作为过滤条件——远程已有 26 个 `_` 前缀脚本在库里，
        # 无日期戳的 `_scan_*` / `_verify_*` 是可复用审计工具，必须入库。
        if DATE_STAMP.search(base) or ONE_OFF_PREFIX.match(base):
            return False, "一次性日期戳脚本"
    if p.startswith("_baidu_daily_run"):
        return False, "一次性跑批脚本"
    return True, ""


# EXTRA 是「本轮新建、CSV 可能还没覆盖」的安全网；但绝不能无条件追加——
# 否则已发布且内容未变的工具会被反复带进批次（虚假差异）。只在 NEW/DIFFER 时补。
status_map = {r["path"]: r["status"] for r in rows}
cand = cand + [p for p in EXTRA
               if os.path.exists(p) and status_map.get(p, "NEW") in ("NEW", "DIFFER")]

for p in cand:
    if p in seen:
        continue
    seen.add(p)
    if not os.path.exists(p):
        skipped.append((p, "本地已不存在"))
        continue
    ok, why = decide(p)
    if ok:
        publish.append(p)
    else:
        skipped.append((p, why))

publish.sort()
sys.stderr.write("[2/2] 发布 %d / 排除 %d\n" % (len(publish), len(skipped)))
for p, why in sorted(skipped):
    sys.stderr.write("  SKIP  %-56s %s\n" % (p, why))
print("\n".join(publish))
