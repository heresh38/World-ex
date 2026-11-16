"""An asset's OWN maps: a second, unique UV set and what is baked from the model itself (the owner's art-production
specification, docs/art/ASSET_PIPELINE.md sections 4, 5 and 8; the audit, docs/art/ASSET_AUDIT.md).

A tiling material set says what a surface is MADE of; it cannot know where on the object it is. This gives every
texel of the object its place:

  unwrap(objs)       a second UV layer `UV1` on every object: unique (nothing overlaps), one texel density
                     throughout (islands scaled to their true areas), packed together across the objects, so one
                     set of maps serves a gun and its moving parts. UV 0 (the tiling materials) is left as it is.
  bake(objs, size)   from a joined copy, through Cycles: ambient occlusion (short reach: an object's own hollows),
                     the world POSITION and NORMAL of every texel, which material it is, and which texels are
                     covered at all. Returned as arrays (rows from the top of the image), with the bounds.
  curvature(maps)    from the position and the normal: how much the surface turns at each texel, signed (convex
                     edges positive: what gets rubbed; concave negative: where dirt lies).

What is painted from these (wear by place, dirt, markings) is the asset's own job: gunpaint.py for guns.
"""
import math
import os
import bpy
import numpy as np
from mathutils import Vector

F32 = np.float32
UV = "UV1"


def clean(objs, dist=2e-6, least=1e-11):
    """No triangle without area reaches the game (the gate, asset_check.py, allows none; an unwrap cannot lay one
    out). Edges with no length are dissolved (a loft's pole, a chamfer clamped to nothing). Most of the rest are born
    when an exporter cuts a face whose corners lie in a line: so the faces are cut HERE, each the better way, and a
    triangle still under `least` square metres is deleted (it covered nothing). Returns how many went."""
    import bmesh
    n = 0
    for o in objs:
        if o.type != 'MESH' or not len(o.data.polygons):
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        before = len(bm.faces)
        bmesh.ops.dissolve_degenerate(bm, dist=dist, edges=bm.edges)
        n += before - len(bm.faces)
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
        dead = [f for f in bm.faces if f.calc_area() < least]
        n += len(dead)
        if dead:
            bmesh.ops.delete(bm, geom=dead, context='FACES')
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
    return n


_WAYS = [(0.0, 0.0, 1.0)] + [(math.sin(t) * math.cos(a), math.sin(t) * math.sin(a), math.cos(t))
                              for t in (math.radians(35), math.radians(65)) for a in (i * math.tau / 8 for i in range(8))]


def hidden_faces(objs, reach=.010):
    """for each object, a flag per polygon: NOTHING can see this face (from its middle and from near each corner,
    every way out is blocked within `reach`: it lies under another part). Conservative on purpose: a face at the
    bottom of a slot or behind a vent is seen and stays."""
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for o in objs:
        base, W = len(verts), o.matrix_world
        verts += [W @ v.co for v in o.data.vertices]
        polys += [[base + i for i in p.vertices] for p in o.data.polygons]
    tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    out = []
    for o in objs:
        W = o.matrix_world
        R3 = W.to_3x3()
        me = o.data
        h = np.zeros(len(me.polygons), bool)
        for p in me.polygons:
            n = (R3 @ p.normal).normalized()
            t = n.orthogonal().normalized()
            b = n.cross(t)
            c = W @ p.center
            pts = [c] + [c.lerp(W @ me.vertices[i].co, .8) for i in p.vertices]
            blocked = True
            for q in pts:
                start = q + n * .0003
                for d in _WAYS:
                    if tree.ray_cast(start, t * d[0] + b * d[1] + n * d[2], reach)[0] is None:
                        blocked = False
                        break
                if not blocked:
                    break
            h[p.index] = blocked
        out.append(h)
    return out


def unwrap(objs, margin=.0016, angle=66.0, shrink=None, log=print, method='MINIMUM_STRETCH'):
    """a unique UV set: islands by angle, then each island laid out again with the least stretch (a projection draws
    a curved face out: the gate allows 10 % of the surface stretched over a quarter), every island at its true size.
    `shrink` (say .25): islands nobody can see (under other parts) are cut off and shrunk to that, so the atlas is
    spent on what is seen. It pays where whole regions are covered (skin under clothes); on a gun made of shells
    laid on shells it did not (5 % of the faces, more seams, a worse pack): off unless asked."""
    from bpy_extras import mesh_utils
    objs = [o for o in objs if o.type == 'MESH' and len(o.data.polygons)]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        me = o.data
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        if UV not in me.uv_layers:
            me.uv_layers.new(name=UV)
        me.uv_layers.active = me.uv_layers[UV]
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)                          # (a second try at a smaller angle starts clean)
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    hidden = hidden_faces(objs) if shrink else [np.zeros(len(o.data.polygons), bool) for o in objs]
    for o, h in zip(objs, hidden):                              # a seam wherever a face nobody sees meets one that is seen
        me = o.data
        ek = {}
        for p in me.polygons:
            for k in p.edge_keys:
                ek.setdefault(k, []).append(p.index)
        for e in me.edges:
            fs = ek.get(e.key, ())
            if len(fs) == 2 and h[fs[0]] != h[fs[1]]:
                e.use_seam = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    try:
        bpy.ops.uv.unwrap(method=method, margin=0.0)
    except TypeError:
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.0)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')
    small = total = 0
    for o, h in zip(objs, hidden):
        if not shrink:
            break
        me = o.data
        uv = np.empty(len(me.loops) * 2, F32)
        me.uv_layers[UV].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        for island in mesh_utils.mesh_linked_uv_islands(me):
            total += 1
            if not all(h[i] for i in island):
                continue
            loops = np.array([l for i in island for l in me.polygons[i].loop_indices], np.int64)
            c = uv[loops].mean(0)
            uv[loops] = c + (uv[loops] - c) * shrink
            small += 1
        me.uv_layers[UV].data.foreach_set("uv", uv.ravel())
    if shrink:
        log(f"[bakekit] UV 1: {total} islands, {small} of them under other parts (shrunk to {shrink}); "
            f"{100 * sum(int(h.sum()) for h in hidden) / max(sum(len(h) for h in hidden), 1):.0f} % of the faces are never seen")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=margin)
    except TypeError:
        bpy.ops.uv.pack_islands(margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in objs:                                              # (UV 0 stays the one a tiling material and an export take first)
        o.data.uv_layers.active = o.data.uv_layers[0]
        o.data.uv_layers[0].active_render = True
    return objs


def stretched(objs, over=1.25):
    """the share of the surface that UV 1 draws out by more than `over` in one direction against the other (the
    gate, asset_check.py, allows a tenth over 1.25)"""
    tot = bad = 0.0
    for o in objs:
        me = o.data
        if o.type != 'MESH' or UV not in me.uv_layers:
            continue
        me.calc_loop_triangles()
        n = len(me.loop_triangles)
        vi = np.empty(n * 3, np.int32)
        li = np.empty(n * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", vi)
        me.loop_triangles.foreach_get("loops", li)
        co = np.empty(len(me.vertices) * 3, F32)
        me.vertices.foreach_get("co", co)
        P = co.reshape(-1, 3)[vi].reshape(n, 3, 3)
        uv = np.empty(len(me.loops) * 2, F32)
        me.uv_layers[UV].data.foreach_get("uv", uv)
        U = uv.reshape(-1, 2)[li].reshape(n, 3, 2)
        e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
        A = .5 * np.linalg.norm(np.cross(e1, e2), axis=1)
        x1 = np.linalg.norm(e1, axis=1)
        ex = e1 / np.maximum(x1, 1e-12)[:, None]
        x2 = (e2 * ex).sum(1)
        y2 = np.linalg.norm(e2 - x2[:, None] * ex, axis=1)
        u1, u2 = U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            j11, j21 = u1[:, 0] / x1, u1[:, 1] / x1
            j12, j22 = (u2[:, 0] - j11 * x2) / y2, (u2[:, 1] - j21 * x2) / y2
            s = j11 * j11 + j12 * j12 + j21 * j21 + j22 * j22
            det = np.abs(j11 * j22 - j12 * j21)
            root = np.sqrt(np.maximum(s * s / 4 - det * det, 0))
            st = np.sqrt((s / 2 + root) / np.maximum(s / 2 - root, 1e-30))
        st = np.where(np.isfinite(st) & (A > 1e-12), st, 1.0)
        tot += float(A.sum())
        bad += float(A[st > over].sum())
    return bad / max(tot, 1e-12)


def unwrap_fit(objs, limit=.08, log=print, tries=None, **kw):
    """unwrap, and while too much of the surface comes out stretched or collapsed, again another way. The
    least-stretch layout is the best where it works, but it needs an island with ONE rim: a flat ring (a tube's end,
    a washer, a band's face) has two and comes out collapsed, so turned guns (a launcher's tube, a barrel cluster)
    go to the angle-based layout, which takes any island; then smaller islands. Stops under `limit`. `tries`: a gun's
    own ((angle, method), ...) (weapons.UNWRAP_TRIES)."""
    tries = tries or ((66.0, 'MINIMUM_STRETCH'), (66.0, 'ANGLE_BASED'), (50.0, 'ANGLE_BASED'), (38.0, 'ANGLE_BASED'))
    best = None
    for a, m in tries:
        unwrap(objs, angle=a, method=m, log=log, **kw)
        share = stretched(objs)
        log(f"[bakekit] UV 1 at {a:.0f} degrees, {m.lower()}: {100 * share:.1f} % of the surface stretched over a quarter")
        if best is None or share < best[0]:
            best = (share, a, m)
        if share <= limit:
            return objs
    if (a, m) != best[1:]:                                      # none got under: keep the best of them
        unwrap(objs, angle=best[1], method=best[2], log=log, **kw)
    return objs


def _gpu(sc):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = 'GPU'
                return kind
    except Exception as e:
        print("[bakekit] no graphics card for Cycles:", e)
    sc.cycles.device = 'CPU'
    return "CPU"


def bake(objs, size=4096, samples=48, reach=.06, log=print):
    """returns dict(ao, pos, nrm, mat, cover, lo, hi, materials): arrays (size, size[, 3]), rows from the top"""
    sc = bpy.context.scene
    objs = [o for o in objs if o.type == 'MESH' and len(o.data.polygons)]
    # a joined copy: one bake, world positions, the parts where they rest
    bpy.ops.object.select_all(action='DESELECT')
    copies = []
    for o in objs:
        c = o.copy()
        c.data = o.data.copy()
        sc.collection.objects.link(c)
        c.select_set(True)
        copies.append(c)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    j.name = "BakeCopy"
    me = j.data
    me.uv_layers.active = me.uv_layers[UV]
    names = [s.material.name if s.material else "" for s in j.material_slots]
    co = np.empty(len(me.vertices) * 3, F32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(0) - .002, co.max(0) + .002
    for o in objs:
        o.hide_render = True
    img = bpy.data.images.new("BakeTarget", size, size, alpha=True, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'

    def material(kind, colour=None):
        m = bpy.data.materials.new("Bake_" + kind)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(em.outputs[0], out.inputs[0])
        if kind in ("pos", "nrm"):
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.vector_type = 'POINT'
            if kind == "pos":
                mp.inputs["Location"].default_value = tuple(float(-lo[i] / (hi[i] - lo[i])) for i in range(3))
                mp.inputs["Scale"].default_value = tuple(float(1 / (hi[i] - lo[i])) for i in range(3))
                nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
            else:
                mp.inputs["Location"].default_value = (.5, .5, .5)
                mp.inputs["Scale"].default_value = (.5, .5, .5)
                nt.links.new(geo.outputs["Normal"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], em.inputs["Color"])
        else:
            em.inputs["Color"].default_value = (*colour, 1)
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        nt.nodes.active = t
        return m

    def read():
        a = np.empty(size * size * 4, F32)
        img.pixels.foreach_get(a)
        return a.reshape(size, size, 4)[::-1].copy()

    sc.render.engine = 'CYCLES'
    dev = _gpu(sc)
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.world = sc.world or bpy.data.worlds.new("BakeWorld")
    sc.world.light_settings.distance = reach
    sc.render.bake.use_clear = True
    bpy.ops.object.select_all(action='DESELECT')
    j.select_set(True)
    bpy.context.view_layer.objects.active = j
    out = dict(lo=lo, hi=hi, materials=names)
    # which material, and what is covered: no margin, so an island's edge is its edge
    n = max(1, len(names))
    for i, s in enumerate(j.material_slots):
        s.material = material("id", ((i + 1) / n, 1.0, 0.0))
    sc.render.bake.margin = 0
    bpy.ops.object.bake(type='EMIT')
    a = read()
    out["cover"] = a[..., 1] > .5
    out["mat"] = np.clip(np.round(a[..., 0] * n) - 1, 0, n - 1).astype(np.int16)
    sc.render.bake.margin = 8
    for kind in ("pos", "nrm"):
        m = material(kind)
        for s in j.material_slots:
            s.material = m
        bpy.ops.object.bake(type='EMIT')
        a = read()[..., :3]
        out[kind] = (a * (hi - lo) + lo).astype(F32) if kind == "pos" else (a * 2 - 1).astype(F32)
    bpy.ops.object.bake(type='AO')
    out["ao"] = read()[..., 0].astype(F32)
    nl = np.linalg.norm(out["nrm"], axis=2, keepdims=True)
    out["nrm"] = out["nrm"] / np.maximum(nl, 1e-6)
    out["texel"] = math.sqrt(sum(p.area for p in me.polygons) / max(out['cover'].sum(), 1))       # metres a texel
    log(f"[bakekit] baked {size} px on {dev}: {int(out['cover'].mean() * 100)} % of the map used, {len(names)} materials, "
        f"{len(me.polygons)} faces, {1000 * math.sqrt(sum(p.area for p in me.polygons) / max(out['cover'].sum(), 1)):.3f} mm a texel")
    bpy.data.objects.remove(j)
    bpy.data.images.remove(img)
    for o in objs:
        o.hide_render = False
    return out


def bake_highpoly_normals(objs, size=4096, bevel=.0007, segments=3, angle=35.0, log=print):
    """The high-poly model and its normals baked onto the game model (the art-production specification: a high-poly
    and a game-ready model with the details BAKED). The high-poly is the game model with every hard edge rounded as a
    machined or moulded part's is (a bevel of `bevel` metres in `segments` steps on edges sharper than `angle`), its
    normals weighted by face area so the flats stay flat and only the rounding turns. Its normals are baked in OBJECT
    space (the gun's own frame: X left, Y back, Z up) onto the unique UV set: the game turns the surface's normal onto
    them (M_SOStandard UniqueNormalTex, on UV 1, no tangent frame needed). Returns (size, size, 3) normals, rows from
    the top, and the cover mask; (None, None) if it could not be baked."""
    sc = bpy.context.scene
    objs = [o for o in objs if o.type == 'MESH' and len(o.data.polygons)]
    bpy.ops.object.select_all(action='DESELECT')
    copies = []
    for o in objs:
        c = o.copy()
        c.data = o.data.copy()
        sc.collection.objects.link(c)
        c.select_set(True)
        copies.append(c)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    low = bpy.context.view_layer.objects.active
    low.name = "BakeLow"
    low.data.uv_layers.active = low.data.uv_layers[UV]
    # the high-poly: rounded edges, weighted normals
    high = low.copy()
    high.data = low.data.copy()
    high.name = "BakeHigh"
    sc.collection.objects.link(high)
    for p in high.data.polygons:
        p.use_smooth = True
    b = high.modifiers.new("Round", 'BEVEL')
    b.width = bevel
    b.segments = segments
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(angle)
    b.use_clamp_overlap = True
    b.harden_normals = False
    w = high.modifiers.new("Weighted", 'WEIGHTED_NORMAL')
    w.mode = 'FACE_AREA'
    w.weight = 50
    w.keep_sharp = True
    bpy.ops.object.select_all(action='DESELECT')
    high.select_set(True)
    bpy.context.view_layer.objects.active = high
    try:
        for m in list(high.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
    except Exception as e:
        log(f"[bakekit] the high-poly could not be made: {e}")
        bpy.data.objects.remove(high)
        bpy.data.objects.remove(low)
        return None, None
    log(f"[bakekit] high-poly: {len(high.data.polygons)} faces (the game model {len(low.data.polygons)})")
    for o in objs:
        o.hide_render = True
    img = bpy.data.images.new("BakeNormals", size, size, alpha=True, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    m = bpy.data.materials.new("Bake_hpn")
    m.use_nodes = True
    t = m.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = img
    m.node_tree.nodes.active = t
    for s in low.material_slots:
        s.material = m
    if not low.material_slots:
        low.data.materials.append(m)
    sc.render.engine = 'CYCLES'
    dev = _gpu(sc)
    sc.cycles.samples = 1
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = .003
    bk.max_ray_distance = .006
    bk.normal_space = 'OBJECT'
    bk.normal_r, bk.normal_g, bk.normal_b = 'POS_X', 'POS_Y', 'POS_Z'
    bk.margin = 8
    bk.use_clear = True
    bpy.ops.object.select_all(action='DESELECT')
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type='NORMAL')
    a = np.empty(size * size * 4, F32)
    img.pixels.foreach_get(a)
    a = a.reshape(size, size, 4)[::-1].copy()
    cover = a[..., 3] > .5
    n = a[..., :3] * 2 - 1
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    bk.use_selected_to_active = False
    log(f"[bakekit] high-poly normals baked {size} px on {dev}: {int(cover.mean() * 100)} % of the map")
    bpy.data.objects.remove(high)
    bpy.data.objects.remove(low)
    bpy.data.images.remove(img)
    bpy.data.materials.remove(m)
    for o in objs:
        o.hide_render = False
    return n.astype(F32), cover


def _blur(a, r):
    for axis in (0, 1):
        c = np.cumsum(np.concatenate([a.take(range(a.shape[axis] - r - 1, a.shape[axis]), axis=axis), a, a.take(range(0, r), axis=axis)], axis=axis),
                      axis=axis, dtype=np.float64)
        n = a.shape[axis]
        a = ((c.take(range(2 * r + 1, 2 * r + 1 + n), axis=axis) - c.take(range(0, n), axis=axis)) / (2 * r + 1)).astype(F32)
    return a


def curvature(maps, step=2):
    """how the surface turns at each texel (1 / metres, convex positive), from neighbours `step` texels apart on the
    same island (a neighbour further off in space than the map's own grain is on another island: ignored)"""
    pos, nrm, cover = maps["pos"], maps["nrm"], maps["cover"]
    acc = np.zeros(cover.shape, F32)
    cnt = np.zeros(cover.shape, F32)
    texel = math.sqrt(1.0)                                      # (set below from the positions themselves)
    d0 = np.linalg.norm(np.roll(pos, -1, 1) - pos, axis=2)
    texel = float(np.median(d0[cover & np.roll(cover, -1, 1)]))
    for axis in (0, 1):
        pa, pb = np.roll(pos, -step, axis), np.roll(pos, step, axis)
        na, nb = np.roll(nrm, -step, axis), np.roll(nrm, step, axis)
        dp = pa - pb
        L2 = (dp * dp).sum(2)
        ok = cover & np.roll(cover, -step, axis) & np.roll(cover, step, axis) & (L2 < (texel * step * 6) ** 2) & (L2 > 1e-14)
        k = ((na - nb) * dp).sum(2) / np.maximum(L2, 1e-14)
        acc += np.where(ok, k, 0)
        cnt += ok
    return np.where(cnt > 0, acc / np.maximum(cnt, 1), 0).astype(F32), texel


def spread(mask, cover, radius):
    """a mask widened and softened by `radius` texels, staying on covered texels"""
    return np.clip(_blur(mask.astype(F32), max(1, int(radius))) * 2.2, 0, 1) * cover


def save_debug(maps, path):
    """the baked maps side by side as a picture (for looking at, not for the game)"""
    size = maps["ao"].shape[0]
    k = max(1, size // 1024)
    pos = (maps["pos"] - maps["lo"]) / (maps["hi"] - maps["lo"])
    tiles = [np.repeat(maps["ao"][..., None], 3, 2), pos, maps["nrm"] * .5 + .5,
             np.repeat((maps["mat"].astype(F32) / max(1, len(maps["materials"]) - 1))[..., None], 3, 2) * maps["cover"][..., None]]
    sheet = np.concatenate([t[::k, ::k] for t in tiles], axis=1)
    H, W = sheet.shape[:2]
    im = bpy.data.images.new("BakeDebug", W, H, alpha=False)
    px = np.ones((H, W, 4), F32)
    px[..., :3] = np.clip(sheet, 0, 1)[::-1]
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
