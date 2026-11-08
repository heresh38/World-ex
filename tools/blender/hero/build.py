"""Builds a hero base mesh: the cage (cage.py + head.py), joined, checked, subdivided and fitted to the anatomy.

blender --background --python tools/blender/hero/build.py -- male|female [--cage] [--sheet out.png] [--levels 2]

  --cage     stop after the cage (no subdivision / fitting) - for checking the topology
  --sheet    render an orthographic front / side / back sheet with the wireframe over a clay shade
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import targets, cage as cage_mod, head as head_mod, shape as shape_mod, fit as fit_mod, headfit


def log(*a):
    print("[hero]", *a)


def build_cage(T):
    c = cage_mod.Cage(T).build()
    feat = head_mod.build_head(c, T)
    neck = c.match(c.neck_top, feat["neck"])
    c.bridge(c.neck_top, neck)
    bm = c.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    loose = [v for v in bm.verts if not v.link_faces]           # the cells inside the arm openings leave these
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return c


def mirror_topology(c, placed):
    """the right half rebuilt as the mirror of the left (positions AND connectivity): the limbs' rings are matched to
    their openings separately per side, so only an exact mirror guarantees the same edge flow on both sides"""
    from mathutils import kdtree
    bm = c.bm
    for v in bm.verts:
        if abs(v.co.x) < 1e-4:
            v.co.x = 0.0
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().x < -1e-6], context='FACES')
    left = list(bm.verts)
    kd = kdtree.KDTree(len(left))
    for i, v in enumerate(left):
        kd.insert(v.co, i)
    kd.balance()
    res = bmesh.ops.mirror(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), axis='X', merge_dist=1e-5)
    swap = lambda p: p[:-1] + {"L": "R", "R": "L"}[p[-1]] if p and p[-2:] in ("_L", "_R") else p
    placed = {v for v in placed if v.is_valid}
    for v in [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]:
        co, i, d = kd.find(Vector((-v.co.x, v.co.y, v.co.z)))
        src = left[i]
        if src in c.part_of:
            c.part_of[v] = swap(c.part_of[src])
        if src in placed:
            placed.add(v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return placed


def check(bm, label):
    """topology report: every face a quad, manifold edges, the open loops are only eyes and mouth"""
    bm.edges.ensure_lookup_table()
    sides = {}
    for f in bm.faces:
        sides[len(f.verts)] = sides.get(len(f.verts), 0) + 1
    nonman = [e for e in bm.edges if len(e.link_faces) > 2]
    bound = [e for e in bm.edges if len(e.link_faces) == 1]
    loose = [v for v in bm.verts if not v.link_faces]
    # symmetry: every vertex has a mirror partner
    from mathutils import kdtree
    kd = kdtree.KDTree(len(bm.verts))
    for i, v in enumerate(bm.verts):
        kd.insert(v.co, i)
    kd.balance()
    asym = 0
    for v in bm.verts:
        p = v.co.copy(); p.x = -p.x
        co, idx, d = kd.find(p)
        asym += d > 1e-4
    poles = {}
    for v in bm.verts:
        n = len(v.link_edges)
        if n != 4 and not v.is_boundary:
            poles[n] = poles.get(n, 0) + 1
    log(f"{label}: {len(bm.verts)} verts, faces by sides {dict(sorted(sides.items()))}, boundary edges {len(bound)}, "
        f"non-manifold {len(nonman)}, loose {len(loose)}, asymmetric verts {asym}, poles {dict(sorted(poles.items()))}")
    return dict(sides=sides, boundary=len(bound), nonmanifold=len(nonman), loose=len(loose), asym=asym)


def to_object(bm, name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def sheet(objs, path, wire=True, ortho=2.0):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (.78, .74, .70)
    sh.show_cavity = True
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("w")
    sc.render.resolution_x, sc.render.resolution_y = 900, 1100
    if wire:
        for o in objs:
            m = o.modifiers.new("wire", 'WIREFRAME')
            m.thickness = .0016
            m.use_replace = False
            m.use_even_offset = False
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    shots = []
    for view, yaw in (("front", 0), ("side", 90), ("back", 180)):
        y = math.radians(yaw)
        d = Vector((math.sin(y), -math.cos(y), 0))
        cam.location = d * 6 + Vector((0, 0, ortho / 2 - .02))
        cam.rotation_euler = (math.radians(90), 0, math.atan2(d.x, -d.y))
        p = path.replace(".png", f"_{view}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        shots.append(p)
    return shots


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["male"]
    sex = argv[0]
    T = targets.SEXES[sex]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    c = build_cage(T)
    check(c.bm, f"{sex} cage")
    if "--cage" in flags:
        o = to_object(c.bm, f"hero_{sex}_cage")
        if isinstance(flags.get("--sheet"), str):
            sheet([o], flags["--sheet"])
        return
    body = shape_mod.Body(T)
    placed = headfit.place_head(c, body, T, log=log)                     # the head laid on its landmarks
    placed = mirror_topology(c, placed)
    check(c.bm, f"{sex} cage (mirrored)")
    c.bm.verts.index_update()
    # the head is laid on its landmarks; fingers, thumbs and toes are built along their bones at their own widths
    # (a coarse 4-sided digit collapses if projected): neither moves until the subdivided mesh is fitted
    hold = [v.index for v in placed if v.is_valid] + [v.index for v in c.bm.verts
                                                      if c.part_of.get(v) in ("finger", "thumb", "toe") and v not in placed]
    o = fit_mod.cage_object(c, f"hero_{sex}")
    levels = int(flags.get("--levels", 2)) if isinstance(flags.get("--levels"), str) else 2
    fit_mod.fit(o, body, T, relax=3, log=lambda *a: log("cage", *a), hold=hold)   # the rest of the cage onto the body
    if "--nofine" not in flags:                                              # --nofine: keep the fitted cage
        fit_mod.subdivide(o, levels)
        fit_mod.fit(o, body, T, relax=16, log=log, per_part=False)                         # then the fine mesh (small moves)
    if "--nofine" not in flags and "--nokeys" not in flags:
        fit_mod.face_keys(o, shape_mod.Body, T, log=log)                    # face customisation shape keys
    eyes = fit_mod.eyeballs(body, T, f"hero_{sex}")
    bm = bmesh.new(); bm.from_mesh(o.data)
    check(bm, f"{sex} mesh"); bm.free()
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=flags["--save"])
    if isinstance(flags.get("--sheet"), str):
        sheet([o] + eyes, flags["--sheet"], wire=bool(flags.get("--wire")))


if __name__ == "__main__":
    main()
