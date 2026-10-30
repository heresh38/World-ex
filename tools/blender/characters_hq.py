"""High-detail player characters built from the owner's reference art (art/reference).

player_female.glb / player_male.glb each contain:
  B_<region>  body regions (skin)       -> hidden per outfit where clothing covers them
  head        sculpted head with the face plate projected from the reference photo
  H_<style>   hair styles               -> one visible at a time
  O_<outfit>  complete outfits          -> one visible at a time
Smoothly skinned (distance-blended weights) to the shared 20-bone rig with the 9 standard clips.
Tintable materials start with armor_primary / armor_secondary / glow (wardrobe colours multiply the textures).
"""
import bpy, bmesh, math, os, sys, json
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(__file__))
import bl, human, characters

R90 = math.pi / 2
TONES = json.load(open(os.path.join(bl.TEXTURES, 'char_skin_tones.json')))
# face-plate landmarks measured on the reference crops: (u of face centre, u half eye spacing, v of eye line, v of chin)
CALIB = {'female': (.504, .156, .52, .08), 'male': (.5, .165, .5, .055)}


def calibrate_face_uv(o, hr, cz, sex):
    """Re-map the head's planar UVs so the photo's eyes and chin land on the sculpted eyes and chin."""
    uc, ue, ve, vc = CALIB[sex]
    x_eye = .3 * .82 * hr
    z_eye = cz + .157 * hr; z_chin = cz - .98 * hr
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
    def coat(self, mat, trim, hem_z):
        """Sleeveless long coat, open at the front, high collar."""
        z, k, sh = self.z, self.k, self.P.shoulder
        body = self.body
        verts = [body.matrix_world @ v.co for v in body.data.vertices]
        def extent(zz, band=.025, xlim=None):
            xs = [abs(v.x) for v in verts if abs(v.z - zz) < band and abs(v.x) < (xlim or sh * .82)]
            ys = [v.y for v in verts if abs(v.z - zz) < band and abs(v.x) < (xlim or sh * .82)]
            if not xs:
                return .12, .09, 0
            return max(xs), (max(ys) - min(ys)) / 2, (max(ys) + min(ys)) / 2
        levels = [z['chin'] - .012, z['neck'] + .01, z['shoulder'] - .005, z['armpit'], z['chest'], z['waist'], z['navel'], z['hip'],
                  z['crotch'], (z['crotch'] + z['knee']) / 2, z['knee'], hem_z]
        N = 26
        secs = []; opens = []
        for i, zz in enumerate(levels):
            if zz > z['shoulder'] - .01:
                rx, ry, cy = (.052 * k + .012, .052 * k + .012, .012) if zz > z['neck'] else (sh * .55, .085 * k, 0)
            else:
                rx, ry, cy = extent(zz, xlim=sh * .78 if zz > z['waist'] else .2)
                rx += .018; ry += .022
            fl = max(0, (z['hip'] - zz)) / max(z['hip'] - hem_z, .01)
            rx += .035 * fl ** 1.2; ry += .04 * fl ** 1.2
            if secs and zz < z['waist']:
                # below the waist the coat only ever widens: no pinches or wings
                prx = max(abs(p.x) for p in secs[-1]); pry = (max(p.y for p in secs[-1]) - min(p.y for p in secs[-1])) / 2
                rx = max(rx, prx); ry = max(ry, pry * .98); cy = 0
            op = math.radians(14 if zz > z['neck'] else 22 + 40 * fl)
            ring = []
            for j in range(N):
                th = op + (2 * math.pi - 2 * op) * j / (N - 1)
                ring.append(Vector((rx * math.sin(th), cy - ry * math.cos(th), zz)))
            secs.append(ring); opens.append(op)
        verts2 = [p for s in secs for p in s]
        faces = []
        for i in range(len(secs) - 1):
            for j in range(N - 1):
                a = i * N + j
                faces.append((a, a + 1, a + 1 + N, a + N))
        o = bl.mesh_from('coat', verts2, faces, mat)
        bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(o.data); bm.free()
        # outward normals: flip if pointing in
        if o.data.polygons[N * 3].normal.dot(Vector((o.data.polygons[N * 3].center.x, o.data.polygons[N * 3].center.y, 0))) < 0:
            for p in o.data.polygons:
                p.flip()
        uvl = o.data.uv_layers.new(name='UVMap')
        for p in o.data.polygons:
            for li in p.loop_indices:
                vi = o.data.loops[li].vertex_index; i, j = divmod(vi, N)
                uvl.data[li].uv = (j / (N - 1) * 6, (levels[0] - levels[i]) * 2.6)
        md = o.modifiers.new('s', 'SOLIDIFY'); md.thickness = .006
        sub = o.modifiers.new('sub', 'SUBSURF'); sub.levels = 1
        bpy.context.view_layer.objects.active = o; o.select_set(True)
        for m in list(o.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
        o.select_set(False)
        bl.autosmooth(o, 60)
        # gold trims: front edges + hem
        parts = [o]
        for col in (0, N - 1):
            pts = [secs[i][col] for i in range(len(secs))]
            nrm = [Vector((p.x, p.y, 0)).normalized() for p in pts]
            parts.append(ribbon('trim', bezier(pts, 40), [Vector((p.x, p.y, 0)).normalized() for p in bezier(pts, 40)], .016, trim, lift=.006))
        hem = secs[-1]
        parts.append(ribbon('hemtrim', hem, [Vector((p.x, p.y - 0, 0)).normalized() for p in hem], .02, trim, lift=.006))
        return parts

    def harness(self, mat, metal):
        z, k = self.z, self.k
        S = self.surf
        parts = []
        for sx in (1, -1):
            pts = [(sx * .07 * k, zz) for zz in [z['shoulder'] - .005 + i * (z['waist'] - z['shoulder']) / 12 for i in range(13)]]
            P, N = S.line(pts, -1)
            if len(P) > 2:
                parts.append(ribbon('strap', P, N, .045 * k, mat, lift=.014))
            P, N = S.line(pts, 1)
            if len(P) > 2:
                parts.append(ribbon('strapb', P, N, .045 * k, mat, lift=.014))
        pts = [(x * .01, z['chest'] - .03) for x in range(-13, 14)]
        P, N = S.line(pts, -1)
        parts.append(ribbon('chestband', P, N, .035 * k, mat, lift=.018))
        c, n = S.hit(0, z['chest'] - .03, -1)
        if c is not None:
            parts.append(bl.box('buckle', (.05 * k, .02, .036 * k), c + n * .025, metal, bevel=.006))
        return parts

    def belt(self, mat, metal, zc, pouch=None):
        z, k = self.z, self.k
        parts = [shell(self.body, 'belt', mat, self.P_(zmin=zc - .022, zmax=zc + .022, bones=('hips', 'spine')), .014, uv=.12)]
        c, n = self.surf.hit(0, zc, -1)
        if c is not None:
            parts.append(bl.box('beltbuckle', (.045 * k, .015, .03 * k), c + n * .02, metal, bevel=.005))
        if pouch:
            p = bl.box('pouch', (.06 * k, .05 * k, .08 * k), (-.15 * k, -.02, zc - .05), pouch, bevel=.012)
            parts.append(p)
        return parts

    def female_outfits(self):
        z, k, sh = self.z, self.k, self.P.shoulder
        coat = tex('armor_primary__coat', 'coat_circuit', color='#8ea2dc', rough=.55, uv=1.0, double=True)
        gold = flat('trim_gold', '#a8935a', .9, .35)
        olive = flat('armor_secondary__harness', '#5d5a3c', 0, .8)
        steel = flat('buckle_steel', '#c9cdd2', 1, .25)
        ribbed = tex('ribbed_white', 'ribbed_white', rough=.85, uv=3.0)
        cyan = flat('glow__f', '#1ad8ff', 0, .4, emit='#1ad8ff', strength=5)
        gaunt = tex('gauntlet', 'gauntlet_dark', metal=.4, rough=.4)
        glove = flat('glove_dark', '#2a2c31', 0, .7)
        knee = tex('kneepad', 'kneepad', metal=.5, rough=.35)
        greave = tex('greave', 'greave_dark', metal=.4, rough=.45)
        boot = tex('boot_tech', 'boot_tech', metal=.2, rough=.5)
        spark = tex('chest_sparkle', 'chest_sparkle', rough=.3, emit=None)
        sparkle_emit = bl.mat('chest_sparkle_glow', '#ffffff', 0, .3, image='char_chest_sparkle.jpg')
        nt = sparkle_emit.node_tree; b = nt.nodes.get('Principled BSDF')
        for nd in nt.nodes:
            if nd.type == 'TEX_IMAGE':
                nt.links.new(nd.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = .8
        outfits = {}

        def armour_common(prefix):
            parts = []
            parts += self.coat(coat, gold, z['knee'] - .17 * k)
            parts += self.harness(olive, steel)
            parts += self.belt(olive, steel, z['navel'] - .02, pouch=olive)
            # sparkle chest panel under the collar
            parts.append(shell(self.body, 'sparkle', sparkle_emit, self.P_(zmin=z['chest'] + .02, zmax=z['armpit'] + .035, xmax=.06 * k, front=True), .011, uv=.12))
            # gauntlets + fingerless gloves
            parts.append(shell(self.body, 'gauntlet', gaunt, self.P_(bones=('forearm',), zmin=0), .013, uv=.14))
            for sx, s in ((1, 'L'), (-1, 'R')):
                el, wr = self.J['forearm.' + s]
                mid = el + (wr - el) * .55
                strip = bl.box('gglow', (.006, .05 * k, .01), mid + Vector((sx * .05 * k, -.02, 0)), cyan)
                parts.append(self.rigid(strip, 'forearm.' + s))
                plate = bl.box('gplate', (.03 * k, .05 * k, .09 * k), mid + Vector((sx * .046 * k, -.005, 0)), gaunt, bevel=.008)
                parts.append(self.rigid(plate, 'forearm.' + s))
            hand_f = lambda c, n: True
            parts.append(shell(self.body, 'glove', glove, self.P_(bones=('hand',)), .003, uv=.1))
            # knee pads + greaves + boots
            for sx, s in ((1, 'L'), (-1, 'R')):
                kn, an = self.J['shin.' + s]
                pad = bl.box('kneepad', (.085 * k, .05 * k, .1 * k), kn + Vector((0, -.06 * k, -.01)), knee, bevel=.02, segs=3)
                parts.append(self.rigid(pad, 'shin.' + s))
                tr = bl.box('kneetrim', (.088 * k, .004, .012), kn + Vector((0, -.088 * k, .035)), gold)
                parts.append(self.rigid(tr, 'shin.' + s))
                tp = bl.box('thighplate', (.07 * k, .04 * k, .1 * k), kn + Vector((sx * .045 * k, -.02, .12 * k)), knee, bevel=.012)
                parts.append(self.rigid(tp, 'thigh.' + s))
            parts.append(shell(self.body, 'greave', greave, self.P_(bones=('shin',), zmin=z['ankle'] + .04, zmax=z['knee'] - .06), .014, uv=.2))
            parts += self.boots('tech', boot, z['ankle'] + .1 * k, glow=cyan, strap=olive)
            return parts

        # 1) circuit coat over the ribbed bodysuit
        p = armour_common('coat')
        p.append(shell(self.body, 'bodysuit', ribbed, self.P_(bones=('hips', 'spine', 'chest', 'thigh', 'shin')), .004, uv=.25))
        outfits['circuit_coat'] = (self.finish_outfit('circuit_coat', p), ['chest', 'midriff', 'pelvis', 'thigh', 'shin', 'foot', 'forearm'])
        # 2) same armour, crop top + trousers (midriff bare)
        p = armour_common('crop')
        p.append(shell(self.body, 'croptop', ribbed, self.P_(bones=('spine', 'chest'), zmin=z['waist'] + .045), .005, uv=.25))
        p.append(shell(self.body, 'trousers', ribbed, self.P_(bones=('hips', 'thigh', 'shin')), .006, uv=.25))
        outfits['circuit_crop'] = (self.finish_outfit('circuit_crop', p), ['pelvis', 'thigh', 'shin', 'foot', 'forearm'])
        # 3) knit crop top, ribbed leggings, white lace boots
        knit = tex('armor_primary__knit', 'knit_white', rough=.9, uv=2.0)
        bootw = tex('boot_white', 'boot_white', rough=.5)
        def top_pred(c, n):
            if not self.P_(bones=('spine', 'chest'), zmin=z['waist'] + .04)(c, n):
                return False
            # sweetheart neckline + bare shoulders (thin straps kept)
            if c.y < 0 and c.z > z['chest'] + .045 and abs(c.x) < .085 * k:
                return False
            if c.z > z['armpit'] + .01 and not (.05 * k < abs(c.x) < .075 * k):
                return False
            return True
        p = [shell(self.body, 'knittop', knit, top_pred, .007, uv=.2)]
        # ruffle hem
        hz = z['waist'] + .045
        ring = []
        verts = [self.body.matrix_world @ v.co for v in self.body.data.vertices if abs(v.co.z - hz) < .02 and abs(v.co.x) < sh * .8]
        rx = max(abs(v.x) for v in verts) + .01; ry = (max(v.y for v in verts) - min(v.y for v in verts)) / 2 + .012
        secs = []
        for zz, g in ((hz + .004, 0), (hz - .022, .008)):
            secs.append([Vector((math.sin(t) * (rx + g + .004 * math.sin(t * 14)), -math.cos(t) * (ry + g + .004 * math.cos(t * 14)), zz))
                         for t in [i * 2 * math.pi / 48 for i in range(48)]])
        ruf = bl.loft('ruffle', secs, knit, cap=False); ruf.data.materials[0].use_backface_culling = False
        bl.uv_box(ruf, .15)
        p.append(ruf)
        p.append(bl.sphere('brooch', .014 * k, (.06 * k, -.1 * k, z['chest'] + .04), flat('brooch', '#efe6c8', .2, .4), 10, 8, scale=(1, .5, 1)))
        p.append(shell(self.body, 'leggings', ribbed, self.P_(bones=('hips', 'thigh', 'shin')), .004, uv=.25))
        p += self.boots('white', bootw, z['ankle'] + .2 * k, sole_col='#e8e4dc')
        outfits['knit'] = (self.finish_outfit('knit', p), ['pelvis', 'thigh', 'shin', 'foot'])
        # 4) off-duty: black ribbed crop tank, olive trousers, belt, brown boots
        tank = tex('armor_primary__tank', 'tank_black', rough=.85, uv=2.0)
        pants = tex('armor_secondary__pants', 'pants_olive', rough=.9, uv=2.0)
        bootb = tex('boot_brown', 'boot_brown', rough=.6)
        def tank_pred(c, n):
            if not self.P_(bones=('spine', 'chest', 'neck'), zmin=z['waist'] + .07, zmax=z['neck'] + .01)(c, n):
                return False
            if c.z > z['armpit'] - .01 and abs(c.x) > .1 * k:
                return False
            return True
        p = [shell(self.body, 'tank', tank, tank_pred, .005, uv=.2),
             shell(self.body, 'pants', pants, self.P_(bones=('hips', 'thigh', 'shin'), zmin=z['ankle'] + .06), .009, uv=.25)]
        p += self.belt(flat('belt_black', '#151515', 0, .5), steel, z['navel'] - .045)
        p += self.boots('brown', bootb, z['ankle'] + .12 * k, sole_col='#2a1d14')
        outfits['offduty'] = (self.finish_outfit('offduty', p), ['pelvis', 'thigh', 'foot'])
        return outfits

    # --------------------------------------------------------- male outfits
    def plate(self, name, mat, pred, off, solid=.008, uv=.18):
        return shell(self.body, name, mat, pred, off, uv=uv, solid=solid)

    def pauldron(self, side, mat, trim, size=1.0):
        s = 'L' if side > 0 else 'R'
        sp, el = self.J['upperarm.' + s]
        parts = []
        for i, sc in enumerate((1.0, .82, .66)):
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=.1 * self.k * size * sc)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -.01], context='VERTS')
            o = mesh_obj('pauldron', bm); o.data.materials.append(mat)
            o.scale = (1.0, 1.15, .6); o.location = sp + Vector((side * (.02 + i * .012), 0, .04 - i * .045 * size))
            o.rotation_euler = (0, -side * (.25 + .15 * i), 0)
            bl.apply_all(o)
            md = o.modifiers.new('s', 'SOLIDIFY'); md.thickness = .008
            bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.object.modifier_apply(modifier=md.name); o.select_set(False)
            bl.uv_box(o, .2); bl.autosmooth(o, 40)
            parts.append(self.rigid(o, 'upperarm.' + s))
        return parts

    def male_outfits(self):
        z, k, sh = self.z, self.k, self.P.shoulder
        outfits = {}
        steel = bl.mat('armor_primary__vanguard', '#3b4a60', .65, .34, normal='panel_n.jpg', image='panel_c.jpg', uv_scale=3.0)
        bronze = flat('armor_secondary__bronze', '#9c6a45', 1, .3)
        under = tex('undersuit_black', 'undersuit_black', color='#2a2c30', rough=.8, uv=3.0)
        glove = tex('glove_black', 'glove_black', metal=.1, rough=.5)
        abd = tex('abdomen', 'abdomen_plates', metal=.6, rough=.4)
        pauld = steel
        light = flat('glow__m', '#e8f4ff', 0, .3, emit='#e8f4ff', strength=6)
        bootd = tex('boot_dark', 'boot_dark', metal=.3, rough=.5)
        allb = ('hips', 'spine', 'chest', 'neck', 'upperarm', 'forearm', 'thigh', 'shin')

        def suit(mat):
            return shell(self.body, 'undersuit', mat, self.P_(bones=allb, zmax=z['chin'] - .01), .004, uv=.2)

        def collar(mat, h=.07, r=None):
            r = r or .062 * k
            return self.rigid(bl.cyl('collar', r + .016, h, (0, .01, z['neck'] + h / 2 - .01), mat, 20, r2=r + .006), 'neck')

        # 1) Vanguard plate armour
        p = [suit(under), collar(steel)]
        p.append(self.plate('chestplate', steel, self.P_(bones=('chest', 'spine'), zmin=z['chest'] - .06, zmax=z['armpit'] + .05, xmax=sh * .8), .026))
        p.append(self.plate('abdomen', abd, self.P_(bones=('spine', 'hips'), zmin=z['navel'] - .05, zmax=z['chest'] - .065, xmax=sh * .7, front=True), .02, uv=.3))
        # bronze edge along the chest plate's lower rim
        P_, N_ = self.surf.line([(x * .012, z['chest'] - .06) for x in range(-14, 15)], -1)
        p.append(ribbon('rim', P_, N_, .014, bronze, lift=.03))
        c, n = self.surf.hit(0, z['chest'] + .02, -1)
        p.append(bl.box('chestlight', (.03 * k, .012, .09 * k), c + n * .036, light, bevel=.006))
        p += self.pauldron(1, pauld, bronze); p += self.pauldron(-1, pauld, bronze)
        p.append(self.plate('bracer', steel, self.P_(bones=('forearm',)), .016))
        p.append(shell(self.body, 'glove', glove, self.P_(bones=('hand',)), .005, uv=.12))
        p.append(self.plate('thighplate', steel, self.P_(bones=('thigh',), front=True, zmin=z['knee'] + .05), .02))
        p.append(self.plate('greave', steel, self.P_(bones=('shin',), zmin=z['ankle'] + .06), .018))
        for s in 'LR':
            kn, _ = self.J['shin.' + s]
            p.append(self.rigid(bl.box('kneecap', (.09 * k, .06 * k, .1 * k), kn + Vector((0, -.06 * k, 0)), steel, bevel=.02), 'shin.' + s))
        p.append(self.plate('cod', abd, self.P_(bones=('hips',), front=True, xmax=.1 * k), .018))
        p += self.belt(bronze, bronze, z['navel'] - .06)
        p += self.boots('vanguard', bootd, z['ankle'] + .1 * k)
        hide = ['chest', 'midriff', 'pelvis', 'upperarm', 'forearm', 'hand', 'thigh', 'shin', 'foot']
        outfits['vanguard'] = (self.finish_outfit('vanguard', p), hide)
        # 2) Ranger armour (rust / green / tan with the blue emblem shoulder)
        rust = bl.mat('armor_primary__ranger', '#8e4430', .35, .55, normal='panel_n.jpg', image='rock_c.jpg', uv_scale=2.0)
        tan = bl.mat('plate_tan', '#8b7150', .3, .6, normal='panel_n.jpg', image='rock_c.jpg', uv_scale=2.0)
        green = bl.mat('plate_green', '#4f6a3c', .3, .6, normal='panel_n.jpg', image='rock_c.jpg', uv_scale=2.0)
        rustleg = rust
        emblem = tex('shoulder_emblem', 'shoulder_emblem', metal=.3, rough=.5)
        olive = tex('armor_secondary__ranger', 'under_olive', rough=.85, uv=3.0)
        pouch = tex('pouch_olive', 'pouch_olive', rough=.8)
        screen = tex('wrist_screen', 'wrist_screen', rough=.3)
        p = [suit(olive), collar(olive, .06)]
        p.append(self.plate('chestplate', rust, self.P_(bones=('chest',), zmin=z['chest'] - .04, zmax=z['armpit'] + .05, xmax=sh * .75, front=True), .026))
        p.append(self.plate('backplate', tan, self.P_(bones=('chest', 'spine'), zmin=z['waist'], zmax=z['armpit'] + .05, xmax=sh * .75, front=False), .024))
        p += self.pauldron(-1, emblem, emblem, 1.1)
        p += self.pauldron(1, tan, tan, .95)
        for i, x in enumerate((-.09, -.045, 0, .045, .09)):
            c, n = self.surf.hit(x * k, z['navel'] + .03, -1)
            if c is not None:
                p.append(self.rigid(bl.box('pouch', (.04 * k, .035 * k, .07 * k), c + n * .03, pouch, bevel=.006), 'spine'))
        p += self.belt(flat('belt_olive', '#4c4a35', 0, .7), flat('buckle_grey', '#888c90', .9, .3), z['navel'] - .05)
        p.append(self.plate('thighR', rustleg, (lambda c, n: c.x < 0 and self.P_(bones=('thigh',), front=True, zmin=z['knee'] + .05)(c, n)), .022))
        p.append(self.plate('thighL', green, (lambda c, n: c.x > 0 and self.P_(bones=('thigh',), front=True, zmin=z['knee'] + .05)(c, n)), .022))
        p.append(self.plate('shinR', tan, (lambda c, n: c.x < 0 and self.P_(bones=('shin',), zmin=z['ankle'] + .06)(c, n)), .02))
        p.append(self.plate('shinL', green, (lambda c, n: c.x > 0 and self.P_(bones=('shin',), zmin=z['ankle'] + .06)(c, n)), .02))
        for s in 'LR':
            kn, _ = self.J['shin.' + s]
            p.append(self.rigid(bl.box('kneecap', (.09 * k, .06 * k, .1 * k), kn + Vector((0, -.06 * k, 0)), tan, bevel=.02), 'shin.' + s))
        p.append(self.plate('bracer', tan, self.P_(bones=('forearm',)), .015))
        p.append(shell(self.body, 'glove', glove, self.P_(bones=('hand',)), .005, uv=.12))
        el, wr = self.J['forearm.R']
        p.append(self.rigid(bl.box('wristscreen', (.03 * k, .06 * k, .08 * k), el + (wr - el) * .6 + Vector((-.05 * k, -.01, 0)), screen, bevel=.006), 'forearm.R'))
        p += self.boots('ranger', bootd, z['ankle'] + .1 * k)
        outfits['ranger'] = (self.finish_outfit('ranger', p), hide)
        # 3) Field jacket: camo vest, two-tone sleeves, cargo trousers, boots, watch
        vest = tex('armor_primary__field', 'vest_camo', color='#9aa070', rough=.85, uv=1.0)
        sleeve_r = bl.mat('sleeve_blue_red', '#ffffff', 0, .85)
        sleeve_l = tex('sleeve_tan', 'sleeve_tan', rough=.85, uv=2.0)
        cargo = tex('armor_secondary__cargo', 'cargo_pants', rough=.9, uv=1.5)
        bootk = tex('boot_black', 'boot_black', rough=.6)
        p = [shell(self.body, 'vest', vest, self.P_(bones=('chest', 'spine', 'hips'), zmin=z['navel'] - .08, zmax=z['neck'] + .02), .02, uv=.3),
             collar(vest, .05, .066 * k)]
        sr = shell(self.body, 'sleeveR', sleeve_r, lambda c, n: c.x < 0 and self.P_(bones=('upperarm', 'forearm'))(c, n), .012, uv=None)
        # weathered blue at the shoulder fading to brick red down the arm (vertex colours)
        bl.uv_box(sr, .15)
        top = self.J['upperarm.R'][0].z; bot = self.J['forearm.R'][1].z
        ca = sr.data.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        blue, red = bl.hexrgb('#6f9ac4'), bl.hexrgb('#8e3b2c')
        for poly in sr.data.polygons:
            for li in poly.loop_indices:
                co = sr.data.vertices[sr.data.loops[li].vertex_index].co
                t = max(0, min(1, (top - co.z) / (top - bot) * 1.6 - .25))
                ca.data[li].color = (*[blue[i] * (1 - t) + red[i] * t for i in range(3)], 1)
        nt = sleeve_r.node_tree
        vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'
        nt.links.new(vc.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
        p.append(sr)
        p.append(shell(self.body, 'sleeveL', sleeve_l, lambda c, n: c.x > 0 and self.P_(bones=('upperarm', 'forearm'))(c, n), .012, uv=.15))
        for sx in (1, -1):
            c, n = self.surf.hit(sx * .07 * k, z['chest'] + .01, -1)
            if c is not None:
                p.append(self.rigid(bl.box('pocket', (.07 * k, .02, .08 * k), c + n * .03, vest, bevel=.006), 'chest'))
            c, n = self.surf.hit(sx * .06 * k, z['navel'] - .02, -1)
            if c is not None:
                p.append(self.rigid(bl.box('pocket2', (.06 * k, .02, .06 * k), c + n * .028, vest, bevel=.006), 'spine'))
        p.append(shell(self.body, 'cargo', cargo, self.P_(bones=('hips', 'thigh', 'shin'), zmin=z['ankle'] + .06), .02, uv=.3))
        for s, sx in (('L', 1), ('R', -1)):
            hj, kn = self.J['thigh.' + s]
            p.append(self.rigid(bl.box('cargopocket', (.03 * k, .1 * k, .12 * k), hj + (kn - hj) * .55 + Vector((sx * .085 * k, 0, 0)), cargo, bevel=.01), 'thigh.' + s))
        p.append(shell(self.body, 'shirt', under, self.P_(bones=('neck',)), .004, uv=.2))
        p += self.boots('field', bootk, z['ankle'] + .12 * k, sole_col='#1a1a1a')
        el, wr = self.J['forearm.L']
        p.append(self.rigid(bl.cyl('watch', .03 * k, .02 * k, wr + (el - wr) * .1, flat('watch', '#1c1d20', .6, .3), 16, rot=(0, R90, 0)), 'forearm.L'))
        outfits['field'] = (self.finish_outfit('field', p), ['pelvis', 'thigh', 'foot'])
        return outfits

    # --------------------------------------------------------- hair
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
            pts = []
            for i in range(9):
                t = i / 8
                q = hl.lerp(end, t)
                d = (q - C)
                q = C + d.normalized() * hr * lift * (1 + .05 * math.sin(t * math.pi))
                pts.append(q)
            nrm = [(p - C).normalized() for p in pts]
            w = [hr * .5 * (1 - .55 * i / 8) for i in range(9)]
            parts.append(card('scalp', pts, w, mat, nrm))
        return parts

    def female_hair(self):
        k, hr, cz, z = self.k, self.hr, self.hcz, self.z
        tone = '#ffffff'
        cardm = card_mat('hair_card_f', 'hair_card_f.png')
        capm = flat('hair_scalp_f', '#2a1d17', 0, .7)
        core = flat('hair_core_f', '#241a15', 0, .65)
        braid = tex('braid', 'braid_lilac', rough=.6)
        brow_z = cz + hr * .32
        def cap_keep(c, n):
            if c.y < 0 and c.z < brow_z and abs(c.x) < hr * .72:
                return False
            if c.z < z['chin'] + .03 and c.y < .02:
                return False
            return True
        def hair_w(co):
            if co.z > z['neck']:
                return {'head': 1.0}
            if co.z > z['waist']:
                t = (co.z - z['waist']) / (z['neck'] - z['waist'])
                return {'head': t * .5, 'chest': 1 - t * .5}
            return {'chest': .5, 'spine': .3, 'hips': .2}
        styles = {}
        # high ponytail reaching the knees, falling to the character's right
        cap = self.hair_cap('cap', capm, .004, cap_keep)
        tie = Vector((-.005, .045, self.P.z['top'] - .005))
        path = bezier([tie, tie + Vector((-.01, .07, .045)), Vector((-.04, .15, z['neck'] + .02)), Vector((-.07, .17, z['chest'] - .05)),
                       Vector((-.1, .19, z['crotch'])), Vector((-.12, .15, z['knee'] + .03))], 40)
        n = len(path)
        radii = [(.02 + .03 * math.sin(min(1, i / (n * .22)) * math.pi / 2)) * (1 - .8 * max(0, (i / n - .3) / .7)) * k / .93 for i in range(n)]
        tail = card_bundle('pony', path, radii, cardm, 14, twist=.18, core=core, seed=3)
        tiering = bl.torus('tie', .024 * k, .008, tie + Vector((0, .006, .006)), flat('tie_pink', '#d9a3c8', 0, .5), rot=(.8, 0, 0), maj=14, mn=5)
        scalp = self.scalp_cards(cardm, tie, 30, seed=2)
        bangs = []
        for sx in (1, -1):
            for j in range(3):
                top = Vector((sx * hr * (.45 + .1 * j), -hr * (.62 - .05 * j), cz + hr * .62))
                pts = bezier([top, Vector((sx * hr * (.78 + .03 * j), -hr * (.55 - .05 * j), cz + hr * .05)),
                              Vector((sx * hr * (.86 + .04 * j), -hr * (.42 - .06 * j), z['chin'] + .01 - .015 * j))], 12)
                nrm = [Vector((sx * .6, -1, 0)).normalized()] * len(pts)
                bangs.append(card('bang', pts, [.03 * k * (1 - .5 * i / len(pts)) for i in range(len(pts))], cardm, nrm))
        br = []
        for i, dx in enumerate((0, .012)):
            pts = [Vector((-hr * .7 - dx, -hr * .2, cz + hr * .5)), Vector((-hr * .95 - dx, -.0, cz - hr * .3)), Vector((-hr * 1.15 - dx, .02, z['chest'] + .02))]
            br.append(tube('braid', bezier(pts, 14), [.0055 * k] * 20, braid, 6, twist=.6))
        moon = bl.torus('moon', .018 * k, .005, Vector((-hr * 1.2, .0, z['chest'] - .005)), flat('moon_gold', '#e2c46a', 1, .25), rot=(R90, 0, 0), maj=14, mn=4)
        stars = [star('star', .014 * k, flat('star_c', '#7fe0ff', .3, .3, emit='#3ab8e0', strength=.6), Vector((-hr * .55, -hr * .5, cz + hr * .9)), (0, 0, .3)),
                 star('star', .012 * k, flat('star_p', '#f2a6cf', .3, .3), Vector((-hr * .2, -hr * .6, cz + hr * 1.02)), (0, 0, -.2)),
                 star('star', .01 * k, flat('star_w', '#f4f4f4', .3, .3), Vector((hr * .55, -hr * .35, cz + hr * .98)), (0, 0, .5))]
        objs = [cap, tiering, moon] + tail + scalp + bangs + br + stars
        for o in objs:
            bl.apply_all(o); self.rig.skin(o, fn=hair_w)
        styles['ponytail'] = bl.join(objs, 'H_ponytail')
        # long straight hair: scalp cards falling straight down the back and over the shoulders
        cap2 = self.hair_cap('cap2', capm, .004, cap_keep)
        C = Vector((0, .008 * k, cz))
        sheets = []
        import random
        rnd = random.Random(9)
        for j in range(34):
            a = -2.5 + 5.0 * j / 33
            if abs(a) < .75:
                a = math.copysign(.75 + abs(a) * .3, a if a != 0 else 1)   # part the hair around the face
            front = abs(a) < 1.25
            top = C + Vector((math.sin(a) * hr * .55, -math.cos(a) * hr * .6, hr * 1.0))
            mid = C + Vector((math.sin(a) * hr * 1.08, -math.cos(a) * hr * 1.0 + (0 if front else .02), -hr * .1))
            sh_ = C + Vector((math.sin(a) * hr * (1.5 if front else 1.25), -math.cos(a) * hr * .8 + (-.02 if front else .07), z['neck'] - cz - .03))
            end = Vector((sh_.x * (1.05 if front else .9), sh_.y + (-.05 if front else .1), (z['chest'] - .06) if front else z['waist'] + rnd.uniform(-.03, .03)))
            pts = bezier([top, mid, sh_, end], 18)
            nrm = [Vector((p.x, p.y - .01, 0)).normalized() for p in pts]
            sheets.append(card('sheet', pts, [.07 * k] * 4 + [.085 * k] * 10 + [.06 * k] * 10, cardm, nrm))
        objs = [cap2] + sheets
        for o in objs:
            bl.apply_all(o); self.rig.skin(o, fn=hair_w)
        styles['long'] = bl.join(objs, 'H_long')
        return styles

    def male_hair(self):
        k, hr, cz, z = self.k, self.hr, self.hcz, self.z
        cardm = card_mat('hair_card_m', 'hair_card_m.png')
        capm = flat('hair_scalp_m', '#1e1915', 0, .7)
        brow_z = cz + hr * .42
        def keep(c, n):
            if c.y < 0 and c.z < brow_z and abs(c.x) < hr * .7:
                return False
            if c.z < cz + hr * .1 and c.y < hr * .1:
                return False
            if c.z < cz - hr * .15 and c.y < hr * .5:
                return False
            if c.z < cz - hr * .55:
                return False
            return True
        cap = self.hair_cap('cap', capm, .004, keep)
        cards = self.scalp_cards(cardm, None, 44, lift=1.045, seed=5)
        # the quiff: front cards lifted
        for o in cards:
            for v in o.data.vertices:
                if v.co.y < -hr * .3 and v.co.z > cz + hr * .4:
                    v.co.z += .01 * k
        objs = [cap] + cards
        for o in objs:
            bl.apply_all(o); self.rig.skin(o, 'rigid', 'head')
        return {'short': bl.join(objs, 'H_short')}

    # --------------------------------------------------------- assemble + export
    def run(self, fname):
        bl.reset()
        self.build_body()
        outfits = self.female_outfits() if self.sex == 'female' else self.male_outfits()
        hair = self.female_hair() if self.sex == 'female' else self.male_hair()
        regions = self.split_regions()
        bpy.data.objects.remove(self.body)
        b = type('B', (), {})(); b.J = self.J; b.s = self.H / 1.82
        arm = characters.make_armature(b)
        for bn in arm.data.bones:
            bn.use_deform = not bn.name.startswith(('ik_', 'pole', 'root'))
        for o in list(bpy.context.scene.objects):
            if o.type == 'MESH':
                o.parent = arm
                md = o.modifiers.new('Armature', 'ARMATURE'); md.object = arm
        characters.animate(arm, b.s)
        meta = {'outfits': {k: v[1] for k, v in outfits.items()}, 'hair': list(hair.keys())}
        arm['worldex'] = json.dumps(meta)
        print('  meta', meta)
        tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.context.scene.objects if o.type == 'MESH')
        print('  total tris (all outfits)', tris)
        bl.export(fname, animations=True)


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for sex, f in (('female', 'player_female.glb'), ('male', 'player_male.glb')):
        if not only or sex in only:
            Builder(sex).run(f)
