"""Refined classical piano sheet music engraver prototype."""

import math
import os
import json
import sqlite3
import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4  # 595.28 x 841.89 pt
MARGIN_LEFT = 50.0
MARGIN_RIGHT = PAGE_W - 40.0
USABLE_WIDTH = MARGIN_RIGHT - MARGIN_LEFT
LINE_SP = 6.0  # 6 pt between staff lines -> 24 pt total staff height
STAFF_H = 4 * LINE_SP  # 24 pt
INTER_STAFF_GAP = 38.0  # gap between treble and bass staff
SYSTEM_H = STAFF_H + INTER_STAFF_GAP + STAFF_H  # 86 pt
SYSTEM_GAP = 42.0  # gap between consecutive systems

SEMITONE_TO_DIATONIC = [0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6]
IS_SHARP = [False, True, False, True, False, False, True, False, True, False, True, False]

def pitch_to_diatonic(pitch: int):
    octave = (pitch // 12) - 1
    semitone = pitch % 12
    diatonic = SEMITONE_TO_DIATONIC[semitone]
    abs_step = octave * 7 + diatonic
    is_accidental = IS_SHARP[semitone]
    return abs_step, is_accidental

TREBLE_BOTTOM_STEP = 4 * 7 + 2  # E4 = 30
BASS_BOTTOM_STEP = 2 * 7 + 4    # G2 = 18

def draw_brace(c: canvas.Canvas, x: float, y_top: float, y_bottom: float):
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
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(1.0)
    c.line(x, g_y + sp * 4.5, x, y_bot - sp * 1.2)
    c.circle(x - 1.5, y_bot - sp * 1.2, 1.8, stroke=0, fill=1)

def draw_bass_clef(c: canvas.Canvas, x: float, y_bot: float, sp: float):
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

def draw_key_signature(c: canvas.Canvas, key_name: str, x: float, treble_y: float, bass_y: float, sp: float):
    sharps_treble = [4.0, 2.5, 4.5, 3.0]
    sharps_bass = [3.0, 1.5, 3.5, 2.0]
    
    num_sharps = 0
    k_upper = key_name.upper()
    if "E " in k_upper or "E MAJ" in k_upper or "C# MIN" in k_upper:
        num_sharps = 4
    elif "A " in k_upper or "A MAJ" in k_upper or "F# MIN" in k_upper:
        num_sharps = 3
    elif "D " in k_upper or "D MAJ" in k_upper or "B MIN" in k_upper:
        num_sharps = 2
    elif "G " in k_upper or "G MAJ" in k_upper or "E MIN" in k_upper:
        num_sharps = 1
    
    c.setFont("Times-Bold", 10)
    for i in range(num_sharps):
        sx = x + i * 7.5
        c.drawString(sx, treble_y + sharps_treble[i] * sp - 4, "#")
        c.drawString(sx, bass_y + sharps_bass[i] * sp - 4, "#")
    return num_sharps * 7.5

def draw_note(c: canvas.Canvas, x: float, y: float, staff_bot: float, staff_top: float, sp: float, dur: float = 0.5):
    # Ledger lines if outside staff
    c.setLineWidth(0.6)
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

    # Notehead (ellipse slightly tilted)
    c.saveState()
    c.translate(x, y)
    c.rotate(18)
    if dur >= 2.0:
        c.setLineWidth(1.2)
        c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=1, fill=0)
    else:
        c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=0, fill=1)
    c.restoreState()

    # Stem
    mid_staff = (staff_bot + staff_top) / 2.0
    c.setLineWidth(0.7)
    if y < mid_staff:
        stem_x = x + 2.8
        stem_end_y = y + 20
        c.line(stem_x, y, stem_x, stem_end_y)
        return stem_x, stem_end_y, True
    else:
        stem_x = x - 2.8
        stem_end_y = y - 20
        c.line(stem_x, y, stem_x, stem_end_y)
        return stem_x, stem_end_y, False

def draw_beams_for_measure(c: canvas.Canvas, note_stems: list):
    """Connect stems of adjacent eighth/sixteenth notes with a beam."""
    # note_stems is a list of (stem_x, stem_end_y, is_up, beat_pos)
    if len(note_stems) < 2:
        return
    # Group stems in groups of 2 to 4
    # Sort by beat_pos
    sorted_stems = sorted(note_stems, key=lambda s: s[3])
    c.setLineWidth(2.4)
    for i in range(len(sorted_stems) - 1):
        s1 = sorted_stems[i]
        s2 = sorted_stems[i + 1]
        # Only beam if same stem direction and beat difference <= 1.0
        if s1[2] == s2[2] and 0.1 <= (s2[3] - s1[3]) <= 1.05:
            c.line(s1[0], s1[1], s2[0], s2[1])

def render_sample_score():
    con = sqlite3.connect(r'C:\Users\ADMIN\Documents\MELODYX\melodyx.db')
    con.row_factory = sqlite3.Row
    row = con.cursor().execute('SELECT * FROM analysis_results WHERE analysis_id = ?', ('an_9b2673209489',)).fetchone()
    res = json.loads(row['result_json'])
    music = res.get('music', {})
    notes = music.get('notes', [])
    measures = music.get('measures', [])
    tempo_val = round(music.get('tempo_bpm', {}).get('value', 120.0))
    key_name = music.get('key', {}).get('value', 'E major')
    time_sig = music.get('time_signature', {}).get('value', '4/4')
    chords = music.get('chords', [])

    pdf_out = os.path.join(os.path.dirname(__file__), 'test_score.pdf')
    c = canvas.Canvas(pdf_out, pagesize=A4)

    # Group notes by measure
    notes_by_measure = {}
    for n in notes:
        m_idx = n.get('measure', 1)
        notes_by_measure.setdefault(m_idx, []).append(n)

    # Map chords by measure index
    chord_by_measure = {}
    for m in measures:
        m_idx = m.get('index', 1)
        m_start = m.get('start', 0.0)
        for ch in chords:
            if ch.get('start', 0.0) <= m_start < ch.get('end', 0.0):
                chord_by_measure[m_idx] = ch.get('label', '')
                break

    measures_per_system = 4
    systems_per_page = 4
    total_measures = len(measures)
    total_systems = math.ceil(total_measures / measures_per_system)
    total_pages = math.ceil(total_systems / systems_per_page)

    # Render pages (let's render all pages or at least 2 pages)
    cur_measure = 1
    page_num = 1

    while cur_measure <= total_measures and page_num <= 4:
        # Header
        if page_num == 1:
            # Main Title (Classical Opera / Piano engraving)
            c.setFont("Times-Bold", 18)
            c.drawCentredString(PAGE_W / 2.0, PAGE_H - 45, "Transcription pour Piano & Ensemble")

            c.setFont("Times-Roman", 10)
            c.drawRightString(MARGIN_RIGHT, PAGE_H - 45, "MELODYX Concert Score")

            c.setFont("Times-Bold", 11)
            c.drawString(MARGIN_LEFT, PAGE_H - 72, f"Allegro moderato  ♩ = {tempo_val}")

            c.setFont("Times-Italic", 9.5)
            c.drawRightString(MARGIN_RIGHT, PAGE_H - 72, f"Tonalité: {key_name}  •  Métrique: {time_sig}")

            # Elegant decorative double bar
            c.setLineWidth(0.8)
            c.setStrokeColorRGB(0.2, 0.2, 0.2)
            c.line(MARGIN_LEFT, PAGE_H - 82, MARGIN_RIGHT, PAGE_H - 82)
            c.setLineWidth(0.3)
            c.line(MARGIN_LEFT, PAGE_H - 85, MARGIN_RIGHT, PAGE_H - 85)

            first_treble_y = PAGE_H - 148
            num_systems_this_page = 4
        else:
            # Compact running header for subsequent pages
            c.setFont("Times-Italic", 9)
            c.drawString(MARGIN_LEFT, PAGE_H - 35, "Transcription pour Piano & Ensemble")
            c.drawRightString(MARGIN_RIGHT, PAGE_H - 35, f"MELODYX • Page {page_num}")
            c.setLineWidth(0.4)
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.line(MARGIN_LEFT, PAGE_H - 40, MARGIN_RIGHT, PAGE_H - 40)

            first_treble_y = PAGE_H - 92
            num_systems_this_page = 4  # more systems fit on subsequent pages

        for sys_idx in range(num_systems_this_page):
            if cur_measure > total_measures:
                break

            treble_y = first_treble_y - sys_idx * (SYSTEM_H + SYSTEM_GAP)
            bass_y = treble_y - INTER_STAFF_GAP - STAFF_H
            sys_y = bass_y

            # Grand Staff lines (0.5 pt crisp vector lines)
            c.setStrokeColorRGB(0.12, 0.12, 0.12)
            c.setLineWidth(0.5)
            for i in range(5):
                c.line(MARGIN_LEFT, treble_y + i * LINE_SP, MARGIN_RIGHT, treble_y + i * LINE_SP)
                c.line(MARGIN_LEFT, bass_y + i * LINE_SP, MARGIN_RIGHT, bass_y + i * LINE_SP)

            # Brace and initial bar line
            draw_brace(c, MARGIN_LEFT, treble_y + 4 * LINE_SP, bass_y)
            c.setLineWidth(0.8)
            c.line(MARGIN_LEFT, bass_y, MARGIN_LEFT, treble_y + 4 * LINE_SP)

            # System instrument label
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
                c.setFont("Times-Bold", 12)
                c.drawCentredString(meas_start_x + 6, treble_y + 2.5 * LINE_SP, "4")
                c.drawCentredString(meas_start_x + 6, treble_y + 0.5 * LINE_SP, "4")
                c.drawCentredString(meas_start_x + 6, bass_y + 2.5 * LINE_SP, "4")
                c.drawCentredString(meas_start_x + 6, bass_y + 0.5 * LINE_SP, "4")
                meas_start_x += 16

            # Rehearsal Mark ([A], [B], [C]...) every 8 measures or at measure 1
            if cur_measure in [1, 9, 17, 25, 33, 41, 49, 57, 65, 73, 81, 89, 97]:
                section_letters = {1: "A", 9: "B", 17: "C", 25: "D", 33: "E", 41: "F", 49: "G", 57: "H", 65: "I", 73: "J", 81: "K", 89: "L", 97: "M"}
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

                # Bar line at end of measure
                c.setLineWidth(0.6)
                if m_num == total_measures:
                    # Final double barline
                    c.line(bx_end - 3, bass_y, bx_end - 3, treble_y + 4 * LINE_SP)
                    c.setLineWidth(1.6)
                    c.line(bx_end, bass_y, bx_end, treble_y + 4 * LINE_SP)
                else:
                    c.line(bx_end, bass_y, bx_end, treble_y + 4 * LINE_SP)

                # Measure number (small italic)
                c.setFont("Times-Italic", 7.5)
                c.drawString(bx + 3, treble_y + 4 * LINE_SP + 3, str(m_num))

                # Chord symbol centered above the measure
                ch_label = chord_by_measure.get(m_num, '')
                if ch_label:
                    c.setFont("Times-Bold", 9)
                    c.drawCentredString(bx + bar_w / 2.0, treble_y + 4 * LINE_SP + 4, ch_label)

                # Draw notes for this measure
                m_notes = notes_by_measure.get(m_num, [])
                treble_stems = []
                bass_stems = []

                for n in m_notes:
                    beat_pos = n.get('beat_position', 0.0)
                    # horizontal position
                    nx = bx + 10 + (beat_pos / 4.0) * (bar_w - 20)
                    pitch = n.get('pitch', 60)
                    hand = n.get('hand', 'right')
                    dur = n.get('duration', 0.5)

                    abs_step, is_acc = pitch_to_diatonic(pitch)

                    if hand == 'left' or pitch < 57:
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

                # Beams connecting eighth notes
                draw_beams_for_measure(c, treble_stems)
                draw_beams_for_measure(c, bass_stems)

                cur_measure += 1

        # Page Footer
        c.setFont("Times-Roman", 8)
        c.drawCentredString(PAGE_W / 2.0, 22, f"Page {page_num}  •  MELODYX Partition Studio  •  Édition de Concert")
        c.showPage()
        page_num += 1

    c.save()
    print("Multi-page PDF generated:", pdf_out)

    # Render Page 1 to PNG
    doc = pymupdf.open(pdf_out)
    page1 = doc.load_page(0)
    pix1 = page1.get_pixmap(dpi=150)
    png_out1 = os.path.join(os.path.dirname(__file__), 'test_score_p1.png')
    pix1.save(png_out1)
    print("Saved preview Page 1:", png_out1)

    if doc.page_count > 1:
        page2 = doc.load_page(1)
        pix2 = page2.get_pixmap(dpi=150)
        png_out2 = os.path.join(os.path.dirname(__file__), 'test_score_p2.png')
        pix2.save(png_out2)
        print("Saved preview Page 2:", png_out2)

if __name__ == '__main__':
    render_sample_score()
