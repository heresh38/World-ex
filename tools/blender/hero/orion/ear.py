"""The game head's ears (Project Orion male): a clean ring grid on the sculpt's own ear.

The head's cage leaves a window on each side of the head (headcage.EAR_WIN); subdivided, its border is a loop of n
vertices round the ear's place. The ear is cut out of the sculpt where its own field takes over from the head's (a
dense surface-nets patch round it, cut exactly along ear - rest = 0: the middle of the blend where the auricle grows
out of the head), laid flat onto a disc (harmonic: the cut onto the circle by its length, the inside by the
cotangent Laplacian), and a ring grid is drawn in the disc: n spokes, the outer ring on the cut (the window's loop
is moved there and the head's skin relaxed round it), rings at equal lengths down each spoke, a rectangular cap in
the middle. Laid back onto the sculpt (barycentric in the disc, then onto its surface). Every vertex is a smooth
function of the field's shape, so the face's ear sliders move the ear as one.

(The first game ear, the window lifted out, capped over and laid onto the sculpt by nearest points, crumpled over
the helix and into the concha: its normals stood 31 degrees off the sculpt's at the median.)
"""
import copy
import math
import numpy as np

F32 = np.float32
RINGS = 22                      # rings from the cut to the cap


# ---------------------------------------------------------------------------------------------------------------
# the window's loop in the subdivided head

def boundary_loops(faces):
    """every boundary loop of a quad mesh (vertex indices, in order)"""
    F = np.asarray(faces)
    a = F.ravel()
    b = np.roll(F, -1, axis=1).ravel()
    key = np.minimum(a, b) * (1 << 32) + np.maximum(a, b)
    uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    one = cnt[inv] == 1
    nxt = {}
    for u, v in zip(a[one], b[one]):
        nxt[int(u)] = int(v)
    loops, seen = [], set()
    for s in list(nxt):
        if s in seen:
            continue
        loop, v = [], s
        while v not in seen and v in nxt:
            seen.add(v); loop.append(v); v = nxt[v]
        if len(loop) > 2:
            loops.append(loop)
    return loops


def cap_loop(faces, cap):
    """the border of the faces `cap` (a boolean per face: the window's subdivided cap), in order: the window's loop"""
    F = np.asarray(faces)[cap]
    a = F.ravel()
    b = np.roll(F, -1, axis=1).ravel()
    key = np.minimum(a, b) * (1 << 32) + np.maximum(a, b)
    uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    one = cnt[inv] == 1
    nxt = {int(u): int(v) for u, v in zip(a[one], b[one])}
    s = next(iter(nxt))
    loop, v = [], s
    while True:
        loop.append(v)
        v = nxt[v]
        if v == s:
            break
    if len(loop) != len(nxt):
        raise RuntimeError(f"ear: the window's border is not one loop ({len(loop)} of {len(nxt)})")
    return loop


# ---------------------------------------------------------------------------------------------------------------
# the sculpt's ear, cut out and laid flat

def _rest(hd):
    """the head without its ears"""
    hr = copy.copy(hd)
    hr.ear = lambda Q: np.full(len(Q), 10.0, F32)
    return hr


def _to_cm(P, hd):
    return np.c_[P[:, 0] * 100, (P[:, 1] - hd.Y0) * 100, (P[:, 2] - hd.Z0) * 100].astype(F32)


def cut_patch(hd, sx, h=.0005, log=print):
    """(V, T, loop): the ear's skin as triangles (metres) and its border loop (vertex indices, in order)"""
    import sdf
    lo_cm = np.array([5.0 if sx > 0 else -10.8, -3.6, -7.2])
    hi_cm = np.array([10.8 if sx > 0 else -5.0, 5.6, 4.2])
    lo = np.array([lo_cm[0] / 100, hd.Y0 + lo_cm[1] / 100, hd.Z0 + lo_cm[2] / 100], F32)
    hi = np.array([hi_cm[0] / 100, hd.Y0 + hi_cm[1] / 100, hd.Z0 + hi_cm[2] / 100], F32)
    V, Q = sdf.mesh(hd, lo, hi, h)
    V = np.asarray(V, np.float64)
    hr = _rest(hd)
    Qc = _to_cm(V, hd)
    s = hd.ear(hd.warp(Qc)).astype(np.float64) - hr.cm(Qc).astype(np.float64)
    T = np.r_[Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]].astype(np.int64)
    # the exact cut: each triangle clipped to its ear side (s < 0), new vertices where an edge crosses s = 0
    neg = s < 0
    nneg = neg[T].sum(1)
    keep = [T[nneg == 3]]
    mixed = T[(nneg > 0) & (nneg < 3)]
    extra, cross = [], {}

    def xv(a, b):
        k = (min(a, b), max(a, b))
        if k not in cross:
            t = s[a] / (s[a] - s[b])
            cross[k] = len(V) + len(extra)
            extra.append(V[a] + (V[b] - V[a]) * t)
        return cross[k]
    out = []
    for tri in mixed:
        tri = list(tri)
        # rotate so the odd one out is first
        sg = [neg[v] for v in tri]
        odd = next(i for i in range(3) if sum(sg) == 1 and sg[i] or sum(sg) == 2 and not sg[i])
        a, b, c = tri[odd:] + tri[:odd]
        if neg[a]:                                     # one corner in: a smaller triangle
            out.append((a, xv(a, b), xv(a, c)))
        else:                                          # two in: a quad, as two triangles
            p, q = xv(a, b), xv(a, c)
            out.append((p, b, c)); out.append((p, c, q))
    if out:
        keep.append(np.array(out, np.int64))
    T = np.concatenate(keep)
    if extra:
        V = np.r_[V, np.array(extra)]
    # the piece round the ear's origin; its holes (if the cut left any inside it) filled back in
    T = _largest_component(T, V, hd, sx)
    loop = _outer_loop(T, V)
    # drop unused vertices
    used = np.unique(T)
    remap = np.full(len(V), -1, np.int64); remap[used] = np.arange(len(used))
    log(f"ear {'L' if sx > 0 else 'R'}: the sculpt's ear cut out, {len(T)} triangles, its base {len(loop)} points")
    return V[used], remap[T], [int(remap[v]) for v in loop]


def _tri_adjacency(T):
    e = np.c_[T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]].reshape(-1, 2)
    key = np.minimum(e[:, 0], e[:, 1]) * (1 << 32) + np.maximum(e[:, 0], e[:, 1])
    tri = np.repeat(np.arange(len(T)), 3)
    order = np.argsort(key, kind="stable")
    ks, ts = key[order], tri[order]
    same = ks[1:] == ks[:-1]
    return ts[:-1][same], ts[1:][same]


def _components(n, a, b):
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for u, v in zip(a, b):
        ru, rv = find(int(u)), find(int(v))
        if ru != rv:
            parent[ru] = rv
    return np.array([find(i) for i in range(n)])


def _largest_component(T, V, hd, sx):
    a, b = _tri_adjacency(T)
    comp = _components(len(T), a, b)
    o = np.array([.0705 * sx, hd.Y0 + .0015, hd.Z0 - .016])
    cen = V[T].mean(1)
    near = np.linalg.norm(cen - o, axis=1)
    labels, counts = np.unique(comp, return_counts=True)
    # the biggest piece within 4 cm of the canal's opening
    best = max(labels, key=lambda L: (counts[labels == L][0] if near[comp == L].min() < .04 else 0))
    return T[comp == best]


def _outer_loop(T, V):
    e = np.c_[T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]].reshape(-1, 2)
    key = np.minimum(e[:, 0], e[:, 1]) * (1 << 32) + np.maximum(e[:, 0], e[:, 1])
    uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    one = e[cnt[inv] == 1]
    nxt = {int(u): int(v) for u, v in one}
    loops, seen = [], set()
    for s in list(nxt):
        if s in seen:
            continue
        loop, v = [], s
        while v not in seen and v in nxt:
            seen.add(v); loop.append(v); v = nxt[v]
        loops.append(loop)
    length = lambda lp: np.linalg.norm(V[lp] - V[np.roll(lp, -1)], axis=1).sum()
    return max(loops, key=length)


def disc(V, T, loop, iters=4000):
    """harmonic coordinates (u, v) in the unit disc: the loop onto the circle by its length, the inside by the
    cotangent Laplacian (cotangents clamped above zero: no fold), solved by conjugate gradients"""
    n = len(V)
    P = V[loop]
    seg = np.linalg.norm(P - np.roll(P, -1, axis=0), axis=1)
    ang = 2 * np.pi * np.r_[0, np.cumsum(seg)[:-1]] / seg.sum()
    UV = np.zeros((n, 2))
    UV[loop, 0], UV[loop, 1] = np.cos(ang), np.sin(ang)
    # cotangent weights
    I, J, W = [], [], []
    for k in range(3):
        i, j, o = T[:, k], T[:, (k + 1) % 3], T[:, (k + 2) % 3]
        u_, v_ = V[i] - V[o], V[j] - V[o]
        cot = (u_ * v_).sum(1) / np.maximum(np.linalg.norm(np.cross(u_, v_), axis=1), 1e-12)
        cot = np.maximum(cot, .02) * .5
        I.append(i); J.append(j); W.append(cot)
    I, J, W = np.concatenate(I), np.concatenate(J), np.concatenate(W)
    deg = np.bincount(I, weights=W, minlength=n) + np.bincount(J, weights=W, minlength=n)
    fixed = np.zeros(n, bool); fixed[loop] = True
    free = ~fixed

    def L(x):                                         # (L x) for the free unknowns, the fixed ones held at 0
        y = deg * x
        y -= np.bincount(I, weights=W * x[J], minlength=n) + np.bincount(J, weights=W * x[I], minlength=n)
        return y
    for c in range(2):
        xb = np.where(fixed, UV[:, c], 0.0)
        b = -L(xb)
        b[fixed] = 0
        x = np.zeros(n)
        r = b.copy(); r[fixed] = 0
        p = r.copy(); rr = (r * r).sum()
        for _ in range(iters):
            Ap = L(p); Ap[fixed] = 0
            al = rr / max((p * Ap).sum(), 1e-30)
            x += al * p; r -= al * Ap
            rn = (r * r).sum()
            if rn < 1e-20:
                break
            p = r + (rn / rr) * p; rr = rn
        UV[free, c] = x[free]
    return UV, ang


class Locator:
    """which triangle of the disc a point falls in, and where (a grid of buckets over the disc)"""

    def __init__(self, UV, T, n=96):
        self.UV, self.T, self.n = UV, T, n
        tmin = UV[T].min(1); tmax = UV[T].max(1)
        g = lambda x: np.clip(((x + 1.0001) / 2.0002 * n).astype(int), 0, n - 1)
        self.buckets = {}
        a0, a1, b0, b1 = g(tmin[:, 0]), g(tmax[:, 0]), g(tmin[:, 1]), g(tmax[:, 1])
        for t in range(len(T)):
            for i in range(a0[t], a1[t] + 1):
                for j in range(b0[t], b1[t] + 1):
                    self.buckets.setdefault((i, j), []).append(t)
        self.g = g

    def __call__(self, Pq, V):
        out = np.zeros((len(Pq), 3))
        for q, (x, y) in enumerate(Pq):
            cand = self.buckets.get((int(self.g(np.array([x]))[0]), int(self.g(np.array([y]))[0])), [])
            best, bw = None, -1e9
            for t in cand:
                a, b, c = self.UV[self.T[t]]
                d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(d) < 1e-18:
                    continue
                l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
                l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
                l3 = 1 - l1 - l2
                m = min(l1, l2, l3)
                if m > bw:
                    best, bw, lam = t, m, (l1, l2, l3)
                    if m >= 0:
                        break
            if best is None:
                raise RuntimeError("ear: a point fell outside the disc")
            i, j, k = self.T[best]
            out[q] = lam[0] * V[i] + lam[1] * V[j] + lam[2] * V[k]
        return out


# ---------------------------------------------------------------------------------------------------------------
# the ring grid

def cap_sides(n):
    """a rectangle's sides (m, k) for the cap inside a ring of n: 2 (m + k) = n, a little longer than wide"""
    half = n // 2
    m = max(2, int(round(half * .38)))
    return m, half - m


def build(hf, sx, start, rings=RINGS, cap_r=None, log=print):
    """the ear on side sx for the field hf, its outer ring matched to `start` (the window loop's current points, in
    order: its count is the ring's). Returns (ring0, inner, faces): ring0 (n, 3) the window loop's new places, inner
    the new vertices (m, 3), faces quads over local indices (0..n-1 the window loop, n.. the new vertices), wound
    outward"""
    hd = hf.hd
    V, T, loop = cut_patch(hd, sx, log=log)
    UV, ang = disc(V, T, loop)
    n = len(start)
    # the cut resampled at n points by its length; start and direction matched to the window loop's
    P = V[loop]
    seg = np.linalg.norm(P - np.roll(P, -1, axis=0), axis=1)
    cum = np.r_[0, np.cumsum(seg)]
    total = cum[-1]

    def at(fr):                                        # the cut's point and angle at fractions of its length
        fr = np.mod(fr, 1.0) * total
        i = np.clip(np.searchsorted(cum, fr, side="right") - 1, 0, len(P) - 1)
        t = (fr - cum[i]) / np.maximum(seg[i], 1e-12)
        return P[i] + (P[(i + 1) % len(P)] - P[i]) * t[:, None], 2 * np.pi * fr / total
    best = None
    for direction in (1, -1):
        for off in np.linspace(0, 1, 360, endpoint=False):
            fr = off + direction * np.arange(n) / n
            X, _ = at(fr)
            err = ((X - start) ** 2).sum()
            if best is None or err < best[0]:
                best = (err, fr)
    fr = best[1]
    ring0, phi = at(fr)
    # each spoke: from the cut to the cap's ring, sampled finely in the disc, laid back in 3D, then cut into rings
    # of equal lengths
    loc = Locator(UV, T)
    if cap_r is None:
        cap_r = .30
    rs = np.linspace(1.0, cap_r, 160)
    spokes = np.zeros((n, rings + 1, 3))
    spoke_uv = np.zeros((n, rings + 1, 2))
    for k in range(n):
        c, s_ = math.cos(phi[k]), math.sin(phi[k])
        Pq = np.c_[rs * c, rs * s_] * .999
        X = loc(Pq, V)
        X[0] = ring0[k]
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(X, axis=0), axis=1))]
        want = np.linspace(0, L[-1], rings + 1)
        idx = np.clip(np.searchsorted(L, want, side="right") - 1, 0, len(L) - 2)
        t = (want - L[idx]) / np.maximum(L[idx + 1] - L[idx], 1e-12)
        spokes[k] = X[idx] + (X[idx + 1] - X[idx]) * t[:, None]
        r_at = rs[idx] + (rs[idx + 1] - rs[idx]) * t
        spoke_uv[k] = np.c_[r_at * c, r_at * s_]
    spokes[:, 0] = ring0
    # the cap: a rectangle's grid inside the last ring (a Coons patch in the disc, laid back in 3D)
    m, kk = cap_sides(n)
    last = spoke_uv[:, -1]
    c0, c1, c2, c3 = 0, m, m + kk, 2 * m + kk
    bottom = last[[c0 + i for i in range(m + 1)]]                  # (m+1): corner 0 -> corner 1
    right = last[[(c1 + j) % n for j in range(kk + 1)]]            # (kk+1): corner 1 -> corner 2
    top = last[[(c3 - i) % n for i in range(m + 1)]]               # corner 3 -> corner 2 reversed to run 0..m
    left = last[[(c0 - j) % n for j in range(kk + 1)]]             # corner 0 -> corner 3 (backwards round the ring)
    grid_uv = np.zeros((m + 1, kk + 1, 2))
    for i in range(m + 1):
        for j in range(kk + 1):
            u, v = i / m, j / kk
            grid_uv[i, j] = ((1 - v) * bottom[i] + v * top[i] + (1 - u) * left[j] + u * right[j]
                             - ((1 - u) * (1 - v) * bottom[0] + u * (1 - v) * bottom[m] + (1 - u) * v * top[0] + u * v * top[m]))
    inner_uv = grid_uv[1:m, 1:kk].reshape(-1, 2)
    inner_cap = loc(inner_uv * .999, V) if len(inner_uv) else np.zeros((0, 3))
    # vertices: ring 0 is the window loop (local 0..n-1), rings 1..R new, then the cap's inside
    verts = [spokes[:, j] for j in range(1, rings + 1)]
    inner = np.concatenate(verts + [inner_cap])
    ring_id = lambda j, k: k % n if j == 0 else n + (j - 1) * n + (k % n)
    faces = []
    for j in range(rings):
        for k in range(n):
            faces.append((ring_id(j, k), ring_id(j, k + 1), ring_id(j + 1, k + 1), ring_id(j + 1, k)))
    base_cap = n + rings * n

    def cap_id(i, j):                                  # grid (i 0..m, j 0..kk) -> local vertex
        if j == 0:
            return ring_id(rings, c0 + i)
        if i == m:
            return ring_id(rings, c1 + j)
        if j == kk:
            return ring_id(rings, c3 - i)
        if i == 0:
            return ring_id(rings, c0 - j)
        return base_cap + (i - 1) * (kk - 1) + (j - 1)
    for i in range(m):
        for j in range(kk):
            faces.append((cap_id(i, j), cap_id(i + 1, j), cap_id(i + 1, j + 1), cap_id(i, j + 1)))
    faces = np.array(faces, np.int64)
    # onto the sculpt's surface, then wound outward (the field's gradient at the first quad of every ring)
    allv = np.r_[ring0, inner]
    allv = _onto(hd, allv)
    ring0, inner = allv[:n], allv[n:]
    import sdf
    c = allv[faces[:n * 2]].mean(1)
    fn = np.cross(allv[faces[:n * 2, 1]] - allv[faces[:n * 2, 0]], allv[faces[:n * 2, 3]] - allv[faces[:n * 2, 0]])
    g = sdf.grad(hd, c)
    if (fn * g).sum() < 0:
        faces = faces[:, ::-1]
    log(f"ear {'L' if sx > 0 else 'R'}: {len(inner)} new vertices, {len(faces)} quads, cap {m} x {kk}")
    return ring0, inner, faces


def _onto(hd, X, steps=5):
    import sdf
    X = np.asarray(X, np.float64).copy()
    for _ in range(steps):
        d = hd(X).astype(np.float64)
        g = sdf.grad(hd, X)
        g /= np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]
        X -= g * np.clip(d, -.003, .003)[:, None]
    return X


# ---------------------------------------------------------------------------------------------------------------
# into the mesh

def attach(o, me, co, ears, drop, keys=None, log=print):
    """the windows' caps (faces `drop`, a boolean per face) cut out and the ears' new vertices and quads stitched to
    their loops (a new mesh: the body's kept vertices first, in their order, then each side's ear in the order the
    face keys use: his left, then his right); the attributes carried (the head's share 1 on the ears, the ears'
    faces the head's region). keys: {name: (n, 3) deltas over the old vertices + the ears'}, remapped too.
    Returns (mesh, co, keys)"""
    import bpy
    sides = sorted(ears, reverse=True)
    nl = len(me.loops)
    lv = np.zeros(nl, np.int64); me.loops.foreach_get("vertex_index", lv)
    ls = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get("loop_total", lt)
    keep_f = np.flatnonzero(~np.asarray(drop))
    used = np.zeros(len(co), bool)
    for f in keep_f:
        used[lv[ls[f]:ls[f] + lt[f]]] = True
    kept = np.flatnonzero(used)
    remap = np.full(len(co), -1, np.int64); remap[kept] = np.arange(len(kept))
    n0 = len(kept)
    faces = [tuple(remap[lv[ls[f]:ls[f] + lt[f]]]) for f in keep_f]
    V = [np.asarray(co, np.float64)[kept]]
    nxt = n0
    for s in sides:
        lp, ring0, inner, ef = ears[s]
        if (remap[lp] < 0).any():
            raise RuntimeError("ear: the window's loop was cut out with its cap")
        V[0][remap[lp]] = ring0
        loc = np.r_[remap[lp], np.arange(nxt, nxt + len(inner))]
        faces += [tuple(int(v) for v in loc[f]) for f in ef]
        V.append(inner)
        nxt += len(inner)
    V = np.concatenate(V)
    n_old = len(co)
    if keys:
        keys = {k: np.r_[D[:n_old][kept], D[n_old:]] for k, D in keys.items()}
    me2 = bpy.data.meshes.new(me.name)
    me2.from_pydata(V.astype(np.float32), [], faces)
    me2.update()
    sm = np.zeros(len(me.polygons), bool); me.polygons.foreach_get("use_smooth", sm)
    sm = sm[keep_f]
    me2.polygons.foreach_set("use_smooth", np.r_[sm, np.full(len(me2.polygons) - len(sm), bool(sm.all()))])
    for a in list(me.attributes):
        if a.domain != 'POINT' or a.data_type != 'FLOAT' or a.name.startswith(".") or a.name == "position":
            continue
        vals = np.zeros(n_old, np.float32); a.data.foreach_get("value", vals)
        fill = 1.0 if a.name == "headw" else 0.0
        b = me2.attributes.new(a.name, 'FLOAT', 'POINT')
        b.data.foreach_set("value", np.r_[vals[kept], np.full(len(V) - n0, fill, np.float32)])
    for a in list(me.attributes):                          # face attributes (the body's regions): the ears are the head's
        if a.domain != 'FACE' or a.data_type != 'INT' or a.name.startswith(".") or a.name in ("earcap", "ear"):
            continue
        vals = np.zeros(len(ls), np.int32); a.data.foreach_get("value", vals)
        b = me2.attributes.new(a.name, 'INT', 'FACE')
        b.data.foreach_set("value", np.r_[vals[keep_f], np.zeros(len(me2.polygons) - len(keep_f), np.int32)])
    ear = me2.attributes.new("ear", 'INT', 'FACE')        # which ear a face is (1 his left, 2 his right; 0 none)
    ev = np.zeros(len(me2.polygons), np.int32)
    at = len(keep_f)
    for s in sides:
        k = len(ears[s][3])
        ev[at:at + k] = 1 if s > 0 else 2
        at += k
    ear.data.foreach_set("value", ev)
    for m in me.materials:
        me2.materials.append(m)
    old = o.data
    o.data = me2
    bpy.data.meshes.remove(old)
    log(f"ears stitched in: {len(V) - n0} vertices, {len(faces) - len(keep_f)} quads; the windows' caps cut out "
        f"({len(co) - n0} vertices, {len(ls) - len(keep_f)} faces)")
    return me2, V.astype(np.float32), keys
