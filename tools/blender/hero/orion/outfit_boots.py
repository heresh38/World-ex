"""The Orion outfit's combat boots, to the owner's sheet: black leather on a combat boot's last measured from the foot
(a heel counter, the instep rising to the ankle, a WIDE, LOW toe box: a boot's section is wide and flat, never round),
a padded shaft to a third of the way up the shin with a rolled collar, a tongue under laces crossing between steel
eyelets, a grey plate over the shaft's front and a grey strap round the ankle, a pull tab behind; on a thick lugged
sole that stands a little out past the upper, wraps up over the toe as a rubber cap, and is cut away under the arch
between the heel block and the forefoot. Distance fields meshed with Surface Nets (tools/blender/sdf.py): every surface
smooth and closed, no lumps.

The foot is hidden under the boot (the wardrobe hides the body's `foot` region), so the boot keeps a boot's shape
instead of following the toes: the first boots held the whole foot inside and came out as balls 16 cm wide and round.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import sdf

REGIONS = ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot")
Z0 = .030                     # the insole line: the sole's top, the upper's bottom
SOLE_TOP = .034               # the sole's top edge (it overlaps the upper by a few mm)


def foot_points(base, sx):
    """the suited body's foot (one side) as points, world space"""
    me = base.data
    mw = base.matrix_world
    foot = REGIONS.index("foot")
    vs = set()
    for f in me.polygons:
        if f.material_index == foot:
            vs.update(f.vertices)
    P = np.array([tuple(mw @ me.vertices[i].co) for i in vs])
    return P[P[:, 0] * sx > 0]


class Last:
    """one boot's upper as a distance field"""

    def __init__(self, P, ankle, top, sx):
        self.sx = sx
        y_heel, y_toe = float(P[:, 1].max()), float(P[:, 1].min())
        L = y_heel - y_toe
        # the ball: where the foot is widest, in its front half
        ys = np.linspace(y_toe + L * .15, y_toe + L * .5, 14)
        rows = [P[np.abs(P[:, 1] - y) < .006] for y in ys]
        widths = [np.ptp(r[:, 0]) if len(r) else 0.0 for r in rows]
        i = int(np.argmax(widths))
        self.w = w = float(widths[i])
        self.y_ball = y_ball = float(ys[i])
        x_ball = float((rows[i][:, 0].min() + rows[i][:, 0].max()) / 2)
        heel_rows = P[P[:, 1] > y_heel - .05]
        x_heel = float((heel_rows[:, 0].min() + heel_rows[:, 0].max()) / 2)
        self.hw = hw = w * .5 + .014                          # the upper's half width at the ball (13 cm across)
        self.y_heel, self.y_toe = y_heel, y_toe
        self.y_front = y_toe - .014                           # the toe's tip, 1.4 cm past the toes
        self.y_back = y_heel + .008                           # the heel counter's back
        self.x_ball, self.x_heel = x_ball, x_heel
        # (centre, half sizes): the heel counter, the instep rising to the ankle, the ball, the toe box
        self.parts = [
            ((x_heel, y_heel - .044, .074), (hw * .76, .052, .062)),
            (((x_heel + x_ball) / 2, (y_heel + y_ball) / 2 - .004, .072), (hw * .88, .070, .058)),
            ((x_ball, y_ball + .010, .057), (hw, .064, .034)),
            ((x_ball - sx * .004, self.y_front + .060, .053), (hw * .91, .060, .029)),
        ]
        self.a = np.array([ankle.x, ankle.y + .004, .100])
        self.t = np.array([ankle.x - sx * .003, ankle.y + .010, top])
        self.top = top
        self.r_shaft = .054

    def foot(self, P):
        d = None
        for c, r in self.parts:
            e = sdf.ellipsoid(P, c, r)
            d = e if d is None else sdf.smin(d, e, .040)
        return d

    def shaft(self, P):
        # a little deeper than wide (the leg is): the cone in a space drawn in along y
        Q = P.copy()
        Q[:, 1] = (P[:, 1] - self.a[1]) / 1.10 + self.a[1]
        return sdf.round_cone(Q, self.a, self.t, self.r_shaft + .002, self.r_shaft)

    def __call__(self, P):
        d = sdf.smin(self.foot(P), self.shaft(P), .034)
        # the tongue: a soft ridge down the shaft's front under the laces
        tongue = sdf.ellipsoid(P, (self.a[0], self.a[1] - self.r_shaft * 1.02, (Z0 + self.top) / 2 + .030), (.026, .012, .085))
        d = sdf.smin(d, tongue, .016)
        # the padded collar: a roll round the top
        tz = self.top - .012
        d = sdf.smin(d, sdf.torus(P * np.array([1, 1 / 1.10, 1], np.float32) + np.array([0, self.t[1] * (1 - 1 / 1.10), 0], np.float32),
                                  (self.t[0], self.t[1], tz), self.r_shaft - .002, .012), .010)
        # its bottom flat on the insole line
        return sdf.smax(d, Z0 - P[:, 2], .004)


class Sole:
    """the outsole: the upper's footprint flared out 1.3 cm, from the floor to its top edge, rounded; lugs cut across
    and along its tread, the arch cut away between the heel block and the forefoot"""

    def __init__(self, last):
        self.l = last

    def __call__(self, P):
        l = self.l
        Q = P.copy()
        Q[:, 2] = Z0 + .008                                    # the upper's footprint just above the insole line
        d = l.foot(Q) - .013
        d = sdf.smax(d, np.maximum(-P[:, 2], P[:, 2] - SOLE_TOP), .005)
        # the lugs: grooves across the tread every 2.2 cm and one along its middle, 9 mm deep
        u = np.mod(P[:, 1] - l.y_toe, .022) - .011
        across = np.maximum(np.abs(u) - .0024, P[:, 2] - .009)
        along = np.maximum(np.abs(P[:, 0] - l.x_ball) - .0022, P[:, 2] - .009)
        d = sdf.smax(d, -np.minimum(across, along), .0012)
        # the arch: cut away under the shank between the heel block and the forefoot
        mid = (l.y_heel - .074 + l.y_ball + .044) / 2
        half = max(.01, (l.y_heel - .074 - (l.y_ball + .044)) / 2)
        arch = np.maximum(np.abs(P[:, 1] - mid) - half, P[:, 2] - .010)
        return sdf.smax(d, -arch, .004)


def mesh_field(fn, lo, hi, h):
    V, Q = sdf.mesh(fn, np.array(lo), np.array(hi), h)
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(p)) for p in V]
    for q in Q:
        try:
            bm.faces.new([vs[i] for i in q])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


class BMSurface:
    """a bmesh's surface: the nearest point and its normal, a ray's hit (as outfit_parts.Surface)"""

    def __init__(self, bm):
        from mathutils.bvhtree import BVHTree
        bm.normal_update()
        self.bvh = BVHTree.FromBMesh(bm)

    def near(self, p):
        loc, nrm, _, _ = self.bvh.find_nearest(p)
        return loc, nrm

    def hit(self, origin, direction, far=1.0):
        loc, nrm, _, _ = self.bvh.ray_cast(origin, direction.normalized(), far)
        return (loc, nrm) if loc is not None else None


def eyelet(bm, at, n, r=.0042, h=.0022, seg=10):
    """a steel eyelet: a short ring standing off the leather"""
    from outfit_parts import frame
    c, ri, up, out = frame(at, n, Vector((0, 0, 1)) if abs(n.z) < .9 else Vector((0, 1, 0)))
    ring_o, ring_t = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        d = ri * math.cos(a) + up * math.sin(a)
        ring_o.append(bm.verts.new(c + d * r - out * .001))
        ring_t.append(bm.verts.new(c + d * r + out * h))
    inner = [bm.verts.new(c + (ri * math.cos(2 * math.pi * k / seg) + up * math.sin(2 * math.pi * k / seg)) * r * .45 + out * h * .7)
             for k in range(seg)]
    for k in range(seg):
        j = (k + 1) % seg
        bm.faces.new((ring_o[k], ring_o[j], ring_t[j], ring_t[k]))
        bm.faces.new((ring_t[k], ring_t[j], inner[j], inner[k]))
    bm.faces.new(list(reversed(inner)))


def build(base, T, log=print):
    from outfit_mat import to_object
    import outfit_parts as OP
    uppers, soles, plates, straps, laces, steel = (bmesh.new() for _ in range(6))
    A = Vector(T["ankle"])
    for sx in (1, -1):
        P = foot_points(base, sx)
        ank = Vector((A.x * sx, A.y, A.z))
        last = Last(P, ank, T["boot_top"], sx)
        lo = (min(P[:, 0].min(), ank.x - .08) - .03, last.y_front - .03, Z0 - .004)
        hi = (max(P[:, 0].max(), ank.x + .08) + .03, last.y_back + .04, T["boot_top"] + .012)
        up = mesh_field(last, lo, hi, .0035)
        sole = Sole(last)
        so = mesh_field(sole, (lo[0], lo[1], -.004), (hi[0], hi[1], SOLE_TOP + .006), .0024)
        surf = BMSurface(up)
        side = "left" if sx > 0 else "right"
        log(f"boots: {side} upper {2 * last.hw * 100:.1f} cm across the ball, toe box {100 * (last.parts[-1][0][2] + last.parts[-1][1][2]):.1f} cm high")

        # the laces: up the instep from behind the ball to the shaft's front, crossing between two rows of eyelets
        start = Vector((last.x_ball, last.y_ball + .046, .0))
        end = Vector((float(last.t[0]), float(last.a[1]) - last.r_shaft, .0))
        rows = []
        for k in range(7):
            t = k / 6
            p = start.lerp(end, t)
            z = .082 + (T["boot_top"] - .030 - .082) * t
            h = surf.hit(Vector((p.x, p.y - .25, z)), Vector((0, 1, 0)), .5)
            if not h:
                continue
            loc, nrm = h
            across = Vector((1, 0, 0)) - nrm * nrm.x
            across.normalize()
            half = .015 - .003 * t
            rows.append((surf.near(loc + across * half)[0], surf.near(loc - across * half)[0], nrm))
        for (l0, r0, n0), (l1, r1, n1) in zip(rows[:-1], rows[1:]):
            OP.band(laces, surf, [l0, r1], .0042, thick=.0018, lift=.0034, step=.004)
            OP.band(laces, surf, [r0, l1], .0042, thick=.0018, lift=.0040, step=.004)
        if rows:
            OP.band(laces, surf, [rows[0][0], rows[0][1]], .0042, thick=.0018, lift=.0030, step=.004)
        for l0, r0, n0 in rows:
            for p in (l0, r0):
                eyelet(steel, p, surf.near(p)[1])

        # the grey plate over the shaft's front, above the laces' top: angular, its top flared
        fz = T["boot_top"] - .038
        h = surf.hit(Vector((float(last.t[0]), float(last.t[1]) - .3, fz)), Vector((0, 1, 0)), .5)
        if h:
            fr = OP.frame(h[0] + h[1] * .004, h[1])
            OP.plate(plates, [(-.022, -.024), (.022, -.024), (.027, .012), (.018, .030), (-.018, .030), (-.027, .012)], fr,
                     thick=.005, ridge=.005, rings=2, wrap=.060, bevel=.0015)
        # the grey strap round the ankle, lower at the front than behind
        c = Vector((float(last.a[0]), float(last.a[1]), .128))
        ring = OP.ring_path(c, Vector((0, 0, 1)), last.r_shaft, surf, n=36, tilt=0.0)
        ring = [Vector((p.x, p.y, p.z + .020 * (p.y - c.y) / last.r_shaft)) for p in ring]
        OP.band(straps, surf, ring, .018, thick=.0035, lift=.0035, step=.008, closed=True)
        # the pull tab behind the collar
        h = surf.hit(Vector((float(last.t[0]), float(last.t[1]) + .3, T["boot_top"] - .022)), Vector((0, -1, 0)), .5)
        if h:
            fr = OP.frame(h[0] + h[1] * .003, h[1])
            OP.plate(plates, [(-.011, -.020), (.011, -.020), (.011, .022), (-.011, .022)], fr,
                     thick=.004, ridge=.002, rings=1, wrap=.055, bevel=.0012)

        for src, dst in ((up, uppers), (so, soles)):
            tmp = bpy.data.meshes.new("_tmp")
            src.to_mesh(tmp)
            dst.from_mesh(tmp)                                 # (appends: both boots in one)
            bpy.data.meshes.remove(tmp)
            src.free()
    log("boots: uppers, soles, laces, eyelets, plates and straps")
    return [to_object(uppers, "C_feet__orion", "orion_leather"), to_object(soles, "boot_soles", "orion_sole"),
            to_object(plates, "boot_plates", "orion_boot_panel"), to_object(straps, "boot_straps", "orion_boot_panel"),
            to_object(laces, "boot_laces", "orion_strap"),
            to_object(steel, "boot_eyelets", "orion_steel")]
