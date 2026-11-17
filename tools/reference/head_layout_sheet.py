"""Draws head_layout.py's masks over each other: ours red, Epic's template cyan, from the front and the side, with
the lines a portrait artist checks (the crown, the brow, the eyes, the nose's base, the mouth, the chin; the
halves and thirds of each head) and the widths at those heights, so the two layouts can be read side by side.

python tools/reference/head_layout_sheet.py <out_dir> <sheet.png>
"""
import json, sys
import numpy as np
from PIL import Image, ImageDraw

D, OUT = sys.argv[1], sys.argv[2]
meta = json.load(open(f"{D}/layout.json"))
fr = meta["frame"]; mpp, W, H, z0, yc = fr["mpp"], fr["w"], fr["h"], fr["z0"], fr["yc"]
row = lambda z: int(round(H - (z - z0) / mpp))
COL = {"ours": (235, 60, 40), "mh": (40, 200, 230)}


def mask(name, view):
    return np.array(Image.open(f"{D}/{name}_{view}.png").convert("L")) > 128


def outline(m):
    e = np.zeros_like(m)
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & ~(m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:])
    return e


panels = []
report = []
for view in ("front", "side"):
    img = np.full((H, W, 3), 245, np.uint8)
    ms = {n: mask(n, view) for n in ("ours", "mh")}
    for n in ("mh", "ours"):
        img[ms[n]] = (img[ms[n]] * .75 + np.array(COL[n]) * .25).astype(np.uint8)
    for n in ("mh", "ours"):
        img[outline(ms[n])] = COL[n]
    im = Image.fromarray(img); d = ImageDraw.Draw(im)
    for n, xo in (("ours", 6), ("mh", W - 150)):
        L = meta[n]
        top, men = L["top"][2], L["men"][2]
        Hh = top - men
        # the halves and thirds of the head, the eye line half way (where a portrait puts it)
        for f, lab in ((0, "chin"), (1 / 3, "1/3"), (.5, "1/2"), (2 / 3, "2/3"), (1, "crown")):
            y = row(men + f * Hh)
            d.line([(0 if n == "ours" else W // 2, y), (W // 2 if n == "ours" else W, y)], fill=COL[n], width=1)
            d.text((xo, y - 12), f"{n} {lab}", fill=COL[n])
        y = row(L["tip"][2]); d.text((xo, y - 12), f"{n} nose tip", fill=COL[n])
    # widths (front) / depths (side) at fractions of OUR head's height
    Lo = meta["ours"]
    for f in (.12, .25, .38, .5, .62, .75, .88):
        z = Lo["men"][2] + f * (Lo["top"][2] - Lo["men"][2])
        r = row(z)
        vals = []
        for n in ("ours", "mh"):
            cols = np.nonzero(ms[n][r])[0]
            vals.append((cols.max() - cols.min() + 1) * mpp * 100 if len(cols) else 0)
        report.append(f"{view} at {f:.2f} of our height: ours {vals[0]:.1f} cm, Epic {vals[1]:.1f} cm")
        d.text((W // 2 - 60, r - 12), f"{vals[0]:.1f} / {vals[1]:.1f}", fill=(0, 0, 0))
    d.text((6, 6), f"{view}: ours red, Epic's template cyan (true scale, same chin)", fill=(0, 0, 0))
    panels.append(np.array(im))
Image.fromarray(np.concatenate(panels, 1)).save(OUT)
for n in ("ours", "mh"):
    L = meta[n]
    print(f"{n}: crown-chin {(L['top'][2] - L['men'][2]) * 100:.1f} cm, nose tip {(L['tip'][2] - L['men'][2]) * 100:.1f} cm "
          f"over the chin, ear {(L['ear'][2] - L['men'][2]) * 100:.1f} cm over the chin")
print("\n".join(report))
print("sheet", OUT)
