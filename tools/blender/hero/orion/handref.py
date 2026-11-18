"""A hand laid under ours (the owner, 2026-11-17: "layout the hand i send and sketch on top of it"): measures a
picture of a hand, fingers up and front on (a reference, or our own silhouette from handlay.py with --alpha): its
outline, the fingertips, the webs, each finger's axis, length and width along it, the palm's edges, the wrist; draws
them over the picture (the sketch layer, <out>_sketch.png) and writes the numbers in the hand's own frame (x along the
hand from the wrist's crease, y across toward the thumb, cm: <out>.json, the mask <out>_mask.npy).

python handref.py <image.png> <x0> <x1> <thumb: left|right> <out_prefix> [--wrist=<row>] [--hand_cm=20]
    [--alpha --frame=<a reference's json>]     (our silhouette, measured in the reference's frame)
Plain Python (numpy, scipy, PIL). A reference picture is never kept in the repository: it is measured, not copied.
"""
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

path, x0, x1, thumb_side, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
flags = dict(a.split("=", 1) for a in sys.argv[6:] if "=" in a)
im0 = Image.open(path)
if "--alpha" in sys.argv:
    al = np.asarray(im0.convert("RGBA"))[:, x0:x1, 3]
    im = Image.new("RGB", im0.size, (250, 250, 250))
    im.paste(Image.new("RGB", im0.size, (200, 160, 140)), mask=im0.convert("RGBA").split()[3])
    A = np.asarray(im).astype(int)[:, x0:x1]
    H, W = A.shape[:2]
    m = al > 127
else:
    im = im0.convert("RGB")
    A = np.asarray(im).astype(int)[:, x0:x1]
    H, W = A.shape[:2]
    bg = np.median(np.r_[A[:6].reshape(-1, 3), A[:, :6].reshape(-1, 3)], axis=0)
    d = np.abs(A - bg[None, None, :]).max(2)
    m = d > int(flags.get("--thr", 16))
m = ndi.binary_opening(m, iterations=1)
m = ndi.binary_closing(m, iterations=2)
m = ndi.binary_fill_holes(m)
lab, n = ndi.label(m)
sizes = ndi.sum(m, lab, range(1, n + 1))
m = lab == (1 + int(np.argmax(sizes)))


def runs(row):
    r = np.flatnonzero(np.diff(np.r_[0, row.astype(np.int8), 0]))
    return [(int(a), int(b) - 1) for a, b in zip(r[::2], r[1::2])]


# tracks from the top: a run that touches no track starts one (a tip); runs that merge end their tracks (a web)
tracks, done = [], []
webs = []
for y in range(H):
    rs = runs(m[y])
    claimed = {}
    for i, (a, b) in enumerate(rs):
        hit = [t for t in tracks if not (t["runs"][-1][2] < a - 1 or t["runs"][-1][1] > b + 1)]
        claimed[i] = hit
    new_tracks = []
    used = set()
    for i, (a, b) in enumerate(rs):
        hit = claimed[i]
        if not hit:
            new_tracks.append(dict(start=y, runs=[(y, a, b)]))
        elif len(hit) == 1 and id(hit[0]) not in used:
            hit[0]["runs"].append((y, a, b)); used.add(id(hit[0])); new_tracks.append(hit[0])
        else:
            hit = sorted(hit, key=lambda t: t["runs"][-1][1])
            longs = [t for t in hit if len(t["runs"]) >= 15 or t.get("merged")]
            if len(longs) <= 1:
                # a notch in a tip's outline (two runs for a few rows) is not a web: one track goes on
                keep = max(hit, key=lambda t: len(t["runs"]))
                keep["runs"].append((y, a, b)); new_tracks.append(keep)
                for t in hit:
                    used.add(id(t))
                continue
            for t1, t2 in zip(longs, longs[1:]):
                webs.append((y, .5 * (t1["runs"][-1][2] + t2["runs"][-1][1])))
            for t in hit:
                t["end"] = y; done.append(t); used.add(id(t))
            new_tracks.append(dict(start=y, runs=[(y, a, b)], merged=True))
    tracks = new_tracks
done += tracks
digits = sorted([t for t in done if not t.get("merged") and len(t["runs"]) > 20], key=lambda t: t["runs"][0][1])
body = [t for t in done if t.get("merged")]
print("digits found:", len(digits), "webs:", [(int(y), round(x)) for y, x in webs])

# the wrist: the narrowest row below the thumb's web
widths = np.array([sum(b - a + 1 for a, b in runs(m[y])) for y in range(H)])
lowest_web = max(y for y, _ in webs) if webs else H // 2
if "--wrist" in flags:
    wy = int(flags["--wrist"])
else:
    rng = np.arange(lowest_web + 40, min(H - 5, lowest_web + 420))
    wy = int(rng[np.argmin(widths[rng])])
wr = runs(m[wy])
wx = .5 * (wr[0][0] + wr[-1][1])
print("wrist row", wy, "width px", widths[wy], "centre", wx)


def axis_of(t, cut=None):
    """centre line of a digit: a line fit to its runs' centres (from its tip to where it joins the hand), its
    direction from the root to the tip, its tip (the farthest point of the outline along it)"""
    R = np.array(t["runs"], float)
    if cut is not None:
        R = R[R[:, 0] <= cut]
    c = np.c_[.5 * (R[:, 1] + R[:, 2]), R[:, 0]]
    # skip the rounded tip's first rows (their centres are not on the axis's line)
    keep = c[len(c) // 6:]
    mu = keep.mean(0)
    u, s, vt = np.linalg.svd(keep - mu)
    dvec = vt[0]
    if dvec[1] > 0:                      # toward the tip (up the image)
        dvec = -dvec
    return mu, dvec, c


# ordering: from the little finger to the index, then the thumb
if thumb_side == "right":
    order = digits                      # left to right: little .. index, thumb last
else:
    order = digits[::-1]
names = ["little", "ring", "middle", "index", "thumb"][:len(order)]
mid = order[2]
mu_m, d_m, _ = axis_of(mid)
# the hand's frame in the image: x from the wrist's centre toward the middle finger's tip, y toward the thumb
tip_m = np.array([.5 * (mid["runs"][0][1] + mid["runs"][0][2]), mid["runs"][0][0]], float)
origin = np.array([wx, wy], float)
ex = (tip_m - origin) / np.linalg.norm(tip_m - origin)
ey = np.array([ex[1], -ex[0]]) if thumb_side == "left" else np.array([-ex[1], ex[0]])     # toward the thumb
L_px = float(np.linalg.norm(tip_m - origin))
scale = float(flags.get("--hand_cm", 20.0)) / L_px          # cm per px
if "--frame" in flags:
    fr = json.load(open(flags["--frame"]))
    origin = np.array(fr["origin"], float); ex = np.array(fr["ex"], float); ey = np.array(fr["ey"], float)
    scale = fr["scale_cm_px"]
to_hand = lambda p: (np.array([(np.asarray(p) - origin) @ ex, (np.asarray(p) - origin) @ ey]) * scale)
print(f"hand length {L_px:.1f} px -> {scale * 10:.4f} mm/px")

out = dict(edges=None, scale_cm_px=scale, origin=origin.tolist(), ex=ex.tolist(), ey=ey.tolist(), wrist_width_cm=widths[wy] * scale,
           digits={}, webs=[to_hand((x, y)).round(2).tolist() for y, x in webs])
edges = []
for xh in np.arange(0.0, 12.01, 1.0):
    # the line across the hand at xh: walk from the axis both ways to the outline
    c0 = origin + ex * (xh / scale)
    row = []
    for sgn in (-1, 1):
        k = 0
        while True:
            q = c0 + ey * sgn * k
            xi, yi = int(round(q[0])), int(round(q[1]))
            if not (0 <= xi < W and 0 <= yi < H) or not m[yi, xi]:
                break
            k += 1
        row.append(round(sgn * k * scale, 2))
    edges.append([round(float(xh), 1)] + row)
img = im.crop((x0, 0, x1, H)).convert("RGBA")
over = Image.new("RGBA", img.size, (0, 0, 0, 0))
dr = ImageDraw.Draw(over)
# the outline
edge = m ^ ndi.binary_erosion(m)
ys, xs = np.nonzero(edge)
for x, y in zip(xs, ys):
    dr.point((x, y), fill=(30, 90, 255, 255))
for name, t in zip(names, order):
    mu, dv, c = axis_of(t)
    # the tip: the outline's farthest point along the axis
    pts = np.array([(x, y) for (y, a, b) in t["runs"] for x in (a, b)], float)
    s = (pts - mu) @ dv
    tip = mu + dv * s.max()
    # its root: where the axis crosses the line between the webs either side (or the web's row)
    # its root: on its axis, level with the webs either side of it (the visible finger, as the palm shows it)
    ws_ = sorted(webs, key=lambda w: w[1])
    side_webs = [w for w in ws_ if abs(w[1] - mu[0]) < 1.6 * (t["runs"][len(t["runs"]) // 2][2] - t["runs"][len(t["runs"]) // 2][1])]
    if name == "thumb":
        side_webs = [max(webs, key=lambda w: w[0])]
    elif not side_webs:
        side_webs = [min(ws_, key=lambda w: abs(w[1] - mu[0]))]
    end_row = float(np.mean([w[0] for w in side_webs]))
    root = mu + dv * ((end_row - mu[1]) / dv[1])
    # widths across the axis at fractions from the root to the tip, measured on the mask
    nrm = np.array([-dv[1], dv[0]])
    wid = []
    for f in np.linspace(0, 1, 11):
        p = root + (tip - root) * f
        ws = []
        for sgn in (1, -1):
            k = 0
            while True:
                q = p + nrm * sgn * k
                xi, yi = int(round(q[0])), int(round(q[1]))
                if not (0 <= xi < W and 0 <= yi < H) or not m[yi, xi]:
                    break
                k += 1
            ws.append(k)
        wid.append(sum(ws))
    ang = math.degrees(math.atan2(float(dv @ ey), float(dv @ ex))) - math.degrees(math.atan2(float(d_m @ ey), float(d_m @ ex)))
    out["digits"][name] = dict(tip=to_hand(tip).round(2).tolist(), root=to_hand(root).round(2).tolist(),
                               length_cm=round(float(np.linalg.norm(tip - root)) * scale, 2), angle_deg=round(ang, 1),
                               width_cm=[round(w * scale, 2) for w in wid])
    dr.line([tuple(root), tuple(tip)], fill=(0, 200, 0, 255), width=2)
    for f in np.linspace(0, 1, 11):
        p = root + (tip - root) * f
        dr.ellipse([p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2], fill=(0, 200, 0, 255))
    dr.ellipse([tip[0] - 5, tip[1] - 5, tip[0] + 5, tip[1] + 5], outline=(255, 0, 0, 255), width=2)
    dr.ellipse([root[0] - 5, root[1] - 5, root[0] + 5, root[1] + 5], outline=(255, 140, 0, 255), width=2)
for y, x in webs:
    dr.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(200, 0, 200, 255), width=2)
dr.line([(wr[0][0], wy), (wr[-1][1], wy)], fill=(255, 0, 0, 255), width=2)
dr.line([tuple(origin), tuple(tip_m)], fill=(255, 0, 0, 160), width=1)
Image.alpha_composite(img, over).convert("RGB").save(outp + "_sketch.png")
out["edges"] = edges
np.save(outp + "_mask.npy", m)
json.dump(out, open(outp + ".json", "w"), indent=1)
print(json.dumps(out, indent=1))
