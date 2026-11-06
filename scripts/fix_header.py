p = r"C:\Users\ADMIN\Documents\MELODYX\app\services\pdf_generator.py"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()

target = 'c.setFont("Times-Bold", 18)\n            c.drawCentredString(PAGE_W / 2.0, PAGE_H - 45, title)\n\n            c.setFont("Times-Roman", 10)\n            c.drawRightString(MARGIN_RIGHT, PAGE_H - 45, subtitle)'

replacement = 'c.setFont("Times-Bold", 17)\n            c.drawCentredString(PAGE_W / 2.0, PAGE_H - 42, title)\n\n            c.setFont("Times-Italic", 9.5)\n            c.drawCentredString(PAGE_W / 2.0, PAGE_H - 56, subtitle)'

if target in text:
    text = text.replace(target, replacement)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    print("Header fixed!")
else:
    # try CRLF
    target_crlf = target.replace("\n", "\r\n")
    replacement_crlf = replacement.replace("\n", "\r\n")
    if target_crlf in text:
        text = text.replace(target_crlf, replacement_crlf)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print("Header fixed (CRLF)!")
    else:
        print("Target not found")
