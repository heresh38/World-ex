"""Fits the subdivided cage onto the anatomical target (shape.py):

  1. the cage (all quads, the base mesh's edge loops) is subdivided Catmull-Clark (levels 2: ~37k quads)
  2. every vertex is projected onto the part it belongs to (an arm vertex onto the arm, a finger onto its finger)
     so it cannot jump to a neighbouring surface, then onto the blended body
  3. a few rounds of tangential relaxation (Laplacian smoothing within the surface, re-projected) even out the quads
  4. the eye openings are placed on the lid margins (an almond fissure over the eyeball: canthi, upper lid higher than
     the lower, a slight upward tilt outward) and the mouth's slit on the lip line; they stay pinned while relaxing

The topology never changes here: only vertex positions.
"""
import math
import numpy as np
import bpy, bmesh
from mathutils import Vector
import sdf

F32 = np.float32
PART_OF = {"torso": "torso", "neck": "neck", "head": "head", "nose": "head", "ear_L": "head", "ear_R": "head",
           "arm_L": "arm", "arm_R": "arm", "hand_L": "hand", "hand_R": "hand", "finger": "hand", "thumb": "hand",
           "leg_L": "leg", "leg_R": "leg", "foot_L": "foot", "foot_R": "foot", "toe": "toe"}


def cage_object(cage, name):
    """the cage as a mesh object with one vertex group per shape part"""
    bm = cage.bm
    bm.verts.index_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    groups = {}
    for v in bm.verts:
        part = PART_OF.get(cage.part_of.get(v, "torso"), "torso")
        groups.setdefault(part, []).append(v.index)
    for part, idx in groups.items():
        vg = o.vertex_groups.new(name=part)
        vg.add(idx, 1.0, 'REPLACE')
    return o


def subdivide(o, levels):
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    m = o.modifiers.new("subd", 'SUBSURF')
    m.levels = m.render_levels = levels
    m.subdivision_type = 'CATMULL_CLARK'
    m.boundary_smooth = 'ALL'
    bpy.ops.object.modifier_apply(modifier=m.name)


def arrays(o):
    me = o.data
    n = len(me.vertices)
    V = np.zeros(n * 3, F32)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    E = np.zeros(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", E)
    E = E.reshape(-1, 2)
    names = [g.name for g in o.vertex_groups]
    W = np.zeros((n, len(names)), F32)
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    label = np.array([names[i] for i in W.argmax(1)])
    return V, E, label


def neighbours(n, E):
    """CSR adjacency"""
    deg = np.bincount(E.ravel(), minlength=n)
    order = np.argsort(np.concatenate([E[:, 0], E[:, 1]]), kind="stable")
    nb = np.concatenate([E[:, 1], E[:, 0]])[order]
    start = np.concatenate([[0], np.cumsum(deg)])
    return nb, start, deg


def laplacian(V, nb, start, deg):
    acc = np.zeros_like(V)
    owner = np.repeat(np.arange(len(V)), deg)
    np.add.at(acc, owner, V[nb])
    return acc / np.maximum(deg, 1)[:, None]


def boundary_loops(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    seen, loops = set(), []
    for e in bm.edges:
        if not e.is_boundary or e.index in seen:
            continue
        # walk the loop
        loop = [e.verts[0].index]
        cur, prev_e = e.verts[1], e
        seen.add(e.index)
        while cur.index != loop[0] and len(loop) < 5000:
            loop.append(cur.index)
            nxt = next((x for x in cur.link_edges if x.is_boundary and x is not prev_e and x.index not in seen), None)
            if nxt is None:
                break
            seen.add(nxt.index)
            prev_e = nxt
            cur = nxt.other_vert(cur)
        loops.append(loop)
    bm.free()
    return loops


def place_features(V, loops, body, T):
    """eye openings on the fissure over each eyeball, the mouth on the lip line; returns the pinned indices"""
    g = body.head_geometry()
    ec, er = g["eye_c"], g["eye_r"]
    pinned = []
    for loop in loops:
        P = V[loop]
        c = P.mean(0)
        if abs(c[0]) > .015 and c[2] > T["chin_z"] + .07:          # an eye
            sx = 1 if c[0] > 0 else -1
            cx, cz = ec.x * sx, ec.z
            ang = np.arctan2(P[:, 2] - c[2], (P[:, 0] - c[0]) * sx)   # 0 = outward (lateral), toward the temple
            fc = T.get("face", {})
            es, tilt = fc.get("eye_size", 1.0), fc.get("eye_tilt", 1.0)
            w = T["eye_w"] / 2 * es
            hu, hl = g["eye_hu"] * es, g["eye_hl"] * es
            for k, i in enumerate(loop):
                a = ang[k]
                ca, sa = math.cos(a), math.sin(a)
                # almond: the upper lid's peak a little inward of centre, the lower lid's low point a little outward
                u = w * ca
                lift = .0008 * tilt * (u / w)                                  # positive canthal tilt
                if sa >= 0:                                                    # rounded: a fuller arc than an almond
                    v = hu * math.copysign(abs(sa) ** .8, sa) * (1 - .08 * ca) + lift
                else:
                    v = hl * -abs(sa) ** .85 * (1 + .10 * ca) + lift
                x = cx + u * sx
                z = cz + v
                # the fissure is wider than the globe: laid on it compressed across (the canthi wrap round it)
                du, dv = (x - ec.x * sx) * (.76 * er / w), z - ec.z
                y = ec.y - math.sqrt(max((er + .0004) ** 2 - du * du - dv * dv, 1e-8))
                V[i] = (x, y, z)
            pinned += loop
        else:                                                          # the mouth
            st, mw = g["stomion"], g["mouth_w"]
            ang = np.arctan2(P[:, 2] - c[2], P[:, 0] - c[0])
            for k, i in enumerate(loop):
                a = ang[k]
                u = mw / 2 * math.cos(a)
                v = .0004 * math.sin(a)
                x, z = u, st.z + v + .0008 * (1 - (u / (mw / 2)) ** 2)
                # on the lip line: the front surface at (x, z) by bisection along -y
                lo_, hi_ = st.y - .02, st.y + .03
                for _ in range(30):
                    mid = (lo_ + hi_) / 2
                    if body(np.array([[x, mid, z]], F32))[0] < 0:
                        hi_ = mid
                    else:
                        lo_ = mid
                V[i] = (x, (lo_ + hi_) / 2 + .0015, z)
            pinned += loop
    return np.array(sorted(set(pinned)), np.int64)


def mirror_pairs(V):
    """for every vertex, its mirror partner (x -> -x) in the symmetric topology"""
    from mathutils import kdtree
    kd = kdtree.KDTree(len(V))
    for i, p in enumerate(V):
        kd.insert(Vector(p), i)
    kd.balance()
    pair = np.zeros(len(V), np.int64)
    for i, p in enumerate(V):
        co, j, d = kd.find(Vector((-p[0], p[1], p[2])))
        pair[i] = j
    return pair


def symmetrize(V, pair):
    """the right side (x < 0) copies the left; the midline sits on x = 0"""
    ok = pair[pair] == np.arange(len(V))                      # only true mirror pairs (a vertex claimed twice is left)
    left = (V[:, 0] > 1e-6) & ok
    mid = (pair == np.arange(len(V))) & ok
    R = V.copy()
    src = np.where(left)[0]
    R[pair[src]] = V[src] * np.array([-1, 1, 1], F32)
    R[mid, 0] = 0.0
    return R


def fit(o, body, T, relax=6, log=print, per_part=True, hold=None):
    """hold: vertex indices already placed (the head at the cage level): neither projected nor relaxed"""
    V, E, label = arrays(o)
    n = len(V)
    pair = mirror_pairs(V)
    held = np.zeros(n, bool)
    if hold is not None:
        held[np.asarray(list(hold), np.int64)] = True
    # 1. each part onto its own shape, then everything onto the blended body
    if per_part:
        for part in np.unique(label):
            idx = np.where((label == part) & ~held)[0]
            V[idx] = sdf.project(lambda P, p=part: body.part(p, P), V[idx], iters=8, max_step=.03)
    free = ~held
    toe = free & (label == "toe")                              # toes onto the toes alone
    V[toe] = sdf.project(lambda P: body.part("toe", P), V[toe], iters=6, max_step=.006)
    free &= ~toe
    V[free] = sdf.project(body, V[free], iters=4, max_step=.01)
    V = symmetrize(V, pair)
    log(f"projected {n} vertices; max |f| {np.abs(body(V)).max():.4f}")
    # 2. the features
    mask = held.copy()
    if hold is None:
        loops = boundary_loops(o)
        mask[place_features(V, loops, body, T)] = True
    # 3. tangential relaxation
    nb, start, deg = neighbours(n, E)
    for it in range(relax):
        L = laplacian(V, nb, start, deg)
        Nn = sdf.normals(body, V)
        d = L - V
        d -= Nn * (d * Nn).sum(1)[:, None]
        Vn = V + d * .5
        tv = label == "toe"
        Vn[~tv] = sdf.project(body, Vn[~tv], iters=2, max_step=.004)
        Vn[tv] = sdf.project(lambda P: body.part("toe", P), Vn[tv], iters=2, max_step=.004)
        V = np.where(mask[:, None], V, Vn)
        V = symmetrize(V, pair)
    log(f"relaxed; max |f| {np.abs(body(V[~mask])).max():.4f}")
    o.data.vertices.foreach_set("co", V.astype(F32).ravel())
    o.data.update()
    for p in o.data.polygons:
        p.use_smooth = True
    return V


def morph(o, V0, body, T, relax=4):
    """the fitted head re-fitted to a varied face (T["face"]): the base positions V0 move onto the new head, the eye
    and mouth openings are re-laid, the head relaxed; only the head's vertices move. Returns the new positions."""
    V, E, label = arrays(o)
    n = len(V)
    V = V0.copy()
    head = label == "head"
    pair = mirror_pairs(V)
    V[head] = sdf.project(body, V[head], iters=6, max_step=.006)
    V = symmetrize(V, pair)
    mask = ~head
    mask[place_features(V, boundary_loops(o), body, T)] = True
    nb, start, deg = neighbours(n, E)
    for it in range(relax):
        L = laplacian(V, nb, start, deg)
        Nn = sdf.normals(body, V)
        d = L - V
        d -= Nn * (d * Nn).sum(1)[:, None]
        Vn = sdf.project(body, V + d * .5, iters=2, max_step=.004)
        V = np.where(mask[:, None], V, Vn)
        V = symmetrize(V, pair)
    return V


def face_keys(o, body_cls, T, log=print):
    """one shape key per face customisation (headshape.FACE_KEYS) on the fitted mesh"""
    import copy
    import headshape
    me = o.data
    V0 = np.zeros(len(me.vertices) * 3, F32)
    me.vertices.foreach_get("co", V0)
    V0 = V0.reshape(-1, 3)
    if not me.shape_keys:
        o.shape_key_add(name="Basis", from_mix=False)
    Vb = morph(o, V0, body_cls(T), T)                    # the same re-fit of the unchanged face: its drift cancels
    for name, fac in headshape.FACE_KEYS.items():
        Tv = copy.deepcopy(T)
        Tv["face"] = dict(fac)
        D = morph(o, V0, body_cls(Tv), Tv) - Vb
        D[np.linalg.norm(D, axis=1) < 5e-5] = 0
        kb = o.shape_key_add(name="face_" + name, from_mix=False)
        kb.value = 0.0                                   # off by default (Blender 5 adds new keys at 1.0)
        kb.data.foreach_set("co", (V0 + D).astype(F32).ravel())
        log(f"shape key face_{name}: max move {np.abs(D).max() * 1000:.1f} mm, {int((np.abs(D).sum(1) > 0).sum())} verts")


def eyeballs(body, T, name):
    """the eyeballs as their own meshes (white, iris, pupil come from the material later)"""
    g = body.head_geometry()
    out = []
    for sx in (1, -1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=g["eye_r"],
                                             location=(g["eye_c"].x * sx, g["eye_c"].y, g["eye_c"].z))
        e = bpy.context.active_object
        e.name = f"{name}_eye_{'L' if sx > 0 else 'R'}"
        e.rotation_euler = (math.radians(90), 0, 0)                  # the pole looks forward (-Y)
        for p in e.data.polygons:
            p.use_smooth = True
        out.append(e)
    return out


def eye_sockets(o, eyes, log=print):
    """closes each eye opening behind the lids: the lid margin is extruded twice, first tucked onto the eyeball (the
    lids rest on it), then back round it past its widest point, so the corners show skin instead of the inside of
    the head. Face shape keys move the new rings with their margin vertex (same offset in every key)."""
    import bmesh
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    shapes = list(bm.verts.layers.shape.values())
    basis = bm.verts.layers.shape.get("Basis")
    added = 0
    margins = []
    for e in eyes:
        c = e.matrix_world.translation.copy()
        r = max(e.dimensions) / 2
        edges = [ed for ed in bm.edges if ed.is_boundary and all((v.co - c).length < r * 1.8 for v in ed.verts)]
        if not edges:
            continue
        loop = {v for ed in edges for v in ed.verts}
        margins.append([list(v.co) for v in loop])
        prev = loop
        for k, (shrink, back) in enumerate(((.97, .15), (.90, .55))):
            res = bmesh.ops.extrude_edge_only(bm, edges=edges)
            new_v = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
            for v in new_v:
                src = next(ed.other_vert(v) for ed in v.link_edges if ed.other_vert(v) in prev)
                d = src.co - c
                # onto the eyeball (k = 0) then behind it: direction toward the back, length a bit under r
                d.y = d.y + back * r * (1.0 if k else .3)
                p = c + d.normalized() * r * shrink
                delta = p - src.co
                v.co = p
                for lay in shapes:
                    v[lay] = src[lay] + delta
            edges = [g for g in res["geom"] if isinstance(g, bmesh.types.BMEdge) and g.is_boundary]
            prev = set(new_v)
            added += len(new_v)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    import json
    o["eye_margins"] = json.dumps(margins)                # the lid margins (no longer open edges): the lashes root here
    o["socket_verts"] = added                             # (the last vertices: rig.py weights the body without them)
    log(f"eye sockets: {added} vertices behind the lids")
