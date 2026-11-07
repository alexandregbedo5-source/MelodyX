"""Helpers for validating and exporting edited final MusicXML scores."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from typing import Any, Optional


SCORE_INSTRUMENTS = frozenset({"conductor", "piano", "lead", "bass"})
MAX_MUSICXML_BYTES = 5 * 1024 * 1024


def validate_musicxml(xml_text: Any) -> tuple[bool, str]:
    """Validate an edited MusicXML payload without rewriting its formatting."""
    if not isinstance(xml_text, str) or not xml_text.strip():
        return False, "Une partition MusicXML est requise."

    if len(xml_text.encode("utf-8")) > MAX_MUSICXML_BYTES:
        return False, "La partition dépasse la taille maximale autorisée (5 Mo)."

    # Music21 emits the standard MusicXML DOCTYPE. Keep it for compatibility,
    # but reject entity declarations to avoid entity expansion in user content.
    if re.search(r"<!\s*ENTITY\b", xml_text, flags=re.IGNORECASE):
        return False, "Les déclarations d’entités XML ne sont pas autorisées."

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False, "Le document MusicXML est invalide."

    root_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
    if root_name not in {"score-partwise", "score-timewise"}:
        return False, "Le document doit contenir une partition MusicXML."

    parts = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "part"]
    measures = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "measure"]
    if not parts or not measures:
        return False, "La partition doit contenir au moins une partie et une mesure."

    return True, ""


def musicxml_to_analysis_result(
    xml_text: str,
    original_result: Optional[dict[str, Any]],
    instrument: str,
) -> dict[str, Any]:
    """Translate the edited score to the event shape used by MELODYX PDF export."""
    from music21 import chord as m21_chord
    from music21 import converter
    from music21 import key as m21_key
    from music21 import meter as m21_meter
    from music21 import note as m21_note
    from music21 import tempo as m21_tempo

    parsed_score = converter.parseData(xml_text, format="musicxml")
    result = deepcopy(original_result or {})
    music = deepcopy(result.get("music", {}))
    events: list[dict[str, Any]] = []
    measure_numbers: set[int] = set()
    part_count = 0

    for part in parsed_score.parts:
        part_count += 1
        measures = list(part.getElementsByClass("Measure"))
        for fallback_number, measure in enumerate(measures, start=1):
            try:
                measure_number = int(measure.number)
            except (TypeError, ValueError):
                measure_number = fallback_number
            measure_number = max(1, measure_number)
            measure_numbers.add(measure_number)

            for event in measure.notes:
                event_offset = float(event.offset)
                duration = float(event.duration.quarterLength)
                if isinstance(event, m21_chord.Chord):
                    pitches = event.pitches
                elif isinstance(event, m21_note.Note):
                    pitches = [event.pitch]
                else:
                    continue

                for pitch in pitches:
                    midi_pitch = int(pitch.midi)
                    events.append({
                        "pitch": midi_pitch,
                        "measure": measure_number,
                        "beat_position": event_offset,
                        "duration": duration,
                        "hand": "left" if instrument == "bass" or (instrument == "piano" and midi_pitch < 57) else "right",
                    })

    time_signature = None
    key_name = None
    tempo_value = None
    for element in parsed_score.recurse():
        if time_signature is None and isinstance(element, m21_meter.TimeSignature):
            time_signature = element.ratioString
        elif key_name is None and isinstance(element, m21_key.KeySignature):
            try:
                key_name = element.asKey().name
            except Exception:
                pass
        elif tempo_value is None and isinstance(element, m21_tempo.MetronomeMark):
            tempo_value = element.number

    bar_length = 4.0
    if time_signature:
        try:
            numerator, denominator = (int(value) for value in time_signature.split("/", 1))
            bar_length = numerator * 4.0 / denominator
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    total_measures = max(measure_numbers, default=1)
    original_tempo = music.get("tempo_bpm", {})
    original_tempo = original_tempo.get("value", 120) if isinstance(original_tempo, dict) else original_tempo
    original_key = music.get("key", {})
    original_key = original_key.get("value", "C major") if isinstance(original_key, dict) else original_key
    original_time = music.get("time_signature", {})
    original_time = original_time.get("value", "4/4") if isinstance(original_time, dict) else original_time

    music["notes"] = events
    music["measures"] = [
        {"index": number, "start": (number - 1) * bar_length, "end": number * bar_length}
        for number in range(1, total_measures + 1)
    ]
    # The analysis-time chord labels do not necessarily match notes edited in
    # the final score, so omit them from the regenerated PDF rather than show
    # stale harmony information.
    music["chords"] = []
    music["tempo_bpm"] = {"value": tempo_value or original_tempo or 120}
    music["key"] = {"value": key_name or original_key or "C major"}
    music["time_signature"] = {"value": time_signature or original_time or "4/4"}
    result["music"] = music
    result.setdefault("audio", {})
    result["score_instrument"] = instrument
    result["score_part_count"] = part_count
    return result


def write_musicxml_midi(xml_text: str, output_path: str) -> str:
    """Render the edited final score to MIDI using the existing music21 stack."""
    from music21 import converter

    score = converter.parseData(xml_text, format="musicxml")
    return str(score.write("midi", fp=output_path))
