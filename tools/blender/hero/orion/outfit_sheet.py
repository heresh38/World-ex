"""The owner's outfit sheet read into numbers (art/reference/player/orion_tpose_outfit.png: the male in his outfit in
the same T-pose and on the same layout as the bodysuit sheet the Orion body was built to), so the outfit is BUILT to it,
centimetre by centimetre, and checked against it (the owner, 2026-11-22: "i want this exact outfit in the game, 100%
the same with the same colours").

python tools/blender/hero/orion/outfit_sheet.py [--out=dir]     (system Python: numpy, scipy, PIL)

Per view (front, side, back) of the top row (the male): the figure's mask on the outfit sheet and on the bodysuit
sheet, and per row the outfit's silhouette against the body's (how far the clothing stands out, in metres, through the
body's own sheet scale: body.CPX metres a pixel, the views' centre columns, the sheet's ground row). Writes
`outfit_male.json` and `outfit_male_masks.npz` (the figure's masks on the outfit sheet, for outfit.py) beside this
file; with --out an overlay of the two sheets for a look.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
REF = os.path.join(ROOT, "art", "reference", "player")
OUTFIT = os.path.join(REF, "orion_tpose_outfit.png")
BODYSUIT = os.path.join(REF, "orion_tpose_bodysuit.png")

# the male's views on both sheets (x0, y0, x1, y1): the top row; the fourth column (a second side view) is not used
VIEWS = dict(front=(8, 2, 528, 509), side=(530, 2, 712, 509), back=(712, 2, 1110, 509))


def backdrop(a, box, band=6):
    """the backdrop under the figure: a smooth quadratic surface per channel fitted to the box's border band"""
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1].astype(np.float64)
    h, w, _ = sub.shape
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.zeros((h, w), bool)
    edge[:band], edge[-band:], edge[:, :band], edge[:, -band:] = True, True, True, True
    X = np.stack([np.ones(h * w), xx.ravel() / w, yy.ravel() / h, (xx.ravel() / w) ** 2, (yy.ravel() / h) ** 2,
                  xx.ravel() * yy.ravel() / (w * h)], 1)
    Xe = X[edge.ravel()]
    bg = np.zeros_like(sub)
    for c in range(3):
        ye = sub[..., c].ravel()[edge.ravel()]
        med = np.median(ye)
        keep = np.abs(ye - med) < 18                      # (a limb touching the border is not the backdrop)
        coef, *_ = np.linalg.lstsq(Xe[keep], ye[keep], rcond=None)
        bg[..., c] = (X @ coef).reshape(h, w)
    return sub, bg


def mask(path, box, tol=11.0):
    """the figure: what the backdrop's flood from the box's border does not reach (holes filled), largest piece"""
    a = np.asarray(Image.open(path).convert("RGB"))
    sub, bg = backdrop(a, box)
    d = np.sqrt(((sub - bg) ** 2).sum(-1))
    near = d < tol
    # the backdrop is what a flood from the box's border reaches through backdrop-coloured pixels, crossing the floor's
    # strip under the feet too (its shadow sealed the backdrop between the legs off from the border); the rest is the
    # figure (its own dark creases stay the figure's)
    h = near.shape[0]
    floor = np.zeros_like(near)
    floor[h - 16:] = True
    passable = near | (floor & (d < 3.2 * tol))
    lab, _ = ndi.label(passable)
    border = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    out = ~np.isin(lab, border[border > 0])
    out = ndi.binary_opening(out, np.ones((3, 3)))
    lab, n = ndi.label(out)
    if n:
        sizes = ndi.sum(out, lab, range(1, n + 1))
        out = lab == (1 + int(np.argmax(sizes)))
    # only small holes are the figure's (a crease the backdrop's colour); the space between the legs, closed in by
    # the coat and the floor's shadow, is backdrop
    holes = ndi.binary_fill_holes(out) & ~out
    lab, n = ndi.label(holes)
    if n:
        sizes = ndi.sum(holes, lab, range(1, n + 1))
        small = np.isin(lab, 1 + np.nonzero(sizes < 160)[0])
        out = out | small
    return out, sub


def edges(m):
    """per row: (first, last) column of the figure, or None"""
    rows = []
    for r in range(m.shape[0]):
        cs = np.nonzero(m[r])[0]
        rows.append((int(cs[0]), int(cs[-1])) if len(cs) else None)
    return rows


def landmarks(m):
    ys, xs = np.nonzero(m)
    return dict(top=int(ys.min()), bottom=int(ys.max()), left=int(xs.min()), right=int(xs.max()))


def main():
    flags = {x.split("=")[0]: (x.split("=", 1)[1] if "=" in x else True) for x in sys.argv[1:]}
    res = {}
    for v, box in VIEWS.items():
        mo, so = mask(OUTFIT, box)
        mb, sb = mask(BODYSUIT, box)
        lo, lb = landmarks(mo), landmarks(mb)
        res[v] = dict(box=box, outfit=lo, body=lb, outfit_rows=edges(mo), body_rows=edges(mb))
        print(f"{v}: outfit {lo}  body {lb}")
        if isinstance(flags.get("--out"), str):
            os.makedirs(flags["--out"], exist_ok=True)
            ov = so.copy()
            ov[mo & ~mb] = ov[mo & ~mb] * .4 + np.array([255, 120, 0]) * .6        # clothing beyond the body: orange
            ov[mb & ~mo] = ov[mb & ~mo] * .4 + np.array([0, 160, 255]) * .6        # body beyond the clothing: blue
            Image.fromarray(np.clip(ov, 0, 255).astype(np.uint8)).save(os.path.join(flags["--out"], f"overlay_{v}.png"))
    with open(os.path.join(HERE, "outfit_male.json"), "w") as f:
        json.dump(res, f)
    # the figures' masks themselves, for the outfit lab (Blender's Python has neither PIL nor scipy)
    masks = {}
    for v, box in VIEWS.items():
        masks[v] = mask(OUTFIT, box)[0]
        masks[v + "_box"] = np.array(box)
    np.savez_compressed(os.path.join(HERE, "outfit_male_masks.npz"), **masks)


if __name__ == "__main__":
    main()
