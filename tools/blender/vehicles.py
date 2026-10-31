"""Vehicles: modern road cars (cars.glb), the player's hover boards, the old skyway hover cars, the jumpship and the
enemy dropship.

cars.glb holds five everyday cars as top-level nodes CAR_hatch, CAR_sedan, CAR_suv, CAR_pickup, CAR_van. Each has
  hi_<k>   full detail: lofted body with boolean wheel arches and door shut-lines, glass/pillars/roof from one greenhouse
           loft, conformed lamps/grille/plates/badges (ray-projected onto the body), and a complete interior: dashboard
           with gauge cluster and screen, steering wheel, seats with quilted inserts, door cards, console, gear lever,
           pedals, headliner, visors, mirrors. Animated parts: steer_<k> (rotates about its local Z = column axis),
           needleS_<k>/needleR_<k> (local Z = dial normal), wheel_<FL|FR|RL|RR>_<k> (steer about Y) with spin_* (spin about X).
  lo_<k>   one mesh, 7 materials, for distance.
  seat_<k>, eye_<k> empties (driver hip / eye) and a 'worldex' extra (JSON) with the dimensions the game's physics uses.
Every texture comes from vehicle_textures.py; UVs are world-scale (box projection per face) so nothing stretches.
Cars face Blender -Y (+Z in three.js). Paint material 'car_paint' has a clear-coat layer.
Run: blender --background --python tools/blender/vehicles.py [-- cars|boards|legacy]
"""
import bpy, bmesh, math, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

R90 = math.pi / 2


def ring(y, w, h, z0, n=16, squash=1.0, flat=0.0):
    """Superellipse cross-section at length y: half-width w, height h above z0."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        e = .55  # superellipse exponent -> boxier
        x = w * math.copysign(abs(c) ** e, c)
        z = h * .5 * math.copysign(abs(s) ** e, s)
        if z < 0:
            z *= squash
        pts.append((x, y, z0 + h * .5 + z - flat * (1 if z < 0 else 0)))
    return pts


def car(name, L=4.7, W=1.0, H=.62, paint='#b0122a', style='sport'):
    bl.reset()
    P = bl.palette()
    paint_m = bl.mat('car_paint', paint, .55, .22, coat=1.0)
    glass = bl.mat('canopy', '#0d1a22', .2, .02, alpha=.55)
    chrome = bl.mat('chrome', '#d8dde3', 1.0, .08)
    interior = bl.mat('interior', '#222326', 0, .6, image='carbon_c.jpg', uv_scale=3)
    pad = bl.mat('hover_glow', '#3ad6ff', 0, .3, emit='#3ad6ff', strength=8)
    tail = bl.mat('tail_light', '#ff2030', 0, .3, emit='#ff2030', strength=6)
    head = bl.mat('head_light', '#fff4e0', 0, .3, emit='#fff4e0', strength=10)
    parts = []
    # lofted body: nose (-Y) to tail (+Y)
    prof = []
    N = 14
    for i in range(N + 1):
        t = i / N
        y = -L / 2 + t * L
        if style == 'sport':
            w = W * (.55 + .45 * math.sin(math.pi * min(1, t * 1.25)) ** .6) * (1 - .12 * t)
            h = H * (.45 + .55 * math.sin(math.pi * min(1, .15 + t * .95)) ** .8)
        else:  # utility: boxy, tall
            w = W * (.8 + .2 * math.sin(math.pi * min(1, t * 2)) ** .5)
            h = H * (.6 + .4 * min(1, t * 4)) * 1.15
        prof.append(ring(y, w, h, .38, 20, squash=.5))
    body = bl.loft('body', prof, paint_m)
    bl.uv_box(body, 2)
    parts.append(body)
    # canopy
    cz = .38 + H * .85
    if style == 'sport':
        cs = []
        for i in range(9):
            t = i / 8
            y = -.55 + t * 1.9
            w = .62 * math.sin(math.pi * (.08 + t * .84)) ** .5
            h = .42 * math.sin(math.pi * (.05 + t * .9)) ** .7
            cs.append(ring(y, w, h * 2, cz - h * .9, 16, squash=.2))
        parts.append(bl.loft('canopy', cs, glass))
    else:
        parts.append(bl.box('cab', (1.5, 1.6, .55), (0, -.35, cz + .18), glass, bevel=.12, segs=3))
        parts.append(bl.box('roofrack', (1.4, 1.3, .06), (0, -.25, cz + .5), P['gunmetal'], bevel=.02))
        parts.append(bl.box('bed', (1.8, 1.4, .35), (0, 1.5, .85), P['gunmetal'], bevel=.04))
    # interior seat visible through the glass
    parts.append(bl.box('seat', (.55, .5, .12), (0, .1, cz - .25), interior, bevel=.04))
    parts.append(bl.box('seatback', (.55, .12, .55), (0, .38, cz), interior, bevel=.04, rot=(-.25, 0, 0)))
    parts.append(bl.box('dash', (1.0, .25, .18), (0, -.55, cz - .1), P['dark'], bevel=.03))
    parts.append(bl.box('dashglow', (.6, .02, .04), (0, -.68, cz - .05), P['cyan']))
    # side skirts + intakes
    for sx in (1, -1):
        parts.append(bl.box('skirt', (.08, L * .7, .18), (sx * W * .98, .1, .45), P['gunmetal'], bevel=.03))
        parts.append(bl.box('intake', (.1, .5, .14), (sx * W * .95, .55, .78), P['dark'], bevel=.02))
        parts.append(bl.box('trim', (.02, L * .55, .03), (sx * W * 1.0, 0, .62), chrome))
    # hover pads (4) with glow discs
    for sx in (1, -1):
        for sy in (-1, 1):
            p = (sx * W * .72, sy * L * .3, .3)
            parts.append(bl.cyl('pod', .32, .22, p, P['gunmetal'], 20))
            parts.append(bl.cyl('podglow', .27, .03, (p[0], p[1], p[2] - .12), pad, 20))
            parts.append(bl.torus('podring', .32, .035, (p[0], p[1], p[2] - .08), chrome, maj=20, mn=6))
    # lights
    parts.append(bl.box('headL', (.42, .05, .06), (W * .5, -L / 2 + .12, .62), head))
    parts.append(bl.box('headR', (.42, .05, .06), (-W * .5, -L / 2 + .12, .62), head))
    parts.append(bl.box('tailbar', (W * 1.7, .05, .06), (0, L / 2 - .02, .78), tail))
    # spoiler / rear engine
    if style == 'sport':
        parts.append(bl.box('wing', (W * 2.0, .35, .05), (0, L / 2 - .3, 1.2), paint_m, bevel=.02))
        for sx in (1, -1):
            parts.append(bl.box('wingpost', (.05, .15, .3), (sx * .6, L / 2 - .3, 1.02), P['gunmetal']))
        parts.append(bl.cyl('exhaust', .16, .25, (0, L / 2 + .05, .7), P['gunmetal'], 16, rot=(R90, 0, 0)))
        parts.append(bl.cyl('exhaustglow', .12, .02, (0, L / 2 + .18, .7), pad, 16, rot=(R90, 0, 0)))
    for o in parts:
        bl.apply_all(o)
    # merge by material keeps draw calls low
    g = bl.join(parts, name)
    bl.empty('seat', (0, .15, cz - .2), g)
    bl.empty('exit', (W + 1.0, 0, 0), g)
    bl.export(name + '.glb')


def jumpship(name='ship_jumper', hull='#e8e2d4', accent='#c79a45', glowc='#1ad8ff', enemy=False):
    bl.reset()
    P = bl.palette()
    hull_m = bl.mat('ship_hull', hull, .3, .35, image='panel_c.jpg', normal='panel_n.jpg')
    acc = bl.mat('ship_accent', accent, .9 if not enemy else .5, .3)
    glow = bl.mat('ship_glow', glowc, 0, .3, emit=glowc, strength=3.5)
    glass = bl.mat('ship_glass', '#0a1016', .6, .04, emit='#0b2a3a', strength=.4)
    parts = []
    L = 16 if not enemy else 13
    prof = []
    for i in range(17):
        t = i / 16
        y = -L / 2 + t * L
        w = 2.3 * (math.sin(math.pi * min(1, .05 + t * 1.1)) ** .7) * (1.25 if enemy else 1)
        h = 2.4 * (math.sin(math.pi * min(1, .1 + t * .95)) ** .8)
        prof.append(ring(y, max(w, .2), max(h, .2), 1.4, 20, squash=.6))
    body = bl.loft('fuselage', prof, hull_m)
    bl.uv_box(body, 3)
    parts.append(body)
    # cockpit glass
    parts.append(bl.sphere('cockpit', 1.0, (0, -L / 2 + 3.4, 3.25), glass, 20, 12, scale=(1.0, 2.0, .55)))
    # wings
    for sx in (1, -1):
        wv = [(sx * 1.6, -1.5, 2.2), (sx * 8.0, 2.5, 2.0), (sx * 8.0, 4.6, 2.0), (sx * 1.6, 5.5, 2.2),
              (sx * 1.6, -1.5, 2.55), (sx * 8.0, 2.5, 2.15), (sx * 8.0, 4.6, 2.15), (sx * 1.6, 5.5, 2.55)]
        f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        w = bl.mesh_from('wing', wv, f, hull_m)
        bl.uv_box(w, 3)
        parts.append(w)
        parts.append(bl.box('wingtip', (.4, 2.6, .7), (sx * 8.1, 3.5, 2.3), acc, bevel=.08))
        parts.append(bl.box('wingglow', (.05, 2.0, .08), (sx * 8.32, 3.5, 2.3), glow))
        # engines
        parts.append(bl.cyl('engine', .85, 4.0, (sx * 2.6, L / 2 - 2.6, 2.3), P['gunmetal'], 20, rot=(R90, 0, 0)))
        parts.append(bl.cyl('enginering', .95, .5, (sx * 2.6, L / 2 - .7, 2.3), acc, 20, rot=(R90, 0, 0)))
        parts.append(bl.cyl('nozzle', .8, .6, (sx * 2.6, L / 2 - .2, 2.3), P['dark'], 20, rot=(R90, 0, 0), r2=.62))
        parts.append(bl.cyl('engineglow', .45, .05, (sx * 2.6, L / 2 - .55, 2.3), glow, 20, rot=(R90, 0, 0)))
        # landing struts
        for sy in (-L / 2 + 3, L / 2 - 4):
            parts.append(bl.box('strut', (.25, .25, 1.5), (sx * 1.5, sy, .8), P['dark']))
            parts.append(bl.box('foot', (.8, 1.0, .15), (sx * 1.5, sy, .08), P['gunmetal'], bevel=.04))
    parts.append(bl.box('spine', (.5, L * .6, .4), (0, 1, 3.75), acc, bevel=.1))
    parts.append(bl.box('dorsalglow', (.08, L * .45, .06), (0, 1, 3.97), glow))
    if enemy:
        for sx in (1, -1):
            parts.append(bl.box('claw', (.4, 3.5, .4), (sx * 1.3, -L / 2 + 1.0, 1.0), P['red'], rot=(.3, 0, 0)))
    else:
        parts.append(bl.box('ramp', (2.0, 3.0, .15), (0, L / 2 - 1.0, .8), P['gunmetal'], rot=(-.35, 0, 0)))
    for o in parts:
        bl.apply_all(o)
    g = bl.join(parts, name)
    bl.empty('ramp_exit', (0, L / 2 + 1.5, 0), g)
    for sx in (1, -1):
        bl.empty('thruster', (sx * 2.6, L / 2 - .3, 2.3), g)
    bl.export(name + '.glb')


from vehicles_modern import build_cars, build_boards   # noqa: E402  (modern cars + boards live in their own module)

if __name__ == '__main__':
    what = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    what = [w for w in what if w] or ['cars', 'boards', 'legacy']
    if 'cars' in what:
        build_cars()
    if 'boards' in what:
        build_boards()
    if 'legacy' in what:
        car('car_sport', paint='#a3121f', style='sport')        # skyway hover cars (Earth decoration)
        car('car_utility', L=5.0, W=1.05, H=.75, paint='#2a4f7a', style='utility')
        import jumpship as _js   # the Wayfarer's landing craft has its own detailed builder
        _js.build()
        jumpship('ship_dropship', hull='#3a3a40', accent='#5d1c1c', glowc='#ff3326', enemy=True)
