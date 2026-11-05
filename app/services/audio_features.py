"""MELODYX — B3: Audio feature extraction.

Extracts chromagram and RMS energy from a WAV file for downstream
harmony and dynamics analysis.
"""

import logging

import librosa
import numpy as np
from numpy import ndarray

logger = logging.getLogger(__name__)


def extract_features(wav_path: str, sr: int = 22050) -> dict:
    """Extract low-level audio features from a WAV file.

    Args:
        wav_path: Path to a mono WAV file (22 050 Hz expected).
        sr: Target sample rate.

    Returns:
        A dict with keys ``chroma`` (ndarray), ``rms`` (ndarray),
        ``sr`` (int), and ``duration`` (float, seconds).
    """
    y, sr_actual = librosa.load(wav_path, sr=sr, mono=True)
    duration: float = float(librosa.get_duration(y=y, sr=sr_actual))

    chroma: ndarray = librosa.feature.chroma_stft(y=y, sr=sr_actual)
    rms: ndarray = librosa.feature.rms(y=y)[0]

    logger.info(
        "Extracted features from %s — chroma shape %s, RMS shape %s, duration %.2f s",
        wav_path, chroma.shape, rms.shape, duration,
    )

    return {
        "chroma": chroma,
        "rms": rms,
        "sr": sr_actual,
        "duration": round(duration, 4),
    }
