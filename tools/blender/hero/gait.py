"""The motion engine behind the hero bodies' clips. It holds no style: each body has its own clip set in its own
folder (male/motion.py, female/motion.py) and only uses this to turn poses into baked keys.

Conventions (Blender armature space, metres): +X = the body's left, -Y = forward, +Z = up.

A clip is a sampler f(t) -> Pose for t in [0, duration) (loops sample one cycle; the last key repeats the first).
Pose fields:
  hips   Vector: the pelvis offset from its rest position
  rot    {bone: [(axis, deg), ...]}: rotations in armature axes, applied in order, about the bone's own pivot and
         carried by its parent (characters.wq's convention). The A-pose arms are lowered to the sides first
         (`arms_down`), so arm rotations are written against arms hanging at the sides.
  feet   {"L"|"R": Foot | None}: an ankle target in armature space and the foot's orientation, reached with leg IK
         (baked to FK); None = the leg follows `rot` (in the air, falling)
Feet planned with `Gait` plant exactly: a foot on the ground moves back at the clip's ground speed, rolling from the
heel to the ball about real pivots, so at the speed the game plays the clip at (Clips.WalkSpeed / RunSpeed) nothing
slides. The hips are lowered whenever a planted leg would have to reach farther than it can (no knee pops).

What makes generated motion read as a body and not a machine, and where it lives here:
  - nothing peaks together: `locomote` drives the spine, chest, head, forearms and hands off the same cycle with a
    lag each (overlap / follow-through), and `Track.at(t, lags)` does the same for keyed clips;
  - no pure sine: the swings carry a second harmonic (a quick drive, a slower return), the pelvis loads fast and
    rises slowly, the swing foot recovers high behind, passes under the hip and comes back toward the ground before
    it lands (`retract`), so it meets the ground already moving with it;
  - the two sides are not copies: `asym` scales and shifts one side a little.
`locomote` and `Track` hold no style either: every number comes from the body's own motion.py.
"""
import math
import bpy
from mathutils import Vector, Quaternion, Matrix

FPS = 30
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
SIDES = (("L", 1), ("R", -1))


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def minjerk(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (10 - 15 * u + 6 * u * u)


def bump(u, c, w):
    """a smooth bump of width w centred at c (0 outside)"""
    d = (u - c) / w
    return math.cos(d * math.pi / 2) ** 2 if abs(d) < 1 else 0.0


def quat(rots):
    q = Quaternion()
    for ax, d in rots:
        q = Quaternion(Vector(ax), math.radians(d)) @ q
    return q


class Foot:
    def __init__(self, ankle, pitch=0.0, yaw=0.0, roll=0.0):
        self.ankle, self.pitch, self.yaw, self.roll = Vector(ankle), pitch, yaw, roll   # deg: toe up +, toe out +

    def rotation(self, sx):
        # toe up = about -X; toe out = the left foot turning toward +X (about +Z), mirrored for the right
        return quat([(X, -self.pitch), (Y, sx * self.roll), (Z, sx * self.yaw)])


class Pose:
    def __init__(self):
        self.hips = Vector()
        self.rot = {}
        self.feet = {"L": None, "R": None}
        self.knee_out = {"L": 0.0, "R": 0.0}     # m: the knee pole moved out (+) or in (-) from straight ahead
        self.local = {}                          # {bone: [(axis, deg)]} in the bone's own frame (finger curls)

    def curl(self, side, fingers, thumb=0.0):
        """fingers: (proximal, middle, distal) degrees toward the palm for index, middle, ring, pinky (a 4-tuple of
        triples, or one triple for all); thumb: degrees for its two outer joints"""
        names = ("index", "middle", "ring", "pinky")
        per = fingers if isinstance(fingers[0], (tuple, list)) else (fingers,) * 4
        for n, (a, b, c) in zip(names, per):
            for k, d in ((1, a), (2, b), (3, c)):
                self.local[f"{n}_0{k}.{side}"] = [((1, 0, 0), -d)]
        for k, d in ((2, thumb), (3, thumb * .8)):
            self.local[f"thumb_0{k}.{side}"] = [((1, 0, 0), -d)]
        return self

    def add(self, bone, *rots):
        self.rot.setdefault(bone, []).extend(rots)
        return self


class Body:
    """the rest skeleton's measurements"""

    def __init__(self, arm, T, arms_down_deg):
        B = arm.data.bones
        self.arm, self.T = arm, T
        self.scale = T["height"] / 1.84
        self.hips0 = B["hips"].head_local.copy()
        self.hip, self.knee, self.ankle, self.ball, self.heel = {}, {}, {}, {}, {}
        import skeleton
        F = skeleton.foot(T)
        for s, sx in SIDES:
            self.hip[s] = B["thigh." + s].head_local.copy()
            self.knee[s] = B["shin." + s].head_local.copy()
            self.ankle[s] = B["foot." + s].head_local.copy()
            self.ball[s] = Vector((F["ball"].x * sx, F["ball"].y, 0.0))
            self.heel[s] = Vector((F["ankle"].x * sx, F["heel"].y, 0.0))
        # the elbow / wrist hinge in the rest (A-pose) frame: perpendicular to the upper arm in the frontal plane, so
        # once the arm is lowered (arms_down) a bend about it swings the forearm straight forward
        self.elbow = {}
        for s, sx in SIDES:
            a = (B["upperarm." + s].tail_local - B["upperarm." + s].head_local).normalized()
            h = Vector((-a.z, 0.0, a.x))                        # lowered, both sides become +X (bends forward)
            self.elbow[s] = tuple(h.normalized())
        self.thigh = (self.knee["L"] - self.hip["L"]).length
        self.shin = (self.ankle["L"] - self.knee["L"]).length
        self.leg = self.thigh + self.shin
        self.arms_down = arms_down_deg

    def planted(self, s, ref, pitch, yaw=0.0):
        """the ankle of a foot whose rest layout is moved so its ankle sits over ref (x, y), pitched about the heel
        (toe up) or the ball (heel up), toed out by yaw about the ankle"""
        sx = 1 if s == "L" else -1
        a0 = self.ankle[s]
        off = Vector((ref[0] - a0.x, ref[1] - a0.y, 0.0))
        pivot = (self.heel[s] if pitch >= 0 else self.ball[s]) + off
        r = Quaternion(Vector(X), math.radians(-pitch))
        ankle = pivot + r @ (a0 + off - pivot)
        if yaw:
            q = Quaternion(Vector(Z), math.radians(sx * yaw))
            c = Vector((ref[0], ref[1], 0.0))
            ankle = c + q @ (ankle - c)
        return ankle

    def hip_joint(self, s, pose):
        """where a hip joint goes with the pose's hips offset and hips rotation"""
        q = quat(pose.rot.get("hips", []))
        return self.hips0 + pose.hips + q @ (self.hip[s] - self.hips0)

    def need_drop(self, pose, slack=.003):
        """how far the hips must come down for every IK foot to be within reach (keeping a little knee bend)"""
        drop = 0.0
        for s, _sx in SIDES:
            f = pose.feet[s]
            if f is None:
                continue
            h = self.hip_joint(s, pose)
            d = f.ankle - h
            horiz = math.hypot(d.x, d.y)
            L = self.leg - slack
            if d.length > L:
                drop = max(drop, h.z - (f.ankle.z + math.sqrt(max(L * L - horiz * horiz, .04))))
        return drop

    def reach(self, pose, slack=.002):
        """lower the hips until every IK foot is within reach (the knee keeps a little bend)"""
        for _ in range(3):
            drop = 0.0
            for s, _sx in SIDES:
                f = pose.feet[s]
                if f is None:
                    continue
                h = self.hip_joint(s, pose)
                d = f.ankle - h
                horiz = math.hypot(d.x, d.y)
                L = self.leg - slack
                if d.length > L:
                    zmax = f.ankle.z + math.sqrt(max(L * L - horiz * horiz, .04))
                    drop = max(drop, h.z - zmax)
            if drop <= 1e-5:
                break
            pose.hips.z -= drop
        return pose


class Gait:
    """a cyclic run (or walk) planned from the feet. Left contact at phase 0, right at .5.

    v        ground speed (m/s) the clip plays at 1x        cadence  steps per minute
    duty     stance fraction of the cycle per foot           front    share of the stance length ahead of the hip
    width    ankle x from the middle while planted (m)       toe_out  deg
    lift     swing clearance (m)                             kick     heel kick behind early in the swing (m)
    strike   heel-strike toe-up (deg)                        toeoff   heel-up at toe-off (deg)
    swing_in the swing foot passes this much nearer the middle (m)
    heel     a heeled boot: every planted foot is pitched heel-up by this many degrees (the heel block meets the ground)
    stance   heel-up through the middle of the stance, deg (a run on the ball of the foot: the leg stays long)
    """

    def __init__(self, body, **p):
        self.b = body
        self.p = dict(v=4.4, cadence=165, duty=.33, front=.42, width=.10, toe_out=8, lift=.10, kick=.10,
                      strike=12, toeoff=38, swing_in=.015, swing_pitch=-18, heel=0.0, stance=0.0,
                      # retract: 0..1, how much of the ground's speed the swing foot has at both ends of the swing (it
                      # trails back after toe-off and comes back before it lands); peak: where in the swing (0..1) the
                      # foot is highest (the heel recovery behind the body comes early); None = the old symmetric arc
                      retract=0.0, peak=None)
        self.p.update(p)
        frames = max(8, round(120.0 / self.p["cadence"] * FPS))   # one cycle = two steps
        self.T = frames / FPS
        self.L = self.p["v"] * self.p["duty"] * self.T          # how far the foot travels under the body per stance

    def foot(self, s, phase):
        """ankle target, pitch and yaw of one foot; returns (Foot, planted?)"""
        p, b = self.p, self.b
        sx = 1 if s == "L" else -1
        ph = (phase + (0.0 if s == "L" else 0.5)) % 1.0
        y0 = b.hip[s].y
        yf = y0 - p["front"] * self.L                    # landing (forward is -Y)
        yb = yf + self.L                                 # toe-off
        x = sx * p["width"]
        duty = p["duty"]

        def stance_pitch(u):
            st = -p["stance"]
            if u < .2:
                return p["strike"] + (st - p["strike"]) * smooth(u / .2)
            if u > .5:
                return st + (-p["toeoff"] - st) * smooth((u - .5) / .5)
            return st

        hl = p["heel"]
        if ph < duty:
            u = ph / duty
            ref = (x, yf + self.L * u)
            pitch = stance_pitch(u) - hl
            return Foot(b.planted(s, ref, pitch, p["toe_out"]), pitch, p["toe_out"]), True
        w = (ph - duty) / (1 - duty)
        a_off = b.planted(s, (x, yb), -p["toeoff"] - hl, p["toe_out"])
        a_on = b.planted(s, (x, yf), p["strike"] - hl, p["toe_out"])
        m = minjerk(w)
        ankle = a_off.lerp(a_on, m)
        ankle.x -= sx * p["swing_in"] * math.sin(math.pi * w)
        if p["peak"] is None:
            ankle.z += p["lift"] * math.sin(math.pi * w) ** 1.5 + p["kick"] * bump(w, .3, .3)
            # the heel kick carries the foot up behind the body before it swings through
            ankle.y += p["kick"] * .6 * bump(w, .25, .25)
        else:
            # along the way: a Hermite curve that leaves and arrives with part of the stance speed (the foot trails
            # behind the hip after toe-off, reaches ahead and is drawn back before the strike)
            tang = p["retract"] * p["v"] * (1 - duty) * self.T
            h00, h10 = 2 * w ** 3 - 3 * w ** 2 + 1, w ** 3 - 2 * w ** 2 + w
            h01, h11 = -2 * w ** 3 + 3 * w ** 2, w ** 3 - w ** 2
            ankle.y = h00 * a_off.y + h10 * tang + h01 * a_on.y + h11 * tang
            # up: the recovery peaks early (the heel comes up behind), the foot stays up as the knee drives through
            # and comes down late
            e = math.log(.5) / math.log(max(.05, min(.95, p["peak"])))
            ankle.z = a_off.z + (a_on.z - a_off.z) * m + (p["lift"] + p["kick"]) * math.sin(math.pi * w ** e) ** 1.25
        if w < .45:
            pitch = -p["toeoff"] + (p["toeoff"] + p["swing_pitch"]) * smooth(w / .45)
        else:
            pitch = p["swing_pitch"] + (p["strike"] - p["swing_pitch"]) * smooth((w - .45) / .55)
        return Foot(ankle, pitch - hl, p["toe_out"]), False

    def phase(self, t):
        return (t / self.T) % 1.0


def arms_down(body, pose):
    """prepend the A-pose -> arms-at-the-sides rotation to the upper arms (every clip)"""
    for s, sx in SIDES:
        k = "upperarm." + s
        pose.rot[k] = [(Y, sx * -body.arms_down)] + pose.rot.get(k, [])
    return pose


# --- cyclic locomotion ----------------------------------------------------------------------------------------------

TAU = 2 * math.pi


def wave(ph, h2=0.0, ph2=0.0):
    """cos of the cycle with a second harmonic (h2 its share, ph2 its phase in cycles): a swing that drives one way
    quicker than it comes back"""
    return math.cos(TAU * ph) + h2 * math.cos(2 * TAU * (ph + ph2))


def locomote(b, g, t, S, lift=0.0):
    """One pose of a walk or run cycle planned by the Gait `g`, the body above the feet solved from the cycle's phase.
    Left contact at phase 0. S (all from the body's own motion.py):

      lean        forward lean, deg (hips, spine and chest share it; the head stays level)
      hip_yaw     pelvis rotation with the stride      hip_roll   pelvis list (the swing side drops)
      sway, bob   pelvis side shift (m) and rise / fall per step (m; negative = highest over the planted foot: a walk)
      bob2        second harmonic of the bob (the quick load after the strike)      drop  how low the pelvis rides (m)
      dip         the extra give at each strike (m)
      counter     shoulders against the hips (0 = just undoing the pelvis, 1 = as much again)
      lag         {"spine", "chest", "head", "arm", "forearm", "hand"}: cycles each part runs behind the pelvis
      nod         chest pitch per step, deg      chest_up  the chest carried up and back against the lean, deg
      arm         swing amplitude, deg      arm_bias  centre of the swing, deg (negative = carried behind)
      arm_h2      second harmonic of the swing (the drive)
      abd         elbow out from the body, deg; abd_back / abd_fwd: more on the back swing, less on the forward one
      cross       the upper arm turning in on the forward swing, deg (the hand comes toward the middle)
      elbow       elbow bend, deg; elbow_fwd: more at the front; elbow_back: less (it opens) at the back
      wrist, wrist_lag  hand bend and how much it drags behind the forearm, deg
      clav        shoulder girdle forward / back with the arm, deg
      curl        finger curl (see Pose.curl), thumb
      knee_out    knee poles (m)
      asym        the right side's amplitude scale; asym_ph: its phase shift (cycles)
    """
    ph = g.phase(t)
    duty = g.p["duty"]
    p = Pose()
    for s, _ in SIDES:
        p.feet[s], _ = g.foot(s, ph)
    L = S.get("lag", {})
    step = (2 * ph) % 1.0
    bob = S["bob"] * math.cos(TAU * (step - duty)) + S.get("bob2", 0.0) * math.cos(2 * TAU * (step - duty) + 1.1)
    p.hips = Vector((S["sway"] * math.cos(TAU * (ph - duty / 2)), 0.0,
                     lift - S["drop"] - bob - S.get("dip", 0.0) * bump(step, .07, .09)))
    yaw = -S["hip_yaw"] * wave(ph, .12, .08)
    roll = -S["hip_roll"] * math.cos(TAU * (ph - duty / 2))
    lean = S["lean"]
    p.add("hips", (Z, yaw), (Y, roll), (X, lean * .40))

    def turn(lag):                                   # the shoulders' answer to the pelvis, running behind it
        return S["hip_yaw"] * (1 + S["counter"]) * wave(ph - lag, .12, .08)

    def list_(lag):
        return S["hip_roll"] * math.cos(TAU * (ph - duty / 2 - lag))

    nod = S.get("nod", 0.0)
    p.add("spine", (Z, turn(L.get("spine", 0)) * .45), (Y, list_(L.get("spine", 0)) * .6), (X, lean * .32 + nod * .4 * math.cos(2 * TAU * (ph - L.get("spine", 0)) - .6)))
    p.add("chest", (Z, turn(L.get("chest", 0)) * .55), (Y, list_(L.get("chest", 0)) * .3),
          (X, lean * .28 - S.get("chest_up", 0.0) + nod * .6 * math.cos(2 * TAU * (ph - L.get("chest", 0)) - .6)))
    # the head stays on the line of travel and level: it undoes what is below it, a touch late
    hy = S["hip_yaw"] * S["counter"] * wave(ph - L.get("head", 0), .12, .08)
    p.add("neck", (Z, -hy * .5), (Y, -roll * .15), (X, -lean * .42 + S.get("chest_up", 0.0) * .6))
    p.add("head", (Z, -hy * .5), (X, -lean * .30 - nod * .5 * math.cos(2 * TAU * (ph - L.get("head", 0)) - .6)))

    for s, sx in SIDES:
        amp = 1.0 if s == "L" else S.get("asym", 1.0)
        off = (0.0 if s == "L" else .5 + S.get("asym_ph", 0.0))

        def fwd(lag):                                # -1 = fully back, +1 = fully forward (the left arm back at left contact)
            return -wave(ph + off - lag, S.get("arm_h2", 0.0), .12) / (1 + abs(S.get("arm_h2", 0.0)))

        f = fwd(L.get("arm", 0))
        ff = fwd(L.get("forearm", 0))
        fh = fwd(L.get("hand", 0))
        ang = S.get("arm_bias", 0.0) + S["arm"] * amp * f                         # + = forward
        abd = S["abd"] + S.get("abd_back", 0.0) * max(0.0, -f) - S.get("abd_fwd", 0.0) * max(0.0, f)
        p.add("clavicle." + s, (Z, sx * S.get("clav", 0.0) * f), (Y, sx * -S.get("clav_up", 0.0) * max(0.0, -f)))
        p.add("upperarm." + s, (Y, -sx * abd), (X, -ang), (Z, sx * S.get("cross", 0.0) * max(0.0, f)))
        flex = S["elbow"] + S.get("elbow_fwd", 0.0) * max(0.0, ff) - S.get("elbow_back", 0.0) * max(0.0, -ff)
        p.add("forearm." + s, (b.elbow[s], -flex * (1.0 if s == "L" else S.get("asym_elbow", 1.0))))
        p.add("hand." + s, (b.elbow[s], -S.get("wrist", 8.0) - S.get("wrist_lag", 0.0) * fh), (Z, sx * S.get("hand_turn", 0.0)))
        p.curl(s, S["curl"], S.get("thumb", 20))
    k = S.get("knee_out", .08)
    p.knee_out = {"L": k, "R": k}
    return p


# --- keyed clips ----------------------------------------------------------------------------------------------------

def blend(a, c, k):
    """the pose k of the way from a to c: joint rotations the short way round, the rest straight"""
    k = min(1.0, max(0.0, k))
    out = Pose()
    out.hips = a.hips.lerp(c.hips, k)
    for bone in set(a.rot) | set(c.rot):
        q = quat(a.rot.get(bone, [])).slerp(quat(c.rot.get(bone, [])), k)
        out.rot[bone] = [(tuple(q.axis), math.degrees(q.angle))]
    for bone in set(a.local) | set(c.local):
        la, lc = a.local.get(bone, [((1, 0, 0), 0.0)]), c.local.get(bone, [((1, 0, 0), 0.0)])
        out.local[bone] = [(la[0][0], la[0][1] + (lc[0][1] - la[0][1]) * k)]
    for s in ("L", "R"):
        fa, fc = a.feet[s], c.feet[s]
        if fa is not None and fc is not None:
            out.feet[s] = Foot(fa.ankle.lerp(fc.ankle, k), fa.pitch + (fc.pitch - fa.pitch) * k, fa.yaw + (fc.yaw - fa.yaw) * k,
                               fa.roll + (fc.roll - fa.roll) * k)
        else:
            out.feet[s] = fa if k < .5 else fc
        out.knee_out[s] = a.knee_out[s] + (c.knee_out[s] - a.knee_out[s]) * k
    return out


class Track:
    """a clip from key poses: [(time, Pose), ...] eased from one to the next. `at(t, lags)` reads each part of the
    body a little later than the hips ({"spine", "chest", "head", "arm", "forearm", "hand", "leg"}: seconds), so the
    body does not arrive in a pose all at once: the hips lead, the chest, head and hands follow through."""
    PARTS = (("spine", ("spine",)), ("chest", ("chest", "clavicle")), ("head", ("neck", "head")),
             ("arm", ("upperarm",)), ("forearm", ("forearm",)),
             ("hand", ("hand", "index", "middle", "ring", "pinky", "thumb")), ("leg", ("thigh", "shin", "foot", "toe")))

    def __init__(self, keys, ease=minjerk):
        self.keys = sorted(keys, key=lambda k: k[0])
        self.ease = ease

    def pose(self, t):
        K = self.keys
        if t <= K[0][0]:
            return K[0][1]
        for (t0, a), (t1, c) in zip(K, K[1:]):
            if t <= t1:
                return blend(a, c, self.ease((t - t0) / max(t1 - t0, 1e-6)))
        return K[-1][1]

    def at(self, t, lags=None):
        base = self.pose(t)
        if not lags:
            return base
        out = blend(base, base, 0.0)
        late = {}
        for part, prefixes in self.PARTS:
            lag = lags.get(part, 0.0)
            if lag <= 0.0:
                continue
            if lag not in late:
                late[lag] = self.pose(t - lag)
            src = late[lag]
            for bone in list(out.rot):
                if bone.split(".")[0].split("_")[0] in prefixes:
                    q = quat(src.rot.get(bone, []))
                    out.rot[bone] = [(tuple(q.axis), math.degrees(q.angle))]
            for bone in list(out.local):
                if bone.split(".")[0].split("_")[0] in prefixes and bone in src.local:
                    out.local[bone] = src.local[bone]
        return out


# --- baking ---------------------------------------------------------------------------------------------------------

def _setup(arm, body):
    """temporary IK helpers: mk_foot.X (rest = the foot's), mk_knee.X; IK on the shins, the feet copy mk_foot"""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    root = eb["root"] if "root" in eb else None
    for s, sx in SIDES:
        f = eb["foot." + s]
        e = eb.new("mk_foot." + s)
        e.head, e.tail, e.roll = f.head.copy(), f.tail.copy(), f.roll
        e.parent = root
        k = eb.new("mk_knee." + s)
        k.head = body.knee[s] + Vector((0, -.5, 0))
        k.tail = k.head + Vector((0, 0, .05))
        k.parent = root
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    for s, sx in SIDES:
        ik = arm.pose.bones["shin." + s].constraints.new('IK')
        ik.name = "mk_IK"
        ik.target, ik.subtarget = arm, "mk_foot." + s
        ik.pole_target, ik.pole_subtarget = arm, "mk_knee." + s
        ik.chain_count = 2
        ik.use_stretch = False
        cr = arm.pose.bones["foot." + s].constraints.new('COPY_ROTATION')
        cr.name = "mk_ROT"
        cr.target, cr.subtarget = arm, "mk_foot." + s
    bpy.ops.object.mode_set(mode='OBJECT')
    _calibrate_pole(arm, body)


def _calibrate_pole(arm, body):
    """the pole angle that keeps the rest pose with the knee pole straight ahead (depends on the bones' rolls)"""
    best = None
    for ang in (-90, 0, 90, 180):
        for s, _ in SIDES:
            arm.pose.bones["shin." + s].constraints["mk_IK"].pole_angle = math.radians(ang)
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix()
        bpy.context.view_layer.update()
        err = sum((arm.pose.bones["shin." + s].head - body.knee[s]).length for s, _ in SIDES)
        if best is None or err < best[0]:
            best = (err, ang)
    for s, _ in SIDES:
        arm.pose.bones["shin." + s].constraints["mk_IK"].pole_angle = math.radians(best[1])
    return best


def _apply(arm, body, pose, frame):
    PB = arm.pose.bones
    B = arm.data.bones
    for pb in PB:
        if pb.name.startswith(("mk_", "ik_", "pole")) or pb.name == "root":
            continue
        rr = B[pb.name].matrix_local.to_quaternion()
        q = quat(pose.rot.get(pb.name, []))
        pb.rotation_quaternion = rr.inverted() @ q @ rr @ quat(pose.local.get(pb.name, []))
        pb.keyframe_insert("rotation_quaternion", frame=frame)
    hb = PB["hips"]
    rr = B["hips"].matrix_local.to_quaternion()
    hb.location = rr.inverted() @ pose.hips
    hb.keyframe_insert("location", frame=frame)
    for s, sx in SIDES:
        f = pose.feet[s]
        on = f is not None
        PB["shin." + s].constraints["mk_IK"].influence = 1.0 if on else 0.0
        PB["foot." + s].constraints["mk_ROT"].influence = 1.0 if on else 0.0
        PB["shin." + s].constraints["mk_IK"].keyframe_insert("influence", frame=frame)
        PB["foot." + s].constraints["mk_ROT"].keyframe_insert("influence", frame=frame)
        mf = PB["mk_foot." + s]
        if on:
            rest = B["foot." + s].matrix_local.to_3x3()
            M = (f.rotation(sx).to_matrix() @ rest).to_4x4()
            M.translation = f.ankle
            mf.matrix = M
            # the knee points along the shin's swing plane, ahead of the hip
            h = body.hip_joint(s, pose)
            fwd = Vector((0, -1, 0))
            pole = h.lerp(f.ankle, .5) + fwd * .5 + Vector((sx * pose.knee_out[s], 0, 0))
            mk = PB["mk_knee." + s]
            K = Matrix.Translation(pole)
            mk.matrix = K
            bpy.context.view_layer.update()
        for b in (mf, PB["mk_knee." + s]):
            b.keyframe_insert("location", frame=frame)
            b.keyframe_insert("rotation_quaternion", frame=frame)


def plan(body, f, dur, loop):
    """the clip's poses, one per frame, with the hips brought down where a leg would over-reach"""
    n = max(2, round(dur * FPS))
    poses = []
    for i in range(n + 1):
        t = (i / n) * dur
        pose = f(t % dur if loop else t)
        arms_down(body, pose)
        poses.append(pose)
    # the hips come down where a leg would over-reach, planned over the whole clip and smoothed (a widened,
    # blurred envelope), so the reach never shows as a dip in a single frame; a last per-frame clamp is a guard
    need = [body.need_drop(p) for p in poses]
    m = len(need) - 1 if loop else len(need)
    idx = (lambda k: k % m) if loop else (lambda k: min(max(k, 0), m - 1))
    wide = [max(need[idx(i + k)] for k in range(-3, 4)) for i in range(len(need))]
    kern = (1, 3, 6, 7, 6, 3, 1)
    soft = [sum(w * wide[idx(i + k - 3)] for k, w in enumerate(kern)) / sum(kern) for i in range(len(need))]
    for i, pose in enumerate(poses):
        pose.hips.z -= soft[i]
        body.reach(pose)
    return poses


def measure(body, clips, names, log=print):
    """Numbers instead of eyes: for each clip, frame by frame, how high the hips ride against standing (cm), each
    knee's bend (deg; 0 = straight) and each ankle's height (cm), then the trunk's forward pitch. Nothing is baked."""
    a, c = body.thigh, body.shin
    for name in names:
        if name not in clips:
            log(f"no clip {name}")
            continue
        f, dur, loop = clips[name]
        poses = plan(body, f, dur, loop)
        rows, flex = [], {"L": [], "R": []}
        for i, pose in enumerate(poses[:-1] if loop else poses):
            cell = [f"{i:2d}", f"hips {pose.hips.z * 100:+5.1f}"]
            for s, _sx in SIDES:
                ft = pose.feet[s]
                if ft is None:
                    cell.append(f"{s} fk")
                    continue
                d = min((ft.ankle - body.hip_joint(s, pose)).length, a + c)
                k = 180.0 - math.degrees(math.acos(max(-1.0, min(1.0, (a * a + c * c - d * d) / (2 * a * c)))))
                flex[s].append(k)
                cell.append(f"{s} knee {k:5.1f} ankle {(ft.ankle.z - body.ankle[s].z) * 100:+5.1f} y {(body.hip[s].y - ft.ankle.y) * 100:+6.1f}")
            rows.append("  ".join(cell))
        z = [p.hips.z * 100 for p in poses]

        def pitch(p, bones):
            return sum(ang for b in bones for ax, ang in p.rot.get(b, []) if ax == X)

        mid = poses[len(poses) // 4]
        log(f"--- {name} ({dur:.2f} s): hips {min(z):+.1f} .. {max(z):+.1f} cm (mean {sum(z) / len(z):+.1f}); "
            f"knee L {min(flex['L'], default=0):.0f}-{max(flex['L'], default=0):.0f}; "
            f"trunk pitch {pitch(mid, ('hips', 'spine', 'chest')):.0f}, head {pitch(mid, ('hips', 'spine', 'chest', 'neck', 'head')):.0f}")
        for r in rows:
            log("   " + r)


def bake(arm, body, clips, log=print):
    """clips: {name: (sampler, duration, loop)} -> one baked action per clip (FK keys only)"""
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    arm.animation_data_create()
    _setup(arm, body)
    made = []
    for name, (f, dur, loop) in clips.items():
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        arm.animation_data.action = act
        poses = plan(body, f, dur, loop)
        n = len(poses) - 1
        for i, pose in enumerate(poses):
            _apply(arm, body, pose, 1 + i)
        made.append((act, n))
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    for act, n in made:
        arm.animation_data.action = act
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.nla.bake(frame_start=1, frame_end=n + 1, step=1, only_selected=False, visual_keying=True,
                         clear_constraints=False, use_current_action=True, bake_types={'POSE'})
    bpy.ops.object.mode_set(mode='OBJECT')
    _teardown(arm, [a for a, _ in made])
    arm.animation_data.action = bpy.data.actions[next(iter(clips))]
    log(f"motion: {', '.join(f'{a.name} {n / FPS:.2f}s' for a, n in made)}")
    return made


def _fcurves(act):
    try:
        return [(act.fcurves, fc) for fc in act.fcurves]
    except AttributeError:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out += [(cb.fcurves, fc) for fc in cb.fcurves]
        return out


def _teardown(arm, acts):
    for s, _ in SIDES:
        pb = arm.pose.bones["shin." + s]
        pb.constraints.remove(pb.constraints["mk_IK"])
        pb = arm.pose.bones["foot." + s]
        pb.constraints.remove(pb.constraints["mk_ROT"])
    for act in acts:
        for coll, fc in _fcurves(act):
            if "mk_" in fc.data_path or "constraints" in fc.data_path:
                coll.remove(fc)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for s, _ in SIDES:
        for n in ("mk_foot." + s, "mk_knee." + s):
            arm.data.edit_bones.remove(arm.data.edit_bones[n])
    bpy.ops.object.mode_set(mode='OBJECT')


# --- checks ---------------------------------------------------------------------------------------------------------

def check_feet(arm, act, speed, frames, contact):
    """planted-foot slide (m/s) and the straightest knee over a baked locomotion clip: contact(side, phase) says when
    a foot is down; on the ground the ankle must move back at `speed`"""
    arm.animation_data.action = act
    sc = bpy.context.scene
    worst, straight = 0.0, 180.0
    prev = {}
    body = check_feet.body
    for i in range(1, frames + 2):
        sc.frame_set(i)
        ph = (i - 1) / frames
        for s, _ in SIDES:
            M = arm.pose.bones["foot." + s].matrix @ arm.data.bones["foot." + s].matrix_local.inverted()
            heel, ball = M @ body.heel[s], M @ body.ball[s]
            a = (heel, ball, heel.z < ball.z)               # which point is on the ground
            th, sh = arm.pose.bones["thigh." + s], arm.pose.bones["shin." + s]
            ang = math.degrees((th.tail - th.head).angle(sh.tail - sh.head))
            straight = min(straight, ang)        # the least bend the knee ever has
            if s in prev and contact(s, ph) and contact(s, (i - 2) / frames) and prev[s][2] == a[2]:
                k = 0 if a[2] else 1                         # the same point, on the ground in both frames
                vy = (a[k].y - prev[s][k].y) * FPS
                worst = max(worst, abs(vy - speed))
            prev[s] = a
    return worst, straight
