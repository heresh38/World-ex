"""Nexus Prime city props: real-size street, wall and roof pieces for the Unreal city builder (ASONexusCity).

build_props(M) builds every prop as one root mesh object NCK_<name> in the current scene and returns
{name: info}; nexus_city.build_kit() calls it before exporting nexus_city_kit.glb.

Conventions (the placement code depends on them):
  * metres, Blender Z up.
  * anchor "wall": the building face is the plane y = 0, the prop stands out of it toward -y (the street); the
    origin is on the wall at ground level (z = 0), centred along x. Nothing goes deeper into the wall than y = 0
    (door reveals are made with a proud surround so they read even on a closed facade).
  * anchor "ground": the origin is the base centre on the ground (or roof), the side people use / read faces -y,
    long props run along +x.
  * info: size [x, y, z], min / max (bounds), anchor, tris, plus per-prop extras (stack / repeat steps, attach
    points for wires, ...).

Plain colour materials are np_* (bl.mat), shared ones come from nexus_city.materials() (nc_steel, nc_glow_*, ...).
No textures: the props read by shape, colour and their lit parts.
"""
import math, os, random, sys
from mathutils import Vector as V, geometry

sys.path.insert(0, os.path.dirname(__file__))
import bl

# name: (colour, metallic, roughness)
PLAIN = {
    'np_door_glass': ('#1b2733', .3, .1), 'np_door_frame': ('#2b2f35', .8, .4), 'np_interior': ('#17130f', 0, .95),
    'np_stone': ('#b4ab9c', 0, .65), 'np_stone_dark': ('#5d5953', 0, .7),
    'np_paint_red': ('#a3221c', 0, .45), 'np_paint_white': ('#e4e4de', 0, .5), 'np_paint_black': ('#151515', 0, .5),
    'np_sign_green': ('#17633a', 0, .4), 'np_sign_blue': ('#1d4e9e', 0, .4),
    'np_plywood': ('#b88d5c', 0, .8), 'np_plywood_old': ('#8f7350', 0, .85), 'np_batten': ('#7a5d3e', 0, .85),
    'np_hoarding': ('#d9d4c4', 0, .7),
    'np_leaf_dry': ('#7a5a24', 0, .8), 'np_leaf_red': ('#8b3a1c', 0, .8), 'np_paper': ('#d9d6cc', 0, .9),
    'np_wrapper': ('#2a6fa8', .2, .5),
    'np_concrete_light': ('#aeaba4', 0, .85), 'np_concrete': ('#8d8a84', 0, .9), 'np_concrete_dark': ('#64625d', 0, .9),
    'np_concrete_patch': ('#a19d93', 0, .9), 'np_rust': ('#7a3f1f', .3, .8),
    'np_hivis': ('#ff6a10', 0, .5), 'np_hivis_yellow': ('#f0c000', 0, .5),
    'np_chainlink': ('#44484c', .7, .55), 'np_steel_galv': ('#8f9498', .9, .45), 'np_steel_black': ('#1d1f22', .6, .5),
    'np_steel_door': ('#5b6269', .6, .45), 'np_wood_bench': ('#8a5a35', 0, .6),
    'np_awning_red': ('#9e1f1f', 0, .8), 'np_awning_green': ('#245c34', 0, .8), 'np_awning_blue': ('#1f3f7a', 0, .8),
    'np_awning_cream': ('#e6dcc0', 0, .8),
    'np_rubber': ('#111111', 0, .9), 'np_glass_dark': ('#10161c', .2, .08), 'np_glass_shelter': ('#7d97a4', .1, .05),
    'np_grille': ('#0b0c0d', .5, .6), 'np_solar': ('#142038', .3, .12), 'np_wrap': ('#c6ccd0', 0, .3),
    'np_pallet': ('#a37b4c', 0, .85), 'np_soil': ('#2b2018', 0, 1.0), 'np_hedge': ('#2e5a22', 0, .85),
    'np_green_cab': ('#3d5d44', .2, .55), 'np_dumpster': ('#2a4a2d', .3, .6), 'np_container': ('#8a3a25', .4, .6),
    'np_site_office': ('#d8d5ca', .2, .6), 'np_crane': ('#e2b21a', .3, .5), 'np_ac': ('#cfd1cb', .3, .5),
    'np_hvac': ('#b2b6b3', .6, .45), 'np_pole_wood': ('#4f3f2e', 0, .9), 'np_insulator': ('#6f8580', 0, .2),
    'np_cable': ('#0e0e0f', 0, .6), 'np_soot': ('#1b1a18', 0, .9), 'np_bin': ('#2c3338', .5, .5),
    'np_booth': ('#d9dbd6', .2, .5), 'np_lens_red': ('#3c0905', 0, .15), 'np_lens_amber': ('#3d2805', 0, .15),
    'np_reflective': ('#e8e8e8', 0, .25), 'np_cast_iron': ('#2a2826', .7, .6), 'np_chrome': ('#c8cbce', 1.0, .2),
    'np_graf_pink': ('#d23a8a', 0, .8), 'np_graf_teal': ('#1fa79a', 0, .8), 'np_graf_yellow': ('#e0c020', 0, .8),
    'np_graf_purple': ('#6a3bb5', 0, .8), 'np_graf_black': ('#151515', 0, .85), 'np_graf_white': ('#e0e0dc', 0, .8),
    'np_parasol': ('#b9533a', 0, .8), 'np_kiosk': ('#2f4a5a', .4, .5), 'np_bike_red': ('#8a1f1f', .5, .4),
    'np_bike_teal': ('#1f6f73', .5, .4), 'np_polished': ('#d9dde2', 1.0, .08),
}
# name: (colour, strength)
GLOW = {
    'np_glass_sign_warm': ('#ffb066', 6), 'np_glass_sign_cyan': ('#38e0ff', 6), 'np_glass_sign_magenta': ('#ff3fb0', 6),
    'np_glow_white': ('#e6eeff', 4), 'np_glow_green': ('#3dff7a', 6), 'np_glow_red': ('#ff2a1a', 6),
    'np_glow_amber': ('#ffaa22', 6), 'np_glow_ped': ('#ff7a1f', 5),
}


def materials(M):
    for k, (c, m, r) in PLAIN.items():
        M[k] = bl.mat(k, c, m, r)
    for k, (c, s) in GLOW.items():
        M[k] = bl.mat(k, c, 0, .4, emit=c, strength=s)
    return M


def ring(r, n=12, cx=0.0, cy=0.0, ph=0.0):
    return [(cx + r * math.cos(ph + 2 * math.pi * i / n), cy + r * math.sin(ph + 2 * math.pi * i / n)) for i in range(n)]


def octagon(r):
    """flat-topped octagon, r = circumradius"""
    return ring(r, 8, ph=math.pi / 8)


# ------------------------------------------------------------------ builder
class Prop:
    def __init__(self):
        from nexus_city import Acc
        self.a = Acc()

    def face(self, pts, mat, want):
        pts = [V(p) for p in pts]
        n = V((0, 0, 0))
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            n.x += (a.y - b.y) * (a.z + b.z); n.y += (a.z - b.z) * (a.x + b.x); n.z += (a.x - b.x) * (a.y + b.y)
        if n.length < 1e-10:
            return
        if n.dot(V(want)) < 0:
            pts = pts[::-1]; n = -n
        n.normalize()
        ax = max(range(3), key=lambda i: abs(n[i]))
        i, j = ((1, 2), (0, 2), (0, 1))[ax]
        self.a.face([tuple(p) for p in pts], mat, [(p[i], p[j]) for p in pts])

    def box(self, x0, x1, y0, y1, z0, z1, mat, skip=''):
        x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
        F = {'-x': ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
             '+x': ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
             '-y': ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
             '+y': ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
             '-z': ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
             '+z': ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1))}
        for k, (pts, w) in F.items():
            if k not in skip:
                self.face(pts, mat, w)

    def obox(self, c, u, v, w, hu, hv, hw, mat, skip=()):
        """oriented box: centre c, axes u v w (normalised here), half sizes; skip = {(axis, sign)}"""
        c = V(c); ax = [V(u).normalized(), V(v).normalized(), V(w).normalized()]; h = (hu, hv, hw)
        for a in range(3):
            o = [i for i in range(3) if i != a]
            for s in (-1, 1):
                if (a, s) in skip:
                    continue
                pts = []
                for p, q in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    t = [0, 0, 0]; t[a] = s; t[o[0]] = p; t[o[1]] = q
                    pts.append(c + ax[0] * (t[0] * h[0]) + ax[1] * (t[1] * h[1]) + ax[2] * (t[2] * h[2]))
                self.face(pts, mat, ax[a] * s)

    def beam(self, p0, p1, w, mat, h=None, up=(0, 0, 1), caps=False):
        """rectangular member from p0 to p1: w across (horizontal side), h the other way"""
        p0, p1 = V(p0), V(p1); d = p1 - p0; L = d.length
        if L < 1e-6:
            return
        d.normalize(); up = V(up)
        if abs(d.dot(up)) > .95:
            up = V((1, 0, 0)) if abs(d.x) < .9 else V((0, 1, 0))
        s = d.cross(up).normalized(); t = s.cross(d).normalized()
        self.obox((p0 + p1) / 2, d, s, t, L / 2, w / 2, (h or w) / 2, mat, skip=() if caps else {(0, -1), (0, 1)})

    def tube(self, p0, p1, r, mat, n=8, caps=(True, True), r1=None, capmat=None):
        p0, p1 = V(p0), V(p1); d = p1 - p0
        if d.length < 1e-6:
            return
        d.normalize()
        up = V((0, 0, 1)) if abs(d.z) < .95 else V((1, 0, 0))
        s = d.cross(up).normalized(); t = s.cross(d).normalized()
        r1 = r if r1 is None else r1
        rg = lambda c, rr: [c + (s * math.cos(2 * math.pi * (i + .5) / n) + t * math.sin(2 * math.pi * (i + .5) / n)) * rr
                            for i in range(n)]
        A, B = rg(p0, r), rg(p1, r1)
        mid = (p0 + p1) / 2
        for i in range(n):
            j = (i + 1) % n
            want = (A[i] + A[j] + B[i] + B[j]) / 4 - mid
            want = want - d * want.dot(d) + d * ((r - r1) / max(.01, (p1 - p0).length) * .5)
            if r1 < 1e-6:
                self.face([A[i], A[j], p1], mat, want)
            else:
                self.face([A[i], A[j], B[j], B[i]], mat, want)
        if caps[0]:
            self.face(A, capmat or mat, -d)
        if caps[1] and r1 > 1e-6:
            self.face(B, capmat or mat, d)

    def cyl(self, x, y, r, z0, z1, mat, n=12, top=True, bottom=False, r1=None, topmat=None):
        self.tube((x, y, z0), (x, y, z1), r, mat, n, (bottom, top), r1, None)
        if top and topmat:  # recolour: draw the cap again a hair higher in its own material
            rr = r if r1 is None else r1
            self.face([(x + p[0], y + p[1], z1 + .002) for p in ring(rr, n, ph=math.pi / n)], topmat, (0, 0, 1))

    def slab(self, poly, o, u, v, t0, t1, mat, side=None, caps=(True, True)):
        """2D polygon in the (u, v) plane at o, extruded along u x v from t0 to t1 (t1 > t0)"""
        from nexus_city import ccw
        o, u, v = V(o), V(u), V(v); n = u.cross(v).normalized()
        poly = ccw(poly)
        P = lambda p, t: o + u * p[0] + v * p[1] + n * t
        tris = geometry.tessellate_polygon([[V((x, y, 0)) for x, y in poly]])
        for tri in tris:
            if caps[1]:
                self.face([P(poly[i], t1) for i in tri], mat, n)
            if caps[0]:
                self.face([P(poly[i], t0) for i in tri], mat, -n)
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            if math.hypot(dx, dy) < 1e-6:
                continue
            self.face([P(a, t0), P(b, t0), P(b, t1), P(a, t1)], side or mat, u * dy - v * dx)

    def panel_xz(self, poly, y_front, y_back, mat, side=None, back=True):
        """a flat plate in the wall plane: polygon in (x, z), front face at y_front (< y_back) facing -y"""
        self.slab(poly, (0, 0, 0), (1, 0, 0), (0, 0, 1), -y_back, -y_front, mat, side, caps=(back, True))

    def prism_x(self, poly, x0, x1, mat, side=None):
        """profile in (y, z) extruded along +x"""
        self.slab(poly, (0, 0, 0), (0, 1, 0), (0, 0, 1), x0, x1, mat, side)

    def prism_z(self, poly, z0, z1, mat, side=None, bottom=False):
        self.slab(poly, (0, 0, 0), (1, 0, 0), (0, 1, 0), z0, z1, mat, side, caps=(bottom, True))

    def loftz(self, r0, z0, r1, z1, mat, top=True, topmat=None):
        """walls between two rings of equal length (CCW), e.g. a tapered bin"""
        cx = sum(p[0] for p in r0) / len(r0); cy = sum(p[1] for p in r0) / len(r0)
        for i in range(len(r0)):
            j = (i + 1) % len(r0)
            want = ((r0[i][0] + r0[j][0]) / 2 - cx, (r0[i][1] + r0[j][1]) / 2 - cy, 0)
            self.face([(*r0[i], z0), (*r0[j], z0), (*r1[j], z1), (*r1[i], z1)], mat, want)
        if top:
            self.face([(*p, z1) for p in r1], topmat or mat, (0, 0, 1))


# ------------------------------------------------------------------ entrances and walls (anchor wall)
def door_lobby(p):
    S, F = 'np_stone', 'np_door_frame'
    p.box(-2.1, -1.5, -.32, 0, 0, 3.6, S, '-z+y')
    p.box(1.5, 2.1, -.32, 0, 0, 3.6, S, '-z+y')
    p.box(-1.5, 1.5, -.32, 0, 2.7, 3.6, S, '+y')
    p.box(-1.5, 1.5, -.32, 0, 0, .02, 'np_stone_dark', '-z+y')
    p.box(-2.4, 2.4, -1.2, -.32, 0, .15, 'np_stone_dark', '-z')            # entrance step / landing
    p.box(-1.5, 1.5, -.03, 0, .02, 2.7, 'np_interior', '+y-z')             # lobby seen through the glass
    p.box(-1.46, 1.46, -.07, -.055, .12, 2.62, 'np_door_glass', '+y')
    for x0, x1 in ((-1.5, -1.43), (1.43, 1.5), (-.04, .04), (-.06, -.04), (.04, .06)):
        p.box(x0, x1, -.1, -.03, .02, 2.7, F, '-z')
    for z0, z1 in ((.02, .14), (2.22, 2.28), (2.6, 2.7)):
        p.box(-1.5, 1.5, -.1, -.03, z0, z1, F)
    for x0, x1 in ((-1.3, -.2), (.2, 1.3)):                                   # push bars on standoffs
        p.box(x0, x1, -.17, -.13, .98, 1.03, 'np_chrome')
        for x in (x0 + .05, x1 - .05):
            p.box(x - .015, x + .015, -.13, -.1, .99, 1.02, 'np_chrome')
    p.box(-2.5, 2.5, -2.2, 0, 3.6, 3.82, F, '+y')                             # canopy
    p.box(-2.52, 2.52, -2.22, -2.18, 3.56, 3.86, F)                           # fascia
    p.box(-2.35, 2.35, -2.08, -1.96, 3.585, 3.6, 'nc_glow_warm')              # lit strip on the underside
    for x in (-1.6, 0, 1.6):
        p.box(x - .14, x + .14, -1.15, -.87, 3.585, 3.6, 'nc_glow_warm')
    for x in (-2.25, 2.25):                                                   # tie rods to the wall
        p.beam((x, -2.0, 3.82), (x, -.03, 5.05), .04, F)
        p.box(x - .1, x + .1, -.04, 0, 4.85, 5.2, F, '+y')
    p.box(1.62, 1.98, -.345, -.32, 2.0, 2.24, 'np_glass_sign_warm', '+y')    # address plate
    p.box(1.6, 2.0, -.335, -.32, 1.98, 2.26, F, '+y')


def door_shop(p, awn, stripe, glow):
    F = 'np_door_frame'
    p.box(-.55, .55, -.02, 0, 0, 2.3, 'np_interior', '+y-z')
    p.box(-.62, -.55, -.11, 0, 0, 2.42, F, '-z+y'); p.box(.55, .62, -.11, 0, 0, 2.42, F, '-z+y')
    p.box(-.62, .62, -.11, 0, 2.3, 2.42, F, '+y')
    p.box(-.5, .5, -.075, -.06, .2, 2.25, 'np_door_glass')
    p.box(-.55, .55, -.085, -.03, 0, .2, F, '-z')                            # kick plate
    for x0, x1 in ((-.55, -.5), (.5, .55)):
        p.box(x0, x1, -.085, -.03, .2, 2.3, F)
    p.box(-.55, .55, -.085, -.03, 2.25, 2.3, F)
    p.box(.36, .4, -.17, -.12, .85, 1.35, 'np_chrome')                       # pull handle
    for z in (.9, 1.3):
        p.box(.365, .395, -.12, -.085, z - .015, z + .015, 'np_chrome')
    for s in (-1, 1):                                                         # display windows each side
        x0, x1 = sorted((s * .62, s * 1.55))
        p.box(x0, x1, -.13, 0, 0, .5, F, '-z+y')                              # stall riser
        p.box(x0, x1, -.025, 0, .5, 2.35, 'np_interior', '+y')
        p.box(x0, x1, -.065, -.05, .5, 2.35, 'np_door_glass')
        p.box(x0, x1, -.11, 0, 2.35, 2.42, F, '+y')
        xo = (x1 - .06, x1) if s > 0 else (x0, x0 + .06)
        p.box(*xo, -.11, 0, .5, 2.35, F, '+y')
    p.box(-1.6, 1.6, -.14, 0, 2.42, 2.62, F, '+y')                           # fascia
    # awning: 3.2 wide, 1.3 deep, sloping from 3.1 at the wall to 2.6, valance down to 2.35
    n = 8 if stripe else 1
    up = (0, -.36, .93)
    for i in range(n):
        x0 = -1.6 + 3.2 * i / n; x1 = -1.6 + 3.2 * (i + 1) / n
        m = awn if (i % 2 == 0 or not stripe) else 'np_awning_cream'
        p.face([(x0, 0, 3.1), (x1, 0, 3.1), (x1, -1.3, 2.6), (x0, -1.3, 2.6)], m, up)
        p.face([(x0, 0, 3.07), (x1, 0, 3.07), (x1, -1.27, 2.58), (x0, -1.27, 2.58)], m, (0, .36, -.93))
        p.box(x0, x1, -1.3, -1.28, 2.35, 2.6, m, '+z')
    for x in (-1.6, 1.6):
        tri = [(x, 0, 3.1), (x, -1.3, 2.6), (x, -1.3, 2.35)]
        p.face(tri, awn, (1, 0, 0)); p.face(tri, awn, (-1, 0, 0))
    p.tube((-1.6, -1.29, 2.6), (1.6, -1.29, 2.6), .02, 'np_steel_black', 6)
    for x in (-1.55, 1.55):
        p.beam((x, -.02, 2.8), (x, -1.26, 2.58), .025, 'np_steel_black')
    p.box(-1.4, 1.4, -.15, 0, 3.3, 3.9, F, '+y')                             # lit sign box
    p.box(-1.32, 1.32, -.16, -.15, 3.37, 3.83, glow, '+y')


def door_service(p):
    F = 'np_door_frame'
    p.box(-.58, -.5, -.07, 0, 0, 2.3, F, '-z+y'); p.box(.5, .58, -.07, 0, 0, 2.3, F, '-z+y')
    p.box(-.58, .58, -.07, 0, 2.2, 2.3, F, '+y')
    p.box(-.5, .5, -.045, 0, .02, 2.2, 'np_steel_door', '+y-z')
    for z in (.75, 1.45):                                                     # pressed panel lines
        p.box(-.42, .42, -.05, -.045, z, z + .02, F)
    p.box(-.5, .5, -.05, -.045, .02, .3, 'np_steel_galv')                    # kick plate
    p.box(.32, .38, -.07, -.045, .95, 1.1, 'np_chrome')                      # lever handle
    p.box(.2, .36, -.11, -.07, 1.0, 1.04, 'np_chrome')
    p.box(-.8, .8, -.55, 0, 0, .18, 'np_concrete', '-z+y')                    # step
    # caged lamp
    p.box(-.1, .1, -.03, 0, 2.42, 2.72, F, '+y')
    p.box(-.065, .065, -.2, -.03, 2.5, 2.64, 'nc_glow_warm')
    p.box(-.09, .09, -.23, -.2, 2.48, 2.66, F)
    for x in (-.085, .085):
        for z in (2.485, 2.655):
            p.beam((x, -.03, z), (x, -.2, z), .012, 'np_steel_black')
    for yy in (-.08, -.14):
        p.box(-.09, .09, yy - .006, yy + .006, 2.48, 2.66, 'np_steel_black', '+z-z')


def door_garage(p):
    from nexus_city import clip_convex
    C = 'np_concrete'
    p.box(-2.75, 2.75, -.03, -.02, 0, 2.6, 'nc_tunnel', '-z+z')
    for s in (-1, 1):
        x0, x1 = sorted((s * 2.75, s * 3.05))
        p.box(x0, x1, -.25, 0, 0, 2.6, C, '-z+y')
        p.box(x0, x1, -.27, -.25, 0, .9, 'nc_paint_yellow', '-z+y')  # kerb guard paint
    p.box(-3.05, 3.05, -.25, 0, 2.6, 3.25, C, '+y')
    p.box(-3.05, 3.05, -.26, -.25, 2.65, 3.2, 'np_paint_black', '+y')
    rect = [(-3.05, 2.65), (3.05, 2.65), (3.05, 3.2), (-3.05, 3.2)]
    x = -3.8
    while x < 3.1:                                                           # diagonal hazard stripes
        par = [(x, 2.65), (x + .28, 2.65), (x + .83, 3.2), (x + .55, 3.2)]
        poly = clip_convex(par, rect)
        if len(poly) >= 3:
            p.panel_xz(poly, -.264, -.26, 'nc_paint_yellow', back=False)
        x += .56
    # hanging height bar in front of the opening, red / white
    for xb in (-2.4, 2.4):
        p.box(xb - .05, xb + .05, -.85, -.25, 3.0, 3.08, 'np_steel_black')
        p.beam((xb, -.8, 2.4), (xb, -.8, 3.0), .02, 'np_steel_black')
    for i in range(10):
        x0 = -2.6 + .52 * i
        p.box(x0, x0 + .52, -.84, -.76, 2.32, 2.42, 'np_paint_red' if i % 2 == 0 else 'np_paint_white')
    # round height sign on the left jamb (no text: white disc, red ring)
    p.tube((-2.9, -.27, 1.55), (-2.9, -.285, 1.55), .22, 'np_paint_red', 16)
    p.tube((-2.9, -.28, 1.55), (-2.9, -.29, 1.55), .17, 'np_paint_white', 16, caps=(False, True))


def loading_dock(p):
    p.box(-2.2, 2.2, -3.5, 0, 0, 1.2, 'np_concrete', '-z+y')                  # dock platform
    p.box(-2.2, 2.2, -3.52, -3.5, 1.08, 1.2, 'nc_steel', '-z')               # edge angle
    p.box(-2.2, 2.2, -3.5, -3.32, 1.2, 1.203, 'nc_paint_yellow', '-z')       # yellow edge strip
    for x in (-1.3, 1.3):                                                     # bumpers
        p.box(x - .14, x + .14, -3.66, -3.52, .65, 1.15, 'np_rubber')
    for i in range(3):                                                        # side steps
        h = 1.2 * (i + 1) / 4
        p.box(2.2, 2.95, -3.4 + i * .3, -2.4, 0, h, 'np_concrete', '-z')
    p.box(-1.8, 1.8, -.06, 0, 1.2, 5.2, 'np_steel_door', '+y-z')             # roll-up door
    for i in range(16):
        z = 1.3 + i * .25
        p.box(-1.8, 1.8, -.09, -.06, z, z + .05, 'np_steel_door')
    p.box(-1.8, 1.8, -.1, -.06, 1.2, 1.28, 'np_rubber')
    for s in (-1, 1):                                                         # guides
        x0, x1 = sorted((s * 1.8, s * 1.98))
        p.box(x0, x1, -.13, 0, 1.2, 5.2, 'nc_steel', '+y')
        p.box(x0, x1, -.14, -.13, 1.2, 3.2, 'nc_paint_yellow')
    p.box(-2.05, 2.05, -.55, 0, 5.2, 5.75, 'nc_steel', '+y')                 # coil housing
    # dock lamp on a swing arm
    p.box(2.15, 2.35, -.05, 0, 2.8, 3.2, 'nc_steel', '+y')
    p.beam((2.25, -.05, 3.0), (2.25, -1.1, 3.05), .05, 'nc_steel')
    p.box(2.1, 2.4, -1.35, -1.05, 2.9, 3.15, 'nc_steel')
    p.box(2.13, 2.37, -1.36, -1.35, 2.93, 3.12, 'nc_glow_warm')


def fire_escape(p):
    K = 'np_steel_black'
    Z = 3.2
    # landing deck with the opening the flight below comes up through (x -0.6..1.4 on the outer strip)
    p.box(-2.0, 2.0, -.7, 0, Z - .05, Z, 'np_grille', '+y')
    p.box(-2.0, -.6, -1.3, -.7, Z - .05, Z, 'np_grille')
    p.box(1.4, 2.0, -1.3, -.7, Z - .05, Z, 'np_grille')
    p.box(-2.0, 2.0, -1.32, -1.28, Z - .16, Z, K)                             # edge channels
    for x in (-2.0, 2.0):
        p.box(x - .02, x + .02, -1.32, 0, Z - .16, Z, K, '+y')
    p.box(-.6, 1.4, -.72, -.68, Z - .12, Z, K)
    for x in (-1.85, 1.85):                                                   # wall brackets
        p.beam((x, -.02, Z - 1.0), (x, -1.25, Z - .08), .05, K)
        p.box(x - .08, x + .08, -.02, 0, Z - 1.1, Z - .02, K, '+y')
    # railing: outer edge and both ends, top rail 1.0 m, mid rail 0.5 m
    for x in (-2.0, -1.0, 0.0, 1.0, 2.0):
        p.beam((x, -1.3, Z), (x, -1.3, Z + 1.0), .035, K)
    for x in (-2.0, 2.0):
        p.beam((x, -.65, Z), (x, -.65, Z + 1.0), .035, K)
    for h in (.5, 1.0):
        p.beam((-2.0, -1.3, Z + h), (2.0, -1.3, Z + h), .035, K)
        for x in (-2.0, 2.0):
            p.beam((x, -1.3, Z + h), (x, -.02, Z + h), .035, K)
    # flight from the landing (x 1.4, z 3.2) down to the landing below (x -1.4, z 0)
    xt, xb = 1.4, -1.4
    for y in (-1.24, -.71):
        p.beam((xt + .1, y, Z - .05), (xb - .1, y, -.1), .03, K, h=.2)
    for i in range(1, 16):
        z = Z - i * .2
        x = xb + (z / Z) * (xt - xb)
        p.box(x - .11, x + .11, -1.22, -.73, z - .03, z, 'np_grille')
    for y in (-1.26, -.69):                                                  # stair handrails
        p.beam((xt, y, Z + .9), (xb + .2, y, .9 + .2 * Z / (xt - xb)), .035, K)
        p.beam((xb + .35, y, .35 * Z / (xt - xb)), (xb + .35, y, .9 + .35 * Z / (xt - xb)), .03, K)


def wall_ac(p):
    p.box(-.35, .35, -.45, -.02, 0, .5, 'np_ac')
    p.box(-.3, .3, -.455, -.45, .05, .32, 'np_grille')
    for i in range(6):
        z = .07 + i * .045
        p.box(-.3, .3, -.465, -.455, z, z + .015, 'np_ac')
    p.box(-.34, -.34 + .01, -.4, -.1, .1, .4, 'np_grille')                    # side vents
    p.box(-.3, .3, -.43, -.04, .5, .51, 'np_ac', '-z')
    for x in (-.25, .25):                                                     # brackets
        p.box(x - .02, x + .02, -.43, 0, -.04, 0, 'np_steel_black', '+z')
        p.beam((x, -.025, -.38), (x, -.4, -.03), .035, 'np_steel_black')
        p.box(x - .04, x + .04, -.01, 0, -.42, 0, 'np_steel_black', '+y')
    p.tube((.28, -.2, 0), (.28, -.2, -.25), .008, 'np_rubber', 5)            # drip hose


def meter_box(p):
    p.box(-.45, .45, -.35, 0, .4, 2.0, 'np_steel_galv', '+y')
    p.box(-.43, .43, -.355, -.35, .42, 1.98, 'np_steel_galv')
    p.box(-.005, .005, -.36, -.35, .44, 1.96, 'np_steel_black')              # door seam
    for x in (-.22, .22):
        p.box(x - .09, x + .09, -.365, -.355, 1.45, 1.65, 'np_glass_dark')    # meter windows
    p.box(.06, .1, -.38, -.355, 1.0, 1.12, 'np_paint_black')
    p.box(-.47, .47, -.38, 0, 2.0, 2.04, 'np_steel_galv', '+y')               # drip cap
    p.box(-.3, -.2, -.33, -.31, 1.8, 1.88, 'nc_paint_yellow')                 # hazard tag
    p.cyl(.25, -.12, .045, 2.04, 4.0, 'np_steel_galv', 8)                     # conduit up
    p.cyl(-.2, -.15, .05, 0, .4, 'np_steel_galv', 8, top=False)               # feed from the ground
    for z in (2.6, 3.3, 3.95):
        p.box(.18, .32, -.18, 0, z, z + .04, 'np_steel_black', '+y')


def sign_blade(p, face, edge):
    F = 'np_door_frame'
    p.box(-.3, .3, -1.4, -.2, 4.0, 8.0, F)
    for i in range(4):                                                       # stacked glowing panels, no text
        z0 = 4.12 + i * .95
        p.box(-.305, .305, -1.32, -.28, z0, z0 + .82, face, '+y-y')
    p.box(-.08, .08, -1.42, -1.4, 4.08, 7.92, edge, '+y')
    p.box(-.31, .31, -1.43, -.17, 7.98, 8.05, F)
    for z in (4.4, 7.6):                                                      # brackets
        p.box(-.04, .04, -.22, 0, z - .04, z + .04, 'np_steel_black', '+y')
        p.box(-.12, .12, -.02, 0, z - .15, z + .15, 'np_steel_black', '+y')


def boarded(p):
    p.box(-1.2, -.005, -.03, 0, 0, 2.6, 'np_plywood', '+y-z')
    p.box(.005, 1.2, -.03, 0, 0, 2.6, 'np_plywood_old', '+y-z')
    p.box(-.005, .005, -.025, 0, 0, 2.6, 'np_interior', '+y-z')
    for z in (.3, 1.3, 2.3):
        p.box(-1.26, 1.26, -.055, -.03, z - .05, z + .05, 'np_batten', '+y')
    p.beam((-1.0, -.04, .4), (1.0, -.04, 2.2), .08, 'np_batten', h=.022, up=(0, 1, 0))
    for z in (.3, 1.3, 2.3):                                                  # nail heads
        for x in (-1.15, -.6, 0, .6, 1.15):
            p.box(x - .008, x + .008, -.058, -.055, z - .008, z + .008, 'np_steel_galv', '+y')


def graffiti(p):
    from nexus_city import offset_line
    R = random.Random(11)
    clamp = lambda pts: [(max(-1.48, min(1.48, x)), max(.02, min(1.98, z))) for x, z in pts]

    def blob(cx, cz, rx, rz, k=1.0, n=16):
        ph = R.random() * 6.3
        out = []
        for i in range(n):
            a = 2 * math.pi * i / n
            f = k * (1 + .22 * math.sin(3 * a + ph) + .12 * math.sin(5 * a + ph * 2))
            out.append((cx + rx * f * math.cos(a), cz + rz * f * math.sin(a)))
        return out

    def stroke(path, w):
        return offset_line(path, w) + offset_line(path, -w)[::-1]

    layer = [0]

    def put(poly, mat):
        layer[0] += 1
        p.panel_xz(clamp(poly), -(.003 + .0012 * layer[0]), 0, mat, back=False)

    # big bubble shapes with dark outlines, then strokes and drips on top (abstract, no letters)
    shapes = [(-.85, 1.05, .55, .62, 'np_graf_pink'), (.0, 1.15, .5, .55, 'np_graf_teal'), (.85, 1.0, .55, .6, 'np_graf_purple')]
    for cx, cz, rx, rz, m in shapes:
        b0 = blob(cx, cz, rx, rz, 1.0)
        put([(cx + (x - cx) * 1.1, cz + (z - cz) * 1.1) for x, z in b0], 'np_graf_black')
        put(b0, m)
        put(blob(cx - .1, cz + .15, rx * .35, rz * .25), 'np_graf_white')
    path = [(-1.35, .35 + .25 * math.sin(i * .7)) for i in range(1)]
    path = [(-1.35 + i * .3, .45 + .22 * math.sin(i * .9)) for i in range(10)]
    put(stroke(path, .06), 'np_graf_yellow')
    path = [(-1.2 + i * .26, 1.75 + .12 * math.sin(i * 1.3 + 1)) for i in range(10)]
    put(stroke(path, .035), 'np_graf_white')
    for x in (-.95, -.55, .1, .7, 1.0):                                       # drips
        z0 = .55 + R.random() * .2
        put([(x - .015, z0), (x + .015, z0), (x + .01, z0 - .25 - R.random() * .2), (x - .01, z0 - .25 - R.random() * .2)],
            'np_graf_pink' if x < 0 else 'np_graf_purple')


def repair_patch(p):
    from nexus_city import offset_line
    p.box(-1.5, 1.5, -.012, 0, 0, 2.0, 'np_concrete_patch', '+y')
    for x0, x1, z0, z1 in ((-1.5, 1.5, 0, .03), (-1.5, 1.5, 1.97, 2.0), (-1.5, -1.47, 0, 2.0), (1.47, 1.5, 0, 2.0)):
        p.box(x0, x1, -.016, -.011, z0, z1, 'np_concrete_dark', '+y')
    path = [(-.9 + i * .22, 1.4 - i * .09 + .05 * math.sin(i * 2.1)) for i in range(9)]
    poly = offset_line(path, .008) + offset_line(path, -.008)[::-1]
    p.panel_xz(poly, -.0135, -.012, 'np_concrete_dark', back=False)
    p.box(-.4, 1.1, -.0128, -.012, .3, .7, 'np_concrete_light', '+y')        # fresher trowelled patch


# ------------------------------------------------------------------ roof (anchor ground)
def roof_stair(p):
    p.box(-2.25, 2.25, -1.6, 1.6, 0, 3.2, 'np_concrete_light', '-z')
    p.box(-2.35, 2.35, -1.7, 1.7, 3.2, 3.4, 'np_concrete_dark', '-z')
    p.box(-2.3, 2.3, -1.65, 1.65, 3.15, 3.2, 'np_concrete_dark', '+z-z')
    p.box(-.58, .58, -1.66, -1.6, 0, 2.2, 'np_door_frame', '-z')
    p.box(-.5, .5, -1.68, -1.66, .02, 2.12, 'np_steel_door', '-z')
    p.box(.3, .36, -1.72, -1.68, .95, 1.1, 'np_chrome')
    p.box(-1.0, 1.0, -2.3, -1.6, 0, .15, 'np_concrete', '-z')                # step
    p.box(-.12, .12, -1.76, -1.6, 2.4, 2.55, 'np_steel_black')
    p.box(-.09, .09, -1.77, -1.62, 2.36, 2.4, 'nc_glow_warm')
    p.cyl(1.4, .6, .14, 3.4, 3.9, 'nc_steel', 10)                             # vent cap
    p.cyl(1.4, .6, .32, 3.9, 4.1, 'nc_steel', 10, r1=.08)
    p.box(-1.8, -1.0, .3, 1.3, 3.4, 3.65, 'nc_steel')                         # lift machine vent box
    for i in range(4):
        p.box(-1.78, -1.02, .22 + .0, .3, 3.43 + i * .055, 3.46 + i * .055, 'np_grille')


def roof_hvac(p):
    H = 'np_hvac'
    p.box(-2.5, 2.5, -1.1, 1.1, .2, 2.0, H)
    for y in (-.9, .9):
        p.box(-2.55, 2.55, y - .1, y + .1, 0, .2, 'nc_steel', '-z')
    for x in (-1.25, 1.25):                                                   # fans with dark grilles
        p.cyl(x, 0, .82, 2.0, 2.18, 'nc_steel', 16, topmat=None)
        p.face([(x + q[0], 0 + q[1], 2.183) for q in ring(.74, 16)], 'np_grille', (0, 0, 1))
        p.cyl(x, 0, .12, 2.18, 2.22, 'nc_steel', 8)
        for a in (0, math.pi / 2):
            c, s = math.cos(a) * .74, math.sin(a) * .74
            p.beam((x - c, -s, 2.2), (x + c, s, 2.2), .03, 'nc_steel')
    for i in range(7):                                                        # louvres on the front
        z = .45 + i * .18
        p.box(-2.2, .4, -1.14, -1.1, z, z + .08, 'np_grille')
    p.box(.8, 2.2, -1.12, -1.1, .4, 1.8, 'np_steel_galv')                    # access panel
    p.box(1.9, 1.98, -1.16, -1.12, 1.0, 1.2, 'np_chrome')
    # ducts out of both ends, bending down into the roof
    p.box(-3.4, -2.5, -.55, .45, .7, 1.5, 'np_steel_galv')
    p.box(-3.4, -2.8, -.55, .45, 0, .7, 'np_steel_galv', '-z')
    p.box(2.5, 3.2, -.2, .6, .9, 1.6, 'np_steel_galv')
    p.box(2.6, 3.2, -.2, .6, 0, .9, 'np_steel_galv', '-z')


def roof_vents(p):
    for x, y, h, r in ((-1.6, -.2, .9, .16), (-.4, .35, 1.1, .2), (1.0, -.25, .8, .14)):
        p.cyl(x, y, r, 0, h, 'np_steel_galv', 12, top=False)
        p.cyl(x, y, r * 2.0, h, h + .06, 'np_steel_galv', 12, top=False)       # mushroom cap
        p.cyl(x, y, r * 2.0, h + .06, h + .22, 'np_steel_galv', 12, r1=r * .4)
        p.cyl(x, y, r * 1.3, 0, .06, 'nc_steel', 12)                          # flashing
    p.tube((-2.2, .7, .35), (2.0, .7, .35), .08, 'np_steel_galv', 10)        # pipe run
    p.tube((2.0, .7, .35), (2.0, .7, 0), .08, 'np_steel_galv', 10, caps=(False, False))
    p.tube((-2.2, .7, .35), (-2.2, .7, 1.2), .08, 'np_steel_galv', 10)
    for x in (-1.6, -.4, .8, 1.7):
        p.box(x - .12, x + .12, .55, .85, 0, .1, 'np_rubber', '-z')
        p.beam((x, .7, .1), (x, .7, .27), .04, 'nc_steel')


def roof_solar(p):
    t = math.radians(25)
    L = 2.2 / math.cos(t); z0 = .35
    u = V((1, 0, 0)); v = V((0, math.cos(t), math.sin(t))); n = V((0, -math.sin(t), math.cos(t)))
    w = 1.7
    for i in range(4):
        x = -3.5 + w / 2 + i * (w + .067)
        c = V((x, 0, z0 + L * math.sin(t) / 2))
        p.obox(c, u, v, n, w / 2, L / 2, .02, 'np_door_frame')
        q = lambda a, b: c + u * a + v * b + n * .0215
        p.face([q(-w / 2 + .03, -L / 2 + .03), q(w / 2 - .03, -L / 2 + .03), q(w / 2 - .03, L / 2 - .03), q(-w / 2 + .03, L / 2 - .03)],
               'np_solar', n)
        for b in (-L / 6, L / 6):                                            # cell row lines
            p.face([q(-w / 2 + .03, b - .006) + n * .0005, q(w / 2 - .03, b - .006) + n * .0005,
                    q(w / 2 - .03, b + .006) + n * .0005, q(-w / 2 + .03, b + .006) + n * .0005], 'np_door_frame', n)
    for k in range(5):                                                        # frames between the panels
        x = -3.5 + k * (7.0 / 4)
        yf, yb = -1.0, .95
        zf = z0 + (yf + 1.1) * math.tan(t) - .05; zb = z0 + (yb + 1.1) * math.tan(t) - .05
        p.beam((x, yf, 0), (x, yf, zf), .05, 'np_steel_galv')
        p.beam((x, yb, 0), (x, yb, zb), .05, 'np_steel_galv')
        p.beam((x, -1.1, z0 - .05), (x, 1.1, z0 + L * math.sin(t) - .05), .05, 'np_steel_galv')
        p.beam((x, yf, .1), (x, yb, zb - .1), .035, 'np_steel_galv')
    for y in (-1.0, .95):
        p.box(-3.55, 3.55, y - .1, y + .1, 0, .08, 'np_concrete', '-z')       # ballast rails


def billboard(p):
    S = 'nc_steel'
    p.box(-6.0, 6.0, -.3, 0, 3.0, 7.0, 'np_door_frame')
    p.box(-5.88, 5.88, -.305, -.3, 3.1, 6.9, 'np_glow_white', '+y')
    for x in (-4.5, -1.5, 1.5, 4.5):                                          # legs and struts
        p.box(x - .12, x + .12, .5, .74, 0, 7.0, S, '-z')
        p.box(x - .3, x + .3, .32, .92, 0, .05, S, '-z')
        p.beam((x, 0, 3.4), (x, .5, 3.4), .1, S); p.beam((x, 0, 6.6), (x, .5, 6.6), .1, S)
        p.beam((x, .62, 2.75), (x, -1.25, 2.75), .1, S, h=.14)                # catwalk bearers
        p.beam((x, .62, 1.4), (x, -1.2, 2.7), .07, S)
    for z in (1.4, 4.0, 6.4):
        p.beam((-4.62, .62, z), (4.62, .62, z), .08, S)
    for x0, x1 in ((-4.5, -1.5), (-1.5, 1.5), (1.5, 4.5)):
        p.beam((x0, .62, 1.4), (x1, .62, 4.0), .06, S)
        p.beam((x0, .62, 6.4), (x1, .62, 4.0), .06, S)
    p.box(-6.0, 6.0, -1.3, -.3, 2.82, 2.86, 'np_grille')                     # catwalk grating
    for x in (-6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0):
        p.beam((x, -1.3, 2.86), (x, -1.3, 3.9), .04, S)
    for h in (3.4, 3.9):
        p.beam((-6.0, -1.3, h), (6.0, -1.3, h), .04, S)
    for x in (-3.0, 3.0):                                                     # floodlights aimed at the face
        p.beam((x, -1.25, 2.9), (x, -1.9, 3.25), .06, S)
        c = V((x, -1.95, 3.3)); a = V((0, .6, .8)).normalized()
        p.obox(c, (1, 0, 0), a, a.cross(V((1, 0, 0))), .3, .08, .12, 'np_door_frame')
        p.obox(c + a * .081, (1, 0, 0), a, a.cross(V((1, 0, 0))), .26, .002, .09, 'np_glow_white')


def exhaust_stack(p):
    p.cyl(0, 0, .55, 0, .3, 'nc_steel', 16)
    p.cyl(0, 0, .4, .3, 8.2, 'np_steel_galv', 16, top=False)
    p.cyl(0, 0, .405, 8.2, 9.0, 'np_soot', 16, top=False)
    p.face([(q[0], q[1], 8.98) for q in ring(.37, 16)], 'nc_tunnel', (0, 0, 1))
    p.tube((0, 0, 9.0), (0, 0, 8.98), .405, 'np_soot', 16, caps=(False, False), r1=.37)
    for z in (3.0, 6.0):
        p.cyl(0, 0, .45, z, z + .08, 'nc_steel', 16)
    p.cyl(0, 0, .46, 4.0, 4.2, 'nc_steel', 16)                               # brace collar
    for k in range(3):
        a = 2 * math.pi * k / 3 + .3
        c, s = math.cos(a), math.sin(a)
        p.beam((c * .44, s * .44, 4.1), (c * 1.8, s * 1.8, .05), .08, 'nc_steel')
        p.box(c * 1.8 - .2, c * 1.8 + .2, s * 1.8 - .2, s * 1.8 + .2, 0, .08, 'np_concrete', '-z')


# ------------------------------------------------------------------ street (anchor ground)
def bench(p):
    K, W = 'np_steel_black', 'np_wood_bench'
    for i in range(4):
        y0 = -.29 + i * .105
        p.box(-.9, .9, y0, y0 + .09, .41, .45, W)
    tilt = math.radians(12)
    for zc in (.62, .8):                                                      # back rest slats
        yc = .19 + (zc - .45) * math.tan(tilt)
        p.obox((0, yc, zc), (1, 0, 0), (0, -math.sin(tilt), math.cos(tilt)), (0, math.cos(tilt), math.sin(tilt)),
               .9, .06, .018, W)
    for x in (-.72, .72):
        p.beam((x, -.24, 0), (x, -.24, .41), .05, K)
        p.beam((x, .16, 0), (x, .17, .41), .05, K)
        p.beam((x, -.3, .395), (x, .2, .395), .05, K, h=.03)
        p.beam((x, .16, .41), (x, .17 + .45 * math.tan(tilt), .88), .045, K)
        p.beam((x, -.28, .64), (x, .19, .66), .05, K, h=.03)                 # arm rest
        p.beam((x, -.24, .41), (x, -.25, .64), .035, K)
        for y in (-.24, .16):
            p.box(x - .05, x + .05, y - .05, y + .05, 0, .01, K, '-z')


def litter_bin(p):
    p.cyl(0, 0, .24, 0, .06, 'nc_steel', 14)
    p.cyl(0, 0, .275, .06, .85, 'np_bin', 14, top=False)
    p.cyl(0, 0, .278, .62, .7, 'np_hivis_yellow', 14, top=False)
    p.cyl(0, 0, .29, .85, .9, 'np_bin', 14)
    p.cyl(0, 0, .29, .9, .95, 'np_bin', 14, r1=.18)
    p.panel_xz([(-.14, .74), (.14, .74), (.14, .82), (-.14, .82)], -.283, -.27, 'np_grille', back=False)


def bus_stop(p):
    F = 'np_door_frame'
    for x in (-1.95, 1.95):
        for y in (-.72, .72):
            p.box(x - .04, x + .04, y - .04, y + .04, 0, 2.48, F, '-z')
    p.box(-2.05, 2.05, -.85, .85, 2.48, 2.6, F)
    p.box(-1.9, 1.9, -.7, -.62, 2.465, 2.48, 'np_glow_white')                 # light under the roof edge
    p.box(-1.91, 1.91, .705, .715, .15, 2.35, 'np_glass_shelter')            # glass back
    for z0, z1 in ((.1, .15), (2.35, 2.4)):
        p.box(-1.95, 1.95, .69, .73, z0, z1, F)
    p.box(-.02, .02, .69, .73, .15, 2.35, F)
    p.box(-1.95, -1.91, -.6, .7, .15, 2.35, 'np_glass_shelter')              # glass end (west)
    p.box(1.9, 2.0, -.62, .7, .15, 2.35, F)                                   # lit ad panel (east end)
    p.box(1.885, 2.015, -.55, .63, .25, 2.25, 'np_glow_white', '-y+y-z+z')
    for x in (-1.3, 1.3):                                                     # bench
        p.box(x - .03, x + .03, .45, .55, 0, .42, F, '-z')
    p.box(-1.5, 1.5, .3, .66, .42, .46, 'np_wood_bench')
    # pole sign
    p.cyl(-2.55, -.7, .035, 0, 3.0, 'np_steel_galv', 8)
    p.box(-2.8, -2.3, -.75, -.735, 2.35, 2.95, 'np_paint_white')
    p.box(-2.8, -2.3, -.752, -.75, 2.78, 2.95, 'np_sign_blue', '+y')
    p.box(-2.8, -2.3, -.752, -.75, 2.4, 2.47, 'np_sign_blue', '+y')


def traffic_light(p):
    K = 'np_paint_black'
    p.cyl(0, 0, .26, 0, .45, 'nc_steel', 12)
    p.cyl(0, 0, .14, .45, 6.5, 'nc_steel', 12, r1=.11)
    p.beam((0, 0, 6.22), (0, -6.0, 6.28), .14, 'nc_steel', h=.16, caps=True)  # mast arm over the road (-y)
    p.beam((0, -.1, 5.4), (0, -2.4, 6.2), .07, 'nc_steel')
    p.box(-.14, .14, -.2, .2, 6.0, 6.5, 'nc_steel')                           # arm clamp
    # two vehicle heads hung under the arm; lenses face +x (traffic approaching along -x, the pole on its right)
    for y in (-3.0, -5.5):
        p.beam((0, y, 6.15), (0, y, 6.24), .06, K)
        p.box(-.15, .15, y - .18, y + .18, 5.1, 6.15, K)
        p.box(-.19, -.15, y - .32, y + .32, 4.98, 6.27, K, )                    # backplate
        p.box(-.195, -.19, y - .32, y + .32, 4.98, 5.02, 'np_reflective')
        for k, (z, m) in enumerate(((5.95, 'np_lens_red'), (5.63, 'np_lens_amber'), (5.31, 'np_glow_green'))):
            p.tube((.15, y, z), (.165, y, z), .11, m, 14, caps=(False, True))
            p.face([(.15, y - .13, z + .14), (.15, y + .13, z + .14), (.36, y + .13, z + .15), (.36, y - .13, z + .15)], K, (0, 0, 1))
            p.face([(.15, y - .13, z + .14), (.15, y + .13, z + .14), (.36, y + .13, z + .15), (.36, y - .13, z + .15)], K, (0, 0, -1))
    # pedestrian head on the pole, facing -y (across the road)
    p.box(-.03, .03, -.16, -.1, 2.7, 2.9, K)
    p.box(-.17, .17, -.38, -.16, 2.55, 3.05, K)
    p.box(-.13, .13, -.385, -.38, 2.83, 3.0, 'np_glow_ped', '+y')
    p.box(-.13, .13, -.385, -.38, 2.6, 2.77, 'np_lens_amber', '+y')
    p.box(-.06, .06, -.22, -.13, 1.0, 1.2, 'np_hivis_yellow')                # push button
    p.box(-.03, .03, -.225, -.22, 1.08, 1.14, 'np_chrome', '+y')


def stop_sign(p):
    p.tube((0, 0, 0), (0, 0, 2.4), .03, 'np_steel_galv', 8)
    zc = 2.4 - .375
    R = .375 / math.cos(math.pi / 8)
    oc = [(x, z + zc) for x, z in octagon(R)]
    p.panel_xz(oc, -.045, -.032, 'np_paint_white', side='np_steel_galv')
    p.panel_xz([(x, (z - zc) * .87 + zc) for x, z in [(x * .87, z) for x, z in oc]], -.049, -.045, 'np_paint_red', back=False)
    for z in (zc - .2, zc + .2):
        p.box(-.05, .05, -.032, -.025, z - .02, z + .02, 'np_steel_galv')


def street_sign(p):
    p.cyl(0, 0, .045, 0, 3.0, 'np_steel_galv', 8)
    p.cyl(0, 0, .055, 3.0, 3.06, 'np_steel_galv', 8)
    p.box(-.46, .46, -.011, .011, 2.72, 2.92, 'np_paint_white')
    p.box(-.44, .44, -.014, .014, 2.735, 2.905, 'np_sign_green', '-x+x+z-z')
    p.box(-.011, .011, -.46, .46, 2.48, 2.68, 'np_paint_white')
    p.box(-.014, .014, -.44, .44, 2.495, 2.665, 'np_sign_green', '-y+y+z-z')


def hydrant(p):
    R = 'np_paint_red'
    p.cyl(0, 0, .17, 0, .06, R, 12)
    p.cyl(0, 0, .12, .06, .6, R, 12)
    p.cyl(0, 0, .14, .6, .66, R, 12)
    p.cyl(0, 0, .13, .66, .74, 'np_hivis_yellow', 12, r1=.07)
    p.cyl(0, 0, .03, .74, .8, 'np_chrome', 5)
    for s in (-1, 1):
        p.tube((s * .1, 0, .46), (s * .2, 0, .46), .045, R, 10)
        p.tube((s * .2, 0, .46), (s * .225, 0, .46), .055, 'np_chrome', 6)
    p.tube((0, -.1, .42), (0, -.22, .42), .07, R, 12)
    p.tube((0, -.22, .42), (0, -.25, .42), .08, 'np_chrome', 6)
    for a in range(6):                                                        # flange bolts
        c, s = math.cos(a * math.pi / 3), math.sin(a * math.pi / 3)
        p.box(c * .145 - .012, c * .145 + .012, s * .145 - .012, s * .145 + .012, .06, .08, 'np_chrome', '-z')


def bollard(p):
    p.cyl(0, 0, .1, 0, .95, 'np_steel_black', 12, top=False)
    p.cyl(0, 0, .102, .8, .88, 'np_reflective', 12, top=False)
    p.cyl(0, 0, .1, .95, 1.0, 'np_steel_black', 12, r1=.06)
    p.cyl(0, 0, .14, 0, .02, 'np_steel_black', 12)


def planter(p):
    C = 'np_concrete_light'
    for x0, x1, y0, y1 in ((-1.2, 1.2, -.6, -.5), (-1.2, 1.2, .5, .6), (-1.2, -1.1, -.5, .5), (1.1, 1.2, -.5, .5)):
        p.box(x0, x1, y0, y1, 0, .7, C, '-z')
    p.box(-1.1, 1.1, -.5, .5, .55, .62, 'np_soil', '-z-x+x-y+y')
    p.box(-1.0, 1.0, -.4, .4, .62, 1.15, 'np_hedge')
    p.box(-.95, .95, -.35, .35, 1.15, 1.22, 'np_hedge')
    for x in (-1.0, 1.0):
        p.box(x - .18, x + .18, -.55, .55, -.0, .06, 'np_concrete_dark', '-z')


def ad_column(p):
    p.cyl(0, 0, .65, 0, .3, 'np_door_frame', 16)
    p.cyl(0, 0, .6, .3, 2.8, 'np_door_frame', 16, top=False)
    n = 16
    for k in range(3):                                                        # three curved lit panels
        for i in range(4):
            j = k * 5 + i
            a0, a1 = 2 * math.pi * j / n + math.pi / n, 2 * math.pi * (j + 1) / n + math.pi / n
            r = .605
            q = [(r * math.cos(a0), r * math.sin(a0), .45), (r * math.cos(a1), r * math.sin(a1), .45),
                 (r * math.cos(a1), r * math.sin(a1), 2.65), (r * math.cos(a0), r * math.sin(a0), 2.65)]
            am = (a0 + a1) / 2
            p.face(q, 'np_glow_white', (math.cos(am), math.sin(am), 0))
    p.cyl(0, 0, .72, 2.8, 2.92, 'np_door_frame', 16, top=False)
    p.cyl(0, 0, .72, 2.92, 3.1, 'np_door_frame', 16, r1=.2)
    p.cyl(0, 0, .06, 3.1, 3.2, 'np_chrome', 8, r1=.02)


def power_pole(p, tx):
    p.cyl(0, 0, .16, 0, 11.0, 'np_pole_wood', 8, r1=.11)
    yA = -.22                                                                 # crossarm bolted on the -y face
    p.box(-1.2, 1.2, yA - .05, yA + .05, 9.9, 10.02, 'np_pole_wood')
    for s in (-1, 1):
        p.beam((s * .7, yA, 9.92), (0, yA + .02, 9.4), .04, 'np_steel_galv', h=.01)
    p.box(-.06, .06, -.18, -.11, 9.85, 10.05, 'np_steel_galv')
    attach = []
    for x in (-.9, 0.0, .9):                                                  # insulators
        p.cyl(x, yA, .012, 10.02, 10.1, 'np_steel_galv', 6, top=False)
        for z in (10.1, 10.17, 10.24):
            p.cyl(x, yA, .07, z, z + .04, 'np_insulator', 10)
            p.cyl(x, yA, .035, z + .04, z + .07, 'np_insulator', 8, top=False)
        attach.append([x, yA, 10.3])
    p.cyl(0, 0, .12, 11.0, 11.04, 'np_steel_galv', 8)
    for z in (2.5, 3.5, 4.5, 5.5):                                            # climbing steps
        s = 1 if int(z) % 2 else -1
        p.beam((s * .1, 0, z), (s * .32, 0, z), .025, 'np_steel_galv')
    if tx:
        p.box(-.12, .12, .1, .2, 7.4, 8.6, 'np_steel_galv')
        p.cyl(0, .5, .32, 7.4, 8.5, 'np_steel_galv', 12)
        p.cyl(0, .5, .34, 8.5, 8.58, 'np_steel_galv', 12)
        for x in (-.15, .15):
            p.cyl(x, .5, .04, 8.58, 8.8, 'np_insulator', 8)
            p.tube((x, .5, 8.8), (x * 6, yA, 9.95), .008, 'np_cable', 4)
        p.box(-.2, .2, .17, .2, 7.7, 7.9, 'nc_paint_yellow')
    return attach


def wire(p, ys):
    for y in ys:
        p.box(0, 1.0, y - .0125, y + .0125, -.0125, .0125, 'np_cable', '-x+x')


def transformer(p):
    p.box(-.95, .95, -.85, .85, 0, .15, 'np_concrete', '-z')
    p.box(-.8, .8, -.7, .7, .15, 1.48, 'np_green_cab')
    p.box(-.84, .84, -.74, .74, 1.48, 1.55, 'np_green_cab')
    p.box(-.004, .004, -.706, -.7, .2, 1.43, 'np_paint_black')               # door seam
    for x in (-.4, .4):
        p.box(x - .12, x + .12, -.72, -.7, 1.15, 1.25, 'np_hivis_yellow')    # warning plates (blank)
        p.box(x * .2 - .02 + (.1 if x > 0 else -.1), x * .2 + .02 + (.1 if x > 0 else -.1), -.74, -.7, .7, .9, 'np_chrome')
    for s in (-1, 1):
        for i in range(5):
            z = .4 + i * .12
            p.box(s * .8, s * .81, -.4, .4, z, z + .05, 'np_paint_black')
    p.box(-.8, .8, -.7, .7, .15, .2, 'np_concrete_dark', '-z')


def manhole_open(p):
    p.face([(q[0], q[1], .005) for q in ring(.4, 16)], 'nc_tunnel', (0, 0, 1))
    for i in range(16):                                                       # frame ring
        a0, a1 = 2 * math.pi * i / 16, 2 * math.pi * (i + 1) / 16
        q = [(.4 * math.cos(a0), .4 * math.sin(a0), .015), (.4 * math.cos(a1), .4 * math.sin(a1), .015),
             (.5 * math.cos(a1), .5 * math.sin(a1), .015), (.5 * math.cos(a0), .5 * math.sin(a0), .015)]
        p.face(q, 'np_cast_iron', (0, 0, 1))
    p.tube((0, 0, .015), (0, 0, -.25), .4, 'np_concrete_dark', 16, caps=(False, False))  # shaft wall
    p.tube((0, 0, 0), (0, 0, .015), .5, 'np_cast_iron', 16, caps=(False, False))
    p.cyl(1.1, .15, .38, 0, .035, 'np_cast_iron', 16)
    for k in range(4):
        p.box(1.1 - .3 + k * .2 - .01, 1.1 - .3 + k * .2 + .01, -.1, .4, .035, .04, 'np_steel_black', '-z')
    H = 'np_hivis'
    pts = [(-.65, -.65), (.65, -.65), (.65, .65), (-.65, .65)]
    for x, y in pts:
        p.tube((x, y, 0), (x, y, 1.0), .025, 'np_steel_galv', 6)
        p.box(x - .1, x + .1, y - .1, y + .1, 0, .03, 'np_rubber', '-z')
    for i in range(4):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
        for z in (.92, .5):
            p.beam((x0, y0, z), (x1, y1, z), .04, H if z > .6 else 'np_paint_white', h=.1)


def cone(p):
    p.box(-.19, .19, -.19, .19, 0, .03, 'np_rubber', '-z')
    rr = lambda z: .16 + (.03 - .16) * (z - .03) / (.7 - .03)
    segs = [(.03, .3, 'np_hivis'), (.3, .37, 'np_reflective'), (.37, .45, 'np_hivis'), (.45, .52, 'np_reflective'), (.52, .7, 'np_hivis')]
    for z0, z1, m in segs:
        p.cyl(0, 0, rr(z0), z0, z1, m, 12, top=(z1 >= .7), r1=rr(z1))


def leaf(p, mat):
    # a dry leaf blown along the street (the ambient system tumbles it): a thin blade with a raised midrib
    p.box(-.04, .04, -.022, .022, 0, .002, mat)
    p.box(-.045, .045, -.003, .003, .002, .004, mat)


def paper(p):
    # a sheet of litter with a fold
    p.box(-.105, .0, -.14, .14, 0, .001, 'np_paper')
    p.box(.0, .105, -.14, .14, .012, .013, 'np_paper')


def wrapper(p):
    # a crumpled wrapper
    p.box(-.05, .05, -.03, .03, 0, .04, 'np_wrapper')
    p.box(-.03, .06, -.035, .02, .02, .055, 'np_paper')


def barrier_jersey(p):
    prof = [(-.3, 0), (.3, 0), (.3, .075), (.2, .33), (.075, .8), (-.075, .8), (-.2, .33), (-.3, .075)]
    p.prism_x(prof, -1.5, 1.5, 'np_concrete_light')
    for x in (-1.0, 1.0):                                                     # lifting / drain slots
        p.panel_xz([(x - .25, .0), (x + .25, .0), (x + .25, .07), (x - .25, .07)], -.302, -.29, 'np_concrete_dark', back=False)
    p.box(-1.5, 1.5, -.002, .002, .8, .805, 'np_concrete_dark', '-z')


def fence(p):
    for x in (-1.5, 1.5):
        p.cyl(x, 0, .03, 0, 2.2, 'np_steel_galv', 8)
        p.cyl(x, 0, .1, 0, .08, 'np_concrete', 8)
    p.tube((-1.5, 0, 2.15), (1.5, 0, 2.15), .02, 'np_steel_galv', 6, caps=(False, False))
    p.tube((-1.5, 0, .08), (1.5, 0, .08), .006, 'np_steel_galv', 4, caps=(False, False))
    p.box(-1.47, 1.47, -.004, .004, .08, 2.13, 'np_chainlink', '-z+z')


def fence_site(p):
    p.box(-1.5, 1.5, -.012, .012, 0, 2.4, 'np_hoarding', '-z')
    p.box(-1.5, 1.5, -.016, -.012, 2.05, 2.2, 'np_hivis', '+y')
    p.box(-1.5, 1.5, -.016, -.012, .1, .25, 'np_hivis', '+y')
    for x in (-1.45, 1.45):                                                   # timber posts and raking braces behind
        p.box(x - .05, x + .05, .012, .112, 0, 2.35, 'np_batten', '-z')
        p.beam((x, .06, 1.7), (x, 1.2, 0.02), .06, 'np_batten', up=(1, 0, 0))
        p.box(x - .2, x + .2, 1.05, 1.45, 0, .12, 'np_concrete', '-z')        # kentledge block
    for z in (.5, 1.9):
        p.box(-1.5, 1.5, .012, .06, z - .05, z + .05, 'np_batten')


def barrier_arm(p):
    p.box(-.22, .22, -.22, .22, 0, 1.15, 'np_paint_white', '-z')
    p.box(-.24, .24, -.24, .24, 1.15, 1.2, 'np_paint_red')
    p.box(-.05, .05, -.05, .05, 1.2, 1.3, 'np_glow_red')
    p.box(-.23, .23, -.232, -.22, .3, .5, 'np_paint_black', '+y')
    p.box(-.6, -.22, -.08, .08, .9, 1.1, 'nc_steel')                          # counterweight stub
    for i in range(12):
        x0 = .22 + .5 * i
        p.box(x0, x0 + .5, -.04, .04, .96, 1.04, 'np_paint_red' if i % 2 == 0 else 'np_paint_white')
    p.cyl(5.9, 0, .04, 0, .9, 'np_paint_white', 8)                            # rest fork
    p.box(5.82, 5.98, -.06, .06, .9, .96, 'np_paint_red')


def guard_booth(p):
    W = 'np_booth'
    p.box(-1.25, 1.25, -1.05, 1.05, 0, .15, 'np_concrete', '-z')
    p.box(-1.2, 1.2, -1.0, 1.0, .15, 1.0, W, '-z')
    p.box(-1.18, 1.18, -.98, .98, 1.0, 2.3, 'np_glass_dark', '-z+z')
    for x in (-1.2, 1.2):
        for y in (-1.0, 1.0):
            p.box(x - .04, x + .04, y - .04, y + .04, 1.0, 2.3, W)
    for x in (-.2,):
        p.box(x - .03, x + .03, -1.02, -.98, 1.0, 2.3, W)
    p.box(-1.2, 1.2, -1.0, 1.0, 2.3, 2.6, W)
    p.box(-1.32, 1.32, -1.12, 1.12, 2.6, 2.7, 'np_door_frame')
    p.box(.2, 1.0, -1.025, -1.0, .15, 2.3, W)                                  # door with its own window
    p.box(.3, .9, -1.03, -1.025, 1.25, 2.15, 'np_glass_dark')
    p.box(.85, .9, -1.06, -1.03, 1.0, 1.08, 'np_chrome')
    p.box(-.95, -.15, -1.01, -1.0, 2.37, 2.53, 'np_paint_white')              # blank number plate
    p.box(-.6, .6, -.15, .15, 2.7, 2.78, 'np_door_frame')
    p.box(-.55, .55, -.12, .12, 2.78, 2.86, 'np_glow_amber')                  # roof light bar
    p.box(-1.24, -1.2, -.6, .6, 1.0, 1.04, 'np_door_frame')                    # sill shelf west window
    p.box(-1.38, -1.2, -.4, .4, .98, 1.02, 'np_door_frame')


def container(p, office):
    C = 'np_site_office' if office else 'np_container'
    zb = .2 if office else 0.0
    if office:
        for x in (-2.7, 2.7):
            for y in (-.9, .9):
                p.box(x - .2, x + .2, y - .2, y + .2, 0, zb, 'np_concrete', '-z')
    p.box(-3.0, 3.0, -1.19, 1.19, zb + .12, zb + 2.47, C, '-z+z')
    p.box(-3.0, 3.0, -1.19, 1.19, zb + 2.47, zb + 2.59, C, '-z')
    p.box(-3.0, 3.0, -1.22, 1.22, zb, zb + .12, 'nc_steel' if not office else C, '-z')
    for y0, y1 in ((-1.22, -1.16), (1.16, 1.22)):
        p.box(-3.0, 3.0, y0, y1, zb + 2.47, zb + 2.59, C)
    for x in (-3.05, 2.87):                                                   # corner castings
        for y in (-1.22, 1.06):
            for z in (zb, zb + 2.47):
                p.box(x, x + .18, y, y + .16, z, z + .12, 'np_steel_black')
    for x in (-3.0, 3.0):                                                     # corner posts
        for y in (-1.22, 1.22):
            p.box(x - .05 if x > 0 else x, x if x > 0 else x + .05, y - .06 if y > 0 else y, y if y > 0 else y + .06,
                  zb + .12, zb + 2.47, C)
    if not office:
        for s in (-1, 1):                                                     # corrugation ribs on the long sides
            for i in range(20):
                x = -2.75 + i * .29
                y0, y1 = sorted((s * 1.19, s * 1.22))
                p.box(x - .07, x + .07, y0, y1, zb + .12, zb + 2.47, C, '-z+z')
        for y in (-.85, -.3, .3, .85):                                       # door locking bars (+x end)
            p.tube((3.03, y, zb + .15), (3.03, y, zb + 2.44), .02, 'np_steel_galv', 6)
            p.box(3.0, 3.05, y + .03, y + .09, zb + 1.1, zb + 1.3, 'np_steel_galv')
        p.box(3.0, 3.005, -.004, .004, zb + .12, zb + 2.47, 'np_steel_black')
        for i in range(8):
            y = -1.0 + i * .285
            p.box(-3.03, -3.0, y - .06, y + .06, zb + .12, zb + 2.47, C, '-z+z')
        return dict(door_end='+x')
    # site office: windows and a door on -y, stair, lamp
    for x0, x1 in ((-2.5, -1.2), (.9, 2.2)):
        p.box(x0, x1, -1.215, -1.19, zb + 1.0, zb + 2.1, 'np_glass_dark')
        for zz in (zb + .96, zb + 2.1):
            p.box(x0 - .04, x1 + .04, -1.24, -1.19, zz, zz + .04, 'np_door_frame')
        for xx in (x0 - .04, (x0 + x1) / 2 - .02, x1):
            p.box(xx, xx + .04, -1.24, -1.19, zb + 1.0, zb + 2.1, 'np_door_frame')
        for i in range(5):                                                    # security bars
            xx = x0 + (x1 - x0) * (i + .5) / 5
            p.beam((xx, -1.26, zb + 1.0), (xx, -1.26, zb + 2.1), .015, 'np_steel_black')
    p.box(-.6, .35, -1.21, -1.19, zb + .12, zb + 2.2, 'np_steel_door')
    p.box(-.65, .4, -1.23, -1.19, zb + 2.2, zb + 2.26, 'np_door_frame')
    p.box(.18, .24, -1.25, -1.21, zb + 1.0, zb + 1.12, 'np_chrome')
    p.box(-.25, .0, -1.3, -1.19, zb + 2.35, zb + 2.45, 'np_steel_black')
    p.box(-.23, -.02, -1.305, -1.3, zb + 2.36, zb + 2.44, 'nc_glow_warm')
    S = 'np_steel_galv'
    p.box(-.8, .55, -1.95, -1.22, .3, .34, 'np_grille')                       # landing
    for x in (-.78, .53):
        p.beam((x, -1.93, 0), (x, -1.93, .3), .04, S)
        p.beam((x, -1.25, 0), (x, -1.25, .3), .04, S)
    p.box(-.8, .55, -2.2, -1.95, .14, .18, 'np_grille')                       # step
    for x in (-.8, .55):
        p.beam((x, -2.2, 0), (x, -1.95, .3), .03, S, h=.12)
        p.beam((x, -2.15, .2), (x, -2.15, 1.25), .03, S)
        p.beam((x, -1.93, .34), (x, -1.93, 1.25), .03, S)
        p.beam((x, -2.15, 1.25), (x, -1.25, 1.25), .03, S)
    return dict(door='-y')


def pallets(p):
    for k in range(3):
        z = k * .144
        for y in (-.45, 0, .45):
            p.box(-.6, .6, y - .05, y + .05, z, z + .022, 'np_pallet', '-z')
            for x in (-.55, 0, .55):
                p.box(x - .05, x + .05, y - .05, y + .05, z + .022, z + .122, 'np_batten')
        for y in (-.44, -.22, 0, .22, .44):
            p.box(-.6, .6, y - .05, y + .05, z + .122, z + .144, 'np_pallet')
    z = .432
    p.box(-.58, .58, -.48, .48, z, z + .95, 'np_wrap', '-z')
    p.box(-.59, .59, -.49, .49, z + .3, z + .42, 'np_wrap', '-z+z')
    p.box(-.56, .56, -.46, .46, z + .95, z + .97, 'np_pallet', '-z')         # card top sheet


def dumpster(p):
    D = 'np_dumpster'
    r0 = [(-.85, -.45), (.85, -.45), (.85, .45), (-.85, .45)]
    r1 = [(-.95, -.55), (.95, -.55), (.95, .55), (-.95, .55)]
    p.loftz(r0, .12, r1, 1.08, D, top=False)
    p.box(-.85, .85, -.45, .45, .12, .14, D, '+z')
    p.box(-.97, .97, -.57, .57, 1.03, 1.1, D, '-z')                           # rim
    p.face([(-.95, -.55, 1.1), (.95, -.55, 1.1), (.95, .55, 1.2), (-.95, .55, 1.2)], 'np_rubber', (0, -.1, 1))  # lid
    p.face([(-.95, -.55, 1.1), (.95, -.55, 1.1), (.95, .55, 1.2), (-.95, .55, 1.2)], 'np_rubber', (0, .1, -1))
    p.box(-.95, .95, .55, .6, 1.08, 1.2, 'np_rubber')
    for s in (-1, 1):
        p.box(s * .9 - .06, s * .9 + .06, -.3, .3, .55, .7, 'nc_steel')        # lift pockets
        for y in (-.35, .35):
            p.box(s * .75 - .05, s * .75 + .05, y - .05, y + .05, .0, .12, 'np_rubber', '-z')
    p.box(-.6, .6, -.5, -.48, .6, .8, 'np_paint_white')                       # blank label


def debris(p):
    R = random.Random(5)
    mats = ('np_concrete', 'np_concrete_light', 'np_concrete_dark', 'np_concrete_patch')
    base = [(1.5 * math.cos(a) * (1 + .12 * math.sin(3 * a)), 1.25 * math.sin(a) * (1 + .1 * math.cos(4 * a)))
            for a in [2 * math.pi * i / 12 for i in range(12)]]
    top = [(x * .55, y * .55) for x, y in base]
    p.loftz(base, 0, top, .22, 'np_concrete_dark', top=True)
    hgt = lambda x, y: max(0.0, .8 * (1 - (x / 1.5) ** 2 - (y / 1.25) ** 2))
    for i in range(26):
        a = R.random() * 6.283; rr = math.sqrt(R.random())
        x, y = 1.3 * rr * math.cos(a), 1.05 * rr * math.sin(a)
        s = .12 + .3 * (1 - rr) * R.random() + .08
        h = hgt(x, y)
        yaw = R.random() * 6.283; tilt = (R.random() - .5) * .9
        u = V((math.cos(yaw), math.sin(yaw), 0)); v = V((-math.sin(yaw), math.cos(yaw), 0))
        w = V((0, 0, 1))
        rot = lambda vec: vec * math.cos(tilt) + u.cross(vec) * math.sin(tilt)
        v2, w2 = rot(v), rot(w)
        hz = s * (.35 + .3 * R.random())
        p.obox((x, y, max(hz * .5, h - hz * .3)), u, v2, w2, s, s * (.5 + .5 * R.random()), hz, mats[i % 4])
    p.obox((.3, -.2, .45), (1, .2, .35), (-.2, 1, 0), V((1, .2, .35)).cross(V((-.2, 1, 0))), .7, .45, .06, 'np_concrete_light')
    for i in range(7):                                                        # rebar
        a = R.random() * 6.283; rr = R.random() * .8
        x, y = 1.2 * rr * math.cos(a), 1.0 * rr * math.sin(a)
        z = hgt(x, y) * .7
        d = V((R.random() - .5, R.random() - .5, .4 + R.random())).normalized()
        L = .5 + R.random() * .7
        p.beam((x, y, z), V((x, y, z)) + d * L, .016, 'np_rust')
        if i % 2:
            e = V((x, y, z)) + d * L
            p.beam(e, e + V((R.random() - .5, R.random() - .5, -.2)).normalized() * .3, .016, 'np_rust')


def scaffold(p):
    G, B = 'np_steel_galv', 'np_plywood'
    t = lambda a, b: p.tube(a, b, .024, G, 6, caps=(False, False))
    yi, yo = -.15, -1.25
    for x in (-1.5, 1.5):
        for y in (yi, yo):
            t((x, y, 0), (x, y, 3.2))
        t((x, yi, .05), (x, yo, .05))                                         # transoms
        t((x, yi, 1.05), (x, yo, 1.05))
    for x in (-.5, .5):
        t((x, yi - .05, .05), (x, yo + .05, .05))
    for y in (yi, yo):
        t((-1.5, y, .02), (1.5, y, .02))                                       # ledgers
    for z in (.55, 1.05):
        t((-1.5, yo, z), (1.5, yo, z))                                        # guard rails
    t((-1.5, yo - .03, .1), (1.5, yo - .03, 3.15))                            # face brace
    for i in range(5):                                                        # deck boards
        y0 = -1.22 + i * .2
        p.box(-1.5, 1.5, y0, y0 + .19, .08, .12, B)
    p.box(-1.5, 1.5, -1.24, -1.22, .12, .27, B)                               # toe board
    for x in (-1.5, 1.5):                                                     # couplers
        for y in (yi, yo):
            for z in (.02, 1.05):
                p.box(x - .04, x + .04, y - .04, y + .04, z - .03, z + .03, 'np_steel_black')


def tool_cart(p):
    Y, K = 'np_hivis_yellow', 'np_steel_black'
    p.box(-.62, .52, -.38, .38, .2, .3, K)
    p.box(-.55, .45, -.32, .32, .3, .92, Y)
    p.box(-.5, .4, -.3, .3, .92, .95, Y)
    for x in (-.62, .52):
        for y in (-.38, .38):
            p.tube((x, y, .3), (x, y, 1.0), .02, K, 6, caps=(False, True))
    for y in (-.38, .38):
        p.tube((-.62, y, 1.0), (.52, y, 1.0), .02, K, 6, caps=(False, False))
    for x in (-.62, .52):
        p.tube((x, -.38, 1.0), (x, .38, 1.0), .02, K, 6, caps=(False, False))
    p.box(-.35, .15, -.335, -.32, .5, .82, 'np_paint_black')                 # control panel
    p.box(.0, .06, -.34, -.335, .72, .76, 'np_glow_green')
    for x in (-.25, -.1):
        p.box(x - .03, x + .03, -.345, -.335, .58, .64, 'np_paint_red')
    for i in range(5):                                                        # vents on +y
        z = .45 + i * .08
        p.box(-.3, .3, .32, .33, z, z + .04, K)
    for y in (-.44, .44):                                                     # wheels
        p.tube((-.35, y - .06, .2), (-.35, y + .06, .2), .2, 'np_rubber', 12)
        p.tube((-.35, y + (.065 if y > 0 else -.065), .2), (-.35, y + (.07 if y > 0 else -.07), .2), .1, 'np_steel_galv', 8)
    p.beam((.45, 0, .2), (.45, 0, 0), .05, K)                                 # stand
    p.beam((.52, 0, .28), (.78, 0, .25), .05, K)                              # tow bar
    p.tube((.78, 0, .25), (.78, 0, .3), .04, K, 8)
    p.tube((-.35, .15, .95), (-.35, .15, 1.08), .03, 'np_steel_galv', 6)     # exhaust


def crane(p):
    Y, S = 'np_crane', 'np_steel_black'
    p.box(-3.0, 3.0, -3.0, 3.0, 0, .5, 'np_concrete', '-z')
    H = 60.0; z0 = .5; h = .95; step = 3.0
    cs = [(-h, -h), (h, -h), (h, h), (-h, h)]
    for x, y in cs:
        p.beam((x, y, z0), (x, y, H), .18, Y)
    nlev = int((H - z0) // step)
    for k in range(nlev + 1):
        z = z0 + k * step if k < nlev else H - .1
        for i in range(4):
            a, b = cs[i], cs[(i + 1) % 4]
            p.beam((a[0], a[1], z), (b[0], b[1], z), .1, Y)
            if k < nlev:
                z1 = min(z + step, H - .1)
                if k % 2:
                    a, b = b, a
                p.beam((a[0], a[1], z), (b[0], b[1], z1), .08, Y)
    # slewing unit, turntable, cab
    p.cyl(0, 0, 1.35, H, H + .25, S, 16)
    p.box(-1.4, 1.4, -1.4, 1.4, H + .25, H + 1.4, Y)
    p.box(.4, 2.3, -3.0, -1.4, H + .2, H + 2.5, 'np_paint_white')
    p.box(2.3, 2.32, -2.9, -1.5, H + 1.0, H + 2.4, 'np_glass_dark')
    p.box(.5, 2.2, -3.02, -3.0, H + 1.0, H + 2.4, 'np_glass_dark')
    p.box(.3, 2.4, -3.1, -1.3, H + 2.5, H + 2.6, Y)
    zb = H + 1.4                                                              # chord level of both jibs
    # apex tower
    top = V((0, 0, zb + 8.0))
    for x, y in cs:
        p.beam((x, y, zb), top, .14, Y)
    p.box(-.3, .3, -.3, .3, top.z - .2, top.z + .3, Y)
    p.box(-.1, .1, -.1, .1, top.z + .3, top.z + .45, 'np_glow_red')
    # jib: triangular section, bottom chords y +-0.8, top chord y 0 at +1.8, 1.3..50 m along +x
    L0, L1, pw = 1.3, 50.0, 2.5
    zt = zb + 1.8
    for y in (-.8, .8):
        p.beam((L0, y, zb), (L1, y, zb), .14, Y)
    p.beam((L0, 0, zt), (L1 - 1.25, 0, zt), .12, Y)
    n = int((L1 - L0) // pw)
    for k in range(n + 1):
        x = L0 + k * pw
        if x > L1:
            break
        p.beam((x, -.8, zb), (x, .8, zb), .08, Y)
        if k < n:
            xm = x + pw / 2; x1 = min(x + pw, L1)
            for y in (-.8, .8):
                p.beam((x, y, zb), (xm, 0, zt), .07, Y)
                p.beam((xm, 0, zt), (x1, y, zb), .07, Y)
    p.box(L1 - .1, L1 + .1, -.1, .1, zb + .1, zb + .25, 'np_glow_red')
    # counter-jib with walkway, winch and counterweights
    C0, C1 = -1.3, -15.0
    for y in (-1.0, 1.0):
        p.beam((C0, y, zb), (C1, y, zb), .16, Y, h=.3)
        p.beam((C0, y, zb + 1.1), (C1, y, zb + 1.1), .05, Y)
        for x in (-3.5, -7.0, -10.5, -14.5):
            p.beam((x, y, zb), (x, y, zb + 1.1), .05, Y)
    for x in (-1.5, -4.0, -6.5, -9.0, -11.5, -14.0):
        p.beam((x, -1.0, zb), (x, 1.0, zb), .1, Y)
    p.box(C1, C0, -.5, .5, zb + .15, zb + .19, 'np_grille')
    p.box(-8.0, -5.5, -.8, .8, zb + .19, zb + 1.3, 'nc_steel')                # winch house
    for i in range(4):
        x0 = -14.85 + i * .7
        p.box(x0, x0 + .66, -1.0, 1.0, zb - 1.8, zb + 1.0, 'np_concrete_light')
    # pendant ties from the apex
    for e in ((L1 - 2.0, 0, zt), (25.0, 0, zt), (C1 + .5, -.9, zb + .2), (C1 + .5, .9, zb + .2)):
        p.beam(top, e, .05, S)
    # trolley at 30 m, hook block on its line
    xt = 30.0
    p.box(xt - .6, xt + .6, -.9, .9, zb - .5, zb - .05, S)
    hz = 28.0
    for y in (-.15, .15):
        p.beam((xt, y, zb - .5), (xt, y, hz + 1.0), .03, S)
    p.box(xt - .3, xt + .3, -.3, .3, hz, hz + 1.0, Y)
    p.box(xt - .3, xt + .3, -.31, .31, hz + .4, hz + .6, S)
    p.beam((xt, 0, hz), (xt, 0, hz - .45), .07, S)
    p.beam((xt, 0, hz - .45), (xt + .25, 0, hz - .45), .07, S)
    p.beam((xt + .25, 0, hz - .45), (xt + .25, 0, hz - .3), .06, S)
    return dict(hook=[xt, 0.0, hz], jib=[L0, L1], counter_jib=[C1, C0], slew_z=H)


# ------------------------------------------------------------------ plaza / street extras (anchor ground)
def hoop(p, c, u, v, R, r, mat, n=16, a0=0.0, a1=2 * math.pi, sides=6):
    """a bent tube along an arc of radius R round c in the (u, v) plane (wheels, rings, rack hoops)"""
    c, u, v = V(c), V(u).normalized(), V(v).normalized()
    pts = [c + (u * math.cos(a0 + (a1 - a0) * i / n) + v * math.sin(a0 + (a1 - a0) * i / n)) * R for i in range(n + 1)]
    for i in range(n):
        p.tube(pts[i], pts[i + 1], r, mat, sides, caps=(False, False))


def cafe_set(p):
    K, W = 'np_steel_black', 'np_wood_bench'
    p.cyl(0, 0, .25, 0, .03, K, 12)                                          # table
    p.cyl(0, 0, .04, .03, .72, K, 8, top=False)
    p.cyl(0, 0, .35, .72, .75, 'np_paint_white', 16)
    for k in range(3):                                                        # chairs facing the table
        a = math.pi / 2 + 2 * math.pi * k / 3
        f = V((-math.cos(a), -math.sin(a), 0)); s = V((-f.y, f.x, 0)); z = V((0, 0, 1))
        c = V((math.cos(a), math.sin(a), 0)) * .8
        p.obox(c + z * .45, f, s, z, .21, .21, .02, W)
        for df in (-.18, .18):
            for ds in (-.18, .18):
                q = c + f * df + s * ds
                p.beam(q, q + z * .43, .025, K)
        b = c - f * .2
        for ds in (-.18, .18):
            p.beam(b + s * ds + z * .45, b - f * .04 + s * ds + z * .88, .025, K)
        t = math.radians(10)
        bf = f * math.cos(t) + z * math.sin(t); bz = z * math.cos(t) - f * math.sin(t)
        p.obox(b - f * .03 + z * .72, s, bz, bf, .2, .12, .015, W)
    # parasol through the table
    p.cyl(0, 0, .025, .75, 2.55, 'np_steel_galv', 8)
    n = 8; R = 1.2; zr, za = 2.2, 2.5
    rim = [(R * math.cos(2 * math.pi * i / n), R * math.sin(2 * math.pi * i / n), zr) for i in range(n)]
    for i in range(n):
        a, b = rim[i], rim[(i + 1) % n]
        tri = [a, b, (0, 0, za)]
        mid = V(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0)).normalized()
        p.face(tri, 'np_parasol', mid * .3 + V((0, 0, 1)))
        p.face(tri, 'np_parasol', -(mid * .3 + V((0, 0, 1))))
        p.face([a, b, (b[0], b[1], zr - .12), (a[0], a[1], zr - .12)], 'np_parasol', mid)   # valance
        p.face([a, b, (b[0], b[1], zr - .12), (a[0], a[1], zr - .12)], 'np_parasol', -mid)
        p.beam((0, 0, 1.9), (a[0] * .97, a[1] * .97, zr - .02), .015, 'np_steel_galv')
    p.cyl(0, 0, .05, za, za + .08, 'np_steel_galv', 8, r1=.01)


def kiosk(p):
    K, F = 'np_kiosk', 'np_door_frame'
    p.box(-1.35, 1.35, -1.05, 1.05, 0, .1, 'np_concrete', '-z')
    p.box(-1.3, 1.3, .94, 1.0, .1, 2.5, K)                                    # back
    for x0, x1 in ((-1.3, -1.24), (1.24, 1.3)):
        p.box(x0, x1, -1.0, 1.0, .1, 2.5, K)                                  # sides
    p.box(-1.3, 1.3, -1.0, -.94, .1, .95, K)                                  # front below the hatch
    p.box(-1.3, 1.3, -1.0, -.94, 2.0, 2.5, K)                                 # front above it
    for x0, x1 in ((-1.3, -.9), (.9, 1.3)):
        p.box(x0, x1, -1.0, -.94, .95, 2.0, K)
    p.box(-1.24, 1.24, -.94, .94, .1, .12, 'np_wood_bench', '-z')             # inside: floor, lining, ceiling lamp
    p.box(-1.24, 1.24, .92, .94, .12, 2.44, 'np_interior', '+y')
    p.box(-1.3, 1.3, -1.0, 1.0, 2.44, 2.5, K, '+z')
    p.box(-.4, .4, -.2, .2, 2.42, 2.44, 'nc_glow_warm', '+z')
    for z in (1.2, 1.5, 1.8):                                                 # shelves with goods
        p.box(-.85, .85, .5, .92, z - .02, z, 'np_wood_bench')
        x = -.8
        for i in range(9):
            w = .12 + .05 * ((i * 7) % 3)
            m = ('np_graf_pink', 'np_graf_teal', 'np_graf_yellow', 'np_paint_white', 'np_graf_purple')[(i + int(z * 10)) % 5]
            p.box(x, x + w - .02, .6, .86, z, z + .18 + .04 * (i % 2), m)
            x += w
            if x > .7:
                break
    p.box(-.95, .95, -1.18, -.88, .92, .97, 'np_wood_bench')                  # serving counter
    p.box(-1.0, -.9, -1.03, -.94, .95, 2.0, F); p.box(.9, 1.0, -1.03, -.94, .95, 2.0, F)
    # fabric awning over the hatch
    up = (0, -.4, .9)
    p.face([(-1.25, -1.0, 2.35), (1.25, -1.0, 2.35), (1.25, -1.8, 2.05), (-1.25, -1.8, 2.05)], 'np_awning_green', up)
    p.face([(-1.25, -1.0, 2.33), (1.25, -1.0, 2.33), (1.25, -1.78, 2.03), (-1.25, -1.78, 2.03)], 'np_awning_green', (0, .4, -.9))
    p.box(-1.25, 1.25, -1.82, -1.8, 1.85, 2.05, 'np_awning_green', '+z')
    for x in (-1.2, 1.2):
        p.beam((x, -1.0, 2.15), (x, -1.78, 2.04), .025, 'np_steel_black')
    # sign band (blank, lit) and roof
    p.box(-1.36, 1.36, -1.06, 1.06, 2.5, 2.75, F)
    p.box(-1.25, 1.25, -1.07, -1.06, 2.54, 2.71, 'np_glass_sign_warm', '+y')
    for s in (-1, 1):
        p.box(s * 1.36, s * 1.37, -.95, .95, 2.54, 2.71, 'np_glass_sign_warm')
    p.box(-1.42, 1.42, -1.12, 1.12, 2.75, 2.8, K)


def bicycle(p, x, frame):
    K = 'np_steel_black'
    yr, yf, rw = .52, -.53, .34                                             # rear / front axle (front toward -y)
    for y in (yr, yf):
        hoop(p, (x, y, rw), (0, 1, 0), (0, 0, 1), rw - .02, .02, 'np_rubber', 14, sides=4)
        hoop(p, (x, y, rw), (0, 1, 0), (0, 0, 1), rw - .05, .008, 'np_steel_galv', 10, sides=3)
        p.tube((x - .05, y, rw), (x + .05, y, rw), .025, 'np_steel_galv', 6)
        for a in range(4):                                                    # spokes
            c, s = math.cos(a * math.pi / 4), math.sin(a * math.pi / 4)
            p.beam((x, y - c * (rw - .05), rw - s * (rw - .05)), (x, y + c * (rw - .05), rw + s * (rw - .05)), .004, 'np_steel_galv')
    bb = V((x, .02, .3)); seat = V((x, .12, .76)); head_t = V((x, -.38, .78)); head_b = V((x, -.41, .62))
    for a, b in ((bb, seat), (seat - V((0, .02, .04)), head_t), (bb, head_b), (bb, V((x, yr, rw))),
                 (seat - V((0, .01, .05)), V((x, yr, rw))), (head_b, V((x, yf, rw)))):
        p.tube(a, b, .018, frame, 6)
    p.tube(head_b, head_t, .022, frame, 6)
    p.tube(head_t, V((x, -.36, .95)), .014, K, 6)                            # stem and bars
    p.tube((x - .24, -.34, .95), (x + .24, -.34, .95), .013, K, 6)
    p.obox(seat + V((0, .0, .05)), (0, 1, 0), (1, 0, 0), (0, 0, 1), .13, .07, .025, K)
    p.tube(seat, seat + V((0, 0, .03)), .012, K, 6)
    p.beam(bb + V((-.07, .0, .0)), bb + V((-.07, -.12, -.12)), .02, K)       # crank and pedal
    p.box(x - .13, x - .07, -.15, -.07, .16, .19, K)


def bike_rack(p):
    G = 'np_steel_galv'
    for y in (-.35, .35):
        p.box(-1.6, 1.6, y - .03, y + .03, 0, .01, G, '-z')
    for x in (-1.2, -.4, .4, 1.2):                                            # hoops in the y-z plane
        for y in (-.35, .35):
            p.tube((x, y, 0), (x, y, .6), .025, G, 6, caps=(False, False))
        hoop(p, (x, 0, .6), (0, 1, 0), (0, 0, 1), .35, .025, G, 8, 0, math.pi)
    bicycle(p, -1.06, 'np_bike_red')
    bicycle(p, .54, 'np_bike_teal')


def sculpture(p):
    S, M = 'np_stone', 'np_polished'
    p.box(-1.5, 1.5, -1.5, 1.5, 0, .42, S, '-z')                              # plinth with a stepped cap
    p.box(-1.42, 1.42, -1.42, 1.42, .42, .5, S)
    p.box(-1.505, 1.505, -1.505, 1.505, .36, .38, 'nc_glow_cyan', '+z-z')
    # two ribbons twisting round each other, rising to ~5.8 m
    N = 28
    for k in range(2):
        rings = []
        for i in range(N + 1):
            t = i / N
            th = t * 1.6 * math.pi + k * math.pi
            r = .25 + .55 * math.sin(math.pi * min(1.0, t * 1.15)) ** .8
            z = .5 + t * 5.3
            c = V((r * math.cos(th), r * math.sin(th), z))
            rad = V((math.cos(th), math.sin(th), 0)); tan = V((-math.sin(th), math.cos(th), 0))
            w = .32 * (1 - .55 * t) + .06; h = .07
            rings.append((c, [c + rad * w + tan * h, c + rad * w - tan * h, c - rad * w - tan * h, c - rad * w + tan * h]))
        for i in range(N):
            (c0, A), (c1, B) = rings[i], rings[i + 1]
            for j in range(4):
                jj = (j + 1) % 4
                want = (A[j] + A[jj] + B[j] + B[jj]) / 4 - (c0 + c1) / 2
                p.face([A[j], A[jj], B[jj], B[j]], M, want)
        p.face(rings[0][1], M, (0, 0, -1)); p.face(rings[-1][1], M, (0, 0, 1))
    # a tilted ring the ribbons pass through, and a floating orb near the top
    t = math.radians(22)
    hoop(p, (0, 0, 3.0), (1, 0, 0), (0, math.cos(t), math.sin(t)), 1.05, .07, M, 28, sides=8)
    o = V((0, 0, 5.95)); n = 10
    for i in range(n):                                                        # faceted orb (two cones)
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        e0 = o + V((math.cos(a0), math.sin(a0), 0)) * .28; e1 = o + V((math.cos(a1), math.sin(a1), 0)) * .28
        out = V((math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0))
        p.face([e0, e1, o + V((0, 0, .28))], M, out + V((0, 0, 1)))
        p.face([e0, e1, o - V((0, 0, .28))], M, out - V((0, 0, 1)))


# ------------------------------------------------------------------ catalogue
def _finish(p, name, M, anchor, out, **extra):
    o = p.a.object(name, M, two_uv=True)
    vs = [v.co for v in o.data.vertices]
    mn = [min(v[i] for v in vs) for i in range(3)]; mx = [max(v[i] for v in vs) for i in range(3)]
    tris = sum(len(f.vertices) - 2 for f in o.data.polygons)
    out[name] = dict(size=[round(mx[i] - mn[i], 3) for i in range(3)], min=[round(c, 3) for c in mn],
                     max=[round(c, 3) for c in mx], anchor=anchor, tris=tris, **extra)
    return o


def build_props(M):
    """Builds every NCK_* prop below as a root mesh object in the current scene; returns {name: info}."""
    materials(M)
    out = {}

    def make(name, anchor, fn, *a, **extra):
        p = Prop()
        r = fn(p, *a)
        if isinstance(r, dict):
            extra.update(r)
        _finish(p, name, M, anchor, out, **extra)

    # entrances and walls
    make('NCK_door_lobby', 'wall', door_lobby, kind='entrance', opening=[3.0, 2.7])
    for sfx, awn, stripe, glow in (('a', 'np_awning_red', True, 'np_glass_sign_warm'), ('b', 'np_awning_green', False, 'np_glass_sign_cyan'),
                                   ('c', 'np_awning_blue', True, 'np_glass_sign_magenta'), ('d', 'np_awning_cream', False, 'np_glass_sign_warm')):
        make('NCK_door_shop_' + sfx, 'wall', door_shop, awn, stripe, glow, kind='entrance', opening=[1.1, 2.3])
    make('NCK_door_service', 'wall', door_service, kind='entrance', opening=[1.0, 2.2])
    make('NCK_door_garage', 'wall', door_garage, kind='entrance', opening=[5.5, 2.6])
    make('NCK_loading_dock', 'wall', loading_dock, kind='entrance', opening=[3.6, 4.0], sill=1.2)
    make('NCK_fire_escape', 'wall', fire_escape, stack=3.2,
         note='one storey: landing at z 3.2, flight down to z 0; stack identical modules every 3.2 m (base module at ground)')
    make('NCK_wall_ac', 'wall', wall_ac, note='origin at the unit base (z 0 = bottom of the unit), mount at window sill height')
    make('NCK_meter_box', 'wall', meter_box)
    make('NCK_sign_blade_a', 'wall', sign_blade, 'np_glass_sign_cyan', 'nc_glow_cyan', note='base at z 4')
    make('NCK_sign_blade_b', 'wall', sign_blade, 'np_glass_sign_magenta', 'nc_glow_warm', note='base at z 4')
    make('NCK_boarded', 'wall', boarded, opening=[2.4, 2.6])
    make('NCK_graffiti_patch', 'wall', graffiti, note='patch spans z 0..2; lift it as wanted')
    make('NCK_repair_patch', 'wall', repair_patch, note='patch spans z 0..2; lift it as wanted')
    # roof
    make('NCK_roof_stair', 'ground', roof_stair, place='roof')
    make('NCK_roof_hvac', 'ground', roof_hvac, place='roof')
    make('NCK_roof_vents', 'ground', roof_vents, place='roof')
    make('NCK_roof_solar', 'ground', roof_solar, place='roof', note='panels face -y, tilt 25 deg')
    make('NCK_billboard', 'ground', billboard, place='roof', note='lit face toward -y')
    make('NCK_exhaust_stack', 'ground', exhaust_stack, place='roof')
    # street
    make('NCK_bench', 'ground', bench)
    make('NCK_bin', 'ground', litter_bin)
    make('NCK_bus_stop', 'ground', bus_stop, note='open side and pole sign toward -y (the kerb)')
    make('NCK_traffic_light', 'ground', traffic_light,
         note='pole at the origin, arm over the road along -y; vehicle heads face +x, pedestrian head faces -y')
    make('NCK_stop_sign', 'ground', stop_sign)
    make('NCK_street_sign', 'ground', street_sign)
    make('NCK_hydrant', 'ground', hydrant)
    make('NCK_bollard', 'ground', bollard)
    make('NCK_planter', 'ground', planter)
    make('NCK_ad_column', 'ground', ad_column)
    p = Prop(); att = power_pole(p, False); _finish(p, 'NCK_power_pole', M, 'ground', out, attach=att)
    p = Prop(); att = power_pole(p, True); _finish(p, 'NCK_power_pole_tx', M, 'ground', out, attach=att)
    make('NCK_wire', 'ground', wire, (0.0,), unit=True,
         note='unit span 0..1 along +x, centred on y = z = 0: scale x to the span, place at the attach point')
    make('NCK_wire_set', 'ground', wire, (-.9, 0.0, .9), unit=True, spacing=.9,
         note='three unit spans 0.9 m apart along y (matches the power pole insulators along its x)')
    make('NCK_transformer', 'ground', transformer)
    make('NCK_manhole_open', 'ground', manhole_open)
    make('NCK_cone', 'ground', cone)
    make('NCK_barrier_jersey', 'ground', barrier_jersey, repeat=3.0)
    make('NCK_fence', 'ground', fence, repeat=3.0, note='posts at x +-1.5: repeat every 3.0 m along x')
    make('NCK_fence_site', 'ground', fence_site, repeat=3.0, note='hoarding face toward -y, braces behind (+y)')
    make('NCK_barrier_arm', 'ground', barrier_arm, note='post at the origin, arm along +x')
    make('NCK_guard_booth', 'ground', guard_booth)
    make('NCK_container', 'ground', container, False)
    make('NCK_site_office', 'ground', container, True)
    make('NCK_pallets', 'ground', pallets)
    make('NCK_dumpster', 'ground', dumpster)
    make('NCK_debris', 'ground', debris)
    make('NCK_scaffold', 'wall', scaffold, stack=3.2, repeat=3.0,
         note='deck at z 0 with guard rails; stack every 3.2 m, repeat every 3.0 m along x (shared standards)')
    make('NCK_tool_cart', 'ground', tool_cart)
    make('NCK_crane', 'ground', crane)
    make('NCK_cafe_set', 'ground', cafe_set, note='table at the origin, three chairs round it, parasol through the table')
    make('NCK_kiosk', 'ground', kiosk, note='serving hatch and awning toward -y')
    make('NCK_bike_rack', 'ground', bike_rack, note='four hoops along x, two parked bikes (fronts toward -y)')
    make('NCK_sculpture', 'ground', sculpture, place='plaza')
    # airborne debris for the weather (ASOAmbience tumbles them on the wind; not placed in the city)
    make('NCK_leaf_dry', 'ground', leaf, 'np_leaf_dry', place='air')
    make('NCK_leaf_red', 'ground', leaf, 'np_leaf_red', place='air')
    make('NCK_paper', 'ground', paper, place='air')
    make('NCK_wrapper', 'ground', wrapper, place='air')
    return out
