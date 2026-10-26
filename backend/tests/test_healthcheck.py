import math
import struct
import wave
from io import BytesIO
import pytest
from healthcheck.routes import _analyze_audio_waveform


def _create_synthetic_wav(duration_sec=1.5, sample_rate=16000, frequency=440.0, bursts=2) -> bytes:
    """Generates an in-memory 16-bit PCM mono WAV file with simulated cough bursts."""
    num_samples = int(duration_sec * sample_rate)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            t = float(i) / sample_rate
            # Add burst transients at 0.3s and 0.8s
            amplitude = 25000.0 if (0.3 <= t <= 0.45 or 0.8 <= t <= 0.95) else 1500.0
            sample_val = int(amplitude * math.sin(2.0 * math.pi * frequency * t))
            frames.extend(struct.pack("<h", sample_val))
        wf.writeframes(frames)
    return buffer.getvalue()


def test_audio_waveform_analysis():
    wav_bytes = _create_synthetic_wav(duration_sec=1.5, bursts=2)
    metrics = _analyze_audio_waveform(wav_bytes)

    assert metrics["duration_sec"] == 1.5
    assert metrics["framerate"] == 16000
    assert metrics["channels"] == 1
    assert metrics["rms_energy"] > 0.05
    assert metrics["peak_amplitude"] > 0.5
    assert metrics["zero_crossing_rate"] > 0.01
    assert metrics["detected_coughs"] >= 2


def test_audio_waveform_rejects_empty():
    with pytest.raises(ValueError):
        _analyze_audio_waveform(b"")


def test_audio_waveform_rejects_too_short():
    short_wav = _create_synthetic_wav(duration_sec=0.1)
    with pytest.raises(ValueError):
        _analyze_audio_waveform(short_wav)
