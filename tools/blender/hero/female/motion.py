"""Her clips (feminine movement): the player clip set the game plays for the female body only.

  Idle      contrapposto: weight on the right leg, the right hip out and up, the left knee soft and turned in a
            little with the left foot ahead and turned out, shoulders tilted against the hips, head poised; light,
            quick breathing
  Walk      the game's default move (4.4 m/s): a light jog. Feet landing close to the line of travel (crossover),
            quicker shorter steps, a pronounced hip roll and sway, little shoulder turn, a high heel kick, arms
            carried close with the forearms swinging slightly across the body, hands relaxed
  Run       the sprint (8.6 m/s): the same character at speed, quick cadence, high heel recovery, a lighter lean
  Jump      knees together, the trailing leg tucked behind, toes pointed, arms lifting gracefully (held airborne)
  Slide     lead leg extended with the toes pointed, the other folded beneath, back arched, one hand brushing the
            ground, the other out for balance
  Death     she crumples: the knees fold and she twists down onto her side
  Fidget1-3 idle variations: the weight shifts onto the other hip and back, a look back over the right shoulder,
            a neck and shoulder stretch; each starts and ends on the idle pose
"""
import math
from mathutils import Vector
import gait
from gait import X, Y, Z, Pose, Foot, Gait, smooth, bump

TAU = 2 * math.pi


def heel_pitch(b):
    """degrees her foot stands heel-up in her heeled boots (boots.HEEL_F under the heel, pivoting on the ball)"""
    from boots import HEEL_F
    lever = (b.heel["L"] - b.ball["L"]).length
    return math.degrees(math.asin(min(.5, HEEL_F / lever)))


def heel_lift():
    """her heels raise her: the hips ride this much higher in every clip that stands her on them"""
    from boots import HEEL_F
    return HEEL_F * .95


WALK = dict(v=4.4, cadence=176, duty=.19, front=.52, width=.035, toe_out=4, lift=.08, kick=.22, strike=8, toeoff=36,
            swing_in=-.012, swing_pitch=-16)
RUN = dict(v=8.6, cadence=206, duty=.15, front=.48, width=.035, toe_out=3, lift=.13, kick=.42, strike=4, toeoff=44,
           swing_in=-.010, swing_pitch=-26)


def idle_pose(b, t, shift=0.0, hp=None):
    """the idle at time t (2.8 s breaths, a 5.6 s sway: the clip loops over 5.6 s). shift 0 = weight on the right leg, 1 = on the left"""
    p = Pose()
    br = math.sin(TAU * t / 2.8)
    w = 1 - 2 * smooth(shift)                    # +1 right leg loaded, -1 left
    free_l, free_r = max(0.0, w), max(0.0, -w)  # how relaxed each leg is
    sc = b.scale
    for s, sx in gait.SIDES:
        a = b.ankle[s]
        free = free_l if s == "L" else free_r
        x = sx * (.075 - .02 * free) * sc
        y = a.y - .07 * free * sc                # the free foot a little ahead
        yaw = 6 + 14 * free
        pitch = -7 * free - (heel_pitch(b) if hp is None else hp)   # on her heels; the free foot's heel a little higher
        p.feet[s] = Foot(b.planted(s, (x, y), pitch, yaw), pitch, yaw)
    p.hips = Vector((-.05 * w * sc + .003 * math.sin(TAU * t / 5.6), 0, heel_lift() - .004 - .0012 * (1 + br)))
    p.add("hips", (Y, 9 * w), (Z, -5 * w), (X, 3.0))            # the free side drops, the loaded hip turns back
    p.add("spine", (Y, -4 * w), (X, -2.5 - .6 * br))
    p.add("chest", (Y, -4.5 * w), (Z, 3 * w), (X, -2.0 - 1.0 * br))
    p.add("neck", (Y, 3 * w), (X, 1.5))
    p.add("head", (Y, 4 * w), (X, 1.0 + .4 * br), (Z, -3 * w))
    for s, sx in gait.SIDES:
        p.add("clavicle." + s, (Z, sx * -1.5))
        p.add("upperarm." + s, (Y, -sx * 3), (X, 2), (Z, sx * 6))
        p.add("forearm." + s, (b.elbow[s], -20))
        p.add("hand." + s, (b.elbow[s], -4), (Z, sx * 8))
        p.curl(s, ((8, 12, 6), (12, 18, 9), (16, 22, 12), (20, 26, 14)), 8)     # soft, graceful cascade
    p.knee_out = {"L": -.10 * free_l, "R": -.10 * free_r}     # the free knee turns in
    return p


def run_pose(b, g, t, lean, hip_yaw, hip_roll, sway, bob, drop, arm_sw, elbow, counter, cross):
    ph = g.phase(t)
    p = Pose()
    for s, _ in gait.SIDES:
        p.feet[s], _ = g.foot(s, ph)
    duty = g.p["duty"]
    step = (2 * ph) % 1.0
    p.hips = Vector((sway * math.cos(TAU * (ph - duty / 2)), 0,
                     heel_lift() - drop - bob * math.cos(TAU * (step - duty))))
    yaw = -hip_yaw * math.cos(TAU * ph)
    roll = -hip_roll * math.cos(TAU * (ph - duty / 2))
    p.add("hips", (Z, yaw), (Y, roll), (X, lean * .45))
    # the hips do the moving; the shoulders stay quiet and level, the head floats
    cy = -yaw * (1 + counter)
    p.add("spine", (Z, cy * .5), (Y, -roll * .75), (X, lean * .3))
    p.add("chest", (Z, cy * .5), (Y, -roll * .35), (X, lean * .2 - 2))
    p.add("neck", (Z, counter * yaw * .5), (Y, roll * .15), (X, -lean * .45))
    p.add("head", (Z, counter * yaw * .5), (X, -lean * .3))
    for s, sx in gait.SIDES:
        sw = arm_sw * -math.cos(TAU * ph + (0 if s == "L" else math.pi))
        p.add("upperarm." + s, (Y, -sx * 3), (X, -sw), (Z, sx * cross))           # forearms swing across a little
        p.add("forearm." + s, (b.elbow[s], -elbow - max(0.0, sw) * .3), (Z, sx * cross * .5))
        p.add("hand." + s, (b.elbow[s], -4), (Z, sx * (6 + .15 * sw)))
        p.curl(s, ((22, 34, 18), (30, 42, 22), (36, 46, 24), (40, 50, 26)), 16)   # relaxed, open hands
    p.knee_out = {"L": -.05, "R": -.05}
    return p


def clips(b):
    hp = heel_pitch(b)
    walk, run = Gait(b, **dict(WALK, heel=hp)), Gait(b, **dict(RUN, heel=hp))

    def Idle(t):
        return idle_pose(b, t)

    def Walk(t):
        return run_pose(b, walk, t, lean=8, hip_yaw=9, hip_roll=7, sway=.020, bob=.022, drop=.016,
                        arm_sw=26, elbow=78, counter=.2, cross=9)

    def Run(t):
        return run_pose(b, run, t, lean=13, hip_yaw=10, hip_roll=5.5, sway=.014, bob=.030, drop=.026,
                        arm_sw=46, elbow=84, counter=.25, cross=8)

    def Jump(t):
        k = smooth(t / .22)
        p = Pose()
        p.hips = Vector((0, 0, -.01 * k))
        p.add("hips", (Z, -6 * k), (X, 2 * k))
        p.add("spine", (X, 2 * k), (Z, 4 * k))
        p.add("chest", (X, -3 * k), (Z, -8 * k))
        p.add("head", (X, -4 * k))
        p.add("thigh.L", (Y, 4 * k), (X, -48 * k))
        p.add("shin.L", (X, 96 * k))
        p.add("foot.L", (X, 26 * k))
        p.add("thigh.R", (Y, -4 * k), (X, 12 * k))
        p.add("shin.R", (X, 82 * k))
        p.add("foot.R", (X, 32 * k))
        for s, sx in gait.SIDES:
            p.add("upperarm." + s, (Y, -sx * (4 + 8 * k)), (X, -34 * k), (Z, sx * 8 * k))
            p.add("forearm." + s, (b.elbow[s], -22 - 30 * k))
            p.add("hand." + s, (b.elbow[s], 8 * k))
        return p

    def Slide(t):
        v = math.sin(TAU * t / .8)
        p = Pose()
        p.hips = Vector((0, .02, -.60 * b.scale + .003 * v))
        p.add("hips", (X, -20), (Z, 6))
        p.add("thigh.L", (Y, -2), (X, -70))
        p.add("shin.L", (X, 4))
        p.add("foot.L", (X, 24))
        p.add("thigh.R", (Y, 4), (X, -22))
        p.add("shin.R", (X, 124))
        p.add("foot.R", (X, 28))
        p.add("spine", (X, -8), (Z, -4))
        p.add("chest", (X, -6), (Z, -4))
        p.add("head", (X, 16 + .6 * v), (Z, 4))
        p.add("upperarm.L", (Y, -32), (X, 22), (Z, 6))
        p.add("forearm.L", (b.elbow["L"], -6))
        p.add("hand.L", (Y, -14), (X, 12))
        p.add("upperarm.R", (Y, 18), (X, -34))
        p.add("forearm.R", (b.elbow["R"], -30))
        p.add("hand.R", (b.elbow["R"], 6))
        return p

    def Death(t):
        k = smooth(min(1.0, t / .8))                         # knees fold, she twists down onto her right side
        fold = bump(t, .3, .32)
        p = Pose()
        p.hips = Vector((-.30 * k * b.scale, .10 * k, -.84 * k * b.scale - .05 * fold))
        p.add("hips", (Y, -78 * k), (X, -20 * k), (Z, 18 * k))
        p.add("thigh.L", (Y, 6 * k), (X, -38 * k - 30 * fold))
        p.add("shin.L", (X, 58 * k + 40 * fold))
        p.add("foot.L", (X, 20 * k))
        p.add("thigh.R", (X, -24 * k - 30 * fold))
        p.add("shin.R", (X, 36 * k + 50 * fold))
        p.add("foot.R", (X, 20 * k))
        p.add("spine", (Y, 8 * k), (Z, -10 * k))
        p.add("chest", (Y, 6 * k), (Z, -8 * k))
        p.add("head", (Y, 16 * k), (Z, -20 * k))
        p.add("upperarm.L", (Y, -20 * k), (X, -36 * k))
        p.add("forearm.L", (b.elbow["L"], -48 * k))
        p.add("upperarm.R", (Y, 34 * k), (X, -10 * k))
        p.add("forearm.R", (b.elbow["R"], -20 * k))
        return p

    def fidget(dur, extra, shift=None):
        def f(t):
            p = idle_pose(b, t, shift(t) if shift else 0.0)
            e = smooth(t / .6) * smooth((dur - t) / .6)
            extra(p, t, e)
            return p
        return f

    def none(p, t, e):
        pass

    def weight(t):                                           # onto the left hip, settle, back onto the right
        return smooth((t - .5) / 1.1) - smooth((t - 3.3) / 1.1)

    def look_back(p, t, e):                                  # a glance back over the right shoulder
        turn = -38 * bump(t, 2.1, 1.3)
        p.add("spine", (Z, turn * .2 * e))
        p.add("chest", (Z, turn * .3 * e))
        p.add("neck", (Z, turn * .25 * e), (Y, -4 * e * bump(t, 2.1, 1.3)))
        p.add("head", (Z, turn * .35 * e), (Y, -5 * e * bump(t, 2.1, 1.3)))

    def stretch(p, t, e):                                    # the head tips to each side, shoulders lift and drop
        a = math.sin(TAU * (t - .7) / 2.6) if .7 < t < 3.3 else 0.0
        p.add("neck", (Y, -8 * a * e))
        p.add("head", (Y, -10 * a * e), (X, -3 * e))
        lift = bump(t, 2.0, 1.2) * e
        for s, sx in gait.SIDES:
            p.add("clavicle." + s, (Y, sx * -7 * lift))
        p.add("chest", (X, -5 * lift))
        p.hips.z += .004 * lift

    return {"Idle": (Idle, 5.6, True), "Walk": (Walk, walk.T, True), "Run": (Run, run.T, True),
            "Jump": (Jump, .5, False), "Slide": (Slide, .8, True), "Death": (Death, 1.2, False),
            "Fidget1": (fidget(4.4, none, weight), 4.4, False), "Fidget2": (fidget(4.2, look_back), 4.2, False),
            "Fidget3": (fidget(4.0, stretch), 4.0, False)}, (walk, run)
