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
  blocks      polygons between the roads, per district; lots inside them (building footprints)
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
    # blocks: the city minus the road corridors, per district; lots inside
    corridors = unary_union([l.buffer(WIDTH[c] / 2 + 4.0, cap_style=2, join_style=2) for c, l in lines])
    free = inside.difference(corridors).difference(lm_union.buffer(10))
    rng = np.random.default_rng(7)
    blocks, lots = [], []
    dpolys = {k: Polygon(d["poly"]) for k, d in DISTRICTS.items()}
    dpolys["spire"] = Polygon(SPIRE["poly"])
    dkind = {k: d["kind"] for k, d in DISTRICTS.items()}; dkind["spire"] = "spire"
    for b in getattr(free, "geoms", [free]):
        if b.area < 400:
            continue
        c = b.representative_point()
        dist = next((k for k in ("spire",) + tuple(DISTRICTS) if dpolys[k].contains(c)), "north_quarter")
        blocks.append(dict(district=dist, poly=[[round(x, 1), round(y, 1)] for x, y in b.exterior.coords]))
        st = STYLE[dkind[dist]]
        for lot in subdivide(b, st["lot"], rng):
            h = float(rng.uniform(*st["h"]))
            # taller toward the Spire
            r = math.hypot(lot.centroid.x, lot.centroid.y)
            h *= 1.0 + 1.2 * max(0.0, 1 - r / 2600)
            lots.append(dict(district=dist, kind=dkind[dist], h=round(h, 1),
                             poly=[[round(x, 1), round(y, 1)] for x, y in lot.exterior.coords]))
    plan = dict(version=1, units="m", axes="E,N (Unreal X = N, Y = E)", size=[round(wall.bounds[2] - wall.bounds[0]), round(wall.bounds[3] - wall.bounds[1])],
                wall=[list(p) for p in WALL], gates={k: list(v) for k, v in GATES.items()},
                roads=dict(widths=WIDTH, nodes=nodes, edges=edges),
                metro=dict(loop=[list(p) for p in METRO], hubs=[list(h) for h in HUBS], height=16.0),
                rail=dict(lines={k: [list(p) for p in v] for k, v in RAIL.items()}, stations={k: list(v) for k, v in RAIL_STATIONS.items()}, height=9.0),
                districts={**{k: dict(label=d["label"], kind=d["kind"], poly=[list(p) for p in d["poly"]]) for k, d in DISTRICTS.items()},
                           "spire": dict(label=SPIRE["label"], kind="spire", poly=[list(p) for p in SPIRE["poly"]])},
                landmarks={k: dict(kind=L["kind"], centre=list(L["centre"]), radius=L["radius"]) for k, L in LANDMARKS.items()},
                key_locations={k: list(v) for k, v in KEY_LOCATIONS.items()},
                blocks=blocks, lots=lots)
    return plan, lines, wall


def subdivide(poly, size, rng, depth=0):
    """Recursive split along the long side of the minimum rotated rectangle until lots are size[0]..size[1] long."""
    if poly.area < size[0] * size[0] * .5:
        return []
    mrr = poly.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    e1 = math.hypot(xs[1] - xs[0], ys[1] - ys[0]); e2 = math.hypot(xs[2] - xs[1], ys[2] - ys[1])
    long_ = max(e1, e2)
    if long_ <= size[1] or depth > 9:
        inset = poly.buffer(-3.0, join_style=2)
        return [g for g in getattr(inset, "geoms", [inset]) if g.geom_type == "Polygon" and g.area > 150]
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
