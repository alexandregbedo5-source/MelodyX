from PIL import Image

im = Image.open("scripts/test_an_f2d491edc5dd_p1.png")
# Crop system 1: around y=100..400, x=50..PAGE_W
scale = 150.0 / 72.0
crop = im.crop((int(40 * scale), int(30 * scale), int(560 * scale), int(260 * scale)))
crop.save("scripts/crop_dadju_p1_system1.png")
print("Cropped DADJU system 1 saved!")
