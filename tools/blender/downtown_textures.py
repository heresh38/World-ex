"""Downtown facade and street texture sets for downtown.py (numpy painted, no Blender needed; runs under the bpy shim too).

Every facade set is one tiling unit of whole floors x whole bays, so the UVs in downtown.py map u = metres / tile width,
v = metres from the ground / tile height and the windows line up with the floors of the geometry. Outputs in assets/textures:
  <name>_c.jpg  colour            (embedded in the downtown GLBs)
  <name>_n.jpg  tangent normal    (OpenGL / glTF convention, +Y up)
  <name>_m.jpg  R = lit window mask (night/emissive), G = roughness, B = metalness. The glTF exporter uses G/B as the
                metallicRoughness texture; earth.js reuses the same image as the emissive mask (red channel).
Sets: dt_curtain (unitised glass curtain wall), dt_ribbon (1970s bronze ribbon glazing + concrete spandrels),
dt_precast (ribbed precast panels), dt_punched (residential / hotel punched windows), dt_brick (historic red brick, sash
windows), dt_stone (rusticated sandstone, arched windows), dt_derelict (boarded and broken windows, grime), dt_shop
(ground-floor shopfronts with fictional generic signs), plus dt_roof, dt_pavers, dt_rawconc, dt_hoarding, dt_awning and
RGBA cut-outs dt_lattice (crane / scaffold truss) and dt_net (safety netting).
Usage: python3 tools/blender/downtown_textures.py  (or via blender --background --python)
"""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'assets', 'textures')
os.makedirs(OUT, exist_ok=True)


def font(px, bold=True):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf'):
        if os.path.exists(f):
            return ImageFont.truetype(f, px)
    return ImageFont.load_default()


def noise(h, w, beta=1.6, seed=0, ax=1.0, ay=1.0):
    """Tileable 1/f^beta noise in 0..1 (FFT filtered white noise). ax/ay > 1 squash features along that axis."""
    r = np.random.RandomState(seed)
    F = np.fft.fft2(r.randn(h, w))
    fy = np.fft.fftfreq(h)[:, None] * h / max(h, w) * ay
    fx = np.fft.fftfreq(w)[None, :] * w / max(h, w) * ax
    f = np.sqrt(fx * fx + fy * fy); f[0, 0] = 1
    n = np.real(np.fft.ifft2(F / f ** beta))
    return (n - n.min()) / (np.ptp(n) + 1e-9)


class Canvas:
    def __init__(self, w, h, col=(.5, .5, .5), rough=.8, metal=0.0):
        self.w, self.h = w, h
        self.c = np.zeros((h, w, 3), np.float32); self.c[:] = col
        self.hg = np.zeros((h, w), np.float32)
        self.lit = np.zeros((h, w), np.float32)
        self.r = np.full((h, w), rough, np.float32)
        self.m = np.full((h, w), metal, np.float32)

    def rect(self, x0, y0, x1, y1, col=None, h=None, rough=None, metal=None, lit=None, dh=None):
        x0, x1 = int(round(max(0, min(x0, x1)))), int(round(min(self.w, max(x0, x1))))
        y0, y1 = int(round(max(0, min(y0, y1)))), int(round(min(self.h, max(y0, y1))))
        if x1 <= x0 or y1 <= y0:
            return
        s = (slice(y0, y1), slice(x0, x1))
        if col is not None:
            self.c[s] = col
        if h is not None:
            self.hg[s] = h
        if dh is not None:
            self.hg[s] += dh
        if rough is not None:
            self.r[s] = rough
        if metal is not None:
            self.m[s] = metal
        if lit is not None:
            self.lit[s] = lit

    def mask(self, m, col=None, h=None, rough=None, metal=None, lit=None, mul=None):
        if col is not None:
            self.c[m] = col
        if mul is not None:
            self.c[m] *= mul
        if h is not None:
            self.hg[m] = h
        if rough is not None:
            self.r[m] = rough
        if metal is not None:
            self.m[m] = metal
        if lit is not None:
            self.lit[m] = lit

    def save(self, name, strength=2.0, normal=True, aux=True, csize=None, nsize=None):
        def to_img(a, size):
            im = Image.fromarray(np.clip(a * 255 + .5, 0, 255).astype(np.uint8))
            if size and (im.width, im.height) != size:
                im = im.resize(size, Image.LANCZOS)
            return im
        to_img(self.c ** (1 / 2.2), csize).save(os.path.join(OUT, name + '_c.jpg'), quality=88)
        if normal:
            hg = self.hg
            dx = (np.roll(hg, -1, 1) - np.roll(hg, 1, 1)) * .5 * strength
            dy = (np.roll(hg, 1, 0) - np.roll(hg, -1, 0)) * .5 * strength     # row 0 is the top: +v is up
            n = np.dstack([-dx, -dy, np.ones_like(hg)])
            n /= np.linalg.norm(n, axis=2, keepdims=True)
            to_img(n * .5 + .5, nsize).save(os.path.join(OUT, name + '_n.jpg'), quality=90)
        if aux:
            a = np.dstack([np.clip(self.lit, 0, 1), np.clip(self.r, .02, 1), np.clip(self.m, 0, 1)])
            to_img(a, nsize).save(os.path.join(OUT, name + '_m.jpg'), quality=90)
        print('[texture] %s (%dx%d)' % (name, self.w, self.h))


def grime(cv, seed, amount=.25, streak=.35, scale=1.0):
    """Large blotchy dirt plus vertical rain streaks multiplied into the colour."""
    n = noise(cv.h, cv.w, 1.8, seed)
    s = noise(cv.h, cv.w, 1.4, seed + 1, ax=6, ay=.35)
    k = 1 - amount * np.clip((n - .45) * 2.2, 0, 1) - streak * np.clip((s - .55) * 2.5, 0, 1)
    cv.c *= k[..., None] * scale


def jitter(rg, col, amt):
    return tuple(max(0, c * (1 + (rg.rand() - .5) * 2 * amt)) for c in col)


# ---------------------------------------------------------------- glass curtain wall: 8 modules x 4 floors
def curtain():
    W, H, B, F = 1024, 1024, 8, 4
    cw, ch = W // B, H // F
    cv = Canvas(W, H, (.1, .13, .17), .06, .85)
    rg = np.random.RandomState(11)
    tone = noise(H, W, 2.2, 5)
    for f in range(F):
        lit_floor = rg.rand() < .45
        for b in range(B):
            x0, y0 = b * cw, f * ch
            g = jitter(rg, (.085, .115, .15), .14)
            cv.rect(x0, y0, x0 + cw, y0 + ch, col=g, h=0, rough=.03 + rg.rand() * .05, metal=.85)
            # spandrel (opaque shadow-box glass at the slab), bottom 0.9 m of the 4 m floor
            sp = int(ch * .22)
            cv.rect(x0, y0 + ch - sp, x0 + cw, y0 + ch, col=jitter(rg, (.055, .07, .085), .08), rough=.09, metal=.8, h=.15)
            # interior: blinds pulled down part way, ceiling light strip on lit floors
            vis0, vis1 = y0 + 6, y0 + ch - sp - 4
            bl = rg.rand()
            if bl < .55:
                dn = int((vis1 - vis0) * rg.uniform(.1, .7))
                shade = jitter(rg, (.3, .3, .29), .15)
                cv.rect(x0 + 4, vis0, x0 + cw - 4, vis0 + dn, col=shade, rough=.05)
                for yy in range(vis0, vis0 + dn, 5):
                    cv.rect(x0 + 4, yy, x0 + cw - 4, yy + 1, col=tuple(c * .78 for c in shade))
            if lit_floor and rg.rand() < .8:
                cv.rect(x0 + 4, vis0 + 3, x0 + cw - 4, vis1, lit=.75 + rg.rand() * .25)
                cv.rect(x0 + 4, vis0 + 2, x0 + cw - 4, vis0 + 6, col=(.8, .78, .7))
                cv.c[vis0 + 6:vis1, x0 + 4:x0 + cw - 4] += np.array((.06, .055, .04), np.float32)
            # mullions (vertical) and transom at the slab line
            m = 4
            cv.rect(x0, y0, x0 + m, y0 + ch, col=(.55, .58, .61), h=1, rough=.35, metal=.9)
            cv.rect(x0 + cw - m, y0, x0 + cw, y0 + ch, col=(.55, .58, .61), h=1, rough=.35, metal=.9)
            cv.rect(x0, y0 + ch - sp - 3, x0 + cw, y0 + ch - sp + 2, col=(.5, .53, .56), h=1, rough=.35, metal=.9)
            cv.rect(x0, y0, x0 + cw, y0 + 3, col=(.5, .53, .56), h=1, rough=.35, metal=.9)
    cv.c *= (.9 + .2 * tone)[..., None]
    cv.save('dt_curtain', strength=3.0, nsize=(512, 512))


# ---------------------------------------------------------------- 1970s ribbon glazing: bronze glass + concrete bands
def ribbon():
    W, H, B, F = 1024, 1024, 8, 4
    cw, ch = W // B, H // F
    conc = noise(H, W, 1.2, 21)
    cv = Canvas(W, H, (.56, .52, .46), .85, 0)
    cv.c *= (.85 + .3 * conc)[..., None]
    rg = np.random.RandomState(22)
    for f in range(F):
        y0 = f * ch
        band0, band1 = y0 + int(ch * .12), y0 + int(ch * .58)
        lit_floor = rg.rand() < .4
        for b in range(B):
            x0 = b * cw
            cv.rect(x0, band0, x0 + cw, band1, col=jitter(rg, (.16, .1, .055), .12), h=-1, rough=.07, metal=.75)
            if rg.rand() < .5:
                dn = int((band1 - band0) * rg.uniform(.2, .8))
                cv.rect(x0 + 3, band0, x0 + cw - 3, band0 + dn, col=jitter(rg, (.28, .22, .15), .1), h=-1, rough=.07)
            if lit_floor and rg.rand() < .7:
                cv.rect(x0 + 3, band0 + 3, x0 + cw - 3, band1 - 2, lit=.7 + rg.rand() * .3)
            cv.rect(x0, band0, x0 + 4, band1, col=(.12, .08, .05), h=-.6, rough=.4, metal=.8)
        # sill and drip edge
        cv.rect(0, band1, W, band1 + 6, col=(.66, .62, .55), h=.3)
        cv.rect(0, band0 - 5, W, band0, col=(.4, .37, .33), h=-.3)
        # panel joints in the spandrel
        for b in range(0, B, 2):
            cv.rect(b * cw - 1, band1 + 6, b * cw + 2, y0 + ch + band0 - y0 if f < F - 1 else H, col=(.35, .33, .3), h=-.5)
    # rain streaks under the windows
    s = noise(H, W, 1.3, 23, ax=8, ay=.3)
    cv.c *= (1 - .32 * np.clip((s - .5) * 2.4, 0, 1))[..., None]
    grime(cv, 24, .18, .0)
    cv.save('dt_ribbon', strength=2.5, nsize=(512, 512))


# ---------------------------------------------------------------- ribbed precast: 4 bays x 4 floors
def precast():
    W, H, B, F = 1024, 1024, 4, 4
    cw, ch = W // B, H // F
    agg = noise(H, W, .6, 31)
    cv = Canvas(W, H, (.78, .76, .71), .8, 0)
    cv.c *= (.92 + .12 * agg)[..., None]
    cv.hg += agg * .15
    rg = np.random.RandomState(32)
    rib = int(cw * .17)
    for f in range(F):
        y0 = f * ch
        lit_floor = rg.rand() < .4
        for b in range(B):
            x0 = b * cw
            wx0, wx1 = x0 + rib + 8, x0 + cw - 8
            wy0, wy1 = y0 + int(ch * .1), y0 + int(ch * .66)
            cv.rect(x0 + rib, y0, x0 + cw, y0 + ch, h=.5)
            cv.rect(wx0 - 6, wy0 - 6, wx1 + 6, wy1 + 6, col=(.6, .59, .56), h=.15)                # reveal
            cv.rect(wx0, wy0, wx1, wy1, col=jitter(rg, (.07, .085, .1), .15), h=-.6, rough=.05, metal=.7)
            cv.rect((wx0 + wx1) // 2 - 2, wy0, (wx0 + wx1) // 2 + 2, wy1, col=(.25, .26, .27), h=-.4, rough=.4, metal=.8)
            if rg.rand() < .45:
                cv.rect(wx0, wy0, wx1, wy0 + int((wy1 - wy0) * rg.uniform(.15, .6)), col=jitter(rg, (.42, .41, .38), .1), h=-.6, rough=.06)
            if lit_floor and rg.rand() < .75:
                cv.rect(wx0 + 2, wy0 + 2, wx1 - 2, wy1 - 2, lit=.7 + rg.rand() * .3)
            # rib (pilaster) proud of the panel, with a shadow edge
            cv.rect(x0, y0, x0 + rib, y0 + ch, col=(.84, .82, .77), h=1.6, rough=.75)
            cv.rect(x0 + rib, y0, x0 + rib + 5, y0 + ch, col=(.55, .54, .5), h=.4)
        cv.rect(0, y0 + ch - 4, W, y0 + ch, col=(.5, .49, .46), h=.2)
    s = noise(H, W, 1.3, 33, ax=9, ay=.3)
    cv.c *= (1 - .22 * np.clip((s - .5) * 2.4, 0, 1))[..., None]
    grime(cv, 34, .14, .0)
    cv.save('dt_precast', strength=3.5, nsize=(512, 512))


# ---------------------------------------------------------------- punched windows (residential, hotel): 4 x 4
def punched():
    W, H, B, F = 1024, 1024, 4, 4
    cw, ch = W // B, H // F
    cv = Canvas(W, H, (.82, .8, .76), .85, 0)
    cv.c *= (.93 + .1 * noise(H, W, 1.0, 41))[..., None]
    rg = np.random.RandomState(42)
    curtains = [(.75, .68, .55), (.55, .2, .18), (.85, .84, .8), (.3, .4, .55), (.6, .55, .35), (.4, .45, .3)]
    for f in range(F):
        y0 = f * ch
        for b in range(B):
            x0 = b * cw
            door = rg.rand() < .3
            wx0, wx1 = x0 + int(cw * .2), x0 + int(cw * .8)
            wy0, wy1 = y0 + int(ch * .16), y0 + (ch - 2 if door else int(ch * .7))
            cv.rect(wx0 - 7, wy0 - 7, wx1 + 7, wy1 + 9, col=(.62, .6, .57), h=.3)                 # surround
            cv.rect(wx0, wy0, wx1, wy1, col=(.25, .26, .27), h=-.3, rough=.4, metal=.5)              # frame
            g0, g1 = wx0 + 5, wx1 - 5
            cv.rect(g0, wy0 + 5, g1, wy1 - 5, col=jitter(rg, (.06, .075, .09), .2), h=-.8, rough=.05, metal=.6)
            cc = curtains[rg.randint(len(curtains))]
            k = rg.rand()
            if k < .5:   # curtains drawn to the sides
                cwid = int((g1 - g0) * rg.uniform(.12, .3))
                cv.rect(g0, wy0 + 5, g0 + cwid, wy1 - 5, col=cc, h=-.8, rough=.06)
                cv.rect(g1 - cwid, wy0 + 5, g1, wy1 - 5, col=cc, h=-.8, rough=.06)
            elif k < .7:
                cv.rect(g0, wy0 + 5, g1, wy0 + 5 + int((wy1 - wy0) * rg.uniform(.2, .7)), col=cc, h=-.8, rough=.06)
            cv.rect((g0 + g1) // 2 - 2, wy0 + 5, (g0 + g1) // 2 + 2, wy1 - 5, col=(.25, .26, .27), h=-.3)
            if rg.rand() < .35:
                cv.rect(g0 + 2, wy0 + 7, g1 - 2, wy1 - 7, lit=.65 + rg.rand() * .35)
                cv.c[wy0 + 7:wy1 - 7, g0 + 2:g1 - 2] += np.array((.12, .09, .05), np.float32)
            if not door:
                cv.rect(wx0 - 9, wy1 + 4, wx1 + 9, wy1 + 12, col=(.7, .68, .64), h=.8)                 # sill
        cv.rect(0, y0 + ch - 6, W, y0 + ch, col=(.7, .68, .64), h=.25)
    grime(cv, 43, .15, .25)
    cv.save('dt_punched', strength=2.5, nsize=(512, 512))


def brickfield(cv, x0, y0, x1, y1, base, seed, bw=17, bh=6, mortar=(.62, .58, .52)):
    """Running-bond brick courses (per-brick tone) in a region."""
    rg = np.random.RandomState(seed)
    h = y1 - y0; w = x1 - x0
    yy, xx = np.mgrid[0:h, 0:w]
    row = yy // bh
    xs = xx + (row % 2) * (bw // 2)
    col_i = xs // bw
    ids = (row * 7919 + col_i * 104729) % 9973
    tones = rg.uniform(.78, 1.18, 9973).astype(np.float32)
    tint = rg.uniform(-.06, .06, (9973, 3)).astype(np.float32)
    t = tones[ids]
    c = np.array(base, np.float32)[None, None, :] * t[..., None] * (1 + tint[ids])
    joint = ((yy % bh) == 0) | ((xs % bw) == 0)
    c[joint] = mortar
    sl = (slice(y0, y1), slice(x0, x1))
    cv.c[sl] = c
    cv.hg[sl] = np.where(joint, -.4, .2 + .05 * t)
    cv.r[sl] = np.where(joint, .95, .82)
    cv.m[sl] = 0


def sash(cv, rg, x0, y0, x1, y1, frame=(.9, .88, .82), lit_p=.3, arch=False):
    """Timber sash window: frame, two sashes, glazing bars, blinds; optional round arch head."""
    cv.rect(x0, y0, x1, y1, col=frame, h=-.2, rough=.5)
    gx0, gx1 = x0 + 5, x1 - 5
    gy0, gy1 = y0 + 5, y1 - 5
    glass = jitter(rg, (.05, .065, .08), .2)
    cv.rect(gx0, gy0, gx1, gy1, col=glass, h=-.9, rough=.05, metal=.6)
    mid = (gy0 + gy1) // 2
    cv.rect(x0, mid - 3, x1, mid + 3, col=frame, h=-.2, rough=.5)
    cx = (gx0 + gx1) // 2
    cv.rect(cx - 1, gy0, cx + 2, gy1, col=frame, h=-.3, rough=.5)
    if rg.rand() < .5:
        dn = int((mid - gy0) * rg.uniform(.3, 1.0))
        cv.rect(gx0, gy0, gx1, gy0 + dn, col=jitter(rg, (.78, .72, .6), .1), h=-.9, rough=.08)
    if rg.rand() < lit_p:
        cv.rect(gx0 + 1, gy0 + 1, gx1 - 1, gy1 - 1, lit=.65 + rg.rand() * .35)
        cv.c[gy0:gy1, gx0:gx1] += np.array((.1, .07, .03), np.float32)


# ---------------------------------------------------------------- historic red brick: 4 bays x 4 floors (3.6 x 4.2 m)
def brick():
    W, H, B, F = 1024, 1024, 4, 4
    cw, ch = W // B, H // F
    cv = Canvas(W, H)
    brickfield(cv, 0, 0, W, H, (.5, .22, .14), 51)
    rg = np.random.RandomState(52)
    stone = (.78, .7, .56)
    for f in range(F):
        y0 = f * ch
        for b in range(B):
            x0 = b * cw
            wx0, wx1 = x0 + int(cw * .3), x0 + int(cw * .7)
            wy0, wy1 = y0 + int(ch * .2), y0 + int(ch * .85)
            cv.rect(wx0 - 10, wy0 - 16, wx1 + 10, wy0 - 2, col=stone, h=.6, rough=.8)               # lintel
            cv.rect(wx0 - 8, wy1, wx1 + 8, wy1 + 9, col=stone, h=.8, rough=.8)                     # sill
            cv.rect(wx0 - 9, wy0 - 16 + 3, wx0 - 6, wy0 - 2, col=(.6, .5, .4))
            sash(cv, rg, wx0, wy0, wx1, wy1, frame=(.88, .85, .78) if (b + f) % 3 else (.18, .28, .22))
        cv.rect(0, y0 + ch - 9, W, y0 + ch - 3, col=(.42, .19, .12), h=.5)                          # string course
    grime(cv, 53, .2, .3)
    cv.save('dt_brick', strength=2.2, nsize=(512, 512))


# ---------------------------------------------------------------- rusticated sandstone, arched windows: 4 bays x 2 floors
def stone():
    W, H, B, F = 1024, 1024, 4, 2
    cw, ch = W // B, H // F
    cv = Canvas(W, H, (.74, .62, .44), .9, 0)
    rg = np.random.RandomState(61)
    yy, xx = np.mgrid[0:H, 0:W]
    cour = 56                                                   # ~0.55 m courses
    row = yy // cour
    bw = 112
    xs = xx + (row % 2) * (bw // 2)
    ids = (row * 31 + xs // bw * 17) % 997
    tone = rg.uniform(.82, 1.12, 997).astype(np.float32)[ids]
    warm = rg.uniform(-.05, .05, 997).astype(np.float32)[ids]
    n1 = noise(H, W, 1.0, 62)
    cv.c *= (tone * (.9 + .2 * n1))[..., None]
    cv.c[..., 0] *= (1 + warm); cv.c[..., 2] *= (1 - warm)
    jy, jx = yy % cour, xs % bw
    dist = np.minimum(np.minimum(jy, cour - jy), np.minimum(jx, bw - jx)).astype(np.float32)
    cv.hg = np.clip(dist / 5, 0, 1) * 1.0 + n1 * .25          # V-jointed rustication
    cv.c *= (.75 + .25 * np.clip(dist / 4, 0, 1))[..., None]
    for f in range(F):
        y0 = f * ch
        for b in range(B):
            x0 = b * cw
            wx0, wx1 = x0 + int(cw * .28), x0 + int(cw * .72)
            wy1 = y0 + int(ch * .86)
            arch = f == 0                                       # top row of the tile is the upper (arched) floor
            wy0 = y0 + int(ch * (.3 if arch else .22))
            r = (wx1 - wx0) // 2
            # smooth dressed surround
            cv.rect(wx0 - 14, wy0 - (r + 14 if arch else 18), wx1 + 14, wy1 + 12, col=(.8, .69, .5), h=1.1, rough=.85)
            if arch:
                cx, cy = (wx0 + wx1) / 2, wy0
                m = ((xx - cx) ** 2 + (yy - cy) ** 2 < r * r) & (yy < cy) & (yy > cy - r - 1)
                m2 = ((xx - cx) ** 2 + (yy - cy) ** 2 < (r - 5) ** 2) & (yy < cy) & (yy > cy - r)
                cv.mask(m, col=(.88, .86, .8), h=.0, rough=.5)
                cv.mask(m2, col=(.06, .07, .085), h=-.9, rough=.05, metal=.6)
                cv.rect(cx - 8, cy - r - 16, cx + 8, cy - r + 4, col=(.84, .73, .54), h=1.4)    # keystone
            sash(cv, rg, wx0, wy0, wx1, wy1, frame=(.88, .86, .8), lit_p=.35)
            cv.rect(wx0 - 16, wy1 + 4, wx1 + 16, wy1 + 14, col=(.8, .69, .5), h=1.3)
        cv.rect(0, y0 + ch - 20, W, y0 + ch - 6, col=(.8, .7, .52), h=1.2)                       # belt course
        cv.rect(0, y0 + ch - 6, W, y0 + ch - 3, col=(.45, .37, .26), h=.3)
    grime(cv, 63, .22, .3)
    cv.save('dt_stone', strength=2.4, nsize=(512, 512))


# ---------------------------------------------------------------- derelict: boarded / broken windows, faded paint, grime
def derelict():
    W, H, B, F = 1024, 1024, 4, 4
    cw, ch = W // B, H // F
    cv = Canvas(W, H)
    brickfield(cv, 0, 0, W, H, (.4, .25, .19), 71, mortar=(.45, .42, .38))
    # remains of an old painted coat, flaking
    paint = noise(H, W, 1.5, 72)
    pm = paint > .52
    cv.c[pm] = cv.c[pm] * .35 + np.array((.36, .34, .3), np.float32) * .65
    cv.hg[pm] += .3
    rg = np.random.RandomState(73)
    for f in range(F):
        y0 = f * ch
        for b in range(B):
            x0 = b * cw
            wx0, wx1 = x0 + int(cw * .27), x0 + int(cw * .73)
            wy0, wy1 = y0 + int(ch * .18), y0 + int(ch * .84)
            cv.rect(wx0 - 9, wy0 - 14, wx1 + 9, wy0 - 2, col=(.42, .4, .36), h=.4)
            cv.rect(wx0 - 8, wy1, wx1 + 8, wy1 + 8, col=(.42, .4, .36), h=.6)
            k = rg.rand()
            if k < .5:      # plywood boarding with grain, weathered grey, nails
                base = jitter(rg, (.55, .42, .27), .15) if rg.rand() < .6 else jitter(rg, (.42, .4, .36), .1)
                g = noise(wy1 - wy0, wx1 - wx0, 1.2, int(rg.randint(9999)), ax=.15, ay=4)
                cv.rect(wx0, wy0, wx1, wy1, h=.5, rough=.9)
                cv.c[wy0:wy1, wx0:wx1] = np.array(base, np.float32) * (.8 + .35 * g)[..., None]
                for yy in (wy0 + 6, (wy0 + wy1) // 2, wy1 - 6):
                    for xx in (wx0 + 5, wx1 - 6):
                        cv.rect(xx, yy, xx + 2, yy + 2, col=(.2, .18, .16))
                cv.rect(wx0, (wy0 + wy1) // 2 - 1, wx1, (wy0 + wy1) // 2 + 1, col=tuple(c * .6 for c in base), h=.2)
            else:
                cv.rect(wx0, wy0, wx1, wy1, col=(.3, .28, .25), h=-.2, rough=.7)
                cv.rect(wx0 + 5, wy0 + 5, wx1 - 5, wy1 - 5, col=(.03, .03, .035), h=-1, rough=.2, metal=.3)
                if k < .8:  # broken panes: jagged shards left in the frame
                    hh, ww = wy1 - wy0 - 10, wx1 - wx0 - 10
                    yy, xx = np.mgrid[0:hh, 0:ww]
                    cx, cy = rg.uniform(.3, .7) * ww, rg.uniform(.3, .7) * hh
                    ang = np.arctan2(yy - cy, xx - cx)
                    rad = np.hypot(yy - cy, xx - cx)
                    ph = rg.rand(3) * 6
                    edge = (.62 + .2 * np.sin(ang * 2 + ph[0]) + .12 * np.sin(ang * 5 + ph[1]) + .06 * np.sign(np.sin(ang * 11 + ph[2]))) * max(hh, ww) * .5
                    shard = rad > edge
                    sub = cv.c[wy0 + 5:wy0 + 5 + hh, wx0 + 5:wx0 + 5 + ww]
                    sub[shard] = np.array((.16, .18, .19), np.float32)
                    cv.r[wy0 + 5:wy0 + 5 + hh, wx0 + 5:wx0 + 5 + ww][shard] = .1
                else:
                    cv.rect(wx0 + 5, wy0 + 5, wx1 - 5, wy1 - 5, col=(.12, .13, .12), rough=.3, metal=.2)
    # rust streaks and heavy grime, abstract spray marks on the bottom floor of the tile
    s = noise(H, W, 1.2, 74, ax=10, ay=.25)
    cv.c *= (1 - .4 * np.clip((s - .45) * 2.2, 0, 1))[..., None]
    rust = np.clip((noise(H, W, 1.2, 75, ax=10, ay=.3) - .62) * 3, 0, 1)
    cv.c = cv.c * (1 - rust[..., None] * .5) + np.array((.35, .17, .07), np.float32) * rust[..., None] * .5
    yy, xx = np.mgrid[0:H, 0:W]
    for k in range(9):
        cx, cy = rg.uniform(0, W), rg.uniform(H - ch * .8, H - 10)
        col = np.array([(.8, .2, .3), (.2, .5, .8), (.9, .7, .1), (.2, .7, .4), (.9, .9, .9)][k % 5], np.float32)
        for t in range(14):
            px, py = cx + math.sin(t * .7 + k) * 40 + t * 6, cy + math.cos(t * .9 + k * 2) * 20
            m = (xx - px) ** 2 + (yy - py) ** 2 < 36
            cv.c[m] = cv.c[m] * .2 + col * .8
    grime(cv, 76, .4, .3)
    cv.c *= .85
    cv.r = np.clip(cv.r + .05, 0, 1)
    cv.lit[:] = 0
    cv.save('dt_derelict', strength=2.2, nsize=(512, 512))


# ---------------------------------------------------------------- ground-floor shopfronts: 8 bays of 5 m, one 5 m storey
SHOPS = ['CAFE', 'BOOKS', 'BAKERY', 'FLOWERS', 'DELI', 'NOODLES', 'OPTICIAN', 'RECORDS', 'TAILOR', 'GALLERY', 'PHARMACY', 'SHOES']


def shopfront():
    W, H, B = 2048, 256, 8
    cw = W // B
    cv = Canvas(W, H, (.2, .2, .21), .5, .5)
    rg = np.random.RandomState(81)
    signs = [(.12, .2, .16), (.55, .12, .1), (.1, .14, .25), (.85, .82, .74), (.15, .15, .16), (.6, .45, .15), (.25, .1, .2), (.1, .3, .32)]
    im = Image.new('RGB', (W, H)); dr = ImageDraw.Draw(im)
    names = list(SHOPS); rg.shuffle(names)
    for b in range(B):
        x0 = b * cw
        sc = signs[b % len(signs)]
        sign_h = 46
        cv.rect(x0, 0, x0 + cw, sign_h, col=sc, h=.6, rough=.4, metal=.2)
        cv.rect(x0, sign_h, x0 + cw, sign_h + 5, col=(.12, .12, .12), h=.8)
        # glazing: frame colour per shop (timber or aluminium)
        fr = (.75, .76, .78) if b % 3 == 0 else jitter(rg, sc, .1)
        cv.rect(x0, sign_h + 5, x0 + cw, H, col=fr, h=.3, rough=.45, metal=.6 if b % 3 == 0 else .1)
        gx0, gx1, gy0, gy1 = x0 + 8, x0 + cw - 8, sign_h + 12, H - 26
        door = rg.randint(2)
        # interior: warm light, shelves / tables / racks as coloured blobs
        cv.rect(gx0, gy0, gx1, gy1, col=(.55, .45, .32), h=-.8, rough=.05, metal=.3, lit=.8)
        inner = cv.c[gy0:gy1, gx0:gx1]
        ih, iw = inner.shape[:2]
        for s in range(3):
            yy = int(ih * (.35 + s * .2))
            inner[yy:yy + 3] *= .5
        for k in range(18):
            px, py = rg.randint(0, iw - 12), rg.randint(int(ih * .3), ih - 8)
            inner[py:py + rg.randint(6, 18), px:px + rg.randint(5, 14)] = jitter(rg, [(.7, .2, .2), (.2, .4, .7), (.9, .8, .3), (.3, .6, .3), (.85, .85, .8)][k % 5], .2)
        inner[:8] = (.9, .85, .7)                     # ceiling glow
        dx = gx0 + (8 if door == 0 else cw - 16 - 60)
        cv.rect(dx, gy0, dx + 60, H - 6, col=(.3, .26, .2), h=-.6, rough=.08, lit=.6)          # door glazing
        cv.rect(dx + 28, gy0, dx + 32, H - 6, col=fr, h=.3)
        mx = gx0 + (cw - 16) // 2
        cv.rect(mx - 2, gy0, mx + 2, gy1, col=fr, h=.3)
        cv.rect(x0, gy1, x0 + cw, H, col=tuple(c * .7 for c in fr), h=.4, rough=.5)               # kickplate
        if dx > gx0 + 20 or True:
            cv.rect(dx, gy1, dx + 60, H - 4, col=(.3, .26, .2), h=-.6, rough=.08, lit=.5)
        cv.rect(x0, 0, x0 + 3, H, col=(.15, .15, .16), h=1)                                      # pier between shops
        # sign lettering (fictional generic words)
        name = names[b % len(names)]
        f = font(30)
        tw = dr.textlength(name, font=f)
        light = sum(sc) / 3 > .5
        dr.rectangle([x0, 0, x0 + cw, sign_h], fill=(0, 0, 0))
        dr.text((x0 + cw / 2 - tw / 2, 6), name, font=f, fill=(255, 255, 255))
    txt = np.asarray(im, np.float32)[..., 0] / 255
    for b in range(B):
        x0 = b * cw; sc = signs[b % len(signs)]
        light = sum(sc) / 3 > .5
        t = txt[:46, x0:x0 + cw]
        tc = np.array((.12, .12, .12) if light else (.98, .92, .78), np.float32)
        cv.c[:46, x0:x0 + cw] = cv.c[:46, x0:x0 + cw] * (1 - t[..., None]) + tc * t[..., None]
        cv.lit[:46, x0:x0 + cw] = np.maximum(cv.lit[:46, x0:x0 + cw], t * (0 if light else .9))
        cv.hg[:46, x0:x0 + cw] += t * .6
    grime(cv, 82, .1, .1)
    cv.save('dt_shop', strength=2.0, nsize=(1024, 128))


# ---------------------------------------------------------------- roof membrane + gravel, raw concrete, pavers
def roof():
    W = 512
    cv = Canvas(W, W, (.42, .42, .41), .9, 0)
    g = noise(W, W, .3, 91); cv.c *= (.8 + .4 * g)[..., None]; cv.hg = g * .6
    big = noise(W, W, 1.8, 92); cv.c *= (.85 + .25 * big)[..., None]
    for k in range(0, W, 128):
        cv.rect(0, k, W, k + 3, col=(.3, .3, .3), h=.8)
    cv.save('dt_roof', strength=1.5, aux=False)


def rawconc():
    W = 512
    cv = Canvas(W, W, (.62, .6, .56), .85, 0)
    n = noise(W, W, 1.5, 101); cv.c *= (.85 + .25 * n)[..., None]
    board = noise(W, W, 1.0, 102, ax=.1, ay=6)
    cv.c *= (.92 + .12 * board)[..., None]; cv.hg = board * .4
    for y in range(0, W, 32):
        cv.rect(0, y, W, y + 1, col=(.5, .48, .45), h=-.3)
    for y in range(64, W, 128):
        for x in range(64, W, 128):
            cv.rect(x - 3, y - 3, x + 3, y + 3, col=(.3, .3, .3), h=-1)
    cv.save('dt_rawconc', strength=1.5, aux=False)


def pavers():
    W = 1024                                     # 6 m tile: 0.6 x 0.3 m granite setts in running bond, two tones
    cv = Canvas(W, W, (.6, .58, .55), .75, 0)
    rg = np.random.RandomState(111)
    yy, xx = np.mgrid[0:W, 0:W]
    bh, bw = W // 20, W // 10
    row = yy // bh
    xs = xx + (row % 2) * (bw // 2)
    ids = (row * 131 + xs // bw * 7) % 991
    tone = rg.uniform(.85, 1.12, 991).astype(np.float32)[ids]
    dark = (rg.rand(991) < .18)[ids]
    speck = noise(W, W, .2, 112)
    cv.c *= (tone * (.9 + .2 * speck))[..., None]
    cv.c[dark] *= np.array((.62, .62, .66), np.float32)
    j = ((yy % bh) < 2) | ((xs % bw) < 2)
    cv.c[j] = (.3, .29, .28); cv.hg = np.where(j, -1, 0).astype(np.float32) + speck * .2
    grime(cv, 113, .2, 0)
    cv.save('dt_pavers', strength=2.0, aux=False, nsize=(512, 512))


def hoarding():
    W, H = 1024, 256                             # 8 m x 2 m: painted plywood panels with a mural strip and a warning band
    cv = Canvas(W, H, (.12, .22, .2), .85, 0)
    rg = np.random.RandomState(121)
    yy, xx = np.mgrid[0:H, 0:W]
    # abstract city mural: overlapping tower silhouettes in a few tones
    for k in range(26):
        x0 = rg.randint(0, W); w = rg.randint(20, 70); h = rg.randint(50, 190)
        col = np.array([(.85, .6, .25), (.2, .45, .55), (.9, .85, .75), (.35, .55, .4), (.7, .3, .25)][k % 5], np.float32)
        m = (((xx - x0) % W) < w) & (yy > H - 30 - h) & (yy < H - 30)
        cv.c[m] = cv.c[m] * .15 + col * .85
    cv.rect(0, H - 30, W, H - 18, col=(.95, .75, .1))
    for x in range(0, W, 24):
        cv.rect(x, H - 30, x + 12, H - 18, col=(.08, .08, .08))
    cv.rect(0, H - 18, W, H, col=(.1, .1, .1))
    for x in range(0, W, 128):
        cv.rect(x, 0, x + 2, H, col=(.05, .05, .05), h=-1)
    grime(cv, 122, .15, .2)
    cv.save('dt_hoarding', strength=1.5, aux=False, nsize=(512, 128))


def awning():
    W = 256
    cv = Canvas(W, W, (.92, .9, .85), .9, 0)
    for x in range(0, W, 64):
        cv.rect(x, 0, x + 32, W, col=(.5, .5, .5))
    cv.c *= (.9 + .15 * noise(W, W, 1.0, 131))[..., None]
    cv.save('dt_awning', normal=False, aux=False)


def save_rgba(name, rgb, a):
    arr = np.dstack([rgb, a[..., None]])
    Image.fromarray(np.clip(arr * 255 + .5, 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, name + '.png'))
    print('[texture] %s.png' % name)


def lattice():
    S = 256                                      # one square truss bay: chords, a rung and a diagonal
    yy, xx = (np.mgrid[0:S, 0:S] + .5) / S
    t = .07
    a = (xx < t) | (xx > 1 - t) | (yy < t * .7) | (np.abs(xx - yy) < t * .55)
    rgb = np.ones((S, S, 3), np.float32) * .95
    edge = (xx < t * .3) | (xx > 1 - t * .3)
    rgb[edge] *= .7
    save_rgba('dt_lattice', rgb, a.astype(np.float32))


def net():
    S = 256
    yy, xx = np.mgrid[0:S, 0:S]
    a = np.full((S, S), .55, np.float32)
    a[(xx % 8 < 2) | (yy % 8 < 2)] = .9
    a *= .85 + .15 * noise(S, S, 1.5, 141)
    rgb = np.ones((S, S, 3), np.float32) * .9
    save_rgba('dt_net', rgb, a)


def main():
    curtain(); ribbon(); precast(); punched(); brick(); stone(); derelict(); shopfront()
    roof(); rawconc(); pavers(); hoarding(); awning(); lattice(); net()


if __name__ == '__main__':
    main()
