"""Procedural trees for New Meridian (Earth): trees.glb (root nodes TR_*).

blender --background --python tools/blender/trees.py [-- [species ...] [--fast]]

Every tree is grown here, nothing is imported:
  * broadleaf crowns by space colonisation (attractor clouds shaped per species, tropism, jitter), radii by the
    pipe model, smoothed into tapered bark tubes with root flare / buttresses;
  * conifers by a whorled recursive rule (trunk leader, drooping whorls, side shoots, layered pads for pines);
  * foliage as leaf-cluster cards (folded quads) at the twig tips, normals bent away from the crown centre and an
    ambient-occlusion vertex colour (COLOR_0) that darkens the inner crown;
  * snow (`snow` material) on the up-facing faces of branches and rocks, snow-laden needle sprays and snow clump cards.
Textures (1024 px, drawn with numpy here and embedded as WebP): tileable bark colour + normal maps (oak, birch, pine,
cherry) and alpha leaf-cluster atlases per species (2x2 clusters, willow 4 hanging strands).
Three levels per tree:  TR_x (hero, 3-6k tris), TR_x_mid (~0.5-1k tris), TR_x_lod (two crossed impostor cards that
show a Cycles render of the hero tree from a shared atlas).  Root nodes carry extras: h (height), w (crown radius),
trunk (trunk radius at 1 m) for colliders and LOD ranges.
Material names are an API: leaves_* (alpha-tested cards), bark_*, snow, rock.
Pass species names (e.g. `-- oak birch`) to build only those into $TREE_OUT (default /tmp/trees_partial.glb);
$TREE_PREVIEW=<dir> also writes one GLB per species (heroes side by side) for tools/blender/preview.py.
"""
import bpy, math, os, sys, random, tempfile, time
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import bl

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FAST = '--fast' in ARGS
ONLY = [a for a in ARGS if not a.startswith('--')]
TEX = 512 if FAST else 1024
TMP = tempfile.mkdtemp(prefix='trees_')
PREVIEW = os.environ.get('TREE_PREVIEW')
IMP = 256                     # impostor cell size (px)
UP = np.array([0., 0., 1.])


def nrm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


# =============================================================================================== textures
def spectral(S, seed, beta=2.0, ax=1.0, ay=1.0, fmin=0.0):
    """Tileable fractal noise by spectral synthesis (zero mean, unit std). ax/ay > 1 squash features along x/y."""
    r = np.random.default_rng(seed)
    f = np.fft.fftfreq(S) * S
    FX, FY = np.meshgrid(f, f)
    k = np.sqrt((FX * ax) ** 2 + (FY * ay) ** 2)
    k[0, 0] = 1
    amp = k ** (-beta / 2)
    amp[0, 0] = 0
    if fmin:
        amp[k < fmin] = 0
    n = np.real(np.fft.ifft2(amp * np.exp(2j * np.pi * r.random((S, S)))))
    return (n - n.mean()) / (n.std() + 1e-9)


def voronoi(S, nx, ny, seed, jitter=.9):
    """Periodic cellular noise: returns (F1, F2) distances in cell units."""
    r = np.random.default_rng(seed)
    pts = r.random((ny, nx, 2)) * jitter + (1 - jitter) / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    gx, gy = xx * nx, yy * ny
    ix, iy = np.floor(gx).astype(int), np.floor(gy).astype(int)
    ds = []
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = ix + ox, iy + oy
            p = pts[cy % ny, cx % nx]
            dx = cx + p[..., 0] - gx
            dy = cy + p[..., 1] - gy
            ds.append(np.sqrt(dx * dx + dy * dy))
    ds = np.sort(np.stack(ds), axis=0)
    return ds[0], ds[1]


def blur(a, sigma):
    """Periodic gaussian blur (FFT)."""
    S0, S1 = a.shape[:2]
    fy = np.fft.fftfreq(S0)[:, None]; fx = np.fft.fftfreq(S1)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    if a.ndim == 3:
        return np.stack([np.real(np.fft.ifft2(np.fft.fft2(a[..., i]) * g)) for i in range(a.shape[2])], -1)
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def normal_map(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * .5 * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * .5 * strength
    n = np.dstack([-dx, dy, np.ones_like(h)])            # rows run down the image: +v is up, so -dh/dv = +dh/drow
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * .5 + .5


def save(name, rgb, alpha=None):
    from PIL import Image
    arr = np.clip(rgb, 0, 1)
    if alpha is not None:
        arr = np.dstack([arr, np.clip(alpha, 0, 1)])
    img = Image.fromarray((arr * 255 + .5).astype(np.uint8), 'RGBA' if alpha is not None else 'RGB')
    path = os.path.join(TMP, name + '.png')
    img.save(path)
    return path


def lerp(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return np.asarray(a) * (1 - t) + np.asarray(b) * t


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def bark_textures():
    S = TEX
    out = {}
    # oak: deep meandering vertical fissures between corky plates, lichen on the plates
    n1 = spectral(S, 11, 2.3, 1, 7)
    n2 = spectral(S, 12, 2.0, 5, 1)
    fine = spectral(S, 13, 1.2)
    plates = np.clip(np.abs(n1) / 1.0, 0, 1) ** .38
    h = plates * (1 - .25 * sstep(1.2, 2.2, np.abs(n2))) + .05 * fine
    lich = sstep(.4, 1.3, spectral(S, 14, 2.6)) * sstep(.35, .7, plates)
    col = lerp((.12, .09, .07), (.44, .39, .33), h)
    col = lerp(col, (.48, .50, .40), lich * .55)
    col *= (1 + .08 * fine)[..., None]
    out['oak'] = (save('bark_oak_c', col), save('bark_oak_n', normal_map(h, 7.0)))
    # birch: chalk-white with horizontal dark lenticels, black scars and a little peeling tan
    st = spectral(S, 21, 1.3, 1, 1)
    lent = sstep(1.7, 2.4, spectral(S, 22, 1.4, 1, 9)) * sstep(-.2, .6, st)
    scar = sstep(1.0, 1.5, spectral(S, 23, 2.8, 1, 2.5))
    peel = sstep(.9, 1.4, spectral(S, 24, 2.4, 1, 4))
    fine = spectral(S, 25, 1.1)
    col = np.ones((S, S, 3)) * np.array((.86, .84, .78)) * (1 + .05 * fine)[..., None]
    col = lerp(col, (.80, .66, .52), peel * .5)
    col = lerp(col, (.10, .09, .08), np.clip(lent * .9 + scar, 0, 1))
    h = .6 + .06 * fine - .5 * lent - .3 * scar + .1 * peel
    out['birch'] = (save('bark_birch_c', col), save('bark_birch_n', normal_map(h, 4.0)))
    # pine: scaly plates (stretched cells) with dark furrows, reddish under-bark
    f1, f2 = voronoi(S, 7, 4, 31)
    edge = f2 - f1
    n = spectral(S, 32, 2.0)
    fine = spectral(S, 33, 1.2)
    h = sstep(.0, .35, edge) * (.8 + .2 * n) + .05 * fine
    tone = np.clip(.5 + .25 * spectral(S, 34, 3.0), 0, 1)
    col = lerp(lerp((.42, .25, .16), (.46, .38, .32), tone), (.08, .05, .04), 1 - sstep(.0, .25, edge))
    col *= (1 + .07 * fine)[..., None]
    out['pine'] = (save('bark_pine_c', col), save('bark_pine_n', normal_map(h, 6.0)))
    # cherry: smooth dark mahogany with pale horizontal lenticel bands
    band = sstep(1.6, 2.3, spectral(S, 41, 1.6, 1, 14))
    rings = sstep(1.2, 1.8, spectral(S, 42, 2.4, 1, 10))
    fine = spectral(S, 43, 1.4)
    col = np.ones((S, S, 3)) * np.array((.27, .14, .12)) * (1 + .1 * spectral(S, 44, 2.4) + .05 * fine)[..., None]
    col = lerp(col, (.50, .40, .36), band * .8)
    col = lerp(col, (.16, .09, .08), rings * .6)
    h = .5 + .04 * fine + .25 * band - .2 * rings
    out['cherry'] = (save('bark_cherry_c', col), save('bark_cherry_n', normal_map(h, 4.0)))
    return out


def snow_textures():
    """Ground snow for the terrain shader: assets/textures/snow_c.jpg + snow_n.jpg (tileable)."""
    from PIL import Image
    S = TEX
    big = spectral(S, 51, 2.6)
    mid = spectral(S, 52, 2.0)
    fine = spectral(S, 53, 1.0)
    h = .5 * big + .35 * mid + .12 * fine
    col = np.ones((S, S, 3)) * np.array((.93, .95, .98))
    col = lerp(col, (.80, .85, .93), sstep(.2, 1.4, -h) * .6)          # blue hollows
    sp = (fine > 2.6).astype(float)                                       # glints
    col = np.clip(col * (1 + .025 * fine)[..., None] + sp[..., None] * .05, 0, 1)
    Image.fromarray((col * 255).astype(np.uint8)).save(os.path.join(bl.TEXTURES, 'snow_c.jpg'), quality=90)
    Image.fromarray((normal_map(h, 1.6) * 255).astype(np.uint8)).save(os.path.join(bl.TEXTURES, 'snow_n.jpg'), quality=92)
    print('[texture] snow_c.jpg snow_n.jpg')


# ---------------------------------------------------------------- leaf-cluster painter
class Canvas:
    def __init__(self, W, H=None):
        H = H or W
        self.c = np.zeros((H, W, 3), np.float32); self.a = np.zeros((H, W), np.float32)
        self.W, self.H = W, H

    def region(self, x0, y0, x1, y1):
        x0 = max(0, int(math.floor(x0))); y0 = max(0, int(math.floor(y0)))
        x1 = min(self.W, int(math.ceil(x1)) + 1); y1 = min(self.H, int(math.ceil(y1)) + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        return (slice(y0, y1), slice(x0, x1), xx + .5, yy + .5)

    def over(self, R, alpha, rgb):
        sy, sx = R[0], R[1]
        a = alpha[..., None]
        self.c[sy, sx] = rgb * a + self.c[sy, sx] * (1 - a)
        self.a[sy, sx] = alpha + self.a[sy, sx] * (1 - alpha)

    def seg(self, x0, y0, x1, y1, w0, w1, col, shade=True):
        m = max(w0, w1) / 2 + 2
        R = self.region(min(x0, x1) - m, min(y0, y1) - m, max(x0, x1) + m, max(y0, y1) + m)
        if R is None:
            return
        xx, yy = R[2], R[3]
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / L2, 0, 1)
        px, py = x0 + t * dx - xx, y0 + t * dy - yy
        d = np.sqrt(px * px + py * py)
        w = (w0 + (w1 - w0) * t) / 2
        al = np.clip(w - d + .5, 0, 1)
        if not al.any():
            return
        c = np.broadcast_to(np.asarray(col, np.float32), al.shape + (3,)).copy()
        if shade:   # round stem: lighter on one side
            L = math.sqrt(L2)
            side = ((xx - x0) * (-dy) + (yy - y0) * dx) / L / np.maximum(w, .5)
            c *= (1 - .25 * np.clip(side, -1, 1))[..., None]
        self.over(R, al, c)

    def leaf(self, px, py, ang, L, shape, col, light=1.0, vein=.18, nveins=7, edge=.12):
        """ang: direction from petiole to tip (0 = up the image, radians clockwise)."""
        dxr, dyr = math.sin(ang), -math.cos(ang)
        cx, cy = px + dxr * L / 2, py + dyr * L / 2
        R = self.region(cx - L * .62, cy - L * .62, cx + L * .62, cy + L * .62)
        if R is None:
            return
        xx, yy = R[2] - px, R[3] - py
        u = (xx * dxr + yy * dyr) / L
        v = (xx * -dyr + yy * dxr) / L
        uc = np.clip(u, 0, 1)
        hw = np.nan_to_num(shape(uc)) * ((u >= 0) & (u <= 1))
        d = (hw - np.abs(v)) * L
        al = np.clip(d + .5, 0, 1) * (hw * L > .35)
        if not al.any():
            return
        c = np.broadcast_to(np.asarray(col, np.float32), al.shape + (3,)).copy()
        k = (.82 + .26 * uc) * light * (1 - .10 * np.sign(v) * np.clip(np.abs(v) / (hw + 1e-3), 0, 1))
        mid = np.exp(-(v * L / (.7 + .012 * L)) ** 2)
        sv = np.abs(np.sin((uc * 1.0 - np.abs(v) * 1.3) * math.pi * nveins)) ** 30 * (np.abs(v) > .02)
        k = k * (1 + vein * mid) * (1 - .10 * sv) * (1 - edge * (1 - np.clip(d / 2.5, 0, 1)))
        self.over(R, al, c * k[..., None])

    def polar(self, cx, cy, R0, rfun, col, light=1.0, center=None, crad=.25):
        R = self.region(cx - R0 * 1.05, cy - R0 * 1.05, cx + R0 * 1.05, cy + R0 * 1.05)
        if R is None:
            return
        xx, yy = R[2] - cx, R[3] - cy
        rho = np.sqrt(xx * xx + yy * yy)
        th = np.arctan2(xx, -yy)
        lim = rfun(th) * R0
        al = np.clip(lim - rho + .5, 0, 1)
        if not al.any():
            return
        t = np.clip(rho / np.maximum(lim, 1e-3), 0, 1)
        c = np.broadcast_to(np.asarray(col, np.float32), al.shape + (3,)).copy()
        c = c * ((.84 + .22 * t) * light)[..., None]
        if center is not None:
            cm = sstep(crad * R0 + 1, crad * R0 - 1, rho)
            c = c * (1 - cm[..., None]) + np.asarray(center, np.float32) * cm[..., None]
        self.over(R, al, c)

    def finish(self):
        """Bleed leaf colours into the transparent texels so mipmaps don't go dark at the edges."""
        a = self.a
        prem = self.c * a[..., None]
        out = self.c.copy()
        fill = np.full_like(out, 0)
        got = np.zeros_like(a)
        for s in (2, 8, 32):
            ba = blur(a, s); bc = blur(prem, s)
            ok = (ba > 1e-3) & (got == 0)
            fill[ok] = bc[ok] / ba[ok][..., None]
            got[ok] = 1
        mean = prem.sum((0, 1)) / max(a.sum(), 1)
        fill[got == 0] = mean
        w = np.clip(a * 1.5, 0, 1)[..., None]
        out = out * w + fill * (1 - w)
        return out, a


def jit(rng, col, s=.07):
    c = np.asarray(col, np.float32) * (1 + rng.normal(0, s, 3)).astype(np.float32)
    return np.clip(c * rng.uniform(.88, 1.1), 0, 1)


def pick(rng, cols):
    return cols[rng.integers(len(cols))]


# leaf outlines: half width (in leaf lengths) along u = 0 (petiole) .. 1 (tip)
def _s(x):
    return np.maximum(0, np.sin(np.pi * np.clip(x, 0, 1)))


def ovate(a, tipk=.35, serr=0.0):
    return lambda u: a * _s(u) ** .75 * (1.12 - tipk * u) + serr * a * np.abs(np.sin(u * 40)) * (u > .1)


def lance(a, p=1.0):
    return lambda u: a * _s(np.clip(u, 0, 1) ** .8) ** p


def oak_outline(a):
    return lambda u: a * _s(u) ** .5 * (.58 + .42 * np.abs(np.cos(np.pi * 4.5 * u))) * (1.05 - .25 * u)


def maple_r(th):
    lobes = ((0, 1.0), (.95, .88), (-.95, .88), (1.85, .55), (-1.85, .55))
    r = .34 + sum(w * np.exp(-((th - a) / .30) ** 2) * .66 for a, w in lobes)
    r = r + .05 * np.abs(np.sin(th * 13))
    return r * (np.abs(th) < 2.55) + .18 * (np.abs(th) >= 2.55)


def petals(n=5, depth=.45, phase=0.0):
    return lambda th: (1 - depth) + depth * np.abs(np.cos(n / 2 * (th + phase))) ** .7


def twig_path(rng, x, y, ang, length, steps=6, wob=.18):
    pts = [(x, y)]
    a = ang
    for i in range(steps):
        a += rng.normal(0, wob)
        x += math.sin(a) * length / steps; y -= math.cos(a) * length / steps
        pts.append((x, y))
    return pts


def draw_twig(cv, pts, w0, w1, col):
    n = len(pts) - 1
    for i in range(n):
        cv.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w0 + (w1 - w0) * i / n, w0 + (w1 - w0) * (i + 1) / n, col)


def along(pts, t):
    """point + direction angle at fraction t of a polyline."""
    n = len(pts) - 1
    f = t * n; i = min(n - 1, int(f)); k = f - i
    (x0, y0), (x1, y1) = pts[i], pts[i + 1]
    return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, math.atan2(x1 - x0, -(y1 - y0))


TWIG = (.30, .22, .15)


def broadleaf_cell(cv, ox, oy, C, rng, leaf_fn, n_side=3, twig_len=.78, gap=.075, start=.18, spread=(.5, 1.1),
                   tip_rosette=0, twig_col=TWIG, stem_w=.012):
    bx, by = ox + C * (.5 + rng.uniform(-.04, .04)), oy + C * .985
    main = twig_path(rng, bx, by, rng.normal(0, .12), C * twig_len, 7, .1)
    twigs = [(main, 1.0)]
    for k in range(n_side):
        t = .25 + .55 * (k + rng.random() * .6) / n_side
        x, y, a = along(main, t)
        s = 1 if k % 2 == 0 else -1
        twigs.append((twig_path(rng, x, y, a + s * rng.uniform(*spread), C * twig_len * (1 - t) * rng.uniform(.75, 1.05), 5, .12), .6))
    for pts, wk in twigs:
        draw_twig(cv, pts, C * stem_w * wk, C * stem_w * .35 * wk, twig_col)
    leaves = []
    for pts, wk in twigs:
        L = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        n = max(2, int(L / (gap * C)))
        for i in range(n):
            t = start + (1 - start) * i / max(1, n - 1)
            x, y, a = along(pts, min(t, .999))
            s = 1 if i % 2 else -1
            leaves.append((x, y, a + s * rng.uniform(.45, 1.05), t))
        x, y, a = along(pts, .999)
        leaves.append((x, y, a + rng.normal(0, .15), 1.0))
        for r in range(tip_rosette):
            leaves.append((x, y, a + rng.uniform(-1.4, 1.4), 1.0))
    rng.shuffle(leaves)
    for x, y, a, t in leaves:
        leaf_fn(cv, x, y, a, t)


def snow_blobs(cv, ox, oy, C, rng, cover=.45, seed=0):
    """White clumps over the existing needle mask (snow-laden spray)."""
    S = C
    n = spectral(S, 900 + seed, 2.4)
    m = sstep(1 - cover * 1.6, 1 - cover * 1.6 + .5, n)
    sl = (slice(oy, oy + C), slice(ox, ox + C))
    grow = np.clip(blur(cv.a[sl], 3) * 2.2, 0, 1)
    al = np.clip(m * grow, 0, 1)
    shade = np.clip(.88 + .12 * n, .75, 1.02)
    col = np.dstack([shade * .93, shade * .95, shade * 1.0])
    cv.c[sl] = col * al[..., None] + cv.c[sl] * (1 - al[..., None])
    cv.a[sl] = np.maximum(cv.a[sl], al)


def leaf_textures(names):
    """Returns {name: (png path, cols, rows)} for the requested foliage atlases."""
    S = TEX
    C = S // 2
    out = {}
    cells = [(0, 0), (C, 0), (0, C), (C, C)]

    def make(name, cell_fn, cols=2, rows=2, seed=0):
        if name not in names:
            return
        rng = np.random.default_rng(abs(hash(name)) % 10000 + seed)
        cv = Canvas(S)
        cw, ch = S // cols, S // rows
        for j in range(rows):
            for i in range(cols):
                cell_fn(cv, i * cw, j * ch, cw, ch, rng)
        rgb, a = cv.finish()
        out[name] = (save('leaves_' + name, rgb, a), cols, rows)

    def sq(fn):
        return lambda cv, ox, oy, cw, ch, rng: fn(cv, ox, oy, cw, rng)

    # --- oak: lobed leaves in rosettes at the twig tips
    def oak_cell(pal, light=(.75, 1.15)):
        def f(cv, ox, oy, C, rng):
            def lf(cv, x, y, a, t):
                cv.leaf(x, y, a, C * rng.uniform(.19, .26), oak_outline(.25), jit(rng, pick(rng, pal)), rng.uniform(*light), nveins=5)
            broadleaf_cell(cv, ox, oy, C, rng, lf, n_side=4, gap=.085, start=.22, tip_rosette=4, twig_len=.74)
        return f
    make('oak', sq(oak_cell([(.25, .37, .11), (.30, .42, .13), (.21, .33, .10), (.34, .45, .15)])))
    make('oak_gold', sq(oak_cell([(.74, .57, .17), (.82, .66, .22), (.62, .50, .17), (.88, .74, .30), (.50, .48, .17)])))

    # --- ash: pinnate compound leaves (paired lance leaflets + a terminal one)
    def ash_cell(cv, ox, oy, C, rng, pal=((.27, .41, .13), (.31, .45, .15), (.24, .37, .12))):
        def compound(cv, x, y, a, t):
            L = C * rng.uniform(.30, .40)
            pts = twig_path(rng, x, y, a, L, 4, .08)
            draw_twig(cv, pts, C * .006, C * .003, (.36, .40, .2))
            col = jit(rng, pick(rng, pal)); li = rng.uniform(.8, 1.12)
            for k in range(5):
                tx, ty, ta = along(pts, .2 + .19 * k)
                for s in (-1, 1):
                    cv.leaf(tx, ty, ta + s * rng.uniform(.9, 1.25), C * rng.uniform(.10, .13), lance(.17), jit(rng, col, .04), li * rng.uniform(.92, 1.06), nveins=6)
            tx, ty, ta = along(pts, .999)
            cv.leaf(tx, ty, ta, C * .13, lance(.17), col, li, nveins=6)
        broadleaf_cell(cv, ox, oy, C, rng, compound, n_side=2, gap=.2, start=.3)
    make('ash', sq(ash_cell))

    # --- maple: palmate leaves on long petioles, opposite pairs
    def maple_cell(pal):
        def f(cv, ox, oy, C, rng):
            def lf(cv, x, y, a, t):
                R = C * rng.uniform(.085, .115)
                px, py = x + math.sin(a) * R * .9, y - math.cos(a) * R * .9
                cv.seg(x, y, px, py, 2.2, 1.6, (.45, .3, .15))
                rot = a
                cv.polar(px + math.sin(a) * R * .55, py - math.cos(a) * R * .55, R, lambda th: maple_r(((th - rot + math.pi) % (2 * math.pi)) - math.pi),
                         jit(rng, pick(rng, pal)), rng.uniform(.78, 1.15))
            broadleaf_cell(cv, ox, oy, C, rng, lf, n_side=3, gap=.1, start=.25, tip_rosette=2)
        return f
    make('maple', sq(maple_cell([(.24, .40, .11), (.29, .45, .13), (.21, .36, .10)])))
    make('maple_autumn', sq(maple_cell([(.80, .16, .05), (.95, .36, .05), (.98, .50, .08), (.93, .64, .14), (.62, .09, .05), (.90, .27, .05)])))

    # --- birch: small serrated ovate leaves on fine drooping twigs
    def birch_cell(cv, ox, oy, C, rng):
        pal = [(.40, .52, .15), (.48, .58, .18), (.36, .48, .14), (.55, .62, .22)]
        def lf(cv, x, y, a, t):
            cv.leaf(x, y, a, C * rng.uniform(.09, .13), ovate(.33, .45, .05), jit(rng, pick(rng, pal)), rng.uniform(.8, 1.15), nveins=6)
        broadleaf_cell(cv, ox, oy, C, rng, lf, n_side=4, gap=.055, start=.15, twig_col=(.26, .18, .14), stem_w=.008)
    make('birch', sq(birch_cell))

    # --- cherry: pompoms of double blossoms with a few young leaves
    def cherry_cell(cv, ox, oy, C, rng):
        pinks = [(.96, .56, .76), (.99, .70, .86), (.90, .44, .66), (.98, .78, .90), (.93, .50, .72)]
        def lf(cv, x, y, a, t):
            if rng.random() < .25:
                cv.leaf(x, y, a, C * rng.uniform(.09, .12), ovate(.3), jit(rng, (.45, .35, .16)), rng.uniform(.8, 1.05))
                return
            for k in range(rng.integers(3, 7)):
                r = C * rng.uniform(.03, .045)
                cx, cy = x + rng.normal(0, C * .035), y + rng.normal(0, C * .035)
                col = jit(rng, pick(rng, pinks), .05); ph = rng.random() * 3
                cv.polar(cx, cy, r, petals(5, .35, ph), col, rng.uniform(.85, 1.1), center=(.75, .25, .35), crad=.18)
                cv.polar(cx, cy, r * .62, petals(5, .4, ph + .6), np.clip(col * 1.06, 0, 1), 1.0, center=(.85, .4, .45), crad=.25)
        broadleaf_cell(cv, ox, oy, C, rng, lf, n_side=4, gap=.07, start=.1, twig_col=(.24, .12, .10), stem_w=.012)
    make('cherry', sq(cherry_cell))

    # --- umbrella (savanna) tree: feathery bipinnate fronds of tiny leaflets
    def umb_cell(cv, ox, oy, C, rng):
        pal = [(.36, .50, .13), (.42, .56, .16), (.31, .45, .12)]
        def frond(cv, x, y, a, t):
            L = C * rng.uniform(.26, .34)
            pts = twig_path(rng, x, y, a, L, 4, .1)
            draw_twig(cv, pts, 2.0, 1.0, (.35, .38, .18))
            col = jit(rng, pick(rng, pal)); li = rng.uniform(.8, 1.12)
            n = 13
            for k in range(n):
                tx, ty, ta = along(pts, .08 + .9 * k / n)
                for s in (-1, 1):
                    cv.leaf(tx, ty, ta + s * 1.15, C * .045 * (1 - .4 * k / n), ovate(.32), jit(rng, col, .05), li, vein=.0, nveins=1, edge=.05)
        broadleaf_cell(cv, ox, oy, C, rng, frond, n_side=3, gap=.13, start=.2, twig_col=(.3, .24, .17))
    make('umbrella', sq(umb_cell))

    # --- rainforest: big glossy drip-tip leaves
    def rain_cell(cv, ox, oy, C, rng):
        pal = [(.13, .30, .09), (.18, .36, .11), (.11, .26, .08), (.22, .40, .13)]
        def lf(cv, x, y, a, t):
            cv.leaf(x, y, a, C * rng.uniform(.26, .36), lance(.2, .7), jit(rng, pick(rng, pal)), rng.uniform(.8, 1.2), vein=.25, nveins=9)
        broadleaf_cell(cv, ox, oy, C, rng, lf, n_side=2, gap=.13, start=.3, tip_rosette=2, stem_w=.016)
    make('rainforest', sq(rain_cell))

    # --- bush: dense small leaves; flowering variant adds white-pink blossoms
    def bush_cell(flowers):
        def f(cv, ox, oy, C, rng):
            pal = [(.20, .34, .11), (.24, .39, .12), (.17, .30, .10)]
            def lf(cv, x, y, a, t):
                cv.leaf(x, y, a, C * rng.uniform(.09, .13), ovate(.36), jit(rng, pick(rng, pal)), rng.uniform(.75, 1.15), nveins=5)
                if flowers and rng.random() < .3:
                    cv.polar(x + rng.normal(0, C * .03), y + rng.normal(0, C * .03), C * .03, petals(5, .4, rng.random()), jit(rng, (.97, .88, .92), .03), 1.0, center=(.95, .8, .3), crad=.2)
            broadleaf_cell(cv, ox, oy, C, rng, lf, n_side=5, gap=.05, start=.1)
        return f
    make('bush', sq(bush_cell(False)))
    make('bush_flower', sq(bush_cell(True)))

    # --- willow: four hanging strands (cards hang from the top of the strip)
    def willow_strip(cv, ox, oy, cw, ch, rng):
        pal = [(.47, .58, .24), (.53, .63, .28), (.42, .54, .22)]
        x, y = ox + cw / 2, oy + 2
        pts = [(x, y)]
        for i in range(10):
            x += rng.normal(0, cw * .03); y += ch * .095
            pts.append((min(max(x, ox + cw * .3), ox + cw * .7), y))
        draw_twig(cv, pts, 3, 1.4, (.42, .38, .2))
        n = 46
        for k in range(n):
            t = .03 + .95 * k / n
            px, py, a = along(pts, t)
            s = 1 if k % 2 else -1
            L = cw * rng.uniform(.34, .46) * (1 - .3 * t)
            cv.leaf(px, py, a + s * rng.uniform(.25, .5), L, lance(.1), jit(rng, pick(rng, pal)), rng.uniform(.8, 1.15), vein=.12, nveins=3)
    make('willow', willow_strip, cols=4, rows=1)

    # --- pine: long needle fascicles
    def pine_cell(cv, ox, oy, C, rng, pal=((.20, .36, .18), (.25, .42, .20), (.17, .31, .16))):
        main = twig_path(rng, ox + C * .5, oy + C * .985, rng.normal(0, .1), C * .62, 6, .08)
        twigs = [main]
        for k in range(2):
            x, y, a = along(main, .35 + .25 * k)
            twigs.append(twig_path(rng, x, y, a + (1 if k else -1) * rng.uniform(.5, .8), C * .38, 4, .1))
        for p in twigs:
            draw_twig(cv, p, C * .014, C * .008, (.36, .26, .18))
        for p in twigs:
            for i in range(26):
                t = .15 + .85 * i / 25
                x, y, a = along(p, min(t, .999))
                col = jit(rng, pick(rng, pal), .08)
                for k in range(4):
                    na = a + rng.normal(0, .55) * (1.2 - t * .6)
                    L = C * rng.uniform(.14, .24)
                    cv.seg(x, y, x + math.sin(na) * L, y - math.cos(na) * L, 2.4, 1.2, col * rng.uniform(.85, 1.12), shade=False)
    make('pine', sq(pine_cell))

    # --- spruce: flat combed sprays of short needles; the snowy variant gets clumps of snow on top
    def spruce_cell(snow):
        def f(cv, ox, oy, C, rng):
            pal = [(.11, .25, .16), (.14, .29, .18), (.10, .22, .15)]
            main = twig_path(rng, ox + C * .5, oy + C * .985, rng.normal(0, .08), C * .9, 7, .06)
            twigs = [(main, 1.0)]
            for k in range(7):
                t = .12 + .78 * k / 7
                x, y, a = along(main, t)
                s = 1 if k % 2 else -1
                twigs.append((twig_path(rng, x, y, a + s * rng.uniform(.7, 1.0), C * .42 * (1 - t * .7), 4, .08), .6))
            for p, w in twigs:
                draw_twig(cv, p, C * .012 * w, C * .006 * w, (.33, .24, .17))
            for p, w in twigs:
                L = sum(math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) for i in range(len(p) - 1))
                n = int(L / 3.2)
                for i in range(n):
                    x, y, a = along(p, min(.999, i / n))
                    col = jit(rng, pick(rng, pal), .08)
                    for s in (-1, 1):
                        na = a + s * rng.uniform(.75, 1.15)
                        nl = C * rng.uniform(.035, .05)
                        cv.seg(x, y, x + math.sin(na) * nl, y - math.cos(na) * nl, 2.2, 1.1, col, shade=False)
            if snow:
                snow_blobs(cv, ox, oy, C, rng, .5, int(ox + oy))
        return f
    make('spruce', sq(spruce_cell(False)))
    make('spruce_snow', sq(spruce_cell(True)))

    # --- bare winter twigs with snow on their upper edges
    def twig_snow_cell(cv, ox, oy, C, rng):
        def grow(x, y, a, L, w, depth):
            pts = twig_path(rng, x, y, a, L, 3, .15)
            draw_twig(cv, pts, w, w * .6, (.24, .21, .19))
            for i in range(len(pts) - 1):
                (x0, y0), (x1, y1) = pts[i], pts[i + 1]
                flat = abs(math.cos(math.atan2(x1 - x0, -(y1 - y0)))) < .85
                if flat or depth < 2:
                    cv.seg(x0, y0 - w * .45, x1, y1 - w * .45, w * .75, w * .5, (.93, .95, 1.0), shade=False)
            if depth >= 3:
                return
            for k in range(2 + (depth < 1)):
                t = rng.uniform(.3, .9)
                bx, by, ba = along(pts, t)
                grow(bx, by, ba + (1 if k % 2 else -1) * rng.uniform(.35, .8), L * rng.uniform(.45, .65), w * .62, depth + 1)
        grow(ox + C * .5, oy + C * .985, rng.normal(0, .1), C * .55, C * .022, 0)
    make('twig_snow', sq(twig_snow_cell))

    # --- snow clumps lying on conifer branches
    def clump_cell(cv, ox, oy, C, rng):
        yy, xx = np.mgrid[0:C, 0:C].astype(np.float32) / C
        n = spectral(C, int(rng.integers(1e6)), 2.2)
        e = ((xx - .5) / .44) ** 2 + ((yy - .5) / rng.uniform(.26, .36)) ** 2
        m = sstep(1.05, .85, e + .18 * n)
        sh = np.clip(.86 + .14 * (1 - yy) + .05 * n, .7, 1.03)
        col = np.dstack([sh * .92, sh * .95, sh * 1.0])
        sl = (slice(oy, oy + C), slice(ox, ox + C))
        cv.c[sl] = col; cv.a[sl] = m
    make('snowclump', sq(clump_cell))
    return out


# =============================================================================================== materials
_IMG = {}


def image(path, color=True):
    if path in _IMG:
        return _IMG[path]
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    _IMG[path] = im
    return im


def bark_mat(name, tex, tint='#ffffff', rough=.92):
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = rough
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = image(tex[0])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    mix.inputs[7].default_value = (*bl.hexrgb(tint), 1)
    nt.links.new(tn.outputs['Color'], mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    nn = nt.nodes.new('ShaderNodeTexImage'); nn.image = image(tex[1], False)
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(nn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    m['tex'] = 1
    bl._MATS[name] = m
    return m


def leaf_mat(name, path, rough=.7):
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = rough
    try:
        b.inputs['Specular IOR Level'].default_value = .35
    except Exception:
        pass
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = image(path)
    nt.links.new(tn.outputs['Color'], b.inputs['Base Color'])
    rd = nt.nodes.new('ShaderNodeMath'); rd.operation = 'ROUND'          # -> glTF alphaMode MASK (cutoff .5)
    nt.links.new(tn.outputs['Alpha'], rd.inputs[0]); nt.links.new(rd.outputs[0], b.inputs['Alpha'])
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    m.use_backface_culling = False
    bl._MATS[name] = m
    return m


def snow_mat():
    return bl.mat('snow', '#eef2f8', 0, .55)


# =============================================================================================== mesh building
class MB:
    """Accumulates vertices with per-vertex normal/uv/colour and faces with material slots."""

    def __init__(self):
        self.V = []; self.N = []; self.UV = []; self.C = []; self.F = []; self.FM = []
        self.mats = []

    def mat(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def vert(self, p, n, uv, c=1.0):
        self.V.append(p); self.N.append(n); self.UV.append(uv); self.C.append(c)
        return len(self.V) - 1

    def face(self, idx, m):
        self.F.append(idx); self.FM.append(m)

    def tris(self):
        return sum(len(f) - 2 for f in self.F)

    def build(self, name, loc=(0, 0, 0)):
        me = bpy.data.meshes.new(name)
        V = np.array(self.V, np.float64)
        me.from_pydata(V.tolist(), [], [tuple(f) for f in self.F])
        for m in self.mats:
            me.materials.append(m)
        me.polygons.foreach_set('material_index', self.FM)
        me.polygons.foreach_set('use_smooth', [True] * len(self.F))
        lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', np.array(self.UV, np.float32)[lv].ravel())
        ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
        c = np.array(self.C, np.float32)
        ca.data.foreach_set('color', np.stack([c, c, c, np.ones_like(c)], 1).ravel())
        try:
            me.color_attributes.active_color = ca
        except Exception:
            pass
        me.update()
        me.normals_split_custom_set_from_vertices(nrm(np.array(self.N, np.float64)).tolist())
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        o.location = loc
        return o


def perp(t):
    a = np.array([0., 0., 1.]) if abs(t[2]) < .9 else np.array([1., 0., 0.])
    n = np.cross(t, a)
    return n / np.linalg.norm(n)


def sides_for(r, trunk=False, lod=0):
    s = 3 if r < .022 else 4 if r < .045 else 5 if r < .08 else 6 if r < .14 else 8 if r < .26 else 10
    if trunk:
        s = max(s, 9 if r < .5 else 12)
    if lod:
        s = max(3, s // 2 + (1 if trunk else 0))
    return s


def tube(mb, pts, rad, bark, snow=None, trunk=False, lod=0, flare=0.0, buttress=0.0, gnarl=0.0, seed=0, tile=1.4, ao_ground=True):
    pts = np.asarray(pts, np.float64); rad = np.asarray(rad, np.float64)
    n = len(pts)
    if n < 2:
        return
    S = sides_for(rad[0], trunk, lod)
    mi = mb.mat(bark); si = mb.mat(snow) if snow is not None else None
    # tangents + parallel-transport frames
    T = np.zeros_like(pts)
    T[0] = pts[1] - pts[0]; T[-1] = pts[-1] - pts[-2]
    T[1:-1] = pts[2:] - pts[:-2]
    T = nrm(T)
    N0 = perp(T[0]); frames = [N0]
    for i in range(1, n):
        v = frames[-1] - T[i] * np.dot(frames[-1], T[i])
        frames.append(v / max(np.linalg.norm(v), 1e-9))
    rnd = random.Random(seed)
    ph = [rnd.random() * 6.28 for _ in range(4)]
    urep = max(1, round(2 * math.pi * rad[0] / tile)) if rad[0] > .05 else 1
    vacc = 0.0
    rings = []
    for i in range(n):
        if i:
            vacc += np.linalg.norm(pts[i] - pts[i - 1])
        Nf = frames[i]; B = np.cross(T[i], Nf)
        z = pts[i][2]
        ring = []
        for k in range(S + 1):
            th = 2 * math.pi * k / S
            dirv = math.cos(th) * Nf + math.sin(th) * B
            r = rad[i]
            if trunk:
                if flare:
                    r *= 1 + flare * math.exp(-max(0, z + .3) / .45)
                if buttress:
                    r *= 1 + buttress * max(0, math.cos(5 * th + ph[0])) ** 3 * math.exp(-max(0, z + .3) / 1.6)
            if gnarl:
                r *= 1 + gnarl * (math.sin(3 * th + ph[1] + z * 1.7) * .5 + math.sin(5 * th + ph[2] - z * 2.9) * .3)
            p = pts[i] + dirv * r
            ao = .55 + .45 * min(1, max(0, (p[2] + .3) / 1.8)) if ao_ground else 1.0
            ring.append(mb.vert(p, dirv, (k / S * urep, vacc / tile), ao))
        rings.append(ring)
    for i in range(n - 1):
        for k in range(S):
            a, b, c, d = rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]
            m = mi
            if si is not None:
                nz = (mb.N[a][2] + mb.N[b][2] + mb.N[c][2] + mb.N[d][2]) / 4
                if nz > .38:
                    m = si
                    for v in (a, b, c, d):      # a little thickness of snow on top
                        mb.V[v] = mb.V[v] + np.array(mb.N[v]) * .012 + UP * .01
            mb.face((a, b, c, d), m)


def card(mb, base, d, n, size, cell, m, out_fn, aspect=1.0, fold=.0, flipv=False, ao=1.0, nbend=.75):
    """Leaf card: base at the twig, extends along d, faces n. cell = (u0, v0, u1, v1). Folded cards are 2 quads."""
    d = d / np.linalg.norm(d)
    n = n - d * np.dot(n, d); n = n / max(np.linalg.norm(n), 1e-9)
    r = np.cross(d, n)
    w = size * aspect; h = size
    u0, v0, u1, v1 = cell
    if flipv:
        v0, v1 = v1, v0
    p0 = base - d * h * .04
    mi = mb.mat(m)
    def V(p, u, v):
        o = out_fn(p)
        nn = nrm(n * (1 - nbend) + o * nbend)
        return mb.vert(p, nn, (u, v), ao)
    if fold > 0:
        back = -n * w * .5 * fold
        L0 = V(p0 - r * w / 2 + back, u0, v0); C0 = V(p0, (u0 + u1) / 2, v0); R0 = V(p0 + r * w / 2 + back, u1, v0)
        L1 = V(p0 + d * h - r * w / 2 + back, u0, v1); C1 = V(p0 + d * h, (u0 + u1) / 2, v1); R1 = V(p0 + d * h + r * w / 2 + back, u1, v1)
        mb.face((L0, C0, C1, L1), mi); mb.face((C0, R0, R1, C1), mi)
    else:
        a = V(p0 - r * w / 2, u0, v0); b = V(p0 + r * w / 2, u1, v0)
        c = V(p0 + d * h + r * w / 2, u1, v1); e = V(p0 + d * h - r * w / 2, u0, v1)
        mb.face((a, b, c, e), mi)


def cell_uv(i, cols, rows, pad=.004):
    cx, cy = i % cols, (i // cols) % rows
    u0 = cx / cols; u1 = (cx + 1) / cols
    v1 = 1 - cy / rows; v0 = 1 - (cy + 1) / rows        # Blender UV: v up; image row 0 is the top
    return (u0 + pad, v0 + pad, u1 - pad, v1 - pad)


# =============================================================================================== growth
class Tree:
    def __init__(self):
        self.tubes = []        # dict(pts, rad, trunk, lod_ok)
        self.cards = []        # dict(base, d, n, size, aspect, tex, cell, fold, flipv, ao, out)
        self.c = np.array([0, 0, 5.]); self.R = np.array([4, 4, 4.])
        self.meta = {}

    def out(self, p):
        o = (np.asarray(p) - self.c) / self.R
        return nrm(o + np.array([0, 0, .35]))


def envelope(rng, n, c, r, lump=.3, shell=0.0, flat=1.0, nlobes=7):
    lobes = nrm(rng.normal(size=(nlobes, 3)))
    ls = rng.uniform(.5, 1.0, nlobes)
    out = []
    while sum(len(o) for o in out) < n:
        u = rng.uniform(-1, 1, (4000, 3))
        rho = np.linalg.norm(u, axis=1)
        dirv = u / np.maximum(rho, 1e-6)[:, None]
        f = 1 + lump * ((np.maximum(0, dirv @ lobes.T) ** 3) * ls).sum(1) - lump * .45
        ok = (rho < f) & (rho > shell * f) & (u[:, 2] > -flat)
        out.append(np.asarray(c) + u[ok] * np.asarray(r))
    return np.concatenate(out)[:n]


def grow_sc(rng, seeds, A, step, di, dk, trop, jitter, maxit=220):
    """Space colonisation. seeds: list of (pos, parent). Returns positions (N,3) and parent indices."""
    P = [np.asarray(p, np.float64) for p, _ in seeds]; par = [q for _, q in seeds]
    kids = [[] for _ in P]
    for i, q in enumerate(par):
        if q >= 0:
            kids[q].append(i)
    Parr = np.array(P)
    D = np.linalg.norm(A[:, None, :] - Parr[None], axis=2)
    near = D.argmin(1); nd = D.min(1)
    alive = nd > dk
    trop = np.asarray(trop)
    for it in range(maxit):
        act = alive & (nd < di)
        if not act.any():
            break
        idx = near[act]
        v = nrm(A[act] - Parr[idx])
        acc = np.zeros((len(Parr), 3)); np.add.at(acc, idx, v)
        g = np.nonzero(np.bincount(idx, minlength=len(Parr)))[0]
        dirs = nrm(nrm(acc[g]) + trop + rng.normal(0, jitter, (len(g), 3)))
        newp = Parr[g] + dirs * step
        add = []
        for k, gi in enumerate(g):
            if len(kids[gi]) >= 4:
                continue
            if any(np.linalg.norm(Parr[c] - newp[k]) < step * .45 for c in kids[gi]):
                continue
            add.append(k)
        if not add:
            break
        base = len(Parr)
        newp = newp[add]
        for j, k in enumerate(add):
            kids[g[k]].append(base + j); par.append(int(g[k])); kids.append([])
        Parr = np.vstack([Parr, newp])
        Dn = np.linalg.norm(A[:, None, :] - newp[None], axis=2)
        m = Dn.min(1); better = m < nd
        near[better] = base + Dn.argmin(1)[better]; nd = np.minimum(nd, m)
        alive &= nd > dk
    return Parr, np.array(par), kids


def graph_to_tree(T, P, par, kids, sp, rng):
    n = len(P)
    tips = np.zeros(n); dtip = np.zeros(n, int)
    for i in range(n - 1, -1, -1):
        if kids[i]:
            tips[i] = sum(tips[k] for k in kids[i]); dtip[i] = 1 + min(dtip[k] for k in kids[i])
        else:
            tips[i] = 1
    heavy = [max(kids[i], key=lambda k: tips[k]) if kids[i] else -1 for i in range(n)]
    # smooth the polylines (keeps the root and tips)
    for _ in range(2):
        Q = P.copy()
        for i in range(1, n):
            if par[i] >= 0 and heavy[i] >= 0:
                Q[i] = .5 * P[i] + .25 * (P[par[i]] + P[heavy[i]])
        P = Q
    # pipe model radii, scaled so the trunk hits the requested radius
    e = sp.get('pipe', 2.3); tr = sp.get('tip_r', .012)
    raw = tr * tips ** (1 / e)
    k = sp['trunk_r'] / raw[0]
    rad = np.maximum(tr, raw * k ** sp.get('pipe_k', .75))
    rad[0] = sp['trunk_r']
    # trunk taper below the crown
    for i in range(n):
        if sp.get('trunk_ids') is not None and i in sp['trunk_ids']:
            pass
    # chains: follow the heaviest child, other children start new chains
    stack = [(0, None)]
    while stack:
        start, attach = stack.pop()
        chain = [] if attach is None else [attach]
        i = start
        while True:
            chain.append(i)
            ks = sorted(kids[i], key=lambda q: -tips[q])
            if not ks:
                break
            for q in ks[1:]:
                stack.append((q, i))
            i = ks[0]
        pts = P[chain]; rr = rad[chain].copy()
        if attach is not None:
            rr[0] = rr[1] * 1.02
        T.tubes.append(dict(pts=pts, rad=rr, trunk=attach is None, ids=chain))
    T.nodes = (P, par, kids, rad, dtip, tips)
    return P, rad, dtip


def resample(pts, rad, rmin, lod):
    """Drop nodes on straight thin stretches; cut the chain where it gets thinner than rmin."""
    keep = [0]
    acc = 0.0
    for i in range(1, len(pts)):
        if rad[i] < rmin * .7 and i > 1:
            keep.append(i)
            break
        acc += np.linalg.norm(pts[i] - pts[i - 1])
        seg = min(1.6, max(.35, rad[i] * (10 if lod else 6)))
        if acc >= seg or i == len(pts) - 1:
            keep.append(i); acc = 0.0
    if keep[-1] != len(pts) - 1 and rad[keep[-1]] >= rmin * .7:
        keep.append(len(pts) - 1)
    p = pts[keep]; r = rad[keep].copy()
    r[-1] *= .45
    return p, r


def tube_set(T, rmin, lod):
    out = []
    for t in T.tubes:
        r0 = t['rad'][1] if len(t['rad']) > 1 and not t['trunk'] else t['rad'][0]
        if r0 < rmin and not t['trunk']:
            continue
        p, r = resample(t['pts'], t['rad'], rmin, lod)
        if len(p) >= 2:
            out.append((p, r, t['trunk']))
    return out


def tube_tris(ts, lod):
    return sum(2 * sides_for(r[0], tr, lod) * (len(p) - 1) for p, r, tr in ts)


def pick_rmin(T, budget, lod):
    for rm in (.006, .008, .01, .012, .015, .018, .022, .027, .033, .04, .05, .06, .075, .09, .11, .14, .18, .25, .4):
        ts = tube_set(T, rm, lod)
        if tube_tris(ts, lod) <= budget:
            return ts
    return tube_set(T, 1.0, lod)


def sc_tree(sp, seed):
    rng = np.random.default_rng(seed)
    T = Tree()
    h = sp['h'] * rng.uniform(.93, 1.07)
    s = h / sp['h']
    ec = np.array([0, 0, sp['env_c'] * s]); er = np.array(sp['env_r']) * np.array([rng.uniform(.9, 1.1), rng.uniform(.9, 1.1), 1]) * s
    T.c, T.R = ec, er
    # trunk seed polyline (lean + sway)
    tt = sp['trunk_top'] * s
    lean = rng.normal(0, 1, 2); lean = lean / np.linalg.norm(lean) * sp.get('lean', .03)
    ph = rng.random() * 6.28
    seeds = []
    z = -.4
    while z <= tt:
        sw = sp.get('sway', .15) * math.sin(z / max(tt, 1) * 2.4 + ph)
        seeds.append((np.array([lean[0] * z + sw, lean[1] * z + sw * .6, z]), len(seeds) - 1))
        z += .5
    top = len(seeds) - 1
    # scaffold limbs (vase / umbrella / emergent crowns)
    for (cnt, ang, L, z0, z1) in sp.get('scaffold', []):
        a0 = rng.random() * 6.28
        for b in range(cnt):
            az = a0 + b * 6.28 / cnt + rng.normal(0, .25)
            zz = (z0 + (z1 - z0) * rng.random()) * s
            ia = min(range(len(seeds)), key=lambda i: abs(seeds[i][0][2] - zz))
            p = seeds[ia][0].copy(); prev = ia
            tilt = math.radians(ang + rng.normal(0, 7))
            d = np.array([math.cos(az) * math.sin(tilt), math.sin(az) * math.sin(tilt), math.cos(tilt)])
            n = max(2, int(L * s / .5))
            for i in range(n):
                d = nrm(d + rng.normal(0, .12, 3) + np.array([0, 0, sp.get('scaffold_rise', .05)]))
                p = p + d * L * s / n
                seeds.append((p.copy(), prev)); prev = len(seeds) - 1
    A = envelope(rng, sp.get('nattr', 800), ec, er, sp.get('lump', .3), sp.get('shell', .3), sp.get('flat', 1.0), sp.get('nlobes', 7))
    P, par, kids = grow_sc(rng, seeds, A, sp.get('step', .45) * s, sp.get('di', 3.0) * s, sp.get('dk', .85) * s,
                           (0, 0, sp.get('trop', .05)), sp.get('jitter', .2))
    P, rad, dtip = graph_to_tree(T, P, par, kids, sp, rng)
    # leaves
    leafk = sp.get('leaf_depth', 3)
    cand = np.nonzero((dtip <= leafk) & (P[:, 2] > sp.get('leaf_zmin', 1.5) * s))[0]
    if sp.get('kind') == 'bare':
        cand = np.nonzero((dtip <= 1) & (P[:, 2] > 2))[0]
    w = 1.0 / (1 + dtip[cand])
    w /= w.sum()
    nc = sp.get('n_cards', 600)
    chosen = rng.choice(cand, nc, p=w)
    for i in chosen:
        p = P[i] + rng.normal(0, .12, 3)
        tw = nrm(P[i] - P[par[i]]) if par[i] >= 0 else UP
        o = T.out(p)
        size = sp['card'] * rng.uniform(.8, 1.2) * s
        if sp.get('kind') == 'bare':
            d = nrm(tw * .7 + o * .3)
            n = nrm(np.cross(d, UP) + rng.normal(0, .3, 3))
            q = np.linalg.norm((p - T.c) / T.R)
            T.cards.append(dict(base=p, d=d, n=n, size=size, tex=sp['leaves'], fold=0, ao=.8 + .2 * min(1, q), nb=.3))
            continue
        d = nrm(tw * (1 - sp.get('card_out', .45)) + o * sp.get('card_out', .45) + UP * sp.get('card_up', .15))
        n0 = o - d * np.dot(o, d)
        if np.linalg.norm(n0) < 1e-3:
            n0 = perp(d)
        n0 = nrm(n0)
        if sp.get('card_face_up'):
            n0 = nrm(n0 * .4 + UP * sp['card_face_up'])
        b = np.cross(d, n0); roll = rng.normal(0, sp.get('roll', .55))
        n = nrm(n0 * math.cos(roll) + b * math.sin(roll))
        q = np.linalg.norm((p - T.c) / T.R)
        zf = min(1, max(0, (p[2] - (T.c[2] - T.R[2])) / (2 * T.R[2])))
        ao = (sp.get('ao', .42) + (1 - sp.get('ao', .42)) * min(1, q) ** 1.3) * (.8 + .2 * zf)
        T.cards.append(dict(base=p, d=d, n=n, size=size, tex=sp['leaves'], fold=sp.get('fold', .35), ao=ao))
    # willow: long strands hanging from the outer crown
    if sp.get('strands'):
        outer = [i for i in cand if np.linalg.norm((P[i] - T.c) / T.R) > .55 and P[i][2] > T.c[2] - T.R[2] * .4]
        for i in rng.choice(outer, sp['strands']):
            p = P[i]
            o = T.out(p); oh = nrm(np.array([o[0], o[1], 0]) + 1e-4)
            L = sp.get('strand_len', 3.2) * rng.uniform(.7, 1.25) * s
            L = min(L, p[2] - .8)
            if L < 1:
                continue
            d = nrm(-UP + oh * rng.uniform(.05, .25))
            T.cards.append(dict(base=p, d=d, n=nrm(oh + rng.normal(0, .3, 3)), size=L, aspect=.3, tex=sp['leaves'], fold=.0, flipv=True,
                                ao=.55 + .45 * min(1, np.linalg.norm((p - T.c) / T.R))))
    T.meta = dict(h=float(max(P[:, 2].max(), max((c['base'][2] + c['size'] * .5 for c in T.cards), default=0))),
                  w=float(max(er[0], er[1])), trunk=float(sp['trunk_r'] * (1 + sp.get('flare', 0) * .3)))
    return T


def conifer(sp, seed):
    """Whorled conifer: spruce (dense cone) or pine (curved trunk, limbs ending in flat needle pads)."""
    rng = np.random.default_rng(seed)
    T = Tree()
    H = sp['h'] * rng.uniform(.92, 1.08); s = H / sp['h']
    r0 = sp['trunk_r'] * s
    lean = rng.normal(0, 1, 2); lean = lean / np.linalg.norm(lean) * sp.get('lean', .02)
    bend = sp.get('bend', 0.0); ph = rng.random() * 6.28
    def axis(z):
        f = z / H
        b = bend * math.sin(f * math.pi * 1.3 + ph * .1) * f
        return np.array([lean[0] * z + b * math.cos(ph), lean[1] * z + b * math.sin(ph), z])
    def rtr(z):
        return r0 * max(.06, (1 - z / H)) ** sp.get('taper', 1.0) + .015
    zs = np.arange(-.4, H + .01, .6 if not bend else .45)
    T.tubes.append(dict(pts=np.array([axis(z) for z in zs]), rad=np.array([rtr(z) for z in zs]), trunk=True))
    snow = sp.get('snow', False)
    T.c = np.array([0, 0, H * .5]); T.R = np.array([sp.get('Lmax', 3) * s, sp.get('Lmax', 3) * s, H * .5])
    def cone_out(p):
        a = axis(p[2]); o = p - a; o[2] = 0
        return nrm(nrm(o + 1e-5) + np.array([0, 0, .55]))
    T.out = cone_out
    tex, tex_snow = sp['leaves'], sp.get('leaves_snow')
    if sp.get('kind') == 'spruce':
        z = sp['z0'] * s
        while z < H - .6:
            t = (z - sp['z0'] * s) / (H - sp['z0'] * s)
            nb = int(rng.integers(4, 6))
            a0 = rng.random() * 6.28
            for b in range(nb):
                az = a0 + b * 6.28 / nb + rng.normal(0, .3)
                L = (sp['Lmax'] * (1 - t) ** sp.get('shape', 1.0) + .35) * rng.uniform(.8, 1.15) * s
                pitch = sp['pitch_lo'] + (sp['pitch_hi'] - sp['pitch_lo']) * t + rng.normal(0, .08)
                hd = np.array([math.cos(az), math.sin(az), 0])
                base = axis(z)
                nseg = max(2, int(L / .5))
                pts = []; 
                for k in range(nseg + 1):
                    f = k / nseg
                    p = base + hd * L * f * math.cos(pitch) + UP * (L * f * math.sin(pitch) - sp.get('sag', .12) * L * f * f + sp.get('upturn', .1) * L * f ** 3)
                    pts.append(p)
                pts = np.array(pts)
                rb = max(.014, rtr(z) * .42 * (L / (sp['Lmax'] * s)) ** .6)
                rad = np.array([rb * (1 - .75 * k / nseg) for k in range(nseg + 1)])
                T.tubes.append(dict(pts=pts, rad=rad, trunk=False))
                # sprays along the branch: alternating side shoots + the tip
                m = max(1, int(L / sp.get('spray_gap', .62)))
                for k in range(m + 1):
                    f = .2 + .8 * k / m if m else 1
                    i = min(nseg - 1, int(f * nseg)); fk = f * nseg - i
                    p = pts[i] * (1 - fk) + pts[i + 1] * fk
                    bd = nrm(pts[i + 1] - pts[i])
                    side = np.cross(UP, bd); side = nrm(side)
                    for sgn in ((1, -1) if k < m else (0,)):
                        d = nrm(bd * (1 if sgn == 0 else .55) + side * sgn * .85 + UP * rng.normal(-.05, .12))
                        tilt = rng.normal(0, .55)
                        nup = nrm(UP - d * np.dot(UP, d))
                        bx = np.cross(d, nup)
                        n = nrm(nup * math.cos(tilt) + bx * math.sin(tilt))
                        size = sp['card'] * rng.uniform(.8, 1.15) * s * (.75 + .25 * (1 - t))
                        ao = (.5 + .5 * f ** .8) * (.75 + .25 * t)
                        tx = tex_snow if (snow and n[2] > .55) else tex
                        T.cards.append(dict(base=p - d * size * .1, d=d, n=n, size=size, tex=tx, fold=.2, ao=ao, nb=.6))
                    if snow and sgn != 0 and k % 2 == 0 and f > .25:
                        cs = (.45 + .5 * L / (sp['Lmax'] * s)) * rng.uniform(.85, 1.2)
                        T.cards.append(dict(base=p + UP * .1 - bd * cs * .5, d=bd, n=UP.copy(), size=cs, tex='snowclump', fold=0, ao=1.0, nb=.2))
            z += sp['spacing'] * rng.uniform(.8, 1.2) * s
        # leader
        top = axis(H)
        for k in range(3):
            d = nrm(UP * 3 + rng.normal(0, .3, 3))
            T.cards.append(dict(base=axis(H - .9), d=d, n=nrm(perp(d)), size=1.1 * s, tex=tex, fold=.3, ao=1))
    else:   # pine: limbs ending in flat pads of needle tufts
        nl = sp['limbs']
        zl = np.sort(rng.uniform(sp['crown_lo'], .93, nl)) * H
        a0 = rng.random() * 6.28
        pads = []
        for j, z in enumerate(zl):
            t = (z / H - sp['crown_lo']) / (1 - sp['crown_lo'])
            az = a0 + j * 2.4 + rng.normal(0, .3)
            hd = np.array([math.cos(az), math.sin(az), 0])
            L = (sp['Lmax'] * (1 - .55 * t) * rng.uniform(.75, 1.15)) * s
            pitch = sp['pitch'] + rng.normal(0, .12)
            p = axis(z); pts = [p.copy()]
            d = nrm(hd * math.cos(pitch) + UP * math.sin(pitch))
            n = max(3, int(L / .45))
            for k in range(n):
                d = nrm(d + rng.normal(0, .18, 3) + UP * sp.get('rise', .04) - UP * sp.get('droop', .0) * k / n)
                p = p + d * L / n; pts.append(p.copy())
            pts = np.array(pts)
            rb = max(.03, rtr(z) * .55 * (L / (sp['Lmax'] * s)) ** .5)
            T.tubes.append(dict(pts=pts, rad=np.array([rb * (1 - .7 * k / n) for k in range(n + 1)]), trunk=False))
            pads.append((pts[-1], sp['pad'] * rng.uniform(.8, 1.2) * s * (1.1 - .3 * t)))
            # a fork: a second, shorter pad part way along
            if L > 2.2 * s and rng.random() < sp.get('fork', .6):
                k = int(n * rng.uniform(.45, .7)); q = pts[k]
                fd = nrm(np.cross(UP, hd) * rng.choice([-1, 1]) + hd * .6 + UP * .35)
                fl = L * rng.uniform(.3, .45)
                fp = np.array([q + fd * fl * i / 3 for i in range(4)])
                T.tubes.append(dict(pts=fp, rad=np.array([rb * .5, rb * .4, rb * .3, rb * .2]), trunk=False))
                pads.append((fp[-1], sp['pad'] * .75 * s))
        pads.append((axis(H) - UP * .4, sp['pad'] * .8 * s))
        for c, pr in pads:
            nc = int(sp.get('pad_cards', 32) * (pr / sp['pad']) ** 1.5)
            for k in range(max(8, nc)):
                u = rng.normal(0, 1, 3); u[2] = abs(u[2]) * .5
                u = u / max(1, np.linalg.norm(u)) * rng.uniform(.2, 1)
                p = c + np.array([u[0] * pr, u[1] * pr, u[2] * pr * .55 - pr * .08])
                o = p - c; o[2] = 0; o = nrm(o + 1e-4)
                d = nrm(o + rng.normal(0, .35, 3) + UP * .15)
                nup = nrm(UP - d * np.dot(UP, d)); bx = np.cross(d, nup); tilt = rng.normal(0, .5)
                n = nrm(nup * math.cos(tilt) + bx * math.sin(tilt))
                ao = .55 + .45 * min(1, (p[2] - c[2] + pr * .3) / (pr * .7))
                tx = tex_snow if (snow and n[2] > .5) else tex
                T.cards.append(dict(base=p - d * .3, d=d, n=n, size=sp['card'] * rng.uniform(.8, 1.2) * s, tex=tx, fold=.25, ao=ao, nb=.55,
                                    out=nrm((p - c) / np.array([pr, pr, pr * .5]) + UP * .4)))
            if snow:
                for k in range(max(2, nc // 7)):
                    u = rng.normal(0, .45, 2)
                    p = c + np.array([u[0] * pr, u[1] * pr, pr * .3])
                    cs = pr * rng.uniform(.5, .8)
                    d = nrm(np.array([u[0], u[1], 0]) + 1e-3)
                    T.cards.append(dict(base=p - d * cs * .5, d=d, n=UP.copy(), size=cs, tex='snowclump', fold=0, ao=1.0, nb=.2))
    T.meta = dict(h=float(H), w=float(sp.get('Lmax', 3) * s), trunk=float(r0 * 1.1))
    return T


# =============================================================================================== species
OAKB = dict(bark='oak'); ASHB = dict(bark='ash')
SPECIES = {
    'oak': [
        ('TR_oak_a', 11, dict(h=13, trunk_top=4.6, trunk_r=.42, env_c=8.4, env_r=(6.6, 6.6, 5.0), lump=.38, shell=.38, flat=.75, nattr=900,
                              jitter=.24, trop=.02, flare=.55, gnarl=.07, bark='oak', leaves='oak', card=1.9, n_cards=780)),
        ('TR_oak_b', 12, dict(h=12, trunk_top=3.4, trunk_r=.45, env_c=7.4, env_r=(7.4, 7.0, 4.6), lump=.42, shell=.38, flat=.7, nattr=950,
                              jitter=.26, trop=.0, flare=.6, gnarl=.08, bark='oak', leaves='oak', card=1.9, n_cards=800, lean=.08)),
        ('TR_oak_gold', 13, dict(h=12.5, trunk_top=2.8, trunk_r=.62, env_c=7.6, env_r=(6.6, 6.6, 5.3), lump=.45, shell=.5, nattr=850,
                                 jitter=.32, trop=.02, flare=.8, gnarl=.12, bark='oak', leaves='oak_gold', card=1.75, n_cards=700, ao=.5,
                                 scaffold=[(4, 38, 2.6, 2.5, 2.8)])),
    ],
    'ash': [
        ('TR_ash_a', 21, dict(h=16, trunk_top=5.5, trunk_r=.40, env_c=10.6, env_r=(6.2, 6.2, 6.0), lump=.5, nlobes=8, shell=.32, nattr=950,
                              jitter=.22, trop=.07, flare=.45, gnarl=.04, bark='ash', leaves='ash', card=1.6, n_cards=740, lean=.05)),
        ('TR_ash_b', 22, dict(h=13, trunk_top=3.6, trunk_r=.40, env_c=8.3, env_r=(6.0, 6.0, 5.0), lump=.18, shell=.25, nattr=950,
                              jitter=.18, trop=.05, flare=.45, bark='ash', leaves='ash', card=1.5, n_cards=860)),
        ('TR_ash_young', 23, dict(h=10, trunk_top=5.0, trunk_r=.14, env_c=7.0, env_r=(2.9, 2.9, 3.2), lump=.35, shell=.2, nattr=500,
                                  step=.35, di=2.2, dk=.6, jitter=.2, trop=.08, flare=.3, bark='ash', leaves='ash', card=1.15, n_cards=430,
                                  tip_r=.009, budget=1500, sway=.25)),
    ],
    'maple': [
        ('TR_maple_a', 31, dict(h=12, trunk_top=3.4, trunk_r=.36, env_c=7.6, env_r=(5.2, 5.2, 4.8), lump=.3, shell=.3, nattr=850,
                                jitter=.2, trop=.05, flare=.5, bark='maple', leaves='maple', card=1.45, n_cards=760)),
        ('TR_maple_b', 32, dict(h=10, trunk_top=2.8, trunk_r=.32, env_c=6.4, env_r=(5.6, 5.6, 4.0), lump=.32, shell=.3, nattr=850,
                                jitter=.22, trop=.03, flare=.5, bark='maple', leaves='maple', card=1.45, n_cards=740)),
        ('TR_maple_autumn_a', 33, dict(h=12.5, trunk_top=3.2, trunk_r=.38, env_c=7.8, env_r=(5.6, 5.6, 5.0), lump=.4, shell=.3, nattr=900,
                                       jitter=.22, trop=.05, flare=.5, bark='maple', leaves='maple_autumn', card=1.45, n_cards=780)),
        ('TR_maple_autumn_b', 34, dict(h=10, trunk_top=2.8, trunk_r=.32, env_c=6.4, env_r=(5.4, 5.4, 4.0), lump=.35, shell=.3, nattr=850,
                                       jitter=.22, trop=.03, flare=.5, bark='maple', leaves='maple_autumn', card=1.45, n_cards=740)),
    ],
    'birch': [
        ('TR_birch_a', 41, dict(h=14, trunk_top=11.5, trunk_r=.2, env_c=9.2, env_r=(2.8, 2.8, 5.0), lump=.3, shell=.2, nattr=650,
                                step=.38, di=2.2, dk=.65, jitter=.2, trop=.0, tip_r=.009, bark='birch', leaves='birch', card=1.05, n_cards=560,
                                budget=1800, sway=.25)),
        ('TR_birch_b', 42, dict(h=12, trunk_top=9.0, trunk_r=.18, env_c=8.0, env_r=(3.3, 3.3, 4.2), lump=.35, shell=.2, nattr=650,
                                step=.38, di=2.2, dk=.65, jitter=.22, trop=-.02, tip_r=.009, bark='birch', leaves='birch', card=1.05, n_cards=560,
                                budget=1800, lean=.06, sway=.3)),
        ('TR_birch_c', 43, dict(h=15.5, trunk_top=13, trunk_r=.22, env_c=10.5, env_r=(2.5, 2.5, 5.4), lump=.3, shell=.2, nattr=650,
                                step=.38, di=2.2, dk=.65, jitter=.2, trop=.02, tip_r=.009, bark='birch', leaves='birch', card=1.05, n_cards=560,
                                budget=1800, sway=.35)),
    ],
    'cherry': [
        ('TR_cherry_a', 51, dict(h=7.5, trunk_top=1.8, trunk_r=.32, env_c=5.0, env_r=(6.4, 6.4, 2.9), lump=.3, shell=.35, flat=.45, nattr=850,
                                 jitter=.22, trop=-.02, flare=.5, gnarl=.06, bark='cherry', leaves='cherry', card=1.5, n_cards=800,
                                 scaffold=[(4, 58, 3.0, 1.5, 1.8)], ao=.5)),
        ('TR_cherry_b', 52, dict(h=8.5, trunk_top=2.2, trunk_r=.36, env_c=5.8, env_r=(7.0, 7.0, 3.2), lump=.35, shell=.35, flat=.45, nattr=900,
                                 jitter=.22, trop=-.03, flare=.5, gnarl=.07, bark='cherry', leaves='cherry', card=1.5, n_cards=820,
                                 scaffold=[(3, 52, 3.4, 1.9, 2.2)], ao=.5, lean=.06)),
    ],
    'umbrella': [
        ('TR_umbrella_a', 61, dict(h=11, trunk_top=5.2, trunk_r=.4, env_c=9.4, env_r=(8.8, 8.8, 2.1), lump=.25, shell=.3, flat=.55, nattr=900,
                                   jitter=.16, trop=.03, flare=.4, bark='umbrella', leaves='umbrella', card=1.65, n_cards=780,
                                   scaffold=[(5, 62, 4.4, 4.6, 5.2)], scaffold_rise=.02, card_face_up=.9, card_up=.35, ao=.5)),
        ('TR_umbrella_b', 62, dict(h=9, trunk_top=4.2, trunk_r=.34, env_c=7.7, env_r=(7.0, 7.0, 2.0), lump=.3, shell=.3, flat=.55, nattr=800,
                                   jitter=.18, trop=.03, flare=.4, bark='umbrella', leaves='umbrella', card=1.6, n_cards=680,
                                   scaffold=[(4, 58, 3.6, 3.7, 4.2)], scaffold_rise=.02, card_face_up=.9, card_up=.35, ao=.5, lean=.06)),
    ],
    'rainforest': [
        ('TR_emergent_a', 71, dict(h=30, trunk_top=23, trunk_r=.6, env_c=27.2, env_r=(7.4, 7.4, 3.4), lump=.45, shell=.3, flat=.5, nattr=850,
                                   step=.6, di=3.6, dk=1.0, jitter=.18, trop=.05, flare=.4, buttress=.9, bark='rainforest', leaves='rainforest',
                                   card=1.9, n_cards=640, scaffold=[(4, 52, 4.0, 22, 23.5)], leaf_zmin=20)),
        ('TR_emergent_b', 72, dict(h=26, trunk_top=19, trunk_r=.5, env_c=23.2, env_r=(6.4, 6.4, 3.6), lump=.55, nlobes=5, shell=.3, flat=.55, nattr=800,
                                   step=.55, di=3.4, dk=.95, jitter=.2, trop=.05, flare=.4, buttress=.7, bark='rainforest', leaves='rainforest',
                                   card=1.8, n_cards=600, scaffold=[(3, 48, 3.5, 18, 19.5)], leaf_zmin=16, lean=.04)),
        ('TR_understory_a', 73, dict(h=9, trunk_top=3.0, trunk_r=.2, env_c=6.0, env_r=(3.7, 3.7, 3.2), lump=.3, shell=.25, nattr=600,
                                     step=.38, di=2.4, dk=.65, jitter=.2, trop=.04, flare=.3, bark='understory', leaves='rainforest', card=1.45, n_cards=520,
                                     budget=1600)),
        ('TR_understory_b', 74, dict(h=7, trunk_top=2.2, trunk_r=.17, env_c=4.6, env_r=(3.3, 3.3, 2.6), lump=.35, shell=.25, nattr=550,
                                     step=.35, di=2.2, dk=.6, jitter=.22, trop=.03, flare=.3, bark='understory', leaves='rainforest', card=1.4, n_cards=470,
                                     budget=1500, lean=.08)),
    ],
    'willow': [
        ('TR_willow_a', 81, dict(h=11, trunk_top=3.0, trunk_r=.48, env_c=7.4, env_r=(5.6, 5.6, 4.2), lump=.3, shell=.35, nattr=800,
                                 jitter=.22, trop=.08, flare=.6, gnarl=.08, bark='willow', leaves='willow', card=1.6, n_cards=330, card_out=.2,
                                 card_up=-.6, fold=0, strands=300, strand_len=3.6, scaffold=[(4, 34, 2.8, 2.6, 3.0)], lean=.07)),
        ('TR_willow_b', 82, dict(h=9.5, trunk_top=2.4, trunk_r=.42, env_c=6.4, env_r=(5.0, 5.0, 3.8), lump=.35, shell=.35, nattr=750,
                                 jitter=.24, trop=.08, flare=.6, gnarl=.08, bark='willow', leaves='willow', card=1.5, n_cards=300, card_out=.2,
                                 card_up=-.6, fold=0, strands=280, strand_len=3.3, scaffold=[(3, 30, 2.4, 2.0, 2.4)], lean=.1)),
    ],
    'bare_snow': [
        ('TR_bare_snow_a', 91, dict(kind='bare', h=13, trunk_top=4.5, trunk_r=.4, env_c=8.6, env_r=(6.0, 6.0, 5.0), lump=.35, shell=.35, nattr=900,
                                    jitter=.24, trop=.06, flare=.5, gnarl=.06, bark='winter', leaves='twig_snow', card=1.4, n_cards=330, budget=4300,
                                    tip_r=.008, snow=True)),
        ('TR_bare_snow_b', 92, dict(kind='bare', h=11, trunk_top=6.0, trunk_r=.24, env_c=7.6, env_r=(3.6, 3.6, 4.4), lump=.3, shell=.25, nattr=700,
                                    step=.4, di=2.4, dk=.7, jitter=.22, trop=.1, flare=.4, bark='winter', leaves='twig_snow', card=1.2, n_cards=280,
                                    budget=3800, tip_r=.007, snow=True, sway=.3)),
    ],
    'spruce': [
        ('TR_spruce_a', 101, dict(kind='spruce', h=17, trunk_r=.34, z0=1.0, spacing=.75, Lmax=3.7, shape=1.0, pitch_lo=-.32, pitch_hi=.3,
                                  bark='spruce', leaves='spruce', card=1.2)),
        ('TR_spruce_b', 102, dict(kind='spruce', h=13, trunk_r=.28, z0=.7, spacing=.7, Lmax=3.1, shape=.95, pitch_lo=-.38, pitch_hi=.25,
                                  bark='spruce', leaves='spruce', card=1.1)),
        ('TR_spruce_c', 103, dict(kind='spruce', h=21, trunk_r=.38, z0=1.6, spacing=.85, Lmax=3.3, shape=1.2, pitch_lo=-.28, pitch_hi=.32,
                                  bark='spruce', leaves='spruce', card=1.2, lean=.03)),
    ],
    'spruce_snow': [
        ('TR_spruce_snow_a', 111, dict(kind='spruce', h=16, trunk_r=.33, z0=.9, spacing=.75, Lmax=3.6, shape=1.0, pitch_lo=-.4, pitch_hi=.25,
                                       bark='spruce', leaves='spruce', leaves_snow='spruce_snow', card=1.2, snow=True, sag=.2)),
        ('TR_spruce_snow_b', 112, dict(kind='spruce', h=12, trunk_r=.27, z0=.6, spacing=.7, Lmax=3.0, shape=.95, pitch_lo=-.45, pitch_hi=.2,
                                       bark='spruce', leaves='spruce', leaves_snow='spruce_snow', card=1.1, snow=True, sag=.22)),
        ('TR_pine_snow', 113, dict(kind='pine', h=15, trunk_r=.32, lean=.03, crown_lo=.58, limbs=11, Lmax=3.2, pitch=.3, pad=1.5, pad_cards=34,
                                   bark='pine', leaves='pine', leaves_snow='spruce_snow', card=1.15, snow=True, taper=.8)),
    ],
    'pine': [
        ('TR_pine_a', 121, dict(kind='pine', h=9.5, trunk_r=.36, lean=.18, bend=1.4, crown_lo=.3, limbs=10, Lmax=5.0, pitch=.12, droop=.25,
                                rise=.06, pad=1.9, pad_cards=40, bark='pine', leaves='pine', card=1.2, taper=.8)),
        ('TR_pine_b', 122, dict(kind='pine', h=17, trunk_r=.32, lean=.03, crown_lo=.6, limbs=12, Lmax=3.4, pitch=.35, pad=1.5, pad_cards=34,
                                bark='pine', leaves='pine', card=1.15, taper=.8)),
    ],
    'bush': [
        ('TR_bush_a', 131, dict(kind='bush', h=1.9, trunk_top=-.1, trunk_r=.06, env_c=1.0, env_r=(1.4, 1.4, 1.0), lump=.25, shell=.3, nattr=320,
                                step=.22, di=1.2, dk=.32, jitter=.2, trop=.05, tip_r=.006, bark='oak', leaves='bush', card=.72, n_cards=240,
                                budget=420, leaf_zmin=.2, stems=6, ao=.35)),
        ('TR_bush_b', 132, dict(kind='bush', h=2.6, trunk_top=-.1, trunk_r=.08, env_c=1.35, env_r=(1.9, 1.7, 1.3), lump=.35, shell=.3, nattr=380,
                                step=.25, di=1.4, dk=.36, jitter=.22, trop=.05, tip_r=.007, bark='oak', leaves='bush', card=.85, n_cards=280,
                                budget=480, leaf_zmin=.2, stems=7, ao=.35)),
        ('TR_bush_flower', 133, dict(kind='bush', h=1.8, trunk_top=-.1, trunk_r=.06, env_c=.95, env_r=(1.3, 1.3, .95), lump=.3, shell=.3, nattr=320,
                                     step=.22, di=1.2, dk=.32, jitter=.2, trop=.05, tip_r=.006, bark='oak', leaves='bush_flower', card=.72, n_cards=250,
                                     budget=420, leaf_zmin=.2, stems=6, ao=.38)),
    ],
}
BARK = {   # material -> (texture set, tint)
    'oak': ('oak', '#ffffff'), 'ash': ('oak', '#c2bcb2'), 'maple': ('oak', '#b3a89c'), 'birch': ('birch', '#ffffff'),
    'cherry': ('cherry', '#ffffff'), 'umbrella': ('cherry', '#d6b49a'), 'rainforest': ('birch', '#c9c0b0'), 'understory': ('oak', '#a8a69a'),
    'willow': ('oak', '#aaa08f'), 'winter': ('oak', '#8f877e'), 'pine': ('pine', '#e6a273'), 'spruce': ('pine', '#a29890'),
}


def bush_seeds(sp, rng):
    """Bushes: several stems from the root fanning out."""
    seeds = [(np.array([0, 0, -.1]), -1)]
    for k in range(sp.get('stems', 6)):
        a = k * 6.28 / sp['stems'] + rng.normal(0, .3)
        d = nrm(np.array([math.cos(a) * .6, math.sin(a) * .6, 1]))
        p = seeds[0][0].copy(); prev = 0
        for i in range(3):
            p = p + d * .18; seeds.append((p.copy(), prev)); prev = len(seeds) - 1
    return seeds


def grow(name, seed, sp):
    kind = sp.get('kind', 'sc')
    if kind in ('spruce', 'pine'):
        return conifer(sp, seed)
    if kind == 'bush':
        rng = np.random.default_rng(seed)
        T = Tree()
        T.c = np.array([0, 0, sp['env_c']]); T.R = np.array(sp['env_r'])
        A = envelope(rng, sp['nattr'], T.c, T.R, sp['lump'], sp['shell'], 1.0)
        P, par, kids = grow_sc(rng, bush_seeds(sp, rng), A, sp['step'], sp['di'], sp['dk'], (0, 0, sp['trop']), sp['jitter'])
        P, rad, dtip = graph_to_tree(T, P, par, kids, sp, rng)
        cand = np.nonzero((dtip <= 3) & (P[:, 2] > .15))[0]
        for i in rng.choice(cand, sp['n_cards']):
            p = P[i] + rng.normal(0, .06, 3)
            o = T.out(p); tw = nrm(P[i] - P[par[i]])
            d = nrm(tw * .5 + o * .5 + UP * .1)
            n0 = nrm(o - d * np.dot(o, d) + 1e-5)
            b = np.cross(d, n0); roll = rng.normal(0, .6)
            q = np.linalg.norm((p - T.c) / T.R)
            T.cards.append(dict(base=p, d=d, n=nrm(n0 * math.cos(roll) + b * math.sin(roll)), size=sp['card'] * rng.uniform(.8, 1.2),
                                tex=sp['leaves'], fold=.35, ao=sp['ao'] + (1 - sp['ao']) * min(1, q) ** 1.2))
        T.meta = dict(h=float(sp['h']), w=float(max(sp['env_r'][:2])), trunk=.1)
        return T
    return sc_tree(sp, seed)


# =============================================================================================== assembling meshes
def build_mesh(T, sp, mats, lod, name):
    mb = MB()
    bark = mats['bark_' + sp['bark']]
    snow = mats['snow'] if sp.get('snow') else None
    if 'nodes' in T.__dict__:
        ts = pick_rmin(T, sp.get('budget', 2300) if not lod else sp.get('mid_budget', 220 if sp.get('kind') != 'bare' else 600), lod)
    else:
        ts = []
        for t in T.tubes:
            if lod and not t['trunk'] and t['rad'][0] < .05:
                continue
            p, r = t['pts'], t['rad']
            if lod and len(p) > 3:
                idx = sorted(set(list(range(0, len(p), 2)) + [len(p) - 1]))
                p, r = p[idx], r[idx]
            ts.append((p, r, t['trunk']))
    for i, (p, r, tr) in enumerate(ts):
        tube(mb, p, r, bark, snow, trunk=tr, lod=lod, flare=sp.get('flare', .3) if tr else 0, buttress=sp.get('buttress', 0) if tr else 0,
             gnarl=sp.get('gnarl', 0) * (1 if tr else .5), seed=i, tile=1.6 if tr else 1.0)
    btris = mb.tris()
    rng = random.Random(len(name))
    cards = T.cards
    keep_f = 1.0
    if lod:
        keep_f = .3 if len(cards) > 300 else .4
    for c in cards:
        if lod and c['tex'] != 'snowclump' and rng.random() > keep_f:
            continue
        if lod and c['tex'] == 'snowclump' and rng.random() > .5:
            continue
        tx = c['tex']; m = mats['leaves_' + tx]
        cols, rows = mats['_grid'][tx]
        cell = cell_uv(rng.randrange(cols * rows), cols, rows)
        scale = 1.0
        if lod:
            scale = (1 / keep_f) ** .5 * .92 if tx != 'snowclump' else 1.3
        out_fn = (lambda p, o=c['out']: o) if 'out' in c else T.out
        aspect = c.get('aspect', 1.0) * (1.6 if lod and c.get('aspect', 1) < 1 else 1)
        size = c['size'] * (scale if c.get('aspect', 1) >= 1 else 1.0)
        card(mb, c['base'], c['d'], c['n'], size, cell, m, out_fn, aspect=aspect, fold=0 if lod else c.get('fold', .3),
             flipv=c.get('flipv', False), ao=c.get('ao', 1.0), nbend=c.get('nb', .75))
    o = mb.build(name)
    return o, btris, mb.tris() - btris, mb


def make_materials(barks, leaves):
    mats = {'snow': snow_mat(), '_grid': {}}
    for k, (tex, tint) in BARK.items():
        mats['bark_' + k] = bark_mat('bark_' + k, barks[tex], tint)
    for k, (path, cols, rows) in leaves.items():
        mats['leaves_' + k] = leaf_mat('leaves_' + k, path, .55 if k in ('rainforest',) else .75 if 'snow' not in k else .6)
        mats['_grid'][k] = (cols, rows)
    return mats


# =============================================================================================== impostors
def emit_material(m):
    """Unlit albedo (texture x tint x vertex AO) with alpha, for rendering impostors."""
    e = bpy.data.materials.new(m.name + '__emit')
    nt = e.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    src = m.node_tree
    b = src.nodes.get('Principled BSDF')
    imgs = [n for n in src.nodes if n.type == 'TEX_IMAGE' and n.image and n.image.colorspace_settings.name != 'Non-Color']
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'
    em = nt.nodes.new('ShaderNodeEmission')
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1
    nt.links.new(vc.outputs['Color'], mul.inputs[7])
    tint = (1, 1, 1, 1)
    mixes = [n for n in src.nodes if n.type == 'MIX']
    if mixes:
        tint = tuple(mixes[0].inputs[7].default_value)
    if imgs:
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = imgs[0].image
        t2 = nt.nodes.new('ShaderNodeMix'); t2.data_type = 'RGBA'; t2.blend_type = 'MULTIPLY'; t2.inputs['Factor'].default_value = 1
        t2.inputs[7].default_value = tint
        nt.links.new(tn.outputs['Color'], t2.inputs[6]); nt.links.new(t2.outputs[2], mul.inputs[6])
    else:
        mul.inputs[6].default_value = tuple(b.inputs['Base Color'].default_value)
    nt.links.new(mul.outputs[2], em.inputs['Color'])
    if imgs and m.name.startswith('leaves_'):
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tn.outputs['Alpha'], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs['Surface'])
    else:
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    return e


def render_impostors(heroes):
    """heroes: list of (name, obj, bounds). Renders each from the front into a cell of one atlas."""
    from PIL import Image
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 24 if not FAST else 8; sc.cycles.device = 'CPU'
    try:
        sc.cycles.use_denoising = False
    except Exception:
        pass
    sc.cycles.transparent_max_bounces = 160; sc.cycles.max_bounces = 0
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
    sc.render.resolution_x = sc.render.resolution_y = IMP; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    w = bpy.data.worlds.new('imp'); sc.world = w
    cam = bpy.data.objects.new('impcam', bpy.data.cameras.new('impcam')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = 'ORTHO'; cam.rotation_euler = (math.pi / 2, 0, 0)
    cam.data.clip_start = .1; cam.data.clip_end = 500
    emits = {}
    all_objs = [o for o in sc.objects if o.type == 'MESH']
    cols = 8; rows = (len(heroes) + cols - 1) // cols
    atlas = np.zeros((rows * IMP, cols * IMP, 4), np.float32)
    cells = {}
    for i, (name, o, bb) in enumerate(heroes):
        for q in all_objs:
            q.hide_render = q is not o
        saved = [s.material for s in o.material_slots]
        for s in o.material_slots:
            if s.material.name not in emits:
                emits[s.material.name] = emit_material(s.material)
            s.material = emits[s.material.name]
        (x0, x1, y0, y1, z0, z1) = bb
        S = max(x1 - x0, y1 - y0, z1 - z0) * 1.03
        cx = o.matrix_world.translation.x + (x0 + x1) / 2; zc = (z0 + z1) / 2
        cam.location = (cx, -200, zc); cam.data.ortho_scale = S
        p = os.path.join(TMP, 'imp_%d.png' % i)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        for s, m in zip(o.material_slots, saved):
            s.material = m
        img = np.asarray(Image.open(p).convert('RGBA'), np.float32) / 255
        r, c = i // cols, i % cols
        atlas[r * IMP:(r + 1) * IMP, c * IMP:(c + 1) * IMP] = img
        cells[name] = (i, (x0 + x1) / 2, zc, S)
    for q in all_objs:
        q.hide_render = False
    cv = Canvas(cols * IMP, rows * IMP); cv.c = atlas[..., :3].copy(); cv.a = atlas[..., 3].copy()
    rgb, a = cv.finish()
    path = save('leaves_impostor', rgb, a)
    return path, cells, cols, rows


def lod_mesh(name, cell, cols, rows, mat):
    i, cx, zc, S = cell
    mb = MB(); mi = mb.mat(mat)
    u0, v0, u1, v1 = cell_uv(i, cols, rows, .002)
    for ax in (np.array([1., 0, 0]), np.array([0, 1., 0])):
        nface = np.cross(UP, ax)
        c0 = ax * cx if ax[0] else np.zeros(3)
        vs = []
        for (s, t, u, v) in ((-1, -1, u0, v0), (1, -1, u1, v0), (1, 1, u1, v1), (-1, 1, u0, v1)):
            p = c0 + ax * s * S / 2 + UP * (zc + t * S / 2)
            nn = nrm(ax * s * .55 + UP * .85 + nface * .1)
            vs.append(mb.vert(p, nn, (u, v), 1.0))
        mb.face(tuple(vs), mi)
    return mb.build(name), mb.tris()


# =============================================================================================== rocks
def rock(name, seed, snow, mats, scale):
    import bmesh
    from mathutils import noise
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    off = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), rnd.uniform(0, 50)))
    for v in bm.verts:
        p = v.co.copy()
        d = 1 + .35 * noise.noise(p * .9 + off) + .12 * noise.noise(p * 2.6 + off) + .05 * noise.noise(p * 6 + off)
        q = p * d
        q.z = q.z if q.z > -.15 else -.15 + (q.z + .15) * .25
        # flat facets: quantise along a few planes
        v.co = Vector((q.x * scale[0], q.y * scale[1], q.z * scale[2] + .2 * scale[2]))
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-4)
    me = bpy.data.meshes.new(name + '_mesh'); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name + '_mesh', me); bpy.context.scene.collection.objects.link(o)
    me.materials.append(mats['rock'])
    if snow:
        me.materials.append(mats['snow'])
        for p in me.polygons:
            if p.normal.z > .5:
                p.material_index = 1
        for p in me.polygons:
            if p.material_index == 1:
                for vi in p.vertices:
                    me.vertices[vi].co.z += .04
    bl.decimate(o, .55)
    bl.uv_box(o, 2.0)
    bl.autosmooth(o, 50)
    return o


# =============================================================================================== main
def main():
    t0 = time.time()
    bl.reset()
    full = not ONLY
    if full:
        snow_textures()
    barks = bark_textures()
    todo = [(sk, v) for sk, vs in SPECIES.items() for v in vs if full or any(a in sk or a in v[0] for a in ONLY)]
    need = set()
    for sk, (name, seed, sp) in todo:
        need.add(sp['leaves'])
        if sp.get('leaves_snow'):
            need.add(sp['leaves_snow'])
        if sp.get('snow') and sp.get('kind') in ('spruce', 'pine'):
            need.add('snowclump')
    leaves = leaf_textures(need)
    print('[trees] textures %.0fs' % (time.time() - t0))
    mats = make_materials(barks, leaves)
    mats['rock'] = bl.mat('rock', '#a8a29a', 0, .9, image='rock_c.jpg', normal='rock_n.jpg')
    heroes = []; report = []; roots = {}
    for i, (sk, (name, seed, sp)) in enumerate(todo):
        T = grow(name, seed, sp)
        X = 60.0 * i
        r = bl.empty(name, (X, 0, 0))
        for k, v in T.meta.items():
            r[k] = round(v, 3)
        r['species'] = sk
        o, bt, lt, mb = build_mesh(T, sp, mats, 0, name + '_mesh'); o.parent = r
        V = np.array(mb.V)
        bb = (V[:, 0].min(), V[:, 0].max(), V[:, 1].min(), V[:, 1].max(), max(-.2, V[:, 2].min()), V[:, 2].max())
        rm = bl.empty(name + '_mid', (X, 60, 0)); rm['lod'] = 1
        om, bt2, lt2, _ = build_mesh(T, sp, mats, 1, name + '_mid_mesh'); om.parent = rm
        heroes.append((name, o, bb)); roots[name] = (r, rm, sk)
        report.append((name, bt + lt, bt, lt, bt2 + lt2))
        print('[tree] %-20s hero %5d tris (bark %4d, leaves %4d)  mid %4d  h %.1f w %.1f' % (name, bt + lt, bt, lt, bt2 + lt2, T.meta['h'], T.meta['w']))
    bpy.context.view_layer.update()
    path, cells, cols, rows = render_impostors(heroes)
    imp = leaf_mat('leaves_impostor', path, .85)
    for name, o, bb in heroes:
        r, rm, sk = roots[name]
        rl = bl.empty(name + '_lod', (r.location.x, 120, 0)); rl['lod'] = 2
        ol, t = lod_mesh(name + '_lod_mesh', cells[name], cols, rows, imp); ol.parent = rl
    print('[trees] impostors %.0fs' % (time.time() - t0))
    if full or 'rock' in ONLY:
        for j, (nm, sd, sn, scl) in enumerate([('TR_rock_a', 1, False, (2.2, 1.6, 1.2)), ('TR_rock_b', 2, False, (1.3, 1.1, 1.0)), ('TR_rock_c', 3, False, (3.4, 2.4, 1.8)),
                                               ('TR_rock_snow_a', 4, True, (2.2, 1.7, 1.3)), ('TR_rock_snow_b', 5, True, (1.4, 1.2, 1.0)), ('TR_rock_snow_c', 6, True, (3.6, 2.6, 2.0))]):
            r = bl.empty(nm, (60.0 * j, -60, 0)); r['species'] = 'rock'; r['h'] = scl[2] * 1.2; r['w'] = scl[0]; r['trunk'] = 0
            o = rock(nm, sd, sn, mats, scl); o.parent = r
            print('[tree] %-20s %d tris' % (nm, sum(len(p.vertices) - 2 for p in o.data.polygons)))
    out = 'trees.glb' if full else os.environ.get('TREE_OUT', '/tmp/trees_partial.glb')
    kw = dict(export_image_format='WEBP', export_image_quality=88, export_vertex_color='ACTIVE')
    if full:
        bl.export(out, **kw)
    else:
        bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True, export_yup=True, export_extras=True,
                                  export_animations=False, export_lights=False, export_cameras=False, **kw)
        print('[export]', out)
    if PREVIEW:
        os.makedirs(PREVIEW, exist_ok=True)
        groups = {}
        for name, o, bb in heroes:
            groups.setdefault(roots[name][2], []).append((name, o, bb))
        for sk, items in groups.items():
            x = 0; sel = []
            for name, o, bb in items:
                r = roots[name][0]
                r['_x'] = r.location.x
                r.location.x = x - (bb[0] + bb[1]) / 2; x += (bb[1] - bb[0]) + 1.5
                sel += [r, o]
            bpy.context.view_layer.update()
            bpy.ops.object.select_all(action='DESELECT')
            for q in sel:
                q.select_set(True)
            bpy.ops.export_scene.gltf(filepath=os.path.join(PREVIEW, sk + '.glb'), export_format='GLB', use_selection=True, export_extras=True,
                                      export_vertex_color='ACTIVE', export_image_format='WEBP')
            for name, o, bb in items:
                r = roots[name][0]; r.location.x = r['_x']
        print('[preview] species GLBs in', PREVIEW)
    print('[trees] done in %.0fs' % (time.time() - t0))
    for row in report:
        print('[tris] %s hero=%d (bark %d leaves %d) mid=%d' % row)


main()
