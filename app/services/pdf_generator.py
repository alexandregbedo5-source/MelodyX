"""MELODYX — High-Fidelity Classical Sheet Music & Conductor PDF Generator.

Produces vector-engraved grand staff piano scores matching professional opera
and classical publication standards (comparable to Henle, Bärenreiter, or Durand editions).
Includes treble and bass staves, brace, key signatures, meter, measure numbers,
chord symbols, noteheads, stems, eighth-note beams, rehearsal marks ([A], [B]...),
and an executive conductor guide with harmonic grid.
"""

import math
import os
import logging
from typing import Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# Page geometry (A4 portrait: 595.28 x 841.89 points)
PAGE_W, PAGE_H = A4
MARGIN_LEFT = 50.0
MARGIN_RIGHT = PAGE_W - 40.0
USABLE_WIDTH = MARGIN_RIGHT - MARGIN_LEFT

LINE_SP = 6.0          # Distance between adjacent staff lines (6 pt)
STAFF_H = 4 * LINE_SP  # 24 pt (5 lines = 4 spaces)
INTER_STAFF_GAP = 38.0 # Gap between treble and bass staff
SYSTEM_H = STAFF_H + INTER_STAFF_GAP + STAFF_H  # 86 pt
SYSTEM_GAP = 42.0      # Vertical spacing between systems

# Diatonic mappings for MIDI pitches
# Pitch class: C:0, C#:0, D:1, D#:1, E:2, F:3, F#:3, G:4, G#:4, A:5, A#:5, B:6
SEMITONE_TO_DIATONIC = [0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6]
IS_CHROMATIC_SHARP = [False, True, False, True, False, False, True, False, True, False, True, False]

TREBLE_BOTTOM_STEP = 4 * 7 + 2  # E4 (MIDI 64) = diatonic step 30
BASS_BOTTOM_STEP = 2 * 7 + 4    # G2 (MIDI 43) = diatonic step 18

# Key signatures table: (number_of_accidentals, is_flat_bool)
KEY_SIGNATURES = {
    # Sharps
    "C major": (0, False), "A minor": (0, False),
    "G major": (1, False), "E minor": (1, False),
    "D major": (2, False), "B minor": (2, False),
    "A major": (3, False), "F# minor": (3, False),
    "E major": (4, False), "C# minor": (4, False),
    "B major": (5, False), "G# minor": (5, False),
    "F# major": (6, False), "D# minor": (6, False),
    "C# major": (7, False), "A# minor": (7, False),
    # Flats
    "F major": (1, True), "D minor": (1, True),
    "Bb major": (2, True), "G minor": (2, True),
    "Eb major": (3, True), "C minor": (3, True),
    "Ab major": (4, True), "F minor": (4, True),
    "Db major": (5, True), "Bb minor": (5, True),
    "Gb major": (6, True), "Eb minor": (6, True),
    "Cb major": (7, True), "Ab minor": (7, True),
}


def pitch_to_diatonic(pitch: int) -> tuple[int, bool]:
    """Convert MIDI note number to (absolute_diatonic_step, is_accidental)."""
    octave = (pitch // 12) - 1
    semitone = pitch % 12
    diatonic = SEMITONE_TO_DIATONIC[semitone]
    abs_step = octave * 7 + diatonic
    is_acc = IS_CHROMATIC_SHARP[semitone]
    return abs_step, is_acc


def draw_brace(c: canvas.Canvas, x: float, y_top: float, y_bottom: float):
    """Draw classical curly piano brace joining treble and bass staves."""
    h = y_top - y_bottom
    mid = (y_top + y_bottom) / 2.0
    p = c.beginPath()
    p.moveTo(x, y_top)
    p.curveTo(x - 6, y_top - h * 0.15, x - 6, mid + h * 0.12, x - 12, mid)
    p.curveTo(x - 6, mid - h * 0.12, x - 6, y_bottom + h * 0.15, x, y_bottom)
    c.setLineWidth(1.8)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.drawPath(p, stroke=1, fill=0)


def draw_treble_clef(c: canvas.Canvas, x: float, y_bot: float, sp: float):
    """Draw vector G-clef (𝄞) centered on line 1 (G4)."""
    g_y = y_bot + sp
    p = c.beginPath()
    p.moveTo(x + 4, y_bot - sp * 0.6)
    p.curveTo(x - 2, y_bot - sp * 0.7, x - 5, y_bot, x, g_y)
    p.curveTo(x + 6, g_y + sp * 0.5, x + 6, g_y + sp * 1.5, x, g_y + sp * 2.5)
    p.curveTo(x - 6, g_y + sp * 3.5, x - 3, g_y + sp * 4.2, x, g_y + sp * 4.5)
    p.curveTo(x + 3.5, g_y + sp * 4.5, x + 3.5, g_y + sp * 3.5, x, g_y + sp * 2.0)
    p.curveTo(x - 6, g_y + sp * 1.0, x - 6, g_y - sp * 0.2, x - 1, g_y - sp * 0.5)
    p.curveTo(x + 4, g_y - sp * 0.8, x + 5, g_y + sp * 0.2, x + 2, g_y + sp * 0.8)
    c.setLineWidth(1.3)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(1.0)
    c.line(x, g_y + sp * 4.5, x, y_bot - sp * 1.2)
    c.circle(x - 1.5, y_bot - sp * 1.2, 1.8, stroke=0, fill=1)


def draw_bass_clef(c: canvas.Canvas, x: float, y_bot: float, sp: float):
    """Draw vector F-clef (𝄢) anchored on line 3 (F3)."""
    f_y = y_bot + 3 * sp
    c.circle(x, f_y, 2.3, stroke=0, fill=1)
    p = c.beginPath()
    p.moveTo(x, f_y)
    p.curveTo(x + 5, f_y + sp * 0.9, x + 9, f_y + sp * 0.4, x + 9, f_y - sp * 0.5)
    p.curveTo(x + 9, f_y - sp * 1.6, x + 3, f_y - sp * 2.3, x, f_y - sp * 2.6)
    c.setLineWidth(1.4)
    c.drawPath(p, stroke=1, fill=0)
    c.circle(x + 13, f_y + sp * 0.5, 1.3, stroke=0, fill=1)
    c.circle(x + 13, f_y - sp * 0.5, 1.3, stroke=0, fill=1)


def draw_key_signature(
    c: canvas.Canvas,
    key_name: str,
    x: float,
    treble_y: float,
    bass_y: float,
    sp: float,
) -> float:
    """Draw key signature accidentals and return the horizontal width consumed."""
    key_clean = key_name.strip()
    # Normalize key lookup
    num_acc, is_flat = KEY_SIGNATURES.get(key_clean, (0, False))
    if num_acc == 0:
        # Fallback partial matching
        for k, val in KEY_SIGNATURES.items():
            if k.lower() in key_clean.lower():
                num_acc, is_flat = val
                break

    if num_acc == 0:
        return 0.0

    # Sharp line positions (step heights from staff bottom)
    sharps_treble = [4.0, 2.5, 4.5, 3.0, 1.5, 3.5, 2.0]
    sharps_bass = [3.0, 1.5, 3.5, 2.0, 0.5, 2.5, 1.0]

    # Flat line positions
    flats_treble = [2.0, 3.5, 1.5, 3.0, 1.0, 2.5, 0.5]
    flats_bass = [1.0, 2.5, 0.5, 2.0, 0.0, 1.5, -0.5]

    symbol = "b" if is_flat else "#"
    c.setFont("Times-Bold", 10)

    for i in range(min(num_acc, 7)):
        sx = x + i * 7.5
        t_pos = flats_treble[i] if is_flat else sharps_treble[i]
        b_pos = flats_bass[i] if is_flat else sharps_bass[i]
        c.drawString(sx, treble_y + t_pos * sp - 4, symbol)
        c.drawString(sx, bass_y + b_pos * sp - 4, symbol)

    return min(num_acc, 7) * 7.5


def draw_note(
    c: canvas.Canvas,
    x: float,
    y: float,
    staff_bot: float,
    staff_top: float,
    sp: float,
    dur: float = 0.5,
) -> tuple[float, float, bool]:
    """Draw a note with ledger lines, angled notehead, and stem."""
    # Ledger lines if note is outside the 5 staff lines
    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    if y < staff_bot:
        cur_y = staff_bot - sp
        while cur_y >= y - 1.0:
            c.line(x - 5.5, cur_y, x + 5.5, cur_y)
            cur_y -= sp
    elif y > staff_top:
        cur_y = staff_top + sp
        while cur_y <= y + 1.0:
            c.line(x - 5.5, cur_y, x + 5.5, cur_y)
            cur_y += sp

    # Notehead (ellipse slightly tilted at 18 degrees)
    c.saveState()
    c.translate(x, y)
    c.rotate(18)
    if dur >= 2.0:
        c.setLineWidth(1.2)
        c.setFillColorRGB(1.0, 1.0, 1.0)
        c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=1, fill=0)
    else:
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=0, fill=1)
    c.restoreState()

    # Stem
    mid_staff = (staff_bot + staff_top) / 2.0
    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    if y < mid_staff:
        # Stem UP on right
        stem_x = x + 2.8
        stem_end_y = y + 20
        c.line(stem_x, y, stem_x, stem_end_y)
        return stem_x, stem_end_y, True
    else:
        # Stem DOWN on left
        stem_x = x - 2.8
        stem_end_y = y - 20
        c.line(stem_x, y, stem_x, stem_end_y)
        return stem_x, stem_end_y, False


def draw_beams_for_measure(c: canvas.Canvas, note_stems: list):
    """Connect stems of adjacent eighth/sixteenth notes with a continuous beam."""
    if len(note_stems) < 2:
        return
    sorted_stems = sorted(note_stems, key=lambda s: s[3])
    c.setLineWidth(2.4)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    for i in range(len(sorted_stems) - 1):
        s1 = sorted_stems[i]
        s2 = sorted_stems[i + 1]
        # Beam if same stem direction and beat difference between 0.1 and 1.05 beats
        if s1[2] == s2[2] and 0.1 <= (s2[3] - s1[3]) <= 1.05:
            c.line(s1[0], s1[1], s2[0], s2[1])


def generate_sheet_music_pdf(
    result_data: dict[str, Any],
    output_path: str,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    max_measures: Optional[int] = None,
) -> str:
    """Generate a publication-grade classical sheet music score PDF from analysis results.

    Args:
        result_data: Dict containing 'music' (notes, measures, tempo_bpm, key, time_signature, chords).
        output_path: Path where the resulting .pdf file will be written.
        title: Piece title (defaults to cleaned filename or "Transcription pour Piano & Ensemble").
        subtitle: Subtitle (defaults to "MELODYX Concert Score — Orchestre & Clavier").
        max_measures: Optional limit on number of measures to render (None = all measures).

    Returns:
        The output_path on success.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    music = result_data.get("music", {})
    notes = music.get("notes", [])
    measures = music.get("measures", [])
    tempo_info = music.get("tempo_bpm", {})
    tempo_val = round(tempo_info.get("value", 120.0)) if isinstance(tempo_info, dict) else round(float(tempo_info or 120.0))
    key_info = music.get("key", {})
    key_name = key_info.get("value", "C major") if isinstance(key_info, dict) else str(key_info or "C major")
    time_sig_info = music.get("time_signature", {})
    time_sig = time_sig_info.get("value", "4/4") if isinstance(time_sig_info, dict) else str(time_sig_info or "4/4")
    chords = music.get("chords", [])

    if not title:
        raw_fn = result_data.get("audio", {}).get("filename", "")
        if raw_fn:
            title = os.path.splitext(os.path.basename(raw_fn))[0].replace("_", " ").title()
        else:
            title = "Transcription pour Piano & Ensemble"

    if not subtitle:
        subtitle = "MELODYX Concert Score — Édition d'Orchestre"

    # Group notes by measure
    notes_by_measure: dict[int, list[dict]] = {}
    for n in notes:
        m_idx = n.get("measure", 1)
        notes_by_measure.setdefault(m_idx, []).append(n)

    # Map chords by measure index
    chord_by_measure: dict[int, str] = {}
    for m in measures:
        m_idx = m.get("index", 1)
        m_start = m.get("start", 0.0)
        for ch in chords:
            if ch.get("start", 0.0) <= m_start < ch.get("end", 0.0):
                chord_by_measure[m_idx] = ch.get("label", "")
                break

    # If no measures detected, create synthetic measures
    total_measures = len(measures)
    if total_measures == 0:
        total_measures = max(1, math.ceil(len(notes) / 6))
        for m_i in range(1, total_measures + 1):
            measures.append({"index": m_i, "start": (m_i - 1) * 2.0, "end": m_i * 2.0})

    if max_measures and max_measures < total_measures:
        total_measures = max_measures

    measures_per_system = 4
    total_systems = math.ceil(total_measures / measures_per_system)
    # Page 1 holds 4 systems; subsequent pages hold 4 systems
    total_score_pages = max(1, 1 + math.ceil(max(0, total_systems - 4) / 4))

    c = canvas.Canvas(output_path, pagesize=A4)

    cur_measure = 1
    page_num = 1

    section_letters = {
        1: "A", 9: "B", 17: "C", 25: "D", 33: "E", 41: "F",
        49: "G", 57: "H", 65: "I", 73: "J", 81: "K", 89: "L", 97: "M",
    }

    while cur_measure <= total_measures:
        if page_num == 1:
            # Main Title Header (Opera Score Engraving)
            c.setFont("Times-Bold", 18)
            c.drawCentredString(PAGE_W / 2.0, PAGE_H - 45, title)

            c.setFont("Times-Roman", 10)
            c.drawRightString(MARGIN_RIGHT, PAGE_H - 45, subtitle)

            c.setFont("Times-Bold", 11)
            c.drawString(MARGIN_LEFT, PAGE_H - 72, f"Allegro moderato   ♩ = {tempo_val}")

            c.setFont("Times-Italic", 9.5)
            c.drawRightString(
                MARGIN_RIGHT, PAGE_H - 72, f"Tonalité: {key_name}  •  Métrique: {time_sig}"
            )

            # Elegant decorative double bar
            c.setLineWidth(0.8)
            c.setStrokeColorRGB(0.2, 0.2, 0.2)
            c.line(MARGIN_LEFT, PAGE_H - 82, MARGIN_RIGHT, PAGE_H - 82)
            c.setLineWidth(0.3)
            c.line(MARGIN_LEFT, PAGE_H - 85, MARGIN_RIGHT, PAGE_H - 85)

            first_treble_y = PAGE_H - 148
            num_systems_this_page = 4
        else:
            # Running header for subsequent pages
            c.setFont("Times-Italic", 9)
            c.drawString(MARGIN_LEFT, PAGE_H - 35, title)
            c.drawRightString(MARGIN_RIGHT, PAGE_H - 35, f"MELODYX • Page {page_num}")
            c.setLineWidth(0.4)
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.line(MARGIN_LEFT, PAGE_H - 40, MARGIN_RIGHT, PAGE_H - 40)

            first_treble_y = PAGE_H - 92
            num_systems_this_page = 4

        for sys_idx in range(num_systems_this_page):
            if cur_measure > total_measures:
                break

            treble_y = first_treble_y - sys_idx * (SYSTEM_H + SYSTEM_GAP)
            bass_y = treble_y - INTER_STAFF_GAP - STAFF_H
            sys_y = bass_y

            # 5-line grand staff
            c.setStrokeColorRGB(0.12, 0.12, 0.12)
            c.setLineWidth(0.5)
            for i in range(5):
                c.line(MARGIN_LEFT, treble_y + i * LINE_SP, MARGIN_RIGHT, treble_y + i * LINE_SP)
                c.line(MARGIN_LEFT, bass_y + i * LINE_SP, MARGIN_RIGHT, bass_y + i * LINE_SP)

            # Piano brace and initial bar line
            draw_brace(c, MARGIN_LEFT, treble_y + 4 * LINE_SP, bass_y)
            c.setLineWidth(0.8)
            c.line(MARGIN_LEFT, bass_y, MARGIN_LEFT, treble_y + 4 * LINE_SP)

            # Label "Piano" / "Pno."
            c.setFont("Times-Roman", 8)
            label = "Piano" if (page_num == 1 and sys_idx == 0) else "Pno."
            c.drawRightString(MARGIN_LEFT - 14, sys_y + (SYSTEM_H / 2.0) - 3, label)

            # Clefs
            draw_treble_clef(c, MARGIN_LEFT + 8, treble_y, LINE_SP)
            draw_bass_clef(c, MARGIN_LEFT + 8, bass_y, LINE_SP)

            # Key signature
            key_w = draw_key_signature(c, key_name, MARGIN_LEFT + 22, treble_y, bass_y, LINE_SP)

            # Time signature on measure 1
            meas_start_x = MARGIN_LEFT + 26 + key_w
            if page_num == 1 and sys_idx == 0:
                ts_parts = time_sig.split("/")
                top_digit = ts_parts[0] if ts_parts else "4"
                bot_digit = ts_parts[1] if len(ts_parts) > 1 else "4"
                c.setFont("Times-Bold", 12)
                c.drawCentredString(meas_start_x + 6, treble_y + 2.5 * LINE_SP, top_digit)
                c.drawCentredString(meas_start_x + 6, treble_y + 0.5 * LINE_SP, bot_digit)
                c.drawCentredString(meas_start_x + 6, bass_y + 2.5 * LINE_SP, top_digit)
                c.drawCentredString(meas_start_x + 6, bass_y + 0.5 * LINE_SP, bot_digit)
                meas_start_x += 16

            # Rehearsal Mark ([A], [B], [C]...)
            sec_letter = section_letters.get(cur_measure, "")
            if sec_letter:
                c.setFont("Times-Bold", 9)
                c.rect(meas_start_x + 2, treble_y + 4 * LINE_SP + 14, 12, 11, stroke=1, fill=0)
                c.drawCentredString(meas_start_x + 8, treble_y + 4 * LINE_SP + 16, sec_letter)

            # Measures in this system
            avail_w = MARGIN_RIGHT - meas_start_x
            bar_w = avail_w / measures_per_system

            for b in range(measures_per_system):
                if cur_measure > total_measures:
                    break

                m_num = cur_measure
                bx = meas_start_x + b * bar_w
                bx_end = bx + bar_w

                # Barline at end of measure
                c.setLineWidth(0.6)
                if m_num == total_measures:
                    # Final double barline
                    c.line(bx_end - 3, bass_y, bx_end - 3, treble_y + 4 * LINE_SP)
                    c.setLineWidth(1.6)
                    c.line(bx_end, bass_y, bx_end, treble_y + 4 * LINE_SP)
                else:
                    c.line(bx_end, bass_y, bx_end, treble_y + 4 * LINE_SP)

                # Measure number
                c.setFont("Times-Italic", 7.5)
                c.drawString(bx + 3, treble_y + 4 * LINE_SP + 3, str(m_num))

                # Chord symbol centered above measure
                ch_label = chord_by_measure.get(m_num, "")
                if ch_label:
                    c.setFont("Times-Bold", 9)
                    c.drawCentredString(bx + bar_w / 2.0, treble_y + 4 * LINE_SP + 4, ch_label)

                # Draw notes
                m_notes = notes_by_measure.get(m_num, [])
                treble_stems: list = []
                bass_stems: list = []

                for n in m_notes:
                    beat_pos = n.get("beat_position", 0.0)
                    nx = bx + 10 + (beat_pos / 4.0) * (bar_w - 20)
                    pitch = n.get("pitch", 60)
                    hand = n.get("hand", "right")
                    dur = n.get("duration", 0.5)

                    abs_step, is_acc = pitch_to_diatonic(pitch)

                    if hand == "left" or pitch < 57:
                        # Bass staff
                        delta_steps = abs_step - BASS_BOTTOM_STEP
                        ny = bass_y + delta_steps * (LINE_SP / 2.0)
                        stem_info = draw_note(c, nx, ny, bass_y, bass_y + 4 * LINE_SP, LINE_SP, dur)
                        if stem_info and dur <= 0.6:
                            bass_stems.append((stem_info[0], stem_info[1], stem_info[2], beat_pos))
                    else:
                        # Treble staff
                        delta_steps = abs_step - TREBLE_BOTTOM_STEP
                        ny = treble_y + delta_steps * (LINE_SP / 2.0)
                        stem_info = draw_note(c, nx, ny, treble_y, treble_y + 4 * LINE_SP, LINE_SP, dur)
                        if stem_info and dur <= 0.6:
                            treble_stems.append((stem_info[0], stem_info[1], stem_info[2], beat_pos))

                # Continuous beams for eighth-notes
                draw_beams_for_measure(c, treble_stems)
                draw_beams_for_measure(c, bass_stems)

                cur_measure += 1

        # Footer
        c.setFont("Times-Roman", 8)
        c.drawCentredString(
            PAGE_W / 2.0, 22, f"Page {page_num}  •  MELODYX Partition Studio  •  Édition de Concert"
        )
        c.showPage()
        page_num += 1

    # Final Page: Fiche Conducteur d'Orchestre & Grille Harmonique (Lead Sheet)
    _draw_conductor_guide_page(
        c, title, key_name, tempo_val, time_sig, total_measures, len(notes), chord_by_measure, result_data
    )
    c.showPage()

    c.save()
    logger.info("Generated PDF sheet music at: %s (%d pages)", output_path, page_num)
    return output_path


def _draw_conductor_guide_page(
    c: canvas.Canvas,
    title: str,
    key_name: str,
    tempo_val: int,
    time_sig: str,
    total_measures: int,
    total_notes: int,
    chord_by_measure: dict[int, str],
    result_data: dict[str, Any],
):
    """Draw an executive conductor guide with harmonic progression and rehearsal notes."""
    c.setFont("Times-Bold", 16)
    c.drawCentredString(PAGE_W / 2.0, PAGE_H - 45, f"FICHE CONDUCTEUR & GRILLE D'ENSEMBLE — {title}")

    c.setFont("Times-Italic", 10)
    c.drawCentredString(PAGE_W / 2.0, PAGE_H - 62, "Guide d'Interprétation Musicale & Grille Harmonique d'Orchestre")

    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.line(MARGIN_LEFT, PAGE_H - 72, MARGIN_RIGHT, PAGE_H - 72)

    # Repertoire specs box
    c.rect(MARGIN_LEFT, PAGE_H - 145, USABLE_WIDTH, 65, stroke=1, fill=0)
    c.setFont("Times-Bold", 10)
    c.drawString(MARGIN_LEFT + 15, PAGE_H - 92, "PARAMÈTRES D'EXÉCUTION :")

    c.setFont("Times-Roman", 9.5)
    c.drawString(MARGIN_LEFT + 25, PAGE_H - 110, f"• Tonalité principale : {key_name}")
    c.drawString(MARGIN_LEFT + 25, PAGE_H - 125, f"• Tempo de référence : {tempo_val} BPM (Allegro moderato)")
    c.drawString(MARGIN_LEFT + 250, PAGE_H - 110, f"• Métrique : {time_sig}")
    c.drawString(MARGIN_LEFT + 250, PAGE_H - 125, f"• Mesures transcrites : {total_measures} ({total_notes} notes détectées)")

    # Harmonic Grid (Grille d'accords par mesure)
    c.setFont("Times-Bold", 11)
    c.drawString(MARGIN_LEFT, PAGE_H - 170, "GRILLE HARMONIQUE PAR MESURE (LEAD SHEET) :")

    # Table of 4 measures per line
    grid_y = PAGE_H - 190
    col_w = USABLE_WIDTH / 4.0
    cell_h = 22.0

    c.setFont("Times-Roman", 9)
    measures_to_show = min(total_measures, 32)  # show up to 32 measures in lead sheet

    for i in range(measures_to_show):
        m_num = i + 1
        row = i // 4
        col = i % 4
        cx = MARGIN_LEFT + col * col_w
        cy = grid_y - row * cell_h

        # cell box
        c.setLineWidth(0.4)
        c.rect(cx, cy - cell_h + 5, col_w, cell_h, stroke=1, fill=0)

        # measure index
        c.setFont("Times-Italic", 7.5)
        c.drawString(cx + 4, cy - 3, f"m.{m_num}")

        # chord
        ch = chord_by_measure.get(m_num, "—")
        c.setFont("Times-Bold", 10)
        c.drawCentredString(cx + col_w / 2.0, cy - 11, ch)

    # Rehearsal & AI Performance Advice box
    advice_y = grid_y - (math.ceil(measures_to_show / 4.0) * cell_h) - 30

    c.setFont("Times-Bold", 11)
    c.drawString(MARGIN_LEFT, advice_y, "CONSEILS D'INTERPRÉTATION & COORDINATION MUSICALE :")

    c.setFont("Times-Roman", 9)
    advice_lines = [
        "1. Phrasé du clavier : Soigner l'équilibre entre la main droite mélodique et l'ostinato de la main gauche.",
        "2. Nuances recommandées : Commencer piano (p) sur la première section [A], puis crescendo progressif vers [B].",
        "3. Pédale forte (sustain) : Renouveler la pédale à chaque changement d'accord pour éviter la saturation harmonique.",
        "4. Ensembles et cordes : Les repères [A], [B], [C] servent de marques de répétition pour synchroniser le groupe.",
    ]

    # If AI summary or explanations are in result_data, include them!
    ai_data = result_data.get("ai", {})
    if ai_data.get("available") and ai_data.get("summary"):
        summary_text = ai_data["summary"].get("executive_summary", "")
        if summary_text:
            advice_lines.insert(0, f"Notice du Maître d'Orchestre : {summary_text[:140]}...")

    for idx, line in enumerate(advice_lines):
        c.drawString(MARGIN_LEFT + 10, advice_y - 20 - (idx * 16), line)

    # Final footer
    c.setFont("Times-Roman", 8)
    c.drawCentredString(
        PAGE_W / 2.0, 22, "Fiche Conducteur • MELODYX Studio • Conforme Charte Hackathon SIMA × EPITECH"
    )
