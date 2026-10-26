"""Guideline corpus: official documents -> page-aware chunks -> BM25 index (no external search service).

    python -m app.services.assistant.corpus fetch    # download sources in config/guideline_sources.yaml
    python -m app.services.assistant.corpus build    # chunk + index everything in data/v2/guidelines/
"""
from __future__ import annotations

import html
import json
import math
import re
import sys
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import yaml

from pipeline.config import REPO_ROOT, get_paths, load_city

TOKEN = re.compile(r"[a-z0-9]+|[ऀ-ॿ]+|[ಀ-೿]+")  # latin, devanagari, kannada
STOP = set("the a an of and or to in on for is are be with by as at from this that it its into was were which "
           "can may should will not no if than then there their these those such".split())


def guidelines_dir() -> Path:
    d = get_paths().root / "guidelines"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sources() -> list[dict]:
    path = REPO_ROOT / load_city()["assistant"]["sources_file"]
    return yaml.safe_load(path.read_text())["sources"]


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header") and self.skip:
            self.skip -= 1
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "tr", "br", "div"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def fetch_all() -> None:
    for s in sources():
        ext = "pdf" if s.get("kind") == "pdf" else "html"
        out = guidelines_dir() / f"{s['id']}.{ext}"
        if out.exists():
            print(f"have {out.name}")
            continue
        try:
            req = urllib.request.Request(s["url"], headers={"User-Agent": "NeighborHealth/2.0 (public health project)"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                out.write_bytes(resp.read())
            print(f"downloaded {out.name}")
        except Exception as e:
            print(f"FAILED {s['id']}: {e}  -> update the URL in config/guideline_sources.yaml or add the file manually")


def _pages(path: Path) -> list[tuple[int, str]]:
    if path.suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = [(i + 1, p.extract_text(x_tolerance=1.5) or "") for i, p in enumerate(pdf.pages)]
        if sum(len(t) for _, t in pages) < 200 * max(len(pages), 1) * 0.1:
            # No text layer (some official PDFs have text converted to outlines): OCR once, cache the result.
            cache = path.with_suffix(".ocr.json")
            if not cache.exists():
                from pipeline.extract.ocr_extractor import ocr_pdf_pages
                print(f"  {path.name} has no text layer; running OCR (one-off, cached)...")
                cache.write_text(json.dumps(ocr_pdf_pages(path)))
            pages = [(i + 1, t) for i, t in enumerate(json.loads(cache.read_text()))]
        return pages
    raw = path.read_text(errors="ignore")
    if path.suffix in (".html", ".htm"):
        start = raw.find('id="maincont"')           # NCVBDC pages: real content lives here
        if start >= 0:
            raw = raw[start:].split(">", 1)[-1]
        p = _Text()
        p.feed(raw)
        raw = "".join(p.parts)
        end = raw.find("Disclaimer")               # footer: policies, visitor counter
        if start >= 0 and end > 0:
            raw = raw[:end]
        raw = html.unescape(raw)
    return [(1, raw)]


def chunk(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    text = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind(". ", start + size // 2, end)
            end = cut + 1 if cut > 0 else end
        piece = text[start:end].strip()
        if len(piece) > 80:
            out.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def stem(t: str) -> str:
    """Very light English stemmer so 'symptoms'/'symptom' and 'breeding'/'breed' match. Non-Latin tokens unchanged."""
    if not t.isascii() or len(t) <= 4 or t.isdigit():
        return t
    if t.endswith(("ous", "us", "ss", "is")):          # dangerous, virus, mass, analysis: not plurals
        return t
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            base = t[: len(t) - len(suf)] + rep
            if suf in ("ing", "ed") and len(base) > 3 and base[-1] == base[-2] and base[-1] not in "lsz":
                base = base[:-1]                       # getting -> get, running -> run
            return base
    return t


BOILERPLATE = re.compile(r"all rights reserved|without warranty of any kind|permission to reproduce|legal status of any|"
                         r"library cataloguing|isbn|printed in|acknowledg|designations employed|cip data|dotted lines on maps|"
                         r"endorsed or recommended|specific companies|the mention of", re.I)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def is_noise(chunk_text: str) -> bool:
    """Front matter (copyright, disclaimers) and bibliography lists are not guidance and must not be cited."""
    return bool(BOILERPLATE.search(chunk_text)) or len(YEAR.findall(chunk_text)) >= 4


def tokenize(s: str) -> list[str]:
    return [stem(t) for t in TOKEN.findall(s.lower()) if t not in STOP and len(t) > 1]


def build_index() -> dict:
    meta = {s["id"]: s for s in sources()}
    chunks = []
    for path in sorted(guidelines_dir().glob("*")):
        if path.suffix not in (".pdf", ".html", ".htm", ".txt", ".md"):
            continue
        src = meta.get(path.stem, {"id": path.stem, "title": path.stem, "org": "local file", "url": None})
        for page, text in _pages(path):
            for c in chunk(text):
                if is_noise(c):
                    continue
                chunks.append({"id": len(chunks), "source_id": src["id"], "title": src["title"], "org": src["org"],
                               "url": src.get("url"), "page": page, "text": c})
    docs = [tokenize(c["title"] + " " + c["text"]) for c in chunks]   # title is searchable, so lay pages rank on topic
    df = Counter(t for d in docs for t in set(d))
    idx = {"chunks": chunks, "doc_len": [len(d) for d in docs], "tf": [dict(Counter(d)) for d in docs],
           "idf": {t: math.log(1 + (len(docs) - n + 0.5) / (n + 0.5)) for t, n in df.items()},
           "avgdl": (sum(len(d) for d in docs) / len(docs)) if docs else 0}
    (guidelines_dir() / "index.json").write_text(json.dumps(idx))
    return {"chunks": len(chunks), "sources": len({c["source_id"] for c in chunks})}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "fetch":
        fetch_all()
    print(build_index())
