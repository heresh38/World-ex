"""Void Requiem: the weapon set the Spire Warden guards in VANTHOS (one random piece per operation run).

"Echoes of the fallen... power for the bold." Nine guns in one style: obsidian black gunmetal bodies with weathered gold
trim, jagged blade fins and thorns sweeping back along barrel and stock, violet void crystals set into the receivers,
crackling energy veins along the flanks, and the set emblem (a gold ring core holding a diamond crystal) on both sides
of every receiver. Purple energy burns in every muzzle.

  rifle       assault rifle: shard handguard with forward fangs, curved magazine (rifle rock-in reload)
  sniper      long spiked barrel (thorned collars), violet-lensed scope, thumbhole stock (DMR mag + op-rod reload)
  smg         compact SMG: crowned shroud of four fins, blade foregrip (compact-SMG reload)
  shotgun     pump shotgun with a three-fanged maw (per-shell pump reload)
  lmg         belt-fed LMG with a box magazine and a feed cover (own reload: cover up, box out, belt laid, cover slammed)
  handcannon  six-shot hand cannon: crane-out cylinder, finned top rib (revolver reload with speedloader)
  pistol      pistol: slide with a crystal spine window (pistol reload, slide lock)
  fusion      fusion rifle: twin ring cores, three-pronged emitter cage, crystal cell (charge, then a burst of bolts)
  rocket      rocket launcher: wide glowing bore, fang crown, tail fins, crystal canister

Frame, empties and moving-part names follow weapons.py (origin = top of the pistol grip, barrel along -Y, right = -X;
muzzle / foregrip / sight / rail / scope / OPTIC; reload parts mag, bolt, charge, slide, pump, crane > cylinder > rounds,
cover; loose x_shell / x_casing / x_speedloader).

Material names are an API (src/game/voidset.js applies the vq_* maps and the void shaders by name):
  void_obsidian, void_plate, void_gold, void_grip, void_glow (crystals; `_vq` = 0 at the root .. 1 at the tip),
  void_vein (energy veins; `_vq` = distance along the vein, for the crackle), void_lens.
Every mesh carries `_wear` (gunkit.wear_attr: edge highlights) and `_vq`.

The GLBs ship without images (the vq_* sets are one download for the whole set); VQ_PREVIEW=<dir> also writes copies
with the textures embedded for preview.py. Run void_textures.py first.

Run: blender --background --python tools/blender/void_requiem.py [-- rifle sniper ...]   (no names = all nine)
"""
import bpy, bmesh, math, os, sys, random
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import bl
import gunkit as K
from gunkit import B, ext, tube, cbox, ccyl, cylx, cylz, ball, ring, rod, R90

RIGHT = -1
F32 = np.float32


# ================================================================== materials
def mats():
    return dict(obs=K.tmat('void_obsidian', 'vq_obsidian'),
                plate=K.tmat('void_plate', 'vq_plate'),
                gold=K.tmat('void_gold', 'vq_gold'),
                grip=K.tmat('void_grip', 'vq_grip', metal=0, rough=.7),
                glow=K.tmat('void_glow', 'vq_crystal', rough=.1, emit='#ffffff', strength=3.0, emit_tex=True),
                vein=bl.mat('void_vein', '#b46cff', 0, .3, emit='#c27aff', strength=6),
                lens=bl.mat('void_lens', '#2a0a4a', .4, .05, emit='#7a2ad8', strength=.6))


# ================================================================== attributes
def vq(o, vals=None):
    """Per-vertex `_vq` (crystal gradient / vein coordinate); zeros when vals is None."""
    me = o.data
    a = me.attributes.get('_vq') or me.attributes.new('_vq', 'FLOAT', 'POINT')
    v = np.zeros(len(me.vertices), F32) if vals is None else np.asarray(vals, F32)
    a.data.foreach_set('value', v)
    return o


def assemble(name, parts):
    parts = [p for p in parts if p is not None]
    for p in parts:
        if p.type == 'MESH' and '_vq' not in p.data.attributes:
            vq(p)
    return K.assemble(name, parts)


def moving(name, parts, pivot, parent, parent_pivot=(0, 0, 0)):
    o = assemble(name, parts)
    o.name = name
    o.data.transform(Matrix.Translation(-Vector(pivot)))
    o.location = Vector(pivot) - Vector(parent_pivot)
    o.parent = parent
    return o


def finish(name, parts, muzzle, fore, sight, optic=(), rail=None, scoped=False, moving_parts=(), loose=()):
    g = assemble(name, parts)
    made = {}
    for spec in moving_parts:
        nm, pp, pv = spec[:3]
        par = made[spec[3]] if len(spec) > 3 else None
        o = moving(nm, pp, pv, par[0] if par else g, par[1] if par else (0, 0, 0))
        made[nm] = (o, pv)
    for nm, pp, pv in loose:
        moving(nm, pp, pv, g)
    if optic:
        o = assemble('OPTIC', list(optic)); o.parent = g
    bl.empty('muzzle', muzzle, g); bl.empty('foregrip', fore, g); bl.empty('sight', sight, g)
    if scoped:
        bl.empty('scope', sight, g)
    if rail:
        bl.empty('rail', rail, g)
    path = bl.export(name + '.glb', export_attributes=True, export_image_format='NONE')
    bl.quantize_glb(path)
    pv = os.environ.get('VQ_PREVIEW')
    if pv:
        os.makedirs(pv, exist_ok=True)
        keep = bl.MODELS; bl.MODELS = pv
        try:
            bl.export(name + '.glb', export_attributes=True)
        finally:
            bl.MODELS = keep


# ================================================================== shapes
def _mesh(name, bm, m):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    if m is not None:
        me.materials.append(m)
    return o


def _xf(o, rot=None, pivot=(0, 0, 0), move=None):
    if rot is not None:
        from mathutils import Euler
        M = Matrix.Translation(Vector(pivot)) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Translation(-Vector(pivot))
        o.data.transform(M)
    if move is not None:
        o.data.transform(Matrix.Translation(Vector(move)))
    return o


def _seg_dist(p, a, b):
    ab = b - a; L = ab.length_squared
    t = 0 if L == 0 else max(0, min(1, (p - a).dot(ab) / L))
    return (p - (a + ab * t)).length


def blade(name, pts, w, m, sharp=.88, root=None, plane='x', at=0.0, rot=None, pivot=(0, 0, 0), smooth=22, glow=None):
    """Shard / fin / thorn: polygon pts in a plane ('x': (y, z) side profile, thickness along X centred on `at`;
    'z': (x, y) top profile, thickness along Z; 'y': (x, z) front profile, thickness along Y). Thickness is w at the
    root edge (pts[root[0]] -> pts[root[1]], default the first and last point) and thins to (1 - sharp) w at the
    point farthest from it, so the fin reads as a blade with bevelled faces. Optional rotation about `pivot`."""
    P = [Vector(p) for p in pts]
    ia, ib = root if root else (0, len(P) - 1)
    d = [_seg_dist(p, P[ia], P[ib]) for p in P]
    dm = max(d) or 1
    th = [w * (1 - sharp * (di / dm) ** .75) / 2 for di in d]

    def V3(p, off):
        if plane == 'x':
            return (at + off, p.x, p.y)
        if plane == 'z':
            return (p.x, p.y, at + off)
        return (p.x, at + off, p.y)
    bm = bmesh.new()
    top = [bm.verts.new(V3(p, t)) for p, t in zip(P, th)]
    bot = [bm.verts.new(V3(p, -t)) for p, t in zip(P, th)]
    ft = bm.faces.new(top); fb = bm.faces.new(bot[::-1])
    n = len(P)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((top[j], top[i], bot[i], bot[j]))
    bmesh.ops.triangulate(bm, faces=[ft, fb], quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = _mesh(name, bm, m)
    _xf(o, rot, pivot)
    if glow is not None:
        vq(o, [glow] * len(o.data.vertices))
    return K.harden(o, smooth)


def spike(name, base, tip, r, m, sides=4, twist=0.0, glow=None):
    """Pyramid thorn from a polygon of `sides` around `base` to `tip`."""
    base, tip = Vector(base), Vector(tip)
    ax = (tip - base).normalized()
    u = ax.orthogonal().normalized(); v = ax.cross(u)
    bm = bmesh.new()
    ring_ = [bm.verts.new(base + (u * math.cos(twist + k * 2 * math.pi / sides) + v * math.sin(twist + k * 2 * math.pi / sides)) * r) for k in range(sides)]
    t = bm.verts.new(tip)
    bm.faces.new(ring_[::-1])
    for k in range(sides):
        bm.faces.new((ring_[k], ring_[(k + 1) % sides], t))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = _mesh(name, bm, m)
    if glow is not None:
        vq(o, [0.0] * sides + [glow])
    return K.harden(o, 20)


def crystal(name, base, tip, r, m, sides=6, back=0.0, seed=0, flat=1.0, jitter=.18, waist=.35):
    """Faceted void crystal: a hexagonal (by default) prism with a pointed tip (and optional back point), slightly
    irregular. `_vq` runs 0 at the root to 1 at the tip (the shader brightens toward the tip and the core).
    flat squashes the cross-section along the second axis (flat > 1 = wider)."""
    rng = random.Random(seed)
    base, tip = Vector(base), Vector(tip)
    L = (tip - base).length; ax = (tip - base).normalized()
    u = Vector((1, 0, 0)) if abs(ax.x) < .9 else Vector((0, 0, 1))
    u = (u - ax * u.dot(ax)).normalized(); v = ax.cross(u)
    bm = bmesh.new()
    rings = []
    for k, (f, rr) in enumerate(((0.0, .82), (waist, 1.0))):
        c = base + ax * (L * f)
        rs = []
        for s in range(sides):
            a = s * 2 * math.pi / sides + rng.uniform(-.12, .12)
            q = rr * r * (1 + rng.uniform(-jitter, jitter))
            rs.append(bm.verts.new(c + u * math.cos(a) * q + v * math.sin(a) * q * flat))
        rings.append(rs)
    t = bm.verts.new(tip + (u * rng.uniform(-.2, .2) + v * rng.uniform(-.2, .2)) * r)
    for s in range(sides):
        a0, a1 = rings[0][s], rings[0][(s + 1) % sides]
        b0, b1 = rings[1][s], rings[1][(s + 1) % sides]
        bm.faces.new((a0, a1, b1, b0))
        bm.faces.new((b0, b1, t))
    vals = [0.0] * sides + [waist] * sides + [1.0]
    if back > 0:
        bt = bm.verts.new(base - ax * back)
        for s in range(sides):
            bm.faces.new((rings[0][(s + 1) % sides], rings[0][s], bt))
        vals.append(.6)
    else:
        bm.faces.new(rings[0][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = _mesh(name, bm, m)
    vq(o, vals)
    return K.harden(o, 15)


def cluster(name, c, normal, n, size, m, seed=0, spread=.55, sides=6):
    """A few crystals sprouting from one socket (sizes and tilts vary)."""
    rng = random.Random(seed)
    c = Vector(c); N = Vector(normal).normalized()
    u = N.orthogonal().normalized(); v = N.cross(u)
    out = []
    for k in range(n):
        a = rng.uniform(0, 2 * math.pi); t = spread * (0 if k == 0 else rng.uniform(.35, 1))
        d = (N + (u * math.cos(a) + v * math.sin(a)) * t).normalized()
        L = size * (1 if k == 0 else rng.uniform(.45, .8)); r = L * rng.uniform(.2, .26)
        b = c + (u * math.cos(a) + v * math.sin(a)) * size * .12 * (k > 0) - d * L * .2
        out.append(crystal(name, b, b + d * L, r, m, sides, seed=seed * 7 + k))
    return out


def diamond(name, c, hy, hz, hx, m, side=1):
    """Octahedral diamond crystal facing +X*side (the emblem gem): tips up/down along Z, front/back along Y."""
    c = Vector(c)
    bm = bmesh.new()
    V = [bm.verts.new(c + Vector(p)) for p in ((0, 0, hz), (0, 0, -hz), (0, -hy, 0), (0, hy, 0), (side * hx, 0, 0), (-side * hx * .3, 0, 0))]
    T, Bo, F, Bk, O, I = V
    for a, b in ((F, T), (T, Bk), (Bk, Bo), (Bo, F)):
        bm.faces.new((a, b, O)); bm.faces.new((b, a, I))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = _mesh(name, bm, m)
    vq(o, [.45, .45, .45, .45, 1.0, .2])
    return K.harden(o, 10)


def emblem(M, x, y, z, R, side=1, prongs=True):
    """The set emblem on a receiver flank (surface at x, facing +X*side): obsidian boss, gold outer ring with eight
    thorns, thin inner ring, four claws holding the diamond void crystal."""
    s = side
    P = [cylx('em_boss', R * 1.02, .004, (x + s * .0012, y, z), M['obs'], 40, .001),
         ring('em_ring', R, R * .13, (x + s * .0035, y, z), M['gold'], axis='x', maj=40, mn=8),
         ring('em_inner', R * .7, R * .055, (x + s * .0038, y, z), M['gold'], axis='x', maj=32, mn=6)]
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 2
        P.append(_thorn2d(M, x + s * .0024, y, z, a, R * 1.06, R * (.5 if k % 2 == 0 else .26), R * .11, R * .12))
    if prongs:
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            ca, sa = math.cos(a), math.sin(a)
            P.append(rod('em_claw', (x + s * .003, y + ca * R * .68, z + sa * R * .68), (x + s * .0075, y + ca * R * .3, z + sa * R * .3), R * .05, M['gold'], 8))
    P.append(diamond('em_gem', (x + s * .0045, y, z), R * .34, R * .6, R * .34, M['glow'], s))
    return P


def _thorn2d(M, x, y, z, a, r0, L, half, w):
    ca, sa = math.cos(a), math.sin(a)
    pts = [(y + ca * r0 - sa * half, z + sa * r0 + ca * half), (y + ca * (r0 + L), z + sa * (r0 + L)), (y + ca * r0 + sa * half, z + sa * r0 - ca * half)]
    return blade('em_thorn', pts, w, M['gold'], .75, root=(0, 2), plane='x', at=x)


def jag(pts, rng, amp=.22, n=3):
    """Midpoint-displaced polyline (lightning-like) through 2D control points."""
    P = [Vector(p) for p in pts]
    for it in range(n):
        Q = [P[0]]
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]; d = b - a
            nr = Vector((-d.y, d.x))
            Q += [(a + b) / 2 + nr * rng.uniform(-amp, amp), b]
        P = Q; amp *= .6
    return P


def ribbon(name, P, x, side, w, m, s0=0.0, taper=True, h=.0006):
    """Thin raised strip along a 2D (y, z) polyline on a flank at x (facing +X*side). `_vq` = metres along it + s0."""
    bm = bmesh.new()
    n = len(P); S = [0.0]
    for i in range(1, n):
        S.append(S[-1] + (P[i] - P[i - 1]).length)
    tot = S[-1] or 1
    rows = []
    for i in range(n):
        t = (P[min(n - 1, i + 1)] - P[max(0, i - 1)]); t = t.normalized() if t.length else Vector((0, 1))
        nr = Vector((-t.y, t.x))
        ww = w * (.25 + .75 * math.sin(math.pi * min(1, max(0, S[i] / tot))) ** .5) if taper else w
        a, b = P[i] + nr * ww / 2, P[i] - nr * ww / 2
        rows.append([bm.verts.new((x + side * h, a.x, a.y)), bm.verts.new((x + side * h, b.x, b.y)),
                     bm.verts.new((x - side * .0008, a.x, a.y)), bm.verts.new((x - side * .0008, b.x, b.y))])
    for i in range(n - 1):
        A, Bq = rows[i], rows[i + 1]
        for f in ((A[0], Bq[0], Bq[1], A[1]), (A[2], Bq[2], Bq[0], A[0]), (A[1], Bq[1], Bq[3], A[3])):
            bm.faces.new(f)
    bm.normal_update()
    for f in bm.faces:
        if abs(f.normal.x) > .7 and f.normal.x * side < 0:
            f.normal_flip()
    o = _mesh(name, bm, m)
    vq(o, [s0 + S[i] for i in range(n) for _ in range(4)])
    return o


def veins(M, paths, x, side, seed, w=.0022, branches=2, amp=.2):
    """Crackling energy veins on a flank: each control path becomes a jagged ribbon, with a few short forks."""
    rng = random.Random(seed)
    out = []
    for k, pts in enumerate(paths):
        P = jag(pts, rng, amp)
        s0 = rng.uniform(0, 3)
        out.append(ribbon('vein', P, x, side, w, M['vein'], s0))
        for b in range(branches):
            i = rng.randrange(2, max(3, len(P) - 2))
            d = (P[min(len(P) - 1, i + 1)] - P[i - 1]).normalized()
            nr = Vector((-d.y, d.x)) * rng.choice((-1, 1))
            L = rng.uniform(.012, .03)
            end = P[i] + (d * .6 + nr).normalized() * L
            Q = jag([tuple(P[i]), tuple(end)], rng, amp * .8, 2)
            out.append(ribbon('vein', Q, x, side, w * .7, M['vein'], s0 + rng.uniform(0, 1)))
    return out


def both(fn):
    """fn(side) for the left (+X) and right (-X) flank."""
    return fn(1) + fn(-1)


def gold_band(name, r, L, y0, z, M, x=0.0, verts=40):
    return tube(name, r, L, y0, z, M['gold'], verts, x=x)


def void_muzzle(M, y, z, r, L=.05, fangs=4, fang_len=.035, rot0=math.pi / 4, glow_r=None):
    """Muzzle crown: gold collar, `fangs` forward thorns around the bore, a glowing void disc and ring in the bore."""
    P = [tube('mz_collar', r, L, y, z, M['obs'], 40, hollow=r * .55),
         tube('mz_gold', r * 1.08, .008, y, z, M['gold'], 40),
         tube('mz_lip', r * 1.04, .006, y - L + .006, z, M['gold'], 40, hollow=r * .6),
         tube('mz_glow', (glow_r or r * .56), .004, y - L * .4, z, M['glow'], 24),
         ring('mz_ring', r * .62, r * .07, (0, y - L + .002, z), M['glow'], maj=32, mn=6)]
    for k in range(fangs):
        a = rot0 + k * 2 * math.pi / fangs
        ca, sa = math.cos(a), math.sin(a)
        b = Vector((ca * r * .82, y - L * .55, z + sa * r * .82))
        t = Vector((ca * r * 1.05, y - L - fang_len, z + sa * r * 1.05))
        P.append(spike('mz_fang', b, t, r * .26, M['obs'], 4, twist=a))
        P.append(spike('mz_fang_g', b + Vector((ca, 0, sa)) * r * .12, b + Vector((ca * r * .5, -L * .5, sa * r * .5)), r * .14, M['gold'], 3, twist=a))
    return P


def grip(M, ang=.3, h=.112, w=.032, y=0.0, z=0.0, pommel=True):
    P = [K.grip_profile('grip', M['grip'], ang=ang, h=h, w=w, y=y, z=z, swell=.005)]
    ca, sa = math.cos(ang), math.sin(ang)
    by, bz = y + (h + .002) * sa - .004 * ca, z - (h + .002) * ca

    if pommel:
        P.append(B('pommel', (w + .004, .05, .008), (0, by + .002, bz - .002), M['gold'], .002, rot=(ang, 0, 0)))
        P.append(blade('pommel_spike', [(by + .018, bz - .002), (by + .03, bz - .03), (by - .012, bz - .004)], w * .6, M['obs'], .8, root=(0, 2)))
    P += K.trigger_group(None, M['obs'], M['gold'], y=y - .03, z=z + .01, L=.06, drop=.048)
    return P


def void_sight(M, y, z, w=.03):
    """Factory sight: angular shard frame, violet glass, diamond reticle at (0, y - .024, z)."""
    P = [B('vs_base', (w, .052, .008), (0, y, z - .024), M['plate'], .002),
         B('vs_glass', (w - .006, .0015, .028), (0, y - .016, z), M['lens'], 0),
         B('vs_top', (w + .004, .016, .004), (0, y - .016, z + .017), M['gold'], .0012),
         diamond('vs_dot', (0, y - .024, z), .0012, .0022, .0012, M['glow'])]
    for s in (1, -1):
        P.append(blade('vs_wing', [(y + .024, z - .02), (y - .028, z - .02), (y - .02, z + .02), (y - .004, z + .012)], .004, M['obs'], .5,
                       root=(0, 1), at=s * (w / 2 + .001)))
    return P


def void_shell(M, z=.3):
    """Loose shell prop for the pump reload (x_shell): obsidian hull, gold base, violet band."""
    return [tube('sh_hull', .0092, .052, .02, z, M['obs'], 16, bevel=.001), tube('sh_base', .0098, .012, .032, z, M['gold'], 16, bevel=.0008),
            tube('sh_band', .0094, .006, -.004, z, M['glow'], 16, bevel=0), tube('sh_crimp', .0086, .003, -.032, z, M['obs'], 16, bevel=0)]


# ================================================================== 1 assault rifle
def rifle():
    """Void assault rifle: shard side plates over an obsidian receiver, a crystal through the upper receiver, a shard
    handguard with two forward fangs, crowned muzzle, curved magazine, thorned skeleton stock."""
    bl.reset(); M = mats(); P = []
    zb = .066
    P += grip(M, ang=.32, h=.112, z=.02)
    # receivers
    P.append(ext('lower', [(.12, .05), (.12, .02), (.08, .012), (.03, .012), (.03, .02), (-.06, .02), (-.06, -.006), (-.13, -.006), (-.15, .02),
                           (-.2, .03), (-.2, .05)], .046, M['obs'], .002, cuts=[cbox((.032, .07, .03), (0, -.095, .0))]))
    P.append(ext('upper', [(.16, .05), (.16, .084), (.13, .1), (-.04, .106), (-.2, .1), (-.235, .084), (-.235, .05)], .05, M['obs'], .003,
                 cuts=[cbox((.014, .06, .02), (RIGHT * .025, -.02, .072))] + [cbox((.08, .031, .031), (0, -.12, .077), rot=(math.pi / 4, 0, 0))]))
    # shard side plates (proud of the receiver), cut around a diamond crystal window
    win = [cbox((.08, .031, .031), (0, -.12, .077), rot=(math.pi / 4, 0, 0))]
    P.append(ext('plate', [(.11, .058), (.07, .097), (-.07, .1), (-.2, .094), (-.225, .072), (-.17, .052), (-.09, .058), (-.02, .052)], .055, M['plate'], .0015, cuts=win))
    P.append(ext('plate_gold', [(-.085, .057), (-.1, .06), (-.205, .066), (-.21, .072), (-.17, .053)], .057, M['gold'], .001))
    P.append(crystal('core', (0, -.095, .077), (0, -.155, .077), .029, M['glow'], 6, back=.012, seed=3, flat=.6, waist=.45))
    P += both(lambda s: [ring('win_rim', .0225, .0022, (s * .0275, -.12, .077), M['gold'], axis='x', maj=4, mn=4)])
    # emblem on both flanks, rear of the upper
    P += both(lambda s: emblem(M, s * .0275, .078, .072, .018, s))
    # veins along the plates and the lower
    P += both(lambda s: veins(M, [[(.05, .09), (-.02, .092), (-.08, .088)], [(-.16, .06), (-.205, .07)], [(.045, .062), (-.02, .058), (-.08, .062)]],
                              s * .0275, s, 11 + s, branches=2))
    P += both(lambda s: veins(M, [[(.1, .04), (.05, .028), (-.04, .03)]], s * .023, s, 21 + s, w=.0018, branches=1))
    # bolt carrier + charging handle (right side) = the rifle reload's 'bolt'
    BOLT = [B('carrier', (.012, .056, .016), (RIGHT * .02, -.02, .072), M['gold'], .002),
            rod('chstem', (RIGHT * .024, -.045, .074), (RIGHT * .046, -.05, .074), .0042, M['obs']),
            spike('chknob', (RIGHT * .044, -.05, .074), (RIGHT * .06, -.038, .074), .0075, M['gold'], 4)]
    # handguard: hexagonal shard tube with slanted vents, fangs reaching past the barrel
    vents = lambda: [cbox((.08, .012, .03), (0, -.28 - i * .04, .066), rot=(.6, 0, 0)) for i in range(4)]
    P.append(ext('hg', [(-.235, .036), (-.235, .096), (-.255, .102), (-.44, .1), (-.47, .088), (-.48, .05), (-.45, .034)], .052, M['obs'], .004, cuts=vents()))
    P.append(ext('hg_plate', [(-.25, .04), (-.25, .09), (-.43, .092), (-.46, .058), (-.43, .04)], .056, M['plate'], .002, cuts=vents()))
    P.append(B('hg_vent_glow', (.04, .17, .012), (0, -.34, .066), M['glow'], 0))
    for s in (1, -1):
        P.append(blade('fang', [(-.42, .095), (-.47, .098), (-.6, .085), (-.5, .08)], .012, M['obs'], .85, root=(0, 3), at=s * .02, rot=(0, s * .25, 0), pivot=(s * .02, -.45, .09)))
        P.append(blade('fang_lo', [(-.43, .042), (-.5, .038), (-.585, .03), (-.48, .048)], .01, M['obs'], .85, root=(0, 3), at=s * .019, rot=(0, -s * .3, 0), pivot=(s * .019, -.45, .04)))
    P += [gold_band('hg_band', .036, .012, -.232, .066, M, verts=6), gold_band('hg_band2', .033, .008, -.44, .066, M, verts=6)]
    P += both(lambda s: veins(M, [[(-.26, .088), (-.33, .084), (-.42, .086)], [(-.27, .046), (-.38, .05)]], s * .028, s, 31 + s, branches=1))
    # barrel + muzzle
    P += [tube('barrel', .0105, .17, -.46, zb, M['obs'], 32)] + void_muzzle(M, -.6, zb, .017, .05, 4, .03)
    # optic rail on the upper (factory sight sits on it)
    P += K.rail(None, .13, -.2, .1, .022, M['plate'])
    # stock: skeleton with thorns
    P.append(ext('stock', [(.16, .088), (.24, .084), (.4, .08), (.47, .108), (.44, .07), (.45, -.04), (.49, -.085), (.43, -.06), (.3, -.02), (.22, .02), (.16, .04)], .042, M['obs'], .006,
                 cuts=[cbox((.06, .12, .034), (0, .32, .028), rot=(.1, 0, 0))]))
    P.append(ext('stock_plate', [(.18, .08), (.39, .074), (.42, .05), (.25, .052)], .045, M['plate'], .002))
    P.append(ext('buttpad', [(.44, .074), (.455, .072), (.462, -.036), (.448, -.04)], .046, M['grip'], .004))
    P.append(blade('stock_fin', [(.22, .086), (.36, .082), (.46, .125), (.3, .095)], .008, M['gold'], .85, root=(0, 1)))
    P += both(lambda s: veins(M, [[(.2, .07), (.3, .062), (.4, .062)], [(.26, .01), (.36, -.02)]], s * .0225, s, 41 + s, branches=1))
    P += K.pins(.047, [(.1, .036), (-.12, .036)], M['gold'])
    # magazine: curved, plate with gold ribs and a glowing round counter; pivot at its front lip (rock-in)
    MAG = curved_mag('mag', -.07, .02, .36, .062, .58, .03, M)
    sz = .132
    finish('gun_void_rifle', P, (0, -.68, zb), (0, -.34, .016), (0, .1, sz), optic=void_sight(M, -.04, sz), rail=(0, -.04, .1095),
           moving_parts=[('mag', MAG, (0, -.132, .02)), ('bolt', BOLT, (RIGHT * .046, -.05, .074))])


def curved_mag(name, y_rear, z_top, R, depth, theta, w, M):
    cy, cz = y_rear - R, z_top
    n = 14
    rear = [(cy + R * math.cos(t), cz - R * math.sin(t)) for t in np.linspace(0, theta, n)]
    front = [(cy + (R - depth) * math.cos(t), cz - (R - depth) * math.sin(t)) for t in np.linspace(theta, 0, n)]
    P = [ext(name, rear + front, w, M['plate'], .0025)]
    for k in range(2):
        r0 = R - depth * (.25 + .5 * k) + .003; r1 = r0 - .005
        a = [(cy + r0 * math.cos(t), cz - r0 * math.sin(t)) for t in np.linspace(.1, theta - .05, 10)]
        b = [(cy + r1 * math.cos(t), cz - r1 * math.sin(t)) for t in np.linspace(theta - .05, .1, 10)]
        P.append(ext('magrib', a + b, w + .003, M['gold'], .001, 2))
    # counter window: glowing strip down the flank
    r0 = R - depth * .5 + .004; r1 = r0 - .008
    a = [(cy + r0 * math.cos(t), cz - r0 * math.sin(t)) for t in np.linspace(.14, theta * .7, 8)]
    b = [(cy + r1 * math.cos(t), cz - r1 * math.sin(t)) for t in np.linspace(theta * .7, .14, 8)]
    P.append(ext('magglow', a + b, w + .0015, M['glow'], 0))
    t = theta; ca, sa = math.cos(t), math.sin(t)
    mid = (cy + (R - depth / 2) * ca, cz - (R - depth / 2) * sa)
    P.append(B('magfloor', (w + .006, depth + .014, .01), (0, mid[0] + sa * .003, mid[1] - ca * .003), M['gold'], .003, rot=(-t, 0, 0)))
    P.append(blade('magspike', [(mid[0] - depth * .5 * ca + sa * .006, mid[1] + depth * .5 * sa - ca * .006 - .002),
                                (mid[0] + .01, mid[1] - .03), (mid[0] + depth * .5 * ca + sa * .006, mid[1] - depth * .5 * sa - ca * .006 - .002)],
                   w * .7, M['obs'], .8, root=(0, 2)))
    return P


GUNS = dict(rifle=rifle)

if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = [a for a in args if a]
    for k in (args or list(GUNS)):
        GUNS[k]()
