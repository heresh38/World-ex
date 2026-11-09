"""The Orion gloves: fingerless tactical gloves (the concept's) and an armoured full-finger pair, built on the hand
like the other garments (coat.py):

  shell      the hand and wrist eased a millimetre or two, the fingers cut clean half way along the first phalanx
             (fingerless) or kept whole (armoured), the cuff cut clean up the forearm
  seams      fourchettes between the fingers and the back's seam to the cuff, stitched; the openings topstitched
  palm       a synthetic suede reinforcement over the palm, stitched round
  knuckles   moulded pads over each knuckle (armoured: plates down every finger segment too)
  cuff       a wrist strap round the back of the cuff with its tab and a D-ring
  wrist tech the concept's device on the back of the wrist: a rounded housing, a light strip, two buttons
Left glove built on the body, the right one its mirror. Hidden body region: hand (armoured only; the fingerless
pair leaves the fingers bare, so the hand stays).
"""
import math
import bmesh
from mathutils import Vector, Matrix
import garment

CLOTH, SUEDE, PLATE, STEEL, GLOW, STITCH = "orion_black", "orion_strap", "orion_plate", "orion_steel", "orion_glow", "orion_stitch"


def shell(info, armoured):
    from coat import bisect, keep_largest, strip_shape_layers
    from wardrobe import drape_out
    A, Hd = info.A, info.H
    W, a = A["W"], A["a"]
    bm = info.bm.copy()
    strip_shape_layers(bm)
    bm.faces.ensure_lookup_table()
    drop = []
    for f, r in zip(bm.faces, info.face_region):
        c = f.calc_center_median()
        q = Vector((abs(c.x), c.y, c.z))
        if c.x <= 0 or not (r == "hand" or (r == "forearm" and (q - W).dot(a) > -.09)):
            drop.append(f)
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    keep_largest(bm)
    bm.normal_update()
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        e = .0016 if (v.co - W).dot(a) > .01 else .0024
        v.co = loc + nrm * e
    bm.normal_update()
    drape_out(bm, info, 2, min_off=.0012)
    # the cuff, clean across the forearm
    bisect(bm, bm.faces[:], W - a * .060, -a, clear=True)
    if not armoured:                                        # fingerless: each finger and the thumb cut clean
        for ch in list(Hd["fingers"].values()) + [Hd["thumb"]]:
            J = ch["joints"]
            d = (J[1] - J[0]).normalized()
            cut = J[0] + (J[1] - J[0]) * .55
            near = [f for f in bm.faces if seg_dist(f.calc_center_median(), J[0], J[2]) < ch["width"] * .9
                    and (f.calc_center_median() - J[0]).dot(d) > 0]
            if near:
                bisect(bm, near, cut, d, clear=True)
        keep_largest(bm)
        clean_openings(bm)
    bm.normal_update()
    return bm


def clean_openings(bm, passes=3, smooth=4):
    """the cuts' leftovers: slivers and tabs (faces with two or more open edges) go, then the openings' edges are
    smoothed along themselves so each finger hole is a clean curve"""
    for _ in range(passes):
        bad = [f for f in bm.faces if sum(1 for e in f.edges if e.is_boundary) >= 2]
        if not bad:
            break
        bmesh.ops.delete(bm, geom=bad, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for _ in range(smooth):
        new = {}
        for v in bm.verts:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                new[v] = v.co * .5 + (nb[0].co + nb[1].co) * .25
        for v, co in new.items():
            v.co = co


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def build_left(info, armoured, log=print):
    from wardrobe import to_object, material
    from coat import thick, inset_strip
    from coat_details import Surface, panel, solid
    import fabric
    A, Hd = info.A, info.H
    W, a, dor = A["W"], A["a"], A["dorsal"].normalized()
    palm_n = -dor
    bm = shell(info, armoured)
    edges = garment.boundary_chains(bm)
    o = to_object(bm, "glove", CLOTH)
    o.data.materials.append(material(CLOTH))
    thick(o, .0014)
    fabric.world_uvs(o, fabric.TILE["knit"])
    parts = [o]
    for ch in edges:
        st = inset_strip(o, ch, .0035, STITCH)
        if st:
            parts.append(st)
    surf = Surface(o)
    side = a.cross(dor).normalized()
    # the palm's suede reinforcement
    pc = W + a * (Hd["knuckle"] - W).length * .55
    fr = surf.frame(pc - dor * .03, palm_n, down=a)
    parts += panel(surf, fr, .070, .068, SUEDE, lift=.0010, thick=.0014, k=3.5, n=(12, 12), name="palm")
    # the knuckle guard: one low moulded strip across the knuckles (no separate bumps); the armoured pair adds a
    # plate down every finger segment
    J0 = [ch["joints"][0] for ch in Hd["fingers"].values()]
    kc = sum(J0, Vector()) / len(J0)
    span = max((p - q).length for p in J0 for q in J0) + .020
    kf = surf.frame(kc + dor * .03 - a * .004, dor, down=a)
    parts += panel(surf, kf, span, .020, PLATE, lift=.0012, thick=.0026, k=3.5, n=(20, 6),
                   lift_fn=lambda x, y: .0012 * (1 - y * y), name="knuckles", stitch=False)
    if armoured:
        for f, ch in Hd["fingers"].items():
            J = ch["joints"]
            for i in range(3):
                d = (J[i + 1] - J[i])
                m = J[i] + d * .5
                sf = surf.frame(m + dor * .03, dor, down=d.normalized())
                parts += panel(surf, sf, ch["width"] * .85, d.length * .78, PLATE, lift=.0015, thick=.0026, k=3.0,
                               n=(6, 6), lift_fn=lambda x, y: .0012 * (1 - x * x), name="fingerplate", stitch=False)
    if armoured:
        J = Hd["thumb"]["joints"]
        for i in range(1, 3):
            d = J[i + 1] - J[i]
            sf = surf.frame(J[i] + d * .5 + dor * .03, dor, down=d.normalized())
            parts += panel(surf, sf, Hd["thumb"]["width"] * .85, d.length * .78, PLATE, lift=.0015, thick=.0026, k=3.0,
                           n=(6, 6), lift_fn=lambda x, y: .0015 * (1 - x * x), name="fingerplate", stitch=False)
        bk = surf.frame(W + a * .045 + dor * .03, dor, down=a)
        parts += panel(surf, bk, .062, .050, PLATE, lift=.0018, thick=.0030, k=3.0,
                       lift_fn=lambda x, y: .003 * (1 - x * x) * (1 - y * y), name="backplate", stitch=False)
    # the wrist strap: round the back of the cuff, a tab and a D-ring
    c = W - a * .030
    pts = []
    for k in range(13):
        t = math.pi * (k / 12 - .5) * .95
        d = dor * math.cos(t) + side * math.sin(t)
        q, n = surf.toward(c + d * .08, -d)
        if q is not None:
            pts.append(q)
    if len(pts) > 4:
        strap, path = garment.strap(type("S", (), {"bvh": surf.tree})(), pts, .020, .0025, SUEDE, lift=.0018, name="cuffstrap")
        parts.append(strap)
        q, n = path[-2]
        parts += garment.d_ring(q + n * .002, n, .014, STEEL, up=a)
    # wrist tech: on the back of the wrist, over the strap's middle
    wc, wn = surf.toward(W - a * .040 + dor * .08, -dor)
    if wc is not None:
        R = Matrix((side, a, wn)).transposed()
        parts.append(garment.rounded_box((.034, .042, .010), R, wc + wn * .0085, STEEL, bevel=.003, segs=3, name="wristtech"))
        parts.append(garment.rounded_box((.022, .006, .0022), R, wc + wn * .0140 + a * .006, GLOW, bevel=.0010, segs=2,
                                         name="glow"))
        for s in (-.010, .010):
            parts.append(garment.rounded_box((.006, .006, .0022), R, wc + wn * .0140 - a * .010 + side * s, STEEL,
                                             bevel=.0012, segs=2, name="button"))
    return parts


def build(info, armoured=False, log=print):
    import bpy
    left = build_left(info, armoured, log=log)
    right = []
    for p in left:
        c = p.copy()
        c.data = p.data.copy()
        bpy.context.scene.collection.objects.link(c)
        for v in c.data.vertices:
            v.co.x = -v.co.x
        c.data.flip_normals()
        right.append(c)
    return left + right
