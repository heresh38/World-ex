"""Our own skin textures for the naked base characters, written from maps baked off the body (basemesh_finish.py):
the surface position and normal per texel, the occlusion. Everything is a function of the 3D position on the body
(noise in space, landmarks from the anatomical target), so nothing shows at a UV seam.

  base colour   the sex's skin tone; mottling at three scales; blood near the surface on the cheeks, nose, ears, chin,
                knuckles, elbows, knees, heels and finger tips; lighter, pinker palms and soles; the lips; the areolae;
                a cooler shade round the eyes and (his) where the beard grows; the wet rims of the lids; a few moles
  roughness     skin about .46: oilier down the forehead and nose, wet lips and lid rims, drier joints, palms and soles
  normal        (tangent space, OpenGL: +Y up) from a height field: pores and the skin's fine weave, the lips' vertical
                lines, creases across the finger joints, the nipples
  subsurface    how far light gets in: thin ears, nose and fingers high, the scalp and joints lower

Also the eye's texture (sclera with veins, limbal ring, iris fibres, pupil), a front projection.
"""
import numpy as np

F32 = np.float32


# ------------------------------------------------------------------------------------------------ noise in space
def _hash(ix, iy, iz, seed):
    h = (ix * 374761393 + iy * 668265263 + iz * 2147483647 + seed * 974711) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFF).astype(F32) / F32(65535.0)


def vnoise(P, wavelength, seed=0):
    """value noise in [0, 1] at the points P (n, 3)"""
    q = P / F32(wavelength)
    i = np.floor(q).astype(np.int64)
    f = (q - i).astype(F32)
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(P), F32)
    for dx in (0, 1):
        wx = f[:, 0] if dx else 1 - f[:, 0]
        for dy in (0, 1):
            wy = f[:, 1] if dy else 1 - f[:, 1]
            for dz in (0, 1):
                wz = f[:, 2] if dz else 1 - f[:, 2]
                out += _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed) * wx * wy * wz
    return out


def fbm(P, wavelength, octaves=3, seed=0):
    out = np.zeros(len(P), F32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        out += vnoise(P, wavelength / 2 ** o, seed + o * 17) * amp
        tot += amp; amp *= .5
    return out / tot


def worley(P, cell, seed=0):
    """distance to the nearest feature point (cells of size `cell`), in cells: 0 at a point, ~.6 between"""
    q = P / F32(cell)
    i = np.floor(q).astype(np.int64)
    best = np.full(len(P), 9.0, F32)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cx, cy, cz = i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz
                px = cx + _hash(cx, cy, cz, seed); py = cy + _hash(cx, cy, cz, seed + 1); pz = cz + _hash(cx, cy, cz, seed + 2)
                d = np.sqrt((q[:, 0] - px) ** 2 + (q[:, 1] - py) ** 2 + (q[:, 2] - pz) ** 2)
                best = np.minimum(best, d)
    return best


def g3(P, c, r):
    """gaussian weight round c with radii r (scalar or 3)"""
    q = (P - np.asarray(c, F32)) / np.asarray(r, F32)
    return np.exp(-(q * q).sum(1))


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def seg(P, a, b):
    a, b = np.asarray(a, F32), np.asarray(b, F32)
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1), t


def mix(col, target, w):
    return col + (np.asarray(target, F32) - col) * w[:, None]


# ------------------------------------------------------------------------------------------------ the skin
def skin(Pm, Nm, AO, mask, L, male, log=print):
    """Pm, Nm: (h, w, 3) position / normal maps; AO (h, w); mask (h, w) bool; L: landmarks (basemesh_finish.landmarks).
    Returns base colour (linear rgb), roughness, tangent normal, subsurface: full images, unpadded."""
    h, w = mask.shape
    idx = np.where(mask.ravel())[0]
    P = Pm.reshape(-1, 3)[idx].astype(F32)
    N = Nm.reshape(-1, 3)[idx].astype(F32)
    Pa = P.copy(); Pa[:, 0] = np.abs(Pa[:, 0])                      # (the body is symmetric: landmarks on the left)
    n = len(P)
    log(f"skin maps: {n} texels")
    head_w = sstep(L["neck_z"] - .03, L["neck_z"] + .03, P[:, 2])   # 1 on the head
    ec = np.array(L["eye"], F32); st = np.array(L["stomion"], F32)
    hs = L["hs"]
    # ---- base colour
    tone = np.array((.47, .295, .215) if male else (.54, .355, .275), F32)
    col = np.tile(tone, (n, 1))
    m1 = fbm(P, .045, 3, 11) - .5; m2 = fbm(P, .009, 2, 23) - .5; m3 = vnoise(P, .0022, 37) - .5
    col *= (1 + .10 * m1 + .07 * m2 + .05 * m3)[:, None]
    col = mix(col, tone * np.array((1.10, .93, .88), F32), np.clip(m1 * 2.2 + m2 * 1.4, 0, 1) * .5)      # warmer patches
    col = mix(col, tone * np.array((.97, 1.0, .95), F32), np.clip(-m1 * 2.2, 0, 1) * .35)               # sallower ones
    red = np.zeros(n, F32)
    red += .55 * g3(Pa, L["cheek"], (.024 * hs, .020 * hs, .022 * hs))
    red += .50 * g3(Pa, L["nose_tip"], (.014, .012, .012)) + .30 * g3(Pa, L["alar"], .010)
    red += .55 * g3(Pa, L["ear"], (.012, .020, .030))
    red += .22 * g3(Pa, L["chin"], (.020, .014, .014))
    for c in L["knuckles"]:
        red += .40 * g3(Pa, c, .011)
    for c in L["fingertips"]:
        red += .40 * g3(Pa, c, .012)
    red += .38 * g3(Pa, L["elbow"], .038) + .34 * g3(Pa, L["knee"], (.045, .040, .050)) + .30 * g3(Pa, L["heel"], .040)
    red = np.clip(red * (.8 + .5 * (m2 + .5)), 0, 1)
    col = mix(col, tone * np.array((1.22, .74, .72), F32), red * .85)
    col = mix(col, tone * np.array((1.05, 1.02, .88), F32), g3(Pa, L["forehead"], (.05, .03, .03)) * .22)   # the forehead's yellow
    # palms and soles: less pigment
    palm = np.clip((N * np.asarray(L["palm_n"], F32)).sum(1) * np.where(P[:, 0:1] > 0, 1, 1)[:, 0], 0, 1)   # (normal toward the palm side)
    pn = np.asarray(L["palm_n"], F32).copy()
    Nm_ = N.copy(); Nm_[:, 0] *= np.sign(P[:, 0] + 1e-9)             # mirror the right side's normals onto the left
    palm = sstep(.15, .6, Nm_ @ pn) * g3(Pa, L["palm"], (.075, .075, .075)) ** .35 * (seg(Pa, L["wrist"], L["midtip"])[0] < .06)
    sole = sstep(-.5, -.85, N[:, 2]) * (P[:, 2] < .05)
    col = mix(col, tone * np.array((1.22, 1.06, 1.02), F32), np.clip(palm + sole, 0, 1) * .55)
    # the eyes' surround, cooler and a little darker; his beard's shade
    orb = g3(Pa, ec + np.array((0, -.010, -.004), F32), (.020 * hs, .014, .013 * hs))
    col = mix(col, col * np.array((.86, .82, .88), F32), orb * .55)
    if male:
        # where the beard grows: the upper lip, chin, jaw and under it (never the lips themselves)
        zc = (P[:, 2] - L["chin_z"]) / hs
        yy = (P[:, 1] - L["y0"]) / hs
        beard = sstep(.070, .050, zc) * sstep(-.030, -.005, zc) * sstep(.035, .0, yy) * head_w
        beard *= sstep(.012, .030, np.abs(zc - .050) + np.abs(Pa[:, 0] / hs) * .0 + (np.abs(Pa[:, 0]) / hs > .028) * .03)
        st_ = (.55 + .9 * vnoise(P, .0009, 71))
        col = mix(col, col * np.array((.80, .80, .84), F32), np.clip(beard * .42 * st_, 0, 1))
    # the lips: the vermilion, its bow, a darker line where they meet
    dx = (P[:, 0] - st[0]) / (L["mouth_w"] * .5)
    dz = P[:, 2] - st[2]
    bow = .0012 * hs * np.exp(-(dx / .22) ** 2) - .0016 * hs * np.exp(-(dx / .08) ** 2)                # the upper edge's bow
    up_h = (L["lip_up"] * (1 - np.abs(dx) ** 2.2).clip(0) ** .7) + bow
    lo_h = L["lip_lo"] * (1 - np.abs(dx) ** 2.0).clip(0) ** .6
    lipm = np.where(dz >= 0, sstep(1.10, .78, dz / np.maximum(up_h, 1e-5)), sstep(1.10, .80, -dz / np.maximum(lo_h, 1e-5)))
    lipm = lipm * (np.abs(dx) < 1.02) * sstep(.035, .012, P[:, 1] - st[1]) * head_w
    lipc = np.array((.40, .185, .170) if male else (.50, .165, .175), F32)
    lipc = lipc * (1 + .16 * (vnoise(P, .0016, 91) - .5))[:, None]
    col = col + (lipc - col) * (lipm * (.80 if male else .92))[:, None]
    col *= (1 - .30 * lipm * np.exp(-(dz / .0011) ** 2))[:, None]
    # the areolae and nipples
    ar = sstep(1.0, .72, np.linalg.norm((Pa - np.asarray(L["nipple"], F32)) * np.array((1, .35, 1), F32), axis=1) / L["areola_r"])
    col = mix(col, tone * np.array((.80, .52, .50), F32) * (1 + .2 * (vnoise(P, .0018, 55) - .5))[:, None], ar * .85)
    # the lids' wet rims and the corners' flesh (the socket's wall behind the lid margins)
    de = np.linalg.norm(Pa - ec, axis=1)
    wet = sstep(L["eye_r"] + .0026, L["eye_r"] + .0010, de)
    col = mix(col, np.array((.52, .22, .20), F32), wet * .85)
    # a few moles and freckles
    mo = worley(P, .090, 5)
    col *= (1 - .40 * sstep(.016, .007, mo))[:, None]
    fr = sstep(.62, .80, vnoise(P, .0035, 77)) * sstep(.55, .75, vnoise(P, .05, 78)) * .10
    col *= (1 - fr)[:, None]
    # the ear's folds (helix, antihelix and its two crura, scapha, concha, antitragus): the base mesh carries the
    # auricle's outline, rim and bowl; the fine form is the difference between the detailed ear and the one the mesh
    # was fitted to, taken at each texel: it goes into the normal map as height and shades the hollows
    ear_h = np.zeros(n, F32)
    if L.get("detail_fn") is not None:
        sel = np.where(np.linalg.norm(Pa - np.asarray(L["ear"], F32), axis=1) < .055)[0]
        if len(sel):
            ear_h[sel] = L["detail_fn"](Pa[sel])
            col[sel] *= (1 - .42 * np.clip(-ear_h[sel] / .0022, 0, 1))[:, None]
            col[sel] = mix(col[sel], col[sel] * np.array((1.10, .90, .86), F32), np.clip(-ear_h[sel] / .0022, 0, 1) * .5)
    # occlusion: creases a touch darker and redder
    ao = AO.ravel()[idx]
    cav = np.clip(1 - ao, 0, 1) ** 1.2
    col = col * (1 - .32 * cav)[:, None] * (1 + np.array((.05, -.03, -.04), F32) * cav[:, None])
    col = np.clip(col, 0, 1)
    # ---- roughness
    rough = np.full(n, .54, F32) + .08 * m2 + .06 * m3
    tz = g3(Pa, L["forehead"], (.035, .03, .035)) + g3(Pa, L["nose_tip"], (.016, .03, .03))
    rough -= .10 * np.clip(tz, 0, 1) * head_w
    rough += .10 * (g3(Pa, L["elbow"], .04) + g3(Pa, L["knee"], .05)) + .08 * np.clip(palm + sole, 0, 1)
    rough = rough + (.36 - rough) * lipm * .9
    rough = rough + (.12 - rough) * wet
    rough = np.clip(rough, .08, .95)
    # ---- subsurface
    sss = np.full(n, .55, F32)
    sss += .40 * g3(Pa, L["ear"], (.012, .022, .032)) + .25 * g3(Pa, L["nose_tip"], .016) + .20 * lipm
    for c in L["fingertips"]:
        sss += .2 * g3(Pa, c, .02)
    sss = np.clip(sss, 0, 1)
    # ---- height (metres): pores, the weave, lip lines, joint creases, nipples
    pore = worley(P, .0011, 3)
    hgt = -.000090 * sstep(.38, .05, pore) * (1 - lipm) * (1 - wet)
    hgt += .000070 * (vnoise(P, .0019, 41) - .5) + .000110 * (fbm(P, .0050, 2, 43) - .5)
    wv = worley(P, .0034, 9)
    hgt += -.000070 * sstep(.52, .70, wv)                                               # the weave's furrows
    lines = np.abs(np.sin((P[:, 0] - st[0]) * 2600 + 5 * vnoise(P, .004, 12)))
    hgt += -.00012 * lipm * (1 - lines) ** 3
    for a_, b_, wd in L["joint_lines"]:                                                # across each finger joint
        dj, tj = seg(Pa, a_, b_)
        ax = np.asarray(b_, F32) - np.asarray(a_, F32); ax /= max(float(np.linalg.norm(ax)), 1e-9)
        s_ = (Pa - np.asarray(a_, F32)) @ ax
        mj = (dj < wd) * np.exp(-((tj - .5) / .28) ** 2) * sstep(.1, .5, Nm_ @ np.asarray(L["dorsal"], F32))
        hgt += -.00010 * mj * np.abs(np.sin(s_ * 2300)) ** 4
    hgt += ear_h
    dn = np.linalg.norm(Pa - np.asarray(L["nipple"], F32), axis=1)
    hgt += L["nipple_h"] * np.exp(-(dn / L["nipple_r"]) ** 2) + .00025 * sstep(L["areola_r"], L["areola_r"] * .6, dn) * (vnoise(P, .0016, 61) - .3)
    if male:
        hgt += .00005 * beard * sstep(.55, .75, vnoise(P, .0007, 71))                   # stubble
    out = {}
    for name, arr, ch in (("col", col, 3), ("rough", rough, 1), ("sss", sss, 1), ("hgt", hgt, 1)):
        img = np.zeros((h * w, ch), F32)
        img[idx] = arr.reshape(n, ch)
        out[name] = img.reshape(h, w, ch) if ch > 1 else img.reshape(h, w)
    out["normal"] = height_to_normal(out["hgt"], Pm, mask)
    return out


def height_to_normal(hgt, Pm, mask):
    """tangent-space normal (x along +u, y along +v, z out) from a height field in metres and the position map"""
    h, w = mask.shape
    nx = np.zeros((h, w), F32); ny = np.zeros((h, w), F32)
    # along u (columns)
    ok = mask[:, 2:] & mask[:, :-2] & mask[:, 1:-1]
    du = np.linalg.norm(Pm[:, 2:] - Pm[:, :-2], axis=2)
    dh = hgt[:, 2:] - hgt[:, :-2]
    nx[:, 1:-1] = np.where(ok & (du > 1e-7), -dh / np.maximum(du, 1e-7), 0)
    ok = mask[2:] & mask[:-2] & mask[1:-1]
    dv = np.linalg.norm(Pm[2:] - Pm[:-2], axis=2)
    dh = hgt[2:] - hgt[:-2]
    ny[1:-1] = np.where(ok & (dv > 1e-7), -dh / np.maximum(dv, 1e-7), 0)
    nx = np.clip(nx, -1.5, 1.5); ny = np.clip(ny, -1.5, 1.5)
    nz = np.ones((h, w), F32)
    ln = np.sqrt(nx * nx + ny * ny + 1)
    return np.stack([nx / ln, ny / ln, nz / ln], 2)


def pad(img, mask, steps=12):
    """bleeds the islands outward (so mip-maps and bilinear lookups never pick up the background)"""
    img = img.copy(); m = mask.copy()
    for _ in range(steps):
        acc = np.zeros_like(img); cnt = np.zeros(m.shape, F32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = np.roll(m, (dy, dx), (0, 1)); si = np.roll(img, (dy, dx), (0, 1))
            acc += si * (sm[..., None] if img.ndim == 3 else sm); cnt += sm
        new = (~m) & (cnt > 0)
        if img.ndim == 3:
            img[new] = acc[new] / cnt[new][:, None]
        else:
            img[new] = acc[new] / cnt[new]
        m = m | new
    return img


# ------------------------------------------------------------------------------------------------ the eye
def eye_texture(size, iris_rgb, seed=1):
    """front projection of the eyeball (uv .5,.5 = the pupil's centre; the image spans the globe's diameter)"""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(F32)
    u = (x + .5) / size * 2 - 1; v = (y + .5) / size * 2 - 1
    r = np.sqrt(u * u + v * v); a = np.arctan2(v, u)
    P2 = np.stack([u.ravel(), v.ravel(), np.zeros(size * size, F32)], 1)
    # sclera: warm white, pinker and veined toward the rim
    scl = np.array((.66, .635, .60), F32) * np.ones((size, size, 3), F32)
    scl = scl * (1 - .10 * (fbm(P2, .5, 3, 3).reshape(size, size) - .5))[..., None]
    edge = sstep(.45, 1.0, r)
    scl = scl + (np.array((.60, .40, .37), F32) - scl) * (edge * .45)[..., None]
    ang = a + 1.2 * (fbm(P2, .35, 3, 5).reshape(size, size) - .5)
    veins = np.abs(np.sin(ang * 9 + 3 * fbm(P2, .22, 2, 9).reshape(size, size))) ** 26 * sstep(.36, .9, r)
    veins += np.abs(np.sin(ang * 23 + 7 * fbm(P2, .12, 2, 19).reshape(size, size))) ** 40 * sstep(.5, .95, r) * .6
    scl = scl + (np.array((.62, .16, .14), F32) - scl) * np.clip(veins * .55, 0, 1)[..., None]
    # iris: fibres from the pupil, a darker ring at the rim (limbus), a lighter collarette
    ir = .485; pr = .165
    t = np.clip((r - pr) / (ir - pr), 0, 1)
    base = np.asarray(iris_rgb, F32)
    fib = fbm(np.stack([(a * 14).ravel(), (r * 3).ravel(), np.zeros(size * size, F32)], 1), 1.0, 4, 31).reshape(size, size)
    fib2 = fbm(np.stack([(a * 40).ravel(), (r * 6).ravel(), np.zeros(size * size, F32)], 1), 1.0, 3, 47).reshape(size, size)
    iris = base[None, None, :] * (.55 + 1.1 * fib * (.6 + .4 * fib2))[..., None]
    iris = iris + (base * np.array((1.9, 1.5, 1.0), F32) - iris) * (np.exp(-((t - .28) / .12) ** 2) * .22)[..., None]   # collarette
    iris = iris * (1 - .75 * sstep(.80, 1.0, t))[..., None] * (1 - .35 * sstep(.25, 0, t))[..., None]
    img = scl
    wi = sstep(ir + .012, ir - .012, r)
    img = img + (iris - img) * wi[..., None]
    img = img * (1 - .35 * np.exp(-((r - ir) / .03) ** 2))[..., None]                                    # the limbal ring
    wp = sstep(pr + .006, pr - .006, r)
    img = img * (1 - wp)[..., None] + np.array((.004, .004, .005), F32) * wp[..., None]
    return np.clip(img, 0, 1)
