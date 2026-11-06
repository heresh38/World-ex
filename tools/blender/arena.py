"""Brennick Works: the compact team arena for Shellbreak (src/worlds/arena/). A ruined arms foundry yard on Earth's
outskirts at dusk, mirrored across z = 0 so both squads get the same ground.

Exports (everything already in three.js space: x right, y up; squad A spawns at -z, squad B at +z):
  assets/models/arena_brennick.glb   ARENA (all architecture and props merged per material, world-scale UVs, vertex-colour
                                     contact AO in COLOR_0), ARENA_glass (broken factory glazing + painted signs, alpha),
                                     ARENA_far (backdrop beyond the walls: stacks, sheds, gantry; no collisions)
  assets/models/arena_brennick.json  colliders [minx,miny,minz,maxx,maxy,maxz,tag], nav graph (1 m grid on every walkable
                                     level: walk / drop / mantle edges), cover points, lanes, perches, spawns, light anchors
Layout: three lanes from spawn to spawn.
  west  - the rail cut: two tracks, a box car you can climb into, a flatcar, a hopper, a raised platform (1.2 m ledge)
          under a long canopy (the long sightline) and a shed on the outer alley that the flank route passes through
  mid   - the casting hall: two furnaces, a mezzanine on each side joined by a bridge, four stairs, crate stacks to mantle
          up onto the mezzanine, windows over both lanes; an open apron with barriers and a fuel skid at each end
  east  - the yard and the gatehouse: a two-storey office with an outside stair and balcony, containers (2.4 m, mantle
          onto the roofs), a walk-through container on the outer alley, forklift, pallets and barriers
Materials (names are an API): ar_brick, ar_conc*, ar_floor, ar_ballast, ar_corr_*, ar_steel_*, ar_plate, ar_wood,
ar_hazard, ar_window, ar_signs, ar_lamp (emissive), ar_team_a / ar_team_b (squad strips, recoloured by the game).
Run: blender --background --python tools/blender/arena.py   (textures first: python3 tools/blender/arena_textures.py)
"""
import bpy, bmesh, math, os, sys, json, random
sys.path.insert(0, os.path.dirname(__file__))
import bl

NAME = 'arena_brennick'
TEX = bl.TEXTURES
R = random.Random(4471)
X0, X1, Z0, Z1 = -34.0, 34.0, -52.0, 52.0          # playable floor inside the walls

# ------------------------------------------------------------------ materials
VC = True


def tmat(name, tex, tint='#ffffff', rough=.8, metal=0.0, alpha=None, normal=True, aux=True):
    """Textured material (colour x tint x vertex colour), normal map and aux map (G roughness, B metalness)."""
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    tn = nt.nodes.new('ShaderNodeTexImage')
    tn.image = bpy.data.images.load(os.path.join(TEX, tex + ('.png' if alpha else '_c.jpg')), check_existing=True)
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0; mix.inputs[7].default_value = (*bl.hexrgb(tint), 1)
    nt.links.new(tn.outputs['Color'], mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    if normal and not alpha and os.path.exists(os.path.join(TEX, tex + '_n.jpg')):
        nn = nt.nodes.new('ShaderNodeTexImage'); nn.image = bpy.data.images.load(os.path.join(TEX, tex + '_n.jpg'), check_existing=True)
        nn.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(nn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if aux and not alpha and os.path.exists(os.path.join(TEX, tex + '_m.jpg')):
        an = nt.nodes.new('ShaderNodeTexImage'); an.image = bpy.data.images.load(os.path.join(TEX, tex + '_m.jpg'), check_existing=True)
        an.image.colorspace_settings.name = 'Non-Color'
        sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(an.outputs['Color'], sp.inputs[0])
        nt.links.new(sp.outputs[1], b.inputs['Roughness']); nt.links.new(sp.outputs[2], b.inputs['Metallic'])
    if alpha:
        nt.links.new(tn.outputs['Alpha'], b.inputs['Alpha'])
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    bl._MATS[name] = m
    return m


def materials():
    return dict(
        brick=tmat('ar_brick', 'ar_brick'), brick_dark=tmat('ar_brick_dark', 'ar_brick', '#8a7a70'),
        conc=tmat('ar_conc', 'ar_conc'), conc_dark=tmat('ar_conc_dark', 'ar_conc', '#7a7672'), conc_warm=tmat('ar_conc_warm', 'ar_conc', '#d8c8b0'),
        floor=tmat('ar_floor', 'ar_floor', '#c4b8a8'), floor_in=tmat('ar_floor_hall', 'ar_floor', '#968e84'), ballast=tmat('ar_ballast', 'ar_floor', '#6a5e52', .95),
        corr_red=tmat('ar_corr_red', 'ar_corr', '#9a3a2a'), corr_blue=tmat('ar_corr_blue', 'ar_corr', '#3a5a7a'),
        corr_green=tmat('ar_corr_green', 'ar_corr', '#4a6a4a'), corr_grey=tmat('ar_corr_grey', 'ar_corr', '#8a8c8a'),
        corr_rust=tmat('ar_corr_rust', 'ar_corr', '#7a4a32'), corr_dark=tmat('ar_corr_dark', 'ar_corr', '#4a4a4c'),
        corr_tan=tmat('ar_corr_tan', 'ar_corr', '#b09a72'),
        steel_green=tmat('ar_steel_green', 'ar_steel', '#5a6a5a'), steel_grey=tmat('ar_steel_grey', 'ar_steel', '#6a6e72'),
        steel_rust=tmat('ar_steel_rust', 'ar_steel', '#8a5a3e'), steel_yellow=tmat('ar_steel_yellow', 'ar_steel', '#d8a62a'),
        steel_dark=tmat('ar_steel_dark', 'ar_steel', '#3a3c40'),
        plate=tmat('ar_plate', 'ar_plate'), wood=tmat('ar_wood', 'ar_wood'), wood_dark=tmat('ar_wood_dark', 'ar_wood', '#7a6a5a'),
        hazard=tmat('ar_hazard', 'ar_hazard'),
        window=tmat('ar_window', 'ar_window', alpha=True, rough=.25), signs=tmat('ar_signs', 'ar_signs', alpha=True, rough=.9),
        rubber=bl.mat('ar_rubber', '#161616', 0, .9), sand=bl.mat('ar_sandbag', '#8a7a5a', 0, .95),
        lamp=bl.mat('ar_lamp', '#ffd9a0', 0, .4, emit='#ffc98a', strength=8),
        team_a=bl.mat('ar_team_a', '#ffffff', 0, .4, emit='#ffffff', strength=6),
        team_b=bl.mat('ar_team_b', '#ffffff', 0, .4, emit='#ffffff', strength=6),
        far=bl.mat('ar_far', '#2a2a2e', 0, .9), far_lit=bl.mat('ar_far_lit', '#ffcf8a', 0, .5, emit='#ffb860', strength=4),
        far_cool=bl.mat('ar_far_cool', '#cfe0ff', 0, .5, emit='#bcd4ff', strength=3), far_glass=bl.mat('ar_far_glass', '#1c232c', .6, .22),
        warn=bl.mat('ar_warn', '#ff3020', 0, .4, emit='#ff2a18', strength=9), far_ground=tmat('ar_far_ground', 'ar_floor', '#6e6458', .95),
        tower=tmat('ar_tower', 'ar_conc', '#8a8e98'), tower_dark=tmat('ar_tower_dark', 'ar_conc', '#4a4e58'),
    )


TILE = {'ar_brick': 2, 'ar_brick_dark': 2, 'ar_conc': 4, 'ar_conc_dark': 4, 'ar_conc_warm': 4, 'ar_floor': 8, 'ar_floor_hall': 8,
        'ar_ballast': 3, 'ar_plate': 1, 'ar_wood': 1, 'ar_wood_dark': 1, 'ar_hazard': 1}


def tile_of(m):
    n = m.name
    if n in TILE:
        return TILE[n]
    if n.startswith('ar_corr'):
        return 2
    if n.startswith('ar_steel'):
        return 1
    return 2


# ------------------------------------------------------------------ mesh builder (three space in, Blender out)
def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class MB:
    def __init__(self):
        self.V, self.F, self.UV, self.C, self.MI = [], [], [], [], []
        self.mats = []

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def poly(self, pts, uvs, m, cols):
        """pts: three-space points in CCW order seen from outside."""
        base = len(self.V)
        for (x, y, z) in pts:
            self.V.append((x, -z, y))
        self.F.append(tuple(range(base, base + len(pts))))
        self.UV.append(list(uvs)); self.C.append(list(cols)); self.MI.append(self.mi(m))

    def quad(self, o, u, v, m, tile, ao=(1, 1, 1, 1), uvfix=None):
        """o + s*u + t*v, s,t in [0,1]; u x v = outward normal. World-scale UVs along the unit u / v directions."""
        P = [o, add(o, u), add(add(o, u), v), add(o, v)]
        uh, vh = unit(u), unit(v)
        if uvfix:
            uvs = uvfix
        else:
            uvs = [(dot(p, uh) / tile, dot(p, vh) / tile) for p in P]
        self.poly(P, uvs, m, ao)

    def box(self, x0, y0, z0, x1, y1, z1, m, tile=None, ao=True, tint=1.0, skip=(), rot=0.0):
        tile = tile or tile_of(m)
        g = y0 < .3 and ao              # standing on the floor: darken the foot of the walls
        h = y1 - y0
        cut = [y0] + [y0 + c for c in (.35, 1.2) if g and c < h - .05] + [y1]

        def aof(y):
            if not ao:
                return tint
            k = .5 + .5 * smooth(0, 1.5, y - y0) if g else .9
            return k * tint
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        ca, sa = math.cos(rot), math.sin(rot)

        def R_(p):
            if not rot:
                return p
            dx, dz = p[0] - cx, p[2] - cz
            return (cx + dx * ca + dz * sa, p[1], cz - dx * sa + dz * ca)
        faces = []
        # sides: (outward normal, origin corner, u vector) with v = up
        sides = [('+x', (x1, 0, z1), (0, 0, z0 - z1)), ('-x', (x0, 0, z0), (0, 0, z1 - z0)),
                 ('+z', (x0, 0, z1), (x1 - x0, 0, 0)), ('-z', (x1, 0, z0), (x0 - x1, 0, 0))]
        for nm, o, u in sides:
            if nm in skip:
                continue
            for ya, yb in zip(cut, cut[1:]):
                oo = (o[0], ya, o[2]); v = (0, yb - ya, 0)
                P = [oo, add(oo, u), add(add(oo, u), v), add(oo, v)]
                uh = unit(u)
                uvs = [(dot(p, uh) / tile, p[1] / tile) for p in P]
                P = [R_(p) for p in P]
                self.poly(P, uvs, m, (aof(ya), aof(ya), aof(yb), aof(yb)))
        if '+y' not in skip:
            P = [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)]
            self.poly([R_(p) for p in P], [(p[0] / tile, -p[2] / tile) for p in P], m, (tint,) * 4)
        if '-y' not in skip:
            P = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]
            self.poly([R_(p) for p in P], [(p[0] / tile, p[2] / tile) for p in P], m, (.45 * tint,) * 4)

    def cyl(self, cx, cy, cz, r, L, m, axis='y', seg=14, tile=None, caps=True, ao=1.0):
        """cylinder; axis y: (cx, cz) centre from cy to cy+L; axis x / z: centred at (cx, cy, cz) with length L."""
        tile = tile or tile_of(m)
        circ = 2 * math.pi * r

        def pt(a, t):
            c, s = math.cos(a) * r, math.sin(a) * r
            if axis == 'y':
                return (cx + c, cy + t * L, cz + s)
            if axis == 'x':
                return (cx - L / 2 + t * L, cy + s, cz + c)
            return (cx + c, cy + s, cz + L / 2 - t * L)
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            P = [pt(a1, 0), pt(a0, 0), pt(a0, 1), pt(a1, 1)]
            u0, u1 = circ * (1 - (i + 1) / seg) / tile, circ * (1 - i / seg) / tile
            uvs = [(u0, 0), (u1, 0), (u1, L / tile), (u0, L / tile)]
            cols = (ao * .6, ao * .6, ao, ao) if (axis == 'y' and cy < .3) else (ao,) * 4
            self.poly(P, uvs, m, cols)
        if caps:
            for t in (0, 1):
                ring = [pt(2 * math.pi * i / seg, t) for i in range(seg)]
                if t == 1:
                    ring = ring[::-1]
                uvs = [((p[0] + p[2]) / tile, (p[1] + p[2]) / tile) for p in ring]
                self.poly(ring, uvs, m, (ao,) * seg)

    def beam(self, p0, p1, w, m, d=None, tile=None):
        """box of cross-section w x d along p0 -> p1 (truss members, cables, conveyors, pipes)"""
        tile = tile or tile_of(m); d = d or w
        ax = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]); L = math.sqrt(dot(ax, ax)) or 1e-6
        a = (ax[0] / L, ax[1] / L, ax[2] / L)
        up = (0, 1, 0) if abs(a[1]) < .95 else (1, 0, 0)
        sv = unit(cross(a, up)); uv = cross(sv, a)
        S = lambda k, v: (v[0] * k, v[1] * k, v[2] * k)
        A, Su, Uu = S(L, a), S(w, sv), S(d, uv)
        hs, hu = S(w / 2, sv), S(d / 2, uv)
        neg = lambda v: (-v[0], -v[1], -v[2])
        b = add(add(p0, neg(hs)), neg(hu))           # p0 corner (-s, -u)
        self.quad(add(b, Su), A, Uu, m, tile)                 # +s: (a, u)
        self.quad(b, Uu, A, m, tile)                           # -s: (u, a)
        self.quad(add(b, Uu), Su, A, m, tile)                  # +u: (s, a)
        self.quad(b, A, Su, m, tile)                           # -u: (a, s)
        self.quad(add(b, A), Uu, Su, m, tile)                  # end at p1: (u, s)
        self.quad(b, Su, Uu, m, tile)                          # end at p0: (s, u)

    def tcyl(self, cx, cy, cz, r0, r1, h, m, seg=16, tile=None, cap=True):
        """vertical tapered cylinder (cone when r1 = 0)"""
        tile = tile or tile_of(m)
        pt = lambda a, r, y: (cx + math.cos(a) * r, y, cz + math.sin(a) * r)
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            P = [pt(a1, r0, cy), pt(a0, r0, cy), pt(a0, r1, cy + h), pt(a1, r1, cy + h)]
            u0, u1 = 2 * math.pi * r0 * (1 - (i + 1) / seg) / tile, 2 * math.pi * r0 * (1 - i / seg) / tile
            self.poly(P, [(u0, 0), (u1, 0), (u1, h / tile), (u0, h / tile)], m, (1, 1, 1, 1))
        if cap and r1 > 0:
            ring = [pt(2 * math.pi * i / seg, r1, cy + h) for i in range(seg)][::-1]
            self.poly(ring, [(p[0] / tile, p[2] / tile) for p in ring], m, (1,) * seg)

    def build(self, name, shade_flat=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.V, [], self.F)
        me.update()
        uvl = me.uv_layers.new(name='UVMap')
        col = me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
        li = 0
        for pi, poly in enumerate(me.polygons):
            poly.material_index = self.MI[pi]
            for k, l in enumerate(poly.loop_indices):
                uvl.data[l].uv = self.UV[pi][k]
                c = max(0.0, min(1.0, self.C[pi][k]))
                col.data[l].color = (c, c, c, 1)
        me.color_attributes.active_color = col
        for m in self.mats:
            me.materials.append(m)
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        # merge coincident vertices of the same face set only where UVs agree would be costly; keep flat quads
        return o


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def unit(a):
    l = math.sqrt(dot(a, a)) or 1
    return (a[0] / l, a[1] / l, a[2] / l)


# ------------------------------------------------------------------ the layout (authored for the south half, mirrored)
PARTS = []      # dict(kind, args, m, col, tag, ...)
SIGNS = []      # (cell, centre, normal, w, h, mirror_cell)
LIGHTS = []     # dict(pos, color, intensity, dist) point lights (mirrored)
M = None


def P(x0, y0, z0, x1, y1, z1, m, col=True, tag='wall', ao=True, tint=None, skip=(), rot=0.0, mirror=True, walk=True):
    if x0 > x1:
        x0, x1 = x1, x0
    if z0 > z1:
        z0, z1 = z1, z0
    t = tint if tint is not None else 1 + R.uniform(-.06, .05)
    PARTS.append(dict(k='box', a=(x0, y0, z0, x1, y1, z1), m=m, col=col, tag=tag, ao=ao, tint=t, skip=skip, rot=rot, mirror=mirror))


def CY(cx, cy, cz, r, L, m, axis='y', col=None, tag='prop', seg=14, mirror=True):
    """cylinder part; col: True -> AABB collider of the cylinder"""
    PARTS.append(dict(k='cyl', a=(cx, cy, cz, r, L, axis, seg), m=m, col=col, tag=tag, mirror=mirror))


def wall(axis, f0, f1, a0, a1, y0, h, opens, m, tag='wall', frame=None, glaze=True, mirror=True):
    """A straight wall with rectangular openings. axis 'x': runs along x (fixed z f0..f1), 'z': runs along z (fixed x).
    opens: [(a_start, a_end, y_start, y_end, kind)] kind 'w' window (glazed + frame) | 'd' door / hole."""
    cuts = sorted(set([a0, a1] + [max(a0, min(a1, o[i])) for o in opens for i in (0, 1)]))
    for sa, sb in zip(cuts, cuts[1:]):
        if sb - sa < 1e-4:
            continue
        mid = (sa + sb) / 2
        holes = sorted([(o[2], o[3]) for o in opens if o[0] <= mid <= o[1]])
        ys = y0
        for ha, hb in holes + [(y0 + h, y0 + h)]:
            if ha - ys > 1e-4:
                if axis == 'x':
                    P(sa, ys, f0, sb, ha, f1, m, tag=tag, mirror=mirror)
                else:
                    P(f0, ys, sa, f1, ha, sb, m, tag=tag, mirror=mirror)
            ys = max(ys, hb)
    fm = frame or M['steel_dark']
    for (oa, ob, ya, yb, kind) in opens:
        t = .06
        if kind == 'w':
            # steel frame + sill, broken glazing in the middle of the wall
            if axis == 'x':
                P(oa, ya - .08, f0 - .05, ob, ya, f1 + .05, M['conc_dark'], col=False, mirror=mirror)
                if glaze:
                    GLAZE.append(('x', (oa, ob), (ya, yb), (f0 + f1) / 2, mirror))
            else:
                P(f0 - .05, ya - .08, oa, f1 + .05, ya, ob, M['conc_dark'], col=False, mirror=mirror)
                if glaze:
                    GLAZE.append(('z', (oa, ob), (ya, yb), (f0 + f1) / 2, mirror))
        elif kind == 'd':
            # door jambs: thin steel reveals
            if axis == 'x':
                P(oa - t, ya, f0 - .03, oa, yb, f1 + .03, fm, col=False, mirror=mirror)
                P(ob, ya, f0 - .03, ob + t, yb, f1 + .03, fm, col=False, mirror=mirror)
            else:
                P(f0 - .03, ya, oa - t, f1 + .03, yb, oa, fm, col=False, mirror=mirror)
                P(f0 - .03, ya, ob, f1 + .03, yb, ob + t, fm, col=False, mirror=mirror)


GLAZE = []      # ('x'|'z', (a0,a1), (y0,y1), fixed, mirror)


def stairs(xa, xb, za, zb, y0, y1, n, m, rise_along='+z', tag='stairs'):
    """n solid steps from y0 to y1 between za..zb rising toward rise_along ('+z' / '-z' / '+x' / '-x')."""
    for i in range(n):
        top = y0 + (y1 - y0) * (i + 1) / n
        if rise_along in ('+z', '-z'):
            L = zb - za
            s = za + L * i / n if rise_along == '+z' else za
            e = zb if rise_along == '+z' else zb - L * i / n
            P(xa, y0, s, xb, top, e, m, tag=tag, tint=1.0)
        else:
            L = xb - xa
            s = xa + L * i / n if rise_along == '+x' else xa
            e = xb if rise_along == '+x' else xb - L * i / n
            P(s, y0, za, e, top, zb, m, tag=tag, tint=1.0)


def crate(x, z, w, d, h, y=0.0, m=None, rot=0.0, col=True, tag='cover'):
    m = m or M['wood']
    P(x - w / 2, y, z - d / 2, x + w / 2, y + h, z + d / 2, m, col=col, tag=tag, rot=rot)


def container(x0, z0, along, color, y=0.0, doors_open=False, h=2.4):
    """6.06 x 2.44 x 2.4 box container; along 'x' or 'z'. doors_open: hollow walk-through (both ends open)."""
    L, W = 6.06, 2.44
    if along == 'x':
        x1, z1 = x0 + L, z0 + W
    else:
        x1, z1 = x0 + W, z0 + L
    m = M[color]
    if not doors_open:
        P(x0, y, z0, x1, y + h, z1, m, tag='container')
    else:
        t = .08
        P(x0, y, z0, x1, y + .1, z1, M['plate'], tag='container')                 # floor
        P(x0, y + h - .1, z0, x1, y + h, z1, m, tag='container')                  # roof
        if along == 'z':
            P(x0, y + .1, z0, x0 + t, y + h - .1, z1, m, tag='container')
            P(x1 - t, y + .1, z0, x1, y + h - .1, z1, m, tag='container')
            # doors swung open against the outside walls
            P(x0 - .06, y + .1, z0 - 1.2, x0, y + h - .15, z0, m, col=False)
            P(x1, y + .1, z0 - 1.2, x1 + .06, y + h - .15, z0, m, col=False)
        else:
            P(x0, y + .1, z0, x1, y + h - .1, z0 + t, m, tag='container')
            P(x0, y + .1, z1 - t, x1, y + h - .1, z1, m, tag='container')
    # corner castings + rail along the top (visual)
    for cx in (x0, x1 - .18):
        for cz in (z0, z1 - .18):
            P(cx, y, cz, cx + .18, y + .16, cz + .18, M['steel_dark'], col=False, ao=False)
            P(cx, y + h - .16, cz, cx + .18, y + h + .01, cz + .18, M['steel_dark'], col=False, ao=False)


def barrier(x0, z0, x1, z1, h=1.05):
    """concrete jersey barrier segment (footing + tapered top as two boxes)"""
    if x1 - x0 > z1 - z0:
        P(x0, 0, z0, x1, h * .45, z1, M['conc_warm'], tag='cover')
        P(x0, h * .45, z0 + .12, x1, h, z1 - .12, M['conc_warm'], tag='cover')
        P(x0, .62, z0 - .01, x1, .72, z1 + .01, M['hazard'], col=False)
    else:
        P(x0, 0, z0, x1, h * .45, z1, M['conc_warm'], tag='cover')
        P(x0 + .12, h * .45, z0, x1 - .12, h, z1, M['conc_warm'], tag='cover')
        P(x0 - .01, .62, z0, x1 + .01, .72, z1, M['hazard'], col=False)


def sandbags(x0, z0, x1, z1, h=1.0):
    P(x0, 0, z0, x1, h, z1, M['sand'], tag='cover')
    n = max(1, int(round(max(x1 - x0, z1 - z0) / .6)))
    for i in range(int(h / .2)):          # bag courses (visual bulges)
        y = i * .2
        if x1 - x0 > z1 - z0:
            P(x0 - .03, y + .04, z0 - .04, x1 + .03, y + .16, z1 + .04, M['sand'], col=False, tint=.92 + .08 * (i % 2))
        else:
            P(x0 - .04, y + .04, z0 - .03, x1 + .04, y + .16, z1 + .03, M['sand'], col=False, tint=.92 + .08 * (i % 2))


def barrel(x, z, color='steel_rust', y=0.0, tipped=False):
    if tipped:
        CY(x, y + .3, z, .3, .9, M[color], axis='x', col=True, tag='cover', seg=12)
    else:
        CY(x, y, z, .3, .9, M[color], col=True, tag='cover', seg=12)
        CY(x, y + .89, z, .26, .03, M['steel_dark'], seg=12, col=False)


def lamp_post(x, z, h=6.5, arm=1.2, face=1):
    P(x - .1, 0, z - .1, x + .1, h, z + .1, M['steel_grey'], tag='prop')
    P(x - .08, h - .1, z - .08, x + .08 + arm * max(face, 0), h, z + .08 - arm * min(face, 0), M['steel_grey'], col=False)
    lx = x + arm * face * .9 if face else x
    P(lx - .25, h - .26, z - .15, lx + .25, h - .1, z + .15, M['steel_dark'], col=False)
    P(lx - .2, h - .3, z - .11, lx + .2, h - .26, z + .11, M['lamp'], col=False, ao=False)


def sign(cell, centre, normal, w, h, mcell=None):
    SIGNS.append((cell, centre, normal, w, h, mcell if mcell is not None else cell))


# ------------------------------------------------------------------ the map
def layout():
    m = M
    # ---------------- perimeter: brick walls 9 m, pilasters, coping (full length: symmetric)
    P(X0 - .8, 0, Z0 - .8, X0, 9, Z1 + .8, m['brick'], mirror=False)
    P(X1, 0, Z0 - .8, X1 + .8, 9, Z1 + .8, m['brick'], mirror=False)
    P(X0 - .8, 0, Z0 - .8, X1 + .8, 9.6, Z0, m['brick_dark'])                  # back wall of the south yard (warehouse)
    for z in range(-48, 49, 8):
        if z < 0:
            P(X0, 0, z - .4, X0 + .35, 9.2, z + .4, m['brick_dark'], tag='wall')
            P(X1 - .35, 0, z - .4, X1, 9.2, z + .4, m['brick_dark'], tag='wall')
        elif z == 0:
            P(X0, 0, -.4, X0 + .35, 9.2, .4, m['brick_dark'], mirror=False)
            P(X1 - .35, 0, -.4, X1, 9.2, .4, m['brick_dark'], mirror=False)
    P(X0 - .9, 9, Z0 - .9, X0 + .1, 9.3, Z1 + .9, m['conc_dark'], col=False, mirror=False)
    P(X1 - .1, 9, Z0 - .9, X1 + .9, 9.3, Z1 + .9, m['conc_dark'], col=False, mirror=False)
    P(X0 - .9, 9.6, Z0 - .9, X1 + .9, 9.9, Z0 + .1, m['conc_dark'], col=False)
    # warehouse face: three rolling doors (shut) and a concrete band
    for xa in (-20, -4, 12):
        P(xa, 0, Z0, xa + 8, 5.6, Z0 + .12, m['corr_grey'], col=False, ao=True)
        P(xa - .3, 5.6, Z0, xa + 8.3, 6.1, Z0 + .25, m['steel_dark'], col=False)
        P(xa - .3, 0, Z0, xa, 5.6, Z0 + .2, m['steel_dark'], col=False)
        P(xa + 8, 0, Z0, xa + 8.3, 5.6, Z0 + .2, m['steel_dark'], col=False)
    P(X0, 6.5, Z0, X1, 7.1, Z0 + .15, m['conc'], col=False)
    sign(0, (0, 7.9, Z0 + .02), (0, 0, 1), 10, 2.5)                            # BRENNICK WORKS
    sign(5, (-26, 4.4, Z0 + .02), (0, 0, 1), 5, 1.25, 4)                         # YARD SOUTH / YARD NORTH
    for x in (-24, -8, 8, 24):
        P(x - .3, 6.0, Z0 + .1, x + .3, 6.3, Z0 + .5, m['steel_dark'], col=False)
        P(x - .25, 5.94, Z0 + .15, x + .25, 6.0, Z0 + .45, m['lamp'], col=False, ao=False)

    # ---------------- spawn A: loading dock, canopy with the squad light strip, truck, pallets, barriers
    P(-10, 0, Z0, 10, 1.2, -47.5, m['conc'], tag='dock')
    P(-10, 1.0, -47.6, 10, 1.2, -47.4, m['hazard'], col=False)
    for x in (-8, -4, 0, 4, 8):
        P(x - .3, .25, -47.65, x + .3, .85, -47.45, m['rubber'], col=False)
    stairs(-12.4, -10, -51.6, -47.5, 0, 1.2, 5, m['conc'], rise_along='+x')
    stairs(10, 12.4, -51.6, -47.5, 0, 1.2, 5, m['conc'], rise_along='-x')
    P(-11.2, 5.6, Z0, 11.2, 5.9, -45.3, m['corr_dark'], tag='roof')
    P(-11.2, 5.25, -45.5, 11.2, 5.6, -45.3, m['steel_dark'], col=False)
    P(-11.2, 5.28, -45.32, 11.2, 5.42, -45.26, m['team_a'], col=False, ao=False)
    for x in (-10.6, -3.6, 3.6, 10.6):
        P(x - .18, 0, -45.9, x + .18, 5.6, -45.55, m['steel_yellow'], tag='post')
    for x in (-6, 0, 6):
        P(x - .4, 5.42, -49, x + .4, 5.6, -48.6, m['steel_dark'], col=False)
        P(x - .35, 5.38, -48.95, x + .35, 5.42, -48.65, m['lamp'], col=False, ao=False)
    LIGHTS.append(dict(pos=(0, 4.8, -48.5), color='#ffd2a0', intensity=14, dist=18, team='a'))
    # box truck (west of the dock)
    P(-27.6, .55, -49.2, -24.9, 4.0, -38.2, m['corr_tan'], tag='truck')
    P(-27.4, 0, -48.8, -25.1, .55, -38.6, m['steel_dark'], tag='truck')
    P(-27.5, .5, -37.9, -25.0, 3.0, -35.4, m['steel_rust'], tag='truck')
    P(-27.45, 1.9, -35.45, -25.05, 2.8, -35.3, m['steel_dark'], col=False)
    for zz in (-47.4, -45.9, -40.0, -36.4):
        for xx in (-27.65, -24.85):
            CY(xx, .5, zz, .5, .34, m['rubber'], axis='x', seg=12, col=False)
    # pallets and drums east of the dock
    for i, (x, z) in enumerate([(23.5, -48.5), (25.2, -48.5), (23.5, -47.0)]):
        crate(x, z, 1.4, 1.2, 1.5 if i != 2 else 2.2)
    barrel(27.5, -49.8); barrel(28.2, -49.3, 'steel_green'); barrel(27.7, -48.5)
    P(29, 0, -51.8, 33.6, 3.2, -48.6, m['corr_green'], tag='shed')               # generator housing
    P(29.2, 3.2, -51.6, 33.4, 3.5, -48.8, m['steel_dark'], col=False)
    # barriers: the spawn's waist-high screen with five exits
    for (xa, xb) in ((-30, -26), (-13, -9), (9, 13), (26, 30)):
        barrier(xa, -37.6, xb, -36.9)
    barrier(-5, -41.2, -1, -40.5); barrier(1, -42.8, 5, -42.1)

    # ---------------- west lane: the rail cut
    for tx in (-28.5, -23.5):
        P(tx - 1.6, 0, Z0 + 2, tx + 1.6, .1, -.0001, m['ballast'], col=False, ao=False, tint=1.0)
        for rx in (tx - .72, tx + .72):
            P(rx - .04, .1, Z0 + 2, rx + .04, .24, -.0001, m['steel_dark'], col=False, ao=False, tint=1.0)
        for zz in [Z0 + 2.4 + .75 * i for i in range(int((-Z0 - 2.6) / .75))]:
            P(tx - 1.2, .06, zz - .11, tx + 1.2, .16, zz + .11, m['wood_dark'], col=False, ao=False)
    # box car W1 on the outer track: climb in through the open doors (floor at 1.05)
    x0, x1, za, zb = -30.1, -26.9, -23.0, -9.0
    P(x0 + .2, 0, za + .4, x1 - .2, 1.05, zb - .4, m['steel_dark'], tag='wagon')      # underframe (solid)
    P(x0, .9, za, x1, 1.05, zb, m['plate'], tag='wagon')                              # floor
    wall('z', x0, x0 + .1, za, zb, 1.05, 2.55, [(-17, -15, 1.05, 3.4, 'd')], m['corr_rust'], tag='wagon')
    wall('z', x1 - .1, x1, za, zb, 1.05, 2.55, [(-17, -15, 1.05, 3.4, 'd')], m['corr_rust'], tag='wagon')
    P(x0, 1.05, za, x1, 3.6, za + .1, m['corr_rust'], tag='wagon')
    P(x0, 1.05, zb - .1, x1, 3.6, zb, m['corr_rust'], tag='wagon')
    P(x0 - .1, 3.6, za - .1, x1 + .1, 3.78, zb + .1, m['steel_rust'], tag='wagon')
    P(x0 - .16, 1.05, -15.0, x0, 3.45, -13.0, m['corr_rust'], tag='wagon')            # door slid open
    P(x1, 1.05, -19.0, x1 + .16, 3.45, -17.0, m['corr_rust'], tag='wagon')
    for zz in (za + 1.6, za + 3.0, zb - 3.0, zb - 1.6):
        for xx in (-29.22, -27.78):
            CY(xx, .45, zz, .45, .14, m['steel_dark'], axis='x', seg=12, col=False)
    crate(-29.2, -21.4, 1.2, 1.1, 1.0, y=1.05); crate(-27.9, -10.4, 1.0, 1.0, .8, y=1.05)
    # signal relay cabinets between the tracks (break the line along the gap)
    P(-26.6, 0, -14.0, -25.4, 2.1, -12.6, m['steel_grey'], tag='cover')
    P(-26.7, 2.1, -14.1, -25.3, 2.2, -12.5, m['steel_dark'], col=False)
    # flatcar W2 (centre, symmetric) with crates on the deck
    P(-25.1, 0, -6.0, -21.9, 1.25, 6.0, m['steel_rust'], tag='wagon', mirror=False)
    P(-25.15, 1.1, -6.05, -21.85, 1.3, 6.05, m['wood_dark'], col=False, mirror=False)
    crate(-24.0, -3.4, 1.5, 1.6, 1.2, y=1.3); crate(-22.7, -1.0, 1.0, 1.0, .9, y=1.3, rot=.2)
    # hopper wagon on the inner track, near the spawn (blocks the long line of the inner track)
    P(-25.1, 0, -34.0, -21.9, 1.0, -25.0, m['steel_dark'], tag='wagon')
    P(-25.2, 1.0, -34.0, -21.8, 3.8, -25.0, m['steel_green'], tag='wagon')
    for zz in (-33.0, -30.5, -28.5, -26.0):
        P(-25.3, 1.0, zz - .1, -21.7, 3.85, zz + .1, m['steel_dark'], col=False)
    for zz in (-32.8, -31.4, -27.6, -26.2):
        for xx in (-24.22, -22.78):
            CY(xx, .45, zz, .45, .14, m['steel_dark'], axis='x', seg=12, col=False)
    # sleeper stacks (head-high) between the inner track and the platform
    P(-21.4, 0, -22.2, -18.6, 2.0, -20.0, m['wood_dark'], tag='cover')
    P(-21.2, 0, -40.0, -19.4, 1.1, -38.8, m['wood_dark'], tag='cover')
    # the outer alley's shed: walk through it (doors offset, partition inside)
    sx0, sx1, sz0, sz1 = X0, -30.4, -30.0, -25.0
    wall('x', sz0, sz0 + .2, sx0, sx1, 0, 3.0, [(-32.3, -30.7, 0, 2.4, 'd')], m['corr_grey'], tag='shed')
    wall('x', sz1 - .2, sz1, sx0, sx1, 0, 3.0, [(-34.0, -32.4, 0, 2.4, 'd')], m['corr_grey'], tag='shed')
    wall('z', sx1 - .2, sx1, sz0, sz1, 0, 3.0, [(-28.4, -26.6, 1.2, 2.2, 'w')], m['corr_grey'], tag='shed')
    P(-32.0, 0, -27.7, sx1 - .2, 3.0, -27.5, m['corr_grey'], tag='shed')
    P(sx0, 3.0, sz0 - .3, sx1 + .3, 3.2, sz1 + .3, m['corr_dark'], tag='roof')
    crate(-33.4, -29.4, .9, .9, 1.0); barrel(-31.0, -25.8)
    LIGHTS.append(dict(pos=(-32.2, 2.6, -27.5), color='#ffc98a', intensity=3, dist=6))
    # raised platform under its canopy (1.2 m: mantle up from the tracks), steps down at the far end
    P(-17.5, 0, -30.0, -13.5, 1.2, 30.0, m['conc'], tag='platform', mirror=False)
    P(-17.55, 1.0, -30.0, -17.45, 1.2, 30.0, m['conc_dark'], col=False, mirror=False)
    P(-17.5, 1.2, -30.0, -17.0, 1.205, 30.0, m['hazard'], col=False, mirror=False)
    stairs(-17.5, -13.5, -33.0, -30.0, 0, 1.2, 5, m['conc'], rise_along='+z')
    for z in (-27.0, -21.0, -15.0, -9.0, -3.0):
        P(-15.7, 1.2, z - .15, -15.3, 4.6, z + .15, m['steel_green'], tag='post')
        P(-18.1, 4.3, z - .1, -12.9, 4.6, z + .1, m['steel_green'], col=False)
    P(-18.2, 4.6, -30.0, -12.8, 4.8, 30.0, m['corr_dark'], tag='roof', mirror=False)
    for z in (-24.0, -12.0, 0.0):
        if z < 0:
            P(-15.8, 4.4, z - .3, -15.2, 4.6, z + .3, m['steel_dark'], col=False)
            P(-15.75, 4.37, z - .25, -15.25, 4.4, z + .25, m['lamp'], col=False, ao=False)
    sign(7, (-17.56, 3.0, -18.0), (-1, 0, 0), 4.0, 1.0)                       # RAIL SPUR 7
    # signal hut on the platform (centre, symmetric) and platform cover
    P(-17.3, 1.2, -2.5, -15.0, 4.0, 2.5, m['brick'], tag='hut', mirror=False)
    P(-17.45, 4.0, -2.7, -14.85, 4.25, 2.7, m['conc_dark'], col=False, mirror=False)
    crate(-16.2, -24.0, 1.1, 1.1, 1.0, y=1.2); crate(-15.0, -23.7, .9, .9, .8, y=1.2, rot=.3)
    sandbags(-17.2, -11.2, -15.6, -10.4, 1.0)
    sandbags(-14.6, -6.6, -13.6, -5.0, 1.0)
    barrel(-14.0, -19.0, 'steel_green', y=1.2)
    # service passage between the platform and the hall: barrels, pipes on the hall wall
    barrel(-12.6, -6.4); barrel(-12.4, -13.8, 'steel_grey')

    # ---------------- mid: the casting hall
    hx0, hx1, hz = -11.25, 11.25, -16.25
    up = 4.0
    # side walls (full length, symmetric), openings: side door, ground windows, mezzanine windows
    for xa, xb in ((hx0, hx0 + .5), (hx1 - .5, hx1)):
        opens = [(-12.6, -10.6, 0, 2.6, 'd'), (10.6, 12.6, 0, 2.6, 'd'),
                 (-8.0, -5.6, 1.1, 2.6, 'w'), (5.6, 8.0, 1.1, 2.6, 'w'), (-1.25, 1.25, 1.1, 2.6, 'w'),
                 (-14.6, -12.0, up + .9, up + 2.8, 'w'), (-9.4, -6.4, up + .9, up + 2.8, 'w'), (-4.4, -1.6, up + .9, up + 2.8, 'w'),
                 (1.6, 4.4, up + .9, up + 2.8, 'w'), (6.4, 9.4, up + .9, up + 2.8, 'w'), (12.0, 14.6, up + .9, up + 2.8, 'w')]
        wall('z', xa, xb, hz, -hz, 0, 10, opens, m['brick'], tag='hall', mirror=False)
    # end wall (south; mirrored to north): the big door, two personnel doors, high windows
    wall('x', hz, hz + .5, hx0, hx1, 0, 10, [(-3.0, 3.0, 0, 5.0, 'd'), (-9.6, -8.0, 0, 2.6, 'd'), (8.0, 9.6, 0, 2.6, 'd'),
                                             (-8.0, -5.0, 5.4, 7.4, 'w'), (5.0, 8.0, 5.4, 7.4, 'w')], m['brick'], tag='hall')
    P(-3.2, 5.0, hz - .45, 3.2, 5.8, hz - .05, m['corr_grey'], col=False)            # rolled-up door
    P(-3.3, 4.95, hz - .5, 3.3, 5.05, hz, m['steel_dark'], col=False)
    sign(10, (0, 6.6, hz - .02), (0, 0, -1), 5.0, 1.25)                            # CASTING HALL
    sign(6, (-8.8, 3.0, hz - .02), (0, 0, -1), 2.2, .55)                           # KEEP CLEAR
    sign(1, (5.0, 8.4, hz - .02), (0, 0, -1), 2.4, 2.4, 2)                         # BAY 3 / BAY 4
    P(hx0 - .2, 10.0, hz - .2, hx1 + .2, 10.3, hz + 4.2, m['corr_dark'], tag='roof')
    for (za, zb) in ((hz + 4.2, -10.0), (-6.5, -.0001)):
        P(hx0 - .2, 10.0, za, -6.0, 10.3, zb, m['corr_dark'], tag='roof')
        P(6.0, 10.0, za, hx1 + .2, 10.3, zb, m['corr_dark'], tag='roof')
        P(-2.0, 10.0, za, 2.0, 10.3, zb, m['corr_dark'], tag='roof')
    P(hx0 - .2, 10.0, -10.0, hx1 + .2, 10.3, -6.5, m['corr_dark'], tag='roof')
    P(hx0 - .3, 9.9, hz - .3, hx1 + .3, 10.0, -hz + .3, m['steel_dark'], col=False, mirror=False)   # eaves trim
    for z in (-14.0, -10.0, -6.0, -2.0):                                           # roof trusses
        P(hx0 + .5, 8.9, z - .12, hx1 - .5, 9.4, z + .12, m['steel_green'], col=False)
        for x in (-6.0, 0.0, 6.0):
            P(x - .08, 9.4, z - .08, x + .08, 9.95, z + .08, m['steel_green'], col=False)
    for x in (-9.0, 9.0):                                                          # crane runway beams
        P(x - .2, 7.4, hz + .5, x + .2, 7.9, -hz - .5, m['steel_yellow'], col=False, mirror=False)
    P(-9.2, 7.9, -5.6, 9.2, 8.5, -4.4, m['steel_yellow'], col=False)               # gantry crane bridge
    P(1.4, 7.0, -5.4, 2.6, 7.9, -4.6, m['steel_dark'], col=False)
    CY(2.0, 5.2, -5.0, .05, 1.8, m['steel_dark'], col=False)
    P(1.6, 4.7, -5.3, 2.4, 5.2, -4.7, m['steel_yellow'], col=False)
    # hall floor (inside the walls)
    P(hx0 + .5, 0, hz + .5, hx1 - .5, .02, -.0001, m['floor_in'], col=False, ao=False, tint=1.0)
    # mezzanines: slab, edge girder (the mantle ledge), columns, railing with gaps (bridge + crate climbs)
    for s in (-1, 1):
        xa, xb = (hx0 + .5, -7.0) if s < 0 else (7.0, hx1 - .5)
        P(xa, up - .2, -8.0, xb, up, 8.0, m['plate'], tag='mezz', mirror=False)
        ex = -7.0 if s < 0 else 7.0
        P(min(ex, ex + .3 * s), up - .8, -8.0, max(ex, ex + .3 * s), up, 8.0, m['steel_green'], tag='mezz', mirror=False)
        for z in (-7.8, -3.0):
            P(ex + .15 * s - .15, 0, z - .15, ex + .15 * s + .15, up - .8, z + .15, m['steel_green'], tag='post')
        rail_x = ex + (-.04 if s < 0 else .04)
        for (za, zb) in ((-8.0, -5.7), (-4.3, -1.5)):
            P(rail_x - .04, up, za, rail_x + .04, up + 1.0, zb, m['steel_yellow'], tag='rail')
            P(rail_x - .03, up + .45, za, rail_x + .03, up + .5, zb, m['steel_yellow'], col=False)
        # stairs at both ends, along the outer wall (a landing between the stair foot and the end wall)
        sxa, sxb = (hx0 + .5, hx0 + 2.5) if s < 0 else (hx1 - 2.5, hx1 - .5)
        stairs(sxa, sxb, -14.4, -8.0, 0, up, 16, m['plate'], rise_along='+z')
        rx = sxb + .04 if s < 0 else sxa - .04
        for k in range(4):
            za, zb = -13.6 + k * 1.4, -13.6 + (k + 1) * 1.4
            P(rx - .04, up * (k + 2) / 6 - .2, za, rx + .04, up * (k + 3) / 6 + 1.0, zb, m['steel_yellow'], tag='rail')
        # end railing at z = -8 across the mezzanine edge beside the stair
        P(sxb if s < 0 else xa, up, -8.04, xb if s < 0 else sxa, up + 1.0, -7.96, m['steel_yellow'], tag='rail')
        # crate stack to mantle onto the mezzanine (lower crate + upper crate = 2.2 m), a step crate beside it
        cx = ex + (.65 if s < 0 else -.65)
        crate(cx, -5.0, 1.1, 1.2, 1.2); crate(cx, -5.0, 1.0, 1.1, 1.0, y=1.2, rot=.05)
        crate(cx + (1.0 if s < 0 else -1.0), -5.1, .9, 1.0, 1.0, rot=.1)
        # machine cabinets under the mezzanine
        P(xa + .1, 0, -7.0, xa + .9, 2.0, -4.2, m['steel_grey'], tag='cover')
        P(xa + .1, 0, -1.2, xa + 1.4, 1.1, -.0001, m['steel_dark'], tag='cover')
    # bridge between the mezzanines (centre): slab, edge girders, railings
    P(-7.0, up - .2, -1.5, 7.0, up, 1.5, m['plate'], tag='mezz', mirror=False)
    for zz in (-1.5, 1.5):
        P(-7.0, up - .6, zz - .15, 7.0, up - .2, zz + .15, m['steel_green'], col=True, tag='mezz', mirror=False)
        P(-7.0, up, zz - .04, 7.0, up + 1.0, zz + .04, m['steel_yellow'], tag='rail', mirror=False)
    # furnaces (full cover), chimneys to the roof
    P(-3.0, 0, -9.0, 3.0, 3.2, -4.4, m['brick_dark'], tag='furnace')
    P(-3.2, 3.2, -9.2, 3.2, 3.5, -4.2, m['steel_dark'], col=False)
    P(-1.4, .4, -4.42, 1.4, 1.6, -4.38, m['lamp'], col=False, ao=False)              # glowing furnace mouth
    CY(0, 3.5, -6.7, .8, 6.6, m['steel_rust'], col=False, seg=16)
    sign(3, (0, 2.4, -9.02), (0, 0, -1), 3.6, .9)                                  # NO. 2 FURNACE
    LIGHTS.append(dict(pos=(0, 1.2, -3.6), color='#ff8a3a', intensity=6, dist=9))
    # the casting pit edge and crucible at the south end, ingot stack in the centre (waist-high)
    CY(0, 0, -12.0, 1.3, 1.6, m['steel_rust'], col=False, seg=18)
    PARTS.append(dict(k='colonly', a=(-1.2, 0, -13.2, 1.2, 1.6, -10.8), tag='cover', mirror=True))
    P(-1.5, 0, -.8, 1.5, 1.0, .8, m['steel_dark'], tag='cover', mirror=False)
    for i in range(3):
        P(-1.45 + i * 1.0, 1.0, -.7, -.6 + i * 1.0, 1.25, .7, m['steel_rust'], col=False, mirror=False)
    crate(-4.6, -1.8, 1.0, 1.0, 1.1, rot=.25); barrel(5.0, -2.2, 'steel_grey')
    # pipes along the hall walls (outside, both lanes) and inside
    for x in (hx0 - .25, hx1 + .25):
        CY(x, 2.9, -.0001 - 8, .14, 16, m['steel_rust'], axis='z', col=False)
        CY(x, 3.3, -.0001 - 8, .09, 16, m['steel_grey'], axis='z', col=False)
    for (x, z) in ((-5.0, -12.0), (5.0, -12.0), (-5.0, -2.0), (5.0, -2.0)):
        P(x - .3, 8.0, z - .3, x + .3, 8.15, z + .3, m['steel_dark'], col=False)
        P(x - .25, 7.96, z - .25, x + .25, 8.0, z + .25, m['lamp'], col=False, ao=False)
        CY(x, 8.15, z, .02, .8, m['steel_dark'], col=False, seg=6)
    LIGHTS.append(dict(pos=(-5.0, 7.4, -8.0), color='#ffd0a0', intensity=16, dist=16))
    LIGHTS.append(dict(pos=(5.0, 7.4, -8.0), color='#ffd0a0', intensity=16, dist=16))
    # apron between the hall and the spawn: barriers, the fuel skid, lamp posts
    barrier(-4.0, -24.0, 0.0, -23.3); barrier(3.0, -29.0, 7.0, -28.3); barrier(-9.0, -31.5, -6.6, -30.8)
    CY(-6.5, 1.25, -20.0, 1.1, 5.0, m['steel_green'], axis='x', col=False, seg=18)
    PARTS.append(dict(k='colonly', a=(-9.0, 0, -21.1, -4.0, 2.35, -18.9), tag='cover', mirror=True))
    for x in (-8.4, -4.6):
        P(x - .2, 0, -21.0, x + .2, .9, -19.0, m['steel_dark'], col=False)
    P(-4.0, 1.9, -19.6, -3.6, 2.1, -19.2, m['steel_dark'], col=False)
    lamp_post(-11.8, -21.0, face=1); lamp_post(11.8, -27.0, face=-1)
    crate(7.5, -20.5, 1.2, 1.2, 1.2); crate(8.6, -20.8, 1.0, 1.0, 2.1, rot=.12)
    sign(12, (-2.0, .86, -23.98), (0, 0, -1), 1.2, .3)                             # NO ENTRY (on a barrier)

    # ---------------- east lane: the yard and the gatehouse
    gx0, gx1, gz = 22.0, 31.6, -7.5
    gup = 3.8
    # ground floor walls
    wall('x', gz, gz + .3, gx0, gx1, 0, 7.4, [(24.5, 26.5, 0, 2.5, 'd'), (28.0, 30.5, 1.1, 2.4, 'w'),
                                             (23.0, 26.0, gup + 1.0, gup + 2.6, 'w'), (27.5, 30.5, gup + 1.0, gup + 2.6, 'w')], m['conc'], tag='gate')
    wall('z', gx0, gx0 + .3, gz, -gz, 0, 7.4, [(-1.0, 1.0, 0, 2.5, 'd'), (-6.0, -3.5, 1.1, 2.4, 'w'), (3.5, 6.0, 1.1, 2.4, 'w'),
                                               (-1.0, 1.0, gup, gup + 2.4, 'd'), (-6.4, -3.4, gup + 1.0, gup + 2.6, 'w'), (3.4, 6.4, gup + 1.0, gup + 2.6, 'w')], m['conc'], tag='gate', mirror=False)
    wall('z', gx1 - .3, gx1, gz, -gz, 0, 7.4, [(-1.0, 1.0, 0, 2.5, 'd'), (-5.0, -2.5, 1.1, 2.4, 'w'), (2.5, 5.0, 1.1, 2.4, 'w'),
                                               (-5.6, -2.6, gup + 1.0, gup + 2.6, 'w'), (2.6, 5.6, gup + 1.0, gup + 2.6, 'w')], m['conc'], tag='gate', mirror=False)
    P(gx0 + .3, gup - .2, gz + .3, gx1 - .3, gup, -gz - .3, m['conc_dark'], tag='floor', mirror=False)
    P(gx0, 7.4, gz, gx1, 7.6, -gz, m['conc_dark'], tag='roof', mirror=False)
    P(gx0 - .1, 7.6, gz - .1, gx1 + .1, 8.1, gz + .2, m['conc'], col=False)            # parapet
    P(gx0 - .1, 7.6, gz - .1, gx0 + .2, 8.1, -gz + .1, m['conc'], col=False, mirror=False)
    P(gx1 - .2, 7.6, gz - .1, gx1 + .1, 8.1, -gz + .1, m['conc'], col=False, mirror=False)
    P(gx0 - .02, gup - .25, gz - .02, gx1 + .02, gup + .05, -gz + .02, m['conc_warm'], col=False, mirror=False)   # floor band
    P(gx0 + .3, 0, gz + .3, gx1 - .3, .02, -.0001, m['floor_in'], col=False, ao=False, tint=1.0)
    # ground floor partition with a doorway, desks and cabinets upstairs and down
    wall('z', 26.85, 27.15, gz + .3, -gz - .3, 0, gup - .2, [(-1.0, 1.0, 0, 2.4, 'd')], m['conc_warm'], tag='gate', mirror=False)
    P(23.2, 0, -6.2, 24.6, 1.0, -4.6, m['steel_grey'], tag='cover')                  # filing cabinets
    P(28.0, 0, -3.2, 30.4, .95, -2.2, m['wood_dark'], tag='cover')                   # workbench
    P(23.0, gup, -2.8, 25.2, gup + 1.0, -1.8, m['wood_dark'], tag='cover')           # desks upstairs
    P(28.4, gup, -5.4, 29.4, gup + 1.9, -3.0, m['steel_grey'], tag='cover')          # locker bank
    P(29.0, gup, 1.4, 30.6, gup + 1.0, 2.6, m['wood_dark'], tag='cover', mirror=False)
    sign(8, ((gx0 + gx1) / 2, 6.95, gz - .02), (0, 0, -1), 4.0, 1.0)              # GATEHOUSE
    LIGHTS.append(dict(pos=(26.5, gup + 3.0, -3.5), color='#e8f0ff', intensity=5, dist=9))
    # balcony (west face) with its outside stairs, posts, railing (gaps at the stair heads and the door)
    bx0, bx1 = 19.6, gx0
    P(bx0, gup - .2, gz, bx1, gup, -gz, m['plate'], tag='balcony', mirror=False)
    P(bx0, gup - .8, gz, bx0 + .3, gup, -gz, m['steel_green'], tag='balcony', mirror=False)
    for z in (-7.3, -2.5):
        P(bx0 + .05, 0, z - .15, bx0 + .35, gup - .8, z + .15, m['steel_green'], tag='post')
    P(bx0 - .04, gup, -5.4, bx0 + .04, gup + 1.0, 5.4, m['steel_yellow'], tag='rail', mirror=False)
    P(bx0 - .03, gup + .5, -5.4, bx0 + .03, gup + .55, 5.4, m['steel_yellow'], col=False, mirror=False)
    stairs(19.7, 21.6, -14.6, gz, 0, gup, 15, m['plate'], rise_along='+z')
    for k in range(4):
        za, zb = -14.6 + k * (14.6 + gz) / 4, -14.6 + (k + 1) * (14.6 + gz) / 4
        P(19.62, gup * k / 4 + .2, za, 19.7, gup * (k + 1) / 4 + 1.0, zb, m['steel_yellow'], tag='rail')
    # containers south of the yard (2.4 m: their roofs are mantle-able vantage points)
    container(13.2, -31.0, 'z', 'corr_red')
    container(19.0, -21.6, 'x', 'corr_blue')
    container(27.0, -29.0, 'x', 'corr_green'); container(27.0, -29.0, 'x', 'corr_grey', y=2.4)
    container(24.0, -35.2, 'z', 'corr_grey')
    container(31.0, -22.06, 'z', 'corr_rust', doors_open=True)                        # the walk-through on the alley
    # yard cover: barriers, pallets, the forklift
    barrier(14.2, -5.0, 14.9, -1.5)
    crate(12.9, -10.3, 1.3, 1.2, 1.4); crate(12.9, -10.3, 1.2, 1.1, .3, y=1.4, m=M['wood_dark'])
    P(16.0, .2, -13.0, 17.4, 2.1, -10.6, m['steel_yellow'], tag='cover')              # forklift body + mast
    P(16.1, 2.1, -12.3, 17.3, 2.25, -10.7, m['steel_dark'], col=False)
    P(16.2, 0, -10.6, 17.2, 3.2, -10.3, m['steel_dark'], tag='cover')
    P(16.3, .1, -10.3, 17.1, .2, -9.0, m['steel_dark'], col=False)
    for zz in (-12.5, -11.0):
        for xx in (15.95, 17.45):
            CY(xx, .32, zz, .32, .24, m['rubber'], axis='x', seg=12, col=False)
    sandbags(18.2, -19.0, 19.6, -18.3)
    barrel(25.5, -14.0, 'steel_green'); barrel(26.2, -14.4); barrel(25.9, -13.3, 'steel_grey', tipped=False)
    crate(28.8, -16.0, 1.2, 1.2, 1.2, rot=.3); crate(23.0, -26.0, 1.3, 1.3, 2.0)
    lamp_post(33.0, -10.0, face=-1)
    sign(13, (25.2, 2.9, -35.22), (0, 0, -1), 1.4, 1.4, 14)                       # container numbers 07 / 12
    sign(11, (14.42, 1.4, -31.02), (0, 0, -1), 2.2, .55)                           # DO NOT STACK

    # ---------------- rubble and debris (visual clusters, one low collider each)
    for (x, z, s) in ((-6.5, -34.5, 1.0), (18.5, -33.0, .8), (-31.5, -12.0, .9), (10.0, -45.0, .7)):
        PARTS.append(dict(k='colonly', a=(x - .8 * s, 0, z - .7 * s, x + .8 * s, .7 * s, z + .7 * s), tag='cover', mirror=True))
        for i in range(9):
            a, d = R.uniform(0, 6.28), R.uniform(0, .7) * s
            w = R.uniform(.25, .55) * s
            P(x + math.cos(a) * d - w, 0, z + math.sin(a) * d - w * .7, x + math.cos(a) * d + w, R.uniform(.2, .7) * s, z + math.sin(a) * d + w * .7,
              m['brick'] if i % 3 else m['conc'], col=False, rot=R.uniform(0, 3))

    return []


# ------------------------------------------------------------------ mirror, build, colliders
def mirror_parts():
    out = []
    swap = {M['team_a']: M['team_b'], M['team_b']: M['team_a']}
    for p in PARTS:
        if not p.get('mirror', True):
            continue
        if p['k'] in ('box', 'colonly'):
            x0, y0, z0, x1, y1, z1 = p['a']
            if z1 > 1e-3:
                if abs(z0 + z1) > 1e-3:
                    print('WARN asymmetric centre part', p['a'])
                continue
            q = dict(p); q['a'] = (x0, y0, -z1, x1, y1, -z0)
            if 'rot' in q:
                q['rot'] = -q['rot']
            if 'm' in q:
                q['m'] = swap.get(q['m'], q['m'])
            out.append(q)
        elif p['k'] == 'cyl':
            cx, cy, cz, r, L, axis, seg = p['a']
            if (axis == 'z' and cz + L / 2 > 1e-3) or (axis != 'z' and cz > -1e-3):
                continue
            q = dict(p); q['a'] = (cx, cy, -cz, r, L, axis, seg)
            out.append(q)
    PARTS.extend(out)
    for s in list(SIGNS):
        cell, (x, y, z), n, w, h, mc = s
        if z < -1e-3:
            SIGNS.append((mc, (x, y, -z), (n[0], n[1], -n[2]), w, h, cell))
    for L in list(LIGHTS):
        x, y, z = L['pos']
        if z < -1e-3:
            q = dict(L); q['pos'] = (x, y, -z)
            if 'team' in q:
                q['team'] = 'b' if q['team'] == 'a' else 'a'
            LIGHTS.append(q)
    for g in list(GLAZE):
        ax, (a0, a1), ys, f, mir = g
        if not mir:
            continue
        if ax == 'x' and f < -1e-3:
            GLAZE.append((ax, (a0, a1), ys, -f, False))
        elif ax == 'z' and a1 < 1e-3:
            GLAZE.append((ax, (-a1, -a0), ys, f, False))


def colliders():
    cols = []
    for p in PARTS:
        if p['k'] in ('box', 'colonly') and (p['k'] == 'colonly' or p['col']):
            x0, y0, z0, x1, y1, z1 = p['a']
            cols.append([round(x0, 3), round(y0, 3), round(z0, 3), round(x1, 3), round(y1, 3), round(z1, 3), p['tag']])
        elif p['k'] == 'cyl' and p['col']:
            cx, cy, cz, r, L, axis, seg = p['a']
            if axis == 'y':
                b = [cx - r * .8, cy, cz - r * .8, cx + r * .8, cy + L, cz + r * .8]
            elif axis == 'x':
                b = [cx - L / 2, cy - r, cz - r, cx + L / 2, cy + r, cz + r]
            else:
                b = [cx - r, cy - r, cz - L / 2, cx + r, cy + r, cz + L / 2]
            cols.append([round(v, 3) for v in b] + [p['tag']])
    return cols


def ground(mb, cols):
    """floor grid (2 m) with contact AO from the colliders standing on it, ballast under the tracks drawn separately."""
    step = 2.0
    nx, nz = int((X1 - X0) / step), int((Z1 - Z0) / step)
    foot = [c for c in cols if c[1] < .05 and c[4] - c[1] > .5 and c[6] not in ('roof',)]

    def ao(x, z):
        d = 9.0
        for c in foot:
            dx = max(c[0] - x, 0, x - c[3]); dz = max(c[2] - z, 0, z - c[5])
            d = min(d, math.hypot(dx, dz))
        return .55 + .45 * smooth(0, 1.6, d)
    A = [[ao(X0 + i * step, Z0 + j * step) for i in range(nx + 1)] for j in range(nz + 1)]
    m = M['floor']
    for j in range(nz):
        for i in range(nx):
            xa, xb, za, zb = X0 + i * step, X0 + (i + 1) * step, Z0 + j * step, Z0 + (j + 1) * step
            pts = [(xa, 0, zb), (xb, 0, zb), (xb, 0, za), (xa, 0, za)]
            mb.poly(pts, [(p[0] / 8, -p[2] / 8) for p in pts], m, (A[j + 1][i], A[j + 1][i + 1], A[j][i + 1], A[j][i]))


def glazing(mb):
    m = M['window']
    for ax, (a0, a1), (y0, y1), f, _ in GLAZE:
        w, h = a1 - a0, y1 - y0
        uvs = [(0, 0), (w / 2, 0), (w / 2, h / 2), (0, h / 2)]
        if ax == 'x':
            mb.poly([(a0, y0, f), (a1, y0, f), (a1, y1, f), (a0, y1, f)], uvs, m, (1, 1, 1, 1))
            mb.poly([(a1, y0, f), (a0, y0, f), (a0, y1, f), (a1, y1, f)], uvs, m, (1, 1, 1, 1))
        else:
            mb.poly([(f, y0, a1), (f, y0, a0), (f, y1, a0), (f, y1, a1)], uvs, m, (1, 1, 1, 1))
            mb.poly([(f, y0, a0), (f, y0, a1), (f, y1, a1), (f, y1, a0)], uvs, m, (1, 1, 1, 1))


def signs(mb):
    m = M['signs']
    for cell, (x, y, z), n, w, h, _ in SIGNS:
        cu, cv = (cell % 4) * .25, 1 - (cell // 4 + 1) * .25
        # u axis = up x n (so the text reads left to right seen from the front)
        u = (n[2] * w, 0, -n[0] * w)
        o = (x - u[0] / 2 + n[0] * .015, y - h / 2, z - u[2] / 2 + n[2] * .015)
        pts = [o, add(o, u), add(add(o, u), (0, h, 0)), add(o, (0, h, 0))]
        # keep the cell's aspect: crop the cell's height band to the sign's aspect
        asp = min(1.0, h / w)
        v0, v1 = cv + .125 - .125 * asp, cv + .125 + .125 * asp
        mb.poly(pts, [(cu, v0), (cu + .25, v0), (cu + .25, v1), (cu, v1)], m, (1, 1, 1, 1))


SMOKE = []      # chimney tops for the runtime smoke (three space [x, y, z, r])


def skyline():
    """The district around Brennick Works (no collisions, never reachable): sawtooth and gabled halls, office blocks with
    lit window bands and rooftop kit, banded chimneys with warning lamps, silos, a blast furnace with its stoves, lattice
    gantry cranes, a conveyor bridge, pylons with cables, a water tower, and the city's towers on the far horizon."""
    mb = MB()
    r = random.Random(9071)
    m = M

    def windows(x0, x1, z0, z1, y0, y1, face, floor=3.6, every=3.2, lit=.35, w=1.6, h=1.5, cool=False):
        """window grid on one face of a box: dark glass with some lit rooms (warm, a few cool)"""
        L = (x1 - x0) if face in ('+z', '-z') else (z1 - z0)
        nx, ny = int(L / every), int((y1 - y0 - 1.5) / floor)
        for j in range(ny):
            y = y0 + 1.2 + j * floor
            for i in range(nx):
                a = (i + .5) * L / nx
                mt = m['far_lit'] if r.random() < lit else m['far_glass']
                if mt is m['far_lit'] and cool and r.random() < .35:
                    mt = m['far_cool']
                if face == '+z':
                    mb.box(x0 + a - w / 2, y, z1, x0 + a + w / 2, y + h, z1 + .06, mt, ao=False)
                elif face == '-z':
                    mb.box(x0 + a - w / 2, y, z0 - .06, x0 + a + w / 2, y + h, z0, mt, ao=False)
                elif face == '+x':
                    mb.box(x1, y, z0 + a - w / 2, x1 + .06, y + h, z0 + a + w / 2, mt, ao=False)
                else:
                    mb.box(x0 - .06, y, z0 + a - w / 2, x0, y + h, z0 + a + w / 2, mt, ao=False)

    def rooftop(x0, x1, z0, z1, y):
        """parapet, HVAC boxes, vents and sometimes a tank on legs"""
        t = .4
        for (a, b, c, d) in ((x0, z0, x1, z0 + t), (x0, z1 - t, x1, z1), (x0, z0, x0 + t, z1), (x1 - t, z0, x1, z1)):
            mb.box(a, y, b, c, y + 1.0, d, m['conc_dark'], ao=False)
        for k in range(r.randint(2, 5)):
            cx, cz = r.uniform(x0 + 3, x1 - 3), r.uniform(z0 + 3, z1 - 3)
            sx, sz, sh = r.uniform(1.5, 4), r.uniform(1.5, 3), r.uniform(1, 2.4)
            mb.box(cx - sx / 2, y, cz - sz / 2, cx + sx / 2, y + sh, cz + sz / 2, m['steel_grey'], ao=False)
            if r.random() < .5:
                mb.cyl(cx, y + sh, cz, .4, 1.2, m['steel_dark'], seg=8, tile=2)
        if r.random() < .45:
            cx, cz = r.uniform(x0 + 4, x1 - 4), r.uniform(z0 + 4, z1 - 4)
            for dx, dz in ((-1.3, -1.3), (1.3, -1.3), (-1.3, 1.3), (1.3, 1.3)):
                mb.box(cx + dx - .12, y, cz + dz - .12, cx + dx + .12, y + 4, cz + dz + .12, m['steel_dark'], ao=False)
            mb.cyl(cx, y + 4, cz, 2.0, 3.2, m['wood_dark'], seg=14, tile=2)
            mb.tcyl(cx, y + 7.2, cz, 2.1, .2, 1.2, m['steel_dark'], seg=14)

    def block(x0, x1, z0, z1, h, mat, faces, lit=.35, roof=True, cool=False):
        mb.box(x0, 0, z0, x1, h, z1, mat, tile=4, ao=True)
        for f in faces:
            windows(x0, x1, z0, z1, 0, h, f, lit=lit, cool=cool)
        if roof:
            rooftop(x0, x1, z0, z1, h)

    def sawtooth(x0, x1, z0, z1, h, rise=3.6, pitch=6.0, face='+z'):
        """factory hall with a sawtooth roof; the glazed upright of every tooth faces `face`"""
        mb.box(x0, 0, z0, x1, h, z1, m['brick_dark'], tile=4)
        n = int((z1 - z0) / pitch)
        for k in range(n):
            za, zb = z0 + k * pitch, z0 + (k + 1) * pitch
            lo, hi = (za, zb) if face == '+z' else (zb, za)
            # sloped roof plane from the low edge up to the glazed upright
            P = [(x0, h, lo), (x1, h, lo), (x1, h + rise, hi), (x0, h + rise, hi)]
            if face != '+z':
                P = [P[1], P[0], P[3], P[2]]
            mb.poly(P, [(p[0] / 4, p[2] / 4) for p in P], m['corr_dark'], (1, 1, 1, 1))
            # glazed upright: strip of dark glass with lit panes
            if face == '+z':
                mb.poly([(x0, h, hi), (x1, h, hi), (x1, h + rise, hi), (x0, h + rise, hi)], [(0, 0), (1, 0), (1, 1), (0, 1)], m['far_glass'], (1, 1, 1, 1))
            else:
                mb.poly([(x1, h, hi), (x0, h, hi), (x0, h + rise, hi), (x1, h + rise, hi)], [(0, 0), (1, 0), (1, 1), (0, 1)], m['far_glass'], (1, 1, 1, 1))
            for i in range(int((x1 - x0) / 5)):
                if r.random() < .22:
                    xx = x0 + 2.5 + i * 5
                    zz = hi + (.06 if face == '+z' else -.06)
                    mb.box(xx - 1.8, h + .4, min(hi, zz), xx + 1.8, h + rise - .4, max(hi, zz), m['far_lit'], ao=False)
            # gable ends of the tooth
            for x in (x0, x1):
                tri = [(x, h, lo), (x, h + rise, hi), (x, h, hi)]
                if (x == x0) == (face == '+z'):
                    tri = tri[::-1]
                mb.poly(tri, [(p[2] / 4, p[1] / 4) for p in tri], m['brick_dark'], (1, 1, 1))
        windows(x0, x1, z0, z1, 0, h, face, floor=5, every=4, lit=.25, w=2.6, h=2.6)

    def gabled(x0, x1, z0, z1, h, ridge, wall, roof, along='x', lit=.3, face='+z'):
        mb.box(x0, 0, z0, x1, h, z1, wall, tile=4)
        if along == 'x':
            zm = (z0 + z1) / 2
            for (za, zb) in ((z0, zm), (z1, zm)):
                P = [(x0, h, za), (x1, h, za), (x1, ridge, zb), (x0, ridge, zb)]
                if za > zb:
                    P = [P[1], P[0], P[3], P[2]]
                mb.poly(P, [(p[0] / 4, p[2] / 4 + p[1] / 4) for p in P], roof, (1, 1, 1, 1))
            for x, sg in ((x0, -1), (x1, 1)):
                tri = [(x, h, z0), (x, h, z1), (x, ridge, zm)]
                if sg < 0:
                    tri = tri[::-1]
                mb.poly(tri, [(p[2] / 4, p[1] / 4) for p in tri], wall, (1, 1, 1))
            # clerestory band of lit panes under the eaves
            windows(x0, x1, z0, z1, h - 5, h, face, floor=4, every=4, lit=lit, w=2.8, h=1.6)
        else:
            xm = (x0 + x1) / 2
            for (xa, xb) in ((x0, xm), (x1, xm)):
                P = [(xa, h, z1), (xa, h, z0), (xb, ridge, z0), (xb, ridge, z1)]
                if xa > xb:
                    P = [P[1], P[0], P[3], P[2]]
                mb.poly(P, [(p[2] / 4, p[0] / 4 + p[1] / 4) for p in P], roof, (1, 1, 1, 1))
            for z, sg in ((z0, -1), (z1, 1)):
                tri = [(x1, h, z), (x0, h, z), (xm, ridge, z)]
                if sg < 0:
                    tri = tri[::-1]
                mb.poly(tri, [(p[0] / 4, p[1] / 4) for p in tri], wall, (1, 1, 1))
            windows(x0, x1, z0, z1, h - 5, h, face, floor=4, every=4, lit=lit, w=2.8, h=1.6)

    def chimney(x, z, r0, h):
        mb.tcyl(x, 0, z, r0, r0 * .78, h, m['brick_dark'], seg=20, tile=4)
        for k in range(1, int(h / 7)):
            y = k * 7; rr = r0 - (r0 * .22) * y / h + .12
            mb.tcyl(x, y, z, rr, rr, .5, m['conc_dark'], seg=20, cap=False)
        rt = r0 * .78
        mb.tcyl(x, h, z, rt + .35, rt + .2, 1.4, m['conc_dark'], seg=20, cap=False)
        mb.tcyl(x, h + 1.4, z, rt * .8, rt * .8, .01, m['steel_dark'], seg=16)        # dark mouth
        for a in (0, 2.1, 4.2):
            lx, lz = x + math.cos(a) * (rt + .5), z + math.sin(a) * (rt + .5)
            mb.box(lx - .25, h + .4, lz - .25, lx + .25, h + .9, lz + .25, m['warn'], ao=False)
        SMOKE.append([round(x, 2), round(h + 1.6, 2), round(z, 2), round(rt, 2)])

    def silo(x, z, rr, h):
        mb.cyl(x, 0, z, rr, h, m['conc_warm'], seg=20, tile=4)
        mb.tcyl(x, h, z, rr, .6, rr * .7, m['corr_grey'], seg=20)
        for k in range(1, int(h / 4)):
            mb.tcyl(x, k * 4, z, rr + .06, rr + .06, .15, m['steel_dark'], seg=20, cap=False)

    def lattice_leg(p0, p1, w, mat, step=3.0):
        """4-chord square lattice between two points (crane legs / girders / pylons)"""
        ax = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]); L = math.sqrt(dot(ax, ax)); a = unit(ax)
        up = (0, 1, 0) if abs(a[1]) < .95 else (1, 0, 0)
        sv = unit(cross(a, up)); uv = cross(sv, a)
        C = [(sx * w / 2, sy * w / 2) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        P = lambda t, c: (p0[0] + ax[0] * t + sv[0] * c[0] + uv[0] * c[1], p0[1] + ax[1] * t + sv[1] * c[0] + uv[1] * c[1], p0[2] + ax[2] * t + sv[2] * c[0] + uv[2] * c[1])
        for c in C:
            mb.beam(P(0, c), P(1, c), .22, mat)
        n = max(1, int(L / step))
        for k in range(n + 1):
            t = k / n
            for i in range(4):
                mb.beam(P(t, C[i]), P(t, C[(i + 1) % 4]), .1, mat)
            if k < n:
                for i in range(4):
                    if (i + k) % 2 == 0:
                        mb.beam(P(t, C[i]), P((k + 1) / n, C[(i + 1) % 4]), .08, mat)

    def gantry(x0, x1, za, zb, h):
        for x in (x0, x1):
            for z in (za, zb):
                lattice_leg((x, 0, z), (x, h, z), 1.4, m['steel_yellow'])
            lattice_leg((x, h - 1, za), (x, h - 1, zb), 1.2, m['steel_yellow'])
        for z in (za, zb):
            lattice_leg((x0 - 4, h + .8, z), (x1 + 4, h + .8, z), 2.0, m['steel_yellow'], step=4)
        tx = x0 + (x1 - x0) * .62
        mb.box(tx - 2, h + 1.8, za - 1, tx + 2, h + 4, zb + 1, m['steel_yellow'], ao=False)   # trolley
        mb.box(tx - .3, h - 6, (za + zb) / 2 - .3, tx + .3, h + 1.8, (za + zb) / 2 + .3, m['steel_dark'], ao=False)
        mb.box(tx - 1.2, h - 7, (za + zb) / 2 - .8, tx + 1.2, h - 6, (za + zb) / 2 + .8, m['steel_yellow'], ao=False)

    def pylon(x, z, h=34):
        base = 5.0
        feet = [(x - base, 0, z - base), (x + base, 0, z - base), (x + base, 0, z + base), (x - base, 0, z + base)]
        top = [(x - 1, h, z - 1), (x + 1, h, z - 1), (x + 1, h, z + 1), (x - 1, h, z + 1)]
        for f, t in zip(feet, top):
            mb.beam(f, t, .3, m['steel_grey'])
        for k in range(1, 7):
            t = k / 7
            ring = [(f[0] + (tp[0] - f[0]) * t, h * t, f[2] + (tp[2] - f[2]) * t) for f, tp in zip(feet, top)]
            for i in range(4):
                mb.beam(ring[i], ring[(i + 1) % 4], .12, m['steel_grey'])
                if k > 1:
                    prev = [(f[0] + (tp[0] - f[0]) * (k - 1) / 7, h * (k - 1) / 7, f[2] + (tp[2] - f[2]) * (k - 1) / 7) for f, tp in zip(feet, top)]
                    mb.beam(prev[i], ring[(i + 1) % 4], .08, m['steel_grey'])
        for y, w in ((h * .72, 9), (h * .88, 7)):
            mb.beam((x - w, y, z), (x + w, y, z), .5, m['steel_grey'])
        return [(x - 9, h * .72 - .6, z), (x + 9, h * .72 - .6, z), (x - 7, h * .88 - .6, z), (x + 7, h * .88 - .6, z)]

    # ---- far ground around the walls (four quads, no overdraw on the yard)
    G = 520
    for (xa, za, xb, zb) in ((-G, -G, G, Z0 - .8), (-G, Z1 + .8, G, G), (-G, Z0 - .8, X0 - .8, Z1 + .8), (X1 + .8, Z0 - .8, G, Z1 + .8)):
        P = [(xa, -.02, zb), (xb, -.02, zb), (xb, -.02, za), (xa, -.02, za)]
        mb.poly(P, [(p[0] / 16, -p[2] / 16) for p in P], m['far_ground'], (1, 1, 1, 1))

    # ---- south: the works' own sawtooth shop, the gabled store with its yard crane, stacks, silos, conveyor
    sawtooth(-70, -8, -96, -58, 12, face='+z')
    gabled(-4, 50, -88, -60, 13, 20, m['corr_rust'], m['corr_dark'], along='x', face='+z')
    windows(-4, 50, -88, -60, 0, 9, '+z', floor=4.5, every=5, lit=.3, w=3, h=2)
    chimney(-26, -66, 2.4, 44); chimney(-14, -72, 1.9, 34); chimney(28, -108, 3.0, 58)
    for k, (x, z) in enumerate(((62, -70), (71, -70), (66.5, -78))):
        silo(x, z, 4.0, 22 + k * 2)
    gantry(56, 94, -66, -54, 22)
    for k in range(5):            # conveyor bridge from the silos down onto the store roof
        t0, t1 = k / 5, (k + 1) / 5
        pa = (62 + (44 - 62) * t0, 23 + (17 - 23) * t0, -74 + (-74 + 74) * t0)
        pb = (62 + (44 - 62) * t1, 23 + (17 - 23) * t1, -74)
        mb.beam(pa, pb, 2.2, m['corr_grey'], d=2.0)
    for x in (58, 51):
        mb.beam((x, 0, -74), (x, 21 - (62 - x) * .33, -74), .5, m['steel_dark'])
    block(60, 92, -110, -86, 16, m['brick_dark'], ['+z', '-x'], lit=.3)

    # ---- north: blast furnace and stoves, a gabled hall, a stack and a second crane
    mb.tcyl(12, 0, 86, 7.5, 6.0, 10, m['steel_rust'], seg=24)
    mb.tcyl(12, 10, 86, 6.0, 3.8, 26, m['steel_rust'], seg=24)
    mb.tcyl(12, 36, 86, 3.8, 2.4, 6, m['steel_dark'], seg=20)
    for y in (12, 22, 32):
        mb.tcyl(12, y, 86, 7.2 - y * .1, 7.2 - y * .1, .4, m['steel_dark'], seg=24, cap=False)
        mb.tcyl(12, y + .4, 86, 7.4 - y * .1, 7.4 - y * .1, .06, m['plate'], seg=24)
    for k, x in enumerate((-8, -17, -26)):
        mb.cyl(x, 0, 92, 3.6, 30 + k, m['steel_grey'], seg=20, tile=4)
        mb.tcyl(x, 30 + k, 92, 3.6, 0, 3, m['steel_dark'], seg=20)
        mb.beam((x, 26, 92), (12, 30, 86), .9, m['steel_rust'])
    gabled(-76, -32, 60, 96, 14, 21, m['brick'], m['corr_dark'], along='x', face='-z')
    windows(-76, -32, 60, 96, 0, 10, '-z', floor=4.5, every=5, lit=.3, w=3, h=2)
    chimney(40, 74, 2.6, 48)
    gantry(30, 70, 60, 70, 20)
    block(-30, -6, 104, 128, 20, m['conc_dark'], ['-z'], lit=.35)

    # ---- east: office and warehouse blocks facing the yard, rooftops; pylons and cables beyond
    block(41, 60, -44, -14, 18, m['brick_dark'], ['-x', '+z', '-z'], lit=.4)
    block(42, 66, -8, 22, 24, m['tower'], ['-x', '-z'], lit=.45, cool=True)
    gabled(40, 58, 28, 56, 10, 15, m['corr_green'], m['corr_dark'], along='z', face='-x')
    windows(40, 58, 28, 56, 0, 10, '-x', floor=4, every=5, lit=.25, w=3, h=1.8)
    block(70, 96, -30, 30, 14, m['brick'], ['-x'], lit=.2)
    wires = []
    for z in (-120, -40, 40, 120):
        wires.append(pylon(118, z))
    for a, b in zip(wires, wires[1:]):
        for pa, pb in zip(a, b):
            mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2 - 4, (pa[2] + pb[2]) / 2)
            mb.beam(pa, mid, .06, m['steel_dark']); mb.beam(mid, pb, .06, m['steel_dark'])

    # ---- west: the rail shed, a water tower, a tall brick block
    gabled(-74, -42, -34, 34, 10, 16, m['corr_rust'], m['corr_dark'], along='z', face='+x')
    windows(-74, -42, -34, 34, 0, 9, '+x', floor=4, every=6, lit=.2, w=3.4, h=2)
    for dx, dz in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
        mb.beam((-50 + dx * 1.4, 0, 44 + dz * 1.4), (-50 + dx * .8, 18, 44 + dz * .8), .35, m['steel_dark'])
    mb.cyl(-50, 18, 44, 4.2, 6, m['steel_green'], seg=18, tile=3)
    mb.tcyl(-50, 24, 44, 4.3, .3, 2.2, m['steel_dark'], seg=18)
    block(-66, -42, 40 + 12, 74, 22, m['brick_dark'], ['+x', '-z'], lit=.35)
    block(-68, -44, -76, -48, 16, m['conc'], ['+x', '+z'], lit=.3, cool=True)

    # ---- the city on the horizon (towers with lit floors, mostly to the north-east, a few to the south-west)
    for k in range(34):
        ne = k < 24
        a = r.uniform(.15, 1.35) if ne else r.uniform(3.4, 4.4)
        d = r.uniform(240, 400) if ne else r.uniform(260, 380)
        cx, cz = math.sin(a) * d, math.cos(a) * d
        w, dd = r.uniform(14, 30), r.uniform(14, 30)
        h = r.uniform(50, 140) if ne else r.uniform(30, 70)
        mat = m['tower'] if r.random() < .5 else m['tower_dark']
        mb.box(cx - w / 2, 0, cz - dd / 2, cx + w / 2, h, cz + dd / 2, mat, tile=8, ao=False)
        # lit floors as bands facing the yard (no per-window quads this far out)
        face = '-z' if abs(cz) > abs(cx) and cz > 0 else '+z' if abs(cz) > abs(cx) else '-x' if cx > 0 else '+x'
        for j in range(int(h / 4)):
            if r.random() < .38:
                y = 3 + j * 4
                u0, u1 = sorted((r.uniform(-.45, .1), r.uniform(.0, .45)))
                if face in ('+z', '-z'):
                    zf = cz - dd / 2 - .1 if face == '-z' else cz + dd / 2
                    mb.box(cx + u0 * w, y, zf, cx + u1 * w, y + 1.6, zf + .1, m['far_cool'] if r.random() < .3 else m['far_lit'], ao=False)
                else:
                    xf = cx - w / 2 - .1 if face == '-x' else cx + w / 2
                    mb.box(xf, y, cz + u0 * dd, xf + .1, y + 1.6, cz + u1 * dd, m['far_cool'] if r.random() < .3 else m['far_lit'], ao=False)
        if r.random() < .5:
            mb.box(cx - .25, h, cz - .25, cx + .25, h + r.uniform(6, 16), cz + .25, m['steel_dark'], ao=False)
            mb.box(cx - .5, h + 6, cz - .5, cx + .5, h + 7, cz + .5, m['warn'], ao=False)
    return mb.build('ARENA_far')


# ------------------------------------------------------------------ navigation graph
CELL = 1.0
RAD = .42


class Grid:
    def __init__(self, cols, cs=4.0):
        self.cs = cs; self.g = {}
        for i, c in enumerate(cols):
            for ix in range(int(math.floor(c[0] / cs)), int(math.floor(c[3] / cs)) + 1):
                for iz in range(int(math.floor(c[2] / cs)), int(math.floor(c[5] / cs)) + 1):
                    self.g.setdefault((ix, iz), []).append(c)

    def near(self, x, z, r=0.0):
        out = []; seen = set()
        for ix in range(int(math.floor((x - r) / self.cs)), int(math.floor((x + r) / self.cs)) + 1):
            for iz in range(int(math.floor((z - r) / self.cs)), int(math.floor((z + r) / self.cs)) + 1):
                for c in self.g.get((ix, iz), ()):
                    if id(c) not in seen:
                        seen.add(id(c)); out.append(c)
        return out


def nav(cols):
    G = Grid(cols)
    solid = [c for c in cols if c[6] not in ('rail_vis',)]

    def free(x, y, z, r=RAD, lo=.46, hi=1.75):
        for c in G.near(x, z, r):
            if c[4] <= y + lo or c[1] >= y + hi:
                continue
            dx = max(c[0] - x, 0, x - c[3]); dz = max(c[2] - z, 0, z - c[5])
            if dx * dx + dz * dz < r * r:
                return False
        return True

    FLOORS = ('stairs', 'mezz', 'platform', 'dock', 'floor', 'balcony', 'wagon', 'container', 'truck', 'hut', 'gate')

    def supports(x, z):
        ys = [0.0]
        for c in G.near(x, z, 0):
            if c[0] - .05 <= x <= c[3] + .05 and c[2] - .05 <= z <= c[5] + .05 and c[6] not in ('roof', 'rail', 'post'):
                # no standing on top of small cover (crates, barriers, cabinets): bots walk around those
                if c[6] not in FLOORS and min(c[3] - c[0], c[5] - c[2]) < 1.6:
                    continue
                ys.append(c[4])
        return sorted(set(round(y, 3) for y in ys))

    def support_at(x, z, y):
        """height you stand on at (x, z) coming from y (like CollisionWorld.support)"""
        s = 0.0
        for c in G.near(x, z, 0):
            if c[0] <= x <= c[3] and c[2] <= z <= c[5] and c[4] <= y + .6 and c[4] > s:
                s = c[4]
        return s

    nodes, at = [], {}
    nx, nz = int((X1 - X0) / CELL), int((Z1 - Z0) / CELL)
    for j in range(nz):
        for i in range(nx):
            x, z = X0 + (i + .5) * CELL, Z0 + (j + .5) * CELL
            for y in supports(x, z):
                # covered by a box whose top is above y (inside a solid): skip
                if not free(x, y, z):
                    continue
                if support_at(x, z, y + .05) > y + .05:
                    continue
                at.setdefault((i, j), []).append(len(nodes))
                nodes.append((x, y, z, i, j))
    edges = [[] for _ in nodes]
    for a, (x, y, z, i, j) in enumerate(nodes):
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if not di and not dj:
                    continue
                for b in at.get((i + di, j + dj), ()):
                    bx, by, bz = nodes[b][:3]
                    dy = by - y
                    dist = math.hypot(bx - x, bz - z)
                    mx, mz = (x + bx) / 2, (z + bz) / 2
                    if abs(dy) <= .72:
                        # walkable: level ground, or stairs (the midpoint sits between both ends within a step)
                        sy = support_at(mx, mz, max(y, by) + .05)
                        if abs(sy - y) > .46 or abs(sy - by) > .46 or not free(mx, sy, mz):
                            continue
                        if di and dj:   # no corner cutting
                            ok = all(any(abs(nodes[k][1] - y) <= .72 for k in at.get(c, ())) for c in ((i + di, j), (i, j + dj)))
                            if not ok:
                                continue
                        edges[a].append((b, 'w', dist))
                    elif dy < -.5 and dy > -5.5 and not (di and dj):
                        # drop: walk off the edge; the column above b must be open up to our head height
                        if free(bx, by, bz, hi=y - by + 1.75):
                            edges[a].append((b, 'd', dist + .6))
                    elif .46 < dy <= 2.4 and not (di and dj):
                        # mantle: the ledge face is between us and b, head room above us up to the new height
                        if free(x, y, z, hi=dy + 1.75) and free(bx, by, bz):
                            edges[a].append((b, 'm', dist + 1.2 + dy))
        # two cells out (cardinal): the ledge / wall cell between has no node at either height (wagon doors, container
        # roofs and platform edges sit closer than a body radius to the cell centres beside them)
        for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            mid = at.get((i + di, j + dj), ())
            for b in at.get((i + 2 * di, j + 2 * dj), ()):
                bx, by, bz = nodes[b][:3]; dy = by - y
                if any(abs(nodes[k][1] - y) < .3 or abs(nodes[k][1] - by) < .3 for k in mid):
                    continue
                if .46 < dy <= 2.4 and free(x, y, z, hi=dy + 1.75) and free(x + di * .5, by, z + dj * .5, r=.2):
                    edges[a].append((b, 'm', 2 + 1.2 + dy))
                elif -5.5 < dy < -.46 and free(bx, by, bz, hi=-dy + 1.75) and free(x + di * 1.0, by, z + dj * 1.0, r=.3, hi=-dy + 1.75):
                    edges[a].append((b, 'd', 2.6))
    # keep the part both spawns can reach and return from
    def reach(start, rev=False):
        adj = edges
        if rev:
            radj = [[] for _ in nodes]
            for a, es in enumerate(edges):
                for b, t, c in es:
                    radj[b].append((a, t, c))
            adj = radj
        seen = {start}; st = [start]
        while st:
            a = st.pop()
            for b, t, c in adj[a]:
                if b not in seen:
                    seen.add(b); st.append(b)
        return seen

    def nearest(x, y, z):
        return min(range(len(nodes)), key=lambda k: (nodes[k][0] - x) ** 2 + (nodes[k][2] - z) ** 2 + 4 * (nodes[k][1] - y) ** 2)
    s0 = nearest(0, 1.2, -49.5)
    keep = reach(s0) & reach(s0, True)
    idx = {}; out = []
    for k in sorted(keep):
        idx[k] = len(out); out.append(nodes[k])
    E = [[(idx[b], t, c) for b, t, c in edges[k] if b in idx] for k in sorted(keep)]
    # cover: a node beside a box that hides a crouching (top >= y + .9) or standing (top >= y + 1.8) body
    cover = []
    for n, (x, y, z, i, j) in enumerate(out):
        best = None
        for (dx, dz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            px, pz = x + dx * .9, z + dz * .9
            for c in G.near(px, pz, 0):
                if c[0] <= px <= c[3] and c[2] <= pz <= c[5] and c[1] <= y + .3 and c[4] >= y + .9 and c[6] not in ('rail',):
                    h = 2 if c[4] >= y + 1.8 else 1
                    if not best or h > best[3]:
                        best = (n, dx, dz, h)
        if best:
            cover.append(list(best))
    nflat = []
    for (x, y, z, i, j) in out:
        nflat += [round(x * 10), round(y * 100), round(z * 10)]
    adj = []; typ = []
    for es in E:
        adj.append([b for b, t, c in es]); typ.append(''.join(t for b, t, c in es))
    print('[nav] nodes %d (of %d), edges %d (mantle %d, drop %d), cover %d' % (len(out), len(nodes), sum(len(a) for a in adj),
          sum(t.count('m') for t in typ), sum(t.count('d') for t in typ), len(cover)))
    return dict(cell=CELL, nodes=nflat, adj=adj, typ=typ, cover=cover)


# ------------------------------------------------------------------ spawn line-of-sight audit
def los_audit(cols, spawns):
    G = Grid(cols)

    def blocked(a, b):
        d = [b[i] - a[i] for i in range(3)]; L = math.sqrt(sum(v * v for v in d))
        n = int(L / .25)
        for k in range(1, n):
            t = k / n; p = [a[i] + d[i] * t for i in range(3)]
            for c in G.near(p[0], p[2], 0):
                if c[0] <= p[0] <= c[3] and c[1] <= p[1] <= c[4] and c[2] <= p[2] <= c[5]:
                    return True
        return False
    bad = 0
    for a in spawns['a']:
        for b in spawns['b']:
            if not blocked((a[0], a[1] + 1.6, a[2]), (b[0], b[1] + 1.6, b[2])):
                bad += 1; print('  open spawn sightline', a, b)
    print('[los] spawn-to-spawn open lines:', bad)


def main():
    global M
    bl.reset()
    M = materials()
    far = layout()
    mirror_parts()
    cols = colliders()
    mb = MB()
    for p in PARTS:
        if p['k'] == 'box':
            mb.box(*p['a'], p['m'], ao=p['ao'], tint=p['tint'], skip=p['skip'], rot=p['rot'])
        elif p['k'] == 'cyl':
            cx, cy, cz, r, L, axis, seg = p['a']
            mb.cyl(cx, cy, cz, r, L, p['m'], axis=axis, seg=seg)
    ground(mb, cols)
    arena = mb.build('ARENA')
    gb = MB(); glazing(gb); signs(gb); glass = gb.build('ARENA_glass')
    skyline()
    # spawns: squad A at -z facing +z, mirrored for squad B
    A = [(-6, 1.2, -50), (0, 1.2, -50.2), (6, 1.2, -50), (-3, 1.2, -48.6), (3, 1.2, -48.6), (-16, 0, -43.5), (-8, 0, -43),
         (8, 0, -43), (20.5, 0, -44.5), (28, 0, -42), (-31, 0, -42), (-22.5, 0, -42.5), (15, 0, -40), (-11, 0, -41)]
    spawns = {'a': [list(p) + [0.0] for p in A], 'b': [[x, y, -z, math.pi] for (x, y, z) in A]}
    los_audit(cols, spawns)
    navg = nav(cols)
    lanes = {'west': [[-20, -36], [-20, -18], [-19.5, -8], [-19.5, 0], [-19.5, 8], [-20, 18], [-20, 36]],
             'mid': [[0, -36], [2, -20], [-5, -12], [0, -2.4], [5, 12], [-2, 20], [0, 36]],
             'east': [[17, -36], [18, -24], [17.5, -8], [17, 0], [17.5, 8], [18, 24], [17, 36]],
             'west_alley': [[-32, -36], [-33.0, -28.5], [-32, -15], [-32, 0], [-32, 15], [-33.0, 28.5], [-32, 36]],
             'east_alley': [[32.8, -36], [32.3, -19], [32.8, -10], [32.8, 0], [32.8, 10], [32.3, 19], [32.8, 36]]}
    perches = [[-9.0, 4.0, -4.5], [9.0, 4.0, 4.5], [-9.0, 4.0, 4.5], [9.0, 4.0, -4.5], [20.8, 3.8, -4.0], [20.8, 3.8, 4.0],
               [25.0, 3.8, -5.0], [25.0, 3.8, 5.0], [-15.5, 1.2, -12.0], [-15.5, 1.2, 12.0], [14.4, 2.4, -28.0], [14.4, 2.4, 28.0],
               [-28.5, 1.05, -16.0], [-28.5, 1.05, 16.0], [-23.0, 1.3, 0.0], [0.0, 4.0, 0.0]]
    data = dict(name='Brennick Works', bounds=[X0, Z0, X1, Z1], colliders=cols, spawns=spawns, nav=navg, lanes=lanes, perches=perches,
                lights=[dict(pos=[round(v, 2) for v in L['pos']], color=L['color'], intensity=L['intensity'], dist=L['dist'], team=L.get('team'))
                        for L in LIGHTS],
                smoke=SMOKE, sun=dict(dir=[-.55, .26, -.79], color='#ffc08a', intensity=2.7), sky=['#e3a072', '#33476e'])
    json.dump(data, open(os.path.join(bl.MODELS, NAME + '.json'), 'w'), separators=(',', ':'))
    print('[arena] colliders', len(cols), 'lights', len(LIGHTS), 'signs', len(SIGNS), 'glazing', len(GLAZE))
    p = bl.export(NAME + '.glb', export_vertex_color='ACTIVE')
    bl.quantize_glb(p)
    print('[export] %s %.0f KB (quantized)' % (NAME + '.glb', os.path.getsize(p) / 1024))


main()
