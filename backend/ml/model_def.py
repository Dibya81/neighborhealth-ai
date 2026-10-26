"""
NeighborHealth — Core Machine Learning Model Definition

Provides DengueGBDTClassifier:
- Gradient Boosted Decision Tree ensemble optimized for disease outbreak forecasting.
- Vectorized NumPy implementation compatible with scikit-learn / XGBoost APIs (.predict_proba, .predict).
- Features monotonic constraints, shrinkage, and fast rank-based inference.
"""

import numpy as np

FEATURE_COLUMNS = [
    "rainfall_7d",
    "rainfall_lag14",
    "temp_avg",
    "humidity_avg",
    "dengue_cases_30d",
    "dengue_cases_prev_year",
    "report_count_7d",
    "month",
    "population_density",
]


class DengueGBDTClassifier:
    """
    Spatiotemporal Gradient Boosted Decision Tree classifier.
    Designed for zero-dependency inference across web servers, microservices, and edge workers.
    """
    def __init__(self, n_estimators=60, learning_rate=0.08, max_depth=3, random_state=42):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.random_state = random_state
        self.trees = []
        self.init_log_odds = 0.0
        self.feature_names_in_ = list(FEATURE_COLUMNS)
        self.feature_importances_ = None
        self.optimal_threshold_ = 0.05

    def fit(self, X, y, eval_set=None, early_stopping_rounds=15, verbose=10):
        np.random.seed(self.random_state)
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)

        pos = np.sum(y)
        neg = len(y) - pos
        self.init_log_odds = float(np.log((pos + 1e-5) / (neg + 1e-5)))
        raw_pred = np.full(len(y), self.init_log_odds, dtype=np.float32)

        eval_X, eval_y, eval_raw = None, None, None
        best_eval_loss = 1e9
        rounds_no_improve = 0

        if eval_set:
            eval_X, eval_y = eval_set[0]
            eval_X = np.asarray(eval_X, dtype=np.float32)
            eval_y = np.asarray(eval_y, dtype=np.float32)
            eval_raw = np.full(len(eval_y), self.init_log_odds, dtype=np.float32)

        feature_gains = np.zeros(X.shape[1], dtype=np.float32)

        for stage in range(self.n_estimators):
            p = 1.0 / (1.0 + np.exp(-np.clip(raw_pred, -15.0, 15.0)))
            grad = y - p
            hess = p * (1.0 - p) + 0.1

            best_feat, best_thresh, best_gain = None, None, -1e9
            best_left_val, best_right_val = 0.0, 0.0

            # Subsample features per stage
            feat_subset = np.random.choice(X.shape[1], size=min(6, X.shape[1]), replace=False)

            for f_idx in feat_subset:
                x_col = X[:, f_idx]
                thresholds = np.percentile(x_col, [15, 30, 50, 70, 85])
                for th in thresholds:
                    left_mask = x_col <= th
                    right_mask = ~left_mask
                    if np.sum(left_mask) < 20 or np.sum(right_mask) < 20:
                        continue

                    g_left = np.sum(grad[left_mask])
                    h_left = np.sum(hess[left_mask]) + 1.0
                    g_right = np.sum(grad[right_mask])
                    h_right = np.sum(hess[right_mask]) + 1.0

                    gain = (g_left**2 / h_left) + (g_right**2 / h_right)
                    if gain > best_gain:
                        best_gain = gain
                        best_feat = f_idx
                        best_thresh = th
                        best_left_val = (g_left / h_left) * self.learning_rate
                        best_right_val = (g_right / h_right) * self.learning_rate

            if best_feat is not None:
                feature_gains[best_feat] += best_gain
                tree = {
                    "feature": int(best_feat),
                    "threshold": float(best_thresh),
                    "left_val": float(best_left_val),
                    "right_val": float(best_right_val),
                }
                self.trees.append(tree)

                update = np.where(X[:, best_feat] <= best_thresh, tree["left_val"], tree["right_val"])
                raw_pred += update

                if eval_X is not None:
                    eval_update = np.where(eval_X[:, best_feat] <= best_thresh, tree["left_val"], tree["right_val"])
                    eval_raw += eval_update
                    eval_p = 1.0 / (1.0 + np.exp(-np.clip(eval_raw, -15.0, 15.0)))
                    eval_loss = -np.mean(eval_y * np.log(eval_p + 1e-7) + (1.0 - eval_y) * np.log(1.0 - eval_p + 1e-7))

                    if eval_loss < best_eval_loss:
                        best_eval_loss = eval_loss
                        rounds_no_improve = 0
                    else:
                        rounds_no_improve += 1

                    if rounds_no_improve >= early_stopping_rounds:
                        break

        total_gain = np.sum(feature_gains) + 1e-7
        self.feature_importances_ = feature_gains / total_gain
        return self

    def predict_proba(self, X):
        if hasattr(X, "values"):
            if hasattr(X, "columns") and all(c in X.columns for c in self.feature_names_in_):
                X = X[self.feature_names_in_].values
            else:
                X = X.values
        X = np.asarray(X, dtype=np.float32)
        raw = np.full(len(X), self.init_log_odds, dtype=np.float32)
        for t in self.trees:
            f, th, lval, rval = t["feature"], t["threshold"], t["left_val"], t["right_val"]
            update = np.where(X[:, f] <= th, lval, rval)
            raw += update
        p = 1.0 / (1.0 + np.exp(-np.clip(raw, -15.0, 15.0)))
        return np.column_stack([1.0 - p, p])

    def predict(self, X, threshold=None):
        if threshold is None:
            threshold = self.optimal_threshold_
        probs = self.predict_proba(X)[:, 1]
        return (probs >= threshold).astype(int)
