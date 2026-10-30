"""ZAW world texture set v95 — authored procedurally in the same language as the guns/armour:
bone-white ceramic, gunmetal, slate blue, brass inlay, crisp bevels with worn bright edges,
cavity grime, fine stipple. Every map tiles. Writes <key>_c/_n/_r.jpg into site/tex."""
import numpy as np, os, sys
from PIL import Image
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter

OUT = sys.argv[1] if len(sys.argv) > 1 else 'site/tex'
os.makedirs(OUT, exist_ok=True)
ONLY = set(sys.argv[2:])

# ---------------- palette (sRGB 0..1) — shared with armour/guns ----------------
def hx(h): h = h.lstrip('#'); return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)], float) / 255
BONE, IVORY, SAND = hx('e7e0cf'), hx('d9d1bf'), hx('c9b58f')
WARMGREY, STONE, SLATE = hx('a8a196'), hx('8e8a83'), hx('5f6872')
GUN, GUNDK, NAVY = hx('3a3e45'), hx('25282d'), hx('1f2833')
BRASS, BRASSDK = hx('c9a24c'), hx('8a6a2c')
TERRA, UMBER, OLIVE = hx('92594a'), hx('5c4537'), hx('5f6b3a')
PATINA = hx('5f8a80')

def rng(s): return np.random.default_rng(s)

def gnoise(S, sigma, seed):
    r = rng(seed).standard_normal((S, S))
    f = np.fft.fftfreq(S)
    fx, fy = np.meshgrid(f, f)
    sy, sx = (sigma if isinstance(sigma, tuple) else (sigma, sigma))
    k = np.exp(-2 * np.pi ** 2 * ((sx * fx) ** 2 + (sy * fy) ** 2))
    n = np.real(np.fft.ifft2(np.fft.fft2(r) * k))
    return n / (n.std() + 1e-9)

def fbm(S, base, octs, seed, g=.5, warp=0):
    n = np.zeros((S, S)); a = 1; t = 0
    for i in range(octs):
        n += a * gnoise(S, max(.6, base / 2 ** i), seed + i * 17); t += a * a; a *= g
    return n / np.sqrt(t)

def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

def blur(x, s): return gaussian_filter(x, s, mode='wrap')

def lerp(a, b, t):
    t = np.asarray(t)
    if t.ndim == 2: t = t[..., None]
    return a + (b - a) * t

def grid(S):
    y, x = np.mgrid[0:S, 0:S].astype(float); return x, y

def vor(S, n, seed, jit=1.0):
    r = rng(seed); P = r.random((n, 2)) * S
    T = np.concatenate([P + np.array([dx, dy]) * S for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    tree = cKDTree(T); x, y = grid(S)
    d, i = tree.query(np.stack([x.ravel(), y.ravel()], 1), k=2, workers=-1)
    return d[:, 0].reshape(S, S), d[:, 1].reshape(S, S), (i[:, 0] % n).reshape(S, S)

def bricks(S, rows, cols, mortar, seed, offset=.5, vjit=0):
    """per pixel: brick id, distance (px) to brick edge (negative in mortar), local u,v"""
    x, y = grid(S); rh = S / rows; cw = S / cols
    row = np.floor(y / rh); off = (row % 2) * offset * cw
    xs = (x + off) % S; col = np.floor(xs / cw)
    lu = xs - col * cw; lv = y - row * rh
    d = np.minimum(np.minimum(lu, cw - lu), np.minimum(lv, rh - lv)) - mortar / 2
    bid = (row * cols + col).astype(int)
    return bid, d, lu / cw, lv / rh

def per_id(bid, seed, n=None):
    r = rng(seed); m = bid.max() + 1; v = r.random(m); return v[bid]

def normal_map(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * strength
    n = np.stack([-dx, -dy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * .5 + .5

def cavity(h, s=3):
    return np.clip((blur(h, s) - h) * 4, 0, 1)

MEANS = {}
def save(key, c, h=None, ns=6.0, r=None, size=None):
    if ONLY and key not in ONLY: return
    c = np.clip(c, 0, 1)
    def w(a, name):
        im = Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8))
        if size: im = im.resize((size, size), Image.LANCZOS)
        im.save(f'{OUT}/{key}_{name}.jpg', quality=90)
    w(c, 'c'); MEANS[key] = [round(float(v), 3) for v in c.reshape(-1, 3).mean(0)]
    if h is not None: w(normal_map(h, ns), 'n')
    if r is not None: w(np.repeat(np.clip(r, 0, 1)[..., None], 3, -1), 'r')
    print('saved', key, MEANS[key], flush=True)

def stipple(S, seed, amt=.035):
    return gnoise(S, .7, seed) * amt

def edge_wear(d, bev, S, seed, thr=.35):
    """bright chipped edges like the gun finishes: just inside the bevel, broken up by noise"""
    band = ss(bev * 1.6, bev * .3, d) * (d > 0)
    return band * ss(thr, thr + .25, fbm(S, 6, 4, seed) * .5 + .5)

def want(k): return not ONLY or k in ONLY

S = 1024

# =============================== CITY ===============================
if want('asph'):
    n1 = fbm(S, 40, 5, 1); d1, _, vid = vor(S, 2600, 2)
    agg = ss(5.5, 2.5, d1) * (per_id(vid, 3) > .55)
    c = lerp(GUNDK * 1.05, GUN, .35 + .25 * n1)
    c = lerp(c, STONE * .9, agg * .55)
    patch = ss(.6, .9, fbm(S, 110, 3, 4))
    c = lerp(c, GUNDK * .85, patch * .5)
    c += stipple(S, 5, .03)[..., None]
    h = agg * .5 + n1 * .08 - patch * .1
    save('asph', c, h, 3, .86 + .08 * n1 - .1 * agg)

if want('swalk'):
    bid, d, u, v = bricks(S, 4, 4, 10, 10, offset=0)
    tone = per_id(bid, 11); n1 = fbm(S, 30, 5, 12)
    base = lerp(IVORY * .93, WARMGREY, .25 + .2 * tone[..., None] + .08 * n1[..., None])
    bev = 10; hb = ss(-2, bev, d)
    c = lerp(GUN * 1.1, base, hb)
    # brass caps at slab corners
    x, y = grid(S); cs = S / 4
    cx = (x + cs / 2) % cs - cs / 2; cy = (y + cs / 2) % cs - cs / 2
    cap = (np.maximum(abs(cx), abs(cy)) < 11).astype(float)
    c = lerp(c, BRASS, cap * .95)
    c = lerp(c, BONE, edge_wear(d, bev, S, 13) * .5)
    cav = cavity(hb + n1 * .03, 4); c *= (1 - .25 * cav)[..., None]
    c += stipple(S, 14)[..., None]
    h = hb + n1 * .04 + cap * .3
    save('swalk', c, h, 5, .78 - .25 * cap + .06 * n1)

if want('curb'):
    x, y = grid(S); v = (y % (S / 3)) / (S / 3); n1 = fbm(S, 25, 5, 20)
    top = ss(.0, .07, v) * ss(1, .93, v)
    c = lerp(GUN, lerp(BONE * .95, WARMGREY, .3 + .15 * n1[..., None]), top)
    c = lerp(c, IVORY, edge_wear(np.minimum(v, 1 - v) * (S / 3) - 4, 14, S, 21) * .45)
    c *= (1 - .25 * cavity(top, 3))[..., None]
    c += stipple(S, 22)[..., None]
    save('curb', c, top + n1 * .04, 5, .8 + .05 * n1, size=512)

if want('plaza'):
    # 2x2 big squares, each 3x3 slate pavers framed by bone kerbs, brass inlay between squares
    x, y = grid(S); B = S / 2
    bx = x % B; by = y % B
    inner = np.minimum(np.minimum(bx, B - bx), np.minimum(by, B - by))
    bid, d, u, v = bricks(S, 6, 6, 8, 30, offset=0)
    tone = per_id(bid, 31); n1 = fbm(S, 28, 5, 32)
    pav = lerp(SLATE * 1.05, STONE, .25 + .35 * tone[..., None] + .06 * n1[..., None])
    hb = ss(-2, 8, d)
    c = lerp(GUNDK, pav, hb)
    kerb = (inner < 26).astype(float)
    c = lerp(c, lerp(BONE * .95, IVORY, n1[..., None] * .2 + .5), kerb * ss(4, 7, inner))
    inlay = ss(5, 3, inner)
    c = lerp(c, BRASS, inlay)
    c = lerp(c, BONE, edge_wear(np.where(kerb > 0, inner - 6, d), 8, S, 33) * .35)
    c *= (1 - .22 * cavity(hb, 4))[..., None]
    c += stipple(S, 34)[..., None]
    h = hb * (1 - kerb) + kerb * ss(4, 9, inner) * 1.05 + n1 * .04 - inlay * .1
    save('plaza', c, h, 5, .72 - .35 * inlay + .05 * n1)

if want('paint'):
    x, y = grid(S); n1 = fbm(S, 60, 5, 40); st = blur(rng(41).standard_normal((S, S)), (30, .8))
    st /= st.std()
    c = lerp(BONE, IVORY, .35 + .12 * n1[..., None] + .06 * st[..., None])
    c += stipple(S, 42, .02)[..., None]
    h = n1 * .05 + st * .02 + gnoise(S, 1.2, 43) * .02
    save('paint', c, h, 4, .7 + .05 * n1)

def brick_mat(key, rows, cols, mortar, base, var, mortarc, seed, bev=7, patina=0, chip=.5, sz=None):
    bid, d, u, v = bricks(S, rows, cols, mortar, seed)
    tone = per_id(bid, seed + 1); n1 = fbm(S, 18, 5, seed + 2); n2 = fbm(S, 5, 3, seed + 3)
    col = lerp(base, var, np.clip(tone[..., None] * .8 + n1[..., None] * .12, 0, 1))
    hb = ss(-1, bev, d) * (1 + .06 * (tone - .5)) + n2 * .03 * (d > 0)
    c = lerp(mortarc, col, ss(-1, 1.5, d))
    c = lerp(c, lerp(col, BONE, .5), edge_wear(d, bev, S, seed + 4) * chip)
    if patina: c = lerp(c, PATINA, ss(.55, .9, fbm(S, 30, 4, seed + 5)) * patina * (d > 0))
    c *= (1 - .3 * cavity(hb, 3))[..., None]
    c += stipple(S, seed + 6)[..., None]
    save(key, c, hb, 6, .82 + .08 * n1 - .05 * hb, size=sz)

if want('brick'): brick_mat('brick', 16, 8, 7, TERRA, hx('a8705c'), hx('cfc6b4'), 50)
if want('brickg'): brick_mat('brickg', 16, 8, 7, SLATE, hx('7d858d'), hx('b8b2a6'), 60, patina=.55)
if want('ybrick'): brick_mat('ybrick', 16, 8, 7, SAND, hx('dccaa2'), hx('8a8378'), 70)
if want('gbrick'): brick_mat('gbrick', 20, 10, 6, hx('8c8f93'), hx('b3b2ad'), hx('4a4d52'), 80)
if want('sbrick'): brick_mat('sbrick', 8, 4, 10, GUNDK * 1.15, hx('4a5058'), hx('1b1d21'), 90, bev=14, chip=.7)
if want('w9blk'): brick_mat('w9blk', 16, 8, 6, hx('9c9a94'), hx('b9b6ae'), hx('6c6a66'), 100, bev=5, chip=.3)

if want('stone'):
    d1, d2, vid = vor(S, 150, 110)
    e = d2 - d1; tone = per_id(vid, 111); n1 = fbm(S, 12, 5, 112)
    hb = ss(2, 22, e) ** .7 + n1 * .05
    col = lerp(WARMGREY, BONE * .95, tone[..., None] * .7 + n1[..., None] * .1)
    col = lerp(col, SLATE, (per_id(vid, 113) > .82)[..., None] * .6)
    c = lerp(GUN * .9, col, ss(1, 6, e))
    c = lerp(c, IVORY, edge_wear(e - 4, 10, S, 114) * .35)
    c *= (1 - .3 * cavity(hb, 4))[..., None]; c += stipple(S, 115)[..., None]
    save('stone', c, hb, 6, .8 - .1 * hb)

if want('shing'):
    rows = 10; bid, d, u, v = bricks(S, rows, 6, 5, 120)
    tone = per_id(bid, 121); n1 = fbm(S, 15, 4, 122)
    slope = v  # each slate thickens toward its lower edge
    col = lerp(SLATE * .85, hx('6f7a86'), tone[..., None] * .8 + n1[..., None] * .1)
    hb = ss(-1, 4, d) * (.4 + .6 * slope)
    c = lerp(NAVY, col, ss(-1, 1, d)) * (.82 + .18 * slope)[..., None]
    c = lerp(c, hx('9aa4ad'), edge_wear(d, 5, S, 123) * .35)
    c += stipple(S, 124)[..., None]
    save('shing', c, hb, 6, .75 + .1 * n1)

if want('corr'):
    x, y = grid(S); rib = .5 + .5 * np.cos(x / S * 2 * np.pi * 16)
    n1 = fbm(S, 20, 5, 130)
    paint = lerp(SLATE * .82, NAVY * 1.25, .4 + .15 * n1[..., None])
    chips = ss(.62, .7, fbm(S, 7, 5, 131) * .5 + .5) * (.5 + .5 * ss(.6, 1, rib))
    steel = lerp(hx('8d9298'), hx('b7bcc1'), gnoise(S, (40, .5), 132)[..., None] * .2 + .5)
    c = lerp(paint, steel, chips[..., None])
    c *= (.82 + .18 * rib)[..., None]
    seam = ss(4, 0, abs((y % (S / 2)) - S / 4) - (S / 4 - 4))
    bolts = (seam > 0) * (((x % (S / 16)) - S / 32) ** 2 < 25)
    c = lerp(c, BRASSDK, bolts * .8)
    h = rib * .8 - seam * .2 + bolts * .3
    save('corr', c, h, 4, .6 - .25 * chips, size=512)

if want('wood'):
    x, y = grid(S); planks = 8; ph = S / planks
    row = np.floor(y / ph); off = per_id(row.astype(int), 140) * S
    xs = (x + off) % S; L = S / 2; col = np.floor(xs / L)
    pid = (row * 2 + col).astype(int); tone = per_id(pid, 141)
    lv = (y % ph) / ph; lu = (xs % L)
    d = np.minimum(np.minimum(lu, L - lu), np.minimum(lv * ph, ph - lv * ph)) - 2
    warp = fbm(S, 25, 3, 142)
    grain = .5 + .5 * np.sin((y + warp * 18 + tone * 300) / ph * 2 * np.pi * 5 + gnoise(S, (2, 60), 143) * 2)
    base = lerp(hx('5d4130'), hx('8a6446'), tone[..., None] * .7 + grain[..., None] * .25)
    hb = ss(-1, 4, d) + grain * .06
    c = lerp(hx('2b1f17'), base, ss(-1, 1.5, d))
    c *= (1 - .25 * cavity(hb, 3))[..., None]; c += stipple(S, 144, .025)[..., None]
    save('wood', c, hb, 5, .62 + .1 * grain)

if want('plast'):
    n1 = fbm(S, 50, 6, 150); n2 = gnoise(S, 1.5, 151)
    c = lerp(IVORY, BONE, .5 + .15 * n1[..., None]) + (n2 * .015)[..., None]
    save('plast', c, n1 * .06 + n2 * .03, 5, .85)

if want('wplaster'):
    n1 = fbm(S, 35, 6, 160); blot = ss(.2, .6, fbm(S, 60, 4, 161))
    c = lerp(BONE, lerp(IVORY, SAND, .25), blot[..., None] * .5 + n1[..., None] * .08)
    c += stipple(S, 162, .03)[..., None]
    save('wplaster', c, n1 * .08 + gnoise(S, 1.2, 163) * .04, 5, .88)

if want('wsiding'):
    x, y = grid(S); bh = S / 12; v = (y % bh) / bh; n1 = fbm(S, 40, 4, 170)
    lap = v ** 1.4
    c = lerp(BONE * .97, IVORY, .4 + .1 * n1[..., None]) * (.86 + .14 * lap)[..., None]
    c = lerp(c, GUN, ss(.04, 0, v) * .6)
    save('wsiding', c, lap - ss(.04, 0, v) * .4, 5, .7)

if want('w4c'):
    # architectural concrete: panel seams + formwork tie holes (receiver-panel look)
    x, y = grid(S); PW, PH = S / 2, S / 4; n1 = fbm(S, 30, 6, 180); n2 = fbm(S, 4, 3, 181)
    px = x % PW; py = y % PH
    seam = ss(3, 0, np.minimum(np.minimum(px, PW - px), np.minimum(py, PH - py)))
    hx_ = (px - PW / 4) % (PW / 2) - PW / 4; hy_ = (py - PH / 4) % (PH / 2) - PH / 4
    hole = ss(9, 6, np.hypot(hx_, hy_))
    tone = per_id((np.floor(x / PW) + 7 * np.floor(y / PH)).astype(int), 182)
    c = lerp(hx('a29f99'), hx('c2beb5'), (.35 + .25 * tone + .1 * n1)[..., None])
    c = lerp(c, GUN, seam * .7); c = lerp(c, GUNDK, hole * .85)
    c += (n2 * .02)[..., None] + stipple(S, 183, .02)[..., None]
    save('w4c', c, n1 * .05 - seam * .3 - hole * .5 + n2 * .02, 5, .82)

if want('wroof'):
    rows = 10; bid, d, u, v = bricks(S, rows, 8, 3, 190)
    tone = per_id(bid, 191); n1 = fbm(S, 12, 4, 192)
    arch = np.cos((u - .5) * np.pi) ** .6
    hb = arch * (.5 + .5 * v) * ss(-1, 3, d)
    col = lerp(hx('7a4a3c'), hx('9d6550'), tone[..., None] * .7 + n1[..., None] * .1)
    c = lerp(hx('2a1d18'), col, ss(-1, 1, d)) * (.75 + .25 * hb)[..., None]
    c = lerp(c, hx('b98a72'), edge_wear(d, 4, S, 193) * .3)
    save('wroof', c, hb, 6, .7)

def tile_mat(key, n, base, var, seed, gold=False, cracks=0, run=False):
    bid, d, u, v = bricks(S, n, n, 9, seed, offset=0)
    tone = per_id(bid, seed + 1); n1 = fbm(S, 25, 6, seed + 2); n2 = fbm(S, 6, 4, seed + 3)
    col = lerp(base, var, (.4 + .3 * tone + .12 * n1)[..., None])
    hb = ss(-1, 8, d) + n2 * .03
    c = lerp(GUN, col, ss(-1, 1.5, d))
    if cracks:
        d1, d2, _ = vor(S, 60, seed + 4); cr = ss(2.5, 0, d2 - d1) * ss(.45, .7, fbm(S, 40, 3, seed + 5) * .5 + .5)
        c = lerp(c, GUNDK, cr * cracks); hb = hb - cr * .3
        c = lerp(c, lerp(col, GUNDK, .3), ss(.6, .85, fbm(S, 50, 4, seed + 6)) * .4)
    if gold:
        cs = S / n; lx = (u * cs); ly = (v * cs)
        tri = (lx + ly) < cs * .28
        stripe = (np.floor((lx - ly) / 9) % 2 == 0)
        mark = tri * ss(-1, 1, d)
        c = lerp(c, np.where(stripe[..., None], BRASS, GUNDK), mark * .95)
        hb = hb + mark * .15
    c = lerp(c, BONE, edge_wear(d, 8, S, seed + 7) * .3)
    c *= (1 - .2 * cavity(hb, 4))[..., None]; c += stipple(S, seed + 8)[..., None]
    save(key, c, hb, 5, .8 + .05 * n1)

if want('cdmg'): tile_mat('cdmg', 4, hx('9a978f'), hx('b4b0a6'), 200, cracks=.85)
if want('cgold'): tile_mat('cgold', 4, hx('a7a49c'), hx('c2beb4'), 210, gold=True)
if want('crun'): tile_mat('crun', 4, hx('9d9c97'), hx('b2b1ab'), 220)

if want('gravel'):
    d1, d2, vid = vor(S, 2200, 230); e = d2 - d1; tone = per_id(vid, 231)
    hb = ss(0, 9, e) ** .6
    col = lerp(STONE, BONE * .92, tone[..., None]); col = lerp(col, SLATE, (per_id(vid, 232) > .75)[..., None] * .7)
    c = lerp(GUNDK, col, ss(0, 3, e)) * (.75 + .25 * hb)[..., None]
    save('gravel', c, hb, 6, .85)

# =============================== TERRAIN ===============================
def strokes(S, n, seed, length, width, angle_sd, base_angle=-np.pi / 2):
    """painted blade/needle strokes (tileable)"""
    r = rng(seed); H = np.zeros((S, S)); C = np.zeros((S, S))
    for _ in range(n):
        x0, y0 = r.random(2) * S; a = base_angle + r.normal(0, angle_sd); L = length * (.6 + .8 * r.random())
        t = np.linspace(0, 1, int(L))
        xs = (x0 + np.cos(a) * L * t).astype(int) % S; ys = (y0 + np.sin(a) * L * t).astype(int) % S
        tone = r.random()
        for w in range(width):
            H[ys, (xs + w) % S] = np.maximum(H[ys, (xs + w) % S], t * (1 - .3 * w))
            C[ys, (xs + w) % S] = tone
    return H, C

if want('tgrass'):
    n1 = fbm(S, 70, 5, 300); H, Cn = strokes(S, 26000, 301, 26, 2, .35)
    base = lerp(hx('4d5a2c'), hx('6f7a3e'), (.5 + .2 * n1)[..., None])
    blade = lerp(hx('6a7a38'), hx('a2a65a'), Cn[..., None])
    c = lerp(base * .8, blade, (H ** .8)[..., None] * .85)
    c = lerp(c, SAND * .8, ss(.7, .95, fbm(S, 90, 3, 302))[..., None] * .25)
    save('tgrass', c, H * .6 + n1 * .1, 5)

if want('tforest'):
    n1 = fbm(S, 50, 5, 310); H, Cn = strokes(S, 9000, 311, 18, 1, 3.0)
    soil = lerp(hx('3b3027'), hx('5a4a38'), (.5 + .2 * n1)[..., None])
    c = lerp(soil, lerp(hx('6e5a3c'), hx('8f7a52'), Cn[..., None]), (H > 0)[..., None] * .8)
    c = lerp(c, OLIVE * .8, ss(.65, .9, fbm(S, 40, 4, 312))[..., None] * .5)
    save('tforest', c, H * .4 + n1 * .1, 5)

if want('tdry'):
    n1 = fbm(S, 60, 5, 320); H, Cn = strokes(S, 22000, 321, 30, 1, 1.2, 0)
    base = lerp(hx('8a7346'), hx('a68f5c'), (.5 + .2 * n1)[..., None])
    c = lerp(base * .85, lerp(hx('b9a06a'), hx('dcc890'), Cn[..., None]), (H ** .7)[..., None] * .8)
    save('tdry', c, H * .5 + n1 * .1, 5)

if want('tmud'):
    d1, d2, vid = vor(S, 120, 330); e = d2 - d1; n1 = fbm(S, 25, 5, 331); tone = per_id(vid, 332)
    crack = ss(3, 0, e); plate = ss(0, 18, e) ** .5
    col = lerp(hx('5a4636'), hx('7a6450'), (.4 + .3 * tone + .1 * n1)[..., None])
    c = lerp(col, hx('2d231b'), crack[..., None]) * (.85 + .15 * plate)[..., None]
    c = lerp(c, BONE * .8, edge_wear(e - 3, 6, S, 333)[..., None] * .2)
    save('tmud', c, plate - crack * .5 + n1 * .05, 5)

if want('twet'):
    n1 = fbm(S, 30, 6, 340); pud = ss(.55, .62, fbm(S, 70, 4, 341) * .5 + .5)
    mud = lerp(hx('3e3127'), hx('5f4c3b'), (.5 + .2 * n1)[..., None])
    c = lerp(mud, lerp(NAVY, SLATE * .7, .3), pud[..., None] * .9)
    save('twet', c, n1 * .1 - pud * .2, 4)

if want('tsand'):
    x, y = grid(S); w = fbm(S, 60, 3, 350)
    rip = .5 + .5 * np.sin((y + w * 40) / S * 2 * np.pi * 14)
    c = lerp(hx('cdbb94'), hx('e6d8b6'), (.35 + .3 * rip + .1 * fbm(S, 20, 4, 351))[..., None])
    c += stipple(S, 352, .03)[..., None]
    save('tsand', c, rip * .4, 4)

if want('tsand2'):
    n1 = fbm(S, 40, 5, 360); d1, _, vid = vor(S, 900, 361); peb = ss(6, 3, d1) * (per_id(vid, 362) > .6)
    c = lerp(hx('8f7f66'), hx('ad9c80'), (.5 + .2 * n1)[..., None])
    c = lerp(c, lerp(STONE, BONE * .9, per_id(vid, 363)[..., None]), peb[..., None] * .8)
    save('tsand2', c, n1 * .1 + peb * .5, 5)

if want('tsnow'):
    n1 = fbm(S, 80, 5, 370); n2 = fbm(S, 8, 3, 371)
    c = lerp(hx('d6dde3'), hx('f2f4f5'), (.55 + .2 * n1 + .05 * n2)[..., None])
    c = lerp(c, hx('b9c6d2'), ss(.7, .95, -n1 * .5 + .5)[..., None] * .4)
    save('tsnow', c, n1 * .2 + n2 * .05, 4)

if want('tice'):
    n1 = fbm(S, 60, 5, 380); d1, d2, _ = vor(S, 40, 381); cr = ss(2, 0, d2 - d1)
    c = lerp(hx('8fb2c6'), hx('cfe2ea'), (.5 + .25 * n1)[..., None])
    c = lerp(c, hx('eef6f8'), cr[..., None] * .7)
    save('tice', c, n1 * .1 - cr * .2, 4)

def strata(key, a, b, seed):
    x, y = grid(S); w = fbm(S, 80, 4, seed); n1 = fbm(S, 12, 5, seed + 1)
    band = (y / S * 9 + w * .22 + .05 * np.sin(x / S * 2 * np.pi * 3)) % 1
    ledge = ss(.0, .08, band) * ss(1, .7, band)
    col = lerp(a, b, (.4 + .35 * np.sin(band * 6.28 + w) * .5 + .1 * n1)[..., None])
    c = col * (.7 + .3 * ledge)[..., None]
    c = lerp(c, BONE * .85, edge_wear(ss(.08, .0, band) * 10, 6, S, seed + 2)[..., None] * .2)
    c += stipple(S, seed + 3, .03)[..., None]
    save(key, c, ledge + n1 * .08, 5)

if want('cliffa'): strata('cliffa', hx('5d6066'), hx('8d8f92'), 390)
if want('cliffb'): strata('cliffb', hx('4f3c30'), hx('7d6450'), 400)

import json
mf = f'{OUT}/means95.json'
old = json.load(open(mf)) if os.path.exists(mf) else {}
old.update(MEANS); json.dump(old, open(mf, 'w'), indent=0)
print('done', len(MEANS))
