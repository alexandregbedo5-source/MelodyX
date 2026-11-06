from PIL import Image

im = Image.open("scripts/test_vexflow_clefs.png")
print("Image size:", im.size)
# Crop around F-clef and G-clef
# G-clef around x=70..150, y=280..400 (scaled by 150/72 = 2.083)
scale = 150.0 / 72.0
g_crop = im.crop((int(60 * scale), int(280 * scale), int(120 * scale), int(380 * scale)))
g_crop.save("scripts/crop_g.png")

f_crop = im.crop((int(60 * scale), int(420 * scale), int(120 * scale), int(480 * scale)))
f_crop.save("scripts/crop_f.png")

print("Saved crop_g.png and crop_f.png!")
