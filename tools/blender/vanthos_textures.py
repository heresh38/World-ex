"""VANTHOS ruin texture sets (numpy painted, seamless; runs as plain python3 or under the bpy shim like the other scripts).

Ground (loaded by src/worlds/vanthos/ground.js, sampled in world space and blended by masks so nothing reads as one colour):
  vr_asphalt   8 m tile: worn asphalt, aggregate, alligator and block cracks with weeds in them, repair patches, potholes
  vr_pavers    4 m tile: broken 1 m sidewalk slabs, sunken / tilted / missing ones, moss and grass in the joints
  vr_dirt      6 m tile: ash-grey soil, gravel, concrete chips and brick fragments, dry drift ripples
  vr_grass     4 m tile: wild grass and weeds over moss, dead straw patches, bare soil gaps
Ruins (embedded in vanthos_ruins.glb by ruins.py; UVs: u = metres / tile width, v = metres above the base / tile height):
  vr_conc      14 x 14 m: weathered precast facade, 4 bays x 4 floors, every window blown out and dark (no glass, no light),
               twisted frames and shards, soot plumes from burnt rooms, rust and water streaks, cracks, spalled concrete
  vr_brick     14.4 x 12 m: soot-black brick walk-up, 4 bays x 3 floors, boarded / burnt / empty openings
  vr_frame     12 x 16 m: a stripped glass tower, 8 mullion modules x 4 floors; dark open floors, a few cracked filthy panes
  vr_slab      4 m: raw broken concrete (slab edges, sheared walls, rubble faces), aggregate, rebar rust stains
  vr_rubble    4 m: packed debris (concrete chunks, brick, dust) for rubble mounds
  vr_rust      2 m: corroded steel with flakes of old paint
  vr_burnt     2 m: fire-gutted car body: char, heat tint, blistered paint, rust
  vr_moss      4 m: moss and grass mat for roofs and the tops of rubble
RGBA cut-outs: vr_ivy (hanging vine curtains), vr_weeds (grass / weed tuft atlas, 2 cells), vr_signs (faded fallen signs).
Every set: <name>_c.jpg colour, _n.jpg tangent normal (OpenGL, +Y up), _m.jpg (G roughness, B metalness, R 0).
No set carries a lit window: the city has been empty for years.
Usage: python3 tools/blender/vanthos_textures.py
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
from downtown_textures import Canvas, noise, grime, jitter, brickfield, font, OUT

TAU = math.tau


def voronoi(H, W, n, seed, ny=None):
    """Tileable jittered-grid voronoi: (F1, F2, cell id); n cells across W (ny down H). Distances in cell units."""
    ny = ny or n
    rg = np.random.RandomState(seed)
    jit = rg.rand(ny, n, 2).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    gx, gy = (xx + .5) / W * n, (yy + .5) / H * ny
    cx, cy = np.floor(gx).astype(np.int32), np.floor(gy).astype(np.int32)
    F1 = np.full((H, W), 9.0, np.float32); F2 = np.full((H, W), 9.0, np.float32); ID = np.zeros((H, W), np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ix, iy = (cx + dx) % n, (cy + dy) % ny
            px = cx + dx + jit[iy, ix, 0]; py = cy + dy + jit[iy, ix, 1]
            d = np.hypot(gx - px, gy - py)
            closer = d < F1
            F2 = np.where(closer, F1, np.minimum(F2, d))
            ID = np.where(closer, iy * n + ix, ID)
            F1 = np.where(closer, d, F1)
    return F1, F2, ID


def blur(a, r):
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255


def wrapblur(a, r):
    """Gaussian blur that wraps around the tile edges (seamless)."""
    H, W = a.shape
    p = int(r * 3) + 2
    t = np.pad(a, p, mode='wrap')
    im = Image.fromarray(np.clip(t * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32)[p:p + H, p:p + W] / 255


def cracks(H, W, n, seed, width=.035, keep=.45, ny=None):
    """Crack network: voronoi cell borders broken up by noise (1 on a crack)."""
    F1, F2, _ = voronoi(H, W, n, seed, ny)
    e = F2 - F1
    line = np.clip(1 - e / width, 0, 1)
    gate = noise(H, W, 1.6, seed + 7) > keep
    wob = noise(H, W, .8, seed + 9)
    return line * gate * (.6 + .4 * wob)


def strokes(W, H, n, seed, col_fn, length=(8, 26), width=(1, 3), upward=False, wrap=True):
    """PIL strokes (grass blades, stems) on an RGBA layer + height layer, wrapped across the tile edges."""
    rg = np.random.RandomState(seed)
    rgb = Image.new('RGB', (W, H)); hgt = Image.new('L', (W, H)); a = Image.new('L', (W, H))
    dr, dh, da = ImageDraw.Draw(rgb), ImageDraw.Draw(hgt), ImageDraw.Draw(a)
    for k in range(n):
        x, y = rg.uniform(0, W), rg.uniform(0, H)
        L = rg.uniform(*length); ang = rg.uniform(-math.pi, math.pi) if not upward else -math.pi / 2 + rg.uniform(-.5, .5)
        x1, y1 = x + math.cos(ang) * L, y + math.sin(ang) * L
        c = col_fn(rg)
        w = int(rg.uniform(*width))
        hv = int(120 + rg.uniform(0, 135))
        for ox in ((-W, 0, W) if wrap else (0,)):
            for oy in ((-H, 0, H) if wrap else (0,)):
                seg = [(x + ox, y + oy), ((x + x1) / 2 + ox + rg.uniform(-2, 2), (y + y1) / 2 + oy), (x1 + ox, y1 + oy)]
                dr.line(seg, fill=tuple(int(v * 255) for v in c), width=w)
                dh.line(seg, fill=hv, width=w); da.line(seg, fill=255, width=w)
    return (np.asarray(rgb, np.float32) / 255, np.asarray(hgt, np.float32) / 255, np.asarray(a, np.float32) / 255)


# ====================================================================== ground
def asphalt():
    S = 1024
    cv = Canvas(S, S, (.07, .069, .072), .9, 0)
    big = noise(S, S, 2.0, 1); mid = noise(S, S, 1.4, 2); fine = noise(S, S, .1, 3)
    cv.c *= (.78 + .4 * big)[..., None] * (.9 + .2 * mid)[..., None]
    # aggregate: pale stones in the binder, polished by years of traffic then left to weather
    stones = np.clip((fine - .62) * 6, 0, 1)
    cv.c = cv.c * (1 - stones[..., None] * .55) + np.array((.24, .235, .23), np.float32) * stones[..., None] * .55
    cv.hg = fine * .35 + stones * .25
    # sun-bleached, dusty areas
    dust = np.clip((noise(S, S, 1.9, 4) - .48) * 2.4, 0, 1)
    cv.c = cv.c * (1 - dust[..., None] * .45) + np.array((.19, .17, .15), np.float32) * dust[..., None] * .45
    # repair patches (darker, smoother) with a hard edge
    rg = np.random.RandomState(5)
    yy, xx = np.mgrid[0:S, 0:S]
    for k in range(3):
        x0, y0, w, h = rg.randint(0, S), rg.randint(0, S), rg.randint(90, 260), rg.randint(70, 200)
        m = (((xx - x0) % S) < w) & (((yy - y0) % S) < h)
        cv.c[m] *= .72; cv.hg[m] += .15; cv.r[m] = .8
        edge = m & ~((((xx - x0 - 3) % S) < w - 6) & (((yy - y0 - 3) % S) < h - 6))
        cv.c[edge] *= .6; cv.hg[edge] -= .3
    # alligator cracking (fine, in fatigue zones) and long block cracks
    al = cracks(S, S, 18, 6, .05, .55)
    zone = np.clip((noise(S, S, 1.7, 7) - .45) * 3, 0, 1)
    al *= zone
    bc = cracks(S, S, 4, 8, .018, .35)
    cr = np.clip(al + bc, 0, 1)
    cv.c *= (1 - cr * .75)[..., None]; cv.hg -= cr * 1.2; cv.r = np.clip(cv.r + cr * .05, 0, 1)
    # weeds and moss growing out of the cracks
    near = wrapblur(cr, 3.0) * 4
    weed = np.clip(near * (noise(S, S, 1.0, 9) > .55) * 1.2, 0, 1) * (noise(S, S, .4, 10) > .5) * .8
    gcol = np.where((noise(S, S, 1.2, 11) > .5)[..., None], np.array((.06, .075, .03), np.float32), np.array((.11, .1, .05), np.float32))
    cv.c = cv.c * (1 - weed[..., None] * .8) + gcol * weed[..., None] * .8
    cv.hg += weed * .6; cv.r = np.clip(cv.r + weed * .05, 0, 1)
    # potholes: broken edge, gravel and grit inside, the odd dark puddle stain
    for k in range(2):
        cx, cy, r = rg.uniform(0, S), rg.uniform(0, S), rg.uniform(40, 80)
        dx = (xx - cx + S / 2) % S - S / 2; dy = (yy - cy + S / 2) % S - S / 2
        d = np.hypot(dx, dy) / r + (noise(S, S, 1.3, 50 + k) - .5) * .9
        hole = d < 1
        rim = (d > .85) & (d < 1.08)
        g2 = noise(S, S, .3, 12 + k)
        cv.c[hole] = (np.array((.2, .18, .15), np.float32) * (.6 + .7 * g2[hole])[:, None])
        cv.hg[hole] = -1.5 + g2[hole] * .5; cv.r[hole] = .95
        cv.c[rim] *= .55; cv.hg[rim] -= .5
    cv.r = np.clip(cv.r - stones * .1, 0, 1)
    cv.save('vr_asphalt', strength=2.2, nsize=(512, 512))


def pavers():
    S = 1024
    cv = Canvas(S, S, (.26, .25, .23), .88, 0)
    yy, xx = np.mgrid[0:S, 0:S]
    n = 4; cs = S // n                                    # 1 m slabs on a 4 m tile
    row, col = yy // cs, xx // cs
    sid = row * n + col
    rg = np.random.RandomState(21)
    tone = rg.uniform(.75, 1.1, n * n).astype(np.float32)[sid]
    tiltx = rg.uniform(-.6, .6, n * n)[sid]; tilty = rg.uniform(-.6, .6, n * n)[sid]
    lx, ly = (xx % cs) / cs - .5, (yy % cs) / cs - .5
    speck = noise(S, S, .25, 22)
    cv.c *= (tone * (.86 + .28 * speck))[..., None]
    cv.hg = speck * .25 + tiltx * lx + tilty * ly
    # cracked slabs
    cr = cracks(S, S, 9, 23, .03, .4) * (rg.rand(n * n) < .6)[sid]
    cv.c *= (1 - cr * .7)[..., None]; cv.hg -= cr
    # joints: dirt, moss and grass
    j = np.minimum(np.minimum(xx % cs, cs - 1 - xx % cs), np.minimum(yy % cs, cs - 1 - yy % cs))
    joint = j < 5
    jg = np.clip(1 - j / 16, 0, 1) * (noise(S, S, 1.0, 24) > .42)
    cv.c[joint] = (.16, .14, .11); cv.hg[joint] = -1.2
    moss = np.array((.2, .25, .09), np.float32)
    cv.c = cv.c * (1 - jg[..., None] * .7) + moss * jg[..., None] * .7
    cv.hg += jg * .5
    # missing slabs: soil and weeds where they were lifted out
    gone = (rg.rand(n * n) < .14)[sid]
    soil = noise(S, S, .5, 25)
    cv.c[gone] = (np.array((.2, .17, .13), np.float32) * (.6 + .8 * soil[gone])[:, None])
    cv.hg[gone] = -1.6 + soil[gone] * .6
    g, gh, ga = strokes(S, S, 1400, 26, lambda r: jitter(r, (.22, .27, .1), .3), (6, 16), (1, 3))
    gm = ga * gone
    cv.c = cv.c * (1 - gm[..., None]) + g * gm[..., None]; cv.hg += gm * gh
    # stains: rust, oil, old soot
    st = np.clip((noise(S, S, 1.8, 27) - .55) * 3, 0, 1)
    cv.c *= (1 - st * .35)[..., None]
    grime(cv, 28, .3, 0)
    cv.save('vr_pavers', strength=2.4, nsize=(512, 512))


def dirt():
    S = 1024
    cv = Canvas(S, S, (.13, .115, .1), .95, 0)
    a, b, c = noise(S, S, 1.9, 31), noise(S, S, 1.0, 32), noise(S, S, .35, 39)
    cv.c *= (.7 + .55 * a)[..., None] * (.85 + .3 * b)[..., None] * (.85 + .3 * c)[..., None]
    ash = np.clip((noise(S, S, 1.7, 33) - .5) * 2.5, 0, 1)
    cv.c = cv.c * (1 - ash[..., None] * .5) + np.array((.2, .195, .19), np.float32) * ash[..., None] * .5
    damp = np.clip((noise(S, S, 1.8, 30) - .55) * 3, 0, 1)
    cv.c *= (1 - damp * .35)[..., None]
    cv.hg = a * .5 + b * .3 + c * .3
    rg = np.random.RandomState(35)
    # gravel at three sizes, irregular (two voronoi fields), mostly the soil's own greys and browns
    for n, keep, k, hscale in ((90, .22, 34, .9), (40, .12, 36, 1.3), (16, .07, 37, 1.6)):
        F1, F2, ID = voronoi(S, S, n, k)
        kp = (rg.rand(n * n) < keep)[ID]
        warp = noise(S, S, .8, k + 100) * .25
        dome = np.clip(1 - (F1 + warp) * 2.4, 0, 1) * kp
        stone = dome > .02
        tone = rg.uniform(.6, 1.6, n * n).astype(np.float32)[ID]
        brick = (rg.rand(n * n) < .12)[ID]
        base = np.where(brick[..., None], np.array((.2, .1, .07), np.float32), np.array((.17, .16, .15), np.float32))
        col = base * (tone * (.6 + .5 * dome))[..., None]
        cv.c[stone] = cv.c[stone] * .25 + col[stone] * .75
        cv.hg = np.where(stone, np.maximum(cv.hg, .4 + dome * hscale), cv.hg)
        cv.r[stone] = .85
    # wind ripples in drifted ash
    rip = (np.sin((np.mgrid[0:S, 0:S][0] / S * 22 + noise(S, S, 1.4, 38) * 6) * TAU) * .5 + .5) * ash
    cv.hg += rip * .3
    cv.save('vr_dirt', strength=2.2, nsize=(512, 512))


def grass():
    S = 1024
    cv = Canvas(S, S, (.12, .14, .06), .95, 0)
    m = noise(S, S, 1.6, 41)
    cv.c *= (.7 + .6 * m)[..., None]
    soil = np.clip((noise(S, S, 1.8, 42) - .62) * 4, 0, 1)
    cv.c = cv.c * (1 - soil[..., None]) + np.array((.17, .14, .11), np.float32) * soil[..., None]
    cv.hg = m * .3
    # layers of blades: green, olive, dead straw
    dry = noise(S, S, 1.7, 43)
    for seed, n, pal in ((44, 9000, (.18, .24, .08)), (45, 7000, (.3, .3, .12)), (46, 5000, (.45, .4, .22))):
        g, gh, ga = strokes(S, S, n, seed, lambda r, pal=pal: jitter(r, pal, .25), (8, 28), (1, 3))
        if seed == 46:
            ga = ga * (dry > .55)
        cv.c = cv.c * (1 - ga[..., None]) + g * ga[..., None]
        cv.hg = np.maximum(cv.hg, gh * ga)
    # small weeds with broader leaves
    rg = np.random.RandomState(47)
    im = Image.fromarray((np.clip(cv.c, 0, 1) * 255).astype(np.uint8)); dr = ImageDraw.Draw(im)
    hm = Image.fromarray((np.clip(cv.hg, 0, 1) * 255).astype(np.uint8)); dh = ImageDraw.Draw(hm)
    for k in range(120):
        cx, cy = rg.uniform(0, S), rg.uniform(0, S)
        c = tuple(int(v * 255) for v in jitter(rg, (.2, .3, .1), .3))
        for l in range(rg.randint(4, 8)):
            a = rg.uniform(0, TAU); L = rg.uniform(10, 22)
            pts = [(cx, cy), (cx + math.cos(a - .3) * L * .6, cy + math.sin(a - .3) * L * .6), (cx + math.cos(a) * L, cy + math.sin(a) * L),
                   (cx + math.cos(a + .3) * L * .6, cy + math.sin(a + .3) * L * .6)]
            dr.polygon(pts, fill=c); dh.polygon(pts, fill=220)
    cv.c = np.asarray(im, np.float32) / 255; cv.hg = np.asarray(hm, np.float32) / 255
    cv.c = cv.c ** 1.0
    cv.save('vr_grass', strength=2.6, nsize=(512, 512))


def moss():
    S = 512
    cv = Canvas(S, S, (.14, .17, .06), .95, 0)
    a, b = noise(S, S, 1.4, 51), noise(S, S, .4, 52)
    cv.c *= (.6 + .7 * a)[..., None] * (.85 + .3 * b)[..., None]
    yellow = np.clip((noise(S, S, 1.6, 53) - .55) * 3, 0, 1)
    cv.c = cv.c * (1 - yellow[..., None] * .5) + np.array((.3, .3, .1), np.float32) * yellow[..., None] * .5
    cv.hg = a * .6 + b * .5
    g, gh, ga = strokes(S, S, 2500, 54, lambda r: jitter(r, (.24, .27, .1), .3), (4, 12), (1, 2))
    cv.c = cv.c * (1 - ga[..., None] * .8) + g * ga[..., None] * .8; cv.hg += ga * .4
    cv.save('vr_moss', strength=2.0, nsize=(256, 256))


# ====================================================================== ruin surfaces
def window_hole(cv, rg, x0, y0, x1, y1, kind):
    """A blown-out window: dark interior with a lighter deep reveal at the top; frames, shards or boarding by kind."""
    w, h = x1 - x0, y1 - y0
    yy = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    inside = np.array((.025, .024, .024), np.float32) * (1 + yy[..., None] * 1.4)      # the floor inside catches a little light
    cv.c[y0:y1, x0:x1] = inside
    cv.c[y0:y0 + max(2, h // 9), x0:x1] = (.09, .085, .08)                             # ceiling slab edge inside
    cv.hg[y0:y1, x0:x1] = -1.4; cv.r[y0:y1, x0:x1] = .95; cv.m[y0:y1, x0:x1] = 0
    # reveal (the wall thickness) on the left and top
    cv.rect(x0, y0, x0 + 3, y1, col=(.2, .19, .18), h=-.6)
    if kind == 'frame':                                     # twisted frame, a couple of shards hanging in it
        fc = (.16, .16, .17)
        cv.rect(x0, y0, x1, y0 + 3, col=fc, h=-.3, rough=.5, metal=.7)
        cv.rect(x0, y1 - 3, x1, y1, col=fc, h=-.3, rough=.5, metal=.7)
        mx = x0 + int(w * rg.uniform(.35, .65))
        cv.rect(mx - 1, y0, mx + 2, y1, col=fc, h=-.3, rough=.5, metal=.7)
        for k in range(rg.randint(1, 3)):
            sx = rg.randint(x0 + 3, x1 - 12); sw = rg.randint(6, 18); sh = rg.randint(8, max(9, h // 2))
            top = rg.rand() < .6
            ys = np.arange(sh)
            for i, yv in enumerate(ys):
                ww = int(sw * (1 - i / sh) if top else sw * i / sh)
                yv2 = y0 + 3 + yv if top else y1 - 3 - sh + yv
                if 0 <= yv2 < cv.h:
                    cv.c[yv2, sx:sx + ww] = (.18, .21, .22); cv.r[yv2, sx:sx + ww] = .08; cv.m[yv2, sx:sx + ww] = .5
    elif kind == 'board':                                   # boarded up long ago, the planks grey and split
        base = jitter(rg, (.33, .3, .26), .15)
        g = noise(h, w, 1.0, int(rg.randint(9999)), ax=.12, ay=5)
        cv.c[y0:y1, x0:x1] = np.array(base, np.float32) * (.7 + .45 * g)[..., None]
        cv.hg[y0:y1, x0:x1] = -.4; cv.r[y0:y1, x0:x1] = .9
        for k in range(rg.randint(0, 3)):                   # missing planks
            py = rg.randint(y0, y1 - 8)
            cv.c[py:py + rg.randint(5, 12), x0:x1] = (.03, .03, .03); cv.hg[py:py + 8, x0:x1] = -1.4
    elif kind == 'spall':                                   # blast hole: the wall around the window is gone too
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        R = max(w, h) * rg.uniform(.65, .85)
        Y, X = np.mgrid[max(0, int(cy - R)):min(cv.h, int(cy + R)), max(0, int(cx - R)):min(cv.w, int(cx + R))]
        a = np.arctan2(Y - cy, X - cx); ph = rg.rand(3) * 6
        d = np.hypot((Y - cy) * 1.2, X - cx) / (R * (1 + .12 * np.sin(a * 3 + ph[0]) + .07 * np.sin(a * 7 + ph[1]) + .04 * np.sin(a * 19 + ph[2])))
        hole = d < 1; rim = (d >= 1) & (d < 1.25)
        cv.c[Y[hole], X[hole]] = (.03, .028, .027); cv.hg[Y[hole], X[hole]] = -1.4
        cv.c[Y[rim], X[rim]] *= np.array((.62, .6, .58), np.float32); cv.hg[Y[rim], X[rim]] -= .5
        for k in range(5):                                  # exposed rebar across the hole
            ry = int(cy - R * .6 + k * R * .3)
            if Y[0, 0] <= ry < Y[-1, 0]:
                xr = X[0][hole[ry - Y[0, 0]]]
                if len(xr):
                    cv.c[ry:ry + 2, xr.min():xr.max()] = (.3, .16, .08); cv.hg[ry:ry + 2, xr.min():xr.max()] = .2; cv.m[ry:ry + 2, xr.min():xr.max()] = .3


def soot(cv, x0, y0, x1, y1, k=.85):
    """Scorch plume rising from an opening (row 0 is the top of the image)."""
    cx, w = (x0 + x1) / 2, (x1 - x0)
    top = max(0, int(y0 - w * 2.2))
    Y, X = np.mgrid[top:y1, max(0, int(cx - w * 1.4)):min(cv.w, int(cx + w * 1.4))]
    up = np.clip((y0 + (y1 - y0) * .3 - Y) / (w * 2.2), 0, 1)                    # 0 at the opening, 1 at the top of the plume
    spread = w * (.45 + up * .9)
    f = np.exp(-((X - cx) / spread) ** 2) * (1 - up) ** 1.2 * (Y < y1)
    cv.c[Y, X] *= (1 - np.clip(f * k, 0, .92))[..., None]
    cv.r[Y, X] = np.clip(cv.r[Y, X] + f * .1, 0, 1)


def streaks(cv, seed, amount=.35, rust=.25):
    H, W = cv.h, cv.w
    s = noise(H, W, 1.3, seed, ax=.25, ay=9)               # long vertical runs (smooth along y)
    cv.c *= (1 - amount * np.clip((s - .5) * 2.6, 0, 1))[..., None]
    r = np.clip((noise(H, W, 1.1, seed + 1, ax=.3, ay=12) - .7) * 4, 0, 1) * rust
    cv.c = cv.c * (1 - r[..., None]) + np.array((.3, .15, .06), np.float32) * r[..., None]


def crack_lines(cv, rg, n, seed):
    c = cracks(cv.h, cv.w, 5, seed, .02, .5)
    cv.c *= (1 - c * .6)[..., None]; cv.hg -= c * .8


def conc():
    S, B, F = 1024, 4, 4
    cw, ch = S // B, S // F                           # 3.5 m bays, 3.5 m floors
    cv = Canvas(S, S, (.3, .29, .27), .9, 0)
    n = noise(S, S, 1.6, 61); f = noise(S, S, .3, 62)
    cv.c *= (.8 + .3 * n)[..., None] * (.92 + .16 * f)[..., None]
    cv.hg = f * .3
    rg = np.random.RandomState(63)
    wins = []
    for fl in range(F):
        y0 = fl * ch
        cv.rect(0, y0 + ch - 34, S, y0 + ch - 30, col=(.2, .19, .18), h=-.5)          # panel joint at the slab
        cv.rect(0, y0 + ch - 30, S, y0 + ch, dh=.25)                                     # spandrel band, slightly proud
        burnt_floor = rg.rand() < .35
        for b in range(B):
            x0 = b * cw
            cv.rect(x0, y0, x0 + 3, y0 + ch, col=(.2, .19, .18), h=-.4)              # vertical joint
            wx0, wx1 = x0 + int(cw * .16), x0 + int(cw * .84)
            wy0, wy1 = y0 + int(ch * .18), y0 + int(ch * .66)
            k = rg.rand()
            kind = 'spall' if k < .12 else 'board' if k < .2 else 'frame' if k < .55 else 'empty'
            # sill with moss on it
            cv.rect(wx0 - 6, wy1, wx1 + 6, wy1 + 7, col=(.26, .25, .23), h=.6)
            cv.rect(wx0 - 4, wy1 - 1, wx1 + 4, wy1 + 2, col=(.1, .12, .05), h=.8)
            wins.append((wx0, wy0, wx1, wy1, kind, (burnt_floor and rg.rand() < .7) or rg.rand() < .12))
    # weathering first (rain runs from the sills), then the openings stay dark and clean, then soot over everything
    streaks(cv, 64, .4, .3)
    crack_lines(cv, rg, 6, 65)
    sp = np.clip((noise(S, S, 1.5, 66) - .7) * 5, 0, 1)
    cv.c = cv.c * (1 - sp[..., None] * .4) + np.array((.18, .17, .16), np.float32) * sp[..., None] * .4; cv.hg -= sp * .5
    grime(cv, 67, .3, .2)
    for wx0, wy0, wx1, wy1, kind, burn in wins:
        window_hole(cv, rg, wx0, wy0, wx1, wy1, kind)
    for wx0, wy0, wx1, wy1, kind, burn in wins:
        if burn:
            soot(cv, wx0, wy0, wx1, wy1, .75 + rg.rand() * .2)
    cv.save('vr_conc', strength=2.4, nsize=(512, 512))


def brick():
    S, B, F = 1024, 4, 3                              # 3.6 m bays, 4 m floors
    W, H = S, int(S * 12 / 14.4)
    cv = Canvas(W, H)
    brickfield(cv, 0, 0, W, H, (.2, .11, .08), 71, bw=15, bh=5, mortar=(.2, .19, .17))
    cw, ch = W // B, H // F
    rg = np.random.RandomState(72)
    wins = []
    for fl in range(F):
        y0 = fl * ch
        cv.rect(0, y0 + ch - 10, W, y0 + ch - 4, col=(.22, .2, .18), h=.5)           # string course
        burnt = rg.rand() < .4
        for b in range(B):
            x0 = b * cw
            wx0, wx1 = x0 + int(cw * .3), x0 + int(cw * .7)
            wy0, wy1 = y0 + int(ch * .22), y0 + int(ch * .78)
            cv.rect(wx0 - 8, wy0 - 12, wx1 + 8, wy0, col=(.24, .22, .2), h=.4)          # lintel
            cv.rect(wx0 - 6, wy1, wx1 + 6, wy1 + 6, col=(.24, .22, .2), h=.5)
            k = rg.rand()
            wins.append((wx0, wy0, wx1, wy1, 'board' if k < .25 else 'frame' if k < .5 else 'empty', burnt or rg.rand() < .15))
    streaks(cv, 73, .35, .15)
    crack_lines(cv, rg, 4, 74)
    grime(cv, 75, .35, .25)
    for wx0, wy0, wx1, wy1, kind, burn in wins:
        window_hole(cv, rg, wx0, wy0, wx1, wy1, kind)
    for wx0, wy0, wx1, wy1, kind, burn in wins:
        if burn:
            soot(cv, wx0, wy0, wx1, wy1, .85)
    cv.c *= .9
    cv.save('vr_brick', strength=2.2, nsize=(512, 512))


def frame():
    W, H, B, F = 768, 1024, 8, 4                      # 1.5 m modules, 4 m floors
    cw, ch = W // B, H // F
    cv = Canvas(W, H, (.02, .02, .022), .95, 0)
    rg = np.random.RandomState(81)
    yy = np.mgrid[0:H, 0:W][0]
    for fl in range(F):
        y0 = fl * ch
        # inside: the floor plate seen through the opening, a column now and then
        cv.c[y0:y0 + ch] *= (1 + ((yy[y0:y0 + ch] - y0) / ch) * 1.6)[..., None]
        for b in range(B):
            x0 = b * cw
            if rg.rand() < .18:
                cv.rect(x0 + cw // 2 - 8, y0, x0 + cw // 2 + 8, y0 + ch, col=(.06, .06, .06), h=-1)
            pane = rg.rand()
            if pane < .22:                            # a pane left: filthy, cracked, a little reflective
                cv.rect(x0 + 4, y0 + 4, x0 + cw - 4, y0 + ch - 44, col=jitter(rg, (.06, .065, .068), .2), h=-.4, rough=.25, metal=.6)
                c = cracks(ch - 48, cw - 8, 3, int(rg.randint(9999)), .04, .2)
                sub = cv.c[y0 + 4:y0 + ch - 44, x0 + 4:x0 + cw - 4]
                sub *= (1 + c * .6)[..., None]
                cv.r[y0 + 4:y0 + ch - 44, x0 + 4:x0 + cw - 4] += c * .4
            else:
                cv.hg[y0 + 4:y0 + ch - 44, x0 + 4:x0 + cw - 4] = -1.4
            # mullions (a few bent or gone)
            if rg.rand() > .12:
                cv.rect(x0, y0, x0 + 5, y0 + ch - 40, col=(.2, .2, .21), h=.6, rough=.5, metal=.85)
        # slab edge band: concrete with soot
        band = jitter(rg, (.25, .24, .22), .1)
        cv.rect(0, y0 + ch - 40, W, y0 + ch, col=band, h=.8, rough=.9, metal=0)
        if rg.rand() < .5:
            sx = rg.randint(0, W - 200)
            soot(cv, sx, y0 + ch - 60, sx + 200, y0 + ch - 40, .7)
    streaks(cv, 82, .3, 0)
    grime(cv, 83, .25, .2)
    cv.save('vr_frame', strength=2.0, nsize=(384, 512))


def slab():
    S = 512
    cv = Canvas(S, S, (.27, .26, .24), .92, 0)
    a, b = noise(S, S, 1.5, 91), noise(S, S, .15, 92)
    cv.c *= (.75 + .35 * a)[..., None] * (.85 + .3 * b)[..., None]
    agg = np.clip((b - .6) * 5, 0, 1)
    cv.c = cv.c * (1 - agg[..., None] * .4) + np.array((.36, .35, .33), np.float32) * agg[..., None] * .4
    cv.hg = a * .5 + b * .5
    c = cracks(S, S, 4, 93, .03, .35)
    cv.c *= (1 - c * .7)[..., None]; cv.hg -= c
    rust = np.clip((noise(S, S, 1.2, 94, ax=.3, ay=8) - .66) * 4, 0, 1)
    cv.c = cv.c * (1 - rust[..., None] * .55) + np.array((.32, .17, .07), np.float32) * rust[..., None] * .55
    sootm = np.clip((noise(S, S, 1.9, 95) - .5) * 2.5, 0, 1)
    cv.c *= (1 - sootm * .5)[..., None]
    cv.save('vr_slab', strength=2.4, nsize=(256, 256))


def rubble():
    S = 1024
    cv = Canvas(S, S, (.08, .075, .07), .95, 0)          # dust and grit between the pieces
    rg = np.random.RandomState(103)
    cv.hg = noise(S, S, 1.2, 107) * .3
    pal = np.array([(.27, .26, .24), (.22, .21, .2), (.3, .29, .26), (.19, .1, .07), (.16, .155, .15), (.25, .24, .22), (.12, .115, .11)], np.float32)
    # chunks at three scales; each scale fills only part of the tile so larger pieces lie on a bed of smaller ones
    for n, keep, seed, hs in ((60, .8, 102, .8), (24, .55, 101, 1.4), (9, .35, 108, 2.0)):
        F1, F2, ID = voronoi(S, S, n, seed)
        kp = (rg.rand(n * n) < keep)[ID]
        warp = noise(S, S, 1.0, seed + 50) * .3
        inner = np.clip(1 - (F2 - F1) / .12, 0, 1)                 # 1 at the chunk edge
        dome = np.clip(1 - (F1 + warp) * 1.2, 0, 1)
        m = kp & (inner < .85)
        tone = rg.uniform(.7, 1.25, n * n).astype(np.float32)[ID]
        pick = rg.choice(7, n * n, p=[.24, .2, .18, .07, .12, .12, .07])
        col = pal[pick[ID]] * (tone * (.75 + .35 * dome))[..., None]
        cv.c[m] = col[m]
        cv.hg[m] = .3 + dome[m] * hs + (n == 9) * .5
        cv.c[m] *= (1 - inner[m] * .5)[:, None]
    f = noise(S, S, .2, 104); cv.c *= (.85 + .3 * f)[..., None]; cv.hg += f * .15
    dust = np.clip((noise(S, S, 1.6, 105) - .5) * 2.5, 0, 1)
    cv.c = cv.c * (1 - dust[..., None] * .5) + np.array((.21, .2, .18), np.float32) * dust[..., None] * .5
    sootm = np.clip((noise(S, S, 1.8, 106) - .58) * 3, 0, 1)
    cv.c *= (1 - sootm * .55)[..., None]
    # rebar and pipe bits
    for k in range(14):
        x, y, a, L = rg.uniform(0, S), rg.uniform(0, S), rg.uniform(0, TAU), rg.uniform(30, 90)
        im = Image.new('L', (S, S)); ImageDraw.Draw(im).line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=255, width=3)
        m = np.asarray(im) > 0
        cv.c[m] = (.2, .1, .05); cv.hg[m] = 2.4; cv.m[m] = .4; cv.r[m] = .7
    cv.save('vr_rubble', strength=2.6, nsize=(512, 512))


def rust():
    S = 512
    cv = Canvas(S, S, (.19, .09, .045), .85, .3)
    a, b = noise(S, S, 1.5, 111), noise(S, S, .3, 112)
    cv.c *= (.6 + .7 * a)[..., None] * (.8 + .4 * b)[..., None]
    cv.hg = a * .4 + b * .4
    paint = (noise(S, S, 1.7, 113) * .7 + noise(S, S, .6, 115) * .3) > .56
    pc = np.array((.16, .18, .17), np.float32)
    cv.c[paint] = pc * (.8 + .3 * b[paint])[:, None]; cv.hg[paint] += .4; cv.m[paint] = .1; cv.r[paint] = .7
    pit = np.clip((b - .7) * 6, 0, 1)
    cv.c *= (1 - pit * .5)[..., None]; cv.hg -= pit * .6
    streaks(cv, 114, .3, .1)
    cv.save('vr_rust', strength=2.0, nsize=(256, 256))


def burnt():
    S = 512
    cv = Canvas(S, S, (.06, .055, .05), .9, .4)
    a, b = noise(S, S, 1.6, 121), noise(S, S, .25, 122)
    cv.c *= (.6 + .8 * a)[..., None]
    cv.hg = a * .3 + b * .5
    rust_m = np.clip((noise(S, S, 1.5, 123) - .45) * 2.4, 0, 1)
    cv.c = cv.c * (1 - rust_m[..., None]) + np.array((.27, .13, .06), np.float32) * (.6 + .6 * b)[..., None] * rust_m[..., None]
    cv.m = np.clip(.5 - rust_m * .3, 0, 1)
    # heat tint (straw / blue) at the edges of the char and blistered paint remnants
    heat = np.clip(1 - np.abs(rust_m - .5) * 6, 0, 1) * (noise(S, S, 1.2, 124) > .5)
    cv.c = cv.c * (1 - heat[..., None] * .4) + np.array((.22, .2, .28), np.float32) * heat[..., None] * .4
    blis = (noise(S, S, 1.8, 125) > .66) & (b > .45)
    cv.c[blis] = np.array((.42, .4, .37), np.float32) * (.7 + .4 * b[blis])[:, None]; cv.hg[blis] += .7; cv.r[blis] = .8; cv.m[blis] = 0
    cv.save('vr_burnt', strength=2.4, nsize=(256, 256))


# ====================================================================== cut-outs
def save_rgba(name, rgb, a, size=None):
    arr = np.dstack([np.clip(rgb, 0, 1) ** (1 / 2.2), a[..., None]])
    im = Image.fromarray(np.clip(arr * 255 + .5, 0, 255).astype(np.uint8), 'RGBA')
    if size:
        im = im.resize(size, Image.LANCZOS)
    im.save(os.path.join(OUT, name + '.png'), optimize=True)
    print('[texture] %s.png' % name)


def leaf(dr, x, y, a, s, col):
    pts = []
    for t in range(9):
        u = t / 8
        w = math.sin(u * math.pi) * .5
        pts.append((u, w))
    poly = [(x + math.cos(a) * u * s - math.sin(a) * w * s, y + math.sin(a) * u * s + math.cos(a) * w * s) for u, w in pts]
    poly += [(x + math.cos(a) * u * s + math.sin(a) * w * s, y + math.sin(a) * u * s - math.cos(a) * w * s) for u, w in reversed(pts)]
    dr.polygon(poly, fill=col)


def ivy():
    """Hanging vine curtain (512 x 1024 = 2 x 4 m): stems falling from the top edge, dense leaves near the top."""
    W, H = 1024, 2048
    rgb = Image.new('RGB', (W, H), (40, 52, 20)); a = Image.new('L', (W, H), 0)
    dr, da = ImageDraw.Draw(rgb), ImageDraw.Draw(a)
    rg = np.random.RandomState(131)
    for k in range(46):
        x = rg.uniform(20, W - 20); y = 0; L = rg.uniform(.35, 1.0) * H
        ang = math.pi / 2
        pts = [(x, y)]
        while y < L:
            ang += rg.uniform(-.25, .25); ang = min(max(ang, math.pi / 2 - .5), math.pi / 2 + .5)
            x += math.cos(ang) * 14; y += math.sin(ang) * 14; pts.append((x, y))
        dr.line(pts, fill=(52, 46, 30), width=4); da.line(pts, fill=255, width=4)
        for i, (px, py) in enumerate(pts):
            dens = 1 - py / H * .8
            for j in range(int(3 * dens) + (1 if rg.rand() < dens else 0)):
                c = tuple(int(v * 255) for v in jitter(rg, (.13, .2, .06) if rg.rand() < .7 else (.22, .25, .08), .3))
                aa = rg.uniform(0, TAU); s = rg.uniform(18, 34)
                leaf(dr, px, py, aa, s, c); leaf(da, px, py, aa, s, 255)
    # leaf veins / shading by noise
    c = np.asarray(rgb, np.float32) / 255
    c = c ** 2.2 * (.75 + .5 * noise(H, W, 1.2, 132))[..., None]
    save_rgba('vr_ivy', c, np.asarray(a, np.float32) / 255, size=(512, 1024))


def weeds():
    """Tuft atlas 1024 x 512: left cell tall grass, right cell broad weeds; bases at the bottom edge."""
    W, H = 1024, 512
    rgb = Image.new('RGB', (W, H), (50, 60, 25)); a = Image.new('L', (W, H), 0)
    dr, da = ImageDraw.Draw(rgb), ImageDraw.Draw(a)
    rg = np.random.RandomState(141)
    for k in range(260):                                  # grass blades
        x = rg.uniform(30, 482); h = rg.uniform(.35, .98) * H; lean = rg.uniform(-.35, .35)
        c = tuple(int(v * 255) for v in jitter(rg, (.2, .26, .08) if rg.rand() < .65 else (.42, .38, .18), .25))
        pts = [(x + lean * (t / 6) ** 2 * h, H - t / 6 * h) for t in range(7)]
        w0 = rg.uniform(3, 7)
        for i in range(6):
            dr.line([pts[i], pts[i + 1]], fill=c, width=max(1, int(w0 * (1 - i / 6)))); da.line([pts[i], pts[i + 1]], fill=255, width=max(1, int(w0 * (1 - i / 6))))
    for k in range(18):                                   # weeds: a stalk with broad leaves
        x = rg.uniform(560, 990); h = rg.uniform(.4, .95) * H
        c = tuple(int(v * 255) for v in jitter(rg, (.16, .24, .07), .3))
        dr.line([(x, H), (x + rg.uniform(-20, 20), H - h)], fill=(60, 70, 30), width=5); da.line([(x, H), (x, H - h)], fill=255, width=5)
        for j in range(9):
            y = H - h * (j + 1) / 10; aa = math.pi + rg.uniform(-.6, .6) if j % 2 else rg.uniform(-.6, .6); aa -= .5
            s = rg.uniform(40, 90) * (1 - j / 14)
            leaf(dr, x, y, aa, s, c); leaf(da, x, y, aa, s, 255)
    c = (np.asarray(rgb, np.float32) / 255) ** 2.2
    yy = np.mgrid[0:H, 0:W][0] / H
    c *= (.45 + .55 * (1 - yy))[..., None]                 # darker at the base (ground occlusion)
    save_rgba('vr_weeds', c, np.asarray(a, np.float32) / 255, size=(512, 256))


def signs():
    """Faded fallen street signs (512 x 512 atlas, 4 rows): generic words only."""
    W, H = 1024, 1024
    im = Image.new('RGB', (W, H), (40, 40, 40)); dr = ImageDraw.Draw(im)
    rows = [((150, 40, 32), 'HOTEL', (210, 200, 180)), ((30, 70, 120), 'TRANSIT  4', (220, 220, 210)),
            ((200, 160, 40), 'EVACUATION ROUTE', (30, 30, 30)), ((60, 90, 60), 'PHARMACY', (220, 225, 210))]
    for i, (bg, txt, fg) in enumerate(rows):
        y0 = i * 256
        dr.rectangle([0, y0, W, y0 + 255], fill=bg)
        dr.rectangle([10, y0 + 10, W - 10, y0 + 245], outline=fg, width=6)
        f = font(120 if len(txt) < 12 else 84)
        tw = dr.textlength(txt, font=f)
        dr.text(((W - tw) / 2, y0 + 128), txt, fill=fg, font=f, anchor='lm')
    c = np.asarray(im, np.float32) / 255
    c = c ** 2.2
    fade = noise(H, W, 1.6, 151)
    c = c * (.5 + .5 * fade)[..., None] + np.array((.2, .19, .17), np.float32) * (.5 - .5 * fade)[..., None]
    r = np.clip((noise(H, W, 1.3, 152, ax=6, ay=.4) - .55) * 3, 0, 1)
    c = c * (1 - r[..., None] * .7) + np.array((.3, .15, .06), np.float32) * r[..., None] * .7
    c *= (.7 + .3 * noise(H, W, .3, 153))[..., None]
    Image.fromarray(np.clip(c ** (1 / 2.2) * 255, 0, 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, 'vr_signs_c.jpg'), quality=86)
    print('[texture] vr_signs')


def main(only=None):
    jobs = dict(asphalt=asphalt, pavers=pavers, dirt=dirt, grass=grass, moss=moss, conc=conc, brick=brick, frame=frame, slab=slab,
                rubble=rubble, rust=rust, burnt=burnt, ivy=ivy, weeds=weeds, signs=signs)
    for k, fn in jobs.items():
        if not only or k in only:
            fn()


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    main(set(args) if args else None)
