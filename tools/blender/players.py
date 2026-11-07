"""Player base bodies: naked, high-detail female and male built from signed-distance anatomy (anatomy.py).

Output assets/models/player_female.glb, player_male.glb on the shared rig with the 9 shared clips.
  * B_*   body regions (head, neck, chest, midriff, pelvis, upperarm, forearm, hand, thigh, shin, foot) - clothing
          hides what it fully covers
  * face  morph targets on the head, eyes and brows (nose / mouth / eyes / ears / jaw presets and sliders), see face.py
  * eyes  eye_white + eye_iris (tinted at runtime = eye colour); brows use a style atlas (UV offset at runtime)
  * C_<slot>_<item>  clothing pieces, H_<style> hair styles (wardrobe.py)
Metadata for the game is stored on the armature as the `worldex` extra.

Also writes player_<sex>_npc.glb: the crowd LOD (coarser meshes, single body mesh, thinner hair, same rig, clips,
material names and wardrobe meta) used by the pedestrians.

Run: blender --background --python tools/blender/players.py [-- female|male] [--fast] [--no-npc | --npc-only]
"""
import bpy, bmesh, sys, os, json, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl, sdf, anatomy, characters, face
from mathutils import Vector

F32 = np.float32
T0 = time.time()
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FAST = '--fast' in ARGS


def log(*a):
    print('[players %5.1fs]' % (time.time() - T0), *a, flush=True)


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


def faces(o):
    me = o.data
    n = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', n)
    vi = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', vi)
    return n, vi


def decimate_to(o, target):
    n = len(o.data.vertices)
    if n <= target:
        return
    bpy.context.view_layer.objects.active = o
    md = o.modifiers.new('dec', 'DECIMATE'); md.ratio = target / n
    bpy.ops.object.modifier_apply(modifier=md.name)


def set_normals(o, fn):
    N = sdf.normals(fn, verts(o))
    o.data.normals_split_custom_set_from_vertices([tuple(v) for v in N])


def drop_caps(V, Q, cuts, h):
    """Remove the flat caps the cut planes leave (they are hidden inside the neighbouring part anyway)."""
    if not cuts:
        return V, Q
    on = np.zeros(len(V), bool)
    for c in cuts:
        on |= np.abs(c(V)) < .3 * h
    Q = Q[~on[Q].all(1)]
    used = np.unique(Q)
    remap = np.full(len(V), -1, np.int64); remap[used] = np.arange(len(used))
    return V[used], remap[Q]


def part_mesh(name, fn, lo, hi, h, cuts, target, mat):
    def g(P):
        d = fn(P)
        for c in cuts:
            d = np.maximum(d, c(P))
        return d
    log('mesh', name, 'h=%.1fmm' % (h * 1000))
    V, Q = sdf.mesh(g, lo, hi, h, log=log)
    V, Q = drop_caps(V, Q, cuts, h)
    o = to_object(name, V, Q, mat)
    decimate_to(o, target)
    V = sdf.project(fn, verts(o), 2, max_step=h * .5)
    set_verts(o, V)
    set_normals(o, fn)
    log('  ->', name, len(o.data.vertices), 'verts', len(o.data.polygons), 'faces')
    return o


def plane_keep_below(n, p0, off=0.0):
    """Cut: keeps the side where (P - p0).n <= off."""
    n = np.asarray(n, F32) / np.linalg.norm(n); p0 = np.asarray(p0, F32)
    return lambda P: (P - p0) @ n - off


# ------------------------------------------------------------------ skin weights (analytic, position only)
def chain_param(P, pts):
    """Arc-length parameter of the closest point on a polyline, measured from pts[0] (negative before it)."""
    pts = [np.asarray(p, F32) for p in pts]
    best = np.full(len(P), 1e9, F32); s_out = np.zeros(len(P), F32)
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]; ab = b - a; L = float(np.linalg.norm(ab))
        t = ((P - a) @ ab) / (L * L)
        lo = -np.inf if i == 0 else 0.0
        hi = np.inf if i == len(pts) - 2 else 1.0
        tc = np.clip(t, lo, hi)
        q = a + tc[:, None] * ab
        d = sdf.length(P - q)
        m = d < best
        best[m] = d[m]; s_out[m] = acc + tc[m] * L
        acc += L
    return s_out


def chain_weights(s, joints, widths):
    """Telescoping smoothsteps: bone i owns the span between joints[i-1] and joints[i]."""
    out = []; prev = np.ones_like(s)
    for j, w in zip(joints, widths):
        st = sdf.smoothstep(j - w[0], j + w[1], s)
        out.append(prev * (1 - st)); prev = prev * st
    out.append(prev)
    return out


class Skinner:
    def __init__(self, B, Fd):
        self.B, self.F = B, Fd
        z = B.z
        self.neck_top = float(B.head_o[2] - .035 * B.head.s)

    def __call__(self, V, cover=None, hands=True):
        """Analytic weights at V. cover: the body parts a garment lies on (others never influence it, e.g. a skirt never
        follows the hand hanging next to it); hands=False folds the hand bones into the forearms."""
        B = self.B
        V = np.asarray(V, F32)
        parts = self.F.parts(V)
        names = ['torso', 'armL', 'armR', 'legL', 'legR']
        D = np.stack([parts[n] if (cover is None or n in cover) else np.full(len(V), 1e3, F32) for n in names], 1)
        z = V[:, 2]; ax = np.abs(V[:, 0])
        # blend softness: wide at the shoulder / outer hip, nearly hard elsewhere
        tau_arm = 1e-4 + .01 * sdf.smoothstep(B.zsh - .16, B.zsh - .04, z)
        tau_leg = 1e-4 + .012 * sdf.smoothstep(.03, .1, ax) * sdf.smoothstep(B.hip[2] - .25, B.hip[2] - .05, z)
        tau = np.stack([np.full_like(z, .004), tau_arm, tau_arm, tau_leg, tau_leg], 1)
        dmin = D.min(1, keepdims=True)
        M = np.exp(-np.clip((D - dmin) / tau, 0, 30))
        lat = sdf.smoothstep(B.sx - .06, B.sx - .005, ax)          # inner torso never follows the arm
        M[:, 1] *= lat; M[:, 2] *= lat
        M[:, 0] = np.maximum(M[:, 0], 1e-6)
        M /= M.sum(1, keepdims=True)
        W = {}

        def add(bone, w):
            W[bone] = W.get(bone, 0) + w
        zz = B.z
        tw = chain_weights(z, [B.z['navel'], B.z['chest'], B.z['neck'] + .01, self.neck_top],
                           [(.05, .05), (.06, .06), (.03, .03), (.02, .02)])
        for bone, w in zip(['hips', 'spine', 'chest', 'neck', 'head'], tw):
            add(bone, M[:, 0] * w)
        for k, side, sx in ((1, 'L', 1), (2, 'R', -1)):
            mv = np.array([sx, 1, 1], F32)
            Q = V * mv
            s = chain_param(Q, [B.shoulder, B.elbow, B.wrist, B.tip])
            le = float(np.linalg.norm(B.elbow - B.shoulder)); lw = le + float(np.linalg.norm(B.wrist - B.elbow))
            aw = chain_weights(s, [0.0, le, lw], [(.07, .045), (.035, .035), (.015, .02)])
            for bone, w in zip(['chest', 'upperarm.' + side, 'forearm.' + side, 'hand.' + side if hands else 'forearm.' + side], aw):
                add(bone, M[:, k] * w)
        for k, side, sx in ((3, 'L', 1), (4, 'R', -1)):
            Q = V * np.array([sx, 1, 1], F32)
            s = chain_param(Q, [B.hip, B.knee, B.ankle, B.toe])
            lk = float(np.linalg.norm(B.knee - B.hip)); la = lk + float(np.linalg.norm(B.ankle - B.knee))
            lw = chain_weights(s, [0.0, lk, la], [(.07, .03), (.04, .04), (.03, .02)])
            for bone, w in zip(['hips', 'thigh.' + side, 'shin.' + side, 'foot.' + side], lw):
                add(bone, M[:, k] * w)
        return W


def apply_weights(o, W, limit=4):
    names = list(W)
    A = np.stack([W[n] for n in names], 1)
    # keep the 4 strongest, renormalise
    if A.shape[1] > limit:
        idx = np.argsort(-A, 1)[:, limit:]
        np.put_along_axis(A, idx, 0, 1)
    A[A < .01] = 0
    A /= np.maximum(A.sum(1, keepdims=True), 1e-9)
    for j, n in enumerate(names):
        col = A[:, j]
        nz = np.nonzero(col > 0)[0]
        if not len(nz):
            continue
        vg = o.vertex_groups.get(n) or o.vertex_groups.new(name=n)
        q = np.round(col[nz] * 255).astype(int)
        for val in np.unique(q):
            sel = nz[q == val]
            vg.add(sel.tolist(), float(val) / 255, 'REPLACE')
    return A, names


def set_colors(o, C):
    me = o.data
    attr = me.color_attributes.new('Color', 'BYTE_COLOR', 'POINT')
    rgba = np.ones((len(C), 4), F32); rgba[:, :3] = np.clip(C, 0, 1)
    attr.data.foreach_set('color_srgb' if hasattr(attr.data[0], 'color_srgb') else 'color', rgba.ravel())
    me.color_attributes.active_color = attr


# ------------------------------------------------------------------ materials
def skin_mat(sex):
    m = bl.mat('skin', '#ffffff', 0, .52)
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Subsurface Weight'].default_value = .0
    vc = m.node_tree.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'
    m.node_tree.links.new(vc.outputs['Color'], b.inputs['Base Color'])
    return m


# everyday wardrobe kept on the crowd LOD (population.js picks from these)
NPC_KEEP = {'tee', 'sweater', 'tank', 'blouse', 'flannel', 'jeans', 'chinos', 'shorts', 'skirt', 'cargo', 'sundress', 'hoodie',
            'jacket', 'sneakers', 'ankle_boots', 'beanie', 'cap'}
NPC_HAIR = {'long', 'ponytail', 'bob', 'bun', 'sidepart', 'textured', 'buzz', 'swept'}


# ------------------------------------------------------------------ build
class PlayerBuilder:
    def __init__(self, sex, npc=False):
        self.sex = sex; self.npc = npc
        self.B = anatomy.Body(sex)
        self.F = anatomy.Field(self.B)
        self.skinner = Skinner(self.B, self.F)
        q = 2.0 if FAST else 1.0
        if npc:      # crowd LOD: coarser meshes, one body mesh, no lashes (see export)
            q = max(q, 2.2)
            self.res = dict(body=.0034 * q, head=.0009 * q, hand=.0012 * q, foot=.0016 * q)
            self.tgt = dict(body=7000, head=3200, hand=900, foot=700)
            return
        self.res = dict(body=.0034 * q, head=.0009 * q, hand=.0012 * q, foot=.0016 * q)
        self.tgt = dict(body=22000, head=16000, hand=3800, foot=2800)

    def body_parts(self):
        B, F = self.B, self.F
        mat = self.skin
        zN = float(B.head_o[2] - .114 * B.head.s - .01)   # neck seam just under the jaw (head mesh above)
        zF = float(B.ankle[2] + .045)                     # ankle seam (feet below)
        ov = .006
        objs = {}
        # head (+ upper neck)
        ho = B.head_o; hs = B.head.s
        objs['head'] = part_mesh('B_head', F, (-.1 * hs, ho[1] - .13 * hs, zN - .004), (.1 * hs, ho[1] + .13 * hs, ho[2] + .14 * hs),
                                 self.res['head'], [lambda P: zN - P[:, 2]], self.tgt['head'], mat)
        # hands: region beyond the wrist plane, inside a ball around the hand
        def hand_region(sx):
            wr = (B.wrist * [sx, 1, 1]).astype(F32); tp = (B.tip * [sx, 1, 1]).astype(F32)
            n = (tp - wr) / np.linalg.norm(tp - wr)
            k = 1.12 if B.m else 1.0
            ex = np.array([1.0, 0, 0]) - n[0] * n; ex /= np.linalg.norm(ex)
            Rm = np.array([n, np.cross(n, ex), ex], F32)
            c = (wr + tp) / 2 + n * .01
            return lambda P, o=0.0: np.maximum(-((P - wr) @ n) - o, sdf.ellipsoid(P, c, (.14 * k, .1 * k, .068 * k), Rm))
        self.hand_region = hand_region
        hands = []
        for sx in (1, -1):
            wr = B.wrist * [sx, 1, 1]; tp = B.tip * [sx, 1, 1]
            lo = np.minimum(wr, tp) - .09; hi = np.maximum(wr, tp) + .09      # room for the thumb in front of the palm
            R = hand_region(sx)
            Q = np.array([sx, 1, 1], F32)
            armhand = lambda P, Q=Q: anatomy.smin(F.arm_l(P * Q), F.hand_l(P * Q), .012)
            hands.append(part_mesh('hand', armhand, lo, hi, self.res['hand'], [lambda P, R=R: R(P, ov)], self.tgt['hand'], mat))
        objs['hand'] = bl.join(hands, 'B_hand')
        feet = []
        for sx in (1, -1):
            A = B.ankle * [sx, 1, 1]
            lo = (A[0] - .075, A[1] - .25, -.005); hi = (A[0] + .075, A[1] + .075, zF + .02)
            Q = np.array([sx, 1, 1], F32)
            legfoot = lambda P, Q=Q: anatomy.smin(F.leg_l(P * Q), F.foot_l(P * Q), .02)
            feet.append(part_mesh('foot', legfoot, lo, hi, self.res['foot'], [lambda P: P[:, 2] - zF - ov], self.tgt['foot'], mat))
        objs['foot'] = bl.join(feet, 'B_foot')
        # body between the seams
        cuts = [lambda P: P[:, 2] - zN - ov, lambda P: zF - P[:, 2]]
        for sx in (1, -1):
            R = hand_region(sx)
            cuts.append(lambda P, R=R: -R(P, -ov))
        objs['body'] = part_mesh('body', F, (-.34, -.2, zF - .01), (.34, .22, zN + .02), self.res['body'], cuts, self.tgt['body'], mat)
        return objs

    def colours(self, o, region):
        """Vertex colours: subtle skin variation (redder lips, ears, knuckles, cheeks; paler palms)."""
        V = verts(o)
        B = self.B
        base = np.array([.93, .86, .82], F32)
        C = np.tile(base, (len(V), 1))
        if region == 'head':
            L = V - B.head_o
            h = B.head
            s = h.s
            # lips
            lipd = np.minimum(sdf.ellipsoid(L, np.array([0, -.0815, -.0455 + (.002 if self.sex == 'female' else 0)]) * s, np.array([.021, .0095, .0072]) * s),
                              sdf.ellipsoid(L, np.array([0, -.0795, -.0545 + (.002 if self.sex == 'female' else 0)]) * s, np.array([.018, .0095, .0082]) * s))
            lip = sdf.smoothstep(.0015, -.0008, lipd)[:, None]
            lipc = np.array([.86, .62, .6]) if self.sex == 'female' else np.array([.84, .68, .64])
            C = C * (1 - lip) + lipc * lip
            # cheeks / nose tip / ears warmer
            for c, r, k in (((.04, -.06, -.02), .022, .08), ((-.04, -.06, -.02), .022, .08), ((0, -.09, -.02), .012, .06)):
                w = np.exp(-(sdf.length(L - np.array(c) * s) / (r * s)) ** 2)[:, None] * k
                C = C * (1 - w) + np.array([.92, .66, .64]) * w
            ear = (np.abs(L[:, 0]) > .066 * s)[:, None] * .12
            C = C * (1 - ear) + np.array([.9, .68, .64]) * ear
            # eyelid line darker (lash line)
            for sx in (1, -1):
                E = h.eye * np.array([sx, 1, 1])
                r = sdf.length(L - E)
                op = h.lid_opening(L, E.astype(F32))
                w = (np.exp(-(op / (.0009 * s)) ** 2) * (r < h.eye_r + .003 * s) * (L[:, 1] < E[1]))[:, None] * .75
                up = (L[:, 2] > E[2] - .0005)[:, None]
                C = C * (1 - w * up) + np.array([.18, .12, .11]) * (w * up) + 0 * w
                lw = w * (1 - up) * .5
                C = C * (1 - lw) + np.array([.55, .4, .38]) * lw
        if region == 'hand':
            # nails: dorsal tips of the fingers, pale pink
            pass
        return C

    def eyes(self):
        """Eyeballs: sclera + iris cap (UV 0..1 across the iris for the iris texture)."""
        B = self.B; h = B.head; s = h.s
        objs = []
        white = bl.mat('eye_white', '#f2efea', 0, .18, coat=1.0)
        iris = bl.mat('eye_iris', '#6f8fae', 0, .12, coat=1.0, image='eye_iris.png')
        for sx in (1, -1):
            E = B.head_o + h.eye * np.array([sx, 1, 1])
            r = h.eye_r * .985
            nu, nv = 40, 28
            vs = []; fs = []
            for j in range(nv + 1):
                th = math.pi * j / nv            # 0 at the front pole
                for i in range(nu):
                    ph = 2 * math.pi * i / nu
                    d = np.array([math.sin(th) * math.cos(ph), -math.cos(th), math.sin(th) * math.sin(ph)])
                    rr = r
                    if th < .52:                  # iris: slightly flattened, lens bulge on top
                        rr = r * (1 - .035 * (1 - th / .52)) if th > .2 else r * (1 - .01)
                    vs.append(E + d * rr)
            for j in range(nv):
                for i in range(nu):
                    a = j * nu + i; b = j * nu + (i + 1) % nu
                    fs.append((a, b, b + nu, a + nu))
            V = np.array(vs, F32); Q = np.array(fs)
            o = to_object('eye', V, Q)
            o.data.materials.append(white); o.data.materials.append(iris)
            mi = np.array([1 if j < 8 else 0 for j in range(nv) for i in range(nu)], np.int32)
            o.data.polygons.foreach_set('material_index', mi)
            uv = o.data.uv_layers.new(name='UVMap')
            n, vi = faces(o)
            P = V[vi] - E
            u = .5 + P[:, 0] / (2 * r * math.sin(.52)) * sx
            v = .5 + P[:, 2] / (2 * r * math.sin(.52))
            uv.data.foreach_set('uv', np.stack([u, v], 1).astype(F32).ravel())
            objs.append(o)
        eo = bl.join(objs, 'B_eyes')
        return eo

    def iris_texture(self):
        """Grey iris (tinted by eye colour): radial fibres, darker limbal ring, black pupil."""
        N = 256
        y, x = (np.mgrid[0:N, 0:N] + .5) / N * 2 - 1
        r = np.sqrt(x * x + y * y); a = np.arctan2(y, x)
        rng = np.random.default_rng(3)
        fib = np.zeros_like(r)
        for k, amp in ((24, .25), (57, .18), (113, .12), (203, .08)):
            ph = rng.uniform(0, 6.28)
            fib += amp * np.sin(a * k + ph + r * rng.uniform(1, 4))
        ri = .86   # iris edge (texture covers the cap a bit beyond)
        t = np.clip(r / ri, 0, 1)
        val = .72 + fib * .35 * (t > .3) - .25 * np.clip((t - .75) / .25, 0, 1) ** 1.5 + .15 * np.exp(-((t - .42) / .08) ** 2)
        val = np.clip(val, 0, 1)
        img = np.ones((N, N, 4), F32)
        col = np.stack([val, val, val], -1)
        col[r < ri * .28] = .02                                      # pupil
        col[r > ri] = np.array([.95, .93, .9])                       # white beyond the limbus
        edge = np.clip((r - ri * .97) / (ri * .06), 0, 1)
        col = col * (1 - edge[..., None] * 0)
        img[..., :3] = col
        im = bpy.data.images.new('eye_iris', N, N)
        im.pixels = img[::-1].ravel()
        im.filepath_raw = os.path.join(bl.TEXTURES, 'eye_iris.png'); im.file_format = 'PNG'; im.save()


    # ---------------------------------------------------------------- brows, lashes, morphs
    BROW_STYLES = ['natural', 'arched', 'straight', 'bold']

    def brow_texture(self):
        """4 brow styles stacked top-to-bottom (white strands, tinted by hair colour). u: inner->outer, v: up.
        Each style is 1024 x 256: ~600 thin hairs (a real brow has ~250 hairs of 6-11 mm), crisp so the game's alpha
        cut-off shows hairs, not a bar. Inner hairs stand up, the body sweeps outward, the tail lies flat and thins.
        Style 0 is the default look: slimmer and arched on the female face, fuller and straighter on the male."""
        W, Hb = 1024, 256
        rng = np.random.default_rng(11)
        img = np.zeros((Hb * 4, W, 4), F32)
        fem = self.sex == 'female'
        shapes = {  # centre-line height c(u) and half thickness t(u), both in v units
            'natural': ((lambda u: .40 + .26 * np.sin(np.clip(u, 0, 1) * 2.6) - .16 * u, lambda u: .15 - .1 * u) if fem else
                        (lambda u: .42 + .13 * np.sin(np.clip(u, 0, 1) * 2.3) - .08 * u, lambda u: .23 - .12 * u)),
            'arched': (lambda u: .38 + .3 * np.sin(np.clip(u, 0, 1) * 2.7) - .14 * u, lambda u: .14 - .08 * u),
            'straight': (lambda u: .45 + .05 * u, lambda u: .22 - .1 * u),
            'bold': (lambda u: .4 + .22 * np.clip(u / .7, 0, 1) - .3 * np.clip((u - .7) / .3, 0, 1), lambda u: .3 - .14 * u),
        }
        su, sv = 50.0, 25.0        # the brow patch is ~50 x 25 mm: texels are 2x finer in u
        for k, name in enumerate(self.BROW_STYLES):
            cf, tf = shapes[name]
            A = np.zeros((Hb, W), F32); Cc = np.full((Hb, W), .85, F32)
            n_hairs = 520 if name != 'bold' else 700
            for _ in range(n_hairs):
                u0 = rng.uniform(.02, .95) ** 1.08
                c, t = cf(u0), max(tf(u0), .03)
                v0 = c + rng.uniform(-t, t) * .95
                # direction (radians from +u): inner hairs up, then outward, the tail down a little; top row lies flatter
                ang = np.interp(u0, [0, .18, .5, 1], [1.35, .75, .25, -.18]) - .25 * (v0 - c) / t + rng.normal(0, .1)
                Lmm = rng.uniform(5.5, 9.5) * (1 - .35 * u0)
                curve = rng.normal(-.25, .12)                       # hairs curve with the brow's flow
                shade = rng.uniform(.75, 1.0)
                for st in np.linspace(0, 1, 18):
                    a2 = ang + curve * st
                    pu = u0 + np.cos(a2) * Lmm * st / su
                    pv = v0 + np.sin(a2) * Lmm * st / sv
                    if pu < 0 or pu > 1 or pv < 0 or pv > 1:
                        break
                    cx, cy = pu * W, (1 - pv) * Hb
                    rad = .9 * (1 - .65 * st)                           # tapered tip
                    x0, x1 = int(max(cx - 3, 0)), int(min(cx + 4, W)); y0, y1 = int(max(cy - 3, 0)), int(min(cy + 4, Hb))
                    gx, gy = np.meshgrid(np.arange(x0, x1) + .5, np.arange(y0, y1) + .5)
                    d2 = (gx - cx) ** 2 + ((gy - cy) * 2.0) ** 2
                    a = np.clip(1.6 - np.sqrt(d2) / rad, 0, 1) * (1 - .3 * st)
                    win = A[y0:y1, x0:x1]
                    upd = a > win
                    win[upd] = a[upd]; Cc[y0:y1, x0:x1][upd] = shade
            edge = np.clip(np.minimum(np.arange(W) / W, 1 - np.arange(W) / W)[None, :] / .02, 0, 1)
            img[k * Hb:(k + 1) * Hb, :, 3] = A * edge
            img[k * Hb:(k + 1) * Hb, :, :3] = Cc[..., None]
        im = bpy.data.images.new('brows', W, Hb * 4, alpha=True)
        im.pixels = img[::-1].ravel()
        im.filepath_raw = os.path.join(bl.TEXTURES, f'brows_{self.sex}.png'); im.file_format = 'PNG'; im.save()

    def lash_texture(self):
        W, Hh = 256, 64
        rng = np.random.default_rng(5)
        img = np.zeros((Hh, W, 4), F32)
        uu, vv = np.meshgrid((np.arange(W) + .5) / W, (np.arange(Hh) + .5) / Hh)
        vv = 1 - vv
        a = np.zeros((Hh, W), F32)
        for _ in range(170):
            u0 = rng.uniform(.03, .97); L = rng.uniform(.55, 1.0) * (.6 + .4 * np.sin(u0 * np.pi))
            lean = (u0 - .3) * .08
            for st in np.linspace(0, 1, 10):
                pu = u0 + lean * st ** 2; pv = st * L
                d2 = ((uu - pu) * 9) ** 2 + ((vv - pv) * .2) ** 2
                a = np.maximum(a, np.exp(-d2 / (2 * .02 ** 2)) * (1 - st * .6))
        img[..., 3] = np.clip(a * 1.4, 0, 1); img[..., :3] = .06
        im = bpy.data.images.new('lashes', W, Hh, alpha=True)
        im.pixels = img[::-1].ravel()
        im.filepath_raw = os.path.join(bl.TEXTURES, 'lashes.png'); im.file_format = 'PNG'; im.save()

    def alpha_mat(self, name, image, color='#ffffff', rough=.7):
        m = bpy.data.materials.new(name)
        nt = m.node_tree; b = nt.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*bl.hexrgb(color), 1); b.inputs['Roughness'].default_value = rough
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(bl.TEXTURES, image))
        nt.links.new(tn.outputs['Color'], b.inputs['Base Color']); nt.links.new(tn.outputs['Alpha'], b.inputs['Alpha'])
        try:
            m.surface_render_method = 'DITHERED'
        except Exception:
            pass
        return m

    def brows(self, head):
        """Shell over the brow skin (offset 0.3 mm), UV per side: u inner->outer, v up; style 0 block of the atlas."""
        B = self.B; h = B.head; s = h.s
        me = head.data
        V = verts(head); n, vi = faces(head)
        starts = np.concatenate([[0], np.cumsum(n)[:-1]])
        C = np.add.reduceat(V[vi], starts, axis=0) / n[:, None]
        L = C - B.head_o
        keep = np.zeros(len(n), bool); side = np.zeros(len(n))
        for sx in (1, -1):
            E = h.eye * np.array([sx, 1, 1])
            a = (L[:, 0] - E[0]) * sx; b = L[:, 2] - E[2]
            k = (a > -.024 * s) & (a < .026 * s) & (b > .005 * s) & (b < .03 * s) & (L[:, 1] < E[1] + .004 * s)
            keep |= k; side[k] = sx
        bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep[f.index]], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        nm = bpy.data.meshes.new('brows'); bm.to_mesh(nm); bm.free()
        o = bpy.data.objects.new('B_brows', nm); bpy.context.scene.collection.objects.link(o)
        Vb = verts(o)
        Nb = sdf.normals(self.F, Vb)
        Vb = Vb + Nb * .0003
        set_verts(o, Vb)
        o.data.normals_split_custom_set_from_vertices([tuple(v) for v in Nb])
        o.data.materials.append(self.alpha_mat('brow', f'brows_{self.sex}.png', '#3a2a22', .8))
        n2, vi2 = faces(o)
        P = Vb[vi2] - B.head_o
        sx = np.sign(P[:, 0])
        E = np.stack([h.eye[0] * sx, np.full_like(sx, h.eye[1]), np.full_like(sx, h.eye[2])], 1)
        u = ((P[:, 0] - E[:, 0]) * sx + .024 * s) / (.05 * s)
        v = (P[:, 2] - E[:, 2] - .005 * s) / (.025 * s)
        u = np.clip(u, 0, 1); v = np.clip(v, 0, 1)
        uv = o.data.uv_layers.new(name='UVMap')
        uv.data.foreach_set('uv', np.stack([u, .75 + v * .25], 1).astype(F32).ravel())
        return o

    def lashes(self):
        """Upper lash ribbons along the lid margin, sweeping out and up."""
        B = self.B; h = B.head; s = h.s
        objs = []
        for sx in (1, -1):
            E = (h.eye * np.array([sx, 1, 1])).astype(F32)
            rl = h.eye_r + .0012 * s
            # sample the upper opening curve
            aa = np.linspace(-.0138 * s, .0145 * s, 16)
            pts = []
            for a in aa:
                lo, hi = 0.0, .012 * s
                for _ in range(30):                 # find the upper edge: opening sdf == 0 along b
                    mid = (lo + hi) / 2
                    P = np.array([[E[0] + a * sx, E[1] - .02, E[2] + mid]], F32)
                    if h.lid_opening(P, E)[0] < 0:
                        lo = mid
                    else:
                        hi = mid
                b = lo
                q = np.array([a * sx, 0, b]); yy = -np.sqrt(max(rl * rl - a * a - b * b, 1e-8))
                pts.append(E + np.array([a * sx, yy, b], F32))
            pts = np.array(pts)
            V = []; Q = []; UV = []
            L = (.0065 if not B.m else .005) * s
            for i, p in enumerate(pts):
                nrm = (p - E) / np.linalg.norm(p - E)
                d = nrm + np.array([0, 0, .55]); d /= np.linalg.norm(d)
                d2 = nrm * .4 + np.array([0, 0, 1.0]); d2 /= np.linalg.norm(d2)
                t = i / (len(pts) - 1)
                k = .55 + .45 * np.sin(t * np.pi)
                V += [p, p + d * L * .55 * k, p + d * L * .5 * k + d2 * L * .5 * k]
                UV += [(t, 0), (t, .5), (t, 1)]
            for i in range(len(pts) - 1):
                for j in range(2):
                    a0 = i * 3 + j
                    Q.append((a0, a0 + 3, a0 + 4, a0 + 1))
            o = to_object('lash', np.array(V, F32) + B.head_o, np.array(Q))
            uv = o.data.uv_layers.new(name='UVMap'); n_, vi_ = faces(o)
            UVa = np.array(UV, F32)
            uv.data.foreach_set('uv', UVa[vi_].ravel())
            objs.append(o)
        o = bl.join(objs, 'B_lashes')
        o.data.materials.append(self.alpha_mat('lash', 'lashes.png', '#ffffff', .6))
        return o

    def add_morphs(self, objs):
        """Shape keys for every face morph on the head-attached meshes (sparse in the GLB)."""
        B = self.B
        M = face.Morphs(B.head, self.sex)
        for o, part in objs:
            V = verts(o)
            L = V - B.head_o
            o.shape_key_add(name='Basis', from_mix=False)
            for name in M.names():
                L2 = M.apply(name, L, part)
                if np.abs(L2 - L).max() < 2e-5:
                    L2 = L2.copy(); L2[0, 0] += 1e-6          # keep the key so every mesh has the same morph list
                k = o.shape_key_add(name=name, from_mix=False)
                k.data.foreach_set('co', (L2 + B.head_o).astype(F32).ravel())
                k.value = 0.0                                     # rest face (the GLB's default weights)
        return M

    def run(self):
        bl.reset()
        log('====', self.sex)
        self.iris_texture()
        self.skin = skin_mat(self.sex)
        parts = self.body_parts()
        eyes = self.eyes()
        # weights + colours
        for key, o in parts.items():
            set_colors(o, self.colours(o, key) if key != 'head' else np.ones((len(o.data.vertices), 3), F32))
            W = self.skinner(verts(o))
            apply_weights(o, W)
        # the face: its own UVs and baked skin maps (colour, pores / lines normal, roughness), see skin.py
        import skin
        face_mat = skin.bake_face(self, parts['head'])
        # the rest of the body: tiling pore / crease detail on box-projected UVs
        skin.detail_maps()
        for key, o in parts.items():
            if key != 'head':
                skin.box_uv(o)
        skin.detail_material(self.skin)
        hd = parts['head'].data
        for i, mm in enumerate(hd.materials):
            if mm and mm.name.split('.')[0] == 'skin':
                hd.materials[i] = face_mat
        W = {'head': np.ones(len(eyes.data.vertices), F32)}
        apply_weights(eyes, W)
        regions = self.split_body(parts['body'])
        self.brow_texture(); self.lash_texture()
        brows = self.brows(parts['head']); lashes = self.lashes()
        for o in (brows, lashes):
            apply_weights(o, {'head': np.ones(len(o.data.vertices), F32)})
        self.add_morphs([(parts['head'], 'skin'), (eyes, 'eyeball'), (brows, 'skin'), (lashes, 'skin')])
        import wardrobe
        self.wardrobe = wardrobe.Kit(self).run() if '--naked' not in ARGS else {'items': {}, 'defaults': {}}
        for o in regions:
            set_normals(o, self.F)
        if self.npc:
            # pedestrians only wear everyday pieces: drop the armour/tactical items from the crowd LOD (smaller GLB, fewer clones)
            items = self.wardrobe['items']
            for sl in list(items):
                for it in list(items[sl]):
                    if (it not in NPC_HAIR if sl == 'hair' else it not in NPC_KEEP) and not items[sl][it].get('locked'):
                        o = bpy.data.objects.get('C_%s__%s' % (sl, it))
                        if o is not None:
                            bpy.data.objects.remove(o)
                        del items[sl][it]
                if not items[sl]:
                    del items[sl]
            d = self.wardrobe['defaults']
            for sl in list(d):
                if d[sl] != 'none' and (sl not in items or d[sl] not in items[sl]):
                    d[sl] = {'legs': 'jeans', 'top': 'tee', 'feet': 'sneakers', 'hair': 'long' if self.sex == 'female' else 'sidepart'}.get(sl, 'none')
            # one skin mesh for the whole body below the head (garments cover by the skin cover mask, not region hiding)
            body = bl.join([o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('B_')
                            and o.name not in ('B_head', 'B_eyes', 'B_brows', 'B_lashes')], 'B_body')
            bpy.data.objects.remove(lashes)
        self.cover_masks()
        # rig
        b = type('B', (), {})(); b.J = self.B.joints(); b.s = self.B.H / 1.82
        arm = characters.make_armature(b, pole_angle=90)   # elbows down, little upper-arm twist (skinned shoulders)
        for bn in arm.data.bones:
            bn.use_deform = not bn.name.startswith(('ik_', 'pole', 'root'))
        for o in list(bpy.context.scene.objects):
            if o.type == 'MESH':
                o.parent = arm
                md = o.modifiers.new('Armature', 'ARMATURE'); md.object = arm
        characters.animate(arm, b.s, style=self.sex, clips=characters.PLAYER_CLIPS)
        meta = {'v': 3, 'sex': self.sex, 'regions': sorted(o.name[2:] for o in bpy.context.scene.objects if o.name.startswith('B_')),
                'morphs': {'groups': face.GROUPS, 'sliders': face.SLIDERS}, 'brows': self.BROW_STYLES,
                'wardrobe': self.wardrobe['items'], 'defaults': self.wardrobe['defaults']}
        arm['worldex'] = json.dumps(meta)
        self.arm = arm
        return arm

    def cover_masks(self):
        """Per body vertex bitmask of the garments lying over it (ray along the skin normal hits the garment within 3 cm).
        Bit = wardrobe item's `cover` index. The game pushes masked skin a few mm inwards while those garments are worn,
        so animated skin never pierces cloth. Eroded by two vertex rings so the step stays hidden under the garment."""
        from mathutils.bvhtree import BVHTree
        items = [(sl, it) for sl, d in self.wardrobe['items'].items() for it in d if sl != 'hair']
        trees = []
        for bit, (sl, it) in enumerate(items):
            o = bpy.data.objects.get('C_%s__%s' % (sl, it))
            if o is None or bit > 22:
                continue
            V = verts(o); n, vi = faces(o)
            starts = np.concatenate([[0], np.cumsum(n)[:-1]])
            polys = [vi[a:a + k].tolist() for a, k in zip(starts, n)]
            trees.append((bit, BVHTree.FromPolygons(V.tolist(), polys), V.min(0) - .03, V.max(0) + .03))
            self.wardrobe['items'][sl][it]['cover'] = bit
        tot = 0
        for o in bpy.context.scene.objects:
            if o.type != 'MESH' or not o.name.startswith('B_') or o.name in ('B_eyes', 'B_brows', 'B_lashes'):
                continue
            V = verts(o); N = sdf.normals(self.F, V)
            mask = np.zeros(len(V), np.int64)
            ei = np.empty(len(o.data.edges) * 2, np.int32); o.data.edges.foreach_get('vertices', ei); E = ei.reshape(-1, 2)
            for bit, tree, lo, hi in trees:
                sel = np.nonzero(np.all((V > lo) & (V < hi), 1))[0]
                if not len(sel):
                    continue
                hit = np.zeros(len(V), bool)
                for i in sel:
                    p = V[i] - N[i] * .0005
                    if tree.ray_cast(p.tolist(), N[i].tolist(), .03)[0] is not None:
                        hit[i] = True
                for _ in range(2):          # erode: a vertex stays covered only if all its neighbours are
                    bad = np.zeros(len(V), bool)
                    bad[E[:, 0][~hit[E[:, 1]]]] = True; bad[E[:, 1][~hit[E[:, 0]]]] = True
                    hit &= ~bad
                mask[hit] |= 1 << bit
            at = o.data.attributes.new('_covermask', 'FLOAT', 'POINT')
            at.data.foreach_set('value', mask.astype(F32))
            tot += int((mask > 0).sum())
        log('cover masks:', len(trees), 'garments,', tot, 'covered skin verts')

    def split_body(self, body):
        """Body -> B_<region> objects by dominant bone."""
        names = [g.name for g in body.vertex_groups]
        nv = len(body.data.vertices)
        Wm = np.zeros((nv, len(names)), F32)
        for v in body.data.vertices:
            for g in v.groups:
                Wm[v.index, g.group] = g.weight
        n, vi = faces(body)
        starts = np.concatenate([[0], np.cumsum(n)[:-1]])
        fw = np.add.reduceat(Wm[vi], starts, axis=0)
        dom = [names[i].split('.')[0] for i in fw.argmax(1)]
        V = verts(body)
        fz = np.add.reduceat(V[vi][:, 2], starts) / n
        region_of = {'hips': 'pelvis', 'spine': 'midriff', 'chest': 'chest', 'neck': 'neck', 'head': 'neck', 'upperarm': 'upperarm',
                     'forearm': 'forearm', 'hand': 'forearm', 'thigh': 'thigh', 'shin': 'shin', 'foot': 'shin'}
        tags = np.array([region_of[d] for d in dom])
        out = []
        for r in sorted(set(tags)):
            o = body.copy(); o.data = body.data.copy(); o.name = 'B_' + r
            bpy.context.scene.collection.objects.link(o)
            bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if tags[f.index] != r], context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(o.data); bm.free()
            out.append(o)
        bpy.data.objects.remove(body)
        return out


def export(sex):
    kw = dict(animations=True, export_vertex_color='ACTIVE', export_morph_normal=False, export_attributes=True)
    if '--npc-only' not in ARGS:
        PlayerBuilder(sex).run()
        bl.quantize_glb(bl.export('player_%s.glb' % sex, **kw))
    if '--no-npc' not in ARGS:
        PlayerBuilder(sex, npc=True).run()
        bl.quantize_glb(bl.export('player_%s_npc.glb' % sex, **kw))


if __name__ == '__main__':
    for sex in ('female', 'male'):
        if not [a for a in ARGS if a in ('female', 'male')] or sex in ARGS:
            export(sex)
