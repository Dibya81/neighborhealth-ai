"""OCR extractor for the scanned bulletins (no text layer; from ~Oct 2023 most files are HP scans).

Reading a whole noisy scan with OCR drops and garbles digits, so we do the minimum that matters:
  1. render page 1, deskew it (projection-profile search, +-4 degrees),
  2. OCR the page once to find the y position of the "Total" and "Bangaluru City (BBMP)" rows,
  3. crop each of those two rows, remove the table's ruled lines (they get read as '1', 'l', '|'),
     and OCR the crop at several scales,
  4. accept a reading only if it passes arithmetic checks: IgM + NS1 == Total and
     Total <= Samples <= Suspected. Every variant votes; the most common valid reading wins.

macOS only (uses the Vision framework through pyobjc). Rows we cannot validate are left out and
the bulletin is flagged, so the reconciler / series builder treat it as missing, never as a guess.
"""
from __future__ import annotations

import io
import itertools
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps

from pipeline.extract.schema import AreaRow, Bulletin, Counts

RENDER_SCALE = 3
VARIANTS = [(2, True), (3, True), (3, False), (4, True), (2, False)]  # (upscale, strip ruled lines)


class OcrUnavailable(RuntimeError):
    pass


def _vision():
    try:
        import Vision
        from Foundation import NSData
    except ImportError as e:  # pragma: no cover
        raise OcrUnavailable("OCR needs macOS + `pip install pyobjc-framework-Vision`") from e
    return Vision, NSData


def _ocr_tokens(img: Image.Image) -> list[tuple[str, float, float]]:
    """(text, right edge x, top y) for every whitespace-separated token in the image."""
    Vision, NSData = _vision()
    buf = io.BytesIO()
    img.save(buf, "PNG")
    data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None).performRequests_error_([req], None)
    w, h = img.size
    out = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)[0]
        s, pos = cand.string(), 0
        for tok in s.split():
            i = s.index(tok, pos)
            pos = i + len(tok)
            box, _ = cand.boundingBoxForRange_error_((i, len(tok)), None)
            bb = box.boundingBox()
            out.append((tok, (bb.origin.x + bb.size.width) * w, (1 - bb.origin.y - bb.size.height) * h))
    return sorted(out, key=lambda t: t[1])


def deskew(img: Image.Image) -> Image.Image:
    small = img.convert("L").resize((img.width // 3, img.height // 3))
    dark = Image.fromarray(((np.asarray(small) < 140) * 255).astype("uint8"))
    best_angle, best_var = 0.0, -1.0
    for a in np.arange(-4.0, 4.01, 0.1):
        var = np.asarray(dark.rotate(float(a), resample=Image.BILINEAR), dtype=float).sum(axis=1).var()
        if var > best_var:
            best_angle, best_var = float(a), var
    return img.rotate(best_angle, resample=Image.BICUBIC, fillcolor=(255, 255, 255))


def strip_ruled_lines(band: Image.Image) -> Image.Image:
    g = np.asarray(band.convert("L")).copy()
    dark = g < 150
    for c in np.where(dark.mean(axis=0) > 0.55)[0]:
        g[:, max(0, c - 2):c + 3] = 255
    for r in np.where(dark.mean(axis=1) > 0.5)[0]:
        g[max(0, r - 2):r + 3, :] = 255
    return Image.fromarray(g).convert("RGB")


# ---------------------------------------------------------------- reading numbers from a row
def _candidates(tok: str) -> list[int]:
    """Possible values of a token. A trailing '1'/'l'/'|' is often a table border read as a digit."""
    plain = re.sub(r"[^0-9]", "", tok)
    if not plain:
        return []
    out = []
    stripped = re.sub(r"[^0-9]", "", re.sub(r"[lI|/]+$", "", tok))
    if stripped:
        out.append(int(stripped))
    if len(plain) > 1 and plain.endswith("1"):
        out.append(int(plain[:-1]))              # '31' might really be '3' + border
    out.append(int(plain))
    return list(dict.fromkeys(out))


def _valid_group(g: tuple[int, ...]) -> bool:
    susp, samples, igm, ns1, total = g
    return igm + ns1 == total and total <= samples <= susp and total > 0


def find_groups(tokens: list[tuple[str, float, float]]) -> list[tuple]:
    """Every (suspected, samples, igm, ns1, total, x) window that passes the arithmetic checks.
    x is the right edge of the 'suspected' token, so callers can tell which block it belongs to."""
    cands = [_candidates(t[0]) for t in tokens]
    found = []
    for i in range(len(cands) - 4):
        window = cands[i:i + 5]
        if any(not c for c in window):
            continue
        for combo in itertools.product(*window):
            if _valid_group(combo):
                found.append((*combo, tokens[i][1]))
    return found


def _main_line(tokens: list[tuple[str, float, float]], half_height: float) -> list[tuple[str, float, float]]:
    """Keep only the tokens on the row we want. The crop can include slivers of the neighbouring
    row, and sorting by x would interleave their numbers with ours. Anchor on the row label
    ('Total' / '(BBMP)'); if it was not read, fall back to the densest line."""
    if not tokens:
        return tokens
    labels = [t for t in tokens if re.search(r"total|bbmp", t[0], re.IGNORECASE)]
    if labels:
        ref = labels[0][2]
        keep = [t for t in tokens if abs(t[2] - ref) <= half_height]
    else:
        keep = max(([t2 for t2 in tokens if abs(t2[2] - t[2]) <= half_height] for t in tokens), key=len)
    return sorted(keep, key=lambda t: t[1])


def read_groups(band: Image.Image) -> Counter:
    """Valid count groups found across OCR variants, voted. Key: (suspected..total, x in band pixels)."""
    votes: Counter = Counter()
    for scale, strip in VARIANTS:
        b = strip_ruled_lines(band) if strip else band
        b = ImageOps.expand(b.resize((band.width * scale, band.height * scale), Image.LANCZOS),
                            border=30, fill=(255, 255, 255))
        seen = set()
        for g in find_groups(_main_line(_ocr_tokens(b), 7 * scale)):
            key = (*g[:5], int(round((g[5] - 30) / scale / 10)) * 10)   # bucket x so variants agree
            if key not in seen:
                seen.add(key)
                votes[key] += 1
    return votes


def _counts(g: tuple) -> Counts:
    return Counts.from_list(list(g[:5]) + [None])       # deaths are not read from scans (borders corrupt them)


# ---------------------------------------------------------------- page level
def _find_row_y(tokens: list[tuple[str, float, float]], width: float) -> tuple[Optional[float], Optional[float]]:
    """y of the BBMP and Total rows. The label is '(BBMP)' in the left-hand label column; the
    footnote under the table also says 'BBMP (4)', so position and parentheses both matter."""
    left = [t for t in tokens if "BBMP" in t[0].upper() and t[1] < 0.4 * width]
    labelled = [t for t in left if "(" in t[0] or ")" in t[0]]
    pool = labelled or left
    if not pool:
        return None, None
    bbmp_y = max(t[2] for t in pool)
    totals = [t for t in tokens if t[0].lower().startswith("total") and 0 < bbmp_y - t[2] < 250 and t[1] < 0.4 * width]
    return bbmp_y, max((t[2] for t in totals), default=None)


def title_year(tokens: list[tuple[str, float, float]]) -> Optional[int]:
    """Year in the title 'Daily Report of Dengue in Karnataka State - 2023' (same text line as 'Karnataka')."""
    for _, _, y in (t for t in tokens if t[0].lower().startswith("karnataka")):
        for tok, _, ty in tokens:
            if abs(ty - y) <= 20 and re.fullmatch(r"-?(20\d\d)", tok):
                return int(tok.lstrip("-"))
    return None


def orient(base: Image.Image) -> tuple[Image.Image, Optional[float], Optional[float], list]:
    """Scans are often fed sideways. Try the likely rotations and keep the first where both the
    'Total' and 'BBMP' rows are found."""
    angles = (0, 180, -90, 90) if base.width >= base.height else (-90, 90, 0, 180)
    img = base
    for a in angles:
        img = deskew(base.rotate(a, expand=True, fillcolor=(255, 255, 255)) if a else base)
        tokens = _ocr_tokens(img)
        bbmp_y, total_y = _find_row_y(tokens, img.width)
        if bbmp_y is not None and total_y is not None:
            return img, bbmp_y, total_y, tokens
    return img, None, None, []


def extract_scan(pdf_path: Path, report_date: date) -> Bulletin:
    page = pdfium.PdfDocument(str(pdf_path))[0]
    img, bbmp_y, total_y, tokens = orient(page.render(scale=RENDER_SCALE).to_pil())
    year = title_year(tokens)
    warnings: list[str] = ["scanned bulletin: OCR (rows BBMP and STATE_TOTAL only)"]
    if year is None:
        warnings.append("year in title not read")
    if bbmp_y is None:
        warnings.append("BBMP row not located")
    votes: dict[str, Counter] = {}
    for area, y in (("STATE_TOTAL", total_y), ("BBMP", bbmp_y)):
        if y is not None:
            band = img.crop((int(img.width * 0.08), int(y) - 24, img.width, int(y) + 52))
            votes[area] = read_groups(band)

    # Where does the cumulative block sit on this page? Any row showing both blocks tells us:
    # cluster the x positions of its valid groups; the right-most cluster is the cumulative block.
    cum_x = None
    for area in ("STATE_TOTAL", "BBMP"):
        xs = sorted(k[5] for k in votes.get(area, {}))
        clusters: list[list[int]] = []
        for x in xs:
            if clusters and x - clusters[-1][-1] <= 60:
                clusters[-1].append(x)
            else:
                clusters.append([x])
        if len(clusters) >= 2 and clusters[-1][0] - clusters[-2][-1] > 150:
            cum_x = float(np.median(clusters[-1]))
            break
    if cum_x is None:
        # Never guess: a lone block could be the on-the-day numbers. Better a missing day than a wrong one.
        warnings.append("could not locate the cumulative block by position; no values accepted")
        return Bulletin(report_date=report_date, year_in_pdf=year, extractor="ocr", rows=[],
                        warnings=warnings, source_file=str(pdf_path))

    rows: list[AreaRow] = []
    for area in ("STATE_TOTAL", "BBMP"):
        v = votes.get(area)
        if not v:
            warnings.append(f"{area}: no OCR reading passed the arithmetic checks")
            continue
        cum_c = [(k, n) for k, n in v.items() if abs(k[5] - cum_x) <= 40]
        day_c = [(k, n) for k, n in v.items() if k[5] < cum_x - 150]
        if not cum_c:
            warnings.append(f"{area}: only the on-the-day block was readable; cumulative missing")
            continue
        cum, n = max(cum_c, key=lambda kn: kn[1])
        if n < 2:
            warnings.append(f"{area}: only {n} OCR variant(s) agree")
        day = max(day_c, key=lambda kn: kn[1])[0] if day_c else None
        rows.append(AreaRow(area=area, raw_label=area, on_day=_counts(day) if day else Counts(),
                            cumulative=_counts(cum)))
    return Bulletin(report_date=report_date, year_in_pdf=year, extractor="ocr", rows=rows,
                    warnings=warnings, source_file=str(pdf_path))


# ---------------------------------------------------------------- whole-document OCR
def _ocr_lines(img: Image.Image) -> list[str]:
    """Recognised text lines in reading order (top to bottom, then left to right)."""
    Vision, NSData = _vision()
    buf = io.BytesIO()
    img.save(buf, "PNG")
    data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)
    Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None).performRequests_error_([req], None)
    items = []
    for obs in req.results() or []:
        bb = obs.boundingBox()
        items.append((1 - bb.origin.y - bb.size.height, bb.origin.x, obs.topCandidates_(1)[0].string()))
    items.sort(key=lambda t: (round(t[0], 2), t[1]))
    return [t[2] for t in items]


def ocr_pdf_pages(pdf_path: Path, scale: float = 2.0) -> list[str]:
    """Plain text of every page of a PDF that has no text layer (e.g. text converted to outlines)."""
    doc = pdfium.PdfDocument(str(pdf_path))
    return ["\n".join(_ocr_lines(doc[i].render(scale=scale).to_pil())) for i in range(len(doc))]
