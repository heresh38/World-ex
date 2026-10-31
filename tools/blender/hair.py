"""Player hair: a fitted scalp cap plus layered, alpha-tested strand cards grown over the head (wardrobe.py calls this).

* `strand_texture()` paints assets/textures/hair_strands.png with numpy: four card columns (dense, layered, wispy,
  short tufts) of thin strands drawn root (v=0) to tip (v=1) with per-strand brightness, darker roots, clumps that
  converge towards tapered tips and uneven lengths. RGB is grey (tinted at runtime by the hair colour), alpha is the
  strand coverage. The cap samples the same image as an opaque streak texture.
* `Groom` grows guide strands over the head field: they hug the scalp at a small offset while combed along the
  style's flow, then hang under gravity and are pushed out of the head and body. Each guide becomes a ribbon with a
  shallow V cross-section whose normals point away from the scalp (the cards light like one hair volume).
Material names are an API: `hair` (cards, alpha) and `hair__cap` (opaque), both tinted with the hair colour.
"""
import bpy, os, math
import numpy as np
import bl, sdf, face
import players as PL
from sdf import smoothstep

F32 = np.float32
ATLAS = 'hair_strands.png'
CAP_TEX = 'hair_cap.jpg'
NCOL = 4                      # 0 dense, 1 layered, 2 wispy, 3 short tufts


# ====================================================================== texture
def strand_texture(size=1024):
    W = size // NCOL; Hh = size
    rng = np.random.default_rng(17)
    alpha = np.zeros((Hh, size), F32)
    num = np.zeros((Hh, size), F32); den = np.zeros((Hh, size), F32)
    rows = np.arange(Hh)
    cfg = [dict(n=560, clumps=15, lmin=.72, wmin=1.3, wmax=2.5, conv=.55, fill=.08),
           dict(n=400, clumps=11, lmin=.5, wmin=1.1, wmax=2.2, conv=.7, fill=.05),
           dict(n=150, clumps=8, lmin=.35, wmin=.8, wmax=1.5, conv=.4, fill=.0),
           dict(n=440, clumps=16, lmin=.45, wmin=1.3, wmax=2.4, conv=.85, fill=.1)]
    for c, k in enumerate(cfg):
        x0 = c * W
        centres = rng.uniform(12, W - 12, k['clumps'])
        cw = W / k['clumps'] * .75
        for _ in range(k['n']):
            ci = rng.integers(len(centres)); cx = centres[ci]
            xr = np.clip(cx + rng.normal(0, cw), 3, W - 4)
            ln = rng.uniform(k['lmin'], 1.0) ** .7
            n = int(ln * (Hh - 1))
            t = rows[:n + 1] / (Hh - 1)                 # v (0 root .. 1)
            tl = t / ln                                  # 0..1 along this strand
            tipx = cx + rng.normal(0, cw * .25)
            x = xr + (tipx - xr) * k['conv'] * tl ** 1.6
            x += rng.uniform(.5, 2.5) * np.sin(tl * rng.uniform(4, 11) + rng.uniform(0, 6.3))
            if c == 2:
                x += rng.normal(0, 6) * tl ** 2      # wisps stray
            w = rng.uniform(k['wmin'], k['wmax']) * (1 - .75 * smoothstep(.55, 1.0, tl))
            a = (1 - smoothstep(.8, 1.0, tl)) * rng.uniform(.75, 1.0)
            b = rng.uniform(.6, 1.0) * (.78 + .22 * tl) * (1 + .06 * np.sin(tl * rng.uniform(40, 90)))
            xi = np.floor(x).astype(int)
            for o in range(-3, 4):
                col = np.clip(xi + o, 0, W - 1)
                dist = np.abs(col + .5 - x)
                prof = np.clip(1 - dist / np.maximum(w, .35), 0, 1)
                val = prof * a
                r = rows[:n + 1]; cc = col + x0
                alpha[r, cc] = np.maximum(alpha[r, cc], val)
                num[r, cc] += prof * b; den[r, cc] += prof
        u = (np.arange(W) + .5) / W
        edge = smoothstep(0, .16, u) * smoothstep(1, .84, u)
        v = rows / (Hh - 1)
        alpha[:, x0:x0 + W] *= (edge[None, :] ** (.6 + .8 * v[:, None])) * .45 + .55 * edge[None, :] ** 2.5
        if k['fill']:
            alpha[:, x0:x0 + W] = np.maximum(alpha[:, x0:x0 + W], smoothstep(k['fill'], 0, v)[:, None] * edge[None, :] ** .5)
        alpha[:, x0:x0 + 2] = 0; alpha[:, x0 + W - 2:x0 + W] = 0          # gutters between the columns
    grey = np.where(den > .05, num / np.maximum(den, 1e-6), 0)
    # fill empty texels with a blurred version so mip levels keep a hair colour
    fill = grey.copy(); m = den > .05
    for _ in range(6):
        acc = np.zeros_like(fill); cnt = np.zeros_like(fill)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            acc += np.roll(np.roll(fill * m, dx, 1), dy, 0); cnt += np.roll(np.roll(m.astype(F32), dx, 1), dy, 0)
        nm = (~m) & (cnt > 0)
        fill[nm] = acc[nm] / cnt[nm]; m = m | nm
    fill[~m] = .7
    grey = np.clip(fill * .95 + .05, 0, 1)
    img = np.ones((Hh, size, 4), F32)
    img[..., 0] = img[..., 1] = img[..., 2] = grey
    img[..., 3] = np.clip(alpha * 1.15, 0, 1)
    im = bpy.data.images.new('hair_strands', size, Hh, alpha=True)
    im.pixels = img.ravel()                     # row 0 = image bottom = v 0 (the roots)
    im.filepath_raw = os.path.join(bl.TEXTURES, ATLAS); im.file_format = 'PNG'; im.save()
    # scalp cap: low-contrast, tileable streaks running along v (it mostly shows through partings and hairlines)
    N = 256; uu = (np.arange(N) + .5) / N
    val = np.full(N, .66, F32)
    for kk in (7, 13, 29, 53, 97):
        val += (.05 / kk ** .3) * np.sin(2 * math.pi * kk * uu + rng.uniform(0, 6.3))
    val += rng.normal(0, .025, N).astype(F32)
    cap = np.ones((N, N, 4), F32)
    vv = (np.arange(N) + .5) / N
    shade = val[None, :] * (.94 + .06 * np.sin(2 * math.pi * 3 * vv + 1.0)[:, None])
    cap[..., 0] = cap[..., 1] = cap[..., 2] = np.clip(shade, 0, 1)
    ci = bpy.data.images.new('hair_cap', N, N)
    ci.pixels = cap.ravel()
    sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    ci.save_render(os.path.join(bl.TEXTURES, CAP_TEX))
    return im


def card_material():
    m = bpy.data.materials.get('hair')
    if m is not None:
        return m
    m = bpy.data.materials.new('hair')
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = .45
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(bl.TEXTURES, ATLAS), check_existing=True)
    nt.links.new(tn.outputs['Color'], b.inputs['Base Color']); nt.links.new(tn.outputs['Alpha'], b.inputs['Alpha'])
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    return m


def cap_material():
    return bl.mat('hair__cap', '#ffffff', 0, .6, image=CAP_TEX)


# ====================================================================== groom
def nrm(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


class Groom:
    def __init__(self, kit):
        self.kit = kit; self.B = kit.B; self.H = kit.B.head; self.s = self.H.s
        self.ho = np.asarray(kit.B.head_o, F32); self.F = kit.F
        self.cards_mat = card_material(); self.cap_mat = cap_material()
        self.rng = np.random.default_rng(5)
        self.V = []; self.Q = []; self.UV = []; self.N = []; self.nv = 0

    def S(self, *v):
        return np.array(v, F32) * self.s

    # ---------------------------------------------------------------- scalp sampling
    def roots(self, n, mask, off=.002, c0=(0, .012, .02), jitter=.35, band=None):
        """~n points on the scalp (head-local) where mask(L) < 0, at `off` above the skin. band=(lo, hi) keeps only
        lo < mask < hi (e.g. a strip just inside the hairline)."""
        n = max(8, int(n * (.55 if self.kit.npc else 1.0)))
        m = n * 6 if band is None else n * 60
        i = np.arange(m) + .5
        phi = np.arccos(1 - 2 * i / m); th = math.pi * (1 + 5 ** .5) * i
        Dv = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1).astype(F32)
        Dv = nrm(Dv + self.rng.normal(0, jitter / math.sqrt(m) * 3, Dv.shape).astype(F32))
        P = self.S(*c0) + Dv * .2
        P = self.shell(P, off, 8)
        mv = mask(P)
        keep = mv < 0 if band is None else (mv > band[0] * self.s) & (mv < band[1] * self.s)
        P = P[keep]
        if len(P) > n:
            P = P[self.rng.choice(len(P), n, replace=False)]
        return P.astype(F32)

    def shell(self, P, off, iters=4):
        for _ in range(iters):
            h = self.H(P); g = sdf.normals(self.H, P)
            P = P - g * (h - off)[:, None]
        return P

    def hairline(self, L, lift=0.0):
        return self.kit.hairline(L) + lift * self.s

    # ---------------------------------------------------------------- growth
    def grow(self, R, length, nseg, flow, hang=None, off=.003, hug=1.0, body_off=.012, ctx=None, fall=1.0):
        """Guides from roots R (head-local). flow(p, t, ctx) -> direction; hang(p, t, ctx) -> 0..1 gravity blend.
        off: scalar/array (per strand) or callable(t) shell offset while hugging the scalp."""
        n = len(R); length = np.broadcast_to(np.asarray(length, F32), (n,))
        P = np.zeros((n, nseg + 1, 3), F32); Nn = np.zeros((n, nseg + 1, 3), F32)
        p = R.astype(F32).copy(); P[:, 0] = p
        Nn[:, 0] = sdf.normals(self.H, p)
        down = np.array([0, 0, -1], F32)
        step = (length / nseg)[:, None]
        for i in range(nseg):
            t = (i + .5) / nseg; t1 = (i + 1) / nseg
            o = off(t1, ctx) if callable(off) else off
            o = np.broadcast_to(np.asarray(o, F32), (n,))
            h = self.H(p); nh = sdf.normals(self.H, p)
            near = smoothstep(o + .016, o + .004, h)
            d = nrm(flow(p, t, ctx).astype(F32))
            tan = nrm(d - (np.einsum('ij,ij->i', d, nh) * near)[:, None] * nh)
            if hang is not None:
                g = np.maximum(np.broadcast_to(np.asarray(hang(p, t, ctx), F32), (n,)), smoothstep(o + .005, o + .016, h) * fall)
            else:
                g = np.zeros(n, F32)
            dn = down[None, :]
            if ctx is not None and ('flare' in ctx or 'fwd' in ctx):
                # hanging hair stands off the head and shoulders (volume), front locks fall forward over the chest
                fl = np.broadcast_to(np.asarray(ctx.get('flare', 0.0), F32), (n,))[:, None]
                fw = np.broadcast_to(np.asarray(ctx.get('fwd', 0.0), F32), (n,))[:, None]
                dn = nrm(dn + _radial(self, p) * fl * (1 - t) + np.array([0, -1, 0], F32) * fw)
            dirv = nrm(tan * (1 - g)[:, None] + dn * g[:, None])
            p = p + dirv * step
            # hug the scalp while combed, never inside the offset shell
            h = self.H(p); nh = sdf.normals(self.H, p)
            pull = (1 - g) * hug * (h < o + (.02 if hang is not None else .06))
            corr = np.where(h < o, o - h, (o - h) * pull)
            p = p + nh * corr[:, None]
            # keep out of the body (shoulders, back, chest)
            W = p + self.ho
            f = self.F(W); low = f < body_off
            if low.any():
                gn = sdf.normals(self.F, W[low])
                p[low] += gn * (body_off - f[low])[:, None]
            P[:, i + 1] = p
            nh = sdf.normals(self.H, p); h = self.H(p)
            rad = nrm(np.stack([p[:, 0], p[:, 1] - .01 * self.s, np.zeros(n, F32) + .15 * p[:, 2].clip(None, 0)], 1))
            a = smoothstep(.05, .015, h)[:, None]
            Nn[:, i + 1] = nrm(nh * a + rad * (1 - a))
        return P, Nn

    # ---------------------------------------------------------------- cards
    def cards(self, P, Nn, w0, w1, col, v0=0.0, v1=1.0, lift=.06, normals=None):
        """Ribbon per guide (V-shaped cross-section, 3 verts). col: atlas column (or array per card)."""
        n, k, _ = P.shape
        if n == 0:
            return 0
        wk = 1.3 if self.kit.npc else 1.0          # fewer, wider cards on the crowd LOD
        w0 = np.broadcast_to(np.asarray(w0, F32) * wk, (n,)); w1 = np.broadcast_to(np.asarray(w1, F32) * wk, (n,))
        col = np.broadcast_to(np.asarray(col), (n,))
        T = np.zeros_like(P)
        T[:, 1:-1] = P[:, 2:] - P[:, :-2]; T[:, 0] = P[:, 1] - P[:, 0]; T[:, -1] = P[:, -1] - P[:, -2]
        T = nrm(T)
        side = nrm(np.cross(T, Nn))
        tt = np.linspace(0, 1, k, dtype=F32)
        W = (w0[:, None] * (1 - tt) + w1[:, None] * tt)[..., None]
        L = P - side * W * .5; R = P + side * W * .5; C = P + Nn * W * lift
        V = np.stack([L, C, R], 2)                     # n, k, 3, 3
        NN = np.stack([nrm(Nn - side * .15), Nn, nrm(Nn + side * .15)], 2)
        flip = self.rng.random(n) < .5
        ua = (col * (1.0 / NCOL) + .006).astype(F32); ub = ((col + 1) * (1.0 / NCOL) - .006).astype(F32)
        u0 = np.where(flip, ub, ua); u1 = np.where(flip, ua, ub)
        U = np.stack([u0, (u0 + u1) / 2, u1], 1)       # n, 3
        v0 = np.broadcast_to(np.asarray(v0, F32), (n,)); v1 = np.broadcast_to(np.asarray(v1, F32), (n,))
        UV = np.zeros((n, k, 3, 2), F32)
        UV[..., 0] = U[:, None, :]
        UV[..., 1] = (v0[:, None] + (v1 - v0)[:, None] * tt[None])[..., None]
        base = self.nv + np.arange(n)[:, None, None] * (k * 3)
        ii = np.arange(k - 1)[None, :, None] * 3; jj = np.arange(2)[None, None, :]
        a = base + ii + jj; b = a + 1; c = a + 4; d = a + 3
        # quads L_i, C_i, C_i+1, L_i+1: geometric normal = side x T = the hair normal (front faces outward)
        Qd = np.stack([a, b, c, d], -1).reshape(n, -1, 4)
        g = np.cross(side, T)
        sgn = np.einsum('nkj,nkj->n', g, Nn) < 0
        Qd[sgn] = Qd[sgn][..., ::-1]
        self.V.append(V.reshape(-1, 3)); self.N.append(NN.reshape(-1, 3)); self.UV.append(UV.reshape(-1, 2))
        self.Q.append(Qd.reshape(-1, 4)); self.nv += n * k * 3
        return n * (k - 1) * 4

    def card_object(self, name):
        if not self.V:
            return None
        V = np.concatenate(self.V); Q = np.concatenate(self.Q); UV = np.concatenate(self.UV); N = np.concatenate(self.N)
        o = PL.to_object(name, V + self.ho, Q)
        o.data.materials.append(self.cards_mat)
        uv = o.data.uv_layers.new(name='UVMap')
        n_, vi = PL.faces(o)
        uv.data.foreach_set('uv', UV[vi].ravel())
        o.data.normals_split_custom_set_from_vertices([tuple(v) for v in N])
        self.V, self.Q, self.UV, self.N, self.nv = [], [], [], [], 0
        return o

    # ---------------------------------------------------------------- cap
    def cap(self, t_fn, mask, target=650, shrink=.004):
        kit = self.kit; s = self.s; ho = self.ho
        cm = lambda L: mask(L) + shrink * s
        fn = kit.scalp(lambda L: t_fn(L) * (.25 + .75 * smoothstep(0, -.012 * s, cm(L))), None, 0, mask=cm)
        o = kit.build('hair_cap', fn, ho + self.S(-.11, -.12, -.1), ho + self.S(.11, .13, .15), [self.cap_mat],
                      h=.0026 if not PL.FAST else .0034, target=int(target / max(kit.tscale, .6)), weights=lambda V: {'head': np.ones(len(V), F32)})
        if o is None:
            return None
        V = PL.verts(o) - ho
        n_, vi = PL.faces(o)
        P = V[vi]
        az = np.arctan2(P[:, 0], -P[:, 1] + .02 * s)
        u = (az / (2 * math.pi) + .5) * 2.0
        v = np.clip((.13 * s - P[:, 2]) / (.22 * s), 0, 1)
        uv = o.data.uv_layers.get('UVMap') or o.data.uv_layers.new(name='UVMap')
        uv.data.foreach_set('uv', np.stack([u, v], 1).astype(F32).ravel())
        return o

    def finish(self, item, label, parts, weights=None):
        kit = self.kit
        cards = self.card_object('hair_cards')
        w = weights or (lambda V: {'head': np.ones(len(V), F32)})
        if cards is not None:
            PL.apply_weights(cards, w(PL.verts(cards)))
        objs = [o for o in parts if o is not None] + [cards]
        o = kit.add('hair', item, label, objs)
        self.morphs(o)
        tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
        PL.log('  hair', item, tris, 'tris')
        kit.hair_tris[item] = tris
        return o

    def morphs(self, o):
        """Face morphs that move the skin under the hair (face width, jaw, cheekbones, ears) also move the hair."""
        M = face.Morphs(self.H, self.kit.sex)
        V = PL.verts(o); L = V - self.ho
        keys = []
        for name in M.names():
            if name.startswith('ears_'):
                continue             # hair over the ears stays put; pointed ears may show through
            L2 = M.apply(name, L, 'skin')
            if np.abs(L2 - L).max() > 2.5e-4:
                keys.append((name, L2))
        if not keys:
            return
        o.shape_key_add(name='Basis', from_mix=False)
        for name, L2 in keys:
            k = o.shape_key_add(name=name, from_mix=False)
            k.data.foreach_set('co', (L2 + self.ho).astype(F32).ravel())


# ====================================================================== styles
def _radial(g, p):
    return nrm(np.stack([p[:, 0], p[:, 1] - .01 * g.s, np.zeros(len(p), F32)], 1))


def female_styles(g):
    kit = g.kit; s = g.s; S = g.S; rng = g.rng
    full = lambda L: g.hairline(L)
    W = kit.hair_weights()

    def part_flow(xp, back_k=.75):
        def flow(p, t, c):
            sd = c['side']
            back = smoothstep(.01 * s, .07 * s, p[:, 1])
            front = smoothstep(-.02 * s, -.07 * s, p[:, 1])
            sdn = smoothstep(.03 * s, .06 * s, np.abs(p[:, 0]))
            d = np.stack([sd * (1 - back * back_k), .2 + .45 * front + .25 * back, -.1 - .8 * sdn * (1 - front * .5) - 1.2 * back], 1)
            if 'wave' in c:
                d = d + _radial(g, p) * (c['wave'] * np.sin(t * 2 * math.pi * 2.6 + c['ph']))[:, None] * smoothstep(.25, .45, t)
            if 'curl' in c:
                d = d - _radial(g, p) * (c['curl'] * smoothstep(.72, 1.0, t))[:, None]
            return d
        return flow

    def sides(R, xp):
        sd = np.sign(R[:, 0] - xp); z = sd == 0
        sd[z] = rng.choice([-1.0, 1.0], z.sum())
        return sd.astype(F32)

    def layered(R, length, nseg, flow, hang, specs, ctx):
        """specs: list of (fraction, off, w0, w1, col, length scale)."""
        n = len(R); idx = rng.permutation(n); a = 0
        for frac, off, w0, w1, col, ls in specs:
            b = n if frac is None else a + int(frac * n)
            ii = idx[a:b]; a = b
            c = {k: (v[ii] if isinstance(v, np.ndarray) and len(v) == n else v) for k, v in ctx.items()}
            P, N = g.grow(R[ii], length[ii] * ls, nseg, flow, hang, off=off, ctx=c)
            g.cards(P, N, w0, w1, col)

    # ---------------------------------------------------------------- long layered, centre part
    xp = .002 * s
    R = np.concatenate([g.roots(130, full), g.roots(40, full, band=(-.014, -.002))])
    fr = smoothstep(-.0 * s, -.07 * s, R[:, 1])
    length = (.5 - .12 * fr) * rng.uniform(.92, 1.05, len(R))
    hang = lambda p, t, c: smoothstep(.05 * s, .0, p[:, 2])
    front_lock = (R[:, 1] < -.0 * s) & (np.abs(R[:, 0]) > .02 * s) & (rng.random(len(R)) < .7)
    ctx = {'side': sides(R, xp), 'flare': np.full(len(R), .35, F32), 'fwd': np.where(front_lock, .35, 0).astype(F32)}
    layered(R, length, 10, part_flow(xp), hang, [(.5, .004, .03, .022, 0, 1.0), (.4, .0095, .026, .016, 1, .93),
                                                 (None, .013, .014, .008, 2, .85)], ctx)
    cap = g.cap(lambda L: np.full(len(L), .0024 * s, F32), full)
    g.finish('long', 'Long layered', [cap], W)

    # ---------------------------------------------------------------- high ponytail
    tie = S(0, .082, .092)
    R = np.concatenate([g.roots(130, full), g.roots(40, full, band=(-.014, -.002))])[::-1]
    length = np.linalg.norm(tie - R, axis=1) * 1.08
    flow = lambda p, t, c: tie - p
    for (lo, hi), off, col in (((0, int(len(R) * .6)), .0022, 0), ((int(len(R) * .6), len(R)), .0038, 1)):
        P, N = g.grow(R[lo:hi], length[lo:hi], 6, flow, None, off=off)
        g.cards(P, N, .022, .01, col, lift=.0)
    path = np.array([tie / s, (0, .13, .085), (0, .165, .0), (0, .175, -.12), (0, .17, -.27), (0, .16, -.44)], F32) * s
    radii = np.array([.014, .042, .052, .048, .036, .012]) * s
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]; seg /= seg[-1]
    k = 11; tt = np.linspace(0, 1, k)
    C = np.stack([np.interp(tt, seg, path[:, i]) for i in range(3)], 1).astype(F32)
    rad = np.interp(tt, seg, radii)
    Tn = nrm(np.gradient(C, axis=0))
    e1 = nrm(np.cross(Tn, [1, 0, 0])); e2 = nrm(np.cross(Tn, e1))
    n = 52; Ps = np.zeros((n, k, 3), F32); Ns = np.zeros((n, k, 3), F32)
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-.15, .15); r = rng.uniform(.45, 1.0); tw = rng.uniform(.4, .9)
        ang = a + tw * tt * 2
        dirs = nrm(np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2)
        Ps[i] = C + dirs * (rad * r)[:, None]
        Ns[i] = dirs
    # keep the tail outside the back
    for j in range(k):
        Wp = Ps[:, j] + g.ho; f = g.F(Wp); low = f < .012
        if low.any():
            Ps[low, j] += sdf.normals(g.F, Wp[low]) * (.012 - f[low])[:, None]
    inner = np.arange(n) % 2 == 0
    g.cards(Ps, Ns, .024, .008, np.where(inner, 0, 1), lift=.08)
    cap = g.cap(lambda L: np.full(len(L), .0021 * s, F32), full)
    band = bl.mat('trim_hair', '#2a2a30', .2, .45)
    Fm = sdf.frame(Tn[1]); Rt = np.array([Fm[1], Fm[2], Fm[0]])
    tp = (C[0] * .6 + C[1] * .4)
    tb = kit.build('tie', lambda P: sdf.torus(P - g.ho, tp, .015 * s, .0045 * s, Rt), g.ho + tp - .03, g.ho + tp + .03,
                   [band], h=.001, target=600, weights=W)
    g.finish('ponytail', 'High ponytail', [cap, tb], W)

    # ---------------------------------------------------------------- chin-length bob, side part
    xp = .024 * s
    R = np.concatenate([g.roots(130, full), g.roots(40, full, band=(-.014, -.002))])
    endz = -.078 * s
    length = np.clip((R[:, 2] - endz) * 1.12 + .02 + .05 * smoothstep(xp, .06 * s, -R[:, 0] + xp) * smoothstep(0, -.05 * s, R[:, 1]), .05, None) * rng.uniform(.96, 1.03, len(R))
    hang = lambda p, t, c: smoothstep(.045 * s, .005 * s, p[:, 2]) * (1 - .7 * smoothstep(.75, 1.0, t))
    ctx = {'side': sides(R, xp), 'curl': np.full(len(R), 1.4, F32), 'flare': np.full(len(R), .45, F32)}
    layered(R, length, 9, part_flow(xp, .6), hang, [(.55, .0045, .032, .026, 0, 1.0), (None, .0105, .028, .02, 1, .97)], ctx)
    cap = g.cap(lambda L: np.full(len(L), .0026 * s, F32), full)
    g.finish('bob', 'Bob', [cap], W)

    # ---------------------------------------------------------------- top bun
    bc = S(0, .022, .122)
    R = np.concatenate([g.roots(120, full), g.roots(40, full, band=(-.014, -.002))])[::-1]
    length = np.linalg.norm(bc - R, axis=1) * 1.08
    flow = lambda p, t, c: bc - p
    for (lo, hi), off, col in (((0, int(len(R) * .62)), .0022, 0), ((int(len(R) * .62), len(R)), .0038, 1)):
        P, N = g.grow(R[lo:hi], length[lo:hi], 6, flow, None, off=off)
        g.cards(P, N, .024, .012, col, lift=.0)
    ax = nrm(np.array([0, .35, 1.0], F32)); e1 = nrm(np.cross(ax, [1, 0, 0])); e2 = np.cross(ax, e1)
    cen = g.shell(bc[None], .0, 3)[0] + ax * .03 * s
    n = 32; k = 16; Ps = np.zeros((n, k, 3), F32); Ns = np.zeros((n, k, 3), F32)
    RR = .027 * s
    for i in range(n):
        a0 = 2 * math.pi * i / n; r = .021 * s * rng.uniform(.75, 1.05)
        th = np.linspace(0, 2 * math.pi * 1.05, k) + rng.uniform(0, 6.28)
        a = a0 + th * .5
        ring = np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2
        Ps[i] = cen + ring * (RR + r * np.cos(a))[:, None] + ax * (r * np.sin(a))[:, None]
        Ns[i] = nrm(ring * np.cos(a)[:, None] + ax * np.sin(a)[:, None])
    g.cards(Ps, Ns, .02, .016, np.where(np.arange(n) % 2 == 0, 0, 1), lift=.1)
    cap = g.cap(lambda L: np.full(len(L), .0021 * s, F32), full)
    g.finish('bun', 'Top bun', [cap], W)

    # ---------------------------------------------------------------- wavy shoulder length
    xp = .012 * s
    R = np.concatenate([g.roots(130, full), g.roots(40, full, band=(-.014, -.002))])
    fr = smoothstep(0, -.07 * s, R[:, 1])
    length = (.25 - .045 * fr) * rng.uniform(.92, 1.06, len(R))
    hang = lambda p, t, c: smoothstep(.05 * s, .0, p[:, 2]) * .85
    ctx = {'side': sides(R, xp), 'wave': rng.uniform(1.2, 1.6, len(R)).astype(F32), 'ph': rng.uniform(0, .8, len(R)).astype(F32),
           'flare': np.full(len(R), .55, F32)}
    layered(R, length, 11, part_flow(xp), hang, [(.5, .005, .032, .022, 0, 1.0), (.4, .011, .026, .016, 1, .94),
                                                 (None, .014, .014, .008, 2, .85)], ctx)
    cap = g.cap(lambda L: np.full(len(L), .0026 * s, F32), full)
    g.finish('wavy', 'Wavy shoulder-length', [cap], W)
    return 'long'


def male_styles(g):
    kit = g.kit; s = g.s; S = g.S; rng = g.rng
    full = lambda L: g.hairline(L)
    top_m = lambda L: np.maximum(full(L), .056 * s - L[:, 2])            # crown / top only
    side_m = lambda L: np.maximum(full(L), L[:, 2] - .062 * s)           # sides and back (fade)
    W = lambda V: {'head': np.ones(len(V), F32)}

    def fade_cap(top_t, side_t):
        return lambda L: side_t * s + (top_t - side_t) * s * smoothstep(.04 * s, .075 * s, L[:, 2])

    # ---------------------------------------------------------------- classic side part
    xp = .03 * s
    R = g.roots(120, top_m)
    sd = np.sign(R[:, 0] - xp).astype(F32); sd[sd == 0] = 1
    front = smoothstep(.0, -.06 * s, R[:, 1])
    ctx = {'side': sd, 'off': (.003 + .004 * front).astype(F32)}

    def flow(p, t, c):
        big = c['side'] < 0
        return np.stack([c['side'] * np.where(big, .85, .6), np.where(big, .45, .25), np.where(big, -.2, -.65)], 1)
    length = (.075 + .02 * front) * rng.uniform(.85, 1.1, len(R))
    P, N = g.grow(R, length, 5, flow, None, off=lambda t, c: c['off'] * (1 - .35 * t), ctx=ctx)
    g.cards(P, N, .024, .012, np.where(rng.random(len(R)) < .5, 3, 1), lift=.02)
    cap = g.cap(fade_cap(.0042, .0016), full, shrink=0)
    g.finish('sidepart', 'Classic side part', [cap], W)

    # ---------------------------------------------------------------- undercut, slicked back
    band = lambda L: np.maximum(full(L), np.maximum(.064 * s - L[:, 2], np.abs(L[:, 0]) - .047 * s))
    R = g.roots(120, band)
    front = smoothstep(.03 * s, -.06 * s, R[:, 1])
    ctx = {'off': (.004 + .007 * front).astype(F32)}
    flow = lambda p, t, c: np.stack([p[:, 0] * 2, np.ones(len(p), F32), -.15 - .9 * smoothstep(.06 * s, .1 * s, p[:, 1])], 1)
    length = (.07 + .07 * front) * rng.uniform(.9, 1.08, len(R))
    P, N = g.grow(R, length, 7, flow, None, off=lambda t, c: c['off'] * (1 - .5 * t) + .002, ctx=ctx)
    g.cards(P, N, .026, .016, np.where(rng.random(len(R)) < .5, 0, 1))
    cap = g.cap(lambda L: .0012 * s + .0036 * s * smoothstep(.0, -.006 * s, band(L)), full, shrink=0)
    g.finish('undercut', 'Undercut, slicked back', [cap], W)

    # ---------------------------------------------------------------- textured crop
    R = g.roots(170, top_m)
    front = smoothstep(.0, -.06 * s, R[:, 1])
    ctx = {'jit': rng.normal(0, .25, (len(R), 3)).astype(F32)}

    def flow(p, t, c):
        nh = sdf.normals(g.H, p)
        return np.array([0, -1.0, -.1], F32) + c['jit'] + nh * (.5 * t)
    length = (.045 - .018 * front) * rng.uniform(.75, 1.15, len(R))
    P, N = g.grow(R, length, 4, flow, None, off=.0045, hug=.6, ctx=ctx)
    g.cards(P, N, .022, .006, 3, lift=.02)
    cap = g.cap(fade_cap(.0045, .0014), full, shrink=0)
    g.finish('textured', 'Textured crop', [cap], W)

    # ---------------------------------------------------------------- buzz cut
    cap = g.cap(lambda L: np.full(len(L), .0018 * s, F32), full, target=900, shrink=0)
    g.finish('buzz', 'Buzz cut', [cap], W)

    # ---------------------------------------------------------------- medium swept back
    R = g.roots(190, full)
    front = smoothstep(.02 * s, -.06 * s, R[:, 1])
    sideness = smoothstep(.04 * s, .065 * s, np.abs(R[:, 0]))
    ctx = {'off': (.004 + .007 * front).astype(F32)}

    def flow(p, t, c):
        sdn = smoothstep(.035 * s, .065 * s, np.abs(p[:, 0]))
        backn = smoothstep(.04 * s, .09 * s, p[:, 1])
        return np.stack([np.sign(p[:, 0]) * .15 * sdn, 1.0 - .6 * backn, -.25 - .9 * sdn - 1.3 * backn], 1)
    hang = None
    backn = smoothstep(.03 * s, .09 * s, R[:, 1]) * smoothstep(.08 * s, .0, R[:, 2])
    length = (.11 + .03 * front - .02 * sideness) * (1 - .45 * backn) * rng.uniform(.9, 1.08, len(R))
    idx = rng.permutation(len(R))
    cut = int(len(R) * .55)
    for ii, col, w0, w1, oo in ((idx[:cut], 0, .028, .018, 0), (idx[cut:], 1, .024, .014, .003)):
        c = {'off': ctx['off'][ii] + oo}
        P, N = g.grow(R[ii], length[ii], 7, flow, hang, off=lambda t, c: c['off'] * (1 - .4 * t) + .0015, ctx=c)
        g.cards(P, N, w0, w1, col)
    cap = g.cap(fade_cap(.0042, .0025), full, shrink=0)
    g.finish('swept', 'Medium swept back', [cap], W)
    return 'sidepart'
