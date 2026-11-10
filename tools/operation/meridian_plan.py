"""Operation: Meridian Fall, the first operation (the owner's layout sheet art/reference/operation/first_operation_map.png,
made smaller and linear; our own names).

The old capital Meridian went silent in the Stillfall. Its crown, a round platform under a broken orbital ring, now
holds a beam into the sky and the thing that guards it. The route runs south to north:

  Approach   (south)  the entry road under a broken viaduct, up to the city wall
  Meridian Gate       the wall's great arch and the court behind it (clear)
  The Boulevard       a tower-lined avenue with a fallen overpass, into the centre
  Concord Ring        the round plaza with the broken monument (hold until the terrace barrier falls)
  High Terraces       a ramp up the east side, then the elevated deck loop north and west (clear)
  Crown Bridge        the bridge north to the crown (its barrier falls when the terraces are clear)
  The Crown           the round platform with the beam: the Hollow Colossus (boss)

This module is the single source of the layout numbers: tools/blender/meridian.py builds the level's geometry from
it and `python tools/operation/meridian_plan.py` writes unreal/ShatteredOrbit/Data/op_meridian.json (stages, waves,
spawn groups, barriers, map points, rewards) that ASOOperation and make_operation_map.py read.

Coordinates are metres (E, N, up), the plaza's centre at the origin; the json is Unreal world cm (X = N, Y = E).
"""
import json
import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "unreal", "ShatteredOrbit", "Data", "op_meridian.json")

NAME = "Meridian Fall"
TAGLINE = "The old capital went silent in the Stillfall. Something answers from its crown."

# ---------------------------------------------------------------------------------------------------- layout (m)
ENTRY = (0.0, -310.0)
APPROACH = dict(n0=-320.0, n1=-206.0, half=30.0, road=8.0)            # entry road, half width of the corridor
WALL = dict(n=-200.0, thick=7.0, height=22.0, span=170.0, gate_w=18.0, gate_h=14.0)
COURT = dict(n0=-196.0, n1=-138.0, half=36.0)                           # the gate court
BOULEVARD = dict(n0=-138.0, n1=-44.0, road=12.0, walk=18.0, lots=46.0, overpass_n=-96.0, overpass_z=7.0)
PLAZA = dict(r=36.0, inner=18.0, sunk=0.9, ring_in=44.0, ring_out=72.0)  # open plaza, sunken circle, building ring
RAMP = dict(e0=44.0, e1=78.0, half=6.0, z=10.0)                         # east ramp up to the terraces
TERRACE = dict(z=10.0, w=14.0, east_e=80.0, n0=-8.0, north_n=114.0, west_e=-8.0)   # deck centre lines
BRIDGE = dict(e=0.0, n0=121.0, n1=161.0, half=7.0, z=10.0)
CROWN = dict(c=(0.0, 200.0), r=40.0, z=10.0, beam_r=4.0, pylon_r=28.0, pylon_angles=(90.0, 210.0, 330.0),
             column_r=20.0, column_angles=(45.0, 135.0, 225.0, 315.0))
SPIRE = dict(c=(0.0, 470.0), height=360.0, ring_r=190.0)                # the backdrop spire and its broken ring


def deg_yaw_toward(frm, to):
    """Unreal yaw (degrees) to face from (E, N) toward (E, N): X = N, Y = E, yaw 0 = north, 90 = east"""
    return math.degrees(math.atan2(to[0] - frm[0], to[1] - frm[1]))


def ring_points(c, r, angles, z=0.0):
    """points on a circle round c (E, N); angles in degrees, 0 = east, counter-clockwise (90 = north)"""
    return [(c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)), z) for a in angles]


def line_points(a, b, n, z=0.0):
    return [(a[0] + (b[0] - a[0]) * i / max(n - 1, 1), a[1] + (b[1] - a[1]) * i / max(n - 1, 1), z) for i in range(n)]


# ---------------------------------------------------------------------------------------------------- spawn groups
TZ = TERRACE["z"]
GROUPS = {
    # yaw: which way they face (toward the players' way in)
    "approach_rubble": dict(points=line_points((-18.0, -246.0), (18.0, -246.0), 5), toward=ENTRY),
    "court_north": dict(points=line_points((-22.0, -146.0), (22.0, -146.0), 6), toward=(0.0, -196.0)),
    "court_flanks": dict(points=[(-31.0, -176.0, 0.0), (31.0, -176.0, 0.0), (-30.0, -160.0, 0.0), (30.0, -160.0, 0.0)],
                         toward=(0.0, -196.0)),
    "boulevard_mid": dict(points=line_points((-10.0, -84.0), (10.0, -84.0), 5), toward=(0.0, -138.0)),
    "plaza_north": dict(points=ring_points((0.0, 0.0), 41.0, (70.0, 80.0, 90.0, 100.0, 110.0)), toward=(0.0, 0.0)),
    "plaza_west": dict(points=ring_points((0.0, 0.0), 41.0, (160.0, 170.0, 180.0, 190.0, 200.0)), toward=(0.0, 0.0)),
    "plaza_east": dict(points=ring_points((0.0, 0.0), 41.0, (30.0, 40.0, 320.0, 330.0)), toward=(0.0, 0.0)),
    "terrace_east": dict(points=line_points((TERRACE["east_e"], 34.0), (TERRACE["east_e"], 70.0), 5, TZ),
                         toward=(TERRACE["east_e"], 0.0)),
    "terrace_north": dict(points=line_points((70.0, TERRACE["north_n"]), (30.0, TERRACE["north_n"]), 5, TZ),
                          toward=(TERRACE["east_e"], 60.0)),
    "crown_boss": dict(points=[(CROWN["c"][0] + 6.0, CROWN["c"][1] + 25.0, CROWN["z"])], toward=(0.0, BRIDGE["n1"])),
    "crown_ring": dict(points=ring_points(CROWN["c"], 34.0, (20.0, 60.0, 100.0, 140.0, 160.0), CROWN["z"]),
                       toward=CROWN["c"]),
}


def checkpoint(e, n, z, toward):
    return [n * 100.0, e * 100.0, z * 100.0 + 100.0, deg_yaw_toward((e, n), toward)]


def goal(e, n, z=0.0):
    return [n * 100.0, e * 100.0, z * 100.0]


STAGES = [
    dict(id="approach", title="Meridian Approach", objective="Reach the city gate", kind="travel",
         goal=goal(0.0, WALL["n"] - 4.0), radius=1800,
         checkpoint=checkpoint(ENTRY[0], ENTRY[1] + 4.0, 0.0, (0.0, 0.0)),
         waves=[dict(hunt=False, spawn=[["remnant", 3, "approach_rubble"], ["stalker", 2, "approach_rubble"]])]),
    dict(id="gate", title="Meridian Gate", objective="Break the hold on the gate", kind="clear",
         goal=goal(0.0, -168.0),
         checkpoint=checkpoint(0.0, WALL["n"] + 6.0, 0.0, (0.0, 0.0)),
         waves=[dict(hunt=False, spawn=[["remnant", 4, "court_north"], ["stalker", 2, "court_flanks"], ["veilborn", 1, "court_north"]]),
                dict(delay=2.0, maxAlive=3, spawn=[["remnant", 6, "court_north"], ["veilborn", 2, "court_flanks"]]),
                dict(delay=2.0, maxAlive=2, spawn=[["bulwark", 1, "court_north"], ["remnant", 4, "court_flanks"]])]),
    dict(id="boulevard", title="The Boulevard", objective="Push into the central district", kind="travel",
         goal=goal(0.0, -42.0), radius=1500,
         waves=[dict(hunt=False, spawn=[["stalker", 2, "boulevard_mid"], ["remnant", 3, "boulevard_mid"]])]),
    dict(id="ring", title="Concord Ring", objective="Hold the ring until the terrace barrier falls", kind="hold", hold=90,
         goal=goal(0.0, 0.0),
         checkpoint=checkpoint(0.0, -40.0, 0.0, (0.0, 0.0)),
         waves=[dict(spawn=[["remnant", 6, "plaza_north"]]),
                dict(delay=6.0, maxAlive=4, spawn=[["remnant", 5, "plaza_west"], ["stalker", 2, "plaza_north"]]),
                dict(delay=8.0, maxAlive=4, spawn=[["veilborn", 2, "plaza_east"], ["remnant", 4, "plaza_west"]]),
                dict(delay=8.0, maxAlive=3, spawn=[["bulwark", 1, "plaza_north"], ["remnant", 4, "plaza_west"]])]),
    dict(id="climb", title="High Terraces", objective="Climb to the terraces", kind="travel",
         goal=goal(TERRACE["east_e"], 2.0, TZ), radius=1200,
         checkpoint=checkpoint(36.0, 0.0, 0.0, (RAMP["e1"], 0.0))),
    dict(id="terraces", title="High Terraces", objective="Clear the terraces", kind="clear",
         goal=goal(TERRACE["east_e"], 60.0, TZ),
         checkpoint=checkpoint(TERRACE["east_e"], 4.0, TZ, (TERRACE["east_e"], 60.0)),
         waves=[dict(hunt=False, spawn=[["veilborn", 2, "terrace_north"], ["remnant", 4, "terrace_east"], ["stalker", 2, "terrace_east"]]),
                dict(delay=2.0, maxAlive=3, spawn=[["bulwark", 2, "terrace_north"], ["stalker", 3, "terrace_east"]]),
                dict(delay=2.0, maxAlive=2, spawn=[["veilborn", 2, "terrace_north"], ["remnant", 6, "terrace_east"]])]),
    dict(id="bridge", title="Crown Bridge", objective="Cross to the Crown", kind="travel",
         goal=goal(BRIDGE["e"], BRIDGE["n1"] - 2.0, TZ), radius=1000,
         checkpoint=checkpoint(56.0, TERRACE["north_n"], TZ, (0.0, TERRACE["north_n"]))),
    dict(id="crown", title="The Crown", objective="Bring down the Hollow Colossus", kind="boss",
         boss="colossus", bossGroup="crown_boss", goal=goal(*CROWN["c"], CROWN["z"]),
         checkpoint=checkpoint(BRIDGE["e"], BRIDGE["n1"] - 6.0, TZ, CROWN["c"]),
         waves=[dict(bossHealth=0.75, spawn=[["remnant", 6, "crown_ring"]]),
                dict(bossHealth=0.5, spawn=[["veilborn", 3, "crown_ring"], ["remnant", 4, "crown_ring"]]),
                dict(bossHealth=0.25, spawn=[["bulwark", 2, "crown_ring"], ["stalker", 3, "crown_ring"]])]),
]

# Waves: the first of a stage is a garrison (hunt=False): unaware at its post until it sees, hears or is hurt by
# someone, so it can be crept up on; later waves are reinforcements that know where the players are.

# Energy barriers that keep the route linear: closed until their stage begins.
BARRIERS = [
    dict(id="terrace_barrier", opens="climb", c=(RAMP["e0"] + 1.0, 0.0, 0.0), width=RAMP["half"] * 2 + 2.0, height=8.0, yaw=90.0),
    dict(id="crown_barrier", opens="bridge", c=(BRIDGE["e"], BRIDGE["n0"] + 1.0, TZ), width=BRIDGE["half"] * 2 + 2.0, height=8.0, yaw=0.0),
]

# The Colossus's shield conduits (destroy all three to break its shield).
PYLONS = ring_points(CROWN["c"], CROWN["pylon_r"], CROWN["pylon_angles"], CROWN["z"])

# Map points (mini-map, map screen): label, subtitle, kind, (E, N, z), fast travel
MAP_POINTS = [
    ("Meridian Approach", "Where you come in", "FastTravel", (ENTRY[0], ENTRY[1] + 4.0, 0.0)),
    ("Meridian Gate", "The city wall", "Landmark", (0.0, WALL["n"], 0.0)),
    ("Concord Ring", "The central district", "Landmark", (0.0, 0.0, 0.0)),
    ("High Terraces", "The upper sectors", "Landmark", (TERRACE["east_e"], 50.0, TZ)),
    ("The Crown", "The beam", "Mission", (CROWN["c"][0], CROWN["c"][1], CROWN["z"])),
    ("Shuttle to Nexus Prime", "Back to the city", "AreaTravel", (8.0, ENTRY[1] - 2.0, 0.0)),
]

# Finishing grants one random piece of these sets (the owner's concept sheets in art/reference/operation/).
REWARDS = dict(
    rarity=3,
    armor=[["head", "void_sentinel"], ["vest", "void_sentinel"], ["hands", "void_sentinel"], ["legs", "void_sentinel"],
           ["feet", "void_sentinel"], ["outer", "void_sentinel"]],
    weapons=["vr_rifle", "vr_sniper", "vr_smg", "vr_shotgun", "vr_lmg", "vr_handcannon", "vr_pistol", "vr_fusion", "vr_rocket"],
)

# What this operation puts on top of the species it uses. The creatures themselves are written once in the game
# (one class per species, USOSpeciesLibrary) and are the same in every operation: a plan never describes behaviour.
# ENEMIES: multipliers on every creature here, e.g. dict(health=1.2, damage=1.1).
# VARIANTS: named dressings of a species that waves spawn like a species, e.g.
#   dict(remnant_ashen=dict(species="remnant", name="Ashen Remnant", health=1.6, damage=1.2, speed=1.1, aim=0.8,
#                           sight=1.2, weapon="shotgun"))  ->  ["remnant_ashen", 3, "court_north"] in a wave.
ENEMIES = {}
VARIANTS = {}


def to_json():
    groups = {}
    for gid, g in GROUPS.items():
        pts = g["points"]
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        groups[gid] = dict(yaw=round(deg_yaw_toward(c, g["toward"]), 2),
                           points=[[round(p[1] * 100.0, 1), round(p[0] * 100.0, 1), round(p[2] * 100.0, 1)] for p in pts])

    def cm(p):
        return [round(p[1] * 100.0, 1), round(p[0] * 100.0, 1), round(p[2] * 100.0, 1)]

    return dict(
        name=NAME, tagline=TAGLINE,
        groups=groups,
        stages=STAGES,
        barriers=[dict(b, c=cm(b["c"]), width=b["width"] * 100.0, height=b["height"] * 100.0) for b in BARRIERS],
        pylons=[cm(p) for p in PYLONS],
        crown=dict(c=cm((CROWN["c"][0], CROWN["c"][1], CROWN["z"])), r=CROWN["r"] * 100.0),
        map=[dict(label=l, subtitle=s, kind=k, at=cm(p)) for l, s, k, p in MAP_POINTS],
        rewards=REWARDS,
        **(dict(enemies=ENEMIES) if ENEMIES else {}),
        **(dict(variants=VARIANTS) if VARIANTS else {}),
    )


if __name__ == "__main__":
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(to_json(), f, indent=1)
    print("wrote", OUT)
