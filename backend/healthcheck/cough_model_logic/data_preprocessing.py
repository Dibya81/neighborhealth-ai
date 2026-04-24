import os
import re
import numpy as np
import pandas as pd
import librosa
from typing import Optional, Callable, Dict, Tuple
from utils import knn_predict, DTWLookup, dtw_distance
from config import SEED, WAV_SUBDIR, ROOT_DIR
from feature_extraction import get_mfcc, get_mfsc, get_mel_spectrogram, get_raw_waveform

FEATURE_FUNCTIONS = {
    "mfcc": get_mfcc,
    "mfsc": get_mfsc,
    "mel_spectrogram": get_mel_spectrogram,
    "raw_waveform": get_raw_waveform,
}

FEATURE_COLS = list(FEATURE_FUNCTIONS.keys())

FEATURE_PARAM_FILTERS = {
    "mfcc": lambda p: p,
    "mfsc": lambda p: {k: v for k, v in p.items() if k not in {"lifter", "n_mfcc"}},
    "mel_spectrogram": lambda p: {k: v for k, v in p.items() if k not in {"lifter", "n_mfcc"}},
    "raw_waveform": lambda p: {}, 
}

DEFAULTS = {"n_mfcc": 13, "n_mels": 80}

def parse_kaldi_metadata(kaldi_dir: str, class_to_id: dict, wav_dir: str = WAV_SUBDIR) -> list:
    """
    Parse Kaldi-style data directory to extract file paths and labels.
    Args:
        kaldi_dir (str): Path to Kaldi-style data directory (e.g., 'data/train').
        class_to_id (dict): Mapping from class name (e.g., 'pos', 'neg') to numeric ID.
    Returns:
        pd.DataFrame: Columns = ['wav_file', 'label', 'label_id'].
    """
    text_path = os.path.join(kaldi_dir, "text")
    wav_scp_path = os.path.join(kaldi_dir, "wav.scp")
    key_to_wav = {}
    key_to_label = {}
    with open(wav_scp_path, "rt") as wav_scp:             # wav.scp: key to path mapping
        for line in wav_scp:
            key, wav_file = line.strip().split(" ", 1)
            key_to_wav[key] = wav_file
            key_to_label[key] = None

    if os.path.isfile(text_path):                         # text: key to label mapping
        with open(text_path, "rt") as text_file:
            for line in text_file:
                key, label = line.strip().split(" ", 1)
                key_to_label[key] = label

    data = []
    for key, wav_file in key_to_wav.items():
        wav_path = os.path.join(wav_dir, wav_file)
        if not os.path.isfile(wav_path):
            print(f"Missing file skipped: {wav_path}")
            continue
        label = key_to_label[key]
        label_id = class_to_id[label] if label is not None else -1
        data.append((wav_file, label, label_id))

    df = pd.DataFrame(data, columns=["wav_file", "label", "label_id"])
    return df

def detect_source_id(wav_path: str) -> int:
    """Heuristically assign source ID (1–4) based on filename pattern."""
    name = os.path.basename(wav_path).lower()
    prefix = name.split("_", 1)[0]
    if "audio_file" in name:
        return 2    # Cambridge
    elif name.startswith("speech_commands"):
        return 4    # Coughvid
    elif len(prefix) == 28 and prefix.isalnum():
        return 3    # Coswara
    else:
        return 1    # Cambridge?

def detect_audio_type(wav_file: str) -> str:
    """Detects the audio type from the filename."""
    name = os.path.basename(wav_file).lower()
    if re.search(r'coughs?|coughing', name):
        return 'cough'
    elif re.search(r'breath[s|ing]?', name):
        return 'breath'
    else:
        return 'unknown'

def enrich_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Add source_id and audio_type columns to the dataframe."""
    df = df.copy()
    df["source_id"] = df["wav_file"].apply(detect_source_id)
    df["audio_type"] = df["wav_file"].apply(detect_audio_type)
    return df

def extract_feature_from_audio(y: np.ndarray, sr: int, feature_fn: Callable, params: Optional[Dict] = None, normalize: bool = True) -> np.ndarray:
    """Call a feature function with y, sr and named params."""
    params = params or {}
    feat = feature_fn(y=y, sr=sr, **params)
    if normalize:  # Apply mean-variance normalization per feature dimension.
        feat = feat - feat.mean(axis=1, keepdims=True)
        feat = feat / (feat.std(axis=1, keepdims=True) + 1e-8)
    return feat

def _process_one_row(
    wav_file: str,
    feature_fn: Callable,
    params: Dict,
    save_dir: Optional[str],
    wav_dir: Optional[str],
    load_if_exists: bool,
    normalize: bool,
    target_sr: Optional[int] = None,
    ) -> np.ndarray:
    """From wav_file (str), returns selected feature (numpy array)."""
    try:
        if save_dir is not None and load_if_exists:
            base = os.path.splitext(os.path.basename(wav_file))[0]   # Cache filename: <basename>.<feature_fn_name>.npy
            fname = f"{base}.{feature_fn.__name__}.npy"
            cache_path = os.path.join(save_dir, fname)
            if load_if_exists and os.path.exists(cache_path):        # Load pre-computed features
                return np.load(cache_path)
        
        wav_path = os.path.join(wav_dir, wav_file)  
        if not os.path.isfile(wav_path):
            print(f"File not found: {wav_path}")
            return None

        y, sr = librosa.load(wav_path, sr=target_sr)
        feat = extract_feature_from_audio(y, sr, feature_fn, params, normalize)
        
        if save_dir is not None and load_if_exists:
            os.makedirs(save_dir, exist_ok=True)
            np.save(cache_path, feat)
        return feat
    
    except Exception as e:
        print(f"Error processing {wav_file}: {e}")
        return None

def add_features_to_df(
    df: pd.DataFrame,
    feature_fn: Callable,
    params: Optional[Dict] = None,
    wav_col: str = "wav_path",
    out_col: str = "features",
    save_dir: Optional[str] = None,
    wav_dir: str = WAV_SUBDIR,
    load_if_exists: bool = True,
    normalize: bool = True,
    target_sr: Optional[int] = 16000,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Compute and attach features to a DataFrame.
    Args:
      df: pandas DataFrame containing audio file paths in column 'wav_col'.
      feature_fn: Example: get_mfcc, get_mfsc.
      params: dict of keyword args to pass to feature_fn.
      wav_col: name of column in df with wav filenames.
      out_col: output column name where features will be stored.
      save_dir: cache feature .npy files here.
      wav_dir: directory of audio files.
      load_if_exists: if True and cache exists, load instead of recompute.
      normalize: whether to apply mean-variance normalization per feature dimension.
      target_sr: target sampling rate.
      verbose: whether to print progress.
    Returns:
      New DataFrame with an added 'out_col' column with features.
    """
    params = params or {}
    wav_files = df[wav_col].tolist()
    features  = []
    valid_rows = []
    for i, file in enumerate(wav_files):
        if verbose and (i % 100 == 0):
            print(f"Processing {i}/{len(wav_files)}: {file}")
        feat = _process_one_row(file, feature_fn, params, save_dir, wav_dir, load_if_exists, normalize, target_sr)
        if feat is not None:
            valid_rows.append(i)
            features.append(feat)
            
    new_df = df.iloc[valid_rows].copy()
    new_df[out_col] = features 
    return new_df

def add_features_to_splits(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    params: dict,
    feats_dir: str,
    target_sr: int,
    feature_type: str,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute audio features (MFCC, MFSC, Mel spectrogram) for both train and test splits.
    Args:
        train_df: Training metadata containing a 'wav_file' column.
        test_df: Test metadata containing a 'wav_file' column.
        params: Base parameter dictionary (typically MFCC params); filtered depending on feature_type.
        feats_dir: Directory under ROOT_DIR where features will be saved.
        target_sr: Target sampling rate.
        feature_type: One of: "mfcc", "mfsc", "mel_spectrogram".
        verbose: Whether to print progress messages.
    Returns
        Updated copies of train_df and test_df with a new `feature_type` column.
    """

    feature_type = feature_type.lower()
    if feature_type not in FEATURE_FUNCTIONS:
        raise ValueError(
            f"Invalid feature_type='{feature_type}'. "
            f"Must be one of: {list(FEATURE_FUNCTIONS.keys())}"
        )

    if verbose:
        print(f"Adding {feature_type.upper()} features...\n")

    feature_fn = FEATURE_FUNCTIONS[feature_type]
    feature_params = FEATURE_PARAM_FILTERS[feature_type](params.copy())  # Allows us to reuse mfcc_params dictionary
    
    if feature_type == "mfcc":                                           # Full directory for the features
        n_mfcc = params.get("n_mfcc", DEFAULTS["n_mfcc"])
        feat_suffix = feature_type if n_mfcc == DEFAULTS["n_mfcc"] else f"{feature_type}.{n_mfcc}"
    elif feature_type in {"mfsc", "mel_spectrogram"}:
        n_mels = params.get("n_mels", DEFAULTS["n_mels"])
        feat_suffix = feature_type if n_mels == DEFAULTS["n_mels"] else f"{feature_type}.{n_mels}"
    else:
        feat_suffix = feature_type

    wav_dir = os.path.join(ROOT_DIR, WAV_SUBDIR)
    train_save = os.path.join(ROOT_DIR, feats_dir, "train", feat_suffix)
    test_save = os.path.join(ROOT_DIR, feats_dir, "test", feat_suffix)
    cache_enabled = feature_type != "raw_waveform"
    
    train_out = add_features_to_df(
        train_df,
        feature_fn=feature_fn,
        params=feature_params,
        wav_col="wav_file",
        out_col=feature_type,
        save_dir=train_save,
        wav_dir=wav_dir,
        load_if_exists=cache_enabled,
        target_sr=target_sr,
        verbose=verbose,
    )

    test_out = add_features_to_df(
        test_df,
        feature_fn=feature_fn,
        params=feature_params,
        wav_col="wav_file",
        out_col=feature_type,
        save_dir=test_save,
        wav_dir=wav_dir,
        load_if_exists=cache_enabled,
        target_sr=target_sr,
        verbose=verbose,
    )

    return train_out, test_out

def change_features(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    params: dict,
    feats_dir: str,
    target_sr: int,
    feature_type: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Replace the features in train_df and test_df with feature_type (MFCC, MFSC, or Mel Spectrogram).
    Args
        train_df, test_df: Input metadata with any subset of ['mfcc', 'mfsc', 'mel_spectrogram'].
        params: Base parameter dictionary; typically MFCC params.
        feats_dir: Directory for saving computed features.
        target_sr: Target sampling rate for audio files.
        feature_type: Feature to add ("mfcc", "mfsc", or "mel_spectrogram").
    Returns
        DataFrames with only the new feature_type column.
    """
    cols_to_drop = [c for c in FEATURE_COLS if c in train_df.columns]     # Drop existing feature columns
    train_df = train_df.drop(columns=cols_to_drop, errors="ignore")
    test_df = test_df.drop(columns=cols_to_drop, errors="ignore")
    
    return add_features_to_splits(                                        # Add the new features                                      
        train_df, test_df,
        params=params,
        feats_dir=feats_dir,
        target_sr=target_sr,
        feature_type=feature_type,
    )

def knn_extend_labels(
    reference_df: pd.DataFrame,
    target_df: pd.DataFrame,
    feature_col: str,
    target_col: str,
    lookup: Dict,
    distance_fn: Callable[[np.ndarray, np.ndarray], float],
    k: int = 1,
) -> pd.DataFrame:
    """Uses k-NN to extend labels (target_col) from reference_df to target_df
    using feature_col and a distance_fn (lookup contains precomputed distances)."""
    predicted_labels = []
    closest_dists = []
    target_df = target_df.copy()
    for _, target_row in target_df.iterrows():
        predicted_label, dist = knn_predict(reference_df, target_row, feature_col, target_col, lookup, distance_fn, k=k)
        predicted_labels.append(predicted_label)
        closest_dists.append(dist)
                
    target_df.loc[:, target_col] = predicted_labels
    target_df.loc[:, "1nn_closest"] = closest_dists
    return target_df

def clean_audio_type(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feats_dir: str,
    clean_test: bool = True,
    threshold: float = 20.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Classify audio samples with 'unknown' audio_type using 1-NN with DTW over MFCC features.
    Requires either that 1) complete lookup is built, 2) both train_df and test_df contain an 'mfcc' column.
      - Loads or builds a lookup based on mfcc DTW distances.
      - Assigns 'cough' or 'breath' to samples labeled 'unknown' using 1-NN.
      - Removes samples whose nearest neighbor distance exceeds a threshold (chosen heuristically).
    Args
        train_df: Training metadata with 'mfcc' and 'audio_type'.
        test_df: Test metadata with 'mfcc' and 'audio_type'.
        feats_dir: Path (relative to ROOT_DIR) containing the DTW lookup directory.
        clean_test: Whether to perform the same cleaning on the test split.
        threshold: Maximum allowed DTW distance to accept a nearest neighbor label.
    Returns
        New train_df and test_df with corrected audio_type values.
    """
    print("Processing training data...\n")                           # Load lookups
    lookup_dir = os.path.join(ROOT_DIR, feats_dir, "lookups")
    lookup_file = "dtw_lookup.pkl"
    lookup = DTWLookup(lookup_dir, lookup_file)

    def extend_and_filter(df_ref, df_target):                        # Helper function
        """Assign labels by 1-NN DTW and filter by threshold."""
        labeled = knn_extend_labels(
            df_ref,
            df_target,
            feature_col="mfcc",
            target_col="audio_type",
            lookup=lookup,
            distance_fn=dtw_distance,
            k=1,
        )
        return (labeled[labeled["1nn_closest"] <= threshold].drop(columns=["1nn_closest"]).copy())

    train_ref = train_df[train_df["audio_type"].isin(["cough", "breath"])]            # Clean training data
    train_unknown = train_df[train_df["audio_type"] == "unknown"]
    train_fixed_unknown = extend_and_filter(train_ref, train_unknown)
    train_clean = pd.concat([train_ref, train_fixed_unknown], ignore_index=True)

    if clean_test:                                                                    # Clean test data
        print("Processing test data...\n")
        test_ref = test_df[test_df["audio_type"].isin(["cough", "breath"])]
        test_unknown = test_df[test_df["audio_type"] == "unknown"]
        test_fixed_unknown = extend_and_filter(train_ref, test_unknown)
        test_clean = pd.concat([test_ref, test_fixed_unknown], ignore_index=True)
    else:
        test_clean = test_df.copy()

    lookup.save()
    return train_clean, test_clean

def partition_by_source(train_df: pd.DataFrame, test_df: pd.DataFrame, source: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Partition the dataset into train and test based on a specific source."""
    full_df = pd.concat([train_df, test_df], ignore_index=True)
    if source == 1 or source == 2: # sources 1 and 2 are the same source
        test_partition = full_df[full_df['source_id'].isin([1, 2])]
        train_partition = full_df[~full_df['source_id'].isin([1, 2])]
    else:
        test_partition = full_df[full_df['source_id'] == source]
        train_partition = full_df[full_df['source_id'] != source]
        
    return train_partition, test_partition

def process_data(
    params: Dict,
    class_to_id: Dict[str, int],
    feats_dir: str,
    feature_type: str,
    target_sr: int = 16000,
    dtw_computed: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Preprocess the dataset by:
      1. Optionally computing mfcc to build DTW lookup (if dtw_computed=False).
      2. Cleaning audio_type labels using DTW.
      3. Computing the final desired feature type.
    
    Notes
    -----
    - If dtw_computed=True, this function assumes that the DTW lookup already
      exists in `feats_dir/lookups/dtw_lookup.pkl`. If the lookup is missing or
      incomplete, the function will fail during clean_audio_type().
    - params should be a dictionary of mfcc parameters. It can be reused for 
      mfsc or mel_spectrogram, non-applicable parameters are automatically
      filtered out by FEATURE_PARAM_FILTERS.
    """
    train_df = enrich_metadata(parse_kaldi_metadata(os.path.join(ROOT_DIR, "data", "train"), class_to_id))
    test_df  = enrich_metadata(parse_kaldi_metadata(os.path.join(ROOT_DIR, "data", "test"), class_to_id))

    if not dtw_computed:                                   # Add mfcc for DTW if needed (lookup not built)
        train_df, test_df = add_features_to_splits(
            train_df, test_df,
            params=params,
            feats_dir=feats_dir,
            target_sr=target_sr,
            feature_type="mfcc",
        )

    train_df, test_df = clean_audio_type(train_df, test_df, feats_dir) # Clean audio_type (uses lookup or mfcc column)

    if feature_type != "mfcc" and not dtw_computed:        # Drop mfcc if feature_type is not mfcc
        train_df = train_df.drop(columns=["mfcc"])
        test_df = test_df.drop(columns=["mfcc"])

    if feature_type != "mfcc" or dtw_computed:             # Add desired features
        train_df, test_df = add_features_to_splits(
            train_df, test_df,
            params=params,
            feats_dir=feats_dir,
            target_sr=target_sr,
            feature_type=feature_type,
        )

    return train_df, test_df
