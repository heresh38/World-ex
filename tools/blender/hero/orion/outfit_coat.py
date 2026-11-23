"""The long coat of the owner's Orion sheet (orion_tpose_outfit.png, image-1794017268247.png), built fresh on the Orion
male over his undersuit and measured against the sheet: every height of it stands where the sheet's outline does.

  bodice   the shoulders, the chest's sides, the back and the sleeves, grown from the suited body's own surface and
           carried out, section by section, to the sheet's own width (front view) and back (side view); the front hangs
           open over the armoured vest from the collar down, the sleeves end at the wrist over the gloves' bracers
  skirt    from the waist edge to the ragged hem, every column carried down the sheet's flare (front view: half a
           metre wider than the hips at the knee; side view: its back hangs 19 cm behind at the knee), the front
           panels swinging out to the legs' sides, the centre back split by a vent, the hem torn into tails
  hood     the hood down, gathered round the back and the sides of the neck over the gaiter, into the lapels
  facings  the light grey front edges: the lapels turned back over the chest, a band down both skirt edges

Lengths in metres, the body's frame (Z up, -Y forward, +X the body's left).
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils import noise as mnoise
from mathutils.bvhtree import BVHTree

REGIONS = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
R = {n: i for i, n in enumerate(REGIONS)}


# ------------------------------------------------------------------------------------------------ the sheet's outline

class Envelope:
    """the sheet's figure per height (outfit.extents(): every 2 mm): the trunk's half width in front (the run that
    holds the middle, arms cut away), its back and front in the side view (y: + behind, - in front)"""

    def __init__(self, E):
        self.z, self.hw, self.yb, self.yf = [], [], [], []
        for zs, spans in E["front"].items():
            z = float(zs)
            mid = [s for s in spans if s[0] <= 0.0 <= s[1]]
            side = E["side"].get(zs)
            if not mid or not side:
                continue
            self.z.append(z)
            self.hw.append(max(-mid[0][0], mid[0][1]))
            self.yb.append(-min(a for a, b in side))          # (the side view's image right is the front: h = -y)
            self.yf.append(-max(b for a, b in side))
        o = np.argsort(self.z)
        self.z = np.array(self.z)[o]
        self.hw, self.yb, self.yf = (np.array(a)[o] for a in (self.hw, self.yb, self.yf))

    def at(self, z, what):
        return float(np.interp(z, self.z, getattr(self, what)))


# ------------------------------------------------------------------------------------------------ helpers

def neck_ring(cy, rx, ry, n=48):
    """a ring round the neck as a polygon of vertical planes tangent to an ellipse (centre y cy, half widths rx
    across, ry front to back): [(point, outward normal)], from the front round the body's left"""
    out = []
    for k in range(n):
        t = 2 * math.pi * (k + .5) / n
        p = Vector((rx * math.sin(t), cy - ry * math.cos(t), 0))
        out.append((p, Vector((math.sin(t) / rx, -math.cos(t) / ry, 0)).normalized()))
    return out


def inside_ring(poly, c, z0, slack=0.0):
    return c.z > z0 and all((c - p).dot(n) < slack for p, n in poly)


def cut_ring(bm, poly, z0, cy, rx, ry):
    """cut along every plane of the ring near it, drop what lies inside, then what that left loose; returns the
    ring's own open vertices"""
    from coat import bisect, faces_where, keep_largest
    near = lambda f: (lambda c: c.z > z0 - .015 and (c.x / rx) ** 2 + ((c.y - cy) / ry) ** 2 < 2.6)(f.calc_center_median())
    for p, n in poly:
        bisect(bm, faces_where(bm, near), p, n)
    drop = [f for f in bm.faces if inside_ring(poly, f.calc_center_median(), z0)]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    keep_largest(bm)
    return [v for v in bm.verts if v.is_boundary and inside_ring(poly, v.co, z0 - .005, slack=.002)]


def bm_of(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    return bm


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def section(base_bm, z, regions=("chest", "midriff", "pelvis"), band=.008):
    """the suited body's trunk at a height: half width, back and front (y), the middle's y"""
    idx = {R[r] for r in regions}
    pts = [v.co for v in base_bm.verts if abs(v.co.z - z) < band and any(f.material_index in idx for f in v.link_faces)]
    if not pts:
        return None
    xs = [abs(p.x) for p in pts]
    ys = [p.y for p in pts]
    return max(xs), max(ys), min(ys)


# ------------------------------------------------------------------------------------------------ the bodice

def bodice(base, env, T, log=print):
    """shoulders, chest sides, back and sleeves: the suited body's own faces carried out to the sheet's outline"""
    from coat import keep_largest, bisect, faces_where, strip_shape_layers
    bm = bm_of(base)
    strip_shape_layers(bm)
    zw = T["coat_waist"]
    keep = {R[r] for r in ("neck", "chest", "midriff", "pelvis", "upperarm", "forearm")}
    drop = [f for f in bm.faces if f.material_index not in keep or f.calc_center_median().z < zw - .03]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    keep_largest(bm)
    bm.normal_update()
    # the suited body's trunk, section by section (for the scale to the sheet's outline)
    src = bm_of(base)
    secs = {}
    for k in range(int((zw - .05) * 100), int(1.62 * 100)):
        z = k / 100.0
        s = section(src, z)
        if s:
            secs[k] = s
    src.free()

    def body_at(z):
        ks = sorted(secs)
        k = min(ks, key=lambda q: abs(q / 100.0 - z))
        return secs[k]

    S = Vector(T["shoulder_joint"])
    arm_x = S.x + .02                                      # (the sleeves' cuffs are cut past this)
    armpit = S.z - .16                                     # below this the sheet's trunk run is the trunk alone
    sleeve = T["sleeve"]                                   # [(x, ease)] along the arm (outfit.sleeve_ease)
    arms = {R["upperarm"], R["forearm"]}
    moved = []
    for v in bm.verts:
        p = v.co.copy()
        n = v.normal.copy()
        if any(f.material_index in arms for f in v.link_faces):
            e = float(np.interp(abs(p.x), [a for a, b in sleeve], [b for a, b in sleeve]))
            moved.append(p + n * e)
            continue
        if p.z > armpit + .08:                             # the shoulders, the upper chest and back: a cloth's ease
            moved.append(p + n * (.011 + .004 * max(0.0, n.y)))
            continue
        hw_b, yb_b, yf_b = body_at(min(p.z, armpit))
        yc = (yb_b + yf_b) / 2
        # the coat's own outline at this height: the sheet's, but cinched under the belt (the belt and its pouches
        # stand on it there: the coat is a finger off the suit) and never inside the suit
        belt = smoothstep(.96, 1.00, p.z) * (1 - smoothstep(1.13, 1.17, p.z))
        ze = min(p.z, armpit)
        hw = max(hw_b + .012, (1 - belt) * (env.at(ze, "hw") - .003) + belt * (hw_b + .014))
        yb = max(yb_b + .012, (1 - belt) * (env.at(ze, "yb") - .003) + belt * (yb_b + .016))
        yf = yf_b - .022                                   # (the front panels lie over the vest)
        sx = hw / max(hw_b, 1e-3)
        sb = (yb - yc) / max(yb_b - yc, 1e-3)
        sf = (yc - yf) / max(yc - yf_b, 1e-3)
        d = Vector((p.x, p.y - yc, 0))
        ang = math.atan2(d.x, -d.y)                        # 0 the front, pi the back
        c, s_ = math.cos(ang), math.sin(ang)
        s = min(1.35, sx * s_ * s_ + (sf if c > 0 else sb) * c * c)
        q = Vector((p.x * s, yc + (p.y - yc) * s, p.z))
        q = p + n * max(.011, (q - p).dot(n))              # (outward only, and a cloth's ease at the least)
        if p.z > armpit:                                    # (into the shoulders' ease over 8 cm)
            k = (p.z - armpit) / .08
            q = q.lerp(p + n * (.011 + .004 * max(0.0, n.y)), k)
        moved.append(q)
    for v, q in zip(bm.verts, moved):
        v.co = q
    bm.normal_update()
    # a coat hangs over the body, it does not cling to it: the anatomy carried out with the shell (the abs, the
    # pectorals' edges, the arm's muscles) smoothed away, the shell then held a cloth's ease outside the suit
    from outfit_mat import taubin, hold_out
    taubin(bm, iters=40)
    hold_out(bm, base, .009)
    # the waist edge: a clean cut (the skirt carries on from it)
    bisect(bm, faces_where(bm, lambda f: not any(f.material_index == R[r] for r in ("upperarm", "forearm"))),
           (0, 0, zw), (0, 0, -1), clear=True)
    # the sleeves end at the wrist, over the bracer
    for sx in (1, -1):
        bisect(bm, faces_where(bm, lambda f, sx=sx: f.calc_center_median().x * sx > arm_x), (sx * T["cuff_x"], 0, 0), (sx, 0, 0), clear=True)
    keep_largest(bm)
    bm.normal_update()
    return bm


# ------------------------------------------------------------------------------------------------ the neckline, the front

def open_front(bm, T, log=print):
    """the collar's ring round the gaiter and the open front down to the waist edge"""
    from coat import bisect, faces_where, keep_largest
    cy, rx, ry = T["collar_y"], T["collar_rx"] + .030, T["collar_ry"] + .032
    ring = cut_ring(bm, neck_ring(cy, rx, ry), T["neck_base_z"] - .045, cy, rx, ry)
    front = [v.co.z for v in ring if v.co.y < cy and abs(v.co.x) < .05]
    top = min(front) if front else T["neck_base_z"]
    # the open front: from either side of the ring's front down to the waist edge, a little wider below the chest
    zw = T["coat_waist"]
    for sx in (1, -1):
        p0 = Vector((sx * .055, 0, top + .01))
        p1 = Vector((sx * .085, 0, zw))
        t = (p1 - p0).normalized()
        n = t.cross(Vector((0, 1, 0))).normalized()
        if n.x * sx > 0:
            n = -n
        bisect(bm, faces_where(bm, lambda f, sx=sx: f.calc_center_median().y < T["collar_y"] - .02
                               and -.01 <= f.calc_center_median().x * sx < .17 and abs(f.calc_center_median().x) < .2
                               and f.calc_center_median().z < top + .06), p0, n, clear=True)
    keep_largest(bm)
    log(f"coat: neckline from {top:.3f} at the front, open front {len(ring)} ring vertices")
    return top


# ------------------------------------------------------------------------------------------------ the skirt

def skirt(bm, env, T, log=print):
    """from the waist edge down: the sheet's flare, the front panels swinging out, the vent, the torn hem"""
    from coat import ordered_boundary, orient_out
    zw = T["coat_waist"]
    chain = ordered_boundary(bm, lambda c: abs(c.z - zw) < .004 and abs(c.x) < .34)
    if chain[0].co.x < chain[-1].co.x:
        chain.reverse()
    log(f"coat: waist edge {len(chain)} vertices, {tuple(round(x, 3) for x in chain[0].co)} .. {tuple(round(x, 3) for x in chain[-1].co)}")
    yc = (env.at(zw, "yb") + env.at(zw, "yf")) / 2
    # the columns, unwrapped from the left front edge (+, the body's left) round the back (pi) to the right front edge:
    # each keeps its share of the way round as the edges swing out
    unw = [(lambda a: a if a > 0 else a + 2 * math.pi)(math.atan2(v.co.x, -(v.co.y - yc))) for v in chain]
    u = [(a - unw[0]) / (unw[-1] - unw[0]) for a in unw]
    e0 = chain[0].co
    n_rows = 44
    hem_b = T["hem_back"]
    seed = Vector((2.3, 1.7, .4))
    rows = [chain]
    vent_col = min(range(len(chain)), key=lambda k: abs(u[k] - .5))
    vent_rows = {}
    edges = ([], [])                                        # (the front edges' vertices, for the facings)
    for i in range(1, n_rows + 1):
        t = i / n_rows
        row = []
        # the front edges swing out from the waist to the thighs' outer front (the sheet: the trousers show across
        # the whole front between them), quickly at first
        s_e = 1 - (1 - t) ** 2.2
        xe = e0.x + (T["skirt_edge_x"] - e0.x) * s_e
        ye = e0.y + (T["skirt_edge_y"] - e0.y) * s_e
        ae = math.atan2(xe, -(ye - yc))
        for k in range(len(chain)):
            aw = ae + u[k] * (2 * math.pi - 2 * ae)
            a = aw if aw <= math.pi else aw - 2 * math.pi
            # the hem: the back's line, the front panels' corners hanging into tails at the sides, torn
            side = abs(math.sin(a))
            frontness = max(0.0, math.cos(a))
            hem = hem_b - .055 * side * side - .035 * frontness
            hem += .022 * mnoise.noise(Vector((a * 3.1, .7, .2)) + seed) + .012 * mnoise.noise(Vector((a * 9.0, 2.0, .9)) + seed)
            z = zw + (hem - zw) * t
            # the outline at this height: the sheet's half width (sides) and back (side view); the front panels over
            # the thighs' front, swinging out toward the legs' sides
            hw = env.at(z, "hw") - .004
            yb = env.at(z, "yb") - .004
            c = math.cos(a)
            s_ = math.sin(a)
            ex = 2.4                                        # (a superellipse: the skirt's squarer section)
            if c < 0:
                ry = yb - yc
            else:                                           # the front: through the front edge's own point
                re = math.hypot(xe, ye - yc)
                rest_ = 1 / re ** ex - (abs(math.sin(ae)) / hw) ** ex
                ry = abs(math.cos(ae)) / rest_ ** (1 / ex) if rest_ > 1e-9 else re
            r = 1.0 / ((abs(s_) / hw) ** ex + (abs(c) / ry) ** ex) ** (1 / ex)
            a2 = a
            p = Vector((math.sin(a2) * r, yc - math.cos(a2) * r, z))
            # drape: soft vertical folds, deeper toward the hem; the waist row stays where the bodice ends
            amp = (.002 + .016 * t * t)
            fold = amp * (math.sin(a * 13 + 1.7 * mnoise.noise(Vector((a * 1.3, t, .5)) + seed)) * .7
                          + .5 * mnoise.noise(Vector((a * 4.0, t * 2.0, 3.0)) + seed))
            p += Vector((math.sin(a2), -math.cos(a2), 0)) * fold
            if i == 1:
                p = p.lerp(chain[k].co + Vector((0, 0, (hem - zw) / n_rows)), .5)
            row.append(bm.verts.new(p))
        rows.append(row)
        edges[0].append(row[0])
        edges[1].append(row[-1])
        if z < T["vent_top"]:
            v = row[vent_col]
            vent_rows[i] = bm.verts.new(v.co + Vector((.006, .003, 0)))
    for i in range(n_rows):
        A_, B_ = rows[i], rows[i + 1]
        for k in range(len(chain) - 1):
            a0, a1, b0, b1 = A_[k], A_[k + 1], B_[k], B_[k + 1]
            if k + 1 == vent_col and (i + 1) in vent_rows:
                b1 = vent_rows[i + 1]
                if i in vent_rows:
                    a1 = vent_rows[i]
            bm.faces.new((a0, b0, b1, a1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    orient_out(bm)
    return [v.co.copy() for v in edges[0]] + [v.co.copy() for v in edges[1]]


# ------------------------------------------------------------------------------------------------ the collar

def collar(bm, T, log=print):
    """the hood's collar: raised from the neckline ring, leaning out as it rises, tallest behind the head (the
    hood's gathered mass), its two front ends turning into the lapels"""
    from coat import ordered_boundary
    cy, rx, ry = T["collar_y"], T["collar_rx"] + .030, T["collar_ry"] + .032
    poly = neck_ring(cy, rx, ry)
    chain = ordered_boundary(bm, lambda c: c.z > T["neck_base_z"] - .06 and inside_ring(poly, c, T["neck_base_z"] - .06, slack=.003))
    if chain[0].co.x < chain[-1].co.x:
        chain.reverse()
    n_rows = 10
    rows = [chain]
    for j in range(1, n_rows + 1):
        s = j / n_rows
        row = []
        for v in chain:
            d = Vector((v.co.x, v.co.y - cy, 0))
            a = math.atan2(d.x, -d.y)
            back = max(0.0, -math.cos(a))
            out = Vector((math.sin(a) / rx, -math.cos(a) / ry, 0)).normalized()
            top = T["collar_top"] + T["collar_back"] * back ** 1.3
            lean = .022 * s ** 1.6 + .030 * back * s ** 2.2 + .012 * back * math.sin(math.pi * s)
            row.append(bm.verts.new(v.co + Vector((0, 0, (top - v.co.z) * s)) + out * lean))
        rows.append(row)
    for row in rows[1:]:                                    # (each row smoothed along its length)
        for _ in range(6):
            P_ = [v.co.copy() for v in row]
            for k in range(1, len(row) - 1):
                row[k].co = (P_[k - 1] + 2 * P_[k] + P_[k + 1]) / 4
    for i in range(n_rows):
        for k in range(len(chain) - 1):
            bm.faces.new((rows[i][k], rows[i][k + 1], rows[i + 1][k + 1], rows[i + 1][k]))
    log(f"coat: collar on {len(chain)} neckline vertices")
    return rows


def facings(o, front_pts, T, collar_idx):
    """the light grey front edges: the lapels turned back wide over the chest, a band down both skirt edges, the
    whole collar's outside"""
    from mathutils.kdtree import KDTree
    me = o.data
    # the bodice's open front edges, from the collar's front ends down to the waist
    bm = bmesh.new()
    bm.from_mesh(me)
    pts = list(front_pts)
    for e in bm.edges:
        if e.is_boundary:
            c = (e.verts[0].co + e.verts[1].co) / 2
            if c.y < T["collar_y"] - .04 and T["coat_waist"] - .01 < c.z < T["neck_base_z"] + .02 and abs(c.x) < .16:
                pts.append(c.copy())
    bm.free()
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    for f in me.polygons:
        c = Vector(f.center)
        if sum(1 for i in f.vertices if i in collar_idx) >= 2:
            f.material_index = 1
            continue
        _, _, d = kd.find(c)
        w = .045 + .030 * max(0.0, min(1.0, (c.z - 1.18) / .12))    # (the lapel's width over the chest)
        if d < w:
            f.material_index = 1


# ------------------------------------------------------------------------------------------------ the hood

def hood(T, log=print):
    """the hood down: a gathered roll round the back and the sides of the neck, standing a little off the gaiter,
    tallest behind the head, its two ends running into the lapels at the front"""
    cy = T["collar_y"]
    rx, ry = T["collar_rx"] + .045, T["collar_ry"] + .040
    nb = T["neck_base_z"]
    bm = bmesh.new()
    n_u, n_v = 56, 14
    rings = []
    seed = Vector((.3, 4.1, 1.2))
    for i in range(n_u + 1):
        u = i / n_u
        a = math.radians(-128 + 256 * u)                    # from the front left round the back to the front right
        back = max(0.0, -math.cos(a))                       # 1 at the back
        centre = Vector((rx * math.sin(a), cy - ry * math.cos(a), nb + .030 + .018 * back))
        out = Vector((math.sin(a) / rx, -math.cos(a) / ry, 0)).normalized()
        up = Vector((0, 0, 1))
        h = .050 + .042 * back                              # how tall the roll stands
        w = .036 + .014 * back                              # how far out it bulges
        ring = []
        for j in range(n_v):
            v = 2 * math.pi * j / n_v
            gather = .004 * mnoise.noise(Vector((a * 5.0, v, .7)) + seed) + .003 * math.sin(a * 17 + v)
            p = centre + out * (w * (.5 - .5 * math.cos(v)) + gather) + up * (h * (.5 + .5 * math.sin(v)))
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for i in range(n_u):
        for j in range(n_v):
            a0, a1 = rings[i][j], rings[i][(j + 1) % n_v]
            b0, b1 = rings[i + 1][j], rings[i + 1][(j + 1) % n_v]
            bm.faces.new((a0, a1, b1, b0))
    for ring in (rings[0], rings[-1]):                       # (its two ends closed)
        bm.faces.new(ring if ring is rings[-1] else list(reversed(ring)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# ------------------------------------------------------------------------------------------------ build

def build(base, T, E, log=print):
    from outfit_mat import to_object, material
    env = Envelope(E)
    bm = bodice(base, env, T, log=log)
    top = open_front(bm, T, log=log)
    front_pts = skirt(bm, env, T, log=log)
    collar_rows = collar(bm, T, log=log)
    # fine wrinkles over everything (cloth is never perfectly smooth)
    seed = Vector((5.3, 1.1, 2.7))
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * (.0008 * mnoise.noise(v.co * 30 + seed) + .0004 * mnoise.noise(v.co * 85 + seed))
    bm.normal_update()
    from outfit_mat import face_out
    log(f"coat: {face_out(bm, base)} faces turned to face out")
    bm.verts.index_update()
    collar_idx = {v.index for row in collar_rows[1:] for v in row}
    o = to_object(bm, "C_outer__orion", "orion_coat")
    for m in ("orion_coat_light", "orion_lining", "orion_lining"):
        o.data.materials.append(material(m))
    facings(o, front_pts, T, collar_idx)
    sol = o.modifiers.new("thick", 'SOLIDIFY')
    sol.thickness = .005
    sol.offset = -1.0
    sol.use_rim = True
    sol.material_offset = 2                                 # (the inside faces: the blue lining)
    log(f"coat: {len(o.data.polygons)} faces")
    return [o]
