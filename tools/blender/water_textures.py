"""Water textures from Blender's ocean simulation (FFT spectrum on a periodic tile, so every map wraps exactly).

assets/textures/water_n1.jpg     1024 tangent normal: short wind ripples (fast-scrolling detail layer)
assets/textures/water_n2.jpg     1024 tangent normal: longer swells (slow layer)
assets/textures/water_foam.jpg   1024 foam/whitecap mask (Jacobian of the choppy ocean + lacy breakup)
assets/textures/water_spray.png  256x512 RGBA splash plume sprite (droplet streaks fanning up from the impact)
The game's water material (src/game/water.js) scrolls the two normal maps against each other, adds ring ripples
from impacts on top, and uses the foam map on shorelines, wakes and splashes.
Usage: blender --background --python tools/blender/water_textures.py
"""
import bpy, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl

RES = 32          # ocean resolution 32 -> 1024 x 1024 grid


def ocean_field(size, wind, align, direction, scale, chop=0.0, seed=1, spectrum='PHILLIPS', scale_min=.01, depth=200.0):
    """Evaluate Blender's ocean modifier on a periodic tile; returns (height, disp_x, disp_z) as N x N arrays."""
    bl.reset()
    bpy.ops.mesh.primitive_plane_add(size=2)
    o = bpy.context.object
    m = o.modifiers.new('ocean', 'OCEAN')
    m.geometry_mode = 'GENERATE'; m.resolution = RES; m.viewport_resolution = RES
    m.spatial_size = int(size); m.wind_velocity = wind; m.wave_alignment = align; m.wave_direction = direction
    m.wave_scale = scale; m.choppiness = chop; m.random_seed = seed; m.depth = depth
    m.wave_scale_min = scale_min
    try:
        m.spectrum = spectrum
    except Exception:
        pass
    m.time = 1.0
    dg = bpy.context.evaluated_depsgraph_get()
    me = o.evaluated_get(dg).to_mesh()
    n = len(me.vertices)
    co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    side = int(round(math.sqrt(n)))
    # grid indices from the undisplaced layout: the modifier writes rows of `side` vertices
    co = co.reshape(side, side, 3)
    if abs(co[0, 1, 0] - co[0, 0, 0]) < abs(co[1, 0, 0] - co[0, 0, 0]):
        co = co.transpose(1, 0, 2)
    N = side - 1                       # last row/column repeats the first (periodic tile)
    cell = size / N
    gx = np.arange(side) * cell - size / 2
    if co[1, 0, 1] < co[0, 0, 1]:
        co = co[::-1]
    # arrays are [row = y (bottom-up, like Blender image pixels), col = x]
    h = co[:N, :N, 2].copy()
    dx = (co[:N, :N, 0] - gx[None, :N]) if chop else np.zeros_like(h)
    dy = (co[:N, :N, 1] - gx[:N, None]) if chop else np.zeros_like(h)
    o.evaluated_get(dg).to_mesh_clear()
    return h, dx, dy, cell


def ddx(a, cell):
    return (np.roll(a, -1, 1) - np.roll(a, 1, 1)) / (2 * cell)


def ddy(a, cell):
    return (np.roll(a, -1, 0) - np.roll(a, 1, 0)) / (2 * cell)


def blur(a, r):
    """Periodic box blur (3 passes ~ gaussian)."""
    for _ in range(3):
        acc = np.zeros_like(a)
        for k in range(-r, r + 1):
            acc += np.roll(a, k, 0)
        a = acc / (2 * r + 1)
        acc = np.zeros_like(a)
        for k in range(-r, r + 1):
            acc += np.roll(a, k, 1)
        a = acc / (2 * r + 1)
    return a


def save(name, arr, color=True, quality=94, top_down=False):
    """arr: H x W x 3 (or 4 for png) float 0..1, row 0 = bottom (Blender pixel order) unless top_down."""
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), np.float32)], 2)
    png = name.endswith('.png')
    img = bpy.data.images.new(name, w, h, alpha=png, float_buffer=False)
    if not color:
        img.colorspace_settings.name = 'Non-Color'
    img.pixels = np.ascontiguousarray(arr[::-1] if top_down else arr).astype(np.float32).ravel()
    img.filepath_raw = os.path.join(bl.TEXTURES, name)
    img.file_format = 'PNG' if png else 'JPEG'
    sc = bpy.context.scene
    sc.render.image_settings.quality = quality
    img.save(quality=quality) if not png else img.save()
    print('[texture]', name, w, 'x', h)


def normal_map(h, cell, slope_rms):
    gx, gy = ddx(h, cell), ddy(h, cell)
    k = slope_rms / max(1e-6, math.sqrt(float(np.mean(gx * gx + gy * gy))))
    nx, ny, nz = -gx * k, -gy * k, np.ones_like(h)      # rows run bottom-up, so +v = +y
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / ln * .5 + .5, ny / ln * .5 + .5, nz / ln * .5 + .5], 2).astype(np.float32)


def main():
    # 1) wind ripples: short, choppy, broad directional spread
    h1, _, _, c1 = ocean_field(12, 7.5, .15, .6, 1.0, seed=11, scale_min=.09)
    h1b, _, _, _ = ocean_field(12, 4.0, .0, 2.1, .6, seed=12, scale_min=.06)
    h = blur(h1 + h1b * .55, 1)
    h = (h - blur(h, 40)) + (blur(h, 40) - h.mean()) * .35     # keep the ripples, tame the long swell inside the tile
    save('water_n1.jpg', normal_map(h, c1, .42), color=False)
    # 2) swells: long, aligned crests with a little cross-sea
    h2, dx2, dy2, c2 = ocean_field(96, 16.0, .7, .35, 1.0, chop=1.4, seed=21, spectrum='JONSWAP' if hasattr(bpy.types, 'OceanModifier') else 'PHILLIPS')
    save('water_n2.jpg', normal_map(h2, c2, .30), color=False)
    # 3) foam: where the choppy surface folds (Jacobian < 1) plus lacy breakup from a fine ripple field
    J = (1 + ddx(dx2, c2)) * (1 + ddy(dy2, c2)) - ddy(dx2, c2) * ddx(dy2, c2)
    fold = np.clip((1.05 - J) * 1.6, 0, 1)
    fold = np.maximum(fold, blur(fold, 6) * 1.4)
    fine, _, _, _ = ocean_field(12, 9.0, .0, 0.0, 1.0, seed=31)
    fine = (fine - fine.mean()) / (fine.std() + 1e-6)
    lace = np.clip(1 - np.abs(fine) * 1.25, 0, 1) ** 1.6              # bubbly cell borders
    fine2, _, _, _ = ocean_field(12, 5.0, .0, 1.0, 1.0, seed=32)
    fine2 = (fine2 - fine2.mean()) / (fine2.std() + 1e-6)
    lace2 = np.clip(1 - np.abs(fine2) * 1.6, 0, 1) ** 2
    base = np.clip(fold, 0, 1)
    foam = np.clip(base * (.35 + .65 * lace) + lace2 * .35 + lace * .25, 0, 1)
    foam = np.clip((foam - .12) * 1.25, 0, 1)
    save('water_foam.jpg', np.repeat(foam[:, :, None], 3, 2).astype(np.float32))
    # 4) spray plume sprite: droplet streaks fanning up from a bright base, soft mist edge
    W, H = 256, 512
    rs = np.random.RandomState(5)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xx - W / 2) / (W / 2); v = 1 - yy / H                    # v = 0 at the bottom
    a = np.zeros((H, W), np.float32)
    for k in range(240):
        ang = rs.normal(0, .32); length = .35 + rs.rand() * .65; w = .006 + rs.rand() * .012
        t = np.clip(v / length, 0, 1)
        cx = np.sin(ang) * v * 1.2 + np.sin(ang) * v * v * .4
        d = np.abs(u - cx)
        streak = np.exp(-(d / w) ** 2) * (v < length) * (1 - t) ** .6
        a += streak * (.4 + rs.rand() * .6)
    for k in range(900):        # droplets
        dv = rs.rand() ** .7; ang = rs.normal(0, .38)
        cx = np.sin(ang) * dv * 1.25; r = .006 + rs.rand() * .012
        d2 = ((u - cx) / r) ** 2 + ((v - dv) / (r * W / H * 2)) ** 2
        m = d2 < 9
        a[m] += np.exp(-d2[m]) * (.6 + rs.rand() * .4)
    core = np.exp(-(u / (.28 + v * .5)) ** 2) * np.clip(1 - v * 1.6, 0, 1)
    a = np.clip(a * .45 + core * .55, 0, 1) ** 1.15
    a *= np.clip((1 - np.abs(u)) * 3, 0, 1) * np.clip(v * 30, 0, 1)
    rgba = np.zeros((H, W, 4), np.float32)
    rgba[..., 0] = .92 + .08 * v; rgba[..., 1] = .96 + .04 * v; rgba[..., 2] = 1.0; rgba[..., 3] = a
    save('water_spray.png', rgba, top_down=True)


main()
