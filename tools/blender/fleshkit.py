"""Organic creature kit: tagged signed-distance sculpting -> skinned, vertex-coloured, textured, animated GLB.

A creature is a list of tagged primitives (round cones, ellipsoids, chains, shells, cuts). Every primitive carries:
  bone  - the rig bone it follows (skin weights are a soft-min blend of the nearest primitives' bones, so joints bend
          smoothly while plates and spikes stay rigid),
  mat   - material slot (hx_flesh / hx_skin / hx_chitin / hx_bone / hx_sac / hx_rag / glow ...),
  col   - macro colour (blended softly between neighbours into the vertex colours, times cavity darkening + mottling),
  amp   - how strongly the creature's displacement (wrinkles, veins, lumps) acts on it,
  writhe- 0..1 exported as the `_writhe` vertex attribute; the game's vertex shader wriggles those parts (tentacles).
Primitives are combined in order with smooth union (op 'add') or smooth subtraction (op 'sub', e.g. a burst chest).
Fields are evaluated with bounding-box culling (a box distance is a lower bound outside each primitive's box), meshed
with Surface Nets (sdf.py), decimated, re-projected and shaded with field-gradient normals.

Animation: clips are pose functions baked to plain FK keys on a rig made from a joint table (`make_rig`).
"""
import bpy, math, os, sys, time, random
import numpy as np
from mathutils import Vector, Quaternion
sys.path.insert(0, os.path.dirname(__file__))
import bl, sdf
from characters import wq

F32 = np.float32
FPS = 30
T0 = time.time()
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def log(*a):
    print('[flesh %5.1fs]' % (time.time() - T0), *a, flush=True)


# ------------------------------------------------------------------ noise (numpy, deterministic)
def _hash(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761 + 1013904223)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xffff).astype(np.float64) / 65535.0


def vnoise(P, freq, seed=0):
    """Smooth value noise in [0, 1]."""
    Q = np.asarray(P, np.float64) * freq + seed * 3.17
    i = np.floor(Q).astype(np.int64); f = Q - i; u = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                out = out + wx * wy * wz * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm(P, freq, octaves=3, seed=0, gain=.5):
    s = 0.0; a = 1.0; norm = 0.0
    for o in range(octaves):
        s = s + a * vnoise(P, freq * 2 ** o, seed + o * 31); norm += a; a *= gain
    return s / norm


def ridge(P, freq, seed=0, sharp=6):
    """Rope-like ridges (1 on the ridge line): veins under the skin."""
    n = vnoise(P, freq, seed) * .6 + vnoise(P, freq * 2.1, seed + 7) * .4
    return (1 - np.abs(2 * n - 1)) ** sharp


# ------------------------------------------------------------------ primitives
class Prim:
    def __init__(self, fn, lo, hi, bone, mat, col, k=.02, op='add', amp=1.0, writhe=0.0):
        self.fn = fn; self.lo = np.asarray(lo, F32); self.hi = np.asarray(hi, F32)
        self.bone = bone; self.mat = mat; self.col = np.asarray(col, F32); self.k = k; self.op = op
        self.amp = amp; self.writhe = writhe

    def eval(self, P, margin):
        lo = self.lo - margin; hi = self.hi + margin
        q = np.maximum(np.maximum(self.lo - P, P - self.hi), 0)
        out = np.sqrt((q * q).sum(1)).astype(F32)
        m = np.all((P >= lo) & (P <= hi), 1)
        if m.any():
            out[m] = self.fn(P[m])
        return out


def hexc(h):
    return np.asarray(bl.hexrgb(h), F32) if isinstance(h, str) else np.asarray(h, F32)


def lerp3(a, b, t):
    a = np.asarray(a, float); b = np.asarray(b, float)
    return a + (b - a) * t


class Sculpt:
    TAU = .012

    def __init__(self, seed=1):
        self.prims = []
        self.rnd = random.Random(seed)
        self.disp = None          # P -> outward displacement (m)
        self.margin = .09

    # ---- generic
    def add(self, fn, lo, hi, bone, mat, col, k=.02, op='add', amp=1.0, writhe=0.0):
        r = max(k, 0) * 2 + self.margin * .3
        p = Prim(fn, np.asarray(lo) - r, np.asarray(hi) + r, bone, mat, hexc(col), k, op, amp, writhe)
        self.prims.append(p)
        return p

    def cone(self, a, b, r1, r2, bone, mat, col, k=.02, **kw):
        a = np.asarray(a, float); b = np.asarray(b, float); R = max(r1, r2)
        if np.linalg.norm(b - a) < 1e-4:
            b = a + np.array([0, 0, 1e-3])
        return self.add(lambda P, a=a, b=b: sdf.round_cone(P, a, b, r1, r2), np.minimum(a, b) - R, np.maximum(a, b) + R,
                        bone, mat, col, k, **kw)

    def ell(self, c, r, bone, mat, col, k=.02, R=None, **kw):
        c = np.asarray(c, float); r = np.asarray(r, float)
        e = r.max()
        return self.add(lambda P, c=c, r=r, R=R: sdf.ellipsoid(P, c, r, R), c - e, c + e, bone, mat, col, k, **kw)

    def sph(self, c, r, bone, mat, col, k=.02, **kw):
        c = np.asarray(c, float)
        return self.add(lambda P, c=c: sdf.sphere(P, c, r), c - r, c + r, bone, mat, col, k, **kw)

    def chain(self, pts, radii, bone, mat, col, k=.015, writhe=(0.0, 0.0), cols=None, **kw):
        """Tapered tube through points (Catmull-Rom smoothed). bone may be a list (one per input point)."""
        pts = [np.asarray(p, float) for p in pts]
        fine = []
        for i in range(len(pts) - 1):
            p0 = pts[max(0, i - 1)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(len(pts) - 1, i + 2)]
            for s in range(3):
                t = s / 3
                t2, t3 = t * t, t * t * t
                fine.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
        fine.append(pts[-1])
        n = len(fine) - 1
        out = []
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            r0 = np.interp(t0, np.linspace(0, 1, len(radii)), radii); r1 = np.interp(t1, np.linspace(0, 1, len(radii)), radii)
            b = bone[min(len(bone) - 1, int(t0 * (len(bone) - 1) + .5))] if isinstance(bone, (list, tuple)) else bone
            c = col if cols is None else lerp3(hexc(cols[0]), hexc(cols[1]), t0)
            out.append(self.cone(fine[i], fine[i + 1], r0, r1, b, mat, c, k, writhe=writhe[0] + (writhe[1] - writhe[0]) * (t0 + t1) / 2, **kw))
        return out

    def shell(self, base_fn, lo, hi, thick, bone, mat, col, keep=None, holes=None, k=.004, **kw):
        """Thin shell around a surface (torn clothing, armour fragments). keep(P)<=0 keeps; holes=(freq, thr, seed)."""
        def f(P):
            d = np.abs(base_fn(P)) - thick
            if keep is not None:
                d = np.maximum(d, keep(P))
            if holes is not None:
                fq, thr, sd = holes
                d = np.maximum(d, (fbm(P, fq, 2, sd) - thr) * .08)
            return d
        return self.add(f, lo, hi, bone, mat, col, k, **kw)

    def cut(self, fn_or_prim, lo=None, hi=None, k=.015, bone=None, mat=None, col=(.3, .05, .05)):
        return self.add(fn_or_prim, lo, hi, bone, mat, col, k, op='sub')

    def cut_ell(self, c, r, bone, mat, col, k=.015, R=None):
        c = np.asarray(c, float); r = np.asarray(r, float); e = r.max()
        return self.add(lambda P, c=c, r=r, R=R: sdf.ellipsoid(P, c, r, R), c - e, c + e, bone, mat, col, k, op='sub')

    # ---- evaluation
    def field(self, P, disp=True):
        P = np.asarray(P, F32)
        n = len(P)
        d = np.full(n, 1e3, F32)
        dm = np.full(n, 1e3, F32); S = np.zeros(n, F32); A = np.zeros(n, F32)
        for pr in self.prims:
            di = pr.eval(P, self.margin)
            if pr.op == 'add':
                d = sdf.smin(d, di, pr.k) if pr.k > 0 else np.minimum(d, di)
            else:
                d = sdf.smax(d, -di, pr.k) if pr.k > 0 else np.maximum(d, -di)
            if disp and self.disp is not None:
                a = np.abs(di); nm = np.minimum(dm, a)
                e0 = np.exp(-(dm - nm) / self.TAU); e1 = np.exp(-(a - nm) / self.TAU)
                S = S * e0 + e1; A = A * e0 + e1 * pr.amp; dm = nm
        if disp and self.disp is not None:
            d = d - (A / np.maximum(S, 1e-9)) * self.disp(P).astype(F32)
        return d

    def surface_point(self, origin, direction, dist=.5):
        """First surface hit marching from outside towards origin (for scattering pustules/spikes)."""
        o = np.asarray(origin, float); dv = np.asarray(direction, float); dv /= np.linalg.norm(dv)
        P = (o + dv * dist)[None, :].astype(F32)
        for _ in range(60):
            f = self.field(P, disp=False)[0]
            if f < 1e-3:
                break
            P = P - dv[None, :].astype(F32) * max(f * .9, 1e-3)
        return P[0].astype(float)

    def distances(self, V):
        return np.stack([pr.eval(V, self.margin) for pr in self.prims], 1)


# ------------------------------------------------------------------ mesh plumbing
def to_object(name, V, Q, mat=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V)); me.vertices.foreach_set('co', np.asarray(V, F32).ravel())
    nl = Q.shape[1]
    me.loops.add(len(Q) * nl); me.loops.foreach_set('vertex_index', np.asarray(Q, np.int32).ravel())
    me.polygons.add(len(Q))
    me.polygons.foreach_set('loop_start', np.arange(0, len(Q) * nl, nl, dtype=np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(Q), nl, np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if mat is not None:
        me.materials.append(mat)
    return o


def verts(o):
    a = np.empty(len(o.data.vertices) * 3, F32); o.data.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def set_verts(o, V):
    o.data.vertices.foreach_set('co', np.asarray(V, F32).ravel()); o.data.update()


def decimate_to(o, target_tris):
    lt = np.empty(len(o.data.polygons), np.int32); o.data.polygons.foreach_get('loop_total', lt)
    n = int((lt - 2).sum())
    if n <= target_tris:
        return
    bpy.context.view_layer.objects.active = o
    md = o.modifiers.new('dec', 'DECIMATE'); md.ratio = target_tris / n
    bpy.ops.object.modifier_apply(modifier=md.name)


def set_colors(o, C):
    me = o.data
    attr = me.color_attributes.new('Color', 'BYTE_COLOR', 'POINT')
    rgba = np.ones((len(C), 4), F32); rgba[:, :3] = np.clip(C, 0, 1)
    attr.data.foreach_set('color_srgb' if hasattr(attr.data[0], 'color_srgb') else 'color', rgba.ravel())
    me.color_attributes.active_color = attr


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= .0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - .055)


# ------------------------------------------------------------------ materials
def tmat(name, tex, rough=.4, emit=None, strength=1.0, nstr=1.0, metal=0.0):
    """Textured PBR material (hx_<tex>_c/_n/_m) wired the way the glTF exporter reads it; vertex colours multiply it
    in three (COLOR_0), and in Blender through a Color Attribute multiply for the previews."""
    if name in bl._MATS:
        return bl._MATS[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*bl.hexrgb(emit), 1)
        b.inputs['Emission Strength'].default_value = strength
    T = bl.TEXTURES

    def img(f, data):
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(os.path.join(T, f), check_existing=True)
        if data:
            n.image.colorspace_settings.name = 'Non-Color'
        return n
    if tex:
        c = img(tex + '_c.jpg', False)
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'
        nt.links.new(c.outputs['Color'], mix.inputs[6]); nt.links.new(vc.outputs['Color'], mix.inputs[7])
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
        n = img(tex + '_n.jpg', True); nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
        nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
        r = img(tex + '_m.jpg', True); sp = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(r.outputs['Color'], sp.inputs['Color'])
        nt.links.new(sp.outputs['Green'], b.inputs['Roughness']); nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    else:
        vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'
        nt.links.new(vc.outputs['Color'], b.inputs['Base Color'])
    m.use_backface_culling = True
    bl._MATS[name] = m
    return m


def glow_mat(name, color, strength=5):
    return bl.mat(name, color, 0, .3, emit=color, strength=strength)


# ------------------------------------------------------------------ build: sculpt -> skinned mesh
def build_mesh(sc, name, lo, hi, h, target, mats, uv_scale=.45, ao_dist=.06, ao_k=1.0, mottle=.4, seed=0,
               bruise=('#6a4a66', .55, 4.0), veins=('#5a2a44', .5, 5.0)):
    """mats: slot name -> bpy material. Returns the mesh object with vertex groups, colours, `_writhe`, UVs."""
    log(name, 'meshing h=%.1fmm, %d primitives' % (h * 1000, len(sc.prims)))
    V, Q = sdf.mesh(sc.field, lo, hi, h, log=log)
    o = to_object(name, V, Q)
    decimate_to(o, target)
    o.data.validate(clean_customdata=False)
    V = sdf.project(sc.field, verts(o), 2, max_step=h * .5)
    set_verts(o, V)
    N = sdf.normals(sc.field, V)
    o.data.normals_split_custom_set_from_vertices([tuple(v) for v in N])
    # ownership: soft-min of |distance| to each primitive
    D = np.abs(sc.distances(V))
    dmin = D.min(1, keepdims=True)
    W = np.exp(-(D - dmin) / .01)
    Wc = np.exp(-(D - dmin) / .006)
    owner = D.argmin(1)
    # colour: blended primitive colours x cavity darkening x mottling
    cols = np.stack([p.col for p in sc.prims])
    C = (Wc @ cols) / Wc.sum(1, keepdims=True)
    occ = np.zeros(len(V))
    sca = 1.0
    for i in range(1, 6):
        hh = ao_dist * i / 5
        occ += (hh - sc.field(V + N * hh, disp=True)) * sca
        sca *= .75
    ao = np.clip(1 - ao_k * 1.6 * occ / ao_dist, .12, 1)
    C = C * ao[:, None] ** 1.3
    C = C * (1 - mottle * .5 + mottle * fbm(V, 9, 3, seed + 5))[:, None]
    if bruise:
        t = sdf.smoothstep(.5, .75, fbm(V, bruise[2], 3, seed + 11))[:, None] * bruise[1]
        C = C * (1 - t + t * hexc(bruise[0]) / max(hexc(bruise[0]).max(), 1e-3))
    if veins:
        t = (ridge(V, veins[2], seed + 21, 10) * veins[1])[:, None]
        C = C * (1 - t + t * hexc(veins[0]) * 1.5)
    set_colors(o, lin2srgb(C))
    # writhe attribute (tentacles wriggle in the game's vertex shader)
    wr = np.array([p.writhe for p in sc.prims])
    Wt = (W @ wr) / W.sum(1)
    a = o.data.attributes.new('_writhe', 'FLOAT', 'POINT'); a.data.foreach_set('value', Wt.astype(F32))
    # materials: majority owner per face
    names = []
    for p in sc.prims:
        if p.mat and p.mat not in names:
            names.append(p.mat)
    for nm in names:
        o.data.materials.append(mats[nm])
    vmat = np.array([names.index(sc.prims[i].mat) if sc.prims[i].mat else 0 for i in owner])
    me = o.data
    lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
    vi = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', vi)
    ls = np.concatenate([[0], np.cumsum(lt)[:-1]])
    fm = np.zeros(len(me.polygons), np.int32)
    vm = vmat[vi]
    for f in range(len(me.polygons)):
        seg = vm[ls[f]:ls[f] + lt[f]]
        fm[f] = np.bincount(seg).argmax()
    me.polygons.foreach_set('material_index', fm)
    # skin weights: soft blend of the owning primitives' bones, 4 strongest
    bones = sorted({p.bone for p in sc.prims if p.bone})
    B = np.zeros((len(V), len(bones)))
    for j, p in enumerate(sc.prims):
        if p.bone:
            B[:, bones.index(p.bone)] += W[:, j]
    if B.shape[1] > 4:
        idx = np.argsort(-B, 1)[:, 4:]
        np.put_along_axis(B, idx, 0, 1)
    B[B < .02 * B.max(1, keepdims=True)] = 0
    B /= np.maximum(B.sum(1, keepdims=True), 1e-9)
    for j, bn in enumerate(bones):
        col = B[:, j]; nz = np.nonzero(col > 0)[0]
        if not len(nz):
            continue
        vg = o.vertex_groups.new(name=bn)
        q = np.round(col[nz] * 255).astype(int)
        for val in np.unique(q):
            if val == 0:
                continue
            vg.add(nz[q == val].tolist(), float(val) / 255, 'REPLACE')
    bl.uv_box(o, uv_scale)
    log(' ->', name, len(me.vertices), 'verts', len(me.polygons), 'faces', 'mats', names)
    return o


# ------------------------------------------------------------------ rig + clips
HUMAN_PARENT = {'hips': 'root', 'spine': 'hips', 'chest': 'spine', 'neck': 'chest', 'head': 'neck'}
for _s in 'LR':
    HUMAN_PARENT.update({'upperarm.' + _s: 'chest', 'forearm.' + _s: 'upperarm.' + _s, 'hand.' + _s: 'forearm.' + _s,
                         'thigh.' + _s: 'hips', 'shin.' + _s: 'thigh.' + _s, 'foot.' + _s: 'shin.' + _s})
HUMAN_ORDER = ['hips', 'spine', 'chest', 'neck', 'head'] + [n + '.' + sd for sd in 'LR' for n in
                                                            ('upperarm', 'forearm', 'hand', 'thigh', 'shin', 'foot')]
CONNECT = ('spine', 'chest', 'neck', 'head', 'forearm', 'hand', 'shin', 'foot')


def make_rig(J, parent=None, order=None):
    parent = parent or HUMAN_PARENT
    order = order or HUMAN_ORDER
    ad = bpy.data.armatures.new('rig')
    arm = bpy.data.objects.new('Armature', ad)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    root = eb.new('root'); root.head = (0, 0, 0); root.tail = (0, .2, 0)
    for n in order:
        e = eb.new(n); e.head, e.tail = Vector(J[n][0]), Vector(J[n][1]); e.roll = 0
        e.parent = eb[parent[n]]
        e.use_connect = parent is HUMAN_PARENT and n.startswith(CONNECT) and (Vector(J[n][0]) - Vector(J[parent[n]][1])).length < 1e-4
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.select_set(False)
    return arm


def bake_clips(arm, clips, loc_bone='hips', scale=1.0):
    """clips: name -> (seconds, loop, f(p) -> (rots{bone: [(axis, deg)]}, loc Vector (world, m), scales{bone: (x,y,z)}))."""
    arm.animation_data_create()
    rr = arm.data.bones[loc_bone].matrix_local.to_quaternion()
    # bones that scale in any clip get scale keys in every clip (so no clip inherits another's swelling)
    sbones = set()
    for dur, loop, f in clips.values():
        for p in (0, .25, .5, .75, 1):
            scl = f(p)[2]
            if scl:
                sbones |= set(scl)
    for clip, (dur, loop, f) in clips.items():
        act = bpy.data.actions.new(clip)
        act.use_fake_user = True
        arm.animation_data.action = act
        nfr = max(2, round(dur * FPS))
        steps = max(8, nfr // 2)
        for i in range(steps + 1):
            p = i / steps
            fr = 1 + p * nfr
            rots, loc, scl = f(p % 1.0 if loop else p)
            for pb in arm.pose.bones:
                pb.rotation_quaternion = wq(arm, pb.name, rots.get(pb.name, []))
                pb.keyframe_insert('rotation_quaternion', frame=fr)
                if pb.name in sbones:
                    pb.scale = (scl or {}).get(pb.name, (1, 1, 1))
                    pb.keyframe_insert('scale', frame=fr)
            hb = arm.pose.bones[loc_bone]
            hb.location = rr.inverted() @ (Vector(loc) * scale)
            hb.keyframe_insert('location', frame=fr)
    arm.animation_data.action = bpy.data.actions['Idle']


def finish(mesh, arm, fname):
    """Exports without images: the game applies the shared hx_* maps by material name (one download for every
    creature). Set FLESH_PREVIEW=<dir> to also write a copy with the textures embedded, for preview.py renders."""
    mesh.parent = arm
    md = mesh.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    kw = dict(animations=True, export_vertex_color='ACTIVE', export_attributes=True)
    bl.export(fname, export_image_format='NONE', **kw)
    pv = os.environ.get('FLESH_PREVIEW')
    if pv:
        os.makedirs(pv, exist_ok=True)
        keep = bl.MODELS
        bl.MODELS = pv
        try:
            bl.export(fname, **kw)
        finally:
            bl.MODELS = keep


# ------------------------------------------------------------------ pose helpers
S = math.sin
TAU2 = 2 * math.pi


def pulse(p, at, w=.04):
    """Sharp periodic spike (0..1) centred on phase `at` (wraps): twitches and spasms."""
    d = (p - at + .5) % 1.0 - .5
    return math.exp(-(d / w) ** 2)


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def merge(d, extra):
    for k, v in extra.items():
        d[k] = d.get(k, []) + v
    return d
