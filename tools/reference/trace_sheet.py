"""Trace the Sarketh weapons off the owner's design sheet (art/reference/sarketh/sarketh_design_sheet.png): each gun's
side view as masks, cm by cm, for tools/blender/sarketh_guns.py to build from.

python tools/reference/trace_sheet.py [out_dir]       (system Python: Pillow, numpy, scipy)

For each weapon (found as the big shapes on the weapons panel, top to bottom; the pistol and the grenade by where they
sit) it writes <out>/<gun>.npz:
  mask   the gun (what is not the panel's background), its see-through windows kept as holes
  cls    what each pixel is: 1 dark plate, 2 pale metal, 3 amber light, 4 white light
  lum    its brightness 0..1 (the shading the painter gave it: ridges and edges catch the light)
  inside how far each pixel lies inside the outline, in pixels (outside: how far outside it)
  px     metres per pixel (from the weapon's length: LENGTHS)
and <out>/<gun>_trace.png to look at. The sheet shows each weapon from ONE side: the outline and where every plate and
light sits are exact; the thickness across the gun is the builder's (the sheet does not show it).
"""
import os
import sys
import json
import numpy as np
from PIL import Image
from scipy import ndimage as nd
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SHEET = os.path.join(ROOT, 'art', 'reference', 'sarketh', 'sarketh_design_sheet.png')
PANEL = (1030, 40, 1536, 1010)                 # the weapons panel (x0, y0, x1, y1) on the sheet
# the weapons' real lengths, muzzle to butt (a Sarketh stands 2.0-2.3 m: its rifle is about the length of its arm)
LENGTHS = {'skr_rifle': .98, 'skr_sniper': 1.14, 'skr_cannon': 1.04, 'skr_blade': .92, 'skr_pistol': .42, 'skr_grenade': .13}


def background(lum):
    """the panel's own shade at every row (a smooth gradient): the median of each row's quietest pixels"""
    bg = np.zeros(lum.shape[0])
    for y in range(lum.shape[0]):
        r = np.sort(lum[y])
        mid = r[len(r) // 4: 3 * len(r) // 4]
        bg[y] = np.median(mid)
    return nd.uniform_filter1d(bg, 25)[:, None]


def chaikin(pts, n=1):
    """corners cut, twice: a pixel outline's steps become the curve the painter drew"""
    P = np.asarray(pts, float)
    for _ in range(n):
        Q = np.roll(P, -1, 0)
        P = np.stack([P * .75 + Q * .25, P * .25 + Q * .75], 1).reshape(-1, 2)
    return P.round(3).tolist()


def polys(mask, simplify=1.35, min_area=12):
    """a mask's regions as polygons with their holes (pixel units, x = column, y = row): the union of each row's runs,
    simplified to under a pixel"""
    rects = []
    for r in range(mask.shape[0]):
        row = mask[r].astype(np.int8)
        d = np.diff(np.concatenate([[0], row, [0]]))
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            rects.append(box(a, r, b, r + 1))
    if not rects:
        return []
    u = unary_union(rects).simplify(simplify, preserve_topology=True)
    geoms = list(u.geoms) if isinstance(u, MultiPolygon) else [u]
    out = []
    for g in geoms:
        if g.area < min_area:
            continue
        out.append(dict(ext=chaikin(g.exterior.coords[:-1]),
                        holes=[chaikin(h.coords[:-1]) for h in g.interiors if Polygon(h).area > 8],
                        area=float(g.area), c=[float(g.centroid.x), float(g.centroid.y)]))
    return out


def main(out):
    os.makedirs(out, exist_ok=True)
    im = np.asarray(Image.open(SHEET).convert('RGB')).astype(np.float32)
    x0, y0, x1, y1 = PANEL
    rgb = im[y0:y1, x0:x1]
    lum = rgb.mean(2)
    bg = background(lum)
    sat = rgb.max(2) - rgb.min(2)
    diff = np.abs(lum - bg)
    # 1. where each gun is: the plain test (far from the panel's shade, or coloured)
    rough = (diff > 9) | (sat > 22)
    rough = nd.binary_closing(nd.binary_opening(rough, iterations=1), iterations=2)
    lab, n = nd.label(rough)
    boxes = []
    for i, sl in enumerate(nd.find_objects(lab)):
        h = sl[0].stop - sl[0].start
        if int((lab[sl] == i + 1).sum()) > 1500 and h > 25:
            boxes.append(sl)
    boxes.sort(key=lambda sl: (sl[0].start + sl[0].stop) / 2)
    # 2. the gun inside its box: its plates, even where as dark as the panel, carry painted texture (the panel is smooth)
    m1 = nd.uniform_filter(lum, 5); m2 = nd.uniform_filter(lum * lum, 5)
    texture = np.sqrt(np.maximum(m2 - m1 * m1, 0))
    objs = []
    for sl in boxes:
        ys, xs = slice(max(sl[0].start - 6, 0), sl[0].stop + 6), slice(max(sl[1].start - 6, 0), sl[1].stop + 6)
        g = (diff[ys, xs] > 8) | (sat[ys, xs] > 22) | (texture[ys, xs] > 3.2)
        g = nd.binary_closing(nd.binary_opening(g, iterations=1), iterations=3)
        holes = nd.binary_fill_holes(g) & ~g
        hl, hn = nd.label(holes)
        for k, sz in enumerate(nd.sum(holes, hl, range(1, hn + 1))):
            if sz < 260:                                   # a speck; a window you can see the panel through stays open
                g[hl == k + 1] = True
        gl, gn = nd.label(g)
        if not gn:
            continue
        big = 1 + int(np.argmax(nd.sum(g, gl, range(1, gn + 1))))
        g = gl == big
        # the texture test reaches a pixel or two past the outline (an edge is 'textured'): trim back to the true outline
        core = nd.binary_erosion(g, iterations=2)
        g = core | (g & ((diff[ys, xs] > 8) | (sat[ys, xs] > 22)))
        g = nd.binary_opening(g, iterations=1)
        objs.append(((ys, xs), g))
    names = []
    for sl, msk in objs:
        cy = (sl[0].start + sl[0].stop) / 2 + y0
        cx = (sl[1].start + sl[1].stop) / 2 + x0
        w = sl[1].stop - sl[1].start
        if w < 120:
            nm = 'skr_grenade'
        elif w < 260 and cx > 1300 and cy > 650:
            nm = 'skr_pistol'
        else:
            nm = ['skr_rifle', 'skr_sniper', 'skr_cannon', 'skr_blade'][len([x for x in names if x in ('skr_rifle', 'skr_sniper', 'skr_cannon', 'skr_blade')])]
        names.append(nm)
        m = msk
        c = rgb[sl]
        L = lum[sl] / 255.0
        s = sat[sl]
        cls = np.zeros(m.shape, np.uint8)
        pale = m & (L > .215) & (s < 48)            # the pale metal, even in shadow, sits above ~45 of 255; the dark plates under ~30
        amber = m & (c[..., 0] > 150) & (c[..., 0] - c[..., 2] > 45)
        white = m & (L > .78) & (c[..., 2] >= c[..., 0] - 8) & ~amber
        cls[pale] = 2
        cls[amber] = 3
        cls[white] = 4
        cls[~m] = 0
        cls[m & (cls == 0)] = 1
        cls = nd.median_filter(cls, 5) * m
        # clean shapes, as the painter's plates are: pale and dark regions opened and closed, specks under 60 px taken
        # into what surrounds them (the lights are kept as found)
        pale_m = nd.binary_closing(nd.binary_opening(cls == 2, iterations=1), iterations=2) & m
        pl, pn = nd.label(pale_m)
        for k, sz in enumerate(nd.sum(pale_m, pl, range(1, pn + 1))):
            if sz < 60:
                pale_m[pl == k + 1] = False
        dark_m = m & ~pale_m
        dl, dn = nd.label(dark_m)
        for k, sz in enumerate(nd.sum(dark_m, dl, range(1, dn + 1))):
            if sz < 60:
                pale_m[dl == k + 1] = True
        glow = (cls == 3) | (cls == 4)
        cls = np.where(m, np.where(pale_m, 2, 1), 0).astype(np.uint8)
        cls[glow & m] = np.where(white[glow & m], 4, 3) if False else cls[glow & m]
        cls[(amber & m)] = 3
        cls[(white & m) & ~amber] = 4
        m = nd.gaussian_filter(m.astype(np.float32), 1.1) > .5          # a clean outline (no pixel steps)
        L = nd.gaussian_filter(L, 1.2)
        inside = nd.distance_transform_edt(m)
        outside = nd.distance_transform_edt(~m)
        px = LENGTHS[nm] / max(m.shape[1], 1) if nm != 'skr_grenade' else LENGTHS[nm] / m.shape[0]
        np.savez_compressed(os.path.join(out, nm + '.npz'), mask=m, cls=cls, lum=L.astype(np.float32), inside=inside.astype(np.float32), outside=outside.astype(np.float32), pale_in=nd.distance_transform_edt(cls == 2).astype(np.float32), pale_out=nd.distance_transform_edt(cls != 2).astype(np.float32), px=px)
        # the shapes to build from: the outline, two inner tiers (the body steps out toward its core), each pale plate,
        # each light (pixel polygons with their holes; the builder turns them into bevelled solids)
        shapes = dict(size=[int(m.shape[1]), int(m.shape[0])], px=px,
                      outline=polys(m, 1.6), tier1=polys(inside > 3.5, 2.2), tier2=polys(inside > 8.5, 2.6, min_area=30),
                      pale=[dict(p, depth=float(inside[int(min(max(p['c'][1], 0), m.shape[0] - 1)), int(min(max(p['c'][0], 0), m.shape[1] - 1))]))
                            for p in polys(cls == 2, min_area=20)],
                      amber=polys(nd.binary_dilation(cls == 3), .6, 3), white=polys(nd.binary_dilation(cls == 4), .6, 3),
                      # the plates as they lie on a solid block's flat face: kept 3 px in from its rounded edge
                      pale_face=[dict(p, depth=0.0) for p in polys((cls == 2) & (inside > 3.0), 1.1, 20)])
        json.dump(shapes, open(os.path.join(out, nm + '.json'), 'w'))
        vis = np.zeros(m.shape + (3,), np.uint8)
        pal = {0: (30, 30, 34), 1: (60, 60, 90), 2: (200, 196, 186), 3: (255, 170, 60), 4: (210, 230, 255)}
        for k, col in pal.items():
            vis[cls == k] = col
        Image.fromarray(vis).resize((m.shape[1] * 2, m.shape[0] * 2), Image.NEAREST).save(os.path.join(out, nm + '_trace.png'))
        print(f'{nm}: {m.shape[1]} x {m.shape[0]} px, {px * 1000:.2f} mm a pixel, pale {pale.sum()} amber {amber.sum()} white {white.sum()}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'tools', 'reference', 'sarketh_trace'))
