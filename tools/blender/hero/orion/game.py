"""The new male (Project Orion) made ready for the game, from a saved lab build
(lab.py -- out.png --levels=2 --detail --gamehead --facekeys --save=build.blend):

    blender -b build.blend -P tools/blender/hero/orion/game.py -- <out_dir> [--stages=a,b,...] [--save=x.blend]

Stages (in order; --stages picks some, the default runs them all):
  normals   the head's normals from the sculpt's own field (its skin is laid on the sculpt, but a vertex's normal
            from the faces round it shows the topology: fans under the chin where the neck's 24 columns become the
            head's 40); faded into the mesh's own down the neck
  uv        seams on hidden lines (every region's border; the back's midline up the torso, the neck and the back of
            the head; under the arms; inside the legs; round the hands' and feet's edges; round each ear's rim),
            unwrapped, packed into two maps: the FACE (the head and its ears) and the BODY (the rest; the hands at a
            higher density: the first-person view is all hands)
Everything here is the new body's own: nothing of the old player's rig, skin maps or clothing is used.
"""
import heapq
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))         # tools/blender
sys.path.insert(0, HERE)
import body as B                                                    # noqa: E402

T0 = time.time()
HAND_DENSITY = 1.7              # the hands' texels per metre over the rest of the body's


def log(*a):
    print("[game]", f"{time.time() - T0:6.1f}s", *a, flush=True)


def body_object():
    """the whole body (None once the export has split it into its regions' B_* objects: a saved build after the
    export can still bake its clips and export again)"""
    return next((o for o in bpy.context.scene.objects if o.type == 'MESH' and "region" in o.data.attributes
                 and not o.name.startswith(("B_", "C_"))), None)


def read(me, name, domain_len, dtype=np.float32, width=1):
    a = me.attributes.get(name)
    if a is None:
        return None
    key = "value" if width == 1 else "vector"
    out = np.zeros(domain_len * width, dtype)
    a.data.foreach_get(key, out)
    return out if width == 1 else out.reshape(-1, width)


def coords(me):
    co = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def quads(me):
    ls = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get("loop_total", lt)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    if (lt == 4).all():
        return lv.reshape(-1, 4)
    return [lv[s:s + t] for s, t in zip(ls, lt)]


# ---------------------------------------------------------------------------------------------------------------
# normals

def field_normals(o):
    """the head's vertex normals from the sculpt's field where they agree with the mesh's (within 60 degrees,
    faded out by 80: the lids' and the lips' inner walls keep their own), faded by the head's share down the neck;
    set as the mesh's custom normals"""
    import head as HD
    import sdf
    me = o.data
    co = coords(me)
    n = len(co)
    nr = np.zeros(n * 3, np.float32); me.vertices.foreach_get("normal", nr); nr = nr.reshape(-1, 3)
    hw = read(me, "headw", n)
    sel = np.flatnonzero(hw > .001)
    hd = HD.Head()
    g = sdf.grad(hd, co[sel].astype(np.float64))
    g /= np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]
    ang = np.degrees(np.arccos(np.clip((g * nr[sel]).sum(1), -1, 1)))
    t = np.clip((80 - ang) / 20, 0, 1) * hw[sel]
    N = nr.copy()
    m = nr[sel] * (1 - t[:, None]) + g * t[:, None]
    N[sel] = m / np.maximum(np.linalg.norm(m, axis=1), 1e-9)[:, None]
    me.normals_split_custom_set_from_vertices([tuple(v) for v in N])
    moved = np.degrees(np.arccos(np.clip((N[sel] * nr[sel]).sum(1), -1, 1)))
    log(f"normals: {len(sel)} head vertices from the sculpt's field, turned {np.median(moved):.1f} deg (median), "
        f"{np.percentile(moved, 99):.1f} (99 %); {int((t < .5).sum())} kept their own")


# ---------------------------------------------------------------------------------------------------------------
# seams

def vertex_normals(me):
    nr = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("normal", nr)
    return nr.reshape(-1, 3)


def face_normals(me):
    fn = np.zeros(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("normal", fn)
    return fn.reshape(-1, 3)


def face_adjacency(F):
    """pairs of faces sharing an edge, and that edge's vertices"""
    F = np.asarray(F)
    k = F.shape[1]
    a = F.ravel(); b = np.roll(F, -1, axis=1).ravel()
    key = np.minimum(a, b) * (1 << 32) + np.maximum(a, b)
    face = np.repeat(np.arange(len(F)), k)
    order = np.argsort(key, kind="stable")
    ks, fs = key[order], face[order]
    same = np.flatnonzero(ks[1:] == ks[:-1])
    return fs[same], fs[same + 1], np.c_[ks[same] >> 32, ks[same] & 0xFFFFFFFF]


def smooth_labels(lab, f0, f1, nf, rounds=4, keep=None):
    """each face takes its neighbours' majority label (two-label regions), a few rounds"""
    lab = lab.copy()
    for _ in range(rounds):
        votes = np.zeros(nf); cnt = np.zeros(nf)
        for a_, b_ in ((f0, f1), (f1, f0)):
            np.add.at(votes, a_, lab[b_] == 1)
            np.add.at(cnt, a_, 1)
        m = cnt > 0
        new = lab.copy()
        new[m & (votes > cnt * .6)] = 1
        new[m & (votes < cnt * .4)] = 2
        if keep is not None:
            new[~keep] = lab[~keep]
        lab = new
    return lab


def drop_specks(lab, f0, f1, members, min_faces=40):
    """a small piece of one label inside the other takes its surroundings' label"""
    sel = np.zeros(len(lab), bool); sel[members] = True
    for _ in range(3):
        same = sel[f0] & sel[f1] & (lab[f0] == lab[f1])
        parent = np.arange(len(lab))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for a_, b_ in zip(f0[same], f1[same]):
            ra, rb = find(a_), find(b_)
            if ra != rb:
                parent[ra] = rb
        roots = np.array([find(i) for i in members])
        labels, counts = np.unique(roots, return_counts=True)
        small = set(labels[counts < min_faces].tolist())
        if not small:
            return lab
        for i, r in zip(members, roots):
            if r in small:
                lab[i] = 3 - lab[i]
    return lab


def dijkstra(adj, src, dst, cost):
    """the cheapest path src -> dst over adj {v: [(w, edge length)]} with cost(v, w, length)"""
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    while pq:
        d, v = heapq.heappop(pq)
        if v == dst:
            break
        if d > dist.get(v, 1e18):
            continue
        for w, L in adj.get(v, ()):
            nd = d + cost(v, w, L)
            if nd < dist.get(w, 1e18):
                dist[w] = nd; prev[w] = v
                heapq.heappush(pq, (nd, w))
    if dst not in prev and dst != src:
        return []
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return path[::-1]


def mark_seams(o):
    """every seam the unwrap needs (see the module's docstring); returns the seam edges as vertex pairs"""
    me = o.data
    co = coords(me)
    F = np.asarray(quads(me))
    nf = len(F)
    region = read(me, "region", nf, np.int32)
    ear = read(me, "ear", nf, np.int32)
    if ear is None:
        ear = np.zeros(nf, np.int32)
    fn = face_normals(me)
    vn = vertex_normals(me)
    f0, f1, ev = face_adjacency(F)
    seams = set()

    def add(a, b):
        seams.add((min(int(a), int(b)), max(int(a), int(b))))
    # 1. the regions' borders and the ears' (the head's map holds the ears too, as their own islands)
    border = (region[f0] != region[f1]) | (ear[f0] != ear[f1])
    for a, b in ev[border]:
        add(a, b)
    nb = len(seams)
    # 2. two-sided pieces split along their edges: each hand (back / palm), each foot (top / sole), each ear
    # (outside / the side toward the head)
    side = np.zeros(nf, np.int32)
    cen = co[F].mean(1)
    pieces = []
    for sx in (1, -1):
        hand = np.flatnonzero((region == B.REGIONS.index("hand")) & (cen[:, 0] * sx > 0))
        P = co[np.unique(F[hand])]
        c = P.mean(0)
        _, _, vt = np.linalg.svd(P - c, full_matrices=False)
        n_palm = vt[2] if vt[2][2] > 0 else -vt[2]                    # the back of the hand faces up (T-pose)
        pieces.append((hand, fn[hand] @ n_palm))
        foot = np.flatnonzero((region == B.REGIONS.index("foot")) & (cen[:, 0] * sx > 0))
        pieces.append((foot, -fn[foot, 2] - .35))                     # the sole: faces looking down
        e_f = np.flatnonzero(ear == (1 if sx > 0 else 2))
        if len(e_f):
            Pe = co[np.unique(F[e_f])]
            ce = Pe.mean(0)
            _, _, vt = np.linalg.svd(Pe - ce, full_matrices=False)
            n_ear = vt[2] if vt[2][0] * sx > 0 else -vt[2]
            pieces.append((e_f, fn[e_f] @ n_ear))
    for members, score in pieces:
        lab = np.zeros(nf, np.int32)
        lab[members] = np.where(score > 0, 1, 2)
        keep = np.zeros(nf, bool); keep[members] = True
        lab = smooth_labels(lab, f0, f1, nf, keep=keep)
        lab = drop_specks(lab, f0, f1, members)
        side[members] = lab[members]
    split = (side[f0] != side[f1]) & (side[f0] > 0) & (side[f1] > 0) & (region[f0] == region[f1]) & (ear[f0] == ear[f1])
    for a, b in ev[split]:
        add(a, b)
    ns = len(seams) - nb
    # 3. one cut down each tube, from one border to the other, along its most hidden line
    cuts = 0
    edges_all = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 3]], F[:, [3, 0]]]
    for rname in ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "thigh", "shin"):
        for sx in ((0,) if rname in ("head", "neck", "chest", "midriff", "pelvis") else (1, -1)):
            ri = B.REGIONS.index(rname)
            fsel = (region == ri) & (ear == 0)
            if sx:
                fsel &= cen[:, 0] * sx > 0
            fid = np.flatnonzero(fsel)
            if not len(fid):
                continue
            E = np.r_[F[fid][:, [0, 1]], F[fid][:, [1, 2]], F[fid][:, [2, 3]], F[fid][:, [3, 0]]]
            E = np.unique(np.sort(E, axis=1), axis=0)
            vs = np.unique(E)
            # the region's border vertices: on an edge it shares with another region (or the mesh's edge)
            inner_e = set(map(tuple, np.sort(ev[(fsel[f0]) & (fsel[f1])], axis=1)))
            bverts = set()
            for a, b in E:
                if (a, b) not in inner_e:
                    bverts.add(int(a)); bverts.add(int(b))
            bverts = np.array(sorted(bverts))
            adj = {}
            for a, b in E:
                L = float(np.linalg.norm(co[a] - co[b]))
                adj.setdefault(int(a), []).append((int(b), L))
                adj.setdefault(int(b), []).append((int(a), L))
            Pv = co[vs]
            if rname in ("head", "neck", "chest", "midriff", "pelvis"):
                yc = np.median(Pv[:, 1])
                hid = lambda v: math.exp(-(co[v, 0] / .002) ** 2) * (1.0 if co[v, 1] > yc else 0.0)
                axis = np.array([0, 0, 1.0])
                if rname == "head":
                    hid = lambda v: math.exp(-(co[v, 0] / .002) ** 2) * (1.0 if co[v, 1] > -.025 else 0.0)
            elif rname in ("upperarm", "forearm"):
                S, a_, up, _ = B.arm_axis(sx)
                hid = lambda v, up=up: max(0.0, -float(vn[v] @ up))
                axis = a_
            else:
                hid = lambda v, sx=sx: max(0.0, -float(vn[v, 0]) * sx)
                axis = np.array([0, 0, 1.0])
            s_along = Pv @ axis
            lo_s, hi_s = np.percentile(s_along, 2), np.percentile(s_along, 98)
            bpos = co[bverts] @ axis
            mid = .5 * (lo_s + hi_s)
            cand_a = bverts[bpos < mid]
            if rname == "head":                                      # the head: from the nape up to the crown's top
                top = vs[np.argmax(Pv[:, 2] - 50 * np.abs(Pv[:, 0]))]
                cand_b = np.array([top])
            elif rname == "pelvis":                                  # the pelvis: down to the crotch
                cand_b = np.array([vs[np.argmin(Pv[:, 2] + 50 * np.abs(Pv[:, 0]) - 5 * Pv[:, 1])]])
                cand_a = bverts[bpos > mid]
            else:
                cand_b = bverts[bpos >= mid]
            if not len(cand_a) or not len(cand_b):
                continue
            src = int(max(cand_a, key=hid))
            dst = int(max(cand_b, key=hid))
            path = dijkstra(adj, src, dst, lambda v, w, L: L * (1 + 60 * (1 - .5 * (hid(v) + hid(w)))))
            for a, b in zip(path, path[1:]):
                add(a, b)
            cuts += 1
    bm = bmesh.new(); bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    n_on = 0
    for e in bm.edges:
        k = (min(e.verts[0].index, e.verts[1].index), max(e.verts[0].index, e.verts[1].index))
        e.seam = k in seams
        n_on += e.seam
    bm.to_mesh(me); bm.free()
    log(f"seams: {nb} on the regions' and ears' borders, {ns} round hands / feet / ears, {cuts} cuts; {n_on} edges")
    return seams


# ---------------------------------------------------------------------------------------------------------------
# unwrap and pack

FACE_SET = ("head",)            # the regions on the face's map (the head and its ears)


def unwrap(o):
    me = o.data
    bpy.context.view_layer.objects.active = o
    for ob in bpy.context.scene.objects:
        ob.select_set(ob is o)
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    nf = len(me.polygons)
    region = read(me, "region", nf, np.int32)
    face_set = np.isin(region, [B.REGIONS.index(r) for r in FACE_SET])
    hands = region == B.REGIONS.index("hand")
    # every island at one density (texels per metre), the hands at more
    islands = uv_islands(me)
    uv = uv_array(me)
    ls = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_total", lt)
    co = coords(me)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    for faces in islands:
        loops = np.concatenate([np.arange(ls[f], ls[f] + lt[f]) for f in faces])
        a3 = sum(poly_area(co[lv[ls[f]:ls[f] + lt[f]]]) for f in faces)
        a2 = sum(abs(poly_area2(uv[ls[f]:ls[f] + lt[f]])) for f in faces)
        k = math.sqrt(a3 / max(a2, 1e-12))
        if hands[faces].mean() > .5:
            k *= HAND_DENSITY
        c = uv[loops].mean(0)
        uv[loops] = c + (uv[loops] - c) * k
    set_uv(me, uv)
    # pack each map's islands into the square
    for name, sel in (("face", face_set), ("body", ~face_set)):
        pack(o, sel)
        log(f"uv: {name} map packed ({int(sel.sum())} faces)")
    report_density(o, face_set)


def poly_area(P):
    return .5 * np.linalg.norm(sum(np.cross(P[i], P[(i + 1) % len(P)]) for i in range(len(P))))


def poly_area2(Q):
    x, y = Q[:, 0], Q[:, 1]
    return .5 * (x * np.roll(y, -1) - np.roll(x, -1) * y).sum()


def uv_array(me):
    uv = np.zeros(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    return uv.reshape(-1, 2).astype(np.float64)


def set_uv(me, uv):
    me.uv_layers.active.data.foreach_set("uv", uv.astype(np.float32).ravel())


def uv_islands(me):
    """faces grouped by shared UV corners across their edges (the seams split them)"""
    nf = len(me.polygons)
    F = np.asarray(quads(me))
    uv = uv_array(me)
    ls = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_start", ls)
    parent = np.arange(nf)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    # an edge joins two faces' islands when both its corners have the same UV in both faces
    corner = {}
    for f in range(nf):
        for k in range(4):
            a, b = int(F[f, k]), int(F[f, (k + 1) % 4])
            ua, ub = uv[ls[f] + k], uv[ls[f] + (k + 1) % 4]
            key = (min(a, b), max(a, b))
            ends = (ua, ub) if a < b else (ub, ua)
            if key in corner:
                g, (pa, pb) = corner[key]
                if np.abs(pa - ends[0]).max() < 1e-6 and np.abs(pb - ends[1]).max() < 1e-6:
                    ra, rb = find(f), find(g)
                    if ra != rb:
                        parent[ra] = rb
            else:
                corner[key] = (f, ends)
    roots = np.array([find(i) for i in range(nf)])
    return [np.flatnonzero(roots == r) for r in np.unique(roots)]


def pack(o, sel):
    me = o.data
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.scene.tool_settings.use_uv_select_sync = True       # the UVs' selection is the mesh's
    bpy.ops.mesh.select_mode(type='FACE')
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    for v in bm.verts:
        v.select = False
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = bool(sel[f.index])
    bm.select_flush_mode()
    bmesh.update_edit_mesh(me)
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=True,
                            merge_overlap=False, margin_method='FRACTION', margin=.004, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')


def report_density(o, face_set):
    me = o.data
    nf = len(me.polygons)
    uv = uv_array(me)
    co = coords(me)
    ls = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_start", ls)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    region = read(me, "region", nf, np.int32)
    for name, sel in (("face", face_set), ("body", ~face_set)):
        faces = np.flatnonzero(sel)
        a3 = np.array([poly_area(co[lv[ls[f]:ls[f] + 4]]) for f in faces])
        a2 = np.array([abs(poly_area2(uv[ls[f]:ls[f] + 4])) for f in faces])
        used = a2.sum()
        dens = np.sqrt(a2 / np.maximum(a3, 1e-12)) * 4096           # texels per metre at 4K
        msg = [f"uv {name}: {used * 100:.0f} % of the square used, {4096 * 4096 * used / a3.sum() ** 1 / 1e6:.2f} Mtexel/m2"]
        for r in np.unique(region[faces]):
            m = region[faces] == r
            msg.append(f"{B.REGIONS[r]} {1000 / np.median(dens[m]):.2f} mm/texel")
        log(", ".join(msg))


# ---------------------------------------------------------------------------------------------------------------
# the skin's maps

SKIN_SIZE = 4096
NAMES = {"face": "orion_male_skin_face", "body": "orion_male_skin_body"}


SCALP_SHADE = .5                # a shaved scalp's shade where the hair grows (the lab's groomed head: .8 under its hair)


def head_marks(hd, P, edges=None):
    """per point (world metres): the shaved beard's shadow and the scalp's root shade (the lab's 'beard'), the lips'
    red part (the lab's 'lip'); headlab.skin_material reads both. The scalp's shade is spread over the surface
    (edges given: 40 rounds along them): groom.scalp_density is cut by planes (the sideburn's, behind the ear) that
    its hair hides and a shaved head showed as straight lines"""
    import groom as GR
    import headbase as HBm
    Q = GR.to_head(np.asarray(P, np.float64), hd)
    scalp = GR.scalp_shade(Q.astype(np.float32), hd).astype(np.float64)
    if edges is not None:
        e0, e1 = edges[:, 0], edges[:, 1]
        n = len(scalp)
        deg = np.maximum(np.bincount(e0, minlength=n) + np.bincount(e1, minlength=n), 1)
        for _ in range(40):
            avg = (np.bincount(e0, weights=scalp[e1], minlength=n) + np.bincount(e1, weights=scalp[e0], minlength=n)) / deg
            scalp = .5 * scalp + .5 * avg
    beard = np.maximum(GR.beard_mask(Q, hd, soft=True) * (hd.ear(Q.astype(np.float32)) > .6) * .3, SCALP_SHADE * scalp)
    lp = HBm.lips(Q.astype(np.float32), hd.stom_z, hd.k)[0]
    lip = np.clip(1 - lp / .12, 0, 1) * (np.abs(Q[:, 0]) < HBm.MOUTH_W + .1)
    return beard.astype(np.float32), lip.astype(np.float32)


def quad_edges(Qf):
    Qf = np.asarray(Qf)
    e = np.r_[Qf[:, [0, 1]], Qf[:, [1, 2]], Qf[:, [2, 3]], Qf[:, [3, 0]]]
    return np.unique(np.sort(e, axis=1), axis=0)


def put_marks(me, beard, lip):
    for name, v in (("beard", beard), ("lip", lip)):
        a = me.color_attributes.get(name) or me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
        a.data.foreach_set("color", np.c_[v, v, v, np.ones_like(v)].astype(np.float32).ravel())


def bake_image(name, size, data=True):
    im = bpy.data.images.get(name) or bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    im.colorspace_settings.name = 'Non-Color' if data else 'Linear Rec.709'
    return im


def target(mat, image):
    """the material's bake target: an unconnected image node, active"""
    nt = mat.node_tree
    n = nt.nodes.get("bake") or nt.nodes.new("ShaderNodeTexImage")
    n.name = "bake"
    n.image = image
    for m in nt.nodes:
        m.select = False
    n.select = True
    nt.nodes.active = n


def bake(kind, o, mats_images, high=None, extrude=.003, dist=.008, samples=16, **kw):
    """one Cycles bake into each material's own target image ({material: image}); high: bake from it onto o"""
    sc = bpy.context.scene
    sc.cycles.samples = samples
    for m, im in mats_images.items():
        target(m, im)
    for ob in sc.objects:
        ob.select_set(False)
    if high is not None:
        high.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bk = sc.render.bake
    bk.use_selected_to_active = high is not None
    bk.cage_extrusion = extrude
    bk.max_ray_distance = dist
    bk.margin = 24
    bk.margin_type = 'EXTEND'
    bk.use_clear = True
    bk.target = 'IMAGE_TEXTURES'
    t = time.time()
    bpy.ops.object.bake(type=kind, **kw)
    log(f"bake {kind}{' from ' + high.name if high is not None else ''}: {time.time() - t:.0f} s")


def pixels(im):
    a = np.zeros(im.size[0] * im.size[1] * 4, np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(im.size[1], im.size[0], 4)


def save_png(arr, path, srgb, depth=8):
    """arr (h, w, 3|4) linear floats; written as PNG (sRGB-encoded when srgb)"""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :arr.shape[2]] = arr[..., :4]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=False, float_buffer=True)
    im.colorspace_settings.name = 'Linear Rec.709' if srgb else 'Non-Color'
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    sc = bpy.context.scene
    st = sc.render.image_settings
    st.file_format = 'PNG'; st.color_mode = 'RGBA' if arr.shape[2] == 4 else 'RGB'; st.color_depth = str(depth)
    if srgb:
        sc.view_settings.view_transform = 'Standard'
    im.save_render(path, scene=sc)
    bpy.data.images.remove(im)


# the brows, hair by hair, in the face's own map: the B of its ORM is how much of a texel is hair, the game's skin puts
# the hair's colour over the skin by it (M_SOSkin: HairColor, HairAmount), so the creator can colour the brows with the
# hair. (Cards of six hairs each, laid on the skin, read as shingles and a hairbrush against the owner's bar for a face)
BROW_WIDTH = (.105, .035)        # mm: a brow hair at its root and at its tip


def brow_mask(o, face_set, size):
    """each of the groom's brow strands (groom.brows: roots along the brow, laid along its flow on the skin) carried
    onto the game mesh (nearest point, its UV from the triangle it lies in) and drawn into the face's map as a tapered
    line (0.13 mm a texel: a hair is a line of its own); returns the mask (size x size, rows as Blender's pixels)"""
    import groom as GR
    import head as HD
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    hd = HD.Head()
    S = np.asarray(GR.brows(hd), np.float64)                       # (n, k, 3) head cm
    n, k, _ = S.shape
    W = np.asarray(GR.to_world(S.reshape(-1, 3).astype(np.float32), hd), np.float64)
    me = o.data
    co = coords(me).astype(np.float64)
    nf = len(me.polygons)
    ls = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_total", lt)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2).astype(np.float64)
    tl = []
    for f in np.flatnonzero(face_set):
        s_, t_ = ls[f], lt[f]
        for j in range(1, t_ - 1):
            tl.append((s_, s_ + j, s_ + j + 1))
    tl = np.array(tl, np.int64)
    tv = lv[tl]
    bvh = BVHTree.FromPolygons([tuple(p) for p in co], [tuple(int(i) for i in t) for t in tv])
    UV = np.zeros((len(W), 2))
    far = 0
    dens = []
    for i, p in enumerate(W):
        loc, _nrm, ti, dist = bvh.find_nearest(Vector(p))
        if ti is None:
            far += 1
            continue
        if i % k == 0:                                         # the map's texels a millimetre where the root lies
            ta, tb, tc = co[tv[ti]]
            ua, ub, uc = uv[tl[ti]]
            aw = np.linalg.norm(np.cross(tb - ta, tc - ta)) * 1e6           # mm2
            au = abs((ub - ua)[0] * (uc - ua)[1] - (ub - ua)[1] * (uc - ua)[0]) * size * size
            if aw > 1e-9:
                dens.append(np.sqrt(au / aw))
        a, b, c = co[tv[ti]]
        q = np.asarray(loc, np.float64)
        v0, v1, v2 = b - a, c - a, q - a
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
        d20, d21 = v2 @ v0, v2 @ v1
        den = max(d00 * d11 - d01 * d01, 1e-18)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        UV[i] = uv[tl[ti, 0]] * (1 - bv - bw) + uv[tl[ti, 1]] * bv + uv[tl[ti, 2]] * bw
        far += dist > .002
    UV = UV.reshape(n, k, 2) * size
    px_mm = float(np.median(dens)) if dens else 7.7
    mask = np.zeros((size, size), np.float32)
    w0, w1 = BROW_WIDTH[0] * px_mm, BROW_WIDTH[1] * px_mm
    for s in range(n):
        P = UV[s]
        for j in range(k - 1):
            p0, p1 = P[j], P[j + 1]
            wa = w0 + (w1 - w0) * j / (k - 1)
            wb = w0 + (w1 - w0) * (j + 1) / (k - 1)
            r = max(wa, wb) / 2 + 1.5
            x0, x1 = int(max(min(p0[0], p1[0]) - r, 0)), int(min(max(p0[0], p1[0]) + r, size - 1)) + 1
            y0, y1 = int(max(min(p0[1], p1[1]) - r, 0)), int(min(max(p0[1], p1[1]) + r, size - 1)) + 1
            if x1 <= x0 or y1 <= y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1) + .5, np.arange(y0, y1) + .5)
            d = p1 - p0
            L2 = max(d @ d, 1e-9)
            t = np.clip(((gx - p0[0]) * d[0] + (gy - p0[1]) * d[1]) / L2, 0, 1)
            dist = np.hypot(gx - (p0[0] + t * d[0]), gy - (p0[1] + t * d[1]))
            w = wa + (wb - wa) * t
            cov = np.clip(w / 2 + .5 - dist, 0, np.minimum(w, 1.0))
            sub = mask[y0:y1, x0:x1]
            mask[y0:y1, x0:x1] = 1 - (1 - sub) * (1 - cov)
    log(f"brows: {n} hairs drawn into the face's map ({px_mm:.1f} texels a mm; {far} of {len(W)} points over 2 mm off "
        f"the skin)")
    return mask



def skin_maps(o, out, size=SKIN_SIZE):
    """the face's and the body's skin maps (colour, normal, roughness, occlusion), baked through the head lab's own
    skin (headlab.skin_material: made for this head): the face from the sculpt itself (0.6 mm surface nets, high to
    low: the lids' margins, the lips' line, the ears' folds), the body from the game mesh"""
    import headlab as HL
    import head as HD
    import sdf
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    HL.gpu(sc)
    me = o.data
    nf = len(me.polygons)
    region = read(me, "region", nf, np.int32)
    face_set = np.isin(region, [B.REGIONS.index(r) for r in FACE_SET])
    hd = HD.Head()
    co = coords(me)
    beard, lip = head_marks(hd, co, quad_edges(quads(me)))
    put_marks(me, beard, lip)
    # the materials: the face's slot and the body's, both the lab's skin (the body's bakes from itself)
    skin = HL.skin_material(False)
    skin.name = "skin"
    face = skin.copy(); face.name = "skin_face"
    me.materials.clear()
    me.materials.append(face); me.materials.append(skin)
    me.polygons.foreach_set("material_index", np.where(face_set, 0, 1).astype(np.int32))
    # (every map is baked from the game mesh itself, the face's too: baked from a dense copy of the sculpt, rays met
    # the wrong side of the nose and the lids (streaks across the bridge of the nose) and missed under the jaw where
    # the head's skin leaves the sculpt down the neck (black specks along the jaw); the shader draws the lips' line,
    # the pores and the creases from the position at any mesh)
    dummy = bake_image("dummy", 64)
    res = {}
    for part in ("face", "body"):
        own = face if part == "face" else skin
        other = skin if part == "face" else face
        out_ = {}
        for kind, extra, data in (("DIFFUSE", dict(pass_filter={'COLOR'}), False), ("ROUGHNESS", {}, True),
                                  ("NORMAL", dict(normal_space='TANGENT'), True), ("AO", {}, True)):
            im = bake_image(f"{part}_{kind}", size, data)
            bake(kind, o, {own: im, other: dummy}, samples=(16 if kind != "AO" else 64), **extra)
            out_[kind] = pixels(im)
        res[part] = out_
    brows = brow_mask(o, face_set, size)
    import hair_cards as HC
    scalp, _ = HC.scalp_mask(o, face_set, size, log=log)       # the scalp's short hair and the floor under the cards
    brows = np.maximum(brows, scalp)
    for part, maps in res.items():
        stem = os.path.join(out, NAMES[part])
        save_png(maps["DIFFUSE"][..., :3], stem + "_BaseColor.png", srgb=True)
        save_png(maps["NORMAL"][..., :3], stem + "_Normal.png", srgb=False)
        ao = np.clip(maps["AO"][..., 0], 0, 1) ** .7
        hair = brows if part == "face" else np.zeros_like(ao)
        orm = np.dstack([ao, np.clip(maps["ROUGHNESS"][..., 0], .2, 1), hair])
        save_png(orm, stem + "_ORM.png", srgb=False)
        log(f"skin maps: {stem}_*.png")
    return res


# ---------------------------------------------------------------------------------------------------------------
# the eyes: the sculpt's own eyeballs (head.extras: a globe and its cornea's bulge), each unwrapped from the front (the
# iris in the middle of the map), the lab's eye (headlab.eye_material) baked into one map both share

EYE_SIZE = 1024


def fresh_material(name):
    """a material of this name with no older one left in the file (a stage run again on a saved build made
    `eye.001`, and the game's import looks the maps up by the name)"""
    for m in list(bpy.data.materials):
        if m.name == name or (m.name.startswith(name + ".") and m.name[len(name) + 1:].isdigit()):
            bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m


def make_eyes(out, size=EYE_SIZE):
    import head as HD
    import headlab as HL
    hd = HD.Head()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    HL.gpu(sc)
    for ob in [ob for ob in sc.objects if ob.name.startswith(("B_eyes", "eye_L", "eye_R"))]:
        bpy.data.objects.remove(ob, do_unlink=True)
    objs = []
    for name, (EV, EF, _col) in hd.extras():
        c = EV.mean(0)
        o = HL.to_object(name, EV - c, EF, origin=tuple(c))
        me = o.data
        uv = me.uv_layers.new(name="UVMap")
        lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
        P = (EV - c)[lv]
        r = np.linalg.norm(P, axis=1).max()
        # the front half (-Y) from the front: x across, z up, the iris in the middle; the back half (never seen)
        # into a small corner of its own (laid over the front, its white baked over the iris: blank eyes)
        ls = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get("loop_start", ls)
        lt = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get("loop_total", lt)
        front = np.zeros(len(lv), bool)
        for s_, t_ in zip(ls, lt):
            front[s_:s_ + t_] = P[s_:s_ + t_, 1].mean() < .35 * r   # (past the equator: through a wide opening the
            # globe's side shows, and the map's corner was a red patch at the outer corner)
        UVs = np.where(front[:, None], np.c_[.5 + .45 * P[:, 0] / r, .5 + .45 * P[:, 2] / r],
                       np.c_[.03 + .02 * P[:, 0] / r, .03 + .02 * P[:, 2] / r])
        uv.data.foreach_set("uv", UVs.astype(np.float32).ravel())
        m = HL.eye_material("eye_bake")
        me.materials.append(m)
        objs.append(o)
    im = bake_image("eye_DIFFUSE", size, data=False)
    for o in objs:
        for ob in sc.objects:
            ob.select_set(False)
        bake("DIFFUSE", o, {o.data.materials[0]: im}, samples=8, pass_filter={'COLOR'})
        # (each eye bakes over the same map: both are the same eye, mirrored)
        bk = sc.render.bake
        bk.use_clear = False
    sc.render.bake.use_clear = True
    path = os.path.join(out, "orion_male_eye_BaseColor.png")
    save_png(pixels(im)[..., :3], path, srgb=True)
    # one object, both eyes, in the world's frame, one material ("eye": its map, wet)
    for o in objs:
        o.data.transform(o.matrix_world)
        o.matrix_world = o.matrix_world.Identity(4)
    for ob in sc.objects:
        ob.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    eyes = objs[0]
    eyes.name = eyes.data.name = "B_eyes"
    m = fresh_material("eye")
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(path)
    nt.links.new(t.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = .08
    b.inputs["Metallic"].default_value = 0.0
    eyes.data.materials.clear()
    eyes.data.materials.append(m)
    for p in eyes.data.polygons:
        p.use_smooth = True
    log(f"eyes: {len(eyes.data.vertices)} vertices, their map {path}")
    return eyes


# ---------------------------------------------------------------------------------------------------------------
# the lashes (B_lashes: hair__lash): cards made from the groom's own strands (groom.lashes, the new head's), a few
# lashes to a card, each card a ribbon along its lid (its width along the lid, its length out along the lashes); an
# atlas of lashes drawn here; the cards follow the face's sliders (each vertex the skin's own key under it). The brows
# are drawn hair by hair into the face's own map (brow_mask)

HAIR_COLS = 8


def hair_atlas(path, size=1024, cols=HAIR_COLS, seed=3, base=(.030, .021, .016), tip=(.075, .055, .042), coarse=1.0,
               per=(14, 21), taper=.85, dense=0):
    """(per: strands a column; taper: how much of a strand's root width is gone at its tip; dense: the last `dense`
    columns carry twice the strands, close-packed: the base layer of a head of hair)"""
    """an atlas of hair clumps (RGBA, linear colour): `cols` columns, each a clump of tapered strands from the root
    (v = 0, the top of the image) to the tip, alpha their coverage, the colour lighter toward the tips"""
    rng = np.random.default_rng(seed)
    H = W = size
    alpha = np.zeros((H, W), np.float32)
    tone = np.zeros((H, W), np.float32)
    cw = W / cols
    ys = np.arange(H, dtype=np.float32) + .5
    for c in range(cols):
        # (a card of 2 mm is 128 px: a brow hair, about a tenth of a millimetre, is 5-7 px at its root; each starts
        # a little further in than the last and fades in, or every card's roots drew one hard line)
        is_dense = c >= cols - dense
        m = rng.integers(*per) * (2 if is_dense else 1)
        for _ in range(m):
            x0 = (c + rng.uniform(.12, .88)) * cw
            v0 = rng.uniform(0, .2) * H
            L = rng.uniform(.6, .98) * H
            bend = rng.uniform(-.12, .12) * cw
            wob = rng.uniform(-.03, .03) * cw
            w0 = rng.uniform(4.0, 6.5) * coarse * size / 1024 * (1.25 if is_dense else 1.0)
            t = np.clip((ys - v0) / max(L - v0, 1.0), 0, 1)
            xc = x0 + bend * t * t + wob * np.sin(t * 6.0 + rng.uniform(0, 6))
            width = w0 * (1 - taper * t) * (ys < L) * (ys > v0) * np.clip(t / .08, 0, 1)
            lo, hi = int(max(0, x0 - cw)), int(min(W, x0 + cw))
            xs = np.arange(lo, hi, dtype=np.float32) + .5
            d = np.abs(xs[None, :] - xc[:, None])
            cov = np.clip(width[:, None] / 2 - d + .5, 0, 1)
            a = alpha[:, lo:hi]
            alpha[:, lo:hi] = 1 - (1 - a) * (1 - cov)
            tone[:, lo:hi] = np.maximum(tone[:, lo:hi], cov * t[:, None])
    col = np.asarray(base, np.float32)[None, None] * (1 - tone[..., None]) + np.asarray(tip, np.float32)[None, None] * tone[..., None]
    rgba = np.dstack([col, alpha])
    save_png(rgba[::-1].copy(), path, srgb=True)      # (Blender's rows run up: the root at the image's top)
    log(f"hair atlas: {path}")


def cards_from(strands, hd, groups, width, cols, rng, facing=None):
    """one card per group of strands (head cm): their mean line, as wide as `width` (cm), lying across the skin
    (facing None: its normal the skin's at the root) or across `facing` (a direction it shows to)"""
    import groom as GR
    V, Fc, UV = [], [], []
    for g in groups:
        S = strands[g]
        c = S.mean(0)                                         # (k, 3)
        k = len(c)
        tan = np.gradient(c, axis=0)
        tan /= np.maximum(np.linalg.norm(tan, axis=1), 1e-9)[:, None]
        if facing is None:
            nrm = GR.grad_world(hd, GR.to_world(c[:1], hd).astype(np.float32))[0]
            nrm = np.asarray(nrm, np.float64)
            side = np.cross(nrm, tan)
        elif isinstance(facing, str) and facing == "along":
            # across the card: along the lid (the line through its lashes' roots), square to the lashes
            R0 = S[:, 0]
            if len(g) > 1:
                _u, _s, vt = np.linalg.svd(R0 - R0.mean(0), full_matrices=False)
                lid = vt[0]
            else:
                lid = np.array([1.0, 0.0, 0.0])
            if lid[0] < 0:
                lid = -lid
            side = lid[None] - tan * (tan @ lid)[:, None]
        else:
            side = np.cross(np.asarray(facing, np.float64)[None], tan)
        side /= np.maximum(np.linalg.norm(side, axis=1), 1e-9)[:, None]
        spread = np.ptp(S[:, 0] @ side[0]) if len(g) > 1 else 0.0
        w = max(width, min(2.2 * width, spread + width * .6))
        taper = np.linspace(1.0, .55, k)[:, None]
        L = c - side * (w / 2) * taper
        R = c + side * (w / 2) * taper
        base = len(V) and sum(len(v) for v in V)
        V.append(np.r_[L, R])
        col = rng.integers(0, cols)
        u0, u1 = col / cols + .004, (col + 1) / cols - .004
        for i in range(k - 1):
            Fc.append((base + i, base + i + 1, base + k + i + 1, base + k + i))
        vv = np.linspace(1.0, .02, k)                         # the root at the atlas's top
        UV.append(np.r_[np.c_[np.full(k, u0), vv], np.c_[np.full(k, u1), vv]])
    import groom as GR
    Vw = GR.to_world(np.concatenate(V), hd)
    return Vw, Fc, np.concatenate(UV)


def kmeans_groups(P, n_groups, rng, iters=12):
    idx = rng.choice(len(P), n_groups, replace=False)
    C = P[idx].copy()
    for _ in range(iters):
        d = ((P[:, None, :] - C[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1)
        for j in range(n_groups):
            m = lab == j
            if m.any():
                C[j] = P[m].mean(0)
    return [np.flatnonzero(lab == j) for j in range(n_groups) if (lab == j).any()]


def make_lashes(body, out):
    """B_lashes: the lashes (about four to a card on the upper lid, three on the lower), weighted to the head, with the
    face's keys from the skin under them"""
    import groom as GR
    import head as HD
    hd = HD.Head()
    rng = np.random.default_rng(17)
    for ob in [ob for ob in bpy.context.scene.objects if ob.name.startswith(("B_brows", "B_lashes"))]:
        bpy.data.objects.remove(ob, do_unlink=True)
    lash_png = os.path.join(out, "orion_male_lash_strands.png")
    hair_atlas(lash_png, seed=9, base=(.010, .008, .007), tip=(.022, .018, .015), coarse=1.15, per=(5, 8))
    La = np.asarray(GR.lashes(hd), np.float64)
    n_up, n_lo = 115, 65                                   # (groom.lashes: upper left, upper right, lower left, lower right)
    blocks = [(0, n_up, 4), (n_up, 2 * n_up, 4), (2 * n_up, 2 * n_up + n_lo, 3), (2 * n_up + n_lo, 2 * n_up + 2 * n_lo, 3)]
    groups = []
    for i0, i1, per in blocks:
        sel = np.arange(i0, min(i1, len(La)))
        if not len(sel):
            continue
        k = max(1, len(sel) // per)
        groups += [sel[g] for g in kmeans_groups(La[sel, 0], k, rng)]
    V, F, UV = cards_from(La, hd, groups, .10, HAIR_COLS, rng, "along")
    parts = [(V, F, UV, "hair__lash", lash_png)]
    log(f"hair__lash: {len(groups)} cards from {len(La)} lashes")
    verts, faces, uvs, mats = [], [], [], []
    for i, (V, F, UV, mat_name, png) in enumerate(parts):
        base = sum(len(p[0]) for p in parts[:i])
        verts.append(V)
        faces += [tuple(int(v) + base for v in f) for f in F]
        mats += [i] * len(F)
        uvs.append(UV)
    V = np.concatenate(verts)
    me = bpy.data.meshes.new("B_lashes")
    me.from_pydata(V.astype(np.float32).tolist(), [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    UVa = np.concatenate(uvs)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    uv.data.foreach_set("uv", UVa[lv].astype(np.float32).ravel())
    me.polygons.foreach_set("material_index", np.array(mats, np.int32))
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("B_lashes", me)
    bpy.context.scene.collection.objects.link(o)
    for (V_, F_, UV_, mat_name, png) in parts:
        m = fresh_material(mat_name)
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(png, check_existing=True)
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
        b.inputs["Roughness"].default_value = .45
        try:
            m.surface_render_method = 'DITHERED'
        except Exception:
            pass
        m.blend_method = 'CLIP' if hasattr(m, "blend_method") else None
        me.materials.append(m)
    # the face's keys: each vertex the skin's own delta under it
    keys = body.data.shape_keys
    if keys:
        n = len(body.data.vertices)
        base_co = np.zeros(n * 3, np.float32); keys.key_blocks[0].data.foreach_get("co", base_co); base_co = base_co.reshape(n, 3)
        hw = read(body.data, "headw", n)
        head_v = np.flatnonzero(hw > .5)
        from mathutils.kdtree import KDTree
        kd = KDTree(len(head_v))
        for i, vi in enumerate(head_v):
            kd.insert(base_co[vi], i)
        kd.balance()
        near = np.array([head_v[kd.find(tuple(p))[1]] for p in V])
        o.shape_key_add(name="Basis", from_mix=False)
        for kb in keys.key_blocks[1:]:
            k = np.zeros(n * 3, np.float32); kb.data.foreach_get("co", k); k = k.reshape(n, 3)
            D = (k - base_co)[near]
            nk = o.shape_key_add(name=kb.name, from_mix=False)
            nk.value = 0.0
            nk.data.foreach_set("co", (V + D).astype(np.float32).ravel())
    log(f"lashes: {len(V)} vertices, {len(faces)} cards' quads")
    return o


# ---------------------------------------------------------------------------------------------------------------
# the skeleton (the game's shared player layout, characters.make_armature: root > hips > spine > chest > neck > head;
# chest > clavicle.X > upperarm.X > forearm.X > hand.X > <finger>_01..03.X; hips > thigh.X > shin.X > foot.X), its
# joints where THIS body's are: the shoulder, elbow and wrist of its arm (body.arm_axis), the hand's own finger
# joints (hand.joints_of / thumb_joints), the knee at its leg's knee ring, the ankle and the toes' roots of its foot

FINGER_GAME = {"index": "index", "middle": "middle", "ring": "ring", "little": "pinky"}


def joints(co):
    """{bone: (head, tail)} in metres, both sides, from the body's own construction and its mesh"""
    import hand as HM
    from mathutils import Vector
    C, info = B.build(log=lambda *a: None, game_head=False)
    V = lambda p: Vector(tuple(float(c) for c in p))
    # the spine's line: at each height, 62 % of the way from the front of the midline to its back
    mid = np.abs(co[:, 0]) < .004

    def spine_y(z, share=.62):
        near = mid & (np.abs(co[:, 2] - z) < .012)
        ys = co[near, 1]
        return float(ys.min() + share * (ys.max() - ys.min()))
    J = {}
    hip_z = B.CROTCH_Z + .035                                   # the femoral heads, 3.5 cm over the crotch
    waist_z, chest_z, neck_z = 1.100, 1.300, 1.515
    head = V((0, H_Y0() + .010, H_Z0() - .045))                 # the skull's pivot, below and behind the ears' canals
    J["hips"] = (V((0, spine_y(hip_z + .035, .5), hip_z + .035)), V((0, spine_y(waist_z), waist_z)))
    J["spine"] = (J["hips"][1], V((0, spine_y(chest_z), chest_z)))
    J["chest"] = (J["spine"][1], V((0, spine_y(neck_z, .55), neck_z)))
    J["neck"] = (J["chest"][1], head)
    J["head"] = (head, V((0, float(head.y), B.STATURE)))
    for side, sx in (("L", 1), ("R", -1)):
        S, a, up, back = B.arm_axis(sx)
        E, W = S + a * B.UPPER_ARM, S + a * (B.UPPER_ARM + B.FOREARM)
        F = next(f for f in info["hands"] if f.sx == sx)
        fingers = {}
        for name, kx, ky, L, _r, spread in HM.FINGERS:
            fingers[FINGER_GAME[name]] = [V(p) for p in HM.joints_of(F, kx, ky, L, spread)]
        fingers["thumb"] = [V(p) for p in HM.thumb_joints(F)]
        J["upperarm." + side] = (V(S), V(E))
        J["forearm." + side] = (V(E), V(W))
        J["hand." + side] = (V(W), fingers["middle"][0])
        for name, ch in fingers.items():
            for k in range(3):
                J[f"{name}_0{k + 1}.{side}"] = (ch[k], ch[k + 1])
        # the clavicle: from beside the jugular notch, in front, to the shoulder joint
        J["clavicle." + side] = (V((.024 * sx, S[1] - .040, neck_z - .022)), V(S))
        # the leg: the hip joint, the knee in its ring's middle (a little behind it), the ankle; the foot to the toes'
        # roots (the second's)
        Ft = next(f for f in info["feet"] if f.sx == sx)
        A = np.asarray(Ft.A, float)
        ring = [np.asarray(C.V[v]) for v in info["legs"][sx][1 + B.L_Z.index(B.KNEE_Z)]]
        Hj = np.array([.088 * sx, spine_y(hip_z, .45), hip_z])
        K = np.mean(ring, axis=0)
        # the knee a little AHEAD of the line from the hip to the ankle (the way it bends: a knee behind that line, as a
        # straight leg's can be, was bent backward by the game's leg IK, 27 cm in a sideways crouch-walk)
        Aa = np.asarray(Ft.A, float)
        tl = (K[2] - Hj[2]) / (Aa[2] - Hj[2])
        line_y = Hj[1] + (Aa[1] - Hj[1]) * tl
        K[1] = min(K[1], line_y - .012)
        J["thigh." + side] = (V(Hj), V(K))
        J["shin." + side] = (V(K), V(A))
        J["foot." + side] = (V(A), V(Ft.p(.139, -.0055, .020)))
    feet = {f.sx: f for f in info["feet"]}
    Fl = feet[1]
    foot_pts = {"ankle": V(Fl.A), "ball": V(Fl.p(.139, -.0055, 0.0)), "heel": V(Fl.p(-.063, .003, 0.0))}
    return J, foot_pts


def H_Y0():
    import head as HD
    return HD.Y0


def H_Z0():
    import head as HD
    return HD.Z0


def rigid_skull(o, z_head):
    """the skull and the face whole on the head bone: the heat weights spread the neck's share up the face, so when
    the head pitched 80 degrees (the aim) the sockets lagged behind the eyeballs, which are weighted whole to the
    head, and the eyes stood out of the face (the owner, 2026-11-21: "the players eyes seem to be popping out of his
    head"). From 2 cm under the skull's base joint up, blended in over 5 cm (the throat under the jaw stays the neck's)"""
    names = {g.index: g.name for g in o.vertex_groups}
    head = o.vertex_groups.get("head")
    if head is None:
        return
    n = 0
    for v in o.data.vertices:
        k = (v.co.z - (z_head - .02)) / .05
        if k <= 0.0:
            continue
        k = min(1.0, k)
        k = k * k * (3 - 2 * k)
        w = {g.group: g.weight for g in v.groups}
        total = sum(w.values()) or 1.0
        wh = w.get(head.index, 0.0)
        for gi, wt in w.items():
            if gi != head.index:
                o.vertex_groups[gi].add([v.index], wt * (1 - k), 'REPLACE')
        head.add([v.index], wh + (total - wh) * k, 'REPLACE')
        n += 1
    log(f"rig: the skull rigid on the head from {100 * (z_head - .02):.0f} cm up ({n} vertices)")


def make_rig(o, log_=None):
    """the armature on THIS body's joints, the body skinned to it (automatic heat weights), the IK helpers the shared
    layout carries kept out of the deform set"""
    import characters
    import types
    from mathutils import Vector
    for ob in [ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE']:      # (a rig made before)
        bpy.data.objects.remove(ob, do_unlink=True)
    for m in [m for m in o.modifiers if m.type == 'ARMATURE']:
        o.modifiers.remove(m)
    o.vertex_groups.clear()
    o.parent = None
    co = coords(o.data)
    J, foot_pts = joints(co)
    b = types.SimpleNamespace(J=J, s=B.STATURE / 1.84)
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    arm = characters.make_armature(b, pole_angle=90)
    arm.name = "Armature"
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for side in "LR":
        c = eb.new("clavicle." + side)
        c.head, c.tail = J["clavicle." + side]
        c.align_roll(Vector((0, 0, 1)))
        c.parent = eb["chest"]
        up = eb["upperarm." + side]
        up.use_connect = False
        up.parent = c
        dorsal = (J["hand." + side][1] - J["hand." + side][0]).cross(
            J["index_01." + side][0] - J["pinky_01." + side][0]).normalized()
        if dorsal.z < 0:
            dorsal = -dorsal
        for name in ("index", "middle", "ring", "pinky", "thumb"):
            parent = eb["hand." + side]
            for k in range(3):
                e = eb.new(f"{name}_0{k + 1}.{side}")
                e.head, e.tail = J[f"{name}_0{k + 1}.{side}"]
                e.align_roll(dorsal)
                e.parent = parent
                e.use_connect = k > 0
                parent = e
    bpy.ops.object.mode_set(mode='OBJECT')
    for bn in arm.data.bones:
        if bn.name == "root" or bn.name.startswith(("ik_", "pole")):
            bn.use_deform = False
    # skin: Blender's heat weights, solved on a closed copy of the body (voxels of 4 mm: the eyes' openings filled,
    # the ears' and lids' fine folds smoothed over; on the body itself the solve failed for every vertex), then each
    # vertex given its nearest face's on the copy
    sc = bpy.context.scene
    proxy = o.copy()
    proxy.data = o.data.copy()
    proxy.modifiers.clear()
    sc.collection.objects.link(proxy)
    if proxy.data.shape_keys:
        proxy.shape_key_clear()
    bmp = bmesh.new()                                   # (open, the eyes' openings broke the voxels' inside: 4k left)
    bmp.from_mesh(proxy.data)
    bmesh.ops.holes_fill(bmp, edges=[e for e in bmp.edges if e.is_boundary], sides=0)
    bmp.to_mesh(proxy.data)
    bmp.free()
    rm = proxy.modifiers.new("remesh", 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = .0045
    dg = bpy.context.evaluated_depsgraph_get()
    pme = bpy.data.meshes.new_from_object(proxy.evaluated_get(dg))
    proxy.modifiers.clear()
    proxy.data = pme
    for ob in sc.objects:
        ob.select_set(False)
    proxy.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    unweighted = sum(1 for v in proxy.data.vertices if not any(g.weight > 1e-4 for g in v.groups))
    log(f"rig: heat weights on a closed copy ({len(proxy.data.vertices)} vertices), {unweighted} without a weight")
    copy_weights(proxy, o)
    bpy.data.objects.remove(proxy, do_unlink=True)
    rigid_skull(o, float(J["neck"][1][2]))
    o.parent = arm
    mod = o.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    unweighted = sum(1 for v in o.data.vertices if not any(g.weight > 1e-4 for g in v.groups))
    log(f"rig: {len(arm.data.bones)} bones; {unweighted} body vertices without a weight")
    arm["foot_points"] = {k: list(v) for k, v in foot_pts.items()}
    return arm, J, foot_pts


# ---------------------------------------------------------------------------------------------------------------
# the undersuit (always worn, never armour: the owner, 2026-11-17, "the undersuit is on at all times and armor goes on
# top of that"): the game's piece is this body's own mesh offset and cut as the suit is (suit.py: off the skin by
# OFFSET, the skin's grooves spanned, cut under the collar, at the wrists' ring and the ankles' ring, so every region
# it hides is wholly under it), its collar's surface beside it; the lab's detailed suit (panels over the muscles,
# seams, piping, plates, the knee's shell, lights, the relief) and collar baked onto it

SUIT_SIZE = 4096
SUIT_NAME = "orion_male_suit"
SUIT_HIDE = ("chest", "midriff", "pelvis", "upperarm", "forearm", "thigh", "shin")


def copy_weights(src, dst):
    """dst's vertex groups from src's (each vertex from the nearest face's, interpolated), both in the rest pose (the
    transfer reads src as it is drawn: posed by a clip, the sleeves took the torso's weights)"""
    rigs = [ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE']
    was = {r: r.data.pose_position for r in rigs}
    for r in rigs:
        r.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    for g in src.vertex_groups:
        if g.name not in dst.vertex_groups:
            dst.vertex_groups.new(name=g.name)
    m = dst.modifiers.new("weights", 'DATA_TRANSFER')
    m.object = src
    m.use_vert_data = True
    m.data_types_verts = {'VGROUP_WEIGHTS'}
    m.vert_mapping = 'POLYINTERP_NEAREST'
    m.layers_vgroup_select_src = 'ALL'
    m.layers_vgroup_select_dst = 'NAME'
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    dst.select_set(True)
    bpy.context.view_layer.objects.active = dst
    bpy.ops.object.modifier_apply(modifier=m.name)
    for r, p in was.items():
        r.data.pose_position = p


def rewired(mat, socket):
    """a copy of mat whose surface is an emission of what feeds its BSDF's `socket` (to bake that value)"""
    m = mat.copy()
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    link = next((lk for lk in nt.links if lk.to_socket == bsdf.inputs[socket]), None)
    if link is not None:
        nt.links.new(link.from_socket, em.inputs["Color"])
    else:
        v = bsdf.inputs[socket].default_value
        em.inputs["Color"].default_value = (v, v, v, 1) if isinstance(v, float) else tuple(v)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def make_suit(o, arm, out, size=SUIT_SIZE):
    import suit as SU
    sc = bpy.context.scene
    # just past the wrists' ring and the ankles' ring (6 mm over the hand's and the foot's skin): the forearm and the
    # shin wholly under it (cut on the rings themselves, the subdivided rings wander a hair either side)
    SU.SUIT_WRIST, SU.SUIT_ANKLE = B.UPPER_ARM + B.FOREARM + .006, B.L_Z[-1] - .006
    zb = SU.neckline(o, log=log)
    # --- the game's suit: the body's mesh, off the skin, cut
    low = o.copy()
    low.data = o.data.copy()
    low.modifiers.clear()
    low.parent = None
    sc.collection.objects.link(low)
    low.name = low.data.name = "C_suit__orion"
    if low.data.shape_keys:
        low.shape_key_clear()
    for ob in sc.objects:
        ob.select_set(False)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me = low.data
    co = coords(me).astype(np.float64)
    nr = vertex_normals(me).astype(np.float64)
    ed = np.zeros(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    off = co + nr * SU.OFFSET
    span = SU.smooth_vectors(off, ed, 10)
    lift = np.maximum(((span - off) * nr).sum(1), 0.0)
    co2 = off + nr * lift[:, None]
    me.vertices.foreach_set("co", co2.astype(np.float32).ravel())
    me.update()
    # which regions it covers wholly (the game hides those: no skin through the suit in any pose)
    f = SU.cut_field(co2, zb)
    nf = len(me.polygons)
    region = read(me, "region", nf, np.int32)
    F = np.asarray(quads(me))
    hide = []
    for r in SUIT_HIDE:
        vs = np.unique(F[region == B.REGIONS.index(r)])
        n_out = int((f[vs] > 1e-6).sum())
        if n_out == 0:
            hide.append(r)
        else:
            log(f"suit: {r} not wholly under it ({n_out} vertices out): not hidden")
    bm = bmesh.new()
    bm.from_mesh(me)
    SU.iso_cut(bm, f)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # --- the lab's detailed suit and its collar on this body (the bake's sources)
    hi = SU.build_suit(o, log=log, zb=zb)
    hi.modifiers.clear()                                          # (its thickness: only its outside is baked)
    # the relief itself onto the game's mesh (each of its vertices takes the fine suit's relief at the nearest point:
    # the plates, the knee's shell, the shoulder caps and the studs stand in its silhouette; the bevels and the seams
    # stay the normal map's)
    if True:
        from mathutils.kdtree import KDTree
        hme = hi.data
        nh = len(hme.vertices)
        hco = np.zeros(nh * 3, np.float32); hme.vertices.foreach_get("co", hco); hco = hco.reshape(nh, 3)
        hrel = np.zeros(nh, np.float32); hme.attributes["relief"].data.foreach_get("value", hrel)
        kd = KDTree(nh)
        for i in range(nh):
            kd.insert(hco[i], i)
        kd.balance()
        co3 = coords(me).astype(np.float64)
        nr3 = vertex_normals(me).astype(np.float64)
        rel_lo = np.array([hrel[kd.find(tuple(p))[1]] for p in co3], np.float64)
        me.vertices.foreach_set("co", (co3 + nr3 * rel_lo[:, None]).astype(np.float32).ravel())
        me.update()
        log(f"suit: the game's mesh carries the relief, {rel_lo.min() * 1000:.1f} .. {rel_lo.max() * 1000:.1f} mm")
    collar_hi = SU.build_collar(o, hi, o, zb, log=log)
    collar = collar_hi.copy()
    collar.data = collar_hi.data.copy()
    collar.modifiers.clear()
    sc.collection.objects.link(collar)
    if "thick" in collar_hi.modifiers:
        collar_hi.modifiers.remove(collar_hi.modifiers["thick"])
    # the collar's seam down its back, then into the suit's object
    cme = collar.data
    bmc = bmesh.new()
    bmc.from_mesh(cme)
    for e in bmc.edges:
        va, vb = e.verts
        e.seam = abs(va.co.x) < 1e-4 and abs(vb.co.x) < 1e-4 and va.co.y > 0 and vb.co.y > 0
    bmc.to_mesh(cme)
    bmc.free()
    while cme.uv_layers:
        cme.uv_layers.remove(cme.uv_layers[0])
    cme.uv_layers.new(name="UVMap")
    for a in list(cme.color_attributes):
        cme.color_attributes.remove(a)
    cme.materials.clear()
    for ob in sc.objects:
        ob.select_set(False)
    collar.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.join()
    me = low.data
    # its own UVs: the body's seams (kept on the copy) and the cuts' edges; unwrapped, packed into its own square
    for ob in sc.objects:
        ob.select_set(False)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    pack(low, np.ones(len(me.polygons), bool))
    log(f"suit: {len(me.vertices)} vertices, {len(me.polygons)} faces (the body's own mesh and the collar's surface)")
    # --- the bake: colour, roughness, metal, the lights, the normal (the relief, the panels' edges, the seams), occlusion
    import headlab as HL
    sc.render.engine = 'CYCLES'
    HL.gpu(sc)
    target_mat = bpy.data.materials.new(SUIT_NAME + "_bake")
    target_mat.use_nodes = True
    me.materials.clear()
    me.materials.append(target_mat)
    highs = (hi, collar_hi)
    mats = {h: h.data.materials[0] for h in highs}
    res = {}
    for kind, extra, data, swap in (("DIFFUSE", dict(pass_filter={'COLOR'}), False, None), ("ROUGHNESS", {}, True, None),
                                    ("EMIT", {}, True, "Metallic"), ("EMIT", {}, False, None),
                                    ("NORMAL", dict(normal_space='TANGENT'), True, None), ("AO", {}, True, None)):
        key = "METALLIC" if swap == "Metallic" else kind
        for h in highs:
            h.data.materials[0] = rewired(mats[h], swap) if swap else mats[h]
        im = bake_image(f"suit_{key}", size, data)
        for ob in sc.objects:
            ob.select_set(False)
        for h in highs:
            h.select_set(True)
        sc.cycles.samples = 16 if kind != "AO" else 48
        target(target_mat, im)
        low.select_set(True)
        bpy.context.view_layer.objects.active = low
        bk = sc.render.bake
        bk.use_selected_to_active = True
        bk.cage_extrusion = .006
        bk.max_ray_distance = .012
        bk.margin = 24
        bk.margin_type = 'EXTEND'
        bk.use_clear = True
        bk.target = 'IMAGE_TEXTURES'
        t = time.time()
        bpy.ops.object.bake(type=kind, **extra)
        log(f"suit bake {key}: {time.time() - t:.0f} s")
        res[key] = pixels(im)
    for h in highs:
        h.data.materials[0] = mats[h]
    stem = os.path.join(out, SUIT_NAME)
    save_png(res["DIFFUSE"][..., :3], stem + "_BaseColor.png", srgb=True)
    save_png(res["NORMAL"][..., :3], stem + "_Normal.png", srgb=False)
    orm = np.dstack([np.clip(res["AO"][..., 0], 0, 1) ** .8, np.clip(res["ROUGHNESS"][..., 0], .05, 1),
                     np.clip(res["METALLIC"][..., 0], 0, 1)])
    save_png(orm, stem + "_ORM.png", srgb=False)
    glow = np.clip(res["EMIT"][..., :3] / 7.0, 0, 1)                   # (the lights' strength, 7, set on the material)
    save_png(glow, stem + "_Emissive.png", srgb=True)
    for h in highs:
        bpy.data.objects.remove(h, do_unlink=True)
    # --- the game's material, the body's weights, onto the rig
    m = bpy.data.materials.new("orion_suit")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]

    def img(kind, data):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(f"{stem}_{kind}.png", check_existing=True)
        n.image.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
        return n
    nt.links.new(img("BaseColor", False).outputs[0], bsdf.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(img("ORM", True).outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("Normal", True).outputs[0], nmap.inputs["Color"])
    nt.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
    nt.links.new(img("Emissive", False).outputs[0], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 7.0
    me.materials.clear()
    me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    copy_weights(o, low)
    low.parent = arm
    mod = low.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    log(f"suit: its maps {stem}_*.png; hides {', '.join(hide)}")
    return low, hide


# ---------------------------------------------------------------------------------------------------------------
# the clips: the male's own motion (tools/blender/hero/male/motion.py: his gait, his idle, his blows, as the owner
# approved them) baked by the motion engine (gait.py) on THIS skeleton: it plans the feet and solves the legs on the
# body it is given, so every clip is fitted to the new body's legs, arms and feet

def make_clips(arm, foot_pts):
    import importlib.util
    hero = os.path.dirname(HERE)
    if hero not in sys.path:
        sys.path.append(hero)                    # (last: its anatomy.py must not stand in for this folder's)
    import gait
    path = os.path.join(os.path.dirname(HERE), "male", "motion.py")
    spec = importlib.util.spec_from_file_location("motion_male", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    up = arm.data.bones["upperarm.L"]
    a = (up.tail_local - up.head_local).normalized()
    arms_down = math.degrees(math.atan2(-a.z, a.x)) - 84.0      # the clips are written for arms at the sides
    body = gait.Body(arm, {"height": B.STATURE, "foot": foot_pts}, arms_down)
    clips, _ = mod.clips(body)
    made = gait.bake(arm, body, clips, log)
    for side in "LR":                                   # the shared layout's arm IK (unused: the game has its own)
        pb = arm.pose.bones["forearm." + side]
        if "IK" in pb.constraints:
            pb.constraints.remove(pb.constraints["IK"])
    log(f"clips: {len(made)} baked on the new skeleton")
    return made


# ---------------------------------------------------------------------------------------------------------------
# into the game's shape: one object per region (B_<region>, its material skin__<region>: the game hides what a worn
# piece covers by these), the eyes (B_eyes), the wardrobe's metadata on the armature (`worldex`), a GLB that
# tools/blender/export_fbx.py --per-item turns into the game's FBX files

def skin_material(name, stem, out):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]

    def img(kind, data):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(os.path.join(out, f"{stem}_{kind}.png"), check_existing=True)
        n.image.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
        return n
    nt.links.new(img("BaseColor", False).outputs[0], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(img("ORM", True).outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], b.inputs["Roughness"])          # G: roughness (R occlusion, B the brows' hair)
    # every channel of the packed map wired the way glTF packs one (R occlusion through the exporter's own output group,
    # G roughness, B "metallic"), so the exporter writes the map as it is: with only G wired it wrote a map of its own,
    # R and B white, and in the game the skin lost its occlusion and the whole face took the brows' colour (M_SOSkin
    # reads B as the hair, never as metal)
    nt.links.new(sep.outputs[2], b.inputs["Metallic"])
    gltf = bpy.data.node_groups.get("glTF Material Output")
    if gltf is None:
        gltf = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        gltf.interface.new_socket("Occlusion", in_out='INPUT', socket_type='NodeSocketFloat')
    go = nt.nodes.new("ShaderNodeGroup")
    go.node_tree = gltf
    nt.links.new(sep.outputs[0], go.inputs["Occlusion"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("Normal", True).outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    return m


def split_regions(o, out):
    """the body into one object per region, each with its own material slot skin__<region> (the face's maps on the
    head, the body's on the rest)"""
    me = o.data
    nf = len(me.polygons)
    region = read(me, "region", nf, np.int32)
    me.materials.clear()
    face = skin_material("skin_face", NAMES["face"], out)
    body = skin_material("skin", NAMES["body"], out)
    for r, name in enumerate(B.REGIONS):
        m = (face if name == "head" else body).copy()
        m.name = "skin__" + name
        me.materials.append(m)
    me.polygons.foreach_set("material_index", region.astype(np.int32))
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')
    parts = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and ob.data.materials
             and ob.data.materials[0].name.startswith("skin__")]
    for ob in parts:
        used = {p.material_index for p in ob.data.polygons}
        mat = ob.data.materials[min(used)]
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        ob.name = ob.data.name = "B_" + mat.name.split("__", 1)[1].split(".")[0]
        # shape keys only where the face's sliders move something
        keys = ob.data.shape_keys
        if keys and ob.name != "B_head":
            basis = np.zeros(len(ob.data.vertices) * 3, np.float32)
            keys.key_blocks[0].data.foreach_get("co", basis)
            moves = False
            for kb in keys.key_blocks[1:]:
                k = np.zeros_like(basis); kb.data.foreach_get("co", k)
                moves |= bool(np.abs(k - basis).max() > 1e-6)
            if not moves:
                ob.shape_key_clear()
    log(f"regions: {', '.join(sorted(ob.name for ob in parts))}")
    return parts


def attach_eyes(eyes, arm):
    vg = eyes.vertex_groups.new(name="head")
    vg.add(list(range(len(eyes.data.vertices))), 1.0, 'REPLACE')
    eyes.parent = arm
    mod = eyes.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm


def write_glb(path, arm, wardrobe=None, defaults=None):
    import json
    arm["worldex"] = json.dumps({"wardrobe": wardrobe or {}, "defaults": defaults or {}, "regions": list(B.REGIONS)})
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_animations=True, export_morph=True,
                              export_skins=True, export_yup=True, export_apply=False, use_selection=False,
                              export_extras=True, export_vertex_color='NONE')
    log(f"glb: {path} ({os.path.getsize(path) / 1e6:.1f} MB)")


# ---------------------------------------------------------------------------------------------------------------

STAGES = ("normals", "uv", "skin", "eyes", "lashes", "hair", "rig", "suit", "clips", "export")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    os.makedirs(out, exist_ok=True)
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    stages = flags.get("--stages", ",".join(STAGES)).split(",")
    o = body_object()
    if o is not None:
        log(f"{o.name}: {len(o.data.vertices)} vertices, {len(o.data.polygons)} faces")
    else:
        log("the body is already split into its regions (a saved build after its export)")
    if "normals" in stages:
        field_normals(o)
    if "uv" in stages:
        mark_seams(o)
        unwrap(o)
    if "skin" in stages:
        skin_maps(o, out, int(flags.get("--size", SKIN_SIZE)))
    eyes = None
    if "eyes" in stages:
        eyes = make_eyes(out)
        arm0 = next((ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE'), None)
        if arm0 is not None and "rig" not in stages:
            attach_eyes(eyes, arm0)
    lashes = None
    if "lashes" in stages:
        lashes = make_lashes(o, out)
        arm0 = next((ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE'), None)
        if arm0 is not None and "rig" not in stages:
            attach_eyes(lashes, arm0)
    hair = None
    if "hair" in stages:
        import hair_cards as HC
        hair, _ = HC.make_hair(o, out, log=log)
        arm0 = next((ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE'), None)
        if arm0 is not None and "rig" not in stages:           # (grown again on a rigged build: onto its head bone)
            attach_eyes(hair, arm0)
    arm = foot_pts = None
    if "rig" in stages:
        arm, J, foot_pts = make_rig(o)
        eyes = eyes or bpy.data.objects.get("B_eyes")
        if eyes is not None:
            attach_eyes(eyes, arm)
        lashes = lashes or bpy.data.objects.get("B_lashes")
        if lashes is not None:
            attach_eyes(lashes, arm)                     # (on the head bone, as the eyes)
        hair = hair or bpy.data.objects.get("B_hair")
        if hair is not None:
            attach_eyes(hair, arm)
    wardrobe, defaults = {}, {}
    if "suit" in stages:
        arm = arm or next(ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE')
        suit, hide = make_suit(o, arm, out, int(flags.get("--suit-size", SUIT_SIZE)))
        wardrobe["suit"] = {"orion": {"label": "Orion Undersuit", "hide": list(hide)}}
        defaults["suit"] = "orion"
        arm["suit_hide"] = list(hide)
    if "clips" in stages:
        arm = arm or next(ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE')
        if foot_pts is None:
            from mathutils import Vector
            foot_pts = {k: Vector(v) for k, v in arm["foot_points"].items()}
        make_clips(arm, foot_pts)
    if isinstance(flags.get("--save"), str):          # (the build before the export splits it: stages run again on it)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(flags["--save"]))
        log("saved", flags["--save"])
    if "export" in stages:
        arm = arm or next(ob for ob in bpy.context.scene.objects if ob.type == 'ARMATURE')
        if not wardrobe and "suit_hide" in arm.keys():
            wardrobe["suit"] = {"orion": {"label": "Orion Undersuit", "hide": list(arm["suit_hide"])}}
            defaults["suit"] = "orion"
        if o is not None:
            split_regions(o, out)
        write_glb(os.path.join(out, flags.get("--glb", "orion_male.glb")), arm, wardrobe, defaults)


if __name__ == "__main__":
    main()
