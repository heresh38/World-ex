"""The head's hair (Project Orion male), as strands, to the owner's portrait: thick dark hair, short and tapered on the
sides and the back, long on top, swept up and back with volume, a few locks falling forward over his forehead's
right side; a short boxed beard (dense on the chin and the moustache, a clean line across each cheek); heavy, low,
straight brows; lashes on both lids. Blender hair curves, rendered with the Principled Hair BSDF (dark brown-black).

Strands grow from roots spread over each region of the scalp / face (head.py's frame, cm), stand off the skin at the
root (volume), follow a flow over the head and lie onto it, held off the skin by the head's own distance field;
locks: children follow their clump's guide more and more toward the tips. The game's hair (cards / grooms) comes
from these strands later.
"""
import math
import numpy as np

F32 = np.float32


def to_head(P, H):
    return np.c_[P[:, 0] * 100, (P[:, 1] - H.Y0) * 100, (P[:, 2] - H.Z0) * 100]


def to_world(Q, H):
    return np.c_[Q[..., 0] / 100, Q[..., 1] / 100 + H.Y0, Q[..., 2] / 100 + H.Z0]


def HAIRLINE(ax):
    """the forehead's hairline (z, cm) at |x|: a man's, a little recessed at the temples"""
    return 5.8 + .07 * ax * ax - .35 * np.exp(-((ax - 4.6) / 1.0) ** 2)


def scalp_density(Q):
    """where hair grows (0..1, cm): bounded by a man's hairline with soft edges, never by boxes (boxes left a straight
    vertical cut at each temple and a level cut across the nape): the forehead's line, then down past the temple to
    the sideburn in front of the ear, round the ear, and the nape's line, tapering"""
    x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
    ramp = lambda v, w: np.clip(v / w, 0, 1)
    fore = ramp(z - HAIRLINE(x) + .3, .7) ** .8                       # the forehead's line
    temple = ramp(y - (-5.6 + .48 * (6.6 - z)), .55)                   # the temple's edge: back and down to ...
    burn = ramp(y + 2.7, .3) * ramp(z + 2.7, .35)                      # ... the sideburn's foot
    side = np.maximum(temple * ramp(z + 1.2, .5), burn) * (x > 4.2)
    face = np.where(y < -5.0, fore, 1.0) * np.where((x > 4.2) & (z < 6.6) & (y < 1.0), side, 1.0)  # (in front of the ear)
    nape = ramp(z - (-6.0 + .12 * x), .8) ** 1.3                      # the nape's line, tapering
    behind_ear = np.where(y > -.5, nape, 1.0)
    return (face * behind_ear * (z > -7.5)).astype(F32)


def scalp_mask(Q):
    """the scalp (cm): where any hair grows (scalp_density)"""
    return scalp_density(Q) > .02


def scalp_shade(Q, H):
    """how much the scalp's skin is shaded by the hair's roots (0..1 per point): a fade's short hair reads as hair
    from a distance only with its roots' shadow under it"""
    return (scalp_density(Q) * (H.ear(Q) > .7)).astype(F32)


def beard_mask(Q, H, soft=False):
    """the beard (cm): under a line across each cheek (from the sideburn down to beside the mouth), the moustache,
    the chin, the jaw, under it to the neck; the lips bare. soft: 0..1, fading in over a centimetre at its borders,
    fuller on the chin and the moustache"""
    x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
    st = H.stom_z
    cheek_line = -2.0 - 1.2 * np.clip(6.4 - x, 0, 3.0)                  # the sideburn down to beside the mouth
    # the lips bare: the beard (the moustache, the soul patch) grows right to the vermilion's own border, which the
    # lips' volume gives (a fixed band round the mouth made the moustache's edge a straight line over the bow)
    import headbase as HB
    lp = HB.lips(Q, st, H.k)[0]
    W = HB.MOUTH_W * H.k("mouth_width")
    corner = (x - W) ** 2 + ((z - st) / .8) ** 2 < .3 ** 2
    lips = ((lp < .14) | corner) & (y < -9.0)
    under_nose = (z > H.subn[0] - .15) & (x < 1.6)
    moust = (x < W + .3) & (z < H.subn[0] - .1) & (z > st) & (y < -9.0)
    if not soft:
        face = (y < 1.5) & ((z < cheek_line) | moust) & (z > -15.5)
        neck = (z < -13.0) & (y > -5.0)
        return face & ~lips & ~under_nose & ~neck
    f = np.clip((cheek_line - z) / 1.2, 0, 1)
    fm = np.clip((H.subn[0] - .1 - z) / .4, 0, 1) * np.clip((W + .3 - x) / .5, 0, 1) * (z > st) * (y < -9.0)
    f = np.maximum(f, fm) * np.clip((z + 14.0) / 1.5, 0, 1) * (y < 1.5)
    f = f * np.where((z < -13.0) & (y > -5.0), np.clip((-13.0 - z) * 0 + 1 - (z + 13.0) * -.6, 0, 1), 1.0)
    full = .55 + .45 * np.maximum(np.exp(-((z + 10.6) / 2.2) ** 2) * np.exp(-(x / 2.8) ** 2),
                                  (z > st) * (x < 3.0) * 1.0)
    return f * full * ~lips * ~under_nose


def strands_from(roots, normals, flow, length, k, H, lift0=.9, lift1=.12, gravity=0.0, noise=.08, rng=None,
                 hug=.06, reach=None):
    """strands of k points from each root (cm): they stand off the skin at the root, turn into the flow and lie
    onto the head, kept `hug` cm off its skin by the head's own field and, given `reach`, no further off it than
    that (the hair's volume: rising from the root they lie back inside it, layered, instead of standing up)"""
    rng = rng or np.random.default_rng(1)
    n = len(roots)
    hug = np.broadcast_to(np.asarray(hug, F32), (n,))
    gravity = np.broadcast_to(np.asarray(gravity, F32), (n,))
    reach = None if reach is None else np.broadcast_to(np.asarray(reach, F32), (n,))
    P = np.zeros((n, k, 3), F32)
    p = roots - normals * .03
    P[:, 0] = p
    step = (length / (k - 1))[:, None]
    for i in range(1, k):
        t = i / (k - 1)
        lift = lift0 + (lift1 - lift0) * min(1.0, t * 1.6)
        d = normals * lift + flow * (1 - lift)
        d[:, 2] -= gravity * t
        d += rng.normal(0, noise * t, d.shape)
        d /= np.linalg.norm(d, axis=1)[:, None] + 1e-9
        p = p + d * step
        # held off the skin
        W = to_world(p, H)
        dist = H(W) * 100
        under = dist < hug
        if under.any():
            gW = grad_world(H, W[under])
            p[under] += gW * (hug[under] - dist[under])[:, None]
        if reach is not None:
            over = dist > reach
            if over.any():
                gO = grad_world(H, W[over])
                p[over] -= gO * (dist[over] - reach[over])[:, None]
        P[:, i] = p
    return P


def onto_scalp(P, H, hug, reach, iters=2):
    """every point but the root of each strand (n x k x 3, cm) held between `hug` and `reach` cm off the skin"""
    n, k, _ = P.shape
    hug = np.broadcast_to(np.asarray(hug, F32), (n,))
    reach = np.broadcast_to(np.asarray(reach, F32), (n,))
    Q = P[:, 1:].reshape(-1, 3).copy()
    hq, rq = np.repeat(hug, k - 1), np.repeat(reach, k - 1)
    for _ in range(iters):
        W = to_world(Q, H)
        dist = H(W) * 100
        bad = (dist < hq) | (dist > rq)
        if not bad.any():
            break
        g = grad_world(H, W[bad])
        target = np.clip(dist[bad], hq[bad], rq[bad])
        Q[bad] += g * (target - dist[bad])[:, None]
    out = P.copy()
    out[:, 1:] = Q.reshape(n, k - 1, 3)
    return out


def grad_world(H, W, e=2e-4):
    g = np.zeros_like(W)
    for a in range(3):
        d = np.zeros(3, F32); d[a] = e
        g[:, a] = (H(W + d) - H(W - d)) / (2 * e)
    return g / (np.linalg.norm(g, axis=1)[:, None] + 1e-9)


def clump(P, groups, amount):
    """children follow their clump's guide (its first strand) more and more toward the tips"""
    out = P.copy()
    k = P.shape[1]
    w = (np.linspace(0, 1, k) ** 1.4 * amount)[None, :, None]
    for g in groups:
        if len(g) < 2:
            continue
        guide = P[g[0]]
        rel = guide - guide[0]
        out[g] = P[g] * (1 - w[0]) + (P[g][:, :1] + rel[None]) * w[0]
    return out


def soft_noise(P, scale, seed=0, k=7):
    """a smooth noise in space (cm): a sum of plane waves in random directions, -1..1, features about `scale` cm"""
    r = np.random.default_rng(seed)
    D = r.normal(size=(k, 3)); D /= np.linalg.norm(D, axis=1)[:, None]
    ph = r.uniform(0, 2 * np.pi, k)
    f = 2 * np.pi / scale * r.uniform(.7, 1.3, k)
    return (np.sin(P @ D.T * f + ph)).sum(1) / np.sqrt(k / 2)


def hair(V, N, H, n=120000, rng=None):
    """the scalp's hair (world points, the head's vertices and normals)"""
    rng = rng or np.random.default_rng(7)
    Q = to_head(V, H)
    soft = scalp_density(Q)                       # a man's hairline with soft edges (lower and denser at the front)
    ear_v = H.ear(Q)                              # the ears' own distance (cm): nothing grows on them (the owner:
    m = (soft > .02) & (ear_v > .7)               # "the ears are hairy"), a bare rim round each
    cand = np.nonzero(m & (soft > .02))[0]
    wgt = soft[cand] / soft[cand].sum()
    idx = rng.choice(cand, size=min(n, len(cand)), replace=True, p=wgt)
    R, Nn = Q[idx] + rng.normal(0, .05, (len(idx), 3)), N[idx]
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    ax = np.abs(x)
    # ONE style, combed in one direction (the owner: "the hair doesn't seem continuous in one direction ... the
    # side of the head is almost bald ... too much hair at the top front"), then "add some style to it though like
    # do a fade": a FADE on the sides and the back, near the skin low down and growing smoothly to a couple of
    # centimetres at the top of the sides, dense all the way; the top longer, swept back, a soft lift at the front
    topw = np.clip((z - 4.0) / 3.0, 0, 1) * np.clip((5.8 - ax) / 2.8, 0, 1) * np.clip((7.0 - y) / 4.0, 0, 1)
    topw = topw * topw * (3 - 2 * topw)           # the top blends into the fade down the back (a block hung over it)
    top = topw
    zb = -2.6 - 3.0 * np.clip((y - 1.0) / 4.0, 0, 1)      # the fade's foot: round the ears, lower at the nape
    f = np.clip((z - zb) / (5.2 - zb), 0, 1)
    L_side = .12 + 1.9 * f ** 1.5                         # 1 mm at the foot, 2 cm at the top of the sides
    L_top = 3.0 + 3.8 * np.clip((5.0 - y) / 9.0, 0, 1)     # long at the front, shorter to the crown (the owner:
    # "the hair on the top of the head looks like a building, 3 stories": the long top ended in a ledge there)
    L = L_side * (1 - topw) + L_top * topw
    ear_r = H.ear(R)
    L *= np.where(ear_r < 2.0, .5 + .5 * np.clip((ear_r - .7) / 1.3, 0, 1), 1.0)     # tapered close round the ears
    L *= rng.uniform(.85, 1.12, len(L))
    # the flow: back over the top from the hairline, back and down over the sides and the back: one field
    side = np.clip((ax - 3.0) / 3.5, 0, 1) * np.clip((7.5 - z) / 4.0, 0, 1)
    behind = np.clip((y - 2.0) / 4.0, 0, 1) * np.clip((8.5 - z) / 4.0, 0, 1)
    wd = np.maximum(side, behind)[:, None]
    wd = wd * wd * (3 - 2 * wd)
    flow = np.c_[np.zeros(len(x)), np.ones(len(x)), np.zeros(len(x))] * (1 - wd)         + np.c_[np.sign(x) * .25, .35 * np.ones(len(x)), -np.ones(len(x))] * wd
    flow[:, 0] += .12 * topw                                       # the top swept a little to his left
    flow[:, 2] += .32 * np.clip((-y - 4.0) / 4.0, 0, 1) * topw     # up off the hairline, then back
    by_ear = ear_r < 2.5                          # round the ears the hair goes back, not down over them
    flow[by_ear] = np.c_[np.sign(x[by_ear]) * .1, np.ones(by_ear.sum()), -.2 * np.ones(by_ear.sum())]
    flow /= np.linalg.norm(flow, axis=1)[:, None]
    # the roots' rise follows the blend (switched at a line it stood the top's hair up as a wall over the fade)
    lift0 = (.25 + (.40 + .10 * np.clip((-y - 4.0) / 2.0, 0, 1)) * topw)[:, None]
    # the volume: the fade close to the head (as far off it as it is long), the top full and even, a little more
    # at its front (a soft lift, not a pile)
    lift = np.clip((-y + 1.0) / 8.0, 0, 1)
    reach = np.maximum(.05, .55 * L_side) * (1 - topw) + (1.05 + .7 * lift) * topw    # a soft quiff at the front
    reach *= np.clip(1 + .08 * soft_noise(R, 5.0, 3), .9, 1.1) * rng.uniform(.93, 1.06, len(top))
    stray = (topw > .5) & (rng.random(len(top)) < .01)  # a few strays (a head of hair is never combed perfectly)
    reach = np.where(stray, reach * 1.2, reach)
    P = strands_from(R, Nn, flow, L, 14, H, lift0=lift0, lift1=np.where(stray, .2, .06)[:, None],
                     gravity=.25 * topw, noise=.28, rng=rng, hug=.03 + .3 * topw, reach=reach)
    # locks: clumps of neighbours round seeds
    seeds = rng.choice(len(R), 900, replace=False)
    from_seed = np.argmin(((R[:, None, :] - R[seeds][None, :, :]) ** 2).sum(2), axis=1)
    groups = [np.r_[seeds[i], np.nonzero(from_seed == i)[0]] for i in range(len(seeds))]
    P = clump(P, groups, .7)
    # a lock follows its guide's path from its own root: on the crown's curve that path left the scalp and the locks
    # stood up in a knob there; every point is held between the skin and the hair's own reach again
    P = onto_scalp(P, H, .03 + .3 * topw, reach / np.where(stray, 1.2, 1.0))
    # and no strand lies on an ear
    n, k, _ = P.shape
    touch = (H.ear(P.reshape(-1, 3)).reshape(n, k) < .3).any(axis=1)
    return P[~touch]


def beard(V, N, H, n=75000, rng=None):
    rng = rng or np.random.default_rng(3)
    Q = to_head(V, H)
    m = beard_mask(Q, H)
    w = beard_mask(Q, H, soft=True) * (H.ear(Q) > .6)
    cand = np.nonzero(w > .02)[0]
    idx = rng.choice(cand, size=n, replace=True, p=w[cand] / w[cand].sum())
    R, Nn = Q[idx] + rng.normal(0, .03, (len(idx), 3)), N[idx]
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    chin = np.exp(-((z + 10.5) / 2.0) ** 2) * np.exp(-(x / 2.6) ** 2)
    moust = (z > H.stom_z) & (np.abs(x) < 3.0)
    L = .2 + .24 * chin + .1 * moust                         # a short boxed beard, 2-4.5 mm, fuller on the chin
    L *= rng.uniform(.7, 1.25, len(L))
    flow = np.zeros_like(R)
    flow[:, 2] = -1.0
    flow[:, 0] = np.where(moust, np.sign(x) * .8, 0.0)
    flow[:, 1] = np.where(z < -11.5, .9, 0.0)
    flow /= np.linalg.norm(flow, axis=1)[:, None]
    return strands_from(R, Nn, flow, L, 5, H, lift0=.5, lift1=.32, noise=.3, rng=rng, hug=.02)


def brows(H, n=1350, rng=None):
    """roots along each brow: thick at its head by the nose, thin at its tail, the hairs up at the head, out along it"""
    rng = rng or np.random.default_rng(5)
    t = rng.random(n)
    u = rng.normal(0, .33, n)
    x = 1.15 + 4.95 * t
    # a man's brow: heavy, low and nearly straight over the orbit's rim; its tail runs on past the eye's outer
    # corner and down along the rim toward the temple (the owner: "the eyebrows are too short")
    # low at its head, highest two thirds out (a man's arch is shallow), easing down past the eye's corner (dropping
    # from the head outward it read as a worried look)
    zc = 1.12 + .26 * np.sin(np.pi * np.clip(t / 1.24, 0, 1)) - .08 * t - .16 * np.clip((t - .82) / .18, 0, 1) ** 2
    w = .78 * (1 - .5 * t)                  # heavy: about 9 mm deep at its head, tapering to the tail
    z = zc + u * w
    R = np.c_[x, np.full(n, -12.0), z]
    out = []
    for sx in (1, -1):
        Rs = R.copy(); Rs[:, 0] *= sx
        Qs = onto_face(Rs, H)                        # straight back onto the skin, where each was meant to be
        Ns = grad_world(H, to_world(Qs, H))
        body = np.c_[sx * (.8 + .2 * t), -.1 * np.ones(n),
                     .3 - .55 * t - .25 * np.clip((t - .8) / .2, 0, 1) - .3 * np.clip(u / .33, -1.5, 1.5)]
        head = np.c_[sx * .75 * np.ones(n), -.1 * np.ones(n), .55 * np.ones(n)]    # the head's hairs up and OUT
        # (straight up they stood taller than the brow: raised inner ends, a worried look)
        hw = np.clip((t - .04) / .16, 0, 1)[:, None]
        flow = head * (1 - hw) + body * hw
        flow /= np.linalg.norm(flow, axis=1)[:, None]
        L = (.6 + .22 * (1 - t)) * (.7 + .3 * np.clip(t / .2, 0, 1))      # the head's hairs short
        out.append(strands_from(Qs, Ns, flow, L * rng.uniform(.75, 1.1, n), 6, H, lift0=.18, lift1=.04, noise=.2,
                                rng=rng, hug=.012))
    return np.concatenate(out)


def onto_face(Q, H, y0=-13.5, y1=-4.0, step=.05):
    """points (head cm) carried straight back (+y) onto the skin, keeping their x and z: the first place the head's
    field turns inside along each one's line, refined by halving. (Slid down the field's gradient instead, the
    brows' roots ran up onto the brow ridge and in toward the nose: the brow 1.6 cm short and 7 mm high, highest at
    its head, a worried look.)"""
    Q = np.asarray(Q, F32)
    ys = np.arange(y0, y1, step, dtype=F32)
    out = Q.copy()
    hit = np.full(len(Q), -1)
    for j, yv in enumerate(ys):
        todo = np.nonzero(hit < 0)[0]
        if not len(todo):
            break
        P = Q[todo].copy(); P[:, 1] = yv
        inside = H(to_world(P, H)) < 0
        hit[todo[inside]] = j
    for i in np.nonzero(hit >= 0)[0]:
        a_, b_ = ys[max(hit[i] - 1, 0)], ys[hit[i]]
        for _ in range(12):
            m = .5 * (a_ + b_)
            P = Q[i:i + 1].copy(); P[0, 1] = m
            if H(to_world(P, H))[0] < 0:
                b_ = m
            else:
                a_ = m
        out[i, 1] = b_
    return out


def lashes(H, n_up=115, n_lo=65, rng=None):
    """the eyelashes (there were none): a row along each lid's margin, rooted on its front edge; the upper ones
    longer in the middle and toward the outer corner, curling up and a little out, the lower ones short and sparse,
    curving down"""
    import head as HM
    rng = rng or np.random.default_rng(11)
    out = []
    for upper, n in ((True, n_up), (False, n_lo)):
        t = np.sort(rng.random(n)) * .94 + .03
        x = HM.EN[0] + (HM.EX[0] - HM.EN[0]) * t
        _, up, lo = H.fissure(x, np.zeros_like(x))
        z = up + .015 if upper else lo - .015
        for sx in (1, -1):
            R = np.c_[sx * x, np.full(n, HM.EYE[1] - 2.2), z].astype(F32)
            Qs = onto_face(R, H, y0=HM.EYE[1] - 2.6, y1=HM.EYE[1])     # straight back onto the lid's front edge
            Ns = grad_world(H, to_world(Qs, H))
            if upper:
                flow = np.c_[sx * .25 * (t - .3), -.97 * np.ones(n), -.08 * np.ones(n)]  # out of the eye, forward
                L = (.45 + .25 * np.sin(np.pi * np.clip(t * .85 + .1, 0, 1))) * rng.uniform(.85, 1.1, n)
                curl = -.55             # then curling up (curled harder they lay back on the lid up to the brow)
            else:
                flow = np.c_[sx * .15 * (t - .4), -.9 * np.ones(n), -.3 * np.ones(n)]
                L = (.22 + .14 * np.sin(np.pi * t)) * rng.uniform(.8, 1.15, n)
                curl = .5
            flow /= np.linalg.norm(flow, axis=1)[:, None]
            out.append(strands_from(Qs, Ns, flow, L, 7, H, lift0=.15, lift1=.0, gravity=curl, noise=.08, rng=rng,
                                    hug=.01))
    return np.concatenate(out)


def to_curves(name, P, H, r_root, r_tip, material):
    import bpy
    n, k, _ = P.shape
    W = to_world(P.reshape(-1, 3), H).astype(F32)
    c = bpy.data.hair_curves.new(name)
    c.add_curves([k] * n)
    c.position_data.foreach_set("vector", W.ravel())
    rad = c.attributes.get("radius") or c.attributes.new("radius", 'FLOAT', 'POINT')
    t = np.linspace(0, 1, k)
    rad.data.foreach_set("value", np.tile(r_root * (1 - t) + r_tip * t, n).astype(F32))
    o = bpy.data.objects.new(name, c)
    bpy.context.scene.collection.objects.link(o)
    c.materials.append(material)
    return o


def hair_material(name, melanin=.9, redness=.45, rough=.32):
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        if nd.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(nd)
    h = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    h.parametrization = 'MELANIN'
    h.inputs["Melanin"].default_value = melanin
    h.inputs["Melanin Redness"].default_value = redness
    h.inputs["Roughness"].default_value = rough
    h.inputs["Radial Roughness"].default_value = .32
    h.inputs["Coat"].default_value = .1
    for key, v in (("Random Color", .14), ("Random Roughness", .12)):      # no two hairs quite the same colour
        try:
            h.inputs[key].default_value = v
        except KeyError:
            pass
    out = [nd for nd in nt.nodes if nd.type == 'OUTPUT_MATERIAL'][0]
    nt.links.new(h.outputs[0], out.inputs["Surface"])
    return m


def groom(V, N, H, log=print, beard_on=False):
    """all of it as curve objects; returns the beard's mask per head vertex (the skin darkens under it). The base
    model is clean-shaven (the owner, 2026-11-16: "remove the beard/mustache for the base model as we will have an
    option for the player to include it when we build the full character builder"); the beard is an option
    (beard_on), and without it the mask is empty"""
    hm = hair_material("hair", .92, .3, .3)
    bm = hair_material("beard", .992, .25, .36)
    wm = hair_material("brows", .965, .3, .34)                 # dark brown, not black
    lm = hair_material("lashes", .97, .25, .3)
    P = hair(V, N, H)
    to_curves("hair", P, H, .000065, .00002, hm)
    log(f"groom: hair {len(P)} strands")
    if not beard_on:
        Bw = brows(H)
        to_curves("brows", Bw, H, .000038, .000011, wm)
        log(f"groom: brows {len(Bw)} strands, no beard")
        La = lashes(H)
        to_curves("lashes", La, H, .00005, .000012, lm)
        log(f"groom: lashes {len(La)}")
        return np.zeros(len(V), F32)
    B = beard(V, N, H)
    to_curves("beard", B, H, .000036, .000014, bm)
    log(f"groom: beard {len(B)} strands")
    Bw = brows(H)
    to_curves("brows", Bw, H, .000038, .000011, wm)
    log(f"groom: brows {len(Bw)} strands")
    La = lashes(H)
    to_curves("lashes", La, H, .00005, .000012, lm)
    log(f"groom: lashes {len(La)}")
    return beard_mask(to_head(V, H), H, soft=True)
