from PIL import Image

im = Image.open("scripts/test_new_engraver.png")
# Crop system 1: around y=100..400, x=50..PAGE_W
scale = 150.0 / 72.0
crop = im.crop((int(40 * scale), int(30 * scale), int(560 * scale), int(260 * scale)))
crop.save("scripts/crop_system1.png")
print("Cropped system 1 saved!")
