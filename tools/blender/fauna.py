"""Small city fauna for New Meridian (meridian/fauna.js): two street birds and a stray cat, sculpted with fleshkit
(SDF primitives -> Surface Nets -> vertex-coloured mesh) and exported together as assets/models/fauna.glb.

  BIRD_pigeon   plump grey city pigeon, iridescent neck, dark wing bars (~0.32 m)
  BIRD_sparrow  small streaked brown sparrow (~0.16 m)
     Static meshes (one draw call per species, instanced in the game). Wings are modelled spread; two vertex attributes
     drive the game's vertex shader: `_wing` (0 body, 1 wing; soft at the shoulder; the span comes from x) folds / flaps the wings and
     `_head` (1 head and neck) bobs the head for pecking. Material `bird` (vertex colours).
  CAT           a lean short-haired stray (~0.45 m body + tail) on its own 14-bone rig: clips Idle, Sit, Walk (low
     slink, lateral-sequence gait), Run (bounding gallop), Look (alert, head up, tail flick).
     Materials (names are an API, tinted per cat at runtime): `cat_coat` (tabby-striped vertex colours), `cat_light`
     (muzzle, bib and paws), `cat_eye` (eyeshine at night).

Blender is Z-up, -Y forward; the exporter turns it into three's Y-up, +Z forward.
Run: blender --background --python tools/blender/fauna.py
"""
import bpy, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl, sdf
import fleshkit as fk
from fleshkit import X, Y, Z, S, TAU2, smooth, fbm

PI = math.pi


def soft_mask(V, c, r0, r1):
    d = np.linalg.norm(V - np.asarray(c, float), axis=1)
    return 1 - sdf.smoothstep(r0, r1, d)


def colors(o):
    me = o.data
    a = me.color_attributes.active_color
    C = np.empty(len(a.data) * 4, np.float32)
    a.data.foreach_get('color_srgb' if hasattr(a.data[0], 'color_srgb') else 'color', C)
    return C.reshape(-1, 4)[:, :3]


def write_colors(o, C):
    me = o.data
    a = me.color_attributes.active_color
    rgba = np.ones((len(C), 4), np.float32); rgba[:, :3] = np.clip(C, 0, 1)
    a.data.foreach_set('color_srgb' if hasattr(a.data[0], 'color_srgb') else 'color', rgba.ravel())


def attr(o, name, vals):
    a = o.data.attributes.new(name, 'FLOAT', 'POINT'); a.data.foreach_set('value', np.asarray(vals, np.float32))


# ================================================================== birds
def bird(name, s, pal, seed):
    """s: overall scale (pigeon 1.0). pal: colour dict. Spread wings along +-X at shoulder height."""
    sc = fk.Sculpt(seed)
    B = lambda *v: np.array(v, float) * s
    body, head = pal['body'], pal['head']
    sc.ell(B(0, .0, .12), B(.058, .11, .062), 'b', 'bird', body, k=.03 * s, amp=0)                  # body
    sc.ell(B(0, -.05, .115), B(.05, .07, .058), 'b', 'bird', pal['breast'], k=.03 * s, amp=0)         # breast
    sc.ell(B(0, .03, .095), B(.045, .08, .04), 'b', 'bird', pal['belly'], k=.03 * s, amp=0)           # belly
    sc.cone(B(0, -.07, .15), B(0, -.1, .19), .03 * s, .026 * s, 'b', 'bird', pal['neck'], k=.02 * s, amp=0)
    sc.sph(B(0, -.11, .2), .03 * s, 'b', 'bird', head, k=.012 * s, amp=0)                          # head
    sc.cone(B(0, -.135, .198), B(0, -.162, .19), .009 * s, .003 * s, 'b', 'bird', pal['beak'], k=.004 * s, amp=0)
    for sx in (1, -1):
        sc.sph(B(sx * .022, -.122, .207), .0065 * s, 'b', 'bird', '#141210', k=.002 * s, amp=0)   # eyes
    # tail fan, slightly raised
    sc.ell(B(0, .15, .125), B(.04, .07, .009), 'b', 'bird', pal['tail'], k=.012 * s, amp=0)
    sc.ell(B(0, .2, .13), B(.036, .022, .008), 'b', 'bird', pal['tailtip'], k=.01 * s, amp=0)
    # legs (short, pinkish) and feet
    for sx in (1, -1):
        sc.cone(B(sx * .018, .02, .07), B(sx * .02, .0, .01), .006 * s, .004 * s, 'b', 'bird', pal['legs'], k=.004 * s, amp=0)
        for a in (-.4, 0, .4):
            sc.cone(B(sx * .02, 0, .006), B(sx * .02 + math.sin(a) * .025, -math.cos(a) * .025, .004), .0035 * s, .002 * s,
                    'b', 'bird', pal['legs'], k=.002 * s, amp=0)
    # wings, spread: inner (covert) + outer (primaries), dark bars across the inner wing
    for sx in (1, -1):
        sc.ell(B(sx * .1, -.01, .15), B(.07, .06, .01), 'b', 'bird', pal['wing'], k=.02 * s, amp=0, writhe=.5)
        sc.ell(B(sx * .2, .015, .15), B(.075, .05, .007), 'b', 'bird', pal['primaries'], k=.02 * s, amp=0, writhe=1.0)
        for k in range(2):
            sc.ell(B(sx * .11, .01 + k * .025, .158), B(.05, .006, .004), 'b', 'bird', pal['bar'], k=.004 * s, amp=0, writhe=.5)
    lo, hi = B(-.31, -.2, -.01), B(.31, .25, .24)
    o = fk.build_mesh(sc, name, lo, hi, .0042 * s, 620 if s > .8 else 440, {'bird': fk.tmat('bird', None, rough=.75)},
                      uv_scale=.2, ao_dist=.02 * s, mottle=.25, seed=seed, bruise=None, veins=None)
    V = fk.verts(o)
    # `_writhe` from the sculpt = wing ownership (0.5 inner wing, 1 primaries); rescale to span fraction
    wr = np.empty(len(V), np.float32); o.data.attributes['_writhe'].data.foreach_get('value', wr)
    span = np.clip((np.abs(V[:, 0]) - .035 * s) / (.27 * s), 0, 1)
    wing = np.clip(wr * 2, 0, 1) * np.clip(span * 5, 0, 1)
    o.data.attributes.remove(o.data.attributes['_writhe'])
    attr(o, '_wing', wing)
    attr(o, '_head', soft_mask(V, B(0, -.115, .2), .035 * s, .06 * s))
    # feather streaks on the back / wings
    C = colors(o)
    st = fbm(V / s, 40, 2, seed + 3)
    C *= (.88 + .24 * st)[:, None]
    write_colors(o, C)
    o.vertex_groups.clear()
    return o


PIGEON = dict(body='#8d929c', head='#6c717c', breast='#7f7f8e', belly='#9aa0aa', neck='#5f7f74', beak='#3a3433',
              tail='#7a7f8a', tailtip='#2c2e34', legs='#b0605a', wing='#9aa0aa', primaries='#4a4e57', bar='#2a2c31')
SPARROW = dict(body='#8a6a48', head='#6e5a4a', breast='#b8a88e', belly='#cfc2a8', neck='#9a8a76', beak='#3a3026',
               tail='#5a4430', tailtip='#3a2c20', legs='#9a7a64', wing='#8a6440', primaries='#4a3624', bar='#efe4d0')


# ================================================================== cat
def cat_joints():
    J = {
        'hips': ((0, .1, .2), (0, .0, .215)),
        'chest': ((0, .0, .215), (0, -.13, .225)),
        'neck': ((0, -.13, .225), (0, -.175, .285)),
        'head': ((0, -.175, .285), (0, -.245, .29)),
        'tail1': ((0, .13, .215), (0, .23, .22)),
        'tail2': ((0, .23, .22), (0, .31, .27)),
        'tail3': ((0, .31, .27), (0, .35, .36)),
    }
    P = {'hips': 'root', 'chest': 'hips', 'neck': 'chest', 'head': 'neck', 'tail1': 'hips', 'tail2': 'tail1', 'tail3': 'tail2'}
    for sd, sx in (('L', 1), ('R', -1)):
        J['fleg.' + sd] = ((sx * .04, -.1, .19), (sx * .042, -.11, .095))
        J['fpaw.' + sd] = ((sx * .042, -.11, .095), (sx * .042, -.115, .012))
        J['hleg.' + sd] = ((sx * .045, .085, .19), (sx * .048, .03, .1))
        J['hpaw.' + sd] = ((sx * .048, .03, .1), (sx * .048, .1, .012))
        P['fleg.' + sd] = 'chest'; P['fpaw.' + sd] = 'fleg.' + sd
        P['hleg.' + sd] = 'hips'; P['hpaw.' + sd] = 'hleg.' + sd
    J = {k: (np.array(a, float), np.array(t, float)) for k, (a, t) in J.items()}
    order = ['hips', 'chest', 'neck', 'head', 'tail1', 'tail2', 'tail3'] + [n + '.' + sd for sd in 'LR' for n in ('fleg', 'fpaw', 'hleg', 'hpaw')]
    return J, P, order


def cat():
    bl.reset()
    J, PAR, ORDER = cat_joints()
    sc = fk.Sculpt(77)
    COAT, LIGHT, PINK = '#c8c2b8', '#f4f0ea', '#d89a94'
    sc.disp = lambda P: (fbm(P, 60, 2, 4) - .5) * .0015
    # torso: ribcage, waist, haunches
    sc.ell((0, -.07, .215), (.062, .1, .07), 'chest', 'coat', COAT, k=.035)
    sc.ell((0, .03, .21), (.05, .1, .058), 'hips', 'coat', COAT, k=.035)
    sc.ell((0, .1, .2), (.058, .065, .066), 'hips', 'coat', COAT, k=.03)
    sc.ell((0, -.09, .175), (.042, .07, .035), 'chest', 'light', LIGHT, k=.03)            # bib / chest
    sc.ell((0, .03, .17), (.035, .08, .025), 'hips', 'light', LIGHT, k=.03)               # belly
    sc.cone((0, -.14, .23), (0, -.18, .28), .042, .036, 'neck', 'coat', COAT, k=.025)
    # head: skull, cheeks, muzzle, chin, ears, nose
    sc.ell((0, -.2, .3), (.05, .046, .042), 'head', 'coat', COAT, k=.02)
    for sx in (1, -1):
        sc.ell((sx * .028, -.225, .285), (.024, .022, .02), 'head', 'coat', COAT, k=.015)
        sc.cone((sx * .028, -.195, .325), (sx * .036, -.192, .37), .019, .002, 'head', 'coat', COAT, k=.008)  # ear
        sc.cut_ell((sx * .029, -.2, .345), (.008, .004, .016), 'head', 'coat', '#8a6a66', k=.004)          # ear hollow
        sc.sph((sx * .021, -.236, .307), .0105, 'head', 'eye', '#c8a030', k=.003, amp=0)                   # eyes
    sc.ell((0, -.245, .285), (.021, .016, .016), 'head', 'light', LIGHT, k=.012)
    sc.ell((0, -.24, .27), (.016, .016, .01), 'head', 'light', LIGHT, k=.01)
    sc.sph((0, -.262, .292), .006, 'head', 'light', PINK, k=.003, amp=0)
    # legs: slim, paws white
    for sd, sx in (('L', 1), ('R', -1)):
        a, b = J['fleg.' + sd]; _, f = J['fpaw.' + sd]
        sc.cone(a + np.array([0, 0, .02]), b, .026, .016, 'fleg.' + sd, 'coat', COAT, k=.02)
        sc.cone(b, f + np.array([0, 0, .01]), .016, .013, 'fpaw.' + sd, 'coat', COAT, k=.01)
        sc.ell(f + np.array([0, -.008, .004]), (.016, .021, .011), 'fpaw.' + sd, 'light', LIGHT, k=.01)
        a, b = J['hleg.' + sd]; _, f = J['hpaw.' + sd]
        sc.ell(a + np.array([0, -.012, -.025]), (.03, .045, .045), 'hleg.' + sd, 'coat', COAT, k=.025)        # thigh
        sc.cone(a, b, .028, .017, 'hleg.' + sd, 'coat', COAT, k=.02)
        sc.cone(b, f + np.array([0, 0, .01]), .016, .012, 'hpaw.' + sd, 'coat', COAT, k=.012)
        sc.ell(f + np.array([0, -.01, .004]), (.016, .024, .011), 'hpaw.' + sd, 'light', LIGHT, k=.01)
    # tail
    sc.chain([J['tail1'][0], J['tail1'][1], J['tail2'][1], J['tail3'][1], J['tail3'][1] + np.array([0, .01, .04])],
             [.019, .016, .014, .012, .008], ['tail1', 'tail1', 'tail2', 'tail3', 'tail3'], 'coat', COAT, k=.012)
    mats = {'coat': fk.tmat('cat_coat', None, rough=.85), 'light': fk.tmat('cat_light', None, rough=.85),
            'eye': bl.mat('cat_eye', '#c8a030', 0, .08, emit='#e0c040', strength=.05)}
    o = fk.build_mesh(sc, 'Body_cat', (-.12, -.3, -.02), (.12, .4, .42), .0045, 3200, mats, uv_scale=.3, ao_dist=.03,
                      mottle=.15, seed=31, bruise=None, veins=None)
    # tabby: dark stripes ringing the body/legs/tail, a darker spine line, an "M" mark on the forehead
    V = fk.verts(o)
    C = colors(o)
    warp = fbm(V, 12, 2, 9)
    stripes = np.sin(V[:, 1] * 110 + warp * 3.5 + V[:, 2] * 25)
    legs = V[:, 2] < .14
    stripes = np.where(legs, np.sin(V[:, 2] * 150 + warp * 4), stripes)
    tail = V[:, 1] > .15
    stripes = np.where(tail, np.sin(np.linalg.norm(V[:, 1:] - np.array([.15, .2]), axis=1) * 130 + warp * 2), stripes)
    t = sdf.smoothstep(.3, .75, stripes) * .6
    spine = (1 - sdf.smoothstep(.01, .035, np.abs(V[:, 0]))) * sdf.smoothstep(.22, .27, V[:, 2]) * .35
    t = np.clip(t + spine, 0, .7)
    light = C.mean(1) > .85
    t = np.where(light, t * .15, t)
    C *= (1 - t)[:, None]
    write_colors(o, C)
    o.data.attributes.remove(o.data.attributes['_writhe'])
    arm = fk.make_rig(J, PAR, ORDER)

    def legs_pose(d, sd, swing, knee, front, lift=0):
        if front:
            d['fleg.' + sd] = [(X, swing)]; d['fpaw.' + sd] = [(X, knee)]
        else:
            d['hleg.' + sd] = [(X, swing)]; d['hpaw.' + sd] = [(X, knee)]

    def tail(d, p, curl, sway):
        d['tail1'] = [(X, -curl * .4), (Z, sway * S(TAU2 * p))]
        d['tail2'] = [(X, -curl * .5), (Z, sway * 1.4 * S(TAU2 * p - .8))]
        d['tail3'] = [(X, -curl * .4), (Z, sway * 1.8 * S(TAU2 * p - 1.6))]

    def idle(p):
        b = S(TAU2 * p)
        d = {'head': [(Z, 22 * S(TAU2 * p * 1)), (X, -4 * b)], 'chest': [(X, .8 * b)]}
        tail(d, p, 25, 9)
        return d, fk.Vector((0, 0, .002 * b)), {}

    def look(p):
        d = {'neck': [(X, -16)], 'head': [(X, 12), (Z, 30 * S(TAU2 * p))], 'chest': [(X, -3)]}
        tail(d, p * 2, 40, 14)
        return d, fk.Vector((0, 0, .006)), {}

    def sit(p):
        b = S(TAU2 * p)
        # haunches down, front legs straight, chest raised, tail wrapped round the paws
        d = {'hips': [(X, -38)], 'chest': [(X, 14)], 'neck': [(X, 8)], 'head': [(X, 22), (Z, 14 * S(TAU2 * p))]}
        for sd in 'LR':
            d['hleg.' + sd] = [(X, -62)]; d['hpaw.' + sd] = [(X, 118)]
            d['fleg.' + sd] = [(X, 18)]; d['fpaw.' + sd] = [(X, -2)]
        d['tail1'] = [(X, 30), (Z, 50)]; d['tail2'] = [(Z, 55), (X, 10)]; d['tail3'] = [(Z, 50 + 6 * b)]
        return d, fk.Vector((0, .03, -.075)), {}

    def walk(p):
        # lateral sequence: LH 0, LF .25, RH .5, RF .75; low slink
        d = {'head': [(X, 6), (Z, 3 * S(TAU2 * p))], 'chest': [(Z, 3 * S(TAU2 * p))], 'hips': [(Z, -3 * S(TAU2 * p))]}
        for sd, off in (('L', 0), ('R', .5)):
            for front, ph in ((False, off), (True, off + .25)):
                a = TAU2 * (p - ph)
                sw = -24 * math.cos(a) if front else -22 * math.cos(a)
                lift = max(0, math.sin(a))
                legs_pose(d, sd, sw - (8 * lift if front else -6 * lift), (-20 if front else 30) * lift, front)
        tail(d, p, 8, 6)
        return d, fk.Vector((0, 0, -.018 + .005 * abs(math.sin(TAU2 * p * 2)))), {}

    def run(p):
        # bounding gallop: spine flexes, front pair then hind pair (slightly offset)
        a = TAU2 * p
        flex = math.sin(a)
        d = {'chest': [(X, -10 * flex)], 'hips': [(X, 8 * flex)], 'neck': [(X, -6 + 6 * flex)], 'head': [(X, 8)]}
        for sd, o_ in (('L', 0), ('R', .07)):
            fa = a - TAU2 * o_; ha = a + PI - TAU2 * o_
            legs_pose(d, sd, -48 * math.cos(fa), -45 * max(0, math.sin(fa)), True)
            legs_pose(d, sd, -46 * math.cos(ha), 55 * max(0, math.sin(ha)), False)
        d['tail1'] = [(X, 18)]; d['tail2'] = [(X, 8 + 10 * flex)]; d['tail3'] = [(X, 6 + 8 * flex)]
        return d, fk.Vector((0, 0, .025 * max(0, math.sin(a * 2)) - .01)), {}

    fk.bake_clips(arm, {'Idle': (3.2, True, idle), 'Look': (2.4, True, look), 'Sit': (4.0, True, sit),
                        'Walk': (.9, True, walk), 'Run': (.34, True, run)}, 'hips')
    arm.name = 'CAT'
    o.parent = arm
    md = o.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    return arm


def main():
    cat()
    for name, s, pal, seed in (('BIRD_pigeon', 1.0, PIGEON, 5), ('BIRD_sparrow', .55, SPARROW, 9)):
        o = bird(name, s, pal, seed)
        o.location.x = 1.0 if 'pigeon' in name else 1.6           # side by side in the file (the game resets positions)
    p = bl.export('fauna.glb', animations=True, export_vertex_color='ACTIVE', export_attributes=True, export_image_format='NONE',
                  export_texcoords=False)
    bl.quantize_glb(p)
    pv = os.environ.get('FAUNA_PREVIEW')          # separate cat / bird files for preview.py contact sheets
    if pv:
        os.makedirs(pv, exist_ok=True)
        keep = bl.MODELS; bl.MODELS = pv
        try:
            cat_objs = [o for o in bpy.data.objects if o.name in ('CAT', 'Body_cat') or (o.parent and o.parent.name == 'CAT')]
            bl.export('cat.glb', animations=True, selected=cat_objs, export_vertex_color='ACTIVE')
            for n in ('BIRD_pigeon', 'BIRD_sparrow'):
                bl.export(n.lower() + '.glb', selected=[bpy.data.objects[n]], export_vertex_color='ACTIVE')
        finally:
            bl.MODELS = keep
    print('[export] fauna.glb quantized %.0f KB' % (os.path.getsize(p) / 1024))


if __name__ == '__main__':
    main()
