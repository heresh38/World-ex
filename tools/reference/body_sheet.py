"""Grid sheet from body_views.py renders: for each pair, Epic | ours | overlay (cyan Epic, orange ours) in front, side
and back view, 10 cm grid lines (labelled every 20 cm). python body_sheet.py <views_dir> <out.jpg>"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageChops

D, OUT = sys.argv[1], sys.argv[2]
RES_H, ORTHO = 1100, 2.05
PPM = RES_H / ORTHO
PAIRS = [("epic_metahuman", "ours_male", "MetaHuman vs ours (male)"), ("epic_manny", "ours_male", "Manny vs ours (male)"),
         ("epic_quinn", "ours_female", "Quinn vs ours (female)")]
VIEWS = ["front", "side", "back"]
CW, CH = 300, 367
try:
    F = ImageFont.truetype("arial.ttf", 15); FS = ImageFont.truetype("arial.ttf", 11)
except Exception:
    F = FS = ImageFont.load_default()


def load(name, view):
    im = Image.open(f"{D}/{name}_{view}.png").convert("RGBA")
    bg = Image.new("RGBA", im.size, (22, 24, 28, 255)); bg.alpha_composite(im)
    return im, bg.convert("RGB")


def overlay(a, b):
    la = a.split()[3].point(lambda x: 255 if x > 40 else 0); lb = b.split()[3].point(lambda x: 255 if x > 40 else 0)
    ga = a.convert("L"); gb = b.convert("L")
    r = ImageChops.multiply(lb, gb.point(lambda x: min(255, x + 60)))
    bch = ImageChops.multiply(la, ga.point(lambda x: min(255, x + 60)))
    g = ImageChops.multiply(ImageChops.multiply(la, lb), ImageChops.lighter(ga, gb))
    g = ImageChops.lighter(g, ImageChops.multiply(lb, gb).point(lambda x: x * .55))
    g = ImageChops.lighter(g, ImageChops.multiply(la, ga).point(lambda x: x * .85))
    return Image.merge("RGB", (r, g, bch))


def grid(im):
    d = ImageDraw.Draw(im)
    w, h = im.size
    for cm in range(0, 200, 10):
        y = h - (cm / 100 + .02) * PPM * h / RES_H
        col = (70, 130, 200) if cm % 50 else (230, 90, 70)
        d.line([(0, y), (w, y)], fill=col, width=1)
        if cm % 20 == 0:
            d.text((2, y - 12), f"{cm}", fill=(200, 205, 215), font=FS)
    return im


cols = len(VIEWS) * 3
sheet = Image.new("RGB", (cols * CW, 40 + len(PAIRS) * (CH + 26)), (16, 17, 20))
d = ImageDraw.Draw(sheet)
for r, (ref, ours, title) in enumerate(PAIRS):
    y0 = 40 + r * (CH + 26)
    d.text((6, y0 - 2), title, fill=(235, 238, 245), font=F)
    for v, view in enumerate(VIEWS):
        ra, rb = load(ref, view); oa, ob = load(ours, view)
        cells = [rb, ob, overlay(ra, oa)]
        for k, im in enumerate(cells):
            c = grid(im.resize((CW, CH)))
            x = (v * 3 + k) * CW
            sheet.paste(c, (x, y0 + 20))
            if r == 0:
                d.text((x + 6, 8), f"{view}: " + ("Epic" if k == 0 else "ours" if k == 1 else "overlay"), fill=(200, 205, 215), font=F)
sheet.save(OUT, quality=90)
print(OUT)
