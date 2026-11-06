"""MELODYX — Multi-Instrument MusicXML / Score Generation via music21.

Generates professional, publication-grade MusicXML scores for individual instruments
(Piano, Basse, Chant / Lead) as well as a full Orchestral Conductor score
(Conducteur Général) uniting all parts.
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_EXPRESSIBLE_DURATIONS = np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])


def generate_musicxml(
    notes: list[dict],
    tempo_bpm: float,
    key_name: str,
    time_signature: str,
    chords: list[dict],
    output_path: str,
    instrument_type: str = "piano",
    title: Optional[str] = None,
) -> str:
    """Generate a MusicXML file for a specific instrument or full conductor score.

    Args:
        notes: Quantized note dicts (``pitch``, ``start``/``quantized_start``,
            ``duration``, ``hand``, ``name``).
        tempo_bpm: Tempo in beats per minute.
        key_name: Key signature string, e.g. ``"C major"`` or ``"A minor"``.
        time_signature: Time signature string, e.g. ``"4/4"``.
        chords: Chord dicts from harmony analysis.
        output_path: Destination file path for the ``.musicxml`` file.
        instrument_type: One of ``"conductor"``, ``"piano"``, ``"lead"``, ``"bass"``.
        title: Score title (optional).

    Returns:
        The *output_path* on success.
    """
    try:
        from music21 import (
            chord as m21_chord,
            clef as m21_clef,
            duration as m21_duration,
            instrument as m21_inst,
            key as m21_key,
            metadata as m21_meta,
            meter as m21_meter,
            note as m21_note,
            stream as m21_stream,
            tempo as m21_tempo,
        )
    except ImportError as exc:
        raise ImportError(
            "music21 is required for score generation. "
            "Install it with:  pip install 'music21>=9.0,<10.0'"
        ) from exc

    if not tempo_bpm or tempo_bpm <= 0:
        tempo_bpm = 120.0

    # Parse time signature
    ts_parts = time_signature.split("/")
    ts_numerator = int(ts_parts[0]) if len(ts_parts) >= 1 else 4
    ts_denominator = int(ts_parts[1]) if len(ts_parts) >= 2 else 4
    beat_duration_ql: float = 4.0 / ts_denominator
    seconds_per_beat: float = 60.0 / tempo_bpm

    # Helper: quantize part cleanly
    def _finalize_part(part):
        if len(part.notes) == 0:
            part.append(m21_note.Rest(type="whole"))
        try:
            return part.quantize([4], processOffsets=True, processDurations=True)
        except Exception as e:
            logger.warning("Quantization warning on part %s: %s", getattr(part, 'partName', ''), e)
            return part

    # Helper: cluster simultaneous notes into clean chords & deduplicate
    def _populate_part(part, note_list):
        if not note_list:
            part.append(m21_note.Rest(type="whole"))
            return _finalize_part(part)

        # 1. Filter micro-glitches (< 0.08s) or low confidence
        filtered = [
            n for n in note_list
            if n.get("duration", 0.25) >= 0.08 and n.get("confidence", 1.0) >= 0.20
        ]
        if not filtered:
            filtered = note_list

        # 2. Group notes by quantized beat offset (16th note grid = 0.25 QL)
        from collections import defaultdict
        groups = defaultdict(list)
        for nd in filtered:
            start = nd.get("quantized_start", nd.get("start", 0.0))
            raw_offset_ql = (start / seconds_per_beat) * beat_duration_ql
            offset_ql = round(raw_offset_ql * 4.0) / 4.0
            groups[offset_ql].append(nd)

        # 3. For each beat offset, build clean Note or unified Chord
        for offset_ql in sorted(groups.keys()):
            nds = groups[offset_ql]
            pitches = []
            durations = []
            for n in nds:
                p = int(round(n.get("pitch", 60)))
                if p not in pitches:
                    pitches.append(p)
                    dur = n.get("duration", 0.25)
                    raw_dur = (dur / seconds_per_beat) * beat_duration_ql
                    durations.append(raw_dur)

            if not pitches:
                continue

            # Expressible duration (capped to prevent overlapping whole-measure ties)
            med_dur = float(np.median(durations)) if durations else 0.5
            idx = int(np.argmin(np.abs(_EXPRESSIBLE_DURATIONS - med_dur)))
            final_dur = min(float(_EXPRESSIBLE_DURATIONS[idx]), 4.0)

            # Eliminate micro-second pitch collisions (e.g. vibrato / flutter minor 2nds)
            pitches.sort()
            clean_pitches = []
            for p in pitches:
                if clean_pitches and p - clean_pitches[-1] <= 1:
                    # Adjacent semitone collision from audio vibrato: keep the higher prominent pitch
                    clean_pitches[-1] = p
                else:
                    clean_pitches.append(p)

            # Cap max 4 notes per chord for engraving clarity
            if len(clean_pitches) > 4:
                clean_pitches = clean_pitches[-4:]

            if len(clean_pitches) == 1:
                el = m21_note.Note(clean_pitches[0])
            else:
                el = m21_chord.Chord(clean_pitches)

            el.quarterLength = final_dur
            part.insert(offset_ql, el)

        return _finalize_part(part)

    score = m21_stream.Score()
    score.metadata = m21_meta.Metadata()

    ks = _parse_key(key_name, m21_key)
    mm = m21_tempo.MetronomeMark(number=tempo_bpm)

    if instrument_type == "bass":
        score.metadata.title = title or "Partition Basse"
        bass_part = m21_stream.Part()
        bass_part.partName = "Basse"
        bass_part.insert(0, m21_inst.ElectricBass())
        bass_part.insert(0, m21_clef.BassClef())
        bass_part.insert(0, m21_meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))
        bass_part.insert(0, mm)
        bass_part.insert(0, ks)

        bass_part = _populate_part(bass_part, notes)
        score.insert(0, bass_part)

    elif instrument_type == "lead":
        score.metadata.title = title or "Partition Chant / Lead"
        lead_part = m21_stream.Part()
        lead_part.partName = "Chant / Lead"
        lead_part.insert(0, m21_inst.Vocalist())
        lead_part.insert(0, m21_clef.TrebleClef())
        lead_part.insert(0, m21_meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))
        lead_part.insert(0, mm)
        lead_part.insert(0, ks)

        lead_part = _populate_part(lead_part, notes)
        score.insert(0, lead_part)

    elif instrument_type == "conductor":
        score.metadata.title = title or "Conducteur Général d'Orchestre"
        lead_part = m21_stream.Part()
        lead_part.partName = "Chant / Lead"
        lead_part.insert(0, m21_inst.Vocalist())
        lead_part.insert(0, m21_clef.TrebleClef())
        lead_part.insert(0, m21_meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))
        lead_part.insert(0, mm)
        lead_part.insert(0, ks)

        piano_part = m21_stream.Part()
        piano_part.partName = "Piano"
        piano_part.insert(0, m21_inst.Piano())
        piano_part.insert(0, m21_clef.TrebleClef())
        piano_part.insert(0, m21_meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))
        piano_part.insert(0, ks)

        bass_part = m21_stream.Part()
        bass_part.partName = "Basse"
        bass_part.insert(0, m21_inst.ElectricBass())
        bass_part.insert(0, m21_clef.BassClef())
        bass_part.insert(0, m21_meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))
        bass_part.insert(0, ks)

        lead_notes = []
        piano_notes = []
        bass_notes = []
        for nd in notes:
            p = nd.get("pitch", 60)
            if p >= 60:
                lead_notes.append(nd)
                piano_notes.append(nd)
            elif p >= 50:
                piano_notes.append(nd)
            else:
                bass_notes.append(nd)
                piano_notes.append(nd)

        lead_part = _populate_part(lead_part, lead_notes)
        piano_part = _populate_part(piano_part, piano_notes)
        bass_part = _populate_part(bass_part, bass_notes)

        score.insert(0, lead_part)
        score.insert(0, piano_part)
        score.insert(0, bass_part)

    else:
        # Default: Piano Grand Staff
        score.metadata.title = title or "Partition Piano"
        treble_part = m21_stream.Part()
        treble_part.partName = "Piano (Main Droite)"
        treble_part.insert(0, m21_inst.Piano())
        treble_part.insert(0, m21_clef.TrebleClef())
        treble_part.insert(0, m21_meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))
        treble_part.insert(0, mm)
        treble_part.insert(0, ks)

        bass_part = m21_stream.Part()
        bass_part.partName = "Piano (Main Gauche)"
        bass_part.insert(0, m21_inst.Piano())
        bass_part.insert(0, m21_clef.BassClef())
        bass_part.insert(0, m21_meter.TimeSignature(f"{ts_numerator}/{ts_denominator}"))
        bass_part.insert(0, ks)

        treble_notes = []
        bass_notes = []
        for nd in notes:
            hand = nd.get("hand", "right")
            if hand == "left" or nd.get("pitch", 60) < 60:
                bass_notes.append(nd)
            else:
                treble_notes.append(nd)

        treble_part = _populate_part(treble_part, treble_notes)
        bass_part = _populate_part(bass_part, bass_notes)

        score.insert(0, treble_part)
        score.insert(0, bass_part)

    # Export to disk
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        score.write("musicxml", fp=output_path)
    except Exception as exc:
        logger.warning("Direct MusicXML export failed (%s), attempting makeMeasures", exc)
        try:
            score = score.makeMeasures()
            score.write("musicxml", fp=output_path)
        except Exception as exc2:
            raise ValueError(f"Could not generate valid MusicXML: {exc2}") from exc2

    # Verify valid XML
    try:
        ET.parse(output_path)
        logger.info("MusicXML [%s] written to %s", instrument_type, output_path)
    except ET.ParseError as exc:
        raise ValueError(f"Generated MusicXML is not valid XML: {exc}") from exc

    return output_path


def generate_multi_instrument_scores(
    notes: list[dict],
    tempo_bpm: float,
    key_name: str,
    time_signature: str,
    chords: list[dict],
    output_dir: str,
    analysis_id: str,
    title_prefix: str = "MELODYX",
) -> dict[str, str]:
    """Generate separate MusicXML scores for all instruments plus conductor score.

    Returns:
        Dict mapping instrument IDs (``conductor``, ``piano``, ``lead``, ``bass``)
        to their respective generated MusicXML file paths.
    """
    from app.services.stem_separator import dispatch_notes_to_instruments

    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)

    dispatched = dispatch_notes_to_instruments(notes)
    results: dict[str, str] = {}

    # 1. Conductor (full score)
    conductor_path = str(out_p / f"{analysis_id}.musicxml")
    generate_musicxml(
        dispatched["conductor"],
        tempo_bpm,
        key_name,
        time_signature,
        chords,
        conductor_path,
        instrument_type="conductor",
        title=f"{title_prefix} — Conducteur Général",
    )
    results["conductor"] = conductor_path

    # 2. Piano
    piano_path = str(out_p / f"{analysis_id}_piano.musicxml")
    generate_musicxml(
        dispatched["piano"],
        tempo_bpm,
        key_name,
        time_signature,
        chords,
        piano_path,
        instrument_type="piano",
        title=f"{title_prefix} — Partition Piano",
    )
    results["piano"] = piano_path

    # 3. Lead / Chant
    lead_path = str(out_p / f"{analysis_id}_lead.musicxml")
    generate_musicxml(
        dispatched["lead"],
        tempo_bpm,
        key_name,
        time_signature,
        chords,
        lead_path,
        instrument_type="lead",
        title=f"{title_prefix} — Chant / Lead",
    )
    results["lead"] = lead_path

    # 4. Bass
    bass_path = str(out_p / f"{analysis_id}_bass.musicxml")
    generate_musicxml(
        dispatched["bass"],
        tempo_bpm,
        key_name,
        time_signature,
        chords,
        bass_path,
        instrument_type="bass",
        title=f"{title_prefix} — Partition Basse",
    )
    results["bass"] = bass_path

    return results


def _parse_key(key_name: str, m21_key_module) -> object:
    """Parse a key name string into a music21 Key object."""
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
