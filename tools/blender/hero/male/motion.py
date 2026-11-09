"""His clips (masculine movement): the player clip set the game plays for the male body only.

  Idle      squared, wide base (feet past shoulder width, toes out), chest up, shoulders back, weight even; slow,
            deep breathing from the chest, a slight settle of the knees
  Walk      the game's default move (4.4 m/s): a purposeful jog. Wide track, toes out, a firm heel strike with a
            dip, little hip roll or sway, strong shoulder counter-rotation, arms pumping from the shoulder with the
            elbows out a little, fists loose
  Run       the sprint (8.6 m/s): driving knee lift, a long powerful stride, a deep forward lean, big arm drive
  Jump      a powerful tuck, knees apart, arms out for balance (held while airborne)
  Slide     aggressive: lead leg out, the other folded under, leaning back, the left hand trailing on the ground
  Death     the legs go, he drops heavily onto his back, arms thrown out
  Fidget1-3 idle variations the game slips in while he stands: a neck stretch (ear to each shoulder), a scan of the
            area (chest and head turn left, then right), a shoulder roll with a deep breath; each starts and ends on
            the idle pose
"""
import math
from mathutils import Vector
import gait
from gait import X, Y, Z, Pose, Foot, Gait, smooth, bump

TAU = 2 * math.pi
WALK = dict(v=4.4, cadence=162, duty=.21, front=.48, width=.10, toe_out=10, lift=.09, kick=.16, strike=11, toeoff=34,
            swing_in=.004, swing_pitch=-14)
RUN = dict(v=8.6, cadence=196, duty=.16, front=.45, width=.10, toe_out=7, lift=.15, kick=.34, strike=5, toeoff=42,
           swing_in=.004, swing_pitch=-22)


def stand_feet(b, p, width, toe_out, fwd=(0.0, 0.0)):
    for s, sx in gait.SIDES:
        a = b.ankle[s]
        p.feet[s] = Foot(b.planted(s, (sx * width, a.y + (fwd[0] if s == "L" else fwd[1])), 0.0, toe_out), 0.0, toe_out)


def idle_pose(b, t):
    """the idle at time t (3.6 s breaths, a 7.2 s sway: the clip loops over 7.2 s); the fidgets add to this"""
    p = Pose()
    br = math.sin(TAU * t / 3.6)
    stand_feet(b, p, .175 * b.scale, 14)
    p.hips = Vector((.004 * math.sin(TAU * t / 7.2), 0, -.004 - .0015 * (1 + br)))
    p.add("hips", (X, 2.0))
    p.add("spine", (X, -1.5 - .8 * br))
    p.add("chest", (X, -3.0 - 1.4 * br))
    p.add("neck", (X, 2.0 + .6 * br))
    p.add("head", (X, 1.0 + .5 * br))
    for s, sx in gait.SIDES:
        p.add("clavicle." + s, (Z, sx * -3.0), (Y, sx * -1.0 * (1 + br) * .5))   # shoulders back, rising with the breath
        p.add("upperarm." + s, (Y, -sx * 9), (X, 4))
        p.add("forearm." + s, (b.elbow[s], -16))
        p.add("hand." + s, (b.elbow[s], -6))
        p.curl(s, ((14, 24, 12), (18, 28, 14), (22, 30, 16), (26, 32, 18)), 12)   # heavy, relaxed hands
    p.knee_out = {"L": .08, "R": .08}
    return p


def run_pose(b, g, t, lean, hip_yaw, hip_roll, sway, bob, drop, arm_sw, elbow, counter, abd):
    ph = g.phase(t)
    p = Pose()
    for s, _ in gait.SIDES:
        p.feet[s], _ = g.foot(s, ph)
    duty = g.p["duty"]
    step = (2 * ph) % 1.0
    p.hips = Vector((sway * math.cos(TAU * (ph - duty / 2)), 0,
                     -drop - bob * math.cos(TAU * (step - duty))))
    yaw = -hip_yaw * math.cos(TAU * ph)
    roll = -hip_roll * math.cos(TAU * (ph - duty / 2))
    # the dip at each heel strike (firm, heavy steps)
    p.hips.z -= .012 * bump(step, .06, .08)
    p.add("hips", (Z, yaw), (Y, roll), (X, lean * .45))
    # shoulders turn against the hips (strongly) and the head stays on the line of travel
    cy = -yaw * (1 + counter)
    p.add("spine", (Z, cy * .45), (Y, -roll * .6), (X, lean * .3))
    p.add("chest", (Z, cy * .55), (Y, -roll * .3), (X, lean * .25))
    p.add("neck", (Z, counter * yaw * .5), (X, -lean * .45))
    p.add("head", (Z, counter * yaw * .5), (X, -lean * .3))
    for s, sx in gait.SIDES:
        sw = arm_sw * -math.cos(TAU * ph + (0 if s == "L" else math.pi))       # left arm back at left contact
        p.add("clavicle." + s, (Z, sx * sw * .12))
        p.add("upperarm." + s, (Y, -sx * abd), (X, -sw))
        p.add("forearm." + s, (b.elbow[s], -elbow - max(0.0, sw) * .25))
        p.add("hand." + s, (b.elbow[s], -10))
        p.curl(s, (62, 82, 46), 34)                          # loose fists
    p.knee_out = {"L": .10, "R": .10}
    return p


def clips(b):
    walk, run = Gait(b, **WALK), Gait(b, **RUN)

    def Idle(t):
        return idle_pose(b, t)

    def Walk(t):
        return run_pose(b, walk, t, lean=11, hip_yaw=6, hip_roll=2.5, sway=.008, bob=.028, drop=.018,
                        arm_sw=34, elbow=82, counter=.55, abd=13)

    def Run(t):
        return run_pose(b, run, t, lean=17, hip_yaw=8, hip_roll=2.5, sway=.006, bob=.036, drop=.030,
                        arm_sw=58, elbow=88, counter=.6, abd=11)

    def Jump(t):
        k = smooth(t / .22)                                   # take-off extension -> tuck, then held
        p = Pose()
        p.hips = Vector((0, 0, -.02 * k))
        p.add("hips", (X, 6 * k))
        p.add("spine", (X, 8 * k))
        p.add("chest", (X, 4 * k))
        p.add("head", (X, -8 * k))
        p.add("thigh.L", (Y, -8 * k), (X, -62 * k))
        p.add("shin.L", (X, 92 * k))
        p.add("foot.L", (X, -10 * k))
        p.add("thigh.R", (Y, 8 * k), (X, -14 * k))
        p.add("shin.R", (X, 58 * k))
        p.add("foot.R", (X, 14 * k))
        for s, sx in gait.SIDES:
            p.add("clavicle." + s, (Y, sx * -6 * k))
            p.add("upperarm." + s, (Y, -sx * (10 + 18 * k)), (X, -24 * k))
            p.add("forearm." + s, (b.elbow[s], -20 - 30 * k))
        return p

    def Slide(t):
        v = math.sin(TAU * t / .8)
        p = Pose()
        p.hips = Vector((0, .02, -.62 * b.scale + .004 * v))
        p.add("hips", (X, -26), (Z, 8))
        p.add("thigh.L", (Y, -5), (X, -64))
        p.add("shin.L", (X, 8))
        p.add("foot.L", (X, -14))
        p.add("thigh.R", (Y, 10), (X, -30))
        p.add("shin.R", (X, 118))
        p.add("foot.R", (X, 22))
        p.add("spine", (X, -4), (Z, -5))
        p.add("chest", (X, -2), (Z, -6))
        p.add("head", (X, 24 + .8 * v), (Z, 6))
        p.add("upperarm.L", (Y, -40), (X, 30))
        p.add("forearm.L", (b.elbow["L"], -10))
        p.add("hand.L", (Y, -12))
        p.add("upperarm.R", (X, -22), (Y, 30))
        p.add("forearm.R", (b.elbow["R"], -28))
        p.add("hand.R", (b.elbow["R"], -10))
        return p

    def Death(t):
        k = smooth(min(1.0, t / .75))                        # legs give, he drops backward
        knees = bump(t, .25, .28)
        p = Pose()
        p.hips = Vector((0, .38 * k, -.86 * k * b.scale - .06 * knees))
        p.add("hips", (X, -84 * k))
        p.add("thigh.L", (X, -30 * k - 35 * knees))
        p.add("shin.L", (X, 34 * k + 60 * knees))
        p.add("thigh.R", (Y, 6 * k), (X, -8 * k - 30 * knees))
        p.add("shin.R", (X, 14 * k + 55 * knees))
        p.add("spine", (X, -6 * k))
        p.add("head", (X, -24 * k), (Z, 28 * k))
        for s, sx in gait.SIDES:
            p.add("upperarm." + s, (Y, -sx * 62 * k), (X, -24 * k))
            p.add("forearm." + s, (b.elbow[s], -32 * k))
        return p

    def fidget(dur, extra):
        def f(t):
            p = idle_pose(b, t)
            e = smooth(t / .6) * smooth((dur - t) / .6)       # in and out of the idle pose
            extra(p, t, e)
            return p
        return f

    def neck(p, t, e):                                       # ear to the right shoulder, then the left, roll out
        a = math.sin(TAU * (t - .6) / 2.8) if .6 < t < 3.4 else 0.0
        p.add("neck", (Y, -10 * a * e), (X, 3 * e * abs(a)))
        p.add("head", (Y, -14 * a * e))
        for s, sx in gait.SIDES:
            p.add("clavicle." + s, (Y, sx * -5 * e * bump(t, 2.0, 1.4)))

    def scan(p, t, e):                                       # check the area: left, hold, right, back
        turn = 32 * (bump(t, 1.4, 1.0) - bump(t, 3.0, 1.0))
        p.add("spine", (Z, turn * .2 * e))
        p.add("chest", (Z, turn * .3 * e))
        p.add("neck", (Z, turn * .25 * e))
        p.add("head", (Z, turn * .35 * e), (X, -3 * e))
        p.hips.x += .012 * (bump(t, 1.4, 1.0) - bump(t, 3.0, 1.0)) * e

    def shoulders(p, t, e):                                  # two slow shoulder rolls with a deep breath
        r = TAU * (t - .5) / 1.5
        on = 1.0 if .5 < t < 3.5 else 0.0
        for s, sx in gait.SIDES:
            p.add("clavicle." + s, (Y, sx * -9 * on * e * max(0.0, math.sin(r))), (Z, sx * 7 * on * e * math.cos(r)))
        p.add("chest", (X, -4 * e * bump(t, 2.0, 1.6)))
        p.hips.z += .006 * e * bump(t, 2.0, 1.6)

    return {"Idle": (Idle, 7.2, True), "Walk": (Walk, walk.T, True), "Run": (Run, run.T, True),
            "Jump": (Jump, .5, False), "Slide": (Slide, .8, True), "Death": (Death, 1.2, False),
            "Fidget1": (fidget(4.0, neck), 4.0, False), "Fidget2": (fidget(4.6, scan), 4.6, False),
            "Fidget3": (fidget(4.0, shoulders), 4.0, False)}, (walk, run)
