"""MELODYX — B5: MusicXML / score generation via music21.

Creates a grand-staff piano score with key signature, time signature,
tempo marking, notes split between treble and bass clefs, and optional
chord symbols.
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_musicxml(
    notes: list[dict],
    tempo_bpm: float,
    key_name: str,
    time_signature: str,
    chords: list[dict],
    output_path: str,
) -> str:
    """Generate a MusicXML file from quantized note events.

    Args:
        notes: Quantized note dicts (``pitch``, ``start``/``quantized_start``,
            ``duration``, ``hand``, ``name``).
        tempo_bpm: Tempo in beats per minute.
        key_name: Key signature string, e.g. ``"C major"`` or ``"A minor"``.
        time_signature: Time signature string, e.g. ``"4/4"``.
        chords: Chord dicts from harmony analysis (``label``, ``start``,
            ``end``, ``confidence``).
        output_path: Destination file path for the ``.musicxml`` file.

    Returns:
        The *output_path* on success.

    Raises:
        ImportError: If music21 is not installed.
        ValueError: If the generated XML is invalid.
    """
    try:
        from music21 import (
            chord as m21_chord,
            converter,
            duration as m21_duration,
            harmony,
            instrument,
            key as m21_key,
            metadata,
            meter,
            note as m21_note,
            stream,
            tempo,
        )
    except ImportError as exc:
        raise ImportError(
            "music21 is required for score generation. "
            "Install it with:  pip install 'music21>=9.0,<10.0'"
        ) from exc

    # ---- Create the score --------------------------------------------------
    score = stream.Score()
    score.metadata = metadata.Metadata()
    score.metadata.title = "MELODYX Transcription"

    # ---- Parse key signature -----------------------------------------------
    ks = _parse_key(key_name, m21_key)
    score.insert(0, ks)

    # ---- Parse time signature ----------------------------------------------
    ts_parts = time_signature.split("/")
    ts_numerator = int(ts_parts[0]) if len(ts_parts) >= 1 else 4
    ts_denominator = int(ts_parts[1]) if len(ts_parts) >= 2 else 4
    ts = meter.TimeSignature(f"{ts_numerator}/{ts_denominator}")

    if not tempo_bpm or tempo_bpm <= 0:
        tempo_bpm = 120.0

    # ---- Tempo marking -----------------------------------------------------
    mm = tempo.MetronomeMark(number=tempo_bpm)

    # ---- Create two parts (treble + bass) ----------------------------------
    treble_part = stream.Part()
    treble_part.insert(0, instrument.Piano())
    treble_part.partName = "Right Hand"

    bass_part = stream.Part()
    bass_part.insert(0, instrument.Piano())
    bass_part.partName = "Left Hand"

    # Insert time signature and tempo into both parts
    treble_part.insert(0, ts)
    treble_part.insert(0, mm)
    bass_part.insert(0, meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))

    # ---- Compute beat duration for offset conversion -----------------------
    beat_duration_ql: float = 4.0 / ts_denominator  # quarter-length per beat

    # Expressible musical durations in quarter-lengths
    import numpy as _np
    _EXPRESSIBLE_DURATIONS = _np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])

    # ---- Add notes ---------------------------------------------------------
    for note_dict in notes:
        pitch: int = note_dict["pitch"]
        start: float = note_dict.get("quantized_start", note_dict["start"])
        dur: float = note_dict.get("duration", 0.25)
        hand: str = note_dict.get("hand", "right")

        # Convert seconds to quarter-note offset
        seconds_per_beat: float = 60.0 / tempo_bpm
        raw_offset_ql: float = (start / seconds_per_beat) * beat_duration_ql
        offset_ql: float = round(raw_offset_ql * 4.0) / 4.0

        raw_duration_ql: float = (dur / seconds_per_beat) * beat_duration_ql
        # Snap duration to nearest standard musical note value
        idx = int(_np.argmin(_np.abs(_EXPRESSIBLE_DURATIONS - raw_duration_ql)))
        duration_ql: float = float(_EXPRESSIBLE_DURATIONS[idx])

        n = m21_note.Note(pitch)
        n.quarterLength = duration_ql

        if hand == "left":
            bass_part.insert(offset_ql, n)
        else:
            treble_part.insert(offset_ql, n)

    # ---- Add chord symbols (confidence > 0.6) -----------------------------
    for ch in chords:
        if ch.get("confidence", 0) <= 0.6:
            continue
        label: str = ch["label"]
        ch_start: float = ch["start"]

        seconds_per_beat = 60.0 / tempo_bpm
        offset_ql = round(((ch_start / seconds_per_beat) * beat_duration_ql) * 4.0) / 4.0

        try:
            cs = harmony.ChordSymbol(label)
            treble_part.insert(offset_ql, cs)
        except Exception:
            logger.debug("Could not parse chord symbol '%s', skipping", label)

    # ---- Ensure parts have content and quantize to expressible rhythms ----
    if len(treble_part.notes) == 0:
        treble_part.append(m21_note.Rest(type="whole"))
    if len(bass_part.notes) == 0:
        bass_part.append(m21_note.Rest(type="whole"))

    try:
        treble_part = treble_part.quantize([4], processOffsets=True, processDurations=True)
    except Exception as e:
        logger.warning("Treble quantization warning: %s", e)

    try:
        bass_part = bass_part.quantize([4], processOffsets=True, processDurations=True)
    except Exception as e:
        logger.warning("Bass quantization warning: %s", e)

    # ---- Assemble score ----------------------------------------------------
    score.insert(0, treble_part)
    score.insert(0, bass_part)

    # ---- Export -------------------------------------------------------------
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        score.write("musicxml", fp=output_path)
    except Exception as exc:
        logger.warning("Direct MusicXML export failed (%s), attempting makeMeasures fallback", exc)
        try:
            score = score.makeMeasures()
            score.write("musicxml", fp=output_path)
        except Exception as exc2:
            raise ValueError(f"Could not generate valid MusicXML: {exc2}") from exc2

    # ---- Verify valid XML --------------------------------------------------
    try:
        ET.parse(output_path)
        logger.info("MusicXML written to %s", output_path)
    except ET.ParseError as exc:
        raise ValueError(
            f"Generated MusicXML is not valid XML: {exc}"
        ) from exc

    return output_path


def _parse_key(key_name: str, m21_key_module) -> object:
    """Parse a key name string into a music21 Key object.

    Handles formats like ``"C major"``, ``"F# minor"``, ``"Bb major"``.

    Args:
        key_name: Key name string.
        m21_key_module: The ``music21.key`` module.

    Returns:
        A ``music21.key.Key`` instance.
    """
    parts = key_name.strip().split()
    if len(parts) >= 2:
        tonic = parts[0]
        mode = parts[1].lower()
    elif len(parts) == 1:
        tonic = parts[0]
        mode = "major"
    else:
        tonic = "C"
        mode = "major"

    try:
        return m21_key_module.Key(tonic, mode)
    except Exception:
        logger.warning("Could not parse key '%s', defaulting to C major", key_name)
        return m21_key_module.Key("C", "major")
