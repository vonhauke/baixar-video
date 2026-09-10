#!/usr/bin/env python3
"""Gera icone.ico (seta de download) para o aplicativo."""

from PIL import Image, ImageDraw

SIZE = 256
BG_TOP = (91, 108, 255)     # azul
BG_BOTTOM = (140, 82, 255)  # roxo
FG = (255, 255, 255)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# fundo com cantos arredondados e degrade vertical simples
grad = Image.new("RGBA", (SIZE, SIZE))
gd = ImageDraw.Draw(grad)
for y in range(SIZE):
    t = y / (SIZE - 1)
    r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
    g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
    b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
    gd.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=52, fill=255)
img.paste(grad, (0, 0), mask)

# seta de download
cx = SIZE // 2
draw.rectangle([cx - 22, 60, cx + 22, 150], fill=FG)          # haste
draw.polygon([(cx - 60, 132), (cx + 60, 132), (cx, 200)], fill=FG)  # ponta
draw.rounded_rectangle([cx - 78, 212, cx + 78, 238], radius=13, fill=FG)  # base

img.save(
    "icone.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("icone.ico gerado")
