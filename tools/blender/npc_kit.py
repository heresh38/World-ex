"""Shared kit for the civilian pedestrians (civilians.py): skinned human body, rig weights, cloth shells, ribbons,
tubes, hair cards and the painted-face UV calibration. (The old armoured player builder that lived here was scrapped;
players are now built by players.py.)
"""
import bpy, bmesh, math, os, sys, json
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(__file__))
import bl, human, characters

R90 = math.pi / 2
_tp = os.path.join(bl.TEXTURES, 'char_skin_tones.json')
TONES = json.load(open(_tp)) if os.path.exists(_tp) else {'face_female': [.8, .6, .5], 'face_male': [.7, .5, .4]}
# face-plate landmarks measured on the reference crops: (u of face centre, u half eye spacing, v of eye line, v of chin)
CALIB = {'female': (.504, .156, .52, .08), 'male': (.5, .165, .5, .055)}


def calibrate_face_uv(o, hr, cz, sex):
    """Re-map the head's planar UVs so the photo's eyes and chin land on the sculpted eyes and chin."""
    uc, ue, ve, vc = CALIB[sex]
    x_eye = .3 * .82 * hr
    z_eye = cz + .157 * hr; z_chin = cz - 1.05 * hr
    me = o.data; uv = me.uv_layers.active
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (uc + co.x * ue / x_eye, vc + (co.z - z_chin) * (ve - vc) / (z_eye - z_chin))


def tone_hex(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(1, c)) * 255) for c in rgb)


def tex(name, file, color='#ffffff', metal=0.0, rough=.6, emit=None, strength=1.0, uv=1.0, double=False):
    m = bl.mat(name, color, metal, rough, emit=emit, strength=strength, image='char_%s.jpg' % file, uv_scale=uv)
    if double:
        m.use_backface_culling = False
    return m


def flat(name, color, metal=0.0, rough=.6, emit=None, strength=1.0):
    return bl.mat(name, color, metal, rough, emit=emit, strength=strength)


def card_mat(name, file, tint='#ffffff'):
    """Alpha-tested, double-sided hair card material (glTF alphaMode MASK via the Round node)."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(os.path.join(bl.TEXTURES, file))
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1
    mix.inputs[7].default_value = (*bl.hexrgb(tint), 1)
    nt.links.new(t.outputs['Color'], mix.inputs[6]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    rnd = nt.nodes.new('ShaderNodeMath'); rnd.operation = 'ROUND'
    nt.links.new(t.outputs['Alpha'], rnd.inputs[0]); nt.links.new(rnd.outputs[0], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = .55; b.inputs['Specular IOR Level'].default_value = .6
    m.use_backface_culling = False
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    return m


def frame_along(path, i):
    t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
    a = Vector((1, 0, 0)) if abs(t.x) < .9 else Vector((0, 1, 0))
    u = t.cross(a).normalized(); w = t.cross(u).normalized()
    return t, u, w


def card(name, path, widths, mat, normals=None, offsets=None):
    """A hair card: a strip following path, facing normals (default: away from the path's own frame)."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    rows = []
    n = len(path)
    for i, p in enumerate(path):
        t, u, w = frame_along(path, i)
        nn = normals[i] if normals else u
        side = t.cross(nn).normalized() * widths[min(i, len(widths) - 1)] / 2
        q = p + (offsets[i] if offsets else Vector())
        rows.append((bm.verts.new(q - side), bm.verts.new(q + side)))
    for i in range(n - 1):
        f = bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
        for l, (a, b) in zip(f.loops, ((0, i), (1, i), (1, i + 1), (0, i + 1))):
            l[uvl].uv = (a, 1 - b / (n - 1))
    o = mesh_obj(name, bm); o.data.materials.append(mat)
    return o


def card_bundle(name, path, radii, mat, count=12, twist=.25, core=None, seed=0):
    """Ponytail-style bundle: a dark core tube wrapped by twisting strand cards."""
    import random
    rnd = random.Random(seed)
    path = path[:len(radii)]
    parts = []
    if core:
        parts.append(tube(name + '_core', path, [r * .62 for r in radii], core, 10, squash=1.3))
    for j in range(count):
        a0 = 2 * math.pi * j / count + rnd.uniform(-.2, .2)
        rr = rnd.uniform(.75, 1.0)
        nrm, offs, wid = [], [], []
        for i, p in enumerate(path):
            t, u, w = frame_along(path, i)
            a = a0 + twist * i / len(path) * 6.28
            d = (u * math.cos(a) * 1.3 + w * math.sin(a)).normalized()
            nrm.append(d); offs.append(d * radii[i] * rr)
            wid.append(radii[i] * 1.5)
        parts.append(card(name + '_c', path, wid, mat, nrm, offs))
    return parts


# ------------------------------------------------------------------ rig helpers
PARENT = {'hips': None, 'spine': 'hips', 'chest': 'spine', 'neck': 'chest', 'head': 'neck'}
for _s in 'LR':
    PARENT.update({'upperarm.' + _s: 'chest', 'forearm.' + _s: 'upperarm.' + _s, 'hand.' + _s: 'forearm.' + _s,
                   'thigh.' + _s: 'hips', 'shin.' + _s: 'thigh.' + _s, 'foot.' + _s: 'shin.' + _s})


def seg_dist(p, a, b):
    ab = b - a; t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (a + ab * t - p).length


class Rig:
    def __init__(self, J):
        self.J = J
        self.adj = {b: set() for b in J}
        for b, p in PARENT.items():
            if p:
                self.adj[b].add(p); self.adj[p].add(b)

    def weights(self, co, allow=None):
        ds = {b: seg_dist(co, a, t) for b, (a, t) in self.J.items() if allow is None or b in allow}
        b1 = min(ds, key=ds.get)
        cand = [b for b in self.adj[b1] if b in ds]
        out = {b1: 1 / max(ds[b1], .004) ** 4}
        if cand:
            b2 = min(cand, key=ds.get)
            out[b2] = 1 / max(ds[b2], .004) ** 4
        s = sum(out.values())
        out = {b: w / s for b, w in out.items() if w / s > .04}
        s = sum(out.values())
        return {b: w / s for b, w in out.items()}

    def skin(self, o, mode='auto', bone=None, allow=None, fn=None):
        """mode auto: distance blend; rigid: one bone; fn: custom co -> {bone: w}."""
        for b in self.J:
            if b not in o.vertex_groups:
                o.vertex_groups.new(name=b)
        mw = o.matrix_world
        for v in o.data.vertices:
            co = mw @ v.co
            if mode == 'rigid':
                ws = {bone: 1.0}
            elif fn:
                ws = fn(co)
            else:
                ws = self.weights(co, allow)
            for b, w in ws.items():
                o.vertex_groups[b].add([v.index], w, 'REPLACE')
        return o


# ------------------------------------------------------------------ geometry helpers
def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    return o


def shell(src, name, mat, pred, offset, uv=.25, smooth=True, solid=0.0):
    """Copy the faces of src whose centre/normal satisfy pred(center, normal) and push them out along normals."""
    bm = bmesh.new(); bm.from_mesh(src.data)
    mw = src.matrix_world
    kill = [f for f in bm.faces if not pred(mw @ f.calc_center_median(), (mw.to_3x3() @ f.normal).normalized())]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    if bm.verts.layers.deform.active:
        bm.verts.layers.deform.remove(bm.verts.layers.deform.active)   # weights are recomputed per piece
    bm.normal_update()
    for v in bm.verts:
        v.co = v.co + v.normal * offset
    o = mesh_obj(name, bm)
    o.matrix_world = mw
    o.data.materials.append(mat)
    bl.apply_all(o)
    if solid > 0:
        md = o.modifiers.new('s', 'SOLIDIFY'); md.thickness = solid; md.offset = 1
        bpy.context.view_layer.objects.active = o; o.select_set(True)
        bpy.ops.object.modifier_apply(modifier=md.name); o.select_set(False)
    if uv:
        bl.uv_box(o, uv)
    if smooth:
        bl.autosmooth(o, 50)
    return o


def ribbon(name, pts, nrm, width, mat, lift=.004, uv_len=.2):
    """A strip following surface points pts (with normals nrm) - straps, trims, belts."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    rows = []
    for i, (p, n) in enumerate(zip(pts, nrm)):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = t.cross(n).normalized() * width / 2
        q = p + n * lift
        rows.append((bm.verts.new(q - side), bm.verts.new(q + side)))
    acc = 0
    for i in range(len(rows) - 1):
        f = bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
        d = (pts[i + 1] - pts[i]).length
        for l, uvv in zip(f.loops, ((0, acc), (1, acc), (1, acc + d), (0, acc + d))):
            l[uvl].uv = (uvv[0], uvv[1] / uv_len)
        acc += d
    o = mesh_obj(name, bm); o.data.materials.append(mat)
    return o


class Surface:
    def __init__(self, obj):
        dg = bpy.context.evaluated_depsgraph_get()
        self.bvh = BVHTree.FromObject(obj, dg)
        self.mw = obj.matrix_world.copy()

    def hit(self, x, z, side=-1, y0=None):
        """Ray toward the body centre from the front (side=-1) or back (+1) at (x, z)."""
        o = Vector((x, side * 1.0, z)); d = Vector((0, -side, 0))
        loc, n, i, dist = self.bvh.ray_cast(o, d, 3)
        if loc is None:
            return None, None
        return loc, n

    def line(self, pts2, side=-1, lift=.0):
        P, N = [], []
        for x, z in pts2:
            p, n = self.hit(x, z, side)
            if p is not None:
                P.append(p + n * lift); N.append(n)
        return P, N


def tube(name, path, radii, mat, segs=10, squash=1.0, uv_v=1.0, cap=True, twist=0.0):
    """Lofted tube along a polyline (hair, braids, ponytail)."""
    path = path[:len(radii)]
    secs = []
    for i, (p, r) in enumerate(zip(path, radii)):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        a = Vector((1, 0, 0)) if abs(t.x) < .9 else Vector((0, 1, 0))
        u = t.cross(a).normalized(); w = t.cross(u).normalized()
        ring = []
        for k in range(segs):
            th = 2 * math.pi * k / segs + twist * i
            ring.append(p + u * math.cos(th) * r * squash + w * math.sin(th) * r)
        secs.append(ring)
    o = bl.loft(name, secs, mat, cap=cap, smooth=True)
    # UVs: u around, v along
    uv = o.data.uv_layers.new(name='UVMap'); n = segs
    L = [0]
    for i in range(1, len(path)):
        L.append(L[-1] + (path[i] - path[i - 1]).length)
    tot = L[-1] or 1
    for poly in o.data.polygons:
        for li in poly.loop_indices:
            vi = o.data.loops[li].vertex_index
            if vi < len(path) * n:
                ri, k = divmod(vi, n)
                uv.data[li].uv = (k / n, (1 - L[ri] / tot) * uv_v)
    return o


def bezier(pts, n=24):
    """Catmull-Rom through pts."""
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        for k in range(n // (len(pts) - 1) + 1):
            t = k / (n // (len(pts) - 1) + 1)
            p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
            out.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


def star(name, r, mat, loc, rot=(0, 0, 0)):
    bm = bmesh.new()
    pts = []
    for i in range(10):
        a = i * math.pi / 5; rr = r if i % 2 == 0 else r * .45
        pts.append((math.sin(a) * rr, 0, math.cos(a) * rr))
    top = [bm.verts.new((x, -.003, z)) for x, _, z in pts]
    bot = [bm.verts.new((x, .003, z)) for x, _, z in pts]
    bm.faces.new(top); bm.faces.new(bot[::-1])
    for i in range(10):
        j = (i + 1) % 10; bm.faces.new((top[i], top[j], bot[j], bot[i]))
    o = mesh_obj(name, bm); o.data.materials.append(mat); o.location = loc; o.rotation_euler = rot
    bl.apply_all(o)
    return o


def join(objs, name):
    objs = [o for o in objs if o]
    for o in objs:
        bl.apply_all(o)
    return bl.join(objs, name)


# ------------------------------------------------------------------ build
class Builder:
    def __init__(self, sex):
        self.sex = sex
        self.P = human.Proportions(sex, 1.58 if sex == 'female' else 1.83, 1.0 if sex == 'female' else 1.1)
        self.J = self.P.joints()
        self.rig = Rig(self.J)
        self.z = self.P.z; self.H = self.P.H; self.k = self.H / 1.7

    def build_body(self):
        P, sex = self.P, self.sex
        tone = TONES['face_' + sex]
        self.skin = flat('skin_' + sex, tone_hex([c * .9 for c in tone]), 0, .55)
        body = human.skin_body(P, 'body_full')
        body.data.materials.append(self.skin)
        bl.uv_box(body, .3)
        self.rig.skin(body)
        self.body = body
        self.surf = Surface(body)
        # head with projected face plate (clamped texture, feathered edge = skin tone)
        hd = human.head(P, 'head')
        face = bl.mat('face_' + sex, '#ffffff', 0, .45, image='char_face_%s.jpg' % sex)
        for nd in face.node_tree.nodes:
            if nd.type == 'TEX_IMAGE':
                nd.extension = 'EXTEND'
        hd.data.materials.append(face)
        self.hr = hd['head_r']; self.hcz = hd['head_cz']
        calibrate_face_uv(hd, self.hr, self.hcz, sex)
        self.rig.skin(hd, 'rigid', 'head')
        self.head = hd
        self.headsurf = Surface(hd)
        # ears
        ears = []
        for sx in (1, -1):
            e = bl.sphere('ear', .028 * self.k, (sx * self.hr * .8, .012, self.hcz - .005), self.skin, 12, 8, scale=(.35, .6, 1))
            ears.append(e)
        self.ears = join(ears, 'ears'); self.rig.skin(self.ears, 'rigid', 'head')

    def split_regions(self):
        """Body -> B_<region> objects (weights kept) so outfits can hide what they cover."""
        z = self.z
        regions = {}
        bm0 = bmesh.new(); bm0.from_mesh(self.body.data)
        dl = bm0.verts.layers.deform.active
        names = [g.name for g in self.body.vertex_groups]
        def region(f):
            c = f.calc_center_median()
            acc = {}
            for v in f.verts:
                for gi, w in v[dl].items():
                    acc[names[gi]] = acc.get(names[gi], 0) + w
            b = max(acc, key=acc.get).split('.')[0]
            if b == 'hips':
                return 'pelvis'
            if b == 'spine':
                return 'midriff' if c.z < z['waist'] + .03 else 'chest'
            return {'chest': 'chest', 'neck': 'neck', 'head': 'neck', 'upperarm': 'upperarm', 'forearm': 'forearm',
                    'hand': 'hand', 'thigh': 'thigh', 'shin': 'shin', 'foot': 'foot'}[b]
        tags = {f.index: region(f) for f in bm0.faces}
        bm0.free()
        out = []
        for r in sorted(set(tags.values())):
            o = self.body.copy(); o.data = self.body.data.copy(); o.name = 'B_' + r
            bpy.context.scene.collection.objects.link(o)
            bm = bmesh.new(); bm.from_mesh(o.data)
            bm.faces.ensure_lookup_table()
            kill = [f for f in bm.faces if tags[f.index] != r]
            bmesh.ops.delete(bm, geom=kill, context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(o.data); bm.free()
            out.append(o)
        return out

    # predicates over body faces
    def P_(self, zmin=-9, zmax=9, xmax=9, front=None, bones=None, xmin=0):
        z = self.z
        def f(c, n):
            if not (zmin <= c.z <= zmax and abs(c.x) <= xmax and abs(c.x) >= xmin):
                return False
            if front is True and n.y > .1:
                return False
            if front is False and n.y < -.1:
                return False
            if bones is not None:
                ws = self.rig.weights(c)
                b = max(ws, key=ws.get).split('.')[0]
                if b not in bones:
                    return False
            return True
        return f

    def skin_all(self, objs, **kw):
        for o in objs:
            if o:
                self.rig.skin(o, **kw)

    # --------------------------------------------------------- shared pieces
    def boots(self, tag, mat, top_z, sole_col='#151515', glow=None, strap=None):
        z, k = self.z, self.k
        parts = [shell(self.body, 'boot', mat, self.P_(zmax=top_z, bones=('shin', 'foot')), .016, uv=.18)]
        for sx in (1, -1):
            _, an = self.J['shin.' + ('L' if sx > 0 else 'R')]
            _, toe = self.J['foot.' + ('L' if sx > 0 else 'R')]
            sole = bl.box('sole', (.1 * k, .27 * k, .03), (an.x, (an.y + toe.y) / 2 - .02, .015), flat('sole_' + tag, sole_col, 0, .8), bevel=.01)
            parts.append(sole)
            if glow:
                parts.append(bl.box('soleglow', (.102 * k, .27 * k, .004), (an.x, (an.y + toe.y) / 2 - .02, .028), glow))
            if strap:
                parts.append(bl.torus('strap', .055 * k, .008, (an.x, an.y, z['ankle'] + .04), strap, maj=16, mn=4))
        return parts

    def finish_outfit(self, name, parts, rigid=None):
        objs = [o for o in parts if o]
        for o in objs:
            bl.apply_all(o)
            bone = (rigid or {}).get(o.name.split('.')[0])
            if 'bone' in o.keys():
                self.rig.skin(o, 'rigid', o['bone'])
            elif bone:
                self.rig.skin(o, 'rigid', bone)
            else:
                self.rig.skin(o)
        return bl.join(objs, 'O_' + name)

    def rigid(self, o, bone):
        o['bone'] = bone
        return o

    # --------------------------------------------------------- female outfits
    def hair_cap(self, name, mat, off, keep):
        return shell(self.head, name, mat, keep, off, uv=.12)

    def scalp_cards(self, mat, tie, count=26, lift=1.07, front_only=False, length=None, seed=1):
        """Combed-back cards over the skull from the hairline toward the tie point (or straight back)."""
        import random
        rnd = random.Random(seed)
        k, hr, cz = self.k, self.hr, self.hcz
        C = Vector((0, .008 * k, cz))
        parts = []
        for j in range(count):
            a = -2.4 + 4.8 * j / (count - 1) + rnd.uniform(-.06, .06)     # around the hairline, front=0
            hl = C + Vector((math.sin(a) * hr * .8, -math.cos(a) * hr * .9, hr * (.55 if abs(a) < 1.2 else .1 + .3 * (1 - abs(a) / 2.4))))
            end = tie if tie is not None else C + Vector((math.sin(a) * hr * .55, hr * .9, -hr * .25))
            pts, nrm = [], []
            for i in range(9):
                t = i / 8
                q = hl.lerp(end, t)
                d = (q - C)
                # project onto the head's own ellipsoid (narrow sides, tall crown) so the hair hugs the skull
                e = Vector((d.x / (hr * .82), d.y / (hr * (1.0 if d.y > 0 else .92)), d.z / (hr * 1.12))).normalized()
                lift_t = lift * (1 + .03 * math.sin(t * math.pi)) if t < .9 or tie is None else 1.0
                p = C + Vector((e.x * hr * .82, e.y * hr * (1.0 if d.y > 0 else .92), e.z * hr * 1.12)) * lift_t
                if tie is not None and t >= .9:
                    p = q
                pts.append(p)
                nrm.append(Vector((e.x / .82, e.y, e.z / 1.12)).normalized())
            w = [hr * .42 * (1 - .75 * i / 8) for i in range(9)]
            parts.append(card('scalp', pts, w, mat, nrm))
        return parts
