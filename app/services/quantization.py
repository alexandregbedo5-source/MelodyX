"""MELODYX — B4: Note quantization and measure grouping.

Snaps transcribed note start times to the nearest beat-grid position
(16th-note resolution), groups notes into measures, and assigns hand
(left / right) based on pitch.
"""

import logging
from copy import deepcopy

import numpy as np

logger = logging.getLogger(__name__)

# Split point between left and right hand (MIDI note number)
_SPLIT_POINT: int = 60      # Middle C
_HYSTERESIS: int = 2         # ±2 semitones hysteresis zone


def quantize_notes(
    notes: list[dict],
    beats: list[float],
    time_signature: str = "4/4",
) -> tuple[list[dict], list[dict]]:
    """Quantize note start times and build measure structures.

    Args:
        notes: List of note dicts from the transcription stage.
        beats: Beat times in seconds (ascending).
        time_signature: Time signature string, e.g. ``"4/4"`` or ``"3/4"``.

    Returns:
        A tuple ``(quantized_notes, measures)`` where *quantized_notes*
        is a copy of the input notes enriched with ``quantized_start``,
        ``measure``, ``beat_position``, and ``hand`` fields, and
        *measures* is a list of measure dicts.
    """
    if not notes:
        return [], []

    beats_arr = np.array(sorted(beats), dtype=np.float64) if beats else np.array([], dtype=np.float64)
    beats_per_measure = _beats_per_measure(time_signature)

    max_note_time = max((n.get("start", 0.0) + n.get("duration", 0.5) for n in notes), default=10.0)
    max_time = max(max_note_time + 4.0, 10.0)

    # ---- Build the 16th-note grid -----------------------------------------
    grid = _build_grid(beats_arr, subdivisions=4, max_time=max_time)

    # ---- Build measures ----------------------------------------------------
    measures = _build_measures(beats_arr, beats_per_measure, time_signature, max_time=max_time)

    # ---- Quantize each note ------------------------------------------------
    quantized: list[dict] = []
    # Track previous hand assignment for hysteresis
    prev_hand: str = "right"

    for note in notes:
        qn = deepcopy(note)
        original_start: float = note["start"]

        # Snap to nearest grid position
        idx = int(np.argmin(np.abs(grid - original_start)))
        quantized_start: float = round(float(grid[idx]), 4)

        qn["quantized_start"] = quantized_start
        # Preserve original start and duration
        qn["original_start"] = round(original_start, 4)
        qn["original_duration"] = round(note["duration"], 4)

        # Assign measure number and beat position
        measure_idx, beat_pos = _locate_in_measures(
            quantized_start, measures, beats_arr, beats_per_measure,
        )
        qn["measure"] = measure_idx
        qn["beat_position"] = round(beat_pos, 4)

        # Assign hand with hysteresis
        pitch = note.get("pitch", 60)
        hand = _assign_hand(pitch, prev_hand)
        qn["hand"] = hand
        prev_hand = hand

        quantized.append(qn)

    # Sort by quantized start, then pitch
    quantized.sort(key=lambda n: (n["quantized_start"], n["pitch"]))

    logger.info(
        "Quantized %d notes into %d measures (sig=%s)",
        len(quantized), len(measures), time_signature,
    )

    return quantized, measures


# ── Internal helpers ───────────────────────────────────────────────────────

def _beats_per_measure(time_signature: str) -> int:
    """Parse beats-per-measure from a time-signature string."""
    try:
        numerator = int(time_signature.split("/")[0])
        return numerator
    except (ValueError, IndexError):
        return 4


def _build_grid(
    beats: np.ndarray,
    subdivisions: int = 4,
    default_tempo: float = 120.0,
    max_time: float = 300.0,
) -> np.ndarray:
    """Build a quantization grid from beat times.

    Each beat interval is divided into *subdivisions* equal parts
    (4 = 16th notes). If fewer than 2 beats are available, a regular
    grid is synthesized using *default_tempo*.
    """
    if len(beats) < 2:
        beat_interval = 60.0 / default_tempo
        sub_interval = beat_interval / subdivisions
        return np.arange(0.0, max_time + beat_interval, sub_interval, dtype=np.float64)

    grid_points: list[float] = []
    for i in range(len(beats) - 1):
        interval = beats[i + 1] - beats[i]
        sub_interval = interval / subdivisions
        for s in range(subdivisions):
            grid_points.append(float(beats[i] + s * sub_interval))
    # Add the last beat
    grid_points.append(float(beats[-1]))

    # Extend beyond the last beat for trailing notes
    last_interval = beats[-1] - beats[-2]
    sub_interval = last_interval / subdivisions
    for s in range(1, subdivisions + 1):
        grid_points.append(float(beats[-1] + s * sub_interval))

    return np.array(sorted(set(grid_points)), dtype=np.float64)


def _build_measures(
    beats: np.ndarray,
    beats_per_measure: int,
    time_signature: str,
    default_tempo: float = 120.0,
    max_time: float = 300.0,
) -> list[dict]:
    """Group beats into measures. If beats are missing, synthesizes regular measures."""
    if len(beats) < 2:
        beat_interval = 60.0 / default_tempo
        measure_duration = beat_interval * beats_per_measure
        measures: list[dict] = []
        measure_idx = 1
        t = 0.0
        while t < max_time:
            measures.append({
                "index": measure_idx,
                "start": round(t, 4),
                "end": round(t + measure_duration, 4),
                "time_signature": time_signature,
            })
            t += measure_duration
            measure_idx += 1
        return measures

    measures: list[dict] = []
    measure_idx = 1

    for i in range(0, len(beats), beats_per_measure):
        start = float(beats[i])
        end_idx = i + beats_per_measure
        if end_idx < len(beats):
            end = float(beats[end_idx])
        elif i + beats_per_measure - 1 < len(beats):
            # Last partial measure — estimate end from last beat + average interval
            remaining = beats[i:]
            if len(remaining) >= 2:
                avg_interval = float(np.mean(np.diff(remaining)))
            elif len(beats) >= 2:
                avg_interval = float(np.mean(np.diff(beats)))
            else:
                avg_interval = 1.0
            end = float(beats[-1] + avg_interval)
        else:
            if len(beats) >= 2:
                avg_interval = float(np.mean(np.diff(beats)))
            else:
                avg_interval = 1.0
            end = float(beats[-1] + avg_interval)

        measures.append({
            "index": measure_idx,
            "start": round(start, 4),
            "end": round(end, 4),
            "time_signature": time_signature,
        })
        measure_idx += 1

    return measures


def _locate_in_measures(
    time_sec: float,
    measures: list[dict],
    beats: np.ndarray,
    beats_per_measure: int,
) -> tuple[int, float]:
    """Find which measure a time falls into and its beat position."""
    if not measures:
        return 1, 0.0

    # Find the matching measure
    target_measure: dict = measures[-1]
    for m in measures:
        if m["start"] <= time_sec < m["end"]:
            target_measure = m
            break

    measure_idx: int = target_measure["index"]

    # Compute beat position within the measure
    measure_start = target_measure["start"]
    measure_end = target_measure["end"]
    measure_duration = measure_end - measure_start
    if measure_duration > 0:
        fraction = (time_sec - measure_start) / measure_duration
        beat_position = fraction * beats_per_measure
    else:
        beat_position = 0.0

    return measure_idx, beat_position


def _assign_hand(pitch: int, prev_hand: str) -> str:
    """Assign a note to left or right hand with hysteresis.

    Notes clearly below the split point go to the left hand.
    Notes clearly above go to the right hand.
    Notes within the hysteresis zone keep the previous assignment.
    """
    if pitch < _SPLIT_POINT - _HYSTERESIS:
        return "left"
    elif pitch > _SPLIT_POINT + _HYSTERESIS:
        return "right"
    else:
        # In the hysteresis zone — keep previous hand
        return prev_hand
