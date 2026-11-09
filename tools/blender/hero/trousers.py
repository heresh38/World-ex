"""The Orion trousers: cargo trousers for him, plated trousers for her, cut and sewn like the coat (coat.py) and worn
tucked into the boots (boots.py):

  shell      the body's hips and legs, eased out (loose over the thighs, closer at the seat), draped across the
             hollows, cut clean at the waist and inside the boot (the leg narrows below the boot's top so the shaft
             covers it, and blouses in soft folds just above)
  seams      outseam and inseam down each leg, the centre back seam, the curved back yoke, the fly's J-stitch, the
             waistband's seam, articulated knee panels (a seam above and below the knee); pressed and stitched
  waistband  a band round the top with belt loops
  pockets    his: bellows cargo pockets on the outer thighs (flap, two studs), slanted front pockets; hers: thigh
             and shin plates
  knees      moulded knee plates on a coated backing, riveted
Hidden body regions: pelvis, thigh, shin (so no skin can show through in any pose).
"""
import math
import bmesh
from mathutils import Vector
from mathutils import noise as mnoise
import garment

CLOTH, PATCH, PLATE, STEEL, STITCH = "orion_cloth", "orion_strap", "orion_plate", "orion_steel", "orion_stitch"


class Cut:
    def __init__(self, info):
        T, L = info.T, info.L
        self.m = info.m
        self.waist = T["hips"]["z"] + (.065 if self.m else .080)
        self.H, self.K, self.A = L["H"], L["K"], L["A"]
        self.boot_top = self.A.z + (.145 if self.m else .165)
        self.hem = self.boot_top - .040                    # inside the boot
        self.yc = .012


def shell(info, C):
    from coat import bisect, keep_largest, strip_shape_layers
    from wardrobe import drape_out, Folds
    bm = info.bm.copy()
    strip_shape_layers(bm)
    bm.faces.ensure_lookup_table()
    drop = [f for f, r in zip(bm.faces, info.face_region) if r not in ("pelvis", "thigh", "shin", "midriff")
            or f.calc_center_median().z > C.waist + .05 or f.calc_center_median().z < C.hem - .05]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    keep_largest(bm)
    bm.normal_update()
    m = C.m
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        r = info.face_region[idx] if idx is not None else "thigh"
        z = v.co.z
        if z < C.boot_top - .010:                          # inside the boot: close to the leg
            e = .005
        elif r == "shin":
            e = .013 if m else .007
        elif r == "thigh":
            e = .016 if m else .008
        else:
            e = .010 if m else .006
        # blousing just above the boot's top
        if C.boot_top - .010 <= z < C.boot_top + .055:
            k = 1 - abs(z - (C.boot_top + .022)) / .035
            e += (.010 if m else .005) * max(0.0, k)
        v.co = loc + nrm * e
    bm.normal_update()
    drape_out(bm, info, 10, min_off=.004)
    F_ = Folds(info)
    seed = Vector((2.2, 7.1, .4))
    bm.normal_update()
    moves = []
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        r = info.face_region[idx] if idx is not None else "thigh"
        d = F_.trouser(v.co, r, .0055 if m else .0025)
        z = v.co.z
        if C.boot_top < z < C.boot_top + .06:              # the blouse's stacked folds
            d += (.0035 if m else .0015) * math.sin((z - C.boot_top) * 2 * math.pi / .018
                                                    + 2.5 * mnoise.noise(v.co * 25 + seed))
        d += .0007 * mnoise.noise(v.co * 35 + seed)
        moves.append((v, v.normal.copy(), d))
    for v, n, d in moves:
        v.co += n * d
    bm.normal_update()
    bisect(bm, bm.faces[:], (0, 0, C.waist), (0, 0, 1), clear=True)
    bisect(bm, bm.faces[:], (0, 0, C.hem), (0, 0, -1), clear=True)
    keep_largest(bm)
    bm.normal_update()
    return bm


def seams(bm, C):
    from coat import bisect, press, edge_chains
    out = []
    zc = lambda f: f.calc_center_median()
    for sx in (1, -1):
        Hx, Kx = C.H.x * sx, C.K.x * sx
        # outseam / inseam: the plane through the leg's axis, front to back
        for outer in (True, False):
            e = bisect(bm, [f for f in bm.faces if zc(f).z < C.H.z + .02 and (zc(f).x * sx > abs(Kx) if outer else
                                                                              0 < zc(f).x * sx < abs(Kx))],
                       (Kx, C.yc, 0), (0, 1, 0))
            out.append(("outseam" if outer else "inseam", e))
        # the knee panels: a seam above and one below the knee, across the front
        for dz in (.075, -.060):
            e = bisect(bm, [f for f in bm.faces if zc(f).y < C.K.y - .01 and abs(zc(f).z - C.K.z - dz) < .03
                            and zc(f).x * sx > 0], (0, 0, C.K.z + dz), (0, .25, 1))
            out.append(("knee", e))
        # the back yoke: a V across the seat, down from the side to the centre
        e = bisect(bm, [f for f in bm.faces if zc(f).y > .03 and zc(f).z > C.waist - .14 and zc(f).x * sx > 0],
                   (0, 0, C.waist - .085), (-.35 * sx, 0, 1))
        out.append(("yoke", e))
    # centre back, waist to crotch
    e = bisect(bm, [f for f in bm.faces if zc(f).y > .02 and zc(f).z > C.H.z - .06 and abs(zc(f).x) < .05], (0, 0, 0),
               (1, 0, 0))
    out.append(("back", e))
    # the waistband's seam
    e = bisect(bm, [f for f in bm.faces if abs(zc(f).z - C.waist + .04) < .03], (0, 0, C.waist - .040), (0, 0, 1))
    out.append(("band", e))
    res = []
    for kind, edges in out:
        edges = [g for g in edges if g.is_valid]
        for ch in edge_chains(edges):
            res.append((kind, ch))
    press(bm, [ch for _, ch in res], depth=.0010)
    bm.normal_update()
    return [(k, [(p - n * .0010, n) for p, n in ch]) for k, ch in res]


def build(info, log=print):
    from wardrobe import to_object, material
    from coat import thick, inset_strip
    from coat_details import Surface, panel, stud, solid
    import fabric
    C = Cut(info)
    bm = shell(info, C)
    seam_chains = seams(bm, C)
    edges = garment.boundary_chains(bm, test=lambda c: c.z > C.waist - .01)   # the waist's edge (the hem is hidden)
    o = to_object(bm, "legs", CLOTH)
    o.data.materials.append(material(CLOTH))
    thick(o, .0028)
    fabric.world_uvs(o, fabric.TILE["ripstop"])
    parts = [o]
    for kind, ch in seam_chains:
        for off in ((-.0030, .0030) if kind in ("outseam", "inseam", "back", "yoke") else (-.0028,)):
            st = garment.trim_strip(ch, .0014, STITCH, offset=off, lift=.0005, tile=.012, step=.003, name="stitch")
            if st:
                parts.append(st)
    for ch in edges:
        for d in (.006, .034):
            st = inset_strip(o, ch, d, STITCH)
            if st:
                parts.append(st)
    surf = Surface(o)
    parts += fly(surf, C)
    parts += belt_loops(surf, C)
    for sx in (1, -1):
        parts += knee_plate(surf, C, sx)
        if C.m:
            parts += cargo_pocket(surf, C, sx)
            parts += front_pocket(surf, C, sx)
        else:
            parts += thigh_plate(surf, C, sx)
            parts += shin_plate(surf, C, sx)
    log(f"trousers: shell {len(o.data.polygons)} faces, {len(seam_chains)} seams")
    return parts


def fly(surf, C):
    """the fly's J-stitch down the front from the waistband"""
    pts = []
    for k in range(25):
        t = k / 24
        x = .032 * (1 - (max(0.0, t - .70) / .30) ** 2)
        z = C.waist - .045 - .150 * t
        q, n = surf.toward(Vector((x, -.5, z)), Vector((0, 1, 0)), .0004)
        if q is not None:
            pts.append((q, n))
    out = []
    st = garment.trim_strip(pts, .0014, STITCH, tile=.012, step=.003, name="stitch")
    if st:
        out.append(st)
    return out


def belt_loops(surf, C):
    from coat_details import solid
    out = []
    for a in (-1.15, -.50, .50, 1.15, math.pi - .35, math.pi + .35):
        d = Vector((math.sin(a), -math.cos(a), 0))
        top, n = surf.toward(Vector((0, C.yc, C.waist - .006)) + d * .4, -d)
        if top is None:
            continue
        pts = []
        for k in range(9):
            z = C.waist - .004 - .050 * k / 8
            q, nn = surf.on(Vector((top.x, top.y, z)) + n * .02, n, .0012 + .0018 * math.sin(math.pi * k / 8))
            pts.append((q, nn))
        s = garment.trim_strip(pts, .011, CLOTH, tile=.03, step=.004, name="loop")
        if s:
            solid(s, .0018)
            out.append(s)
    return out


def knee_plate(surf, C, sx):
    from coat_details import panel, solid
    import garment as g
    K = Vector((C.K.x * sx, C.K.y, C.K.z))
    fr = surf.frame(K + Vector((0, -.08, .012)), Vector((.1 * sx, -1, .1)))
    out = panel(surf, fr, .090, .110, "orion_strap", lift=.0016, thick=.0022, k=3.0, name="kneepad")
    c, u, v, n = fr

    def dome(x, y):
        return .006 * (1 - x * x) * (1 - y * y)
    out += panel(surf, fr, .074, .092, PLATE, lift=.0045, thick=.0035, k=3.2, lift_fn=dome, name="kneeplate",
                 stitch=False)
    for x, y in ((-.026, -.032), (.026, -.032), (-.026, .032), (.026, .032)):
        q, qn = surf.on(c + u * x + v * y, n, .0045 + dome(x / .037, y / .046) + .002)
        out.append(g.rivet(q, qn, STEEL))
    return out


def cargo_pocket(surf, C, sx):
    """a bellows patch pocket on the outer thigh: the bag standing off the leg, its pleat, a flap with two studs"""
    from coat_details import panel, stud
    side = Vector((sx, -.45, 0)).normalized()
    p = Vector((C.H.x * sx + .050 * sx, C.yc - .035, C.K.z + .235))
    fr = surf.frame(p, side)
    c, u, v, n = fr

    def bellows(x, y):
        return .007 * (1 - abs(x) ** 4) * (1 - abs(y) ** 6) + .0015 * math.sin(x * 7)
    out = panel(surf, fr, .125, .165, CLOTH, lift=.0018, thick=.0024, k=6.0, lift_fn=bellows, name="cargo")
    flap = surf.frame(c - v * .080, n)
    out += panel(surf, flap, .132, .050, CLOTH, lift=.0080, thick=.0030, k=5.0,
                 lift_fn=lambda x, y: .002 * max(0.0, y), name="flap")
    fc, fu, fv, fn = flap
    for x in (-.038, .038):
        out += stud(surf, fc + fu * x + fv * .012, fn, .0050, .0115)
    return out


def front_pocket(surf, C, sx):
    """the slanted front pocket opening: a welt and stitching from the waistband down to the side"""
    pts = []
    for k in range(20):
        t = k / 19
        x = (.085 + .060 * t) * sx
        z = C.waist - .045 - .095 * t
        q, n = surf.toward(Vector((x, -.5, z)), Vector((0, 1, 0)))
        if q is not None:
            pts.append((q, n))
    out = []
    w = garment.trim_strip(pts, .006, CLOTH, lift=.0012, tile=.03, step=.003, name="welt")
    if w:
        from coat_details import solid
        solid(w, .0016)
        out.append(w)
    for off in (-.0055, .0055):
        st = garment.trim_strip(pts, .0014, STITCH, offset=off, lift=.0006, tile=.012, step=.003, name="stitch")
        if st:
            out.append(st)
    return out


def thigh_plate(surf, C, sx):
    from coat_details import panel
    p = Vector((C.H.x * sx + .02 * sx, -.08, C.K.z + .20))
    fr = surf.frame(p, Vector((.35 * sx, -1, 0)))
    out = panel(surf, fr, .080, .150, "orion_strap", lift=.0014, thick=.0020, k=3.5, name="thighpad")
    out += panel(surf, fr, .066, .132, PLATE, lift=.0040, thick=.0032, k=3.5,
                 lift_fn=lambda x, y: .004 * (1 - x * x), name="thighplate", stitch=False)
    return out


def shin_plate(surf, C, sx):
    from coat_details import panel
    p = Vector((C.K.x * sx, C.K.y - .065, C.K.z - .16))
    fr = surf.frame(p, Vector((.1 * sx, -1, 0)))
    out = panel(surf, fr, .060, .120, "orion_strap", lift=.0014, thick=.0020, k=3.0, name="shinpad")
    out += panel(surf, fr, .048, .104, PLATE, lift=.0038, thick=.0030, k=3.0,
                 lift_fn=lambda x, y: .004 * (1 - x * x), name="shinplate", stitch=False)
    return out
