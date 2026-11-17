"""Quality control of a saved build (lab.py --save=x.blend): every anomaly on the skin found by measure, not by eye.

blender -b <build.blend> -P tools/blender/hero/orion/qc.py -- <out_prefix> [--thresh=18] [--views=feet,hands,...]

  * CREASES: on a subdivided skin two neighbouring faces turn by a few degrees; where they turn by more than
    --thresh degrees the surface folds, pinches or has a ridge it should not (a fin, a step, a sliver);
  * SELF-INTERSECTIONS: faces of the skin passing through other faces of it (a toe through its neighbour, a fold);
  * SPIKES: vertices standing out of their neighbours' plane by far more than the skin around them.
Writes <out_prefix>_<view>.png (the skin in clay, anomalies in red, worse = brighter) and prints each region's count
and its worst places (world metres), so a change can be checked against the last.
"""
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
FL = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
THRESH = float(FL.get("--thresh", 18))
VIEWS = {  # target, ortho size, (yaw, pitch) list
    "feet": ((0.0, -0.04, 0.07), .62, [(0, 15), (90, 5), (-90, 5), (180, 10), (0, -80), (35, 35)]),
    "hands": ((0.80, -0.03, 1.42), .36, [(0, 85), (0, -85), (0, 5), (180, 5)]),
    "toes": ((0.225, -0.10, 0.025), .15, [(0, 80), (0, 25), (40, 30), (-40, 30), (0, -80)]),
    "fingers": ((0.84, -0.03, 1.42), .16, [(0, 85), (0, -85), (0, 5), (40, 40)]),
    "head": ((0.0, -0.03, 1.66), .42, [(0, 0), (90, 0), (180, 0)]),
    "torso": ((0.0, -0.02, 1.22), .80, [(0, 0), (90, 0), (180, 0)]),
    "legs": ((0.0, -0.01, 0.50), 1.0, [(0, 0), (90, 0), (180, 0)]),
    "body": ((0.0, 0.0, 0.93), 2.0, [(0, 0), (90, 0), (180, 0), (35, 0)]),
}
REGIONS = [  # name, test on world points (N, 3)
    ("feet", lambda P: P[:, 2] < .22),
    ("lower legs", lambda P: (P[:, 2] >= .22) & (P[:, 2] < .55)),
    ("thighs/hips", lambda P: (P[:, 2] >= .55) & (P[:, 2] < 1.05) & (np.abs(P[:, 0]) < .25)),
    ("hands", lambda P: np.abs(P[:, 0]) > .68),
    ("forearms", lambda P: (np.abs(P[:, 0]) > .42) & (np.abs(P[:, 0]) <= .68)),
    ("upper arms", lambda P: (np.abs(P[:, 0]) > .22) & (np.abs(P[:, 0]) <= .42) & (P[:, 2] > 1.2)),
    ("torso", lambda P: (P[:, 2] >= 1.05) & (P[:, 2] < 1.55) & (np.abs(P[:, 0]) <= .22)),
    ("neck/head", lambda P: P[:, 2] >= 1.55),
]


def mesh_arrays(me):
    n = len(me.vertices)
    co = np.zeros(n * 3); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
    nf = len(me.polygons)
    fn = np.zeros(nf * 3); me.polygons.foreach_get("normal", fn); fn = fn.reshape(nf, 3)
    fc = np.zeros(nf * 3); me.polygons.foreach_get("center", fc); fc = fc.reshape(nf, 3)
    ls = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(nf, np.int64); me.polygons.foreach_get("loop_total", lt)
    le = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("edge_index", le)
    lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    ed = np.zeros(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", ed)
    return co, fn, fc, ls, lt, le, lv, ed.reshape(-1, 2)


def creases(me):
    co, fn, fc, ls, lt, le, lv, ed = mesh_arrays(me)
    face_of_loop = np.repeat(np.arange(len(ls)), lt)
    # each edge's two faces
    order = np.argsort(le, kind="stable")
    e_sorted = le[order]; f_sorted = face_of_loop[order]
    first = np.searchsorted(e_sorted, np.arange(len(ed)), "left")
    cnt = np.bincount(le, minlength=len(ed))
    two = cnt == 2
    fa = np.full(len(ed), -1); fb = np.full(len(ed), -1)
    fa[two] = f_sorted[first[two]]; fb[two] = f_sorted[first[two] + 1]
    ang = np.zeros(len(ed))
    m = two
    dots = np.clip((fn[fa[m]] * fn[fb[m]]).sum(1), -1, 1)
    ang[m] = np.degrees(np.arccos(dots))
    # per vertex: the sharpest turn of its edges
    va = np.zeros(len(co))
    np.maximum.at(va, ed[:, 0], ang); np.maximum.at(va, ed[:, 1], ang)
    return co, ed, ang, va


def spikes(co, ed):
    """how far each vertex stands out of the mean of its neighbours, against the edge length round it"""
    n = len(co)
    deg = np.bincount(ed[:, 0], minlength=n) + np.bincount(ed[:, 1], minlength=n)
    acc = np.zeros((n, 3))
    np.add.at(acc, ed[:, 0], co[ed[:, 1]]); np.add.at(acc, ed[:, 1], co[ed[:, 0]])
    mean = acc / np.maximum(deg, 1)[:, None]
    el = np.linalg.norm(co[ed[:, 0]] - co[ed[:, 1]], axis=1)
    elv = np.zeros(n)
    np.add.at(elv, ed[:, 0], el); np.add.at(elv, ed[:, 1], el)
    elv /= np.maximum(deg, 1)
    return np.linalg.norm(co - mean, axis=1) / np.maximum(elv, 1e-9)


def intersections(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm, epsilon=0.0)
    pairs = tree.overlap(tree)
    bad = []
    for a, b in pairs:
        if a >= b:
            continue
        va = {v.index for v in bm.faces[a].verts}; vb = {v.index for v in bm.faces[b].verts}
        if va & vb:
            continue                                   # neighbours touch by construction
        bad.append((a, b))
    cen = np.array([tuple(bm.faces[a].calc_center_median()) for a, _ in bad]) if bad else np.zeros((0, 3))
    verts = set()
    for a, b in bad:
        verts |= {v.index for v in bm.faces[a].verts} | {v.index for v in bm.faces[b].verts}
    bm.free()
    return cen, verts


def report(name, P, val, thresh, unit):
    for rname, test in REGIONS:
        m = test(P) & (val > thresh)
        if m.any():
            idx = np.nonzero(m)[0]
            worst = idx[np.argsort(-val[idx])[:4]]
            where = "; ".join(f"({P[i, 0]:+.3f}, {P[i, 1]:+.3f}, {P[i, 2]:.3f}) {val[i]:.0f}{unit}" for i in worst)
            print(f"[qc] {name} {rname}: {int(m.sum())} vertices; worst {where}", flush=True)


def render(obj, col, path_prefix, views):
    sc = bpy.context.scene
    for o in list(sc.objects):
        if o is not obj and o.type in ('MESH', 'CURVES', 'LIGHT'):
            o.hide_render = True
    me = obj.data
    a = me.color_attributes.new("qc", 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set("color", np.c_[col, np.ones(len(col))].astype(np.float32).ravel())
    me.color_attributes.active_color = a
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'VERTEX'
    sc.display.shading.show_cavity = False
    sc.view_settings.view_transform = 'Standard'
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("w")
    cam = bpy.data.objects.get("qc_cam") or bpy.data.objects.new("qc_cam", bpy.data.cameras.new("qc_cam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    sc.render.resolution_x = sc.render.resolution_y = int(FL.get("--res", 520))
    for vname in views:
        tgt, size, vs = VIEWS[vname]
        tgt = Vector(tgt)
        cam.data.ortho_scale = size
        imgs = []
        for i, (yaw, pitch) in enumerate(vs):
            y, p = math.radians(yaw), math.radians(pitch)
            d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
            cam.location = tgt + d * 4
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            f = f"{path_prefix}_{vname}_{i}.png"
            sc.render.filepath = f
            bpy.ops.render.render(write_still=True)
            im = bpy.data.images.load(f, check_existing=False)
            W, H = im.size
            imgs.append(np.array(im.pixels[:], np.float32).reshape(H, W, 4))
            bpy.data.images.remove(im)
            os.remove(f)
        sheet = np.concatenate(imgs, axis=1)
        img = bpy.data.images.new("qc_sheet", sheet.shape[1], sheet.shape[0], alpha=True)
        img.pixels = sheet.ravel()
        img.filepath_raw = f"{path_prefix}_{vname}.png"; img.file_format = 'PNG'; img.save()
        print("[qc] wrote", img.filepath_raw, flush=True)


def main():
    obj = bpy.data.objects["orion_male"]
    co, ed, ang, va = creases(obj.data)
    sp = spikes(co, ed)
    print(f"[qc] {len(co)} vertices; creases over {THRESH:.0f} deg: {int((va > THRESH).sum())}; "
          f"sharpest {va.max():.1f} deg", flush=True)
    report("crease", co, va, THRESH, " deg")
    report("spike", co, sp, 1.2, "x")
    cen, xv = intersections(obj)
    print(f"[qc] self-intersections: {len(cen)} face pairs", flush=True)
    if len(cen):
        hit = np.zeros(len(co)); hit[list(xv)] = 1
        report("intersection", co, hit * 10, 1, "")
    # colour: clay, creases from yellow to red, intersections magenta
    t = np.clip((va - THRESH * .6) / (THRESH * .9), 0, 1)
    col = np.tile([.72, .70, .67], (len(co), 1))
    col = col * (1 - t[:, None]) + np.array([1.0, .08, .02]) * t[:, None]
    s2 = np.clip((sp - 1.2) / 1.5, 0, 1)
    col = col * (1 - s2[:, None]) + np.array([.1, .3, 1.0]) * s2[:, None]
    if xv:
        col[list(xv)] = (1.0, 0.0, 1.0)
    views = str(FL.get("--views", "feet,hands,head,body")).split(",")
    if "--at" in FL:                         # a close look: --at=x,y,z,size (world), every side round it
        x, y, z, size = (float(v) for v in str(FL["--at"]).split(","))
        VIEWS["at"] = ((x, y, z), size, [(0, 20), (0, 60), (40, 25), (-40, 25), (0, -60)])
        views = ["at"]
        if "--wire" in FL:
            w = obj.modifiers.new("w", 'WIREFRAME'); w.thickness = float(FL.get("--wt", .00012)); w.use_replace = False
            w.use_even_offset = False; w.use_relative_offset = False
    render(obj, col, OUT, views)


main()
