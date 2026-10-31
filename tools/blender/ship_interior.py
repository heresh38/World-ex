"""The player's ship (hub): cockpit bridge -> corridor -> commons -> corridor -> hangar bay open to space.

Exports assets/models/ship_interior.glb and ship_interior.json (everything in three.js space):
  colliders:  AABBs [minx,miny,minz,maxx,maxy,maxz]
  stations:   id -> {pos (standing point), look, label, verb, at (object centre), rad (horizontal radius), ...}
  lights:     runtime light anchors (kinds sun, spot, point, weld)
  seats:      [{pos, yaw}] avatar root point (floor / platform under the seat) + facing yaw = atan2(dir.x, dir.z)
  screens:    [{kind, pos}] centres of the live screens (materials screen_<kind>, UV 0..1 per screen)
  portholes:  [{pos, normal, r}] hull windows (for light beams)
Layout (Blender, Z up, nose toward -Y; floor at z=0 everywhere you walk):
  bridge y[-24,-13] | B1 | corridor y[-12.5,-8.5] | B2 | commons y[-8,6] | B3 | corridor y[6.5,10.5] | B4 | hangar y[11,39.5] -> open bay
Cross sections are chamfered octagons (10-point profiles) lofted between ring frames; walls, frames, floors and the
exterior hull are joined by material at the end so the whole ship costs a few dozen draw calls.
"""
import bpy, bmesh, math, os, sys, json, random
sys.path.insert(0, os.path.dirname(__file__))
import bl, props
from mathutils import Vector, Matrix

R90 = math.pi / 2
SOLIDS = []      # prop roots whose world AABB becomes a collider
COLS = []        # explicit collider boxes (three space)
STATIONS = {}
LIGHTS = []
SEATS = []
PORTHOLES = []
STATIC = []      # loose architecture objects, joined by material at export
TILE = {}        # material name -> texture tile size in metres (world-scale UVs)
rnd = random.Random(7)


def to3(v):
    return [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]


def dir3(v):
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


def yaw3(dx, dy):
    """Facing yaw in three space for a Blender XY direction (three dir = (dx, -dy))."""
    return round(math.atan2(dx, -dy), 4)


def col_box(x0, y0, z0, x1, y1, z1):
    COLS.append([round(min(x0, x1), 3), round(min(z0, z1), 3), round(-max(y0, y1), 3),
                 round(max(x0, x1), 3), round(max(z0, z1), 3), round(-min(y0, y1), 3)])


def solid(o):
    SOLIDS.append(o); return o


def part(o):
    m = o.data.materials[0] if o.data.materials else None
    if m is not None and m.name in TILE:
        bl.uv_box(o, TILE[m.name])
    STATIC.append(o)
    return o


# ------------------------------------------------------------------ materials
def tmat(name, color, metal, rough, tex=None, tile=1.0, emit_tex=None, emit_strength=1.0, cull=False):
    m = bl.mat(name, color, metal, rough, image=(tex + '_c.jpg') if tex else None, normal=(tex + '_n.jpg') if tex else None)
    if emit_tex:
        nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(bl.TEXTURES, emit_tex))
        nt.links.new(tn.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = emit_strength
    m.use_backface_culling = cull
    if tex:
        TILE[name] = tile
    return m


def alpha_mat(name, color, image, rough=.7):
    m = bl.mat(name, color, 0, rough)
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(bl.TEXTURES, image))
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0; mix.inputs[7].default_value = (*bl.hexrgb(color), 1)
    nt.links.new(tn.outputs['Color'], mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    nt.links.new(tn.outputs['Alpha'], b.inputs['Alpha'])
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    return m


def materials():
    m = props.M()
    m.update(
        wall=tmat('wall_panel', '#ffffff', .3, .5, 'shipwall', 2.0, 'shipwall_e.jpg', 3.0),
        wall_lower=tmat('wall_lower', '#7f8790', .55, .45, 'paintmetal', 1.0),
        padded=tmat('wall_padded', '#ece9e2', 0, .85, 'padding', 1.2),
        ceil=tmat('ceil_panel', '#8f969f', .5, .5, 'paintmetal', 1.5),
        frame=tmat('wall_frame', '#4b525b', .65, .4, 'paintmetal', 1.0),
        frame_light=tmat('wall_frame_light', '#c9ced4', .4, .42, 'paintmetal', 1.0),
        deck=tmat('floor_deck', '#ffffff', .6, .5, 'deckplate', 2.0),
        grate=tmat('floor_grate', '#ffffff', .8, .4, 'grate', 1.0, 'grate_e.jpg', 1.4),
        mat=tmat('floor_mat', '#ffffff', 0, .85, 'rubbermat', .5),
        hull=tmat('hull_ext', '#ffffff', .25, .45, 'hullplate', 4.0, cull=True),
        hull_dark=tmat('hull_ext_dark', '#5d636b', .5, .4, 'hullplate', 4.0, cull=True),
        glass=bl.mat('window_glass', '#a8d0ff', 0, .02, alpha=.1),
        lightp=bl.mat('light_panel', '#fff4e2', 0, .4, emit='#fff4e2', strength=7),
        lightc=bl.mat('light_cool', '#e6f4ff', 0, .4, emit='#e6f4ff', strength=6),
        field=bl.mat('force_field', '#3aa8ff', 0, .2, emit='#3aa8ff', strength=2, alpha=.25),
        stencil=alpha_mat('stencil', '#f2efe6', 'stencil_c.png'),
        stencil_y=alpha_mat('stencil_yellow', '#f0b52a', 'stencil_c.png'),
        pipe_y=bl.mat('pipe_yellow', '#c99a1e', .5, .4),
        pipe_r=bl.mat('pipe_red', '#8f2a22', .4, .45),
        pipe_b=bl.mat('pipe_blue', '#2a5d8f', .4, .45),
        green=bl.mat('neon_green', '#30ff70', 0, .4, emit='#30ff70', strength=6),
        engine=bl.mat('engine_glow', '#7fd8ff', 0, .3, emit='#7fd8ff', strength=12),
    )
    m['hazard'].node_tree  # existing hazard stripes (hazard_c.jpg)
    TILE['hazard'] = 1.0
    return m


# ------------------------------------------------------------------ mesh accumulator (one object per material)
class MB:
    def __init__(self):
        self.d = {}

    def face(self, m, pts, uvs):
        e = self.d.setdefault(m.name, [m, [], [], []])
        i = len(e[1]); e[1].extend([tuple(p) for p in pts]); e[2].append(tuple(range(i, i + len(pts)))); e[3].extend(uvs)

    def build(self, prefix):
        for name, (m, V, F, UV) in self.d.items():
            me = bpy.data.meshes.new(prefix + name)
            me.from_pydata(V, [], F)
            uvl = me.uv_layers.new(name='UVMap')
            for li, uv in enumerate(UV):
                uvl.data[li].uv = uv
            me.validate(); me.update()
            o = bpy.data.objects.new(prefix + name, me)
            bpy.context.scene.collection.objects.link(o)
            me.materials.append(m)
            STATIC.append(o)
        self.d = {}


MBX = MB()


def newell(pts):
    n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z); n.y += (a.z - b.z) * (a.x + b.x); n.z += (a.x - b.x) * (a.y + b.y)
    return n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))


def uv_auto(pts, t):
    n = newell(pts); ax = max(range(3), key=lambda k: abs(n[k]))
    if ax == 2:
        return [(p.x / t, p.y / t) for p in pts]
    if ax == 0:
        return [(p.y / t * (1 if n.x > 0 else -1), p.z / t) for p in pts]
    return [(p.x / t * (-1 if n.y > 0 else 1), p.z / t) for p in pts]


def poly(m, pts, mb=None, uvs=None, flip=False):
    pts = [Vector(p) for p in pts]
    if flip:
        pts = pts[::-1]
    (mb or MBX).face(m, pts, uvs or uv_auto(pts, TILE.get(m.name, 1.0)))


def fill(m, loops, normal, mb=None, uvfn=None, flip=False):
    """Planar polygon with holes (first loop outer) -> triangles."""
    bm = bmesh.new(); edges = []
    for loop in loops:
        vs = [bm.verts.new(Vector(p)) for p in loop]
        for i in range(len(vs)):
            edges.append(bm.edges.new((vs[i], vs[(i + 1) % len(vs)])))
    r = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges, normal=Vector(normal))
    n = Vector(normal)
    for f in [g for g in r['geom'] if isinstance(g, bmesh.types.BMFace)]:
        pts = [v.co.copy() for v in f.verts]
        if newell(pts).dot(n) < 0:
            pts = pts[::-1]
        if flip:
            pts = pts[::-1]
        uvs = uvfn(pts) if uvfn else uv_auto(pts, TILE.get(m.name, 1.0))
        (mb or MBX).face(m, pts, uvs)
    bm.free()


def beam(p0, p1, w, d, m, up=(0, 0, 1), name='beam'):
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0; L = ax.length
    if L < 1e-4:
        return None
    y = ax / L; z = Vector(up); z = (z - y * z.dot(y))
    if z.length < 1e-4:
        z = Vector((1, 0, 0)) - y * y.x
    z.normalize(); x = y.cross(z)
    o = bl.box(name, (w, L, d), (0, 0, 0), m)
    M4 = Matrix((x, y, z)).transposed().to_4x4(); M4.translation = (p0 + p1) / 2
    o.matrix_world = M4
    return part(o)


def tube_y(m, cx, cz, rings, seg=24, mb=None, cap_end=None, cap_mat=None):
    """Surface of revolution about an axis parallel to Y through (cx, cz). rings: [(y, r)], outward faces."""
    P = [[Vector((cx + r * math.cos(k / seg * 2 * math.pi), y, cz + r * math.sin(k / seg * 2 * math.pi))) for k in range(seg)] for (y, r) in rings]
    for i in range(len(P) - 1):
        for k in range(seg):
            a, b = P[i][k], P[i][(k + 1) % seg]; c, d = P[i + 1][(k + 1) % seg], P[i + 1][k]
            q = [a, d, c, b]
            u0, u1 = k / seg * 4, (k + 1) / seg * 4
            (mb or MBX).face(m, q, [(u0, rings[i][0] / 4), (u0, rings[i + 1][0] / 4), (u1, rings[i + 1][0] / 4), (u1, rings[i][0] / 4)])
    if cap_end is not None:
        ring = P[-1] if cap_end == 'last' else P[0]
        pts = ring[::-1] if cap_end == 'first' else ring
        (mb or MBX).face(cap_mat or m, pts, [(.5 + .5 * math.cos(k / seg * 2 * math.pi), .5 + .5 * math.sin(k / seg * 2 * math.pi)) for k in range(seg)][::(-1 if cap_end == 'first' else 1)])


# ------------------------------------------------------------------ profiles
def prof(W, H, a=.5, a2=.6, sill=1.1, bh=1.2, bv=.9):
    """Chamfered-octagon cross section, 10 points from the left floor edge clockwise to the right floor edge."""
    return [(-W + a, 0), (-W, a2), (-W, sill), (-W, H - bv), (-W + bh, H), (W - bh, H), (W, H - bv), (W, sill), (W, a2), (W - a, 0)]


def seg_normals(pr):
    out = []
    for k in range(len(pr) - 1):
        dx, dz = pr[k + 1][0] - pr[k][0], pr[k + 1][1] - pr[k][1]
        L = math.hypot(dx, dz) or 1
        out.append((dz / L, -dx / L))        # inward for a clockwise profile
    return out


def offset(pr, d, floor_flat=True):
    """Offset a profile inward by d (negative = outward) with mitred corners."""
    ns = seg_normals(pr); out = []
    for k in range(len(pr)):
        if k == 0 or k == len(pr) - 1:
            n = ns[0] if k == 0 else ns[-1]
            if floor_flat:
                n = (1, 0) if k == 0 else (-1, 0)
                out.append((pr[k][0] + n[0] * d, pr[k][1])); continue
            out.append((pr[k][0] + n[0] * d, pr[k][1] + n[1] * d)); continue
        n1, n2 = ns[k - 1], ns[k]
        s = 1 + n1[0] * n2[0] + n1[1] * n2[1]
        out.append((pr[k][0] + (n1[0] + n2[0]) / s * d, pr[k][1] + (n1[1] + n2[1]) / s * d))
    return out


def arclen(pr):
    s = [0.0]
    for k in range(1, len(pr)):
        s.append(s[-1] + math.hypot(pr[k][0] - pr[k - 1][0], pr[k][1] - pr[k - 1][1]))
    return s


def P3(p, y):
    return Vector((p[0], p[2] if len(p) > 2 else y, p[1]))


def shell(secs, matfn, ext=0.0, extfn=None, belly=False, holes=None):
    """Loft the interior skin between sections [(y, profile)] (increasing y), inward faces, arc-length UVs.
    matfn(i, j) -> material or None.  ext>0 also emits an outward hull skin offset by ext where extfn(i, j).
    holes: {(i, j): [(yc, zc, r)]} replaces that (vertical) face with a planar fill with round holes."""
    holes = holes or {}
    for i in range(len(secs) - 1):
        (ya, pa), (yb, pb) = secs[i], secs[i + 1]
        sa, sb = arclen(pa), arclen(pb)
        n = len(pa)
        for j in range(n - 1):
            m = matfn(i, j)
            if m is None:
                continue
            t = TILE.get(m.name, 1.0)
            A0, A1, B0, B1 = P3(pa[j], ya), P3(pa[j + 1], ya), P3(pb[j], yb), P3(pb[j + 1], yb)

            def uv(p, s, S, x):
                if j == 4:
                    return (p.x / t, p.y / t)
                if j < 4:
                    return (p.y / t, s / t)
                return (-p.y / t, (S - s) / t)
            if (i, j) in holes:
                side = -1 if j < 4 else 1
                xw = A0.x
                outer = [A0, B0, B1, A1]
                loops = [outer]
                for (yc, zc, r) in holes[(i, j)]:
                    loops.append([Vector((xw, yc + r * math.cos(k / 20 * 2 * math.pi), zc + r * math.sin(k / 20 * 2 * math.pi))) for k in range(20)])
                s0 = sa[j] - pa[j][1]
                fill(m, loops, (-side, 0, 0),
                     uvfn=lambda pts, s0=s0, side=side: [((p.y if side < 0 else -p.y) / t, (s0 + p.z) / t) for p in pts])
            else:
                MBX.face(m, [A0, B0, B1, A1], [uv(A0, sa[j], sa[-1], A0.x), uv(B0, sb[j], sb[-1], B0.x),
                                                 uv(B1, sb[j + 1], sb[-1], B1.x), uv(A1, sa[j + 1], sa[-1], A1.x)])
        if ext > 0:
            oa, ob = offset(pa, -ext, False), offset(pb, -ext, False)
            for j in range(n - 1):
                if extfn and not extfn(i, j):
                    continue
                q = [P3(oa[j], ya), P3(oa[j + 1], ya), P3(ob[j + 1], yb), P3(ob[j], yb)]
                poly(M_['hull'], q)
            if belly:
                poly(M_['hull'], [P3(oa[-1], ya), P3(oa[0], ya), P3(ob[0], yb), P3(ob[-1], yb)])


def rib(y, pr, depth, thick, m, segs=None, floor_flat=True):
    """Structural frame following the profile at y: a band protruding `depth` inward, `thick` along Y."""
    inner = offset(pr, depth, floor_flat)
    segs = range(len(pr) - 1) if segs is None else segs
    t = TILE.get(m.name, 1.0)
    for j in segs:
        o0, o1, i0, i1 = pr[j], pr[j + 1], inner[j], inner[j + 1]
        for (yy, sgn) in ((y - thick / 2, -1), (y + thick / 2, 1)):
            q = [P3(o0, yy), P3(o1, yy), P3(i1, yy), P3(i0, yy)]
            poly(m, q if sgn > 0 else q[::-1])
        q = [P3(i0, y - thick / 2), P3(i1, y - thick / 2), P3(i1, y + thick / 2), P3(i0, y + thick / 2)]
        poly(m, q)
    return inner


def floor_strip(secs, m, x0f=None, x1f=None, z=0.0):
    """Floor quads between consecutive sections; x0f/x1f(hw) -> x bounds (default full width)."""
    for i in range(len(secs) - 1):
        (ya, pa), (yb, pb) = secs[i], secs[i + 1]
        ha, hb = pa[-1][0], pb[-1][0]
        xa0, xa1 = (x0f(ha), x1f(ha)) if x0f else (-ha, ha)
        xb0, xb1 = (x0f(hb), x1f(hb)) if x0f else (-hb, hb)
        poly(m, [(xa0, ya, z), (xa1, ya, z), (xb1, yb, z), (xb0, yb, z)])


def wall_cols(secs, inset=.05, top=13.0):
    for i in range(len(secs) - 1):
        (ya, pa), (yb, pb) = secs[i], secs[i + 1]
        hw = min(pa[-1][0], pb[-1][0]) - inset
        col_box(-hw - 8, ya, 0, -hw, yb, top); col_box(hw, ya, 0, hw + 8, yb, top)


# ------------------------------------------------------------------ doors / bulkheads
def door_outline(hw, h, ch, d=0.0, low=.2):
    hw2, h2, ch2 = hw + d, h + d, ch + d * .414
    return [(-hw2 + low, 0), (-hw2, low), (-hw2, h2 - ch2), (-hw2 + ch2, h2), (hw2 - ch2, h2), (hw2, h2 - ch2), (hw2, low), (hw2 - low, 0)]


def bulkhead(y, t, profA, profB, hw, h, ch=.6, frame=.5):
    """Wall at [y, y+t] between room A (y<) and room B (y>) with a chamfered door and heavy surrounds both sides."""
    for (yy, pr, sgn) in ((y, profA, -1), (y + t, profB, 1)):
        fo = door_outline(hw, h, ch, frame)
        loop = [P3(p, yy) for p in pr] + [P3(p, yy) for p in fo[::-1]]
        fill(M_['wall'], [loop], (0, sgn, 0))
        # heavy chamfered surround: wall plane -> protruding frame face -> chamfer into the jamb
        Ls = [(door_outline(hw, h, ch, frame), yy), (door_outline(hw, h, ch, frame - .14), yy + sgn * .2),
              (door_outline(hw, h, ch, .14), yy + sgn * .2), (door_outline(hw, h, ch, 0), yy + sgn * .04)]
        for k in range(len(Ls) - 1):
            (la, ya), (lb, yb) = Ls[k], Ls[k + 1]
            mm = M_['frame'] if k < 2 else M_['frame_light']
            for j in range(len(la) - 1):
                q = [P3(la[j], ya), P3(la[j + 1], ya), P3(lb[j + 1], yb), P3(lb[j], yb)]
                poly(mm, q if sgn > 0 else q[::-1])
        # light bar over the door and status lamps on the frame
        part(bl.box('doorlight', (hw * 1.1, .05, .07), (0, yy + sgn * .21, h + frame * .55), M_['lightc']))
        for sx in (-1, 1):
            part(bl.box('doorlamp', (.06, .05, .5), (sx * (hw + frame * .55), yy + sgn * .21, h * .55), M_['cyan']))
    # jamb: hazard stripes on the sides, frame metal on the head
    jo = door_outline(hw, h, ch, 0)
    for j in range(len(jo) - 1):
        mm = M_['hazard'] if j in (1, 5) else M_['frame']
        q = [P3(jo[j], y + .04), P3(jo[j + 1], y + .04), P3(jo[j + 1], y + t - .04), P3(jo[j], y + t - .04)]
        poly(mm, q)
    # door leaves parked in the jamb head (split door, retracted up into the frame)
    part(bl.box('threshold', (hw * 2 - .3, t - .1, .02), (0, y + t / 2, .01), M_['grate']))
    col_box(-30, y - .25, 0, -hw, y + t + .25, 16); col_box(hw, y - .25, 0, 30, y + t + .25, 16)
    col_box(-hw, y - .25, h, hw, y + t + .25, 16)


# ------------------------------------------------------------------ details
def decal(cell, c, normal, up, w, h, m=None):
    c, n, up = Vector(c), Vector(normal).normalized(), Vector(up).normalized()
    r = up.cross(n)
    c = c + n * .012
    col, row = cell % 4, cell // 4
    u0, v0 = col / 4, 1 - (row + 1) / 4
    pts = [c - r * w / 2 - up * h / 2, c + r * w / 2 - up * h / 2, c + r * w / 2 + up * h / 2, c - r * w / 2 + up * h / 2]
    MBX.face(m or M_['stencil'], pts, [(u0 + .01, v0 + .01), (u0 + .24, v0 + .01), (u0 + .24, v0 + .24), (u0 + .01, v0 + .24)])


ST = {s: i for i, s in enumerate(['01', '02', '03', 'D-2', 'ARROW', 'CHEVRON', 'BAY 1', 'HAZ', 'AFT', 'FWD', 'PWR', 'O2', 'LIFT', 'MAX 4T', 'CORE', 'X'])}


def pipe_run(x, z, y0, y1, r, m, clamps=(), clamp_m=None):
    part(bl.cyl('pipe', r, y1 - y0, (x, (y0 + y1) / 2, z), m, 12, rot=(R90, 0, 0)))
    for yc in clamps:
        part(bl.cyl('clamp', r + .025, .08, (x, yc, z), clamp_m or M_['gunmetal'], 12, rot=(R90, 0, 0)))


def cable_tray(y0, y1, x, z, w=.7):
    L = y1 - y0; yc = (y0 + y1) / 2
    part(bl.box('tray', (w, L, .03), (x, yc, z), M_['frame']))
    for sx in (-1, 1):
        part(bl.box('trayside', (.03, L, .12), (x + sx * w / 2, yc, z + .05), M_['frame']))
    for k, mm in enumerate((M_['rubber'], M_['pipe_r'], M_['rubber'], M_['pipe_b'], M_['rubber'])):
        part(bl.cyl('cable', .028, L, (x - w * .35 + k * w * .175, yc, z + .045), mm, 6, rot=(R90, 0, 0)))
    for yy in frange(y0 + .5, y1, 1.0):
        part(bl.box('hanger', (.03, .03, .4), (x - w / 2 - .02, yy, z + .2), M_['steel']))
        part(bl.box('hanger', (.03, .03, .4), (x + w / 2 + .02, yy, z + .2), M_['steel']))


def frange(a, b, s):
    out = []; v = a
    while v <= b + 1e-6:
        out.append(v); v += s
    return out


def screen_panel(kind, w, h, loc, tilt=0.0, yaw=0.0, bezel=True):
    o = props.screen(kind, w, h, loc, tilt, yaw, name='scr_' + kind)
    part(o)
    if bezel:
        n = Vector((math.sin(yaw) * math.cos(tilt), -math.cos(yaw) * math.cos(tilt), math.sin(tilt)))
        b = bl.box('bezel', (w + .08, .04, h + .08), Vector(loc) - n * .025, M_['dark'], rot=(-tilt, 0, yaw))
        part(b)
    return o


def lamp_strip(p0, p1, m=None, w=.12, d=.04, up=(0, 0, -1)):
    beam(p0, p1, w, d, m or M_['lightp'], up)


# ------------------------------------------------------------------ build
def main():
    global M_
    bl.reset()
    M_ = m = materials()

    # ================= BRIDGE (cockpit) =================
    BR = [(-24.2, None), (-22.6, prof(3.7, 3.1, bh=1.0, bv=.8)), (-21.0, prof(4.7, 3.7, bh=1.2, bv=.9)),
          (-19.0, prof(5.6, 4.2, bh=1.4, bv=1.0)), (-17.0, prof(6.2, 4.5, bh=1.5, bv=1.0)),
          (-15.0, prof(6.4, 4.6, bh=1.5, bv=1.0)), (-13.0, prof(6.4, 4.6, bh=1.5, bv=1.0))]
    # leaning nose cap: points at the sill and below sit at y=-24.2, the canopy top leans back to -23.5
    cap = prof(2.7, 2.5, bh=.9, bv=.7)
    cap = [(x, z, -24.2 + max(0.0, z - 1.1) / (2.5 - 1.1) * .7) for (x, z) in cap]
    BR[0] = (-24.2, cap)

    def br_mat(i, j):
        y = BR[i][0]
        if j in (0, 8):
            return m['wall_lower']
        if j in (1, 7):
            return m['wall']
        if j in (2, 6):
            return m['glass'] if y < -15.5 else m['wall']
        if j in (3, 5):
            return m['glass'] if y < -14.5 else m['padded']
        return m['glass'] if y < -19.5 else m['ceil']
    shell(BR, br_mat, ext=.3, extfn=lambda i, j: br_mat(i, j).name != 'window_glass', belly=True)
    # front cap: lower wall + leaning glass pane
    c3 = [P3(p, 0) for p in cap]
    fill(m['wall'], [[c3[0], c3[1], c3[2], c3[7], c3[8], c3[9]]], (0, 1, 0))
    fill(m['glass'], [c3[2:8]], (0, 1, 0))
    # canopy mullions: ring frames at every section + longitudinal ribs along the glass edges
    for (y, pr) in BR[1:-1]:
        rib(y, pr, .13, .14, m['frame'])
    for i in range(len(BR) - 1):
        (ya, pa), (yb, pb) = BR[i], BR[i + 1]
        for j in range(2, 8):
            a, b = P3(pa[j], ya), P3(pb[j], yb)
            if br_mat(i, min(j, 8)).name == 'window_glass' or br_mat(i, max(j - 1, 0)).name == 'window_glass':
                cen = Vector((0, (a.y + b.y) / 2, 1.6))
                beam(a, b, .13, .13, m['frame'], up=(cen - (a + b) / 2).normalized())
    for k in range(2, 7):   # frame around the front pane
        beam(c3[k], c3[k + 1], .13, .13, m['frame'], up=(0, 1, 0))
    beam(c3[7], c3[2], .16, .16, m['frame'], up=(0, 1, 0))
    beam(c3[4] + Vector((0, 0, 0)), Vector((0, -24.2, 1.1)), .08, .08, m['frame'], up=(0, 1, 0))  # centre post
    # floor: deck plates, rubber runner, grating ring around the dais
    floor_strip(BR, m['deck'])
    floor_strip(BR, m['mat'], lambda hw: -1.1, lambda hw: 1.1, z=.006)
    wall_cols(BR, .25)
    col_box(-6, -26, 0, 6, -24.2, 6)
    # nose cone (exterior, below the canopy sill) visible through the forward glass
    nose = []
    ocap = offset([(x, z) for (x, z, _) in cap], -.3, False)
    base = [ocap[2], ocap[1], ocap[0], ocap[9], ocap[8], ocap[7]]   # sill L .. belly .. sill R
    for (y, sx, zt, zb) in ((-24.2, 1.0, 0, 0), (-26.0, .82, -.15, .25), (-28.2, .5, -.5, .6), (-30.0, .18, -.85, .9)):
        ring = [(p[0] * sx, y, (p[1] + zb if p[1] < .5 else p[1] + zt)) for p in base]
        ring += [(base[-1][0] * sx * .6, y, base[-1][1] + .35 + zt), (base[0][0] * sx * .6, y, base[0][1] + .35 + zt)]
        nose.append([Vector(p) for p in ring])
    for i in range(len(nose) - 1):
        a, b = nose[i], nose[i + 1]
        for k in range(len(a)):
            poly(m['hull'], [a[k], a[(k + 1) % len(a)], b[(k + 1) % len(a)], b[k]])
    poly(m['hull'], nose[-1], flip=False)
    # dais + captain's chair + arc console
    part(bl.cyl('dais', 1.75, .2, (0, -17.0, .1), m['frame'], 8, bevel=.03))
    part(bl.torus('dais_ring', 1.68, .025, (0, -17.0, .205), m['cyan'], maj=48, mn=5))
    chair = props.captain_chair((0, -17.0, .2), 0); solid(chair)
    SEATS.append(dict(pos=to3((0, -17.05, .2)), yaw=yaw3(0, -1), id='captain'))
    angs = [-60, -30, 0, 30, 60]
    kinds = ['status', 'radar', 'nav', 'graph', 'data']
    arc = []
    for a in frange(-72, 72, 12):
        r = math.radians(a)
        arc.append((math.sin(r), -math.cos(r)))
    r0, r1 = 2.35, 2.95
    for k in range(len(arc) - 1):
        (s0, c0), (s1, c1) = arc[k], arc[k + 1]
        cy = -17.0
        pts = lambda rr, s, c: Vector((s * rr, cy + c * rr, 0))
        # console body: inner face (toward the chair), sloped desk top, outer face
        prof_c = [(r0, 0), (r0, .78), (r0 - .08, .86), (r0 + .25, .95), (r1, 1.12), (r1, 0)]
        for q in range(len(prof_c) - 1):
            (ra, za), (rb, zb) = prof_c[q], prof_c[q + 1]
            mm = m['hull'] if q in (2, 3) else m['frame']
            A = [pts(ra, s0, c0) + Vector((0, 0, za)), pts(rb, s0, c0) + Vector((0, 0, zb)),
                 pts(rb, s1, c1) + Vector((0, 0, zb)), pts(ra, s1, c1) + Vector((0, 0, za))]
            poly(mm, A)
        if k == 0 or k == len(arc) - 2:
            ss, cc = (s0, c0) if k == 0 else (s1, c1)
            poly(m['frame'], [pts(rr, ss, cc) + Vector((0, 0, zz)) for (rr, zz) in prof_c])
        col_box(min(s0 * r0, s1 * r0, s0 * r1, s1 * r1), min(cy + c0 * r1, cy + c1 * r1, cy + c0 * r0, cy + c1 * r0), 0,
                max(s0 * r0, s1 * r0, s0 * r1, s1 * r1), max(cy + c0 * r1, cy + c1 * r1, cy + c0 * r0, cy + c1 * r0), 1.2)
    for (a, kind) in zip(angs, kinds):
        r = math.radians(a); s, c = math.sin(r), -math.cos(r)
        yaw = math.pi + r   # facing the chair
        base_ = Vector((s * 2.8, -17.0 + c * 2.8, 1.38))
        screen_panel(kind, .74, .46, base_, tilt=.35, yaw=yaw)
        part(bl.box('scrpost', (.08, .08, .3), Vector((s * 2.85, -17.0 + c * 2.85, 1.1)), m['frame']))
        kp = Vector((s * 2.62, -17.0 + c * 2.62, 1.045))
        o = props.screen('keys', .5, .2, kp, tilt=R90 - .22, yaw=yaw, name='arckeys'); part(o)
    # nav holo projector ahead of the console, between the two pilot seats
    part(bl.cyl('nav_emitter', .42, .9, (0, -21.2, .45), m['frame'], 8, bevel=.02))
    part(bl.cyl('nav_lens', .34, .03, (0, -21.2, .915), m['screen'], 24))
    part(bl.torus('nav_ring', .36, .02, (0, -21.2, .93), m['cyan'], maj=32, mn=4))
    col_box(-.45, -21.65, 0, .45, -20.75, 1.0)
    bl.sphere('nav_holo', .45, (0, -21.2, 1.75), m['holo'], 20, 12)
    for sx in (-1, 1):   # pilot seats in front of the dashboard
        pc = props.captain_chair((sx * 2.0, -22.0, 0), 0, name='pilot_chair', side_screen=False); solid(pc)
        SEATS.append(dict(pos=to3((sx * 2.0, -22.05, 0)), yaw=yaw3(0, -1), id='pilot_%s' % ('L' if sx < 0 else 'R')))
    # dashboard along the sill, wrapping the canopy (follows the tapering walls)
    dash = [(BR[i][0], BR[i][1]) for i in range(0, 5)]
    for i in range(len(dash) - 1):
        (ya, pa), (yb, pb) = dash[i], dash[i + 1]
        for sx in (-1, 1):
            wa, wb = abs(pa[2][0]), abs(pb[2][0])
            top = [Vector((sx * wa, ya, 1.08)), Vector((sx * (wa - .6), ya, 1.0)), Vector((sx * (wb - .6), yb, 1.0)), Vector((sx * wb, yb, 1.08))]
            poly(m['hull'], top)
            front = [Vector((sx * (wa - .6), ya, 1.0)), Vector((sx * (wa - .6), ya, .72)), Vector((sx * (wb - .6), yb, .72)), Vector((sx * (wb - .6), yb, 1.0))]
            poly(m['frame'], front)
            under = [Vector((sx * (wa - .6), ya, .72)), Vector((sx * (wa - .05), ya, .45)), Vector((sx * (wb - .05), yb, .45)), Vector((sx * (wb - .6), yb, .72))]
            poly(m['frame'], under)
            if i in (1, 2, 3):
                mid = Vector((sx * ((wa + wb) / 2 - .32), (ya + yb) / 2, 1.05))
                o = props.screen('keys' if i != 2 else 'data', .9, .3, mid + Vector((0, 0, .01)), tilt=R90 - .12, yaw=-sx * R90, name='dashscr')
                part(o)
    # front dashboard under the nose pane
    part(bl.box('frontdash', (4.6, .6, .12), (0, -23.85, 1.02), m['hull'], bevel=.02))
    part(bl.box('frontdash_body', (4.4, .5, 1.0), (0, -23.9, .5), m['frame'], bevel=.02))
    for x in (-1.2, 0, 1.2):
        screen_panel('graph' if x else 'radar', .9, .34, (x, -23.62, 1.25), tilt=.6, yaw=math.pi)
    col_box(-2.4, -24.2, 0, 2.4, -23.55, 1.1)
    # overhead instrument cluster hanging from the opaque ceiling, angled down at the chair
    for (x, kind, yaw) in ((-1.25, 'data', math.pi - .35), (0, 'status', math.pi), (1.25, 'graph', math.pi + .35)):
        p0 = Vector((x, -18.4 + abs(x) * .15, 3.3))
        screen_panel(kind, .8, .48, p0, tilt=-.75, yaw=yaw)
        part(bl.box('hang', (.05, .05, 1.2), p0 + Vector((0, .2, .75)), m['steel']))
    part(bl.box('ovh_frame', (3.6, .2, .12), (0, -18.15, 3.62), m['frame']))
    # side terminals at the rear of the bridge
    for sx in (-1, 1):
        t = props.terminal('bridge_console', (sx * 5.45, -14.0, 0), -sx * R90, kind='radar' if sx < 0 else 'status'); solid(t)
    # ceiling light strips over the rear (opaque) part + cyan floor kerbs
    for sx in (-1, 1):
        lamp_strip((sx * 1.5, -13.4, 4.56), (sx * 1.5, -15.6, 4.56))
    for i in range(len(BR) - 1):
        (ya, pa), (yb, pb) = BR[i], BR[i + 1]
        for side in (0, 9):
            a, b = P3(pa[side], ya), P3(pb[side], yb)
            beam(a + Vector((0, 0, .04)), b + Vector((0, 0, .04)), .05, .03, m['cyan'])
    decal(ST['D-2'], (-6.38, -13.9, 2.7), (1, 0, 0), (0, 0, 1), .8, .8)
    decal(ST['FWD'], (6.38, -13.9, 2.7), (-1, 0, 0), (0, 0, 1), .8, .8)
    STATIONS['captain'] = dict(pos=to3((0, -14.6, 0)), look=to3((0, -24, 1.5)), label='Captain’s Chair', verb='Navigate',
                               seat=to3((0, -17.05, .2)), at=to3((0, -17.0, .9)), rad=1.75)
    LIGHTS.append(dict(kind='spot', name='bridge_key', pos=to3((0, -14.2, 4.3)), target=to3((0, -18, 0)), color='#d6e6ff', intensity=40, angle=.95))

    # ================= CORRIDOR 1 (bridge <-> commons) =================
    C1p = prof(2.7, 3.9, a=.45, a2=.5, bh=.8, bv=.7)
    C1 = [(-12.5, C1p), (-10.5, C1p), (-8.5, C1p)]
    bulkhead(-13.0, .5, BR[-1][1], C1p, 1.7, 3.2)
    corridor(C1, C1p, 'fwd')

    # ================= COMMONS =================
    endp = prof(5.4, 4.6, bh=1.4, bv=1.1)
    midp = prof(7.0, 5.0, bh=1.7, bv=1.3)
    ys = [-8.0] + [-6.6 + k * 1.8667 for k in range(7)] + [6.0]
    CM = [(ys[0], endp)] + [(y, midp) for y in ys[1:-1]] + [(ys[-1], endp)]
    bays = [(ys[k] + ys[k + 1]) / 2 for k in range(1, 7)]
    port_l = [bays[0], bays[2], bays[3], bays[4], bays[5]]
    port_r = [bays[0], bays[2], bays[3]]
    PR, PZ = .42, 1.75
    holes = {}
    for k in range(1, 7):
        yc = bays[k - 1]
        if yc in port_l:
            holes[(k, 2)] = [(yc, PZ, PR)]
        if yc in port_r:
            holes[(k, 6)] = [(yc, PZ, PR)]

    def cm_mat(i, j):
        if j in (0, 8):
            return m['wall_lower']
        if j in (1, 2, 6, 7):
            return m['wall']
        if j in (3, 5):
            return m['padded']
        return m['ceil']
    bulkhead(-8.5, .5, C1p, endp, 1.7, 3.2)
    shell(CM, cm_mat, holes=holes)
    for (y, pr) in CM[1:-1]:
        rib(y, pr, .16, .2, m['frame'])
    floor_strip(CM, m['deck'])
    poly(m['mat'], [(-3.6, -5.4, .006), (3.6, -5.4, .006), (3.6, 3.4, .006), (-3.6, 3.4, .006)])
    for (a, b) in (((-3.6, -5.4), (3.6, -5.4)), ((3.6, -5.4), (3.6, 3.4)), ((3.6, 3.4), (-3.6, 3.4)), ((-3.6, 3.4), (-3.6, -5.4))):
        beam((a[0], a[1], .02), (b[0], b[1], .02), .08, .03, m['frame_light'])
    wall_cols(CM, .25)
    # portholes: thick hull tube, glass, bezels
    for (sx, lst) in ((-1, port_l), (1, port_r)):
        for yc in lst:
            tube_x(sx * 7.0, sx * 7.75, yc, PZ, PR)
            PORTHOLES.append(dict(pos=to3((sx * 7.0, yc, PZ)), normal=dir3((sx, 0, 0)), r=PR))
    # ceiling: light ring above the holo table + strips along the chamfer edges
    part(bl.torus('ceil_ring', 2.3, .06, (0, -1.0, 4.93), m['lightp'], maj=64, mn=6))
    part(bl.cyl('ceil_disc', 2.6, .1, (0, -1.0, 4.97), m['frame'], 8))
    for sx in (-1, 1):
        lamp_strip((sx * 5.25, -6.6, 4.93), (sx * 5.25, 4.6, 4.93))
        for (y, pr) in CM[1:-1]:
            part(bl.box('ribglow', (.04, .1, .5), (sx * 6.82, y, 3.0), m['amber']))
    LIGHTS.append(dict(kind='point', name='commons_a', pos=to3((0, -4.2, 4.3)), color='#ffe8cc', intensity=16, dist=13))
    LIGHTS.append(dict(kind='point', name='commons_b', pos=to3((0, 2.6, 4.3)), color='#ffe8cc', intensity=16, dist=13))
    ht = props.holo_table((0, -1.0, 0)); solid(ht)
    STATIONS['briefing'] = dict(pos=to3((0, 1.3, 0)), look=to3((0, -1.0, 1.2)), label='Briefing Table', verb='Contracts & Field Guide',
                                at=to3((0, -1.0, .9)), rad=1.46)
    wy = bays[1]
    pod = props.locker_pod((-5.4, wy, 0), 0)
    STATIONS['wardrobe'] = dict(pos=to3((-3.6, wy, 0)), look=to3((-5.4, wy, 1.2)), label='Wardrobe Pod', verb='Customize',
                                stand=to3((-5.4, wy, .15)), at=to3((-5.4, wy, 1.4)), rad=1.1)
    for i in range(5):
        a = math.pi * .35 + i * math.pi * .32
        col_box(-5.4 + math.cos(a) * .95 - .15, wy + math.sin(a) * .95 - .15, 0, -5.4 + math.cos(a) * .95 + .15, wy + math.sin(a) * .95 + .15, 2.6)
    t = props.terminal('ST_engineering', (5.95, wy, 0), -R90, kind='status'); solid(t)
    STATIONS['engineering'] = dict(pos=to3((4.5, wy, 0)), look=to3((6.0, wy, 1.3)), label='Engineering Terminal', verb='Settings & Controls',
                                   at=to3((5.95, wy, .9)), rad=.62)
    ry = bays[4]
    t = props.terminal('ST_record', (5.95, ry, 0), -R90, kind='amber'); solid(t)
    STATIONS['record'] = dict(pos=to3((4.5, ry, 0)), look=to3((6.0, ry, 1.3)), label='Service Record', verb='Stats',
                              at=to3((5.95, ry, .9)), rad=.62)
    for by in (bays[4], bays[5]):
        props.bench((-6.05, by, 0), R90)      # back to the wall, facing +X
        col_box(-6.4, by - .95, 0, -5.75, by + .95, .95)
        for o in (-.45, .45):
            SEATS.append(dict(pos=to3((-5.95, by + o, 0)), yaw=yaw3(1, 0), id='bench'))
    # lockers and a wall screen on the right
    for k in range(3):
        part(bl.box('locker', (.5, .56, 2.1), (6.25, bays[5] - .6 + k * .6, 1.05), m['frame_light'], bevel=.02))
        part(bl.box('locker_vent', (.02, .3, .12), (5.99, bays[5] - .6 + k * .6, 1.8), m['dark']))
        part(bl.box('locker_lamp', (.02, .05, .05), (5.99, bays[5] - .6 + k * .6, 1.2), m['green'] if k != 1 else m['amber']))
    col_box(5.95, bays[5] - .95, 0, 7.0, bays[5] + .95, 2.2)
    screen_panel('graph', 1.1, .6, (-6.93, bays[3], 3.0), tilt=0, yaw=R90)
    decal(ST['03'], (6.93, bays[2], 3.0), (-1, 0, 0), (0, 0, 1), .7, .7)
    decal(ST['O2'], (-6.93, bays[2], 3.0), (1, 0, 0), (0, 0, 1), .6, .6, m['stencil_y'])

    # ================= CORRIDOR 2 (commons <-> hangar) =================
    C2p = prof(3.7, 5.4, a=.5, a2=.55, bh=.9, bv=.8)
    C2 = [(6.5, C2p), (8.5, C2p), (10.5, C2p)]
    bulkhead(6.0, .5, endp, C2p, 1.9, 3.4)
    corridor(C2, C2p, 'aft')

    # ================= HANGAR =================
    HP = prof(13.0, 11.0, a=.8, a2=1.0, sill=4.6, bh=3.0, bv=3.0)
    hys = [11.0, 15.0, 19.0, 23.0, 27.0, 31.0, 35.0, 39.5]
    HG = [(y, HP) for y in hys]
    bulkhead(10.5, .5, C2p, HP, 2.6, 4.3, ch=.8)

    def hg_mat(i, j):
        if j in (0, 8):
            return m['wall_lower']
        if j in (1, 2, 6, 7):
            return m['wall']
        return m['ceil']
    shell(HG, hg_mat)
    for y in hys[1:-1]:
        rib(y, HP, .5, .5, m['frame'])
    for y in frange(13.0, 37.0, 4.0):
        rib(y, HP, .16, .2, m['frame_light'], segs=range(1, 8))
    mouth = rib(39.0, HP, 1.1, 1.0, m['frame'])
    floor_strip(HG, m['deck'])
    poly(m['grate'], [(-1.4, 11.0, .006), (1.4, 11.0, .006), (1.4, 38.4, .006), (-1.4, 38.4, .006)])
    for sx in (-1, 1):
        beam((sx * 1.55, 11.2, .015), (sx * 1.55, 38.4, .015), .1, .02, m['pipe_y'])
    wall_cols(HG, .55)
    # bay mouth: lip, hazard edge, force field, emitters
    part(bl.box('lip', (24.2, .9, 2.0), (0, 39.05, -1.0), m['frame']))
    o = part(bl.box('lip_hazard', (21.6, .6, .02), (0, 38.75, .012), m['hazard']))
    fpts = [P3(p, 39.35) for p in offset(HP, 1.1)]
    fill(m['field'], [fpts], (0, -1, 0), uvfn=lambda pts: [(p.x / 22.0 + .5, p.z / 9.9) for p in pts])
    for j in range(len(fpts) - 1):
        beam(fpts[j] + Vector((0, -.45, 0)), fpts[j + 1] + Vector((0, -.45, 0)), .1, .06, m['cyan'], up=(0, -1, 0))
    col_box(-14, 38.6, 0, 14, 40.5, 12)
    LIGHTS.append(dict(kind='point', name='bay_field', pos=to3((0, 36.5, 3.5)), color='#58b4ff', intensity=22, dist=20))
    # catwalks at the sill line with railings, brackets on the ribs
    for sx in (-1, 1):
        x_in = sx * 10.9; x_w = sx * 12.55
        part(bl.box('catwalk', (1.65, 27.6, .08), ((x_in + x_w) / 2, 25.2, 4.6), m['grate']))
        part(bl.box('catwalk_edge', (.08, 27.6, .2), (x_in, 25.2, 4.56), m['frame']))
        part(bl.box('rail', (.06, 27.6, .06), (x_in, 25.2, 5.65), m['pipe_y']))
        part(bl.box('rail_mid', (.04, 27.6, .04), (x_in, 25.2, 5.15), m['steel']))
        for yy in frange(11.6, 38.6, 1.5):
            part(bl.box('post', (.05, .05, 1.05), (x_in, yy, 5.12), m['steel']))
        for y in hys[1:-1]:
            beam((x_w, y, 4.5), (x_in, y, 4.5), .3, .25, m['frame'])
            beam((sx * 12.9, y, 3.2), (x_in + sx * .3, y, 4.45), .2, .15, m['frame'])
        # big pipe bundle along the wall under the catwalk
        for (z, r, mm) in ((3.4, .16, m['pipe_y']), (3.0, .11, m['steel']), (2.7, .09, m['pipe_r'])):
            pipe_run(sx * 12.75, z, 11.3, 38.3, r, mm, clamps=hys[1:-1])
        # floodlights on the heavy frames
        for y in (15.0, 23.0, 31.0):
            p0 = Vector((sx * 12.3, y - .4, 8.3))
            part(bl.box('flood_arm', (.6, .15, .15), p0 + Vector((sx * .2, 0, .25)), m['frame']))
            part(bl.box('flood', (.5, .4, .32), p0, m['dark'], bevel=.03, rot=(0, sx * .6, 0)))
            part(bl.box('flood_lens', (.42, .34, .02), p0 + Vector((-sx * .12, 0, -.15)), m['lightp'], rot=(0, sx * .6, 0)))
        # ceiling light strips between the frames
        for (ya, yb) in zip(hys[:-1], hys[1:]):
            lamp_strip((sx * 4.0, ya + .6, 10.93), (sx * 4.0, yb - .6, 10.93), m['lightc'], w=.25)
        # kerb glow along the floor edges
        beam((sx * 12.2, 11.2, .05), (sx * 12.2, 38.5, .05), .05, .04, m['cyan'])
    for (x, y) in ((-12.3, 15.0), (12.3, 31.0), (12.3, 15.0), (-12.3, 31.0)):
        LIGHTS.append(dict(kind='spot', name='hangar_flood', pos=to3((x, y - .4, 8.1)), target=to3((x * .35, y + 2.5, 0)),
                           color='#ffe6c4', intensity=150, angle=.72))
    # gantry crane on rails at the top of the walls
    for sx in (-1, 1):
        part(bl.box('crane_rail', (.35, 28, .3), (sx * 12.6, 25.0, 8.15), m['frame']))
    part(bl.box('crane_bridge', (25.0, .6, .8), (0, 27.0, 8.6), m['yellow'], bevel=.04))
    part(bl.box('crane_bridge2', (25.0, .6, .8), (0, 28.4, 8.6), m['yellow'], bevel=.04))
    part(bl.box('hoist', (1.2, 2.2, .9), (-2.0, 27.7, 7.9), m['frame'], bevel=.05))
    part(bl.box('hoist_lamp', (.4, .04, .1), (-2.0, 26.58, 7.95), m['amber']))
    part(bl.cyl('hoist_cable', .03, 3.0, (-2.0, 27.7, 5.95), m['steel'], 6))
    part(bl.torus('hook', .22, .05, (-2.0, 27.7, 4.3), m['yellow'], rot=(R90, 0, 0), maj=16, mn=6))
    part(bl.box('hook_block', (.4, .3, .5), (-2.0, 27.7, 4.75), m['dark'], bevel=.03))
    # markings
    for y in (14.0, 34.0):
        decal(ST['ARROW'], (-.0, y, .0), (0, 0, 1), (0, 1, 0), 1.6, 1.6, m['stencil_y'])
    decal(ST['BAY 1'], (0, 16.5, 0), (0, 0, 1), (0, -1, 0), 2.2, 2.2)
    decal(ST['CHEVRON'], (0, 37.2, 0), (0, 0, 1), (0, 1, 0), 2.4, 2.4, m['stencil_y'])
    decal(ST['01'], (-12.97, 21.0, 6.6), (1, 0, 0), (0, 0, 1), 2.4, 2.4)
    decal(ST['02'], (12.97, 21.0, 6.6), (-1, 0, 0), (0, 0, 1), 2.4, 2.4)
    decal(ST['MAX 4T'], (-12.97, 33.0, 6.6), (1, 0, 0), (0, 0, 1), 1.8, 1.8, m['stencil_y'])
    decal(ST['HAZ'], (12.97, 37.0, 2.4), (-1, 0, 0), (0, 0, 1), 1.2, 1.2, m['stencil_y'])
    decal(ST['LIFT'], (-10.0, 28.4, .0), (0, 0, 1), (1, 0, 0), 1.4, 1.4)
    # car pad
    for (sx_, sy_, x, y) in ((6.4, .3, 6, 18.6), (6.4, .3, 6, 25.4), (.3, 7.1, 2.95, 22), (.3, 7.1, 9.05, 22)):
        part(bl.box('hazard_line', (sx_, sy_, .02), (x, y, .01), m['hazard']))
    part(bl.cyl('car_pad', 2.9, .06, (6, 22, .03), m['frame'], 8, bevel=.02))
    part(bl.torus('car_pad_ring', 2.75, .05, (6, 22, .07), m['cyan'], maj=48, mn=6))
    STATIONS['garage'] = dict(pos=to3((2.5, 22, 0)), look=to3((6, 22, .8)), label='Hover Car', verb='Garage', car=to3((6, 22, .0)),
                              at=to3((6, 22, .7)), rad=2.9)
    col_box(4.9, 19.6, 0, 7.1, 24.4, 1.4)
    rack = props.armory_rack((-12.0, 17.0, 0), R90); solid(rack)
    STATIONS['armory'] = dict(pos=to3((-10.0, 17.0, 0)), look=to3((-12.0, 17.0, 1.3)), label='Armory', verb='Loadout',
                              at=to3((-12.0, 17.0, 1.3)), rad=1.8)
    bench = props.gunsmith_bench((-11.55, 25.0, 0), R90); solid(bench)
    STATIONS['gunsmith'] = dict(pos=to3((-9.9, 25.0, 0)), look=to3((-11.5, 25.0, 1.1)), label='Gunsmith Bench', verb='Upgrade Weapons',
                                at=to3((-11.55, 25.0, 1.0)), rad=1.35)
    # welding cell: robot arm working on an engine nacelle on a stand
    props.welder((-6.0, 31.0, 0), 0); col_box(-6.8, 30.2, 0, -5.2, 31.8, 2.5)
    part(bl.box('stand', (2.6, 1.6, .9), (-6.0, 33.8, .45), m['frame'], bevel=.04)); col_box(-7.3, 33.0, 0, -4.7, 34.6, 3.0)
    tube_y(m['hull'], -6.0, 1.95, [(32.2, .7), (32.4, .95), (33.0, 1.0), (34.8, 1.0), (35.4, .8)], seg=24, cap_end='first', cap_mat=m['frame'])
    part(bl.torus('nacelle_ring', 1.02, .08, (-6.0, 33.0, 1.95), m['brass'], rot=(R90, 0, 0), maj=28, mn=6))
    part(bl.cyl('nacelle_glow', .6, .05, (-6.0, 35.42, 1.95), m['cyan'], 24, rot=(R90, 0, 0)))
    for (x, y) in ((-8.5, 29.0), (-3.5, 29.0)):
        part(bl.box('safety_post', (.1, .1, 1.1), (x, y, .55), m['hazard']))
    LIGHTS.append(dict(kind='weld', name='weld_spark', pos=to3((-6.0, 32.8, 2.0))))
    ld = props.loader((8.5, 34.0, 0), R90 * .5); solid(ld)
    ft = props.fuel_tank((10.4, 13.6, 0), R90); solid(ft)
    for (x, y, n) in ((-9.5, 36.6, 3), (-3.0, 37.2, 2), (10.4, 18.2, 2), (-9.6, 12.6, 2), (3.0, 37.2, 1)):
        for k in range(n):
            solid(props.crate('crate', (x + rnd.uniform(-.1, .1), y, k * 1.2), rnd.uniform(-.2, .2), orange=(k % 2 == 1)))
    for (x, y) in ((10.8, 28.6), (10.8, 29.4), (10.0, 29.0), (-3.2, 12.4)):
        solid(props.barrel('barrel', (x, y, 0)))
    props.bench((11.45, 24.0, 0), -R90)   # crew bench on the right wall, facing -X
    col_box(11.1, 23.05, 0, 11.8, 24.95, .95)
    for o in (-.45, .45):
        SEATS.append(dict(pos=to3((11.35, 24.0 + o, 0)), yaw=yaw3(-1, 0), id='bench'))
    t = props.terminal('bay_console', (11.0, 37.6, 0), -R90, kind='radar'); solid(t)
    t = props.terminal('bay_console', (-11.0, 20.8, 0), -R90 + math.pi, kind='data'); solid(t)

    # ================= EXTERIOR HULL =================
    exterior(m)

    STATIONS['_spawn'] = dict(pos=to3((0, 3.6, 0)), look=to3((0, -1.0, 1.2)))
    export(m)


def corridor(secs, pr, way):
    m = M_
    y0, y1 = secs[0][0], secs[-1][0]

    def mat(i, j):
        if j in (0, 8):
            return m['wall_lower']
        if j in (1, 2, 6, 7):
            return m['wall']
        if j in (3, 5):
            return m['frame']
        return m['ceil']
    shell(secs, mat)
    for (y, _) in secs[1:-1]:
        rib(y, pr, .18, .25, m['frame'])
    for y in frange(y0 + 1.0, y1 - .9, 2.0):
        rib(y, pr, .1, .12, m['frame_light'], segs=range(1, 8))
    hw = pr[-1][0]
    floor_strip(secs, m['deck'])
    poly(m['grate'], [(-.9, y0, .006), (.9, y0, .006), (.9, y1, .006), (-.9, y1, .006)])
    wall_cols(secs, .3)
    W = pr[6][0]; H = pr[4][1]; zc = (pr[3][1] + pr[4][1]) / 2
    xc = (abs(pr[3][0]) + abs(pr[4][0])) / 2
    for sx in (-1, 1):
        # pipes on the upper chamfers with clamps at the frames
        for k, (r, mm) in enumerate(((.07, m['pipe_y']), (.05, m['steel']), (.06, m['pipe_r']))):
            t = (k + 1) / 4
            x = sx * (abs(pr[3][0]) * (1 - t) + abs(pr[4][0]) * t) - sx * .16
            z = pr[3][1] * (1 - t) + pr[4][1] * t - .16
            pipe_run(x, z, y0 + .05, y1 - .05, r, mm, clamps=[y for (y, _) in secs[1:-1]])
        # recessed light strip along the wall top + floor kerb glow
        lamp_strip((sx * (W - .02), y0 + .3, pr[3][1] - .1), (sx * (W - .02), y1 - .3, pr[3][1] - .1), m['lightc'], w=.06, d=.1, up=(-sx, 0, 0))
        beam((sx * (hw - .02), y0, .04), (sx * (hw - .02), y1, .04), .05, .03, m['cyan'])
    cable_tray(y0 + .1, y1 - .1, -.85, H - .5, .7)
    for y in frange(y0 + .5, y1 - .5, 1.0):
        part(bl.box('ceil_lamp', (.6, .25, .04), (.75, y, H - .02), m['lightp']))
    # wall screens and markings
    yc = (y0 + y1) / 2
    screen_panel('data' if way == 'fwd' else 'status', .8, .5, (-W + .03, yc - .9, 1.7), tilt=0, yaw=R90)
    decal(ST['FWD' if way == 'fwd' else 'AFT'], (W - .01, yc - .9, 1.9), (-1, 0, 0), (0, 0, 1), .7, .7)
    decal(ST['ARROW'], (W - .01, yc - .9, 1.35), (-1, 0, 0), (0, -1, 0) if way == 'fwd' else (0, 1, 0), .6, .6, M_['stencil_y'])
    decal(ST['PWR' if way == 'fwd' else 'CORE'], (-W + .01, yc + .9, 2.1), (1, 0, 0), (0, 0, 1), .6, .6)
    if way == 'aft':
        decal(ST['BAY 1'], (0, y1 - 1.2, 0), (0, 0, 1), (0, -1, 0), 1.6, 1.6)
    if way == 'fwd':
        LIGHTS.append(dict(kind='point', name='corridor', pos=to3((0, yc, H - .6)), color='#dfefff', intensity=6, dist=7))


def tube_x(x0, x1, yc, zc, r, seg=20):
    """Porthole: tube through the hull wall, glass pane, bezel rings inside and out."""
    m = M_
    for k in range(seg):
        a0, a1 = k / seg * 2 * math.pi, (k + 1) / seg * 2 * math.pi
        q = [Vector((x0, yc + r * math.cos(a0), zc + r * math.sin(a0))), Vector((x1, yc + r * math.cos(a0), zc + r * math.sin(a0))),
             Vector((x1, yc + r * math.cos(a1), zc + r * math.sin(a1))), Vector((x0, yc + r * math.cos(a1), zc + r * math.sin(a1)))]
        poly(m['frame'], q)
    xm = (x0 + x1) / 2
    poly(m['glass'], [Vector((xm, yc + r * math.cos(k / seg * 2 * math.pi), zc + r * math.sin(k / seg * 2 * math.pi))) for k in range(seg)])
    s = 1 if x0 > 0 else -1
    part(bl.torus('porthole_bezel', r + .05, .06, (x0 - s * .02, yc, zc), m['frame_light'], rot=(0, R90, 0), maj=24, mn=6))
    for k in range(8):
        a = k / 8 * 2 * math.pi
        part(bl.cyl('porthole_bolt', .025, .04, (x0 - s * .05, yc + (r + .13) * math.cos(a), zc + (r + .13) * math.sin(a)), m['steel'], 6, rot=(0, R90, 0)))
    part(bl.torus('porthole_outer', r + .06, .07, (x1 + s * .02, yc, zc), m['hull_dark'], rot=(0, R90, 0), maj=24, mn=6))


def exterior(m):
    """Outer hull envelope around corridors/commons/hangar, wings low on the belly, engine nacelles, nav lights."""
    def env(W, top, bot=-2.0):
        return [(-W + 1.2, bot), (-W, bot + 1.0), (-W, top - 1.8), (-W + 1.8, top), (W - 1.8, top), (W, top - 1.8), (W, bot + 1.0), (W - 1.2, bot)]
    cm_ys = [-6.6 + k * 1.8667 for k in range(7)]
    secs = [(-12.9, env(7.3, 5.3, -1.7)), (-8.3, env(7.75, 5.9))] + [(y, env(7.75, 5.9)) for y in cm_ys] + \
           [(6.2, env(7.75, 5.9)), (10.6, env(14.0, 11.9)), (39.5, env(14.0, 11.9))]
    ports = {}
    bays = [(cm_ys[k] + cm_ys[k + 1]) / 2 for k in range(6)]
    for p in PORTHOLES:
        yc = -p['pos'][2]; side = 1 if p['pos'][0] > 0 else -1
        for k in range(6):
            if abs(bays[k] - yc) < .1:
                ports.setdefault((k + 2, 5 if side > 0 else 1), []).append((yc, p['pos'][1], p['r']))
    for i in range(len(secs) - 1):
        (ya, pa), (yb, pb) = secs[i], secs[i + 1]
        n = len(pa)
        for j in range(n):
            a0, a1 = P3(pa[j], ya), P3(pa[(j + 1) % n], ya)
            b0, b1 = P3(pb[j], yb), P3(pb[(j + 1) % n], yb)
            if (i, j) in ports:
                loops = [[a0, a1, b1, b0]]
                for (yc, zc, r) in ports[(i, j)]:
                    loops.append([Vector((a0.x, yc + r * math.cos(k / 20 * 2 * math.pi), zc + r * math.sin(k / 20 * 2 * math.pi))) for k in range(20)])
                fill(m['hull'], loops, (1 if a0.x > 0 else -1, 0, 0))
            else:
                poly(m['hull'], [a0, a1, b1, b0])
    # front face around the bridge, rear face around the open bay
    bridge_out = [P3(p, -12.9) for p in offset(prof(6.4, 4.6, bh=1.5, bv=1.0), -.32, False)]
    fill(m['hull'], [[P3(p, -12.9) for p in secs[0][1]], bridge_out], (0, -1, 0))
    bay = [P3(p, 39.5) for p in prof(13.0, 11.0, a=.8, a2=1.0, sill=4.6, bh=3.0, bv=3.0)]
    fill(m['hull_dark'], [[P3(p, 39.5) for p in secs[-1][1]], bay], (0, 1, 0))
    # hull dressing seen from the canopy side panes: RCS blocks, radiator strips, comms mast + dish
    for sx in (-1, 1):
        part(bl.box('rcs_block', (.9, 1.4, .9), (sx * 7.55, -11.9, 4.3), m['hull_dark'], bevel=.08))
        for k, (dy, dz) in enumerate(((-.71, 0), (0, .46), (0, -.46))):
            part(bl.cyl('rcs_nozzle', .14, .3, (sx * 7.55, -11.9 + dy, 4.3 + dz) if dy else (sx * 8.0, -11.9, 4.3 + dz),
                        m['frame'], 10, rot=(R90, 0, 0) if dy else (0, R90, 0)))
        for y in frange(-6.0, 4.0, 1.25):
            part(bl.box('radiator', (.12, .9, 1.5), (sx * 7.82, y, 3.2), m['hull_dark'], bevel=.02))
        part(bl.box('sensor_pod', (1.2, 3.0, .7), (sx * 4.0, -9.5, 6.2), m['hull'], bevel=.15))
        part(bl.sphere('sensor_dome', .45, (sx * 4.0, -10.6, 6.5), m['glass'], 16, 8))
    part(bl.cyl('mast', .12, 2.4, (0, -8.0, 7.1), m['frame'], 10))
    part(bl.cyl('dish', 1.1, .25, (0, -8.3, 8.2), m['hull'], 24, r2=.3, rot=(.9, 0, 0)))
    part(bl.sphere('mast_blink', .12, (0, -8.0, 8.35), m['red'], 8, 6))
    part(bl.box('spine', (2.2, 16.0, .5), (0, -2.0, 6.1), m['hull_dark'], bevel=.12))
    # running lights along the hull shoulders
    for sx in (-1, 1):
        beam((sx * 7.8, -12.5, 4.0), (sx * 7.8, 6.0, 4.0), .06, .06, m['cyan'])
        beam((sx * 14.05, 11.5, 9.9), (sx * 14.05, 39.3, 9.9), .08, .08, m['cyan'])
    # wings: low on the belly, swept, visible through the portholes and the bay
    for sx in (-1, 1):
        root = [(-4.0, -1.6, 0), (2.0, -1.0, .45), (14.0, -.95, .5), (30.0, -1.3, .2), (34.0, -1.5, 0)]   # (y, zmid, half-thick)
        tip = [(22.0, -.5, 0), (24.0, -.4, .14), (28.0, -.38, .16), (33.0, -.45, .06), (35.0, -.5, 0)]
        xr, xt = sx * 7.4, sx * 34.0

        def sec(x, pts):
            top = [Vector((x, y, z + t)) for (y, z, t) in pts]
            bot = [Vector((x, y, z - t)) for (y, z, t) in pts][::-1][1:-1]
            return top + bot
        A, B = sec(xr, root), sec(xt, tip)
        nn = len(A)
        for k in range(nn):
            q = [A[k], A[(k + 1) % nn], B[(k + 1) % nn], B[k]]
            poly(m['hull'], q if sx < 0 else q[::-1])
        fill(m['hull_dark'], [B], (sx, 0, 0))
        part(bl.sphere('navlight', .22, (xt, 28.0, -.38), m['green'] if sx > 0 else m['red'], 10, 6))
        # engine nacelle on a pylon over the wing, exhaust visible through the open bay
        nx = sx * 21.0
        tube_y(m['hull'], nx, 1.6, [(26.0, 1.9), (26.4, 2.45), (27.5, 2.65), (44.0, 2.65), (49.5, 2.2), (51.0, 1.9)], seg=28)
        tube_y(m['frame'], nx, 1.6, [(26.0, 1.9), (26.6, 1.6), (27.4, 1.3)], seg=28, cap_end='last', cap_mat=m['dark'])
        tube_y(m['frame'], nx, 1.6, [(51.0, 1.9), (51.0, 1.6), (50.2, 1.5)], seg=28, cap_end='last', cap_mat=m['engine'])
        part(bl.torus('exhaust_ring', 1.75, .1, (nx, 51.0, 1.6), m['engine'], rot=(R90, 0, 0), maj=32, mn=6))
        part(bl.torus('intake_ring', 2.2, .12, (nx, 26.1, 1.6), m['frame_light'], rot=(R90, 0, 0), maj=32, mn=6))
        part(bl.box('pylon', (1.0, 12.0, 2.2), (nx, 34.0, -.4), m['hull'], bevel=.1))
        beam((nx, 26.8, 4.28), (nx, 48.0, 4.28), .12, .08, m['cyan'])


def export(m):
    MBX.build('arch_')
    bpy.context.view_layer.update()
    # screens for the runtime: centre of every face that carries a screen_<kind> material
    screens = {}
    for o in list(bpy.context.scene.objects):
        if o.type != 'MESH':
            continue
        mw = o.matrix_world
        for poly_ in o.data.polygons:
            mn = o.data.materials[poly_.material_index].name if o.data.materials else ''
            if mn.startswith('screen_'):
                c = mw @ poly_.center
                key = (mn[7:], round(c.x, 1), round(c.y, 1), round(c.z, 1))
                screens[key] = 1
    SCREENS = [dict(kind=k[0], pos=to3((k[1], k[2], k[3]))) for k in screens]
    for o in STATIC:
        bl.apply_all(o)
    # join static architecture by material to minimise draw calls
    by_mat = {}
    for o in STATIC:
        if o.hide_render or not o.data.materials:
            continue
        if len(o.data.materials) > 1:
            continue
        by_mat.setdefault(o.data.materials[0].name, []).append(o)
    for k, objs in by_mat.items():
        bl.join(objs, 'arch_' + k)
    # colliders: explicit boxes + prop roots
    cols = list(COLS)

    def aabb(o):
        lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        stack = [o]
        while stack:
            x = stack.pop(); stack.extend(x.children)
            if x.type == 'MESH':
                for c in x.bound_box:
                    w = x.matrix_world @ Vector(c)
                    lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        return lo, hi
    bpy.context.view_layer.update()
    for o in SOLIDS:
        lo, hi = aabb(o)
        if lo.x > hi.x:
            continue
        cols.append([round(lo.x, 3), round(lo.z, 3), round(-hi.y, 3), round(hi.x, 3), round(hi.z, 3), round(-lo.y, 3)])
    # sun: from ahead-right-above, pouring in through the canopy; target between bridge and commons
    sd = Vector((.45, -.7, .55)).normalized()
    tgt = Vector((0, -9.0, 0))
    LIGHTS.insert(0, dict(kind='sun', name='canopy_sun', pos=to3(tgt + sd * 60), target=to3(tgt), color='#fff1dc', intensity=3.0))
    out = dict(colliders=cols, stations=STATIONS, lights=LIGHTS, seats=SEATS, screens=SCREENS, portholes=PORTHOLES)
    json.dump(out, open(os.path.join(bl.MODELS, 'ship_interior.json'), 'w'), indent=1)
    print('colliders', len(cols), 'screens', len(SCREENS), 'seats', len(SEATS))
    bl.export('ship_interior.glb')


M_ = None
main()
