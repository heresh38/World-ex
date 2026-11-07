"""Face skin maps for the players, baked from the head's own 3D surface (our procedural fields, no photo sources).

The head gets cylindrical UVs (seam at the back of the head, under the hair) and three 2048x1024 maps:
  face_<sex>_c.jpg  colour (multiplied by the runtime skin tint): lips, warm cheeks / nose / ears, under-eye tone,
                    lash line, mottling, pores, and on the male face the beard and moustache shadow with stubble
  face_<sex>_n.png  tangent-space normal (OpenGL, +Y = +v): pores (bigger on the nose and cheeks), lip lines, faint
                    forehead lines and crow's feet
  face_<sex>_m.png  glTF metallic-roughness: G roughness (oilier T-zone, glossy lips), B metal 0
Every field is evaluated in head space (metres), so nothing tears at the UV seam.
"""
import math, os
import numpy as np
import bpy
import bl, sdf

F32 = np.float32
W, H = 2048, 1024


# ---------------------------------------------------------------- noise
def _hash(ix, iy, iz):
    h = (ix * 374761393 + iy * 668265263 + iz * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF).astype(F32) / 65535.0


def vnoise(P, freq):
    """Trilinear value noise in [0, 1] at points P (n, 3) metres, cells of 1/freq."""
    Q = P * freq
    i = np.floor(Q).astype(np.int64); f = Q - i
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(P), F32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz)
    return out


def fbm(P, freq, octaves=4):
    a, t, n = 1.0, 0.0, 0.0
    for k in range(octaves):
        t += a * vnoise(P + k * 17.3, freq * 2 ** k); n += a; a *= .5
    return t / n


def ss(a, b, x):
    return sdf.smoothstep(a, b, x)


# ---------------------------------------------------------------- UVs and rasterisation
def cylinder_uv(o, head_o, zr):
    """Per-loop cylindrical UVs: u around the head (front = .5, seam behind), v up over zr = (z0, z1)."""
    me = o.data
    V = np.array([v.co[:] for v in me.vertices], F32) - head_o
    th = np.arctan2(V[:, 0], -V[:, 1])                    # 0 at the front
    u_v = .5 + th / (2 * math.pi)
    v_v = (V[:, 2] - zr[0]) / (zr[1] - zr[0])
    uvl = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
    me.uv_layers.active = uvl
    li = np.array([l.vertex_index for l in me.loops])
    U = np.stack([u_v[li], v_v[li]], 1)
    # faces across the seam: lift the small u to u + 1 (the texture wraps)
    for poly in me.polygons:
        idx = list(poly.loop_indices)
        us = U[idx, 0]
        if us.max() - us.min() > .5:
            for k in idx:
                if U[k, 0] < .5:
                    U[k, 0] += 1.0
    uvl.data.foreach_set('uv', U.astype(F32).ravel())
    return U


def rasterise(o, head_o):
    """Head space position and normal for every covered texel (wrap in u)."""
    me = o.data
    me.calc_loop_triangles()
    uvl = me.uv_layers.active.data
    V = np.array([v.co[:] for v in me.vertices], F32) - head_o
    Nv = np.array([v.normal[:] for v in me.vertices], F32)
    pos = np.zeros((H, W, 3), F32); nor = np.zeros((H, W, 3), F32); cov = np.zeros((H, W), bool)
    for t in me.loop_triangles:
        uv = np.array([uvl[l].uv[:] for l in t.loops], F32) * [W, H]
        vi = list(t.vertices)
        x0, y0 = np.floor(uv.min(0)).astype(int); x1, y1 = np.ceil(uv.max(0)).astype(int)
        if x1 - x0 > W // 2 or y1 - y0 > H // 2:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        a, b, c = uv
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9:
            continue
        w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        w2 = 1 - w0 - w1
        inside = (w0 > -.02) & (w1 > -.02) & (w2 > -.02)
        if not inside.any():
            continue
        X = (xs[inside] - .5).astype(int) % W; Y = np.clip((ys[inside] - .5).astype(int), 0, H - 1)
        w = np.stack([w0[inside], w1[inside], w2[inside]], 1)
        pos[Y, X] = w @ V[vi]
        nor[Y, X] = w @ Nv[vi]
        cov[Y, X] = True
    n = np.linalg.norm(nor, axis=2, keepdims=True); nor = nor / np.maximum(n, 1e-6)
    return pos, nor, cov


def dilate(img, cov, it=12):
    """Bleed covered texels into the gutters (no dark seams in the mips)."""
    img = img.copy(); c = cov.copy()
    for _ in range(it):
        acc = np.zeros_like(img); cnt = np.zeros(c.shape, F32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sh = np.roll(np.roll(img, dy, 0), dx, 1); shc = np.roll(np.roll(c, dy, 0), dx, 1)
            acc += sh * shc[..., None] if img.ndim == 3 else sh * shc
            cnt += shc
        new = (~c) & (cnt > 0)
        if img.ndim == 3:
            img[new] = acc[new] / cnt[new][:, None]
        else:
            img[new] = acc[new] / cnt[new]
        c |= new
    return img


def save(name, rgb, srgb=True, jpg=False):
    im = bpy.data.images.new(name, W, H, alpha=False)
    if not srgb:
        im.colorspace_settings.name = 'Non-Color'
    px = np.ones((H, W, 4), F32); px[..., :3] = np.clip(rgb, 0, 1)
    im.pixels = px.ravel()
    ext = '.jpg' if jpg else '.png'
    im.filepath_raw = os.path.join(bl.TEXTURES, name + ext); im.file_format = 'JPEG' if jpg else 'PNG'
    if jpg:
        bpy.context.scene.render.image_settings.quality = 92
    im.save()
    return im


# ---------------------------------------------------------------- the maps
def bake_face(builder, o):
    B = builder.B; h = B.head; s = h.s; m = builder.sex == 'male'
    ho = np.asarray(B.head_o, F32)
    Vh = np.array([v.co[:] for v in o.data.vertices], F32) - ho
    zr = (float(Vh[:, 2].min()) - .002, float(Vh[:, 2].max()) + .002)
    cylinder_uv(o, ho, zr)
    pos, nor, cov = rasterise(o, ho)
    L = pos[cov]                                   # (n, 3) head space, metres
    n = len(L)
    x, y, z = L[:, 0], L[:, 1], L[:, 2]
    ax = np.abs(x)
    S = lambda v: np.asarray(v, F32) * s

    # --- regions (head design units x s, as anatomy.Head places the features)
    eyeL = h.eye
    def near_eye(dz0, dz1, w):
        e = np.zeros(n, F32)
        for sx in (1, -1):
            ex = eyeL[0] * sx
            e = np.maximum(e, np.exp(-((x - ex) / (w * s)) ** 2) * ss(dz0 * s, dz0 * s + .002, z - eyeL[2]) * ss(dz1 * s, dz1 * s - .002, z - eyeL[2]))
        return e
    front = ss(.02 * s, -.03 * s, y)               # the face side of the head
    lz = .002 if not m else 0.0
    full = 1.0 if m else 1.18; mw = (.0232 if not m else .0265)
    dy = -.013                                     # lips sit 13 mm forward of their first build (anatomy.Head)
    up = sdf.ellipsoid(L, S((0, -.0778 + dy, -.0458 + lz)), S((mw + .002, .0112, .0052 * full + .0016)))
    lo = sdf.ellipsoid(L, S((0, -.0758 + dy, -.0548 + lz)), S((mw * .82 + .002, .0116, .0066 * full + .0016)))
    lip = ss(.0022 * s, -.0012 * s, np.minimum(up, lo)).astype(F32)
    lip_edge = np.exp(-(np.minimum(up, lo) / (.0008 * s)) ** 2).astype(F32)
    cheeks = np.zeros(n, F32)
    for sx in (1, -1):
        cheeks += np.exp(-(sdf.length(L - S((sx * .042, -.07, -.016))) / (.022 * s)) ** 2)
    nose = np.exp(-(sdf.length(L - S((0, -.1, -.02))) / (.016 * s)) ** 2)
    ears = ss(.068 * s, .076 * s, ax) * ss(.03 * s, -.01 * s, y + .0) * (1 - front)
    under_eye = near_eye(-.016, -.004, .014)
    tzone = np.maximum(np.exp(-(ax / (.02 * s)) ** 2) * ss(.0, .02 * s, z - eyeL[2]) * ss(.09 * s, .06 * s, z - eyeL[2]), nose)
    # beard (male): jaw, chin, cheeks below the cheekbone line, moustache; never the lips. Soft, noisy edges that
    # follow the jaw (no straight cut lines)
    edge_n = (fbm(L, 140.0, 2) - .5) * .008 * s
    cheek_line = -.024 * s - .3 * np.maximum(ax - .028 * s, 0) + edge_n
    beard = (ss(.0, -.012 * s, z - cheek_line) * ss(.045 * s, -.005 * s, y + edge_n) * ss(.09 * s, .062 * s, ax + edge_n)).astype(F32)
    moust = (np.exp(-(ax / (.022 * s)) ** 2) * ss(-.049 * s, -.044 * s, z) * ss(-.033 * s, -.037 * s, z) * front).astype(F32)
    beard = np.clip(np.maximum(beard, moust) * (1 - ss(.0, .6, lip)) * (1 - ss(.0, .5, nose)), 0, 1) if m else np.zeros(n, F32)
    # lash line (upper lid edge darker)
    lash = np.zeros(n, F32)
    for sx in (1, -1):
        E = (eyeL * np.array([sx, 1, 1])).astype(F32)
        op = h.lid_opening(L, E)
        r = sdf.length(L - E)
        lash = np.maximum(lash, np.exp(-(op / (.0008 * s)) ** 2) * (r < h.eye_r + .003 * s) * (z > E[2] - .0005))

    # --- noise layers (head space: seamless)
    mott = fbm(L, 60.0, 3) - .5                     # blotches ~1-2 cm
    fine = fbm(L, 400.0, 2) - .5
    pore_freq = 820.0 + 300.0 * np.clip(cheeks + nose, 0, 1)
    pn = vnoise(L * (pore_freq / 820.0)[:, None], 820.0)
    pores = ss(.62, .82, pn) * (1 - lip) * (1 - .6 * ss(.0, .5, lash))
    stub = ss(.55, .8, vnoise(L, 1600.0)) * beard

    # --- colour (neutral: the game tints by skin tone)
    base = np.array([.93, .86, .82], F32)
    C = np.tile(base, (n, 1))
    C *= (1 + .045 * mott)[:, None]
    C += np.array([.02, -.01, -.012], F32) * (fine[:, None] * 2)
    warm = np.array([.94, .70, .68], F32)
    C = C * (1 - (cheeks * .16)[:, None]) + warm * (cheeks * .16)[:, None]
    C = C * (1 - (nose * .12)[:, None]) + warm * (nose * .12)[:, None]
    C = C * (1 - (ears * .14)[:, None]) + np.array([.92, .70, .66], F32) * (ears * .14)[:, None]
    C = C * (1 - (under_eye * .14)[:, None]) + np.array([.80, .70, .74], F32) * (under_eye * .14)[:, None]
    lipc = np.array([.88, .66, .64] if not m else [.86, .70, .67], F32)    # close to the skin, a little redder
    C = C * (1 - (lip * .8)[:, None]) + lipc * (lip * .8)[:, None]
    C *= (1 - .03 * lip_edge)[:, None]
    if m:
        shadow = np.array([.76, .74, .74], F32)
        k = (beard * .16 + stub * .2)[:, None]
        C = C * (1 - k) + shadow * C * k
    C *= (1 - .035 * pores)[:, None]
    C = C * (1 - (lash * .7)[:, None]) + np.array([.2, .14, .13], F32) * (lash * .7)[:, None]

    # --- height (mm) -> normal
    hgt = -.035 * pores
    hgt += .006 * (fine * 2)
    # lip lines (vertical grooves), forehead lines, crow's feet
    hgt += -.03 * lip * np.exp(-(np.sin(x / (.0018 * s) * math.pi) ** 2) / .08) * .5
    fz = z - eyeL[2]
    hgt += -.012 * front * np.exp(-(ax / (.04 * s)) ** 2) * ss(.03 * s, .045 * s, fz) * ss(.085 * s, .07 * s, fz) * \
        (np.sin(fz / (.0075 * s) * math.pi) ** 8)
    for sx in (1, -1):
        dxe = (x - eyeL[0] * sx) * sx
        crow = ss(.012 * s, .018 * s, dxe) * ss(.032 * s, .024 * s, dxe) * np.exp(-((fz) / (.012 * s)) ** 2)
        ang = np.arctan2(fz, np.maximum(dxe, 1e-4))
        hgt += -.012 * crow * np.sin(ang * 9) ** 6
    if m:
        hgt += .01 * stub
    rough = .5 - .1 * tzone - .18 * lip + .06 * beard + .05 * ears + .03 * fine

    # back into the texel grid
    def grid(vals, ch=None):
        g = np.zeros((H, W) if ch is None else (H, W, ch), F32)
        g[cov] = vals
        return dilate(g, cov)
    Cg = grid(C, 3); Hg = grid(hgt); Rg = grid(np.clip(rough, .2, .8))
    Pg = dilate(pos, cov)
    # texel size in metres along u (around the head) and v (up)
    r = np.sqrt(Pg[..., 0] ** 2 + Pg[..., 1] ** 2)
    du = np.maximum(2 * math.pi * r / W, 5e-5); dv = (zr[1] - zr[0]) / H
    gy, gx = np.gradient(Hg * .001)                 # height in metres
    nx = -gx / du; ny = -gy / dv
    N = np.stack([nx, ny, np.ones_like(nx)], 2)
    N /= np.linalg.norm(N, axis=2, keepdims=True)
    sx_ = builder.sex
    save(f'face_{sx_}_c', Cg, True, jpg=True)
    save(f'face_{sx_}_n', N * .5 + .5, False)
    save(f'face_{sx_}_m', np.stack([np.ones_like(Rg), Rg, np.zeros_like(Rg)], 2), False)
    return face_material(sx_)


def face_material(sex):
    """'skin_face': colour x the runtime skin tint, normal, roughness (the game hides it with the head region)."""
    m = bpy.data.materials.new('skin_face')
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    def img(name, colour):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(os.path.join(bl.TEXTURES, name))
        if not colour:
            t.image.colorspace_settings.name = 'Non-Color'
        return t
    tc = img(f'face_{sex}_c.jpg', True); nt.links.new(tc.outputs['Color'], b.inputs['Base Color'])
    tn = img(f'face_{sex}_n.png', False); nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    tm = img(f'face_{sex}_m.png', False); sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
    return m


# ---------------------------------------------------------------- body skin detail (tiling)
DETAIL_TILE = .08          # metres per texture repeat on the body
DW = 1024


def _pnoise2(u, v, n, seed=0):
    """Periodic value noise on the unit square, n cells per side (tiles seamlessly)."""
    x = u * n; y = v * n
    i = np.floor(x).astype(np.int64); j = np.floor(y).astype(np.int64)
    fx = x - i; fy = y - j
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    def h(a, b):
        return _hash(a % n, b % n, np.full_like(a, seed))
    return ((h(i, j) * (1 - fx) + h(i + 1, j) * fx) * (1 - fy) + (h(i, j + 1) * (1 - fx) + h(i + 1, j + 1) * fx) * fy)


def detail_maps():
    """skin_detail_c (near-white colour multiplier: faint mottling + pores), _n (pores and the fine cross-hatched
    creases of body skin), _m (roughness) on an 8 cm tile, 0.08 mm per texel."""
    if os.path.exists(os.path.join(bl.TEXTURES, 'skin_detail_n.png')) and '--rebake-skin' not in os.sys.argv:
        return
    u, v = np.meshgrid((np.arange(DW) + .5) / DW, (np.arange(DW) + .5) / DW)
    mott = sum(_pnoise2(u, v, n, k) * a for k, (n, a) in enumerate(((6, .5), (13, .3), (29, .2)))) - .5
    pores = ss(.66, .86, _pnoise2(u, v, 133, 7) * .7 + _pnoise2(u, v, 266, 8) * .3)
    fine = _pnoise2(u, v, 400, 9) - .5
    # fine creases: two families of lines ~1.4 mm apart at +-38 degrees, broken up by noise
    lines = np.zeros_like(u)
    for ang, sd in ((.66, 3), (-.66, 4)):
        t = (u * math.cos(ang) + v * math.sin(ang)) * (DETAIL_TILE / .0014)
        k = np.round(DETAIL_TILE / .0014 * (abs(math.cos(ang)) + abs(math.sin(ang))))   # keep the pattern periodic
        t = (u * np.round(k * math.cos(ang)) + v * np.round(k * math.sin(ang)))
        lines += np.exp(-((t - np.round(t)) / .09) ** 2) * ss(.35, .7, _pnoise2(u, v, 20, sd))
    hgt = -.03 * pores - .012 * lines + .004 * fine        # mm
    C = np.ones((DW, DW, 3), F32) * (1 + .05 * mott)[..., None]
    C *= (1 - .04 * pores)[..., None]
    C[..., 0] += .012 * mott; C[..., 2] -= .01 * mott
    gy, gx = np.gradient(hgt * .001)
    texel = DETAIL_TILE / DW
    N = np.stack([-gx / texel, -gy / texel, np.ones_like(gx)], 2); N /= np.linalg.norm(N, axis=2, keepdims=True)
    R = .52 + .06 * mott + .04 * pores
    global W, H
    W0, H0 = W, H
    W, H = DW, DW
    try:
        save('skin_detail_c', np.clip(C, 0, 1), True, jpg=True)
        save('skin_detail_n', N * .5 + .5, False)
        save('skin_detail_m', np.stack([np.ones_like(R), R, np.zeros_like(R)], 2), False)
    finally:
        W, H = W0, H0


def box_uv(o):
    """Per-face box projection in metres / DETAIL_TILE (the detail maps tile; seams are invisible in pore noise)."""
    me = o.data
    uvl = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
    me.uv_layers.active = uvl
    V = np.array([v.co[:] for v in me.vertices], F32)
    U = np.zeros((len(me.loops), 2), F32)
    for poly in me.polygons:
        nrm = np.abs(np.array(poly.normal[:]))
        ax = int(np.argmax(nrm))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for li in poly.loop_indices:
            p = V[me.loops[li].vertex_index]
            U[li] = (p[a] / DETAIL_TILE, p[b] / DETAIL_TILE)
    uvl.data.foreach_set('uv', U.ravel())


def detail_material(m):
    """Give the body 'skin' material the tiling detail maps (glTF multiplies the vertex colour in)."""
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    def img(name, colour):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(os.path.join(bl.TEXTURES, name))
        if not colour:
            t.image.colorspace_settings.name = 'Non-Color'
        return t
    tc = img('skin_detail_c.jpg', True); nt.links.new(tc.outputs['Color'], b.inputs['Base Color'])
    tn = img('skin_detail_n.png', False); nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 1.0
    nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    tm = img('skin_detail_m.png', False); sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
    return m
