"""City trees and shrubs for the Unreal city (static instances, Nanite, masked foliage) -> assets/models/city_trees.glb.

Plants (one mesh object each, origin at the trunk base on the ground, Z up, metres):
  street (pruned, clear trunk ~2.5-3 m): CT_plane CT_linden CT_maple CT_birch CT_cherry CT_pear
  park (natural form, low branches):     CT_oak CT_willow CT_pine
  shrubs:                                CT_shrub_a CT_shrub_b CT_hedge (3 m along X) CT_grass_clump

Construction
  Broadleaf skeletons grow by space colonisation towards attractor points that fill a crown envelope (clumped, biased
  to the shell, irregular lobes); the pine grows by whorls. Radii follow the pipe model; branches become tapered tubes
  (10 sides at the trunk down to 3 at twigs, parallel-transport frames, root flare with buttresses). The thinnest
  twig radius drawn is chosen so the bark stays inside its triangle budget.
  Foliage = leaf-cluster cards (V-folded quads, 4 tris; flat quads on shrubs) whose twig base sits on a drawn branch,
  so no leaf floats. Willow foliage = hanging ribbons. Custom split normals are bent out of the crown volume.
  COLOR_0 = ambient occlusion (inner / lower crown darker) with a slight per-card tint; glTF multiplies it into the
  base colour, the Blender materials do the same.

Materials (names are an API)
  ct_bark_<plane|rough|birch|cherry|pine>  opaque, colour + normal map
  ct_leaves_<broad|maple|heart|small|cherry|ovate|oak|willow|needles|box|shrub|grass>  alpha MASK 0.5, double sided
  ct_leafcore  opaque dark green core inside the clipped hedge and the mound shrub (stops see-through holes)

Textures (assets/textures, painted with numpy, nothing imported)
  ct_leaves_<kind>.png  RGBA cluster atlas (one spray per card, twig base at the bottom centre; willow: tiling hanging
                        twig, base at the top; grass: 4 blade columns)
  ct_bark_<kind>_c.jpg / ct_bark_<kind>_n.png (tangent normal, OpenGL); one tile = 0.5 m around x 1 m up

Extras on every root: ct = {h, w, kind, trunk_r, clear, species}.

Run: blender --background --python tools/blender/city_trees.py [-- [--no-tex] [plane oak ...]]
     (names build only those plants into city_trees_partial.glb)
"""
import bpy, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl

F32 = np.float32
TEX = bl.TEXTURES
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = [a for a in ARGV if not a.startswith('--')]
NO_TEX = '--no-tex' in ARGV
UP = np.array([0., 0., 1.])


def srgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], F32)


def mix(a, b, t):
    t = np.asarray(t, F32)
    return a + (b - a) * t[..., None]


# =====================================================================================================================
# texture helpers (arrays are y-up: row 0 = bottom = UV v 0)
# =====================================================================================================================
def save_img(name, px, srgb_space=True, jpg=False):
    h, w, c = px.shape
    im = bpy.data.images.new(name, w, h, alpha=(c == 4))
    if not srgb_space:
        im.colorspace_settings.name = 'Non-Color'
    out = np.ones((h, w, 4), F32)
    out[..., :c] = np.clip(px, 0, 1)
    im.pixels.foreach_set(out.ravel())
    ext = '.jpg' if jpg else '.png'
    im.filepath_raw = os.path.join(TEX, name + ext)
    im.file_format = 'JPEG' if jpg else 'PNG'
    bpy.context.scene.render.image_settings.quality = 90
    im.save()
    bpy.data.images.remove(im)


def noise(h, w, sx, sy, seed):
    """Seamless band-limited noise, zero mean / unit std; sx, sy = feature cycles across the width / height."""
    r = np.random.default_rng(seed)
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.fftfreq(w)[None, :] * w
    spec = (r.normal(size=(h, w)) + 1j * r.normal(size=(h, w))) * np.exp(-((fx / sx) ** 2 + (fy / sy) ** 2))
    spec[0, 0] = 0
    v = np.fft.ifft2(spec).real
    return ((v - v.mean()) / (v.std() + 1e-9)).astype(F32)


def fbm(h, w, sx, sy, seed, octaves=4, gain=.5):
    v = np.zeros((h, w), F32); a = 1.0; t = 0.0
    for o in range(octaves):
        v += a * noise(h, w, sx * 2 ** o, sy * 2 ** o, seed + 31 * o); t += a * a; a *= gain
    return v / math.sqrt(t)


def voronoi(h, w, n, seed, sy=1.0, warp=0.0):
    """Periodic cellular noise: f1, f2 (pixels) and the cell id; sy < 1 stretches cells vertically."""
    r = np.random.default_rng(seed)
    pts = r.random((n, 2)) * (w, h)
    yy, xx = np.mgrid[0:h, 0:w].astype(F32)
    if warp:
        xx = xx + warp * noise(h, w, 4, 4, seed + 1)
        yy = yy + warp * noise(h, w, 4, 4, seed + 2)
    f1 = np.full((h, w), 1e9, F32); f2 = f1.copy(); ids = np.zeros((h, w), np.int32)
    for i, (px, py) in enumerate(pts):
        dx = np.abs(xx - px) % w; dx = np.minimum(dx, w - dx)
        dy = np.abs(yy - py) % h; dy = np.minimum(dy, h - dy)
        d = np.sqrt(dx * dx + (dy * sy) ** 2)
        closer = d < f1
        f2 = np.where(closer, f1, np.minimum(f2, d))
        ids = np.where(closer, i, ids)
        f1 = np.where(closer, d, f1)
    return f1, f2, ids


def hash01(ids, seed=0):
    return (((ids.astype(np.int64) * 2654435761 + seed * 97531) % 4294967296) / 4294967296.0).astype(F32)


def normal_from(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * .5 * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * .5 * strength      # rows run up (+V)
    n = np.stack([-gx, -gy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * .5 + .5


def dashes(h, w, n, seed, lx, ly):
    """Horizontal elliptical marks (lenticels), wrapping in x."""
    r = np.random.default_rng(seed)
    m = np.zeros((h, w), F32)
    for _ in range(n):
        cx, cy = r.random() * w, r.random() * h
        a, b = r.uniform(*lx), r.uniform(*ly)
        y0, y1 = max(0, int(cy - b) - 1), min(h, int(cy + b) + 2)
        xs = np.arange(int(cx - a) - 1, int(cx + a) + 2)
        if y1 <= y0:
            continue
        X, Y = np.meshgrid(xs + .5, np.arange(y0, y1) + .5)
        v = np.clip((1 - ((X - cx) / a) ** 2 - ((Y - cy) / b) ** 2) * 3, 0, 1).astype(F32)
        ix = np.ix_(np.arange(y0, y1), xs % w)
        m[ix] = np.maximum(m[ix], v)
    return m


def box_blur(img, r):
    """Separable wrap-around box blur (radius r pixels)."""
    out = img.astype(F32)
    for ax in (0, 1):
        n = out.shape[ax]
        pad = np.concatenate([np.take(out, range(n - r - 1, n), ax), out, np.take(out, range(0, r), ax)], ax)
        c = np.cumsum(pad, ax, dtype=np.float64)
        hi = np.take(c, range(2 * r + 1, n + 2 * r + 1), ax)
        lo = np.take(c, range(0, n), ax)
        out = ((hi - lo) / (2 * r + 1)).astype(F32)
    return out


# =====================================================================================================================
# bark
# =====================================================================================================================
BW, BH = 512, 1024        # one tile = 0.5 m around the stem x 1 m along it


def bark_rough(seed):
    f1, f2, ids = voronoi(BH, BW, 95, seed, sy=.27, warp=9)
    plate = np.clip((f2 - f1) / 11, 0, 1) ** .55
    big = fbm(BH, BW, 3, 2, seed + 5, 3)
    fine = fbm(BH, BW, 48, 24, seed + 6, 3)
    fibre = noise(BH, BW, 60, 3, seed + 7)
    r = hash01(ids, seed)
    hgt = plate * (.72 + .12 * r + .06 * big) + .045 * fine + .035 * fibre
    col = mix(srgb('#5a4f44'), srgb('#80766a'), np.clip(r * .8 + .12 * big + .1, 0, 1))
    col = mix(srgb('#241d18'), col, np.clip(plate * 1.15, 0, 1))
    lichen = np.clip(noise(BH, BW, 5, 4, seed + 8) * .6 - .55, 0, 1) * plate
    col = mix(col, srgb('#8a9077'), lichen * .7)
    col *= (1 + .07 * fine)[..., None]
    return col, hgt, 5.0


def bark_plane(seed):
    f1, f2, ids = voronoi(BH, BW, 60, seed, sy=.85, warp=26)
    r = hash01(ids, seed)
    pal = np.array([srgb(c) for c in ('#d8d1ae', '#aaa375', '#8f977f', '#c4b48b', '#7f7d6f', '#b9bba1', '#9c8f6a')])
    col = pal[(r * len(pal)).astype(int) % len(pal)]
    var = fbm(BH, BW, 12, 12, seed + 3, 3)
    col = col * (1 + .05 * var)[..., None]
    edge = np.clip((f2 - f1) / 3.5, 0, 1)
    col = col * (.8 + .2 * edge)[..., None]
    fine = fbm(BH, BW, 60, 40, seed + 4, 3)
    hgt = np.where(r < .45, .62, .48) * (.5 + .5 * edge) + .03 * fine + .04 * var
    return col, hgt.astype(F32), 3.0


def bark_birch(seed):
    fine = fbm(BH, BW, 40, 30, seed, 3)
    col = mix(srgb('#e2ded2'), srgb('#f1efe8'), np.clip(.5 + .3 * fbm(BH, BW, 6, 10, seed + 1, 3), 0, 1))
    col *= (1 + .025 * fine)[..., None]
    peel = np.clip((noise(BH, BW, 1.5, 22, seed + 2) - 1.1) * 2, 0, 1)
    col = mix(col, srgb('#d6c3a2'), peel * .6)
    len_ = dashes(BH, BW, 240, seed + 3, (6, 34), (1.3, 3.2))
    col = mix(col, srgb('#463d35'), len_ * .9)
    patch = np.clip((noise(BH, BW, 2.2, 9, seed + 4) + .4 * fine - 1.35) * 2.2, 0, 1)
    col = mix(col, srgb('#2c2824'), patch * .92)
    grey = np.clip(noise(BH, BW, 3, 5, seed + 5) * .5 - .3, 0, 1)
    col = mix(col, srgb('#a9a69b'), grey * .35)
    hgt = .5 - .32 * len_ - .12 * patch + .12 * peel + .03 * fine
    return col, hgt.astype(F32), 4.0


def bark_cherry(seed):
    band = noise(BH, BW, 1.5, 36, seed)
    fine = fbm(BH, BW, 40, 30, seed + 1, 3)
    col = mix(srgb('#5b3127'), srgb('#7d4638'), np.clip(.5 + .25 * band + .15 * fine, 0, 1))
    len_ = dashes(BH, BW, 170, seed + 2, (12, 52), (1.6, 3.6))
    col = mix(col, srgb('#a48b72'), len_ * .85)
    sheen = np.clip(noise(BH, BW, 2, 20, seed + 3) * .4, 0, 1)
    col = mix(col, srgb('#8f6a5e'), sheen * .3)
    hgt = .5 + .22 * len_ + .06 * band + .03 * fine
    return col, hgt.astype(F32), 4.0


def bark_pine(seed):
    f1, f2, ids = voronoi(BH, BW, 120, seed, sy=.55, warp=12)
    r = hash01(ids, seed); r2 = hash01(ids, seed + 7)
    edge = np.clip((f2 - f1) / 8, 0, 1)
    fine = fbm(BH, BW, 50, 30, seed + 3, 3)
    col = mix(srgb('#6f412c'), srgb('#a2714e'), r)
    col = np.where((r2 > .62)[..., None], mix(col, srgb('#6b625a'), .65), col)
    flake = np.clip((f1 / 14) % 1.0, 0, 1)                      # layered flakes inside each plate
    col = col * (.86 + .14 * flake)[..., None] * (1 + .06 * fine)[..., None]
    col = mix(srgb('#22170f'), col, edge ** .6)
    hgt = edge ** .5 * (.62 + .3 * r) + .05 * flake + .04 * fine
    return col, hgt.astype(F32), 5.5


BARK = {'rough': bark_rough, 'plane': bark_plane, 'birch': bark_birch, 'cherry': bark_cherry, 'pine': bark_pine}


def make_bark(kind, seed):
    col, hgt, strength = BARK[kind](seed)
    save_img('ct_bark_%s_c' % kind, col, jpg=True)
    save_img('ct_bark_%s_n' % kind, normal_from(hgt * 6, strength), srgb_space=False)
    print('[city_trees] bark %s' % kind)


# =====================================================================================================================
# leaf cluster atlases
# =====================================================================================================================
class Canvas:
    def __init__(s, w, h, seed):
        s.w, s.h = w, h
        s.rgb = np.zeros((h, w, 3), F32)
        s.a = np.zeros((h, w), F32)
        s.grain = (1 + .045 * noise(h, w, w / 6, h / 6, seed) + .04 * noise(h, w, 8, 8, seed + 1)).astype(F32)

    def region(s, cx, cy, rad):
        x0, x1 = max(0, int(cx - rad)), min(s.w, int(cx + rad) + 2)
        y0, y1 = max(0, int(cy - rad)), min(s.h, int(cy + rad) + 2)
        if x0 >= x1 or y0 >= y1:
            return None
        X, Y = np.meshgrid(np.arange(x0, x1, dtype=F32) + .5, np.arange(y0, y1, dtype=F32) + .5)
        return (slice(y0, y1), slice(x0, x1)), X, Y

    def over(s, sl, a, rgb):
        A = s.a[sl]; C = s.rgb[sl]
        na = a + A * (1 - a)
        s.rgb[sl] = (rgb * a[..., None] + C * (A * (1 - a))[..., None]) / np.maximum(na, 1e-6)[..., None]
        s.a[sl] = na

    def finish(s):
        """RGBA with the colour bled into the transparent area (no dark fringes in the mips)."""
        w = (s.a > .02).astype(F32)
        rgb = s.rgb.copy()
        known = w > 0
        for r in (2, 6, 18, 54, 160):
            acc = box_blur(s.rgb * w[..., None], r); ww = box_blur(w, r)
            fill = acc / np.maximum(ww, 1e-6)[..., None]
            new = (~known) & (ww > 1e-4)
            rgb[new] = fill[new]
            known = known | new
        if (~known).any():
            rgb[~known] = (s.rgb * w[..., None]).sum((0, 1)) / max(w.sum(), 1)
        out = np.concatenate([rgb, s.a[..., None]], -1)
        return out


def vdir(a):
    return np.array([math.cos(a), math.sin(a)], F32)


def bezier(p0, p1, p2, n):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def tangent_angle(pts, i):
    d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
    return math.atan2(d[1], d[0])


def line(cv, p0, p1, r0, r1, col):
    p0 = np.asarray(p0, F32); p1 = np.asarray(p1, F32)
    c = (p0 + p1) * .5
    reg = cv.region(c[0], c[1], np.linalg.norm(p1 - p0) * .5 + max(r0, r1) + 2)
    if reg is None:
        return
    sl, X, Y = reg
    d = p1 - p0; dd = max(float(d @ d), 1e-6)
    t = np.clip(((X - p0[0]) * d[0] + (Y - p0[1]) * d[1]) / dd, 0, 1)
    ex = X - (p0[0] + t * d[0]); ey = Y - (p0[1] + t * d[1])
    dist = np.sqrt(ex * ex + ey * ey)
    r = r0 + (r1 - r0) * t
    a = np.clip(r - dist + .5, 0, 1)
    if a.max() <= 0:
        return
    k = np.clip(dist / np.maximum(r, .5), 0, 1)
    shade = 1.12 - .42 * k * k
    cv.over(sl, a, col[None, None, :] * shade[..., None] * cv.grain[sl][..., None])


def polyline(cv, pts, r0, r1, col):
    n = len(pts)
    for i in range(n - 1):
        line(cv, pts[i], pts[i + 1], r0 + (r1 - r0) * i / (n - 1), r0 + (r1 - r0) * (i + 1) / (n - 1), col)


# blade leaves: half width, widest-point exponent p, tip exponent q, serration amp/freq, lobes (amp, count)
BLADE = {
    'ovate': (.27, .72, .75, .015, 30, None),
    'small': (.34, .58, .9, .07, 24, None),
    'box': (.31, 1.0, .5, 0, 0, None),
    'shrub': (.3, .8, .7, .025, 22, None),
    'oak': (.36, 1.1, .55, 0, 0, (.45, 4.5)),
    'lance': (.085, .9, .8, .012, 40, None),
    'young': (.26, .8, .8, .03, 26, None),
    'heart': (.47, .5, .55, .035, 28, None),
}
# palmate leaves: base radius, lobes (angle, amp, sigma) mirrored, serration amp/freq
PALM = {
    'broad': (.24, [(0, .30, .30), (.97, .26, .30), (1.9, .11, .32)], .03, 16),
    'maple': (.18, [(0, .34, .25), (.95, .31, .25), (1.85, .15, .27)], .05, 20),
}


def shape(kind, u, v):
    """Signed distance (in leaf lengths, > 0 inside), interior factor e and vein strength."""
    av = np.abs(v)
    if kind in PALM:
        base, lobes, serr, sf = PALM[kind]
        def R(phi):
            r = base + 0 * phi
            for ang, amp, sig in lobes:
                r = r + amp * np.exp(-((phi - ang) / sig) ** 2)
                if ang:
                    r = r + amp * np.exp(-((phi + ang) / sig) ** 2)
            return r
        S = float(R(np.array(math.pi))) + float(R(np.array(0.0)))
        c = float(R(np.array(math.pi))) / S
        du = u - c
        rho = np.sqrt(du * du + v * v)
        phi = np.arctan2(v, du)
        Rf = R(phi) / S
        Rf = Rf * (1 + serr * (np.abs((phi * sf / math.pi) % 1.0 - .5) * 2 - .5))
        d = Rf - rho
        e = np.clip(1 - rho / np.maximum(Rf, 1e-4), 0, 1)
        vein = np.zeros_like(u)
        for ang, amp, sig in lobes:
            for sgn in ((1, -1) if ang else (1,)):
                dphi = np.angle(np.exp(1j * (phi - sgn * ang)))
                vein = np.maximum(vein, np.exp(-(dphi * rho / .009) ** 2) * (rho < Rf * .9))
        return d, e, vein
    hw, p, q, serr, sf, lob = BLADE[kind]
    if kind == 'heart':
        uu = (u + .08) / 1.08
    else:
        uu = u
    uc = np.clip(uu, 1e-4, 1)
    f = hw * np.clip(np.sin(math.pi * uc ** p), 0, 1) ** q
    if lob:
        amp, cnt = lob
        f = f * (1 - amp + amp * np.abs(np.sin(math.pi * (uc * cnt + .25))) ** .7)
    if serr:
        f = f * (1 + serr * (np.abs((uc * sf) % 1.0 - .5) * 2 - .5))
    inside_u = (uu >= 0) & (uu <= 1)
    d = np.where(inside_u, f - av, -np.abs(uu - np.clip(uu, 0, 1)) - av)
    if kind == 'heart':
        notch = .07 * (1 - uu / .13)
        d = np.where(uu < .13, np.minimum(d, av - notch), d)
    e = np.clip(1 - av / np.maximum(f, 1e-4), 0, 1)
    midrib = np.exp(-(v / .011) ** 2) * (uu > .02) * (uu < .92)
    s = uu - av * 1.25
    nv = 7 if kind not in ('lance', 'box') else 12
    vein = (.5 + .5 * np.cos(2 * math.pi * s * nv)) ** 18 * (av > .015) * (e > .12)
    return d, e, np.maximum(midrib, vein * .6)


def leaf(cv, bx, by, ang, L, kind, col, mid, rng, bright=1.0, shadow=.32):
    ca, sa = math.cos(ang), math.sin(ang)
    flip = 1 if rng.random() < .5 else -1
    reg = cv.region(bx + ca * L * .5, by + sa * L * .5, L * .64 + 3)
    if reg is None:
        return
    sl, X, Y = reg

    def ev(X, Y):
        dx, dy = X - bx, Y - by
        u = (dx * ca + dy * sa) / L
        v = (-dx * sa + dy * ca) / L
        return (u, v) + shape(kind, u, v)
    # soft drop shadow on what is already there
    _, _, ds, _, _ = ev(X - L * .05, Y + L * .07)
    ms = np.clip(ds * L * .25 + .5, 0, 1)
    cv.rgb[sl] *= (1 - shadow * ms)[..., None]
    u, v, d, e, vein = ev(X, Y)
    a = np.clip(d * L + .5, 0, 1).astype(F32)
    if a.max() <= 0:
        return
    side = np.where(v * flip > 0, 1.07, .91)
    k = bright * side * (.8 + .2 * np.sqrt(e)) * (.92 + .12 * np.clip(u, 0, 1))
    c = col[None, None, :] * k[..., None]
    c = c + (mid[None, None, :] * bright - c) * (np.clip(vein, 0, 1) * .42)[..., None]
    c = c * cv.grain[sl][..., None]
    cv.over(sl, a, c.astype(F32))


def leaf_col(base, rng, yellow=None, p=.15):
    c = base * rng.normal(1, .045, 3).astype(F32) * rng.uniform(.88, 1.08)
    if yellow is not None and rng.random() < p:
        c = c + (yellow - c) * rng.uniform(.2, .5)
    return c


def spray(cv, P, rng):
    """A twig with side shoots and leaves; base at the bottom centre."""
    W, H = cv.w, cv.h
    L0 = P['L'] * H
    base = np.array([W * .5, 1.0], F32)
    top = np.array([W * (.5 + rng.uniform(-.05, .05)), H * P['top']], F32)
    ctrl = np.array([W * (.5 + rng.uniform(-.1, .1)), H * .45], F32)
    stem = bezier(base, ctrl, top, 24)
    lines = [(stem, P['stem_r'] * W, P['stem_r'] * W * .4)]
    anchors = []
    ns = P['shoots']
    for i in range(ns):
        t = .12 + .74 * (i + .5) / ns + rng.uniform(-.04, .04)
        k = int(t * 23); p = stem[k]; ta = tangent_angle(stem, k)
        side = 1 if i % 2 == 0 else -1
        a0 = ta + side * math.radians(rng.uniform(*P['shoot_ang']))
        ln = P['shoot_len'] * W * (1 - .4 * t) * rng.uniform(.82, 1.1)
        a1 = a0 + (math.pi / 2 - a0) * .3
        p1 = p + vdir(a0) * ln * .5; p2 = p1 + vdir(a1) * ln * .5
        sh = bezier(p, p1, p2, 12)
        lines.append((sh, P['stem_r'] * W * .62, P['stem_r'] * W * .28))
        per = P['per']
        for j in range(per):
            s = .3 + .7 * (j + 1) / per
            kk = min(11, int(s * 11)); q = sh[kk]; tq = tangent_angle(sh, kk)
            if j == per - 1:
                la = tq + rng.uniform(-.15, .15)
            else:
                la = tq + (1 if j % 2 else -1) * math.radians(rng.uniform(*P['leaf_ang']))
            anchors.append((q, la, rng.uniform(.82, 1.08) * (1 - .18 * t)))
    for j in range(P['stem_leaves']):
        t = .28 + .62 * j / max(1, P['stem_leaves'] - 1)
        k = int(t * 23); ta = tangent_angle(stem, k)
        la = ta + (1 if j % 2 else -1) * math.radians(rng.uniform(35, 70))
        anchors.append((stem[k], la, rng.uniform(.75, 1.0)))
    anchors.append((stem[-1], tangent_angle(stem, 23) + rng.uniform(-.1, .1), 1.0))
    for pts, r0, r1 in lines:
        polyline(cv, pts, r0, r1, P['twig'])
    leaves = []
    m = 3
    for q, la, sc in anchors:
        L = L0 * sc; d = vdir(la)
        for _ in range(10):
            b = q + d * P['petiole'] * L
            tip = b + d * L
            ok = all(m + .3 * L < c < lim - m - .3 * L for c, lim in ((tip[0], W), (b[0], W))) and \
                 (m + .3 * L < tip[1] < H - m - .25 * L)
            if ok:
                break
            L *= .86
        if P['petiole'] > 0:
            line(cv, q, b, max(1.0, P['stem_r'] * W * .3), max(.8, P['stem_r'] * W * .22), P['twig'] * 1.15)
        leaves.append((b, la, L))
    order = rng.permutation(len(leaves))
    for rank, idx in enumerate(order):
        b, la, L = leaves[idx]
        bright = (.7 + .32 * rank / len(leaves)) * rng.uniform(.92, 1.06)
        leaf(cv, b[0], b[1], la, L, P['kind'], leaf_col(P['col'], rng, P.get('yellow')), P['mid'], rng, bright)


def needles(cv, P, rng):
    W, H = cv.w, cv.h
    base = np.array([W * .5, 1.0], F32)
    top = np.array([W * (.5 + rng.uniform(-.04, .04)), H * .9], F32)
    stem = bezier(base, np.array([W * (.5 + rng.uniform(-.08, .08)), H * .45], F32), top, 30)
    shoots = [(stem, 1.0)]
    for i in range(P['shoots']):
        t = .2 + .6 * (i + .5) / P['shoots']
        k = int(t * 29); p = stem[k]; ta = tangent_angle(stem, k)
        a0 = ta + (1 if i % 2 else -1) * math.radians(rng.uniform(32, 48))
        ln = W * .46 * (1 - .35 * t)
        a1 = a0 + (math.pi / 2 - a0) * .25
        p1 = p + vdir(a0) * ln * .5
        shoots.append((bezier(p, p1, p1 + vdir(a1) * ln * .5, 16), .7))
    twig = P['twig']
    for pts, s in shoots:
        polyline(cv, pts, P['stem_r'] * W * s, P['stem_r'] * W * s * .5, twig)
    nl = []
    for pts, s in shoots:
        n = len(pts)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()
        cnt = int(seg / P['spacing'])
        for i in range(cnt):
            f = (i + .5) / cnt
            if f < .06:
                continue
            k = min(n - 1, int(f * (n - 1))); ta = tangent_angle(pts, k)
            for side in (-1, 1):
                a = ta + side * math.radians(rng.uniform(28, 62) * (1 - .45 * f ** 2))
                ln = P['len'] * H * s ** .5 * rng.uniform(.75, 1.05) * (1 - .4 * f ** 3)
                nl.append((pts[k].copy(), a, ln))
    order = rng.permutation(len(nl))
    for rank, i in enumerate(order):
        p, a, ln = nl[i]
        c = leaf_col(P['col'], rng) * (.7 + .35 * rank / len(nl))
        q = p + vdir(a) * ln
        line(cv, p, q, P['w'], P['w'] * .45, c)
        line(cv, p + (q - p) * .55, q, P['w'] * .5, P['w'] * .3, c * 1.18)
    for pts, s in shoots:          # buds
        tip = pts[-1]
        reg = cv.region(tip[0], tip[1], 9)
        if reg:
            sl, X, Y = reg
            a = np.clip(7 * s - np.hypot(X - tip[0], (Y - tip[1]) * .7) + .5, 0, 1)
            cv.over(sl, a.astype(F32), np.broadcast_to(srgb('#7a5a3a'), a.shape + (3,)).astype(F32))


def flower(cv, cx, cy, r, ang, squash, rng, petal, edge, centre):
    reg = cv.region(cx, cy, r + 3)
    if reg is None:
        return
    sl, X, Y = reg
    dx, dy = X - cx, Y - cy
    ca, sa = math.cos(ang), math.sin(ang)
    u = dx * ca + dy * sa; v = (-dx * sa + dy * ca) / squash
    rho = np.sqrt(u * u + v * v); phi = np.arctan2(v, u)
    pc = np.abs(np.cos(2.5 * phi))
    R = r * (.6 + .4 * pc ** .35) * (1 - .07 * np.exp(-((pc - 1) / .02) ** 2))
    a = np.clip((R - rho) + .5, 0, 1).astype(F32)
    # shadow below
    cv.rgb[sl] *= (1 - .25 * np.clip((R * 1.05 - np.hypot(u + r * .1, v - r * .12)) / 3 + .5, 0, 1))[..., None]
    t = np.clip(rho / np.maximum(R, 1e-3), 0, 1)
    c = mix(petal, edge, t ** 1.6)
    c = c * (.82 + .18 * pc ** .5)[..., None]
    cen = np.clip((r * .2 - rho) / 2 + .5, 0, 1)
    c = mix(c, centre, cen * .85)
    stam = np.exp(-((rho - r * .3) / (r * .06)) ** 2) * (np.cos(phi * 9 + ang) > .4)
    c = mix(c, srgb('#e9d36c'), stam * .9)
    cv.over(sl, a, (c * cv.grain[sl][..., None]).astype(F32))


def blossoms(cv, P, rng):
    W, H = cv.w, cv.h
    base = np.array([W * .5, 1.0], F32)
    stem = bezier(base, np.array([W * (.5 + rng.uniform(-.1, .1)), H * .45], F32),
                  np.array([W * (.5 + rng.uniform(-.05, .05)), H * .86], F32), 24)
    lines = [(stem, P['stem_r'] * W, P['stem_r'] * W * .45)]
    spots = []
    for i in range(P['shoots']):
        t = .15 + .7 * (i + .5) / P['shoots']
        k = int(t * 23); p = stem[k]; ta = tangent_angle(stem, k)
        a0 = ta + (1 if i % 2 else -1) * math.radians(rng.uniform(35, 60))
        ln = W * .48 * (1 - .4 * t)
        sh = bezier(p, p + vdir(a0) * ln * .5, p + vdir(a0) * ln * .5 + vdir(a0 + (math.pi / 2 - a0) * .3) * ln * .5, 12)
        lines.append((sh, P['stem_r'] * W * .6, P['stem_r'] * W * .3))
        for s in (.3, .55, .78, 1.0):
            spots.append(sh[min(11, int(s * 11))])
    for t in (.3, .5, .7, .9, 1.0):
        spots.append(stem[min(23, int(t * 23))])
    for pts, r0, r1 in lines:
        polyline(cv, pts, r0, r1, P['twig'])
    # a few young leaves behind the flowers
    for q in spots:
        if rng.random() < .8:
            la = rng.uniform(0, 2 * math.pi)
            L = P['leafL'] * H * rng.uniform(.8, 1.1)
            b = q + vdir(la) * L * .1
            if L * .7 < b[0] < W - L * .7 and L * .7 < b[1] < H - L * .7:
                leaf(cv, b[0], b[1], la, L, 'young', leaf_col(P['leaf'], rng), P['leaf'] * 1.3, rng, .9)
    fl = []
    for q in spots:
        for _ in range(rng.integers(3, 6)):
            a = rng.uniform(0, 2 * math.pi); pl = P['r'] * H * rng.uniform(.6, 1.5)
            c = q + vdir(a) * pl
            r = P['r'] * H * rng.uniform(.82, 1.1)
            if r + 3 < c[0] < W - r - 3 and r + 3 < c[1] < H - r - 3:
                fl.append((q, c, r))
    order = rng.permutation(len(fl))
    for rank, i in enumerate(order):
        q, c, r = fl[i]
        line(cv, q, c, 1.6, 1.2, P['twig'] * 1.4)
        b = (.78 + .26 * rank / len(fl)) * rng.uniform(.95, 1.04)
        flower(cv, c[0], c[1], r, rng.uniform(0, 2 * math.pi), rng.uniform(.55, 1.0), rng,
               P['petal'] * b, P['edge'] * b, P['centre'])


def willow_tex(cv, P, rng):
    """Vertically tiling hanging twigs (0.4 m x 0.8 m), base at the top: a centre twig and two side twigs."""
    W, H = cv.w, cv.h
    twigs = [(W * .5, 14, 0.0, 1.0), (W * .22, 10, 2.1, .8), (W * .78, 10, 4.2, .8)]

    def xat(x0, amp, ph, y):
        return x0 + amp * np.sin(2 * math.pi * y / H + ph) + amp * .4 * np.sin(4 * math.pi * y / H + ph + 1)
    leaves = []
    for x0, amp, ph, sc in twigs:
        ys = np.linspace(0, H, 49)
        polyline(cv, np.stack([xat(x0, amp, ph, ys), ys], 1).astype(F32), P['stem_r'] * W * sc, P['stem_r'] * W * sc,
                 P['twig'])
        n = int(H / (P['spacing'] / sc))
        for i in range(n):
            y = (i + rng.uniform(-.3, .3)) * H / n
            side = 1 if i % 2 else -1
            a = -math.pi / 2 + side * math.radians(rng.uniform(18, 55))
            L = P['L'] * H * rng.uniform(.8, 1.1) * sc
            leaves.append((float(xat(x0, amp, ph, y)), y, a, L))
    order = rng.permutation(len(leaves))
    for rank, i in enumerate(order):
        x, y, a, L = leaves[i]
        col = leaf_col(P['col'], rng, P['silver'], .3)
        bright = (.72 + .3 * rank / len(leaves)) * rng.uniform(.92, 1.06)
        for oy in (-H, 0, H):
            leaf(cv, x, y + oy, a, L, 'lance', col, P['mid'], np.random.default_rng(int(x * 7 + y)), bright)


def grass_tex(cv, P, rng):
    W, H = cv.w, cv.h
    cw = W // 4
    Y = (np.arange(H, dtype=F32) + .5)[:, None] / H
    X = np.arange(cw, dtype=F32)[None, :] + .5
    for c in range(4):
        base, mid, tip = P['cols'][c]
        xc = cw * .5 + cw * .06 * np.sin(Y * 3.0 + c)
        hw = cw * .45 * np.clip(1 - Y, 0, 1) ** .55 * (1 - .15 * np.exp(-Y * 12))
        a = np.clip(hw - np.abs(X - xc) + .5, 0, 1)
        t = np.clip(Y, 0, 1)
        col = np.where((t < .55)[..., None], mix(base, mid, t / .55), mix(mid, tip, (t - .55) / .45))
        col = np.broadcast_to(col, (H, cw, 3)).copy()
        rib = np.exp(-((X - xc) / (cw * .05)) ** 2)
        col = mix(col, col * 1.25, rib * .5)
        edge = np.clip(np.abs(X - xc) / np.maximum(hw, 1), 0, 1)
        col = col * (1.04 - .14 * edge ** 2)[..., None]
        sl = (slice(0, H), slice(c * cw, (c + 1) * cw))
        cv.rgb[sl] = col * cv.grain[sl][..., None]
        cv.a[sl] = a


LEAVES = {
    'broad': dict(fn=spray, size=1024, kind='broad', L=.25, top=.84, shoots=6, per=3, stem_leaves=4, stem_r=.006,
                  shoot_len=.5, shoot_ang=(40, 62), leaf_ang=(25, 55), petiole=.34,
                  col=srgb('#5d7a37'), mid=srgb('#a3b76b'), yellow=srgb('#a8a54a'), twig=srgb('#5b4a37')),
    'maple': dict(fn=spray, size=1024, kind='maple', L=.24, top=.85, shoots=6, per=3, stem_leaves=4, stem_r=.0055,
                  shoot_len=.5, shoot_ang=(38, 60), leaf_ang=(25, 55), petiole=.45,
                  col=srgb('#4b7a2c'), mid=srgb('#97b65a'), yellow=srgb('#b0a83c'), twig=srgb('#6a4434')),
    'heart': dict(fn=spray, size=1024, kind='heart', L=.17, top=.86, shoots=7, per=4, stem_leaves=5, stem_r=.005,
                  shoot_len=.5, shoot_ang=(40, 65), leaf_ang=(30, 60), petiole=.3,
                  col=srgb('#558735'), mid=srgb('#9fc06a'), yellow=srgb('#a7ad45'), twig=srgb('#5e4636')),
    'small': dict(fn=spray, size=1024, kind='small', L=.125, top=.9, shoots=8, per=6, stem_leaves=6, stem_r=.0035,
                  shoot_len=.52, shoot_ang=(32, 58), leaf_ang=(30, 65), petiole=.32,
                  col=srgb('#6c9a3b'), mid=srgb('#b0c879'), yellow=srgb('#b9b445'), twig=srgb('#4a2e24')),
    'ovate': dict(fn=spray, size=1024, kind='ovate', L=.155, top=.88, shoots=7, per=5, stem_leaves=5, stem_r=.0045,
                  shoot_len=.5, shoot_ang=(30, 52), leaf_ang=(25, 55), petiole=.3,
                  col=srgb('#3f6b2a'), mid=srgb('#8fae60'), yellow=srgb('#7d8a3c'), twig=srgb('#4f3d30')),
    'oak': dict(fn=spray, size=1024, kind='oak', L=.22, top=.86, shoots=6, per=4, stem_leaves=4, stem_r=.0055,
                shoot_len=.5, shoot_ang=(35, 60), leaf_ang=(25, 55), petiole=.12,
                col=srgb('#4c6b2e'), mid=srgb('#93a862'), yellow=srgb('#8f8f3e'), twig=srgb('#5a4838')),
    'box': dict(fn=spray, size=512, kind='box', L=.1, top=.9, shoots=8, per=8, stem_leaves=7, stem_r=.006,
                shoot_len=.52, shoot_ang=(30, 60), leaf_ang=(35, 70), petiole=.05,
                col=srgb('#3b5f29'), mid=srgb('#7f9e55'), yellow=srgb('#6f7f34'), twig=srgb('#6a5a3e')),
    'shrub': dict(fn=spray, size=512, kind='shrub', L=.17, top=.88, shoots=6, per=4, stem_leaves=4, stem_r=.007,
                  shoot_len=.5, shoot_ang=(35, 60), leaf_ang=(30, 60), petiole=.18,
                  col=srgb('#4a7431'), mid=srgb('#91ad63'), yellow=srgb('#8a943f'), twig=srgb('#5d4a38')),
    'needles': dict(fn=needles, size=1024, shoots=7, spacing=4.2, len=.13, w=1.7, stem_r=.006,
                    col=srgb('#38582f'), twig=srgb('#6b4b33')),
    'cherry': dict(fn=blossoms, size=1024, shoots=7, r=.042, leafL=.14, stem_r=.006,
                   petal=srgb('#fbe3ea'), edge=srgb('#ef9fbb'), centre=srgb('#b9476e'),
                   leaf=srgb('#7b7a3e'), twig=srgb('#4a2a22')),
    'willow': dict(fn=willow_tex, size=(512, 1024), L=.125, spacing=20, stem_r=.006,
                   col=srgb('#86a04a'), silver=srgb('#aab88a'), mid=srgb('#c2cf8e'), twig=srgb('#7c6a3a')),
    'grass': dict(fn=grass_tex, size=1024,
                  cols=[(srgb('#34502a'), srgb('#6c8c40'), srgb('#cbb67a')),
                        (srgb('#3a5730'), srgb('#7a9548'), srgb('#d3c48e')),
                        (srgb('#4b4a2c'), srgb('#8a7c45'), srgb('#c79f6c')),
                        (srgb('#335a45'), srgb('#6f9a72'), srgb('#c1c08e'))]),
}


def make_leaves(kind, seed):
    P = LEAVES[kind]
    sz = P['size']
    w, h = (sz, sz) if isinstance(sz, int) else sz
    cv = Canvas(w, h, seed)
    P['fn'](cv, P, np.random.default_rng(seed))
    out = cv.finish()
    save_img('ct_leaves_%s' % kind, out)
    print('[city_trees] leaves %-8s %dx%d coverage %.2f' % (kind, w, h, float((cv.a > .5).mean())))


# =====================================================================================================================
# materials
# =====================================================================================================================
_M = {}


def _img(path, non_color=False):
    im = bpy.data.images.load(os.path.join(TEX, path), check_existing=True)
    if non_color:
        im.colorspace_settings.name = 'Non-Color'
    return im


def _vcol(nt):
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'
    return vc


def _multiply(nt, a, b):
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
    mx.inputs['Factor'].default_value = 1.0
    nt.links.new(a, mx.inputs[6]); nt.links.new(b, mx.inputs[7])
    return mx.outputs[2]


def bark_mat(kind):
    name = 'ct_bark_' + kind
    if name in _M:
        return _M[name]
    m = bpy.data.materials.new(name)
    m.use_backface_culling = True                                          # glTF doubleSided false
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = _img(name + '_c.jpg')
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = _img(name + '_n.png', True)
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    nt.links.new(_multiply(nt, tc.outputs['Color'], _vcol(nt).outputs['Color']), b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = .62 if kind in ('cherry', 'birch') else .88
    b.inputs['Specular IOR Level'].default_value = .35
    _M[name] = m
    return m


def leaf_mat(kind):
    name = 'ct_leaves_' + kind
    if name in _M:
        return _M[name]
    m = bpy.data.materials.new(name)
    m.use_backface_culling = False
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        m.blend_method = 'CLIP'
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = _img(name + '.png')
    tc.image.alpha_mode = 'STRAIGHT'
    nt.links.new(_multiply(nt, tc.outputs['Color'], _vcol(nt).outputs['Color']), b.inputs['Base Color'])
    rnd = nt.nodes.new('ShaderNodeMath'); rnd.operation = 'ROUND'          # glTF exporter: alphaMode MASK, cutoff 0.5
    nt.links.new(tc.outputs['Alpha'], rnd.inputs[0]); nt.links.new(rnd.outputs[0], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = .62 if kind in ('ovate', 'box', 'heart') else .74
    b.inputs['Specular IOR Level'].default_value = .22
    _M[name] = m
    return m


def core_mat():
    if 'ct_leafcore' in _M:
        return _M['ct_leafcore']
    m = bpy.data.materials.new('ct_leafcore')
    m.use_backface_culling = True
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    rgb = nt.nodes.new('ShaderNodeRGB'); rgb.outputs[0].default_value = (*bl.hexrgb('#1f3317'), 1)
    nt.links.new(_multiply(nt, rgb.outputs[0], _vcol(nt).outputs['Color']), b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = .9
    _M['ct_leafcore'] = m
    return m


# =====================================================================================================================
# geometry accumulation
# =====================================================================================================================
def nrm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def rotate(v, axis, ang):
    axis = nrm(axis)
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * (axis @ v) * (1 - math.cos(ang))


class Geo:
    def __init__(s):
        s.V, s.N, s.UV, s.C, s.F, s.M = [], [], [], [], [], []
        s.mats = []

    def mat(s, m):
        if m not in s.mats:
            s.mats.append(m)
        return s.mats.index(m)

    def v(s, p, n, uv, c):
        s.V.append(tuple(p)); s.N.append(tuple(nrm(np.asarray(n, float)))); s.UV.append(uv); s.C.append(c)
        return len(s.V) - 1

    def tris(s):
        return sum(len(f) - 2 for f in s.F)

    def tris_of(s, mi):
        return sum(len(f) - 2 for f, m in zip(s.F, s.M) if m == mi)

    def build(s, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(s.V, [], s.F)
        for m in s.mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', np.array(s.M, np.int32))
        me.polygons.foreach_set('use_smooth', np.ones(len(s.F), bool))
        li = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', li)
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', np.array(s.UV, F32)[li].ravel())
        ca = me.color_attributes.new('Col', 'BYTE_COLOR', 'POINT')
        col = np.ones((len(s.V), 4), F32); col[:, :3] = np.clip(np.array(s.C, F32), 0, 1)
        ca.data.foreach_set('color', col.ravel())
        me.update()
        me.normals_split_custom_set_from_vertices(s.N)
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        return o


def sides_for(r):
    return 10 if r >= .15 else 8 if r >= .085 else 6 if r >= .045 else 5 if r >= .026 else 4 if r >= .013 else 3


def tube(g, pts, rad, sides, mi, v0, ao, flare=0.0, phase=0.0):
    pts = np.asarray(pts, float); n = len(pts)
    T = np.zeros_like(pts)
    T[1:-1] = pts[2:] - pts[:-2]; T[0] = pts[1] - pts[0]; T[-1] = pts[-1] - pts[-2]
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    a = UP if abs(T[0][2]) < .9 else np.array([1., 0, 0])
    Nn = nrm(np.cross(T[0], a))
    reps = max(1, int(round(2 * math.pi * rad[0] / .5)))
    s = v0; base = len(g.V)
    for i in range(n):
        if i:
            Nn = nrm(Nn - T[i] * (Nn @ T[i])); s += float(np.linalg.norm(pts[i] - pts[i - 1]))
        B = np.cross(T[i], Nn)
        c = ao(pts[i])
        for j in range(sides + 1):
            th = 2 * math.pi * j / sides
            d = math.cos(th) * Nn + math.sin(th) * B
            r = rad[i]
            if flare:
                z = max(pts[i][2], 0)
                r *= 1 + flare * math.exp(-z / .42) * (1 + .45 * math.cos(5 * th + phase) + .2 * math.cos(3 * th + 2 * phase))
            g.v(pts[i] + d * r, d, (j / sides * reps, s), c)
    for i in range(n - 1):
        for j in range(sides):
            a0 = base + i * (sides + 1) + j; b0 = a0 + sides + 1
            g.F.append((a0, a0 + 1, b0 + 1, b0)); g.M.append(mi)
    return s


class Crown:
    """Ellipsoid used for the bent foliage normals and the AO."""
    def __init__(s, c, r):
        s.c = np.asarray(c, float); s.r = np.asarray(r, float)

    def q(s, p):
        return (np.asarray(p, float) - s.c) / s.r

    def out(s, p):
        return nrm(s.q(p) / s.r + 1e-6)

    def s(s, p):
        return float(np.linalg.norm(s.q(p)))

    def ao(s, p, lo=.38):
        k = min(s.s(p), 1.15)
        h = np.clip((p[2] - (s.c[2] - s.r[2])) / (2 * s.r[2]), 0, 1)
        return lo + (1 - lo) * min(1.0, k ** 1.4) * (.78 + .22 * h)


def card(g, crown, base, axis, pref, size, mi, rng, aspect=1.0, fold=.16, roll=.9, flat=False, bend=.72, tint=None):
    axis = nrm(np.asarray(axis, float))
    pr = pref - axis * (pref @ axis)
    if np.linalg.norm(pr) < 1e-3:
        pr = np.cross(axis, rng.normal(size=3))
    n0 = nrm(pr)
    n0 = rotate(n0, axis, rng.uniform(-roll, roll))
    side = np.cross(axis, n0)                       # cross(side, axis) == n0
    h = size; w = size * aspect
    B0 = base - axis * .04 * h; T0 = base + axis * h
    f = fold * w * .5
    mu = rng.random() < .5
    us = (1, .5, 0) if mu else (0, .5, 1)
    tint = tint if tint is not None else rng.normal(1, .035, 3) * rng.uniform(.9, 1.03)

    def V(p, u, vv):
        o = crown.out(p)
        nn = nrm(n0 * (1 - bend) + o * bend + UP * .12)
        c = tuple(np.clip(crown.ao(p) * tint, 0, 1))
        return g.v(p, nn, (u, vv), c)
    if flat:
        i0 = V(B0 - side * w / 2, us[0], 0); i1 = V(B0 + side * w / 2, us[2], 0)
        i2 = V(T0 + side * w / 2, us[2], 1); i3 = V(T0 - side * w / 2, us[0], 1)
        g.F.append((i0, i1, i2, i3)); g.M.append(mi)
        return
    L0 = V(B0 - side * w / 2 + n0 * f, us[0], 0); L1 = V(T0 - side * w / 2 + n0 * f, us[0], 1)
    C0 = V(B0, .5, 0); C1 = V(T0, .5, 1)
    R0 = V(B0 + side * w / 2 + n0 * f, us[2], 0); R1 = V(T0 + side * w / 2 + n0 * f, us[2], 1)
    g.F.append((L0, C0, C1, L1)); g.M.append(mi)
    g.F.append((C0, R0, R1, C1)); g.M.append(mi)


# =====================================================================================================================
# skeletons
# =====================================================================================================================
class Skel:
    def __init__(s):
        s.pos = []; s.par = []; s.rad = None

    def add(s, p, parent):
        s.pos.append(np.asarray(p, float)); s.par.append(parent)
        return len(s.pos) - 1

    def arrays(s):
        return np.array(s.pos), np.array(s.par)

    def children(s):
        ch = [[] for _ in s.pos]
        for i, p in enumerate(s.par):
            if p >= 0:
                ch[p].append(i)
        return ch

    def smooth(s, passes=2, keep=()):
        P, par = s.arrays(); ch = s.children()
        for _ in range(passes):
            Q = P.copy()
            for i in range(len(P)):
                if par[i] < 0 or i in keep or len(ch[i]) != 1:
                    continue
                Q[i] = .5 * P[i] + .25 * (P[par[i]] + P[ch[i][0]])
            P = Q
        s.pos = list(P)

    def pipe(s, tip_r, base_r, exp=2.4):
        """Pipe-model radii remapped so tips get tip_r and the root base_r."""
        par = np.array(s.par); n = len(par)
        raw = np.zeros(n)
        ch = s.children()
        for i in range(n - 1, -1, -1):
            raw[i] = 1.0 if not ch[i] else sum(raw[c] ** exp for c in ch[i]) ** (1 / exp)
        B = raw.max()
        g = math.log(base_r / tip_r) / math.log(max(B, 1.0001))
        s.rad = tip_r * raw ** g

    def chains(s):
        ch = s.children(); rad = s.rad
        roots = [i for i, p in enumerate(s.par) if p < 0]
        out = []; stack = [(r, None) for r in roots]
        while stack:
            st, att = stack.pop()
            chain = [att] if att is not None else []
            cur = st
            while True:
                chain.append(cur)
                c = sorted(ch[cur], key=lambda k: -rad[k])
                if not c:
                    break
                for k in c[1:]:
                    stack.append((k, cur))
                cur = c[0]
            out.append(chain)
        return out


def plan_tubes(sk, r_min, trunk_flare=0.0):
    """Tubes (points, radii, sides, flare) for every chain, cut where the radius drops below r_min."""
    P = np.array(sk.pos); rad = sk.rad
    tubes = []; tris = 0
    for ch in sk.chains():
        idx = list(ch)
        r = [rad[i] for i in idx]
        if len(idx) > 1 and sk.par[idx[1]] == idx[0] and r[0] > r[1] * 1.01:
            r[0] = r[1]                                  # attach point inside the parent takes the child's radius
        cut = len(idx)
        for k in range(len(idx)):
            if r[k] < r_min:
                cut = k + 1; break
        idx = idx[:cut]; r = r[:cut]
        if len(idx) < 2:
            continue
        if r[-1] < r_min:
            r[-1] = r_min * .5
        is_trunk = sk.par[idx[0]] < 0
        keep = [0]; acc = 0.0
        for k in range(1, len(idx)):
            acc += float(np.linalg.norm(P[idx[k]] - P[idx[k - 1]]))
            seg = min(1.0, max(.24, r[k] * 5))
            if k == len(idx) - 1 or acc >= seg or (is_trunk and P[idx[k]][2] < 1.2):
                keep.append(k); acc = 0.0
        pts = [P[idx[k]] for k in keep]; rr = [r[k] for k in keep]
        # split where the side count drops (the pieces share their joint ring position)
        start = 0
        for k in range(1, len(pts)):
            if k == len(pts) - 1 or sides_for(rr[k]) != sides_for(rr[start]):
                sd = sides_for(rr[start])
                tubes.append((pts[start:k + 1], rr[start:k + 1], sd, trunk_flare if (is_trunk and start == 0) else 0.0))
                tris += 2 * sd * k - 2 * sd * start
                start = k
    return tubes, tris


def bark_geo(g, sk, crown, mat_i, budget, trunk_flare, rng, r_floor=.004):
    best = None
    for r_min in (r_floor, .006, .008, .01, .012, .015, .018, .022, .027, .033, .04, .05, .065, .08):
        tubes, tris = plan_tubes(sk, r_min, trunk_flare)
        best = (tubes, tris, r_min)
        if tris <= budget:
            break
    tubes, tris, r_min = best
    zc = crown.c[2] - crown.r[2]

    def ao(p):
        if p[2] < zc:
            return (.82 + .18 * min(1, max(p[2], 0) / .8),) * 3
        return (crown.ao(p, .45),) * 3
    for pts, rr, sd, fl in tubes:
        tube(g, pts, rr, sd, mat_i, 0.0, ao, fl, rng.uniform(0, 6.28))
    return r_min


def drawn_anchor(sk, r_min):
    """For every node the nearest ancestor (or itself) that is drawn as a tube."""
    anc = np.zeros(len(sk.pos), int)
    for i, p in enumerate(sk.par):
        anc[i] = i if (sk.rad[i] >= r_min or p < 0) else anc[p]
    return anc


def colonise(sk, growable, A, di, dk, step, up, max_nodes, momentum=.25, rng=None, gravity=0.0):
    """Space colonisation from the growable nodes towards attractors A."""
    A = np.asarray(A, float); M = len(A)
    alive = np.ones(M, bool)
    near_d = np.full(M, np.inf); near_i = np.full(M, -1)
    kids = {}

    def update(new):
        if not len(new):
            return
        Q = np.array([sk.pos[i] for i in new])
        d = np.sqrt(((A[:, None, :] - Q[None, :, :]) ** 2).sum(-1))
        j = d.argmin(1); dm = d[np.arange(M), j]
        better = dm < near_d
        near_d[better] = dm[better]; near_i[better] = np.array(new)[j[better]]
        alive[dm < dk] = False
    update(list(growable))
    for it in range(600):
        sel = alive & (near_d < di)
        if not sel.any() or len(sk.pos) >= max_nodes:
            break
        nodes = near_i[sel]
        vec = A[sel] - np.array([sk.pos[i] for i in nodes])
        vec /= np.maximum(np.linalg.norm(vec, axis=1, keepdims=True), 1e-9)
        uniq, inv = np.unique(nodes, return_inverse=True)
        acc = np.zeros((len(uniq), 3)); np.add.at(acc, inv, vec)
        new = []
        for k, ni in enumerate(uniq):
            a = acc[k]
            if np.linalg.norm(a) < .2:
                continue
            d = nrm(a)
            pa = sk.par[ni]
            if pa >= 0:
                d = d + momentum * nrm(sk.pos[ni] - sk.pos[pa])
            d = nrm(d + UP * up + np.array([0, 0, -gravity]))
            q = sk.pos[ni] + d * step
            if any(np.linalg.norm(q - c) < step * .35 for c in kids.get(ni, ())):
                continue
            kids.setdefault(ni, []).append(q)
            new.append(sk.add(q, ni))
        if not new:
            break
        update(new)
    return sk


class Envelope:
    """Crown shape: z from zb to zt, radius R * sin(pi t^a)^b with irregular azimuth lobes; axis offset by lean."""
    def __init__(s, zb, zt, R, a, b, rng, lean=(0, 0), lobe=.12, ry=None):
        s.zb, s.zt, s.R, s.a, s.b = zb, zt, R, a, b
        s.ry = ry or R
        s.lean = np.array(lean, float)
        s.k = [(k, rng.uniform(.5, 1) * lobe / (1 + .4 * i), rng.uniform(0, 6.28), rng.uniform(-2, 2))
               for i, k in enumerate((2, 3, 5))]

    def radius(s, t, phi):
        tt = np.clip(t, 1e-4, 1 - 1e-4)
        r = np.sin(math.pi * tt ** s.a) ** s.b
        lob = 1.0
        for k, amp, ph, tw in s.k:
            lob = lob + amp * np.sin(k * phi + ph + tw * t)
        return r * lob

    def test(s, P):
        P = np.atleast_2d(P)
        t = (P[:, 2] - s.zb) / (s.zt - s.zb)
        off = s.lean[None, :] * np.clip(t, 0, 1)[:, None]
        x = (P[:, 0] - off[:, 0]) / s.R; y = (P[:, 1] - off[:, 1]) / s.ry
        rr = np.hypot(x, y); phi = np.arctan2(y, x)
        Rt = s.radius(t, phi)
        inside = (t > 0) & (t < 1) & (rr < Rt)
        zc = .5 * (s.zb + s.zt); rz = .5 * (s.zt - s.zb)
        sh = np.sqrt(rr ** 2 + ((P[:, 2] - zc) / rz) ** 2)
        return inside, np.clip(sh, 0, 1)

    def sample(s, n, rng, clumps=30, clump_frac=.7, sigma=.16, shell=.75):
        lo = np.array([-s.R * 1.5 + min(0, s.lean[0]), -s.ry * 1.5 + min(0, s.lean[1]), s.zb])
        hi = np.array([s.R * 1.5 + max(0, s.lean[0]), s.ry * 1.5 + max(0, s.lean[1]), s.zt])

        def uniform(m):
            out = []
            while sum(len(o) for o in out) < m:
                P = lo + rng.random((m * 4, 3)) * (hi - lo)
                ins, sh = s.test(P)
                keep = ins & (rng.random(len(P)) < (1 - shell) + shell * sh ** 2)
                out.append(P[keep])
            return np.concatenate(out)[:m]
        n_c = int(n * clump_frac)
        centres = uniform(clumps)
        pts = [uniform(n - n_c)]
        got = 0
        sig = sigma * np.array([s.R, s.ry, (s.zt - s.zb) * .5])
        while got < n_c:
            c = centres[rng.integers(0, len(centres), 4 * n_c)]
            P = c + rng.normal(size=c.shape) * sig
            ins, _ = s.test(P)
            P = P[ins][:n_c - got]; pts.append(P); got += len(P)
        return np.concatenate(pts)


def trunk_line(sk, z0, z1, step, rng, lean=(0, 0), wob=.04):
    ph = rng.uniform(0, 6.28, 2)
    last = -1; ids = []
    n = max(2, int((z1 - z0) / step) + 1)
    L = max(z1, 1e-3)
    for i in range(n):
        z = z0 + (z1 - z0) * i / (n - 1)
        t = max(z, 0) / L
        x = lean[0] * t ** 1.3 + wob * math.sin(z * 1.1 + ph[0]) * t
        y = lean[1] * t ** 1.3 + wob * math.sin(z * .9 + ph[1]) * t
        last = sk.add((x, y, z), last); ids.append(last)
    return ids


# =====================================================================================================================
# plants
# =====================================================================================================================
TREES = {
    #          h     w    crown base, clear (no foliage below), trunk radius, crown shape a/b, leader (fraction of h)
    'plane':  dict(h=11.0, w=8.0, zb=3.4, clear=2.9, trunk=.2, a=1.15, b=.55, leader=0, bark='plane', leaves='broad',
                   card=.95, cards=1750, attr=1500, di=2.2, dk=.48, step=.32, up=.1, lean=(.25, .1), budget=4200,
                   flare=.32, kind='street'),
    'linden': dict(h=10.0, w=6.0, zb=3.0, clear=2.7, trunk=.17, a=.85, b=.72, leader=.62, bark='rough', leaves='heart',
                   card=.78, cards=2000, attr=1500, di=1.9, dk=.42, step=.3, up=.14, lean=(.1, -.1), budget=4000,
                   flare=.3, kind='street'),
    'maple':  dict(h=9.0, w=7.0, zb=3.0, clear=2.6, trunk=.16, a=1.0, b=.55, leader=0, bark='rough', leaves='maple',
                   card=.85, cards=1800, attr=1400, di=2.0, dk=.45, step=.3, up=.1, lean=(-.15, .2), budget=4000,
                   flare=.3, kind='street'),
    'birch':  dict(h=12.0, w=4.5, zb=3.4, clear=2.8, trunk=.13, a=.72, b=.8, leader=.78, bark='birch', leaves='small',
                   card=.66, cards=1600, attr=1200, di=1.7, dk=.38, step=.3, up=.12, lean=(.2, .15), budget=3600,
                   flare=.18, gravity=.08, kind='street'),
    'cherry': dict(h=6.5, w=6.0, zb=2.75, clear=2.5, trunk=.14, a=1.45, b=.42, leader=0, bark='cherry', leaves='cherry',
                   card=.68, cards=1600, attr=1300, di=1.7, dk=.38, step=.26, up=.03, lean=(.1, .1), budget=3600,
                   flare=.25, kind='street'),
    'pear':   dict(h=8.0, w=3.5, zb=2.7, clear=2.45, trunk=.13, a=.8, b=.72, leader=.7, bark='rough', leaves='ovate',
                   card=.62, cards=1500, attr=1100, di=1.5, dk=.34, step=.26, up=.32, lean=(.05, 0), budget=3400,
                   flare=.22, kind='street'),
    'oak':    dict(h=15.0, w=13.2, zb=4.2, clear=1.4, trunk=.42, a=.72, b=.42, shell=.5, leaf_z=4.6, leader=0, bark='rough', leaves='oak',
                   card=1.12, cards=3000, attr=2600, di=2.9, dk=.62, step=.42, up=.0, lean=(.4, -.3), budget=8500,
                   flare=.42, kind='park', clumps=34, lobe=.2, sigma=.11),
    'willow': dict(h=11.0, w=9.6, zb=2.6, clear=1.2, trunk=.36, a=1.6, b=.5, leader=0, bark='rough', leaves='willow',
                   card=.4, cards=1050, attr=1700, di=2.4, dk=.55, step=.36, up=.06, lean=(.5, .2), budget=6000,
                   flare=.4, kind='park', clumps=40),
}


def leafy_cards(g, sk, crown, S, mi, rng, r_min, clear, size_j=(.8, 1.2), droop=0.0, flat=False, fold=.16):
    """Cards at the thin nodes, their twig base on the nearest drawn branch."""
    P = np.array(sk.pos); rad = sk.rad
    anc = drawn_anchor(sk, r_min)
    leafy = np.where(rad < S.get('leaf_r', .035))[0]
    leafy = leafy[P[leafy][:, 2] > max(clear + .15, S.get('leaf_z', 0))]
    w = np.array([.2 + crown.s(P[i]) ** 2 for i in leafy])
    pick = rng.choice(leafy, size=S['cards'], p=w / w.sum())
    made = 0
    for i in pick:
        par = sk.par[i]
        d = nrm(P[i] - P[par]) if par >= 0 else UP
        a = anc[i]
        size = S['card'] * rng.uniform(*size_j)
        node = P[i] + rng.normal(size=3) * .06 * size
        gap = node - P[a]
        lim = .3 * size
        base = P[a] + gap * min(1.0, lim / max(np.linalg.norm(gap), 1e-6)) if a != i else node
        o = crown.out(node)
        axis = nrm(d * .5 + o * .55 + UP * (.18 - droop) + rng.normal(size=3) * .3)
        pref = nrm(UP * .55 + o * .45)
        # skip cards dipping under the clear height
        if base[2] + min(0, axis[2]) * size < clear:
            continue
        card(g, crown, base, axis, pref, size, mi, rng, flat=flat, fold=fold)
        made += 1
    return made


def broadleaf(name, S, seed):
    rng = np.random.default_rng(seed)
    h, R = S['h'], S['w'] / 2
    zt = h - .45 * S['card']; Rr = R - .55 * S['card'] - .5 * float(np.hypot(*S['lean']))
    env = Envelope(S['zb'], zt, Rr, S['a'], S['b'], rng, lean=S['lean'], lobe=S.get('lobe', .2))
    A = env.sample(S['attr'], rng, clumps=S.get('clumps', 22), clump_frac=.8, sigma=S.get('sigma', .13), shell=S.get('shell', .72))
    sk = Skel()
    top = S['leader'] * h if S['leader'] else S['zb'] + .1
    ids = trunk_line(sk, -.25, top, S['step'], rng, lean=np.array(S['lean']) * top / h)
    grow_z = S['clear'] if S['leader'] else top - .5
    growable = [i for i in ids if sk.pos[i][2] >= grow_z]
    colonise(sk, growable, A, S['di'], S['dk'], S['step'], S['up'], 9000, rng=rng, gravity=S.get('gravity', 0))
    sk.smooth(2, keep=set(ids[:3]))
    sk.pipe(.006, S['trunk'], 2.4)
    crown = Crown((S['lean'][0] * .5, S['lean'][1] * .5, .5 * (S['zb'] + h)), (R, R, .5 * (h - S['zb'])))
    g = Geo()
    mb = g.mat(bark_mat(S['bark'])); ml = g.mat(leaf_mat(S['leaves']))
    r_min = bark_geo(g, sk, crown, mb, S['budget'], S['flare'], rng)
    if name == 'willow':
        made = willow_strands(g, sk, crown, S, ml, rng, r_min)
    else:
        made = leafy_cards(g, sk, crown, S, ml, rng, r_min, S['clear'] if S['kind'] == 'street' else 1.0,
                           droop=S.get('gravity', 0) * 2)
    return g, dict(nodes=len(sk.pos), r_min=r_min, cards=made, trunk_r=S['trunk'], clear=S['clear'])


def willow_strands(g, sk, crown, S, mi, rng, r_min):
    P = np.array(sk.pos); rad = sk.rad
    anc = drawn_anchor(sk, r_min)
    leafy = np.where(rad < .03)[0]
    leafy = leafy[P[leafy][:, 2] > 3.0]
    w = np.array([.15 + crown.s(P[i]) ** 2.5 for i in leafy])
    pick = rng.choice(leafy, size=S['cards'], p=w / w.sum())
    made = 0
    for i in pick:
        top = P[anc[i]] + (P[i] - P[anc[i]]) * .5
        ax = top - np.array([crown.c[0], crown.c[1], top[2]])
        outd = nrm(ax) if np.linalg.norm(ax) > .1 else nrm(rng.normal(size=3) * [1, 1, 0])
        s = crown.s(top)
        length = rng.uniform(.9, 1.8) + 2.4 * s ** 2 * rng.uniform(.6, 1.1)
        length = min(length, top[2] - 1.25)
        if length < .6:
            continue
        width = S['card'] * rng.uniform(.85, 1.1)
        nseg = 5
        pts = [top.copy()]
        d = nrm(outd * .85 + UP * rng.uniform(.0, .35))
        seg = length / nseg
        for k in range(nseg):
            p = pts[-1] + d * seg
            pts.append(p)
            d = nrm(d + np.array([0, 0, -1.3]) + rng.normal(size=3) * [.08, .08, 0])
        wv = nrm(np.cross(UP, outd)); wv = rotate(wv, UP, rng.uniform(-.7, .7))
        vt = rng.uniform(0, 1) + length / .8
        tint = rng.normal(1, .04, 3) * rng.uniform(.9, 1.04)
        acc = 0.0; ids = []
        for k, p in enumerate(pts):
            if k:
                acc += float(np.linalg.norm(p - pts[k - 1]))
            o = crown.out(p)
            o = nrm(o * [1, 1, .4] + UP * .1)
            c = tuple(np.clip(crown.ao(p, .42) * tint, 0, 1))
            vv = vt - acc / .8
            ids.append((g.v(p - wv * width / 2, o, (0, vv), c), g.v(p + wv * width / 2, o, (1, vv), c)))
        tng = nrm(pts[-1] - pts[0])
        fn = np.cross(wv, tng)
        flip = fn @ outd < 0
        for k in range(nseg):
            a, b = ids[k]; c2, d2 = ids[k + 1]
            g.F.append((b, a, c2, d2) if flip else (a, b, d2, c2)); g.M.append(mi)
        made += 1
    return made


def pine(name, seed):
    rng = np.random.default_rng(seed)
    H = 14.0; z0 = 6.4; csize = .7
    sk = Skel(); rads = []
    lean = np.array([.35, -.2])

    def add(p, parent, r):
        rads.append(r); return sk.add(p, parent)
    trunk = []
    last = -1
    nz = int((H + .25) / .35) + 1
    ph = rng.uniform(0, 6.28, 2)
    for i in range(nz):
        z = -.25 + (H + .25) * i / (nz - 1)
        t = max(z, 0) / H
        x = lean[0] * t ** 1.5 + .12 * math.sin(z * .45 + ph[0]) * t
        y = lean[1] * t ** 1.5 + .12 * math.sin(z * .38 + ph[1]) * t
        r = .27 * (1 - t) ** .95 + .018
        last = add((x, y, z), last, r); trunk.append(last)
    anchors = []      # (node index, direction)

    def Rprof(t):
        return 3.2 * max(0.0, 1 - t ** 2.2) ** .6 * (.72 + .28 * t)

    z = z0; az = rng.uniform(0, 6.28)
    while z < H - .5:
        t = (z - z0) / (H - z0)
        k = rng.integers(2, 5)
        tn = trunk[min(len(trunk) - 1, int((z + .25) / ((H + .25) / (nz - 1))))]
        tp = sk.pos[tn]
        for b in range(k):
            a = az + 2 * math.pi * b / k + rng.uniform(-.35, .35)
            L = Rprof(t) * rng.uniform(.5, 1.1)
            if L < .35:
                continue
            elev = math.radians(-6 + 34 * t + rng.uniform(-12, 12))
            hd = np.array([math.cos(a), math.sin(a), 0.])
            d = nrm(hd * math.cos(elev) + UP * math.sin(elev))
            rb = min(.03 + .022 * L, rads[tn] * .7)
            nseg = max(3, int(L / .45))
            prev = tn; p = tp.copy(); bn = []
            for s in range(1, nseg + 1):
                f = s / nseg
                dd = nrm(d + UP * (.55 * f ** 2) - UP * .12 * (1 - t) * math.sin(math.pi * f))
                p = p + dd * (L / nseg)
                prev = add(p.copy(), prev, rb * (1 - .78 * f) + .006); bn.append((prev, dd, f))
            # branchlets
            for j, (ni, dd, f) in enumerate(bn):
                if f < .3:
                    continue
                for sgn in ((-1, 1) if f < .95 else (0,)):
                    side = nrm(np.cross(dd, UP)) if np.linalg.norm(np.cross(dd, UP)) > .1 else np.array([1., 0, 0])
                    bd = nrm(dd * (1 if sgn == 0 else .6) + side * sgn * .8 + UP * .25 + rng.normal(size=3) * .12)
                    bl_ = (.35 + .5 * (1 - f) * L / 3.2) * rng.uniform(.7, 1.1) if sgn else .25
                    q = sk.pos[ni] + bd * bl_
                    m = add(q, ni, .009)
                    anchors.append((ni, bd)); anchors.append((m, nrm(bd + UP * .2)))
            anchors.append((bn[-1][0], bn[-1][1]))
        z += rng.uniform(.45, .85); az += rng.uniform(.6, 2.4)
    for i in range(6):   # leader tufts
        anchors.append((trunk[-1 - i // 2], nrm(UP + rng.normal(size=3) * .35)))
    # dead stubs on the bare trunk
    for i in range(7):
        zz = rng.uniform(2.6, z0 - .3)
        tn = trunk[int((zz + .25) / ((H + .25) / (nz - 1)))]
        a = rng.uniform(0, 6.28)
        d = nrm(np.array([math.cos(a), math.sin(a), rng.uniform(-.25, .05)]))
        add(sk.pos[tn] + d * rng.uniform(.25, .7), tn, .028)
    sk.rad = np.array(rads)
    crown = Crown((lean[0] * .5, lean[1] * .5, .5 * (z0 + H)), (3.3, 3.3, .5 * (H - z0) + .5))
    g = Geo()
    mb = g.mat(bark_mat('pine')); ml = g.mat(leaf_mat('needles'))
    r_min = bark_geo(g, sk, crown, mb, 5500, .3, rng)
    anc = drawn_anchor(sk, r_min)
    P = np.array(sk.pos)
    sel = rng.choice(len(anchors), size=1700, replace=len(anchors) < 1700)
    made = 0
    for k in sel:
        ni, d = anchors[k]
        a = anc[ni]
        size = csize * rng.uniform(.8, 1.2)
        base = P[a] + (P[ni] - P[a]) * min(1.0, .3 * size / max(np.linalg.norm(P[ni] - P[a]), 1e-6))
        axis = nrm(d + rng.normal(size=3) * .2)
        card(g, crown, base, axis, UP, size, ml, rng, aspect=1.15, roll=.45, fold=.2, bend=.6)
        made += 1
    return g, dict(nodes=len(sk.pos), r_min=r_min, cards=made, trunk_r=.27, clear=z0 - .8)


SHRUBS = {
    'shrub_a': dict(h=1.4, w=1.7, stems=7, leaves='box', card=.32, cards=1050, attr=900, di=.55, dk=.12, step=.1,
                    up=.05, a=.72, b=.45, zb=.12, base_r=.022, budget=650, flat=True, core=True),
    'shrub_b': dict(h=2.2, w=1.9, stems=6, leaves='shrub', card=.42, cards=520, attr=800, di=.7, dk=.16, step=.13,
                    up=.18, a=1.15, b=.55, zb=.35, base_r=.026, budget=800, flat=False, core=False),
}


def shrub(name, S, seed):
    rng = np.random.default_rng(seed)
    h, R = S['h'], S['w'] / 2
    zt = h - .4 * S['card']; Rr = R - .4 * S['card']
    env = Envelope(S['zb'], zt, Rr, S['a'], S['b'], rng, lobe=.1)
    A = env.sample(S['attr'], rng, clumps=14, sigma=.2, shell=.6)
    sk = Skel(); grow = []
    for i in range(S['stems']):
        a = 2 * math.pi * i / S['stems'] + rng.uniform(-.3, .3)
        hd = np.array([math.cos(a), math.sin(a), 0])
        p = np.array([0, 0, -.05]) + hd * rng.uniform(0, .08)
        last = sk.add(p, -1)
        d = nrm(hd * rng.uniform(.25, .6) + UP)
        for k in range(3):
            p = p + d * S['step']; last = sk.add(p, last)
        grow.append(last)
    colonise(sk, grow, A, S['di'], S['dk'], S['step'], S['up'], 6000, rng=rng)
    sk.smooth(2)
    sk.pipe(.003, S['base_r'], 2.3)
    crown = Crown((0, 0, .5 * (S['zb'] + h)), (R, R, .5 * (h - S['zb']) + .05))
    g = Geo()
    mb = g.mat(bark_mat('rough')); ml = g.mat(leaf_mat(S['leaves']))
    r_min = bark_geo(g, sk, crown, mb, S['budget'], 0.0, rng, r_floor=.003)
    if S['core']:
        mc = g.mat(core_mat())
        ellipsoid(g, crown.c - [0, 0, .05], crown.r * [.62, .62, .6], mc, crown)
    made = leafy_cards(g, sk, crown, dict(S, leaf_r=.012), ml, rng, r_min, .05, flat=S['flat'])
    return g, dict(nodes=len(sk.pos), r_min=r_min, cards=made, trunk_r=S['base_r'], clear=0.0)


def ellipsoid(g, c, r, mi, crown, seg=10, rings=6):
    c = np.asarray(c, float); r = np.asarray(r, float)
    base = len(g.V)
    for i in range(rings + 1):
        th = math.pi * i / rings
        for j in range(seg + 1):
            ph = 2 * math.pi * j / seg
            n = np.array([math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)])
            p = c + n * r
            g.v(p, n / r, (j / seg, i / rings), (crown.ao(p, .3) * .8,) * 3)
    for i in range(rings):
        for j in range(seg):
            a = base + i * (seg + 1) + j; b = a + seg + 1
            if i == 0:
                g.F.append((a, b + 1, b))
            elif i == rings - 1:
                g.F.append((a, a + 1, b))
            else:
                g.F.append((a, a + 1, b + 1, b))
            g.M.append(mi)


def hedge(name, seed):
    rng = np.random.default_rng(seed)
    LX, WY, HZ = 3.0, .9, 1.2
    g = Geo()
    mb = g.mat(bark_mat('rough')); ml = g.mat(leaf_mat('box')); mc = g.mat(core_mat())
    crown = Crown((0, 0, .62), (LX / 2, WY / 2, .62))
    # rounded-box helper: normal from the SDF of a box with rounded top edges
    hx, hy, hz0, hz1, rr = LX / 2 - .06, WY / 2 - .06, .1, HZ - .06, .14

    def snormal(p):
        q = np.array([max(abs(p[0]) - (hx - rr), 0) * np.sign(p[0]), max(abs(p[1]) - (hy - rr), 0) * np.sign(p[1]),
                      max(p[2] - (hz1 - rr), 0)])
        if np.linalg.norm(q) < 1e-6:
            return np.array([0, 0, 1.])
        return nrm(q)
    # core box (inset), 8 corners + bevel-ish top
    ci = .1
    cx, cy, cz = hx - ci, hy - ci, hz1 - ci
    corners = [(-cx, -cy, .04), (cx, -cy, .04), (cx, cy, .04), (-cx, cy, .04),
               (-cx, -cy, cz), (cx, -cy, cz), (cx, cy, cz), (-cx, cy, cz)]
    vi = [g.v(p, nrm(np.array(p) - [0, 0, .5]), (0, 0), (.45,) * 3) for p in corners]
    for f in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)):
        g.F.append(tuple(vi[k] for k in f)); g.M.append(mc)
    # a few stems at the foot
    for i in range(10):
        x = rng.uniform(-hx + .1, hx - .1); y = rng.uniform(-.15, .15)
        pts = [np.array([x, y, -.05]), np.array([x + rng.uniform(-.05, .05), y + rng.uniform(-.05, .05), .2]),
               np.array([x + rng.uniform(-.08, .08), y + rng.uniform(-.08, .08), .42])]
        tube(g, pts, [.016, .013, .01], 3, mb, 0, lambda p: (.6,) * 3)
    # cards over the clipped surface (area weighted: top, two long sides, two ends)
    faces = [('top', LX * WY), ('+y', LX * HZ), ('-y', LX * HZ), ('+x', WY * HZ), ('-x', WY * HZ)]
    ar = np.array([a for _, a in faces]); ar /= ar.sum()
    n_cards = 1330
    for k in range(n_cards):
        f = faces[rng.choice(len(faces), p=ar)][0]
        if f == 'top':
            p = np.array([rng.uniform(-hx, hx), rng.uniform(-hy, hy), hz1])
        elif f in ('+y', '-y'):
            p = np.array([rng.uniform(-hx, hx), hy * (1 if f == '+y' else -1), rng.uniform(.14, hz1)])
        else:
            p = np.array([hx * (1 if f == '+x' else -1), rng.uniform(-hy, hy), rng.uniform(.14, hz1)])
        n = snormal(p)
        # pull onto the rounded edge
        p = p - n * rng.uniform(.0, .12)
        size = .3 * rng.uniform(.8, 1.15)
        axis = nrm(rng.normal(size=3) + n * .6)
        tan = nrm(axis - n * (axis @ n))
        base = p - tan * size * .45
        tint = rng.normal(1, .04, 3) * rng.uniform(.9, 1.03)
        ax = tan
        side = nrm(np.cross(ax, n))
        n0 = rotate(n, ax, rng.uniform(-.7, .7)); side = np.cross(ax, n0)
        B0 = base; T0 = base + ax * size; w = size
        ids = []
        for q, uv in ((B0 - side * w / 2, (0, 0)), (B0 + side * w / 2, (1, 0)), (T0 + side * w / 2, (1, 1)),
                      (T0 - side * w / 2, (0, 1))):
            nn = nrm(snormal(q) * .75 + n0 * .25)
            depth = max(0.0, min(1.0, .35 + .65 * (q[2] / HZ)))
            ids.append(g.v(q, nn, uv, tuple(np.clip((.55 + .45 * depth) * tint, 0, 1))))
        g.F.append(tuple(ids)); g.M.append(ml)
    return g, dict(nodes=0, r_min=.01, cards=n_cards, trunk_r=0.0, clear=0.0)


def grass_clump(name, seed):
    rng = np.random.default_rng(seed)
    g = Geo(); ml = g.mat(leaf_mat('grass'))
    crown = Crown((0, 0, .25), (.35, .35, .3))
    for b in range(64):
        a = rng.uniform(0, 6.28); rr = rng.uniform(0, .06)
        hd = np.array([math.cos(a), math.sin(a), 0.])
        p0 = hd * rr + [0, 0, -.02]
        L = rng.uniform(.38, .62)
        tilt0 = rng.uniform(.05, .45); bend = rng.uniform(.6, 1.3) * (.4 + tilt0)
        w = rng.uniform(.014, .02)
        col = rng.integers(0, 4)
        wv = nrm(np.cross(UP, hd)); wv = rotate(wv, UP, rng.uniform(-.5, .5))
        tint = rng.normal(1, .04, 3)
        pts = [p0]; ang = tilt0
        for k in range(4):
            d = hd * math.sin(ang) + UP * math.cos(ang)
            pts.append(pts[-1] + d * L / 4)
            ang += bend / 4 * (1 + k * .4)
        ids = []
        for k, p in enumerate(pts):
            t = k / 4
            nn = nrm(UP * .75 + hd * .55)
            c = tuple(np.clip((.5 + .5 * t) * tint, 0, 1))
            u0, u1 = col / 4 + .004, (col + 1) / 4 - .004
            ids.append((g.v(p - wv * w / 2, nn, (u0, t), c), g.v(p + wv * w / 2, nn, (u1, t), c)))
        fn = np.cross(wv, nrm(pts[1] - pts[0]))
        flip = fn @ hd < 0
        for k in range(4):
            a0, b0 = ids[k]; a1, b1 = ids[k + 1]
            g.F.append((b0, a0, a1, b1) if flip else (a0, b0, b1, a1)); g.M.append(ml)
    return g, dict(nodes=0, r_min=0, cards=64, trunk_r=0.0, clear=0.0)


PLANTS = [('plane', 'street'), ('linden', 'street'), ('maple', 'street'), ('birch', 'street'), ('cherry', 'street'),
          ('pear', 'street'), ('oak', 'park'), ('willow', 'park'), ('pine', 'park'),
          ('shrub_a', 'shrub'), ('shrub_b', 'shrub'), ('hedge', 'shrub'), ('grass_clump', 'shrub')]


def build_plant(sp, seed):
    if sp in TREES:
        return broadleaf(sp, TREES[sp], seed)
    if sp == 'pine':
        return pine(sp, seed)
    if sp in SHRUBS:
        return shrub(sp, SHRUBS[sp], seed)
    if sp == 'hedge':
        return hedge(sp, seed)
    return grass_clump(sp, seed)


def main():
    t0 = time.time()
    bl.reset()
    if not NO_TEX:
        for i, k in enumerate(BARK):
            make_bark(k, 100 + i)
        for i, k in enumerate(LEAVES):
            make_leaves(k, 200 + i)
        print('[city_trees] textures %.1fs' % (time.time() - t0))
    rows = []
    for i, (sp, kind) in enumerate(PLANTS):
        if ONLY and sp not in ONLY:
            continue
        t1 = time.time()
        g, info = build_plant(sp, 1000 + 37 * i)
        o = g.build('CT_' + sp)
        bb = np.array([v.co[:] for v in o.data.vertices])
        hh = float(bb[:, 2].max()); ww = float(max(np.ptp(bb[:, 0]), np.ptp(bb[:, 1])))
        o['ct'] = dict(h=round(hh, 2), w=round(ww, 2), kind=kind, species=sp, trunk_r=round(info['trunk_r'], 3),
                       clear=round(info['clear'], 2))
        bark = sum(g.tris_of(k) for k, m in enumerate(g.mats) if m.name.startswith('ct_bark'))
        rows.append((sp, hh, ww, float(bb[:, 2].min()), g.tris(), bark, info['cards'], info['r_min'], info['nodes']))
        print('[city_trees] CT_%-12s h %5.2f w %5.2f zmin %5.2f  %6d tris (bark %5d)  cards %4d  r_min %.3f  nodes %d  %.1fs'
              % (rows[-1] + (time.time() - t1,)))
    out = 'city_trees.glb' if not ONLY else 'city_trees_partial.glb'
    bl.export(out, export_vertex_color='MATERIAL', export_image_format='AUTO')
    print('[city_trees] done %.1fs' % (time.time() - t0))


main()
