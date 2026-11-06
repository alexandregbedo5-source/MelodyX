import pymupdf as fitz

doc = fitz.open("scripts/test_vexflow_clefs.pdf")
page = doc[0]
rects = page.get_drawings()
print("Number of drawing paths:", len(rects))
for idx, r in enumerate(rects):
    print(f"Path {idx}: rect={r['rect']}, fill={r['fill']}")
