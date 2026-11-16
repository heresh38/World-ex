"""Her clips (feminine movement): the player clip set the game plays for the female body only.

  Idle      contrapposto: weight on the right leg, the right hip out and up, the left knee soft and turned in a
            little with the left foot ahead and turned out, shoulders tilted against the hips, head poised; light,
            quick breathing
  Stroll    the slow move (1.5 m/s: a light stick, aiming, crouched): an easy, swinging walk on one line, the hips
            rolling over each step, shoulders quiet, the arms loose and close with soft elbows and trailing wrists
  Crouch    crouched and still: the left foot ahead, the right back on its toes, knees close, chest folded, head up
  CrouchWalk  the crouched move (2.7 m/s): hips low the whole way round, short quick steps, a foot always down
  Walk      the game's default move (4.4 m/s): a light, upright run. Feet landing close to the line of travel (crossover),
            quick short steps, the heel recovering high, a pronounced hip roll and sway, little shoulder turn, arms
            carried close with the forearms swinging across the body, hands relaxed and a beat behind
  Run       the sprint (8.6 m/s): the same character at speed, quick cadence, heels to the seat, a lighter lean
  Jump      three poses the game moves between by how fast she is rising or falling: springing off the toes (arms
            lifting), tucked at the top (knees together, the trailing leg behind), reaching down with pointed toes
  Land      the landing after a fall: knees together, she folds low and light, one hand toward the ground, and rises
            onto her standing leg
  Vault     over a low wall off the right hand: the reach, both legs swept through to the left together, the lead
            leg reaching down, away in stride
  Mantle    onto a ledge: the reach, the catch with a toe on the face, the press with the knee coming up onto the top,
            the step up
  Climb     a high ledge: the hang at full stretch, the toes walking up, the pull, then the press, the knee and the
            step up
  Slide     lead leg extended with the toes pointed, the other folded beneath, back arched, one hand brushing the
            ground, the other out for balance
  Death     she crumples: the knees fold and she twists down onto her side
  Throw / Strike / Brace / Slam   the kit's four abilities (the gun is put away while one plays): an overarm throw
            off the right hand with the hips leading (it leaves at 0.2 s); a straight blow behind a short step (it
            lands at 0.16 s); braced behind her forearms; a blow into the ground from full height, down on a lunge
            with the right fist ahead of the front foot (it lands at 0.33 s)
  Fidget1-3 idle variations: the weight shifts onto the other hip and back, a look back over the right shoulder,
            a neck and shoulder stretch; each starts and ends on the idle pose

Vault, Mantle and Climb are one second long and are not played by the clock: the game shows the pose for how far
through the move the body is (and puts the hands on the real edge while it is in reach).
"""
import math
from mathutils import Vector
import gait
from gait import X, Y, Z, Pose, Foot, Gait, Track, smooth, bump, locomote

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


# --- the three gaits: where the feet go (gait.Gait) and how the body rides over them (gait.locomote) -----------------
SOFT = ((22, 34, 18), (30, 42, 22), (36, 46, 24), (40, 50, 26))        # relaxed, open hands
OPEN = ((6, 10, 5), (9, 13, 6), (12, 16, 8), (15, 19, 9))              # fingers long, a soft fan
GRIP = ((38, 56, 28),) * 4
STROLL = dict(v=1.5, cadence=134, duty=.60, front=.37, width=.028, toe_out=5, lift=.03, kick=.03, strike=13, toeoff=50,
              swing_in=-.010, swing_pitch=-8, retract=.22, peak=.36)
STROLL_BODY = dict(lean=2.5, hip_yaw=7, hip_roll=5.5, sway=.016, bob=-.011, bob2=.002, drop=0.0, dip=.0, counter=.25, nod=.6,
                   lag=dict(spine=.03, chest=.06, head=.08, arm=.04, forearm=.09, hand=.14),
                   arm=17, arm_bias=-2, arm_h2=.08, abd=3, abd_back=1, abd_fwd=2, cross=8, elbow=20, elbow_fwd=16, elbow_back=6,
                   wrist=4, wrist_lag=12, hand_turn=8, clav=1.5, curl=((8, 12, 6), (12, 18, 9), (16, 22, 12), (20, 26, 14)), thumb=8,
                   knee_out=-.012, asym=.94, asym_ph=.015)
# The run: upright and long: the foot lands just ahead of the hip on a nearly straight leg, the rear leg drives straight
# behind, the heel comes half way up in recovery. Hers stays on one line with the hips rolling a little.
WALK = dict(v=4.4, cadence=172, duty=.19, front=.22, width=.030, toe_out=3, lift=.08, kick=.20, strike=6, toeoff=48,
            swing_in=-.012, swing_pitch=-16, retract=.34, peak=.42, stance=2)
WALK_BODY = dict(lean=5, hip_yaw=8, hip_roll=3.5, sway=.006, bob=.010, bob2=.004, drop=-.020, dip=0.0, counter=.4, nod=1.2, chest_up=3,
                 lag=dict(spine=.03, chest=.05, head=.07, arm=.03, forearm=.08, hand=.13),
                 arm=40, arm_bias=-12, arm_h2=.16, abd=3, abd_back=4, abd_fwd=1, cross=20, elbow=80, elbow_fwd=14, elbow_back=24,
                 wrist=4, wrist_lag=14, hand_turn=6, clav=4, clav_up=1, curl=SOFT, thumb=16,
                 knee_out=-.012, asym=.95, asym_ph=.012, asym_elbow=1.04)
RUN = dict(v=8.6, cadence=244, duty=.16, front=.24, width=.030, toe_out=2, lift=.10, kick=.33, strike=-4, toeoff=50,
           swing_in=-.010, swing_pitch=-26, retract=.36, peak=.42, stance=14)
RUN_BODY = dict(lean=10, hip_yaw=9, hip_roll=3.0, sway=.004, bob=.015, bob2=.004, drop=-.016, dip=0.0, counter=.45, nod=1.6, chest_up=2,
                lag=dict(spine=.03, chest=.05, head=.07, arm=.03, forearm=.08, hand=.13),
                arm=56, arm_bias=-8, arm_h2=.20, abd=3, abd_back=6, abd_fwd=1, cross=20, elbow=86, elbow_fwd=10, elbow_back=34,
                wrist=2, wrist_lag=16, hand_turn=6, clav=7, clav_up=2, curl=SOFT, thumb=16,
                knee_out=-.012, asym=.96, asym_ph=.010, asym_elbow=1.03)
# Crouched: the hips low between bent legs the whole way round (authored down there: nothing is bent at runtime), short
# quick steps with a foot always on the ground, knees close, the chest folded forward, the head up.
CROUCH = dict(v=2.7, cadence=244, duty=.44, front=.48, width=.060, toe_out=6, lift=.05, kick=.02, strike=3, toeoff=22,
              swing_in=0.0, swing_pitch=-6, retract=.18, peak=.42)
CROUCH_BODY = dict(lean=32, hip_yaw=6, hip_roll=3.0, sway=.010, bob=.007, bob2=0.0, drop=.28, dip=.003, counter=.4, nod=.8, chest_up=0,
                   lag=dict(spine=.03, chest=.05, head=.07, arm=.03, forearm=.08, hand=.13),
                   arm=8, arm_bias=6, arm_h2=0.0, abd=5, abd_back=2, abd_fwd=1, cross=14, elbow=74, elbow_fwd=6, elbow_back=6,
                   wrist=4, wrist_lag=6, hand_turn=6, clav=2, curl=SOFT, thumb=16, knee_out=.03, asym=.96, asym_ph=.012)


def crouch_pose(b, t, hp, up):
    """crouched and still: the left foot ahead, the right back on its toes, knees close, the weight between them"""
    p = Pose()
    br = math.sin(TAU * t / 2.8)
    for s, sx in gait.SIDES:
        a = b.ankle[s]
        fwd = (-.13 if s == "L" else .10) * b.scale
        pitch = -hp if s == "L" else -hp - 22.0
        p.feet[s] = Foot(b.planted(s, (sx * .085 * b.scale, a.y + fwd), pitch, 8), pitch, 8)
    p.hips = Vector((.004 * math.sin(TAU * t / 5.6), .02, up - .29 * b.scale - .002 * (1 + br)))
    p.add("hips", (X, 14))
    p.add("spine", (X, 10 - .6 * br))
    p.add("chest", (X, 6 - 1.0 * br))
    p.add("neck", (X, -11))
    p.add("head", (X, -14 + .4 * br), (Z, 1.2 * math.sin(TAU * t / 5.6 + .8)))
    for s, sx in gait.SIDES:
        p.add("upperarm." + s, (Y, -sx * 5), (X, -12), (Z, sx * 10))
        p.add("forearm." + s, (b.elbow[s], -60))
        p.add("hand." + s, (b.elbow[s], -4), (Z, sx * 8))
        p.curl(s, SOFT, 16)
    p.knee_out = {"L": .03, "R": .05}
    return p


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


def arms(b, p, side, fwd, out, elbow, turn=0.0, hand=-4.0, curl=SOFT, thumb=16):
    """one arm: fwd = degrees raised forward (negative = behind), out = degrees out from the body, elbow = bend,
    turn = the upper arm turned in (the forearm across the body)"""
    sx = 1 if side == "L" else -1
    p.add("upperarm." + side, (Y, -sx * out), (X, -fwd), (Z, sx * turn))
    p.add("forearm." + side, (b.elbow[side], -elbow))
    p.add("hand." + side, (b.elbow[side], hand), (Z, sx * 8))
    p.curl(side, curl, thumb)


def leg(p, side, hip, knee, foot=30.0, out=0.0):
    """one leg off the ground: hip = degrees the thigh is raised forward (negative = behind), knee = bend,
    foot = toes pointed (+) / up (-), out = knee out from the middle (negative = turned in)"""
    sx = 1 if side == "L" else -1
    p.add("thigh." + side, (Y, -sx * out), (X, -hip))
    p.add("shin." + side, (X, knee))
    p.add("foot." + side, (X, foot))


def trunk(p, hips=0.0, spine=0.0, chest=0.0, head=0.0, roll=0.0, turn=0.0, z=0.0, y=0.0, x=0.0):
    """pitch forward (+) of hips / spine / chest, the head against it; roll (+ = to her left) and turn (+ = left) of
    the hips, undone above; the hips moved by (x, y, z) metres"""
    p.hips = Vector((x, y, z))
    p.add("hips", (Z, turn), (Y, roll), (X, hips))
    p.add("spine", (Z, -turn * .4), (Y, -roll * .4), (X, spine))
    p.add("chest", (Z, -turn * .4), (Y, -roll * .35), (X, chest))
    p.add("neck", (X, head * .4))
    p.add("head", (Y, -roll * .2), (X, head * .6))


def clips(b):
    hp = heel_pitch(b)
    up = heel_lift()
    stroll, walk, run = Gait(b, **dict(STROLL, heel=hp)), Gait(b, **dict(WALK, heel=hp)), Gait(b, **dict(RUN, heel=hp))
    crouch = Gait(b, **dict(CROUCH, heel=hp))
    crouch_body = dict(CROUCH_BODY, drop=CROUCH_BODY["drop"] * b.scale)

    def Crouch(t):
        return crouch_pose(b, t, hp, up)

    def CrouchWalk(t):
        return locomote(b, crouch, t, crouch_body, up)

    def Idle(t):
        return idle_pose(b, t)

    def Stroll(t):
        return locomote(b, stroll, t, STROLL_BODY, up)

    def Walk(t):
        return locomote(b, walk, t, WALK_BODY, up)

    def Run(t):
        return locomote(b, run, t, RUN_BODY, up)

    # --- the air: three poses, read by the game by the rise and the fall --------------------------------------------
    def takeoff():
        p = Pose()
        trunk(p, hips=0, spine=-4, chest=-7, head=4, z=.01)
        leg(p, "L", -4, 6, 38)
        leg(p, "R", 8, 16, 36)
        arms(b, p, "L", 12, 10, 40, turn=4)                      # lifting with the spring
        arms(b, p, "R", 4, 8, 46, turn=4)
        return p

    def tuck():
        p = Pose()
        trunk(p, hips=2, spine=2, chest=-3, head=-5, turn=-6, z=-.01)
        leg(p, "L", 50, 98, 26, -4)                             # knees together, the trailing leg tucked behind
        leg(p, "R", -12, 84, 32, -4)
        arms(b, p, "L", 34, 12, 54, turn=8, hand=8, curl=OPEN, thumb=6)
        arms(b, p, "R", 26, 16, 48, turn=8, hand=8, curl=OPEN, thumb=6)
        return p

    def reach():
        p = Pose()
        trunk(p, hips=3, spine=3, chest=-1, head=-4)
        leg(p, "L", 18, 24, 34, -2)                             # toes first
        leg(p, "R", 4, 20, 36, -2)
        arms(b, p, "L", 6, 44, 22, hand=10, curl=OPEN, thumb=6)
        arms(b, p, "R", 12, 38, 26, hand=10, curl=OPEN, thumb=6)
        return p

    jump = Track([(0.0, takeoff()), (.22, tuck()), (.5, reach())])

    def Jump(t):
        return jump.at(t, dict(arm=.03, forearm=.05, hand=.08, head=.02))

    def Land(t):
        def down(z, hips, spine, chest, head, la, ra, knees):
            p = Pose()
            for s, sx in gait.SIDES:
                a = b.ankle[s]
                p.feet[s] = Foot(b.planted(s, (sx * .07 * b.scale, a.y + (-.05 if s == "L" else .03) * b.scale), -hp, 8), -hp, 8)
            trunk(p, hips=hips, spine=spine, chest=chest, head=head, z=up + z)
            arms(b, p, "L", *la)
            arms(b, p, "R", *ra)
            p.knee_out = {"L": knees, "R": knees}
            return p
        land = Track([(0.0, down(-.04, 4, 4, 0, -4, (6, 44, 22), (12, 38, 26), -.02)),
                      (.10, down(-.25, 22, 16, 8, -22, (44, 10, 24), (10, 30, 30), -.06)),      # low, a hand toward the ground
                      (.28, down(-.09, 8, 4, -1, -6, (14, 8, 22), (6, 14, 24), -.03)),
                      (.5, idle_pose(b, 0.0))], ease=smooth)
        return land.at(t, dict(chest=.02, head=.04, arm=.03, forearm=.06, hand=.09))

    def Stop(t):
        """braking out of a run: the left foot set down ahead, the weight back and low, arms out for balance, then up"""
        def brake(z, back, hips, chest, la, ra):
            p = Pose()
            for s, sx in gait.SIDES:
                a = b.ankle[s]
                ahead = (-.12 if s == "L" else .06) * b.scale
                pitch = -hp + (4.0 if s == "L" else -12.0)
                p.feet[s] = Foot(b.planted(s, (sx * .08 * b.scale, a.y + ahead), pitch, 8), pitch, 8)
            trunk(p, hips=hips, spine=hips * .5, chest=chest, head=-(hips * 1.5 + chest) * .6, z=up + z, y=back)
            arms(b, p, "L", *la)
            arms(b, p, "R", *ra)
            p.knee_out = {"L": -.01, "R": .01}
            return p
        stop = Track([(0.0, brake(-.05, .045, -8, -4, (20, 26, 40), (14, 30, 36))), (.13, brake(-.09, .06, -2, 3, (10, 18, 30), (6, 20, 28))),
                      (.30, brake(-.035, .025, 2, -1, (4, 10, 22), (2, 10, 22))), (.5, idle_pose(b, 0.0))], ease=smooth)
        return stop.at(t, dict(chest=.02, head=.04, arm=.03, forearm=.06, hand=.09))

    # --- over and onto things: poses by how far through the move the body is ----------------------------------------
    def Vault(t):
        def run_in():
            p = Pose()
            trunk(p, hips=11, spine=9, chest=5, head=-14)
            leg(p, "L", 40, 66, 20)
            leg(p, "R", -18, 34, 36)
            arms(b, p, "R", 70, 6, 16, hand=-20, curl=OPEN, thumb=6)
            arms(b, p, "L", -28, 6, 60)
            return p

        def over():
            p = Pose()
            trunk(p, hips=18, spine=8, chest=3, head=-16, roll=-44, turn=24, z=-.18, x=.05)
            leg(p, "L", 84, 96, 34, -6)                             # both legs through together, toes pointed
            leg(p, "R", 76, 100, 36, -8)
            arms(b, p, "R", 20, 18, 8, hand=-40, curl=OPEN, thumb=6)
            arms(b, p, "L", 10, 78, 20, hand=10, curl=OPEN, thumb=6)
            return p

        def clearing():
            p = Pose()
            trunk(p, hips=10, spine=5, chest=0, head=-8, roll=-18, turn=8, z=-.08)
            leg(p, "L", 58, 28, 30)
            leg(p, "R", 34, 86, 36)
            arms(b, p, "R", -34, 10, 20)
            arms(b, p, "L", 30, 16, 56, turn=10)
            return p

        def away():
            p = Pose()
            trunk(p, hips=5, spine=4, chest=1, head=-6, z=-.02)
            leg(p, "L", 30, 16, 10)
            leg(p, "R", -20, 60, 36)
            arms(b, p, "R", 18, 3, 84, turn=14)
            arms(b, p, "L", -40, 6, 58)
            return p
        return Track([(0.0, run_in()), (.36, over()), (.68, clearing()), (1.0, away())]).at(t, dict(chest=.02, head=.04, forearm=.04, hand=.07))

    def press():
        p = Pose()
        trunk(p, hips=15, spine=10, chest=4, head=-20)
        leg(p, "R", 104, 124, 10, 10)
        leg(p, "L", -8, 10, 38)
        for s in "LR":
            arms(b, p, s, -10, 12, 16, hand=-50, curl=OPEN, thumb=6)
        return p

    def step_up():
        p = Pose()
        trunk(p, hips=18, spine=9, chest=2, head=-16, z=-.03)
        leg(p, "R", 88, 98, 0, 6)
        leg(p, "L", 20, 56, 30)
        for s in "LR":
            arms(b, p, s, -24, 8, 26)
        return p

    def stand():
        p = Pose()
        trunk(p, hips=6, spine=2, chest=-2, head=-3, z=-.03)
        leg(p, "L", 14, 24, 6, -2)
        leg(p, "R", 12, 22, 6, -2)
        for s in "LR":
            arms(b, p, s, -2, 3, 20)
        return p

    def Mantle(t):
        def reach_up():
            p = Pose()
            trunk(p, hips=-2, spine=-5, chest=-9, head=-16, z=.01)
            leg(p, "L", -6, 8, 38)
            leg(p, "R", 12, 22, 36)
            for s in "LR":
                arms(b, p, s, 124, 8, 20, hand=-10, curl=OPEN, thumb=6)
            return p

        def catch():
            p = Pose()
            trunk(p, hips=5, spine=5, chest=0, head=-12)
            leg(p, "R", 58, 88, -10, 2)                            # a toe on the face
            leg(p, "L", 6, 28, 34)
            for s in "LR":
                arms(b, p, s, 66, 10, 72, hand=-40, curl=OPEN, thumb=6)
            return p
        return Track([(0.0, reach_up()), (.30, catch()), (.58, press()), (.82, step_up()), (1.0, stand())]).at(t, dict(chest=.02, head=.03))

    def Climb(t):
        def hang():
            p = Pose()
            trunk(p, hips=-5, spine=-5, chest=-5, head=-24)
            leg(p, "L", 4, 16, 38)
            leg(p, "R", 12, 30, 38, -2)
            for s in "LR":
                arms(b, p, s, 170, 6, 5, hand=-10, curl=GRIP, thumb=18)
            return p

        def walk_up():
            p = Pose()
            trunk(p, hips=3, spine=-1, chest=-3, head=-22)
            leg(p, "R", 54, 72, -8, 2)
            leg(p, "L", 20, 44, 30)
            for s in "LR":
                arms(b, p, s, 152, 8, 34, hand=-14, curl=GRIP, thumb=18)
            return p

        def pull():
            p = Pose()
            trunk(p, hips=8, spine=6, chest=2, head=-14)
            leg(p, "L", 66, 98, 30, -3)
            leg(p, "R", 82, 102, 24, -3)
            for s in "LR":
                arms(b, p, s, 74, 16, 118, hand=-30, curl=GRIP, thumb=18)
            return p
        return Track([(0.0, hang()), (.26, walk_up()), (.54, pull()), (.76, press()), (.90, step_up()), (1.0, stand())]).at(t, dict(chest=.02, head=.03))

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

    # --- the kit's abilities: the body's own clips (the gun is put away while one plays). Hers are quicker and
    # narrower than his: the hips turn first and far, the feet stay close under her, the free arm stays near the body.
    HIT = dict(chest=.02, head=.035, arm=.015, forearm=.04, hand=.065)

    def act(z=0.0, y=0.0, hips=0.0, spine=0.0, chest=0.0, head=0.0, twist=0.0, turn=0.0, width=.075, toe=8, fwd=(0.0, 0.0),
            pitch=(0.0, 0.0), L=(-2, 3, 20), R=(-2, 3, 20), turnL=0.0, turnR=0.0, curlL=SOFT, curlR=SOFT, knee=0.0):
        """a standing pose on her heels: the hips moved by (y forward is negative, z) and turned (turn + = left), the
        chest twisted on against them (twist), each foot moved along (fwd) and pitched (pitch, - = heel up), each arm
        as (raised forward, out, elbow)"""
        p = Pose()
        for s, sx in gait.SIDES:
            a = b.ankle[s]
            i = 0 if s == "L" else 1
            ft = -hp + pitch[i]
            p.feet[s] = Foot(b.planted(s, (sx * width * b.scale, a.y + fwd[i] * b.scale), ft, toe), ft, toe)
        trunk(p, hips=hips, spine=spine, chest=chest, head=head, turn=turn, z=up + z, y=y)
        p.add("spine", (Z, twist * .35))
        p.add("chest", (Z, twist * .65))
        p.add("neck", (Z, -(twist + turn * .2) * .35))    # the eyes stay on where it is going
        p.add("head", (Z, -(twist + turn * .2) * .35))
        arms(b, p, "L", L[0], L[1], L[2], turn=turnL, curl=curlL)
        arms(b, p, "R", R[0], R[1], R[2], turn=turnR, curl=curlR)
        p.knee_out = {"L": knee, "R": knee}
        return p

    def Throw(t):
        step = (-.09, .05)
        throw = Track([(0.0, idle_pose(b, 0.0)),
                       (.11, act(z=-.03, y=.03, hips=-2, chest=-5, turn=-14, twist=-26, fwd=step, pitch=(0, -8),
                                 L=(34, 10, 34), R=(-34, 48, 112), curlL=OPEN, curlR=GRIP)),     # drawn back, the hips turned away
                       (.21, act(z=-.02, y=-.05, hips=3, chest=5, turn=16, twist=20, fwd=step, pitch=(0, -14),
                                 L=(-14, 14, 46), R=(124, 12, 8), curlR=OPEN)),                 # the hips lead, it leaves the hand high
                       (.36, act(z=-.03, y=-.06, hips=5, chest=9, turn=20, twist=26, fwd=step, pitch=(0, -10),
                                 L=(-20, 12, 40), R=(48, 0, 24))),                              # the arm carries on down across
                       (.68, idle_pose(b, 0.0))], ease=smooth)
        return throw.at(t, HIT)

    def Strike(t):
        strike = Track([(0.0, idle_pose(b, 0.0)),
                        (.08, act(z=-.06, y=.02, hips=4, chest=2, turn=-12, twist=-24, fwd=(-.04, .04), pitch=(0, -6),
                                  L=(54, 14, 100), R=(-24, 16, 118), curlL=GRIP, curlR=GRIP)),  # loaded, the guard up
                        (.16, act(z=-.055, y=-.14, hips=7, chest=10, turn=16, twist=22, fwd=(-.22, .08), pitch=(2, -22),
                                  L=(-10, 12, 106), R=(88, 4, 4), curlL=GRIP, curlR=GRIP)),     # through the step: it lands
                        (.30, act(z=-.045, y=-.12, hips=5, chest=8, turn=12, twist=16, fwd=(-.22, .08), pitch=(2, -18),
                                  L=(-6, 12, 96), R=(76, 8, 18), curlL=GRIP, curlR=GRIP)),      # held a moment
                        (.58, idle_pose(b, 0.0))], ease=smooth)
        return strike.at(t, HIT)

    def Brace(t):
        TURN = -70                                           # the upper arms turned in: the forearms up in front of the face
        def guard(z, hips, head):
            return act(z=z, y=-.015, hips=hips, spine=hips * .7, chest=hips, head=head, width=.12, toe=10, fwd=(-.08, .07),
                       pitch=(0, -10), L=(60, 6, 114), R=(54, 6, 118), turnL=TURN, turnR=TURN, curlL=GRIP, curlR=GRIP, knee=.03)
        brace = Track([(0.0, idle_pose(b, 0.0)), (.15, guard(-.08, 6, 8)), (.23, guard(-.065, 5, 7)), (.6, guard(-.075, 6, 8)),
                       (.9, idle_pose(b, 0.0))], ease=smooth)
        return brace.at(t, dict(chest=.02, head=.04, arm=.02, forearm=.045, hand=.07))

    def Slam(t):
        def down(z, y, lean, reach):
            """a lunge to the ground: the left foot flat ahead, the right back on its toes with the knee near the ground,
            the right fist on the ground ahead of the front foot, the left arm swept back"""
            p = Pose()
            for s, sx in gait.SIDES:
                a = b.ankle[s]
                ahead = (-.28 if s == "L" else .30) * b.scale
                ft = (4.0 if s == "L" else -42.0)             # (off her heels: the front foot flat, the back on its toes)
                p.feet[s] = Foot(b.planted(s, (sx * .09 * b.scale, a.y + ahead), ft, 6), ft, 6)
            trunk(p, hips=lean, spine=lean * .7, chest=lean * .6, head=-lean * 1.5, z=up + z, y=y)
            arms(b, p, "R", reach, 3, 4, curl=GRIP)
            arms(b, p, "L", -44, 26, 22)
            p.knee_out = {"L": .02, "R": .0}
            return p
        slam = Track([(0.0, idle_pose(b, 0.0)),
                      (.19, act(z=.01, y=.02, hips=-5, spine=-8, chest=-12, head=-10, L=(140, 12, 46), R=(168, 6, 22),
                                curlL=SOFT, curlR=GRIP)),                                       # up tall, the fist overhead
                      (.33, down(-.50, -.05, 26, 62)),                                          # it lands
                      (.55, down(-.48, -.045, 24, 58)),                                         # a beat down there
                      (1.0, idle_pose(b, 0.0))], ease=smooth)
        return slam.at(t, HIT)

    # --- melee: the guns on the back, the hands empty (or a blade in the right): a guard, a chain of three light blows,
    # one heavy; each clip begins and ends in its guard, and the time the blow lands is in the game's data ("melee")
    def fist_guard(z=-.03, y=.0, hips=3, twist=-10, turn=-6, bob=0.0, L=(48, 8, 126), R=(42, 10, 136), **k):
        """her guard: light on the balls of her feet, the left ahead, the hands high and close"""
        return act(z=z + bob, y=y, hips=hips, spine=3, chest=2, head=4, twist=twist, turn=turn, width=.12, toe=12,
                   fwd=(-.10, .07), pitch=(0, -10), L=L, R=R, curlL=GRIP, curlR=GRIP, knee=.03, **k)

    def FistGuard(t):
        return fist_guard(bob=-.006 * (1 - math.cos(TAU * t / 1.0)) * .5)

    def Jab(t):
        jab = Track([(0.0, fist_guard()),
                     (.07, fist_guard(y=-.04, twist=8, turn=4, L=(86, 4, 6), R=(40, 16, 132))),           # it lands
                     (.14, fist_guard(y=-.035, twist=6, turn=2, L=(82, 6, 14), R=(40, 16, 132))),
                     (.38, fist_guard())], ease=smooth)
        return jab.at(t, HIT)

    def Cross(t):
        cross = Track([(0.0, fist_guard()),
                       (.05, fist_guard(twist=-18, turn=-12, z=-.04)),
                       (.12, fist_guard(y=-.09, hips=7, twist=26, turn=16, L=(40, 14, 128), R=(88, 4, 4))),  # it lands
                       (.21, fist_guard(y=-.08, hips=6, twist=22, turn=12, L=(40, 14, 128), R=(80, 6, 14))),
                       (.48, fist_guard())], ease=smooth)
        return cross.at(t, HIT)

    def Hook(t):
        hook = Track([(0.0, fist_guard()),
                      (.08, fist_guard(twist=-26, turn=-14, z=-.045, L=(34, 56, 102), turnL=-50)),
                      (.16, fist_guard(y=-.03, hips=5, twist=32, turn=14, L=(22, 78, 94), turnL=-80)),        # it lands
                      (.26, fist_guard(y=-.03, hips=4, twist=26, turn=10, L=(26, 72, 96), turnL=-75)),
                      (.52, fist_guard())], ease=smooth)
        return hook.at(t, HIT)

    def Haymaker(t):                                         # her heavy blow: a spinning back fist would be another's;
        hay = Track([(0.0, fist_guard()),                    # hers is a loaded overhand thrown through the step
                     (.32, fist_guard(z=-.06, y=.05, hips=-2, twist=-38, turn=-20, L=(58, 14, 112), R=(-30, 36, 120))),
                     (.45, fist_guard(z=-.07, y=-.16, hips=11, twist=38, turn=22, L=(20, 18, 120), R=(96, 4, 8))),   # it lands
                     (.62, fist_guard(z=-.065, y=-.14, hips=9, twist=32, turn=18, L=(24, 18, 118), R=(84, 8, 20))),
                     (.92, fist_guard())], ease=smooth)
        return hay.at(t, HIT)

    def blade_guard(z=-.03, y=.0, hips=3, twist=-6, turn=-4, bob=0.0, L=(40, 18, 120), R=(34, 12, 74), **k):
        return act(z=z + bob, y=y, hips=hips, spine=3, chest=2, head=3, twist=twist, turn=turn, width=.12, toe=12,
                   fwd=(-.09, .08), pitch=(0, -10), L=L, R=R, curlL=GRIP, curlR=GRIP, knee=.03, **k)

    def BladeGuard(t):
        return blade_guard(bob=-.006 * (1 - math.cos(TAU * t / 1.2)) * .5)

    def SlashA(t):
        s = Track([(0.0, blade_guard()),
                   (.10, blade_guard(twist=-24, turn=-12, z=-.035, R=(110, 60, 70), turnR=20)),
                   (.16, blade_guard(y=-.06, hips=5, twist=22, turn=12, R=(64, 8, 16), turnR=-10)),       # it lands
                   (.25, blade_guard(y=-.06, hips=5, twist=30, turn=14, R=(30, -22, 24), turnR=-20)),
                   (.48, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def SlashB(t):
        s = Track([(0.0, blade_guard()),
                   (.09, blade_guard(twist=26, turn=12, z=-.04, R=(52, -26, 96), turnR=-30)),
                   (.15, blade_guard(y=-.05, hips=4, twist=-8, turn=-4, R=(80, 18, 12), turnR=10)),        # it lands
                   (.24, blade_guard(y=-.05, hips=4, twist=-22, turn=-10, R=(96, 54, 22), turnR=24)),
                   (.48, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def Thrust(t):
        s = Track([(0.0, blade_guard()),
                   (.10, blade_guard(twist=-20, turn=-12, z=-.045, y=.03, R=(4, 18, 112))),
                   (.19, blade_guard(y=-.14, hips=7, twist=22, turn=14, R=(88, 4, 4))),                    # it lands
                   (.29, blade_guard(y=-.12, hips=6, twist=18, turn=12, R=(84, 6, 10))),
                   (.52, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def Cleave(t):
        s = Track([(0.0, blade_guard()),
                   (.38, blade_guard(z=.0, y=.03, hips=-6, twist=-8, L=(66, 14, 102), R=(158, 12, 70))),   # raised
                   (.50, blade_guard(z=-.09, y=-.14, hips=15, twist=8, L=(10, 24, 110), R=(46, 6, 10))),   # it lands
                   (.68, blade_guard(z=-.085, y=-.13, hips=13, twist=6, L=(14, 24, 110), R=(36, 8, 16))),
                   (.98, blade_guard())], ease=smooth)
        return s.at(t, HIT)


    def Uppercut(t):
        u = Track([(0.0, fist_guard()),
                   (.10, fist_guard(z=-.07, hips=9, twist=-24, turn=-12, R=(10, 18, 120))),
                   (.19, fist_guard(z=.0, y=-.05, hips=-4, twist=28, turn=14, R=(90, 4, 96))),        # it lands
                   (.33, fist_guard(z=.0, y=-.04, hips=-4, twist=24, turn=12, R=(96, 6, 90))),
                   (.68, fist_guard())], ease=smooth)
        return u.at(t, HIT)

    def Rising(t):
        s = Track([(0.0, blade_guard()),
                   (.10, blade_guard(z=-.07, hips=9, twist=-28, turn=-12, R=(-20, 36, 50), turnR=-20)),
                   (.19, blade_guard(z=.0, y=-.06, hips=-4, twist=24, turn=12, R=(140, 22, 16), turnR=10)),  # it lands
                   (.33, blade_guard(z=.0, y=-.05, hips=-4, twist=28, turn=14, R=(150, 26, 20), turnR=10)),
                   (.70, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def sweep_pose(z, fx, fy, twist, hips, L, R):
        p = act(z=z, y=.0, hips=hips, spine=6, chest=4, head=-2, twist=twist, turn=twist * .3, width=.12, toe=12, fwd=(-.10, .07),
                pitch=(0, 0), L=L, R=R, curlL=GRIP, curlR=GRIP, knee=.05)
        a = b.ankle["R"]
        p.feet["R"] = Foot(b.planted("R", (fx * b.scale, a.y + fy * b.scale), -hp, 40), -hp, 40)
        return p

    def Sweep(t):
        s = Track([(0.0, fist_guard()),
                   (.08, sweep_pose(-.24, -.28, .24, -28, 12, (48, 18, 112), (40, 24, 122))),
                   (.17, sweep_pose(-.30, -.58, -.10, 28, 16, (30, 34, 92), (20, 44, 92))),          # it lands
                   (.29, sweep_pose(-.28, -.45, -.38, 38, 14, (30, 34, 92), (20, 44, 92))),
                   (.53, fist_guard())], ease=smooth)
        return s.at(t, HIT)


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

    return {"Idle": (Idle, 5.6, True), "Stroll": (Stroll, stroll.T, True), "Walk": (Walk, walk.T, True), "Run": (Run, run.T, True),
            "Jump": (Jump, .5, False), "Land": (Land, .5, False), "Stop": (Stop, .5, False), "Vault": (Vault, 1.0, False), "Mantle": (Mantle, 1.0, False),
            "Climb": (Climb, 1.0, False), "Crouch": (Crouch, 5.6, True), "CrouchWalk": (CrouchWalk, crouch.T, True),
            "Slide": (Slide, .8, True), "Death": (Death, 1.2, False),
            "Throw": (Throw, .68, False), "Strike": (Strike, .58, False), "Brace": (Brace, .9, False), "Slam": (Slam, 1.0, False),
            "FistGuard": (FistGuard, 2.0, True), "Jab": (Jab, .38, False), "Cross": (Cross, .48, False), "Hook": (Hook, .52, False), "Haymaker": (Haymaker, .92, False), "BladeGuard": (BladeGuard, 2.4, True), "SlashA": (SlashA, .48, False), "SlashB": (SlashB, .48, False), "Thrust": (Thrust, .52, False), "Cleave": (Cleave, .98, False),
            "Uppercut": (Uppercut, .68, False), "Rising": (Rising, .70, False), "Sweep": (Sweep, .53, False),
            "Fidget1": (fidget(4.4, none, weight), 4.4, False), "Fidget2": (fidget(4.2, look_back), 4.2, False),
            "Fidget3": (fidget(4.0, stretch), 4.0, False)}, (walk, run)
