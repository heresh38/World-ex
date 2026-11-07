"""Nexus Prime: the city plan, traced from the owner's master plan (art/reference/nexus_prime_plan.png) and scaled to a
real city (~8.4 x 5.4 km inside the wall). One JSON is the single source for the meshes, the level, the map and later
the NPC, traffic and train routes.

python tools/city/nexus_plan.py [out.json] [preview.png]

Coordinates: metres, +E east, +N north, the Spire at the origin (Unreal: X = north, Y = east).
Writes:
  wall        closed polygon (inner face), gates {N, S, E, W}
  roads       noded network: nodes [[e, n]], edges [{a, b, cls, w, pts}] (every crossing is a node)
  metro       elevated loop polyline + hubs (stations)
  rail        express lines (polylines) + stations
  districts   {name: {poly, kind, label}}; landmarks (dock pads, arena bowl, refuge park, spire plaza)
  blocks      polygons between the roads (edge = kerb), per district; a 4.5 m sidewalk inside the kerb
  alleys      7 m service lanes through deep blocks (centre lines), reaching the kerb at both ends
  lots        the developable land, each with a use (apartments, office, warehouse, parking, park, ...), its street
              front edge (or alley front), alley access, wear, era, abandoned, seed
"""
import json, math, os, sys
import numpy as np
from shapely.geometry import LineString, MultiLineString, Point, Polygon, MultiPolygon, box
from shapely.ops import unary_union, polygonize, split
from shapely import affinity

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "unreal/ShatteredOrbit/Data/nexus_plan.json")
PREVIEW = sys.argv[2] if len(sys.argv) > 2 else None

# Traced on a 1400 px wide copy of the master plan. The Spire is at (645, 340). The plan is drawn in perspective (the
# north-south axis is foreshortened), so north-south gets the larger scale. ~8.4 km E-W x 5.4 km N-S inside the wall.
CX, CY = 645.0, 335.0
SE, SN = 7.6, 8.7


def m(p):
    return (round((p[0] - CX) * SE, 1), round((CY - p[1]) * SN, 1))


def ml(pts):
    return [m(p) for p in pts]


def ellipse(cx, cy, rx, ry, n=96, a0=0.0, a1=2 * math.pi, closed=True):
    k = n + (1 if closed else 0)
    return [m((cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy - ry * math.sin(a0 + (a1 - a0) * i / n))) for i in range(k)]


# ---------------------------------------------------------------- traced from the plan
WALL = ml([(250, 82), (1040, 82), (1182, 210), (1208, 600), (1080, 692), (330, 692), (112, 520), (128, 232)])
GATES = {"N": m((645, 82)), "S": m((645, 692)), "W": m((120, 330)), "E": m((1194, 330))}
WIDTH = {"highway": 32.0, "ring": 28.0, "primary": 20.0, "secondary": 14.0, "access": 10.0}

ROADS = []          # (cls, [points in metres])
def road(cls, pts, px=True):
    ROADS.append((cls, ml(pts) if px else pts))

# outer ring road just inside the wall
ring = [(262, 108), (1028, 108), (1152, 222), (1176, 590), (1066, 664), (344, 664), (142, 506), (156, 242)]
road("ring", ring + [ring[0]])
# the inner (Spire) ring and the metro loop's service road
road("ring", [], px=False); ROADS.pop()
ROADS.append(("ring", ellipse(CX, CY + 5, 122, 78)))
ROADS.append(("primary", ellipse(CX, CY + 5, 232, 146)))          # boulevard outside the metro loop
# major highways from the gates to the Spire ring
road("highway", [(645, 82), (645, 108), (645, 262)])
road("highway", [(645, 418), (645, 664), (645, 692)])
road("highway", [(120, 330), (156, 330), (523, 333)])
road("highway", [(767, 333), (1176, 330), (1194, 330)])
# the two cross highways (north and south bands)
road("highway", [(168, 265), (440, 262), (560, 230)])
road("highway", [(730, 230), (850, 262), (1160, 265)])
road("highway", [(150, 455), (440, 455), (560, 470)])
road("highway", [(730, 470), (850, 455), (1178, 455)])
# radial primaries from the Spire ring to the outer ring (the diagonals)
for ang in (45, 135, 225, 315):
    a = math.radians(ang)
    p0 = (CX + 122 * math.cos(a), CY + 5 - 78 * math.sin(a))
    p1 = (CX + 560 * math.cos(a), CY + 5 - 360 * math.sin(a))
    ROADS.append(("primary", ml([p0, p1])))
# district main streets (primary) seen on the plan
road("primary", [(445, 108), (445, 262)]); road("primary", [(850, 108), (850, 262)])
road("primary", [(300, 265), (300, 455)]); road("primary", [(990, 265), (990, 455)])
road("primary", [(445, 455), (445, 664)]); road("primary", [(990, 455), (990, 664)])
road("primary", [(560, 470), (560, 664)]); road("primary", [(740, 470), (740, 664)])
road("primary", [(156, 380), (430, 380)]); road("primary", [(860, 395), (1170, 395)])

METRO = ellipse(CX, CY + 5, 215, 136)
HUBS = [m((CX + 215 * math.cos(math.radians(a)), CY + 5 - 136 * math.sin(math.radians(a)))) for a in range(0, 360, 45)]
RAIL = {
    "express_west_ne": ml([(112, 365), (300, 362), (430, 350), (540, 340), (645, 335), (720, 300), (790, 250),
                           (900, 205), (1010, 175), (1170, 172)]),
    "express_se": ml([(645, 335), (700, 395), (775, 450), (800, 560), (820, 630), (950, 625), (1060, 600),
                      (1150, 560), (1200, 540)]),
}
RAIL_STATIONS = {"West Terminal": m((300, 362)), "Spire Central": m((645, 335)), "Research": m((900, 205)),
                 "Industrial": m((800, 560)), "Outer Reaches": m((1060, 600))}

DISTRICTS = {
    "orbital_dockyard": dict(label="Orbital Dockyard", kind="dockyard",
                             poly=ml([(156, 242), (262, 108), (560, 108), (560, 230), (440, 262), (168, 265)])),
    "north_quarter": dict(label="North Quarter", kind="mixed", poly=ml([(560, 108), (730, 108), (730, 230), (645, 205), (560, 230)])),
    "research_sector": dict(label="Research Sector", kind="research",
                            poly=ml([(730, 108), (1028, 108), (1152, 222), (1160, 265), (850, 262), (730, 230)])),
    "market_district": dict(label="Market District", kind="market", poly=ml([(156, 265), (440, 262), (430, 455), (150, 455)])),
    "arena_complex": dict(label="Arena Complex", kind="arena", poly=ml([(850, 262), (1160, 265), (1176, 455), (860, 455)])),
    "military_wing": dict(label="Military Wing", kind="military",
                          poly=ml([(150, 455), (440, 455), (560, 470), (560, 664), (344, 664), (142, 506)])),
    "the_refuge": dict(label="The Refuge", kind="housing", poly=ml([(560, 470), (740, 470), (740, 664), (560, 664)])),
    "industrial_zone": dict(label="Industrial Zone", kind="industrial", poly=ml([(740, 470), (990, 455), (990, 664), (740, 664)])),
    "outer_reaches": dict(label="The Outer Reaches", kind="ruins", poly=ml([(990, 455), (1178, 455), (1176, 590), (1066, 664), (990, 664)])),
}
SPIRE = dict(label="The Spire", kind="spire", poly=ellipse(CX, CY + 5, 215, 136, 64))
LANDMARKS = {
    "dock_pads": dict(kind="dock_ring", centre=m((300, 190)), radius=[105 * SE, 72 * SN]),
    "arena_bowl": dict(kind="arena", centre=m((930, 335)), radius=[62 * SE, 42 * SN]),
    "refuge_park": dict(kind="park", centre=m((645, 575)), radius=[85 * SE, 48 * SN]),
    "spire_plaza": dict(kind="plaza", centre=m((CX, CY + 5)), radius=[55 * SE, 35 * SN]),
    "research_dome": dict(kind="dome", centre=m((800, 165)), radius=[30 * SE, 22 * SN]),
}
KEY_LOCATIONS = {"North Gate": GATES["N"], "South Gate": GATES["S"], "West Gate": GATES["W"], "East Gate": GATES["E"],
                 "The Spire": m((CX, CY)), "Orbital Dockyard": m((300, 190)), "Research Sector": m((870, 175)),
                 "Market District": m((330, 335)), "Arena Complex": m((930, 335)), "Military Wing": m((320, 520)),
                 "The Refuge": m((645, 575)), "Industrial Zone": m((880, 560)), "The Outer Reaches": m((1080, 520))}

# per district: secondary grid spacing (m) and rotation (deg), lot size range (m), building height range (m)
STYLE = {
    "dockyard": dict(grid=180, rot=0, lot=(60, 120), h=(10, 45)),
    "mixed": dict(grid=120, rot=0, lot=(30, 60), h=(20, 90)),
    "research": dict(grid=150, rot=0, lot=(40, 80), h=(15, 70)),
    "market": dict(grid=90, rot=0, lot=(18, 36), h=(8, 30)),
    "arena": dict(grid=150, rot=0, lot=(40, 80), h=(12, 40)),
    "military": dict(grid=170, rot=0, lot=(50, 110), h=(8, 30)),
    "housing": dict(grid=100, rot=0, lot=(25, 45), h=(12, 60)),
    "industrial": dict(grid=170, rot=0, lot=(50, 120), h=(10, 35)),
    "ruins": dict(grid=130, rot=12, lot=(30, 70), h=(5, 40)),
    "spire": dict(grid=110, rot=0, lot=(30, 60), h=(40, 160)),
}


def grid_lines(poly, spacing, rot):
    """Secondary streets: a grid over the polygon, rotated, clipped to it (inset so they meet the main roads)."""
    c = poly.centroid
    minx, miny, maxx, maxy = poly.bounds
    R = max(maxx - minx, maxy - miny)
    lines = []
    for k in np.arange(-R, R + spacing, spacing):
        for ln in (LineString([(c.x + k, c.y - R), (c.x + k, c.y + R)]), LineString([(c.x - R, c.y + k), (c.x + R, c.y + k)])):
            ln = affinity.rotate(ln, rot, origin=c)
            cut = ln.intersection(poly)
            if not cut.is_empty:
                lines.append(cut)
    return lines


def build():
    wall = Polygon(WALL)
    inside = wall.buffer(-25)
    lines = [(cls, LineString(p)) for cls, p in ROADS if len(p) > 1]
    # secondary grids per district (not inside landmark footprints)
    lm_shapes = []
    for k, L in LANDMARKS.items():
        e = Point(L["centre"]).buffer(1, 64)
        lm_shapes.append(affinity.scale(e, L["radius"][0], L["radius"][1]))
    lm_union = unary_union(lm_shapes)
    for key, d in DISTRICTS.items():
        poly = Polygon(d["poly"]).intersection(inside)
        st = STYLE[d["kind"]]
        for ln in grid_lines(poly.buffer(-20), st["grid"], st["rot"]):
            ln = ln.difference(lm_union)
            if ln.is_empty:
                continue
            for part in getattr(ln, "geoms", [ln]):
                if part.length > 60:
                    lines.append(("secondary", part))
    # the Spire district: a fine ring-and-spoke street pattern between the inner ring and the metro loop
    for r in (165,):
        lines.append(("secondary", LineString(ellipse(CX, CY + 5, r, r * 136 / 215))))
    for ang in range(0, 360, 30):
        if ang % 45 == 0:
            continue
        a = math.radians(ang)
        lines.append(("secondary", LineString(ml([(CX + 122 * math.cos(a), CY + 5 - 78 * math.sin(a)),
                                                    (CX + 215 * math.cos(a), CY + 5 - 136 * math.sin(a))]))))
    # clip everything to the city: only the gate highways and the ring itself reach past the ring road
    clip = wall.buffer(30)
    ring_poly = Polygon(ml(ring)).buffer(2)
    lines = [(c, l.intersection(clip if c in ("highway", "ring") else ring_poly)) for c, l in lines]
    lines = [(c, l) for c, l in lines if not l.is_empty and l.length > 1]
    # node the network: split every line at every crossing
    rank = {"highway": 0, "ring": 1, "primary": 2, "secondary": 3, "access": 4}
    all_lines = unary_union([l for _, l in lines])
    nodes, node_index, edges = [], {}, []
    def nid(p):
        key = (round(p[0], 1), round(p[1], 1))
        if key not in node_index:
            node_index[key] = len(nodes); nodes.append(list(key))
        return node_index[key]
    classed = [(rank[c], c, l) for c, l in lines]
    for seg in getattr(all_lines, "geoms", [all_lines]):
        mid = seg.interpolate(.5, normalized=True)
        best = min(classed, key=lambda t: (t[2].distance(mid) > .5, t[0]))
        cls = best[1]
        pts = [list(map(lambda v: round(v, 1), q)) for q in seg.coords]
        edges.append(dict(a=nid(pts[0]), b=nid(pts[-1]), cls=cls, w=WIDTH[cls], len=round(seg.length, 1), pts=pts))
    # blocks: the city minus the road corridors (the block edge is the kerb), per district; sidewalks, alleys and
    # lots with their use inside (landuse)
    corridors = unary_union([l.buffer(WIDTH[c] / 2, cap_style=2, join_style=2) for c, l in lines])
    free = inside.difference(corridors).difference(lm_union.buffer(10))
    rng = np.random.default_rng(7)
    dpolys = {k: Polygon(d["poly"]) for k, d in DISTRICTS.items()}
    dpolys["spire"] = Polygon(SPIRE["poly"])
    dkind = {k: d["kind"] for k, d in DISTRICTS.items()}; dkind["spire"] = "spire"
    blocks_geo = []
    for b in getattr(free, "geoms", [free]):
        if b.area < 400:
            continue
        c = b.representative_point()
        dist = next((k for k in ("spire",) + tuple(DISTRICTS) if dpolys[k].contains(c)), "north_quarter")
        blocks_geo.append((dist, b))
    blocks, lots, alleys = landuse(blocks_geo, lambda d: dkind[d], rng)
    plan = dict(version=2, units="m", axes="E,N (Unreal X = N, Y = E)", size=[round(wall.bounds[2] - wall.bounds[0]), round(wall.bounds[3] - wall.bounds[1])],
                wall=[list(p) for p in WALL], gates={k: list(v) for k, v in GATES.items()},
                roads=dict(widths=WIDTH, nodes=nodes, edges=edges),
                metro=dict(loop=[list(p) for p in METRO], hubs=[list(h) for h in HUBS], height=16.0),
                rail=dict(lines={k: [list(p) for p in v] for k, v in RAIL.items()}, stations={k: list(v) for k, v in RAIL_STATIONS.items()}, height=9.0),
                districts={**{k: dict(label=d["label"], kind=d["kind"], poly=[list(p) for p in d["poly"]]) for k, d in DISTRICTS.items()},
                           "spire": dict(label=SPIRE["label"], kind="spire", poly=[list(p) for p in SPIRE["poly"]])},
                landmarks={k: dict(kind=L["kind"], centre=list(L["centre"]), radius=L["radius"]) for k, L in LANDMARKS.items()},
                key_locations={k: list(v) for k, v in KEY_LOCATIONS.items()},
                sidewalk=SIDEWALK, blocks=blocks, lots=lots, alleys=alleys)
    return plan, lines, wall

# ---------------------------------------------------------------- land use
SIDEWALK = 4.5          # kerb to property line (m)
ALLEY_W = 7.0           # service lane through deep blocks
# What each lot is for, per district kind (weights). Building uses get a body in nexus_dress.py; open uses are
# surfaces the tiles draw (parking, park, plaza) or sites (construction, vacant, substation yard).
MIX = {
    "spire": dict(office=40, tower_res=15, hotel=10, mixed=10, plaza=8, parkade=5, park=3, construction=3, clinic=2),
    "mixed": dict(apartments=25, mixed=25, office=12, shops=8, parking=6, park=5, school=3, clinic=3, construction=3,
                  parkade=3, vacant=2, fire_station=1, security=1),
    "research": dict(lab=50, office=15, parking=10, park=8, apartments=8, construction=3, substation=3),
    "market": dict(shops=30, mixed=25, market_hall=8, apartments=15, rowhouses=8, plaza=6, parking=5, vacant=2),
    "arena": dict(hotel=10, mixed=20, shops=15, parkade=12, parking=15, plaza=10, office=10, fire_station=2),
    "military": dict(barracks=30, security=15, warehouse=20, hangar=10, parking=15, vacant=5, substation=5),
    "housing": dict(apartments=35, rowhouses=20, tower_res=10, shops=5, school=5, park=8, parking=6, clinic=3,
                    construction=3, vacant=3, fire_station=2),
    "industrial": dict(warehouse=30, factory=25, workshop=15, parking=10, substation=5, vacant=8, construction=3),
    "dockyard": dict(hangar=25, warehouse=30, factory=10, parking=15, substation=5, vacant=5, construction=5),
    "ruins": dict(apartments=25, workshop=10, warehouse=10, vacant=25, shops=10, rowhouses=10, construction=5),
}
OPEN_USES = {"parking", "park", "plaza", "construction", "vacant", "substation"}
# wear (0 new .. 1 decayed) and the share of abandoned buildings per district
CONDITION = dict(spire=(.08, .0), research=(.15, .01), arena=(.2, .01), mixed=(.3, .02), housing=(.35, .03),
                 market=(.4, .03), military=(.35, .01), industrial=(.45, .06), dockyard=(.45, .05), ruins=(.75, .4))


def frontage(lot, street_line, alley_line):
    """The lot's street front: the longest edge along the block's kerb-side (within the sidewalk band) or, failing
    that, along an alley. Returns (front edge (p, q), on_street, has_alley_access)."""
    pts = list(lot.exterior.coords)[:-1]
    best, best_alley, alley_touch = None, None, False
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        L = math.dist(p, q)
        if L < 3:
            continue
        m = Point((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        if street_line.distance(m) < SIDEWALK + 1.5 and (best is None or L > best[2]):
            best = (p, q, L)
        if alley_line is not None and alley_line.distance(m) < ALLEY_W / 2 + 1.5:
            alley_touch = True
            if best_alley is None or L > best_alley[2]:
                best_alley = (p, q, L)
    if best:
        return (best[0], best[1]), True, alley_touch
    if best_alley:
        return (best_alley[0], best_alley[1]), False, True
    return None, False, False


def cut_alleys(dev, block):
    """Service lanes along the long axis of deep blocks (and across very long ones), reaching the kerb at both ends."""
    mrr = dev.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    e1 = (xs[1] - xs[0], ys[1] - ys[0]); e2 = (xs[2] - xs[1], ys[2] - ys[1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    long_v, long_l, short_l = (e1, l1, l2) if l1 >= l2 else (e2, l2, l1)
    u = (long_v[0] / long_l, long_v[1] / long_l)
    c = dev.centroid
    lines = []
    if short_l > 95:
        lines.append(LineString([(c.x - u[0] * long_l, c.y - u[1] * long_l), (c.x + u[0] * long_l, c.y + u[1] * long_l)]))
    if long_l > 260:
        lines.append(LineString([(c.x + u[1] * short_l, c.y - u[0] * short_l), (c.x - u[1] * short_l, c.y + u[0] * short_l)]))
    alleys = []
    for ln in lines:
        seg = ln.intersection(block)
        for part in getattr(seg, "geoms", [seg]):
            if part.geom_type == "LineString" and part.length > 40:
                alleys.append(part)
    return alleys


DEPTH = dict(market=22, mixed=30, housing=28, spire=40, research=45, arena=40, industrial=60, dockyard=70,
             military=55, ruins=30)


def strip_lots(piece, depth, front, rng):
    """Perimeter lots: the band within `depth` of the piece's edge cut across every `front` metres (perpendicular to
    each edge); what is left in the middle is one courtyard lot (returned separately)."""
    core = piece.buffer(-depth, join_style=2)
    band = piece.difference(core) if not core.is_empty else piece
    cuts = []
    ring = piece.exterior.simplify(1.0)
    pts = list(ring.coords)[:-1]
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        L = math.dist(p, q)
        if L < 4:
            continue
        u = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        n = (-u[1], u[0])
        s = float(rng.uniform(*front)) * .6
        while s < L - front[0] * .5:
            c = (p[0] + u[0] * s, p[1] + u[1] * s)
            cuts.append(LineString([(c[0] - n[0] * depth * 1.6, c[1] - n[1] * depth * 1.6), (c[0] + n[0] * depth * 1.6, c[1] + n[1] * depth * 1.6)]))
            s += float(rng.uniform(*front))
    pieces = split(band, MultiLineString(cuts)) if cuts else band
    lots = [g for g in getattr(pieces, "geoms", [pieces]) if g.geom_type == "Polygon" and g.area > 60]
    cores = [g for g in getattr(core, "geoms", [core]) if g.geom_type == "Polygon" and g.area > 250] if not core.is_empty else []
    return lots, cores


def parking_bays(lot, edge):
    """Car-park bays: rows parallel to the entrance edge (aisle 6 m, two 5 m bay rows back to back, aisle, ...),
    2.6 m wide, kept where the whole bay fits. Returns [[e, n, s]] centre + facing (+1: nose away from the edge)
    and the row axes (a along the edge, n into the lot)."""
    (p, q) = edge
    L = math.dist(p, q)
    a = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
    n = (-a[1], a[0])
    c = lot.centroid
    if (c.x - p[0]) * n[0] + (c.y - p[1]) * n[1] < 0:
        n = (-n[0], -n[1])
    us = [(x - p[0]) * a[0] + (y - p[1]) * a[1] for x, y in lot.exterior.coords]
    vs = [(x - p[0]) * n[0] + (y - p[1]) * n[1] for x, y in lot.exterior.coords]
    bays, v = [], 6.5
    pattern = [(+1, 5.0), (-1, 5.0), (0, 6.0)]                    # bay row, bay row (facing back), aisle
    k = 0
    inner = lot.buffer(-.4)
    while v < max(vs) - 4.5:
        s, depth = pattern[k % 3]
        if s:
            u = min(us) + 1.6
            while u < max(us) - 1.6:
                cu, cv = u, v + depth / 2
                ce = (p[0] + a[0] * cu + n[0] * cv, p[1] + a[1] * cu + n[1] * cv)
                corners = [(ce[0] + a[0] * du + n[0] * dv, ce[1] + a[1] * du + n[1] * dv) for du in (-1.3, 1.3) for dv in (-2.5, 2.5)]
                if all(inner.contains(Point(x)) for x in corners):
                    bays.append([round(ce[0], 2), round(ce[1], 2), s])
                u += 2.6
        v += depth
        k += 1
    return bays, [round(a[0], 4), round(a[1], 4)], [round(n[0], 4), round(n[1], 4)]


def landuse(blocks_geo, dkind_of, rng):
    """blocks_geo: [(district, block polygon)] -> blocks, lots (with use, frontage, condition), alleys."""
    blocks, lots, alleys_out = [], [], []
    for dist, b in blocks_geo:
        kind = dkind_of(dist)
        st = STYLE[kind]
        blocks.append(dict(district=dist, poly=[[round(x, 1), round(y, 1)] for x, y in b.exterior.coords]))
        dev = b.buffer(-SIDEWALK, join_style=2)
        if dev.is_empty:
            continue
        alleys = cut_alleys(dev, b) if kind != "spire" else []
        alley_union = unary_union([a.buffer(ALLEY_W / 2, cap_style=2) for a in alleys]) if alleys else None
        if alley_union is not None:
            dev = dev.difference(alley_union.buffer(1.0, cap_style=2))
            for a in alleys:
                alleys_out.append(dict(district=dist, w=ALLEY_W, pts=[[round(x, 1), round(y, 1)] for x, y in a.coords]))
        alley_line = unary_union(alleys) if alleys else None
        street_line = b.exterior
        wear0, aband = CONDITION[kind]
        mix = MIX[kind]
        names, weights = list(mix), np.array(list(mix.values()), float)
        weights /= weights.sum()
        for piece in getattr(dev, "geoms", [dev]):
            if piece.geom_type != "Polygon" or piece.area < 120:
                continue
            strips, cores = strip_lots(piece, DEPTH[kind], (st["lot"][0], st["lot"][1]), rng)
            for lot in strips + cores:
                front, on_street, alley_access = frontage(lot, street_line, alley_line)
                use = str(rng.choice(names, p=weights))
                if lot in cores or (front is None and use not in ("parking", "park", "vacant")):
                    use = "park" if rng.random() < .55 else "parking"         # the block's courtyard: a garden or car park
                if lot.area < 220 and use not in OPEN_USES:
                    use = "plaza" if kind in ("spire", "market", "arena") else "vacant" if kind in ("industrial", "dockyard", "ruins", "military") else "park"
                h = float(rng.uniform(*st["h"]))
                r = math.hypot(lot.centroid.x, lot.centroid.y)
                h *= 1.0 + 1.2 * max(0.0, 1 - r / 2600)
                wear = float(np.clip(wear0 + rng.normal(0, .15), 0, 1))
                rec = dict(district=dist, kind=kind, use=use, h=round(h, 1), wear=round(wear, 2),
                           abandoned=bool(use not in OPEN_USES and rng.random() < aband),
                           era=("old" if wear > .55 else "mid" if wear > .25 else "new"),
                           seed=int(rng.integers(0, 2 ** 31)), alley=alley_access,
                           poly=[[round(x, 1), round(y, 1)] for x, y in lot.exterior.coords])
                if front:
                    rec["front"] = [[round(front[0][0], 2), round(front[0][1], 2)], [round(front[1][0], 2), round(front[1][1], 2)]]
                    rec["street"] = on_street
                if use == "parking":
                    edge = front
                    if edge is None:                                              # a courtyard car park: its longest side
                        pts = list(lot.exterior.coords)[:-1]
                        i = max(range(len(pts)), key=lambda i: math.dist(pts[i], pts[(i + 1) % len(pts)]))
                        edge = (pts[i], pts[(i + 1) % len(pts)])
                    rec["bays"], rec["bay_a"], rec["bay_n"] = parking_bays(lot, edge)
                lots.append(rec)
    return blocks, lots, alleys_out


def subdivide(poly, size, rng, depth=0):
    """Recursive split along the long side of the minimum rotated rectangle until lots are size[0]..size[1] long."""
    if poly.area < size[0] * size[0] * .5:
        return []
    mrr = poly.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    e1 = math.hypot(xs[1] - xs[0], ys[1] - ys[0]); e2 = math.hypot(xs[2] - xs[1], ys[2] - ys[1])
    long_ = max(e1, e2)
    if long_ <= size[1] or depth > 9:
        return [poly] if poly.area > 60 else []
    if e1 >= e2:
        a, b = (xs[0], ys[0]), (xs[1], ys[1]); d = (xs[3] - xs[0], ys[3] - ys[0])
    else:
        a, b = (xs[1], ys[1]), (xs[2], ys[2]); d = (xs[0] - xs[1], ys[0] - ys[1])
    t = rng.uniform(.4, .6)
    p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    cutter = LineString([(p[0] - d[0] * 2, p[1] - d[1] * 2), (p[0] + d[0] * 2, p[1] + d[1] * 2)])
    out = []
    for piece in getattr(split(poly, cutter), "geoms", []):
        if piece.geom_type == "Polygon":
            out += subdivide(piece, size, rng, depth + 1)
    return out


def preview(plan, path):
    from PIL import Image, ImageDraw
    W, Hh = 1600, 1040
    xs = [p[0] for p in plan["wall"]]; ys = [p[1] for p in plan["wall"]]
    s = min(W / (max(xs) - min(xs) + 600), Hh / (max(ys) - min(ys) + 600))
    ox, oy = W / 2, Hh / 2
    P = lambda p: (ox + p[0] * s, oy - p[1] * s)
    im = Image.new("RGB", (W, Hh), (14, 20, 26)); d = ImageDraw.Draw(im)
    colours = dict(dockyard=(40, 50, 70), mixed=(45, 45, 60), research=(35, 55, 70), market=(70, 50, 40), arena=(60, 40, 70),
                   military=(45, 55, 45), housing=(40, 60, 50), industrial=(60, 55, 40), ruins=(55, 35, 55), spire=(60, 45, 80))
    for lot in plan["lots"]:
        d.polygon([P(p) for p in lot["poly"]], fill=tuple(min(255, c + int(lot["h"] / 2)) for c in colours[lot["kind"]]))
    for L in plan["landmarks"].values():
        c = P(L["centre"]); rx, ry = L["radius"][0] * s, L["radius"][1] * s
        d.ellipse([c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry], outline=(120, 140, 170), width=2)
    rc = dict(highway=((240, 170, 60), 4), ring=((240, 170, 60), 3), primary=((220, 225, 235), 2), secondary=((120, 125, 135), 1), access=((90, 90, 90), 1))
    for e in sorted(plan["roads"]["edges"], key=lambda e: -["highway", "ring", "primary", "secondary", "access"].index(e["cls"])):
        col, w = rc[e["cls"]]
        d.line([P(p) for p in e["pts"]], fill=col, width=w)
    d.line([P(p) for p in plan["metro"]["loop"]], fill=(70, 150, 255), width=3)
    for h in plan["metro"]["hubs"]:
        c = P(h); d.ellipse([c[0] - 6, c[1] - 6, c[0] + 6, c[1] + 6], outline=(120, 200, 255), width=2)
    for ln in plan["rail"]["lines"].values():
        d.line([P(p) for p in ln], fill=(200, 80, 220), width=3)
    d.line([P(p) for p in plan["wall"] + [plan["wall"][0]]], fill=(180, 180, 190), width=3)
    for k, g in plan["gates"].items():
        c = P(g); d.rectangle([c[0] - 7, c[1] - 7, c[0] + 7, c[1] + 7], fill=(255, 255, 255))
    for name, p in plan["key_locations"].items():
        c = P(p); d.text((c[0] + 6, c[1] - 6), name, fill=(255, 230, 160))
    # scale bar
    d.line([(40, Hh - 30), (40 + 2000 * s, Hh - 30)], fill=(255, 255, 255), width=2); d.text((40, Hh - 50), "2 km", fill=(255, 255, 255))
    im.save(path)


if __name__ == "__main__":
    plan, lines, wall = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(plan, open(OUT, "w"), separators=(",", ":"))
    e = plan["roads"]["edges"]
    print(f"plan: {plan['size'][0]} x {plan['size'][1]} m, {len(plan['roads']['nodes'])} road nodes, {len(e)} edges "
          f"({sum(x['len'] for x in e) / 1000:.0f} km of road), {len(plan['blocks'])} blocks, {len(plan['lots'])} lots -> {OUT}")
    if PREVIEW:
        preview(plan, PREVIEW)
