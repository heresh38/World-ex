"""Signed-distance modelling for the organic assets (characters, hair, clothing), meshed with Surface Nets.

Everything is plain numpy so it runs inside Blender's Python. Shapes are functions P(N,3) -> distance(N,), negative
inside. A narrow band keeps the fine grid cheap: the exact field is only evaluated near the surface, far points take
the sign of a coarse pass. Surface Nets gives one vertex per surface cell and quads between them; vertices are then
projected onto the exact surface with Newton steps, and normals come from the field gradient (seam-free shading).
"""
import numpy as np

F32 = np.float32


def length(v):
    return np.sqrt(np.einsum('ij,ij->i', v, v))


def smin(a, b, k):
    """Polynomial smooth minimum; k is a blend radius (scalar or per point)."""
    k = np.maximum(k, 1e-7)
    h = np.clip(.5 + .5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def frame(u, hint=(0, 0, 1)):
    """Orthonormal frame with u as the first axis: returns 3x3 with rows u, v, w."""
    u = np.asarray(u, float); u = u / np.linalg.norm(u)
    h = np.asarray(hint, float)
    if abs(np.dot(h, u)) > .95:
        h = np.array([1.0, 0, 0]) if abs(u[0]) < .9 else np.array([0, 1.0, 0])
    v = np.cross(h, u); v /= np.linalg.norm(v)
    w = np.cross(u, v)
    return np.array([u, v, w])


def rot(axis, ang):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a)
    c, s = np.cos(ang), np.sin(ang)
    x, y, z = a
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


# ------------------------------------------------------------------ primitives
def sphere(P, c, r):
    return length(P - np.asarray(c, F32)) - r


def ellipsoid(P, c, r, R=None):
    """Approximate ellipsoid distance. R: 3x3 whose ROWS are the local axes (world)."""
    q = P - np.asarray(c, F32)
    if R is not None:
        q = q @ np.asarray(R, F32).T
    r = np.asarray(r, F32)
    k0 = length(q / r); k1 = length(q / (r * r))
    return k0 * (k0 - 1) / np.maximum(k1, 1e-9)


def capsule(P, a, b, r):
    a = np.asarray(a, F32); b = np.asarray(b, F32)
    pa = P - a; ba = b - a
    h = np.clip((pa @ ba) / np.dot(ba, ba), 0, 1)
    return length(pa - h[:, None] * ba) - r


def round_cone(P, a, b, r1, r2):
    """Tapered capsule between points a (radius r1) and b (radius r2), exact (after Inigo Quilez)."""
    a = np.asarray(a, np.float64); b = np.asarray(b, np.float64)
    ba = b - a; l2 = np.dot(ba, ba); rr = r1 - r2; a2 = l2 - rr * rr; il2 = 1.0 / l2
    pa = (P - a).astype(np.float64)
    y = pa @ ba; z = y - l2
    q = pa * l2 - y[:, None] * ba
    x2 = np.einsum('ij,ij->i', q, q)
    y2 = y * y * l2; z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    m1 = np.sign(z) * a2 * z2 > k
    m2 = (np.sign(y) * a2 * y2 < k) & ~m1
    d = np.where(m1, np.sqrt(x2 + z2) * il2 - r2, d)
    d = np.where(m2, np.sqrt(x2 + y2) * il2 - r1, d)
    return d.astype(F32)


def round_box(P, c, half, r, R=None):
    q = P - np.asarray(c, F32)
    if R is not None:
        q = q @ np.asarray(R, F32).T
    q = np.abs(q) - (np.asarray(half, F32) - r)
    return length(np.maximum(q, 0)) + np.minimum(q.max(1), 0) - r


def torus(P, c, R_, r, Rm=None):
    """Torus in the local XY plane (local Z is the axis)."""
    q = P - np.asarray(c, F32)
    if Rm is not None:
        q = q @ np.asarray(Rm, F32).T
    a = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2) - R_
    return np.sqrt(a * a + q[:, 2] ** 2) - r


def plane(P, n, d0):
    """Half space n.p <= d0 (inside)."""
    return P @ np.asarray(n, F32) - d0


class Loft:
    """Generalised cylinder along a segment with quadrant-ellipse cross sections and superellipse exponent.

    The frame rows (u, v, w): u runs from a to b; v is the 'outer/side' axis, w the 'front' axis. Profiles are sampled
    over t in [0, 1]: rv_pos (towards +v), rv_neg, rw_pos (+w), rw_neg, cv, cw (centre offsets), n (exponent).
    Beyond the ends the section is held and the solid is closed with a rounded cap of radius `cap` * section size.
    """

    def __init__(self, a, b, prof, hint=(0, 0, 1), v_axis=None, cap=.9):
        self.a = np.asarray(a, F32); b = np.asarray(b, F32)
        self.L = float(np.linalg.norm(b - self.a))
        if v_axis is not None:
            u = (b - self.a) / self.L
            v = np.asarray(v_axis, float); v = v - np.dot(v, u) * u; v /= np.linalg.norm(v)
            self.R = np.array([u, v, np.cross(u, v)], F32)
        else:
            self.R = frame(b - self.a, hint).astype(F32)
        ts = np.asarray(prof['t'], float)
        self.tab = {}
        n = 256
        self.tt = np.linspace(0, 1, n)
        for key in ('rv_pos', 'rv_neg', 'rw_pos', 'rw_neg', 'cv', 'cw', 'n', 'nb'):
            if key in prof:
                vals = np.asarray(prof[key], float)
            elif key in ('rv_neg',):
                vals = np.asarray(prof['rv_pos'], float)
            elif key == 'rw_neg':
                vals = np.asarray(prof['rw_pos'], float)
            elif key == 'n':
                vals = np.full(len(ts), 2.0)
            elif key == 'nb':
                vals = np.asarray(prof['n'], float) if 'n' in prof else np.full(len(ts), 2.0)
            else:
                vals = np.zeros(len(ts))
            self.tab[key] = smooth_curve(ts, vals, self.tt)
        self.cap = cap

    def __call__(self, P):
        q = (P - self.a) @ self.R.T
        t = q[:, 0] / self.L
        tc = np.clip(t, 0, 1)
        g = {k: np.interp(tc, self.tt, v).astype(F32) for k, v in self.tab.items()}
        x = q[:, 1] - g['cv']; y = q[:, 2] - g['cw']
        rx = np.where(x > 0, g['rv_pos'], g['rv_neg']); ry = np.where(y > 0, g['rw_pos'], g['rw_neg'])
        n = np.where(y > 0, g['n'], g['nb'])
        ax = np.abs(x) / rx + 1e-9; ay = np.abs(y) / ry + 1e-9
        rho = (ax ** n + ay ** n) ** (1 / n)
        rad = np.sqrt(x * x + y * y)
        reff = np.where(rho > 1e-4, rad / np.maximum(rho, 1e-4), np.minimum(rx, ry))
        d = (rho - 1) * reff
        # ends: rounded intersection with the end slab
        over = np.maximum(-t, t - 1) * self.L
        cr = np.minimum(rx, ry) * self.cap
        a = d + cr; b = over + cr
        return np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - cr


def smooth_curve(ts, vals, tt):
    """Monotone cubic (Fritsch-Carlson) interpolation so profiles never overshoot."""
    ts = np.asarray(ts, float); vals = np.asarray(vals, float)
    if len(ts) == 1:
        return np.full_like(tt, vals[0])
    h = np.diff(ts); dlt = np.diff(vals) / h
    m = np.zeros(len(ts))
    m[0] = dlt[0]; m[-1] = dlt[-1]
    for i in range(1, len(ts) - 1):
        if dlt[i - 1] * dlt[i] <= 0:
            m[i] = 0
        else:
            w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dlt[i - 1] + w2 / dlt[i])
    i = np.clip(np.searchsorted(ts, tt) - 1, 0, len(ts) - 2)
    x0 = ts[i]; hh = h[i]; s = (tt - x0) / hh
    s = np.clip(s, 0, 1)
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1; h10 = s ** 3 - 2 * s ** 2 + s; h01 = -2 * s ** 3 + 3 * s ** 2; h11 = s ** 3 - s ** 2
    out = h00 * vals[i] + h10 * hh * m[i] + h01 * vals[i + 1] + h11 * hh * m[i + 1]
    out = np.where(tt < ts[0], vals[0], out)
    out = np.where(tt > ts[-1], vals[-1], out)
    return out


# ------------------------------------------------------------------ field tools
def grad(fn, P, e=2e-4):
    P = np.asarray(P, F32)
    g = np.zeros_like(P)
    for i in range(3):
        d = np.zeros(3, F32); d[i] = e
        g[:, i] = (fn(P + d) - fn(P - d)) / (2 * e)
    return g


def project(fn, P, iters=3, max_step=None):
    """Newton steps onto the zero level set."""
    P = np.asarray(P, F32).copy()
    for _ in range(iters):
        f = fn(P); g = grad(fn, P)
        g2 = np.maximum((g * g).sum(1), 1e-8)
        step = (f / g2)[:, None] * g
        if max_step is not None:
            sl = length(step)
            step *= np.minimum(1, max_step / np.maximum(sl, 1e-9))[:, None]
        P -= step
    return P


def normals(fn, P):
    g = grad(fn, P)
    return g / np.maximum(length(g), 1e-9)[:, None]


def sample(fn, lo, hi, h, band=3.0, coarse=4, log=None):
    """Evaluate fn on a grid lo..hi with spacing h. Returns (F, origin). Narrow band around the surface only."""
    lo = np.asarray(lo, float); hi = np.asarray(hi, float)
    n = np.ceil((hi - lo) / h).astype(int) + 1
    H = h * coarse
    nc = np.ceil((n - 1) / coarse).astype(int) + 2
    # coarse pass
    gx, gy, gz = [lo[i] + np.arange(nc[i]) * H for i in range(3)]
    C = np.empty(nc, F32)
    for k in range(nc[2]):
        X, Y = np.meshgrid(gx, gy, indexing='ij')
        P = np.stack([X.ravel(), Y.ravel(), np.full(X.size, gz[k])], 1).astype(F32)
        C[:, :, k] = fn(P).reshape(nc[0], nc[1])
    near = np.abs(C) < band * H
    # dilate by one coarse cell
    nd = near.copy()
    for ax in range(3):
        nd |= np.roll(near, 1, ax) | np.roll(near, -1, ax)
    F = np.empty(n, F32)
    ix = np.arange(n[0]); iy = np.arange(n[1])
    cx = np.minimum((ix + coarse // 2) // coarse, nc[0] - 1); cy = np.minimum((iy + coarse // 2) // coarse, nc[1] - 1)
    evals = 0
    for k in range(n[2]):
        ck = min((k + coarse // 2) // coarse, nc[2] - 1)
        Cs = C[:, :, ck][cx][:, cy]
        Ns = nd[:, :, ck][cx][:, cy]
        sl = np.where(Cs < 0, -band * H, band * H).astype(F32)
        if Ns.any():
            ii, jj = np.nonzero(Ns)
            P = np.stack([lo[0] + ii * h, lo[1] + jj * h, np.full(ii.size, lo[2] + k * h)], 1).astype(F32)
            sl[ii, jj] = fn(P)
            evals += ii.size
        F[:, :, k] = sl
    if log:
        log('  grid %s, exact evals %.1fM' % (tuple(n), evals / 1e6))
    return F, lo


def surface_nets(F, origin, h):
    """Quad mesh from a sampled field. Returns verts (M,3) float32, quads (Q,4) int."""
    nx, ny, nz = F.shape
    s = F < 0
    cnt = np.zeros((nx - 1, ny - 1, nz - 1), np.uint8)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                cnt += s[dx:nx - 1 + dx, dy:ny - 1 + dy, dz:nz - 1 + dz]
    active = (cnt > 0) & (cnt < 8)
    del cnt
    idx = np.argwhere(active)
    vid = np.full(active.shape, -1, np.int32)
    vid[active] = np.arange(len(idx), dtype=np.int32)
    acc = np.zeros((len(idx), 3), np.float64); num = np.zeros(len(idx))
    corners = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
    edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    fc = [F[idx[:, 0] + c[0], idx[:, 1] + c[1], idx[:, 2] + c[2]] for c in corners]
    for a, b in edges:
        fa, fb = fc[a], fc[b]
        m = (fa < 0) != (fb < 0)
        t = np.where(m, fa / np.where(m, fa - fb, 1), 0)
        ca = np.asarray(corners[a]); cb = np.asarray(corners[b])
        p = ca[None, :] + t[:, None] * (cb - ca)[None, :]
        acc[m] += p[m]; num[m] += 1
    V = origin + h * (idx + acc / np.maximum(num, 1)[:, None])
    quads = []
    # edges along each axis with a sign change -> quad of the 4 surrounding cells
    for axis in range(3):
        a1, a2 = [(1, 2), (2, 0), (0, 1)][axis]
        sl0 = [slice(None)] * 3; sl1 = [slice(None)] * 3
        sl0[axis] = slice(0, F.shape[axis] - 1); sl1[axis] = slice(1, F.shape[axis])
        f0 = F[tuple(sl0)]; f1 = F[tuple(sl1)]
        ch = (f0 < 0) != (f1 < 0)
        e = np.argwhere(ch)
        e = e[(e[:, a1] >= 1) & (e[:, a2] >= 1) & (e[:, a1] < F.shape[a1] - 1) & (e[:, a2] < F.shape[a2] - 1)]
        inside = f0[e[:, 0], e[:, 1], e[:, 2]] < 0

        def cell(d1, d2):
            c = e.copy(); c[:, a1] -= d1; c[:, a2] -= d2
            return vid[c[:, 0], c[:, 1], c[:, 2]]
        q = np.stack([cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)], 1)
        q = np.where(inside[:, None], q, q[:, ::-1])
        quads.append(q)
    Q = np.concatenate(quads)
    Q = Q[(Q >= 0).all(1)]
    return V.astype(F32), Q


def mesh(fn, lo, hi, h, log=None, project_iters=2):
    F, o = sample(fn, lo, hi, h, log=log)
    V, Q = surface_nets(F, o, h)
    del F
    if project_iters:
        V = project(fn, V, project_iters, max_step=h)
    if log:
        log('  surface nets: %d verts, %d quads' % (len(V), len(Q)))
    return V, Q
