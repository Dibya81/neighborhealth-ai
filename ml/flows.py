"""The weekly retrain -> backtest -> promote -> publish pipeline (the MLOps loop).

Run it from cron, a GitHub Actions schedule, or by hand:
    python -m ml weekly            # refresh data, backtest, maybe promote, publish forecast
    python -m ml weekly --no-download
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from ml import HORIZONS
from ml.backtest import choose_champion, rolling_backtest
from ml.data import load_table
from ml.metrics import score_predictions
from ml.models import SARIMAFourier, make_model
from ml.publish import publish
from ml.registry import champion_metadata, decide_promotion, models_dir, register_candidate
from pipeline.config import get_paths

ALL_MODELS = ["persistence", "seasonal_naive", "glm_poisson", "gbm", "sarima", "ensemble"]


def model_list() -> list[str]:
    return [m for m in ALL_MODELS if m != "sarima" or SARIMAFourier.available()]


def refresh_data(days_back: int = 21) -> None:
    from pipeline.cli import main as pipeline_main
    start = (date.today() - timedelta(days=days_back)).isoformat()
    pipeline_main(["download", "--start", start])
    pipeline_main(["extract"])
    pipeline_main(["build"])


def run_backtest(min_train: int = 78, refit_every: int = 1, progress: bool = True):
    df = load_table()
    # Score only weeks backed by real bulletin observations, never the interpolated ones.
    preds = rolling_backtest(df, model_list(), min_train=min_train, refit_every=refit_every, progress=progress,
                             scored_weeks=(df["quality"] == "ok"))
    scores = score_predictions(preds)
    out = get_paths().processed
    preds.to_csv(out / "backtest_predictions.csv", index=False)
    scores.to_csv(out / "backtest_scores.csv", index=False)
    return df, preds, scores


def run_weekly(download: bool = True, min_train: int = 78, refit_every: int = 1) -> dict:
    if download:
        refresh_data()
    df, preds, scores = run_backtest(min_train, refit_every)
    best = choose_champion(scores)
    last = int(df["cases"].notna().to_numpy().nonzero()[0].max())
    fitted = {h: make_model(best).fit(df, h, last) for h in HORIZONS}
    data_info = {"first_week": str(df.index.min().date()), "last_week": str(df.index[last].date()),
                 "n_weeks": int(df["cases"].notna().sum())}
    version = register_candidate(best, scores, preds, fitted, data_info)
    decision = decide_promotion(version, scores)

    champ = champion_metadata()
    result = {"candidate": version, "decision": decision}
    if champ:
        champ_backtest = pd.read_csv(models_dir() / champ["version"] / "backtest.csv",
                                     parse_dates=["origin", "target_week"])
        # Intervals come from the current run's residuals for the champion type (most recent data).
        bt = preds if champ["model_type"] in set(preds["model"]) else champ_backtest
        bundle = publish(champ["model_type"], bt, scores, champ["version"], df)
        result["published"] = {"origin_week": bundle["origin_week"], "model": champ["model_type"],
                               "forecast": bundle["forecast"], "drift": bundle["drift"]["overall"]}
    else:
        result["published"] = None
        result["warning"] = "No model has passed the quality gate yet; nothing published."
    (get_paths().processed / "weekly_run.json").write_text(json.dumps(result, indent=2, default=str))
    return result
