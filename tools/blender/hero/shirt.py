"""The Orion base layer: his tactical combat shirt and her high-neck crop top, cut and sewn like the coat (coat.py).

  his    a knit body (close, wicking) with ripstop sleeves joined by raglan seams, a mock-neck collar with a quarter
         zip down the front, ribbed cuffs, side and underarm seams, the hem tucked into the trousers (it blouses a
         little over the waistband)
  hers   sleeveless, a high ribbed neck, princess and side seams, a ribbed band at the cropped hem (the midriff bare)
Close to the body (a few millimetres of ease) so the coat and jacket over it always have room: nothing can show
through them. Hidden body regions: his chest, midriff, upper arms, forearms; her chest.
"""
import math
import bmesh
from mathutils import Vector
from mathutils import noise as mnoise
import garment

KNIT, RIP, STITCH, STEEL, ZIP = "orion_black", "orion_cloth", "orion_stitch", "orion_steel", "orion_zip"


class Cut:
    def __init__(self, info):
        T, A = info.T, info.A
        self.m = info.m
        self.T = T
        self.nb, self.chin = T["neck_base_z"], T["chin_z"]
        self.S, self.E, self.W = A["S"], A["E"], A["W"]
        self.ua = (self.E - self.S).normalized()
        self.fa = (self.W - self.E).normalized()
        self.trouser_waist = T["hips"]["z"] + (.065 if self.m else .080)
        self.hem = self.trouser_waist - .050 if self.m else T["underbust"]["z"] - .040
        self.collar_top = self.chin - (.022 if self.m else .030)
        self.yc = .012
        self.raglan = []                                   # (side, front, point, normal, the sleeve's sign)

    def sleeve(self, c):
        """on a sleeve: past the raglan seam on the arm's side (or out along the arm)"""
        if self.arm(c) != 0:
            return True
        for sx, front, P0, n, sgn in self.raglan:
            if c.x * sx > .03 and (c.y < self.yc) == front and ((c - P0).dot(n) > 0) == sgn and c.z > self.S.z - .16:
                return True
        return False

    def mirror(self, v, sx):
        return Vector((v.x * sx, v.y, v.z))

    def arm(self, c):
        return 0 if abs(c.x) < .22 or c.z < self.hem else (1 if c.x > 0 else -1)


def shell(info, C):
    from coat import bisect, keep_largest, strip_shape_layers
    from wardrobe import drape_out, Folds
    m = C.m
    regions = ("chest", "midriff", "pelvis", "neck") + (("upperarm", "forearm") if m else ())
    bm = info.bm.copy()
    strip_shape_layers(bm)
    bm.faces.ensure_lookup_table()
    names = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
    reg = bm.faces.layers.int.new("reg")
    for f, r in zip(bm.faces, info.face_region):
        f[reg] = names.index(r)
    drop = [f for f, r in zip(bm.faces, info.face_region) if r not in regions
            or f.calc_center_median().z < C.hem - .05 or f.calc_center_median().z > C.collar_top + .03]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    keep_largest(bm)
    bm.normal_update()
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        r = info.face_region[idx] if idx is not None else "chest"
        e = {"neck": .0055, "upperarm": .0050, "forearm": .0050}.get(r, .0038)
        if m and C.trouser_waist - .01 < v.co.z < C.trouser_waist + .05:      # bloused over the waistband
            e += .004 * max(0.0, 1 - abs(v.co.z - C.trouser_waist - .02) / .03)
        v.co = loc + nrm * e
    bm.normal_update()
    drape_out(bm, info, 5, min_off=.0025)
    F_ = Folds(info)
    seed = Vector((4.4, 2.1, .8))
    bm.normal_update()
    moves = []
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        r = info.face_region[idx] if idx is not None else "chest"
        d = F_.sleeve(v.co, r, .0040, cuff=-.035) if m else 0.0
        if m and r in ("midriff", "pelvis"):
            d += F_.waist(v.co, C.trouser_waist, .0022)
        d += .0005 * mnoise.noise(v.co * 40 + seed)
        moves.append((v, v.normal.copy(), d))
    for v, n, d in moves:
        v.co += n * d
    bm.normal_update()
    # clean cuts: the collar's top (a touch higher at the back), the hem, the cuffs / armholes
    bisect(bm, bm.faces[:], (0, 0, C.collar_top), (0, -.30, 1), clear=True)
    bisect(bm, [f for f in bm.faces if C.arm(f.calc_center_median()) == 0], (0, 0, C.hem), (0, 0, -1), clear=True)
    for sx in (1, -1):
        if m:
            W, fa = C.mirror(C.W, sx), C.mirror(C.fa, sx)
            bisect(bm, [f for f in bm.faces if C.arm(f.calc_center_median()) == sx], W - fa * .018, fa, clear=True)
        else:                                               # sleeveless: the armhole round the shoulder joint
            S, ua = C.mirror(C.S, sx), C.mirror(C.ua, sx)
            bisect(bm, [f for f in bm.faces if f.calc_center_median().x * sx > .08], S - ua * .012, ua, clear=True)
    keep_largest(bm)
    # sleeves in ripstop, the body in knit
    for f in bm.faces:
        f.material_index = 1 if names[f[reg]] in ("upperarm", "forearm") and m else 0
    bm.normal_update()
    return bm


def seams(bm, C):
    from coat import bisect, press, edge_chains
    out = []
    zc = lambda f: f.calc_center_median()
    for sx in (1, -1):
        S, ua = C.mirror(C.S, sx), C.mirror(C.ua, sx)
        if C.m:
            # raglan seams: from the collar's base down to the underarm, front and back
            A_ = Vector((.058 * sx, 0, C.nb - .004))
            B_ = Vector((S.x * .95, 0, S.z - .115))
            for front in (True, False):
                out_dir = Vector((0, -1 if front else 1, 0))
                n = (B_ - A_).cross(out_dir).normalized()
                P0 = A_ + Vector((0, -.05 if front else .05, 0))
                C.raglan.append((sx, front, P0, n, (S - P0).dot(n) > 0))
                e = bisect(bm, [f for f in bm.faces if (zc(f).y < C.yc) == front and C.nb + .01 > zc(f).z > S.z - .14
                                and .03 < zc(f).x * sx < S.x * sx + .05], A_ + Vector((0, -.05 if front else .05, 0)), n)
                out.append(("raglan", e))
            down = Vector((0, 0, -1)) - ua * Vector((0, 0, -1)).dot(ua)
            n = ua.cross(down).normalized()
            e = bisect(bm, [f for f in bm.faces if C.arm(zc(f)) == sx and (zc(f) - S).dot(ua) > .06
                            and (zc(f) - S - ua * (zc(f) - S).dot(ua)).dot(down) > 0], S, n)
            out.append(("sleeve", e))
            # the ribbed cuff's seam
            W, fa = C.mirror(C.W, sx), C.mirror(C.fa, sx)
            e = bisect(bm, [f for f in bm.faces if C.arm(zc(f)) == sx and (zc(f) - W).dot(fa) > -.10], W - fa * .060, fa)
            out.append(("cuff", e))
        else:
            e = bisect(bm, [f for f in bm.faces if zc(f).y < -.02 and .03 < zc(f).x * sx < .14 and zc(f).z < C.nb - .03],
                       (.075 * sx, 0, 0), (1, 0, 0))
            out.append(("princess", e))
        e = bisect(bm, [f for f in bm.faces if .08 < zc(f).x * sx < .26 and zc(f).z < S.z - .10 and C.arm(zc(f)) == 0],
                   (0, C.yc + .015, 0), (0, 1, 0))
        out.append(("side", e))
    # the collar's seam round the neck's base, and the ribbed hem band's
    e = bisect(bm, [f for f in bm.faces if abs(zc(f).z - C.nb - .006) < .03 and abs(zc(f).x) < .12], (0, 0, C.nb + .006),
               (0, -.2, 1))
    out.append(("collar", e))
    if not C.m:
        e = bisect(bm, [f for f in bm.faces if abs(zc(f).z - C.hem - .035) < .03], (0, 0, C.hem + .035), (0, 0, 1))
        out.append(("band", e))
    res = []
    for kind, edges in out:
        edges = [g for g in edges if g.is_valid]
        for ch in edge_chains(edges):
            res.append((kind, ch))
    press(bm, [ch for _, ch in res], depth=.0007, width=.0022)
    bm.normal_update()
    return [(k, [(p - n * .0007, n) for p, n in ch]) for k, ch in res]


def build(info, log=print):
    from wardrobe import to_object, material
    from coat import thick, inset_strip
    from coat_details import Surface
    import fabric
    C = Cut(info)
    bm = shell(info, C)
    seam_chains = seams(bm, C)
    edges = garment.boundary_chains(bm)
    o = to_object(bm, "top", KNIT)
    o.data.materials.append(material(RIP))
    o.data.materials.append(material(KNIT))                 # (the inside)
    # (to_object reset the indices: the sleeves' ripstop again from where they are)
    for p in o.data.polygons:
        p.material_index = 1 if C.m and C.sleeve(p.center) else 0
    thick(o, .0018)
    fabric.world_uvs(o, fabric.TILE["knit"])
    parts = [o]
    for kind, ch in seam_chains:
        # flatlock seams on the knit: a wide double row
        for off in (-.0028, .0028):
            st = garment.trim_strip(ch, .0013, STITCH, offset=off, lift=.0004, tile=.012, step=.003, name="stitch")
            if st:
                parts.append(st)
    for ch in edges:
        st = inset_strip(o, ch, .006, STITCH)
        if st:
            parts.append(st)
    surf = Surface(o)
    if C.m:
        parts += quarter_zip(surf, C)
    log(f"shirt: shell {len(o.data.polygons)} faces, {len(seam_chains)} seams")
    return parts


def quarter_zip(surf, C):
    """a zip down the front from the collar's top: tape, teeth, a pull"""
    from coat_details import zip_line
    pts = []
    for k in range(24):
        z = C.collar_top - .026 - .170 * k / 23               # (the collar is cut lower at the front)
        q, n = surf.toward(Vector((0, -.30, z)), Vector((0, 1, 0)))
        if q is not None and q.y < -.03:                   # (the shirt's front only, never through to the back)
            pts.append((q, n))
    return zip_line(pts, pull_at=1) if len(pts) > 4 else []
