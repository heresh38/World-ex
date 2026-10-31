"""Modern road cars and hover boards (imported by vehicles.py; see its header for the node layout).

Coordinates while building: Blender X = car's left (+X is the driver side), -Y = forward, Z up, ground at Z=0.
Most dimensions are given along s = metres from the front bumper (s grows toward the rear); y = s - y0 where y0 puts
the middle of the wheelbase at the origin.
"""
import bpy, bmesh, math, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

TEX = bl.TEXTURES


# ------------------------------------------------------------------ materials
_M = {}


def tmat(name, color='#808080', metal=0.0, rough=.5, img=None, nrm=None, emit_img=None, emit='#000000', strength=0.0,
         coat=0.0, alpha=1.0, nstr=1.0):
    if name in _M:
        return _M[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*bl.hexrgb(color), 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if coat:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = .03
    if img:
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(TEX, img))
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        mix.inputs[7].default_value = (*bl.hexrgb(color), 1)
        nt.links.new(tn.outputs['Color'], mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    if nrm:
        nn = nt.nodes.new('ShaderNodeTexImage'); nn.image = bpy.data.images.load(os.path.join(TEX, nrm))
        nn.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
        nt.links.new(nn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if emit_img:
        en = nt.nodes.new('ShaderNodeTexImage'); en.image = bpy.data.images.load(os.path.join(TEX, emit_img))
        nt.links.new(en.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = strength or 1.0
    elif strength:
        b.inputs['Emission Color'].default_value = (*bl.hexrgb(emit), 1)
        b.inputs['Emission Strength'].default_value = strength
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    _M[name] = m
    return m


def common_mats():
    M = {}
    M['car_paint'] = tmat('car_paint', '#8a8d91', .55, .3, coat=1.0)
    M['trim_black'] = tmat('trim_black', '#141516', 0, .72, img='veh_dash_c.jpg', nrm='veh_dash_n.jpg', nstr=.4)
    M['trim_gloss'] = tmat('trim_gloss', '#060607', .1, .08)
    M['chrome'] = tmat('chrome', '#e8ecf0', 1.0, .06)
    M['glass_front'] = tmat('glass_front', '#1a2a33', .1, .02, alpha=.32)
    M['glass_side'] = tmat('glass_side', '#121c22', .1, .02, alpha=.42)
    M['glass_rear'] = tmat('glass_rear', '#0e161b', .1, .02, alpha=.55)
    M['glass_lo'] = tmat('glass_lo', '#0e171c', .3, .05, alpha=.85)
    M['lamp_head'] = tmat('lamp_head', '#ffffff', .6, .12, img='veh_headlamp_c.jpg', emit_img='veh_headlamp_e.jpg', strength=4.0)
    M['lamp_tail'] = tmat('lamp_tail', '#ffffff', .2, .15, img='veh_taillamp_c.jpg', emit_img='veh_taillamp_e.jpg', strength=2.5)
    M['grille'] = tmat('grille', '#ffffff', .3, .5, img='veh_grille_c.jpg', nrm='veh_grille_n.jpg')
    M['plate'] = tmat('plate', '#ffffff', .1, .35, img='veh_plates_c.jpg', nrm='veh_plates_n.jpg')
    M['badge'] = tmat('badge', '#ffffff', .9, .15, img='veh_badges_c.jpg')
    M['wheelwell'] = tmat('wheelwell', '#0b0b0c', 0, .9)
    M['tyre'] = tmat('tyre', '#ffffff', 0, .86, img='veh_tyre_c.jpg', nrm='veh_tyre_n.jpg', nstr=1.2)
    M['rim'] = tmat('rim', '#c4c8cc', 1.0, .22)
    M['rim_dark'] = tmat('rim_dark', '#3a3d42', 1.0, .3)
    M['brake_disc'] = tmat('brake_disc', '#ffffff', .9, .35, img='veh_disc_c.jpg', nrm='veh_disc_n.jpg')
    M['caliper'] = tmat('caliper', '#b0161c', .3, .35)
    M['caliper_grey'] = tmat('caliper_grey', '#5a5e64', .7, .4)
    # shared interior
    M['carpet'] = tmat('carpet', '#ffffff', 0, .95, img='veh_carpet_c.jpg', nrm='veh_carpet_n.jpg')
    M['headliner'] = tmat('headliner', '#ffffff', 0, .9, img='veh_headliner_c.jpg', nrm='veh_headliner_n.jpg', nstr=.5)
    M['speaker'] = tmat('speaker', '#ffffff', .5, .5, img='veh_speaker_c.jpg', nrm='veh_speaker_n.jpg')
    M['gauges'] = tmat('gauges', '#ffffff', 0, .25, img='veh_gauges_c.jpg', emit_img='veh_gauges_e.jpg', strength=2.0)
    M['screen'] = tmat('screen', '#ffffff', 0, .12, img='veh_screen_c.jpg', emit_img='veh_screen_c.jpg', strength=1.6)
    M['needle'] = tmat('needle', '#ff3a1a', 0, .4, emit='#ff3a1a', strength=3.0)
    M['steering'] = tmat('steering', '#1d1d1f', 0, .55, img='veh_leather_c.jpg', nrm='veh_leather_n.jpg')
    M['rubber'] = tmat('rubber', '#18181a', 0, .9)
    M['alu'] = tmat('alu', '#ffffff', .9, .3, img='veh_brushed_c.jpg')
    M['vent'] = tmat('vent', '#0d0d0e', .2, .5)
    M['mirror'] = tmat('mirror', '#d8e0e8', 1.0, .02)
    M['rover_accent'] = tmat('rover_accent', '#d9661f', .1, .45, coat=.6)
    M['bedliner'] = tmat('bedliner', '#1a1b1d', 0, .9, img='veh_grip_c.jpg', nrm='veh_grip_n.jpg', nstr=.6)
    return M


def theme_mats(k, th):
    """Per-model interior colourway."""
    return {
        'seat_insert': tmat('seat_insert_' + k, th['insert'], 0, .85, img='veh_quilt_c.jpg' if th.get('quilt') else 'veh_seatfab_c.jpg',
                            nrm='veh_quilt_n.jpg' if th.get('quilt') else 'veh_seatfab_n.jpg'),
        'seat_leather': tmat('seat_leather_' + k, th['leather'], 0, .5, img='veh_leather_c.jpg', nrm='veh_leather_n.jpg'),
        'dash_soft': tmat('dash_soft_' + k, th['dash'], 0, .7, img='veh_dash_c.jpg', nrm='veh_dash_n.jpg', nstr=.6),
        'dash_lower': tmat('dash_lower_' + k, th['lower'], 0, .6, img='veh_dash_c.jpg', nrm='veh_dash_n.jpg', nstr=.4),
        'accent': tmat('accent_' + k, th['accent'], .9 if th.get('metal', True) else .1, .3, img='veh_brushed_c.jpg' if th.get('metal', True) else 'carbon_c.jpg'),
        'door_upper': tmat('door_upper_' + k, th['dash'], 0, .7, img='veh_dash_c.jpg', nrm='veh_dash_n.jpg', nstr=.6),
    }


# ------------------------------------------------------------------ geometry helpers
class MB:
    """Mesh builder with per-face materials and world-scale box UVs (scale = metres per texture tile)."""
    SCALE = {'tyre': None, 'brake_disc': None}

    def __init__(self):
        self.v = []; self.f = []; self.mat = []; self.uv = []

    def vert(self, p):
        self.v.append(tuple(p)); return len(self.v) - 1

    def face(self, idx, mat, uv=None):
        self.f.append(tuple(idx)); self.mat.append(mat); self.uv.append(uv)

    def quad_grid(self, rows, mat_fn, uv_fn=None, closed=False, flip=False):
        """rows: list of lists of points (equal length). mat_fn(i, j, centre) -> material name."""
        ids = [[self.vert(p) for p in r] for r in rows]
        n = len(rows[0])
        for i in range(len(rows) - 1):
            for j in range(n - (0 if closed else 1)):
                j2 = (j + 1) % n
                q = [ids[i][j], ids[i][j2], ids[i + 1][j2], ids[i + 1][j]]
                if flip:
                    q = q[::-1]
                c = Vector((0, 0, 0))
                for k in q:
                    c += Vector(self.v[k])
                c /= 4
                uv = uv_fn(i, j, q) if uv_fn else None
                self.face(q, mat_fn(i, j, c), uv)
        return ids

    def build(self, name, M, scales=None):
        scales = scales or {}
        me = bpy.data.meshes.new(name)
        me.from_pydata([Vector(p) for p in self.v], [], self.f)
        names = []
        for mname in self.mat:
            if mname not in names:
                names.append(mname)
        for mname in names:
            me.materials.append(M[mname])
        uvl = me.uv_layers.new(name='UVMap')
        for pi, poly in enumerate(me.polygons):
            poly.material_index = names.index(self.mat[pi])
            given = self.uv[pi]
            nrm = poly.normal
            ax = max(range(3), key=lambda a: abs(nrm[a]))
            sc = scales.get(self.mat[pi], .5)
            for k, li in enumerate(poly.loop_indices):
                if given is not None:
                    uvl.data[li].uv = given[k]
                else:
                    co = me.vertices[me.loops[li].vertex_index].co
                    a, b = [(1, 2), (0, 2), (0, 1)][ax]
                    uvl.data[li].uv = (co[a] / sc, co[b] / sc)
        me.validate(); me.update()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        bl.autosmooth(o, 40)
        return o


def mono(keys):
    """Monotone cubic interpolant (Fritsch-Carlson) over (x, y) keys -> callable."""
    xs = [k[0] for k in keys]; ys = [k[1] for k in keys]; n = len(keys)
    d = [(ys[j + 1] - ys[j]) / (xs[j + 1] - xs[j]) for j in range(n - 1)]
    m = [d[0]] + [((d[j - 1] + d[j]) / 2 if d[j - 1] * d[j] > 0 else 0.0) for j in range(1, n - 1)] + [d[-1]]
    for j in range(n - 1):
        if d[j] == 0:
            m[j] = m[j + 1] = 0.0
            continue
        a, b = m[j] / d[j], m[j + 1] / d[j]
        t = a * a + b * b
        if t > 9:
            k = 3 / math.sqrt(t); m[j] = k * a * d[j]; m[j + 1] = k * b * d[j]

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = 0
        while xs[i + 1] < x:
            i += 1
        h = xs[i + 1] - xs[i]; t = (x - xs[i]) / h
        return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h * m[i]
                + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h * m[i + 1])
    return f


def smooth01(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)


def obj_mats(o, mats):
    o.data.materials.clear()
    for m in mats:
        o.data.materials.append(m)


def boxo(name, size, loc, mat, bevel=0.0, rot=(0, 0, 0), segs=2, uvs=.3):
    o = bl.box(name, size, loc, mat, bevel=bevel, rot=rot, segs=segs)
    bl.apply_all(o)
    bl.uv_box(o, uvs)
    return o


def cylo(name, r, h, loc, mat, verts=16, rot=(0, 0, 0), r2=None, uvs=.3):
    o = bl.cyl(name, r, h, loc, mat, verts, rot=rot, r2=r2)
    bl.apply_all(o)
    bl.uv_box(o, uvs)
    return o


def line_box(name, a, b, w, h, mat, up=Vector((0, 0, 1))):
    """Thin box from point a to point b (cross-section w x h)."""
    a, b = Vector(a), Vector(b)
    d = b - a; L = d.length
    o = bl.box(name, (w, L, h), (0, 0, 0), mat)
    q = Vector((0, 1, 0)).rotation_difference(d.normalized())
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = q; o.location = (a + b) / 2
    bl.apply_all(o)
    bl.uv_box(o, .3)
    return o


# ------------------------------------------------------------------ car definitions
CARS = {
    'hatch': dict(
        name='Nori Pip', L=4.06, W=1.78, wb=2.56, foh=.80, rw=.315, tw=.205, track=1.53, rim='rim',
        ztop=[(0, .56), (.05, .64), (.22, .74), (.6, .82), (1.14, .9), (1.2, .93), (3.7, .97), (3.9, .96), (4.0, .86), (4.06, .62)],
        zbot=[(0, .40), (.12, .28), (.45, .2), (2.0, .19), (3.6, .21), (3.9, .27), (4.06, .42)],
        w=[(0, .70), (.05, .80), (.2, .865), (.6, .885), (2.0, .89), (3.5, .885), (3.85, .86), (3.98, .82), (4.06, .74)],
        cowl=1.16, atop=1.96, ctop=3.48, rear=3.94, roof=1.47, belt=.95, tumble=.16,
        side_glass=[(1.5, 2.36), (2.47, 3.18)], blackB=(2.36, 2.47), doors=[1.24, 2.42, 3.3],
        floor=.30, hipup=.18, reach=1.24, xs=.36, rear_seat=.82, cargo=True,
        hood=[.25, 1.1], plate_z=.42, head_z=(.62, .74), tail_z=(.8, .93), clad=0.0,
        theme=dict(insert='#4a4c52', leather='#2c2d30', dash='#2a2b2e', lower='#1c1d1f', accent='#2a2b2e', metal=False),
        badge=0, paint='#2a5d8a'),
    'sedan': dict(
        name='Valen Aria', L=4.72, W=1.84, wb=2.80, foh=.92, rw=.33, tw=.225, track=1.58, rim='rim',
        ztop=[(0, .56), (.05, .64), (.25, .73), (.8, .82), (1.5, .88), (1.6, .92), (4.1, .99), (4.55, .99), (4.66, .93), (4.72, .66)],
        zbot=[(0, .38), (.15, .26), (.5, .19), (2.4, .18), (4.2, .2), (4.55, .28), (4.72, .44)],
        w=[(0, .72), (.05, .81), (.25, .885), (.8, .91), (2.4, .92), (4.1, .91), (4.55, .88), (4.68, .83), (4.72, .76)],
        cowl=1.56, atop=2.34, ctop=3.62, rear=4.16, roof=1.45, belt=.96, tumble=.17,
        side_glass=[(1.85, 2.92), (3.03, 3.62)], blackB=(2.92, 3.03), doors=[1.64, 2.98, 3.78],
        floor=.26, hipup=.18, reach=1.25, xs=.37, rear_seat=.78, cargo=False,
        hood=[.25, 1.5], trunk=[4.2, 4.6], plate_z=.45, head_z=(.62, .73), tail_z=(.84, .96), clad=0.0,
        theme=dict(insert='#d8c8a8', leather='#c9b28f', dash='#26262a', lower='#1a1a1c', accent='#c4c8cc', quilt=True),
        badge=1, paint='#e8e6e2'),
    'suv': dict(
        name='Hoyt Cairn', L=4.62, W=1.88, wb=2.72, foh=.92, rw=.37, tw=.235, track=1.62, rim='rim_dark',
        ztop=[(0, .74), (.06, .84), (.3, .96), (.9, 1.04), (1.3, 1.08), (1.4, 1.12), (4.4, 1.15), (4.52, 1.1), (4.58, .98), (4.62, .76)],
        zbot=[(0, .5), (.18, .36), (.55, .27), (2.3, .25), (4.0, .27), (4.4, .36), (4.62, .52)],
        w=[(0, .76), (.06, .85), (.3, .915), (.9, .935), (2.3, .94), (4.2, .935), (4.5, .9), (4.62, .82)],
        cowl=1.36, atop=2.12, ctop=4.28, rear=4.5, roof=1.72, belt=1.13, tumble=.14,
        side_glass=[(1.62, 2.76), (2.88, 3.48), (3.62, 4.22)], blackB=(2.76, 2.88), doors=[1.44, 2.82, 3.56],
        floor=.46, hipup=.24, reach=1.16, xs=.39, rear_seat=.82, cargo=True,
        hood=[.3, 1.3], plate_z=.6, head_z=(.82, .95), tail_z=(.98, 1.12), clad=.2,
        theme=dict(insert='#7a4a2c', leather='#5a3420', dash='#2b2522', lower='#1c1917', accent='#b8bcc2', quilt=True),
        badge=2, paint='#3d4a3a', rails=True),
    'pickup': dict(
        name='Hoyt Bracken', L=5.35, W=1.95, wb=3.4, foh=.95, rw=.39, tw=.265, track=1.68, rim='rim',
        ztop=[(0, .92), (.06, 1.0), (.3, 1.12), (1.0, 1.18), (1.5, 1.2), (1.6, 1.24), (3.28, 1.25), (3.4, 1.22), (5.28, 1.22), (5.35, 1.05)],
        zbot=[(0, .58), (.2, .42), (.6, .32), (2.5, .3), (4.7, .32), (5.1, .4), (5.35, .55)],
        w=[(0, .82), (.06, .91), (.3, .965), (1.0, .975), (3.3, .975), (3.4, .97), (5.2, .97), (5.35, .94)],
        cowl=1.58, atop=2.3, ctop=3.2, rear=3.3, roof=1.86, belt=1.25, tumble=.13,
        side_glass=[(1.85, 2.8), (2.92, 3.12)], blackB=(2.8, 2.92), doors=[1.66, 2.86, 3.3, 5.3],
        floor=.56, hipup=.24, reach=1.14, xs=.4, rear_seat=.76, cargo=False, bed=(3.42, 5.29, .82),
        hood=[.3, 1.52], plate_z=.62, head_z=(.98, 1.1), tail_z=(.95, 1.17), clad=.18,
        theme=dict(insert='#5a5d62', leather='#34363a', dash='#2a2b2e', lower='#1b1c1e', accent='#4a4d52', metal=False),
        badge=0, paint='#8e1d1d'),
    'van': dict(
        name='Nori Loft', L=5.0, W=1.95, wb=3.2, foh=.86, rw=.34, tw=.215, track=1.68, rim='rim_dark',
        ztop=[(0, .82), (.06, .9), (.3, 1.0), (.8, 1.08), (1.02, 1.12), (1.1, 1.17), (4.9, 1.18), (4.96, 1.12), (5.0, .9)],
        zbot=[(0, .46), (.18, .34), (.5, .26), (2.5, .25), (4.4, .27), (4.8, .34), (5.0, .48)],
        w=[(0, .8), (.06, .9), (.3, .96), (.8, .975), (4.7, .975), (4.92, .95), (5.0, .9)],
        cowl=1.06, atop=1.92, ctop=4.84, rear=4.94, roof=2.04, belt=1.17, tumble=.1,
        side_glass=[(1.4, 2.42)], blackB=(2.42, 2.54), doors=[1.12, 2.48, 3.4, 4.86],
        floor=.56, hipup=.26, reach=1.1, xs=.4, rear_seat=0, cargo=True, partition=True, rear_win=(1.5, 1.9, .04),
        hood=[.3, 1.0], plate_z=.52, head_z=(.84, .98), tail_z=(.9, 1.4), clad=.16,
        theme=dict(insert='#3e4146', leather='#26272a', dash='#2a2b2e', lower='#1b1c1e', accent='#2a2b2e', metal=False),
        badge=0, paint='#e9e9e6'),
}


CARS['rover'] = dict(
    name='Talus Rover', L=3.95, W=2.3, wb=2.62, foh=.66, rw=.53, tw=.4, track=1.86, rim='rim_dark', knobby=True,
    ztop=[(0, 1.0), (3.95, 1.0)], zbot=[(0, .56), (3.95, .56)], w=[(0, .8), (3.95, .8)],
    cowl=1.0, atop=1.5, ctop=2.5, rear=2.85, roof=1.98, belt=1.06, tumble=.1,
    side_glass=[], blackB=(2.5, 2.5), doors=[], floor=.62, hipup=.26, reach=1.08, xs=.42, rear_seat=0, cargo=False,
    hood=[.1, .9], plate_z=.8, head_z=(.8, .95), tail_z=(.85, 1.0), clad=0.0,
    theme=dict(insert='#3a3d42', leather='#c8622a', dash='#2a2b2e', lower='#1b1c1e', accent='#c8622a', metal=False),
    badge=0, paint='#e9e6df')


class Car:
    def __init__(self, key, M, lo=False):
        self.k = key; self.c = c = CARS[key]; self.M = M; self.lo = lo
        self.L, self.y0 = c['L'], c['foh'] + c['wb'] / 2
        self.ztop, self.zbot, self.w = mono(c['ztop']), mono(c['zbot']), mono(c['w'])
        self.hip = c['floor'] + c['hipup']
        self.s_hp = c['cowl'] + c['reach']
        self.s_rhp = self.s_hp + c['rear_seat'] if c['rear_seat'] else None

    def Y(self, s):
        return s - self.y0

    # ---------------- body cross-section (right half from bottom centre to top centre)
    def half(self, s, inset=0.0, crown=.02):
        c = self.c
        w = self.w(s) - inset; zb = self.zbot(s); zt = self.ztop(s)
        cab = c['cowl'] - .05 < s < c['rear'] + .05
        # the body top meets the window line exactly along the cabin, blending in from the bonnet and the deck
        k = 1.0 if c['cowl'] <= s <= c['rear'] else smooth01(1 - (c['cowl'] - s) / .14) if s < c['cowl'] else smooth01(1 - (s - c['rear']) / .1)
        if c.get('bed') and s > c['rear']:
            k = 1.0 if s < c['bed'][1] else k
        zt = zt + (c['belt'] - zt) * k
        h = max(zt - zb, .05)
        rb = min(.09, h * .3)
        rt = min(.05 if cab else .11, h * .3)
        pts = [(0, zb), (w * .55, zb)]
        for a in (-60, -30, 0):
            r = math.radians(a)
            pts.append((w - rb + rb * math.cos(r), zb + rb + rb * math.sin(r)))
        zs0, zs1 = zb + rb, zt - rt
        for t in (.22, .45, .66, .8, .93):
            z = zs0 + (zs1 - zs0) * t
            bulge = .012 * math.sin(math.pi * min(1, t / .8))
            crease = -.006 if abs(t - .8) < .01 else 0
            pts.append((w + bulge + crease - .018 * max(0, t - .8) / .2, z))
        cx = w - .018 - rt
        for a in (20, 45, 70, 90):
            r = math.radians(a)
            pts.append((cx + rt * math.cos(r), zs1 + rt * math.sin(r)))
        cr = 0 if cab else crown
        pts.append((cx * .5, zt + cr * .75))
        pts.append((0, zt + cr))
        return pts

    def ring(self, s, gap=False):
        hp = self.half(s)
        if gap:
            hp = [(x - (.006 if 5 <= i <= 10 else 0), z) for i, (x, z) in enumerate(hp)]
        right = [(x, z) for x, z in hp]
        left = [(-x, z) for x, z in hp[1:-1]][::-1]
        y = self.Y(s)
        return [(x, y, z) for x, z in right + left]

    def x_at(self, s, z):
        """Outer body half-width at height z (side region)."""
        hp = self.half(s)
        best = hp[4][0]
        for (x0, z0), (x1, z1) in zip(hp[2:15], hp[3:16]):
            if min(z0, z1) <= z <= max(z0, z1) and z1 != z0:
                t = (z - z0) / (z1 - z0); best = x0 + (x1 - x0) * t
                break
        return best

    # ---------------- body
    def stations(self):
        c, L = self.c, self.L
        st = set()
        step = .25 if self.lo else .07
        n = int(L / step)
        for i in range(n + 1):
            st.add(round(L * i / n, 4))
        for e in (.012, .03, .06, .1, L - .012, L - .03, L - .06, L - .1, c['cowl'], c['rear']):
            st.add(round(e, 4))
        if c.get('bed'):
            st.add(c['bed'][0]); st.add(c['bed'][1])
        gaps = set()
        if not self.lo:
            for g in c['doors']:
                for d in (-.007, 0, .007):
                    st.add(round(g + d, 4))
                gaps.add(round(g, 4))
        return sorted(st), gaps

    def body(self):
        c, M = self.c, self.M
        sts, gaps = self.stations()
        prof = [self.ring(s, s in gaps) for s in sts]
        o = bl.loft('body_' + self.k, prof, M['car_paint'], smooth=True)
        # wheel arches: boolean cut (inner faces take the black liner)
        for sa in (c['foh'], c['foh'] + c['wb']):
            cut = bl.cyl('arch', c['rw'] + .055, c['W'] + .6, (0, self.Y(sa), c['rw'] + .015), M['wheelwell'], 24 if not self.lo else 12, rot=(0, math.pi / 2, 0))
            bl.apply_all(cut)
            md = o.modifiers.new('arch', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = cut
            md.solver = 'EXACT'
            try:
                md.material_mode = 'TRANSFER'
            except Exception:
                pass
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier=md.name)
            bpy.data.objects.remove(cut)
        # open the cabin (and bed) tops; assign cladding / underbody
        me = o.data
        names = [m.name for m in me.materials]
        if 'trim_black' not in names:
            me.materials.append(M['trim_black']); names.append('trim_black')
        bm = bmesh.new(); bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        regions = [(c['cowl'], c['rear'], .06)]
        if c.get('bed'):
            regions.append((c['bed'][0], c['bed'][1], .06))
        dele = []
        iw = names.index('wheelwell') if 'wheelwell' in names else -1
        it = names.index('trim_black')
        for f in bm.faces:
            cc = f.calc_center_median(); s = cc.y + self.y0
            if f.material_index == iw:
                continue
            for s0, s1, ins in regions:
                if s0 + .01 < s < s1 - .01 and f.normal.z > .3 and abs(cc.x) < self.w(s) - ins:
                    dele.append(f); break
            else:
                if f.normal.z < -.6 or cc.z < self.zbot(s) + c['clad']:
                    f.material_index = it
        bmesh.ops.delete(bm, geom=dele, context='FACES')
        bm.to_mesh(me); bm.free()
        return o

    # ---------------- greenhouse: glass, pillars, roof in one loft (+ inner headliner shell)
    def roof_z(self, s):
        c = self.c
        belt, roof = c['belt'] + .005, c['roof']
        arch = c.get('arch', (.035, .06))       # roof drop toward the windscreen header / the backlight
        za, zc = roof - arch[0], roof - arch[1]
        if s <= c['atop']:
            t = max(0, min(1, (s - c['cowl']) / (c['atop'] - c['cowl'])))
            return belt + (za - belt) * (.55 * t + .45 * math.sin(t * math.pi / 2))
        if s >= c['ctop']:
            t = max(0, min(1, (c['rear'] - s) / (c['rear'] - c['ctop'])))
            return belt + (zc - belt) * (.55 * t + .45 * math.sin(t * math.pi / 2))
        m = (s - c['atop']) / (c['ctop'] - c['atop'])
        pk = .38
        if m < pk:
            return roof - arch[0] * ((pk - m) / pk) ** 2
        return roof - arch[1] * ((m - pk) / (1 - pk)) ** 2

    def gh_half(self, s, inset=0.0):
        c = self.c
        belt = c['belt'] + .005
        wb = self.x_at(s, c['belt']) - .045 - inset
        zr = self.roof_z(s) - inset
        hrel = (zr - belt) / max(.01, c['roof'] - belt)
        wr = wb - c['tumble'] * max(0, hrel) - (.06 if s < c['atop'] else 0) * (1 - hrel)
        rr = max(.004, min(.06, (zr - belt) * .4))
        zsid = max(belt, zr - rr)
        pts = [(wb, belt)]
        for t in (.4, .75):
            pts.append((wb + (wr + rr - wb) * t, belt + (zsid - belt) * t))
        for a in (0, 30, 60, 90):
            r = math.radians(a)
            pts.append((wr + rr * math.cos(r) - rr * 0, zsid + rr * math.sin(r)))
        crown = .025 * hrel
        pts.append((wr * .9, zr + crown * .2))
        pts.append((wr * .5, zr + crown * .75))
        pts.append((0, zr + crown))
        return pts

    def greenhouse(self):
        c, M = self.c, self.M
        n = int((c['rear'] - c['cowl']) / (.04 if not self.lo else .12))
        sts = [c['cowl'] + (c['rear'] - c['cowl']) * i / n for i in range(n + 1)]
        mb, inner = MB(), MB()
        rows, irows = [], []
        for s in sts:
            hp = self.gh_half(s)
            y = self.Y(s)
            rows.append([(x, y, z) for x, z in hp] + [(-x, y, z) for x, z in hp[:-1]][::-1])
            ih = self.gh_half(s, .022)
            irows.append([(x, y, z) for x, z in ih] + [(-x, y, z) for x, z in ih[:-1]][::-1])
        nh = len(hp)          # points per half (10); faces per half: 0-2 side, 3-5 edge, 6 frit/roof edge, 7-8 roof

        def cat(j):
            jj = j if j < nh - 1 else (2 * nh - 3 - j)
            return 'side' if jj < 3 else ('edge' if jj < 6 else 'roof')

        def side_mat(s):
            for a, b in c['side_glass']:
                if a <= s <= b:
                    return 'glass_side' if not self.lo else 'glass_lo'
            b0, b1 = c['blackB']
            if b0 - .02 <= s <= b1 + .02:
                return 'trim_gloss'
            return 'car_paint'

        def mat(i, j, cc):
            s = cc.y + self.y0
            k = cat(j)
            if k == 'edge':
                return 'car_paint'
            if k == 'side':
                return side_mat(s)
            jj = j if j < nh - 1 else (2 * nh - 3 - j)
            if s < c['atop'] - .02:
                if jj == 6 and not self.lo:
                    return 'trim_gloss'          # ceramic frit band along the A-pillars
                return 'glass_front' if not self.lo else 'glass_lo'
            if s > c['ctop'] + .02:
                rw_ = c.get('rear_win')            # vans: panel doors with two small windows
                if rw_ and not (rw_[0] < cc.z < rw_[1] and abs(cc.x) > rw_[2] and abs(cc.x) < self.w(s) - .25):
                    return 'car_paint' if abs(cc.x) > .012 else 'trim_gloss'
                return 'glass_rear' if not self.lo else 'glass_lo'
            return 'car_paint'
        mb.quad_grid(rows, mat)
        o = mb.build('gh_' + self.k, M)
        if self.lo:
            return [o]

        def imat(i, j, cc):
            k = cat(j)
            s = cc.y + self.y0
            if k == 'roof' and c['atop'] - .02 < s < c['ctop'] + .02:
                return 'headliner'
            if k == 'edge':
                return 'headliner'
            if k == 'side' and side_mat(s) != 'glass_side':
                return 'headliner'
            return None
        # keep only the non-glass faces of the inner shell, normals facing the cabin
        ib = MB()
        ids = [[ib.vert(p) for p in r] for r in irows]
        for i in range(len(irows) - 1):
            for j in range(len(irows[0]) - 1):
                q = [ids[i][j], ids[i + 1][j], ids[i + 1][j + 1], ids[i][j + 1]]
                cc = sum((Vector(ib.v[k]) for k in q), Vector()) / 4
                m = imat(i, j, cc)
                if m:
                    ib.face(q, m)
        io = ib.build('ghin_' + self.k, M, {'headliner': .4})
        return [o, io]

    # ---------------- ray-projected details (lamps, grille, plates, badges, shut lines)
    def make_bvh(self, objs):
        dg = bpy.context.evaluated_depsgraph_get()
        bm = bmesh.new()
        for o in objs:
            tmp = bmesh.new(); tmp.from_mesh(o.data); tmp.transform(o.matrix_world)
            me = bpy.data.meshes.new('t'); tmp.to_mesh(me); tmp.free()
            bm.from_mesh(me); bpy.data.meshes.remove(me)
        self.bvh = BVHTree.FromBMesh(bm)
        bm.free()

    def plane(self, kind, a, b):
        """(origin, dir) for plane coords (a, b)."""
        far = 4.0
        if kind == 'front':
            return Vector((a, -self.y0 - far, b)), Vector((0, 1, 0))
        if kind == 'rear':
            return Vector((-a, self.L - self.y0 + far, b)), Vector((0, -1, 0))
        if kind == 'left':
            return Vector((far, self.Y(a), b)), Vector((-1, 0, 0))
        if kind == 'right':
            return Vector((-far, self.Y(a), b)), Vector((1, 0, 0))
        if kind == 'top':
            return Vector((a, self.Y(b), 4.0)), Vector((0, 0, -1))

    def hit(self, kind, a, b, off):
        o, d = self.plane(kind, a, b)
        loc, nrm, idx, dist = self.bvh.ray_cast(o, d, 10.0)
        if loc is None:
            return None
        return loc - d * off

    def patch(self, mb, kind, outline, off, mat, uvrect=(0, 0, 1, 1), rings=3, flipu=False):
        aa = [p[0] for p in outline]; bb = [p[1] for p in outline]
        a0, a1, b0, b1 = min(aa), max(aa), min(bb), max(bb)
        ca, cb = sum(aa) / len(aa), sum(bb) / len(bb)
        u0, v0, u1, v1 = uvrect

        def uv(a, b):
            u = (a - a0) / max(1e-6, a1 - a0)
            if flipu:
                u = 1 - u
            return (u0 + (u1 - u0) * u, v0 + (v1 - v0) * (b - b0) / max(1e-6, b1 - b0))
        grid = [[(ca, cb)]]
        for k in range(1, rings + 1):
            t = k / rings
            grid.append([(ca + (a - ca) * t, cb + (b - cb) * t) for a, b in outline])
        pts = [[self.hit(kind, a, b, off) for a, b in r] for r in grid]
        if pts[0][0] is None:
            return
        ids = []
        for r, rp in zip(grid, pts):
            row = []
            for (a, b), p in zip(r, rp):
                row.append((mb.vert(p), uv(a, b)) if p is not None else None)
            ids.append(row)
        n = len(outline)
        flip = kind in ('rear', 'right')
        for j in range(n):
            a, b = ids[1][j], ids[1][(j + 1) % n]
            if a and b:
                f = [ids[0][0], a, b]
                f = f if not flip else f[::-1]
                mb.face([x[0] for x in f], mat, [x[1] for x in f])
        for k in range(1, rings):
            for j in range(n):
                q = [ids[k][j], ids[k][(j + 1) % n], ids[k + 1][(j + 1) % n], ids[k + 1][j]]
                if all(q):
                    q = q if not flip else q[::-1]
                    mb.face([x[0] for x in q], mat, [x[1] for x in q])

    def strip(self, mb, kind, pts, width, off, mat):
        """Ray-projected ribbon along a polyline in plane coords."""
        rows = []
        for i, (a, b) in enumerate(pts):
            pa, pb = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
            ta, tb = pb[0] - pa[0], pb[1] - pa[1]; l = math.hypot(ta, tb) or 1
            na, nb = -tb / l * width / 2, ta / l * width / 2
            p0 = self.hit(kind, a + na, b + nb, off); p1 = self.hit(kind, a - na, b - nb, off)
            rows.append((p0, p1))
        for (p0, p1), (q0, q1) in zip(rows, rows[1:]):
            if p0 and p1 and q0 and q1:
                ids = [mb.vert(p0), mb.vert(q0), mb.vert(q1), mb.vert(p1)]
                mb.face(ids if kind not in ('rear', 'right') else ids[::-1], mat)

    def details(self):
        c, M = self.c, self.M
        mb = MB()
        W2 = c['W'] / 2
        h0, h1 = c['head_z']
        rnd = lambda cx, cy, rx, ry, n=20, e=.35: [(cx + rx * math.copysign(abs(math.cos(t)) ** e, math.cos(t)), cy + ry * math.copysign(abs(math.sin(t)) ** e, math.sin(t))) for t in [2 * math.pi * i / n for i in range(n)]]
        # headlamps: swept shape on each front corner
        for sx in (1, -1):
            ol = []
            for i in range(16):
                t = i / 15
                ol.append((sx * (W2 * .36 + (W2 * .88 - W2 * .36) * t), h0 + (h1 - h0) * (.55 + .45 * t) if sx else 0))
            for i in range(16):
                t = 1 - i / 15
                ol.append((sx * (W2 * .36 + (W2 * .92 - W2 * .36) * t), h0 + (h1 - h0) * (.0 + .2 * t)))
            self.patch(mb, 'front', ol, .004, 'lamp_head', flipu=sx < 0, rings=3)
            if not self.lo:
                # fog lamp + lower intake corner
                self.patch(mb, 'front', rnd(sx * W2 * .72, c['plate_z'] - .02, .06, .03, 16), .004, 'lamp_head', (0.78, .22, .93, .62), rings=2)
        # grille between the lamps and lower intake
        g0 = h0 - .02
        self.patch(mb, 'front', [(-W2 * .34, g0 - .06), (W2 * .34, g0 - .06), (W2 * .3, h1 - .01), (-W2 * .3, h1 - .01)], .003, 'grille', rings=2)
        lz = c['plate_z']
        self.patch(mb, 'front', [(-W2 * .62, lz - .17), (W2 * .62, lz - .17), (W2 * .55, lz - .06), (-W2 * .55, lz - .06)], .003, 'grille', rings=2)
        # tail lamps (rear face + wrap strip on each side)
        t0, t1 = c['tail_z']
        for sx in (1, -1):
            if self.k == 'van' or self.k == 'pickup':
                ol = rnd(sx * W2 * .9, (t0 + t1) / 2, W2 * .07, (t1 - t0) / 2, 20, .2)
            else:
                ol = rnd(sx * W2 * .66, (t0 + t1) / 2, W2 * .27, (t1 - t0) / 2, 24, .25)
            self.patch(mb, 'rear', ol, .004, 'lamp_tail', flipu=sx < 0, rings=2)
        # number plates + badges
        if not self.lo:
            cell = (0, .75, .5, 1.0)       # atlas cell 0 (top-left): the game shifts the offset per car
            self.patch(mb, 'front', [(-.26, lz - .055), (.26, lz - .055), (.26, lz + .055), (-.26, lz + .055)], .006, 'plate', cell, rings=1)
            rz = c['tail_z'][0] - .17 if self.k not in ('van', 'pickup') else c['plate_z'] + .05
            self.patch(mb, 'rear', [(-.26, rz - .055), (.26, rz - .055), (.26, rz + .055), (-.26, rz + .055)], .006, 'plate', cell, rings=1)
            self.patch(mb, 'front', rnd(0, (h0 + h1) / 2 - .01, .045, .045, 20, 1.0), .008, 'badge', (0, 0, .25, 1), rings=2)
            bc = c['badge']
            self.patch(mb, 'rear', [(-.16, t0 - .07), (.16, t0 - .07), (.16, t0 - .01), (-.16, t0 - .01)], .004, 'badge', (.25 * (bc + 1) + .03, .25, .25 * (bc + 2) - .03, .75), rings=1)
            # shut lines: bonnet, boot, fuel flap
            hs0, hs1 = c['hood']
            ln = lambda pts: self.strip(mb, 'top', pts, .006, .0015, 'trim_gloss')
            wh = lambda s: self.w(s) - .1
            ln([(-wh(hs0) + .05, hs0), (wh(hs0) - .05, hs0)])
            ln([(wh(s), s) for s in [hs0 + (hs1 - hs0) * t / 8 for t in range(9)]])
            ln([(-wh(s), s) for s in [hs0 + (hs1 - hs0) * t / 8 for t in range(9)]])
            if c.get('trunk'):
                a, b = c['trunk']
                ln([(-wh(a), a), (wh(a), a)])
                ln([(wh(s), s) for s in [a + (b - a) * t / 6 for t in range(7)]])
                ln([(-wh(s), s) for s in [a + (b - a) * t / 6 for t in range(7)]])
            # door shut lines (dark seams) and the sill line, both sides
            for kind in ('left', 'right'):
                sd = [d for d in c['doors'] if d < c['rear'] + .05 or (c.get('bed') is None and d < self.L - .2)]
                zsill = lambda s: self.zbot(s) + .1
                for g in sd:
                    if c.get('bed') and g > c['rear'] + .05:
                        continue
                    self.strip(mb, kind, [(g, zsill(g)), (g + .01, (zsill(g) + c['belt']) / 2), (g, c['belt'] - .012)], .005, .0012, 'trim_gloss')
                d0 = sd[0]; d1 = sd[-1] if sd[-1] <= c['rear'] + .05 else sd[-2]
                self.strip(mb, kind, [(d0 + (d1 - d0) * t / 10, zsill(d0 + (d1 - d0) * t / 10)) for t in range(11)], .005, .0012, 'trim_gloss')
                # wheel-arch lips (black cladding on the SUV / pickup / van)
                for sa in (c['foh'], c['foh'] + c['wb']):
                    R = c['rw'] + .085
                    arc = [(sa + R * math.cos(math.radians(a)), c['rw'] + .015 + R * math.sin(math.radians(a))) for a in range(5, 176, 10)]
                    clad = c['clad'] > 0
                    self.strip(mb, kind, arc, .06 if clad else .022, .006 if clad else .004, 'trim_black' if clad else 'car_paint')
            # door handles (flush pills) on both sides
            hz = c['belt'] - .1
            for kind in ('left', 'right'):
                for d0 in c['doors'][:2]:
                    s0 = d0 + .55 if d0 == c['doors'][0] else d0 + .45
                    if s0 > c['rear']:
                        continue
                    self.patch(mb, kind, [(s0 - .1, hz - .016), (s0 + .1, hz - .016), (s0 + .1, hz + .016), (s0 - .1, hz + .016)], .009, 'chrome' if self.k == 'sedan' else 'car_paint', rings=1)
        return mb.build('det_' + self.k, M, {'grille': .25, 'trim_gloss': 1, 'car_paint': 1, 'chrome': 1})

    # ---------------- exterior hardware: mirrors, wipers, beltline trim, roof rails, exhausts, bed, aerial
    def hardware(self):
        c, M = self.c, self.M
        P = []
        s_m = c['cowl'] + .2
        zm = c['belt'] + .1
        for sx in (1, -1):
            xm = self.x_at(s_m, c['belt']) + .1
            P.append(boxo('mir', (.2, .1, .13), (sx * xm, self.Y(s_m), zm), M['car_paint'], bevel=.04, segs=3))
            P.append(boxo('mirg', (.16, .01, .1), (sx * xm, self.Y(s_m) + .052, zm), M['mirror'], bevel=.01))
            P.append(boxo('mirb', (.12, .06, .05), (sx * (xm - .1), self.Y(s_m), zm - .05), M['trim_black'], bevel=.01))
            # beltline trim
            pts = []
            for i in range(14):
                s = c['cowl'] + .25 + (c['side_glass'][-1][1] - c['cowl'] - .25) * i / 13
                pts.append((self.x_at(s, c['belt']) - .02, self.Y(s), c['belt'] + .006))
            for a, b in zip(pts, pts[1:]):
                P.append(line_box('belt', (sx * a[0], a[1], a[2]), (sx * b[0], b[1], b[2]), .022, .012, M['chrome'] if self.k in ('sedan', 'suv') else M['trim_black']))
            # wipers
            P.append(line_box('wiper', (sx * .05 - .0, self.Y(c['cowl'] + .1), c['belt'] + .03), (sx * .05 + .55, self.Y(c['cowl'] + .16), c['belt'] + .05), .02, .012, M['trim_black']))
            if c.get('rails'):
                for i in range(1):
                    a = (sx * (self.gh_half(c['atop'] + .1)[6][0] - .02), self.Y(c['atop'] + .1), c['roof'] + .03)
                    b = (sx * (self.gh_half(c['ctop'] - .1)[6][0] - .02), self.Y(c['ctop'] - .1), c['roof'] + .03)
                    P.append(line_box('rail', a, b, .04, .035, M['alu']))
                    for s in (c['atop'] + .12, c['ctop'] - .12):
                        P.append(boxo('railfoot', (.05, .08, .04), (sx * (self.gh_half(s)[6][0] - .02), self.Y(s), c['roof'] + .005), M['trim_black']))
        # exhaust tips
        ex = self.L - self.y0 - .06
        for sx in ((1, -1) if self.k == 'sedan' else (-1,)):
            P.append(cylo('exh', .035, .14, (sx * .55, ex, self.zbot(self.L - .1) + .02), M['chrome'], 16, rot=(math.pi / 2, 0, 0)))
            P.append(cylo('exhi', .028, .02, (sx * .55, ex + .065, self.zbot(self.L - .1) + .02), M['trim_gloss'], 16, rot=(math.pi / 2, 0, 0)))
        # aerial fin
        P.append(boxo('fin', (.05, .16, .05), (0, self.Y(c['ctop'] - .05), c['roof'] + .02), M['car_paint'], bevel=.02, segs=3))
        # pickup bed: liner floor, walls, tailgate inner panel
        if c.get('bed'):
            s0, s1, zf = c['bed']
            mb = MB()
            nst = 12
            rows = []
            for i in range(nst + 1):
                s = s0 + (s1 - s0) * i / nst
                zs = [zf + (c['belt'] - .02 - zf) * k / 4 for k in range(5)]
                rows.append([(self.x_at(s, z) - .05, self.Y(s), z) for z in zs])
            mb.quad_grid(rows, lambda i, j, cc: 'bedliner')
            mb.quad_grid([[(-p[0], p[1], p[2]) for p in r] for r in rows], lambda i, j, cc: 'bedliner', flip=True)
            wf = self.x_at(s0, zf) - .05
            P.append(boxo('bedfloor', (2 * wf, s1 - s0, .02), (0, self.Y((s0 + s1) / 2), zf), M['bedliner'], uvs=.6))
            P.append(boxo('bedfront', (2 * wf, .03, c['belt'] - zf), (0, self.Y(s0) + .015, (zf + c['belt']) / 2), M['bedliner'], uvs=.6))
            P.append(boxo('bedtail', (2 * wf, .03, c['belt'] - zf), (0, self.Y(s1) - .015, (zf + c['belt']) / 2), M['bedliner'], uvs=.6))
            for sx in (1, -1):
                P.append(boxo('wellhump', (.22, .9, .3), (sx * (wf - .1), self.Y(c['foh'] + c['wb']), zf + .15), M['bedliner'], bevel=.04, uvs=.6))
                P.append(boxo('railcap', (.06, s1 - s0, .02), (sx * (self.x_at(s0 + .5, c['belt']) - .03), self.Y((s0 + s1) / 2), c['belt'] - .01), M['trim_black']))
            P.append(mb.build('bedwalls', M, {'bedliner': .6}))
        # van rear door windows (rear face) and a sliding-door rail
        return P

    # ---------------- interior
    def interior(self):
        c, M, T = self.c, self.M, self.T
        P = []
        fl, hip, belt = c['floor'], self.hip, c['belt']
        s_hp, xs = self.s_hp, c['xs']
        s_dash = s_hp - .76
        yd = self.Y
        end = (self.L - .22) if c['cargo'] else (self.s_rhp + .32 if self.s_rhp else c['rear'] - .05)
        # door cards / cabin side walls (grid following the body side, inset), sill cap on top
        mb = MB()
        nst = max(6, int((end - c['cowl'] - .05) / .05))
        sts = [c['cowl'] + .05 + (end - c['cowl'] - .05) * i / nst for i in range(nst + 1)]
        zl = [fl - .02, fl + .12, hip - .1, hip - .05, hip + .1, hip + .2, belt - .06, belt - .015]

        def dmat(i, j, cc):
            z = cc.z
            if z < hip - .06:
                return 'dash_lower'
            if z < hip + .15:
                return 'seat_leather'
            return 'door_upper'
        for sx in (1, -1):
            rows = []
            for s in sts:
                r = [(sx * (self.x_at(s, z) - .055), yd(s), z) for z in zl]
                r.append((sx * (self.x_at(s, belt) - .02), yd(s), belt + .004))
                rows.append(r)
            mb.quad_grid(rows, dmat, flip=sx < 0)
        P.append(mb.build('doors', {**M, **T}, {'dash_lower': .35, 'seat_leather': .3, 'door_upper': .4}))
        # floor
        wf = self.x_at(s_hp, fl + .1) - .06
        P.append(boxo('floor', (2 * wf, end - c['cowl'] - .1, .02), (0, yd((end + c['cowl'] + .1) / 2), fl - .01), M['carpet'], uvs=.5))
        for sx in (1, -1):
            P.append(boxo('mat', (.5, .62, .012), (sx * xs, yd(s_hp - .62), fl + .006), M['rubber'], bevel=.01, uvs=.5))
        # ---- dashboard: loft across the width, section in (s, z)
        sec = [(c['cowl'] - .02, belt - .1), (c['cowl'] + .02, belt + .005), ((c['cowl'] + s_dash) / 2, belt + .07), (s_dash - .04, belt + .065),
               (s_dash, belt + .03), (s_dash + .012, belt - .02), (s_dash + .008, belt - .1), (s_dash - .04, belt - .26),
               (s_dash - .14, fl + .36), (c['cowl'] + .16, fl + .1), (c['cowl'] - .02, fl + .1)]
        xmax = self.x_at(c['cowl'] + .3, belt - .1) - .05
        prof = []
        NX = 28
        for i in range(NX + 1):
            x = -xmax + 2 * xmax * i / NX
            bump = smooth01(1 - abs(x - xs) / .26) if abs(x - xs) < .26 else 0
            ring = []
            for k, (s, z) in enumerate(sec):
                if k in (3, 4):
                    z += .07 * bump
                if k in (4, 5):
                    s += .03 * bump
                ring.append((x, yd(s), z))
            prof.append(ring)
        d = bl.loft('dash', prof, T['dash_soft'], smooth=True)
        obj_mats(d, [T['dash_soft'], T['accent'], T['dash_lower']])
        for p in d.data.polygons:
            z = p.center.z
            p.material_index = 0 if (p.normal.z > .45 or z > belt + .025) else (1 if belt - .075 < z < belt - .03 else 2)
        bl.uv_box(d, .3)
        P.append(d)
        # gauge cluster: face, visor and the needles (separate animated objects)
        tilt = .22
        gz = belt + .045
        gs = s_dash - .005
        q = MB()
        gw, gh = .32, .16
        cy = math.cos(tilt); sy = math.sin(tilt)
        def gp(u, v):
            return (xs + (u - .5) * gw, yd(gs) - (v - .5) * gh * sy, gz + (v - .5) * gh * cy)
        ids = [q.vert(gp(0, 0)), q.vert(gp(1, 0)), q.vert(gp(1, 1)), q.vert(gp(0, 1))]
        q.face(ids, 'gauges', [(1, 0), (0, 0), (0, 1), (1, 1)])
        P.append(q.build('gauge', M))
        P.append(boxo('visor', (.4, .1, .025), (xs, yd(gs + .045), gz + .1), T['dash_soft'], bevel=.01, rot=(-.15, 0, 0)))
        for sx in (-1, 1):
            P.append(boxo('cheek', (.02, .1, .16), (xs + sx * .19, yd(gs + .04), gz + .02), T['dash_soft'], bevel=.008))
        self.needles = []
        for k, u in (('S', .25), ('R', .75)):
            nx = xs + (u - .5) * gw * -1
            self.needles.append((k, Vector((nx, yd(gs) + .006 + .002, gz)), tilt))
        # centre stack: screen, vents, climate knobs; side vents
        P.append(boxo('stack', (.34, .14, .36), (0, yd(s_dash - .05), belt - .16), T['dash_lower'], bevel=.02, rot=(.12, 0, 0)))
        sq = MB()
        sw, sh = .25, .14
        sz = belt - .06
        st = .18
        def sp(u, v):
            return ((u - .5) * sw, yd(s_dash + .022) - (v - .5) * sh * math.sin(st), sz + (v - .5) * sh * math.cos(st))
        ids = [sq.vert(sp(0, 0)), sq.vert(sp(1, 0)), sq.vert(sp(1, 1)), sq.vert(sp(0, 1))]
        sq.face(ids, 'screen', [(1, 0), (0, 0), (0, 1), (1, 1)])
        P.append(sq.build('screen', M))
        P.append(boxo('scrbezel', (.28, .012, .17), (0, yd(s_dash + .014), sz), M['trim_gloss'], bevel=.006, rot=(st, 0, 0)))
        for sx in (-1, 1):
            vx = sx * .07
            P.append(boxo('vent', (.11, .03, .05), (vx, yd(s_dash + .02), belt + .035), M['vent'], bevel=.006))
            for k in range(3):
                P.append(boxo('slat', (.1, .035, .004), (vx, yd(s_dash + .022), belt + .02 + k * .014), T['accent']))
            P.append(boxo('svent', (.06, .03, .06), (sx * (xmax - .08), yd(s_dash + .01), belt + .02), M['vent'], bevel=.008))
        for k in (-1, 0, 1):
            P.append(cylo('knob', .022, .025, (k * .08, yd(s_dash - .02), belt - .21), T['accent'], 20, rot=(math.pi / 2 - .12, 0, 0)))
        P.append(boxo('hazard', (.03, .01, .015), (0, yd(s_dash - .025), belt - .15), M['needle']))
        # glovebox shut line
        P.append(boxo('glove', (.36, .004, .004), (-xs, yd(s_dash + .012), belt - .1), M['trim_gloss']))
        # centre console with gear selector, cup holders and armrest
        cl0, cl1 = s_dash - .1, s_hp + .15
        P.append(boxo('console', (.22, cl1 - cl0, hip - fl - .02), (0, yd((cl0 + cl1) / 2), (hip + fl) / 2 - .02), T['dash_lower'], bevel=.025, segs=3))
        P.append(boxo('consoletop', (.2, cl1 - cl0 - .02, .015), (0, yd((cl0 + cl1) / 2), hip - .03), M['trim_gloss'], bevel=.005))
        P.append(boxo('armrest', (.18, .28, .06), (0, yd(s_hp + .02), hip + .03), T['seat_leather'], bevel=.025, segs=3))
        P.append(cylo('boot', .045, .08, (0, yd(s_hp - .36), hip - .0), T['seat_leather'], 16, r2=.022))
        P.append(cylo('lever', .01, .1, (0, yd(s_hp - .36), hip + .06), M['chrome'], 10))
        P.append(bl.sphere('knob', .028, (0, yd(s_hp - .36), hip + .12), T['seat_leather'], 16, 10, scale=(1, 1.2, .9)))
        P[-1].name = 'knob'; bl.apply_all(P[-1]); bl.uv_box(P[-1], .2)
        for k in (0, 1):
            P.append(cylo('cup', .038, .01, (0, yd(s_hp - .18 + k * .085), hip - .02), M['vent'], 18))
        P.append(cylo('start', .014, .01, (xs - .22, yd(s_dash - .0), belt - .05), M['needle'], 14, rot=(math.pi / 2, 0, 0)))
        # steering column (static) — the wheel itself is a separate object
        hub = Vector((xs, yd(s_hp - .58), hip + .38))
        wt = .42
        n = Vector((0, math.cos(wt), math.sin(wt)))     # wheel normal toward the driver (+Y back, tilted up)
        P.append(line_box('column', hub - n * .06, hub - n * .32, .07, .07, M['trim_black']))
        for sx in (-1, 1):
            P.append(line_box('stalk', hub - n * .08 + Vector((sx * .04, 0, 0)), hub - n * .08 + Vector((sx * .14, 0, .01)), .012, .012, M['trim_black']))
        self.hub, self.wheel_tilt = hub, wt
        # pedals
        for k, (dx, w) in enumerate(((-.06, .1), (.1, .05))):
            P.append(boxo('pedal', (w, .02, .07), (xs + dx, yd(s_hp - .9), fl + .14), M['rubber'], bevel=.006, rot=(.5, 0, 0)))
        # seats
        P += self.seat(xs, s_hp, True) + self.seat(-xs, s_hp, False)
        if self.s_rhp:
            wr = self.x_at(self.s_rhp, hip) - .1
            P += self.bench(self.s_rhp, wr)
        # rear: parcel shelf / cargo bay / partition
        if c.get('partition'):
            ws = self.x_at(s_hp + .4, belt) - .05
            P.append(boxo('partition', (2 * ws, .03, c['roof'] - fl - .06), (0, yd(s_hp + .42), (c['roof'] + fl) / 2 - .03), T['dash_lower'], uvs=.5))
            P.append(boxo('partwin', (.6, .035, .25), (0, yd(s_hp + .42), c['roof'] - .32), M['glass_side']))
        elif not c['cargo'] and self.s_rhp:
            wsh = self.x_at(c['rear'], belt) - .05
            P.append(boxo('shelf', (2 * wsh, c['rear'] - self.s_rhp - .25, .02), (0, yd((c['rear'] + self.s_rhp + .25) / 2), belt - .02), M['trim_black'], uvs=.4))
            P.append(boxo('trunkwall', (2 * wsh, .02, belt - fl), (0, yd(self.s_rhp + .3), (belt + fl) / 2), M['carpet'], uvs=.5))
        elif c.get('bed'):
            ww = self.x_at(c['rear'], belt) - .05
            P.append(boxo('cabwall', (2 * ww, .02, belt - fl + .02), (0, yd(c['rear'] - .04), (belt + fl) / 2), T['dash_lower'], uvs=.5))
        if c['cargo']:
            cf0 = (self.s_rhp + .32) if self.s_rhp else s_hp + .45
            wc = self.x_at(cf0, fl + .2) - .07
            P.append(boxo('cargo', (2 * wc, self.L - .24 - cf0, .02), (0, yd((self.L - .24 + cf0) / 2), fl + .1), M['carpet'], uvs=.5))
            P.append(boxo('tailin', (2 * wc, .03, belt - fl), (0, yd(self.L - .22), (belt + fl) / 2 + .02), T['dash_lower'], uvs=.5))
        # door details: armrests, pulls, speakers, switch packs
        for sx in (1, -1):
            for s0, front in ((s_hp, True), (self.s_rhp, False)):
                if not s0 or (not front and c.get('partition')):
                    continue
                xw = self.x_at(s0, hip) - .055
                P.append(boxo('darm', (.08, .42, .05), (sx * (xw - .04), yd(s0 - .16), hip + .1), T['seat_leather'], bevel=.018, segs=3))
                P.append(boxo('dpull', (.02, .12, .025), (sx * (xw - .02), yd(s0 - .5), hip + .28), M['chrome'], bevel=.006))
                P.append(cylo('dspk', .075, .012, (sx * (self.x_at(s0 - .45, fl + .22) - .06), yd(s0 - .45), fl + .22), M['speaker'], 24, rot=(0, math.pi / 2, 0)))
                P.append(boxo('dsw', (.05, .12, .012), (sx * (xw - .05), yd(s0 - .25), hip + .13), M['trim_gloss'], bevel=.004))
        # headliner furniture: sun visors, interior mirror, dome lamp, seat belts on the B-pillars
        zr = c['roof'] - .03
        for sx in (1, -1):
            P.append(boxo('sunvisor', (.36, .17, .025), (sx * .34, yd(c['atop'] + .1), zr - .03), M['headliner'], bevel=.01, rot=(-.15, 0, 0), uvs=.4))
            bs = (c['blackB'][0] + c['blackB'][1]) / 2
            bx = self.x_at(bs, belt) - .09
            P.append(line_box('belt', (sx * bx, yd(bs + .02), c['roof'] - .2), (sx * (bx - .02), yd(bs + .06), fl + .2), .05, .004, M['trim_black']))
        P.append(boxo('rvm', (.25, .035, .07), (0, yd(c['atop'] + .12), zr - .1), M['trim_black'], bevel=.015, segs=3))
        P.append(boxo('rvmg', (.23, .004, .055), (0, yd(c['atop'] + .12) + .019, zr - .1), M['mirror']))
        P.append(line_box('rvms', (0, yd(c['atop'] + .1), zr - .07), (0, yd(c['atop'] + .06), zr + .01), .02, .02, M['trim_black']))
        P.append(boxo('dome', (.16, .08, .012), (0, yd(c['atop'] + .35), zr), M['headliner'], bevel=.005))
        return P

    def seat(self, x, s, driver):
        c, M, T = self.c, self.M, self.T
        hip, fl = self.hip, c['floor']
        yd = self.Y
        P = []
        cz = hip - .1                         # cushion top
        # cushion: leather base, quilted insert between raised bolsters
        P.append(boxo('cush', (.5, .52, .1), (x, yd(s - .2), cz - .05), T['seat_leather'], bevel=.03, segs=3, uvs=.3))
        P.append(boxo('cushin', (.3, .46, .03), (x, yd(s - .2), cz + .005), T['seat_insert'], bevel=.012, segs=2, uvs=.24))
        for sx in (-1, 1):
            P.append(boxo('cbol', (.09, .48, .07), (x + sx * .2, yd(s - .2), cz + .01), T['seat_leather'], bevel=.03, segs=3, rot=(0, sx * .25, 0)))
        P.append(boxo('base', (.42, .45, cz - fl - .1), (x, yd(s - .2), (cz - .1 + fl) / 2), M['trim_black'], bevel=.02))
        # backrest (reclined ~20 degrees), insert, side bolsters, headrest on two posts
        rec = .34
        bh = .62
        by = s + .08 + math.sin(rec) * bh / 2
        bz = cz + math.cos(rec) * bh / 2 + .02
        P.append(boxo('back', (.5, .11, bh), (x, yd(by), bz), T['seat_leather'], bevel=.035, segs=3, rot=(-rec, 0, 0)))
        P.append(boxo('backin', (.3, .03, bh - .1), (x, yd(by - .06 * math.cos(rec)), bz - .01), T['seat_insert'], bevel=.012, rot=(-rec, 0, 0), uvs=.24))
        for sx in (-1, 1):
            P.append(boxo('bbol', (.08, .1, bh - .08), (x + sx * .21, yd(by - .04), bz), T['seat_leather'], bevel=.03, segs=3, rot=(-rec, 0, sx * .3)))
        ty = s + .08 + math.sin(rec) * bh
        tz = cz + math.cos(rec) * bh + .02
        P.append(boxo('head', (.26, .1, .17), (x, yd(ty + .02), tz + .13), T['seat_leather'], bevel=.04, segs=3, rot=(-rec * .5, 0, 0)))
        for sx in (-1, 1):
            P.append(cylo('post', .007, .1, (x + sx * .08, yd(ty + .015), tz + .04), M['chrome'], 8))
        return P

    def bench(self, s, wr):
        c, M, T = self.c, self.M, self.T
        hip, fl = self.hip - .02, c['floor']
        yd = self.Y
        P = []
        cz = hip - .1
        P.append(boxo('rcush', (2 * wr, .5, .12), (0, yd(s - .18), cz - .06), T['seat_leather'], bevel=.035, segs=3))
        for x in (-wr * .55, wr * .55):
            P.append(boxo('rin', (wr * .7, .44, .03), (x, yd(s - .18), cz + .005), T['seat_insert'], bevel=.012, uvs=.24))
        P.append(boxo('rbase', (2 * wr - .1, .4, cz - fl - .12), (0, yd(s - .18), (cz - .12 + fl) / 2), M['trim_black']))
        rec = .3; bh = .6
        by = s + .08 + math.sin(rec) * bh / 2; bz = cz + math.cos(rec) * bh / 2 + .02
        P.append(boxo('rback', (2 * wr, .12, bh), (0, yd(by), bz), T['seat_leather'], bevel=.04, segs=3, rot=(-rec, 0, 0)))
        for x in (-wr * .55, wr * .55):
            P.append(boxo('rbin', (wr * .7, .03, bh - .12), (x, yd(by - .065 * math.cos(rec)), bz - .01), T['seat_insert'], bevel=.012, rot=(-rec, 0, 0), uvs=.24))
            ty = s + .08 + math.sin(rec) * bh; tz = cz + math.cos(rec) * bh + .02
            P.append(boxo('rhead', (.24, .09, .13), (x, yd(ty + .02), tz + .09), T['seat_leather'], bevel=.035, segs=3, rot=(-rec * .5, 0, 0)))
        return P

    # ---------------- steering wheel and needles (animated objects)
    def steering(self):
        M, T = self.M, self.T
        P = []
        P.append(bl.torus('rim', .185, .016, (0, 0, 0), M['steering'], rot=(math.pi / 2, 0, 0), maj=40, mn=10))
        P.append(cylo('hub', .075, .05, (0, -.03, 0), M['steering'], 24, rot=(math.pi / 2, 0, 0)))
        P.append(cylo('emb', .022, .006, (0, -.0, 0), M['chrome'], 20, rot=(math.pi / 2, 0, 0)))
        for a in (0, math.pi, -math.pi / 2):
            d = Vector((math.cos(a), 0, math.sin(a)))
            P.append(line_box('spoke', d * .06 + Vector((0, -.025, 0)), d * .175 + Vector((0, -.008, 0)), .045 if a != -math.pi / 2 else .05, .016, T['dash_lower']))
        for sx in (-1, 1):
            P.append(boxo('btn', (.03, .008, .02), (sx * .1, .002, .0), T['accent']))
        for o in P:
            bl.apply_all(o)
        bl.uv_box(P[0], .2)
        st = bl.join(P, 'steer_' + self.k)
        st.location = self.hub
        st.rotation_euler = (self.wheel_tilt, 0, 0)     # local +Y (toward the driver) tilts up by the column angle
        return st

    def needle_objs(self):
        out = []
        for k, p, tilt in self.needles:
            mb = MB()
            # local frame: needle points +Z (up on the dial), faces +Y (toward the driver)
            vs = [(-.0035, 0, -.012), (.0035, 0, -.012), (.0012, 0, .068), (-.0012, 0, .068)]
            ids = [mb.vert(v) for v in vs]
            mb.face(ids[::-1], 'needle')
            cap = [mb.vert((math.cos(a) * .009, .002, math.sin(a) * .009)) for a in [2 * math.pi * i / 10 for i in range(10)]]
            mb.face(cap, 'trim_gloss')
            o = mb.build('needle%s_%s' % (k, self.k), self.M)
            o.location = p
            o.rotation_euler = (tilt, 0, 0)
            out.append(o)
        return out

    # ---------------- wheels
    def lathe(self, mb, prof, segs, mat, side, uvmode, rot0=0.0):
        """Revolve (r, x) profile around the X axis. side=+1 builds a left wheel (outer face +X)."""
        n = len(prof)
        cum = [0.0]
        for (r0, x0), (r1, x1) in zip(prof, prof[1:]):
            cum.append(cum[-1] + math.hypot(r1 - r0, x1 - x0))
        ids = []
        for i in range(segs + 1):
            a = 2 * math.pi * i / segs + rot0
            row = []
            for (r, x) in prof:
                row.append(mb.vert((side * x, r * math.sin(a), r * math.cos(a))))
            ids.append(row)
        for i in range(segs):
            for j in range(n - 1):
                q = [ids[i][j], ids[i + 1][j], ids[i + 1][j + 1], ids[i][j + 1]]
                if side < 0:
                    q = q[::-1]
                uv = None
                if uvmode:
                    def U(ii, jj):
                        u = 2.0 * ii / segs
                        if side < 0:
                            u = -u
                        return (u, uvmode(jj, cum[jj] / cum[-1]))
                    uu = [U(i, j), U(i + 1, j), U(i + 1, j + 1), U(i, j + 1)]
                    uv = uu if side > 0 else uu[::-1]
                mb.face(q, mat, uv)

    def wheel(self, side, rear):
        c, M = self.c, self.M
        rw, tw = c['rw'], c['tw']
        hw = tw / 2
        sh = rw * .3
        rb = rw - sh
        segs = 48 if not self.lo else 14
        spin = MB()
        tp = [(rb + .004, hw * .8), (rb + sh * .35, hw * .98), (rb + sh * .7, hw), (rw - .03, hw * .95), (rw - .008, hw * .82), (rw, hw * .55),
              (rw, 0), (rw, -hw * .55), (rw - .008, -hw * .82), (rw - .03, -hw * .95), (rb + sh * .7, -hw), (rb + sh * .35, -hw * .98), (rb + .004, -hw * .8)]
        bands = [0, 4, 8, 12]

        def tv(j, f):
            if j <= 4:
                return .3 * j / 4
            if j <= 8:
                return .3 + .4 * (j - 4) / 4
            return .7 + .3 * (j - 8) / 4
        self.lathe(spin, tp, segs, 'tyre', side, tv)
        rimm = c['rim']
        if c.get('knobby') and not self.lo:
            # chunky off-road lugs: staggered blocks standing proud of the tread
            n = 26
            for i in range(n):
                for k, (x0, x1) in enumerate(((-hw * .95, -hw * .1), (hw * .1, hw * .95))):
                    a0 = 2 * math.pi * (i + (.5 if k else 0)) / n
                    da = 2 * math.pi / n * .55
                    vs = []
                    for rr in (rw - .005, rw + .035):
                        for aa, xx in ((a0, x0), (a0 + da, x0), (a0 + da * 1.25, x1), (a0 + da * .25, x1)):
                            vs.append((side * xx, rr * math.sin(aa), rr * math.cos(aa)))
                    ids = [spin.vert(v) for v in vs]
                    for f in ((4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                        q = [ids[j] for j in f]
                        spin.face(q if side > 0 else q[::-1], 'tyre', [(.1, .5), (.14, .5), (.14, .62), (.1, .62)])
        if self.lo:
            self.lathe(spin, [(rb + .006, hw * .78), (rb * .3, hw * .55), (0.0, hw * .5)], segs, rimm, side, None)
            return spin, None
        # rim barrel + lip
        self.lathe(spin, [(rb + .012, hw * .82), (rb + .012, hw * .74), (rb - .012, hw * .7), (rb - .02, hw * .55), (rb - .02, -hw * .7), (rb + .01, -hw * .8)], segs, rimm, side, None)
        # dark barrel interior
        self.lathe(spin, [(rb - .022, hw * .5), (rb - .022, -hw * .6)], segs, 'wheelwell', -side, None)
        # spokes: 5 split spokes dishing toward the hub
        for k in range(10):
            a = 2 * math.pi * (k // 2) / 5 + (k % 2 - .5) * .16
            ca, sa = math.cos(a), math.sin(a)
            r0, r1 = .075, rb - .015
            x0, x1 = hw * .3, hw * .62
            wd0, wd1 = .016, .022
            vs = []
            for (r, x, wdt) in ((r0, x0, wd0), (r1, x1, wd1)):
                for dx, dw in ((.012, -1), (.012, 1), (-.012, 1), (-.012, -1)):
                    t = Vector((0, -sa, ca)) * 0
                    pr = Vector((0, sa * r, ca * r)) + Vector((0, ca, -sa)) * (dw * wdt)
                    vs.append((side * (x + dx), pr.y, pr.z))
            ids = [spin.vert(v) for v in vs]
            for f in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                q = [ids[i] for i in f]
                spin.face(q if side > 0 else q[::-1], rimm)
        # hub, centre cap, lug nuts
        self.lathe(spin, [(.08, hw * .3), (.08, hw * .42), (.03, hw * .48), (0.0, hw * .48)], 20, rimm, side, None)
        for k in range(5):
            a = 2 * math.pi * k / 5 + .3
            cx_, cz_ = .055 * math.sin(a), .055 * math.cos(a)
            self.lathe_small(spin, (side * hw * .44, cx_, cz_), .009, .02, side)
        # brake disc (spins) + caliper (steers, does not spin)
        dx = hw * .05
        dp = [(rb - .045, dx + .012), (.06, dx + .012)]
        def dv(j, f):
            return 1 - j
        self.lathe(spin, [(rb - .045, dx + .012), (.07, dx + .012)], 32, 'brake_disc', side, lambda j, f: 1.0 - j)
        self.lathe(spin, [(.07, dx - .012), (rb - .045, dx - .012)], 32, 'brake_disc', side, lambda j, f: float(j))
        self.lathe(spin, [(rb - .045, dx + .012), (rb - .045, dx - .012)], 32, 'brake_disc', side, lambda j, f: 1.0)
        cal = MB()
        a0, a1 = .35, 1.15                   # behind the axle, upper quarter
        rows = []
        for i in range(7):
            a = a0 + (a1 - a0) * i / 6
            rr0, rr1 = rb - .1, rb - .035
            rows.append([(side * x, r * math.sin(a), r * math.cos(a)) for (r, x) in ((rr0, dx + .045), (rr1, dx + .045), (rr1, dx + .015), (rr1, dx - .03), (rr0, dx - .03), (rr0, dx + .015))])
        cal.quad_grid(rows, lambda i, j, cc: 'caliper' if not rear else 'caliper_grey', closed=True, flip=side < 0)
        return spin, cal

    def lathe_small(self, mb, ctr, r, h, side):
        cx, cy, cz = ctr
        n = 6
        top = [mb.vert((cx + side * h, cy + r * math.sin(2 * math.pi * i / n), cz + r * math.cos(2 * math.pi * i / n))) for i in range(n)]
        bot = [mb.vert((cx, cy + r * math.sin(2 * math.pi * i / n), cz + r * math.cos(2 * math.pi * i / n))) for i in range(n)]
        mb.face(top if side > 0 else top[::-1], self.c['rim'])
        for i in range(n):
            q = [bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]]
            mb.face(q if side > 0 else q[::-1], self.c['rim'])

    def wheels(self, parent):
        c = self.c
        out = []
        for name, sx, rear in (('FL', 1, False), ('FR', -1, False), ('RL', 1, True), ('RR', -1, True)):
            s = c['foh'] + (c['wb'] if rear else 0)
            pos = (sx * c['track'] / 2, self.Y(s), c['rw'])
            spin, cal = self.wheel(sx, rear)
            if self.lo:
                o = spin.build('lw', self.M)
                o.location = pos
                out.append(o)
                continue
            piv = bl.empty('wheel_%s_%s' % (name, self.k), pos, parent)
            so = spin.build('spin_%s_%s' % (name, self.k), self.M, {'rim': .3, 'wheelwell': 1})
            so.parent = piv
            co = cal.build('cal_%s_%s' % (name, self.k), self.M)
            co.parent = piv
            out.append(piv)
        return out

    # ---------------- assemble
    def build(self, root):
        c, M = self.c, self.M
        self.T = theme_mats(self.k, c['theme'])
        hi = bl.empty('hi_' + self.k, (0, 0, 0), root)
        body = self.body()
        gh = self.greenhouse()
        self.make_bvh([body, gh[0]])
        det = self.details()
        hw = self.hardware()
        inter = self.interior()
        for o in hw + inter:
            bl.apply_all(o)
        shell = bl.join([body, gh[0], det] + hw, 'body_' + self.k)
        inside = bl.join(gh[1:] + inter, 'int_' + self.k)
        for o in (shell, inside):
            o.parent = hi
        st = self.steering(); st.parent = hi
        for n in self.needle_objs():
            n.parent = hi
        self.wheels(hi)
        bl.empty('seat_' + self.k, (c['xs'], self.Y(self.s_hp), self.hip), root)
        bl.empty('eye_' + self.k, (c['xs'], self.Y(self.s_hp - .06), self.hip + .74), root)
        return hi

    def build_lo(self, root):
        self.T = theme_mats(self.k, self.c['theme'])
        body = self.body()
        gh = self.greenhouse()[0]
        self.make_bvh([body, gh])
        det = self.details()
        c, M = self.c, self.M
        # cabin silhouette behind the dark glass
        fill = boxo('fill', (2 * (self.x_at(self.s_hp, c['belt']) - .1), c['rear'] - c['cowl'] - .2, .35), (0, self.Y((c['cowl'] + c['rear']) / 2), c['belt'] + .1), M['trim_black'])
        wl = self.wheels(None)
        for o in wl:
            bl.apply_all(o)
        lo = bl.join([body, gh, det, fill] + wl, 'lo_' + self.k)
        # merge the few extra materials of the low model into the shared set
        keep = ['car_paint', 'trim_black', 'glass_lo', 'lamp_head', 'lamp_tail', 'tyre', c['rim']]
        mats = [m.name for m in lo.data.materials]
        remap = {'wheelwell': 'trim_black', 'trim_gloss': 'trim_black', 'grille': 'trim_black', 'chrome': c['rim'], 'badge': c['rim'], 'plate': 'trim_black', 'rim_dark': c['rim'], 'rim': c['rim']}
        newm = []
        for nm in keep:
            if nm in mats or nm in remap.values():
                newm.append(nm)
        idx = []
        for nm in mats:
            t = nm if nm in keep else remap.get(nm, 'trim_black')
            if t not in newm:
                newm.append(t)
            idx.append(newm.index(t))
        polys = [idx[p.material_index] for p in lo.data.polygons]
        lo.data.materials.clear()
        for nm in newm:
            lo.data.materials.append(M[nm] if nm in M else bpy.data.materials[nm])
        for p, i in zip(lo.data.polygons, polys):
            p.material_index = i
        lo.parent = root
        return lo

    def meta(self):
        """Dimensions for the game (three.js space: x = Blender x, y = up, z = -Blender y)."""
        c = self.c
        tz = lambda s: -(s - self.y0)
        return dict(
            name=c['name'], len=c['L'], wid=c['W'], roof=c['roof'], belt=c['belt'], clear=self.zbot(c['foh'] + c['wb'] / 2),
            front=tz(0), back=tz(c['L']), wb=c['wb'], track=c['track'], rw=c['rw'],
            axleF=tz(c['foh']), axleR=tz(c['foh'] + c['wb']),
            cab=[tz(c['rear']), tz(c['cowl'])], hood=[0, (self.ztop(c['foh']) + .05), tz(c['foh'] + .1)],
            seat=[c['xs'], self.hip, tz(self.s_hp)], eye=[c['xs'], self.hip + .74, tz(self.s_hp - .06)],
            paint=c['paint'])


def lo_materials(lo, M, rim):
    keep = ['car_paint', 'trim_black', 'glass_lo', 'lamp_head', 'lamp_tail', 'tyre', rim, 'rover_accent']
    mats = [m.name for m in lo.data.materials]
    remap = {'wheelwell': 'trim_black', 'trim_gloss': 'trim_black', 'grille': 'trim_black', 'chrome': rim, 'badge': rim, 'plate': 'trim_black',
             'rim_dark': rim, 'rim': rim, 'glass_front': 'glass_lo'}
    newm, idx = [], []
    for nm in mats:
        t = nm if nm in keep else remap.get(nm, 'trim_black')
        if t not in newm:
            newm.append(t)
        idx.append(newm.index(t))
    polys = [idx[p.material_index] for p in lo.data.polygons]
    lo.data.materials.clear()
    for nm in newm:
        lo.data.materials.append(M[nm] if nm in M else bpy.data.materials[nm])
    for p, i in zip(lo.data.polygons, polys):
        p.material_index = i


def tube(a, b, r, mat, n=10):
    a, b = Vector(a), Vector(b)
    d = b - a
    o = bl.cyl('tube', r, d.length, (0, 0, 0), mat, n)
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized()); o.location = (a + b) / 2
    bl.apply_all(o)
    bl.uv_box(o, .3)
    return o


class Rover(Car):
    """Open all-terrain rover: white tub, orange accents, roll cage, huge lugged tyres, long-travel arms."""

    def parts(self, lo=False):
        c, M, T = self.c, self.M, self.T
        yd = self.Y
        P = []
        paint, acc, dark = M['car_paint'], M['rover_accent'], M['trim_black']
        cage = M['rim_dark']
        fl, belt, roof = c['floor'], c['belt'], c['roof']
        # tub (open top): floor pan, sides, firewall/dash wall, back wall
        s0, s1, wt = .95, 2.8, .78
        P.append(boxo('tubfloor', (2 * wt, s1 - s0, .1), (0, yd((s0 + s1) / 2), fl - .05), dark, uvs=.6))
        for sx in (1, -1):
            P.append(boxo('tubside', (.08, s1 - s0, belt - fl + .08), (sx * (wt - .04), yd((s0 + s1) / 2), (belt + fl) / 2 - .04), paint, bevel=.03, segs=3))
            P.append(boxo('tubstripe', (.085, s1 - s0 - .2, .06), (sx * (wt - .04), yd((s0 + s1) / 2), fl + .12), acc))
            P.append(boxo('step', (.18, .9, .04), (sx * (wt + .1), yd(1.9), fl - .02), dark, bevel=.01))
        P.append(boxo('tubback', (2 * wt, .08, belt - fl + .1), (0, yd(s1), (belt + fl) / 2), paint, bevel=.03, segs=3))
        # nose: sloped bonnet over a chassis box, bull bar, skid plate, round lamps
        P.append(boxo('nosebox', (1.5, .95, .36), (0, yd(.5), .78), paint, bevel=.08, segs=3))
        P.append(boxo('bonnet', (1.42, .8, .1), (0, yd(.62), .98), paint, bevel=.04, segs=3, rot=(-.16, 0, 0)))
        P.append(boxo('skid', (1.2, .5, .05), (0, yd(.28), .58), dark, bevel=.02, rot=(.5, 0, 0)))
        if not lo:
            for sx in (1, -1):
                P.append(tube((sx * .62, yd(.02), .62), (sx * .62, yd(.02), .98), .035, cage))
                P.append(cylo('lampf', .085, .06, (sx * .5, yd(.03), .86), M['lamp_head'], 20, rot=(math.pi / 2, 0, 0)))
                P.append(cylo('lampr', .1, .05, (sx * .5, yd(.05), .86), M['chrome'], 20, rot=(math.pi / 2, 0, 0)))
                P.append(boxo('vent', (.36, .04, .1), (sx * .32, yd(.6), 1.06), dark, rot=(-.16, 0, 0)))
            P.append(tube((-.62, yd(.02), .98), (.62, yd(.02), .98), .035, cage))
            P.append(tube((-.62, yd(.02), .7), (.62, yd(.02), .7), .035, cage))
            P.append(boxo('grillebar', (.7, .03, .18), (0, yd(.02), .82), M['grille'], uvs=.25))
        # rear deck with cargo box, tail lamps, spare wheel mount
        P.append(boxo('deck', (1.5, 1.05, .32), (0, yd(3.35), .82), paint, bevel=.06, segs=3))
        P.append(boxo('cargo', (1.3, .7, .3), (0, yd(3.3), 1.12), acc, bevel=.04, segs=3))
        for sx in (1, -1):
            P.append(boxo('tail', (.22, .04, .08), (sx * .58, yd(3.9), .9), M['lamp_tail'], uvs=.2))
        # fenders over the wheels (white shells, orange inner lip)
        for sa in (c['foh'], c['foh'] + c['wb']):
            for sx in (1, -1):
                mb = MB()
                R = c['rw'] + .1
                rows = []
                for k in range(13):
                    ang = math.radians(15 + 150 * k / 12)
                    y = yd(sa) - math.cos(ang) * R
                    z = c['rw'] + math.sin(ang) * R
                    rows.append([(sx * (c['track'] / 2 + x), y, z) for x in (-c['tw'] / 2 - .1, c['tw'] / 2 + .08)])
                mb.quad_grid(rows, lambda i, j, cc: 'car_paint')
                P.append(mb.build('fender', M))
                if not lo:
                    # long-travel suspension: upper/lower arms + coil-over
                    hub = Vector((sx * (c['track'] / 2 - c['tw'] / 2 - .02), yd(sa), c['rw']))
                    for dz, zc in ((-.08, .62), (.1, .86)):
                        for dy in (-.18, .18):
                            P.append(tube((sx * .5, yd(sa) + dy, zc), hub + Vector((0, 0, dz)), .025, cage, 8))
                    top = Vector((sx * .62, yd(sa), 1.12))
                    P.append(tube(top, hub + Vector((-sx * .12, 0, -.04)), .025, M['chrome'], 10))          # damper shaft
                    P.append(tube(top + (hub - top) * .1, top + (hub - top) * .6, .055, acc, 12))           # coil spring
        # roll cage
        r = .032 if not lo else .04
        n = 10 if not lo else 6
        hf, hr = 1.18, 2.55                      # front hoop base, main hoop
        tf, tr = 1.55, 2.5
        for sx in (1, -1):
            P.append(tube((sx * .74, yd(hf), belt), (sx * .62, yd(tf), roof), r, cage, n))
            P.append(tube((sx * .74, yd(hr), belt), (sx * .62, yd(tr), roof), r, cage, n))
            P.append(tube((sx * .62, yd(tf), roof), (sx * .62, yd(tr), roof), r, cage, n))
            P.append(tube((sx * .62, yd(tr), roof), (sx * .6, yd(3.75), .98), r, cage, n))
            P.append(tube((sx * .74, yd(hf), belt), (sx * .62, yd(.9), 1.05), r, cage, n))
        for s_, z_ in ((tf, roof), (tr, roof), (hf, belt + .02)):
            P.append(tube((-.62 if z_ == roof else -.74, yd(s_), z_), (.62 if z_ == roof else .74, yd(s_), z_), r, cage, n))
        P.append(tube((-.62, yd(tr), roof), (.62, yd(tf), roof), r * .8, cage, n))
        # light bar on the front roof bar
        P.append(boxo('lightbar', (1.0, .1, .08), (0, yd(tf - .02), roof + .07), dark, bevel=.02))
        if not lo:
            for k in range(4):
                P.append(cylo('bar_lamp', .035, .02, (-.36 + k * .24, yd(tf - .075), roof + .07), M['lamp_head'], 14, rot=(math.pi / 2, 0, 0)))
        # windscreen pane in the front hoop
        mb = MB()
        q = [mb.vert((x, yd(s_), z_)) for x, s_, z_ in ((-.7, hf + .02, belt + .03), (.7, hf + .02, belt + .03), (.6, tf - .02, roof - .04), (-.6, tf - .02, roof - .04))]
        mb.face(q, 'glass_front' if not lo else 'glass_lo')
        P.append(mb.build('screen_glass', M))
        return P

    def cockpit(self):
        c, M, T = self.c, self.M, self.T
        yd = self.Y
        P = []
        fl, hip, belt, xs = c['floor'], self.hip, c['belt'], c['xs']
        s_hp = self.s_hp
        s_dash = s_hp - .74
        # dash: a padded beam across the tub with the cluster and a screen
        P.append(boxo('dash', (1.48, .32, .3), (0, yd(s_dash - .2), belt - .05), T['dash_soft'], bevel=.05, segs=3, uvs=.3))
        P.append(boxo('dashlow', (1.4, .3, .35), (0, yd(s_dash - .2), fl + .2), T['dash_lower'], bevel=.04, uvs=.3))
        gz, tilt = belt + .14, .3
        q = MB()
        gw, gh = .3, .15
        gp = lambda u, v: (xs + (u - .5) * gw, yd(s_dash) - .01 - (v - .5) * gh * math.sin(tilt), gz + (v - .5) * gh * math.cos(tilt))
        ids = [q.vert(gp(0, 0)), q.vert(gp(1, 0)), q.vert(gp(1, 1)), q.vert(gp(0, 1))]
        q.face(ids, 'gauges', [(1, 0), (0, 0), (0, 1), (1, 1)])
        P.append(q.build('gauge', M))
        P.append(boxo('podr', (.36, .14, .2), (xs, yd(s_dash - .11), gz), T['dash_soft'], bevel=.03, segs=3, rot=(tilt, 0, 0)))
        self.needles = [(k, Vector((xs + (u - .5) * gw * -1, yd(s_dash) - .003, gz)), tilt) for k, u in (('S', .25), ('R', .75))]
        sq = MB()
        sp = lambda u, v: ((u - .5) * .24, yd(s_dash) - .02 - (v - .5) * .13 * math.sin(.25), belt + .05 + (v - .5) * .13 * math.cos(.25))
        ids = [sq.vert(sp(0, 0)), sq.vert(sp(1, 0)), sq.vert(sp(1, 1)), sq.vert(sp(0, 1))]
        sq.face(ids, 'screen', [(1, 0), (0, 0), (0, 1), (1, 1)])
        P.append(sq.build('screen', M))
        hub = Vector((xs, yd(s_hp - .58), hip + .38))
        wt = .42
        nrm = Vector((0, math.cos(wt), math.sin(wt)))
        P.append(line_box('column', hub - nrm * .06, hub - nrm * .32, .07, .07, M['trim_black']))
        self.hub, self.wheel_tilt = hub, wt
        # centre tunnel with a gear lever, rubber floor, pedals
        P.append(boxo('tunnel', (.24, .9, .22), (0, yd(s_hp - .2), fl + .11), T['dash_lower'], bevel=.03))
        P.append(cylo('lever', .012, .16, (0, yd(s_hp - .3), fl + .3), M['chrome'], 10))
        P.append(bl.sphere('knob', .03, (0, yd(s_hp - .3), fl + .39), T['seat_leather'], 16, 10)); bl.apply_all(P[-1]); bl.uv_box(P[-1], .2)
        P.append(boxo('mat', (1.4, 1.6, .012), (0, yd(s_hp - .3), fl + .006), M['bedliner'], uvs=.5))
        for dx, w in ((-.06, .1), (.1, .05)):
            P.append(boxo('pedal', (w, .02, .07), (xs + dx, yd(s_hp - .9), fl + .14), M['rubber'], bevel=.006, rot=(.5, 0, 0)))
        P += self.seat(xs, s_hp, True) + self.seat(-xs, s_hp, False)
        # harness straps hanging from the main hoop
        for x in (xs, -xs):
            for dx in (-.12, .12):
                P.append(line_box('harness', (x + dx, yd(2.55), c['roof'] - .25), (x + dx * .6, yd(s_hp + .25), hip + .55), .045, .004, M['rover_accent']))
        return P

    def build(self, root):
        c, M = self.c, self.M
        self.T = theme_mats(self.k, c['theme'])
        hi = bl.empty('hi_' + self.k, (0, 0, 0), root)
        P = self.parts() + self.cockpit()
        for o in P:
            bl.apply_all(o)
        shell = bl.join(P, 'body_' + self.k)
        shell.parent = hi
        st = self.steering(); st.parent = hi
        for n in self.needle_objs():
            n.parent = hi
        self.wheels(hi)
        bl.empty('seat_' + self.k, (c['xs'], self.Y(self.s_hp), self.hip), root)
        bl.empty('eye_' + self.k, (c['xs'], self.Y(self.s_hp - .06), self.hip + .74), root)
        return hi

    def build_lo(self, root):
        self.T = theme_mats(self.k, self.c['theme'])
        P = self.parts(lo=True)
        wl = self.wheels(None)
        for o in P + wl:
            bl.apply_all(o)
        lo = bl.join(P + wl, 'lo_' + self.k)
        lo_materials(lo, self.M, self.c['rim'])
        lo.parent = root
        return lo


def build_cars(only=None):
    bl.reset(); _M.clear()
    M = common_mats()
    for i, k in enumerate(CARS):
        if only and k not in only:
            continue
        root = bl.empty('CAR_' + k, (0, 0, 0))
        K = Rover if k == 'rover' else Car
        car = K(k, M)
        car.build(root)
        lo = K(k, M, lo=True)
        lo.build_lo(root)
        root['worldex'] = json.dumps(car.meta())
        root.location.x = i * 3.0
        print('[car]', k, 'built')
    bl.export('cars.glb')


# ------------------------------------------------------------------ hover boards
def build_boards():
    for name, wide, paint in (('board_sport', False, '#a3121f'), ('board_utility', True, '#2a4f7a')):
        bl.reset(); _M.clear()
        M = common_mats()
        P_ = bl.palette()
        grip = tmat('grip', '#ffffff', 0, .95, img='veh_grip_c.jpg', nrm='veh_grip_n.jpg')
        carbon = tmat('board_carbon', '#3a3c40', .4, .35, img='carbon_c.jpg')
        glow = tmat('hover_glow', '#3ad6ff', 0, .3, emit='#3ad6ff', strength=8)
        light = tmat('board_light', '#fff4e0', 0, .3, emit='#fff4e0', strength=6)
        tail = tmat('board_tail', '#ff2030', 0, .3, emit='#ff2030', strength=5)
        L = 1.32 if not wide else 1.4
        W = .34 if not wide else .44
        T = .045
        z0 = 0.0                                    # deck underside at the origin (board hovers above ground)
        # deck: lofted along its length with kicktails, rounded ends
        prof = []
        N = 26
        for i in range(N + 1):
            t = i / N
            y = -L / 2 + L * t
            e = abs(2 * t - 1)
            w = W / 2 * (1 - max(0, e - .7) ** 2 * 4.2) if not wide else W / 2 * (1 - max(0, e - .78) ** 2 * 3.5)
            w = max(w, .04)
            kick = max(0, e - .74) ** 2 * (1.6 if not wide else 1.0)
            ring = []
            for j in range(16):
                a = 2 * math.pi * j / 16
                ca, sa = math.cos(a), math.sin(a)
                x = w * math.copysign(abs(ca) ** .35, ca)
                zz = T / 2 * math.copysign(abs(sa) ** .5, sa)
                concave = .008 * (1 - (x / max(w, 1e-3)) ** 2) if sa > 0 else 0
                ring.append((x, y, z0 + T / 2 + zz + kick - concave))
            prof.append(ring)
        deck = bl.loft('deck', prof, carbon)
        obj_mats(deck, [carbon, grip, M['car_paint']])
        for p in deck.data.polygons:
            if p.normal.z > .6:
                p.material_index = 1
            elif abs(p.normal.z) < .6:
                p.material_index = 2
        bl.uv_box(deck, .35)
        parts = [deck]
        # rails (painted bumpers) along both edges + nose/tail light bars
        for sx in (1, -1):
            pts = []
            for i in range(9):
                t = .12 + .76 * i / 8
                y = -L / 2 + L * t
                pts.append((sx * (W / 2 + .005), y, z0 + T * .5))
            for a, b in zip(pts, pts[1:]):
                parts.append(line_box('rail', a, b, .022 if not wide else .035, .03, M['car_paint']))
        parts.append(boxo('nose', (W * .6, .015, .012), (0, -L / 2 + .06, z0 + T + .07 * (1.6 if not wide else 1.0) * .0 + .02), light, bevel=.004))
        parts.append(boxo('tail', (W * .6, .015, .012), (0, L / 2 - .06, z0 + T + .02), tail, bevel=.004))
        # footpads with bindings
        for sy in (-1, 1):
            y = sy * L * .2
            parts.append(boxo('pad', (W * .82, .26, .012), (0, y, z0 + T + .004), M['rubber'], bevel=.004, uvs=.2))
            parts.append(boxo('strap', (W * .9, .06, .03), (0, y + sy * .02, z0 + T + .03), carbon, bevel=.012, segs=3))
        # emitters underneath: housings + glowing discs + rings
        em = [(0, -L * .3), (0, L * .3)] if not wide else [(.11, -L * .3), (-.11, -L * .3), (.11, L * .3), (-.11, L * .3)]
        for x, y in em:
            r = .09 if not wide else .075
            parts.append(cylo('emh', r + .02, .05, (x, y, z0 - .02), M['trim_black'], 24))
            parts.append(cylo('emg', r, .012, (x, y, z0 - .048), glow, 24))
            parts.append(bl.torus('emr', r + .015, .008, (x, y, z0 - .045), M['chrome'], maj=24, mn=6))
        # centre spine / battery pack
        parts.append(boxo('spine', (W * .4, L * .38, .03), (0, 0, z0 - .015), M['trim_black'], bevel=.01, uvs=.3))
        parts.append(boxo('spineglow', (.012, L * .3, .006), (0, 0, z0 - .033), glow))
        if wide:
            for sy in (-1, 1):
                parts.append(boxo('bumper', (W * .9, .05, .05), (0, sy * (L / 2 - .06), z0 + .04), M['trim_black'], bevel=.02, segs=3))
        for o in parts:
            bl.apply_all(o)
        g = bl.join(parts, name)
        bl.empty('stand', (0, 0, z0 + T + .01), g)
        g['worldex'] = json.dumps({'len': L, 'wid': W, 'deck': z0 + T})
        bl.export(name + '.glb')


if __name__ == '__main__':
    build_cars()
