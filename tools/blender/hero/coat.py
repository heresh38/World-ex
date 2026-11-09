"""The Orion field coat (the male outer piece, from the concept sheet): a long, open-front coat with a stand collar,
built the way it would be cut and sewn rather than as a body shell pushed out.

  shell      the yoke, body and set-in sleeves grown from the body's own surface (so the shoulders, armholes and
             underarms fit), pushed out by the ease each area needs, then draped (it spans the hollows) and cut along
             straight lines: the neckline, the cuffs, the waist and the open front
  skirt      continues from the waist edge to below the knee: every column carried down the hips' outer envelope
             (never tucking between the legs), flaring toward the hem, with drape folds that grow toward the hem and a
             centre-back vent whose flaps overlap
  collar     a tall stand collar raised from the neckline, leaning out a little, its top edge rolled
  seams      shoulder, armhole, side, front and back princess, centre back, waist and underarm sleeve seams: each a
             pressed groove with a row of stitching either side; the hem, cuffs, front edges and collar topstitched
  cloth      real thickness with a rounded edge (solidify + bevel) and the blue lining on the inside faces

The details (zip, pockets, flaps, patches, straps, hood, hardware) are added by coat_details.py; textures by
fabric.py. All lengths in metres, the body's frame (Z up, -Y forward, +X the body's left).
"""
import math
import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils import noise as mnoise
from mathutils.bvhtree import BVHTree

TORSO = ("chest", "midriff", "pelvis", "neck", "thigh")
ARM = ("upperarm", "forearm")
LEGS = ("pelvis", "thigh", "shin")


class Pattern:
    """the coat's measurements, from the body's targets and skeleton"""

    def __init__(self, info):
        T, A, L = info.T, info.A, info.L
        self.T, self.info = T, info
        self.nb = T["neck_base_z"]
        # his: a long coat (the skirt from the hip bones to mid-calf); hers: a jacket cropped above the waist
        self.crop = not info.m
        self.cloth = "orion_white" if self.crop else "orion_coat"
        self.zw = T["underbust"]["z"] - .025 if self.crop else T["hips"]["z"] + .030
        self.hem = self.zw if self.crop else L["K"].z - .150
        self.vent = self.zw if self.crop else T["hips"]["z"] - .200   # the centre-back vent's top
        self.S, self.E, self.W = A["S"], A["E"], A["W"]
        self.ua = (self.E - self.S).normalized()
        self.fa = (self.W - self.E).normalized()
        self.yc = .012                                     # the torso's centre line (front -y, back +y)
        # the open front: half the gap between the front edges, at the neckline and at the waist
        self.gap_top, self.gap_w = (.040, .085) if not self.crop else (.034, .060)
        self.collar_h = .082 if not self.crop else .068
        self.cuff = .040 if not self.crop else .068        # the sleeve's end, up from the wrist (clear of the hand)

    def arm(self, c):
        """+1 / -1 for a point on the left / right sleeve side, 0 on the torso"""
        # (below a long coat's waist everything is skirt; a cropped jacket's sleeves reach below its hem)
        return 0 if abs(c.x) < .23 or (not self.crop and c.z < self.zw - .05) else (1 if c.x > 0 else -1)

    def mirror(self, v, sx):
        return Vector((v.x * sx, v.y, v.z))


# ------------------------------------------------------------------------------------------------ helpers

def faces_where(bm, test):
    return [f for f in bm.faces if test(f)]


def bisect(bm, faces, co, no, clear=False):
    """cuts the given faces along a plane; clear: removes what lies on the +no side. Returns the new edges."""
    geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + list(faces)
    r = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(co), plane_no=Vector(no).normalized(), clear_outer=clear)
    if clear:
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    return [g for g in r["geom_cut"] if isinstance(g, bmesh.types.BMEdge) and g.is_valid]


def keep_largest(bm):
    """drops the fragments the cuts leave behind (keeps the biggest connected piece)"""
    seen, parts = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, part = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            part.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        parts.append(part)
    parts.sort(key=len, reverse=True)
    drop = [f for p in parts[1:] for f in p]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')


def ordered_boundary(bm, test):
    """the open edges whose midpoints pass test, as one ordered vertex chain (the longest)"""
    edges = [e for e in bm.edges if e.is_boundary and test((e.verts[0].co + e.verts[1].co) / 2)]
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    best = []
    seen = set()
    for s in [v for v, n in adj.items() if len(n) == 1] + list(adj):
        if s in seen:
            continue
        chain, cur, prev = [s], s, None
        seen.add(s)
        while True:
            nxt = [w for w in adj[cur] if w is not prev and w not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            chain.append(cur)
        if len(chain) > len(best):
            best = chain
    return best


def part_bvh(info, regions):
    """a BVH of only the body's faces in these regions (rays that must not hit the arms, ...)"""
    bm = info.bm.copy()
    bm.faces.ensure_lookup_table()
    drop = [f for f, r in zip(bm.faces, info.face_region) if r not in regions]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def orient_out(bm, axis_y=.012):
    """faces of an open garment pointing out of the body (recalc_face_normals guesses on open meshes): flips the
    whole mesh if most faces point toward the body's vertical axis"""
    bm.normal_update()
    score = 0.0
    for f in bm.faces:
        c = f.calc_center_median()
        radial = Vector((c.x, c.y - axis_y, 0))
        if radial.length > 1e-6:
            score += f.normal.dot(radial.normalized()) * f.calc_area()
    if score < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()


def strip_shape_layers(bm):
    for lay in list(bm.verts.layers.shape.values()):
        bm.verts.layers.shape.remove(lay)


# ------------------------------------------------------------------------------------------------ the shell

def shell(info, P):
    """the coat above the waist: yoke, body and sleeves, from the body's own surface"""
    bm = info.bm.copy()
    strip_shape_layers(bm)
    bm.faces.ensure_lookup_table()
    reg = bm.faces.layers.int.new("reg")
    names = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
    for f, r in zip(bm.faces, info.face_region):
        f[reg] = names.index(r)
    keep = set(TORSO + ARM)
    keep = keep | {"thigh"}
    drop = [f for f in bm.faces if names[f[reg]] not in keep or (f.calc_center_median().z < P.zw - .08
                                                                and names[f[reg]] in TORSO + ("thigh",))]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    region = lambda f: names[f[reg]]
    keep_largest(bm)
    bm.normal_update()
    # ease over the body (what is under it: the shirt, and at the waist the belt and its pouches), then drape;
    # the cuts come after, so every edge is a straight line on the finished surface
    ease = {"chest": .020, "midriff": .028, "pelvis": .032, "neck": .010, "upperarm": .014, "forearm": .016}
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        r = info.face_region[idx] if idx is not None else "chest"
        e = ease.get(r, .018)
        if r in ("midriff", "pelvis"):
            e += .010 * max(0.0, min(1.0, (P.zw + .12 - v.co.z) / .10))   # more room over the belt
        v.co = loc + nrm * e
    bm.normal_update()
    from wardrobe import drape_out
    drape_out(bm, info, 14, min_off=.008)
    cloth_folds(bm, info, P)
    # clean cuts: the waist, the cuffs, the neckline, the open front
    torso = lambda f: P.arm(f.calc_center_median()) == 0
    bisect(bm, faces_where(bm, torso), (0, 0, P.zw), (0, 0, -1), clear=True)
    for sx in (1, -1):
        W = P.mirror(P.W, sx)
        fa = P.mirror(P.fa, sx)
        bisect(bm, faces_where(bm, lambda f, sx=sx: P.arm(f.calc_center_median()) == sx), W - fa * P.cuff, fa, clear=True)
    bisect(bm, faces_where(bm, lambda f: f.calc_center_median().z > P.nb - .06 and abs(f.calc_center_median().x) < .17),
           (0, 0, P.nb + .004), (0, 0, 1), clear=True)
    z0, z1 = P.nb + .01, P.zw
    for sx in (1, -1):
        p0 = Vector((P.gap_top * sx, 0, z0))
        t = Vector(((P.gap_w - P.gap_top) * sx, 0, z1 - z0)).normalized()
        n = t.cross(Vector((0, 1, 0))).normalized()
        if n.x * sx > 0:                                   # (+n must point toward the middle: that side goes)
            n = -n
        bisect(bm, faces_where(bm, lambda f, sx=sx: f.calc_center_median().y < -.02
                               and -.01 <= f.calc_center_median().x * sx < .17 and torso(f)), p0, n, clear=True)
    keep_largest(bm)
    bm.normal_update()
    return bm


def cloth_folds(bm, info, P):
    """how a coat this weight folds on the body in the A-pose: rings round the inside of the elbows and stacked at
    the cuffs, drag folds fanning from each armpit across the chest and back, and the cloth bunching a little in the
    small of the back above the waist seam"""
    from wardrobe import Folds
    F_ = Folds(info)
    bm.normal_update()
    moves = []
    for v in bm.verts:
        loc, nrm, idx, _ = info.bvh.find_nearest(v.co)
        r = info.face_region[idx] if idx is not None else "chest"
        c = v.co
        d = F_.sleeve(c, r, .0065, cuff=-.055)
        q = Vector((abs(c.x), c.y, c.z))
        # armpit drag: folds radiating from the armpit, across the side of the chest and the back
        ap = Vector((P.S.x * .78, P.S.y, P.S.z - .125))
        rel = q - ap
        dist = rel.length
        if dist < .22 and r in ("chest", "midriff", "upperarm"):
            ang = math.atan2(rel.z, rel.y)
            d += .0045 * math.sin(ang * 5 + 1.3 * mnoise.noise(q * 9)) * math.exp(-(dist / .09) ** 2) * min(1.0, dist / .03)
        # the small of the back: a few soft horizontal folds above the waist seam
        if c.y > .03 and P.zw < c.z < P.zw + .16 and P.arm(c) == 0:
            k = 1 - (c.z - P.zw) / .16
            d += .0028 * k * math.sin((c.z - P.zw) * 2 * math.pi / .034 + 2.0 * mnoise.noise(q * 6)) * min(1.0, abs(c.x) / .02 + .3)
        moves.append((v, v.normal.copy(), d))
    for v, n, d in moves:
        v.co += n * d
    bm.normal_update()


# ------------------------------------------------------------------------------------------------ the skirt

def skirt(bm, info, P):
    """from the waist edge down to the hem, in the same mesh (the waist seam is a row of the grid)"""
    chain = ordered_boundary(bm, lambda c: abs(c.z - P.zw) < .004 and abs(c.x) < .30)
    # left front (+x, front) first, round the back to the right front
    if chain[0].co.x < chain[-1].co.x:
        chain.reverse()
    print(f"[coat] waist edge: {len(chain)} vertices, from {tuple(round(x, 3) for x in chain[0].co)} to "
          f"{tuple(round(x, 3) for x in chain[-1].co)}")
    legs = part_bvh(info, LEGS + ("midriff",))
    n_rows = 34
    yc = P.yc
    ang = [math.atan2(v.co.x, -(v.co.y - yc)) % (2 * math.pi) for v in chain]   # 0 = front centre, + round the left
    r0 = [math.hypot(v.co.x, v.co.y - yc) for v in chain]
    for _ in range(6):                                     # the skirt's columns from a smoothed waist line
        r0 = [r0[0]] + [(r0[k - 1] + 2 * r0[k] + r0[k + 1]) / 4 for k in range(1, len(r0) - 1)] + [r0[-1]]
    jv = min(range(len(chain)), key=lambda k: abs(ang[k] - math.pi))           # the centre-back column (the vent)
    rows = [chain]
    rprev = list(r0)
    vent_rows = {}
    seed = Vector((3.1, .7, 1.9))
    for i in range(1, n_rows + 1):
        t = i / n_rows
        z = P.zw + (P.hem - P.zw) * (t ** .92)
        row = []
        for k, (a, r_) in enumerate(zip(ang, rprev)):
            d = Vector((math.sin(a), -math.cos(a), 0))
            c = Vector((0, yc, z))
            hit = legs.ray_cast(c + d * .60, -d, .70)[0]
            env = (hit - c).length if hit is not None else 0.0
            back = max(0.0, -math.cos(a))
            flare = 1 + (.05 + .04 * back) * t + (.08 + .10 * back) * t * t
            r = max(r_, env + .040) * (1 + .006)                       # never tucks in between the legs
            r = r * (flare / (1 + (.05 + .04 * back) * (t - 1 / n_rows) + (.08 + .10 * back) * (t - 1 / n_rows) ** 2))
            rprev[k] = r
            # drape: soft vertical folds, deeper and wider toward the hem, irregular
            ph = 1.6 * mnoise.noise(Vector((a * 1.4, 0, .3)) + seed)
            amp = (.003 + .028 * t * t) * (.6 + .4 * mnoise.noise(Vector((a * 2.3, 4.0, 1.0)) + seed))
            fold = amp * math.sin(a * 11 + ph) + (.004 + .020 * t * t) * back * math.sin(a * 5 + .6)
            # the front panels hang a little open toward the hem
            edge = min(k, len(chain) - 1 - k)
            swing = (.035 * t * t) * max(0.0, 1 - edge / 6) * (1 if k < len(chain) / 2 else -1)
            a2 = a + swing
            d2 = Vector((math.sin(a2), -math.cos(a2), 0))
            row.append(bm.verts.new(c + d2 * (r + fold)))
        rows.append(row)
        if z < P.vent:                                      # the vent: a second vertex for the overlapping flap
            v = row[jv]
            vent_rows[i] = bm.verts.new(v.co + Vector((-.008, .004, 0)))
    for i in range(n_rows):
        A_, B_ = rows[i], rows[i + 1]
        for k in range(len(chain) - 1):
            a0, a1, b0, b1 = A_[k], A_[k + 1], B_[k], B_[k + 1]
            # left of the vent column the faces take the flap's own copy
            if k + 1 == jv and (i + 1) in vent_rows:
                b1 = vent_rows[i + 1]
                if i in vent_rows:
                    a1 = vent_rows[i]
            bm.faces.new((a0, b0, b1, a1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    orient_out(bm)
    return chain


# ------------------------------------------------------------------------------------------------ the collar

def collar(bm, P):
    chain = ordered_boundary(bm, lambda c: abs(c.z - P.nb - .004) < .004 and abs(c.x) < .17)
    if chain[0].co.x < chain[-1].co.x:
        chain.reverse()
    n_rows = 5
    centre = Vector((0, P.yc + .01, 0))
    rows = [chain]
    for j in range(1, n_rows + 1):
        s = j / n_rows
        row = []
        for v in chain:
            out = Vector((v.co.x - centre.x, v.co.y - centre.y, 0))
            out = out.normalized() if out.length > 1e-6 else Vector((0, 1, 0))
            front = max(0.0, -out.y)                         # the collar is a touch lower at the front
            h = P.collar_h * (1 - .14 * front)
            lean = .010 * s * s + (.004 if j == n_rows else 0)  # leans out, the top edge rolled over
            row.append(bm.verts.new(v.co + Vector((0, 0, h * s)) + out * lean))
        rows.append(row)
    for row in rows[1:]:                                   # rows smoothed along their length (no facets)
        for _ in range(8):
            P_ = [v.co.copy() for v in row]
            for k in range(1, len(row) - 1):
                row[k].co = (P_[k - 1] + 2 * P_[k] + P_[k + 1]) / 4
    for i in range(n_rows):
        for k in range(len(chain) - 1):
            bm.faces.new((rows[i][k], rows[i][k + 1], rows[i + 1][k + 1], rows[i + 1][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    orient_out(bm)
    return chain, rows[-1]


# ------------------------------------------------------------------------------------------------ seams

def press(bm, chains_, depth=.0012, width=.0030):
    """the seams' grooves: every vertex near a seam line pressed in, deepest on the line and easing out over
    `width` (pressing only the cut's own vertices leaves pinched dimples)"""
    from mathutils import kdtree
    import garment
    pts = [p for ch in chains_ for p, n in garment.resample(ch, .0015)]
    if not pts:
        return
    kd = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    bm.normal_update()
    moves = []
    for v in bm.verts:
        _, _, d = kd.find(v.co)
        if d < width * 2.5:
            moves.append((v, v.normal.copy(), depth * math.exp(-(d / width) ** 2)))
    for v, n, k in moves:
        v.co -= n * k


def edge_chains(edges):
    from garment import chains
    return chains(edges)


def seams(bm, P):
    """the coat's sewn seams: pressed grooves, returned as chains [(co, normal)] for the stitching"""
    out = []
    zc = lambda f: f.calc_center_median()
    for sx in (1, -1):
        S = P.mirror(P.S, sx)
        ua = P.mirror(P.ua, sx)
        # shoulder seam: along the top of the shoulder, neck to shoulder point
        e = bisect(bm, faces_where(bm, lambda f: zc(f).z > S.z - .05 and .05 < zc(f).x * sx < S.x * sx * 1.05 + .02
                                   and zc(f).z < P.nb + .005), (0, P.yc + .006, 0), (0, 1, 0))
        out.append(("shoulder", e))
        # armhole: round the shoulder joint, a little down the arm
        e = bisect(bm, faces_where(bm, lambda f: (zc(f) - S).length < .17 and (zc(f) - S).dot(ua) > -.04
                                   and zc(f).x * sx > 0), S + ua * .045, ua)
        out.append(("armhole", e))
        # underarm sleeve seam: the plane through the arm axis and straight down, on the sleeve's underside
        down = Vector((0, 0, -1)) - ua * Vector((0, 0, -1)).dot(ua)
        n = ua.cross(down).normalized()
        e = bisect(bm, faces_where(bm, lambda f: P.arm(zc(f)) == sx and (zc(f) - S).dot(ua) > .06
                                   and (zc(f) - S - ua * (zc(f) - S).dot(ua)).dot(down) > 0), S, n)
        out.append(("sleeve", e))
        # side seam: where front meets back, armpit to hem
        e = bisect(bm, faces_where(bm, lambda f: .09 < zc(f).x * sx < .30 and zc(f).z < S.z - .10 and P.arm(zc(f)) == 0),
                   (0, P.yc + .02, 0), (0, 1, 0))
        out.append(("side", e))
        # front princess: shoulder-blade height to the waist; back princess: to the hem
        e = bisect(bm, faces_where(bm, lambda f: zc(f).y < -.03 and P.zw < zc(f).z < S.z - .07 and .04 < zc(f).x * sx < .16),
                   (.098 * sx, 0, 0), (1, 0, 0))
        out.append(("princess_f", e))
        e = bisect(bm, faces_where(bm, lambda f: zc(f).y > .04 and P.hem < zc(f).z < S.z - .03 and .04 < zc(f).x * sx < .16),
                   (.092 * sx, 0, 0), (1, 0, 0))
        out.append(("princess_b", e))
    # centre back: below the collar to the vent's top
    e = bisect(bm, faces_where(bm, lambda f: zc(f).y > .04 and P.vent < zc(f).z < P.nb - .01 and abs(zc(f).x) < .05),
               (0, 0, 0), (1, 0, 0))
    out.append(("back", e))
    # the waist seam (the skirt's first row)
    if not P.crop:
        e = bisect(bm, faces_where(bm, lambda f: abs(zc(f).z - P.zw) < .03 and P.arm(zc(f)) == 0), (0, 0, P.zw - .003),
                   (0, 0, 1))
        out.append(("waist", e))
    res = []
    for kind, edges in out:
        edges = [g for g in edges if g.is_valid]
        for ch in edge_chains(edges):
            res.append((kind, ch))
    press(bm, [ch for _, ch in res])
    bm.normal_update()
    res = [(k, [(p - n * .0012, n) for p, n in ch]) for k, ch in res]   # (the stitching follows the groove's floor)
    return res


# ------------------------------------------------------------------------------------------------ build

def build(info, log=print):
    from wardrobe import to_object, material
    import garment
    P = Pattern(info)
    bm = shell(info, P)
    if not P.crop:
        skirt(bm, info, P)
    collar(bm, P)
    # fine wrinkles over everything (cloth is never perfectly smooth)
    seed = Vector((5.3, 1.1, 2.7))
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * (.0009 * mnoise.noise(v.co * 32 + seed) + .0004 * mnoise.noise(v.co * 90 + seed))
    bm.normal_update()
    seam_chains = seams(bm, P)
    # open edges: the hem, the cuffs, the front edges and the collar's top (topstitched)
    edge_chains_ = garment.boundary_chains(bm)
    o = to_object(bm, "coat", P.cloth)
    o.data.materials.append(material("orion_lining"))
    thick(o, .0055)
    import fabric
    fabric.world_uvs(o, fabric.TILE["twill"])
    import coat_details
    parts = [o] + coat_details.build(o, P, log=log)
    stitch = "orion_stitch"
    for kind, ch in seam_chains:
        for off in (-.0034, .0034):
            s = garment.trim_strip(ch, .0016, stitch, offset=off, lift=.0006, tile=.012, step=.003, name="stitch")
            if s:
                parts.append(s)
    for ch in edge_chains_:
        for inset in (.007, .013):
            s = inset_strip(o, ch, inset, stitch)
            if s:
                parts.append(s)
    log(f"coat: shell {len(o.data.polygons)} faces, {len(seam_chains)} seams, {len(edge_chains_)} edges")
    return parts


def thick(o, t):
    """cloth thickness with a rounded edge; the inside faces get the lining (material slot 1)"""
    m = o.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = t
    m.offset = -1.0
    m.use_rim = True
    m.use_even_offset = False
    m.thickness_clamp = .5
    m.material_offset = 1
    b = o.modifiers.new("edge", 'BEVEL')
    b.width = t * .42
    b.segments = 2
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(55)
    bpy.context.view_layer.objects.active = o
    for md in (m, b):
        bpy.ops.object.modifier_apply(modifier=md.name)


def inset_strip(o, chain, inset, mat):
    """topstitching: a stitch row a set distance in from an open edge, along the surface"""
    import garment
    from mathutils.bvhtree import BVHTree as B
    bm = bmesh.new()
    bm.from_mesh(o.data)
    tree = B.FromBMesh(bm)
    bm.free()
    pts = garment.resample(chain, .003)
    out = []
    for i, (p, n) in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0])
        if t.length < 1e-9:
            continue
        t.normalize()
        side = n.cross(t).normalized()
        best = None
        for sgn in (1, -1):                                # the side of the edge where the cloth is
            q = p + side * sgn * inset
            loc, nrm, _, d = tree.find_nearest(q)
            if loc is not None and (best is None or d < best[2]):
                best = (loc, nrm, d)
        if best and best[2] < inset * .5:
            out.append((best[0], best[1]))
    if len(out) < 3:
        return None
    return garment.trim_strip(out, .0016, mat, lift=.0006, tile=.012, step=.003, name="stitch")
