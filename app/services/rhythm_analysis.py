"""MELODYX — B3: Rhythm analysis.

Estimates tempo, beat positions, and time signature from a WAV file
using librosa beat tracking.
"""

import logging

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# Beat regularity threshold for simple‑time heuristics
_REGULARITY_THRESHOLD: float = 0.15  # relative std‑dev of beat intervals


def analyze_rhythm(wav_path: str, sr: int = 22050) -> dict:
    """Analyse rhythm: tempo, beat times, and time signature.

    Args:
        wav_path: Path to a mono WAV file.
        sr: Target sample rate.

    Returns:
        A dict with ``tempo_bpm``, ``beats`` (list of floats, seconds),
        and ``time_signature`` — each carrying ``value``, ``confidence``,
        and ``source``.
    """
    y, sr_actual = librosa.load(wav_path, sr=sr, mono=True)

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr_actual)
    # librosa >= 0.10 returns tempo as an ndarray
    raw_tempo: float = float(np.atleast_1d(tempo)[0])
    if np.isnan(raw_tempo) or raw_tempo <= 0:
        tempo_value = 120.0
        tempo_confidence = 0.2
    else:
        tempo_value = raw_tempo
        tempo_confidence = 0.8

    beat_times: list[float] = [
        round(float(t), 4)
        for t in librosa.frames_to_time(beat_frames, sr=sr_actual)
    ]

    # ---- Tempo confidence --------------------------------------------------
    # Higher confidence when tempo is in a common musical range and the beat
    # tracker returns enough beats relative to the audio duration.
    duration: float = float(librosa.get_duration(y=y, sr=sr_actual))
    expected_beats = (duration * tempo_value) / 60.0
    beat_ratio = len(beat_times) / max(expected_beats, 1.0)
    tempo_confidence: float = round(
        float(np.clip(beat_ratio, 0.0, 1.0)), 3
    )

    # ---- Time signature heuristic ------------------------------------------
    time_sig, ts_confidence = _estimate_time_signature(beat_times)

    logger.info(
        "Rhythm: tempo=%.1f bpm (conf=%.2f), %d beats, sig=%s (conf=%.2f)",
        tempo_value, tempo_confidence, len(beat_times), time_sig, ts_confidence,
    )

    return {
        "tempo_bpm": {
            "value": round(tempo_value, 2),
            "confidence": tempo_confidence,
            "source": "librosa",
        },
        "beats": beat_times,
        "time_signature": {
            "value": time_sig,
            "confidence": round(ts_confidence, 3),
            "source": "librosa",
        },
    }


def _estimate_time_signature(
    beat_times: list[float],
) -> tuple[str, float]:
    """Heuristic time-signature estimation based on beat regularity.

    If the inter-beat intervals are very regular (low relative std-dev),
    we assume 4/4 with higher confidence.  When beats cluster into groups
    of three, we report 3/4.  Falls back to 4/4 with low confidence.

    Returns:
        A tuple of (time_signature_string, confidence).
    """
    if len(beat_times) < 4:
        return "4/4", 0.3

    intervals = np.diff(beat_times)
    if len(intervals) == 0:
        return "4/4", 0.3

    mean_interval: float = float(np.mean(intervals))
    if mean_interval == 0:
        return "4/4", 0.3

    relative_std: float = float(np.std(intervals) / mean_interval)

    # Check for grouping in threes: if every 3rd beat is slightly accented
    # (approximated by checking if interval pattern repeats every 3 beats)
    if len(intervals) >= 6:
        groups_of_3 = intervals[: len(intervals) - len(intervals) % 3].reshape(-1, 3)
        # In 3/4 the first beat of each group tends to have a longer preceding gap
        col_means = groups_of_3.mean(axis=0)
        if col_means.shape[0] == 3:
            ratio = float(np.max(col_means) / (np.min(col_means) + 1e-9))
            if ratio > 1.2:
                confidence = max(0.3, min(0.8, 1.0 - relative_std))
                return "3/4", confidence

    # Default: 4/4
    if relative_std < _REGULARITY_THRESHOLD:
        return "4/4", 0.8
    elif relative_std < 0.3:
        return "4/4", 0.6
    else:
        return "4/4", 0.4
