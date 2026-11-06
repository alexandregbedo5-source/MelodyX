import json
import sqlite3
import sys
sys.path.insert(0, ".")
import pymupdf as fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from clef_module import draw_treble_clef, draw_bass_clef

# Read DADJU result
db = sqlite3.connect("melodyx.db")
db.row_factory = sqlite3.Row
row = db.execute("SELECT result_json FROM analysis_results WHERE analysis_id = 'an_be261202d301'").fetchone()
data = json.loads(row["result_json"])

from app.services.pdf_generator import (
    PAGE_W, PAGE_H, MARGIN_LEFT, MARGIN_RIGHT, LINE_SP,
    TREBLE_BOTTOM_STEP, BASS_BOTTOM_STEP, SYSTEM_H, SYSTEM_GAP,
    INTER_STAFF_GAP, STAFF_H, pitch_to_diatonic, draw_brace,
    draw_key_signature, KEY_SIGNATURES
)

def group_notes_into_chords(m_notes: list[dict]) -> tuple[list, list]:
    deduped = []
    seen = set()
    for n in sorted(m_notes, key=lambda x: -x.get("duration", 0)):
        hand = n.get("hand", "right")
        pitch = n.get("pitch", 60)
        beat_q = round(n.get("beat_position", 0.0) * 8) / 8
        key = (hand, pitch, beat_q)
        if key not in seen:
            seen.add(key)
            deduped.append(n)
    deduped.sort(key=lambda x: x.get("beat_position", 0.0))
    
    treble_chords = []
    bass_chords = []
    for n in deduped:
        pitch = n.get("pitch", 60)
        hand = n.get("hand", "right")
        beat = n.get("beat_position", 0.0)
        target = bass_chords if (hand == "left" or pitch < 57) else treble_chords
        if target and abs(target[-1]["beat"] - beat) < 0.12:
            target[-1]["pitches"].append((pitch, n.get("duration", 0.5)))
        else:
            target.append({
                "beat": beat,
                "pitches": [(pitch, n.get("duration", 0.5))]
            })
    return treble_chords, bass_chords

def draw_chord(c: canvas.Canvas, x: float, pitches: list, staff_bot: float, staff_top: float, sp: float, base_step: int):
    unique_pitches = sorted(list({p: d for p, d in pitches}.items()), key=lambda x: x[0])
    y_coords = []
    for pitch, dur in unique_pitches:
        abs_step, _ = pitch_to_diatonic(pitch)
        delta_steps = abs_step - base_step
        ny = staff_bot + delta_steps * (sp / 2.0)
        y_coords.append((ny, dur))
        
        c.setLineWidth(0.6)
        c.setStrokeColorRGB(0.1, 0.1, 0.1)
        if ny < staff_bot:
            cur_y = staff_bot - sp
            while cur_y >= ny - 1.0:
                c.line(x - 5.5, cur_y, x + 5.5, cur_y)
                cur_y -= sp
        elif ny > staff_top:
            cur_y = staff_top + sp
            while cur_y <= ny + 1.0:
                c.line(x - 5.5, cur_y, x + 5.5, cur_y)
                cur_y += sp
                
        c.saveState()
        c.translate(x, ny)
        c.rotate(18)
        if dur >= 2.0:
            c.setLineWidth(1.2)
            c.setFillColorRGB(1.0, 1.0, 1.0)
            c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=1, fill=0)
        else:
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.ellipse(-3.2, -2.1, 3.2, 2.1, stroke=0, fill=1)
        c.restoreState()
        
    lowest_y = y_coords[0][0]
    highest_y = y_coords[-1][0]
    avg_y = (lowest_y + highest_y) / 2.0
    mid_staff = (staff_bot + staff_top) / 2.0
    
    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    if avg_y < mid_staff:
        stem_x = x + 2.8
        stem_tip_y = highest_y + 20
        c.line(stem_x, lowest_y, stem_x, stem_tip_y)
        return stem_x, stem_tip_y, True, lowest_y
    else:
        stem_x = x - 2.8
        stem_tip_y = lowest_y - 20
        c.line(stem_x, highest_y, stem_x, stem_tip_y)
        return stem_x, stem_tip_y, False, highest_y

def draw_beams_for_measure(c: canvas.Canvas, stems: list):
    if len(stems) < 2:
        return
    stems = sorted(stems, key=lambda s: s[4])
    c.setLineWidth(2.4)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    for i in range(len(stems) - 1):
        s1 = stems[i]
        s2 = stems[i + 1]
        x1, tip1, is_up1, root1, beat1 = s1
        x2, tip2, is_up2, root2, beat2 = s2
        if is_up1 == is_up2 and 0.2 <= (beat2 - beat1) <= 1.1:
            dx = x2 - x1
            dy = tip2 - tip1
            max_dy = 0.35 * dx
            if dy > max_dy:
                target_tip2 = tip1 + max_dy
                c.setLineWidth(0.7)
                c.line(x2, tip2, x2, target_tip2)
                tip2 = target_tip2
            elif dy < -max_dy:
                target_tip2 = tip1 - max_dy
                c.setLineWidth(0.7)
                c.line(x2, tip2, x2, target_tip2)
                tip2 = target_tip2
            c.setLineWidth(2.4)
            c.line(x1, tip1, x2, tip2)

# Generate test PDF page
pdf_out = "scripts/test_new_engraver.pdf"
c = canvas.Canvas(pdf_out, pagesize=A4)

# Title
c.setFont("Times-Bold", 18)
c.drawCentredString(PAGE_W / 2.0, PAGE_H - 45, "DADJU — Ma Faute (Instrumental)")
c.setFont("Times-Bold", 11)
c.drawString(MARGIN_LEFT, PAGE_H - 72, "Moderato   ♩ = 96")
c.setFont("Times-Italic", 9.5)
c.drawRightString(MARGIN_RIGHT, PAGE_H - 72, "Tonalité: D major  •  Métrique: 4/4")
c.setLineWidth(0.8)
c.line(MARGIN_LEFT, PAGE_H - 82, MARGIN_RIGHT, PAGE_H - 82)
c.setLineWidth(0.3)
c.line(MARGIN_LEFT, PAGE_H - 85, MARGIN_RIGHT, PAGE_H - 85)

# First System
treble_y = PAGE_H - 148
bass_y = treble_y - INTER_STAFF_GAP - STAFF_H

for i in range(5):
    c.line(MARGIN_LEFT, treble_y + i * LINE_SP, MARGIN_RIGHT, treble_y + i * LINE_SP)
    c.line(MARGIN_LEFT, bass_y + i * LINE_SP, MARGIN_RIGHT, bass_y + i * LINE_SP)

draw_brace(c, MARGIN_LEFT, treble_y + 4 * LINE_SP, bass_y)
c.setLineWidth(0.8)
c.line(MARGIN_LEFT, bass_y, MARGIN_LEFT, treble_y + 4 * LINE_SP)

# Clefs
draw_treble_clef(c, MARGIN_LEFT + 8, treble_y, LINE_SP)
draw_bass_clef(c, MARGIN_LEFT + 8, bass_y, LINE_SP)

# Key signature (D major = 2 sharps)
key_w = draw_key_signature(c, "D major", MARGIN_LEFT + 22, treble_y, bass_y, LINE_SP)

meas_start_x = MARGIN_LEFT + 26 + key_w
# Time signature
c.setFont("Times-Bold", 12)
c.drawCentredString(meas_start_x + 6, treble_y + 2.5 * LINE_SP, "4")
c.drawCentredString(meas_start_x + 6, treble_y + 0.5 * LINE_SP, "4")
c.drawCentredString(meas_start_x + 6, bass_y + 2.5 * LINE_SP, "4")
c.drawCentredString(meas_start_x + 6, bass_y + 0.5 * LINE_SP, "4")
meas_start_x += 16

avail_w = MARGIN_RIGHT - meas_start_x
bar_w = avail_w / 4

notes = data["music"]["notes"]
chords = data["music"]["chords"]
measures = data["music"]["measures"]

chord_by_m = {}
for m in measures:
    m_i = m.get("index", 1)
    m_s = m.get("start", 0.0)
    for ch in chords:
        if ch.get("start", 0.0) <= m_s < ch.get("end", 0.0):
            chord_by_m[m_i] = ch.get("label", "")
            break

for b in range(4):
    m_num = b + 1
    bx = meas_start_x + b * bar_w
    bx_end = bx + bar_w
    c.setLineWidth(0.6)
    c.line(bx_end, bass_y, bx_end, treble_y + 4 * LINE_SP)
    c.setFont("Times-Italic", 7.5)
    c.drawString(bx + 3, treble_y + 4 * LINE_SP + 3, str(m_num))
    
    ch_lbl = chord_by_m.get(m_num, "")
    if ch_lbl:
        c.setFont("Times-Bold", 9)
        c.drawCentredString(bx + bar_w / 2.0, treble_y + 4 * LINE_SP + 4, ch_lbl)
        
    m_notes = [n for n in notes if n.get("measure") == m_num]
    t_chords, b_chords = group_notes_into_chords(m_notes)
    
    t_stems = []
    b_stems = []
    
    for ch in t_chords:
        beat = ch["beat"]
        nx = bx + 10 + (beat / 4.0) * (bar_w - 20)
        sx, tip, is_up, root = draw_chord(c, nx, ch["pitches"], treble_y, treble_y + 4 * LINE_SP, LINE_SP, TREBLE_BOTTOM_STEP)
        t_stems.append((sx, tip, is_up, root, beat))
        
    for ch in b_chords:
        beat = ch["beat"]
        nx = bx + 10 + (beat / 4.0) * (bar_w - 20)
        sx, tip, is_up, root = draw_chord(c, nx, ch["pitches"], bass_y, bass_y + 4 * LINE_SP, LINE_SP, BASS_BOTTOM_STEP)
        b_stems.append((sx, tip, is_up, root, beat))
        
    draw_beams_for_measure(c, t_stems)
    draw_beams_for_measure(c, b_stems)

c.save()

doc = fitz.open(pdf_out)
page = doc[0]
pix = page.get_pixmap(dpi=150)
pix.save("scripts/test_new_engraver.png")
doc.close()
print("Saved scripts/test_new_engraver.png successfully!")
