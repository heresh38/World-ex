"""The body cage: a coarse all-quad control mesh with the edge loops a production base mesh needs (shoulders, elbows,
wrists, hips, knees, ankles, every finger and toe joint), built as cross-section rings along the skeleton.

  torso   20-vertex rings from the crotch to the neck base; a 10-vertex opening on each side (2 rows x 3 columns)
          where the arm attaches
  legs    12-vertex rings; each leg's first loop is half the torso's bottom ring plus a shared crotch vertex
  arms    10-vertex rings from the opening to the wrist (three loops round the elbow)
  hands   the rings flatten into a palm whose knuckle end is four quads, one per finger; the thumb grows from the
          palm's radial side quad; fingers are 4-vertex rings with two loops at each knuckle
  feet    the leg rings bend forward into the foot; its front end is five quads, one per toe
  neck    20-vertex rings up to the head's neck opening (head.py)

Rings are generated with uniform angles so the subdivision (Catmull-Clark) turns them into round, even loops. Shape
is approximate here: fit.py projects the subdivided mesh onto the anatomical target (shape.py).
Blender coordinates: Z up, the character faces -Y, its left is +X.
"""
import math
import bmesh
from mathutils import Vector
import skeleton

TORSO_N, ARM_N, LEG_N, NECK_N = 20, 10, 12, 20


def lerp(a, b, t):
    return a + (b - a) * t


def unit(v):
    v = Vector(v)
    return v.normalized() if v.length > 1e-9 else v


def mx(v, sx):
    """mirror a left-side point / direction to the side sx (+1 left, -1 right)"""
    return Vector((v[0] * sx, v[1], v[2]))


class Cage:
    def __init__(self, T):
        self.T = T
        self.bm = bmesh.new()
        self.groups = {}             # part name -> set of vertex indices (filled at the end) via tags below
        self.part_of = {}            # BMVert -> part

    # ------------------------------------------------------------- primitives
    def v(self, p, part):
        vert = self.bm.verts.new(Vector(p))
        self.part_of[vert] = part
        return vert

    def quad(self, a, b, c, d):
        try:
            return self.bm.faces.new((a, b, c, d))
        except ValueError:
            return None

    def bridge(self, A, B, skip=None):
        n = len(A)
        for i in range(n):
            if skip and skip(i):
                continue
            j = (i + 1) % n
            self.quad(A[i], A[j], B[j], B[i])

    def ring(self, c, u, v, n, ru, rv, part, offset=0.0, power=2.0, bias=None):
        """n vertices round centre c in the plane (u, v): radius ru along u, rv along v, superellipse power;
        angle 0 on +u, increasing toward +v. bias(theta) -> extra radial scale (muscle bulges)."""
        out = []
        for i in range(n):
            th = offset + 2 * math.pi * i / n
            cs, sn = math.cos(th), math.sin(th)
            e = 2.0 / power
            x = math.copysign(abs(cs) ** e, cs) * ru
            y = math.copysign(abs(sn) ** e, sn) * rv
            k = bias(th) if bias else 1.0
            out.append(self.v(c + u * (x * k) + v * (y * k), part))
        return out

    # ------------------------------------------------------------- torso
    def torso_stations(self):
        T = self.T
        bz = T["biacromial"]
        cz, ch = T["chest"], T["chest"]
        st = [
            (T["crotch_z"] + .025, T["hips"]["w"] * .92, T["hips"]["d"] * .92, .012),
            (T["hips"]["z"], T["hips"]["w"], T["hips"]["d"], .014),
            (lerp(T["hips"]["z"], T["waist"]["z"], .5), lerp(T["hips"]["w"], T["waist"]["w"], .55), lerp(T["hips"]["d"], T["waist"]["d"], .5), .006),
            (T["waist"]["z"], T["waist"]["w"], T["waist"]["d"], .0),
            (lerp(T["waist"]["z"], T["underbust"]["z"], .5), lerp(T["waist"]["w"], T["underbust"]["w"], .5), lerp(T["waist"]["d"], T["underbust"]["d"], .5), -.002),
            (T["underbust"]["z"], T["underbust"]["w"], T["underbust"]["d"], -.002),
            (T["chest"]["z"], T["chest"]["w"], T["chest"]["d"], .0),
            (T["shoulder_z"] - .105, bz * .88, cz["d"] * .95, .006),     # armpit level: the arm opening starts
            (T["shoulder_z"] - .050, bz * .93, cz["d"] * .80, .012),
            (T["shoulder_z"], bz * .86, cz["d"] * .58, .022),           # acromion level: the opening ends
            (T["neck_base_z"] + .004, T["neck_w"] * 1.45, T["neck_d"] * 1.25, .026),
        ]
        return st

    def build_torso(self):
        rings = []
        for i, (z, w, d, yc) in enumerate(self.torso_stations()):
            # angle 0 = front centre, increasing toward the left (+X): u = -Y (front), v = +X (left)
            rings.append(self.ring(Vector((0, yc, z)), Vector((0, -1, 0)), Vector((1, 0, 0)), TORSO_N, d / 2, w / 2, "torso",
                                   power=2.3 if i < 9 else 2.0))
        self.torso = rings
        # arm openings: rows between rings 7-8 and 8-9, columns 4..6 (left, verts 4..7) and their mirror 13..15
        # (right, verts 13..16: vertex k mirrors to 20 - k)
        cols = {4, 5, 6, 13, 14, 15}
        for r in range(len(rings) - 1):
            self.bridge(rings[r], rings[r + 1], skip=(lambda i: i in cols) if r in (7, 8) else None)
        self.arm_holes = {}
        for side, k0 in (("L", 4), ("R", 13)):
            R7, R8, R9 = rings[7], rings[8], rings[9]
            loop = [R7[k0], R7[k0 + 1], R7[k0 + 2], R7[k0 + 3], R8[k0 + 3], R9[k0 + 3], R9[k0 + 2], R9[k0 + 1], R9[k0], R8[k0]]
            self.arm_holes[side] = loop

    # ------------------------------------------------------------- limbs: rings matched to an existing loop
    def match(self, loop, ring):
        """rotate / reverse ring so ring[i] faces loop[i] (least twist)"""
        n = len(ring)
        best = None
        for rev in (False, True):
            r = ring[::-1] if rev else ring
            for s in range(n):
                cost = sum((loop[i].co - r[(i + s) % n].co).length for i in range(n))
                if best is None or cost < best[0]:
                    best = (cost, [r[(i + s) % n] for i in range(n)])
        return best[1]

    def limb(self, start_loop, stations, part, n, offset):
        """stations: [(centre, axis, v_hint, ru, rv, power)] -> rings bridged from start_loop"""
        prev = start_loop
        rings = []
        for c, a, vh, ru, rv, pw in stations:
            a = unit(a)
            v = unit(Vector(vh) - a * Vector(vh).dot(a))
            u = v.cross(a)
            r = self.ring(Vector(c), u, v, n, ru, rv, part, offset=offset, power=pw)
            if prev is start_loop:
                prev = self.match(r, start_loop)     # reorder the existing loop; generated rings keep their indices
            self.bridge(prev, r)
            rings.append(r)
            prev = r
        return rings

    # ------------------------------------------------------------- legs and feet
    def build_legs(self):
        T = self.T
        bottom = self.torso[0]
        cz = T["crotch_z"]
        crotch = self.v((0, T["hips"]["d"] * .02, cz - .005), "torso")
        self.legs = {}
        Lg = skeleton.leg(T)
        for side, sx in (("L", 1), ("R", -1)):
            loop = bottom[0:11] + [crotch] if side == "L" else [bottom[0]] + bottom[19:9:-1] + [crotch]
            hip, knee, ank = mx(Lg["H"], sx), mx(Lg["K"], sx), mx(Lg["A"], sx)
            th, ca = T["thigh"], T["calf"]
            front = Vector((0, -1, 0))
            at = lambda p, q, t: p + (q - p) * t
            st = []
            for t, w, d in ((.10, th["w"] * 1.05, th["d"] * 1.02), (.32, th["w"], th["d"]), (.58, th["w"] * .86, th["d"] * .9),
                            (.80, th["w"] * .70, th["d"] * .76)):
                c = at(hip, knee, t) + Vector((-.012 * sx * (1 - t), 0, 0))
                w = min(w, 2 * (abs(c.x) - .008))                  # each thigh stays on its own side of the midline
                st.append((c, knee - hip, front, w / 2, d / 2, 2.0))
            kw = th["w"] / .18
            for t, w, d in ((.96, .105, .110), (1.04, .100, .104)):       # knee loops
                st.append((at(hip, knee, t), knee - hip, front, w / 2 * kw, d / 2 * kw, 2.0))
            for t, w, d in ((.12, ca["w"] * .95, ca["d"] * .95), (.30, ca["w"], ca["d"]), (.55, ca["w"] * .8, ca["d"] * .78),
                            (.78, ca["w"] * .62, ca["d"] * .6), (.93, .072, .066)):
                st.append((at(knee, ank, t), ank - knee, front, w / 2, d / 2, 2.0))
            rings = self.limb(loop, st, "leg_" + side, LEG_N, math.radians(15))
            self.legs[side] = rings
            self.build_foot(side, rings[-1], sx)

    def explicit_ring(self, c, u, v, us, ru, rv, part):
        """a flattened ring: top row at u fractions us (+v side), bottom row back the other way (-v side)"""
        top = [self.v(c + u * (x * ru) + v * rv, part) for x in us]
        bot = [self.v(c + u * (x * ru) - v * rv, part) for x in us[::-1]]
        return top + bot

    def digits(self, cap_top, cap_bot, chains, part, ring_pos):
        """one 4-vertex tube per cap quad, following the nearest skeleton chain"""
        for k in range(len(cap_top) - 1):
            quad = [cap_top[k], cap_top[k + 1], cap_bot[k + 1], cap_bot[k]]
            base = sum((q.co for q in quad), Vector()) / 4
            ch = min(chains, key=lambda c: (c["base"] - base).length)
            J = ch["joints"]
            w = ch["width"] / 2
            across = unit(cap_top[k + 1].co - cap_top[k].co)
            prev = quad
            for f, s in ring_pos:
                # position along the joint polyline (f in 0..1 of the length)
                seg = min(int(f * (len(J) - 1)), len(J) - 2)
                tt = f * (len(J) - 1) - seg
                c = J[seg] + (J[seg + 1] - J[seg]) * tt
                dirn = unit(J[seg + 1] - J[seg])
                up = unit(ch["up"] - dirn * ch["up"].dot(dirn))
                side = unit(up.cross(dirn))
                if side.dot(across) < 0:
                    side = -side
                h = w * ch.get("flat", .9)
                ring = [self.v(c - side * w * s + up * h * s, part), self.v(c + side * w * s + up * h * s, part),
                        self.v(c + side * w * s - up * h * s, part), self.v(c - side * w * s - up * h * s, part)]
                ring = self.match(prev, ring)
                self.bridge(prev, ring)
                prev = ring
            self.quad(*prev)

    def build_foot(self, side, ank_ring, sx):
        T = self.T
        F = skeleton.foot(T)
        fw = F["width"]
        ank = mx(F["ankle"], sx)
        up, fwd = Vector((0, 0, 1)), Vector((0, -1, 0))
        st = [
            (Vector((ank.x, ank.y - .012, ank.z * .62)), Vector((0, -.6, -.8)), Vector((0, -.8, .6)), fw * .40, .060, 2.0),
            (Vector((ank.x + .003 * sx, ank.y - .055, .048)), fwd, up, fw * .46, .048, 2.4),
            (Vector((ank.x + .006 * sx, ank.y - .115, .036)), fwd, up, fw * .50, .038, 2.6),
        ]
        rings = self.limb(ank_ring, st, "foot_" + side, LEG_N, math.radians(15))
        # the ball of the foot: an explicit flattened ring, six even columns across (five toe quads)
        ball = mx(F["ball"], sx)
        last = rings[-1]
        a = fwd
        v = up
        u = unit(v.cross(a))
        r = self.explicit_ring(ball, u, v, [1.0, .6, .2, -.2, -.6, -1.0], fw / 2 * 1.02, .026, "foot_" + side)
        self.bridge(last, r)
        toes = []
        for t in F["toes"]:
            r_ = t["width"] / 2                                     # on the target's toe axis (shape.foot_part)
            tb = mx(t["base"], sx) + Vector((0, .012, skeleton.TOE_ROOT_Z - t["base"].z))
            d = mx(t["dir"], sx)
            tip = mx(t["base"], sx) + d * t["len"] + Vector((0, 0, r_ * .80 - t["base"].z))
            J = [tb, tb + (tip - tb) * .55, tip]
            toes.append(dict(base=tb, joints=J, width=t["width"], up=up, flat=.8))
        self.digits(r[0:6], [r[11 - i] for i in range(6)], toes, "toe",
                    ((.42, .92), (.56, .90), (.64, .88), (.82, .82), (.96, .72), (1.03, .42)))

    def build_arms(self):
        T = self.T
        self.arms = {}
        A = skeleton.arm(T)
        for side, sx in (("L", 1), ("R", -1)):
            a, dorsal = mx(A["a"], sx), mx(A["dorsal"], sx)
            sh, el, wr = mx(A["S"], sx), mx(A["E"], sx), mx(A["W"], sx)
            ur, fr = T["upper_arm_r"], T["forearm_r"]
            st = [
                (sh + a * .035, a, dorsal, ur * 1.30, ur * 1.20, 2.0),     # deltoid
                (sh + a * .11, a, dorsal, ur * 1.08, ur * 1.05, 2.0),
                (sh + a * .19, a, dorsal, ur * .98, ur * .95, 2.0),
                (el - a * .035, a, dorsal, ur * .86, ur * .80, 2.0),       # elbow loops
                (el, a, dorsal, ur * .82, ur * .76, 2.0),
                (el + a * .035, a, dorsal, fr * 1.12, fr * .98, 2.0),
                (el + a * .10, a, dorsal, fr * 1.12, fr * .92, 2.0),
                (el + a * .18, a, dorsal, fr * .90, fr * .74, 2.0),
                (wr - a * .02, a, dorsal, T["wrist"]["w"] / 2, T["wrist"]["d"] / 2, 2.2),
                (wr + a * .005, a, dorsal, T["wrist"]["w"] / 2 * 1.02, T["wrist"]["d"] / 2 * 1.02, 2.4),   # wrist loops
            ]
            rings = self.limb(self.arm_holes[side], st, "arm_" + side, ARM_N, math.radians(18))
            self.arms[side] = rings
            self.build_hand(side, rings[-1], sx)

    def build_hand(self, side, wrist, sx):
        T = self.T
        Hd = skeleton.hand(T)
        A = Hd["arm"]
        a, d, th = mx(A["a"], sx), mx(A["dorsal"], sx), mx(A["thumb"], sx)
        wr = mx(A["W"], sx)
        P = T["palm"]
        st = [
            (wr + a * (P["l"] * .22), a, d, P["w"] / 2 * .88, P["t"] / 2 * 1.05, 3.0),
            (wr + a * (P["l"] * .60), a, d, P["w"] / 2 * .98, P["t"] / 2, 3.2),
        ]
        palm0, palm1 = self.limb(wrist, st, "hand_" + side, ARM_N, math.radians(18))
        # the knuckles: an explicit flattened ring, five even columns across (four finger quads)
        u = unit(d.cross(a))                       # the same u the limb rings use (angle 0 side)
        kn = self.explicit_ring(mx(Hd["knuckle"], sx), u, d, [1.0, .5, 0.0, -.5, -1.0], P["w"] / 2 * .95, P["t"] / 2 * .85, "hand_" + side)
        self.bridge(palm1, kn)
        chains = []
        for f, ch in Hd["fingers"].items():
            chains.append(dict(base=mx(ch["base"], sx), joints=[mx(j, sx) for j in ch["joints"]], width=ch["width"], up=d))
        self.digits(kn[0:5], [kn[9 - i] for i in range(5)], chains, "finger",
                    ((.06, 1.0), (.36, .96), (.43, .97), (.50, .96), (.70, .90), (.76, .90), (.82, .88), (.96, .80), (1.03, .48)))
        # thumb from the radial side quad between the two palm rings (the side toward the thumb)
        k0, k1 = (0, ARM_N - 1) if u.dot(th) > 0 else (4, 5)
        quad_v = [palm0[k1], palm0[k0], palm1[k0], palm1[k1]]
        for f in list(self.bm.faces):
            if set(f.verts) == set(quad_v):
                self.bm.faces.remove(f)
                break
        tc = Hd["thumb"]
        chain = dict(base=mx(tc["base"], sx), joints=[mx(j, sx) for j in tc["joints"]], width=tc["width"], up=d, flat=1.0)
        # a single tube: reuse digits with a one-quad "cap"
        self.digits([quad_v[0], quad_v[1]], [quad_v[3], quad_v[2]], [chain], "thumb",
                    ((.10, 1.25), (.36, 1.08), (.44, 1.0), (.52, .98), (.78, .9), (.96, .80), (1.03, .48)))

    # ------------------------------------------------------------- neck
    def build_neck(self):
        T = self.T
        top = self.torso[-1]
        st = []
        for t in (.35, .75):
            z = lerp(T["neck_base_z"], T["chin_z"] - .01, t)
            st.append((Vector((0, .028 - .012 * t, z)), Vector((0, 0, 1)), Vector((0, -1, 0)), T["neck_d"] / 2 * (1 - .05 * t),
                       T["neck_w"] / 2 * (1 - .04 * t), 2.0))
        # neck rings: u = -Y? keep the torso's convention (angle 0 front, toward +X): u front, v left
        rings = []
        prev = top
        for c, a, vh, rd, rw, pw in st:
            r = self.ring(c, Vector((0, -1, 0)), Vector((1, 0, 0)), NECK_N, rd, rw, "neck")
            self.bridge(prev, r)
            rings.append(r)
            prev = r
        self.neck_top = prev

    def build(self):
        self.build_torso()
        self.build_legs()
        self.build_arms()
        self.build_neck()
        return self
