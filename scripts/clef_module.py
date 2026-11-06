import json
import os
import pymupdf as fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Load glyphs
with open("scripts/glyphs.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

def get_outline(snippet):
    start = snippet.find('o:"') + 3
    end = snippet.find('"', start)
    return snippet[start:end].split()

VEXFLOW_G_CLEF = get_outline(raw["v83"])
VEXFLOW_F_CLEF = get_outline(raw["v79"])

def render_vexflow_glyph(c: canvas.Canvas, tokens: list, x: float, y: float, scale_x: float, scale_y: float):
    p = c.beginPath()
    h = 0
    cur_x, cur_y = x, y
    
    def next_x():
        nonlocal h
        val = float(tokens[h])
        h += 1
        return x + val * scale_x
        
    def next_y():
        nonlocal h
        val = float(tokens[h])
        h += 1
        return y + val * scale_y

    while h < len(tokens):
        cmd = tokens[h]
        h += 1
        if cmd == 'm':
            cur_x = next_x()
            cur_y = next_y()
            p.moveTo(cur_x, cur_y)
        elif cmd == 'l':
            cur_x = next_x()
            cur_y = next_y()
            p.lineTo(cur_x, cur_y)
        elif cmd == 'q':
            qx, qy = next_x(), next_y()
            ex, ey = next_x(), next_y()
            cp1_x = cur_x + (2.0/3.0) * (qx - cur_x)
            cp1_y = cur_y + (2.0/3.0) * (qy - cur_y)
            cp2_x = ex + (2.0/3.0) * (qx - ex)
            cp2_y = ey + (2.0/3.0) * (qy - ey)
            p.curveTo(cp1_x, cp1_y, cp2_x, cp2_y, ex, ey)
            cur_x, cur_y = ex, ey
        elif cmd == 'b':
            ex, ey = next_x(), next_y()
            cp1_x, cp1_y = next_x(), next_y()
            cp2_x, cp2_y = next_x(), next_y()
            p.curveTo(cp1_x, cp1_y, cp2_x, cp2_y, ex, ey)
            cur_x, cur_y = ex, ey

    c.setFillColorRGB(0.08, 0.08, 0.08)
    c.drawPath(p, fill=1, stroke=0)

def draw_treble_clef(c: canvas.Canvas, x: float, y_bot: float, sp: float):
    # Scale ~0.024 fits 7pt staff. Origin of G-clef glyph: y=0 is G line (line 2 = y_bot + sp)
    render_vexflow_glyph(c, VEXFLOW_G_CLEF, x, y_bot + sp, 0.024, 0.024)

def draw_bass_clef(c: canvas.Canvas, x: float, y_bot: float, sp: float):
    # Origin of F-clef glyph: y=0 is F line (line 4 = y_bot + 3*sp)
    render_vexflow_glyph(c, VEXFLOW_F_CLEF, x, y_bot + 3 * sp, 0.024, 0.024)

print("Vexflow clefs ready!")
