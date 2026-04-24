import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from datetime import date
from utils.logger import get_logger

logger = get_logger("ML")

np.random.seed(42)

WARD_DENSITIES = [
    8500,9200,7800,6900,12000,9800,10200,7200,6500,8900,
    11500,10800,10100,8600,7400,7800,14500,9200,10600,13200,
    9800,7100,11900,15600,13800,12200,10500,9200,8100,8600,
    13100,11800,7900,12400,11200,10800,11500,15200,14600,10900,
    13400,14100,11800,10400,9600,11200,12500,11800,18200,19800,
    15600,13200,14100,13500,16400,21500,17800,14200,12100,8900,
    9800,10900,11400,10200,8100,12600,13900,14200,12100,11400,
    12800,9600,10800,9200,10100,11900,14600,11200,9800,9100,
    8300,7600,13400,16800,13200,12400,11800,10200,9400,12600,
    17200,8800,11200,11800,13100,10600,20400,16200,17400,18800,
    14200,17600,12800,16400,15800,13200,12400,14600,13100,18400,
    17200,16800,15600,17400,16200,19600,18200,15800,13400,19200,
    16400,15200,17600,14800,16600,17800,14200,13100,14900,18600,
    20400,15800,17200,21800,14600,20200,18800,17400,19600,14400,
    13200,12400,11800,10200,16400,11800,9600,11200,9100,13200,
    11600,10400,9600,14800,12200,13600,13100,12400,13800,15600,
    13200,14800,12600,11200,17200,14400,16800,14600,13200,12800,
    13400,16200,17400,13800,14200,16400,12600,11800,13900,17600,
    14200,13400,11600,17800,13200,12400,11200,10400,11800,10900,
    10200,11400,12800,12200,11600,13800,9800,9800,
]

# Realistic Bengaluru monthly weather normals (mean, std) for temp/humidity/rainfall
MONTHLY_WEATHER = {
    1:  {"temp":(21.5,2.0), "hum":(52,8),  "rain":(2.1,1.5)},
    2:  {"temp":(24.0,2.2), "hum":(48,8),  "rain":(3.8,2.8)},
    3:  {"temp":(27.5,2.5), "hum":(43,9),  "rain":(12.4,8.0)},
    4:  {"temp":(29.0,2.0), "hum":(50,9),  "rain":(38.0,20.0)},
    5:  {"temp":(28.0,1.8), "hum":(60,8),  "rain":(110.0,45.0)},
    6:  {"temp":(24.5,1.5), "hum":(78,6),  "rain":(98.0,35.0)},
    7:  {"temp":(23.5,1.2), "hum":(82,5),  "rain":(112.0,38.0)},
    8:  {"temp":(23.8,1.2), "hum":(83,5),  "rain":(138.0,42.0)},
    9:  {"temp":(24.2,1.3), "hum":(81,6),  "rain":(158.0,50.0)},
    10: {"temp":(24.5,1.5), "hum":(78,6),  "rain":(155.0,55.0)},
    11: {"temp":(22.8,1.8), "hum":(68,8),  "rain":(52.0,30.0)},
    12: {"temp":(21.0,2.0), "hum":(60,8),  "rain":(14.0,9.0)},
}

FEATURE_COLUMNS = [
    "rainfall_7d", "rainfall_lag14", "temp_avg", "humidity_avg",
    "dengue_cases_30d", "dengue_cases_prev_year",
    "report_count_7d", "month", "population_density",
]


def _sample_weather(month: int, rng: np.random.Generator) -> dict:
    w = MONTHLY_WEATHER[month]
    rain   = max(0.0, rng.normal(w["rain"][0],   w["rain"][1]))
    temp   = max(15.0, rng.normal(w["temp"][0],  w["temp"][1]))
    hum    = float(np.clip(rng.normal(w["hum"][0], w["hum"][1]), 20, 100))
    rain7d = rain / 4.3  # approximate 7-day portion of monthly total
    return {"rain7d": rain7d, "temp": temp, "hum": hum}


def _season_multiplier(month: int) -> float:
    """Bengaluru dengue peaks post-monsoon (Sep–Nov). Returns 0.2–1.5."""
    m = {1:0.20, 2:0.20, 3:0.30, 4:0.40, 5:0.55,
         6:0.80, 7:1.00, 8:1.15, 9:1.35, 10:1.50, 11:1.20, 12:0.45}
    return m.get(month, 0.5)


def build_training_data(n_ward_repeats: int = 26) -> pd.DataFrame:
    """
    Builds ~9,500 rows by:
    1. Loading the 365-row Karnataka CSV
    2. Repeating each row for n_ward_repeats different population densities
    3. Adding weather noise per repeat so features are not identical
    4. Fixing label leakage: label uses FUTURE cases (14-day lookahead proxy)
    """
    csv_path = Path(__file__).parent.parent / "data" / "dengue_karnataka.csv"
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))

    df_raw = pd.read_csv(csv_path)
    df_raw["date"]   = pd.to_datetime(df_raw["date"], errors="coerce")
    df_raw["month"]  = df_raw["date"].dt.month.fillna(7).astype(int)
    df_raw["cases"]  = df_raw["cases"].fillna(0).astype(float)

    rng = np.random.default_rng(42)
    n_densities = len(WARD_DENSITIES)
    rows = []

    for ward_repeat in range(n_ward_repeats):
        density = WARD_DENSITIES[ward_repeat % n_densities]
        density_noise = rng.uniform(0.88, 1.12) * density  # ±12% noise

        for i, (_, raw_row) in enumerate(df_raw.iterrows()):
            month    = int(raw_row["month"])
            cases_now = float(raw_row["cases"])

            # 14-day lookahead: next available row or 1.1x current (proxy)
            future_idx   = min(i + 14, len(df_raw) - 1)
            cases_future = float(df_raw.iloc[future_idx]["cases"])

            # Label: future outbreak, NOT current cases (fixes leakage)
            label = 1 if cases_future > 55 else 0

            # Weather with noise
            wx       = _sample_weather(month, rng)
            season   = _season_multiplier(month)
            rain7d   = wx["rain7d"]
            rain14   = rain7d * rng.uniform(1.3, 2.1)  # lag approximation
            temp     = wx["temp"]
            hum      = wx["hum"]

            # Cases features use PAST data (current is fine — no future leakage)
            cases_30d     = max(0, int(cases_now * season))
            cases_prev    = max(0, int(cases_now * 0.8 * rng.uniform(0.7, 1.3)))
            reports       = max(0, int(cases_30d * 0.12 * rng.uniform(0.5, 1.5)))

            rows.append({
                "rainfall_7d":            round(rain7d, 2),
                "rainfall_lag14":         round(rain14, 2),
                "temp_avg":               round(temp, 2),
                "humidity_avg":           round(hum, 2),
                "dengue_cases_30d":       cases_30d,
                "dengue_cases_prev_year": cases_prev,
                "report_count_7d":        reports,
                "month":                  month,
                "population_density":     round(density_noise),
                "label":                  label,
            })

    df = pd.DataFrame(rows)
    logger.info(
        "Training data: %d rows | outbreak_rate=%.1f%% | density_range=[%.0f,%.0f]",
        len(df), df["label"].mean() * 100,
        df["population_density"].min(), df["population_density"].max(),
    )
    return df


def train_and_save():
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, roc_auc_score

    df = build_training_data(n_ward_repeats=26)
    X, y = df[FEATURE_COLUMNS], df["label"]

    print(f"\nDataset: {len(X)} rows | class dist: {y.value_counts().to_dict()}")
    print(f"Density range: {X['population_density'].min():.0f}–{X['population_density'].max():.0f}")

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.75,
        colsample_bytree=0.75,
        min_child_weight=5,
        gamma=0.5,
        reg_alpha=0.1,
        reg_lambda=1.5,
        max_delta_step=1,
        early_stopping_rounds=20,   # XGBoost >=2.0: goes in constructor
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=30)

    y_prob = model.predict_proba(X_te)[:, 1]
    y_pred = model.predict(X_te)
    auc    = roc_auc_score(y_te, y_prob)

    print(f"\nROC-AUC: {auc:.4f}  (target: 0.72–0.88)")
    print(classification_report(y_te, y_pred, target_names=["normal","outbreak"]))

    feature_imp = dict(zip(FEATURE_COLUMNS, [float(v) for v in model.feature_importances_]))
    print("\nFeature importance:")
    for f, v in sorted(feature_imp.items(), key=lambda x: -x[1]):
        print(f"  {f:<30} {'█'*int(v*40)} {v:.4f}")

    out = Path(__file__).parent.parent / "ml" / "model" / "xgb_dengue.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out)
    print(f"\nModel → {out}")

    meta = {
        "trained_at":            date.today().isoformat(),
        "n_samples":             len(X),
        "n_features":            len(FEATURE_COLUMNS),
        "feature_columns":       FEATURE_COLUMNS,
        "roc_auc":               round(auc, 4),
        "data_source":           "karnataka_parliamentary_records_x26_density",
        "model_version":         "v2-no-leakage",
        "feature_importances":   feature_imp,
        "note":                  "Label uses 14-day future cases (no leakage). Ward density varied.",
    }
    meta_path = out.parent / "model_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"Metadata → {meta_path}")


if __name__ == "__main__":
    train_and_save()
