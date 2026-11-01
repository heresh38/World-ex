"""Texture sets for the Shellbreak arena map Brennick Works (arena.py): a ruined arms foundry yard on Earth's outskirts.

numpy painted (the Canvas / noise / grime helpers of downtown_textures.py), no Blender needed; runs under the bpy shim
too. Every set tiles; arena.py maps them with world-scale UVs (u = metres / tile size). Outputs in assets/textures:
  ar_<name>_c.jpg  colour, ar_<name>_n.jpg tangent normal (+Y up), ar_<name>_m.jpg  G roughness, B metalness
Sets (tile size): brick 2 m (aged red brick, soot, plaster scars), conc 4 m (board-formed concrete, tie holes, rain
streaks), floor 8 m (cracked yard slabs, joints, oil, gravel), corr 2 m (ribbed sheet steel, neutral paint for tints,
rust runs), steel 1 m (painted steel, chips and rust), plate 1 m (diamond tread plate), wood 1 m (crate / pallet boards),
hazard 1 m (worn yellow-black stripes); RGBA cut-outs ar_window.png (steel-framed factory glazing, broken panes) and
ar_signs.png (painted signage atlas, 4 x 4 cells, our own invented names only).
Usage: python3 tools/blender/arena_textures.py
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from downtown_textures import Canvas, noise, grime, font, OUT   # noqa: E402


def lerp(a, b, t):
    return a + (b - a) * t


def blotch(cv, seed, col, amount, thr=.55, beta=1.9, sharp=3.0):
    """mix a colour in where low-frequency noise is above thr (stains, rust patches, plaster)."""
    n = noise(cv.h, cv.w, beta, seed)
    k = np.clip((n - thr) * sharp, 0, 1) * amount
    cv.c = cv.c * (1 - k[..., None]) + np.array(col, np.float32) * k[..., None]
    return k


# ---------------------------------------------------------------- brick: 2 m tile, 8 bricks x 24 courses
def brick():
    W = 1024
    cv = Canvas(W, W, (.5, .44, .4), .88, 0)
    rg = np.random.RandomState(7)
    yy, xx = np.mgrid[0:W, 0:W]
    cw, bh = W // 8, W // 24                      # 25 cm bricks, 8.3 cm courses
    row = yy // bh
    xs = (xx + (row % 2) * (cw // 2)) % W
    ids = (row * 37 + xs // cw * 11) % 997
    pal = np.array([(.42, .14, .09), (.5, .19, .12), (.36, .12, .08), (.55, .25, .16), (.3, .1, .07), (.46, .2, .14)], np.float32)
    base = pal[rg.randint(0, len(pal), 997)][ids]
    tone = rg.uniform(.8, 1.15, 997).astype(np.float32)[ids]
    speck = noise(W, W, .4, 8)
    cv.c = base * (tone * (.88 + .24 * speck))[..., None]
    mort = ((yy % bh) < 3) | ((xs % cw) < 3)
    cv.c[mort] = (.42, .4, .36)
    face = noise(W, W, .9, 9)
    cv.hg = np.where(mort, -1.0, 0.0).astype(np.float32) + face * .35
    # chipped brick edges and spalled faces
    chip = noise(W, W, .6, 10) > .78
    cv.c[chip & ~mort] *= .72; cv.hg[chip & ~mort] -= .4
    # plaster scars and soot
    blotch(cv, 11, (.62, .6, .56), .8, .72, 2.0, 8)
    blotch(cv, 12, (.07, .06, .06), .5, .55, 1.7, 2.5)
    grime(cv, 13, .25, .3)
    cv.r[mort] = .95
    cv.save('ar_brick', strength=2.2, nsize=(512, 512))


# ---------------------------------------------------------------- board-formed concrete: 4 m tile
def conc():
    W = 1024
    cv = Canvas(W, W, (.5, .49, .46), .9, 0)
    n = noise(W, W, 1.5, 21); cv.c *= (.82 + .3 * n)[..., None]
    board = noise(W, W, 1.0, 22, ax=.08, ay=7)
    cv.c *= (.93 + .1 * board)[..., None]; cv.hg = board * .35
    yy, xx = np.mgrid[0:W, 0:W]
    for y in range(0, W, 32):                     # 12.5 cm boards
        cv.rect(0, y, W, y + 1, col=(.4, .39, .37), dh=-.25)
    for x in range(0, W, 256):                    # 1 m form panels
        cv.rect(x, 0, x + 3, W, col=(.36, .35, .33), dh=-.6)
    for y in range(64, W, 256):
        for x in range(128, W, 256):
            m = (xx - x) ** 2 + (yy - y) ** 2 < 36
            cv.mask(m, col=(.2, .2, .2), h=-1.2)
    blotch(cv, 23, (.3, .3, .28), .5, .58, 1.8, 3)
    blotch(cv, 24, (.38, .26, .18), .35, .7, 1.6, 4)       # rust bleed
    rain = noise(W, W, 1.3, 26, ax=.2, ay=9)                 # vertical rain streaks
    cv.c *= (1 - .35 * np.clip((rain - .5) * 2.5, 0, 1))[..., None]
    grime(cv, 25, .2, 0)
    cv.save('ar_conc', strength=1.8, nsize=(512, 512))


# ---------------------------------------------------------------- yard floor: 8 m tile, 2 x 2 slabs
def floor():
    W = 1024
    cv = Canvas(W, W, (.42, .41, .39), .9, 0)
    rg = np.random.RandomState(31)
    g = noise(W, W, .25, 32); big = noise(W, W, 1.9, 33)
    cv.c *= ((.84 + .22 * g) * (.86 + .26 * big))[..., None]
    cv.hg = g * .4
    yy, xx = np.mgrid[0:W, 0:W]
    slab = W // 2
    tone = np.array([[1.0, .93], [.96, 1.04]], np.float32)[(yy // slab) % 2, (xx // slab) % 2]
    cv.c *= tone[..., None]
    j = ((yy % slab) < 4) | ((xx % slab) < 4)
    cv.c[j] = (.2, .19, .18); cv.hg[j] = -1.2; cv.r[j] = 1
    # cracks: random walks from slab edges
    img = Image.new('L', (W, W), 0); d = ImageDraw.Draw(img)
    for k in range(26):
        x, y = rg.uniform(0, W), rg.uniform(0, W); a = rg.uniform(0, 6.28)
        pts = [(x, y)]
        for s in range(rg.randint(10, 40)):
            a += rg.normal(0, .5); x += math.cos(a) * 9; y += math.sin(a) * 9
            pts.append((x % W, y % W))
        for p0, p1 in zip(pts, pts[1:]):
            if abs(p0[0] - p1[0]) < 50 and abs(p0[1] - p1[1]) < 50:
                d.line([p0, p1], fill=255, width=2)
    cr = np.asarray(img, np.float32) / 255
    cv.c *= (1 - .65 * cr)[..., None]; cv.hg -= cr * .9
    # oil stains, puddle-dark patches, faded yellow lane paint
    k = blotch(cv, 34, (.08, .08, .08), .7, .7, 2.0, 3)
    cv.r -= k * .45
    paint = (np.abs(((xx + 140) % W) - 40) < 10) & (noise(W, W, 1.2, 35) > .35)
    cv.c[paint] = cv.c[paint] * .4 + np.array((.72, .58, .18), np.float32) * .6
    grime(cv, 36, .15, 0)
    cv.r = np.clip(cv.r, .3, 1)
    cv.save('ar_floor', strength=1.6, nsize=(512, 512))


# ---------------------------------------------------------------- corrugated sheet: 2 m tile, neutral paint
def corr():
    W = 512
    cv = Canvas(W, W, (.72, .72, .7), .6, .35)
    yy, xx = np.mgrid[0:W, 0:W]
    rib = np.sin(xx / W * 2 * math.pi * 10) * .5 + .5           # 20 cm pitch
    cv.hg = rib * 2.2
    cv.c *= (.8 + .25 * rib)[..., None]
    n = noise(W, W, 1.4, 41); cv.c *= (.88 + .2 * n)[..., None]
    rust = noise(W, W, 1.3, 42, ax=.25, ay=8)                    # vertical rust runs
    k = np.clip((rust - .55) * 3, 0, 1) * .8
    cv.c = cv.c * (1 - k[..., None]) + np.array((.32, .14, .06), np.float32) * k[..., None]
    cv.r = .55 + k * .4; cv.m = .35 * (1 - k)
    chips = noise(W, W, .7, 43) > .82
    cv.c[chips] = (.25, .22, .2); cv.r[chips] = .5; cv.m[chips] = .7
    for y in (0, W // 2):
        cv.rect(0, y, W, y + 3, col=(.3, .28, .26), dh=-.5)
    grime(cv, 44, .2, .35)
    cv.save('ar_corr', strength=2.0)


# ---------------------------------------------------------------- painted steel: 1 m tile
def steel():
    W = 512
    cv = Canvas(W, W, (.62, .63, .62), .55, .5)
    n = noise(W, W, 1.6, 51); cv.c *= (.85 + .25 * n)[..., None]
    k = blotch(cv, 52, (.3, .13, .06), .9, .66, 1.9, 4)
    cv.r = .5 + k * .45; cv.m = .5 * (1 - k)
    chips = noise(W, W, .8, 53) > .8
    cv.c[chips] = (.4, .4, .41); cv.m[chips] = .9; cv.r[chips] = .35
    cv.hg = n * .3 - chips * .4
    grime(cv, 54, .15, .25)
    cv.save('ar_steel', strength=1.4)


# ---------------------------------------------------------------- diamond tread plate: 1 m tile
def plate():
    W = 512
    cv = Canvas(W, W, (.48, .49, .5), .42, .9)
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    p = 32
    u, v = (xx % p) / p - .5, (yy % p) / p - .5
    u2, v2 = ((xx + p / 2) % p) / p - .5, ((yy + p / 2) % p) / p - .5
    d1 = np.abs((u + v) * .7) + np.abs((u - v) * 2.2)
    d2 = np.abs((u2 - v2) * .7) + np.abs((u2 + v2) * 2.2)
    bump = np.clip(1 - np.minimum(d1, d2) * 3.2, 0, 1)
    cv.hg = bump * 1.5
    cv.c *= (.85 + .3 * bump)[..., None]
    n = noise(W, W, 1.5, 61); cv.c *= (.8 + .3 * n)[..., None]
    k = blotch(cv, 62, (.28, .14, .07), .6, .7, 1.8, 4)
    cv.r = .35 + k * .5 + (1 - bump) * .1; cv.m = .9 * (1 - k)
    grime(cv, 63, .2, 0)
    cv.save('ar_plate', strength=1.8)


# ---------------------------------------------------------------- crate / pallet boards: 1 m tile
def wood():
    W = 512
    cv = Canvas(W, W, (.5, .38, .25), .8, 0)
    rg = np.random.RandomState(71)
    yy, xx = np.mgrid[0:W, 0:W]
    bw = W // 8                                       # 12.5 cm boards (horizontal)
    bi = yy // bw
    tone = rg.uniform(.75, 1.2, 64).astype(np.float32)[bi % 64]
    grain = noise(W, W, 1.1, 72, ax=.06, ay=9)
    cv.c *= (tone * (.8 + .35 * grain))[..., None]
    cv.hg = grain * .5
    gap = (yy % bw) < 3
    cv.c[gap] = (.12, .09, .06); cv.hg[gap] = -1
    for x in (W // 4, 3 * W // 4):                    # nail heads
        for y in range(bw // 2, W, bw):
            m = (xx - x) ** 2 + (yy - y) ** 2 < 10
            cv.mask(m, col=(.25, .24, .23), metal=.8, h=.6)
    blotch(cv, 73, (.25, .25, .24), .5, .62, 1.7, 3)    # weathering to grey
    grime(cv, 74, .2, .2)
    cv.save('ar_wood', strength=1.6)


# ---------------------------------------------------------------- hazard stripes: 1 m tile
def hazard():
    W = 512
    cv = Canvas(W, W, (.78, .58, .08), .7, 0)
    yy, xx = np.mgrid[0:W, 0:W]
    stripe = ((xx + yy) % (W // 2)) < W // 4
    cv.c[stripe] = (.05, .05, .05)
    wear = noise(W, W, .9, 81) > .62
    cv.c[wear] = cv.c[wear] * .3 + np.array((.4, .39, .37), np.float32) * .7
    cv.hg = wear * -.4
    grime(cv, 82, .3, .1)
    cv.save('ar_hazard', strength=1.0)


# ---------------------------------------------------------------- factory glazing: 2 m x 2 m, 4 x 4 panes (RGBA)
def window():
    S = 512
    rg = np.random.RandomState(91)
    yy, xx = np.mgrid[0:S, 0:S]
    p = S // 4
    frame = ((xx % p) < 7) | ((yy % p) < 7) | (xx > S - 4) | (yy > S - 4)
    rgb = np.zeros((S, S, 3), np.float32)
    dirt = noise(S, S, 1.5, 92)
    rgb[:] = (np.array((.32, .38, .36), np.float32) * (.7 + .5 * dirt[..., None]))
    rgb[frame] = (.16, .17, .17)
    a = np.full((S, S), .55, np.float32) + dirt * .25
    pane = (yy // p) * 4 + (xx // p)
    broken = rg.rand(16) < .35
    for i in np.nonzero(broken)[0]:
        m = (pane == i) & ~frame
        # jagged hole with a shard left in a corner
        cy, cx = (i // 4) * p + p / 2, (i % 4) * p + p / 2
        ang = np.arctan2(yy - cy, xx - cx); rr = np.hypot(yy - cy, xx - cx)
        edge = p * (.32 + .14 * np.sin(ang * 5 + i) + .08 * np.sin(ang * 11 + i * 3))
        a[m & (rr < edge + p * .2)] = 0
    a[frame] = 1
    out = np.dstack([np.clip(rgb ** (1 / 2.2), 0, 1), np.clip(a, 0, 1)])
    Image.fromarray((out * 255 + .5).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'ar_window.png'))
    print('[texture] ar_window.png')


# ---------------------------------------------------------------- painted signage atlas (4 x 4 cells of 256 px)
SIGNS = ['BRENNICK WORKS', 'BAY 3', 'BAY 4', 'NO. 2 FURNACE', 'YARD NORTH', 'YARD SOUTH', 'KEEP CLEAR', 'RAIL SPUR 7',
         'GATEHOUSE', 'MIND THE STEP', 'CASTING HALL', 'DO NOT STACK', 'NO ENTRY', '07', '12', '▲ ▲ ▲']


def signs():
    C, N = 256, 4
    img = Image.new('RGBA', (C * N, C * N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rg = np.random.RandomState(101)
    for i, t in enumerate(SIGNS):
        cx, cy = (i % N) * C, (i // N) * C
        col = [(232, 226, 210), (230, 196, 60), (220, 70, 50), (210, 210, 205)][i % 4]
        size = 110 if len(t) <= 3 else 64 if len(t) <= 6 else 40 if len(t) <= 10 else 30
        f = font(size)
        bb = d.textbbox((0, 0), t, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text((cx + (C - tw) / 2 - bb[0], cy + (C - th) / 2 - bb[1]), t, font=f, fill=col + (255,))
    a = np.asarray(img).astype(np.float32) / 255
    # stencil gaps and weathering: paint flaked off in blotches
    flake = noise(C * N, C * N, 1.1, 102)
    a[..., 3] *= np.clip((flake - .2) * 2.5, 0, 1) * (.75 + .25 * noise(C * N, C * N, .3, 103))
    Image.fromarray((a * 255 + .5).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'ar_signs.png'))
    print('[texture] ar_signs.png')


def main():
    brick(); conc(); floor(); corr(); steel(); plate(); wood(); hazard(); window(); signs()


if __name__ == '__main__':
    main()
