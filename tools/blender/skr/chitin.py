"""The Sarketh's ARMOUR (the owner, 2026-11-15: "the metal pieces are its armor"): metal plates worn over the dark
body, laid as blades that follow it; and the body's own claws and lines of light.

MODULAR (the owner: "we will be adding more armor for them later ... a bigger boss version ... different colors"): every
piece belongs to a SLOT (`Armour.slot` when it is made: helmet, neck, chest, back, shoulders, arms, hands, belt, legs,
feet; "body" for what is the creature itself: claws, eyes) and join() makes one part per slot, all skinned to the one
skeleton, so a set is a list of parts that can be swapped, added to or made heavier one slot at a time without
touching the body. Colour is the material's (skr_armour / skr_armour_dark: a tint per set in the game).

The kit:

A BLADE is a plate laid ON the body from a base point to a tip point: its middle line is carried over the surface (the
points projected onto the body's distance field), it is as wide as `w` across the surface (wrapping round a limb), and
from `free` along its length it leaves the body and runs on into the air (a spike, a crest blade, a shoulder flare). Its
outline is a leaf: a rounded base (tucked under the plate before it), widest at `peak`, a point at the tip; its top has a
raised ridge down the middle, it is `thick` at the base and thinner at the tip, and its walls slope in (a chamfer), so
every edge catches the light as the sheet's plates do. Each plate is a closed mesh of its own with UVs in metres along and
across it (the chitin's growth lines run along every plate) and corner colours: a tone of its own, brighter at its rim
(the sheet's pale edge). It moves rigidly with one bone.

A CLAW is a curved horn, flattened to a blade, from a root to a point. A LIGHT is a thin strip of glow on the surface.
"""
import math
import os
import sys
import bpy
import bmesh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sdf          # noqa: E402
import gunkit as K  # noqa: E402

F32 = np.float32
TILE = .25                       # metres of chitin a texture tile covers


def smooth(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / max(e1 - e0, 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def unit(v):
    v = np.asarray(v, float)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def mirror_bone(b):
    return b[:-2] + ('.R' if b.endswith('.L') else '.L') if b and b[-2:] in ('.L', '.R') else b


class Armour:
    def __init__(self, S, mats, seed=1):
        self.S = S
        self.f = lambda P: S.field(np.asarray(P, F32), disp=False)
        self.mats = mats
        self.items = {}                                   # (slot, material) -> list of objects
        self.slot = 'body'
        self.rng = np.random.RandomState(seed)
        self.count = 0
        self.thick_k = 1.0                                # every plate's thickness, scaled (a body's own choice)
        self.tip_k = 1.0                                  # how far every tip flares off the body, scaled

    # ------------------------------------------------------------------ helpers
    def project(self, P, iters=6, fn=None):
        return sdf.project(fn or self.f, np.asarray(P, F32), iters, max_step=.03).astype(float)

    def normal(self, P, fn=None):
        return sdf.normals(fn or self.f, np.asarray(P, F32)).astype(float)

    def subfield(self, bones):
        """the surface of only these bones' primitives (a limb's plates follow that limb, never the next one)"""
        prims = [p for p in self.S.prims if p.bone in bones and p.op == 'add']
        cuts = [p for p in self.S.prims if p.bone in bones and p.op == 'sub']

        def f(P):
            P = np.asarray(P, F32)
            d = np.full(len(P), 1e3, F32)
            for pr in prims:
                di = pr.eval(P, self.S.margin)
                d = sdf.smin(d, di, pr.k) if pr.k > 0 else np.minimum(d, di)
            for pr in cuts:
                d = sdf.smax(d, -pr.eval(P, self.S.margin), pr.k)
            return d
        return f

    def exit_point(self, o, d, fn, maxd=.30, step=.0015):
        """marching out from a point inside along d: where the surface is crossed"""
        o = np.asarray(o, float); d = unit(d)
        ts = np.arange(0, maxd, step)
        v = fn((o[None, :] + ts[:, None] * d[None, :]).astype(F32))
        out = np.nonzero(v > 0)[0]
        if not len(out):
            return None
        t = ts[out[0]]
        return o + d * t

    def bone_at(self, p):
        D = np.abs(self.S.distances(np.asarray([p], F32)))[0]
        for i in np.argsort(D):
            if self.S.prims[i].bone:
                return self.S.prims[i].bone
        return 'hips'

    def _store(self, name, V, faces, uv, col, mat, bone):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(map(float, v)) for v in V], [], faces)
        me.update()
        ul = me.uv_layers.new(name='UVMap')
        ca = me.color_attributes.new('Color', 'BYTE_COLOR', 'CORNER')
        vi = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', vi)
        ul.data.foreach_set('uv', np.asarray(uv, F32)[vi].ravel())
        rgba = np.ones((len(vi), 4), F32); rgba[:, :3] = np.clip(np.asarray(col, F32)[vi], 0, 1)
        ca.data.foreach_set('color', rgba.ravel())
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        o = K._obj(name, me, self.mats[mat])
        K.harden(o, 34)
        vg = o.vertex_groups.new(name=bone)
        vg.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
        self.items.setdefault((self.slot, mat), []).append(o)
        self.count += 1
        return o

    # ------------------------------------------------------------------ the blade
    def blade(self, name, a, b, w, bone=None, lift=.0025, tip=0.0, free=1.0, thick=.006, ridge=.0025, peak=.35, point=1.0,
              base=.55, n=(20, 9), mat='armour', bend=(0, 0, 0), mirror=True, tone=None, lean=0.0, only=()):
        """a, b: base and tip (left side; mirror=True makes the right one too). bend: a bow added along the length
        (metres, at the middle, as a vector). lean: the plate turned about its own length (radians): one edge lifted."""
        out = []
        for side in ((1, -1) if mirror else (1,)):
            sx = np.array([side, 1, 1], float)
            A = np.asarray(a, float) * sx; Bp = np.asarray(b, float) * sx; bd = np.asarray(bend, float) * sx
            bn = bone if side == 1 or bone is None else mirror_bone(bone)
            fn = self.subfield(set(only) | {mirror_bone(o_) for o_ in only}) if only else None
            out.append(self._blade(f'{name}{"" if side == 1 else "_R"}', A, Bp, w, bn, lift, tip, free, thick, ridge, peak,
                                   point, base, n, mat, bd, tone, lean * side, fn))
        return out

    def _blade(self, name, A, Bp, w, bone, lift, tip, free, thick, ridge, peak, point, base, n, mat, bend, tone, lean, fn=None):
        nu, nv = n
        u = np.linspace(0, 1, nu)
        L = float(np.linalg.norm(Bp - A))
        thick = thick * self.thick_k
        tip = tip * self.tip_k
        C = A + (Bp - A) * u[:, None] + bend[None, :] * np.sin(np.pi * np.minimum(u, 1))[:, None]
        att = 1 - smooth(free, min(free + .3, 1.0), u) if free < 1 else np.ones(nu)
        Cp = self.project(C, fn=fn)
        Cc = Cp * att[:, None] + C * (1 - att)[:, None]
        N0 = self.normal(Cp, fn=fn)
        T = unit(np.gradient(Cc, axis=0))
        Sd = unit(np.cross(N0, T))
        if free < 1:
            i0 = max(0, int(np.searchsorted(u, free)) - 1)
            for i in range(i0 + 1, nu):
                sv = Sd[i0] - T[i] * np.dot(Sd[i0], T[i])
                Sd[i] = unit(sv)
        N = unit(np.cross(T, Sd))
        if abs(lean) > 1e-4:
            ca, sa = math.cos(lean), math.sin(lean)
            Sd, N = Sd * ca + N * sa, N * ca - Sd * sa
        def outline(pk, pt):
            return np.where(u < pk, base + (1 - base) * np.sin(np.pi / 2 * u / pk), ((1 - u) / (1 - pk)).clip(0) ** pt)
        pk2 = float(np.clip(peak + self.rng.uniform(-.14, .14), .15, .8))
        pt2 = point * self.rng.uniform(.7, 1.4)
        prof = outline(peak, point)
        prof2 = outline(pk2, pt2)
        hw = w * .5 * np.maximum(prof, prof2)
        v = np.linspace(-1, 1, nv)
        side_scale = np.where(v[None, :] < 0, (prof / np.maximum(np.maximum(prof, prof2), 1e-6))[:, None],
                              (prof2 / np.maximum(np.maximum(prof, prof2), 1e-6))[:, None])
        rise = lift + tip * u ** 2.2

        def grid(vs, off):
            P = Cc[:, None, :] + Sd[:, None, :] * ((v[None, :] * side_scale)[..., None] * vs * hw[:, None, None])
            flat = P.reshape(-1, 3)
            Pp = self.project(flat, fn=fn).reshape(P.shape)
            Np = self.normal(Pp.reshape(-1, 3), fn=fn).reshape(P.shape)
            at = att[:, None, None]
            Q = Pp * at + P * (1 - at)
            Nn = unit(Np * at + N[:, None, :] * (1 - at))
            return Q + Nn * off[..., None]

        crown = ridge * (1 - np.abs(v[None, :]) ** 1.15) * np.maximum(prof, prof2)[:, None] ** .5          # a crease, not a dome
        th = thick * (.35 + .65 * (1 - u))[:, None] * np.ones((1, nv))
        top = grid(1.0, rise[:, None] + crown + th * .5)
        bot = grid(.86, rise[:, None] - th * .5 + .0004)
        V = np.concatenate([top.reshape(-1, 3), bot.reshape(-1, 3)])
        nt = nu * nv
        idx = lambda i, j, b=0: b * nt + i * nv + j
        faces = []
        for i in range(nu - 1):
            for j in range(nv - 1):
                faces.append((idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)))
                faces.append((idx(i, j, 1), idx(i, j + 1, 1), idx(i + 1, j + 1, 1), idx(i + 1, j, 1)))
        per = [(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)] + [(i, nv - 1) for i in range(nu - 2, -1, -1)] + \
              [(0, j) for j in range(nv - 2, 0, -1)]
        for k in range(len(per)):
            (i0, j0), (i1, j1) = per[k], per[(k + 1) % len(per)]
            faces.append((idx(i0, j0), idx(i1, j1), idx(i1, j1, 1), idx(i0, j0, 1)))
        uu = np.tile((u * L)[:, None], (1, nv)); vv = v[None, :] * side_scale * hw[:, None]
        UV = np.stack([vv / TILE + self.rng.uniform(0, 1), uu / TILE + self.rng.uniform(0, 1)], -1).reshape(-1, 2)
        UV = np.concatenate([UV, UV])
        t = self.rng.uniform(.50, .56) if tone is None else tone          # armour: one finish, little variation
        rim = np.maximum(np.abs(v)[None, :] ** 6, smooth(.82, 1.0, u)[:, None]) * np.ones((nu, nv))
        c0 = np.array([t, t * .985, t * .965]); c1 = np.array([.98, .90, .76])          # the pale rim leans warm (bronze)
        Ct = c0[None, None, :] * (1 - rim[..., None] * .7) + c1[None, None, :] * rim[..., None] * .7
        Cb = np.ones((nu, nv, 3)) * c0 * .7
        Col = np.concatenate([Ct.reshape(-1, 3), Cb.reshape(-1, 3)])
        b = bone or self.bone_at(Cp[nu // 3])
        return self._store(name, V, faces, UV, Col, mat, b)

    # ------------------------------------------------------------------ a limb or a trunk covered in rows of plates
    def wrap(self, name, a, b, bone, around=4, rows=2, span=(-150, 150), face=(0, -1, 0), cover=.92, overlap=.32, lift=.003,
             tip=.006, ridge=.003, thick=.006, dark=(), point=1.0, peak=.35, mirror=True, reach=.30, stagger=.5, flip=False, n=(14, 7),
             skip=(), also=()):
        """Rows of plates round the axis a -> b, `around` plates in each row over the arc `span` (degrees about the
        axis, 0 = the direction `face`, positive turning toward +X on the left side), each row from a little before
        its start to past its end (`overlap`), roots toward a and tips toward b (flip: the other way). Each plate is
        as wide as `cover` of its share of the arc as it lies on the surface. dark: (row, k) pairs (or 'all') that are
        dark chitin. A gap between plates shows the body under them, as the sheet's do."""
        a = np.asarray(a, float); b = np.asarray(b, float)
        D = unit(b - a)
        F0 = np.asarray(face, float); F0 = unit(F0 - D * np.dot(F0, D))
        G0 = np.cross(D, F0)
        fn = self.subfield({bone, mirror_bone(bone)} | set(also) | {mirror_bone(x) for x in also})
        out = []
        for side in ((1, -1) if mirror else (1,)):
            sx = np.array([side, 1, 1], float)
            for r in range(rows):
                t0 = r / rows - overlap / rows * .5
                t1 = (r + 1) / rows + overlap / rows * .5
                if flip:
                    t0, t1 = 1 - t0, 1 - t1
                off = stagger * (r % 2) / around
                for k in range(around):
                    if (r, k) in skip:
                        continue
                    f = (k + .5 + off) / around if around > 1 else .5
                    ang = math.radians(span[0] + (span[1] - span[0]) * f)
                    dirv = F0 * math.cos(ang) + G0 * math.sin(ang)
                    p0 = a + (b - a) * max(min(t0, 1), 0)
                    p1 = a + (b - a) * max(min(t1, 1), 0)
                    mid = a + (b - a) * ((t0 + t1) / 2)
                    s0 = self.exit_point(p0, dirv, fn, reach); s1 = self.exit_point(p1, dirv, fn, reach)
                    sm = self.exit_point(mid, dirv, fn, reach)
                    if s0 is None or s1 is None or sm is None:
                        continue
                    rad = max(np.linalg.norm((sm - mid) - D * np.dot(sm - mid, D)), .01)
                    w = cover * rad * math.radians(abs(span[1] - span[0])) / around
                    isdark = dark == 'all' or (r, k) in dark
                    bn = bone if side == 1 else mirror_bone(bone)
                    out.append(self._blade(f'{name}{r}{k}{"" if side == 1 else "_R"}', s0 * sx, s1 * sx, w, bn, lift + .0035 * r, tip, 1.0, thick,
                                           ridge, peak, point, .6, n, 'dark' if isdark else 'armour', np.zeros(3), None, 0.0, fn))
        return out

    # ------------------------------------------------------------------ a solid shell piece (a helmet)
    def shell(self, name, bone, base_fn, lo, hi, off, thick, keep, mat_of, grooves=(), slits=(), h=.0011, target=12000, tone=.54):
        """A closed armour piece made as a shell `off` outside the surface base_fn, `thick` thick, kept where keep(P) < 0;
        cut into panels by grooves ((point, normal, width): a gap across the shell) and through by slits ((a, b, r):
        capsules, where what is under shows: the eyes). mat_of(P) -> 'armour' | 'dark' per face. Meshed on its own grid
        (Surface Nets), so its edges and grooves are as sharp as h."""
        lo = np.asarray(lo, F32); hi = np.asarray(hi, F32)

        def f(P):
            P = np.asarray(P, F32)
            d = np.abs(base_fn(P) - off - thick * .5) - thick * .5
            d = np.maximum(d, keep(P))
            for p0, nrm, wd in grooves:
                nn = unit(np.asarray(nrm, float)).astype(F32)
                d = np.maximum(d, -(np.abs((P - np.asarray(p0, F32)) @ nn) - wd * .5))
            for a, b, r in slits:
                d = np.maximum(d, -sdf.capsule(P, a, b, r))
            return d
        V, Q = sdf.mesh(f, lo, hi, h)
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(V)); me.vertices.foreach_set('co', np.asarray(V, F32).ravel())
        me.loops.add(len(Q) * 4); me.loops.foreach_set('vertex_index', np.asarray(Q, np.int32).ravel())
        me.polygons.add(len(Q))
        me.polygons.foreach_set('loop_start', np.arange(0, len(Q) * 4, 4, dtype=np.int32))
        me.polygons.foreach_set('loop_total', np.full(len(Q), 4, np.int32))
        me.update(calc_edges=True); me.validate(clean_customdata=False)
        o = K._obj(name, me, self.mats['armour'])
        o.data.materials.append(self.mats['dark'])
        bpy.context.view_layer.objects.active = o
        if len(o.data.polygons) > target:
            md = o.modifiers.new('dec', 'DECIMATE'); md.ratio = target / len(o.data.polygons)
            bpy.ops.object.modifier_apply(modifier=md.name)
        Vv = np.empty(len(o.data.vertices) * 3, F32); o.data.vertices.foreach_get('co', Vv); Vv = Vv.reshape(-1, 3)
        cen = np.array([p.center[:] for p in o.data.polygons], F32)
        o.data.polygons.foreach_set('material_index', np.array([0 if mat_of(c) == 'armour' else 1 for c in cen], np.int32))
        ul = o.data.uv_layers.new(name='UVMap')
        vi = np.empty(len(o.data.loops), np.int32); o.data.loops.foreach_get('vertex_index', vi)
        P = Vv[vi]
        ul.data.foreach_set('uv', np.stack([P[:, 0] + P[:, 1] * .7, P[:, 2] + P[:, 1] * .3], 1).ravel() / TILE)
        ca = o.data.color_attributes.new('Color', 'BYTE_COLOR', 'CORNER')
        rgba = np.ones((len(vi), 4), F32); rgba[:, :3] = np.array([tone, tone * .985, tone * .965])
        ca.data.foreach_set('color', rgba.ravel())
        K.harden(o, 40)
        vg = o.vertex_groups.new(name=bone); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
        self.items.setdefault((self.slot, 'armour'), []).append(o)
        self.count += 1
        return o

    # ------------------------------------------------------------------ claws, lights
    def claw(self, name, a, b, r, bone, up=(0, 0, 1), hook=.35, flat=.55, mirror=True, mat='claw', segs=12, ring=8):
        out = []
        for side in ((1, -1) if mirror else (1,)):
            sx = np.array([side, 1, 1], float)
            A = np.asarray(a, float) * sx; Bp = np.asarray(b, float) * sx; U = unit(np.asarray(up, float) * sx)
            L = float(np.linalg.norm(Bp - A)); D = unit(Bp - A)
            ctrl = (A + Bp) * .5 + U * L * hook * .5
            ts = np.linspace(0, 1, segs)
            Pth = ((1 - ts) ** 2)[:, None] * A + (2 * (1 - ts) * ts)[:, None] * ctrl + (ts ** 2)[:, None] * Bp
            T = unit(np.gradient(Pth, axis=0)); Sd = unit(np.cross(T, U)); Nn = unit(np.cross(Sd, T))
            rr = r * (1 - ts) ** .8
            V, faces, UV, Col = [], [], [], []
            for i in range(segs):
                for k in range(ring):
                    ang = 2 * math.pi * k / ring
                    V.append(Pth[i] + Sd[i] * math.cos(ang) * rr[i] * flat + Nn[i] * math.sin(ang) * rr[i])
                    UV.append((k / ring * .03 / TILE, ts[i] * L / TILE))
                    Col.append([.9, .88, .84] if i < segs - 3 else [1.0, .96, .9])
            for i in range(segs - 1):
                for k in range(ring):
                    k1 = (k + 1) % ring
                    faces.append((i * ring + k, i * ring + k1, (i + 1) * ring + k1, (i + 1) * ring + k))
            faces.append(tuple(range(ring - 1, -1, -1)))
            bn = bone if side == 1 else mirror_bone(bone)
            out.append(self._store(f'{name}{"" if side == 1 else "_R"}', np.array(V), faces, UV, Col, mat, bn))
        return out

    def light(self, name, pts, width, bone=None, mirror=True, lift=.0012, mat='glow'):
        """a thin strip of light over the surface through pts"""
        out = []
        for side in ((1, -1) if mirror else (1,)):
            sx = np.array([side, 1, 1], float)
            P = np.asarray(pts, float) * sx
            Pp = self.project(P); Nn = self.normal(Pp)
            T = unit(np.gradient(Pp, axis=0)) if len(Pp) > 1 else np.array([[0, 0, 1.0]])
            Sd = unit(np.cross(Nn, T))
            V = np.concatenate([Pp + Nn * lift - Sd * width * .5, Pp + Nn * lift + Sd * width * .5, Pp + Nn * (lift - .0012)])
            n = len(Pp)
            faces = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
            faces += [(2 * n + i, 2 * n + i + 1, i + 1, i) for i in range(n - 1)] + [(n + i, n + i + 1, 2 * n + i + 1, 2 * n + i) for i in range(n - 1)]
            UV = np.zeros((len(V), 2)); Col = np.ones((len(V), 3))
            bn = (bone if side == 1 else mirror_bone(bone)) if bone else self.bone_at(Pp[len(Pp) // 2])
            out.append(self._store(f'{name}{"" if side == 1 else "_R"}', V, faces, UV, Col, mat, bn))
        return out

    def stud(self, name, p, r, bone=None, mirror=True, mat='glow'):
        out = []
        for side in ((1, -1) if mirror else (1,)):
            P = self.project([np.asarray(p, float) * np.array([side, 1, 1])])[0]
            Nn = self.normal([P])[0]
            bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r)
            me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
            V = np.array([v.co[:] for v in me.vertices]) * np.array([1, 1, .45])
            Z = Nn; X = unit(np.cross(Z, [0, 0, 1] if abs(Z[2]) < .9 else [1, 0, 0])); Y = np.cross(Z, X)
            V = P + Nn * r * .2 + V[:, :1] * X + V[:, 1:2] * Y + V[:, 2:3] * Z
            faces = [tuple(p_.vertices) for p_ in me.polygons]
            bpy.data.meshes.remove(me)
            bn = (bone if side == 1 else mirror_bone(bone)) if bone else self.bone_at(P)
            out.append(self._store(f'{name}{"" if side == 1 else "_R"}', V, faces, np.zeros((len(V), 2)), np.ones((len(V), 3)), mat, bn))
        return out

    def join(self, prefix):
        """one part per SLOT (its materials kept; the vertex groups carry each plate's bone): <prefix>_<slot>"""
        res = {}
        for slot in sorted({k[0] for k in self.items}):
            objs = [o for (sl, _), oo in self.items.items() if sl == slot for o in oo]
            bpy.ops.object.select_all(action='DESELECT')
            for o in objs:
                o.select_set(True)
            bpy.context.view_layer.objects.active = objs[0]
            bpy.ops.object.join()
            o = bpy.context.view_layer.objects.active
            o.name = f'{prefix}_{slot}'
            res[slot] = o
        return res
