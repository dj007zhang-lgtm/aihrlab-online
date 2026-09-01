#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_qa_kb.py — AIHR 问答系统知识库 ETL

把 site-migrated/articles/*.html 的已发布文章切片成可检索文本块（chunk），
输出 assets/qa/kb.json（供无服务器中继做 BM25 检索召回）与 kb.meta.json（统计）。

设计纪律：
- 仅使用 Python 标准库（html.parser），零外部依赖。
- 兼容两种文章格式：v2 模板（.article-body + <section><h2>）与旧版（.article-content + 裸 <h2 id>）。
- 跳过 redirect 桩页（http-equiv="refresh" / robots=noindex）。
- 跳过站内噪声：nav / header.site-header / footer.site-footer / figure.banner /
  .toc / .inline-related / .related-reading / .article-footer-qr / .article-header(含H1+lead) / .article-meta / .article-tags。
- 切片以 H2 小节为单位，长小节按句再切，保证召回粒度。
- 零虚构：文本 100% 来自原文；title/category/date/tags 取自 article-index.json 真相源。

用法：
  python3 scripts/build_qa_kb.py
"""
import argparse
import html
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 整块丢弃的 class
SKIP_CLASSES = {
    "toc", "inline-related", "related-reading", "article-footer-qr",
    "article-banner", "article-meta", "article-tags",
    "site-header", "site-footer",
}
# 整标签丢弃（注意：不放 header/article，否则会吞掉用 <header> 包裹小节的旧格式 h2）
SKIP_TAGS = {"script", "style", "noscript", "head", "footer", "figure", "nav", "aside"}
# 参与正文文本抽取的标签
TEXT_TAGS = {"p", "li", "td", "th", "blockquote", "h2", "h3", "h4", "dd", "dt"}
# 单个 chunk 文本超过该长度则按句再切
CHUNK_SOFT_LIMIT = 900


@dataclass
class Chunk:
    id: str
    slug: str
    title: str
    url: str
    category: str
    date: str
    tags: list
    heading: str
    text: str


class ArticleExtractor(HTMLParser):
    """格式无关的抽取器：skip_depth 跟踪噪声嵌套，H2 起新块。"""

    def __init__(self, slug, meta):
        super().__init__(convert_charrefs=True)
        self.slug = slug
        self.meta = meta
        self.skip_depth = 0
        self.skip_stack = []
        self.in_scope = False
        self.chunks = []
        self.cur = None
        self._capture = False
        self._buf = []

    def _classes(self, attrs):
        for k, v in attrs:
            if k == "class" and v:
                return set(v.split())
        return set()

    def _is_skip(self, tag, attrs):
        if tag in SKIP_TAGS:
            return True
        return bool(self._classes(attrs) & SKIP_CLASSES)

    def _flush(self):
        if self.cur is not None and self.cur.text.strip():
            self.chunks.append(self.cur)
        self.cur = None

    def _split_long(self, heading, text):
        paras = [p.strip() for p in re.split(r"(?<=[。.!?！？])\s*", text) if p.strip()]
        out, buf = [], ""
        for p in paras:
            if buf and len(buf) + len(p) > CHUNK_SOFT_LIMIT:
                out.append((heading, buf.strip()))
                buf = p
            else:
                buf = (buf + " " + p).strip() if buf else p
        if buf.strip():
            out.append((heading, buf.strip()))
        return out or [(heading, text.strip())]

    def _emit(self, heading, text):
        for h, t in self._split_long(heading, text):
            self.chunks.append(Chunk(
                id=f"{self.slug}#{len(self.chunks)+1}",
                slug=self.slug,
                title=self.meta.get("title", ""),
                url=self.meta.get("url", self.slug),
                category=self.meta.get("category", ""),
                date=self.meta.get("date", ""),
                tags=self.meta.get("tags", []),
                heading=h,
                text=t,
            ))

    def handle_starttag(self, tag, attrs):
        cls = self._classes(attrs)
        attrs_dict = dict(attrs)
        is_skip = self._is_skip(tag, attrs)
        is_body = (tag == "article") or (
            tag == "div" and (
                cls & {"article-body", "article-content"}
                or attrs_dict.get("itemprop") == "articleBody"
            )
        )
        if is_body:
            self.in_scope = True
            self.skip_depth = 0
            self.skip_stack = []
        self.skip_stack.append((tag, is_skip))
        if is_skip:
            self.skip_depth += 1
            return
        if not self.in_scope:
            return
        if tag in ("h2", "h3"):
            # 安全护栏：真实小节标题出现即清零可能由畸形嵌套残留的 skip 状态
            self.skip_depth = 0
            self.skip_stack = []
            self._flush()
            self.cur = Chunk(
                id=f"{self.slug}#pending", slug=self.slug,
                title=self.meta.get("title", ""), url=self.meta.get("url", self.slug),
                category=self.meta.get("category", ""), date=self.meta.get("date", ""),
                tags=self.meta.get("tags", []), heading="", text="",
            )
            self._capture = True
            self._buf = []
            return
        if tag in TEXT_TAGS:
            self._capture = True
            self._buf = []

    def handle_endtag(self, tag):
        if not self.skip_stack:
            return
        started_tag, was_skip = self.skip_stack.pop()
        if was_skip:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if not self.in_scope:
            return
        if self._capture and started_tag in TEXT_TAGS:
            txt = html.unescape("".join(self._buf)).strip()
            self._buf = []
            self._capture = False
            if txt:
                if self.cur is None:
                    self.cur = Chunk(
                        id=f"{self.slug}#pending", slug=self.slug,
                        title=self.meta.get("title", ""), url=self.meta.get("url", self.slug),
                        category=self.meta.get("category", ""), date=self.meta.get("date", ""),
                        tags=self.meta.get("tags", []), heading="", text="",
                    )
                if started_tag in ("h2", "h3"):
                    self.cur.heading = txt
                else:
                    self.cur.text = (self.cur.text + "\n" + txt).strip() if self.cur.text else txt

    def handle_data(self, data):
        if self.in_scope and self.skip_depth == 0 and self._capture:
            self._buf.append(data)

    def close(self):
        self._flush()
        super().close()


def is_stub(path):
    head = open(path, "r", encoding="utf-8", errors="ignore").read(8192).lower()
    return ('http-equiv="refresh"' in head) or ('name="robots" content="noindex"' in head)


def clean_text(s):
    return re.sub(r"\s+", " ", s).strip()


def build(articles_dir, index_path, out_dir):
    index = json.load(open(index_path, "r", encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    stats = {"articles_total": len(index), "articles_parsed": 0,
             "stubs_skipped": 0, "articles_with_zero_chunks": 0,
             "chunks_total": 0, "chars_total": 0, "per_article": {}}
    all_chunks = []

    for entry in index:
        slug = entry["url"]
        path = os.path.join(articles_dir, slug + ".html")
        if not os.path.exists(path):
            stats["articles_with_zero_chunks"] += 1
            continue
        if is_stub(path):
            stats["stubs_skipped"] += 1
            continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
        parser = ArticleExtractor(slug, entry)
        parser.feed(src)
        parser.close()
        if not parser.chunks:
            stats["articles_with_zero_chunks"] += 1
            continue
        stats["articles_parsed"] += 1
        stats["per_article"][slug] = len(parser.chunks)
        for c in parser.chunks:
            c.text = clean_text(c.text)
            if not c.text:
                continue
            all_chunks.append(asdict(c))
            stats["chunks_total"] += 1
            stats["chars_total"] += len(c.text)

    for i, ch in enumerate(all_chunks, 1):
        ch["id"] = f"c{i}"

    kb = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "aihrlab.online article library",
        "chunk_count": len(all_chunks),
        "articles_indexed": stats["articles_parsed"],
        "chunks": all_chunks,
    }
    kb_path = os.path.join(out_dir, "kb.json")
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, separators=(",", ":"))

    meta_path = os.path.join(out_dir, "kb.meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"[build_qa_kb] articles_indexed={stats['articles_parsed']} "
          f"stubs_skipped={stats['stubs_skipped']} zero_chunks={stats['articles_with_zero_chunks']}")
    print(f"[build_qa_kb] chunks={stats['chunks_total']} chars={stats['chars_total']} "
          f"kb.json={os.path.getsize(kb_path)/1024:.1f}KB -> {kb_path}")
    return kb_path, meta_path, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--articles-dir", default=os.path.join(ROOT, "articles"))
    ap.add_argument("--index", default=os.path.join(ROOT, "assets/js/article-index.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "assets/qa"))
    args = ap.parse_args()
    build(args.articles_dir, args.index, args.out)
