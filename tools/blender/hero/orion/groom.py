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


def scalp_mask(Q):
    """the scalp (cm): above the forehead's hairline with the temples' recession, the sideburns, round the ears,
    down to the nape"""
    x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
    front = z > 6.2 + .07 * x * x - .45 * np.exp(-((x - 4.6) / 1.0) ** 2)
    top = (y > -7.6) & (z > 3.2)
    side = (x > 5.6) & (y > -3.4) & (y < 3.0) & (z > 1.2)
    burn = (x > 6.0) & (y > -2.6) & (y < -.8) & (z > -2.6)               # the sideburns in front of the ear
    behind = (y > 2.6) & (z > -5.5 - .0 * x)
    ear = ((x > 6.4) & (y > -1.2) & (y < 2.2) & (z < 1.6) & (z > -5.5))
    return (front | top | side | burn | behind) & ~ear & (z > -6.0)


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


def hair(V, N, H, n=60000, rng=None):
    """the scalp's hair (world points, the head's vertices and normals)"""
    rng = rng or np.random.default_rng(7)
    Q = to_head(V, H)
    m = scalp_mask(Q)
    ax0, z0 = np.abs(Q[:, 0]), Q[:, 2]
    line = 6.2 + .07 * ax0 * ax0 - .45 * np.exp(-((ax0 - 4.6) / 1.0) ** 2)
    soft = np.where((Q[:, 1] < -5.0) & (z0 > 3.2), np.clip((z0 - line + .35) / 1.0, 0, 1) ** .8, 1.0)
    ear_v = H.ear(Q)                              # the ears' own distance (cm): nothing grows on them (the owner:
    m = m & (ear_v > .7)                          # "the ears are hairy"), a bare rim round each
    cand = np.nonzero(m & (soft > .02))[0]
    wgt = soft[cand] / soft[cand].sum()
    idx = rng.choice(cand, size=min(n, len(cand)), replace=True, p=wgt)
    R, Nn = Q[idx] + rng.normal(0, .05, (len(idx), 3)), N[idx]
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    ax = np.abs(x)
    # how long: long on top, tapering short down the sides and the back
    top = np.clip((z - 3.0) / 4.0, 0, 1) * np.clip(1 - (ax - 3.5) / 3.0, 0, 1)
    L = 1.3 + 7.8 * top + .8 * np.clip((z - 1.0) / 6, 0, 1)
    L *= np.where(ax > 5.2, .6, 1.0)
    ear_r = H.ear(R)                              # round the ears short, the fade of a cut
    L *= np.where(ear_r < 2.5, .35 + .65 * np.clip((ear_r - .7) / 1.8, 0, 1), 1.0)
    L *= rng.uniform(.8, 1.15, len(L))
    # the flow: up and back on top, back and down on the sides, down at the back
    flow = np.zeros_like(R)
    flow[:, 1] = 1.0
    flow[:, 2] = np.where(z > 5.0, .35 * np.clip((-y - 2) / 6, 0, 1), -.7)        # the front swept up, then back
    flow[:, 0] = np.sign(x) * np.where(ax > 4.5, .25, .05)
    back = y > 3.0
    flow[back] = np.c_[np.sign(x[back]) * .15, .25 * np.ones(back.sum()), -np.ones(back.sum())]
    # the locks over the forehead's right side fall forward and down
    lock = (x < -1.0) & (x > -4.2) & (y < -6.5) & (z > 6.0) & (rng.random(len(x)) < .30)
    flow[lock] = np.c_[-.25 * np.ones(lock.sum()), -.55 * np.ones(lock.sum()), -.75 * np.ones(lock.sum())]
    L[lock] *= 1.15
    by_ear = ear_r < 3.0                          # over and round the ears the hair goes back, not down over them
    flow[by_ear] = np.c_[np.sign(x[by_ear]) * .1, np.ones(by_ear.sum()), .15 * np.ones(by_ear.sum())]
    flow /= np.linalg.norm(flow, axis=1)[:, None]
    lift0 = np.where(top > .3, .9, .45)[:, None]
    # the volume: fullest over the front of the top (the portrait's swept-up front), close on the sides
    front = .7 + .3 * np.clip((-y - 2.0) / 6.0, 0, 1)
    reach = (.45 + 1.7 * top * front) * rng.uniform(.82, 1.12, len(top))
    P = strands_from(R, Nn, flow, L, 14, H, lift0=lift0, lift1=.08, gravity=.3 * (1 - .5 * top), noise=.36,
                     rng=rng, hug=.15 + .45 * top, reach=reach)
    # locks: clumps of neighbours round seeds
    seeds = rng.choice(len(R), 1500, replace=False)
    from_seed = np.argmin(((R[:, None, :] - R[seeds][None, :, :]) ** 2).sum(2), axis=1)
    groups = [np.r_[seeds[i], np.nonzero(from_seed == i)[0]] for i in range(len(seeds))]
    P = clump(P, groups, .82)
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


def brows(H, n=720, rng=None):
    """roots along each brow: thick at its head by the nose, thin at its tail, the hairs up at the head, out along it"""
    rng = rng or np.random.default_rng(5)
    t = rng.random(n)
    u = rng.normal(0, .33, n)
    x = 1.15 + 4.95 * t
    # a man's brow: heavy, low and nearly straight over the orbit's rim; its tail runs on past the eye's outer
    # corner and down along the rim toward the temple (the owner: "the eyebrows are too short")
    zc = 1.32 + .05 * np.sin(np.pi * np.clip(t / .7, 0, 1)) - .05 * t - .42 * np.clip((t - .66) / .34, 0, 1) ** 1.5
    w = .52 * (1 - .45 * t)
    z = zc + u * w
    R = np.c_[x, np.full(n, -12.0), z]
    out = []
    for sx in (1, -1):
        Rs = R.copy(); Rs[:, 0] *= sx
        W = to_world(Rs, H)
        # onto the skin: down the field's gradient
        for _ in range(12):
            d = H(W)
            g = grad_world(H, W)
            W = W - g * d[:, None]
        Qs = to_head(W, H)
        Ns = grad_world(H, W)
        flow = np.c_[sx * (.8 + .2 * t), -.1 * np.ones(n), .35 - .5 * t - .4 * np.clip((t - .66) / .34, 0, 1)]
        flow /= np.linalg.norm(flow, axis=1)[:, None]
        L = .7 + .25 * (1 - t)
        out.append(strands_from(Qs, Ns, flow, L * rng.uniform(.75, 1.1, n), 6, H, lift0=.42, lift1=.16, noise=.26,
                                rng=rng, hug=.02))
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
    P = hair(V, N, H)
    to_curves("hair", P, H, .00006, .00002, hm)
    log(f"groom: hair {len(P)} strands")
    if not beard_on:
        Bw = brows(H)
        to_curves("brows", Bw, H, .00005, .000014, bm)
        log(f"groom: brows {len(Bw)} strands, no beard")
        return np.zeros(len(V), F32)
    B = beard(V, N, H)
    to_curves("beard", B, H, .000036, .000014, bm)
    log(f"groom: beard {len(B)} strands")
    Bw = brows(H)
    to_curves("brows", Bw, H, .00005, .000014, bm)
    log(f"groom: brows {len(Bw)} strands")
    return beard_mask(to_head(V, H), H, soft=True)
