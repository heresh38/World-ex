"""Civilians for New Meridian: civ_female.glb / civ_male.glb.

Same body pipeline as the player characters, one subdivision level lighter, with a painted generic face so
the owner's characters stay unique. Each file holds several outfits (O_*) and hair styles (H_*); the game picks
a combination per pedestrian and tints materials by prefix: skin, hair, shirt, pants, shoes.
"""
import bpy, math, os, sys, json
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import bl, human, characters, npc_kit as hq


def painted_face(name, male):
    """Neutral light-skin face plate (tinted per pedestrian in-game) with eyes, brows, nose and lips."""
    S = 512
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    v = 1 - yy                                  # v up, like UVs
    base = np.array([.86, .72, .64]) if not male else np.array([.84, .69, .6])
    img = np.ones((S, S, 3), np.float32) * base
    def blob(cx, cy, rx, ry, col, a=1.0, soft=.25):
        d = ((xx - cx) / rx) ** 2 + ((v - cy) / ry) ** 2
        m = np.clip((1 - d) / soft, 0, 1)[..., None] * a
        img[:] = img * (1 - m) + np.array(col) * m
    uc, ue, ve, vc = hq.CALIB['female']
    vm, vn = .24, .36
    for sx in (-1, 1):
        ex = uc + sx * ue
        blob(ex, ve + .01, .055, .028, (.55, .38, .33), .5, .6)            # socket shade
        blob(ex, ve, .042, .018, (.93, .92, .9), 1, .35)                   # eye white
        blob(ex, ve, .017, .017, (.25, .17, .12), 1, .3)                   # iris
        blob(ex, ve, .008, .008, (.03, .03, .03), 1, .3)                   # pupil
        blob(ex, ve + .016, .046, .006, (.12, .09, .08), .9, .5)           # lash line
        bw = .012 if male else .007
        blob(ex + sx * .01, ve + .065, .055, bw, (.18, .13, .1), .85, .5)  # brow
    blob(uc, vn + .03, .02, .07, (.75, .58, .5), .35, .8)                  # nose bridge shade
    blob(uc, vn, .04, .018, (.6, .43, .38), .45, .6)                       # nostrils
    blob(uc, vm, .07, .022, (.72, .4, .38) if not male else (.62, .42, .38), .9, .5)   # lips
    blob(uc, vm - .002, .06, .003, (.35, .2, .18), .8, .5)
    if male:
        blob(uc, vc + .12, .26, .14, (.55, .45, .4), .35, .9)               # stubble shadow
    for sx in (-1, 1):
        blob(uc + sx * .2, vm + .08, .08, .06, (.9, .62, .55), .25, .9)    # cheeks
    # feather to the base so the head sides match
    e = ((xx - .5) / .46) ** 2 + ((yy - .51) / .49) ** 2
    m = np.clip((e - .62) / .38, 0, 1)[..., None]
    img = img * (1 - m) + base * m
    im = bpy.data.images.new(name, S, S)
    out = np.ones((S, S, 4), np.float32); out[..., :3] = np.clip(img, 0, 1)
    im.pixels = out[::-1].ravel()
    sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    im.save_render(os.path.join(bl.TEXTURES, name + '.jpg'))


def fabric(name, mode, color):
    S = 256
    rng = np.random.default_rng(len(name))
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    if mode == 'denim':
        tw = .5 + .5 * np.sin((xx + yy) / S * 2 * np.pi * 40)
        shade = .82 + .12 * tw + .06 * rng.random((S, S))
    elif mode == 'knit':
        shade = .86 + .1 * np.abs(np.sin((xx / S * 20 + np.abs(((yy / S * 40) % 2) - 1) * .5) * np.pi))
    elif mode == 'plaid':
        a = ((xx // 24) % 2) * .5 + ((yy // 24) % 2) * .5
        shade = .55 + .45 * a + .04 * rng.random((S, S))
    else:
        shade = .9 + .05 * np.sin(xx / S * 2 * np.pi * 60) * np.sin(yy / S * 2 * np.pi * 60) + .05 * rng.random((S, S))
    img = np.ones((S, S, 4), np.float32); img[..., :3] = np.array(color)[None, None] * shade[..., None]
    im = bpy.data.images.new(name, S, S); im.pixels = np.clip(img, 0, 1)[::-1].ravel()
    sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
    im.save_render(os.path.join(bl.TEXTURES, name + '.jpg'))


class CivBuilder(hq.Builder):
    def build_body(self):
        P, sex = self.P, self.sex
        self.skin = bl.mat('skin__body', '#d6b4a4', 0, .55)
        body = human.skin_body(P, 'body_full', levels=1)
        body.data.materials.append(self.skin)
        bl.uv_box(body, .3)
        self.rig.skin(body)
        self.body = body; self.surf = hq.Surface(body)
        hd = human.head(P, 'head')
        face = bl.mat('skin__face', '#ffffff', 0, .5, image='civ_face_%s.jpg' % sex)
        for nd in face.node_tree.nodes:
            if nd.type == 'TEX_IMAGE':
                nd.extension = 'EXTEND'
        hd.data.materials.append(face)
        self.hr = hd['head_r']; self.hcz = hd['head_cz']
        hq.calibrate_face_uv(hd, self.hr, self.hcz, 'female')
        self.rig.skin(hd, 'rigid', 'head'); self.head = hd

    def outfits(self):
        z, k, sh = self.z, self.k, self.P.shoulder
        f = self.sex == 'female'
        shirt = bl.mat('shirt__cotton', '#ffffff', 0, .85, image='fab_cotton.jpg', uv_scale=3)
        knit = bl.mat('shirt__knit', '#ffffff', 0, .9, image='fab_knit.jpg', uv_scale=3)
        plaid = bl.mat('shirt__plaid', '#ffffff', 0, .85, image='fab_plaid.jpg', uv_scale=2)
        jeans = bl.mat('pants__denim', '#ffffff', 0, .85, image='fab_denim.jpg', uv_scale=3)
        cloth = bl.mat('pants__cloth', '#ffffff', 0, .85, image='fab_cotton.jpg', uv_scale=3)
        shoes = bl.mat('shoes__leather', '#ffffff', .1, .5)
        out = {}
        tee = lambda: hq.shell(self.body, 'tee', shirt, (lambda c, n: self.P_(bones=('spine', 'chest', 'upperarm', 'neck'), zmin=z['navel'] - .04, zmax=z['neck'] + .005)(c, n)
                                                             and not (abs(c.x) > sh and c.z < self.J['upperarm.L'][0].z - .12)), .006, uv=.3)
        def longtop(m, name):
            torso = self.P_(bones=('spine', 'chest', 'neck'), zmin=z['navel'] - .06, zmax=z['neck'] + .005)
            arms = self.P_(bones=('upperarm', 'forearm'))
            return hq.shell(self.body, name, m, lambda c, n: torso(c, n) or arms(c, n), .01, uv=.3)
        trousers = lambda m, off=.008: hq.shell(self.body, 'pants', m, self.P_(bones=('hips', 'thigh', 'shin'), zmin=z['ankle'] + .05), off, uv=.3)
        def shoe_parts():
            return self.boots('civ', shoes, z['ankle'] + .04, sole_col='#222222')
        out['tee_jeans'] = (self.finish_outfit('tee_jeans', [tee(), trousers(jeans)] + shoe_parts()), ['pelvis', 'thigh', 'foot'])
        out['hoodie'] = (self.finish_outfit('hoodie', [longtop(knit, 'hoodie'), trousers(cloth, .012),
                                                       hq.tube('hood', [Vector((0, .09 * k, z['neck'] + .01)), Vector((0, .1 * k, z['neck'] + .05))], [.08 * k, .075 * k], knit, 14)] + shoe_parts()),
                         ['pelvis', 'thigh', 'foot', 'forearm'])
        # farm: plaid shirt + overall bib
        bib = hq.shell(self.body, 'bib', jeans, self.P_(bones=('spine', 'chest'), zmin=z['navel'] - .05, zmax=z['chest'] + .02, xmax=.11 * k, front=True), .016, uv=.3)
        straps = []
        for sx in (1, -1):
            P_, N_ = self.surf.line([(sx * .07 * k, zz) for zz in np.linspace(z['shoulder'] - .01, z['chest'] + .02, 8)], -1)
            if len(P_) > 2:
                straps.append(hq.ribbon('strap', P_, N_, .03 * k, jeans, lift=.015))
        out['farm'] = (self.finish_outfit('farm', [longtop(plaid, 'plaid'), trousers(jeans, .014), bib] + straps + self.boots('farm', shoes, z['ankle'] + .12 * k, sole_col='#2a1d14')),
                       ['pelvis', 'thigh', 'foot', 'forearm'])
        if f:
            # summer dress: fitted top + flared skirt to the knee
            top = hq.shell(self.body, 'dtop', shirt, self.P_(bones=('spine', 'chest'), zmin=z['waist'] - .02, zmax=z['armpit'] + .04), .006, uv=.3)
            verts = [self.body.matrix_world @ v.co for v in self.body.data.vertices]
            secs = []
            for i, zz in enumerate(np.linspace(z['waist'], z['knee'] + .05, 6)):
                band = [v for v in verts if abs(v.z - zz) < .03 and abs(v.x) < .15]
                rx = max(abs(v.x) for v in band) + .015 + i * .012; ry = (max(v.y for v in band) - min(v.y for v in band)) / 2 + .02 + i * .01
                if secs:
                    rx = max(rx, max(abs(p.x) for p in secs[-1]) + .008); ry = max(ry, max(-p.y for p in secs[-1]) + .006)
                secs.append([Vector((math.sin(t) * rx, -math.cos(t) * ry, zz)) for t in np.linspace(0, 2 * math.pi, 28, endpoint=False)])
            skirt = bl.loft('skirt', secs, shirt, cap=False); skirt.data.materials[0].use_backface_culling = False
            bl.uv_box(skirt, .3)
            out['dress'] = (self.finish_outfit('dress', [top, skirt] + self.boots('dress', shoes, z['ankle'] + .02, sole_col='#222222')), ['foot'])
        else:
            jacket = longtop(bl.mat('shirt__wool', '#ffffff', 0, .8, image='fab_cotton.jpg', uv_scale=3), 'jacket')
            lapel = []
            for sx in (1, -1):
                P_, N_ = self.surf.line([(sx * (.03 + .03 * t) * k, z['neck'] - t * (z['neck'] - z['chest'] + .02)) for t in np.linspace(0, 1, 8)], -1)
                if len(P_) > 2:
                    lapel.append(hq.ribbon('lapel', P_, N_, .035 * k, bl.mat('lapel', '#e8e6e2', 0, .7), lift=.016))
            out['suit'] = (self.finish_outfit('suit', [jacket, trousers(cloth, .01)] + lapel + shoe_parts()), ['pelvis', 'thigh', 'foot', 'forearm'])
        return out

    def hair_styles(self):
        k, hr, cz, z = self.k, self.hr, self.hcz, self.z
        cardm = hq.card_mat('hair__card', 'hair_card_m.png')
        capm = bl.mat('hair__scalp', '#3a2c22', 0, .7)
        brow = cz + hr * .42
        def keep(c, n):
            if c.y < 0 and c.z < brow and abs(c.x) < hr * .7:
                return False
            return c.z > cz - hr * .35 or c.y > hr * .3
        styles = {}
        def pack(name, objs):
            for o in objs:
                bl.apply_all(o); self.rig.skin(o, 'rigid', 'head')
            styles[name] = bl.join(objs, 'H_' + name)
        pack('short', [self.hair_cap('cap', capm, .005, keep)] + self.scalp_cards(cardm, None, 30, lift=1.04, seed=11))
        if self.sex == 'female':
            tie = Vector((0, hr * .9, cz + hr * .1))
            bun = bl.sphere('bun', .045 * k, tie + Vector((0, .03, .02)), capm, 12, 8)
            pack('bun', [self.hair_cap('cap', capm, .005, keep), bun] + self.scalp_cards(cardm, tie, 26, seed=12))
            bob = []
            for j in range(26):
                a = -2.4 + 4.8 * j / 25
                if abs(a) < .7:
                    continue
                C = Vector((0, .008 * k, cz))
                top = C + Vector((math.sin(a) * hr * .55, -math.cos(a) * hr * .6, hr))
                end = C + Vector((math.sin(a) * hr * 1.15, -math.cos(a) * hr * 1.05, -hr * .85))
                pts = hq.bezier([top, C + Vector((math.sin(a) * hr * 1.1, -math.cos(a) * hr * 1.05, hr * .2)), end], 12)
                bob.append(hq.card('bob', pts, [.07 * k] * 14, cardm, [Vector((p.x, p.y, 0)).normalized() for p in pts]))
            pack('bob', [self.hair_cap('cap', capm, .005, keep)] + bob)
        else:
            pack('buzz', [self.hair_cap('cap', capm, .003, keep)])
        return styles

    def run(self, fname):
        bl.reset()
        self.build_body()
        outfits = self.outfits()
        hair = self.hair_styles()
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
        arm['worldex'] = json.dumps({'outfits': {k: v[1] for k, v in outfits.items()}, 'hair': list(hair.keys())})
        bl.export(fname, animations=True)


if __name__ == '__main__':
    bl.reset()
    painted_face('civ_face_female', False); painted_face('civ_face_male', True)
    fabric('fab_cotton', 'cotton', (.93, .93, .93)); fabric('fab_knit', 'knit', (.92, .92, .92))
    fabric('fab_denim', 'denim', (.36, .45, .62)); fabric('fab_plaid', 'plaid', (.9, .9, .9))
    CivBuilder('female').run('civ_female.glb')
    CivBuilder('male').run('civ_male.glb')
