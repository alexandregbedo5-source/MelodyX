import fitz
import re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def draw_svg_path(c: canvas.Canvas, d: str, tx: float, ty: float, scale: float):
    """Render an SVG path d string onto reportlab canvas with flip Y."""
    c.saveState()
    c.translate(tx, ty)
    c.scale(scale, -scale) # flip Y because SVG is top-down, PDF is bottom-up
    
    # Simple regex tokenizer for SVG path
    tokens = re.findall(r'([a-zA-Z])|([-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)', d)
    
    p = c.beginPath()
    cmd = ''
    cur_x, cur_y = 0.0, 0.0
    start_x, start_y = 0.0, 0.0
    
    idx = 0
    raw_tokens = []
    for letter, num in tokens:
        if letter:
            raw_tokens.append(letter)
        elif num:
            raw_tokens.append(float(num))
            
    i = 0
    while i < len(raw_tokens):
        item = raw_tokens[i]
        if isinstance(item, str):
            cmd = item
            i += 1
            continue
            
        if cmd == 'M': # Absolute moveTo
            cur_x = raw_tokens[i]
            cur_y = raw_tokens[i+1]
            start_x, start_y = cur_x, cur_y
            p.moveTo(cur_x, cur_y)
            i += 2
            cmd = 'L' # Subsequent pairs are treated as lineTo
        elif cmd == 'm': # Relative moveTo
            cur_x += raw_tokens[i]
            cur_y += raw_tokens[i+1]
            start_x, start_y = cur_x, cur_y
            p.moveTo(cur_x, cur_y)
            i += 2
            cmd = 'l'
        elif cmd == 'L':
            cur_x = raw_tokens[i]
            cur_y = raw_tokens[i+1]
            p.lineTo(cur_x, cur_y)
            i += 2
        elif cmd == 'l':
            cur_x += raw_tokens[i]
            cur_y += raw_tokens[i+1]
            p.lineTo(cur_x, cur_y)
            i += 2
        elif cmd == 'H':
            cur_x = raw_tokens[i]
            p.lineTo(cur_x, cur_y)
            i += 1
        elif cmd == 'h':
            cur_x += raw_tokens[i]
            p.lineTo(cur_x, cur_y)
            i += 1
        elif cmd == 'V':
            cur_y = raw_tokens[i]
            p.lineTo(cur_x, cur_y)
            i += 1
        elif cmd == 'v':
            cur_y += raw_tokens[i]
            p.lineTo(cur_x, cur_y)
            i += 1
        elif cmd == 'C': # Absolute cubic bezier
            p.curveTo(raw_tokens[i], raw_tokens[i+1], raw_tokens[i+2], raw_tokens[i+3], raw_tokens[i+4], raw_tokens[i+5])
            cur_x = raw_tokens[i+4]
            cur_y = raw_tokens[i+5]
            i += 6
        elif cmd == 'c': # Relative cubic bezier
            x1 = cur_x + raw_tokens[i]
            y1 = cur_y + raw_tokens[i+1]
            x2 = cur_x + raw_tokens[i+2]
            y2 = cur_y + raw_tokens[i+3]
            x3 = cur_x + raw_tokens[i+4]
            y3 = cur_y + raw_tokens[i+5]
            p.curveTo(x1, y1, x2, y2, x3, y3)
            cur_x, cur_y = x3, y3
            i += 6
        elif cmd in ('Z', 'z'):
            p.closePath()
            cur_x, cur_y = start_x, start_y
        else:
            i += 1
            
    c.setFillColorRGB(0.08, 0.08, 0.08)
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

print("Parser defined!")
