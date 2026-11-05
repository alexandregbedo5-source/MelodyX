"""MELODYX — B3: Harmony analysis.

Estimates the musical key (Krumhansl-Kessler profiles) and performs
chord detection via chroma template matching with temporal smoothing.
"""

import logging
from typing import Optional

import librosa
import numpy as np
from numpy import ndarray

logger = logging.getLogger(__name__)

# ── Krumhansl-Kessler key profiles ────────────────────────────────────────
# 12 values: C  C#  D  D#  E  F  F#  G  G#  A  A#  B

_KK_MAJOR: ndarray = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)

_KK_MINOR: ndarray = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

_NOTE_NAMES: list[str] = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
]

# ── Chord templates (triads) ──────────────────────────────────────────────
# Binary templates for major / minor triads rooted on each pitch class.
# Index = pitch class, value = 1 if present in chord.

def _build_triad_templates() -> list[tuple[str, ndarray]]:
    """Build (label, 12-d template) for every major and minor triad."""
    templates: list[tuple[str, ndarray]] = []
    major_intervals = [0, 4, 7]
    minor_intervals = [0, 3, 7]
    for root in range(12):
        maj = np.zeros(12, dtype=np.float64)
        for i in major_intervals:
            maj[(root + i) % 12] = 1.0
        templates.append((_NOTE_NAMES[root], maj))

        mn = np.zeros(12, dtype=np.float64)
        for i in minor_intervals:
            mn[(root + i) % 12] = 1.0
        templates.append((f"{_NOTE_NAMES[root]}m", mn))
    return templates


_TRIAD_TEMPLATES: list[tuple[str, ndarray]] = _build_triad_templates()


# ── Public API ─────────────────────────────────────────────────────────────

def analyze_harmony(wav_path: str, sr: int = 22050) -> dict:
    """Estimate key and chords for a WAV file.

    Args:
        wav_path: Path to a mono WAV file.
        sr: Target sample rate.

    Returns:
        A dict with ``key`` (value, confidence, source) and ``chords``
        (list of chord dicts with label, start, end, confidence, source).
    """
    y, sr_actual = librosa.load(wav_path, sr=sr, mono=True)
    chroma: ndarray = librosa.feature.chroma_stft(y=y, sr=sr_actual)

    # ---- Key estimation ---------------------------------------------------
    key_name, key_confidence = _estimate_key(chroma)

    # ---- Chord estimation -------------------------------------------------
    hop_length: int = 512
    chords = _estimate_chords(chroma, sr_actual, hop_length)

    logger.info(
        "Harmony: key=%s (conf=%.2f), %d chord segments",
        key_name, key_confidence, len(chords),
    )

    return {
        "key": {
            "value": key_name,
            "confidence": round(key_confidence, 3),
            "source": "librosa",
        },
        "chords": chords,
    }


# ── Key detection ──────────────────────────────────────────────────────────

def _estimate_key(chroma: ndarray) -> tuple[str, float]:
    """Krumhansl-Kessler key estimation.

    Correlates the mean chroma vector with all 24 major/minor profiles
    and returns the best match.

    Returns:
        (key_name, confidence) — e.g. ``("C major", 0.85)``.
    """
    mean_chroma: ndarray = np.mean(chroma, axis=1)  # shape (12,)
    if np.linalg.norm(mean_chroma) < 1e-9:
        return "C major", 0.0

    best_corr: float = -1.0
    best_key: str = "C major"
    all_corrs: list[float] = []

    for shift in range(12):
        profile_maj = np.roll(_KK_MAJOR, shift)
        profile_min = np.roll(_KK_MINOR, shift)

        corr_maj = float(np.corrcoef(mean_chroma, profile_maj)[0, 1])
        corr_min = float(np.corrcoef(mean_chroma, profile_min)[0, 1])

        all_corrs.extend([corr_maj, corr_min])

        if corr_maj > best_corr:
            best_corr = corr_maj
            best_key = f"{_NOTE_NAMES[shift]} major"
        if corr_min > best_corr:
            best_corr = corr_min
            best_key = f"{_NOTE_NAMES[shift]} minor"

    # Confidence: how much the winner stands out
    sorted_corrs = sorted(all_corrs, reverse=True)
    if len(sorted_corrs) >= 2:
        gap = sorted_corrs[0] - sorted_corrs[1]
        confidence = float(np.clip(best_corr * 0.6 + gap * 2.0, 0.0, 1.0))
    else:
        confidence = float(np.clip(best_corr, 0.0, 1.0))

    return best_key, confidence


# ── Chord detection ────────────────────────────────────────────────────────

def _estimate_chords(
    chroma: ndarray,
    sr: int,
    hop_length: int = 512,
) -> list[dict]:
    """Estimate chords via template matching with temporal smoothing.

    Segments the chroma into overlapping windows, matches each against
    triad templates, then merges consecutive identical labels.

    Returns:
        A list of chord dicts sorted by start time.
    """
    n_frames: int = chroma.shape[1]
    if n_frames == 0:
        return []

    # Window size in frames (~0.5 s at 22050/512 ≈ 43 fps)
    fps: float = sr / hop_length
    win_frames: int = max(1, int(fps * 0.5))
    step: int = max(1, win_frames // 2)

    raw_labels: list[str] = []
    raw_confs: list[float] = []
    frame_positions: list[int] = []

    for start_f in range(0, n_frames, step):
        end_f = min(start_f + win_frames, n_frames)
        segment_chroma = np.mean(chroma[:, start_f:end_f], axis=1)
        seg_norm = float(np.linalg.norm(segment_chroma))
        if seg_norm < 1e-9:
            raw_labels.append("N")
            raw_confs.append(0.0)
            frame_positions.append(start_f)
            continue

        segment_chroma = segment_chroma / seg_norm

        best_label: str = "N"
        best_sim: float = 0.0
        for label, template in _TRIAD_TEMPLATES:
            t_norm = template / (np.linalg.norm(template) + 1e-9)
            sim = float(np.dot(segment_chroma, t_norm))
            if sim > best_sim:
                best_sim = sim
                best_label = label

        raw_labels.append(best_label)
        raw_confs.append(round(best_sim, 3))
        frame_positions.append(start_f)

    # ---- Temporal smoothing (majority vote, window=3) ----------------------
    smoothed_labels = _temporal_smooth(raw_labels, window=3)

    # ---- Merge consecutive identical chords --------------------------------
    chords: list[dict] = []
    if not smoothed_labels:
        return chords

    prev_label: str = smoothed_labels[0]
    seg_start_frame: int = frame_positions[0]
    seg_confs: list[float] = [raw_confs[0]]

    for i in range(1, len(smoothed_labels)):
        if smoothed_labels[i] != prev_label:
            start_sec = round(float(seg_start_frame / fps), 4)
            end_sec = round(float(frame_positions[i] / fps), 4)
            avg_conf = round(float(np.mean(seg_confs)), 3)
            if prev_label != "N":
                chords.append({
                    "label": prev_label,
                    "start": start_sec,
                    "end": end_sec,
                    "confidence": avg_conf,
                    "source": "librosa",
                })
            prev_label = smoothed_labels[i]
            seg_start_frame = frame_positions[i]
            seg_confs = [raw_confs[i]]
        else:
            seg_confs.append(raw_confs[i])

    # Last segment
    start_sec = round(float(seg_start_frame / fps), 4)
    end_sec = round(float((frame_positions[-1] + win_frames) / fps), 4)
    avg_conf = round(float(np.mean(seg_confs)), 3)
    if prev_label != "N":
        chords.append({
            "label": prev_label,
            "start": start_sec,
            "end": end_sec,
            "confidence": avg_conf,
            "source": "librosa",
        })

    return chords


def _temporal_smooth(labels: list[str], window: int = 3) -> list[str]:
    """Apply majority-vote smoothing to a sequence of chord labels."""
    if len(labels) <= window:
        return labels

    smoothed: list[str] = []
    half = window // 2
    for i in range(len(labels)):
        lo = max(0, i - half)
        hi = min(len(labels), i + half + 1)
        neighborhood = labels[lo:hi]
        # Majority vote
        counts: dict[str, int] = {}
        for lbl in neighborhood:
            counts[lbl] = counts.get(lbl, 0) + 1
        winner = max(counts, key=lambda k: counts[k])
        smoothed.append(winner)
    return smoothed
