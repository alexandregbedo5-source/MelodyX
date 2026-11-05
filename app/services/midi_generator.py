"""MELODYX — B5: MIDI file generation.

Creates a standard MIDI file from quantized note events using PrettyMIDI,
splitting notes between right-hand and left-hand tracks.
"""

import logging
from pathlib import Path

import pretty_midi

logger = logging.getLogger(__name__)

# General MIDI program 0 = Acoustic Grand Piano
_PIANO_PROGRAM: int = 0


def generate_midi(
    notes: list[dict],
    tempo_bpm: float,
    output_path: str,
) -> str:
    """Generate a MIDI file from quantized note events.

    Args:
        notes: Quantized note dicts, each containing at least ``pitch``,
            ``start`` (or ``quantized_start``), ``duration``, and ``hand``.
        tempo_bpm: Tempo in beats per minute.
        output_path: Destination file path for the ``.mid`` file.

    Returns:
        The *output_path* (same as input) on success.

    Raises:
        ValueError: If the generated file cannot be read back.
    """
    if not tempo_bpm or tempo_bpm <= 0:
        tempo_bpm = 120.0

    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo_bpm)

    right_track = pretty_midi.Instrument(
        program=_PIANO_PROGRAM,
        is_drum=False,
        name="Right Hand",
    )
    left_track = pretty_midi.Instrument(
        program=_PIANO_PROGRAM,
        is_drum=False,
        name="Left Hand",
    )

    for note_dict in notes:
        pitch: int = note_dict["pitch"]
        # Prefer quantized start if available
        start: float = note_dict.get("quantized_start", note_dict["start"])
        duration: float = note_dict.get("duration", 0.25)
        end: float = start + duration
        velocity: int = _amplitude_to_velocity(note_dict.get("amplitude", 0.8))

        midi_note = pretty_midi.Note(
            velocity=velocity,
            pitch=pitch,
            start=start,
            end=end,
        )

        hand: str = note_dict.get("hand", "right")
        if hand == "left":
            left_track.notes.append(midi_note)
        else:
            right_track.notes.append(midi_note)

    midi.instruments.append(right_track)
    midi.instruments.append(left_track)

    # ---- Write to disk -----------------------------------------------------
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    midi.write(output_path)

    # ---- Verify readability ------------------------------------------------
    try:
        verification = pretty_midi.PrettyMIDI(output_path)
        total_notes = sum(len(inst.notes) for inst in verification.instruments)
        logger.info(
            "MIDI written to %s — %d notes, tempo=%.1f bpm",
            output_path, total_notes, tempo_bpm,
        )
    except Exception as exc:
        raise ValueError(
            f"Generated MIDI file is not readable: {exc}"
        ) from exc

    return output_path


def _amplitude_to_velocity(amplitude: float) -> int:
    """Map a 0.0–1.0 amplitude to a MIDI velocity (1–127).

    Args:
        amplitude: Normalised amplitude value.

    Returns:
        MIDI velocity clamped to [1, 127].
    """
    velocity = int(round(amplitude * 127))
    return max(1, min(127, velocity))
