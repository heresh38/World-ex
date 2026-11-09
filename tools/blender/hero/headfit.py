"""Places the head cage (head.py) on the anatomical head (headshape.py) before anything is subdivided.

Nearest-point projection folds a coarse head (the face is concave round the eyes, the nose and mouth stick out), so
the head is placed the way a modeller lays loops on a sculpt:

  1. every grid vertex of the quad sphere is shot from the head's centre along a ray onto the head (the first exit
     from inside), the cranium as it is; on the front the rows are remapped first so the cube's rows land on the face's
     landmarks: the eye cells on the eyes, the brow row above them, the nose's base and the mouth cell on the mouth
  2. the eye and mouth openings and the two loops round each are laid explicitly: the eyelid fissure (an almond on the
     eyeball, the upper lid higher, a slight upward tilt outward), the lid, the orbit; the lips' slit, the lips'
     middle, the vermilion border
  3. the nose's extruded cap is laid on the nose: the root at the nasion, down the dorsum to the tip, the lobule and
     the alae at the base; the ears' caps onto the ears
  4. the neck opening goes round the neck just under the jaw (a little higher at the nape); the cells under the head
     between it and the face / skull are relaxed (harmonic) and projected onto the body
"""
import math
import numpy as np
from mathutils import Vector
import bmesh
import sdf

F32 = np.float32


def first_exit(fn, C, D, t0=.005, t1=.30, step=.002):
    """for rays C + t D (D: n x 3 unit) the first t where fn turns positive (leaving the solid), refined by bisection"""
    C = np.asarray(C, F32)
    n = len(D)
    hit = np.full(n, t1, F32)
    done = np.zeros(n, bool)
    for k in range(int((t1 - t0) / step) + 1):
        tk = t0 + k * step
        idx = np.where(~done)[0]
        if not len(idx):
            break
        f = fn(C + D[idx] * tk)
        out = f > 0
        hit[idx[out]] = tk
        done[idx[out]] = True
    lo, hi = np.maximum(hit - step, t0), hit.copy()
    for _ in range(22):
        mid = (lo + hi) / 2
        inside = fn(C + D * mid[:, None]) < 0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    return (lo + hi) / 2


def front_y(fn, x, z, y_in):
    """the outermost surface toward -y at (x, z), from y_in (inside the solid) forward"""
    n = len(x)
    C = np.stack([x, y_in, z], 1).astype(F32)
    D = np.array([0, -1, 0], F32)
    step = .0015
    hit = np.full(n, 400 * step, F32)
    done = np.zeros(n, bool)
    for k in range(400):
        idx = np.where(~done)[0]
        if not len(idx):
            break
        out = fn(C[idx] + D * (k * step)) > 0
        hit[idx[out]] = k * step
        done[idx[out]] = True
    lo, hi = np.maximum(hit - step, 0), hit
    for _ in range(22):
        mid = (lo + hi) / 2
        inside = fn(C + D * mid[:, None]) < 0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    return C[:, 1] - (lo + hi) / 2


def rings_out(loop, depth):
    """the hole loop and the loops round it (each vertex's chain outward through the inset rings)"""
    rings = [list(loop)]
    seen = set(loop)
    for _ in range(depth):
        nxt = []
        for v in rings[-1]:
            cand = [e.other_vert(v) for e in v.link_edges if e.other_vert(v) not in seen]
            # the ring vertex outward: the one not on the current ring (an inset ring vertex has exactly one)
            nxt.append(cand[0] if len(cand) == 1 else min(cand, key=lambda w: (w.co - v.co).length))
        seen.update(nxt)
        rings.append(nxt)
    return rings


def place_head(cage, body, T, log=print):
    H = cage.head
    g = body.head_geometry()
    hs, chin, ez = g["hs"], g["chin"], g["ez"]
    ezr = (ez - chin) / hs
    cc = H["centre"]
    rx, ry, rz = H["radii"]
    C = np.array(g["centre"], F32)
    Y0 = float(C[1])
    skull = lambda P: body.part("skull", P)
    bm = cage.bm
    verts = {k: v for k, v in H["verts"].items() if v.is_valid}
    caps = {v: c for v, c in H["caps"].items() if v.is_valid}
    feat = H["feat"]
    placed = {}

    # ---------------------------------------------------------------- 1. the grid, shot from the centre
    # target elevation (degrees, seen from the centre at eye height) of the front rows j (cube face row, -6..6)
    def elev(zr, yr):
        return math.degrees(math.atan2((zr - ezr) * hs, -yr * hs))
    rows = [(-6, elev(.028, -.0915)), (-5, elev(.068, -.097)), (-1, elev(ezr - .020, -.086)), (0, elev(ezr + .022, -.094)),
            (1, elev(ezr + .038, -.096)), (6, math.degrees(math.atan2(rz, ry)))]
    rj = np.array([r[0] for r in rows], float)
    re = np.array([r[1] for r in rows], float)
    # (bmesh's inset may keep a grid vertex on an inner ring, so the grid dict is not the surface: shoot every head
    # vertex except the bottom face's inside; the rings, caps and neck are laid explicitly afterwards)
    under = [k for k in verts if k[2] == -6 and abs(k[0]) < 6 and abs(k[1]) < 6]       # the bottom face's inside
    under_v = {verts[k] for k in under}
    shoot = [v for v in bm.verts if cage.part_of.get(v) == "head" and v not in under_v]
    P = np.array([v.co for v in shoot], F32)
    d = P - np.array(cc, F32)
    dx, dy, dz = d[:, 0], d[:, 1], d[:, 2]
    hor = np.hypot(dx, dy) + 1e-9
    e = np.degrees(np.arctan2(dz, hor))
    az = np.arctan2(dx, -dy)
    nrm = np.sqrt((dx / rx) ** 2 + (dy / ry) ** 2 + (dz / rz) ** 2)
    fwd = np.clip(-dy / ry / nrm, 0, 1)
    w = np.clip((fwd - .35) / .45, 0, 1)
    w = w * w * (3 - 2 * w)
    jf = 6 * (dz / rz) / np.maximum(-dy / ry, 1e-3)
    et = np.interp(np.clip(jf, -6, 6), rj, re)
    e2 = np.radians(e + w * (et - e))
    D = np.stack([np.cos(e2) * np.sin(az), -np.cos(e2) * np.cos(az), np.sin(e2)], 1).astype(F32)
    t = first_exit(skull, C, D)
    Q = C + D * t[:, None]
    for v, q in zip(shoot, Q):
        v.co = Vector(q)
        placed[v] = True

    # ---------------------------------------------------------------- 2. eyes and mouth
    ec, er = g["eye_c"], g["eye_r"]

    G = {v: k for k, v in verts.items()}

    def lay(loop, depth, spec, centre_fn, surface):
        """rings 0..depth-1 round a hole; each chain's outer (grid) vertex gives its place: u across, top / bottom"""
        R = rings_out(loop, depth)
        keys = [next(G[v] for v in ch if v in G) for ch in zip(*R)]
        i0, i1 = min(k[0] for k in keys), max(k[0] for k in keys)
        jt = max(k[2] for k in keys)
        for k, ring in enumerate(R[:depth]):
            Wk, Hk, Lk = spec[k]
            pts = np.array([centre_fn((2 * key[0] - i0 - i1) / (i1 - i0), key[2] == jt, Wk, Hk, Lk) for key in keys], F32)
            ys = surface(k, pts)
            for v, p, y in zip(ring, pts, ys):
                v.co = Vector((p[0], y, p[1]))
                placed[v] = True
        return R

    hu, hl, wf = g["eye_hu"], g["eye_hl"], T["eye_w"] / 2
    for side, sx in (("eye_L", 1), ("eye_R", -1)):
        def eye_pt(u, top, W, Hh, Lh, sx=sx):
            ue = u * sx * .94                                   # + = lateral (toward the temple)
            s = math.sqrt(max(0.0, 1 - ue * ue))
            lift = .0008 * hs * ue
            if top:                                             # (the same rounded arc as fit.place_features)
                v = Hh * s ** .8 * (1 - .08 * ue) + lift
            else:
                v = -Lh * s ** .85 * (1 + .10 * ue) + lift
            if ue > 0:                                          # the outer rings fan out more toward the temple
                W = wf + (W - wf) * 1.7
            return (ec.x * sx + ue * W * sx, ec.z + v)

        def eye_surface(k, pts):
            if k == 0:                                          # the fissure on the eyeball (the canthi wrap
                # round it: the fissure is wider than the globe, so it is laid on the globe compressed across)
                du = (pts[:, 0] - ec.x * np.sign(pts[:, 0])) * (.76 * er / wf)
                dv = pts[:, 1] - ec.z
                return ec.y - np.sqrt(np.maximum((er + .0004) ** 2 - du * du - dv * dv, 1e-8))
            return front_y(body, pts[:, 0], pts[:, 1], np.full(len(pts), ec.y, F32))
        lay(feat[side], 3, [(wf, hu, hl), (wf * 1.10, hu * 1.40, hl * 1.55), (wf * 1.22, hu * 1.85, hl * 2.2)], eye_pt, eye_surface)

    st, mw = g["stomion"], g["mouth_w"]

    def mouth_pt(u, top, W, Hh, Lh):
        ue = u * .96
        s = math.sqrt(max(0.0, 1 - ue * ue)) ** .7
        return (ue * W, st.z + (Hh if top else -Lh) * s)

    def mouth_surface(k, pts):
        return front_y(body, pts[:, 0], pts[:, 1], np.full(len(pts), st.y + .025, F32))
    lay(feat["mouth"], 3, [(mw / 2, .0004 * hs, .0004 * hs), (mw / 2 * 1.08, .0050 * hs, .0060 * hs),
                           (mw / 2 * 1.20, .0100 * hs, .0115 * hs)], mouth_pt, mouth_surface)

    # ---------------------------------------------------------------- 3. the nose's cap and the ears' caps
    nasion, tip, sub = g["nasion"], g["pronasale"], g["subnasale"]
    nose = [(v, c[1]) for v, c in caps.items() if c[0] == "nose"]
    zs = {0: nasion.z - .003 * hs, -1: nasion.z - .013 * hs, -2: nasion.z - .023 * hs, -3: tip.z + .006 * hs,
          -4: tip.z - .005 * hs, -5: sub.z + .0045 * hs}
    ws = {0: .0050, -1: .0062, -2: .0072, -3: .0068, -4: .0070, -5: .0105}
    pts = np.array([(gk[0] * ws[gk[2]] * hs, zs[gk[2]]) for v, gk in nose], F32)
    ys = front_y(body, pts[:, 0], pts[:, 1], np.full(len(pts), Y0 - .06, F32))
    for (v, gk), p, y in zip(nose, pts, ys):
        v.co = Vector((p[0], y, p[1]))
        placed[v] = True
    ears = [(v, c) for v, c in caps.items() if c[0].startswith("ear")]
    if ears:
        for v, (part, gk) in ears:
            sx = 1 if part.endswith("L") else -1
            base = verts.get(gk)
            if base is not None and base.is_valid and base in placed:
                v.co = base.co + Vector((.010 * sx, .004, 0))
        Pe = np.array([v.co for v, c in ears], F32)
        Pe = sdf.project(lambda X: body.part("ear", X), Pe, iters=10, max_step=.01)
        for (v, c), p in zip(ears, Pe):
            v.co = Vector(p)
            placed[v] = True

    # ---------------------------------------------------------------- 4. the neck opening and the cells under the head
    loop = [v for v in feat["neck"] if v.is_valid]
    gc = np.array([G[v] for v in loop], float)
    cyg = (gc[:, 1].min() + gc[:, 1].max()) / 2
    ang = np.arctan2(gc[:, 0], -(gc[:, 1] - cyg))           # 0 = front
    zf, zb = chin - .016 * hs, chin + .004 * hs
    zl = zf + (zb - zf) * (1 - np.cos(ang)) / 2
    Dh = np.stack([np.sin(ang), -np.cos(ang), np.zeros_like(ang)], 1).astype(F32)
    ny = Y0 + .006 * hs
    out = []
    for i in range(len(loop)):
        Ci = np.array([0, ny, zl[i]], F32)
        ti = first_exit(body, Ci, Dh[i:i + 1], t0=.0, t1=.12, step=.002)[0]
        out.append(Ci + Dh[i] * ti)
    for v, p in zip(loop, out):
        v.co = Vector(p)
        placed[v] = True
    free = [verts[k] for k in under if verts[k] not in placed]
    for _ in range(200):                                    # harmonic: each free vertex to its neighbours' mean
        for v in free:
            nb = [e.other_vert(v) for e in v.link_edges]
            v.co = sum((w.co for w in nb), Vector()) / len(nb)
    if free:
        Pf = sdf.project(body, np.array([v.co for v in free], F32), iters=8, max_step=.01)
        for v, p in zip(free, Pf):
            v.co = Vector(p)
            placed[v] = True
    log(f"head placed: {len(shoot)} shot, {len(nose)} nose, {len(ears)} ear, {len(loop)} neck loop, {len(free)} under")
    return set(placed)
