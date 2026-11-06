import json
import pymupdf as fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Load the extracted glyphs
with open("scripts/glyphs.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

# Extract outline string from raw JSON snippet
# v83 snippet is: v83:{x_min:...,o:"..."}
def get_outline(snippet):
    start = snippet.find('o:"') + 3
    end = snippet.find('"', start)
    return snippet[start:end].split()

outline_g = get_outline(raw["v83"])
outline_f = get_outline(raw["v79"])

print("G-clef outline tokens:", len(outline_g))
print("F-clef outline tokens:", len(outline_f))

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
            # quadratic bezier: control point then end point
            qx = next_x()
            qy = next_y()
            ex = next_x()
            ey = next_y()
            cp1_x = cur_x + (2.0/3.0) * (qx - cur_x)
            cp1_y = cur_y + (2.0/3.0) * (qy - cur_y)
            cp2_x = ex + (2.0/3.0) * (qx - ex)
            cp2_y = ey + (2.0/3.0) * (qy - ey)
            p.curveTo(cp1_x, cp1_y, cp2_x, cp2_y, ex, ey)
            cur_x, cur_y = ex, ey
        elif cmd == 'b':
            # VexFlow: a = c(), l = u(), r.b(c(), u(), c(), u(), a, l)
            # end point is read FIRST into (a, l), then cp1, then cp2!
            ex = next_x()
            ey = next_y()
            cp1_x = next_x()
            cp1_y = next_y()
            cp2_x = next_x()
            cp2_y = next_y()
            p.curveTo(cp1_x, cp1_y, cp2_x, cp2_y, ex, ey)
            cur_x, cur_y = ex, ey

    c.setFillColorRGB(0.08, 0.08, 0.08)
    c.drawPath(p, fill=1, stroke=0)

pdf_path = "scripts/test_vexflow_clefs.pdf"
c = canvas.Canvas(pdf_path, pagesize=A4)

# Test on 5 staff lines
y_staff1 = 500
y_staff2 = 380
sp = 7.0

for k in range(5):
    c.line(50, y_staff1 + k * sp, 350, y_staff1 + k * sp)
    c.line(50, y_staff2 + k * sp, 350, y_staff2 + k * sp)

# G-clef standard sizing: scale factor around 0.024
# G-clef curl centers on line 2 (G4) = y_staff1 + 1 * sp
# Let's test a few vertical alignments and scale
render_vexflow_glyph(c, outline_g, 70, y_staff1 + 1 * sp, 0.025, 0.025)
render_vexflow_glyph(c, outline_f, 70, y_staff2 + 3 * sp, 0.025, 0.025)

c.save()

doc = fitz.open(pdf_path)
page = doc[0]
pix = page.get_pixmap(dpi=150)
pix.save("scripts/test_vexflow_clefs.png")
doc.close()
print("Saved scripts/test_vexflow_clefs.png!")
