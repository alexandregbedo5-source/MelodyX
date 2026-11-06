"""MELODYX — Unit tests for PDF Sheet Music Generator."""

import os
import tempfile
import pymupdf
import pytest
from app.services.pdf_generator import generate_sheet_music_pdf, pitch_to_diatonic


def test_pitch_to_diatonic():
    # C4 = MIDI 60 -> octave 4, step 0 -> 4 * 7 + 0 = 28
    step, is_acc = pitch_to_diatonic(60)
    assert step == 28
    assert not is_acc

    # C#4 = MIDI 61 -> diatonic step 28, is_acc = True
    step, is_acc = pitch_to_diatonic(61)
    assert step == 28
    assert is_acc

    # E4 = MIDI 64 -> octave 4, step 2 -> 30
    step, is_acc = pitch_to_diatonic(64)
    assert step == 30
    assert not is_acc


def test_generate_sheet_music_pdf_multipage():
    sample_data = {
        "audio": {"filename": "concerto_test.wav"},
        "music": {
            "tempo_bpm": {"value": 132.0},
            "key": {"value": "E major"},
            "time_signature": {"value": "4/4"},
            "chords": [
                {"label": "E", "start": 0.0, "end": 2.0},
                {"label": "G#m", "start": 2.0, "end": 4.0},
                {"label": "A", "start": 4.0, "end": 6.0},
                {"label": "B", "start": 6.0, "end": 8.0},
            ],
            "measures": [
                {"index": 1, "start": 0.0, "end": 2.0},
                {"index": 2, "start": 2.0, "end": 4.0},
                {"index": 3, "start": 4.0, "end": 6.0},
                {"index": 4, "start": 6.0, "end": 8.0},
                {"index": 5, "start": 8.0, "end": 10.0},
            ],
            "notes": [
                {"pitch": 64, "name": "E4", "start": 0.0, "duration": 0.5, "measure": 1, "beat_position": 0.0, "hand": "right"},
                {"pitch": 68, "name": "G#4", "start": 0.5, "duration": 0.5, "measure": 1, "beat_position": 1.0, "hand": "right"},
                {"pitch": 40, "name": "E2", "start": 0.0, "duration": 1.0, "measure": 1, "beat_position": 0.0, "hand": "left"},
                {"pitch": 47, "name": "B2", "start": 1.0, "duration": 1.0, "measure": 1, "beat_position": 2.0, "hand": "left"},
            ],
        },
    }

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pdf_path = tmp.name

    try:
        res_path = generate_sheet_music_pdf(sample_data, pdf_path, title="Test Concerto")
        assert os.path.isfile(res_path)
        assert os.path.getsize(res_path) > 2000

        # Validate with PyMuPDF
        doc = pymupdf.open(res_path)
        # Should have at least score page + conductor guide page
        assert doc.page_count >= 2
        p1_text = doc.load_page(0).get_text()
        assert "Test Concerto" in p1_text
        assert "E major" in p1_text
        assert "132" in p1_text

        guide_text = doc.load_page(doc.page_count - 1).get_text()
        assert "CONDUCTEUR" in guide_text
        doc.close()
    finally:
        if os.path.isfile(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass
