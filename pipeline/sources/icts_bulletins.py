"""Downloader for Karnataka NVBDCP daily dengue bulletins archived by ICTS Bengaluru.

URL pattern (observed): {base}/{YYYY}/{MonthName}/{DD-MM-YYYY}.pdf
Not every date exists (holidays, gaps), so missing files are expected and recorded in the
manifest rather than treated as errors.

Be polite: one request at a time, a delay between requests, and never re-download a file we
already have. Run this on your own machine (it needs normal internet access).
"""
from __future__ import annotations

import csv
import hashlib
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from pipeline.config import get_paths, load_city

USER_AGENT = "NeighborHealth-research/2.0 (student public-health project; polite crawler)"
MANIFEST_FIELDS = ["date", "url", "status", "http_code", "bytes", "sha256", "path"]


def bulletin_url(d: date, base_url: str) -> str:
    return f"{base_url}/{d.year}/{d.strftime('%B')}/{d.strftime('%d-%m-%Y')}.pdf"


def local_path(d: date, raw_dir: Path) -> Path:
    return raw_dir / str(d.year) / f"{d.isoformat()}.pdf"


def _load_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["date"]: row for row in csv.DictReader(f)}


def _write_manifest(path: Path, rows: dict[str, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])
    tmp.replace(path)


def _ssl_context():
    """macOS python.org builds often lack root certificates; use certifi's bundle when available."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_SSL = None


def _fetch(url: str, timeout: float = 30.0) -> tuple[int, bytes]:
    global _SSL
    _SSL = _SSL or _ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def check_connection(base_url: str) -> None:
    """Fail fast with a readable message instead of silently recording thousands of errors."""
    probe = f"{base_url}/2024/July/08-07-2024.pdf"
    try:
        code, body = _fetch(probe, timeout=20)
    except Exception as e:
        hint = ""
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            hint = ("\nFix: pip install certifi   (or run 'Install Certificates.command' "
                    "from your Python folder in /Applications)")
        raise SystemExit(f"Cannot reach {probe}: {e}{hint}")
    if code != 200 or not body.startswith(b"%PDF"):
        raise SystemExit(f"Archive reachable but probe returned HTTP {code}. Check the URL pattern in config.")
    print(f"Connection OK ({len(body):,} bytes from probe file)")


def download_range(start: date, end: date, delay_s: float = 1.0, retry_missing: bool = False,
                   max_retries: int = 3) -> dict[str, int]:
    """Download every available bulletin between start and end (inclusive)."""
    cfg = load_city()
    paths = get_paths()
    base_url = cfg["surveillance"]["base_url"]
    manifest = _load_manifest(paths.manifest)
    stats = {"downloaded": 0, "skipped": 0, "missing": 0, "errors": 0}
    check_connection(base_url)
    total_days = (end - start).days + 1

    d = start
    while d <= end:
        key = d.isoformat()
        prev = manifest.get(key)
        out = local_path(d, paths.raw_bulletins)
        if prev and prev["status"] == "ok" and out.exists():
            stats["skipped"] += 1
        elif prev and prev["status"] == "missing" and not retry_missing:
            stats["skipped"] += 1
        else:
            url = bulletin_url(d, base_url)
            code, body, err = 0, b"", ""
            for attempt in range(max_retries):
                try:
                    code, body = _fetch(url)
                    break
                except Exception as e:  # network hiccup: back off and retry
                    err = f"{e.__class__.__name__}: {e}"
                    time.sleep(delay_s * (2 ** attempt))
            if err and code == 0:
                print(f"  {key}: {err}")
            row = {"date": key, "url": url, "http_code": code, "bytes": "", "sha256": "", "path": ""}
            if code == 200 and body.startswith(b"%PDF"):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(body)
                row.update(status="ok", bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                           path=str(out.relative_to(paths.root)))
                stats["downloaded"] += 1
            elif code in (404, 403):
                row["status"] = "missing"
                stats["missing"] += 1
            else:
                row["status"] = "error"
                stats["errors"] += 1
            manifest[key] = row
            _write_manifest(paths.manifest, manifest)
            done = (d - start).days + 1
            if done % 30 == 0:
                print(f"  {done}/{total_days} days checked: {stats}")
            time.sleep(delay_s)
        d += timedelta(days=1)

    return stats


def available_bulletins() -> list[tuple[date, Path]]:
    paths = get_paths()
    manifest = _load_manifest(paths.manifest)
    out = []
    for key, row in sorted(manifest.items()):
        if row["status"] == "ok":
            p = paths.root / row["path"]
            if p.exists():
                out.append((date.fromisoformat(key), p))
    # Also pick up PDFs placed manually (e.g. downloaded by hand) that are not in the manifest.
    seen = {p for _, p in out}
    for p in sorted(paths.raw_bulletins.glob("*/*.pdf")):
        if p not in seen:
            try:
                out.append((date.fromisoformat(p.stem), p))
            except ValueError:
                pass
    return sorted(out)
