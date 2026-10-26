"""Forecasting CLI.

    python -m ml backtest            # rolling backtest of all models -> scores table
    python -m ml weekly              # full MLOps loop: refresh data, backtest, promote, publish
    python -m ml weekly --no-download
    python -m ml gate                # CI quality gate: exit 1 if the champion fails
    python -m ml rollback            # previous champion back in service
    python -m ml model-card          # regenerate docs/v2/MODEL_CARD.md
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd


def _print_scores(scores: pd.DataFrame) -> None:
    cols = [c for c in ["model", "horizon", "mae", "wis", "coverage80", "skill_vs_seasonal_naive"] if c in scores]
    with pd.option_context("display.width", 160, "display.max_rows", 200):
        print(scores[cols].round(3).to_string(index=False))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="ml", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("backtest")
    p.add_argument("--min-train", type=int, default=78)
    p.add_argument("--refit-every", type=int, default=1)
    p = sub.add_parser("weekly")
    p.add_argument("--no-download", action="store_true")
    p.add_argument("--min-train", type=int, default=78)
    p.add_argument("--refit-every", type=int, default=1)
    sub.add_parser("gate")
    sub.add_parser("rollback")
    sub.add_parser("model-card")
    args = ap.parse_args(argv)

    if args.cmd == "backtest":
        from ml.flows import run_backtest
        _, _, scores = run_backtest(args.min_train, args.refit_every)
        _print_scores(scores)
    elif args.cmd == "weekly":
        from ml.flows import run_weekly
        from ml.model_card import write_model_card
        res = run_weekly(download=not args.no_download, min_train=args.min_train, refit_every=args.refit_every)
        print(json.dumps(res, indent=2, default=str))
        write_model_card()
    elif args.cmd == "gate":
        from ml.registry import champion_metadata, quality_gate
        champ = champion_metadata()
        if not champ:
            print("FAIL: no champion model")
            sys.exit(1)
        ok, reasons = quality_gate(champ["summary"])
        print(("PASS" if ok else "FAIL"), champ["version"], json.dumps(champ["summary"]), reasons)
        sys.exit(0 if ok else 1)
    elif args.cmd == "rollback":
        from ml.registry import rollback
        print(rollback() or "nothing to roll back to")
    elif args.cmd == "model-card":
        from ml.model_card import write_model_card
        print(write_model_card())
