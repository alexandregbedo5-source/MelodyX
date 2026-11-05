"""MELODYX — B4: Audio-to-note transcription via basic-pitch.

Converts a WAV file into a list of note events using Spotify's
basic-pitch model, with confidence filtering and unique IDs.
"""

import logging
import secrets
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Minimum confidence to keep a note (configurable at call site)
_DEFAULT_CONFIDENCE_THRESHOLD: float = 0.5

# MIDI note names cache
_NOTE_NAMES: list[str] = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
]


def _midi_to_note_name(midi_number: int) -> str:
    """Convert a MIDI pitch number to a human-readable note name.

    Uses pretty_midi when available, otherwise falls back to a simple
    formula.

    Args:
        midi_number: MIDI note number (0–127).

    Returns:
        Note name such as ``"C4"`` or ``"A#3"``.
    """
    try:
        import pretty_midi
        return pretty_midi.note_number_to_name(midi_number)
    except Exception:
        octave = (midi_number // 12) - 1
        note = _NOTE_NAMES[midi_number % 12]
        return f"{note}{octave}"


def transcribe_audio(
    wav_path: str,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[dict]:
    """Transcribe audio to a list of note events.

    Args:
        wav_path: Path to a mono WAV file (22 050 Hz expected).
        confidence_threshold: Discard notes below this confidence.

    Returns:
        A list of note dicts, each containing ``id``, ``pitch``, ``name``,
        ``start``, ``duration``, ``amplitude``, ``confidence``, ``source``,
        and ``estimated``.

    Raises:
        ImportError: If basic-pitch is not installed.
    """
    try:
        from basic_pitch.inference import predict
    except ImportError as exc:
        raise ImportError(
            "basic-pitch is required for transcription. "
            "Install it with:  pip install basic-pitch"
        ) from exc

    logger.info("Transcribing %s (threshold=%.2f)", wav_path, confidence_threshold)

    # basic_pitch.inference.predict returns:
    #   model_output, midi_data, note_events
    # note_events is a list of tuples:
    #   (start_time, end_time, pitch, amplitude, [confidence])
    model_output, midi_data, note_events = predict(wav_path)

    notes: list[dict] = []
    for event in note_events:
        start_time: float = float(event[0])
        end_time: float = float(event[1])
        pitch: int = int(event[2])
        amplitude: float = float(event[3])

        # In basic-pitch, event[3] is amplitude (which serves as confidence/velocity).
        # event[4] is a list of pitch bends.
        if len(event) >= 6 and isinstance(event[5], (int, float)):
            confidence: float = float(event[5])
        elif isinstance(amplitude, (int, float)):
            confidence = float(amplitude)
        else:
            confidence = 0.8

        if confidence < confidence_threshold:
            continue

        duration: float = end_time - start_time
        if duration <= 0:
            continue

        note_id = f"n_{secrets.token_hex(4)}"
        note_name = _midi_to_note_name(pitch)

        notes.append({
            "id": note_id,
            "pitch": pitch,
            "name": note_name,
            "start": round(start_time, 4),
            "duration": round(duration, 4),
            "amplitude": round(amplitude, 4),
            "confidence": round(confidence, 4),
            "source": "basic_pitch",
            "estimated": True,
        })

    # Sort by start time, then pitch (ascending)
    notes.sort(key=lambda n: (n["start"], n["pitch"]))

    logger.info(
        "Transcription complete: %d notes kept (of %d raw events)",
        len(notes), len(note_events),
    )

    return notes
