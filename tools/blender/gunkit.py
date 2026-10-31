"""Modelling kit for the weapons (used by weapons.py).

Hard-surface parts: side-profile extrusions with boolean cuts, bevels and weighted normals (crisp flats, rounded
edges), high-segment barrels, screws, pins, rails, muzzle devices. Organic parts: signed-distance fields meshed with
Surface Nets (sdf.py). Materials are textured PBR sets baked by weapon_textures.py.

Frame (same as the old guns): origin = top of the pistol grip (right hand), barrel along Blender -Y, Z up, the gun's
right side is -X. Every exported gun gets:
  * a per-vertex attribute `_wear` (0..1): convex edges for hard-surface parts (the game's shader rubs paint and
    bluing off there), crevices for organic parts (wet darkening);
  * UVs projected so texture U runs along the gun (wood grain and machining marks follow the barrel).
"""
import bpy, bmesh, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
import sdf

R90 = math.pi / 2
F32 = np.float32


# ------------------------------------------------------------------ materials
def tmat(name, tex=None, color='#ffffff', metal=0.0, rough=.5, coat=0.0, emit=None, strength=1.0, emit_tex=False,
         nstr=1.0, uv=1.0):
    """Principled material wired the way the glTF exporter understands: <tex>_c base colour, <tex>_n normal,
    <tex>_m metallic-roughness (G rough, B metal); emit_tex reuses the colour map as emission."""
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*bl.hexrgb(color), 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if coat:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = .08
    if emit:
        b.inputs['Emission Color'].default_value = (*bl.hexrgb(emit), 1)
        b.inputs['Emission Strength'].default_value = strength
    if tex:
        T = bl.TEXTURES
        vec = None
        if uv != 1.0:
            tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
            mp.inputs['Scale'].default_value = (uv, uv, 1)
            nt.links.new(tc.outputs['UV'], mp.inputs['Vector']); vec = mp.outputs['Vector']

        def img(f, data):
            n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(os.path.join(T, f), check_existing=True)
            if data:
                n.image.colorspace_settings.name = 'Non-Color'
            if vec is not None:
                nt.links.new(vec, n.inputs['Vector'])
            return n
        c = img(tex + '_c.jpg', False)
        nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
        if emit_tex:
            nt.links.new(c.outputs['Color'], b.inputs['Emission Color'])
        if os.path.exists(os.path.join(T, tex + '_n.jpg')):
            n = img(tex + '_n.jpg', True); nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
            nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
        if os.path.exists(os.path.join(T, tex + '_m.jpg')):
            r = img(tex + '_m.jpg', True); sp = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(r.outputs['Color'], sp.inputs['Color'])
            nt.links.new(sp.outputs['Green'], b.inputs['Roughness']); nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    m.use_backface_culling = True
    bl._MATS[name] = m
    return m


def energy_mats():
    """The glowing sci-fi line. gun_body is white-textured so the shader colour multiplies it; gun_glow takes rarity."""
    return dict(body=tmat('gun_body', 'wpn_paint'),
                metal=tmat('gun_metal', 'wpn_metal'),
                dark=tmat('gun_dark', 'wpn_park'),
                trim=bl.mat('gun_trim', '#c79a45', 1.0, .25),
                glow=bl.mat('gun_glow', '#1ad8ff', 0, .4, emit='#1ad8ff', strength=7),
                grip=tmat('gun_grip', 'wpn_knurl', metal=0, rough=.7),
                lens=bl.mat('gun_lens', '#1a3a48', .6, .04, emit='#06141c', strength=1.0),
                dot=bl.mat('gun_dot', '#ff2a2a', 0, .3, emit='#ff2a2a', strength=10),
                green=bl.mat('gun_tritium', '#46ff7a', 0, .3, emit='#46ff7a', strength=8))


def kinetic_mats():
    """Real-material line: never tinted by rarity or shader."""
    return dict(steel=tmat('gun_steel', 'wpn_steel'),
                park=tmat('gun_parkerized', 'wpn_park'),
                poly=tmat('gun_polymer', 'wpn_poly'),
                odg=tmat('gun_polymer_od', 'wpn_odg'),
                wood=tmat('gun_wood', 'wpn_wood'),
                rubber=tmat('gun_rubber', 'wpn_knurl', metal=0, rough=.8),
                brass=bl.mat('gun_brass', '#b8893a', 1.0, .3),
                paint=bl.mat('gun_sightpaint', '#f2efe6', 0, .45),
                orange=bl.mat('gun_sightorange', '#ff7a1a', 0, .45),
                lens=bl.mat('gun_lens', '#1a3a48', .6, .04, emit='#06141c', strength=1.0),
                dot=bl.mat('gun_dot', '#ff2a2a', 0, .3, emit='#ff2a2a', strength=10))


def bio_mats():
    return dict(flesh=tmat('bio_flesh', 'bio_flesh', coat=1.0),
                bone=tmat('bio_bone', 'bio_bone'),
                glow=tmat('bio_glow', 'bio_sac', coat=1.0, rough=.2, emit='#ffffff', strength=2.2, emit_tex=True),
                maw=bl.mat('bio_maw', '#3a0610', 0, .18, coat=1.0))


# ------------------------------------------------------------------ hard-surface parts
def _obj(name, me, m):
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if m is not None:
        me.materials.append(m)
    return o


def _cut(o, cutters):
    cutters = [c for c in cutters if c]
    if not cutters:
        return o
    cj = cutters[0] if len(cutters) == 1 else bl.join(cutters, 'cutter')
    bpy.context.view_layer.objects.active = o
    md = o.modifiers.new('cut', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.object = cj
    md.solver = 'EXACT'
    try:
        md.use_self = True
    except Exception:
        pass
    o.select_set(True)
    bpy.ops.object.modifier_apply(modifier=md.name)
    o.select_set(False)
    bpy.data.objects.remove(cj, do_unlink=True)
    return o


def _bevel(o, w, segs=3, ang=30):
    if w <= 0:
        return o
    bpy.context.view_layer.objects.active = o
    md = o.modifiers.new('bv', 'BEVEL'); md.width = w; md.segments = segs; md.limit_method = 'ANGLE'
    md.angle_limit = math.radians(ang); md.harden_normals = False
    try:
        md.miter_outer = 'MITER_ARC'
    except Exception:
        pass
    o.select_set(True)
    bpy.ops.object.modifier_apply(modifier=md.name)
    o.select_set(False)
    return o


def harden(o, smooth_ang=32):
    """Apply every modifier, smooth by angle, then weighted normals: big flats shade flat, bevels shade round."""
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    for md in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=md.name)
    bpy.ops.object.shade_smooth()
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_ang))
    except Exception:
        pass
    md = o.modifiers.new('wn', 'WEIGHTED_NORMAL'); md.keep_sharp = True; md.weight = 50; md.mode = 'FACE_AREA'
    bpy.ops.object.modifier_apply(modifier=md.name)
    o.select_set(False)
    return o


def cbox(size, loc, rot=(0, 0, 0)):
    """Cutter box (no material)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return o


def ccyl(r, h, loc, rot=(0, 0, 0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc, rotation=rot)
    return bpy.context.object


def ext(name, pts, w, m, bevel=.0025, segs=3, cuts=(), ang=30, x=0.0):
    """Side profile pts [(y, z), ...] extruded across X (width w, centred on x). Boolean cuts, bevel, hardened."""
    bm = bmesh.new()
    vs = [bm.verts.new((x - w / 2, y, z)) for y, z in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(w, 0, 0), verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = _obj(name, me, m)
    _cut(o, list(cuts))
    _bevel(o, bevel, segs, ang)
    return harden(o)


def ext_top(name, pts, h, m, z=0.0, bevel=.0025, segs=3, cuts=()):
    """Top profile pts [(x, y), ...] extruded up along Z from z (height h)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for x, y in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, h), verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = _obj(name, me, m)
    _cut(o, list(cuts))
    _bevel(o, bevel, segs)
    return harden(o)


def B(name, size, loc, m, bevel=.003, rot=(0, 0, 0), segs=3, cuts=()):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(m)
    _cut(o, list(cuts))
    if bevel > 0:
        _bevel(o, min(bevel, min(size) * .45), segs)
    return harden(o)


def tube(name, r, length, y0, z, m, verts=32, r2=None, bevel=.0012, cuts=(), hollow=0.0, x=0.0):
    """Cylinder along -Y starting at y0 (optionally tapered to r2, optionally bored out to radius `hollow`)."""
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=length, location=(x, y0 - length / 2, z), rotation=(R90, 0, 0))
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=length, location=(x, y0 - length / 2, z), rotation=(R90, 0, 0))
    o = bpy.context.object; o.name = name
    o.data.materials.append(m)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    cl = list(cuts)
    if hollow:
        cl.append(ccyl(hollow, length + .01, (x, y0 - length / 2, z), (R90, 0, 0), max(12, verts // 2)))
    _cut(o, cl)
    _bevel(o, min(bevel, r * .3), 2, 40)
    return harden(o, 40)


def cylx(name, r, length, loc, m, verts=24, bevel=.0008):
    """Cylinder across X (pins, knobs, screws)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=length, location=loc, rotation=(0, R90, 0))
    o = bpy.context.object; o.name = name; o.data.materials.append(m)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    _bevel(o, min(bevel, r * .3), 2, 40)
    return harden(o, 40)


def cylz(name, r, length, loc, m, verts=24, bevel=.0008, r2=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=length, location=loc)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=length, location=loc)
    o = bpy.context.object; o.name = name; o.data.materials.append(m)
    _bevel(o, min(bevel, r * .3), 2, 40)
    return harden(o, 40)


def rod(name, a, b, r, m, verts=16, r2=None):
    """Cylinder (or cone to r2) between two points."""
    from mathutils import Vector
    a, b = Vector(a), Vector(b); d = b - a
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=(a + b) / 2)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object; o.name = name; o.data.materials.append(m)
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return harden(o, 40)


def ball(name, r, loc, m, scale=(1, 1, 1), seg=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r, location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale; o.data.materials.append(m)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return harden(o, 60)


def ring(name, R, r, loc, m, axis='y', maj=40, mn=10):
    rot = {'y': (R90, 0, 0), 'x': (0, R90, 0), 'z': (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, rotation=rot, major_segments=maj, minor_segments=mn)
    o = bpy.context.object; o.name = name; o.data.materials.append(m)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return harden(o, 60)


def screw(x, y, z, m, r=.0032, side=1, slot_m=None):
    """Slotted screw head on a side face (side=+1 left/+X, -1 right/-X)."""
    h = cylx('screw', r, .0018, (x + side * .0009, y, z), m, 16, .0005)
    s = B('screwslot', (.0012, r * 1.7, .0007), (x + side * .0019, y, z), slot_m or m, 0, rot=(.6, 0, 0))
    return [h, s]


def pins(xw, pts, m, r=.0022):
    """Cross pins through a receiver of width xw: one cylinder per (y, z), slightly proud on both sides."""
    return [cylx('pin', r, xw + .002, (0, y, z), m, 16, .0005) for y, z in pts]


def rivet(x, y, z, m, r=.0028, side=1):
    return ball('rivet', r, (x + side * .0004, y, z), m, scale=(.45, 1, 1), seg=14, rings=8)


def rail(M, y0, y1, z, w=.022, m=None, slot_cut=True):
    """Picatinny-style rail: bevelled base and recoil-groove teeth. z = base bottom; top is z + .0095."""
    m = m or M.get('dark') or M.get('park')
    L = y0 - y1
    base = B('railbase', (w * .8, L, .005), (0, (y0 + y1) / 2, z + .0025), m, .001)
    n = int(L / .01)
    top = B('railtop', (w, L, .0045), (0, (y0 + y1) / 2, z + .0072), m, .0012,
            cuts=[cbox((w + .01, .0052, .006), (0, y0 - .005 - i * .01, z + .0085)) for i in range(n)] if slot_cut else ())
    return [base, top]


def sling_loop(y, z, m, x=0.0, r=.009):
    return [ring('slingloop', r, .0018, (x, y, z), m, axis='x', maj=24, mn=8)]


def birdcage(y, z, r, L, m, slots=6):
    """Flash hider: tube with long slots; returns parts. y = rear end."""
    cuts = [cbox((.004, L * .62, r * 3), (0, y - L * .55, z), rot=(0, i * math.pi / slots, 0)) for i in range(slots // 2)]
    t = tube('flashhider', r, L, y, z, m, 32, hollow=r * .62, cuts=cuts)
    return [t, tube('fh_ring', r * 1.12, .006, y, z, m, 32)]


def brake(y, z, r, L, m, ports=3):
    """Muzzle brake with side ports and a top slot."""
    cuts = [cbox((r * 3, .007, r * 1.1), (0, y - L * (.25 + i * .22), z)) for i in range(ports)]
    cuts.append(cbox((r * .7, L * .5, r * 2), (0, y - L * .5, z + r)))
    return [tube('brake', r, L, y, z, m, 32, hollow=r * .5, cuts=cuts, bevel=.0015)]


def iron_rear(M, y, z, m=None):
    """Aperture rear sight (ring with ears); centre at (0, y, z)."""
    m = m or M.get('dark') or M.get('park')
    return [ring('rear_ring', .0085, .0026, (0, y, z), m, maj=28, mn=8),
            B('rear_base', (.03, .016, .016), (0, y, z - .016), m, .003),
            B('rear_earL', (.006, .014, .03), (.016, y, z - .004), m, .002),
            B('rear_earR', (.006, .014, .03), (-.016, y, z - .004), m, .002)]


def iron_front(M, y, z, ears=True, dot=None, m=None):
    """Front post with its tip at (0, y, z)."""
    m = m or M.get('dark') or M.get('park')
    P = [B('post', (.004, .004, .02), (0, y, z - .01), m, .0008),
         B('front_base', (.024, .014, .012), (0, y, z - .026), m, .003)]
    if dot is not None:
        P.append(ball('postdot', .0022, (0, y + .0022, z - .002), dot, seg=10, rings=6))
    if ears:
        for s in (1, -1):
            P.append(B('front_ear', (.004, .01, .028), (s * .013, y, z - .012), m, .0015, rot=(0, s * .15, 0)))
    return P


def grip_profile(name, m, ang=.3, h=.115, w=.032, y=0.0, z=0.0, swell=.006):
    """Ergonomic pistol grip as a raked side profile (finger swell at the front, beavertail at the back)."""
    ca, sa = math.cos(ang), math.sin(ang)

    def P(a, b):            # a along the grip's front-back, b down the grip
        return (y + a * ca + b * sa, z - b * ca + a * sa)
    pts = [P(-.024, -.004), P(.03, -.004), P(.032, .02), P(.026, h * .5), P(.028, h), P(-.02, h + .004),
           P(-.026, h * .7), P(-.022 - swell, h * .55), P(-.027, h * .4), P(-.022 - swell, h * .25), P(-.026, .03)]
    return ext(name, pts, w, m, bevel=w * .32, segs=4, ang=25)


def trigger_group(M, m_guard, m_trig, y=-.03, z=0.0, w=.012, L=.075, drop=.05):
    """Trigger guard band (U profile) and curved trigger blade."""
    o, i = .005, 0.0
    outer = [(y + .028, z), (y + .028, z - drop), (y - L + .03, z - drop), (y - L + .015, z - drop + .015), (y - L + .012, z)]
    inner = [(y - L + .018, z), (y - L + .02, z - drop + o + .012), (y - L + .032, z - drop + o), (y + .022, z - drop + o), (y + .022, z)]
    guard = ext('trigguard', outer + inner, w, m_guard, bevel=.0015, segs=2)
    blade = ext('trigger', [(y - .006, z + .002), (y - .016, z - .012), (y - .015, z - .026), (y - .008, z - .034),
                            (y - .004, z - .033), (y - .01, z - .024), (y - .01, z - .012), (y - .0, z + .002)], .006, m_trig, bevel=.001, segs=2)
    return [guard, blade]


# ------------------------------------------------------------------ organic parts (SDF)
def lumps(P, seed, freq, amp):
    """Cheap smooth 3D noise: a sum of random plane waves."""
    rng = np.random.default_rng(seed)
    out = np.zeros(len(P), F32)
    for k in range(7):
        d = rng.normal(size=3); d /= np.linalg.norm(d)
        f = freq * (.7 + rng.random() * .9)
        out += np.sin(P @ (d * f).astype(F32) + rng.random() * 6.28).astype(F32) / 7
    return out * amp


def sdf_part(name, fn, lo, hi, h, m, target=None):
    V, Q = sdf.mesh(fn, lo, hi, h)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V)); me.vertices.foreach_set('co', np.asarray(V, F32).ravel())
    me.loops.add(len(Q) * 4); me.loops.foreach_set('vertex_index', np.asarray(Q, np.int32).ravel())
    me.polygons.add(len(Q))
    me.polygons.foreach_set('loop_start', np.arange(0, len(Q) * 4, 4, dtype=np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(Q), 4, np.int32))
    me.update(calc_edges=True); me.validate(clean_customdata=False)
    o = _obj(name, me, m)
    if target and len(V) > target:
        bpy.context.view_layer.objects.active = o
        md = o.modifiers.new('dec', 'DECIMATE'); md.ratio = target / len(V)
        o.select_set(True); bpy.ops.object.modifier_apply(modifier=md.name); o.select_set(False)
        a = np.empty(len(o.data.vertices) * 3, F32); o.data.vertices.foreach_get('co', a)
        a = sdf.project(fn, a.reshape(-1, 3), 2, max_step=h * .5)
        o.data.vertices.foreach_set('co', a.ravel()); o.data.update()
    me = o.data
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    a = np.empty(len(me.vertices) * 3, F32); me.vertices.foreach_get('co', a)
    N = sdf.normals(fn, a.reshape(-1, 3))
    me.normals_split_custom_set_from_vertices([tuple(v) for v in N])
    print('  sdf %s: %d verts' % (name, len(me.vertices)))
    return o


# ------------------------------------------------------------------ finishing
def uv_project(o, S=.22, cyl_axis=None):
    """Box UVs with U along the gun (Blender -Y). cyl_axis=(x, z) wraps V around the barrel axis instead (organic)."""
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name='UVMap')
    uvl = me.uv_layers[0]
    nl = len(me.loops)
    vi = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', vi)
    co = np.empty(len(me.vertices) * 3, F32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    P = co[vi]
    npoly = len(me.polygons)
    ls = np.empty(npoly, np.int32); lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get('loop_start', ls); me.polygons.foreach_get('loop_total', lt)
    pn = np.empty(npoly * 3, F32); me.polygons.foreach_get('normal', pn); pn = pn.reshape(-1, 3)
    pid = np.repeat(np.arange(npoly), lt)
    if cyl_axis is None:
        n = np.abs(pn[pid]); ax = n.argmax(1)
        u = np.where(ax == 1, P[:, 0], -P[:, 1])
        v = np.where(ax == 2, P[:, 0], P[:, 2])
        uv = np.stack([u, v], 1) / S
    else:
        k = 2.0
        ang = np.arctan2(P[:, 2] - cyl_axis[1], P[:, 0] - cyl_axis[0])
        v = (ang / (2 * math.pi) + .5) * k
        # faces straddling the wrap: lift the low side by one period
        vmax = np.zeros(npoly); np.maximum.at(vmax, pid, v)
        v = np.where((vmax[pid] - v) > k / 2, v + k, v)
        uv = np.stack([-P[:, 1] / S, v], 1)
    uvl.data.foreach_set('uv', uv.astype(F32).ravel())


def wear_attr(o, organic_mats=()):
    """Per-vertex `_wear`: convexity for hard parts (edge wear), concavity for organic ones (wet crevices)."""
    me = o.data
    n = len(me.vertices)
    co = np.empty(n * 3, F32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    no = np.empty(n * 3, F32); me.vertices.foreach_get('normal', no); no = no.reshape(-1, 3)
    ed = np.empty(len(me.edges) * 2, np.int32); me.edges.foreach_get('vertices', ed); ed = ed.reshape(-1, 2)
    d = co[ed[:, 1]] - co[ed[:, 0]]; L = np.linalg.norm(d, axis=1) + 1e-9; d /= L[:, None]
    conv = np.zeros(n); cnt = np.zeros(n)
    np.add.at(conv, ed[:, 0], -(no[ed[:, 0]] * d).sum(1)); np.add.at(conv, ed[:, 1], (no[ed[:, 1]] * d).sum(1))
    np.add.at(cnt, ed[:, 0], 1); np.add.at(cnt, ed[:, 1], 1)
    c = conv / np.maximum(cnt, 1)
    w = sdf.smoothstep(.09, .32, c)
    if organic_mats:
        # vertex -> material via its faces
        npoly = len(me.polygons)
        mi = np.empty(npoly, np.int32); me.polygons.foreach_get('material_index', mi)
        lt = np.empty(npoly, np.int32); me.polygons.foreach_get('loop_total', lt)
        vi = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', vi)
        vm = np.zeros(n, np.int32); vm[vi] = np.repeat(mi, lt)
        names = [s.material.name if s.material else '' for s in o.material_slots]
        org = np.isin(vm, [i for i, nm in enumerate(names) if nm in organic_mats])
        w = np.where(org, sdf.smoothstep(.02, .14, -c), w)
    a = me.attributes.get('_wear') or me.attributes.new('_wear', 'FLOAT', 'POINT')
    a.data.foreach_set('value', w.astype(F32))
    return w


def vert_mats(o):
    me = o.data
    npoly = len(me.polygons)
    mi = np.empty(npoly, np.int32); me.polygons.foreach_get('material_index', mi)
    lt = np.empty(npoly, np.int32); me.polygons.foreach_get('loop_total', lt)
    vi = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', vi)
    vm = np.zeros(len(me.vertices), np.int32); vm[vi] = np.repeat(mi, lt)
    names = [s.material.name if s.material else '' for s in o.material_slots]
    return np.array([names[i] for i in vm])


def shape_key(o, name, fn):
    """fn(co, normal, matnames) -> offsets (N,3). Adds the Basis key first if needed."""
    if not o.data.shape_keys:
        o.shape_key_add(name='Basis', from_mix=False)
    me = o.data; n = len(me.vertices)
    co = np.empty(n * 3, F32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    no = np.empty(n * 3, F32); me.vertices.foreach_get('normal', no); no = no.reshape(-1, 3)
    k = o.shape_key_add(name=name, from_mix=False)
    k.data.foreach_set('co', (co + fn(co, no, vert_mats(o))).astype(F32).ravel())
    return k


def assemble(name, parts, organic=(), S=.22, cyl_axis=None):
    """Join parts into one object, project UVs and write the wear attribute."""
    parts = [p for p in parts if p is not None]
    for o in parts:
        bl.apply_all(o)
    g = bl.join(parts, name)
    uv_project(g, S, cyl_axis)
    wear_attr(g, organic)
    return g


def export(fname, **kw):
    return bl.export(fname, export_attributes=True, **kw)
