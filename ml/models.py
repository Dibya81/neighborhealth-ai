"""Forecasting models, from simplest to most complex. All share one interface:

    m.fit(df, h, t_end)       # train using only weeks <= t_end (row positions)
    m.predict(df, h, t)       # point forecast (expected cases) for week t+h made at origin t

Baselines come first on purpose: a model is only interesting if it beats them.
"""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd

from ml.features import build_design


class Forecaster:
    name = "base"

    def fit(self, df: pd.DataFrame, h: int, t_end: int) -> "Forecaster":
        return self

    def predict(self, df: pd.DataFrame, h: int, t: int) -> float:
        raise NotImplementedError


# ------------------------------------------------------------------ baselines
class Persistence(Forecaster):
    """Next weeks = this week."""
    name = "persistence"

    def predict(self, df, h, t):
        return float(df["cases"].iloc[t])


class SeasonalNaive(Forecaster):
    """Week t+h = the same week last year (3-week average to reduce noise). Falls back to persistence."""
    name = "seasonal_naive"

    def predict(self, df, h, t):
        i = t + h - 52
        if i - 1 >= 0:
            vals = df["cases"].iloc[max(0, i - 1): min(i + 2, t + 1)].dropna()
            if len(vals):
                return float(vals.mean())
        return float(df["cases"].iloc[t])


# ------------------------------------------------------------------ statistical model
class SARIMAFourier(Forecaster):
    """Dynamic harmonic regression: ARIMA(2,0,1) on log1p(cases) + 2 Fourier pairs for yearly seasonality.
    (A plain SARIMA with period 52 is slow and unstable on a few years of weekly data.)
    Needs `statsmodels`; fitted once per origin and reused for all horizons."""
    name = "sarima"
    K = 2

    def __init__(self):
        self._cache: dict[int, np.ndarray] = {}

    @staticmethod
    def available() -> bool:
        try:
            import statsmodels  # noqa: F401
            return True
        except ImportError:
            return False

    def _fourier(self, index: pd.DatetimeIndex) -> np.ndarray:
        w = index.isocalendar().week.astype(float).values
        cols = []
        for k in range(1, self.K + 1):
            cols += [np.sin(2 * np.pi * k * w / 52.18), np.cos(2 * np.pi * k * w / 52.18)]
        return np.column_stack(cols)

    def fit(self, df, h, t_end):
        if t_end in self._cache:
            return self
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        y = np.log1p(df["cases"].iloc[: t_end + 1])
        exog = self._fourier(y.index)
        future_idx = pd.date_range(y.index[-1] + pd.Timedelta(weeks=1), periods=4, freq="W-SUN")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                res = SARIMAX(y.values, exog=exog, order=(2, 0, 1), trend="c",
                              enforce_stationarity=False, missing="drop").fit(disp=False, maxiter=200)
                fc = res.forecast(steps=4, exog=self._fourier(future_idx))
            except Exception:
                fc = np.repeat(y.dropna().iloc[-1], 4)
        self._cache[t_end] = np.expm1(np.asarray(fc)).clip(min=0)
        return self

    def predict(self, df, h, t):
        if t not in self._cache:
            self.fit(df, h, t)
        return float(self._cache[t][h - 1])


# ------------------------------------------------------------------ ML models
class _DesignModel(Forecaster):
    """Shared plumbing for models trained on the feature design matrix."""

    def __init__(self):
        self.model = None
        self.columns: list[str] = []
        self.background: pd.DataFrame | None = None

    def _train_rows(self, df, h, t_end):
        X, y = build_design(df, h)
        last_origin = t_end - h  # target week must be <= t_end
        X, y = X.iloc[: last_origin + 1], y.iloc[: last_origin + 1]
        ok = y.notna() & X["log_cases_lag0"].notna()
        return X[ok], y[ok]

    def row(self, df, h, t) -> pd.DataFrame:
        X, _ = build_design(df, h)
        return X.iloc[[t]][self.columns]


class GLMPoisson(_DesignModel):
    """Poisson regression (log link) on standardised features. Interpretable and hard to overfit;
    a strong middle ground between baselines and boosting on a few years of weekly data."""
    name = "glm_poisson"

    def fit(self, df, h, t_end):
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import PoissonRegressor
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        X, y = self._train_rows(df, h, t_end)
        self.columns = list(X.columns)
        self.model = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                                   StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=1000))
        self.model.fit(X, y)
        self.background = X.tail(52)
        return self

    def predict(self, df, h, t):
        return float(self.model.predict(self.row(df, h, t))[0])

    def log_predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.log(np.clip(self.model.predict(X[self.columns]), 1e-9, None))


class GBM(_DesignModel):
    """Gradient boosting with a Poisson objective. Uses LightGBM if installed (native SHAP via
    pred_contrib, native model file), otherwise scikit-learn's HistGradientBoosting (LightGBM-style)."""
    name = "gbm"

    def __init__(self, backend: str | None = None):
        super().__init__()
        self.backend = backend or ("lightgbm" if self.lightgbm_available() else "sklearn")

    @staticmethod
    def lightgbm_available() -> bool:
        try:
            import lightgbm  # noqa: F401
            return True
        except ImportError:
            return False

    def fit(self, df, h, t_end):
        X, y = self._train_rows(df, h, t_end)
        self.columns = list(X.columns)
        if self.backend == "lightgbm":
            import lightgbm as lgb
            self.model = lgb.LGBMRegressor(objective="poisson", n_estimators=300, learning_rate=0.03,
                                           num_leaves=15, min_child_samples=8, subsample=0.8, subsample_freq=1,
                                           colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, random_state=0)
        else:
            from sklearn.ensemble import HistGradientBoostingRegressor
            self.model = HistGradientBoostingRegressor(loss="poisson", max_iter=300, learning_rate=0.03,
                                                       max_leaf_nodes=15, min_samples_leaf=8,
                                                       l2_regularization=1.0, random_state=0)
        self.model.fit(X, y)
        self.background = X.tail(52)
        return self

    def predict(self, df, h, t):
        return float(max(self.model.predict(self.row(df, h, t))[0], 0.0))

    def log_predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.log(np.clip(self.model.predict(X[self.columns]), 1e-9, None))


class Ensemble(Forecaster):
    """Geometric-mean ensemble of the member models. Ensembles usually beat single models in
    epidemic forecasting (a consistent finding of the CDC forecast hubs)."""
    name = "ensemble"

    def __init__(self, members: list[Forecaster]):
        self.members = members

    def fit(self, df, h, t_end):
        for m in self.members:
            m.fit(df, h, t_end)
        return self

    def predict(self, df, h, t):
        preds = [m.predict(df, h, t) for m in self.members]
        return float(math.expm1(np.mean(np.log1p(np.clip(preds, 0, None)))))


def default_models(include_sarima: bool | None = None) -> list[Forecaster]:
    include_sarima = SARIMAFourier.available() if include_sarima is None else include_sarima
    models: list[Forecaster] = [Persistence(), SeasonalNaive(), GLMPoisson(), GBM()]
    if include_sarima:
        models.append(SARIMAFourier())
    return models


def make_model(name: str) -> Forecaster:
    """Fresh, unfitted model by name (ensemble members are fresh too)."""
    if name == "ensemble":
        members: list[Forecaster] = [GLMPoisson(), GBM()]
        if SARIMAFourier.available():
            members.append(SARIMAFourier())
        return Ensemble(members)
    return {"persistence": Persistence, "seasonal_naive": SeasonalNaive, "glm_poisson": GLMPoisson,
            "gbm": GBM, "sarima": SARIMAFourier}[name]()
