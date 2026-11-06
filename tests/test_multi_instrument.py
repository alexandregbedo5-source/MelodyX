"""Tests for multi-instrument partition generation, dispatching, and exports."""

import os
import tempfile
import xml.etree.ElementTree as ET
import pytest
import pymupdf

from app.services.stem_separator import dispatch_notes_to_instruments, AVAILABLE_INSTRUMENTS
from app.services.score_generator import generate_musicxml, generate_multi_instrument_scores
from app.services.pdf_generator import generate_sheet_music_pdf, generate_multi_instrument_pdfs


@pytest.fixture
def sample_piece_data():
    return {
        "audio": {"filename": "symphonic_theme.wav"},
        "music": {
            "tempo_bpm": {"value": 110.0},
            "key": {"value": "D major"},
            "time_signature": {"value": "4/4"},
            "chords": [
                {"label": "D", "start": 0.0, "end": 2.0},
                {"label": "G", "start": 2.0, "end": 4.0},
                {"label": "A", "start": 4.0, "end": 6.0},
                {"label": "Bm", "start": 6.0, "end": 8.0},
            ],
            "measures": [
                {"index": 1, "start": 0.0, "end": 2.0},
                {"index": 2, "start": 2.0, "end": 4.0},
                {"index": 3, "start": 4.0, "end": 6.0},
                {"index": 4, "start": 6.0, "end": 8.0},
            ],
            "notes": [
                # Lead notes (treble register)
                {"pitch": 74, "name": "D5", "start": 0.0, "duration": 0.5, "measure": 1, "beat_position": 0.0, "hand": "right"},
                {"pitch": 76, "name": "E5", "start": 0.5, "duration": 0.5, "measure": 1, "beat_position": 1.0, "hand": "right"},
                {"pitch": 78, "name": "F#5", "start": 1.0, "duration": 0.5, "measure": 1, "beat_position": 2.0, "hand": "right"},
                {"pitch": 74, "name": "D5", "start": 2.0, "duration": 1.0, "measure": 2, "beat_position": 0.0, "hand": "right"},
                # Bass notes (bass register)
                {"pitch": 38, "name": "D2", "start": 0.0, "duration": 1.0, "measure": 1, "beat_position": 0.0, "hand": "left"},
                {"pitch": 45, "name": "A2", "start": 1.0, "duration": 1.0, "measure": 1, "beat_position": 2.0, "hand": "left"},
                {"pitch": 43, "name": "G2", "start": 2.0, "duration": 1.0, "measure": 2, "beat_position": 0.0, "hand": "left"},
                {"pitch": 45, "name": "A2", "start": 3.0, "duration": 1.0, "measure": 2, "beat_position": 2.0, "hand": "left"},
            ],
        },
    }


def test_available_instruments_list():
    assert len(AVAILABLE_INSTRUMENTS) >= 4
    inst_ids = [inst["id"] for inst in AVAILABLE_INSTRUMENTS]
    assert "conductor" in inst_ids
    assert "piano" in inst_ids
    assert "lead" in inst_ids
    assert "bass" in inst_ids


def test_dispatch_notes_to_instruments(sample_piece_data):
    notes = sample_piece_data["music"]["notes"]
    dispatched = dispatch_notes_to_instruments(notes)

    assert "conductor" in dispatched
    assert "piano" in dispatched
    assert "lead" in dispatched
    assert "bass" in dispatched

    assert len(dispatched["conductor"]) == len(notes)
    assert len(dispatched["piano"]) == len(notes)

    # Lead should only contain high register notes (>= 55)
    for n in dispatched["lead"]:
        assert n["pitch"] >= 55 or n.get("hand") == "right"

    # Bass should only contain low register notes (< 55 or hand == left)
    for n in dispatched["bass"]:
        assert n["pitch"] < 55 or n.get("hand") == "left"


def test_generate_multi_instrument_scores(sample_piece_data):
    with tempfile.TemporaryDirectory() as tmp_dir:
        music = sample_piece_data["music"]
        res = generate_multi_instrument_scores(
            music["notes"],
            music["tempo_bpm"]["value"],
            music["key"]["value"],
            music["time_signature"]["value"],
            music["chords"],
            tmp_dir,
            "test_piece",
            "Theme Symphonique",
        )

        for inst in ("conductor", "piano", "lead", "bass"):
            assert inst in res
            fpath = res[inst]
            assert os.path.isfile(fpath)
            # Verify valid XML
            tree = ET.parse(fpath)
            root = tree.getroot()
            assert root.tag == "score-partwise"


def test_generate_multi_instrument_pdfs(sample_piece_data):
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_res = generate_multi_instrument_pdfs(
            sample_piece_data,
            tmp_dir,
            "test_piece",
            "Theme Symphonique",
        )

        for inst in ("conductor", "piano", "lead", "bass"):
            assert inst in pdf_res
            pdf_path = pdf_res[inst]
            assert os.path.isfile(pdf_path)
            assert os.path.getsize(pdf_path) > 1000

            doc = pymupdf.open(pdf_path)
            assert doc.page_count >= 1
            # Conductor has the lead sheet guide page as well
            if inst == "conductor":
                assert doc.page_count >= 2
            doc.close()
