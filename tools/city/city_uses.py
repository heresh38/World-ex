"""What the lots of Nexus Prime are used for: shared by tools/city/nexus_dress.py (what goes where) and
tools/blender/nexus_city.py (which building designs to model).

Per building use:
  cat      residential | commercial | industrial | service
  floor    storey height (m); gf / gf_h: the ground-floor kind (shop, lobby, service, loading, garage or None) and
           its height: the ground floor is its own instance (NCB_gf_<kind>) under the body
  designs  (shape, facade style) pairs for the body above the ground floor (NCB_<shape>_<style>)
  h        height range (m, before the district's height factor); front / side: setback ranges (m) from the
           property line (side 0 = party walls, a continuous street wall); depth: building depth range (m);
           unit: frontage width per building when one lot holds a row of them (shops, row houses, mixed blocks)
Open uses (parking, park, plaza, construction, vacant, substation) have no body: the tiles draw their ground and the
dressing furnishes them.
"""

USES = {
    "apartments": dict(cat="residential", floor=3.1, gf="lobby", gf_h=4.0, h=(12, 40), front=(2, 5), side=(3, 6), depth=(14, 24),
                       designs=[("slab", "housing"), ("courtyard", "housing"), ("stepped", "housing"), ("block", "brick"), ("lshape", "housing")]),
    "tower_res": dict(cat="residential", floor=3.1, gf="lobby", gf_h=5.0, h=(45, 140), front=(4, 8), side=(5, 8), depth=(18, 30),
                      designs=[("tower", "housing"), ("slab", "glass"), ("chamfer", "panel")]),
    "rowhouses": dict(cat="residential", floor=3.0, gf=None, gf_h=0.0, h=(7, 11), front=(2, 4), side=(0, 0), depth=(9, 14), unit=(6, 9),
                      designs=[("gable", "brick"), ("gable", "housing")]),
    "office": dict(cat="commercial", floor=3.8, gf="lobby", gf_h=5.5, h=(25, 200), front=(4, 10), side=(5, 9), depth=(22, 40),
                   designs=[("tower", "glass"), ("tower", "office"), ("chamfer", "glass"), ("slab", "office"), ("podium_tower", "glass"), ("slab", "panel")]),
    "hotel": dict(cat="commercial", floor=3.3, gf="lobby", gf_h=5.5, h=(30, 110), front=(5, 9), side=(4, 8), depth=(16, 26),
                  designs=[("slab", "panel"), ("tower", "office"), ("podium_tower", "panel")]),
    "mixed": dict(cat="commercial", floor=3.2, gf="shop", gf_h=4.5, h=(10, 36), front=(0, 1), side=(0, 2), depth=(14, 22), unit=(10, 24),
                  designs=[("block", "brick"), ("block", "office"), ("stepped", "office"), ("slab", "office"), ("block", "housing")]),
    "shops": dict(cat="commercial", floor=3.5, gf="shop", gf_h=4.5, h=(5, 12), front=(0, 1), side=(0, 1), depth=(10, 18), unit=(8, 16),
                  designs=[("block", "stone"), ("block", "brick"), ("gable", "stone")]),
    "market_hall": dict(cat="commercial", floor=4.0, gf="shop", gf_h=4.5, h=(9, 16), front=(2, 4), side=(2, 4), depth=(20, 40),
                        designs=[("hall", "stone"), ("market", "stone")]),
    "warehouse": dict(cat="industrial", floor=8.0, gf="loading", gf_h=4.5, h=(8, 14), front=(6, 12), side=(4, 8), depth=(25, 60),
                      designs=[("warehouse", "warehouse"), ("shed", "industrial")]),
    "factory": dict(cat="industrial", floor=6.0, gf="loading", gf_h=4.5, h=(10, 22), front=(6, 12), side=(4, 8), depth=(25, 50),
                    designs=[("shed", "industrial"), ("hall", "industrial"), ("block", "industrial")]),
    "workshop": dict(cat="industrial", floor=4.5, gf="loading", gf_h=4.5, h=(5, 9), front=(4, 8), side=(2, 5), depth=(12, 22),
                     designs=[("block", "industrial"), ("gable", "industrial")]),
    "hangar": dict(cat="industrial", floor=8.0, gf=None, gf_h=0.0, h=(14, 28), front=(10, 20), side=(6, 10), depth=(30, 60),
                   designs=[("hangar", "industrial"), ("hangar", "military")]),
    "clinic": dict(cat="service", floor=3.6, gf="lobby", gf_h=4.5, h=(10, 24), front=(6, 10), side=(4, 8), depth=(16, 30),
                   designs=[("lshape", "panel"), ("block", "office")]),
    "school": dict(cat="service", floor=3.8, gf="lobby", gf_h=4.2, h=(8, 14), front=(8, 14), side=(6, 10), depth=(20, 40),
                   designs=[("lshape", "brick"), ("courtyard", "brick")]),
    "security": dict(cat="service", floor=3.6, gf="service", gf_h=4.2, h=(6, 14), front=(8, 14), side=(5, 8), depth=(14, 26),
                     designs=[("bunker", "military"), ("block", "military")]),
    "fire_station": dict(cat="service", floor=3.8, gf="garage", gf_h=5.0, h=(9, 13), front=(10, 14), side=(3, 6), depth=(18, 28),
                         designs=[("block", "brick"), ("block", "military")]),
    "barracks": dict(cat="service", floor=3.4, gf="service", gf_h=4.0, h=(9, 16), front=(8, 14), side=(5, 8), depth=(14, 22),
                     designs=[("slab", "military"), ("block", "military")]),
    "lab": dict(cat="service", floor=4.0, gf="lobby", gf_h=5.0, h=(12, 60), front=(6, 12), side=(5, 9), depth=(20, 40),
                designs=[("domelab", "panel"), ("slab", "panel"), ("chamfer", "glass"), ("courtyard", "panel")]),
    "parkade": dict(cat="service", floor=3.0, gf="garage", gf_h=3.0, h=(10, 22), front=(2, 5), side=(2, 4), depth=(30, 50),
                    designs=[("block", "parkade")]),
}
OPEN = ("parking", "park", "plaza", "construction", "vacant", "substation")
GROUND_FLOORS = {"shop": "shop", "lobby": "lobby", "service": "service", "loading": "loading", "garage": "service"}


def designs():
    """every body design and ground floor the kit has to model: {name: (shape, style)}"""
    out = {}
    for u in USES.values():
        for shape, style in u["designs"]:
            out[f"NCB_{shape}_{style}"] = (shape, style)
    for gf, style in GROUND_FLOORS.items():
        out[f"NCB_gf_{gf}"] = ("gf", style)
    for style in ("office", "housing"):                     # the bare structure of a building going up
        out[f"NCB_frame_{style}"] = ("frame", style)
    return out
