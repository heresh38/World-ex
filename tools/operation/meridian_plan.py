"""Operation: Meridian Fall, the first operation (the owner's layout sheet art/reference/operation/first_operation_map.png,
made smaller and linear; our own names).

The old capital Meridian went silent in the Stillfall. Its crown, a round platform under a broken orbital ring, now
holds a beam into the sky and the thing that guards it. The route runs south to north, two and a half kilometres from
the city's edge to the crown:

  Ashfall Verge       the city's edge: the landing pad, the dead highway and its toll plaza (first pickets)
  The Stacks          a housing estate: through the gatehouse block's rooms, the walled yard (clear), the archway
                      and the alley between the tenements
  Meridian Galleria   the mall: two storeys round a long atrium, the rotunda under the fallen skylight (hold), then
                      the Warden at the service gate (boss)
  Deepline            down into the transit station: the hive's hearts on the platform (destroy), then the tunnel
  The Sluice          out into the drained canal under the watch on its bridges (clear), up the spillway
  The Causeway        the road back up to the old approach
  Approach            the entry road under a broken viaduct, up to the city wall
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

# The long way in, south of the old approach (everything on the line E = 0 unless it says otherwise).
VERGE = dict(n0=-2310.0, n1=-2000.0, half=30.0, road=9.0, toll_n=-2120.0, pad=(0.0, -2294.0))
STACKS = dict(n0=-2000.0, n1=-1640.0, half=46.0,
              block=dict(n0=-1960.0, n1=-1920.0, lobby=8.0),             # the gatehouse block across the route
              yard=dict(n0=-1920.0, n1=-1820.0),                         # the walled yard behind it
              arch=dict(n0=-1820.0, n1=-1790.0, half=4.5),               # the passage under the north block
              alley=dict(n0=-1790.0, n1=-1640.0, half=9.0))
GALLERIA = dict(fore_n0=-1640.0, n0=-1600.0, n1=-1300.0, half=36.0, conc=22.0, void=9.0, z1=5.0, roof=10.5, bay=12.0,
                rot_n=-1450.0, rot_r=15.0, bridges=(-1540.0, -1360.0), gate_half=5.0, doors=(-14.0, 0.0, 14.0),
                esc=((-15.0, -1582.0, -1570.0), (15.0, -1330.0, -1342.0)),   # (E, N at the foot, N at the top)
                yard_n1=-1262.0, yard_half=20.0)
DEEPLINE = dict(stair_n0=-1262.0, stair_n1=-1236.0, stair_half=5.0, z=-6.0, hall_n1=-1200.0, hall_half=16.0,
                plat_n1=-1100.0, plat_half=5.0, track=-7.2, wall=10.0, top=-1.0,
                tun_n1=-880.0, tun_half=5.0, tun_top=-1.6, rise_n=-904.0,   # the floor rises to the canal bed from here
                fall_n=(-1012.0, -972.0), side=(5.4, 8.6))                  # the collapse and the service corridor round it
SLUICE = dict(n0=-880.0, n1=-520.0, half=15.0, z=-5.0, pump_n=-700.0, bridges=(-800.0, -620.0),
              ramp=dict(n0=-562.0, n1=-548.0, e1=39.0))                      # the spillway up the east bank
CAUSEWAY = dict(path=((47.0, -555.0), (42.0, -518.0), (17.0, -466.0), (0.0, -426.0), (0.0, -318.0)), half=8.0,
                east=((39.4, -562.4), (57.0, -562.4), (52.0, -516.0), (27.0, -462.0), (10.0, -424.0), (10.0, -322.0)),
                west=((39.4, -547.6), (34.0, -540.0), (30.0, -516.0), (5.0, -462.0), (-10.0, -424.0), (-10.0, -322.0)))

# Holes in the ground (E0, E1, N0, N1): what is dug into it and open to the sky.
PITS = [(-DEEPLINE["stair_half"], DEEPLINE["stair_half"], DEEPLINE["stair_n0"], DEEPLINE["stair_n1"]),
        (-SLUICE["half"], SLUICE["half"], SLUICE["n0"], SLUICE["n1"]),
        (SLUICE["half"], SLUICE["ramp"]["e1"], SLUICE["ramp"]["n0"], SLUICE["ramp"]["n1"])]
# The whole route's line (the skyline keeps clear of it).
ROUTE = [(0.0, -2320.0), (0.0, -560.0), (47.0, -555.0), (0.0, -426.0), (0.0, -200.0), (0.0, -40.0), (0.0, 0.0), (80.0, 0.0),
         (80.0, 114.0), (0.0, 114.0), (0.0, 200.0)]
# Where the nav mesh is built (N0, N1, E0, E1, Z0, Z1 metres): only where the route is walked. One box over the
# whole route would take in every floor of every ruined tower and run out of tiles.
NAV = [(-2314, -1958, -32, 32, -2, 8), (-1962, -1788, -48, 48, -2, 3.6), (-1792, -1598, -38, 38, -2, 5),
       (-1602, -1298, -37, 37, -2, 9), (-1302, -1234, -21, 21, -8, 4), (-1238, -878, -17, 17, -9, -1),
       (-882, -518, -16, 41, -7, 3), (-564, -316, -12, 58, -2, 6),
       (-322, -196, -32, 32, -2, 9), (-200, -136, -37, 37, -2, 6), (-138, -38, -19, 19, -2, 9),
       (-46, 46, -46, 46, -3, 5), (-8, 8, 40, 80, -2, 13), (-10, 123, 72, 88, 7, 14), (106, 123, -10, 88, 7, 14),
       (118, 242, -42, 42, 7, 16)]


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
DZ, TRACK, CANAL, GZ = DEEPLINE["z"], DEEPLINE["track"], SLUICE["z"], GALLERIA["z1"]
GROUPS = {
    # yaw: which way they face (toward the players' way in)
    # --- Ashfall Verge
    "verge_toll": dict(points=line_points((-20.0, -2110.0), (20.0, -2110.0), 6), toward=VERGE["pad"]),
    "verge_road": dict(points=[(-14.0, -2060.0, 0.0), (12.0, -2052.0, 0.0), (-4.0, -2038.0, 0.0), (16.0, -2026.0, 0.0)], toward=VERGE["pad"]),
    # --- The Stacks
    "stacks_lobby": dict(points=[(-3.0, -1934.0, 0.0), (4.0, -1928.0, 0.0), (-22.0, -1936.0, 0.0), (24.0, -1940.0, 0.0), (-34.0, -1944.0, 0.0),
                                 (36.0, -1932.0, 0.0)], toward=(0.0, -1962.0)),
    "yard_north": dict(points=line_points((-30.0, -1836.0), (30.0, -1836.0), 7), toward=(0.0, -1918.0)),
    "yard_west": dict(points=line_points((-38.0, -1900.0), (-38.0, -1850.0), 5), toward=(0.0, -1870.0)),
    "yard_east": dict(points=line_points((38.0, -1900.0), (38.0, -1850.0), 5), toward=(0.0, -1870.0)),
    "alley_mid": dict(points=[(-5.0, -1740.0, 0.0), (5.0, -1732.0, 0.0), (-6.0, -1706.0, 0.0), (6.0, -1690.0, 0.0), (0.0, -1668.0, 0.0)],
                      toward=(0.0, -1790.0)),
    # --- Meridian Galleria
    "mall_south": dict(points=line_points((-16.0, -1560.0), (16.0, -1560.0), 6), toward=(0.0, -1600.0)),
    "mall_gallery_w": dict(points=line_points((-15.0, -1520.0), (-15.0, -1400.0), 6, GZ), toward=(0.0, -1450.0)),
    "mall_gallery_e": dict(points=line_points((15.0, -1500.0), (15.0, -1390.0), 6, GZ), toward=(0.0, -1450.0)),
    "mall_north": dict(points=line_points((-18.0, -1380.0), (18.0, -1380.0), 7), toward=(0.0, -1450.0)),
    "mall_shops_w": dict(points=[(-29.0, -1486.0, 0.0), (-29.0, -1462.0, 0.0), (-29.0, -1438.0, 0.0), (-29.0, -1414.0, 0.0)], toward=(0.0, -1450.0)),
    "mall_shops_e": dict(points=[(29.0, -1486.0, 0.0), (29.0, -1462.0, 0.0), (29.0, -1438.0, 0.0), (29.0, -1414.0, 0.0)], toward=(0.0, -1450.0)),
    "mall_gate": dict(points=[(0.0, -1316.0, 0.0)], toward=(0.0, -1450.0)),
    "mall_court": dict(points=line_points((-24.0, -1326.0), (24.0, -1326.0), 6), toward=(0.0, -1400.0)),
    # --- Deepline
    "deep_hall": dict(points=line_points((-10.0, -1212.0), (10.0, -1212.0), 5, DZ), toward=(0.0, -1238.0)),
    # (a heart stands 6 m tall: it only fits down in the track beds, where the hall is 6.2 m high)
    "deep_hearts": dict(points=[(-7.5, -1170.0, TRACK), (7.5, -1150.0, TRACK), (-7.5, -1128.0, TRACK)], toward=(0.0, -1200.0)),
    "deep_platform": dict(points=line_points((-3.0, -1170.0), (3.0, -1112.0), 6, DZ), toward=(0.0, -1200.0)),
    "deep_tracks": dict(points=[(-7.5, -1185.0, TRACK), (7.5, -1165.0, TRACK), (-7.5, -1140.0, TRACK), (7.5, -1118.0, TRACK)], toward=(0.0, -1200.0)),
    "tunnel_a": dict(points=line_points((-3.0, -1050.0), (3.0, -1030.0), 5, TRACK), toward=(0.0, -1100.0)),
    "tunnel_b": dict(points=line_points((-3.0, -950.0), (3.0, -925.0), 6, TRACK), toward=(0.0, -1000.0)),
    # --- The Sluice
    "sluice_south": dict(points=line_points((-10.0, -836.0), (10.0, -836.0), 6, CANAL), toward=(0.0, -880.0)),
    "sluice_pump": dict(points=[(-11.0, -712.0, CANAL), (11.0, -712.0, CANAL), (-4.5, -690.0, CANAL), (4.5, -690.0, CANAL), (-11.0, -676.0, CANAL),
                                (11.0, -676.0, CANAL)], toward=(0.0, -800.0)),
    "sluice_watch": dict(points=[(-6.0, -800.0, 0.6), (7.0, -800.0, 0.6), (-9.0, -620.0, 0.6), (-5.0, -620.0, 0.6)], toward=(0.0, -860.0)),
    "sluice_north": dict(points=line_points((-10.0, -590.0), (10.0, -590.0), 6, CANAL), toward=(0.0, -700.0)),
    "causeway_mid": dict(points=[(40.0, -508.0, 0.0), (29.0, -486.0, 0.0), (15.0, -458.0, 0.0), (2.0, -418.0, 0.0), (-2.0, -380.0, 0.0)],
                         toward=(47.0, -555.0)),
    # --- the old city
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


START = (VERGE["pad"][0], VERGE["pad"][1] + 4.0)
STAGES = [
    # --- the long way in. A strike's rhythm: a walk under fire, a room to clear, a place to hold, a gate-keeper, a
    # dark stretch with something to destroy, an open crossing, then the old city and the Crown.
    dict(id="verge", title="Ashfall Verge", objective="Follow the dead highway into the city", kind="travel",
         goal=goal(0.0, -1990.0), radius=1400,
         checkpoint=checkpoint(START[0], START[1], 0.0, (0.0, 0.0)),
         waves=[dict(hunt=False, spawn=[["remnant", 4, "verge_toll"], ["stalker", 2, "verge_toll"]]),
                dict(delay=14.0, maxAlive=3, hunt=False, spawn=[["remnant", 3, "verge_road"], ["veilborn", 1, "verge_road"]])]),
    dict(id="gatehouse", title="The Stacks", objective="Find a way through the gatehouse block", kind="travel",
         goal=goal(0.0, -1912.0), radius=900,
         checkpoint=checkpoint(0.0, -1986.0, 0.0, (0.0, -1900.0)),
         waves=[dict(hunt=False, spawn=[["stalker_feral", 3, "stacks_lobby"], ["remnant", 3, "stacks_lobby"]])]),
    dict(id="yard", title="The Stacks", objective="Clear the yard", kind="clear",
         goal=goal(0.0, -1870.0),
         checkpoint=checkpoint(0.0, -1914.0, 0.0, (0.0, -1820.0)),
         waves=[dict(hunt=False, spawn=[["remnant", 5, "yard_north"], ["stalker", 2, "yard_west"], ["veilborn", 1, "yard_north"]]),
                dict(delay=2.0, maxAlive=3, spawn=[["remnant", 4, "yard_east"], ["stalker", 3, "yard_west"]]),
                dict(delay=2.0, maxAlive=3, spawn=[["remnant_captain", 1, "yard_north"], ["bulwark", 1, "yard_north"], ["remnant", 4, "yard_east"],
                                                   ["veilborn", 1, "yard_west"]])]),
    dict(id="alley", title="The Stacks", objective="Take the alley to the Galleria", kind="travel",
         goal=goal(0.0, -1612.0), radius=1200,
         checkpoint=checkpoint(0.0, -1812.0, 0.0, (0.0, -1700.0)),
         waves=[dict(hunt=False, spawn=[["stalker", 3, "alley_mid"], ["remnant", 2, "alley_mid"]])]),
    dict(id="galleria", title="Meridian Galleria", objective="Reach the rotunda", kind="travel",
         goal=goal(0.0, GALLERIA["rot_n"] - 4.0), radius=1300,
         checkpoint=checkpoint(0.0, -1616.0, 0.0, (0.0, -1500.0)),
         waves=[dict(hunt=False, spawn=[["remnant", 4, "mall_south"], ["veilborn", 2, "mall_gallery_w"], ["stalker", 2, "mall_gallery_e"]])]),
    dict(id="rotunda", title="Meridian Galleria", objective="Hold the rotunda while the service gate cycles", kind="hold", hold=80,
         goal=goal(0.0, GALLERIA["rot_n"]),
         checkpoint=checkpoint(0.0, GALLERIA["rot_n"] - 26.0, 0.0, (0.0, GALLERIA["rot_n"])),
         waves=[dict(spawn=[["remnant", 5, "mall_north"], ["stalker", 2, "mall_shops_w"]]),
                dict(delay=7.0, maxAlive=4, spawn=[["remnant", 4, "mall_shops_e"], ["veilborn", 2, "mall_gallery_w"]]),
                dict(delay=8.0, maxAlive=4, spawn=[["stalker", 3, "mall_north"], ["remnant", 4, "mall_shops_w"], ["veilborn", 1, "mall_gallery_e"]]),
                dict(delay=8.0, maxAlive=4, spawn=[["veilborn_seer", 1, "mall_gallery_w"], ["bulwark", 1, "mall_north"], ["remnant", 4, "mall_shops_e"]])]),
    dict(id="warden", title="Meridian Galleria", objective="Bring down the Warden at the service gate", kind="boss",
         boss="warden", bossGroup="mall_gate", goal=goal(0.0, -1320.0),
         checkpoint=checkpoint(0.0, GALLERIA["rot_n"] + 30.0, 0.0, (0.0, -1320.0)),
         waves=[dict(bossHealth=0.7, spawn=[["remnant", 5, "mall_court"]]),
                dict(bossHealth=0.35, spawn=[["stalker", 3, "mall_court"], ["veilborn", 2, "mall_gallery_e"]])]),
    dict(id="descent", title="Deepline", objective="Go down into the station", kind="travel",
         goal=goal(0.0, -1206.0, DZ), radius=800,
         checkpoint=checkpoint(0.0, -1290.0, 0.0, (0.0, -1240.0)),
         waves=[dict(hunt=False, spawn=[["stalker_feral", 4, "deep_hall"]])]),
    dict(id="hearts", title="Deepline", objective="Destroy the hive's hearts", kind="clear",
         goal=goal(0.0, -1150.0, DZ),
         checkpoint=checkpoint(0.0, -1226.0, DZ, (0.0, -1150.0)),
         waves=[dict(hunt=False, spawn=[["conduit", 3, "deep_hearts"], ["stalker_feral", 4, "deep_tracks"], ["remnant", 3, "deep_platform"]]),
                dict(delay=6.0, maxAlive=6, spawn=[["stalker_feral", 5, "deep_tracks"], ["veilborn", 1, "deep_platform"]]),
                dict(delay=6.0, maxAlive=6, spawn=[["stalker_alpha", 1, "deep_platform"], ["stalker", 2, "deep_platform"], ["stalker_feral", 4, "deep_tracks"]])]),
    dict(id="tunnel", title="Deepline", objective="Follow the tunnel out", kind="travel",
         goal=goal(0.0, -872.0, CANAL), radius=700,
         checkpoint=checkpoint(0.0, -1104.0, DZ, (0.0, -1000.0)),
         waves=[dict(hunt=False, spawn=[["stalker_feral", 4, "tunnel_a"]]),
                dict(delay=10.0, maxAlive=3, spawn=[["stalker_alpha", 1, "tunnel_b"], ["stalker_feral", 4, "tunnel_b"], ["remnant", 2, "tunnel_b"]])]),
    dict(id="sluice", title="The Sluice", objective="Silence the watch on the canal", kind="clear",
         goal=goal(0.0, -700.0, CANAL),
         checkpoint=checkpoint(0.0, -868.0, CANAL, (0.0, -700.0)),
         waves=[dict(hunt=False, spawn=[["veilborn", 4, "sluice_watch"], ["remnant", 5, "sluice_pump"], ["stalker", 2, "sluice_south"]]),
                dict(delay=3.0, maxAlive=4, spawn=[["remnant", 5, "sluice_north"], ["stalker", 3, "sluice_pump"]]),
                dict(delay=3.0, maxAlive=3, spawn=[["remnant_captain", 1, "sluice_north"], ["bulwark", 2, "sluice_north"], ["veilborn_seer", 1, "sluice_pump"]])]),
    dict(id="causeway", title="The Causeway", objective="Climb the spillway to the old approach", kind="travel",
         goal=goal(ENTRY[0], ENTRY[1], 0.0), radius=1200,
         checkpoint=checkpoint(4.0, -600.0, CANAL, (15.0, -555.0)),
         waves=[dict(hunt=False, spawn=[["remnant", 4, "causeway_mid"], ["stalker", 2, "causeway_mid"]])]),
    # --- the old city
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
    dict(id="arch_barrier", opens="alley", c=(0.0, STACKS["arch"]["n0"] + 2.0, 0.0), width=STACKS["arch"]["half"] * 2 + 1.0, height=6.0, yaw=0.0),
    dict(id="galleria_gate", opens="descent", c=(0.0, GALLERIA["n1"], 0.0), width=GALLERIA["gate_half"] * 2 + 1.0, height=6.0, yaw=0.0),
    dict(id="tunnel_barrier", opens="tunnel", c=(0.0, DEEPLINE["plat_n1"] + 10.0, TRACK), width=DEEPLINE["tun_half"] * 2 + 1.0, height=6.5, yaw=0.0),
    dict(id="spillway_barrier", opens="causeway", c=(SLUICE["half"] + 1.0, -555.0, CANAL), width=16.0, height=7.0, yaw=90.0),
    dict(id="terrace_barrier", opens="climb", c=(RAMP["e0"] + 1.0, 0.0, 0.0), width=RAMP["half"] * 2 + 2.0, height=8.0, yaw=90.0),
    dict(id="crown_barrier", opens="bridge", c=(BRIDGE["e"], BRIDGE["n0"] + 1.0, TZ), width=BRIDGE["half"] * 2 + 2.0, height=8.0, yaw=0.0),
]

# The Colossus's shield conduits (destroy all three to break its shield).
PYLONS = ring_points(CROWN["c"], CROWN["pylon_r"], CROWN["pylon_angles"], CROWN["z"])

# Map points (mini-map, map screen): label, subtitle, kind, (E, N, z), fast travel
MAP_POINTS = [
    ("Ashfall Verge", "Where you come in", "FastTravel", (START[0], START[1], 0.0)),
    ("The Stacks", "The housing estate", "Landmark", (0.0, -1870.0, 0.0)),
    ("Meridian Galleria", "The rotunda", "Landmark", (0.0, GALLERIA["rot_n"], 0.0)),
    ("Deepline", "The transit station", "Landmark", (0.0, -1150.0, DZ)),
    ("The Sluice", "The drained canal", "Landmark", (0.0, -700.0, CANAL)),
    ("Meridian Approach", "The old road", "Landmark", (ENTRY[0], ENTRY[1] + 4.0, 0.0)),
    ("Meridian Gate", "The city wall", "Landmark", (0.0, WALL["n"], 0.0)),
    ("Concord Ring", "The central district", "Landmark", (0.0, 0.0, 0.0)),
    ("High Terraces", "The upper sectors", "Landmark", (TERRACE["east_e"], 50.0, TZ)),
    ("The Crown", "The beam", "Mission", (CROWN["c"][0], CROWN["c"][1], CROWN["z"])),
    ("Shuttle to Nexus Prime", "Back to the city", "AreaTravel", (9.0, VERGE["pad"][1] - 6.0, 0.0)),
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
VARIANTS = dict(
    # the gate-keeper of the Galleria (a boss stage of its own)
    warden=dict(species="bulwark", name="The Warden", health=5.0, damage=1.35, speed=1.08, sight=1.5),
    # the ones a squad forms round: tougher, better shots, a name over their heads
    remnant_captain=dict(species="remnant", name="Remnant Captain", health=2.8, damage=1.25, aim=0.75, sight=1.25),
    veilborn_seer=dict(species="veilborn", name="Veilborn Seer", health=2.4, damage=1.3, aim=0.7, sight=1.4),
    stalker_alpha=dict(species="stalker_feral", name="Pack Alpha", health=3.0, damage=1.4, speed=1.12),
)
# The area map: its centre (E, N) and half size (m).
MAP = dict(c=(20.0, -1035.0), half=1420.0)


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
        mapInfo=dict(c=[MAP["c"][1] * 100.0, MAP["c"][0] * 100.0], half=MAP["half"] * 100.0),
        nav=[list(b) for b in NAV],
        rewards=REWARDS,
        **(dict(enemies=ENEMIES) if ENEMIES else {}),
        **(dict(variants=VARIANTS) if VARIANTS else {}),
    )


if __name__ == "__main__":
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(to_json(), f, indent=1)
    print("wrote", OUT)
