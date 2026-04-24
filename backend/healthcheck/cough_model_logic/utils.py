import time
import random
import os
import pickle
import torch
import numpy as np
import pandas as pd
from dtaidistance import dtw
from sklearn.metrics import accuracy_score
from sklearn.model_selection import KFold
from config import SEED
from typing import Callable, Optional

def set_seeds(seed=304):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True

class DTWLookup:
    """
    Persistent symmetric lookup table for storing pairwise DTW distances.
    This class wraps a dict-of-dicts in a minimal API:
      - Automatic load on initialization
      - Symmetric storage of distances (A->B and B->A)
      - Convenience methods `get()` and `add()`
      - Explicit `save()` to write the lookup to disk
    The lookup is used to cache MFCC-based DTW distances so that
    expensive comparisons do not need to be recomputed across runs.
    """
    def __init__(self, save_dir: str, filename: str):
        self.save_dir = save_dir
        self.filename = filename
        self.path = os.path.join(save_dir, filename)
        os.makedirs(save_dir, exist_ok=True)
        self.lookup = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, "rb") as f:
                data = pickle.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Lookup at {self.path} is not a dict.")
            return data
        return {}

    def save(self):
        with open(self.path, "wb") as f:
            pickle.dump(self.lookup, f, protocol=pickle.HIGHEST_PROTOCOL)

    def get(self, a: str, b: str) -> Optional[float]:
        if a in self.lookup and b in self.lookup[a]:
            return self.lookup[a][b]
        if b in self.lookup and a in self.lookup[b]:
            return self.lookup[b][a]
        return None

    def add(self, a: str, b: str, distance: float):
        self.lookup.setdefault(a, {})[b] = distance
        self.lookup.setdefault(b, {})[a] = distance

def dtw_distance(A: np.ndarray, B: np.ndarray, band_ratio: float = 0.1) -> float:
    A1 = np.linalg.norm(A, axis=0)  # A, B shapes: (n_mfcc, n_frames)
    B1 = np.linalg.norm(B, axis=0)  # Convert 2D MFCCs to 1D sequences
    w = int(len(A1) * band_ratio)   # Sakoe–Chiba window width
    distance = dtw.distance_fast(A1, B1, window=w)
    return distance

def knn_predict(
    reference_df: pd.DataFrame,
    target_row: pd.Series,
    feature_col: str,
    target_col: str,
    lookup: DTWLookup,
    distance_fn: callable,
    k: int = 1,
) -> tuple[str, float]:
    """Predict the target_col of a target sample using k-NN with a 
    custom distance function on feature_col, backed by a DTWLookup cache"""
    id_col = "wav_file"
    target_id = target_row[id_col]
    
    distances = []
    labels = []
    for _, ref_row in reference_df.iterrows():
        ref_id = ref_row[id_col]
        ref_label = ref_row[target_col]
        distance = lookup.get(target_id, ref_id)
        if distance is None:
            if feature_col not in target_row or feature_col not in ref_row:
                raise RuntimeError(
                    f"DTW lookup for pair (target={target_id}, ref={ref_id}) "
                    f"was not found, and '{feature_col}' is missing.\n\n"
                    f"This usually means:\n"
                    f"  - dtw_computed=True was passed to data_preprocessing(),\n"
                    f"    but the DTW lookup file is missing or incomplete.\n"
                    f"  - OR MFCC features were not computed (lookup cannot be built).\n\n"
                    f"Fix: Re-run with dtw_computed=False to force MFCC extraction\n"
                    f"and rebuild the DTW lookup."
                )
            target_sample = target_row[feature_col]
            ref_sample = ref_row[feature_col]
            distance = distance_fn(ref_sample, target_sample)
            lookup.add(target_id, ref_id, distance)

        distances.append(distance)
        labels.append(ref_label)

    k_nearest_indices = np.argsort(distances)[:k]
    k_nearest_labels = [labels[i] for i in k_nearest_indices]
    k_nearest_distances = [distances[i] for i in k_nearest_indices]

    predicted_label = max(set(k_nearest_labels), key=k_nearest_labels.count)
    closest_distance = k_nearest_distances[0]
    return predicted_label, closest_distance

def knn_cross_validate(
    reference_df: pd.DataFrame,
    feature_col: str,
    target_col: str,
    distance_fn: Callable[[np.ndarray, np.ndarray], float],
    lookup_dir: str,
    filename: str,
    k_folds: int = 5,
    k: int = 1,
) -> float:
    """Perform k-fold cross-validation on k-NN classifier with a given distance_fn."""
    kf = KFold(n_splits=k_folds, shuffle=True, random_state=SEED)
    accuracies = []

    lookup = DTWLookup(lookup_dir, filename)
    for train_index, val_index in kf.split(reference_df):
        train_df = reference_df.iloc[train_index]
        val_df = reference_df.iloc[val_index]
        predicted_labels = []
        true_labels = val_df[target_col].tolist()

        for _, target_row in val_df.iterrows():
            #iter_start_time = time.time()
            predicted_label, _ = knn_predict(train_df, target_row, feature_col, target_col, lookup, distance_fn, k)
            predicted_labels.append(predicted_label)
            #iter_duration = time.time() - iter_start_time
            #print(f"{iter_duration:.4f} seconds")


        lookup.save()
        accuracy = accuracy_score(true_labels, predicted_labels)
        accuracies.append(accuracy)
        print(f"Fold accuracy: {accuracy*100:.2f}%")

    avg_accuracy = np.mean(accuracies)
    print(f"Average accuracy: {avg_accuracy*100:.2f}%")
    return avg_accuracy

def knn_eval(train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_col: str,
    target_col: str,
    distance_fn: Callable[[np.ndarray, np.ndarray], float],
    lookup_dir: str,
    filename: str,
    k_folds: int = 5,
    k: int = 1,
) -> float:
    """Evaluate k-NN classifier on test_df."""
    accuracy = 0
    lookup = DTWLookup(lookup_dir, filename)

    predicted_labels = []
    true_labels = test_df[target_col].tolist()
    for i, target_row in test_df.iterrows():
        #iter_start_time = time.time()
        predicted_label, _ = knn_predict(train_df, target_row, feature_col, target_col, lookup, distance_fn, k)
        predicted_labels.append(predicted_label)
        #iter_duration = time.time() - iter_start_time
        #print(f"{iter_duration:.4f} seconds")

    lookup.save()
    accuracy += accuracy_score(true_labels, predicted_labels)
    print(f"Accuracy: {accuracy*100:.2f}%")
    return accuracy
