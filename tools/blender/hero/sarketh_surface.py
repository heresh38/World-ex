"""What a Sarketh's armour is MADE of, and the cloth it wears (the owner, 2026-11-14: "The red piece on the armor
should be a fabric not a block so it should move with the air and it should carry their emblem. The textures on the
armor are too flat ... iron should look like iron not plastic, with scratches and so on, so make it more alive").

  metal     our own tileable maps (numpy; colour, OpenGL normal, breakup / rough / metal), one set per material:
              shell   the pale plates: enamel over forged metal (the hammer's dishes show through the coat, chips and
                      deep scratches go down to the steel, rust in the chips' middles, stains)
              iron    the dark frame: forged iron (hammer blows, pits, casting grain, scratches bright to the metal,
                      rust in the hollows)
              steel   belt and cuffs: blackened steel, brushed
              brass   the fastenings: brushed, tarnished
            Relief is laid in two scales (a hammer blow is a centimetre wide, a scratch a hair): one strength for
            both makes either the blows invisible or the grain a rasp.
  wear      the corner colour `Col`, as on the players' armour (finish.py): RGB = each plate's own tone x grime in
            the recesses x dust on what faces up x dirt from the ground; A = what is rubbed (a band in from every
            convex edge, chips near edges). The material mixes to the bare metal where A and the map's breakup say.
  cloth     the tabard and the tail: ONE layer of cloth cut to a pattern (no thickness: a block was the complaint),
            its own UVs laid flat in metres on a map of its own (2/2 twill in their red, a hem, a border and their
            emblem in thread, the lower edges frayed thread by thread through the alpha, holes burnt in it, dirt up
            from the ground). It hangs from under the belt and is SIMULATED: pinned at the belt, colliding with the
            legs, in a wind (a breeze standing, the air of its own speed at a run).
  emblem    theirs, from their own shapes (the helm with no face, seen from the front): the brow coming down to a
            point, the face as a blade with the vent's slit down it, three dashes of light either side, the lozenge
            they fasten things with. Brow and lozenge in gold thread, the rest pale.
  look      the set rendered as it is made (Cycles): the cloth settled / moving, metal lit so it reads as metal.

In the game the cloth will be the engine's own cloth on that section (pinned by the same group, the same wind);
nothing here is in the game yet.
"""
import math
import os
import zlib
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

F32 = np.float32
SET = "sarketh_veteran"
SUIT, PLATE, DARK, TRIM, GLOW, VISOR, CLOTH, SOLE, GOLD = ("sk_suit", "sk_plate", "sk_plate_dark", "sk_trim", "sk_glow", "sk_visor",
                                                          "sk_cloth", "sk_sole", "sk_gold")
TILE = .15                                                     # metres one repeat of a metal map covers
S = 1024
# material -> (kind, its colour, the bare metal under the wear, that metal's roughness)
METALS = {
    PLATE: ("shell", (.62, .64, .70), (.40, .41, .44), .30),
    DARK: ("iron", (.150, .158, .185), (.56, .57, .60), .26),
    TRIM: ("steel", (.070, .075, .090), (.46, .47, .51), .24),
    GOLD: ("brass", (.78, .56, .22), (.96, .78, .40), .20),
}
CLOTH_W, CLOTH_H = .26, .52                                    # metres each half of the cloth's map covers
RED = (.27, .026, .030)


# ------------------------------------------------------------------------------------------------ small tools

def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _mix(a, b, t):
    return a * (1 - t[..., None]) + np.asarray(b, F32) * t[..., None]


def _lines(n, rng, lmin, lmax, wmin, wmax, bend=0.0, size=S):
    """n scratches (periodic): each drawn in its own window, 1 on its line"""
    out = np.zeros((size, size), F32)
    for _ in range(n):
        x0, y0 = rng.uniform(0, size, 2)
        a = rng.uniform(0, math.pi)
        L = rng.uniform(lmin, lmax)
        w = rng.uniform(wmin, wmax)
        k = rng.uniform(-bend, bend)
        h = int(L / 2 + 6)
        ys = np.arange(int(y0) - h, int(y0) + h + 1)
        xs = np.arange(int(x0) - h, int(x0) + h + 1)
        X, Y = np.meshgrid((xs - x0).astype(F32), (ys - y0).astype(F32))
        along = X * math.cos(a) + Y * math.sin(a)
        d = np.abs(-X * math.sin(a) + Y * math.cos(a) + k * along * along / L)
        m = np.exp(-(d / w) ** 2) * np.clip(1 - (np.abs(along) / (L / 2)) ** 4, 0, 1) * rng.uniform(.45, 1.0)
        idx = np.ix_(ys % size, xs % size)
        out[idx] = np.maximum(out[idx], m.astype(F32))
    return out


def _cells(g, rng, size=S):
    """distance to the nearest of g x g scattered points (periodic), in cells: 0 at a point, ~.7 between"""
    pts = rng.uniform(0, 1, (g, g, 2)).astype(F32)
    y, x = np.mgrid[0:size, 0:size].astype(F32) * (g / size)
    iy, ix = np.floor(y).astype(int), np.floor(x).astype(int)
    d1 = np.full((size, size), 9.0, F32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cy, cx = iy + oy, ix + ox
            p = pts[cy % g, cx % g]
            d1 = np.minimum(d1, np.hypot(cy + p[..., 0] - y, cx + p[..., 1] - x))
    return d1


def _blur(a, n=1):
    for _ in range(n):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5
    return a


def _normal(layers):
    """OpenGL normal map from several periodic height fields, each with its own strength (rows run down the image)"""
    dx = dy = 0
    for h, k in layers:
        dx = dx + (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * .5 * k
        dy = dy + (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * .5 * k
    n = np.dstack([-dx, dy, np.ones_like(dx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * .5 + .5


def _pct(a, p):
    return float(np.percentile(a[::4, ::4], p))


# ------------------------------------------------------------------------------------------------ the metals

def metal(kind, colour, out_dir, seed):
    """writes sk_<kind>_c/_n/_m.png (skips existing) and returns the three paths"""
    import fabric
    paths = [os.path.join(out_dir, f"sk_{kind}_{s}.png") for s in ("c", "n", "m")]
    if all(os.path.exists(p) for p in paths):
        return paths
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.RandomState(seed)

    def N(scale, octaves=3):
        return fabric._noise((S, S), scale, rng, octaves)
    col = np.array(colour, F32)
    steel = np.array((.50, .51, .54), F32)
    rust = np.array((.21, .088, .036), F32)
    fine = _lines(170, rng, 30, 280, .6, 1.1, .15)             # hairlines
    deep = _lines(11 if kind == "shell" else 20, rng, 50, 230, 1.5, 2.6, .25)   # gouges
    grain = N(150, 2)
    low = N(3, 3)
    brk = np.clip(N(7, 4) * .9 + .5, 0, 1)                     # what breaks up the edge wear (the map's red)
    if kind == "iron":
        dish = 1 - np.clip(_cells(13, rng) / .62, 0, 1) ** 2   # the hammer: 1 in a blow's middle, 0 on the ridge round it
        dish2 = 1 - np.clip(_cells(31, rng) / .62, 0, 1) ** 2
        pits = np.clip(_blur((rng.uniform(0, 1, (S, S)) > .9968).astype(F32), 1) * 7, 0, 1)
        hollow = _smooth(.35, .85, dish)
        rf = N(5, 4)
        rmask = np.clip(_smooth(_pct(rf, 55), _pct(rf, 92), rf) * (.2 + .8 * hollow) * .55 + pits * .55, 0, 1)
        broad = -.60 * dish - .16 * dish2 + .30 * low
        small = .26 * grain - 1.5 * pits - .5 * fine - 1.1 * deep
        alb = col * (1 + .12 * low + .07 * grain + .10 * (1 - dish))[..., None]      # the ridges are rubbed lighter
        alb = _mix(alb, steel, np.clip(.7 * fine + deep, 0, 1) * .85)
        alb = _mix(alb, rust, rmask)
        rough = .62 + .10 * grain - .10 * (1 - dish) - .24 * fine - .26 * deep + .30 * rmask
        met = 1 - .78 * rmask
        nrm = _normal([(broad, 6.5), (small, 2.2)])
    elif kind == "shell":
        dish = 1 - np.clip(_cells(9, rng) / .62, 0, 1) ** 2    # forged under the coat: broad and shallow
        peel = N(90, 2)
        cf = N(34, 3) + .45 * N(90, 2)
        t = _pct(cf, 98.6)
        chip = _smooth(t, t + .03, cf)                         # the coat knocked off: sharp-edged, small, a per cent or so
        rustc = _smooth(_pct(cf, 99.5), _pct(cf, 99.9), cf)
        sf = N(4, 4)
        stain = _smooth(_pct(sf, 70), _pct(sf, 99), sf) * .55
        expose = np.clip(chip + .95 * _smooth(.25, .6, deep), 0, 1)
        broad = -.34 * dish + .30 * low
        small = .10 * peel - .95 * chip - .85 * deep - .16 * fine
        alb = col * (1 + .05 * low - .05 * fine)[..., None]
        alb = _mix(alb, col * np.array((.60, .56, .50), F32), stain * .55)
        alb = _mix(alb, np.array((.21, .215, .23), F32), expose)
        alb = _mix(alb, rust, rustc * .7)
        rough = .36 + .07 * peel + .16 * stain + .14 * fine + .08 * expose + .25 * rustc
        met = expose * (1 - .7 * rustc)
        nrm = _normal([(broad, 5.0), (small, 2.2)])
    elif kind == "steel":
        b = rng.uniform(-1, 1, (S, S)).astype(F32)             # brushed: noise drawn out along one way
        for sh in (1, 2, 4, 8, 16, 32, 64):
            b = (b + np.roll(b, sh, 1)) / 2
        brush = b / (b.std() + 1e-9) * .5
        pits = np.clip(_blur((rng.uniform(0, 1, (S, S)) > .9985).astype(F32), 1) * 7, 0, 1)
        rf = N(6, 4)
        rmask = np.clip(_smooth(_pct(rf, 80), _pct(rf, 98), rf) * .4 + pits * .5, 0, 1)
        broad = .30 * low
        small = .30 * brush - 1.2 * pits - .55 * fine - 1.1 * deep
        alb = col * (1 + .14 * brush + .08 * low)[..., None]
        alb = _mix(alb, steel, np.clip(.7 * fine + deep, 0, 1) * .8)
        alb = _mix(alb, rust, rmask)
        rough = .40 + .10 * brush - .18 * fine - .2 * deep + .3 * rmask
        met = 1 - .75 * rmask
        nrm = _normal([(broad, 10.0), (small, 2.4)])
    elif kind == "brass":
        b = rng.uniform(-1, 1, (S, S)).astype(F32)
        for sh in (1, 2, 4, 8, 16, 32):
            b = (b + np.roll(b, sh, 1)) / 2
        brush = b / (b.std() + 1e-9) * .5
        tf = N(6, 4)
        tarn = _smooth(_pct(tf, 50), _pct(tf, 93), tf)
        broad = .25 * low
        small = .22 * brush - .5 * fine - 1.0 * deep
        alb = col * (1 + .08 * brush)[..., None]
        alb = _mix(alb, np.array((.30, .215, .10), F32), tarn * .6)
        alb = _mix(alb, np.array((.98, .80, .42), F32), np.clip(.6 * fine + deep, 0, 1) * .7)
        rough = .30 + .08 * brush + .28 * tarn - .12 * fine
        met = np.ones((S, S), F32)
        nrm = _normal([(broad, 10.0), (small, 2.2)])
    else:
        raise ValueError(kind)
    for arr in (alb, nrm, rough, met):
        assert np.isfinite(arr).all(), f"{kind}: non-finite texels"
    fabric.save(paths[0], alb)
    fabric.save(paths[1], nrm, srgb=False)
    fabric.save(paths[2], np.dstack([brk, np.clip(rough, .14, 1), np.clip(met, 0, 1)]).astype(F32), srgb=False)
    return paths


# ------------------------------------------------------------------------------------------------ the emblem

def _convex(x, y, pts):
    """signed distance (negative inside) to a convex outline"""
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    d = np.full(x.shape, -9.0, F32)
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        nx, ny = by - ay, ax - bx
        ln = math.hypot(nx, ny)
        nx, ny = nx / ln, ny / ln
        if (cx - ax) * nx + (cy - ay) * ny > 0:
            nx, ny = -nx, -ny
        d = np.maximum(d, (x - ax) * nx + (y - ay) * ny)
    return d


def _segment(x, y, a, b):
    ax, ay = a
    bx, by = b
    t = np.clip(((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2), 0, 1)
    return np.hypot(x - ax - t * (bx - ax), y - ay - t * (by - ay))


def emblem(ex, ey, soft=.012):
    """the Sarketh's emblem in its own units (x across, y DOWN; it stands between y -1.42 and 1.47, x within .78):
    returns what is sewn in pale thread and what in gold, each 0..1"""
    def fill(d):
        return np.clip(.5 - d / soft, 0, 1)
    leaf = [(-.36, -.92), (.36, -.92), (.36, -.05), (0.0, 1.0), (-.36, -.05)]      # the face: square above, a point below
    pale = fill(np.abs(_convex(ex, ey, leaf)) - .048)
    pale = np.maximum(pale, fill(np.maximum(np.abs(ex) - .050, np.abs(ey + .30) - .46)))   # the vent's slit
    for cy, hw in ((-.70, .135), (-.38, .115), (-.06, .095)):                   # the dashes of light, either side
        for sg in (-1.0, 1.0):
            xs = ex * sg - .60 - .40 * (ey - cy)
            pale = np.maximum(pale, fill(np.maximum(np.abs(xs) - hw, np.abs(ey - cy) - .095)))
    gold = fill(np.minimum(_segment(ex, ey, (-.72, -1.36), (0.0, -1.13)), _segment(ex, ey, (0.0, -1.13), (.72, -1.36))) - .056)   # the brow
    gold = np.maximum(gold, fill((np.abs(ex) / .105 + np.abs(ey - 1.31) / .155 - 1) * .09))                                      # the lozenge
    return pale, gold


# ------------------------------------------------------------------------------------------------ the cloth

def half_width(s, w0, L, point):
    """half the cloth's width at s metres below its top: straight down to where the point begins, then drawn in"""
    s0 = L * (1 - point)
    return np.where(s < s0, w0, w0 * (1 - np.clip((s - s0) / (L - s0), 0, 1) * .94))


def cloth_maps(out_dir, pats, seed=11):
    """the cloth's own map, 2048 square: each pattern's flat cut in its own half (pats: name -> w0, L, point, half,
    es = the emblem's middle below the top, sc = half the emblem's height / 1.45). Colour + alpha, normal, rough / metal."""
    import fabric
    Z = 2048
    paths = [os.path.join(out_dir, f"sk_cloth_{s}.png") for s in ("c", "n", "m")]
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.RandomState(seed)
    py, px = np.mgrid[0:Z, 0:Z].astype(F32)
    hz = Z // 2
    xm = ((px % hz) + .5) / hz * CLOTH_W - CLOTH_W / 2
    sm = (py + .5) / Z * CLOTH_H
    which = (px >= hz).astype(int)
    thread = (px // 4).astype(int)                             # the warp thread a texel belongs to
    h, tone, fib = fabric.weave(Z // 4, lambda i, j: ((i + j) % 4) < 2, rng, size=Z)
    mott = fabric._noise((Z, Z), 5, rng, 4)
    slub = np.clip(fabric._noise((Z, Z), 40, rng, 2), 0, 1) ** 3
    red = np.array(RED, F32)
    alb = red * (tone * (.93 + .09 * mott) * (1 + .22 * slub))[..., None]
    height = h * .8
    rough = np.full((Z, Z), .88, F32) - .05 * fib
    met = np.zeros((Z, Z), F32)
    alpha = np.zeros((Z, Z), F32)
    cut = rng.exponential(.0018, Z // 4 + 1).astype(F32) + .0004           # where each warp thread ends, short of the edge
    long_ = rng.uniform(0, 1, Z // 4 + 1) < .07
    cut[long_] *= 3.5
    cut = cut[thread]
    hf = fabric._noise((Z, Z), 11, rng, 3)
    lf = fabric._noise((Z, Z), 18, rng, 3)
    for name, P in pats.items():
        w0, L, point = P["w0"], P["L"], P["point"]
        sel = which == P["half"]
        s0 = L * (1 - point)
        w = half_width(sm, w0, L, point)
        cosphi = np.where(sm < s0, 1.0, 1.0 / math.sqrt(1 + (w0 * .94 / (L - s0)) ** 2))
        dedge = (w - np.abs(xm)) * cosphi                      # metres in from the cut edge
        inside = sel & (dedge > 0) & (sm < L)
        s_edge = s0 + (1 - np.abs(xm) / w0) / .94 * (L - s0)   # where this thread meets the slanted lower edge
        a = inside & ((sm < s0) | (s_edge - sm > cut))         # the lower edges are frayed: every thread its own length
        t = float(np.percentile(hf[inside][::16], 99.2)) if inside.any() else 9.0
        holes = (hf > t) & (sm > L * .34)
        char = _smooth(t - .10, t, hf) * (sm > L * .28)        # burnt round each hole
        a &= ~holes
        alpha[a] = 1.0
        # dirt up from the ground, and what burnt
        dirt = _smooth(L * .45, L, sm) * (.40 + .45 * (mott * .5 + .5))
        alb[sel] = _mix(alb, np.array((.075, .055, .045), F32), dirt * .7)[sel]
        alb[sel] = _mix(alb, np.array((.016, .014, .013), F32), char * .9)[sel]
        rough[sel] += (.06 * dirt)[sel]
        # the hem down each straight side: the cloth folded over and stitched
        hem = sel & (dedge < .0058) & (sm < s0 + .01)
        height[hem] += .55
        stitch = sel & (np.abs(dedge - .0066) < .00045) & (((sm * 1000) % 3.2) < 2.1) & (sm < s0 + .01)
        height[stitch] += .5
        alb[stitch] = red * .45
        # a border in gold thread, a broad band and a thin line inside it, all the way round below the belt
        ridge = .7 + .3 * np.sin((px + py) * (2 * math.pi / 5))
        worn = 1 - .75 * _smooth(_pct(lf, 80), _pct(lf, 96), lf)             # where the thread has gone and the red shows
        band = (np.clip(1 - np.abs(dedge - .0140) / .0030, 0, 1) > .08) | (np.abs(dedge - .0212) < .0008)
        g = (sel & band & (sm > .034) & inside).astype(F32) * worn
        # their emblem
        ex, ey = xm / P["sc"], (sm - P["es"]) / P["sc"]
        pale, gold2 = emblem(ex, ey, soft=.00035 / P["sc"] * 3)
        pale = pale * sel * worn
        g = np.maximum(g, gold2 * sel * worn)
        ridge2 = .7 + .3 * np.sin((px - py) * (2 * math.pi / 5))
        alb = _mix(alb, np.array((.70, .50, .19), F32) * ridge[..., None], np.clip(g, 0, 1))
        alb = _mix(alb, np.array((.76, .74, .66), F32) * ridge2[..., None], np.clip(pale, 0, 1))
        alb[sel] = _mix(alb, np.array((.075, .055, .045), F32), dirt * .35)[sel]     # (the thread is dirty too)
        height += .9 * g * ridge + 1.0 * pale * ridge2
        rough = rough * (1 - g) + .50 * g
        rough = rough * (1 - pale) + .64 * pale
        met = np.maximum(met, .55 * g)
    fabric.save(paths[0], alb, alpha)
    fabric.save(paths[1], fabric._normal(height, 2.6), srgb=False)
    fabric.save(paths[2], np.dstack([np.ones_like(rough), np.clip(rough, .2, 1), met]).astype(F32), srgb=False)
    return paths


def cloth_piece(info, log=print, only=None, longer=0.0, bulk=0.0):
    """the tabard before and the tail behind: each ONE layer of cloth cut to its pattern, hanging from under the belt
    with a few soft pleats (the simulation takes it from there). UVs are the flat cut, in metres, on the cloth's map."""
    import wardrobe
    T = info.T
    zh = T["hips"]["z"]
    K = info.L["K"]
    info.bm.verts.ensure_lookup_table()
    mid = [v.co.y for v in info.bm.verts if abs(v.co.x) < .05 and abs(v.co.z - (zh + .02)) < .03]
    top = zh + .050
    pats = {"tabard": dict(w0=.090, L=min(top - (K.z + .035) + longer, CLOTH_H - .01), point=.30, half=0, out=-1.0, y0=float(min(mid)) - .004 - bulk),
            "tail": dict(w0=.106, L=min(top - (K.z + .185) + longer, CLOTH_H - .01), point=.26, half=1, out=1.0, y0=float(max(mid)) + .004 + bulk)}
    if only is not None:                                       # (a rank that is issued only one of them, or neither)
        pats = {k_: v_ for k_, v_ in pats.items() if k_ in only}
        if not pats:
            return None
    for P in pats.values():
        P["es"] = .065 + (P["L"] * (1 - P["point"]) - .065) * .54             # the emblem: in the straight part, under the belt
        P["sc"] = min(.050, (P["L"] * (1 - P["point"]) - .075) / 2.9)
        assert P["L"] < CLOTH_H and P["w0"] < CLOTH_W / 2
    objs = []
    for name, P in pats.items():
        w0, L, point, out, y0 = P["w0"], P["L"], P["point"], P["out"], P["y0"]
        cb = bmesh.new()
        uv = cb.loops.layers.uv.new("UVMap")
        n, cols = max(12, int(round(L / .0105))), 21
        rows, st = [], {}
        for i in range(n + 1):
            f = i / n
            s = L * f
            w = float(half_width(np.float32(s), w0, L, point))
            y = y0 + out * (.0135 + .012 * math.sin(f * math.pi * .85) + .006 * f)
            # gathered where it is held: drawn in to .84 of its width under the belt, the cloth taken up in three
            # folds (so it is as wide as ever along itself); the folds die away down it and the rest is the wind's
            ga = max(0.0, 1 - s / .16)
            gather = 1 - .16 * ga
            row = []
            for j in range(cols):
                x = -1 + 2 * j / (cols - 1)
                pleat = (.0062 * ga + .0030 * (1 - ga) * (1 - .6 * f)) * math.cos(x * math.pi * 3.0)
                v = cb.verts.new((x * w * gather, y + out * (pleat - .010 * x * x), top - s))
                st[v] = ((P["half"] + .5 + x * w / CLOTH_W) / 2, 1 - s / CLOTH_H, s)
                row.append(v)
            rows.append(row)
        for r0, r1 in zip(rows, rows[1:]):
            for j in range(cols - 1):
                f_ = cb.faces.new((r0[j], r0[j + 1], r1[j + 1], r1[j]) if out < 0 else (r0[j + 1], r0[j], r1[j], r1[j + 1]))
                for l in f_.loops:
                    l[uv].uv = st[l.vert][:2]
        cb.normal_update()
        cb.verts.index_update()
        pinned = [v.index for v in cb.verts if st[v][2] < .030]
        o = wardrobe.to_object(cb, "sk_" + name, CLOTH)
        o.vertex_groups.new(name="pin").add(pinned, 1.0, 'REPLACE')
        objs.append(o)
    piece = wardrobe.join(objs, "C_cloth__" + SET)
    piece["sk_bulk"] = float(bulk)                             # (how far a powered frame stands off the body: the collider's too)
    piece["sk_patterns"] = {k: {a: float(b) for a, b in P.items()} for k, P in pats.items()}
    log(f"sarketh: cloth {len(piece.data.vertices)} points, " + ", ".join(f"{k_} {P['L'] * 100:.0f} cm" for k_, P in pats.items()))
    return piece


def hang(piece, arm):
    """the cloth follows the hips where it is pinned; everything below the belt is the simulation's"""
    names = {g.name for g in piece.vertex_groups}
    for b in arm.data.bones:
        if b.name not in names:
            piece.vertex_groups.new(name=b.name)
    piece.vertex_groups["hips"].add(list(range(len(piece.data.vertices))), 1.0, 'REPLACE')
    piece.parent = arm
    mod = piece.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm


# ------------------------------------------------------------------------------------------------ wear

def wear(piece, log=print):
    """the corner colour `Col`: RGB = the plate's own tone x grime x dust x ground dirt, A = 1 - what is rubbed"""
    import finish
    me = piece.data
    n = len(me.vertices)
    if not n:
        return
    co = np.empty(n * 3, F32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    no = np.empty(n * 3, F32)
    me.vertices.foreach_get("normal", no)
    no = no.reshape(-1, 3)
    conv = finish.convexity(me, co, no)
    isl = finish.islands(me)
    ids, inv = np.unique(isl, return_inverse=True)
    rng = np.random.default_rng(zlib.crc32(piece.name.encode()))
    tone = (1.0 + rng.uniform(-.085, .055, len(ids)))[inv].astype(F32)       # no two plates quite the same
    hard = (rng.uniform(0, 1, len(ids)) < .16)[inv]                          # some have had a harder war
    ground = finish.smooth(.46, .02, co[:, 2])
    up = np.clip(no[:, 2], 0, 1)
    front = np.clip(-no[:, 1], 0, 1)
    breakup = finish.fbm(co, .05, 3)
    chips = finish.fbm(co, .022, 7, octaves=2)
    cavity = finish.smooth(.02, .16, -conv)
    edge = finish.smooth(.08, .30, conv)
    band = finish.diffuse(me, edge, 4)
    npoly = len(me.polygons)
    mi = np.empty(npoly, np.int64)
    me.polygons.foreach_get("material_index", mi)
    lt = np.empty(npoly, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    vi = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", vi)
    lm = np.repeat(mi, lt)
    # how wide each face is (2 x area / perimeter: a strip's own width): the chamfer round a plate is a strip a
    # couple of millimetres wide, and THAT is what is rubbed bright. (A band spread in from the rim's points covers
    # the whole of a plate that has few points: every one of them is a rim point.)
    ls = np.empty(npoly, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    area = np.empty(npoly, F32)
    me.polygons.foreach_get("area", area)
    pol = np.repeat(np.arange(npoly), lt)
    li = np.arange(len(vi))
    nxt = ls[pol] + (li - ls[pol] + 1) % lt[pol]
    per = np.bincount(pol, weights=np.linalg.norm(co[vi] - co[vi[nxt]], axis=1), minlength=npoly)
    width = 2 * area / np.maximum(per, 1e-9)
    # ... and a chamfer turns a corner along BOTH its long sides (the plate's face one side, its wall the other); a
    # thin triangle in the middle of a plate's own face turns none, one at the rim turns one
    turn = np.zeros(npoly, F32)
    fb = bmesh.new()
    fb.from_mesh(me)
    for f in fb.faces:
        angs = sorted((e.calc_face_angle(0.0) for e in f.edges if len(e.link_faces) == 2), reverse=True)
        turn[f.index] = angs[1] if len(angs) > 1 else 0.0
    fb.free()
    strip = (finish.smooth(.0046, .0018, width) * finish.smooth(math.radians(20), math.radians(34), turn))[pol]   # per corner: 1 on a chamfer
    near = finish.diffuse(me, edge, 1)
    names = [s.material.name if s.material else "" for s in piece.material_slots]
    out = np.ones((len(me.loops), 4), F32)
    for k, name in enumerate(names):
        sel = lm == k
        if not sel.any() or name in (GLOW, VISOR):
            continue
        v = vi[sel]
        rgb = np.ones((len(v), 3), F32)
        a = np.ones(len(v), F32)
        if name == PLATE:
            rgb *= tone[v, None]
            expo = (.7 + .5 * up[v] + .3 * front[v]) * np.where(hard[v], 1.6, 1.0)
            w = edge[v] * strip[sel] * (.45 + .75 * breakup[v]) * expo
            w = np.maximum(w, near[v] * finish.smooth(.55, .80, chips[v]) * .55)                   # chips, only by an edge
            w = np.maximum(w, np.where(hard[v], finish.smooth(.60, .80, breakup[v]) * .5, 0.0))    # worn through in patches
            a = 1 - np.clip(w, 0, 1)
        elif name in METALS:
            rgb *= tone[v, None]
            a = 1 - np.clip(edge[v] * strip[sel] * (.55 + .6 * breakup[v]), 0, 1)
        else:
            rgb *= (tone[v, None] * .5 + .5)
        g = cavity[v] * (.30 + .40 * breakup[v])
        rgb = rgb * (1 - g[:, None] * np.array((.60, .63, .66), F32))
        dust = up[v] * finish.smooth(.45, .9, finish.fbm(co[v], .03, 11, 2)) * .22
        rgb = rgb * (1 - dust[:, None]) + np.array((.62, .56, .46), F32) * dust[:, None] * rgb.mean(1, keepdims=True) * 1.5
        dirt = ground[v] * (.35 + .45 * breakup[v])
        rgb = rgb * (1 - dirt[:, None] * np.array((.42, .48, .58), F32))
        out[sel, :3] = np.clip(rgb, 0, 1)
        out[sel, 3] = np.clip(a, 0, 1)
    attr = me.color_attributes.get("Col")
    if attr is not None and (attr.domain != "CORNER" or attr.data_type != "BYTE_COLOR"):
        me.color_attributes.remove(attr)
        attr = None
    if attr is None:
        attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    attr.data.foreach_set("color", out.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = list(me.color_attributes).index(attr)
    log(f"surface: {piece.name} tone / grime / wear on {len(me.loops)} corners")


# ------------------------------------------------------------------------------------------------ materials

def _put(nt, sock, v):
    if hasattr(v, "is_output"):
        nt.links.new(v, sock)
    else:
        sock.default_value = v


def _mix_rgb(nt, fac, a, b, blend='MIX'):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = 'RGBA'
    n.blend_type = blend
    _put(nt, n.inputs[0], fac)
    _put(nt, n.inputs[6], a)
    _put(nt, n.inputs[7], b)
    return n.outputs[2]


def _mix_f(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = 'FLOAT'
    _put(nt, n.inputs[0], fac)
    _put(nt, n.inputs[2], a)
    _put(nt, n.inputs[3], b)
    return n.outputs[0]


def _math(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    _put(nt, n.inputs[0], a)
    if b is not None:
        _put(nt, n.inputs[1], b)
    return n.outputs[0]


def textured(name, paths, bare=None, bare_rough=.3, scale=1.0, alpha=False):
    """the material as the game's will be: the three maps, the corner colour's grime multiplied in, and (bare given)
    the bare metal mixed in where the corner colour's alpha and the map's breakup say the surface is rubbed through"""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    b = nt.nodes.get("Principled BSDF")
    vec = None
    if scale != 1.0:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (scale, scale, scale)
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
        vec = mp.outputs["Vector"]

    def tex(path, data):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(path, check_existing=True)
        if data:
            t.image.colorspace_settings.name = 'Non-Color'
        if vec is not None:
            nt.links.new(vec, t.inputs["Vector"])
        return t
    c, n_, r = tex(paths[0], False), tex(paths[1], True), tex(paths[2], True)
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "Col"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(r.outputs["Color"], sep.inputs["Color"])
    base = _mix_rgb(nt, 1.0, c.outputs["Color"], at.outputs["Color"], 'MULTIPLY')
    rough, met = sep.outputs["Green"], sep.outputs["Blue"]
    if bare is not None:
        rubbed = _math(nt, 'SUBTRACT', 1.0, at.outputs["Alpha"])
        x = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rubbed, 1.35), _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', sep.outputs["Red"], .5), .9))
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.clamp = True
        _put(nt, mr.inputs[0], x)
        mr.inputs[1].default_value, mr.inputs[2].default_value = .40, .60
        w = mr.outputs[0]
        base = _mix_rgb(nt, w, base, (*bare, 1.0))
        rough = _mix_f(nt, w, rough, bare_rough)
        met = _mix_f(nt, w, met, 1.0)
    nt.links.new(base, b.inputs["Base Color"])
    nt.links.new(rough, b.inputs["Roughness"])
    nt.links.new(met, b.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(n_.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if alpha:
        nt.links.new(c.outputs["Alpha"], b.inputs["Alpha"])
        m.use_backface_culling = False
    return m


def finish(pieces, out_dir, log=print):
    """UVs (one repeat of a metal map every TILE metres, everywhere), the corner colours, the maps and materials"""
    import fabric
    for p in pieces:
        if not p.name.startswith("C_cloth__"):
            fabric.world_uvs(p, TILE)
        wear(p, log)
    for name, (kind, col, bare, rough) in METALS.items():
        if name in bpy.data.materials:
            textured(name, metal(kind, col, out_dir, zlib.crc32(kind.encode()) % 9973), bare, rough)
    if SUIT in bpy.data.materials:
        textured(SUIT, fabric.make("knit", (.030, .032, .040), .78, out_dir, "sk_suit", 0.0, seed=5), scale=TILE / fabric.TILE["knit"])
    if SOLE in bpy.data.materials:
        textured(SOLE, fabric.make("rubber", (.016, .016, .017), .9, out_dir, "sk_sole", 0.0, seed=6), scale=TILE / fabric.TILE["rubber"])
    cloth = next((p for p in pieces if p.name.startswith("C_cloth__")), None)
    if cloth is not None:
        textured(CLOTH, cloth_maps(out_dir, {k: dict(v) for k, v in cloth["sk_patterns"].to_dict().items()}), alpha=True)
    log(f"surface: maps in {out_dir}")


# ------------------------------------------------------------------------------------------------ the cloth moves

def collider(arm, T, piece):
    """what the cloth lies against: the legs and the hips as plain solids (the armour's own thickness included), each
    following its bone. All of it stands INSIDE the line the cloth is pinned on, before and behind: with the pinned
    rows inside a solid the simulation wrings the cloth into a rope."""
    old = bpy.data.objects.get("SkCollider")
    if old is not None:
        bpy.data.objects.remove(old)
    gi = piece.vertex_groups["pin"].index
    ys = [v.co.y for v in piece.data.vertices if any(g.group == gi and g.weight > .5 for g in v.groups)]
    yf, yb = min(ys), max(ys)
    mid_y = (arm.data.bones["thigh.L"].head_local.y + arm.data.bones["thigh.R"].head_local.y) / 2
    if yf > mid_y:                                             # (only the tail is worn: the front's line is its mirror)
        yf = mid_y - (yb - mid_y)
    elif yb < mid_y:                                           # (only the tabard)
        yb = mid_y + (mid_y - yf)

    def fit(c, r):
        return max(.03, min(r, c.y - yf - .012, yb - c.y - .012))
    bm = bmesh.new()
    owner = {}
    Rt = (T["thigh"]["w"] + T["thigh"]["d"]) / 4 + .018 + piece.get("sk_bulk", 0.0)
    Rs = (T["calf"]["w"] + T["calf"]["d"]) / 4 + .018 + piece.get("sk_bulk", 0.0)
    for side in (".L", ".R"):
        for bone, r0, r1 in (("thigh", Rt, Rt * .82), ("shin", Rs, Rs * .78)):
            b = arm.data.bones[bone + side]
            a_, b_ = Vector(b.head_local), Vector(b.tail_local)
            if bone == "thigh":
                r0 = fit(a_, r0)
            M = Matrix.Translation((a_ + b_) / 2) @ (b_ - a_).to_track_quat('Z', 'Y').to_matrix().to_4x4()
            got = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r0, radius2=r1, depth=(b_ - a_).length, matrix=M)
            for v in got["verts"]:
                owner[v] = bone + side
            for at_, r_ in ((a_, r0), (b_, r1 * 1.03)):
                got = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=r_, matrix=Matrix.Translation(at_))
                for v in got["verts"]:
                    owner[v] = bone + side
    hl, hr = Vector(arm.data.bones["thigh.L"].head_local), Vector(arm.data.bones["thigh.R"].head_local)
    c = Vector((0, (yf + yb) / 2, (hl.z + hr.z) / 2 + .02))
    M = Matrix.Translation(c) @ Matrix.Diagonal((abs(hl.x) + Rt * .7, (yb - yf) / 2 - .014, .115, 1.0))
    got = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0, matrix=M)
    for v in got["verts"]:
        owner[v] = "hips"
    bm.verts.index_update()
    groups = {}
    for v, name in owner.items():
        groups.setdefault(name, []).append(v.index)
    me = bpy.data.meshes.new("SkCollider")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("SkCollider", me)
    bpy.context.scene.collection.objects.link(o)
    for name, idx in groups.items():
        o.vertex_groups.new(name=name).add(idx, 1.0, 'REPLACE')
    o.parent = arm
    o.modifiers.new("Armature", 'ARMATURE').object = arm
    o.modifiers.new("Collision", 'COLLISION')
    o.collision.thickness_outer = .004
    o.collision.thickness_inner = .02
    o.collision.cloth_friction = 6.0
    o.collision.damping = .6
    o.hide_render = True
    return o


def simulate(piece, arm, T):
    """the cloth's simulation and its wind; returns (cloth modifier, wind object)"""
    collider(arm, T, piece)
    m = piece.modifiers.get("Cloth") or piece.modifiers.new("Cloth", 'CLOTH')
    s = m.settings
    s.quality = 10
    s.mass = .16
    s.tension_stiffness = s.compression_stiffness = 22.0
    s.shear_stiffness = 8.0
    s.bending_stiffness = .22
    s.tension_damping = s.compression_damping = s.shear_damping = 6.0
    s.bending_damping = .6
    s.air_damping = 1.6
    s.vertex_group_mass = "pin"
    s.pin_stiffness = 1.0
    c = m.collision_settings
    c.use_collision = True
    c.collision_quality = 4
    c.distance_min = .004
    c.friction = 8.0
    c.use_self_collision = False
    w = bpy.data.objects.get("SkWind")
    if w is None:
        bpy.ops.object.effector_add(type='WIND', location=(0, -4, 1))     # (an empty has no field until one is made for it)
        w = bpy.context.object
        w.name = "SkWind"
    w.field.flow = 0.0
    return m, w


def blow(wind, direction, strength, noise):
    wind.rotation_mode = 'QUATERNION'
    wind.rotation_quaternion = Vector(direction).normalized().to_track_quat('Z', 'Y')
    wind.field.strength = strength
    wind.field.noise = noise


def _fcurves(act):
    try:
        return list(act.fcurves)
    except AttributeError:
        return [fc for layer in act.layers for strip in layer.strips for cb in strip.channelbags for fc in cb.fcurves]


# ------------------------------------------------------------------------------------------------ the look

def _gpu(sc):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = 'GPU'
                return kind
        prefs.compute_device_type = 'NONE'
    except Exception as e:                                     # (no add-on, no driver: the processor renders it)
        print("[sarketh] no graphics card for Cycles:", e)
    sc.cycles.device = 'CPU'
    return "CPU"


def studio(sc, h, quick):
    for o in [o for o in bpy.data.objects if o.name.startswith("SkStudio")]:
        bpy.data.objects.remove(o)
    if quick:
        sc.render.engine = 'BLENDER_WORKBENCH'
        sh = sc.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'TEXTURE'
        sh.show_shadows = False
        sh.show_cavity = True
        sh.cavity_type = 'BOTH'
        sh.show_specular_highlight = True
        sh.show_backface_culling = False
        sc.world = sc.world or bpy.data.worlds.new("W")
        sc.world.color = (.20, .20, .22)
        return "workbench"
    sc.render.engine = 'CYCLES'
    dev = _gpu(sc)
    sc.cycles.samples = int(os.environ.get("SK_SAMPLES", "72"))
    sc.cycles.use_denoising = True
    sc.cycles.use_adaptive_sampling = True
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    sc.view_settings.exposure = -0.4                           # (the pale plates keep their detail)
    w = bpy.data.worlds.new("SkStudioWorld")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (.060, .066, .080, 1)
    bg.inputs[1].default_value = 1.0
    sc.world = w
    aim = Vector((0, 0, h * .55))
    for name, loc, energy, size, col in (("key", (-2.6, -3.6, h * 1.55), 430, 2.6, (1.0, .96, .90)),
                                         ("fill", (3.4, -2.6, h * .75), 110, 4.0, (.78, .87, 1.0)),
                                         ("rim", (2.2, 3.4, h * 1.50), 520, 1.8, (.72, .88, 1.0)),
                                         ("kick", (-3.0, 2.6, h * .70), 200, 2.4, (1.0, .86, .74)),
                                         ("top", (0.0, -.6, h * 2.3), 120, 3.0, (.95, .97, 1.0))):
        L = bpy.data.lights.new("SkStudio_" + name, 'AREA')
        L.shape = 'DISK'
        L.energy, L.size, L.color = energy, size, col
        o = bpy.data.objects.new("SkStudio_" + name, L)
        sc.collection.objects.link(o)
        o.location = loc
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = (aim - Vector(loc)).to_track_quat('-Z', 'Y')
    fm = bpy.data.meshes.new("SkStudio_floor")
    fb = bmesh.new()
    bmesh.ops.create_grid(fb, x_segments=1, y_segments=1, size=400.0)   # (its far edge out of every view)
    fb.to_mesh(fm)
    fb.free()
    fo = bpy.data.objects.new("SkStudio_floor", fm)
    sc.collection.objects.link(fo)
    mat = bpy.data.materials.new("SkStudio_floor")
    mat.use_nodes = True
    pb = mat.node_tree.nodes.get("Principled BSDF")
    pb.inputs["Base Color"].default_value = (.045, .047, .052, 1)
    pb.inputs["Roughness"].default_value = .55
    fm.materials.append(mat)
    return dev


def look(arm, out, T, shown, clips=("Idle", "Run"), log=print, quick=False):
    """the set as it is made: the cloth settled in a breeze from six sides and close, then moving in each clip"""
    sc = bpy.context.scene
    os.makedirs(out, exist_ok=True)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = not shown(o)
    h = T["height"]
    cloth = bpy.data.objects.get("C_cloth__" + SET)
    mod, wind = simulate(cloth, arm, T) if cloth is not None else (None, None)
    dev = studio(sc, h, quick)
    log(f"look: {dev}")
    cam = bpy.data.objects.new("SkStudio_cam", bpy.data.cameras.new("SkStudio_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.clip_end = 60
    sc.render.film_transparent = False

    only = [x for x in os.environ.get("SK_VIEWS", "").split(",") if x]

    def shoot(name, yaw, pitch=0.0, scale=1.12, centre=.5, res=(640, 1020)):
        if only and name not in only:
            return
        cam.data.ortho_scale = h * scale
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        y, p = math.radians(yaw), math.radians(pitch)
        d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
        cam.location = Vector((0, 0, h * centre)) + d * 8
        cam.rotation_euler = (math.radians(90) - p, 0, math.atan2(d.x, -d.y))
        sc.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)

    def tip():
        if cloth is None:
            return ""
        ev = cloth.evaluated_get(bpy.context.evaluated_depsgraph_get())
        zs = [(ev.matrix_world @ v.co) for v in ev.data.vertices]
        lo = min(zs, key=lambda p: p.z)
        return f"cloth's lowest point ({lo.x:+.3f}, {lo.y:+.3f}, {lo.z:.3f})"

    def run(start, end, at):
        """steps the scene a frame at a time from start (the simulation begins again there); at[frame]() on the way"""
        if mod is not None:
            mod.point_cache.frame_start, mod.point_cache.frame_end = start, end
            mod.settings.quality = mod.settings.quality        # (a changed setting throws the old cache away)
        for F in range(start, end + 1):
            sc.frame_set(F)
            if F in at:
                at[F]()

    def rest_views():
        log("rest: " + tip())
        for name, yaw in (("rest_front", 0), ("rest_q", 35), ("rest_left", 90), ("rest_back", 180), ("rest_qb", 215)):
            shoot(name, yaw, 3)
        shoot("rest_chest", 0, 4, .40, .76, (820, 820))
        shoot("rest_bust", 22, 8, .46, .80, (760, 820))
        shoot("rest_bust_back", 200, 8, .46, .80, (760, 820))
        shoot("rest_cloth", 10, 3, .36, .40, (820, 900))
        shoot("rest_cloth_back", 190, 3, .36, .42, (820, 900))
        shoot("rest_legs", 28, 5, .58, .27, (760, 960))
        shoot("rest_arm", 60, 25, .34, .62, (820, 820))
        for nm_, yaw_ in (("helm_front", 0), ("helm_q", 35), ("helm_side", 90)):
            shoot(nm_, yaw_, 3, .24, .915, (820, 820))
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    if wind is not None:
        blow(wind, (.85, .50, 0.0), float(os.environ.get("SK_BREEZE", "0.9")), float(os.environ.get("SK_GUST", "0.7")))
    run(1, 60, {60: rest_views})
    for clip in clips:
        act = bpy.data.actions.get(clip)
        if not act:
            continue
        arm.animation_data.action = act
        f0, f1 = (int(round(x)) for x in act.frame_range)
        period = max(f1 - f0, 1)
        added = []
        for fc in _fcurves(act):                               # the clip over and over, so the cloth is in its swing
            added.append((fc, fc.modifiers.new('CYCLES')))
        pre = period * max(1, math.ceil(40 / period))
        fast = clip in ("Run", "Walk", "Stroll")
        if wind is not None:
            if fast:                                           # the air of its own speed in the face
                blow(wind, (.10, 1.0, .04), float(os.environ.get("SK_HEADWIND", "1.0")) * {"Run": 1.0, "Walk": .55, "Stroll": .22}[clip], .6)
            else:
                blow(wind, (.85, .50, 0.0), float(os.environ.get("SK_BREEZE", "0.9")), float(os.environ.get("SK_GUST", "0.7")))
        at = {}
        for i, f in enumerate((.25, .75)):
            F = f0 + pre + int(round(period * f))

            def views(clip=clip, i=i):
                log(f"{clip} {i}: " + tip())
                shoot(f"{clip}_{i}", 35, 4)
                shoot(f"{clip}_{i}_side", 90, 0)
                shoot(f"{clip}_{i}_back", 200, 2)
            at[F] = views
        run(f0, f0 + pre + period, at)
        for fc, m_ in added:
            fc.modifiers.remove(m_)
    arm.animation_data.action = bpy.data.actions.get("Idle")
    sc.frame_set(1)
    bpy.data.objects.remove(cam)
