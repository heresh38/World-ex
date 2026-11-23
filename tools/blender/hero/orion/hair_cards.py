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


def grow(body, hd, n=120000, seed=7, style="swept"):
    """the groom's strands rooted on the game head (head cm, (m, k, 3)), in one of groom.STYLES"""
    import groom as GR
    rng = np.random.default_rng(seed)
    V, N = head_surface(body.data, 260000, rng)
    return np.asarray(GR.hair(V, N, hd, n=n, rng=rng, style=style), F32)


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


def make_hair(body, out, hd=None, P=None, log=_log, style="swept"):
    """one hairstyle's cards (C_hair__<style>: a piece of the wardrobe's hair slot, the character builder's choice), their
    atlas, the face's keys from the skin under each vertex"""
    import bpy
    import game as G
    import head as HD
    hd = hd or HD.Head()
    rng = np.random.default_rng(23)
    name = f"C_hair__{style}"
    for ob in [ob for ob in bpy.context.scene.objects if ob.name.startswith("B_hair") or ob.name.startswith(name)]:
        bpy.data.objects.remove(ob, do_unlink=True)
    png = os.path.join(out, "orion_male_hair_strands.png")
    # (the game draws the alpha MASKED, cut at a third: the strands need gaps between them, or every card is a tile)
    G.hair_atlas(png, size=2048, seed=5, base=(.026, .018, .013), tip=(.070, .050, .036), coarse=.85, per=(10, 16),
                 taper=.6, dense=0)
    if P is None:
        P = grow(body, hd, style=style)
    import groom as GR
    V, F, UV = build_cards(P, hd, rng, min_len=GR.STYLES[style].get("cards_min", 3.0))
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.astype(F32).tolist(), [], [tuple(int(v) for v in f) for f in F])
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    uv.data.foreach_set("uv", np.asarray(UV)[lv].astype(F32).ravel())
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    m = bpy.data.materials.get("hair") if style != "swept" else None    # (every style one material: the creator tints it)
    m = m or G.fresh_material("hair")
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
    log(f"hair ({style}): {len(V)} vertices, {len(F)} cards' quads")
    return o, P


def raster_max(mask, tri_px, tri_val):
    """every triangle (T, 3, 2 texel coordinates: x, row) filled from its corners' values (T, 3), kept where it is
    more than what is there"""
    size = mask.shape[0]
    for P_, V in zip(tri_px, tri_val):
        if V.max() < .01:
            continue
        x0, y0 = max(0, int(np.floor(P_[:, 0].min()))), max(0, int(np.floor(P_[:, 1].min())))
        x1, y1 = min(size - 1, int(np.ceil(P_[:, 0].max()))), min(size - 1, int(np.ceil(P_[:, 1].max())))
        if x1 < x0 or y1 < y0:
            continue
        (ax, ay), (bx, by), (cx, cy) = P_
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px, py = xs + .5, ys + .5
        l0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / d
        l1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / d
        l2 = 1 - l0 - l1
        inside = (l0 >= -.02) & (l1 >= -.02) & (l2 >= -.02)            # (a hair over each edge: no seam between them)
        val = np.where(inside, l0 * V[0] + l1 * V[1] + l2 * V[2], 0).astype(F32)
        sub = mask[y0:y1 + 1, x0:x1 + 1]
        np.maximum(sub, val, out=sub)


def box_blur(a, radius, passes=3):
    """a box blur by running sums, three passes close to a Gaussian (no scipy in Blender's Python)"""
    out = a.astype(np.float32)
    k = 2 * radius + 1
    for _ in range(passes):
        c = np.cumsum(np.pad(out, ((radius + 1, radius), (0, 0)), mode='edge'), axis=0, dtype=np.float64)
        out = ((c[k:] - c[:-k]) / k).astype(np.float32)
        c = np.cumsum(np.pad(out, ((0, 0), (radius + 1, radius)), mode='edge'), axis=1, dtype=np.float64)
        out = ((c[:, k:] - c[:, :-k]) / k).astype(np.float32)
    return out


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
    # the floor under the top's long hair (no bare scalp between the cards): laid over the head's own triangles,
    # each filled from its corners (discs at the vertices, 4-5 mm apart on the crown,
    # showed as a grid of dots however they were blurred), grown a few texels past each island's rim (the small mips
    # would draw a seam of bare scalp)
    floor = (dens * topw * .80).astype(F32)
    fv = np.zeros(n, F32)
    fv[head_v] = floor
    on = np.flatnonzero(floor > .02)
    tri = []
    for f in np.flatnonzero(face_set):
        s_, t_ = ls[f], lt[f]
        for j in range(1, t_ - 1):
            tri.append((s_, s_ + j, s_ + j + 1))
    tri = np.array(tri, np.int64)
    raster_max(mask, uv[tri] * size, fv[lv[tri]])
    for _ in range(4):
        grown = mask.copy()
        np.maximum(grown[1:], mask[:-1], out=grown[1:])
        np.maximum(grown[:-1], mask[1:], out=grown[:-1])
        np.maximum(grown[:, 1:], mask[:, :-1], out=grown[:, 1:])
        np.maximum(grown[:, :-1], mask[:, 1:], out=grown[:, :-1])
        mask = np.where(mask > 0, mask, grown)
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
    samples = np.linspace(0, 1, 10)
    rng = np.random.default_rng(5)
    tone = rng.uniform(.80, 1.0, m_).astype(F32)                               # every hair a little its own
    strokes = np.zeros((size, size), F32)
    for j in range(3):
        a, b = seg_uv[:, j], seg_uv[:, j + 1]
        d = np.linalg.norm(b - a, axis=1)
        keep = d < 10 * px_mm                                                 # (a jump across an island: no stroke)
        a, b, tj = a[keep], b[keep], tone[keep]
        pts = (a[:, None, :] + (b - a)[:, None, :] * samples[None, :, None]).reshape(-1, 2)
        val = np.repeat(tj * .92 * (1 - .18 * j), len(samples))
        # drawn smooth: each point shared between the four texels round it by how near it lies (snapped to whole
        # texels, every hair was a stair of pixels and the fade read as a grid), a texel's width either side
        x0, y0 = np.floor(pts[:, 0]).astype(np.int64), np.floor(pts[:, 1]).astype(np.int64)
        fx, fy = (pts[:, 0] - x0).astype(F32), (pts[:, 1] - y0).astype(F32)
        corners = ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy))
        # (the nearest texel keeps the hair's whole tone, the others by how near they lie: shared out evenly the hairs
        # drew at half their tone and the fade read as bare skin)
        wmax = np.maximum(np.maximum(corners[0][2], corners[1][2]), np.maximum(corners[2][2], corners[3][2]))
        for ox, oy, wgt in corners:
            for dx, dy, side in ((0, 0, 1.0), (1, 0, .45), (-1, 0, .45), (0, 1, .45), (0, -1, .45)):
                cx = np.clip(x0 + ox + dx, 0, size - 1)
                cy = np.clip(y0 + oy + dy, 0, size - 1)
                np.maximum.at(strokes, (cy, cx), (val * (wgt / np.maximum(wmax, 1e-6)) * side).astype(F32))
    # the fade's own shadow under its hairs: how densely they grow round each texel (from the strokes themselves: they
    # grow only where the scalp does, never on an ear), up to a third of a texel's colour
    shade = np.clip(box_blur(strokes, max(2, int(px_mm * .8)), passes=2) * 1.8, 0, .36)
    np.maximum(mask, shade, out=mask)
    np.maximum(mask, strokes, out=mask)
    log(f"scalp: {len(on)} vertices under the top's hair, {m_} strands' roots drawn as hairs")
    return mask, P
