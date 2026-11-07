"""Nexus Prime city surfaces and facades (nexus_city.py, Unreal M_SOGround / M_SOFacade), painted with numpy.

Ground sets (seamless, world-aligned in Unreal; the metres one tile covers are in GROUND):
  nc_asphalt   road asphalt: aggregate speckle, tar seams, oil and tyre wear
  nc_pavers    sidewalk: 50 cm concrete pavers with sand joints
  nc_plaza     plaza: 2 x 1 m slate slabs in a running bond with thin light inlays
  nc_kerb      kerb / viaduct concrete: fine cast concrete
  nc_lot       yards and dock aprons: poured concrete bays with joints
  nc_grass     park lawn
  nc_roof      flat roofs: membrane sheets, gravel, drains
  nc_wall      city wall: big dark cast panels with tie holes and rain streaks

Facade sets (one tile = one bay x one floor; FACADE gives the metres, M_SOFacade scales them per building):
  ncf_glass, ncf_office, ncf_panel, ncf_housing, ncf_industrial, ncf_military, ncf_stone

Each set: <name>_c.jpg colour, <name>_n.png tangent normal (OpenGL), <name>_m.png (R window glass mask, which lights
at night; G roughness; B metal).

Run: blender --background --python tools/blender/nexus_city_textures.py [-- name ...]
"""
import bpy, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl

F32 = np.float32
GROUND = {"nc_asphalt": 8.0, "nc_pavers": 4.0, "nc_plaza": 8.0, "nc_kerb": 2.0, "nc_lot": 9.0, "nc_grass": 4.0,
          "nc_roof": 8.0, "nc_wall": 12.0, "nc_dirt": 6.0}
FACADE = {"ncf_glass": (3.0, 3.6), "ncf_office": (3.6, 3.6), "ncf_panel": (4.0, 3.6), "ncf_housing": (3.4, 3.0),
          "ncf_industrial": (6.0, 4.5), "ncf_military": (5.0, 4.0), "ncf_stone": (3.6, 4.0),
          # older / special uses
          "ncf_brick": (3.2, 3.1), "ncf_parkade": (6.0, 3.0), "ncf_warehouse": (8.0, 9.0),
          # ground floors (one row: Floor = the ground floor's height)
          "ncf_shop": (4.2, 4.5), "ncf_lobby": (6.0, 4.5), "ncf_service": (5.0, 4.5), "ncf_loading": (6.0, 4.5)}


# ------------------------------------------------------------------ helpers
def rng(seed):
    return np.random.default_rng(seed)


def noise(n, scale, seed, m=None):
    """Seamless band-limited noise in 0..1: random spectrum with a gaussian falloff (scale = features per tile)."""
    m = m or n
    r = rng(seed)
    fy = np.fft.fftfreq(n)[:, None] * n; fx = np.fft.fftfreq(m)[None, :] * m
    k = np.sqrt(fx ** 2 + fy ** 2)
    spec = (r.normal(size=(n, m)) + 1j * r.normal(size=(n, m))) * np.exp(-(k / scale) ** 2)
    spec[0, 0] = 0
    v = np.fft.ifft2(spec).real
    v = (v - v.mean()) / (v.std() + 1e-9)
    return np.clip(.5 + v * .18, 0, 1).astype(F32)


def fbm(n, scale, seed, octaves=4, m=None):
    v = np.zeros((n, m or n), F32); a = 1.0; t = 0.0
    for o in range(octaves):
        v += a * noise(n, scale * 2 ** o, seed + o * 17, m); t += a; a *= .5
    return v / t


def speck(n, density, seed, m=None):
    return (rng(seed).random((n, m or n)) < density).astype(F32)


def blur(a, r=1):
    out = a.copy()
    for _ in range(r):
        out = (out + np.roll(out, 1, 0) + np.roll(out, -1, 0) + np.roll(out, 1, 1) + np.roll(out, -1, 1)) / 5
    return out


def grid_lines(n, cells_x, cells_y, width, m=None, offset_rows=0.0):
    """1 on joint lines of a cells_x x cells_y grid (row offset for a running bond), soft edges."""
    m = m or n
    y = (np.arange(n) + .5)[:, None] / n * cells_y
    x = (np.arange(m) + .5)[None, :] / m * cells_x + np.floor(y) * offset_rows
    dx = np.abs(x - np.round(x)) * m / cells_x; dy = np.abs(y - np.round(y)) * n / cells_y
    d = np.minimum(dx, dy)
    return np.clip(1 - (d - width) / 1.5, 0, 1).astype(F32), np.floor(x).astype(int) % max(1, cells_x * 4), np.floor(y).astype(int)


def cell_rand(ix, iy, seed):
    h = (ix * 73856093 ^ iy * 19349663 ^ seed * 83492791) & 0xffffff
    return (h / float(0xffffff)).astype(F32)


def col(hexs):
    return np.array(bl.hexrgb(hexs), F32)


def ramp(t, a, b):
    t = np.clip(t, 0, 1)[..., None]
    return col(a) * (1 - t) + col(b) * t


def normal_from(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * .5 * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * .5 * strength
    nrm = np.stack([-gx, gy, np.ones_like(h)], -1)          # image rows run down: +V is up in the texture
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    return nrm * .5 + .5


def save(name, rgb, srgb=True, jpg=False):
    h, w = rgb.shape[:2]
    im = bpy.data.images.new(name, w, h, alpha=False)
    if not srgb:
        im.colorspace_settings.name = 'Non-Color'
    px = np.ones((h, w, 4), F32); px[..., :3] = np.clip(rgb, 0, 1)[::-1]      # Blender pixels start at the bottom
    im.pixels = px.ravel()
    ext = '.jpg' if jpg else '.png'
    im.filepath_raw = os.path.join(bl.TEXTURES, name + ext); im.file_format = 'JPEG' if jpg else 'PNG'
    bpy.context.scene.render.image_settings.quality = 90
    im.save()
    bpy.data.images.remove(im)


def write(name, c, h, strength, rough, metal=None, mask=None):
    n = c.shape[0]
    save(name + "_c", c, jpg=True)
    save(name + "_n", normal_from(h, strength), srgb=False)
    m = np.zeros(c.shape, F32)
    m[..., 0] = mask if mask is not None else 0
    m[..., 1] = rough
    m[..., 2] = metal if metal is not None else 0
    save(name + "_m", m, srgb=False)
    print(f"[nexus_city_textures] {name} {n}px")


# ------------------------------------------------------------------ ground sets
def asphalt():
    n = 1024
    base = fbm(n, 6, 1)
    grit = rng(2).random((n, n)).astype(F32)
    stones = blur(speck(n, .035, 3), 1) * 2.2
    h = grit * .35 + stones * .5 + base * .3
    c = ramp(base * .6 + grit * .25, '#34363a', '#55585d')
    c += (stones.clip(0, 1) * .07)[..., None]
    wear = np.clip((fbm(n, 2.5, 4) - .5) * 3, 0, 1)               # lighter worn patches
    c = c * (1 - wear[..., None] * .25) + col('#4a4b4f') * wear[..., None] * .25
    oil = np.clip((noise(n, 3, 5) - .62) * 6, 0, 1)
    c *= (1 - oil[..., None] * .35)
    seam = np.clip(1 - np.abs(np.linspace(-1, 1, n)[None, :] + (noise(n, 3, 6) - .5) * .5) * 60, 0, 1)
    c = c * (1 - seam[..., None] * .5)
    rough = .82 - oil * .25 - seam * .1
    write("nc_asphalt", c, h, 3.0, rough)


def pavers():
    n = 1024
    j, ix, iy = grid_lines(n, 8, 8, 2.5)
    r = cell_rand(ix, iy, 7)
    stain = fbm(n, 5, 8)
    c = ramp(stain * .5 + r * .5, '#6d6f72', '#8c8e90') * (1 - j[..., None] * .55)
    c *= (.92 + rng(9).random((n, n)).astype(F32)[..., None] * .1)
    h = (1 - j) * .8 + rng(10).random((n, n)).astype(F32) * .15 + r[..., None][..., 0] * .1
    write("nc_pavers", c, h, 5.0, .7 + j * .2)


def plaza():
    n = 1024
    j, ix, iy = grid_lines(n, 4, 8, 2.0, offset_rows=.5)
    r = cell_rand(ix, iy, 11)
    v = fbm(n, 8, 12)
    c = ramp(r * .6 + v * .4, '#3a3e46', '#5a5f6a') * (1 - j[..., None] * .5)
    inlay = np.zeros((n, n), F32); inlay[n // 2 - 2:n // 2 + 2, :] = 1
    c = c * (1 - inlay[..., None]) + col('#7fb8c8') * inlay[..., None]
    h = (1 - j) * .7 + v * .2
    write("nc_plaza", c, h, 4.0, .55 + j * .3 - inlay * .2, metal=inlay * .6)


def kerb():
    n = 1024
    v = fbm(n, 10, 13); p = rng(14).random((n, n)).astype(F32)
    holes = blur(speck(n, .004, 15), 1) * 3
    c = ramp(v * .7 + p * .2 - holes * .3, '#6b6c6c', '#9a9a97')
    write("nc_kerb", c, v * .4 + p * .3 - holes * .5, 2.0, .8)


def lot():
    n = 1024
    j, ix, iy = grid_lines(n, 3, 3, 2.0)
    r = cell_rand(ix, iy, 16)
    v = fbm(n, 5, 17)
    c = ramp(v * .6 + r * .3, '#55575a', '#7c7d7e') * (1 - j[..., None] * .6)
    tyre = np.clip((noise(n, 2, 18) - .58) * 5, 0, 1)
    c *= (1 - tyre[..., None] * .25)
    write("nc_lot", c, (1 - j) * .6 + v * .3, 3.0, .8)


def grass():
    n = 1024
    v = fbm(n, 6, 19)
    blades = blur(rng(20).random((n, n)).astype(F32), 1)
    dry = np.clip((noise(n, 2.5, 21) - .55) * 4, 0, 1)
    c = ramp(v * .5 + blades * .5, '#1f3a17', '#47702d')
    c = c * (1 - dry[..., None] * .5) + col('#7c7440') * dry[..., None] * .5
    write("nc_grass", c, blades * .8 + v * .2, 4.0, .9)


def roof():
    n = 1024
    j, ix, iy = grid_lines(n, 4, 2, 2.5)
    r = cell_rand(ix, iy, 22)
    gravel = rng(23).random((n, n)).astype(F32)
    v = fbm(n, 6, 24)
    c = ramp(r * .3 + v * .4 + gravel * .3, '#4f5256', '#73767a') * (1 - j[..., None] * .4)
    drain = np.zeros((n, n), F32)
    yy, xx = np.mgrid[0:n, 0:n]
    for cx, cy in ((256, 256), (768, 768)):
        drain = np.maximum(drain, np.clip(1 - np.hypot(xx - cx, yy - cy) / 14, 0, 1))
    c *= (1 - drain[..., None] * .7)
    write("nc_roof", c, gravel * .4 + (1 - j) * .4 - drain, 3.0, .85)


def dirt():
    n = 1024
    v = fbm(n, 5, 70); g = rng(71).random((n, n)).astype(F32)
    stones = blur(speck(n, .02, 72), 1) * 2
    weeds = np.clip((fbm(n, 7, 73) - .58) * 5, 0, 1)
    c = ramp(v * .6 + g * .3, '#4a4036', '#6e6253') + (stones.clip(0, 1) * .06)[..., None]
    c = c * (1 - weeds[..., None] * .6) + col('#3d4a26') * weeds[..., None] * .6
    write("nc_dirt", c, g * .4 + stones * .5 + v * .2, 3.0, .92)


def wall():
    n = 1024
    j, ix, iy = grid_lines(n, 2, 3, 2.5)
    r = cell_rand(ix, iy, 25)
    v = fbm(n, 6, 26)
    yy, xx = np.mgrid[0:n, 0:n]
    holes = np.zeros((n, n), F32)
    for gx in range(2):
        for gy in range(3):
            for hx in (.25, .75):
                for hy in (.25, .75):
                    cx = (gx + hx) * n / 2; cy = (gy + hy) * n / 3
                    holes = np.maximum(holes, np.clip(1 - np.hypot(xx - cx, yy - cy) / 6, 0, 1))
    streak = np.clip((noise(n // 1, 30, 27) - .5) * 4, 0, 1) * np.clip((fbm(n, 2, 28) - .45) * 3, 0, 1)
    c = ramp(v * .5 + r * .5, '#3f434a', '#5c616a') * (1 - j[..., None] * .5) * (1 - holes[..., None] * .6)
    c *= (1 - streak[..., None] * .25)
    write("nc_wall", c, (1 - j) * .7 + v * .2 - holes * .6, 4.0, .75)


# ------------------------------------------------------------------ facades (one bay x one floor)
def rect(n, x0, x1, y0, y1, soft=1.5):
    """Soft rectangle mask in tile fractions (x along the bay, y up the floor; image row 0 = top of the floor)."""
    y = (np.arange(n) + .5)[:, None] / n; x = (np.arange(n) + .5)[None, :] / n
    yu = 1 - y
    d = np.minimum(np.minimum(x - x0, x1 - x), np.minimum(yu - y0, y1 - yu)) * n
    return np.clip(d / soft + .5, 0, 1).astype(F32)


def glass_pane(n, seed, tint_a, tint_b):
    """Dark reflective pane with a sky gradient and interior hints."""
    y = (np.arange(n) + .5)[:, None] / n
    sky = np.broadcast_to(1 - y, (n, n)).astype(F32)
    v = noise(n, 3, seed)
    return ramp(sky * .7 + v * .3, tint_a, tint_b)


def facade(name, frame_col, frame_var, panes, pane_a, pane_b, frame_rough, frame_metal, extra=None, seed=0):
    n = 512
    v = fbm(n, 6, 30 + seed)
    base = ramp(v, frame_col, frame_var)
    mask = np.zeros((n, n), F32)
    for (x0, x1, y0, y1) in panes:
        mask = np.maximum(mask, rect(n, x0, x1, y0, y1))
    glass = glass_pane(n, 40 + seed, pane_a, pane_b)
    c = base * (1 - mask[..., None]) + glass * mask[..., None]
    h = (1 - mask) * .6 + v * .1
    rough = frame_rough * (1 - mask) + .08 * mask
    metal = frame_metal * (1 - mask) + .2 * mask
    if extra:
        c, h, rough, metal = extra(n, c, h, rough, metal, mask)
    # grime streaks under the sills and a darker floor-slab line
    streak = np.clip((noise(n, 20, 50 + seed) - .5) * 3, 0, 1) * .12
    c *= (1 - streak[..., None] * (1 - mask[..., None]))
    write(name, c, h, 6.0, rough, metal, mask)


def lines_h(n, ys, w=3):
    m = np.zeros((n, n), F32)
    for y in ys:
        r = int((1 - y) * n)
        m[max(0, r - w):min(n, r + w), :] = 1
    return m


def lines_v(n, xs, w=3):
    m = np.zeros((n, n), F32)
    for x in xs:
        c = int(x * n)
        m[:, max(0, c - w):min(n, c + w)] = 1
    return m


def main():
    want = set(sys.argv[sys.argv.index('--') + 1:]) if '--' in sys.argv else set()
    jobs = dict(nc_dirt=dirt, nc_asphalt=asphalt, nc_pavers=pavers, nc_plaza=plaza, nc_kerb=kerb, nc_lot=lot, nc_grass=grass,
                nc_roof=roof, nc_wall=wall)

    def glass_extra(n, c, h, r, m, mask):
        mull = np.maximum(lines_v(n, [0.0, .5, 1.0], 4), lines_h(n, [0.0, 1.0], 5))
        c = c * (1 - mull[..., None]) + col('#2a2d33') * mull[..., None]
        return c, h + mull * .5, r * (1 - mull) + .35 * mull, m * (1 - mull) + .9 * mull

    def panel_extra(n, c, h, r, m, mask):
        seams = np.maximum(lines_v(n, [.33, .66], 2), lines_h(n, [.5], 2)) * (1 - mask)
        lamp = rect(n, .0, 1.0, .02, .05) * .9
        c = c * (1 - seams[..., None] * .5)
        c = c * (1 - lamp[..., None]) + col('#58d8ff') * lamp[..., None]
        return c, h - seams * .4, r, m

    def housing_extra(n, c, h, r, m, mask):
        slab = rect(n, 0, 1, 0, .08)
        rail = lines_h(n, [.32], 3) * rect(n, .05, .95, 0, 1)
        c = c * (1 - slab[..., None]) + col('#b9b2a5') * slab[..., None]
        c = c * (1 - rail[..., None]) + col('#2a2b2e') * rail[..., None]
        return c, h + slab * .6 + rail * .4, r, m + rail * .8

    def industrial_extra(n, c, h, r, m, mask):
        x = (np.arange(n) + .5)[None, :] / n
        ribs = (.5 + .5 * np.cos(x * 2 * np.pi * 24)).astype(F32) * (1 - mask)
        rust = np.clip((fbm(n, 4, 61) - .55) * 4, 0, 1) * (1 - mask)
        c = c * (.85 + ribs[..., None] * .15)
        c = c * (1 - rust[..., None] * .5) + col('#6b4128') * rust[..., None] * .5
        return c, h + np.broadcast_to(ribs, (n, n)) * .5, r + rust * .2, m * (1 - rust)

    def military_extra(n, c, h, r, m, mask):
        plates = np.maximum(lines_v(n, [.5], 3), lines_h(n, [.35, .7], 3)) * (1 - mask)
        stripe = rect(n, 0, 1, .9, .93)
        c = c * (1 - plates[..., None] * .6)
        c = c * (1 - stripe[..., None]) + col('#c9a33a') * stripe[..., None]
        return c, h - plates * .5, r, m

    def stone_extra(n, c, h, r, m, mask):
        j, ix, iy = grid_lines(n, 3, 6, 1.5, offset_rows=.5)
        j = j * (1 - mask)
        c = c * (1 - j[..., None] * .4)
        return c, h - j * .4, r, m

    def brick_extra(n, c, h, r, m, mask):
        j, ix, iy = grid_lines(n, 15, 48, 1.2, offset_rows=.5)
        tone = cell_rand(ix, iy, 81)
        wall_ = (1 - mask)
        c = c * (1 - (j * wall_)[..., None] * .45) * (.88 + tone[..., None] * .2 * wall_[..., None] + mask[..., None] * (.12 - tone[..., None] * .2) * 0)
        lintel = rect(n, .2, .8, .86, .92) + rect(n, .18, .82, .22, .26)
        c = c * (1 - lintel[..., None]) + col('#b8b0a0') * lintel[..., None]
        return c, h - j * wall_ * .5 + lintel * .3, r, m

    def shop_extra(n, c, h, r, m, mask):
        mull = np.maximum(lines_v(n, [.5], 3), lines_h(n, [.72], 3)) * mask
        band = rect(n, 0, 1, .78, .97)
        base = rect(n, 0, 1, 0, .06)
        c = c * (1 - mull[..., None]) + col('#1f2226') * mull[..., None]
        c = c * (1 - band[..., None]) + col('#2c2f35') * band[..., None]
        c = c * (1 - base[..., None]) + col('#3a3632') * base[..., None]
        return c, h + band * .4 + base * .4, r, m * (1 - mull) + mull * .9

    def lobby_extra(n, c, h, r, m, mask):
        mull = lines_v(n, [.33, .66], 3) * mask
        c = c * (1 - mull[..., None]) + col('#2a2d33') * mull[..., None]
        return c, h + mull * .4, r, m

    def parkade_extra(n, c, h, r, m, mask):
        gap = rect(n, 0, 1, .36, .96)           # the open deck: dark, no glass
        c = c * (1 - gap[..., None]) + col('#0b0c0e') * gap[..., None]
        col_ = lines_v(n, [0.0, 1.0], 18)
        c = c * (1 - col_[..., None]) + col('#8a8984') * col_[..., None]
        return c, h - gap * .6 + col_ * .4, r, m

    def warehouse_extra(n, c, h, r, m, mask):
        x = (np.arange(n) + .5)[None, :] / n
        ribs = (.5 + .5 * np.cos(x * 2 * np.pi * 26)).astype(F32) * (1 - mask)
        dirt_ = np.clip(1 - (np.arange(n)[:, None] / n) * 1.0, 0, 1) ** 6 * (1 - mask)
        c = c * (.86 + ribs[..., None] * .14) * (1 - np.broadcast_to(dirt_, (n, n))[..., None] * .35)
        return c, h + np.broadcast_to(ribs, (n, n)) * .5, r, m

    facades = dict(
        ncf_brick=lambda: facade("ncf_brick", '#7a3f2c', '#9a5a40', [(.25, .75, .26, .86)], '#14161a', '#4c5a66', .85, .0, brick_extra, 8),
        ncf_shop=lambda: facade("ncf_shop", '#2c2f35', '#3c4048', [(.06, .94, .07, .76)], '#11171c', '#56707f', .5, .5, shop_extra, 9),
        ncf_lobby=lambda: facade("ncf_lobby", '#8d877c', '#a49e92', [(.12, .88, .02, .9)], '#0e141a', '#46606f', .7, .0, lobby_extra, 10),
        ncf_service=lambda: facade("ncf_service", '#7d7c78', '#96948e', [(.1, .3, .7, .85), (.7, .9, .7, .85)], '#15191c', '#4a5a64', .85, .0, None, 11),
        ncf_loading=lambda: facade("ncf_loading", '#5f646a', '#767b80', [(.4, .6, .84, .9)], '#15191c', '#4a5a64', .6, .5, industrial_extra, 12),
        ncf_parkade=lambda: facade("ncf_parkade", '#8a8984', '#a3a19b', [], '#000000', '#000000', .85, .0, parkade_extra, 13),
        ncf_warehouse=lambda: facade("ncf_warehouse", '#6d737a', '#868c92', [(.05, .95, .88, .95)], '#1a2026', '#56636e', .6, .55, warehouse_extra, 14),
        ncf_glass=lambda: facade("ncf_glass", '#2b3038', '#3a404a', [(.02, .98, .14, .98)], '#0d1622', '#3d5f7a', .35, .9, glass_extra, 1),
        ncf_office=lambda: facade("ncf_office", '#8a8984', '#a5a39d', [(.06, .94, .30, .88)], '#101820', '#4b6a80', .8, .0, None, 2),
        ncf_panel=lambda: facade("ncf_panel", '#2e3238', '#454a52', [(.15, .45, .3, .85), (.55, .85, .3, .85)], '#0c141c', '#365066', .45, .75, panel_extra, 3),
        ncf_housing=lambda: facade("ncf_housing", '#a69c8c', '#c3b8a6', [(.12, .52, .3, .9), (.62, .88, .3, .9)], '#121518', '#506270', .85, .0, housing_extra, 4),
        ncf_industrial=lambda: facade("ncf_industrial", '#5a5f63', '#73787b', [(.1, .9, .78, .93)], '#141a1e', '#58656e', .6, .6, industrial_extra, 5),
        ncf_military=lambda: facade("ncf_military", '#363b33', '#4a5046', [(.2, .8, .55, .62)], '#0b0e0c', '#3c4a40', .6, .5, military_extra, 6),
        ncf_stone=lambda: facade("ncf_stone", '#6e675c', '#8d8576', [(.25, .75, .25, .8)], '#14161a', '#4c5a66', .85, .0, stone_extra, 7),
    )
    jobs.update(facades)
    for k, f in jobs.items():
        if not want or k in want:
            f()


if __name__ == '__main__':
    main()
