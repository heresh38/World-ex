"""Organic human base mesh for the HQ characters.

A joint skeleton is skinned with Blender's Skin modifier, subdivided, then sculpted in code with smooth
displacement fields (torso depth, chest, glutes, deltoids, calves). The head is a separate shaped mesh so the
face can carry its own texture. Everything is in Blender coordinates: Z up, character faces -Y, left = +X.
"""
import bpy, bmesh, math
from mathutils import Vector
import bl


def gauss(d2, s):
    return math.exp(-d2 / (2 * s * s))


class Proportions:
    def __init__(self, sex='female', height=1.62, build=1.0):
        self.sex, self.H = sex, height
        f = sex == 'female'
        H = height
        self.f = f
        self.build = build
        self.shoulder = (.168 if f else .205) * build * H / (1.62 if f else 1.82) * (1.0 if f else 1.0)
        self.hipj = .088 if f else .092
        self.z = dict(ankle=.045 * H, knee=.285 * H, hip=.505 * H, crotch=.47 * H, navel=.6 * H, waist=.625 * H,
                      chest=.715 * H, armpit=.735 * H, shoulder=.81 * H, neck=.835 * H, chin=.865 * H, top=H)
        self.upper_arm = .175 * H
        self.fore_arm = .15 * H
        self.hand = .105 * H

    def joints(self):
        z, s, H = self.z, self.shoulder, self.H
        J = {}
        J['hips'] = (Vector((0, 0, z['hip'])), Vector((0, 0, z['navel'])))
        J['spine'] = (Vector((0, 0, z['navel'])), Vector((0, 0, z['chest'])))
        J['chest'] = (Vector((0, 0, z['chest'])), Vector((0, 0, z['neck'])))
        J['neck'] = (Vector((0, 0, z['neck'])), Vector((0, .005, z['chin'] + .005)))
        J['head'] = (Vector((0, .005, z['chin'] + .005)), Vector((0, .005, z['top'])))
        for side, sx in (('L', 1), ('R', -1)):
            sp = Vector((sx * s, .005, z['shoulder'] - .012 * H))
            el = Vector((sx * (s + .045), .02, sp.z - self.upper_arm))
            wr = Vector((sx * (s + .07), -.005, el.z - self.fore_arm))
            J['upperarm.' + side] = (sp, el)
            J['forearm.' + side] = (el, wr)
            J['hand.' + side] = (wr, wr + Vector((sx * .008, -.005, -self.hand)))
            hj = Vector((sx * self.hipj, 0, z['hip'] - .02))
            kn = Vector((sx * (self.hipj - .006), -.012, z['knee']))
            an = Vector((sx * (self.hipj - .01), .015, z['ankle']))
            J['thigh.' + side] = (hj, kn)
            J['shin.' + side] = (kn, an)
            J['foot.' + side] = (an, Vector((an.x, -.13 * H / 1.7, .015)))
        return J


def skin_body(P, name='body', levels=2):
    """Skin-modifier body without head (neck stub). Returns the evaluated, subdivided mesh object."""
    J = P.joints()
    H, f = P.H, P.f
    verts, edges, rad = [], [], []

    def add(p, r):
        verts.append(Vector(p)); rad.append(r); return len(verts) - 1

    def chain(pts, radii, start=None):
        prev = start
        idx = []
        for p, r in zip(pts, radii):
            i = add(p, r)
            if prev is not None:
                edges.append((prev, i))
            prev = i; idx.append(i)
        return idx

    z = P.z
    k = H / 1.7
    # spine chain: pelvis -> waist -> chest -> neck
    tw = 1.0 if f else 1.12
    spine = chain([(0, 0, z['hip'] - .01), (0, 0, z['navel']), (0, 0, z['waist']),
                   (0, 0, z['chest'] - .03), (0, 0, z['chest'] + .03), (0, 0, z['armpit'] + .03), (0, .01, z['neck'] - .01),
                   (0, .012, z['chin'] + .01), (0, .012, z['chin'] + .05)],
                  [(.15 * k * (1.06 if f else .98), .1 * k), (.122 * k * tw, .09 * k),
                   (.112 * k * tw, .085 * k), (.13 * k * tw, .095 * k), (.142 * k * tw, .1 * k), (.148 * k * tw, .095 * k),
                   (.058 * k, .058 * k), (.052 * k, .052 * k), (.045 * k, .045 * k)])
    pelvis, chestv = spine[0], spine[5]
    for side, sx in (('L', 1), ('R', -1)):
        # arm: shoulder cap from the upper chest
        sp, el = J['upperarm.' + side]; _, wr = J['forearm.' + side]; _, ht = J['hand.' + side]
        arm = chain([Vector((sx * P.shoulder * .55, .005, sp.z + .005)), sp, sp + (el - sp) * .45, el, el + (wr - el) * .5, wr,
                     wr + (ht - wr) * .45],
                    [(.05 * k, .05 * k), (.052 * k, .052 * k), (.046 * k * (1 if f else 1.28), .046 * k * (1 if f else 1.15)), (.037 * k, .037 * k),
                     (.036 * k * (1 if f else 1.25), .034 * k * (1 if f else 1.1)), (.026 * k, .022 * k), (.034 * k, .016 * k)], start=chestv)
        palm = arm[-1]
        # fingers
        for fi in range(4):
            fx = (fi - 1.5) * .011 * k
            base = wr + (ht - wr) * .55 + Vector((fx * (-sx) * 0 + 0, fx, 0))
            pts = [base + Vector((0, 0, -.02 * k)), base + Vector((0, -.006 * k, -.055 * k)), base + Vector((0, -.012 * k, -.085 * k * (.85 if fi in (0, 3) else 1)))]
            chain(pts, [(.0075 * k, .0075 * k), (.0068 * k, .0068 * k), (.006 * k, .006 * k)], start=palm)
        tb = wr + (ht - wr) * .25 + Vector((0, -.022 * k, 0))
        chain([tb, tb + Vector((0, -.02 * k, -.03 * k)), tb + Vector((0, -.03 * k, -.055 * k))], [(.009 * k, .009 * k), (.008 * k, .008 * k), (.007 * k, .007 * k)], start=arm[-2])
        # leg
        hj, kn = J['thigh.' + side]; _, an = J['shin.' + side]; _, toe = J['foot.' + side]
        thick = 1.08 if f else 1.0
        leg = chain([hj + Vector((0, 0, .02)), hj + (kn - hj) * .4, kn, kn + (an - kn) * .35, an + Vector((0, 0, .02)), an + Vector((0, -.04, -.02)), toe + Vector((0, 0, .015))],
                    [(.088 * k * thick, .085 * k), (.075 * k * thick, .072 * k), (.05 * k, .05 * k), (.052 * k, .056 * k),
                     (.032 * k, .034 * k), (.038 * k, .03 * k), (.036 * k, .022 * k)], start=pelvis)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    sk = o.modifiers.new('skin', 'SKIN')
    sk.use_smooth_shade = True
    sv = me.skin_vertices[0].data
    for i, r in enumerate(rad):
        sv[i].radius = r
    sv[spine[0]].use_root = True
    sub = o.modifiers.new('sub', 'SUBSURF'); sub.levels = levels; sub.render_levels = levels
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    o.select_set(False)
    sculpt(o, P)
    return o


def sculpt(o, P):
    """Smooth displacement fields that turn the tube body into anatomy."""
    z, H, f = P.z, P.H, P.f
    k = H / 1.7
    for v in o.data.vertices:
        p = v.co
        x, y, zz = p.x, p.y, p.z
        ax = abs(x)
        # flatten torso depth, keep width (ribcage/abdomen are wider than deep)
        if z['crotch'] - .08 < zz < z['neck'] and ax < P.shoulder * .95:
            t = min(1, max(0, (P.shoulder * .95 - ax) / .05))
            belly = gauss((zz - z['navel']) ** 2, .07)
            p.y = y * (1 - (.16 + (.18 if y < 0 else .08) * belly) * t)
        # chest / bust
        if f:
            for sx in (1, -1):
                c = Vector((sx * .055 * k, -.07 * k, z['chest'] + .01))
                d2 = (x - c.x) ** 2 + ((zz - c.z) * 1.1) ** 2
                if y < 0:
                    p.y -= .038 * k * gauss(d2, .038 * k)
        else:
            for sx in (1, -1):
                d2 = (x - sx * .07 * k) ** 2 + (zz - z['chest'] - .02) ** 2
                if y < 0:
                    p.y -= .012 * k * gauss(d2, .05 * k)
        # glutes
        for sx in (1, -1):
            d2 = (x - sx * .055 * k) ** 2 + (zz - (z['crotch'] + .02)) ** 2
            if y > 0:
                p.y += (.035 if f else .022) * k * gauss(d2, .05 * k)
        # hips width (female)
        if f and z['crotch'] - .1 < zz < z['waist'] and ax > .06:
            p.x += math.copysign(.012 * k * gauss((zz - z['hip']) ** 2, .06), x)
        # waist pinch
        if z['navel'] - .04 < zz < z['chest'] - .02 and ax < P.shoulder:
            pinch = (.05 if f else .02) * gauss((zz - z['waist']) ** 2, .045)
            p.x *= 1 - pinch
        # calves
        if z['ankle'] < zz < z['knee'] and y > 0 and ax > .03:
            p.y += .014 * k * gauss((zz - (z['knee'] - .1 * k)) ** 2, .05 * k)
        # deltoids / shoulder slope
        if zz > z['armpit'] - .02 and ax > P.shoulder * .55:
            p.z -= (.012 if f else .006) * gauss((ax - P.shoulder * .6) ** 2, .04)
    o.data.update()


def head(P, name='head', hair_line=True):
    """Head with face features; UVs: planar front projection (0..1 over the face box) for the face texture."""
    z, H, f = P.z, P.H, P.f
    k = H / 1.7
    hr = (.096 if f else .1) * k * (1.08 if f else 1.0)   # head radius
    cz = z['chin'] + (z['top'] - z['chin']) * .5
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=30, radius=1.0)
    for v in bm.verts:
        x, y, zz = v.co
        # base egg: taller than wide, deeper at the back
        X = x * hr * .82
        Y = y * hr * (1.0 if y > 0 else .92)
        Z = zz * hr * 1.12
        # jaw/chin taper toward the bottom front
        if zz < 0:
            jaw = 1 - (.25 if f else .18) * (-zz) ** 1.5
            X *= jaw
            if y < 0:
                Y *= 1 - .15 * (-zz)
        # flatten the face plane slightly
        if y < -.3:
            Y = Y * .93
        bv = Vector((X, Y, Z))
        # nose, brow, cheeks, lips (smooth bumps on the front)
        fx, fz = X / hr, Z / hr
        if Y < 0:
            nose = gauss(fx ** 2 * 6 + (fz + .05) ** 2 * 1.5, .16) * .16 * hr
            brow = gauss((fz - .28) ** 2 * 4, .14) * gauss(fx ** 2, .45) * .05 * hr
            cheek = sum(gauss((fx - sx * .45) ** 2 + (fz + .12) ** 2, .16) for sx in (1, -1)) * .045 * hr
            eyes = -sum(gauss((fx - sx * .3) ** 2 * 1.2 + (fz - .14) ** 2 * 3, .1) for sx in (1, -1)) * .035 * hr
            lips = gauss(fx ** 2 * 3 + (fz + .43) ** 2 * 12, .12) * .025 * hr
            chin = gauss(fx ** 2 * 2 + (fz + .78) ** 2 * 6, .2) * (.02 if f else .035) * hr
            bv.y -= nose + brow + cheek + eyes + lips + chin
        v.co = bv
    # ears
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = (0, .008 * k, cz)
    bl.apply_all(o)
    bl.autosmooth(o, 80)
    # planar UV from the front: u from x, v from z over the face box
    face_w = hr * 1.65; face_top = cz + hr * .62; face_bot = z['chin'] - .005
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vco = me.vertices[me.loops[li].vertex_index].co
            u = .5 + vco.x / face_w
            vv = (vco.z - face_bot) / (face_top - face_bot)
            uv.data[li].uv = (u, vv)
    o['face_box'] = (face_w, face_top, face_bot)
    o['head_r'] = hr
    o['head_cz'] = cz
    return o
