"""Hair styles and clothing for the player base bodies, modelled as signed-distance shells around the body field.

Each item becomes C_<slot>__<item> (hair: C_hair__<style>) skinned with the same analytic weights as the body, so
cloth and skin move together. Item metadata (label, body regions it hides) goes into the armature's `worldex` extra.
Material names are an API for runtime tinting: cloth_<slot>, armor_primary__<slot>, armor_secondary__<slot>, trim_<slot>,
glow, visor, hair (strand cards), hair__cap (scalp cap); hair itself is grown by hair.py.
The default female set follows the owner's circuit-coat reference, the male set the vanguard plate reference.
"""
import bpy, math, os
import numpy as np
import bl, sdf, anatomy
import players as PL
from sdf import smin, smax, sphere, ellipsoid, capsule, round_cone, round_box, smoothstep, length, Loft

F32 = np.float32


def slab(v, c, w):
    """|v - c| <= w  (negative inside)."""
    return np.abs(v - c) - w


class Kit:
    def __init__(self, pb):
        self.pb, self.B, self.F = pb, pb.B, pb.F
        self.m = pb.B.m; self.sex = pb.sex
        self.items = {}
        self.res = .0032 if PL.FAST else .0021
        self.head_res = .0026 if PL.FAST else .0013
        self.hair_tris = {}

    # ------------------------------------------------------------ field helpers
    def parts(self, P):
        return self.F.parts(P)

    def dom(self, P, keep, p=None):
        """Negative where one of the `keep` parts is the closest part."""
        p = p or self.parts(P)
        a = np.min(np.stack([p[k] for k in keep]), 0)
        others = [k for k in p if k not in keep]
        b = np.min(np.stack([p[k] for k in others]), 0)
        return a - b

    def arm_s(self, P):
        """Arc length along the arm chain (both sides via |x|) and the wrist position on it."""
        B = self.B
        Q = P.copy(); Q[:, 0] = np.abs(Q[:, 0])
        s = PL.chain_param(Q, [B.shoulder, B.elbow, B.wrist, B.tip])
        lw = float(np.linalg.norm(B.elbow - B.shoulder) + np.linalg.norm(B.wrist - B.elbow))
        return s, lw

    def xfer(self, cover=('torso', 'armL', 'armR', 'legL', 'legR'), hands=False):
        """Garment weights copied from the body: each vertex is projected onto the surface of the parts the garment covers
        and takes the body's weights there, so cloth and skin deform identically and never pick up a bone of a part
        they merely hang next to (a skirt beside the hand, a hem beside the wrist)."""
        def w(V):
            fn = lambda P: np.min(np.stack([self.F.parts(P)[k] for k in cover]), 0)
            Vb = sdf.project(fn, V, 4, max_step=.03)
            return self.pb.skinner(Vb, cover=cover, hands=hands)
        return w

    def head_local(self, P):
        return P - self.B.head_o

    def hairline(self, L):
        """Negative on the scalp (above the hairline), head-local coordinates."""
        s = self.B.head.s
        th = np.arctan2(np.abs(L[:, 0]), -L[:, 1])            # 0 front .. pi back
        zl = np.interp(th, [0, .6, 1.05, 1.45, 1.75, 2.2, 3.15], [.074, .068, .05, .03, .012, -.035, -.058]) * s
        return zl - L[:, 2]

    # ------------------------------------------------------------ mesh one item
    def build(self, name, fn, lo, hi, mats, matfn=None, target=9000, h=None, uv=.22, weights=None, nfn=None,
              cover=('torso', 'armL', 'armR', 'legL', 'legR'), hands=False):
        h = h or self.res
        PL.log('item', name)
        V, Q = sdf.mesh(fn, lo, hi, h, log=PL.log)
        if not len(Q):
            PL.log('  (empty)', name); return None
        o = PL.to_object(name, V, Q)
        for m in mats:
            o.data.materials.append(m)
        PL.decimate_to(o, target)
        V = sdf.project(fn, PL.verts(o), 2, max_step=h * .5); PL.set_verts(o, V)
        if matfn is not None and len(mats) > 1:
            n, vi = PL.faces(o)
            starts = np.concatenate([[0], np.cumsum(n)[:-1]])
            C = (np.add.reduceat(V[vi], starts, axis=0) / n[:, None]).astype(F32)
            o.data.polygons.foreach_set('material_index', np.asarray(matfn(C), np.int32))
        bl.uv_box(o, uv)
        PL.set_normals(o, nfn or fn)
        V = PL.verts(o)
        W = weights(V) if weights else self.xfer(cover, hands)(V)
        PL.apply_weights(o, W)
        PL.log('  ->', name, len(o.data.vertices), 'verts')
        return o

    def add(self, slot, item, label, objs, hide=(), extra=None):
        objs = [o for o in objs if o is not None]
        o = bl.join(objs, 'C_%s__%s' % (slot, item)) if len(objs) > 1 else objs[0]
        o.name = 'C_%s__%s' % (slot, item)
        d = {'label': label, 'hide': list(hide)}
        if extra:
            d.update(extra)
        self.items.setdefault(slot, {})[item] = d
        return o

    # ------------------------------------------------------------ textures
    @staticmethod
    def circuit_texture():
        """Tileable navy fabric with gold circuit traces and pads (the owner's coat reference)."""
        N = 512; rng = np.random.default_rng(21)
        img = np.zeros((N, N, 3), F32)
        base = np.array([.07, .1, .2]); img[:] = base
        yy, xx = np.mgrid[0:N, 0:N]
        img *= (1 + .06 * np.sin(xx * .9) * np.sin(yy * .9))[..., None]          # weave
        gold = np.array([.78, .6, .28])
        grid = 16
        for _ in range(70):
            x, y = rng.integers(0, N // grid, 2) * grid
            for seg in range(rng.integers(3, 8)):
                d = rng.integers(0, 4); L = rng.integers(2, 7) * grid
                dx, dy = [(1, 0), (0, 1), (1, 1), (1, -1)][d]
                for t in range(L):
                    px, py = (x + dx * t) % N, (y + dy * t) % N
                    img[py, px] = gold; img[(py + 1) % N, px] = gold * .8; img[py, (px + 1) % N] = gold * .8
                x, y = (x + dx * L) % N, (y + dy * L) % N
            r = 4
            img[np.maximum(np.abs(yy - y), np.abs(xx - x)) <= r] = gold
            img[np.maximum(np.abs(yy - y), np.abs(xx - x)) <= r - 2] = base * 1.4
        im = bpy.data.images.new('circuit_navy', N, N)
        px = np.ones((N, N, 4), F32); px[..., :3] = np.clip(img, 0, 1)
        im.pixels = px[::-1].ravel()
        sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
        im.save_render(os.path.join(bl.TEXTURES, 'circuit_navy.jpg'))

    # ------------------------------------------------------------ materials
    def mats(self):
        M = {}
        M['glow'] = bl.mat('glow', '#1ad8ff' if not self.m else '#ffae2f', 0, .4, emit='#1ad8ff' if not self.m else '#ffae2f', strength=4)
        return M

    # ====================================================================== hair
    def hair_weights(self, tail_from=None):
        """Head for the scalp; long hair hanging behind the neck blends to neck/chest."""
        B = self.B

        def w(V):
            z = V[:, 2]
            zt = B.head_o[2] - .06 * B.head.s
            t = np.clip((zt - z) / .25, 0, 1)
            head = 1 - t
            neck = t * (1 - t) * 2 * .6
            chest = np.clip(1 - head - neck, 0, 1)
            return {'head': head, 'neck': neck, 'chest': chest}
        return w

    def strand_colors(self, o, phase_fn, base=.86, depth=.22):
        V = PL.verts(o)
        ph = phase_fn(V)
        c = base - depth * (.5 + .5 * np.cos(ph)) ** 2
        rng = np.random.default_rng(3)
        c = c * (1 + rng.normal(0, .02, len(c)))
        PL.set_colors(o, np.stack([c, c, c], 1))

    def scalp(self, t_fn, groove_phase=None, amp=.0007, extra=None, mask=None):
        B = self.B; H = B.head

        def fn(P):
            L = P - B.head_o
            d = H(L) - t_fn(L)
            if groove_phase is not None:
                d = d - amp * np.cos(groove_phase(L))
            d = np.maximum(d, mask(L) if mask else self.hairline(L))
            # never inside the face/ears region in front
            if extra is not None:
                d = np.minimum(d, extra(P))
            return d
        return fn

    # ====================================================================== female circuit set
    def female_set(self, M):
        B, F = self.B, self.F
        z = B.z
        tex = lambda name, img, col='#ffffff', metal=0.0, rough=.7: bl.mat(name, col, metal, rough, image=img)
        zcol = float(B.head_o[2] - .105 * B.head.s - .016)
        # ---- top: ribbed sleeveless high-neck
        def top(P):
            p = self.parts(P)
            reg = np.maximum(self.dom(P, ['torso'], p), np.maximum(.975 - P[:, 2], P[:, 2] - zcol))
            return np.maximum(F(P) - .0025, reg)
        t = self.build('top', top, (-.22, -.17, .95), (.22, .17, zcol + .01), [tex('cloth_top', 'char_ribbed_white.jpg', '#f2f0ea', 0, .8)],
                       target=7000, uv=.12, cover=('torso', 'armL', 'armR'))
        self.add('top', 'ribbed', 'Ribbed high-neck top', [t], hide=['midriff'])
        # ---- legs: ribbed leggings + knee pads + greaves
        def legs(P):
            p = self.parts(P)
            reg = np.maximum(self.dom(P, ['torso', 'legL', 'legR'], p), np.maximum(P[:, 2] - 1.0, .1 - P[:, 2]))
            return np.maximum(F(P) - .0045, reg)
        lg = self.build('legs', legs, (-.22, -.17, .09), (.22, .19, 1.01), [tex('cloth_legs', 'char_ribbed_white.jpg', '#eceae4', 0, .8)],
                        target=8000, uv=.12, cover=('torso', 'legL', 'legR'))
        kn = B.knee

        def armour(P):
            Q = P.copy(); Q[:, 0] = np.abs(Q[:, 0])
            pad = np.maximum(F(P) - .012, ellipsoid(Q, kn + np.array([0, -.035, .012]), (.055, .05, .07)))
            gre = np.maximum(F(P) - .008, np.maximum.reduce([Q[:, 2] - (kn[2] - .075), (B.ankle[2] + .07) - Q[:, 2],
                                                             Q[:, 1] - (kn[1] - .005), np.abs(Q[:, 0] - kn[0]) - .05]))
            return np.minimum(pad, gre)

        def armour_mat(C):
            Q = np.abs(C[:, 0]); z_ = C[:, 2]
            g = (np.abs(z_ - (kn[2] + .012)) < .005) | ((np.abs(Q - kn[0]) < .006) & (z_ < kn[2] - .1) & (z_ > B.ankle[2] + .1))
            return np.where(g, 1, 0)
        ar = self.build('legs_armour', armour, (-.2, -.15, .1), (.2, .1, kn[2] + .1),
                        [tex('trim_legs', 'char_kneepad.jpg', '#ffffff', .5, .45), M['glow']], armour_mat, target=5000, uv=.1, cover=('legL', 'legR'))
        self.add('legs', 'leggings', 'Ribbed leggings & knee guards', [lg, ar], hide=['thigh', 'shin', 'pelvis'])
        # ---- outer: sleeveless circuit coat with stand collar
        hem = kn[2] + .02

        def front_cut(P, wz):
            return np.where(P[:, 1] < -.01, wz - np.abs(P[:, 0]), -1.0)

        skirt_loft = Loft((0, 0, hem - .02), (0, 0, 1.06), dict(t=[0, .3, .6, .85, 1], rv_pos=[.2, .192, .186, .158, .137],
                                                                  rw_pos=[.135, .13, .124, .106, .09], rw_neg=[.15, .145, .136, .1, .078],
                                                                  cw=[0, 0, 0, 0, .0], n=[2.1, 2.1, 2.2, 2.3, 2.3]), v_axis=(-1, 0, 0), cap=.2)

        def coat(P):
            p = self.parts(P)
            zz = P[:, 2]
            up = np.maximum(F(P) - .0075, np.maximum(self.dom(P, ['torso'], p), np.maximum(.97 - zz, zz - (B.zsh + .07))))
            up = np.maximum(up, front_cut(P, .045))
            nr = np.sqrt(P[:, 0] ** 2 + (P[:, 1] - .004) ** 2)
            up = np.maximum(up, .072 - nr)
            # collar ring
            col = np.maximum(np.abs(nr - .062) - .004, np.maximum(z['neck'] - .02 - zz, zz - (z['neck'] + .06)))
            col = np.maximum(col, front_cut(P, .03))
            sk = np.abs(skirt_loft(P)) - .004
            sk = np.maximum(sk, np.maximum(hem - zz, zz - 1.045))
            sk = np.maximum(sk, front_cut(P, .04 + (1.0 - zz) * .16))
            slit = np.maximum(np.abs(P[:, 1] - .005) - .012, np.maximum(zz - .68, .16 - np.abs(P[:, 0])))
            sk = np.maximum(sk, -slit)
            return np.minimum(np.minimum(up, sk), col)

        def coat_mat(C):
            zz = C[:, 2]
            ax = np.abs(C[:, 0])
            wz = np.where(zz > .97, .045, .04 + (1.0 - zz) * .16)
            edge = (C[:, 1] < -.01) & (np.abs(ax - wz) < .012)
            edge |= zz < hem + .018
            edge |= (zz > z['neck'] + .045) & (zz < z['neck'] + .07)
            return np.where(edge, 1, 0)

        def coat_w(V):
            W = self.xfer(('torso', 'legL', 'legR'))(V)
            zz = V[:, 2]
            t = np.clip((B.hip[2] - .02 - zz) / .35, 0, 1)
            if t.any():
                for b in list(W):
                    W[b] = W[b] * (1 - t)
                side = smoothstep(-.06, .06, V[:, 0])
                W['hips'] = W.get('hips', 0) + t * .6
                W['thigh.L'] = W.get('thigh.L', 0) + t * .4 * side
                W['thigh.R'] = W.get('thigh.R', 0) + t * .4 * (1 - side)
            return W
        ct = self.build('coat', coat, (-.27, -.2, hem - .03), (.27, .22, z['neck'] + .08),
                        [tex('cloth_outer', 'circuit_navy.jpg', '#ffffff', .1, .55), bl.mat('trim_outer', '#c9a24a', .9, .3)],
                        coat_mat, target=10000, uv=.3, weights=coat_w)
        self.add('outer', 'circuit_coat', 'Circuit coat', [ct])
        # ---- vest: olive harness with chest panel and buckles
        def harness(P):
            zz = P[:, 2]; ax = np.abs(P[:, 0])
            p = self.parts(P)
            straps = np.minimum.reduce([np.maximum(slab(ax, .085, .016), 1.12 - zz), slab(zz, 1.165, .014), slab(zz, 1.035, .018)])
            body = np.maximum(F(P) - .0125, np.maximum(straps, self.dom(P, ['torso'], p)))
            panel = round_box(P, (0, -.098, 1.235), (.05, .012, .04), .006)
            buckles = np.minimum.reduce([round_box(P, (0, -.092, 1.035), (.022, .01, .016), .003),
                                         round_box(P * [1, 1, 1], (.085, -.095, 1.165), (.016, .01, .014), .003),
                                         round_box(P, (-.085, -.095, 1.165), (.016, .01, .014), .003)])
            return np.minimum(np.minimum(body, panel), buckles)

        def harness_mat(C):
            panel = (np.abs(C[:, 0]) < .052) & (np.abs(C[:, 2] - 1.235) < .042) & (C[:, 1] < -.09)
            buck = ((np.abs(C[:, 2] - 1.035) < .018) & (np.abs(C[:, 0]) < .024) & (C[:, 1] < -.085)) | \
                   ((np.abs(C[:, 2] - 1.165) < .016) & (np.abs(np.abs(C[:, 0]) - .085) < .018) & (C[:, 1] < -.085))
            return np.where(panel, 2, np.where(buck, 1, 0))
        hv = self.build('harness', harness, (-.2, -.15, 1.0), (.2, .15, B.zsh + .08),
                        [tex('cloth_vest', 'char_harness_olive.jpg', '#9a9a62', 0, .75), bl.mat('trim_vest', '#7d838c', .9, .3),
                         tex('armor_secondary__vest', 'char_chest_sparkle.jpg', '#ffffff', .3, .35)], harness_mat, target=7000, uv=.15, cover=('torso',))
        self.add('vest', 'harness', 'Tactical harness', [hv])
        # ---- hands: armoured gauntlets + fingerless gloves
        self.gauntlets(M, tex)
        # ---- feet: tech boots
        self.boots(M, tex, 'tech', 'Tech boots', 'char_boot_tech.jpg', .245, .0055, .009, strap='char_harness_olive.jpg')

    def gauntlets(self, M, tex, full_glove=False, label='Armoured gauntlets', item='gauntlets', img='char_gauntlet_dark.jpg'):
        B, F = self.B, self.F

        def fn(P):
            p = self.parts(P)
            s, lw = self.arm_s(P)
            armdom = self.dom(P, ['armL', 'armR'], p)
            g1 = np.maximum(F(P) - .008, np.maximum(armdom, np.maximum((lw - .13) - s, s - (lw + .006))))
            if full_glove:
                g2 = np.maximum(F(P) - .0018, np.maximum(armdom, (lw - .02) - s))
            else:
                g2 = np.maximum(F(P) - .0018, np.maximum(armdom, np.maximum((lw - .01) - s, s - (lw + .085))))
            return np.minimum(g1, g2)

        def mat(C):
            s, lw = self.arm_s(C)
            ax = np.abs(C[:, 0])
            g = (np.abs(s - (lw - .07)) < .028) & (ax > np.interp(s, [0, lw], [B.shoulder[0], B.wrist[0]]) + .012)
            return np.where(g, 1, 0)
        lo = (-B.tip[0] - .07, -.12, B.tip[2] - .03); hi = (B.tip[0] + .07, .12, B.wrist[2] + .17)
        o = self.build(item, fn, lo, hi, [tex('cloth_hands', img, '#ffffff', .35, .5), M['glow']], mat, target=9000, uv=.08,
                       h=self.res * .7, cover=('armL', 'armR'), hands=True)
        self.add('hands', item, label, [o], hide=['hand'] if full_glove else [])

    def boots(self, M, tex, item, label, img, top_z, off, sole, strap=None):
        B, F = self.B, self.F

        def fn(P):
            p = self.parts(P)
            legdom = self.dom(P, ['legL', 'legR'], p)
            up = np.maximum(F(P) - off, np.maximum(legdom, P[:, 2] - top_z))
            so = np.maximum(F(P) - sole, np.maximum(legdom, P[:, 2] - .02))
            d = smin(up, so, .004)
            if strap:
                st = np.maximum(F(P) - off - .003, np.maximum(legdom, slab(P[:, 2], .115, .014)))
                d = np.minimum(d, st)
            return d

        def mat(C):
            zz = C[:, 2]
            out = np.zeros(len(C), np.int32)
            out[(zz > .01) & (zz < .02)] = 1
            if strap:
                out[np.abs(zz - .115) < .013] = 2
            return out
        A = B.ankle
        lo = (-A[0] - .09, A[1] - .28, -.015); hi = (A[0] + .09, A[1] + .09, top_z + .01)
        mats = [tex('cloth_feet', img, '#ffffff', .2, .55), M['glow']]
        if strap:
            mats.append(tex('trim_feet', strap, '#9a9a62', 0, .75))
        o = self.build('boots', fn, lo, hi, mats, mat, target=8000, uv=.1, cover=('legL', 'legR'))
        self.add('feet', item, label, [o], hide=['foot'])

    # ====================================================================== male vanguard set
    def male_set(self, M):
        B, F = self.B, self.F
        z = B.z
        tex = lambda name, img, col='#ffffff', metal=0.0, rough=.7: bl.mat(name, col, metal, rough, image=img)
        zcol = float(B.head_o[2] - .105 * B.head.s - .016)
        # ---- top: black undersuit, long sleeves, turtleneck
        def top(P):
            p = self.parts(P)
            s, lw = self.arm_s(P)
            reg = np.maximum(self.dom(P, ['torso', 'armL', 'armR'], p), np.maximum(1.0 - P[:, 2], P[:, 2] - zcol))
            reg = np.maximum(reg, np.where(self.dom(P, ['armL', 'armR'], p) < 0, s - (lw - .004), -1))
            return np.maximum(F(P) - .002, reg)
        t = self.build('top', top, (-.34, -.18, .9), (.34, .18, zcol + .01), [tex('cloth_top', 'char_undersuit_black.jpg', '#ffffff', 0, .7)],
                       target=10000, uv=.1, cover=('torso', 'armL', 'armR'))
        self.add('top', 'undersuit', 'Tactical undersuit', [t], hide=['chest', 'midriff', 'upperarm', 'forearm', 'neck'])
        # ---- vest: vanguard plate (chest, back, abdomen bands, layered pauldrons, collar, core light)
        steel = tex('armor_primary__vest', 'char_plate_steel.jpg', '#6f7f98', .7, .34)
        bronze = bl.mat('armor_secondary__vest', '#a8683c', 1.0, .35)
        zsh = B.zsh

        def plate(P):
            p = self.parts(P)
            zz = P[:, 2]; ax = np.abs(P[:, 0])
            tor = self.dom(P, ['torso'], p)
            f = F(P)
            chest = np.maximum(f - .016, np.maximum(tor, np.maximum(1.15 - zz, zz - (zsh + .05))))
            nr = np.sqrt(P[:, 0] ** 2 + (P[:, 1] - .004) ** 2)
            chest = np.maximum(chest, .07 - nr)                         # neck opening
            # panel grooves: sternum line + under-pec line
            chest = smax(chest, -np.maximum(slab(P[:, 0], 0, .0025), P[:, 1] + .05), .002)
            chest = smax(chest, -np.maximum(slab(zz, 1.27, .0025), P[:, 1] + .05), .002)
            ab = np.full(len(P), 1.0, F32)
            for i in range(3):
                zc = 1.005 + i * .047
                ab = np.minimum(ab, np.maximum(f - .011, np.maximum.reduce([tor, slab(zz, zc, .019), P[:, 1] + .02, ax - .13])))
            s, lw = self.arm_s(P)
            armdom = self.dom(P, ['armL', 'armR'], p)
            sh = np.full(len(P), 1.0, F32)
            for off, s1 in ((.022, .13), (.031, .085), (.04, .045)):
                sh = np.minimum(sh, np.maximum(f - off, np.maximum.reduce([s - s1, zsh - .2 - zz,
                                                                         np.where(armdom < .02, -1, armdom - .02)])))
            col = np.maximum(np.abs(nr - .072) - .007, slab(zz, z['neck'] + .02, .022))
            core = capsule(P, (0, -.122, 1.3), (0, -.122, 1.37), .012)
            return np.minimum.reduce([chest, ab, sh, col, core])

        def plate_mat(C):
            zz = C[:, 2]; ax = np.abs(C[:, 0])
            core = (ax < .016) & (np.abs(zz - 1.335) < .05) & (C[:, 1] < -.105)
            nr = np.sqrt(C[:, 0] ** 2 + (C[:, 1] - .004) ** 2)
            trim = (nr < .085) & (zz > z['neck'] - .01)
            s, lw = self.arm_s(C)
            trim |= (ax > B.sx) & (np.abs(s - .085) < .012)
            trim |= (np.abs(zz - 1.15) < .012) & (C[:, 1] < 0)
            return np.where(core, 2, np.where(trim, 1, 0))
        pv = self.build('plate', plate, (-.33, -.2, .97), (.33, .2, z['neck'] + .05), [steel, bronze, M['glow']], plate_mat,
                        target=12000, uv=.25, cover=('torso', 'armL', 'armR'))
        self.add('vest', 'vanguard', 'Vanguard plate', [pv])
        # ---- hands: tactical gloves (full)
        self.gauntlets(M, tex, full_glove=True, label='Tactical gloves', item='gloves', img='char_glove_black.jpg')
        # ---- legs: armoured trousers
        def legs(P):
            p = self.parts(P)
            reg = np.maximum(self.dom(P, ['torso', 'legL', 'legR'], p), np.maximum(P[:, 2] - 1.02, .11 - P[:, 2]))
            base = np.maximum(F(P) - .0045, reg)
            Q = P.copy(); Q[:, 0] = np.abs(Q[:, 0])
            kn = B.knee
            th = np.maximum(F(P) - .012, np.maximum.reduce([self.dom(P, ['legL', 'legR'], p), slab(Q[:, 2], (B.hip[2] + kn[2]) / 2 + .02, .13),
                                                         Q[:, 1] - (kn[1] - .02)]))
            pad = np.maximum(F(P) - .014, ellipsoid(Q, kn + np.array([0, -.04, .01]), (.05, .05, .06)))
            belt = np.maximum(F(P) - .01, np.maximum(self.dom(P, ['torso'], p), slab(P[:, 2], .99, .022)))
            return np.minimum.reduce([base, th, pad, belt])

        def legs_mat(C):
            Q = np.abs(C[:, 0]); kn = B.knee
            f = self.F(C)
            plate = f > .0085
            belt = np.abs(C[:, 2] - .99) < .023
            return np.where(belt & plate, 2, np.where(plate, 1, 0))
        lg = self.build('legs', legs, (-.24, -.18, .1), (.24, .2, 1.03),
                        [tex('cloth_legs', 'char_undersuit_black.jpg', '#5a5e66', 0, .75), steel, bl.mat('trim_legs', '#2a2c30', .4, .5)],
                        legs_mat, target=11000, uv=.12, cover=('torso', 'legL', 'legR'))
        self.add('legs', 'armoured', 'Armoured trousers', [lg], hide=['pelvis', 'thigh', 'shin'])
        # ---- feet: combat boots
        self.boots(M, tex, 'combat', 'Combat boots', 'char_boot_black.jpg', .27, .007, .011)
        # ---- head: pioneer helmet (closed, visor)
        H = B.head; s = H.s; ho = B.head_o

        def helm(P):
            L = P - ho
            d = H.base()(L) - .02 * s
            d = smin(d, capsule(L, np.array([0, -.06, .1]) * s, np.array([0, .1, .09]) * s, .012 * s), .01 * s)   # crest
            for sx in (1, -1):
                d = smin(d, sdf.round_box(L, np.array([sx * .085, .005, .0]) * s, np.array([.012, .03, .035]) * s, .008 * s), .006 * s)
            return np.maximum(d, -.13 * s - L[:, 2])

        def helm_mat(C):
            L = C - ho
            visor = (L[:, 1] < -.03 * s) & (np.abs(L[:, 2] - .008 * s) < .022 * s) & (np.abs(L[:, 0]) < .066 * s)
            trim = (np.abs(L[:, 0]) < .014 * s) & (L[:, 2] > .07 * s)
            trim |= (np.abs(np.abs(L[:, 0]) - .09 * s) < .012 * s)
            return np.where(visor, 2, np.where(trim, 1, 0))
        visor = bl.mat('visor', '#0c1418', .9, .06, emit='#ffae2f', strength=.35)
        hm = self.build('helmet', helm, ho + np.array([-.13, -.14, -.15]) * s, ho + np.array([.13, .14, .16]) * s,
                        [tex('armor_primary__head', 'char_plate_steel.jpg', '#6f7f98', .7, .3),
                         bl.mat('armor_secondary__head', '#a8683c', 1.0, .35), visor], helm_mat, h=self.head_res * 1.4, target=9000,
                        weights=lambda V: {'head': np.ones(len(V), F32)})
        self.add('head', 'pioneer', 'Pioneer helmet', [hm], hide=['head', 'eyes', 'brows', 'lashes'], extra={'hideHair': True})

    # ====================================================================== underwear (always worn)
    def underwear(self, M):
        """Non-removable base layer: the game never shows the body naked. Hidden while clothing covers it."""
        B, F = self.B, self.F
        zc = B.z['crotch']
        top_z = B.hip[2] + (.06 if not self.m else .045)

        def briefs(P):
            p = self.parts(P)
            reg = np.maximum(self.dom(P, ['torso', 'legL', 'legR'], p), np.maximum(P[:, 2] - top_z, (zc - .045) - P[:, 2]))
            return np.maximum(F(P) - .0018, reg)
        col = '#2c2f36' if self.m else '#3a3440'
        o = self.build('briefs', briefs, (-.22, -.17, zc - .07), (.22, .19, top_z + .02),
                       [bl.mat('cloth_underbottom', col, 0, .7)], target=3500, uv=.1, cover=('torso', 'legL', 'legR'))
        self.add('underbottom', 'base', 'Base layer', [o], extra={'locked': True, 'coveredBy': ['legs', 'dress']})
        if self.m:
            return
        zsh = B.zsh

        def bra(P):
            p = self.parts(P)
            zz = P[:, 2]; ax = np.abs(P[:, 0])
            band = np.maximum(zz - 1.268, 1.128 - zz)
            straps = np.maximum.reduce([np.abs(ax - .078) - .011, 1.24 - zz, zz - (zsh + .06)])
            reg = np.maximum(self.dom(P, ['torso'], p), np.minimum(band, straps))
            return np.maximum(F(P) - .0018, reg)
        o = self.build('bra', bra, (-.2, -.16, 1.1), (.2, .16, zsh + .08), [bl.mat('cloth_undertop', col, 0, .65)], target=3500, uv=.1, cover=('torso',))
        self.add('undertop', 'base', 'Base layer', [o], extra={'locked': True, 'coveredBy': ['top', 'dress']})

    # ====================================================================== run
    def run(self):
        import hair
        self.circuit_texture()
        hair.strand_texture()
        M = self.mats()
        self.underwear(M)
        g = hair.Groom(self)
        if self.m:
            hair.male_styles(g); self.male_set(M)
            defaults = {'underbottom': 'base', 'hair': 'sidepart', 'head': 'none', 'top': 'undersuit', 'vest': 'vanguard', 'outer': 'none', 'hands': 'gloves',
                        'legs': 'armoured', 'feet': 'combat'}
        else:
            hair.female_styles(g); self.female_set(M)
            defaults = {'undertop': 'base', 'underbottom': 'base', 'hair': 'ponytail', 'head': 'none', 'top': 'ribbed', 'vest': 'harness', 'outer': 'circuit_coat',
                        'hands': 'gauntlets', 'legs': 'leggings', 'feet': 'tech'}
        return {'items': self.items, 'defaults': defaults}


def vc_mat(m):
    b = m.node_tree.nodes['Principled BSDF']
    vc = m.node_tree.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Color'
    m.node_tree.links.new(vc.outputs['Color'], b.inputs['Base Color'])
