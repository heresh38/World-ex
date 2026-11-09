"""Meridian's ruined surfaces (meridian.py, the first operation), painted with numpy. Seamless tiles; the metres one
tile covers are in TILE (meridian.py lays world-scale UVs with them).

  ru_concrete   cast concrete: board-form lines, tie holes, rain streaks, soot, hairline cracks, damp patches
  ru_fracture   broken concrete (every snapped edge, the rubble): lumpy aggregate, pebbles, dust in the hollows
  ru_asphalt    old road: alligator cracking, potholes, ash and grit, a faded lane line
  ru_stone      plaza slabs 1 x 1 m: cracked, a few lifted or gone to dirt, stained
  ru_metal      painted structural steel: chipped paint to bare metal at the scratches, rust blooms and runs
  ru_panel      facade cladding: dark panels with seams and fixings, sun-bleached and streaked, burn marks
  ru_rubble     ground debris: ash, gravel, concrete crumbs
  ru_banner     the Choir's banner cloth: a deep red weave with their sigil (a broken ring pierced by a spike)

Each set: <name>_c.jpg colour, <name>_n.png tangent normal (OpenGL), <name>_m.png (R unused, G roughness, B metal).

Run: blender --background --python tools/blender/ruins_textures.py [-- name ...]
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
from nexus_city_textures import F32, rng, noise, fbm, speck, blur, grid_lines, cell_rand, col, ramp, normal_from, save

TILE = {"ru_concrete": 2.5, "ru_fracture": 1.5, "ru_asphalt": 6.0, "ru_stone": 4.0, "ru_metal": 2.0, "ru_panel": 3.0,
        "ru_rubble": 4.0, "ru_banner": 1.0}
N = 1024


def srgb(c):
    """the palette is linear (bl.hexrgb): colour maps are stored as sRGB"""
    c = np.clip(c, 0, 1)
    return np.where(c <= .0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - .055).astype(F32)


def write(name, c, h, strength, rough, metal=None):
    save(name + "_c", srgb(c), jpg=True)
    save(name + "_n", normal_from(h, strength), srgb=False)
    m = np.zeros(c.shape, F32)
    m[..., 1] = np.clip(rough, 0.03, 1)
    m[..., 2] = 0 if metal is None else np.clip(metal, 0, 1)
    save(name + "_m", m, srgb=False)
    print(f"[ruins_textures] {name}")


def cracks(n, scale, seed, width=1.2):
    """thin branching crack lines: the ridges of a few noise fields (1 on a crack)"""
    out = np.zeros((n, n), F32)
    for k in range(3):
        v = fbm(n, scale * (1 + k * .6), seed + 31 * k, octaves=3)
        ridge = np.abs(v - .5)
        lim = .004 * width * (1 + k * .3)
        out = np.maximum(out, np.clip(1 - ridge / lim, 0, 1) * np.clip((fbm(n, 2, seed + 7 + k) - .42) * 5, 0, 1))
    return out


def streaks(n, seed, density=60):
    """rain streaks running down the tile (image rows run down)"""
    speckle = np.clip((noise(n, density, seed) - .52) * 5, 0, 1)
    fade = np.clip((fbm(n, 2, seed + 1) - .4) * 3, 0, 1)            # where the runs are, large scale
    column = np.clip((noise(n, density, seed + 2)[0:1, :] - .5) * 6, 0, 1)    # one value per column: long runs down
    return np.clip(np.repeat(column, n, 0) * fade * .8 + speckle * .2, 0, 1)


def concrete():
    n = N
    v = fbm(n, 7, 1)
    fine = rng(2).random((n, n)).astype(F32)
    pores = blur(speck(n, .006, 3), 1) * 2.5
    boards = grid_lines(n, 1, 8, 1.0)[0] * (.35 + .65 * noise(n, 4, 4))     # board-form joints (horizontal)
    yy, xx = np.mgrid[0:n, 0:n]
    ties = np.zeros((n, n), F32)
    for gx in (.25, .75):
        for gy in (.125, .625):
            ties = np.maximum(ties, np.clip(1 - np.hypot(xx - gx * n, yy - gy * n) / 7, 0, 1))
    crack = cracks(n, 5, 5)
    rain = streaks(n, 6)
    damp = np.clip((fbm(n, 2.5, 7) - .55) * 4, 0, 1)
    soot = np.clip((fbm(n, 3, 8) - .6) * 4, 0, 1)
    c = ramp(v * .7 + fine * .15, '#6f6c66', '#9b978f')
    c *= (1 - boards[..., None] * .18) * (1 - pores[..., None] * .25) * (1 - ties[..., None] * .55)
    c *= (1 - rain[..., None] * .28)
    c = c * (1 - damp[..., None] * .35) + col('#4a4f3c') * damp[..., None] * .2       # damp, a little green
    c *= (1 - soot[..., None] * .45)
    c *= (1 - crack[..., None] * .7)
    h = v * .5 + fine * .15 - pores * .4 - boards * .25 - ties * .8 - crack * .7
    write("ru_concrete", c, h, 3.5, .86 - damp * .12 + crack * .06)


def fracture():
    n = N
    lumps = fbm(n, 22, 11, octaves=5)
    big = fbm(n, 6, 12)
    peb = blur(speck(n, .02, 13), 2) * 3
    fine = rng(14).random((n, n)).astype(F32)
    h = lumps * .8 + big * .4 + peb.clip(0, 1) * .4 + fine * .1
    hollow = np.clip((.46 - lumps) * 3, 0, 1)
    c = ramp(lumps * .5 + fine * .3 + big * .2, '#827d74', '#a39d92')
    c = c * (1 - peb.clip(0, 1)[..., None] * .3) + col('#5e5a52') * peb.clip(0, 1)[..., None] * .3
    c = c * (1 - hollow[..., None] * .25) + col('#5d584f') * hollow[..., None] * .15        # dust in the hollows
    write("ru_fracture", c, h, 6.0, .94)


def asphalt():
    n = N
    base = fbm(n, 6, 21)
    grit = rng(22).random((n, n)).astype(F32)
    stones = blur(speck(n, .03, 23), 1) * 2
    gator = cracks(n, 14, 24, 1.6)                                # alligator cracking
    big = cracks(n, 4, 25, 2.2)
    yy, xx = np.mgrid[0:n, 0:n]
    holes = np.zeros((n, n), F32)
    r = rng(26)
    for _ in range(4):
        cx, cy, rad = r.random() * n, r.random() * n, 18 + r.random() * 40
        d = np.hypot(((xx - cx + n / 2) % n) - n / 2, ((yy - cy + n / 2) % n) - n / 2)
        holes = np.maximum(holes, np.clip((rad - d) / 6, 0, 1))
    ash = np.clip((fbm(n, 2.5, 27) - .5) * 3, 0, 1)
    line = np.clip(1 - np.abs(np.arange(n)[None, :] - n * .5) / 10, 0, 1) * np.repeat(np.clip((noise(n, 3, 28) - .35) * 3, 0, 1), 1, 0)
    c = ramp(base * .6 + grit * .3, '#2c2e31', '#4e5054') + (stones.clip(0, 1) * .06)[..., None]
    c = c * (1 - line[..., None] * .7) + col('#a29a7e') * line[..., None] * .55          # faded paint
    c = c * (1 - ash[..., None] * .4) + col('#58544d') * ash[..., None] * .4
    c *= (1 - np.maximum(gator, big)[..., None] * .55)
    c = c * (1 - holes[..., None]) + ramp(grit, '#2e2a24', '#4a443a') * holes[..., None]
    h = grit * .3 + stones * .4 + base * .2 - np.maximum(gator, big) * .6 - holes * 1.2
    write("ru_asphalt", c, h, 3.0, .8 + ash * .12 - line * .1)


def stone():
    n = N
    j, ix, iy = grid_lines(n, 4, 4, 2.2)
    r = cell_rand(ix, iy, 31)
    gone = (cell_rand(ix + 3, iy + 5, 32) < .06).astype(F32)
    lift = (cell_rand(ix + 7, iy + 1, 33) - .5) * .25
    v = fbm(n, 8, 34)
    crack = cracks(n, 6, 35, 1.3)
    stain = np.clip((fbm(n, 2.5, 36) - .5) * 3, 0, 1)
    dirt = ramp(fbm(n, 12, 37), '#3c362e', '#5a5145')
    c = ramp(r * .55 + v * .45, '#5f5d58', '#86837b') * (1 - j[..., None] * .55)
    c *= (1 - crack[..., None] * .6) * (1 - stain[..., None] * .3)
    c = c * (1 - gone[..., None]) + dirt * gone[..., None]
    h = (1 - j) * .6 + v * .2 + lift - crack * .5 - gone * .5
    write("ru_stone", c, h, 4.5, .78 + j * .15 + gone * .12)


def metal():
    n = N
    v = fbm(n, 6, 41)
    scratch = np.zeros((n, n), F32)
    r = rng(42)
    for _ in range(120):                                          # short straight scratches
        x0, y0 = r.random() * n, r.random() * n
        a = r.random() * np.pi; L = 10 + r.random() * 60
        t = np.linspace(0, 1, int(L))
        xs = ((x0 + np.cos(a) * L * t) % n).astype(int); ys = ((y0 + np.sin(a) * L * t) % n).astype(int)
        scratch[ys, xs] = 1
    scratch = np.clip(blur(scratch, 1) * 1.2, 0, 1) * (.35 + .65 * noise(n, 6, 48))
    edges = np.clip((fbm(n, 9, 43) - .64) * 6, 0, 1)
    rust = np.clip((fbm(n, 7, 44) - .6) * 4, 0, 1) * .85
    runs = streaks(n, 45, 90) * rust.max()
    paint = ramp(v, '#2a2d31', '#3b3f45')
    bare = col('#6f7173')
    rust_c = ramp(fbm(n, 14, 46), '#3a2014', '#6a3d22')
    chip = np.maximum(scratch * .9, edges)
    c = paint * (1 - chip[..., None] * .8) + bare * chip[..., None] * .8
    c = c * (1 - rust[..., None]) + rust_c * rust[..., None]
    c = c * (1 - runs[..., None] * .4) + col('#5a3018') * runs[..., None] * .3
    h = v * .2 - chip * .25 + rust * .35 + fbm(n, 30, 47) * rust * .4
    write("ru_metal", c, h, 3.0, .55 - chip * .2 + rust * .35, metal=chip * (1 - rust))


def panel():
    n = N
    j, ix, iy = grid_lines(n, 3, 2, 2.0)
    r = cell_rand(ix, iy, 51)
    v = fbm(n, 6, 52)
    yy, xx = np.mgrid[0:n, 0:n]
    bolts = np.zeros((n, n), F32)
    for gx in range(3):
        for gy in range(2):
            for fx in (.08, .92):
                for fy in (.1, .9):
                    cx, cy = (gx + fx) * n / 3, (gy + fy) * n / 2
                    bolts = np.maximum(bolts, np.clip(1 - np.hypot(xx - cx, yy - cy) / 4, 0, 1))
    rain = streaks(n, 53, 70)
    burn = np.clip((fbm(n, 2, 54) - .62) * 5, 0, 1)
    bleach = np.clip((fbm(n, 1.5, 55) - .45) * 2, 0, 1)
    c = ramp(r * .5 + v * .5, '#3a3d42', '#575b62') * (1 - j[..., None] * .6)
    c = c * (1 - bleach[..., None] * .25) + col('#7b7d80') * bleach[..., None] * .25
    c *= (1 - rain[..., None] * .3) * (1 - burn[..., None] * .7)
    c = c * (1 - bolts[..., None] * .4) + col('#7e8186') * bolts[..., None] * .3
    h = (1 - j) * .5 + v * .2 + bolts * .5 - burn * .2
    write("ru_panel", c, h, 4.0, .6 + burn * .3 + bleach * .1, metal=(1 - j) * .45 * (1 - burn))


def rubble():
    n = N
    v = fbm(n, 5, 61)
    grit = rng(62).random((n, n)).astype(F32)
    crumbs = blur(speck(n, .03, 63), 1) * 2.5
    chunks = blur(speck(n, .0015, 64), 4) * 30
    ash = np.clip((fbm(n, 3, 65) - .5) * 3, 0, 1)
    c = ramp(v * .5 + grit * .3, '#4a453e', '#6d675d')
    c = c * (1 - crumbs.clip(0, 1)[..., None] * .4) + col('#8f8a80') * crumbs.clip(0, 1)[..., None] * .4
    c = c * (1 - chunks.clip(0, 1)[..., None] * .5) + col('#7d786f') * chunks.clip(0, 1)[..., None] * .5
    c = c * (1 - ash[..., None] * .5) + col('#3b3936') * ash[..., None] * .5
    h = v * .4 + grit * .2 + crumbs.clip(0, 1) * .4 + chunks.clip(0, 1) * .8
    write("ru_rubble", c, h, 5.0, .93)


def banner():
    """1 x 2 m: the cloth weave and the sigil (a broken ring pierced top to bottom by a spike), top of the image = top"""
    w, hgt = N // 2, N
    yy, xx = np.mgrid[0:hgt, 0:w].astype(F32)
    u, v = xx / w, 1 - yy / hgt                                    # u across, v up
    weave = (np.sin(xx * np.pi * .9) * np.sin(yy * np.pi * .9) * .5 + .5)
    v_noise = fbm(N, 6, 71)[:hgt, :w]
    cloth = ramp(v_noise * .6 + weave * .2, '#4a0b0c', '#7a1416')
    # the sigil, centred at 60 % up
    cx, cy = .5, .60
    dx, dy = (u - cx) * 1.0, (v - cy) * 2.0                        # in metres-ish (the banner is twice as tall)
    rr = np.hypot(dx, dy)
    ang = np.degrees(np.arctan2(dy, dx)) % 360
    ring = np.clip(1 - np.abs(rr - .28) / .028, 0, 1)
    gaps = ((ang > 70) & (ang < 110)) | ((ang > 250) & (ang < 290)) | ((ang > 160) & (ang < 175))
    ring *= ~gaps
    spike_w = np.clip(.045 - np.abs(dx) - np.clip((dy - .1) * .08, 0, .045), 0, 1) / .045
    spike = np.clip(spike_w * 3, 0, 1) * ((dy > -.62) & (dy < .52))
    ray = np.zeros_like(u)
    for a in (210.0, 330.0):                                      # two short rays below
        ax, ay = np.cos(np.radians(a)), np.sin(np.radians(a))
        t = dx * ax + dy * ay
        d = np.abs(-dx * ay + dy * ax)
        ray = np.maximum(ray, np.clip(1 - d / .018, 0, 1) * ((t > .34) & (t < .46)))
    mark = np.clip(ring + spike + ray, 0, 1)
    gold = ramp(v_noise, '#6d5420', '#a8853a')
    c = cloth * (1 - mark[..., None]) + gold * mark[..., None] * .85 + col('#120808') * mark[..., None] * .15
    # a darker border band and grime toward the bottom
    border = np.clip(1 - np.minimum(np.minimum(u, 1 - u), 1 - v) / .04, 0, 1)
    c *= (1 - border[..., None] * .45)
    grime = np.clip((.35 - v) * 2.5, 0, 1) * (.6 + .4 * v_noise)
    c *= (1 - grime[..., None] * .5)
    hh = weave * .3 + v_noise * .2 + mark * .15
    save("ru_banner_c", srgb(c), jpg=True)
    save("ru_banner_n", normal_from(hh, 2.0), srgb=False)
    m = np.zeros(c.shape, F32); m[..., 1] = .9 - mark * .35; m[..., 2] = mark * .6
    save("ru_banner_m", m, srgb=False)
    print("[ruins_textures] ru_banner")


JOBS = dict(ru_concrete=concrete, ru_fracture=fracture, ru_asphalt=asphalt, ru_stone=stone, ru_metal=metal,
            ru_panel=panel, ru_rubble=rubble, ru_banner=banner)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for k, f in JOBS.items():
        if not argv or k in argv:
            f()


if __name__ == '__main__':
    main()
