#!/usr/bin/env python3
"""Fix malformed FAQPage JSON-LD (missing closing brace) in 5 article files.

Both broken files are missing exactly one `}`. Two trailing signatures:
  Pattern A (ai-performance-management): ends `...。"} ]}`  -> does NOT end with `]`,
                the `]` is preceded by `"...}"` missing the Question-close `}` -> insert `}` before `]`.
  Pattern B (the other 4):              ends `..."}}\n]`    -> ends with `]`,
                missing the FAQPage-close `}` -> append `}` after `]`.
Only the 2nd ld+json block (FAQPage) is touched; everything else is read-only.
"""
import re, json, sys

TARGETS = [
    "articles/ai-performance-management.html",
    "articles/hr-three-pillar-ai.html",
    "articles/ai-flattening-management-guide.html",
    "articles/ai-hr-2026-h2-outlook.html",
    "articles/ai-layoff-compliance-guide.html",
]

SCRIPT_RE = re.compile(r'<script([^>]*type="application/ld\+json"[^>]*)>(.*?)</script>', re.S)


def fix_block(content: str):
    b = content.strip()
    no, nc = b.count("{"), b.count("}")
    if no == nc:
        return b, no, nc, "already-ok"
    if no - nc != 1:
        return b, no, nc, "unexpected-imbalance"
    if b.rstrip().endswith("]"):
        # Pattern B: append missing FAQPage-close `}`
        fixed = b.rstrip() + "}"
        return fixed, no, fixed.count("}"), "pattern-b"
    # Pattern A: insert missing Question-close `}` before the mainEntity-closing `]`
    fixed = re.sub(r'("})\s*]', r'\1 }]', b, count=1)
    return fixed, no, fixed.count("}"), "pattern-a"


def main():
    all_ok = True
    for rel in TARGETS:
        html = open(rel, encoding="utf-8").read()
        blocks = SCRIPT_RE.findall(html)
        if len(blocks) < 2:
            print(f"[SKIP] {rel}: only {len(blocks)} ld+json blocks"); all_ok = False; continue
        attrs, content = blocks[1]  # FAQPage is the 2nd block
        fixed, no, nc, kind = fix_block(content)
        if kind in ("unexpected-imbalance",) or no != nc:
            print(f"[FAIL] {rel}: {kind} ({no}/{nc})"); all_ok = False; continue
        try:
            obj = json.loads(fixed)
        except Exception as e:
            print(f"[FAIL] {rel}: json invalid after fix: {e}"); all_ok = False; continue
        q = len(obj.get("mainEntity", [])) if isinstance(obj, dict) else 0
        old_full = "<script" + attrs + ">" + content + "</script>"
        new_full = "<script" + attrs + ">\n" + fixed + "\n</script>"
        if old_full not in html:
            print(f"[FAIL] {rel}: exact block not found for replacement"); all_ok = False; continue
        html2 = html.replace(old_full, new_full, 1)
        open(rel, "w", encoding="utf-8").write(html2)
        print(f"[OK] {rel}: {kind}, balanced {no}/{nc}, FAQ questions={q}")
    print("\nALL OK" if all_ok else "\nSOME FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
