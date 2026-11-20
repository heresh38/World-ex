"""The head's hair for the game (Project Orion male): the groom's own strands (groom.hair: one style, combed back,
a fade on the sides and the back, the top longer and swept) turned into what a game draws:

  * CARDS (`B_hair`, material `hair`): the long hair in locks, each lock a ribbon along its strands' mean line,
    lying along the scalp at the lock's own height off it, as wide as the lock, its strands drawn from an atlas
    (game.hair_atlas: clumps of tapered strands, alpha their coverage); the cards follow the face's sliders;
  * the SCALP in the face's skin map: every strand's root drawn as a short hair into the map's hair mask (the
    same channel the brows use: M_SOSkin lays HairColor over the skin by it), so the fade is short hair on skin,
    and under the top's cards a soft floor of hair so no bare scalp shows between them.

The owner's sheet: short dark hair, thick on top, swept back and up from the hairline, short at the sides.
"""
import os
import numpy as np

F32 = np.float32


def _log(*a):
    print("[hair]", *a, flush=True)


def head_verts(me):
    """the head's vertices and normals of the game body (world metres)"""
    n = len(me.vertices)
    co = np.zeros(n * 3, F32); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
    nr = np.zeros(n * 3, F32); me.vertices.foreach_get("normal", nr); nr = nr.reshape(n, 3)
    hw = np.zeros(n, F32); me.attributes["headw"].data.foreach_get("value", hw)
    sel = np.flatnonzero(hw > .5)
    return co[sel], nr[sel], sel


def head_surface(me, n, rng):
    """n points spread over the head's faces (world metres) with the skin's normal there: the groom roots a hair on
    each point it is given, and the game head's own vertices are 3 mm apart (5000 on the scalp, where the sculpt's
    fine mesh gave it 120000 roots)"""
    nv = len(me.vertices)
    co = np.zeros(nv * 3, F32); me.vertices.foreach_get("co", co); co = co.reshape(nv, 3)
    nr = np.zeros(nv * 3, F32); me.vertices.foreach_get("normal", nr); nr = nr.reshape(nv, 3)
    hw = np.zeros(nv, F32); me.attributes["headw"].data.foreach_get("value", hw)
    nf = len(me.polygons)
    ls = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_total", lt)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    tris = []
    for f in range(nf):
        s_, t_ = ls[f], lt[f]
        vs = lv[s_:s_ + t_]
        if hw[vs].min() < .5:
            continue
        for j in range(1, t_ - 1):
            tris.append((vs[0], vs[j], vs[j + 1]))
    tris = np.array(tris, np.int64)
    A, Bv, Cv = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    area = .5 * np.linalg.norm(np.cross(Bv - A, Cv - A), axis=1)
    pick = rng.choice(len(tris), size=n, p=area / area.sum())
    r1, r2 = rng.random(n), rng.random(n)
    u = 1 - np.sqrt(r1); v = np.sqrt(r1) * (1 - r2); w = np.sqrt(r1) * r2
    t = tris[pick]
    P = co[t[:, 0]] * u[:, None] + co[t[:, 1]] * v[:, None] + co[t[:, 2]] * w[:, None]
    N = nr[t[:, 0]] * u[:, None] + nr[t[:, 1]] * v[:, None] + nr[t[:, 2]] * w[:, None]
    N /= np.maximum(np.linalg.norm(N, axis=1), 1e-9)[:, None]
    return P.astype(F32), N.astype(F32)


def grow(body, hd, n=120000, seed=7):
    """the groom's strands rooted on the game head (head cm, (m, k, 3))"""
    import groom as GR
    rng = np.random.default_rng(seed)
    V, N = head_surface(body.data, 260000, rng)
    return np.asarray(GR.hair(V, N, hd, n=n, rng=rng), F32)


def lengths(P):
    return np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1)


def kmeans(P, k, rng, iters=10, chunk=4000):
    """k groups of the points P (n, 3) by nearness (chunked: a whole distance table of 30k x 1400 was a gigabyte)"""
    P = np.asarray(P, F32)
    C = P[rng.choice(len(P), k, replace=False)].copy()
    lab = np.zeros(len(P), np.int64)
    for _ in range(iters):
        for s in range(0, len(P), chunk):
            Q = P[s:s + chunk]
            d = (Q * Q).sum(1)[:, None] - 2 * Q @ C.T + (C * C).sum(1)[None, :]
            lab[s:s + chunk] = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                C[j] = P[m].mean(0)
    return [np.flatnonzero(lab == j) for j in range(k) if (lab == j).sum() >= 3]


def build_cards(P, hd, rng, n_cards=1400, min_len=3.0, width=1.0, sample=14000):
    """the long hair as cards in two layers: the strands longer than `min_len` cm, a sample of them grouped into
    `n_cards` locks by their roots (width in HEAD CM: a lock is a centimetre or two across; written in metres the
    cards were hairlines); each lock a card along its own line (the outer layer, the locks' volume) and a
    second card laid onto the scalp under it from the dense columns of the atlas (the base layer: no scalp seen
    between the locks). game.cards_from draws them"""
    import game as G
    import groom as GR
    L = lengths(P)
    # the top's hair only (the fade's short hair is drawn into the skin map): a lock whose root lies on the top
    x, y, z = np.abs(P[:, 0, 0]), P[:, 0, 1], P[:, 0, 2]
    topw = np.clip((z - 4.0) / 3.0, 0, 1) * np.clip((5.8 - x) / 2.8, 0, 1) * np.clip((7.0 - y) / 4.0, 0, 1)
    long = np.flatnonzero((L > min_len) & (topw > .25))
    sub = rng.choice(long, size=min(sample, len(long)), replace=False)
    groups = [sub[g] for g in kmeans(P[sub, 0], min(n_cards, len(sub) // 4), rng)]
    Pd = P.astype(np.float64)
    V, F, UV = G.cards_from(Pd, hd, groups, width, G.HAIR_COLS, rng, None)
    # the base layer: the same locks pressed onto the scalp
    flat = GR.onto_scalp(P.copy(), hd, np.full(len(P), .25, F32), np.full(len(P), .45, F32), iters=3)
    # (from the same sparse columns as the outer layer: the game draws the alpha masked, and a dense column made
    # every base card an opaque tile; the dark floor under the cards is the scalp's own hair mask)
    V2, F2, UV2 = G.cards_from(np.asarray(flat, np.float64), hd, groups, width * 1.1, G.HAIR_COLS, rng, None)
    UV2 = np.asarray(UV2).copy()
    off = len(V)
    V = np.concatenate([V, V2])
    F = list(F) + [tuple(int(v) + off for v in f) for f in F2]
    UV = np.concatenate([np.asarray(UV), UV2])
    _log(f"{len(groups)} locks, {len(F)} cards' quads in two layers, from {len(long)} long strands ({len(P)} grown)")
    return V, F, UV


def make_hair(body, out, hd=None, P=None, log=_log):
    """B_hair on the body: the cards, their atlas, the face's keys from the skin under each vertex"""
    import bpy
    import game as G
    import head as HD
    hd = hd or HD.Head()
    rng = np.random.default_rng(23)
    for ob in [ob for ob in bpy.context.scene.objects if ob.name.startswith("B_hair")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    png = os.path.join(out, "orion_male_hair_strands.png")
    # (the game draws the alpha MASKED, cut at a third: the strands need gaps between them, or every card is a tile)
    G.hair_atlas(png, size=2048, seed=5, base=(.026, .018, .013), tip=(.070, .050, .036), coarse=.85, per=(10, 16),
                 taper=.6, dense=0)
    if P is None:
        P = grow(body, hd)
    V, F, UV = build_cards(P, hd, rng)
    me = bpy.data.meshes.new("B_hair")
    me.from_pydata(V.astype(F32).tolist(), [], [tuple(int(v) for v in f) for f in F])
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    uv.data.foreach_set("uv", np.asarray(UV)[lv].astype(F32).ravel())
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("B_hair", me)
    bpy.context.scene.collection.objects.link(o)
    m = G.fresh_material("hair")
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(png, check_existing=True)
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = .42
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    me.materials.append(m)
    # the face's keys: each vertex the skin's own delta under it (the forehead's and the temples' sliders move the
    # hairline's roots)
    keys = body.data.shape_keys
    if keys:
        n = len(body.data.vertices)
        base_co = np.zeros(n * 3, F32); keys.key_blocks[0].data.foreach_get("co", base_co); base_co = base_co.reshape(n, 3)
        _, _, head_v = head_verts(body.data)
        from mathutils.kdtree import KDTree
        kd = KDTree(len(head_v))
        for i, vi in enumerate(head_v):
            kd.insert(base_co[vi], i)
        kd.balance()
        near = np.array([head_v[kd.find(tuple(p))[1]] for p in V])
        o.shape_key_add(name="Basis", from_mix=False)
        for kb in keys.key_blocks[1:]:
            k = np.zeros(n * 3, F32); kb.data.foreach_get("co", k); k = k.reshape(n, 3)
            D = (k - base_co)[near]
            nk = o.shape_key_add(name=kb.name, from_mix=False)
            nk.value = 0.0
            nk.data.foreach_set("co", (V + D).astype(F32).ravel())
    log(f"hair: {len(V)} vertices, {len(F)} cards' quads")
    return o, P


def scalp_mask(body, face_set, size, hd=None, P=None, log=_log):
    """the scalp's hair in the face map's hair mask (size x size, rows as Blender's pixels): every strand's root drawn
    as a short hair (the fade: short dark hair on skin), and under the top's long hair a soft floor so no bare scalp
    shows between the cards"""
    import groom as GR
    import head as HD
    hd = hd or HD.Head()
    me = body.data
    n = len(me.vertices)
    co = np.zeros(n * 3, F32); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
    nf = len(me.polygons)
    ls = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_total", lt)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    uv = np.zeros(len(me.loops) * 2, F32); me.uv_layers["UVMap"].data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
    # each head vertex's place on the map (its first loop's)
    vuv = np.full((n, 2), -1.0, np.float64)
    for f in np.flatnonzero(face_set):
        s_, t_ = ls[f], lt[f]
        for j in range(t_):
            vuv[lv[s_ + j]] = uv[s_ + j]
    _, _, head_v = head_verts(me)
    Q = GR.to_head(co[head_v], hd)
    dens = GR.scalp_density(Q)
    x, y, z = np.abs(Q[:, 0]), Q[:, 1], Q[:, 2]
    topw = np.clip((z - 4.0) / 3.0, 0, 1) * np.clip((5.8 - x) / 2.8, 0, 1) * np.clip((7.0 - y) / 4.0, 0, 1)
    topw = topw * topw * (3 - 2 * topw)
    mask = np.zeros((size, size), F32)
    # the floor under the cards: each vertex a soft disc of its density (the vertices lie 2-3 mm apart)
    floor = dens * topw * .80
    on = np.flatnonzero((floor > .02) & (vuv[head_v, 0] >= 0))
    r = max(2, int(size * .0035))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = np.clip(1 - np.hypot(xx, yy) / r, 0, 1).astype(F32)
    for i in on:
        vi = head_v[i]
        cx, cy = int(vuv[vi, 0] * size), int(vuv[vi, 1] * size)
        x0, y0 = cx - r, cy - r
        if x0 < 0 or y0 < 0 or x0 + 2 * r + 1 > size or y0 + 2 * r + 1 > size:
            continue
        sub = mask[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]
        np.maximum(sub, disc * floor[i], out=sub)
    # every strand's root as a short hair: its first three segments, each point carried onto the map through the
    # triangle it lies over (the nearest head vertex's place alone put a whole hair on one vertex: a dot)
    if P is None:
        P = grow(body, hd, n=60000)
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    tl = []
    for f in np.flatnonzero(face_set):
        s_, t_ = ls[f], lt[f]
        for j in range(1, t_ - 1):
            tl.append((s_, s_ + j, s_ + j + 1))
    tl = np.array(tl, np.int64)
    tv = lv[tl]
    bvh = BVHTree.FromPolygons([tuple(p) for p in co], [tuple(int(i) for i in t) for t in tv])
    W = GR.to_world(P[:, :4, :].reshape(-1, 3), hd).astype(np.float64)
    seg_uv = np.full((len(W), 2), -1.0)
    for i, p in enumerate(W):
        loc, _nrm, ti, dist = bvh.find_nearest(Vector(p))
        if ti is None or dist > .004:
            continue
        a_, b_, c_ = co[tv[ti]].astype(np.float64)
        q = np.asarray(loc, np.float64)
        v0, v1, v2 = b_ - a_, c_ - a_, q - a_
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
        d20, d21 = v2 @ v0, v2 @ v1
        den = max(d00 * d11 - d01 * d01, 1e-18)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        seg_uv[i] = (uv[tl[ti, 0]] * (1 - bv - bw) + uv[tl[ti, 1]] * bv + uv[tl[ti, 2]] * bw) * size
    seg_uv = seg_uv.reshape(len(P), 4, 2)
    px_mm = size / 4096 * 7.7                                               # texels a millimetre (0.13 mm a texel at 4K)
    ok = (seg_uv[..., 0] >= 0).all(1)
    seg_uv = seg_uv[ok]
    m_ = len(seg_uv)
    samples = np.linspace(0, 1, 8)
    for j in range(3):
        a, b = seg_uv[:, j], seg_uv[:, j + 1]
        d = np.linalg.norm(b - a, axis=1)
        keep = d < 10 * px_mm                                                 # (a jump across an island: no stroke)
        a, b = a[keep], b[keep]
        pts = (a[:, None, :] + (b - a)[:, None, :] * samples[None, :, None]).reshape(-1, 2)
        for dx, dy, wgt in ((0, 0, 1.0), (1, 0, .6), (-1, 0, .6), (0, 1, .6), (0, -1, .6)):
            cx = np.clip((pts[:, 0] + dx).astype(np.int64), 0, size - 1)
            cy = np.clip((pts[:, 1] + dy).astype(np.int64), 0, size - 1)
            np.maximum.at(mask, (cy, cx), np.full(len(cx), .92 * wgt * (1 - .18 * j), F32))
    log(f"scalp: {len(on)} vertices under the top's hair, {m_} strands' roots drawn as hairs")
    return mask, P
