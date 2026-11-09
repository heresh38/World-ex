"""Nexus Prime, dressed: every building, door, dock, roof plant, yard, tree, car, street fixture and story detail of
the city, placed from the plan's land use (Data/nexus_plan.json) and the kit's design data (Data/nexus_city.json).

python tools/city/nexus_dress.py

Each building lot answers: who uses it (the use: apartments, offices, a warehouse, a clinic, ...), how they get in
(a lobby on the street front, shop doors under awnings, a service door at the back, loading docks on the alley or
the yard, garage ramps), how it is powered and kept (meter cabinets, transformers, power lines along the back
streets, roof plant: stair bulkheads, air handlers, vents, tanks, panels, exhaust stacks), how it meets the city
(set back by use on its sidewalk, trees, lamps, bins, hydrants, bus stops, parked cars, signals and signs at the
junctions) and what happened to it (wear, repairs, graffiti, boarded and fenced when abandoned, scaffolding and a
crane when going up). Open lots become car parks (cars in their bays), pocket parks, plazas, vacant ground and
fenced substations. Checkpoints guard the gates and the military wing; maintenance crews' sites dot the streets.

Writes:
  Data/nexus_instances.bin   "NXI1", uint32 header length, header JSON {meshes: [{name, path, count, custom,
                             collide, cull (m, 0 = always drawn)}]}, then per mesh `count` float32 records [X, Y, Z (cm, world), yaw (deg),
                             scale x, y, z, custom...] (world X = N, Y = E); ASONexusCity instances them
  Data/nexus_buildings.json  every building: use, footprint, floors, doors (for the people of the next stage)
Mesh axes after import: kit local +X = Blender +x (width / along), local +Y = Blender -y (out of a wall / the front
of a free-standing prop / a car's nose).
"""
import json, math, os, struct, sys
import numpy as np
from shapely.geometry import Polygon, Point, LineString
from shapely.prepared import prep

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from city_uses import USES, OPEN

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "unreal", "ShatteredOrbit", "Data")
K = 0.15                                       # block top (kerb height)
KIT, TREES, VEHICLES = ("/Game/Environments/NexusCity", "/Game/Environments/NexusCity/Trees", "/Game/Environments/NexusCity/Vehicles")
# Vehicles stay out of the city for now (owner, 2026-11-07: no vehicles and no people yet). The placements are kept
# so they can come back with the traffic stage: flip this.
VEHICLES = False
# what a player bumps into: buildings, vehicles and the solid props (small fixtures and wall details do not collide)
COLLIDE = {"NCK_container", "NCK_site_office", "NCK_guard_booth", "NCK_bus_stop", "NCK_barrier_jersey", "NCK_dumpster",
           "NCK_transformer", "NCK_debris", "NCK_loading_dock", "NCK_fence", "NCK_fence_site", "NCK_crane", "NCK_kiosk",
           "NCK_roof_stair", "NCK_roof_hvac", "NCK_roof_tank", "NCK_billboard", "NCK_planter", "NCK_pallets",
           "NCK_power_pole", "NCK_power_pole_tx", "NCK_lamp", "NCK_traffic_light", "NCK_kiosk", "NCK_sculpture"}
# how far (m) the small things stay drawn (0 = always)
CULL = {"NCK_wall_ac": 160, "NCK_cone": 160, "NCK_hydrant": 160, "NCK_bin": 180, "NCK_meter_box": 140, "NCK_graffiti_patch": 200,
        "NCK_repair_patch": 220, "NCK_pallets": 220, "NCK_tool_cart": 160, "NCK_bench": 220, "NCK_stop_sign": 220, "NCK_street_sign": 220,
        "NCK_bollard": 160, "NCK_roof_vents": 260, "NCK_roof_ac": 300, "NCK_wire_set": 500, "NCK_lamp": 900, "NCK_traffic_light": 600}
VEHICLE_KINDS = ["hatch", "sedan", "suv", "pickup", "van"]
PAINTS = [(.82, .82, .8), (.02, .02, .022), (.5, .52, .54), (.18, .19, .2), (.03, .06, .16), (.4, .03, .02),
             (.55, .48, .36), (.04, .12, .06), (.75, .74, .7), (.1, .1, .11)]
RUST = (.16, .07, .03)
STREET_TREES = {"spire": ["CT_cherry", "CT_pear", "CT_birch"], "mixed": ["CT_plane", "CT_linden", "CT_maple"],
                "market": ["CT_linden", "CT_cherry", "CT_plane"], "arena": ["CT_plane", "CT_pear"],
                "housing": ["CT_maple", "CT_linden", "CT_birch", "CT_cherry"], "research": ["CT_birch", "CT_pear"],
                "industrial": ["CT_linden"], "dockyard": ["CT_linden"], "military": ["CT_pear", "CT_birch"],
                "ruins": ["CT_maple", "CT_plane", "CT_shrub_b"]}
PARK_TREES = ["CT_oak", "CT_willow", "CT_pine", "CT_plane", "CT_maple", "CT_birch", "CT_cherry"]
BUSHES = ["CT_shrub_a", "CT_shrub_b", "CT_grass_clump"]
LIT = dict(residential=.32, commercial=.26, industrial=.08, service=.18)
PARK_FILL = dict(spire=.62, arena=.55, mixed=.48, market=.46, research=.42, housing=.4, military=.4, industrial=.35, dockyard=.35, ruins=.12)


class Rng:
    """numpy Generator whose uniform() takes its bounds in either order (small faces make some ranges invert)"""
    def __init__(self, seed):
        self.g = np.random.default_rng(seed)

    def uniform(self, a=0.0, b=1.0, size=None):
        return self.g.uniform(min(a, b), max(a, b), size)

    def __getattr__(self, k):
        return getattr(self.g, k)


# ---------------------------------------------------------------- output
class Out:
    def __init__(self):
        self.m = {}

    def add(self, name, e, n, z, yaw, s=(1, 1, 1), custom=()):
        if name.startswith("CV_") and not VEHICLES:
            return
        if name.startswith("CT_"):
            path = f"{TREES}/SM_{name}"
        elif name.startswith("CV_"):
            path = f"{VEHICLES}/SM_{name}"
        else:
            path = f"{KIT}/SM_{name}"
        solid = name in COLLIDE or name.startswith(("NCB_", "CV_"))
        cull = 0 if name.startswith(("NCB_", "NCK_crane", "NCK_billboard")) else CULL.get(name, 450 if name.startswith(("CV_", "CT_")) else 300)
        rec = self.m.setdefault(name, dict(path=path, custom=len(custom), collide=solid, cull=cull, data=[]))
        rec["data"].append([n * 100.0, e * 100.0, z * 100.0, yaw % 360.0, *s, *custom])

    def write(self, path):
        meshes = [dict(name=k, path=v["path"], count=len(v["data"]), custom=v["custom"], collide=v["collide"], cull=v["cull"]) for k, v in sorted(self.m.items())]
        head = json.dumps(dict(version=1, meshes=meshes)).encode()
        with open(path, "wb") as f:
            f.write(b"NXI1"); f.write(struct.pack("<I", len(head))); f.write(head)
            for k, v in sorted(self.m.items()):
                f.write(np.asarray(v["data"], np.float32).tobytes())
        return sum(len(v["data"]) for v in self.m.values())


# ---------------------------------------------------------------- vectors (plan metres, (E, N))
def unit(v):
    L = math.hypot(*v) or 1e-9
    return (v[0] / L, v[1] / L)


def ccw(v):
    return (-v[1], v[0])


def cw(v):
    return (v[1], -v[0])


def add(p, *terms):
    x, y = p
    for v, s in terms:
        x += v[0] * s; y += v[1] * s
    return (x, y)


def yaw_along(a):
    """local +X onto plan direction a"""
    return math.degrees(math.atan2(a[0], a[1]))


def yaw_out(o):
    """local +Y (out of a wall, a prop's front, a car's nose) onto plan direction o"""
    return math.degrees(math.atan2(-o[1], o[0]))


# ---------------------------------------------------------------- buildings
class Building:
    def __init__(self, c, a, n, W, D, use, lot, rng):
        self.c, self.a, self.n, self.W, self.D, self.use, self.lot, self.rng = c, a, n, W, D, use, lot, rng
        self.spec = USES[use]
        self.doors = []

    def face(self, side, u, out=0.0):
        """a point on a face: front (street), rear, left / right (sides; u runs along the face from its centre)"""
        c, a, n, W, D = self.c, self.a, self.n, self.W, self.D
        if side == "front":
            return add(c, (a, u), (n, -D / 2 - out)), (-n[0], -n[1]), a
        if side == "rear":
            return add(c, (a, u), (n, D / 2 + out)), n, (-a[0], -a[1])
        s = -1 if side == "left" else 1
        return add(c, (a, s * (W / 2 + out)), (n, u)), (a[0] * s, a[1] * s), (n[0] * -s, n[1] * -s)

    def face_len(self, side):
        return self.W if side in ("front", "rear") else self.D


def fit_rect(lot_poly, p0, a, n, u0, u1, v0, v1):
    """shrink a rectangle (u along a from p0, v along n) until it lies in the lot"""
    pp = prep(lot_poly.buffer(.3))
    for _ in range(8):
        corners = [add(p0, (a, u), (n, v)) for u in (u0, u1) for v in (v0, v1)]
        if all(pp.contains(Point(q)) for q in corners):
            return u0, u1, v0, v1
        cu, w = (u0 + u1) / 2, (u1 - u0) * .45
        u0, u1 = cu - w, cu + w
        v1 = v0 + (v1 - v0) * .9
    return None


def plan_buildings(lot, rng):
    """the building(s) a lot holds: setbacks by use, a row of units where the use builds a street wall"""
    use = lot["use"]; spec = USES[use]
    poly = Polygon(lot["poly"])
    (p, q) = lot["front"]
    a = unit((q[0] - p[0], q[1] - p[1])); n = ccw(a)
    cen = poly.centroid
    if (cen.x - p[0]) * n[0] + (cen.y - p[1]) * n[1] < 0:
        n = (-n[0], -n[1])
    us = [(x - p[0]) * a[0] + (y - p[1]) * a[1] for x, y in poly.exterior.coords]
    vs = [(x - p[0]) * n[0] + (y - p[1]) * n[1] for x, y in poly.exterior.coords]
    fs = float(rng.uniform(*spec["front"])); ss = float(rng.uniform(*spec["side"]))
    rear_yard = 12.0 if spec["cat"] == "industrial" else 3.0
    depth = min(float(rng.uniform(*spec["depth"])), max(vs) - fs - rear_yard)
    if depth < 7:
        depth = max(vs) - fs - 1.0
    if depth < 6:
        return []
    u0, u1 = min(us) + ss, max(us) - ss
    spans = []
    if "unit" in spec:
        u = u0
        while u < u1 - spec["unit"][0] * .6:
            w = float(rng.uniform(*spec["unit"]))
            spans.append((u, min(u1, u + w)))
            u += w
    else:
        spans = [(u0, u1)]
    out = []
    for a0, a1 in spans:
        if a1 - a0 < 5.5:
            continue
        r = fit_rect(poly, p, a, n, a0, a1, fs, fs + depth)
        if not r:
            continue
        ru0, ru1, rv0, rv1 = r
        W, D = ru1 - ru0, rv1 - rv0
        if W < 5.5 or D < 5.5:
            continue
        c = add(p, (a, (ru0 + ru1) / 2), (n, (rv0 + rv1) / 2))
        out.append(Building(c, a, n, W, D, use, lot, rng))
    return out


TALL = {"tower", "chamfer", "podium_tower"}
# which side of the unit design should face the street: +1 Blender +y, -1 Blender -y, 0 either
STREET_SIDE = {"courtyard": 1, "lshape": -1, "stepped": -1}


def dress_building(b, city, O, rng, stats, lot_h, wire_hint):
    spec, lot, use = b.spec, b.lot, b.use
    cat = spec["cat"]
    # height: whole floors, the district's height within the use's range
    lo, hi = spec["h"]
    h = float(np.clip(lot_h * rng.uniform(.8, 1.15), lo, hi))
    gf_h = spec["gf_h"]
    floors = max(1, int(round((h - gf_h) / spec["floor"])))
    H = gf_h + floors * spec["floor"]
    # design
    opts = list(spec["designs"])
    if lot["era"] == "old":
        old = [d for d in opts if d[1] in ("brick", "stone", "housing")]
        if old and rng.random() < .6:
            opts = old
    ok = [d for d in opts if d[0] not in TALL or (H >= 30 and min(b.W, b.D) >= 14)]
    shape, style = (ok or [("block", opts[0][1])])[int(rng.integers(len(ok or [1])))]
    if shape == "block" and f"NCB_block_{style}" not in city["designs"]:
        shape, style = opts[0]
    name = f"NCB_{shape}_{style}"
    abandoned = lot["abandoned"]
    wear = lot["wear"]
    seed = float(rng.uniform(0, 100))
    lit = 0.0 if abandoned else LIT[cat]
    # orientation of the unit design (flip 180 so its street side meets the street)
    yaw = yaw_along(b.a)
    want = STREET_SIDE.get(shape, 0)
    plus_y = ccw(b.a)                                  # Blender +y in plan
    street = (-b.n[0], -b.n[1])
    flip = want and ((plus_y[0] * street[0] + plus_y[1] * street[1] > 0) != (want > 0))
    if flip:
        yaw += 180
    ex = (b.a[0] * (-1 if flip else 1), b.a[1] * (-1 if flip else 1))
    ey = (plus_y[0] * (-1 if flip else 1), plus_y[1] * (-1 if flip else 1))
    custom = lambda hh, z0: (b.W, b.D, hh, seed, wear, 1.0 if abandoned else 0.0, lit, z0)
    if spec["gf"]:
        O.add(f"NCB_gf_{spec['gf']}", b.c[0], b.c[1], K, yaw, (b.W, b.D, gf_h), custom(gf_h, 0.0))
    O.add(name, b.c[0], b.c[1], K + gf_h, yaw, (b.W, b.D, H - gf_h), custom(H - gf_h, gf_h))
    stats["buildings"] += 1
    rec = dict(use=use, cat=cat, district=lot["district"], c=[round(b.c[0], 2), round(b.c[1], 2)], a=[round(b.a[0], 4), round(b.a[1], 4)],
               w=round(b.W, 2), d=round(b.D, 2), h=round(H, 1), floors=floors + (1 if gf_h else 0), abandoned=abandoned, doors=[])

    def wall(prop, side, u, z=0.0, out=0.0):
        pt, o, along = b.face(side, u, out)
        O.add(prop, pt[0], pt[1], K + z, yaw_out(o))
        return pt, o

    def door(prop, side, u, kind):
        pt, o = wall(prop, side, u)
        rec["doors"].append(dict(kind=kind, p=[round(pt[0], 2), round(pt[1], 2)], out=[round(o[0], 3), round(o[1], 3)]))

    # ---- entrances
    gf = spec["gf"]
    if abandoned:
        for side in ("front", "rear"):
            for k in range(max(1, int(b.W / 9))):
                wall("NCK_boarded", side, -b.W / 2 + (k + .5) * b.W / max(1, int(b.W / 9)))
        rec["doors"].append(dict(kind="boarded", p=[round(b.c[0], 2), round(b.c[1], 2)], out=[0, 0]))
    elif gf == "shop":
        n_shops = max(1, int((b.W - 2) / 8))
        lobby_at = None
        if use == "mixed" and b.W > 14:
            lobby_at = rng.choice([0, n_shops - 1])
        for k in range(n_shops):
            u = -b.W / 2 + (k + .5) * b.W / n_shops
            if k == lobby_at:
                door("NCK_door_lobby", "front", u, "residents")
            else:
                door(f"NCK_door_shop_{'abcd'[int(rng.integers(4))]}", "front", u, "shop")
                if rng.random() < .18:                              # a cafe's tables on the sidewalk
                    pt, o, al = b.face("front", u + 2.5, 2.6 + float(lot.get("fs", 0)))
                    O.add("NCK_cafe_set", pt[0], pt[1], K, yaw_out(o))
        if rng.random() < .35:
            wall(f"NCK_sign_blade_{'ab'[int(rng.integers(2))]}", "front", rng.choice([-1, 1]) * (b.W / 2 - .6))
    elif gf == "garage":
        n_g = 3 if use == "fire_station" else (2 if b.W > 30 else 1)
        for k in range(n_g):
            door("NCK_door_garage", "front", -b.W / 2 + (k + .5) * b.W / n_g, "vehicles")
        if use == "fire_station":
            door("NCK_door_service", "left", 0, "staff")
            for k in range(min(2, n_g)):
                pt, o, al = b.face("front", -b.W / 2 + (k + .5) * b.W / n_g, 5.0)
                O.add("CV_van", pt[0], pt[1], K, yaw_out(o), custom=(.55, .04, .02))
    elif gf in ("lobby", "service"):
        door("NCK_door_lobby" if gf == "lobby" else "NCK_door_service", "front", float(rng.uniform(-b.W / 5, b.W / 5)), "main")
        if b.W > 40 and gf == "lobby":
            door("NCK_door_service", "front", -b.W / 2 + 3, "side")
    elif gf == "loading":
        door("NCK_door_service", "front", float(rng.uniform(-b.W / 3, b.W / 3)), "staff")
    elif use == "rowhouses":
        door("NCK_door_service", "front", float(rng.uniform(-b.W / 4, b.W / 4)), "home")
        O.add("NCK_bin", *add(b.face("front", b.W / 2 - .8, 1.0)[0], ((0, 0), 0)), K, 0)
    elif use == "hangar":
        pt, o = wall("NCK_door_garage", "front", 0)
        rec["doors"].append(dict(kind="hangar", p=[round(pt[0], 2), round(pt[1], 2)], out=[round(o[0], 3), round(o[1], 3)]))
    # the back: service door, bins, dumpsters; loading docks where trucks can reach (alley, yard or the side)
    if not abandoned:
        if cat != "industrial" and use not in ("rowhouses", "hangar"):
            door("NCK_door_service", "rear", float(rng.uniform(-b.W / 3, b.W / 3)), "service")
            for k in range(1 + int(cat == "commercial")):
                pt, o, al = b.face("rear", -b.W / 2 + 2.5 + k * 2.4, 1.6)
                O.add("NCK_dumpster", pt[0], pt[1], K, yaw_out(o))
        if cat == "industrial" or use in ("market_hall",):
            dock_side = "rear" if (lot.get("alley") or cat == "industrial") else "left"
            n_d = int(np.clip(b.face_len(dock_side) / 12, 1, 5))
            for k in range(n_d):
                u = -b.face_len(dock_side) / 2 + (k + .5) * b.face_len(dock_side) / n_d
                door("NCK_loading_dock", dock_side, u, "goods")
                if rng.random() < .55:                              # a truck backed up to the dock
                    pt, o, al = b.face(dock_side, u, 7.0)
                    O.add(f"CV_{rng.choice(['van', 'box_truck', 'box_truck', 'pickup'])}", pt[0], pt[1], K, yaw_out(o), custom=PAINTS[int(rng.integers(len(PAINTS)))])
            for k in range(int(rng.integers(1, 4))):
                pt, o, al = b.face("rear", float(rng.uniform(-b.W / 2, b.W / 2)), float(rng.uniform(4, 10)))
                O.add(rng.choice(["NCK_pallets", "NCK_pallets", "NCK_dumpster", "NCK_container"]), pt[0], pt[1], K, float(rng.uniform(0, 360)))
        # utilities: the meter cabinet by the service side, a transformer for the big ones
        wall("NCK_meter_box", rng.choice(["left", "right"]), b.D / 2 - 1.5)
        if b.W * b.D > 900:
            pt, o, al = b.face("right" if rng.random() < .5 else "left", b.D / 2 - 4, 2.2)
            O.add("NCK_transformer", pt[0], pt[1], K, yaw_out(o))
        if use == "tower_res" and b.D > 20:
            door("NCK_door_garage", "left", b.D / 4, "residents' parking")
    # ---- facade life: fire escapes on the old walk-ups, window air-con, repairs, graffiti
    if cat == "residential" and lot["era"] in ("old", "mid") and floors >= 3 and use != "tower_res" and not abandoned:
        side = rng.choice(["left", "right", "rear"])
        u = float(rng.uniform(-b.face_len(side) / 4, b.face_len(side) / 4))
        for f in range(1, floors):
            wall("NCK_fire_escape", side, u, gf_h + (f - 1) * spec["floor"] + spec["floor"])
    if cat in ("residential", "commercial") and style in ("brick", "housing", "office", "stone") and lot["era"] != "new":
        for k in range(int(rng.integers(2, 4 + floors * 2))):
            side = rng.choice(["front", "rear", "left"])
            bays = max(1, int(b.face_len(side) / 3.3))
            u = -b.face_len(side) / 2 + (int(rng.integers(bays)) + .5) * b.face_len(side) / bays
            f = int(rng.integers(floors))
            wall("NCK_wall_ac", side, u, gf_h + f * spec["floor"] + .9)
    if wear > .3:
        for k in range(int(rng.integers(0, 3))):
            side = rng.choice(["front", "rear", "left", "right"])
            wall("NCK_repair_patch", side, float(rng.uniform(-b.face_len(side) / 3, b.face_len(side) / 3)), float(rng.uniform(0, max(.1, H - 3))))
    if wear > .45 or abandoned:
        for k in range(int(rng.integers(1, 4 if abandoned else 3))):
            side = rng.choice(["left", "right", "rear", "front"])
            wall("NCK_graffiti_patch", side, float(rng.uniform(-b.face_len(side) / 3, b.face_len(side) / 3)), .2)
    if abandoned:
        for k in range(int(rng.integers(1, 3))):
            pt, o, al = b.face("front", float(rng.uniform(-b.W / 3, b.W / 3)), float(rng.uniform(1.5, 3.5)))
            O.add("NCK_debris", pt[0], pt[1], K, float(rng.uniform(0, 360)))
    # ---- the roof: access, plant, panels, signs
    roof = city["designs"].get(name, {}).get("roof")
    if roof and not abandoned:
        x0, x1, y0, y1, rz = roof
        z = K + gf_h + rz * (H - gf_h)
        def roof_pt(fx, fy):
            bx, by = x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy
            return add(b.c, (ex, bx * b.W), (ey, by * b.D))
        rw, rd = (x1 - x0) * b.W, (y1 - y0) * b.D
        items = ["NCK_roof_stair"]
        if cat == "commercial" or use in ("lab", "clinic", "hotel"):
            items += ["NCK_roof_hvac"] * int(np.clip(rw * rd / 300, 1, 4)) + ["NCK_roof_vents", "NCK_roof_ac"]
        elif cat == "residential":
            items += ["NCK_roof_tank"] if lot["era"] != "new" else ["NCK_roof_solar", "NCK_roof_solar"]
            items += ["NCK_roof_vents", "NCK_roof_ac"]
        elif cat == "industrial":
            items += ["NCK_roof_vents", "NCK_exhaust_stack"] if use == "factory" else ["NCK_roof_vents"]
        else:
            items += ["NCK_roof_hvac", "NCK_roof_vents"]
        if H > 60 and rng.random() < .6:
            items.append("NCK_roof_mast")
        slots = [(fx, fy) for fx in np.linspace(.18, .82, max(1, int(rw / 7))) for fy in np.linspace(.2, .8, max(1, int(rd / 7)))]
        rng.shuffle(slots)
        for item, (fx, fy) in zip(items, slots):
            pt = roof_pt(fx, fy)
            O.add(item, pt[0], pt[1], z, yaw + 90 * int(rng.integers(4)))
        if cat == "commercial" and H < 40 and lot.get("street") and rng.random() < .22:   # a billboard to the street
            pt = roof_pt(.5, .5)
            O.add("NCK_billboard", pt[0], pt[1], z, yaw_out((-b.n[0], -b.n[1])))
    # ---- yards: fenced works, depots, schools and posts
    if (cat == "industrial" or use in ("security", "barracks", "school")) and not abandoned:
        fence_lot(lot, O, rng, "NCK_fence", gate_w=9.0, sides=[LineString(lot["front"])])
        if use in ("security", "barracks"):
            fp, fo = Building.face(b, "front", 0, max(2.0, b.D * 0))[:2]
            q = add(fp, (fo, 4.0), (b.a, 5.0))
            O.add("NCK_guard_booth", q[0], q[1], K, yaw_out(fo))
        if cat == "industrial":
            for k in range(int(rng.integers(0, 5))):
                pt, o, al = b.face("front", float(rng.uniform(-b.W / 2 + 3, b.W / 2 - 3)), float(rng.uniform(3, 6)))
                O.add(f"CV_{rng.choice(VEHICLE_KINDS)}", pt[0], pt[1], K, yaw_out(o), custom=PAINTS[int(rng.integers(len(PAINTS)))])
    stats[use] += 1
    return rec


def fence_lot(lot, O, rng, prop, gate_w=8.0, kerb=K, skip_front=False, sides=None):
    """a fence along the lot's edge in 3 m panels with a gate gap in the middle of the street front; sides: only the
    edges near these lines (the street front, the alley), not the boundaries shared with the neighbours"""
    poly = Polygon(lot["poly"]).buffer(-.5, join_style=2)
    if poly.is_empty or poly.geom_type != "Polygon":
        return
    front = lot.get("front")
    mid = ((front[0][0] + front[1][0]) / 2, (front[0][1] + front[1][1]) / 2) if front else None
    pts = list(poly.exterior.coords)
    for i in range(len(pts) - 1):
        p, q = pts[i], pts[i + 1]
        L = math.dist(p, q)
        if L < 1:
            continue
        a = unit((q[0] - p[0], q[1] - p[1]))
        k = 0
        while k * 3 + 1.5 <= L:
            c = add(p, (a, k * 3 + 1.5))
            if mid and math.dist(c, mid) < gate_w / 2 + 1.5:
                k += 1
                continue
            if skip_front and front and LineString(front).distance(Point(c)) < 2:
                k += 1
                continue
            if sides is not None and min(s.distance(Point(c)) for s in sides) > 6:
                k += 1
                continue
            O.add(prop, c[0], c[1], kerb, yaw_along(a))
            k += 1


# ---------------------------------------------------------------- open lots
def scatter(poly, spacing, rng, margin=2.0):
    inner = poly.buffer(-margin)
    if inner.is_empty:
        return []
    pp = prep(inner)
    x0, y0, x1, y1 = inner.bounds
    out = []
    for x in np.arange(x0, x1, spacing):
        for y in np.arange(y0, y1, spacing):
            q = (x + rng.uniform(-.35, .35) * spacing, y + rng.uniform(-.35, .35) * spacing)
            if pp.contains(Point(q)):
                out.append(q)
    return out


def dress_open(lot, O, rng, stats):
    use = lot["use"]; poly = Polygon(lot["poly"]); kind = lot["kind"]
    if use == "parking":
        a, n = lot["bay_a"], lot["bay_n"]
        fill = PARK_FILL.get(kind, .5)
        for e, nn, s in lot["bays"]:
            if rng.random() < fill:
                o = (n[0] * s, n[1] * s)
                paint = RUST if lot["abandoned"] or kind == "ruins" and rng.random() < .5 else PAINTS[int(rng.integers(len(PAINTS)))]
                O.add(f"CV_{rng.choice(VEHICLE_KINDS, p=[.28, .3, .22, .1, .1])}", e + rng.uniform(-.15, .15), nn + rng.uniform(-.1, .1), K + .01,
                      yaw_out(o) + rng.uniform(-3, 3), custom=paint)
                stats["parked cars"] += 1
        for q in scatter(poly, 32, rng, 1.0)[:8]:
            O.add("NCK_lamp", q[0], q[1], K, float(rng.uniform(0, 360)))
        if lot.get("front") and kind in ("spire", "arena", "mixed", "research") and rng.random() < .4:
            (p, q) = lot["front"]
            m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            ax = unit((q[0] - p[0], q[1] - p[1]))
            O.add("NCK_barrier_arm", *add(m, (ax, -3)), K, yaw_along(ax))
            O.add("NCK_guard_booth", *add(m, (ax, -6), (n, 2.5)), K, yaw_out(n))
    elif use == "park":
        if lot.get("front"):                                              # a hedge along the street, a gap for the gate
            (p, q) = lot["front"]
            ax = unit((q[0] - p[0], q[1] - p[1])); L = math.dist(p, q)
            inward = ccw(ax)
            if (poly.centroid.x - p[0]) * inward[0] + (poly.centroid.y - p[1]) * inward[1] < 0:
                inward = (-inward[0], -inward[1])
            for k in range(int(L / 3)):
                if abs(k * 3 + 1.5 - L / 2) < 3:
                    continue
                h = add(p, (ax, k * 3 + 1.5), (inward, 1.0))
                O.add("CT_hedge", h[0], h[1], K, yaw_along(ax))
        trees = scatter(poly, float(rng.uniform(9, 13)), rng, 2.5)
        for q in trees:
            if rng.random() < .8:
                O.add(str(rng.choice(PARK_TREES)), q[0], q[1], K, float(rng.uniform(0, 360)), (s := float(rng.uniform(.75, 1.05)),) * 3)
            else:
                O.add(str(rng.choice(BUSHES)), q[0], q[1], K, float(rng.uniform(0, 360)))
        for q in scatter(poly, 22, rng, 4)[:10]:
            yaw = float(rng.uniform(0, 360))
            O.add("NCK_bench", q[0], q[1], K, yaw)
            if rng.random() < .5:
                O.add("NCK_bin", q[0] + 1.6, q[1], K, yaw)
        for q in scatter(poly, 30, rng, 2)[:6]:
            O.add("NCK_lamp", q[0], q[1], K, float(rng.uniform(0, 360)))
        stats["parks"] += 1
    elif use == "plaza":
        spots = scatter(poly, 9, rng, 2.0)
        rng.shuffle(spots)
        for i, q in enumerate(spots[:14]):
            r = rng.random()
            yaw = float(rng.uniform(0, 4)) // 1 * 90
            if r < .3:
                O.add("NCK_planter", q[0], q[1], K, yaw)
                O.add(str(rng.choice(["CT_cherry", "CT_pear"])), q[0], q[1], K + .7, float(rng.uniform(0, 360)), (.6, .6, .6))
            elif r < .5:
                O.add("NCK_bench", q[0], q[1], K, yaw)
            elif r < .6:
                O.add("NCK_ad_column", q[0], q[1], K, yaw)
            elif r < .7:
                O.add("NCK_kiosk", q[0], q[1], K, yaw)
            elif r < .78:
                O.add("NCK_bike_rack", q[0], q[1], K, yaw)
            elif r < .9:
                O.add("NCK_bin", q[0], q[1], K, yaw)
            else:
                O.add("NCK_lamp", q[0], q[1], K, yaw)
        if poly.area > 1500 and rng.random() < .5:
            c = poly.representative_point()
            O.add("NCK_sculpture", c.x, c.y, K, float(rng.uniform(0, 360)))
        stats["plazas"] += 1
    elif use == "vacant":
        if lot.get("front"):
            fence_lot(lot, O, rng, "NCK_fence", gate_w=4.0, sides=[LineString(lot["front"])])
        for q in scatter(poly, 7, rng, 1.5):
            r = rng.random()
            if r < .25:
                O.add(str(rng.choice(BUSHES)), q[0], q[1], K, float(rng.uniform(0, 360)), (s := float(rng.uniform(.6, 1.0)),) * 3)
            elif r < .32:
                O.add("NCK_debris", q[0], q[1], K, float(rng.uniform(0, 360)))
            elif r < .34:
                O.add(f"CV_{rng.choice(VEHICLE_KINDS)}", q[0], q[1], K, float(rng.uniform(0, 360)), custom=RUST)
        stats["vacant"] += 1
    elif use == "substation":
        fence_lot(lot, O, rng, "NCK_fence", gate_w=5.0)
        for q in scatter(poly, 6.5, rng, 3.5)[:20]:
            O.add("NCK_transformer", q[0], q[1], K, 0.0 if rng.random() < .5 else 90.0)
        for q in scatter(poly, 18, rng, 2)[:4]:
            O.add("NCK_power_pole_tx", q[0], q[1], K, float(rng.uniform(0, 360)))
        stats["substations"] += 1


def dress_construction(lot, city, O, rng, stats):
    """a building going up: the frame, scaffolding on the street face, a crane, the site fence, site office, stores"""
    use = "office" if lot["kind"] in ("spire", "research", "arena") else "apartments"
    tmp = dict(lot, use=use)
    bs = plan_buildings(tmp, rng) if lot.get("front") else []
    fence_lot(lot, O, rng, "NCK_fence_site", gate_w=7.0)
    poly = Polygon(lot["poly"])
    if bs:
        b = bs[0]
        H = float(np.clip(lot["h"], 18, 90))
        style = "office" if use == "office" else "housing"
        O.add(f"NCB_frame_{style}", b.c[0], b.c[1], K, yaw_along(b.a), (b.W, b.D, H), (b.W, b.D, H, 0, .2, 0, 0, 0))
        built = H * .17
        for k in range(int(b.W / 3)):
            for f in range(max(1, int(built / 3.2)) + 1):
                pt, o, al = b.face("front", -b.W / 2 + 1.5 + k * 3, 0)
                O.add("NCK_scaffold", pt[0], pt[1], K + f * 3.2, yaw_out(o))
        side = b.face("right", 0, 8)[0]
        O.add("NCK_crane", side[0], side[1], K, float(rng.uniform(0, 360)), (1, 1, float(np.clip(H / 50, .8, 1.6))))
        office = b.face("left", -b.D / 4, 5)[0]
        O.add("NCK_site_office", office[0], office[1], K, yaw_along(b.n))
    for q in scatter(poly, 9, rng, 3)[:10]:
        O.add(str(rng.choice(["NCK_pallets", "NCK_container", "NCK_debris", "NCK_pallets", "NCK_dumpster"])), q[0], q[1], K, float(rng.uniform(0, 4)) // 1 * 90)
    if lot.get("front"):
        (p, q) = lot["front"]
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        ax = unit((q[0] - p[0], q[1] - p[1]))
        for k in range(-3, 4):
            O.add("NCK_cone", *add(m, (ax, k * 1.2), (ccw(ax), -1.0)), K, 0)
    stats["construction"] += 1


# ---------------------------------------------------------------- streets
def dress_streets(plan, O, rng, stats, dist_of):
    # roads crossing the landmark grounds (Spire plaza, parks, arena, dome, dock pads) keep their lamps but no kerb
    # furniture: those grounds are furnished as places of their own
    from shapely import affinity
    grounds = [prep(affinity.scale(Point(L["centre"]).buffer(1, 48), L["radius"][0], L["radius"][1])) for L in plan["landmarks"].values()]
    open_ground = lambda q: any(g.contains(Point(q)) for g in grounds)
    roads = plan["roads"]
    nodes = roads["nodes"]
    deg, wmax, classes = {}, {}, {}
    for e in roads["edges"]:
        for k in (e["a"], e["b"]):
            deg[k] = deg.get(k, 0) + 1
            wmax[k] = max(wmax.get(k, 0), e["w"])
            classes.setdefault(k, set()).add(e["cls"])
    radius = {k: (wmax[k] / 2 + 1.0 if deg[k] >= 3 else 0.0) for k in deg}
    lanes = {"highway": (4, 3.7, .35), "ring": (3, 3.6, .35), "primary": (2, 3.5, .35), "secondary": (1, 3.6, .1), "access": (1, 3.3, .1)}
    powered = {"industrial", "dockyard", "housing", "ruins", "military"}
    for ei, e in enumerate(roads["edges"]):
        pts = e["pts"]; w = e["w"]; cls = e["cls"]
        line = LineString(pts)
        L = line.length
        mid = line.interpolate(.5, normalized=True)
        kind = dist_of((mid.x, mid.y))
        r0 = radius.get(e["a"], 0) + 6; r1 = L - radius.get(e["b"], 0) - 6
        if r1 - r0 < 8:
            continue

        def at(s, off):
            s = min(max(s, 0), L)
            p = line.interpolate(s)
            p2 = line.interpolate(min(L, s + .5)); p1 = line.interpolate(max(0, s - .5))
            t = unit((p2.x - p1.x, p2.y - p1.y))
            lft = ccw(t)
            return (p.x + lft[0] * off, p.y + lft[1] * off), t, lft

        trees = STREET_TREES.get(kind, ["CT_linden"])
        bus_s = []
        if cls in ("primary", "ring") and L > 150:
            for s in np.arange(r0 + 60, r1 - 30, 420):
                bus_s.append(s)
                q, t, lft = at(s, -(w / 2 + 2.6))                       # right-hand side
                O.add("NCK_bus_stop", q[0], q[1], K, yaw_out(lft))
                stats["bus stops"] += 1
                if rng.random() < .25:                                    # a bus at the stop, doors to the kerb
                    bq, bt, bl_ = at(s, -(w / 2 - 1.5))
                    O.add("CV_bus", bq[0], bq[1], .01, yaw_out(bt), custom=(.08, .3, .45))
        for side in (-1, 1):
            # lamps, trees between them, hydrants, bins, benches: the kerb-side furniture strip
            lamp_s = np.arange(r0 + (0 if side > 0 else 18), r1, 36.0)
            for s in lamp_s:
                q, t, lft = at(s, side * (w / 2 + .7))
                O.add("NCK_lamp", q[0], q[1], K, yaw_out((-lft[0] * side, -lft[1] * side)))
                stats["lamps"] += 1
            if kind not in ("dockyard",) and cls != "highway":
                s = r0 + 6 + float(rng.uniform(0, 4))
                while s < r1 - 4:
                    if min((abs(s - x) for x in lamp_s), default=99) > 5 and all(abs(s - b) > 9 for b in bus_s):
                        q, t, lft = at(s, side * (w / 2 + 1.7))
                        sc = float(rng.uniform(.85, 1.1))
                        if not open_ground(q):
                            O.add(str(rng.choice(trees)), q[0], q[1], K, float(rng.uniform(0, 360)), (sc, sc, sc))
                        stats["street trees"] += 1
                    s += float(rng.uniform(11, 15))
            for s in np.arange(r0 + 20, r1, 95):
                q, t, lft = at(s + float(rng.uniform(-5, 5)), side * (w / 2 + .5))
                if not open_ground(q):
                    O.add("NCK_hydrant", q[0], q[1], K, yaw_out((-lft[0] * side, -lft[1] * side)))
            for s in np.arange(r0 + 12, r1, 55):
                q, t, lft = at(s + float(rng.uniform(-6, 6)), side * (w / 2 + .9))
                if open_ground(q):
                    continue
                O.add("NCK_bin", q[0], q[1], K, yaw_out((-lft[0] * side, -lft[1] * side)))
                if kind in ("spire", "market", "mixed", "arena", "housing") and rng.random() < .3:
                    q, t, lft = at(s + 3, side * (w / 2 + 3.2))
                    O.add("NCK_bench", q[0], q[1], K, yaw_out((-lft[0] * side, -lft[1] * side)))
            # parked cars along the kerb (not on the ring / highways, clear of junctions and bus stops)
            if cls in ("primary", "secondary", "access"):
                n_l, lw, med = lanes[cls]
                fill = PARK_FILL.get(kind, .5) * .8
                s = r0 + 8
                while s < r1 - 8:
                    if all(abs(s - b) > 16 for b in bus_s) and rng.random() < fill:
                        q, t, lft = at(s, side * (w / 2 - 1.25))
                        travel = t if side < 0 else (-t[0], -t[1])            # cars face the way their lane runs
                        paint = RUST if kind == "ruins" and rng.random() < .4 else PAINTS[int(rng.integers(len(PAINTS)))]
                        O.add(f"CV_{rng.choice(VEHICLE_KINDS, p=[.3, .3, .2, .1, .1])}", q[0], q[1], .01, yaw_out(travel), custom=paint)
                        stats["kerbside cars"] += 1
                    s += float(rng.uniform(6.0, 7.2))
        # power lines on the back streets of the working and older districts
        if cls in ("secondary", "access") and kind in powered and L > 60:
            span = 36.0
            ss = np.arange(r0, r1, span)
            prev = None
            for i, s in enumerate(ss):
                q, t, lft = at(s, w / 2 + 3.9)
                O.add("NCK_power_pole_tx" if i % 5 == 2 else "NCK_power_pole", q[0], q[1], K, yaw_along(lft))
                if prev:
                    d = (q[0] - prev[0], q[1] - prev[1])
                    O.add("NCK_wire_set", prev[0], prev[1], K + 10.3, yaw_along(unit(d)), (math.hypot(*d), 1, 1))
                prev = q
            stats["power poles"] += len(ss)
    # junctions: signals on the main roads, stop signs on the small ones, a name sign on a corner
    edges_at = {}
    for e in roads["edges"]:
        edges_at.setdefault(e["a"], []).append((e, False)); edges_at.setdefault(e["b"], []).append((e, True))
    for k, lst in edges_at.items():
        if deg.get(k, 0) < 3:
            continue
        main = bool(classes[k] & {"highway", "ring", "primary"}) or deg[k] >= 4
        p0 = nodes[k]
        for i, (e, at_end) in enumerate(lst):
            pts = e["pts"]
            nxt = pts[-2] if at_end else pts[1]
            t = unit((nxt[0] - p0[0], nxt[1] - p0[1]))                    # from the junction along the arm
            incoming = (-t[0], -t[1])
            right = cw(incoming)
            corner = add(p0, (t, radius[k] + 1.5), (right, e["w"] / 2 + .9))
            if main:
                O.add("NCK_traffic_light", corner[0], corner[1], K, yaw_out((-right[0], -right[1])))
                stats["signals"] += 1
            elif e["cls"] in ("access", "secondary"):
                O.add("NCK_stop_sign", corner[0], corner[1], K, yaw_out(t))
            if i == 0:
                c2 = add(p0, (t, radius[k] + 1.5), (right, -(e["w"] / 2 + .9)))
                O.add("NCK_street_sign", c2[0], c2[1], K, yaw_along(t))


def checkpoints(plan, O, rng, stats, military):
    """the gates' inner checkpoints and the posts where roads enter the military wing"""
    sites = []
    edges = plan["roads"]["edges"]
    for gname, g in plan["gates"].items():
        best = None
        for e in edges:
            if e["cls"] != "highway":
                continue
            for end in (0, -1):
                d = math.dist(e["pts"][end], g)
                if best is None or d < best[0]:
                    best = (d, e, end)
        if best and best[0] < 400:
            e, end = best[1], best[2]
            line = LineString(e["pts"] if end == 0 else e["pts"][::-1])
            sites.append((line, 140.0, e["w"], f"{gname} gate"))
    for e in edges:
        if e["cls"] not in ("primary", "secondary"):
            continue
        line = LineString(e["pts"])
        cross = line.intersection(military.boundary)
        for p in getattr(cross, "geoms", [cross]):
            if p.geom_type != "Point":
                continue
            s = line.project(p)
            inside = military.contains(line.interpolate(min(line.length, s + 10)))
            sl = LineString(e["pts"]) if inside else LineString(e["pts"][::-1])
            sites.append((sl, sl.project(p) + 18, e["w"], "military wing"))
    out = []
    for line, s, w, label in sites:
        if line.length < s + 5:
            continue
        p = line.interpolate(s); p2 = line.interpolate(s + 1)
        t = unit((p2.x - p.x, p2.y - p.y)); lft = ccw(t)
        c = (p.x, p.y)
        for side in (-1, 1):
            post = add(c, (lft, side * (w / 2 - .4)))
            O.add("NCK_barrier_arm", post[0], post[1], .0, yaw_along((-lft[0] * side, -lft[1] * side)))
            booth = add(c, (lft, side * (w / 2 + 2.6)), (t, 4 * side))
            O.add("NCK_guard_booth", booth[0], booth[1], K, yaw_out((-lft[0] * side, -lft[1] * side)))
            for k in range(3):
                j = add(c, (t, -12 - k * 7), (lft, side * (w / 4 - (k % 2) * 3)))
                O.add("NCK_barrier_jersey", j[0], j[1], 0, yaw_along(t))
            for k in range(5):
                q = add(c, (t, -4 - k * 2.5), (lft, side * .6))
                O.add("NCK_cone", q[0], q[1], 0, 0)
        out.append(dict(label=label, p=[round(c[0], 1), round(c[1], 1)], dir=[round(t[0], 3), round(t[1], 3)]))
        stats["checkpoints"] += 1
    return out


def maintenance(plan, O, rng, stats, n=80):
    """crew sites on the streets: an open manhole in a lane, coned off, the crew's van and tool cart, barriers"""
    edges = [e for e in plan["roads"]["edges"] if e["cls"] in ("primary", "secondary", "access") and e["len"] > 80]
    out = []
    for i in rng.choice(len(edges), size=min(n, len(edges)), replace=False):
        e = edges[i]
        line = LineString(e["pts"]); s = line.length * float(rng.uniform(.3, .7))
        p = line.interpolate(s); p2 = line.interpolate(s + 1)
        t = unit((p2.x - p.x, p2.y - p.y)); right = cw(t)
        lane = 2.0 if e["cls"] != "primary" else 5.4
        c = add((p.x, p.y), (right, lane))
        O.add("NCK_manhole_open", c[0], c[1], 0, yaw_along(t))
        for k in range(8):
            a = 2 * math.pi * k / 8
            O.add("NCK_cone", c[0] + math.cos(a) * 2.6, c[1] + math.sin(a) * 2.6, 0, 0)
        van = add(c, (t, -9))
        O.add("CV_van", van[0], van[1], .01, yaw_out(t), custom=(.85, .55, .02))
        cart = add(c, (t, 3.5), (right, .8))
        O.add("NCK_tool_cart", cart[0], cart[1], 0, yaw_along(t))
        bar = add(c, (t, -16))
        O.add("NCK_barrier_jersey", bar[0], bar[1], 0, yaw_along(right))
        out.append(dict(p=[round(c[0], 1), round(c[1], 1)], dir=[round(t[0], 3), round(t[1], 3)]))
        stats["crew sites"] += 1
    return out


def main():
    plan = json.load(open(os.path.join(DATA, "nexus_plan.json")))
    city = json.load(open(os.path.join(DATA, "nexus_city.json")))
    rng = Rng(11)
    O = Out()
    from collections import Counter
    stats = Counter()
    districts = [(Polygon(d["poly"]), d["kind"]) for k, d in plan["districts"].items() if k != "spire"]
    spire = Polygon(plan["districts"]["spire"]["poly"])

    def dist_of(p):
        if spire.contains(Point(p)):
            return "spire"
        for poly, kind in districts:
            if poly.contains(Point(p)):
                return kind
        return "mixed"

    buildings = []
    for lot in plan["lots"]:
        lrng = Rng(lot["seed"])
        use = lot["use"]
        if use == "construction":
            dress_construction(lot, city, O, lrng, stats)
            continue
        if use in OPEN:
            dress_open(lot, O, lrng, stats)
            continue
        if not lot.get("front"):
            continue
        bs = plan_buildings(lot, lrng)
        if not bs:
            dress_open(dict(lot, use="park" if lot["kind"] not in ("industrial", "dockyard", "ruins") else "vacant"), O, lrng, stats)
            continue
        for b in bs:
            buildings.append(dress_building(b, city, O, lrng, stats, lot["h"], None))
    dress_streets(plan, O, rng, stats, dist_of)
    mil = next(Polygon(d["poly"]) for d in plan["districts"].values() if d["kind"] == "military")
    posts = checkpoints(plan, O, rng, stats, mil)
    crews = maintenance(plan, O, rng, stats)
    n = O.write(os.path.join(DATA, "nexus_instances.bin"))
    json.dump(dict(version=1, buildings=buildings, checkpoints=posts, crew_sites=crews),
              open(os.path.join(DATA, "nexus_buildings.json"), "w"), separators=(",", ":"))
    print(f"[nexus_dress] {n} instances of {len(O.m)} meshes; " + ", ".join(f"{k} {v}" for k, v in stats.most_common()))
    big = sorted(((len(v['data']), k) for k, v in O.m.items()), reverse=True)[:12]
    print("[nexus_dress] most:", ", ".join(f"{k} {c}" for c, k in big))


if __name__ == "__main__":
    main()
