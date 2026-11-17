"""The owner's concept sheet read into numbers: the male's silhouette in the front, side and back views of
art/reference/player/orion_tpose_bodysuit.png (the T-pose in the base bodysuit), so the body is BUILT to them and
checked against them, never guessed.

python tools/blender/hero/orion/concept.py [--out=dir]     (system Python: numpy, scipy, PIL)

Writes `concept_male.json` beside this file: per view the figure's box, and per row (top of the hair to the soles,
in fractions of the stature) the silhouette's left and right edge; the torso's width / depth profiles with the arms
cut away; and the landmarks read off them (crown, chin, shoulders, armpits, crotch, knees, ankles). With --out it
also writes the masks over the sheet for a look.
"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
SHEET = os.path.join(ROOT, "art", "reference", "player", "orion_tpose_bodysuit.png")

# where each view of the male stands on the sheet (x0, y0, x1, y1): the top row of the sheet is the male
VIEWS = dict(front=(10, 2, 520, 509), side=(540, 2, 720, 509), back=(720, 2, 1205, 509))


def mask_of(a, box):
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1].astype(np.float32)
    # the backdrop: the median of the box's border, with a slow gradient fitted across the box
    h, w, _ = sub.shape
    border = np.concatenate([sub[:4].reshape(-1, 3), sub[-4:].reshape(-1, 3), sub[:, :4].reshape(-1, 3),
                             sub[:, -4:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    d = np.sqrt(((sub - bg) ** 2).sum(-1))
    # the sheet's frame lines: rows / columns mostly unlike the backdrop while the rows / columns three away are not
    # (a T-posed arm is as long as a line but a dozen pixels thick)
    off = d > 12.0
    rf, cf = off.mean(1), off.mean(0)
    line = np.zeros_like(off)
    for r in range(h):
        if rf[r] > .45 and rf[max(r - 3, 0)] < .3 and rf[min(r + 3, h - 1)] < .3:
            line[r] = True
    for c in range(w):
        if cf[c] > .45 and cf[max(c - 3, 0)] < .3 and cf[min(c + 3, w - 1)] < .3:
            line[:, c] = True
    d = np.where(ndi.binary_dilation(line, np.ones((3, 3))), 0.0, d)
    # the backdrop is what is reached from the border through backdrop-coloured pixels: the figure's rim light and
    # seams close it off, so a grey panel inside the outline that happens to match the backdrop stays figure
    near = d < 6.5
    seeds = np.zeros_like(near)
    seeds[0, :] = seeds[-1, :] = seeds[:, 0] = seeds[:, -1] = True
    lab, n = ndi.label(near)
    keep = np.unique(lab[seeds & near])
    bgm = np.isin(lab, keep[keep > 0])
    m = ~bgm
    m = ndi.binary_opening(m, np.ones((3, 3)))
    lab, n = ndi.label(m)
    if n == 0:
        return m, bg
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = lab == (1 + int(np.argmax(sizes)))
    m = ndi.binary_fill_holes(m)
    return m, bg


def rows(m):
    """per row: (left, right) of the outermost figure pixels, or None"""
    out = []
    for r in range(m.shape[0]):
        cs = np.nonzero(m[r])[0]
        out.append((int(cs[0]), int(cs[-1])) if len(cs) else None)
    return out


def runs(row):
    """the separate spans of figure in one row"""
    cs = np.nonzero(row)[0]
    if not len(cs):
        return []
    br = np.nonzero(np.diff(cs) > 1)[0]
    starts = np.r_[cs[0], cs[br + 1]]
    ends = np.r_[cs[br], cs[-1]]
    return list(zip(starts.tolist(), ends.tolist()))


def analyse():
    a = np.asarray(Image.open(SHEET).convert("RGB"))
    res = {}
    masks = {}
    for name, box in VIEWS.items():
        m, bg = mask_of(a, box)
        masks[name] = m
        ys, xs = np.nonzero(m)
        top, bot = int(ys.min()), int(ys.max())
        H = bot - top
        cx = None
        prof = []
        for r in range(top, bot + 1):
            rr = runs(m[r])
            prof.append(rr)
        res[name] = dict(box=box, bg=bg.tolist(), top=top, bottom=bot, height_px=H, runs=prof,
                         xmin=int(xs.min()), xmax=int(xs.max()))
    return a, masks, res


def torso_profile(res, name):
    """the body's own width at each height with the arms cut away: the span that holds the figure's centre line"""
    v = res[name]
    H = v["height_px"]
    # the centre line: the median of the figure's middle over the legs-to-chest rows
    mids = []
    for i, rr in enumerate(v["runs"]):
        if rr and .25 < i / H < .7:
            lo = min(s for s, e in rr); hi = max(e for s, e in rr)
            mids.append((lo + hi) / 2)
    c = float(np.median(mids))
    out = []
    for i, rr in enumerate(v["runs"]):
        span = None
        for s, e in rr:
            if s - 1 <= c <= e + 1:
                span = (s, e)
        out.append(span)
    return c, out


def main():
    flags = {x.split("=")[0]: (x.split("=", 1)[1] if "=" in x else True) for x in sys.argv[1:]}
    a, masks, res = analyse()
    summary = {}
    for name in VIEWS:
        v = res[name]
        H = v["height_px"]
        c, prof = torso_profile(res, name)
        summary[name] = dict(height_px=H, top=v["top"], bottom=v["bottom"], centre=c,
                             # the widest span in each row (fraction of the stature, from the top), and the torso's own
                             rows=[[None if not rr else [min(s for s, e in rr), max(e for s, e in rr)]] for rr in v["runs"]],
                             body=[None if p is None else [p[0], p[1]] for p in prof],
                             runs=v["runs"])
        print(f"{name}: figure {H} px tall (rows {v['top']}..{v['bottom']}), centre column {c:.1f}")
    # the arms in the front view: per column out from the centre line, the arm's top and bottom row (both arms
    # averaged: the sheet's arms are mirror images to a pixel)
    m = masks["front"]
    c0 = int(round(summary["front"]["centre"]))
    arm = []
    for dx in range(36, 260):
        spans = []
        for col in (c0 - dx, c0 + dx):
            if not 0 <= col < m.shape[1]:
                continue
            cs = np.nonzero(m[60:175, col])[0]
            if not len(cs):
                continue
            br = np.nonzero(np.diff(cs) > 1)[0]
            st, en = np.r_[cs[0], cs[br + 1]], np.r_[cs[br], cs[-1]]
            k = int(np.argmax(en - st))
            spans.append((int(st[k]) + 60, int(en[k]) + 60))
        if len(spans) == 2:
            arm.append([dx, (spans[0][0] + spans[1][0]) / 2, (spans[0][1] + spans[1][1]) / 2])
    summary["arm"] = arm
    with open(os.path.join(HERE, "concept_male.json"), "w") as f:
        json.dump(summary, f)
    # the outlines themselves (the lab compares the body's against them)
    for name, mm in masks.items():
        Image.fromarray((mm * 255).astype(np.uint8)).save(os.path.join(HERE, f"concept_mask_{name}.png"))
    if isinstance(flags.get("--out"), str):
        os.makedirs(flags["--out"], exist_ok=True)
        for name, m in masks.items():
            x0, y0, x1, y1 = VIEWS[name]
            sub = a[y0:y1, x0:x1].copy()
            edge = m ^ ndi.binary_erosion(m)
            sub[edge] = (255, 60, 40)
            Image.fromarray(sub).resize((sub.shape[1] * 2, sub.shape[0] * 2), Image.NEAREST).save(
                os.path.join(flags["--out"], f"mask_{name}.png"))


if __name__ == "__main__":
    main()
