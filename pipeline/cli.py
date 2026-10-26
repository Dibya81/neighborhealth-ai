"""Command line for the Step 1 data pipeline.

    python -m pipeline download --start 2022-01-01 --end 2025-12-31
    python -m pipeline extract            # rule-based (free, fast)
    python -m pipeline extract --llm      # also run the LLM extractor (needs OPENROUTER_API_KEY)
    python -m pipeline label --n 40       # hand-label a stratified sample (ground truth)
    python -m pipeline build              # reconcile -> weekly BBMP series -> weekly weather
    python -m pipeline eval               # accuracy report -> docs/v2/extraction_eval.md
    python -m pipeline status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from pipeline.config import get_paths, load_city


def cmd_download(args) -> None:
    from pipeline.sources.icts_bulletins import download_range
    stats = download_range(date.fromisoformat(args.start), date.fromisoformat(args.end),
                           delay_s=args.delay, retry_missing=args.retry_missing)
    print(json.dumps(stats, indent=2))


def cmd_extract(args) -> None:
    from pipeline.extract.text_parser import parse_bulletin
    from pipeline.sources.icts_bulletins import available_bulletins
    paths = get_paths()
    items = available_bulletins()
    if args.since:
        items = [(d, p) for d, p in items if d >= date.fromisoformat(args.since)]
    if args.limit:
        items = items[: args.limit]
    extractors = [("rule", parse_bulletin)]
    if args.llm:
        from pipeline.extract.llm_extractor import extract_llm
        extractors.append(("llm", extract_llm))
    for name, fn in extractors:
        out = paths.interim / f"extracted_{name}.jsonl"
        # Incremental: keep earlier results and only extract what is new (--force redoes everything).
        # Scanned bulletins need macOS OCR, so on another machine (CI) a failed re-extraction must not
        # erase the result we already have.
        known: dict[str, str] = {}
        if out.exists():
            for line in out.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    known[json.loads(line)["report_date"]] = line
        n_ok = n_cached = n_fail = 0
        for i, (d, p) in enumerate(items, 1):
            if d.isoformat() in known and not args.force:
                n_cached += 1
                continue
            try:
                known[d.isoformat()] = fn(p, d).model_dump_json()
                n_ok += 1
            except Exception as e:  # keep going; one broken PDF must not stop the run
                n_fail += 1
                print(f"  [{name}] {d}: {e.__class__.__name__}: {e}", file=sys.stderr)
            if i % 50 == 0:
                print(f"  [{name}] {i}/{len(items)}")
        out.write_text("".join(known[k] + "\n" for k in sorted(known)), encoding="utf-8")
        print(f"{name}: {n_ok} extracted, {n_cached} already done, {n_fail} failed -> {out}")


def cmd_build(args) -> None:
    from pipeline.build.reconcile import reconcile
    from pipeline.build.series import build_weekly
    from pipeline.build.weather import build_weekly_weather
    from pipeline.eval.evaluate import load_extractions
    paths = get_paths()
    cfg = load_city()
    exts = {name: load_extractions(name) for name in ("rule", "llm")}
    dates = set().union(*[set(v) for v in exts.values()])
    if not dates:
        raise SystemExit("Nothing extracted yet. Run: python -m pipeline extract")
    merged = {iso: {n: e[iso] for n, e in exts.items() if iso in e} for iso in dates}
    rows = reconcile(merged, cfg["surveillance"]["keep_areas"], prefer=args.prefer)
    rows.to_csv(paths.processed / "bulletin_rows.csv", index=False)
    print(f"bulletin_rows.csv: {len(rows)} rows, trusted {int(rows['trusted'].sum())}")

    target = cfg["surveillance"]["target_area"]
    weekly, report = build_weekly(rows, target)
    if not weekly.empty:
        weekly.to_csv(paths.processed / f"{target.lower()}_weekly_cases.csv", index=False)
    tests, tests_report = build_weekly(rows, target, value_col="cum_samples")
    if not tests.empty:
        tests.rename(columns={"cases": "tests"}).to_csv(paths.processed / f"{target.lower()}_weekly_tests.csv", index=False)
    report["tests_series"] = {k: v for k, v in tests_report.items() if k in ("n_weeks", "weeks_ok", "error")}
    try:
        wx = build_weekly_weather()
        wx.to_csv(paths.processed / "weather_weekly.csv", index=False)
        report["weather_weeks"] = int(len(wx))
        report["weather_end"] = str(wx["week_end"].max().date())
    except FileNotFoundError as e:
        report["weather_error"] = str(e)
    (paths.processed / "build_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


def cmd_label(args) -> None:
    from pipeline.eval.gold import label_interactive
    label_interactive(n=args.n, labeller=args.labeller)


def cmd_eval(args) -> None:
    from pipeline.eval.evaluate import evaluate
    res = evaluate()
    for ext, r in res["extractors"].items():
        print(f"{ext:>10}: overall accuracy {r['overall_accuracy']}")
    print("Report written to docs/v2/extraction_eval.md")


def cmd_status(args) -> None:
    from pipeline.eval.gold import load_gold
    from pipeline.sources.icts_bulletins import available_bulletins
    items = available_bulletins()
    by_year: dict[int, int] = {}
    for d, _ in items:
        by_year[d.year] = by_year.get(d.year, 0) + 1
    paths = get_paths()
    print(f"PDFs downloaded: {len(items)}  by year: {by_year}")
    for name in ("rule", "llm"):
        p = paths.interim / f"extracted_{name}.jsonl"
        print(f"extracted_{name}: {sum(1 for _ in open(p)) if p.exists() else 0}")
    print(f"gold labels: {len(load_gold())}")


def cmd_fetch_weather(args) -> None:
    from pipeline.build.weather import fetch_nasa_power
    print(fetch_nasa_power(date.fromisoformat(args.start), date.fromisoformat(args.end)))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="pipeline", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("download", help="download bulletin PDFs")
    p.add_argument("--start", required=True)
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests (be polite)")
    p.add_argument("--retry-missing", action="store_true")
    p.set_defaults(fn=cmd_download)

    p = sub.add_parser("extract", help="extract tables from downloaded PDFs")
    p.add_argument("--llm", action="store_true", help="also run the LLM extractor")
    p.add_argument("--force", action="store_true", help="re-extract bulletins that already have a result")
    p.add_argument("--since")
    p.add_argument("--limit", type=int)
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser("build", help="reconcile + weekly series + weather")
    p.add_argument("--prefer", choices=["rule", "llm"], default="rule",
                   help="extractor to trust when both pass validation but disagree (set from the eval)")
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser("label", help="hand-label a sample of bulletins")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--labeller", default="me")
    p.set_defaults(fn=cmd_label)

    sub.add_parser("eval", help="accuracy report vs gold labels").set_defaults(fn=cmd_eval)
    sub.add_parser("status", help="what's downloaded / extracted / labelled").set_defaults(fn=cmd_status)

    p = sub.add_parser("fetch-weather", help="download NASA POWER daily data")
    p.add_argument("--start", required=True)
    p.add_argument("--end", default=date.today().isoformat())
    p.set_defaults(fn=cmd_fetch_weather)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
