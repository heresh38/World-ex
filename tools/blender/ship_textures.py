"""Bakes the ship's tiling texture sets (1024 px): interior wall panels, exterior hull plating, floor grating with
lit gaps, padded insulation, chipped painted metal, deck plates, rubber mat, plus a stencil marking atlas.

Hard shapes (panel layouts, vents, bolts, slots, studs) are drawn as periodic signed-distance fields with numpy and
handed to the node graphs as float images; wear, grime and micro surface come from the seamless 4D-torus noise of
textures.G, and every colour / emissive / micro-normal map goes through textures.bake(). The shape normals are
derived from the same periodic height field and blended (whiteout) over the baked micro normal, so all maps tile.
The stencil atlas (stencil_c.png, RGBA, 4x4 cells) is rendered from Blender text and curve objects: own invented
deck numbers, arrows and chevrons only.

Run: blender --background --python tools/blender/ship_textures.py
"""
import bpy, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import bake, G   # noqa: F401  (G is the builder bake() hands to the graph functions below)

N = 1024
S = 1.0 / N
_vv, _uu = np.mgrid[0:N, 0:N].astype(np.float32)
U = (_uu + .5) / N          # u across, v up (Blender pixel rows start at the bottom)
V = (_vv + .5) / N


# ------------------------------------------------------------------ periodic SDF kit
def wrap(d):
    return (d + .5) % 1.0 - .5


def box(cx, cy, hx, hy, r=0.0):
    dx = np.abs(wrap(U - cx)) - hx + r
    dy = np.abs(wrap(V - cy)) - hy + r
    out = np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2)
    return out + np.minimum(np.maximum(dx, dy), 0) - r


def rect(x0, y0, x1, y1, r=0.0):
    return box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, r)


def circle(cx, cy, r):
    return np.sqrt(wrap(U - cx) ** 2 + wrap(V - cy) ** 2) - r


def fill(sd, soft=1.2 * S):
    return np.clip(.5 - sd / soft, 0, 1)


def bevel(sd, w):
    t = np.clip(-sd / w, 0, 1)
    return t * t * (3 - 2 * t)


def dome(sd, r):
    t = np.clip(-sd / r, 0, 1)
    return np.sqrt(1 - (1 - t) ** 2)


def line(sd, w):
    return np.clip(1 - np.abs(sd) / w, 0, 1)


def fnoise(freq, octaves=4, seed=0, rough=.5, aniso=(1, 1)):
    """Seamless fractal noise: band-limited white noise (periodic by construction). ~0..1, mean .5."""
    r = np.random.default_rng(seed)
    fy = np.fft.fftfreq(N)[:, None] * N * aniso[1]; fx = np.fft.fftfreq(N)[None, :] * N * aniso[0]
    k = np.sqrt(fx ** 2 + fy ** 2)
    out = np.zeros((N, N), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        f = freq * 2 ** o
        spec = np.fft.fft2(r.standard_normal((N, N)))
        n = np.real(np.fft.ifft2(spec * np.exp(-((k - f) / (f * .6 + 1e-6)) ** 2))).astype(np.float32)
        out += amp * n / (n.std() + 1e-6); tot += amp; amp *= rough
    return np.clip(out / tot * .25 + .5, 0, 1)


def scratches(count, seed, length=(.03, .15), width=.7 * S):
    r = np.random.default_rng(seed)
    m = np.zeros((N, N), np.float32)
    for _ in range(count):
        cx, cy = r.random(2); a = r.random() * math.pi; L = r.uniform(*length) / 2
        ca, sa = math.cos(a), math.sin(a)
        du = wrap(U - cx); dv = wrap(V - cy)
        along = du * ca + dv * sa; across = -du * sa + dv * ca
        s = np.clip(1 - np.abs(across) / width, 0, 1) * (np.abs(along) < L)
        m = np.maximum(m, s * r.uniform(.3, 1))
    return m


def edge_of(h, k=1.0):
    """Convexity-ish edge mask from a height field (periodic)."""
    lap = 4 * h - np.roll(h, 1, 0) - np.roll(h, -1, 0) - np.roll(h, 1, 1) - np.roll(h, -1, 1)
    return np.clip(lap * k, 0, 1)


def blur(a, it=2):
    for _ in range(it):
        a = (a * 4 + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 8
    return a


def col(h):
    return np.array(bl.hexrgb(h), np.float32)


def lerp(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def plain(h):
    return np.broadcast_to(col(h), (N, N, 3)).copy()


# ------------------------------------------------------------------ images in / out
def image(name, data):
    """Float array(s) -> linear float image used by the node graphs."""
    img = bpy.data.images.new('src_' + name, N, N, alpha=True, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    px = np.ones((N, N, 4), np.float32)
    if isinstance(data, np.ndarray) and data.ndim == 3:
        px[..., :3] = data
    else:
        for i, a in enumerate(data):
            px[..., i] = a
    img.pixels.foreach_set(px.ravel())
    return img


def tex(g, img):
    nd = g.n('ShaderNodeTexImage'); nd.image = img; nd.interpolation = 'Linear'
    g.nt.links.new(g.uv(), nd.inputs['Vector'])
    sep = g.n('ShaderNodeSeparateColor'); g.nt.links.new(nd.outputs['Color'], sep.inputs[0])
    return nd.outputs['Color'], sep.outputs[0], sep.outputs[1], sep.outputs[2]


def save_px(path, rgb, alpha=None, fmt='JPEG'):
    img = bpy.data.images.new('out', N, N, alpha=alpha is not None)
    img.colorspace_settings.name = 'Non-Color'
    px = np.ones((N, N, 4), np.float32); px[..., :3] = np.clip(rgb, 0, 1)
    if alpha is not None:
        px[..., 3] = np.clip(alpha, 0, 1)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path; img.file_format = fmt
    if fmt == 'JPEG':
        bpy.context.scene.render.image_settings.quality = 90
    img.save()
    bpy.data.images.remove(img)


def shape_normal(name, h, k):
    """Blend the shape normal of height field h (whiteout) over the baked micro normal <name>_n.jpg."""
    path = os.path.join(bl.TEXTURES, name + '_n.jpg')
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * .5 * N * k
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * .5 * N * k
    n1 = np.dstack([-dx, -dy, np.ones_like(h)])
    if os.path.exists(path):
        im = bpy.data.images.load(path); im.colorspace_settings.name = 'Non-Color'
        n2 = np.array(im.pixels[:], np.float32).reshape(N, N, 4)[..., :3] * 2 - 1
        bpy.data.images.remove(im)
        n1 = n1 / np.linalg.norm(n1, axis=2, keepdims=True)
        n = np.dstack([n1[..., 0] + n2[..., 0], n1[..., 1] + n2[..., 1], n1[..., 2] * n2[..., 2]])
    else:
        n = n1
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    save_px(path, n * .5 + .5)
    print('[texture] %s_n.jpg (shape + micro)' % name)


def grime(g, c, freq, seed, lo='#ffffff', hi='#a39d92', a=.4, b=.85):
    return g.mix(c, g.ramp(g.noise(freq, 6, .62, seed), [(a, lo), (b, hi)]), 1.0, 'MULTIPLY')


def micro(freq, amt, seed, extra=None):
    def f(g):
        n = g.math('MULTIPLY', g.noise(freq, 4, .55, seed), amt)
        if extra is not None:
            n = g.math('ADD', n, g.math('MULTIPLY', g.noise(extra[0], 3, .5, seed + 1), extra[1]))
        return n
    return f


def setup():
    bl.reset()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.device = 'CPU'
    sc.render.bake.margin = 0
    sc.view_settings.view_transform = 'Standard'   # colours as authored, no filmic curve
    sc.view_settings.look = 'None'
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    return bpy.context.object


def bolt(h, cx, cy, r, top=.25):
    c = circle(cx, cy, r)
    return h + top * dome(c, r * .9) - .12 * line(c, 1.2 * S)


# ------------------------------------------------------------------ 1. interior wall panels (2 m tile)
def ship_wall(p):
    h = np.zeros((N, N), np.float32); dark = np.zeros((N, N), np.float32); emit = np.zeros((N, N, 3), np.float32)
    tint = np.zeros((N, N), np.float32)
    rng = np.random.default_rng(3)
    plates = [(0, 0, .5, .28), (.5, 0, 1, .28), (0, .28, .5, .8), (.5, .28, 1, .8), (0, .8, 1, 1.0)]
    for (x0, y0, x1, y1) in plates:
        sd = rect(x0 + 3 * S, y0 + 3 * S, x1 - 3 * S, y1 - 3 * S, 4 * S)
        h = np.maximum(h, .5 * bevel(sd, 6 * S))
        tint += fill(sd) * rng.uniform(-1, 1)
    for x0 in (0, .5):                       # kick band grooves + bolts
        for gy in (.09, .19):
            h -= .18 * line(rect(x0 + .03, gy - .003, x0 + .47, gy + .003), 3 * S)
        for bx in (.025, .475):
            for by in (.03, .25, .305, .775):
                h = bolt(h, x0 + bx, by, 7 * S)
    sd_in = rect(.06, .34, .44, .74, 10 * S)  # recessed inset with greebles + label plate
    h -= .3 * bevel(sd_in, 5 * S)
    dark = np.maximum(dark, .35 * line(sd_in, 3 * S))
    lab = rect(.16, .63, .34, .69, 3 * S)
    h += .22 * bevel(lab, 3 * S)
    for (a, b, c_, d) in ((.09, .38, .2, .45), (.24, .38, .41, .42), (.33, .45, .41, .58), (.09, .5, .14, .6), (.17, .5, .29, .56)):
        h += .2 * bevel(rect(a, b, c_, d, 2 * S), 3 * S)
    for i in range(4):
        h = bolt(h, .22 + i * .03, .465, 4 * S, .15)
    vent = np.zeros((N, N), np.float32)     # vent grid + lamps + handle
    for i in range(10):
        sl = rect(.58, .4 + i * .028, .79, .4 + i * .028 + .012, 5 * S)
        vent = np.maximum(vent, bevel(sl, 3 * S))
    h -= .45 * vent; dark = np.maximum(dark, vent * .95)
    h += .08 * line(rect(.565, .385, .805, .69, 6 * S), 3 * S)
    lamp = rect(.86, .64, .94, .66, 3 * S)
    h += .12 * bevel(lamp, 2 * S)
    emit = np.maximum(emit, fill(lamp)[..., None] * col('#3fe0ff') * 1.6)
    lamp2 = circle(.9, .6, 6 * S)
    emit = np.maximum(emit, fill(lamp2)[..., None] * col('#ffb040') * 1.6)
    h += .1 * dome(lamp2, 6 * S)
    handle = rect(.84, .42, .96, .47, 12 * S)
    h -= .3 * bevel(handle, 4 * S); dark = np.maximum(dark, .45 * fill(handle))
    lou = np.zeros((N, N), np.float32)       # louvre band: angled slats
    for i in range(36):
        x = .02 + i * .0267
        sl = rect(x, .84, x + .014, .96, 2 * S)
        ramp = np.clip((U - x) / .014, 0, 1)
        lou = np.maximum(lou, fill(sl) * (1 - ramp))
    h -= .35 * lou; dark = np.maximum(dark, lou * .85)
    seam = np.clip(1 - h / .2, 0, 1) * (h < .2)
    base = plain('#dfe2e6') * (1 + .035 * tint)[..., None]
    base = lerp(base, plain('#c7ccd2'), fill(rect(.5, .28, 1, .8)) * .5)     # two-tone plates
    base = lerp(base, plain('#5a6068'), fill(rect(0, 0, 1, .28)) * .75)      # darker kick band
    base = lerp(base, plain('#e9b23a'), fill(lab) * .9)                       # amber label plate
    base = lerp(base, plain('#2c3036'), np.clip(seam * .85 + dark, 0, 1))
    stripe = fill(rect(.0, .785, 1, .795))
    base = lerp(base, plain('#2a8fb8'), stripe * .8)
    ao = np.clip(blur(h, 4) - h + .5, 0, 1)
    base *= (.75 + .25 * (1 - np.clip((ao - .5) * 6, 0, 1)))[..., None]
    edges = edge_of(h, 40)
    img_c = image('wall_c', base); img_m = image('wall_m', [edges, seam, dark]); img_e = image('wall_e', emit)

    def colour(g):
        c, edge, _, _ = tex(g, img_c)[0], *tex(g, img_m)[1:]
        c = grime(g, c, 5, 31, a=.35, b=.9)
        wear = g.math('MULTIPLY', edge, g.math('GREATER_THAN', g.noise(24, 5, .6, 32), .5))
        return g.mix(c, (.62, .64, .67), wear)
    bake(p, 'shipwall', colour, micro(90, .25, 33), lambda g: tex(g, img_e)[0], strength=.15, size=N)
    shape_normal('shipwall', h, .0045)


# ------------------------------------------------------------------ 2. exterior hull plating (4 m tile)
def hull_plate(p):
    rng = np.random.default_rng(21)
    rows = [(0, .22, [0, .31, .56, .82]), (.22, .5, [.12, .45, .7]), (.5, .62, [0, .2, .4, .6, .8]), (.62, 1.0, [.05, .38, .72])]
    h = np.zeros((N, N), np.float32); pid = np.zeros((N, N), np.float32); seams = np.zeros((N, N), np.float32)
    accent = np.zeros((N, N), np.float32)
    for (y0, y1, xs) in rows:
        xs2 = xs + [xs[0] + 1]
        for a, b in zip(xs2[:-1], xs2[1:]):
            sd = rect(a + 1.5 * S, y0 + 1.5 * S, b - 1.5 * S, y1 - 1.5 * S, 1 * S)
            lift = rng.uniform(0, .25)
            h = np.maximum(h, (.5 + lift) * bevel(sd, 2.5 * S))
            pid += fill(sd) * rng.uniform(-1, 1)
            seams = np.maximum(seams, line(sd, 1.6 * S))
            # rivet rows inside each seam
            for k in range(int((b - a) / (12 * S))):
                x = a + 6 * S + k * 12 * S
                if x < b - 4 * S:
                    h = bolt(h, x, y0 + 5 * S, 1.6 * S, .12); h = bolt(h, x, y1 - 5 * S, 1.6 * S, .12)
    accent = fill(rect(0, .5, 1, .62))
    hatch = rect(.43, .7, .63, .92, 8 * S)                # access hatch with fasteners
    h -= .2 * line(hatch, 2 * S); seams = np.maximum(seams, line(hatch, 1.5 * S))
    for (x, y) in ((.45, .72), (.61, .72), (.45, .9), (.61, .9)):
        h = bolt(h, x, y, 3 * S, .2)
    grille = rect(.2, .3, .34, .42, 3 * S)
    for i in range(7):
        sl = rect(.21, .31 + i * .016, .33, .318 + i * .016, 1 * S)
        h -= .3 * bevel(sl, 1.5 * S)
    h -= .1 * bevel(grille, 2 * S)
    near = blur(seams, 6) * 3
    chips = np.clip((fnoise(14, 4, 5) - .62) * 12, 0, 1) * np.clip(near, 0, 1)
    chips = np.maximum(chips, np.clip((fnoise(40, 3, 6) - .9) * 10, 0, 1) * .7)
    h -= .04 * chips
    streak = fnoise(6, 4, 7, aniso=(1, .12))
    base = plain('#e8e5de') * (1 + .03 * pid)[..., None]
    base = lerp(base, plain('#b9bec4'), accent * .8)    # a slightly darker plate row (livery stripes are modelled)
    base = lerp(base, plain('#73777d'), chips)
    base = lerp(base, plain('#2a2c30'), seams * .85)
    base *= (1 - np.clip((streak - .55) * 1.5, 0, .25))[..., None]
    img_c = image('hull_c', base)
    bake(p, 'hullplate', lambda g: grime(g, tex(g, img_c)[0], 3, 41, a=.3, b=.9, hi='#9b968c'),
         micro(70, .2, 42), strength=.12, size=N)
    shape_normal('hullplate', h, .003)


# ------------------------------------------------------------------ 3. floor grating with lit gaps (1 m tile)
def grate(p):
    frame = 1 - fill(rect(.035, .035, .965, .965))
    bars = (np.abs(((U * 20) % 1) - .5) > .32).astype(np.float32)
    bars = np.clip((np.abs(((U * 20) % 1) - .5) - .3) * 40, 0, 1)
    rods = np.clip((.06 - np.abs(((V * 10) % 1) - .5)) * 60, 0, 1)
    solid_ = np.maximum(np.maximum(bars, rods * .9), frame)
    h = np.where(solid_ > .02, .4 + .6 * np.maximum(bars * 1.0, np.maximum(rods * .85, frame)), 0.0).astype(np.float32)
    h = blur(h, 1)
    for (x, y) in ((.018, .018), (.982, .018), (.018, .982), (.982, .982), (.5, .018), (.5, .982), (.018, .5), (.982, .5)):
        h = bolt(h, x, y, 6 * S, .15)
    hole = 1 - np.clip(solid_, 0, 1)
    depthshade = blur(hole, 6)
    glow = fnoise(3, 3, 9) * .7 + .5
    emit = (hole * depthshade)[..., None] * col('#22c8ff') * (glow[..., None] * 1.2)
    base = plain('#9aa1a9')
    edges = edge_of(h, 25)
    base = lerp(base, plain('#d9dde1'), np.clip(edges, 0, 1) * .8)
    base = lerp(base, plain('#5d636b'), frame * .5)
    base = lerp(base, plain('#04070a'), hole * (1 - depthshade * .3))
    img_c = image('grate_c', base); img_e = image('grate_e', emit)
    bake(p, 'grate', lambda g: grime(g, tex(g, img_c)[0], 6, 51, a=.35, b=.9, hi='#8d877b'),
         micro(120, .2, 52), lambda g: tex(g, img_e)[0], strength=.1, size=N)
    shape_normal('grate', h, .0035)


# ------------------------------------------------------------------ 4. padded insulation panels (1.2 m tile)
def padding(p):
    h = np.zeros((N, N), np.float32); inside = np.zeros((N, N), np.float32); stitch = np.zeros((N, N), np.float32)
    for (x0, y0, x1, y1) in ((0, 0, .5, .5), (.5, 0, 1, .5), (0, .5, .5, 1), (.5, .5, 1, 1)):
        sd = rect(x0 + 4 * S, y0 + 4 * S, x1 - 4 * S, y1 - 4 * S, 30 * S)
        h = np.maximum(h, .7 * dome(sd, 60 * S))
        inside = np.maximum(inside, fill(sd, 3 * S))
        st = line(sd + 14 * S, 1.2 * S) * (((U + V) * 140) % 1 > .45)
        stitch = np.maximum(stitch, st)
    # diamond quilting grooves inside the pillows
    seam = 1 - inside
    q1 = np.abs(((U + V) * 4) % 1 - .5); q2 = np.abs(((U - V) * 4) % 1 - .5)
    groove = np.clip(1 - np.minimum(q1, q2) / .012, 0, 1) * (h > .2)
    h -= .18 * blur(groove, 2)
    tuft = np.zeros((N, N), np.float32)
    for i in range(8):
        for j in range(8):
            x, y = (i + .5) / 8, (j + .5) / 8
            if ((i + j) % 2) == 0:
                tuft = np.maximum(tuft, fill(circle(x, y, 5 * S)))
    tuft *= (h > .3)
    h -= .1 * blur(tuft, 2)
    h -= .05 * stitch
    weave = fnoise(160, 2, 61) - .5
    base = plain('#d8d5ce') * (1 + .08 * weave)[..., None]
    base *= (.72 + .28 * np.clip(h / .7, 0, 1))[..., None]
    base = lerp(base, plain('#3b3d40'), seam * .9)
    base = lerp(base, plain('#7a8088'), tuft * .8)
    base = lerp(base, plain('#9da3aa'), stitch * .6)
    img_c = image('pad_c', base)
    bake(p, 'padding', lambda g: grime(g, tex(g, img_c)[0], 4, 62, a=.4, b=.95, hi='#b4ada0'),
         micro(200, .35, 63), strength=.08, size=N)
    shape_normal('padding', h, .0025)


# ------------------------------------------------------------------ 5. painted metal with chipped edges (1 m tile)
def paint_metal(p):
    h = np.zeros((N, N), np.float32)
    sd = rect(3 * S, 3 * S, 1 - 3 * S, 1 - 3 * S, 3 * S)
    h = np.maximum(h, .6 * bevel(sd, 4 * S))
    seam = 1 - fill(sd, 2 * S)
    for (x, y) in ((.03, .03), (.97, .03), (.03, .97), (.97, .97), (.5, .03), (.5, .97), (.03, .5), (.97, .5)):
        c = circle(x, y, 9 * S)
        h -= .2 * bevel(c, 4 * S); h += .12 * dome(circle(x, y, 6 * S), 6 * S)
        h -= .08 * line(rect(x - 4 * S, y - .6 * S, x + 4 * S, y + .6 * S), 1.2 * S)   # screw slot
    near = np.clip(blur(seam, 10) * 4, 0, 1)
    chips = np.clip((fnoise(10, 5, 71) - .58) * 14, 0, 1) * near
    chips = np.maximum(chips, np.clip((fnoise(28, 4, 72) - .9) * 14, 0, 1))
    sc = scratches(60, 73)
    dent = fnoise(2, 2, 74) - .5
    h = h - .06 * chips - .02 * sc + .05 * dent
    base = plain('#cfd2d6')
    base = lerp(base, plain('#8b8f95'), chips)          # bare steel where the paint flaked
    base = lerp(base, plain('#b9bcc0'), sc * .7)
    base = lerp(base, plain('#33363a'), seam * .9)
    base *= (1 - .15 * blur(chips, 2) * (1 - chips))[..., None]
    img_c = image('pm_c', base)
    bake(p, 'paintmetal', lambda g: grime(g, tex(g, img_c)[0], 4, 75, a=.35, b=.9, hi='#a29a8c'),
         micro(140, .18, 76), strength=.08, size=N)
    shape_normal('paintmetal', h, .003)


# ------------------------------------------------------------------ 6. deck plates (2 m tile)
def deck_plate(p):
    h = np.zeros((N, N), np.float32); inside = np.zeros((N, N), np.float32)
    for (x0, y0) in ((0, 0), (.5, 0), (0, .5), (.5, .5)):
        sd = rect(x0 + 2.5 * S, y0 + 2.5 * S, x0 + .5 - 2.5 * S, y0 + .5 - 2.5 * S, 2 * S)
        h = np.maximum(h, .5 * bevel(sd, 3 * S)); inside = np.maximum(inside, fill(sd, 2 * S))
        for k in range(6):
            t = .04 + k * .084
            for (x, y) in ((x0 + t, y0 + .018), (x0 + t, y0 + .482), (x0 + .018, y0 + t), (x0 + .482, y0 + t)):
                h = bolt(h, x, y, 4 * S, .1)
    seam = 1 - inside
    # checker tread on two plates: alternating elongated lugs
    lug = np.zeros((N, N), np.float32)
    for i in range(24):
        for j in range(24):
            cx, cy = (i + .5) / 24, (j + .5) / 24
            inside = (cx < .5) == (cy < .5)
            if not inside or min(abs(cx % .5 - .25), abs(cy % .5 - .25)) > .2:
                continue
            a = math.pi / 4 if (i + j) % 2 == 0 else -math.pi / 4
            du = wrap(U - cx); dv = wrap(V - cy)
            x = du * math.cos(a) + dv * math.sin(a); y = -du * math.sin(a) + dv * math.cos(a)
            d = np.sqrt((x / 9) ** 2 + (y / 2.2) ** 2) * N - 1
            lug = np.maximum(lug, np.clip(1 - d, 0, 1))
    lug = np.sqrt(np.clip(lug, 0, 1))
    h += .18 * lug
    hatch = rect(.6, .1, .9, .4, 6 * S)                       # recessed hatch + lift ring on a plain plate
    h -= .25 * line(hatch, 2 * S)
    ring = circle(.75, .35, 10 * S)
    h -= .2 * line(ring, 2 * S)
    strip = rect(.05, .6, .45, .66, 2 * S)                    # anti-slip strip
    h += .05 * bevel(strip, 2 * S) * (fnoise(200, 1, 81) > .5)
    wear = fnoise(5, 4, 82)
    base = plain('#6a6f77')
    base = lerp(base, plain('#9ca2aa'), lug * np.clip((wear - .45) * 4, 0, 1))
    base = lerp(base, plain('#2f3237'), fill(strip) * .9)
    base = lerp(base, plain('#e0b028'), line(hatch, 3 * S) * .9)
    base = lerp(base, plain('#24262a'), seam * .9)
    base *= (.9 + .2 * (wear - .5))[..., None]
    img_c = image('deck_c', base)
    bake(p, 'deckplate', lambda g: grime(g, tex(g, img_c)[0], 3, 83, a=.3, b=.85, hi='#8f8a80'),
         micro(110, .2, 84), strength=.1, size=N)
    shape_normal('deckplate', h, .003)


# ------------------------------------------------------------------ 7. rubber floor mat (0.5 m tile, coin studs)
def rubber_mat(p):
    h = np.zeros((N, N), np.float32)
    for i in range(8):
        for j in range(8):
            h = np.maximum(h, dome(circle((i + .5) / 8, (j + .5) / 8, 22 * S), 6 * S))
    dust = np.clip(1 - h, 0, 1) * fnoise(8, 4, 91)
    base = plain('#2a2c2f')
    base = lerp(base, plain('#4a4743'), np.clip((dust - .35) * 2, 0, 1) * .6)
    base = lerp(base, plain('#3a3c40'), h * .5)
    img_c = image('rub_c', base)
    bake(p, 'rubbermat', lambda g: grime(g, tex(g, img_c)[0], 4, 92, a=.3, b=.9, hi='#c9c2b5'),
         micro(220, .3, 93), strength=.08, size=N)
    shape_normal('rubbermat', h, .002)


# ------------------------------------------------------------------ 8. stencil atlas (rendered text + shapes)
STENCILS = ['01', '02', '03', 'D-2', 'ARROW', 'CHEVRON', 'BAY 1', 'HAZ',
            'AFT', 'FWD', 'PWR', 'O2', 'LIFT', 'MAX 4T', 'CORE', 'X']


def stencil_atlas():
    bl.reset()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 16; sc.cycles.device = 'CPU'
    sc.render.resolution_x = sc.render.resolution_y = N
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w
    em = bpy.data.materials.new('ink')
    nt = em.node_tree
    for nd in list(nt.nodes):
        if nd.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(nd)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (1, 1, 1, 1)
    nt.links.new(e.outputs[0], [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0].inputs['Surface'])

    def text(body, x, y, size):
        cu = bpy.data.curves.new('t', 'FONT'); cu.body = body; cu.size = size
        cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.extrude = 0
        try:
            cu.font = bpy.data.fonts.load('<builtin>')
        except Exception:
            pass
        o = bpy.data.objects.new('t', cu); sc.collection.objects.link(o)
        o.location = (x, y, 0); o.data.materials.append(em)
        return o

    def poly(pts, x, y, s):
        me = bpy.data.meshes.new('p'); me.from_pydata([(x + px * s, y + py * s, 0) for px, py in pts], [], [list(range(len(pts)))])
        o = bpy.data.objects.new('p', me); sc.collection.objects.link(o); me.materials.append(em)
        return o

    cell = 1.0
    for k, s in enumerate(STENCILS):
        cx = (k % 4) * cell + .5; cy = 3.5 - (k // 4) * cell     # row 0 at the top
        if s == 'ARROW':
            poly([(-.35, -.08), (.1, -.08), (.1, -.22), (.38, 0), (.1, .22), (.1, .08), (-.35, .08)], cx, cy, 1)
        elif s == 'CHEVRON':
            for d in (-.2, 0, .2):
                poly([(-.08 + d, -.3), (.04 + d, -.3), (.2 + d, 0), (.04 + d, .3), (-.08 + d, .3), (.08 + d, 0)], cx, cy, 1)
        elif s == 'HAZ':
            poly([(-.36, -.3), (.36, -.3), (0, .34)], cx, cy, 1)
            t = text('!', cx, cy - .06, .42); t.location.z = .01
            m2 = bpy.data.materials.new('cut'); m2.diffuse_color = (0, 0, 0, 1)
            nt2 = m2.node_tree; nt2.nodes.remove(nt2.nodes['Principled BSDF'])
            hold = nt2.nodes.new('ShaderNodeHoldout')
            nt2.links.new(hold.outputs[0], nt2.nodes['Material Output'].inputs['Surface'])
            t.data.materials.clear(); t.data.materials.append(m2)
        elif s == 'X':
            for a in (1, -1):
                poly([(-.32, -.32 * a + .06 * a), (-.26, -.32 * a), (.32, .32 * a - .06 * a), (.26, .32 * a)], cx, cy, 1)
        else:
            size = .5 if len(s) <= 2 else .34 if len(s) <= 4 else .26
            text(s, cx, cy, size)
        # thin underline bar on text cells
        if s not in ('ARROW', 'CHEVRON', 'HAZ', 'X'):
            poly([(-.38, -.36), (.38, -.36), (.38, -.33), (-.38, -.33)], cx, cy, 1)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 4.0; cam.location = (2, 2, 5)
    path = os.path.join(bl.TEXTURES, '_stencil_raw.png')
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path)
    px = np.array(im.pixels[:], np.float32).reshape(N, N, 4)
    a = px[..., 3]
    # spray-paint wear: patchy loss + speckle
    a = a * np.clip(fnoise(6, 4, 101) * 2.2 - .35, 0, 1) * np.clip(1.15 - (fnoise(120, 2, 102) > .62) * .7, 0, 1)
    out = np.ones((N, N, 3), np.float32) * .92
    save_px(os.path.join(bl.TEXTURES, 'stencil_c.png'), out, a, fmt='PNG')
    os.remove(path)
    print('[texture] stencil_c.png')


def main():
    """All sets, or only the ones named after '--' (shipwall hullplate grate padding paintmetal deckplate rubbermat stencil)."""
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = [w for w in only if w]
    p = setup()
    for name, fn in (('shipwall', ship_wall), ('hullplate', hull_plate), ('grate', grate), ('padding', padding),
                     ('paintmetal', paint_metal), ('deckplate', deck_plate), ('rubbermat', rubber_mat)):
        if not only or name in only:
            fn(p)
    if not only or 'stencil' in only:
        stencil_atlas()


if __name__ == '__main__':
    main()
