import numpy as np
import scipy.signal
import librosa
from functools import lru_cache
from typing import Optional

@lru_cache(maxsize=16)
def get_window(n: int, type: str ='hamming') -> np.ndarray:
    return scipy.signal.get_window(type, n)

@lru_cache(maxsize=16)
def get_mel_filterbank(sr: int, n_fft: int, n_mels: int, fmin: float, fmax: float) -> np.ndarray:
    return librosa.filters.mel(sr=sr, n_fft=n_fft, n_mels=n_mels, fmin=fmin, fmax=fmax)

def get_raw_waveform(y: np.ndarray, sr: int) -> np.ndarray:
    return y[np.newaxis, :]   # shape: (1, T)

def get_mel_spectrogram(
    y: np.ndarray,
    sr: int,
    preemph: float = 0.97,
    n_fft: int = 2048,
    hop_length: Optional[int] = None,
    win_length: Optional[int] = None,
    n_mels: int = 80,
    fmin: float = 0.0,
    fmax: Optional[float] = None,
    win_size: float = 0.025,
    win_stride: float = 0.01,
    use_cached: bool = True,
) -> np.ndarray:
    """
    Compute the Mel power spectrogram from an audio signal.
    Args:
      y: np.ndarray. Audio time series.
      sr: int. Sampling rate.
      preemph: float. Pre-emphasis coefficient (default 0.97).
      n_fft: int. FFT window size.
      hop_length: int, optional. Hop length (in samples).
      win_length: int, optional. Window length (in samples).
      n_mels: int. Number of Mel bands.
      fmin: float. Minimum frequency (Hz).
      fmax: float, optional. Maximum frequency (Hz). Defaults to Nyquist frequency sr/2.
      win_size: float. Window size in seconds (default 0.025).
      win_stride: float. Hop size in seconds (default 0.01).
      use_cached: bool. Whether to use cached Mel filterbank and window functions for speed.
    Returns:
      np.ndarray. Mel power spectrogram (n_mels, n_frames).
    """
    fmax = fmax or sr / 2.0
    y = librosa.effects.preemphasis(y, coef=preemph)  # Boost high frequencies
    hop_length = hop_length or int(round(win_stride * sr))
    win_length = win_length or int(round(win_size * sr))
    if use_cached:
        window = get_window(win_length, 'hamming')    # Precompute window and filterbank using cached functions
        mel_fb = get_mel_filterbank(sr, n_fft, n_mels, fmin, fmax)

        stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length, win_length=win_length, window=window)
        power_spec = np.abs(stft) ** 2
        mel_spec = np.dot(mel_fb, power_spec)         # Compute STFT and apply mel filterbank manually
    else:                                             # Librosa's built-in (Recomputes filters each call)
        mel_spec = librosa.feature.melspectrogram(
            y=y,
            sr=sr,
            n_fft=n_fft,
            hop_length=hop_length,
            win_length=win_length,
            window="hamming",
            n_mels=n_mels,
            fmin=fmin,
            fmax=fmax,
            power=2.0,
        )
    return mel_spec

def get_mfsc(
    y: np.ndarray,
    sr: int,
    preemph: float = 0.97,
    n_fft: int = 2048,
    hop_length: Optional[int] = None,
    win_length: Optional[int] = None,
    n_mels: int = 80,
    fmin: float = 0.0,
    fmax: Optional[float] = None,
    win_size: float = 0.025,
    win_stride: float = 0.01,
    use_cached: bool = True,
) -> np.ndarray:
    """
    Compute MFSC (log-Mel energies) from an audio signal.
    Args:
      y: np.ndarray. Audio time series.
      sr: int. Sampling rate.
      Other parameters: Passed directly to `get_mel_spectrogram`.
      use_cached: bool. Whether to use cached Mel filterbank and window functions for speed.
    Returns:
      np.ndarray. Log-Mel spectrogram in dB (n_mels, n_frames).
    """
    mel_spec = get_mel_spectrogram(  # Includes preemphasis and windowing
        y=y,
        sr=sr,
        preemph=preemph,
        n_fft=n_fft,
        hop_length=hop_length,
        win_length=win_length,
        n_mels=n_mels,
        fmin=fmin,
        fmax=fmax,
        win_size=win_size,
        win_stride=win_stride,
    )

    mfsc = librosa.power_to_db(mel_spec, ref=np.max)
    return mfsc

def get_mfcc(
    y: np.ndarray,
    sr: int,
    n_mfcc: int = 13,
    lifter: int = 22,
    preemph: float = 0.97,
    n_fft: int = 2048,
    hop_length: Optional[int] = None,
    win_length: Optional[int] = None,
    n_mels: int = 80,
    fmin: float = 0.0,
    fmax: Optional[float] = None,
    win_size: float = 0.025,
    win_stride: float = 0.01,
    use_cached: bool = True,
) -> np.ndarray:
    """
    Compute MFCC from the audio signal (with preemphasis and liftering).
    Args:
      y: np.ndarray. Audio time series.
      sr: int. Sampling rate.
      n_mfcc: int. Number of MFCC coefficients.
      lifter: int. Liftering parameter (0 to disable).
      preemph: float. Pre-emphasis coefficient.
      Other parameters: Passed to `get_mfsc`.
      use_cached: bool. Whether to use cached Mel filterbank and window functions for speed.
    Returns:
      np.ndarray. MFCCs (n_mfcc, n_frames).
    """
    mfsc = get_mfsc(              # Includes preemphasis and windowing
        y=y,
        sr=sr,
        preemph=preemph,
        n_fft=n_fft,
        hop_length=hop_length,
        win_length=win_length,
        n_mels=n_mels,
        fmin=fmin,
        fmax=fmax,
        win_size=win_size,
        win_stride=win_stride,
    )
    mfcc = librosa.feature.mfcc(S=mfsc, n_mfcc=n_mfcc, dct_type=2, norm="ortho")

    if lifter > 0:                # Liftering (optional)
        n = np.arange(n_mfcc)
        lift = 1 + (lifter / 2.0) * np.sin(np.pi * (n + 1) / lifter)
        mfcc = mfcc * lift[:, None]
    return mfcc