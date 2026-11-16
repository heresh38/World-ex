"""His clips (masculine movement): the player clip set the game plays for the male body only.

  Idle      squared, wide base (feet past shoulder width, toes out), chest up, shoulders back, weight even; slow,
            deep breathing from the chest, a slight settle of the knees, the head drifting on its own slower time
  Stroll    the slow move (1.5 m/s: a light stick, aiming, crouched): a heavy, unhurried walk. Heel first, the body
            rising over the planted leg and settling between steps, shoulders rolling against the hips, arms hanging
            long and swinging from the shoulder
  Crouch    crouched and still: the left foot ahead and flat, the right back on its ball, chest folded, head up
  CrouchWalk  the crouched move (2.7 m/s): hips low the whole way round, short quick flat steps, a foot always down
  Walk      the game's default move (4.4 m/s): a strong, upright run. A wide track, the pelvis level and still, the
            leg nearly straight at the strike and driven straight behind, the shoulders doing the turning, the foot
            coming
            back to meet the ground, the pelvis loading on each strike, big shoulder drive; the arms swing from behind
            the hip to the chest, the elbows opening behind and closing in front, hands dragging a beat after
  Run       the sprint (8.6 m/s): knees driving to the horizontal, heels to the seat, a deep lean, the arms pumping
            through their whole range
  Jump      three poses the game moves between by how fast he is rising or falling: driving off the ground (legs
            long, arms thrown up), tucked at the top (knees apart), reaching for the ground (legs opening, arms wide)
  Land      the landing after a fall: both feet take it, the hips sink and the chest folds over them, the arms carry
            on down and forward, then he comes up into the idle
  Vault     over a low wall off the right hand: the reach, the legs swung through to the left with the knees up, the
            lead leg reaching for the ground, away in stride
  Mantle    onto a ledge: the reach, the catch with one boot on the face, the press with the knee coming up onto the
            top, the step up
  Climb     a high ledge: the hang at full stretch, the boots walking up, the pull to the chin, then the press, the
            knee and the step up
  Slide     aggressive: lead leg out, the other folded under, leaning back, the left hand trailing on the ground
  Death     the legs go, he drops heavily onto his back, arms thrown out
  Throw     the kit's thrown charge, off the right hand: the arm drawn back with the chest turned away and the left
            arm out ahead, the whip through with the hips and chest coming round, the hand carrying on down across
            the body (the charge leaves at 0.2 s)
  Strike    the kit's blow: the fist loaded at the ribs behind a turned shoulder, then the whole body driven through
            a short step onto the left foot, the arm straight at the end of it (it lands at 0.16 s)
  Brace     braced behind his forearms: the stance dropped and widened, both forearms up in front of the chest and
            face, the head down behind them; held, then let go
  Slam      the blow into the ground: up tall with both fists overhead, then the whole body dropped onto them, the
            front knee bent and the back knee near the ground, the right fist driven into the ground ahead of the
            front foot (it lands at 0.34 s); a beat down there, then up
            (the gun is put away while one of these four plays)
  Fidget1-3 idle variations the game slips in while he stands: a neck stretch (ear to each shoulder), a scan of the
            area (chest and head turn left, then right), a shoulder roll with a deep breath; each starts and ends on
            the idle pose

Vault, Mantle and Climb are one second long and are not played by the clock: the game shows the pose for how far
through the move the body is (and puts the hands on the real edge while it is in reach).
"""
import math
from mathutils import Vector
import gait
from gait import X, Y, Z, Pose, Foot, Gait, Track, smooth, bump, locomote

TAU = 2 * math.pi

# --- the three gaits: where the feet go (gait.Gait) and how the body rides over them (gait.locomote) -----------------
FISTS = ((34, 46, 26), (40, 52, 30), (46, 56, 32), (50, 60, 34))        # heavy half-closed hands
LAG = dict(spine=.02, chest=.04, head=.05, arm=.02, forearm=.06, hand=.10)
# A man's gait: the feet under the hip joints (a wide track), the pelvis level and still, the weight landing heavy on
# each step, and the movement coming from the shoulders: they turn hard against the stride, the chest carried up, the
# arms driving with the elbows a little out. (Narrow track + rolling hips reads as a woman's walk; a wide track with
# rolling hips and knees out reads as a waddle: neither.)
STROLL = dict(v=1.5, cadence=124, duty=.60, front=.37, width=.085, toe_out=8, lift=.03, kick=.03, strike=20, toeoff=50,
              swing_in=0.0, swing_pitch=-8, retract=.22, peak=.36)
STROLL_BODY = dict(lean=3, hip_yaw=4, hip_roll=1.4, sway=.010, bob=-.012, bob2=.004, drop=0.0, dip=.006, counter=1.3, nod=1.2, chest_up=4,
                   lag=dict(spine=.02, chest=.045, head=.06, arm=.03, forearm=.07, hand=.11),
                   arm=24, arm_bias=-2, arm_h2=.10, abd=12, abd_back=3, abd_fwd=2, cross=3, elbow=22, elbow_fwd=18, elbow_back=8,
                   wrist=10, wrist_lag=8, clav=4, curl=FISTS, thumb=22, knee_out=.035, asym=.93, asym_ph=.012)
# The run: upright and long. The foot lands just ahead of the hip on a nearly straight leg, the body rides high over
# it and the rear leg drives all the way straight behind (the push); the heel only comes half way up in recovery. The
# arms pump from behind the hip to the chest.
WALK = dict(v=4.4, cadence=164, duty=.19, front=.22, width=.075, toe_out=6, lift=.08, kick=.19, strike=6, toeoff=48,
            swing_in=0.0, swing_pitch=-16, retract=.34, peak=.42, stance=6)
WALK_BODY = dict(lean=5, hip_yaw=6, hip_roll=1.2, sway=.003, bob=.016, bob2=.004, drop=-.012, dip=.003, counter=1.2, nod=2.0, chest_up=5,
                 lag=LAG, arm=48, arm_bias=-12, arm_h2=.20, abd=13, abd_back=8, abd_fwd=5, cross=8, elbow=88, elbow_fwd=12, elbow_back=30,
                 wrist=6, wrist_lag=10, clav=8, clav_up=3, curl=(62, 84, 48), thumb=32,
                 knee_out=.03, asym=.94, asym_ph=.012, asym_elbow=1.05)
RUN = dict(v=8.6, cadence=240, duty=.16, front=.21, width=.070, toe_out=4, lift=.10, kick=.32, strike=-4, toeoff=50,
           swing_in=0.0, swing_pitch=-24, retract=.36, peak=.42, stance=14)
RUN_BODY = dict(lean=11, hip_yaw=8, hip_roll=1.0, sway=.002, bob=.015, bob2=.004, drop=-.010, dip=0.0, counter=1.2, nod=2.4, chest_up=3,
                lag=LAG, arm=62, arm_bias=-6, arm_h2=.22, abd=12, abd_back=10, abd_fwd=4, cross=10, elbow=92, elbow_fwd=8, elbow_back=38,
                wrist=4, wrist_lag=14, clav=11, clav_up=4, curl=(56, 76, 44), thumb=30,
                knee_out=.03, asym=.95, asym_ph=.010, asym_elbow=1.04)
# Crouched: the hips low between bent legs the whole way round (the clip is authored down there: nothing is bent at
# runtime), short quick flat steps with a foot always on the ground, the chest folded forward, the head up.
CROUCH = dict(v=2.7, cadence=240, duty=.44, front=.48, width=.105, toe_out=10, lift=.05, kick=.02, strike=4, toeoff=22,
              swing_in=0.0, swing_pitch=-6, retract=.18, peak=.42)
CROUCH_BODY = dict(lean=36, hip_yaw=5, hip_roll=1.5, sway=.008, bob=.008, bob2=0.0, drop=.28, dip=.004, counter=.8, nod=1.0, chest_up=0,
                   lag=LAG, arm=8, arm_bias=6, arm_h2=0.0, abd=14, abd_back=2, abd_fwd=2, cross=6, elbow=70, elbow_fwd=6, elbow_back=6,
                   wrist=6, wrist_lag=4, clav=2, curl=FISTS, thumb=22, knee_out=.09, asym=.95, asym_ph=.012)

LOOSE = ((14, 24, 12), (18, 28, 14), (22, 30, 16), (26, 32, 18))       # heavy, relaxed hands
OPEN = ((6, 10, 5), (8, 12, 6), (10, 14, 7), (12, 16, 8))              # spread for balance, or flat on a ledge
GRIP = ((40, 60, 30),) * 4


def stand_feet(b, p, width, toe_out, fwd=(0.0, 0.0)):
    for s, sx in gait.SIDES:
        a = b.ankle[s]
        p.feet[s] = Foot(b.planted(s, (sx * width, a.y + (fwd[0] if s == "L" else fwd[1])), 0.0, toe_out), 0.0, toe_out)


def idle_pose(b, t):
    """the idle at time t (3.6 s breaths, a 7.2 s sway: the clip loops over 7.2 s); the fidgets add to this"""
    p = Pose()
    br = math.sin(TAU * t / 3.6)
    late = math.sin(TAU * (t - .5) / 3.6)                     # the shoulders and head follow the chest
    drift = math.sin(TAU * t / 7.2)
    stand_feet(b, p, .175 * b.scale, 14)
    p.hips = Vector((.005 * drift, .002 * math.sin(TAU * t / 7.2 + 1.3), -.004 - .0015 * (1 + br)))
    p.add("hips", (X, 2.0), (Y, .6 * drift))
    p.add("spine", (X, -1.5 - .8 * br), (Y, -.5 * drift))
    p.add("chest", (X, -3.0 - 1.4 * br))
    p.add("neck", (X, 2.0 + .6 * late))
    p.add("head", (X, 1.0 + .5 * late), (Z, 1.6 * math.sin(TAU * t / 7.2 + .8)))
    for s, sx in gait.SIDES:
        p.add("clavicle." + s, (Z, sx * -3.0), (Y, sx * -1.0 * (1 + late) * .5))   # shoulders back, rising with the breath
        p.add("upperarm." + s, (Y, -sx * (9 + .6 * late)), (X, 4))
        p.add("forearm." + s, (b.elbow[s], -16 - 1.2 * math.sin(TAU * (t - .9) / 3.6)))
        p.add("hand." + s, (b.elbow[s], -6))
        p.curl(s, LOOSE, 12)
    p.knee_out = {"L": .08, "R": .08}
    return p


def arms(b, p, side, fwd, out, elbow, turn=0.0, hand=-6.0, curl=LOOSE, thumb=12):
    """one arm: fwd = degrees raised forward (negative = behind), out = degrees out from the body, elbow = bend"""
    sx = 1 if side == "L" else -1
    p.add("upperarm." + side, (Y, -sx * out), (X, -fwd), (Z, sx * turn))
    p.add("forearm." + side, (b.elbow[side], -elbow))
    p.add("hand." + side, (b.elbow[side], hand))
    p.curl(side, curl, thumb)


def leg(p, side, hip, knee, foot=0.0, out=0.0):
    """one leg off the ground: hip = degrees the thigh is raised forward (negative = behind), knee = bend,
    foot = toes down (+) / up (-), out = knee out from the middle"""
    sx = 1 if side == "L" else -1
    p.add("thigh." + side, (Y, -sx * out), (X, -hip))
    p.add("shin." + side, (X, knee))
    p.add("foot." + side, (X, foot))


def trunk(p, hips=0.0, spine=0.0, chest=0.0, head=0.0, roll=0.0, turn=0.0, z=0.0, y=0.0, x=0.0):
    """pitch forward (+) of hips / spine / chest, the head against it; roll (+ = to his left) and turn (+ = left) of
    the hips, undone above; the hips moved by (x, y, z) metres"""
    p.hips = Vector((x, y, z))
    p.add("hips", (Z, turn), (Y, roll), (X, hips))
    p.add("spine", (Z, -turn * .4), (Y, -roll * .35), (X, spine))
    p.add("chest", (Z, -turn * .4), (Y, -roll * .35), (X, chest))
    p.add("neck", (X, head * .4))
    p.add("head", (Y, -roll * .2), (X, head * .6))


def crouch_pose(b, t):
    """crouched and still: the left foot ahead and flat, the right back on its ball, the weight between them"""
    p = Pose()
    br = math.sin(TAU * t / 3.6)
    late = math.sin(TAU * (t - .5) / 3.6)
    for s, sx in gait.SIDES:
        a = b.ankle[s]
        fwd = (-.15 if s == "L" else .11) * b.scale
        pitch = 0.0 if s == "L" else -20.0
        p.feet[s] = Foot(b.planted(s, (sx * .13 * b.scale, a.y + fwd), pitch, 12), pitch, 12)
    p.hips = Vector((.006 * math.sin(TAU * t / 7.2), .02, -.31 * b.scale - .002 * (1 + br)))
    p.add("hips", (X, 15))
    p.add("spine", (X, 12 - .8 * br))
    p.add("chest", (X, 8 - 1.2 * br))
    p.add("neck", (X, -13 + .5 * late))
    p.add("head", (X, -16 + .5 * late), (Z, 1.4 * math.sin(TAU * t / 7.2 + .8)))
    for s, sx in gait.SIDES:
        p.add("clavicle." + s, (Y, sx * -.8 * (1 + late) * .5))
        p.add("upperarm." + s, (Y, -sx * 12), (X, -14))
        p.add("forearm." + s, (b.elbow[s], -58))
        p.add("hand." + s, (b.elbow[s], -6))
        p.curl(s, FISTS, 22)
    p.knee_out = {"L": .10, "R": .12}
    return p


def clips(b):
    stroll, walk, run, crouch = Gait(b, **STROLL), Gait(b, **WALK), Gait(b, **RUN), Gait(b, **CROUCH)
    crouch_body = dict(CROUCH_BODY, drop=CROUCH_BODY["drop"] * b.scale)

    def Crouch(t):
        return crouch_pose(b, t)

    def CrouchWalk(t):
        return locomote(b, crouch, t, crouch_body)

    def Idle(t):
        return idle_pose(b, t)

    def Stroll(t):
        return locomote(b, stroll, t, STROLL_BODY)

    def Walk(t):
        return locomote(b, walk, t, WALK_BODY)

    def Run(t):
        return locomote(b, run, t, RUN_BODY)

    # --- the air: three poses, read by the game by the rise and the fall --------------------------------------------
    def takeoff():
        p = Pose()
        trunk(p, hips=1, spine=-3, chest=-5, head=3, z=.01)
        leg(p, "L", -6, 8, 34, 2)
        leg(p, "R", 6, 14, 30, 2)
        arms(b, p, "L", 14, 14, 46, curl=LOOSE)                 # coming up with the push
        arms(b, p, "R", 6, 12, 52, curl=LOOSE)
        return p

    def tuck():
        p = Pose()
        trunk(p, hips=8, spine=10, chest=5, head=-12, z=-.02)
        leg(p, "L", 72, 98, -8, 9)
        leg(p, "R", 30, 74, 10, 9)
        arms(b, p, "L", 20, 30, 58, curl=LOOSE)
        arms(b, p, "R", 30, 26, 52, curl=LOOSE)
        return p

    def reach():
        p = Pose()
        trunk(p, hips=5, spine=6, chest=2, head=-6)
        leg(p, "L", 24, 30, -12, 7)
        leg(p, "R", 10, 22, -8, 7)
        arms(b, p, "L", 8, 50, 28, hand=4, curl=OPEN, thumb=6)
        arms(b, p, "R", 14, 44, 32, hand=4, curl=OPEN, thumb=6)
        return p

    jump = Track([(0.0, takeoff()), (.22, tuck()), (.5, reach())])

    def Jump(t):
        return jump.at(t, dict(arm=.02, forearm=.04, hand=.06, head=.02))

    def Land(t):
        def down(z, hips, spine, chest, head, fwd, out, elbow, curl):
            p = Pose()
            stand_feet(b, p, .17 * b.scale, 13, (-.03, .02))
            trunk(p, hips=hips, spine=spine, chest=chest, head=head, z=z)
            for s in "LR":
                arms(b, p, s, fwd, out, elbow, curl=curl)
            p.knee_out = {"L": .10, "R": .10}
            return p
        land = Track([(0.0, down(-.05, 6, 6, 2, -6, 10, 44, 30, OPEN)), (.10, down(-.27, 20, 16, 10, -22, 34, 18, 46, LOOSE)),
                      (.26, down(-.10, 8, 5, 0, -6, 12, 12, 26, LOOSE)), (.5, idle_pose(b, 0.0))], ease=smooth)
        return land.at(t, dict(chest=.02, head=.04, arm=.03, forearm=.05, hand=.07))

    def Stop(t):
        """braking out of a run: the left foot dug in ahead, the weight thrown back and low, then up into the idle"""
        def brake(z, back, hips, chest, fwd, elbow):
            p = Pose()
            for s, sx in gait.SIDES:
                a = b.ankle[s]
                ahead = (-.13 if s == "L" else .07) * b.scale
                pitch = 5.0 if s == "L" else -12.0
                p.feet[s] = Foot(b.planted(s, (sx * .16 * b.scale, a.y + ahead), pitch, 12), pitch, 12)
            trunk(p, hips=hips, spine=hips * .5, chest=chest, head=-(hips * 1.5 + chest) * .6, z=z, y=back)
            for s in "LR":
                arms(b, p, s, fwd, 16, elbow, curl=LOOSE)
            p.knee_out = {"L": .07, "R": .09}
            return p
        stop = Track([(0.0, brake(-.06, .05, -9, -5, 24, 46)), (.13, brake(-.10, .07, -3, 3, 12, 34)),
                      (.30, brake(-.04, .03, 2, -1, 6, 22)), (.5, idle_pose(b, 0.0))], ease=smooth)
        return stop.at(t, dict(chest=.02, head=.04, arm=.03, forearm=.05, hand=.07))

    # --- over and onto things: poses by how far through the move the body is ----------------------------------------
    def Vault(t):
        def run_in():
            p = Pose()
            trunk(p, hips=14, spine=12, chest=8, head=-18)
            leg(p, "L", 44, 62, -6)
            leg(p, "R", -16, 30, 20)
            arms(b, p, "R", 72, 8, 18, hand=-20, curl=OPEN, thumb=6)
            arms(b, p, "L", -30, 10, 70)
            return p

        def over():
            p = Pose()
            # the legs go through to his left with the knees up; the chest stays over the planted right hand
            trunk(p, hips=22, spine=10, chest=6, head=-20, roll=-40, turn=22, z=-.20, x=.05)
            leg(p, "L", 88, 104, 6, -4)
            leg(p, "R", 72, 110, 10, -6)
            arms(b, p, "R", 22, 20, 10, hand=-40, curl=OPEN, thumb=6)
            arms(b, p, "L", 6, 72, 30, curl=OPEN, thumb=6)
            return p

        def clearing():
            p = Pose()
            trunk(p, hips=12, spine=6, chest=2, head=-10, roll=-16, turn=8, z=-.10)
            leg(p, "L", 62, 34, -12)
            leg(p, "R", 30, 82, 12)
            arms(b, p, "R", -36, 12, 24)
            arms(b, p, "L", 32, 20, 60)
            return p

        def away():
            p = Pose()
            trunk(p, hips=7, spine=5, chest=3, head=-8, z=-.03)
            leg(p, "L", 32, 18, -8)
            leg(p, "R", -18, 56, 18)
            arms(b, p, "R", 20, 10, 88, curl=WALK_BODY["curl"], thumb=30)
            arms(b, p, "L", -44, 14, 62, curl=WALK_BODY["curl"], thumb=30)
            return p
        return Track([(0.0, run_in()), (.36, over()), (.68, clearing()), (1.0, away())]).at(t, dict(chest=.02, head=.04, forearm=.03, hand=.05))

    def press():
        p = Pose()
        trunk(p, hips=16, spine=11, chest=6, head=-22)
        leg(p, "R", 106, 126, -4, 14)
        leg(p, "L", -6, 12, 28)
        for s in "LR":
            arms(b, p, s, -12, 16, 18, hand=-50, curl=OPEN, thumb=6)
        return p

    def step_up():
        p = Pose()
        trunk(p, hips=20, spine=10, chest=4, head=-18, z=-.04)
        leg(p, "R", 90, 100, -6, 8)
        leg(p, "L", 22, 52, 10)
        for s in "LR":
            arms(b, p, s, -28, 12, 30)
        return p

    def stand():
        p = Pose()
        trunk(p, hips=8, spine=3, chest=-1, head=-4, z=-.04)
        leg(p, "L", 16, 26, -4, 4)
        leg(p, "R", 14, 24, -4, 4)
        for s in "LR":
            arms(b, p, s, -4, 9, 20)
        return p

    def Mantle(t):
        def up():
            p = Pose()
            trunk(p, hips=0, spine=-4, chest=-8, head=-18, z=.01)
            leg(p, "L", -6, 10, 32)
            leg(p, "R", 10, 20, 28)
            for s in "LR":
                arms(b, p, s, 122, 12, 24, hand=-10, curl=OPEN, thumb=6)
            return p

        def catch():
            p = Pose()
            trunk(p, hips=6, spine=6, chest=2, head=-14)
            leg(p, "R", 56, 86, -18, 4)                            # one boot on the face
            leg(p, "L", 8, 24, 20)
            for s in "LR":
                arms(b, p, s, 64, 14, 70, hand=-40, curl=OPEN, thumb=6)
            return p
        return Track([(0.0, up()), (.30, catch()), (.58, press()), (.82, step_up()), (1.0, stand())]).at(t, dict(chest=.02, head=.03))

    def Climb(t):
        def hang():
            p = Pose()
            trunk(p, hips=-4, spine=-4, chest=-4, head=-26)
            leg(p, "L", 6, 18, 26)
            leg(p, "R", 14, 26, 26)
            for s in "LR":
                arms(b, p, s, 168, 8, 6, hand=-10, curl=GRIP, thumb=20)
            return p

        def walk_up():
            p = Pose()
            trunk(p, hips=4, spine=0, chest=-2, head=-24)
            leg(p, "R", 52, 70, -14, 4)
            leg(p, "L", 22, 40, 10)
            for s in "LR":
                arms(b, p, s, 150, 10, 36, hand=-14, curl=GRIP, thumb=20)
            return p

        def pull():
            p = Pose()
            trunk(p, hips=10, spine=8, chest=4, head=-16)
            leg(p, "L", 70, 96, 4, 6)
            leg(p, "R", 86, 100, -8, 6)
            for s in "LR":
                arms(b, p, s, 72, 22, 116, hand=-30, curl=GRIP, thumb=20)
            return p
        return Track([(0.0, hang()), (.26, walk_up()), (.54, pull()), (.76, press()), (.90, step_up()), (1.0, stand())]).at(t, dict(chest=.02, head=.03))

    def Slide(t):
        v = math.sin(TAU * t / .8)
        w = math.sin(TAU * (t - .12) / .8)                     # the head and the free arm ride the bumps a beat late
        p = Pose()
        p.hips = Vector((0, .02, -.62 * b.scale + .004 * v))
        p.add("hips", (X, -26), (Z, 8))
        p.add("thigh.L", (Y, -5), (X, -64 - 1.5 * v))
        p.add("shin.L", (X, 8))
        p.add("foot.L", (X, -14))
        p.add("thigh.R", (Y, 10), (X, -30))
        p.add("shin.R", (X, 118))
        p.add("foot.R", (X, 22))
        p.add("spine", (X, -4 + .8 * v), (Z, -5))
        p.add("chest", (X, -2 + .6 * w), (Z, -6))
        p.add("head", (X, 24 + 1.2 * w), (Z, 6))
        p.add("upperarm.L", (Y, -40), (X, 30))
        p.add("forearm.L", (b.elbow["L"], -10))
        p.add("hand.L", (Y, -12))
        p.add("upperarm.R", (X, -22 - 3 * w), (Y, 30))
        p.add("forearm.R", (b.elbow["R"], -28 - 4 * w))
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

    # --- the kit's abilities: the body's own clips (the gun is put away while one plays) ------------------------------
    HIT = dict(chest=.015, head=.03, arm=.015, forearm=.035, hand=.055)

    def act(z=0.0, y=0.0, hips=0.0, spine=0.0, chest=0.0, head=0.0, twist=0.0, width=.175, toe=14, fwd=(0.0, 0.0),
            L=(-4, 9, 16), R=(-4, 9, 16), turnL=0.0, turnR=0.0, curlL=LOOSE, curlR=LOOSE, knee=.08):
        """a standing pose: the hips moved by (y forward is negative, z), the trunk pitched, the chest twisted against
        the hips (twist + = to his left), each arm as (raised forward, out, elbow)"""
        p = Pose()
        stand_feet(b, p, width * b.scale, toe, (fwd[0] * b.scale, fwd[1] * b.scale))
        trunk(p, hips=hips, spine=spine, chest=chest, head=head, z=z, y=y)
        p.add("spine", (Z, twist * .35))
        p.add("chest", (Z, twist * .65))
        p.add("neck", (Z, -twist * .35))                  # the eyes stay on where it is going
        p.add("head", (Z, -twist * .35))
        arms(b, p, "L", L[0], L[1], L[2], turn=turnL, curl=curlL)
        arms(b, p, "R", R[0], R[1], R[2], turn=turnR, curl=curlR)
        p.knee_out = {"L": knee, "R": knee}
        return p

    def Throw(t):
        step = (-.10, .06)                                   # the left foot a little ahead: he throws across it
        throw = Track([(0.0, idle_pose(b, 0.0)),
                       (.12, act(z=-.035, y=.035, hips=-2, chest=-4, twist=-32, fwd=step, L=(42, 16, 30), R=(-38, 58, 108),
                                 curlL=OPEN, curlR=GRIP)),                                      # drawn back
                       (.22, act(z=-.02, y=-.06, hips=3, chest=6, twist=26, fwd=step, L=(-20, 22, 42), R=(122, 16, 10),
                                 curlL=LOOSE, curlR=OPEN)),                                     # it leaves the hand, high
                       (.38, act(z=-.03, y=-.07, hips=5, chest=10, twist=34, fwd=step, L=(-26, 18, 36), R=(46, 2, 22),
                                 curlR=LOOSE)),                                                 # the arm carries on down across
                       (.7, idle_pose(b, 0.0))], ease=smooth)
        return throw.at(t, HIT)

    def Strike(t):
        strike = Track([(0.0, idle_pose(b, 0.0)),
                        (.09, act(z=-.07, y=.02, hips=4, chest=2, twist=-30, fwd=(-.05, .05), L=(58, 24, 96), R=(-28, 22, 116),
                                  curlL=GRIP, curlR=GRIP)),                                     # loaded behind the shoulder
                        (.17, act(z=-.06, y=-.15, hips=8, chest=12, twist=30, fwd=(-.24, .09), L=(-14, 20, 104), R=(86, 6, 6),
                                  curlL=GRIP, curlR=GRIP)),                                     # through the step: it lands
                        (.32, act(z=-.05, y=-.13, hips=6, chest=9, twist=22, fwd=(-.24, .09), L=(-8, 20, 92), R=(74, 10, 20),
                                  curlL=GRIP, curlR=GRIP)),                                     # held a moment
                        (.6, idle_pose(b, 0.0))], ease=smooth)
        return strike.at(t, HIT)

    def Brace(t):
        TURN = -70                                           # the upper arms turned in: the forearms cross in front of the face
        def guard(z, hips, head):
            return act(z=z, y=-.02, hips=hips, spine=hips * .7, chest=hips, head=head, width=.23, toe=16, fwd=(-.08, .06),
                       L=(62, 8, 112), R=(56, 8, 116), turnL=TURN, turnR=TURN, curlL=GRIP, curlR=GRIP, knee=.10)
        brace = Track([(0.0, idle_pose(b, 0.0)), (.16, guard(-.09, 6, 8)), (.24, guard(-.075, 5, 7)), (.6, guard(-.085, 6, 8)),
                       (.9, idle_pose(b, 0.0))], ease=smooth)
        return brace.at(t, dict(chest=.02, head=.04, arm=.02, forearm=.04, hand=.06))

    def Slam(t):
        def down(z, y, lean, reach):
            """on the left knee's side of a lunge: the left foot flat ahead, the right back on its ball with the knee
            near the ground, the right fist on the ground ahead of the front foot, the left arm thrown back"""
            p = Pose()
            for s, sx in gait.SIDES:
                a = b.ankle[s]
                ahead = (-.30 if s == "L" else .32) * b.scale
                pitch = 0.0 if s == "L" else -38.0
                p.feet[s] = Foot(b.planted(s, (sx * .13 * b.scale, a.y + ahead), pitch, 8), pitch, 8)
            trunk(p, hips=lean, spine=lean * .7, chest=lean * .6, head=-lean * 1.5, z=z, y=y)
            arms(b, p, "R", reach, 4, 4, curl=GRIP)
            arms(b, p, "L", -40, 34, 26, curl=LOOSE)
            p.knee_out = {"L": .05, "R": .02}
            return p
        slam = Track([(0.0, idle_pose(b, 0.0)),
                      (.20, act(z=.012, y=.02, hips=-6, spine=-8, chest=-12, head=-10, L=(150, 14, 40), R=(166, 8, 26),
                                curlL=GRIP, curlR=GRIP)),                                       # up tall, the fist overhead
                      (.34, down(-.50, -.06, 26, 62)),                                          # it lands
                      (.56, down(-.48, -.05, 24, 58)),                                          # a beat down there
                      (1.0, idle_pose(b, 0.0))], ease=smooth)
        return slam.at(t, HIT)

    # --- melee: the guns on the back, the hands empty (or a blade in the right): a guard, a chain of three light blows,
    # one heavy; each clip begins and ends in its guard, and the time the blow lands is in the game's data ("melee")
    def fist_guard(z=-.035, y=.0, hips=4, twist=-12, bob=0.0, L=(50, 10, 124), R=(44, 12, 134), **k):
        """his boxer's guard: the left foot ahead, knees soft, the chin down behind two fists"""
        return act(z=z + bob, y=y, hips=hips, spine=3, chest=2, head=4, twist=twist, width=.2, toe=18, fwd=(-.12, .07),
                   L=L, R=R, curlL=GRIP, curlR=GRIP, knee=.10, **k)

    def FistGuard(t):
        return fist_guard(bob=-.006 * (1 - math.cos(TAU * t / 1.2)) * .5)

    def Jab(t):                                              # the left straight, the right fist kept at the chin
        jab = Track([(0.0, fist_guard()),
                     (.08, fist_guard(y=-.04, twist=10, L=(86, 6, 6), R=(42, 24, 130))),           # it lands
                     (.15, fist_guard(y=-.035, twist=8, L=(82, 8, 14), R=(42, 24, 130))),
                     (.40, fist_guard())], ease=smooth)
        return jab.at(t, HIT)

    def Cross(t):                                            # the right straight, the hip and shoulder turned through
        cross = Track([(0.0, fist_guard()),
                       (.05, fist_guard(twist=-20, z=-.045)),
                       (.13, fist_guard(y=-.09, hips=8, twist=30, L=(40, 20, 128), R=(86, 4, 4))),  # it lands
                       (.22, fist_guard(y=-.08, hips=7, twist=26, L=(40, 20, 128), R=(80, 6, 14))),
                       (.50, fist_guard())], ease=smooth)
        return cross.at(t, HIT)

    def Hook(t):                                             # the left hook: the elbow up, the fist round on a level line
        hook = Track([(0.0, fist_guard()),
                      (.08, fist_guard(twist=-28, z=-.05, L=(34, 58, 100), turnL=-50)),
                      (.17, fist_guard(y=-.03, hips=6, twist=36, L=(22, 80, 94), turnL=-80)),        # it lands
                      (.27, fist_guard(y=-.03, hips=5, twist=30, L=(26, 74, 96), turnL=-75)),
                      (.55, fist_guard())], ease=smooth)
        return hook.at(t, HIT)

    def Haymaker(t):                                         # the heavy blow: loaded far back, thrown over the top
        hay = Track([(0.0, fist_guard()),
                     (.34, fist_guard(z=-.07, y=.05, hips=-2, twist=-42, L=(60, 20, 110), R=(-34, 44, 118))),  # loaded
                     (.47, fist_guard(z=-.08, y=-.17, hips=12, twist=42, L=(20, 24, 120), R=(96, 6, 8))),     # it lands
                     (.64, fist_guard(z=-.075, y=-.15, hips=10, twist=36, L=(24, 24, 118), R=(84, 10, 20))),
                     (.95, fist_guard())], ease=smooth)
        return hay.at(t, HIT)

    def blade_guard(z=-.035, y=.0, hips=4, twist=-6, bob=0.0, L=(42, 26, 118), R=(34, 18, 74), **k):
        """the blade held out before him in the right hand, the point up and forward; the left guards the face"""
        return act(z=z + bob, y=y, hips=hips, spine=3, chest=2, head=3, twist=twist, width=.21, toe=18, fwd=(-.10, .08),
                   L=L, R=R, curlL=GRIP, curlR=GRIP, knee=.10, **k)

    def BladeGuard(t):
        return blade_guard(bob=-.006 * (1 - math.cos(TAU * t / 1.4)) * .5)

    def SlashA(t):                                           # high right down across to low left
        s = Track([(0.0, blade_guard()),
                   (.10, blade_guard(twist=-26, z=-.04, R=(110, 64, 70), turnR=20)),
                   (.17, blade_guard(y=-.06, hips=6, twist=24, R=(64, 10, 16), turnR=-10)),              # it lands
                   (.26, blade_guard(y=-.06, hips=6, twist=34, R=(30, -24, 24), turnR=-20)),
                   (.50, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def SlashB(t):                                           # back again: low left up across to high right
        s = Track([(0.0, blade_guard()),
                   (.09, blade_guard(twist=28, z=-.045, R=(52, -28, 96), turnR=-30)),
                   (.16, blade_guard(y=-.05, hips=5, twist=-8, R=(80, 20, 12), turnR=10)),                # it lands
                   (.25, blade_guard(y=-.05, hips=5, twist=-24, R=(96, 58, 22), turnR=24)),
                   (.50, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def Thrust(t):                                           # drawn back to the hip and driven straight in
        s = Track([(0.0, blade_guard()),
                   (.10, blade_guard(twist=-22, z=-.05, y=.03, R=(4, 22, 112))),
                   (.20, blade_guard(y=-.14, hips=8, twist=24, R=(88, 4, 4))),                            # it lands
                   (.30, blade_guard(y=-.12, hips=7, twist=20, R=(84, 6, 10))),
                   (.55, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def Cleave(t):                                           # the heavy blow: raised over the head, brought straight down
        s = Track([(0.0, blade_guard()),
                   (.40, blade_guard(z=.0, y=.03, hips=-6, twist=-10, L=(70, 20, 100), R=(158, 16, 70))),  # raised
                   (.52, blade_guard(z=-.10, y=-.14, hips=16, twist=8, L=(10, 30, 110), R=(46, 8, 10))),   # it lands
                   (.70, blade_guard(z=-.095, y=-.13, hips=14, twist=6, L=(14, 30, 110), R=(36, 10, 16))),
                   (1.0, blade_guard())], ease=smooth)
        return s.at(t, HIT)


    def Uppercut(t):                                         # dropped low behind the turn, the fist driven up under the chin
        u = Track([(0.0, fist_guard()),
                   (.10, fist_guard(z=-.08, hips=10, twist=-26, R=(10, 24, 118))),
                   (.20, fist_guard(z=.0, y=-.05, hips=-4, twist=30, R=(88, 6, 96))),                  # it lands
                   (.34, fist_guard(z=.0, y=-.04, hips=-4, twist=26, R=(94, 8, 90))),
                   (.70, fist_guard())], ease=smooth)
        return u.at(t, HIT)

    def Rising(t):                                           # the blade low behind the hip, brought up through the target
        s = Track([(0.0, blade_guard()),
                   (.10, blade_guard(z=-.08, hips=10, twist=-30, R=(-20, 40, 50), turnR=-20)),
                   (.20, blade_guard(z=.0, y=-.06, hips=-4, twist=26, R=(140, 26, 16), turnR=10)),      # it lands
                   (.34, blade_guard(z=.0, y=-.05, hips=-4, twist=30, R=(150, 30, 20), turnR=10)),
                   (.72, blade_guard())], ease=smooth)
        return s.at(t, HIT)

    def sweep_pose(z, fx, fy, twist, hips, L, R):
        """down on the left leg, the right foot planted far out where the sweep has carried it along the floor"""
        p = act(z=z, y=.0, hips=hips, spine=6, chest=4, head=-2, twist=twist, width=.2, toe=18, fwd=(-.10, .07), L=L, R=R,
                curlL=GRIP, curlR=GRIP, knee=.12)
        a = b.ankle["R"]
        p.feet["R"] = Foot(b.planted("R", (fx * b.scale, a.y + fy * b.scale), 0.0, 40), 0.0, 40)
        return p

    def Sweep(t):
        s = Track([(0.0, fist_guard()),
                   (.08, sweep_pose(-.26, -.30, .26, -30, 14, (50, 24, 110), (40, 30, 120))),         # the leg drawn behind
                   (.18, sweep_pose(-.32, -.62, -.10, 30, 18, (30, 40, 90), (20, 50, 90))),          # it lands, swept round low
                   (.30, sweep_pose(-.30, -.48, -.40, 40, 16, (30, 40, 90), (20, 50, 90))),
                   (.55, fist_guard())], ease=smooth)
        return s.at(t, HIT)


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
        late = 32 * (bump(t - .12, 1.4, 1.0) - bump(t - .12, 3.0, 1.0))   # the eyes lead, the chest follows
        p.add("spine", (Z, late * .2 * e))
        p.add("chest", (Z, late * .3 * e))
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

    return {"Idle": (Idle, 7.2, True), "Stroll": (Stroll, stroll.T, True), "Walk": (Walk, walk.T, True), "Run": (Run, run.T, True),
            "Jump": (Jump, .5, False), "Land": (Land, .5, False), "Stop": (Stop, .5, False), "Vault": (Vault, 1.0, False), "Mantle": (Mantle, 1.0, False),
            "Climb": (Climb, 1.0, False), "Crouch": (Crouch, 7.2, True), "CrouchWalk": (CrouchWalk, crouch.T, True),
            "Slide": (Slide, .8, True), "Death": (Death, 1.2, False),
            "Throw": (Throw, .7, False), "Strike": (Strike, .6, False), "Brace": (Brace, .9, False), "Slam": (Slam, 1.0, False),
            "FistGuard": (FistGuard, 2.4, True), "Jab": (Jab, .40, False), "Cross": (Cross, .50, False), "Hook": (Hook, .55, False), "Haymaker": (Haymaker, .95, False), "BladeGuard": (BladeGuard, 2.8, True), "SlashA": (SlashA, .50, False), "SlashB": (SlashB, .50, False), "Thrust": (Thrust, .55, False), "Cleave": (Cleave, 1.0, False),
            "Uppercut": (Uppercut, .70, False), "Rising": (Rising, .72, False), "Sweep": (Sweep, .55, False),
            "Fidget1": (fidget(4.0, neck), 4.0, False), "Fidget2": (fidget(4.6, scan), 4.6, False),
            "Fidget3": (fidget(4.0, shoulders), 4.0, False)}, (walk, run)
