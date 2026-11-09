"""The field coat's details, built onto its finished surface (coat.py): every part is shaped over the cloth it sits
on (projected onto it along its normal), with its own thickness, rounded edges and stitching, and hardware where a
real coat would have it.

  zip          a separating zip down both front edges to the waist: woven tape on the inside of each edge, moulded
               teeth along it (alternate sides), the slider and pull parked at the bottom of the left half, a box
               and pin at the bottom stop
  collar tab   a strap on the right half of the collar with a press stud, its partner stud on the left
  hood         stowed: rolled into a soft bundle under the collar at the back, its seam stitched
  pockets      hip flap pockets (flap, stitched border, two studs), a diagonal zip pocket on the left chest (welted),
               a patch pocket with a flap on the left upper arm and an insignia patch above it
  patches      reinforced elbows and shoulders (coated fabric, stitched), the shoulder tabs with their light strip
  straps       cuff adjusters with studs, a half belt across the back waist between the princess seams
"""
import math
import bmesh
import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import garment

STEEL, COAT, PATCH, STITCH, ZIP, GLOW = "orion_steel", "orion_coat", "orion_strap", "orion_stitch", "orion_zip", "orion_glow"
TILE = .08                                                 # (fabric.TILE["twill"]: one UV unit in metres)


class Surface:
    """the coat's outer surface for laying parts on it"""

    def __init__(self, o):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.normal_update()
        self.tree = BVHTree.FromBMesh(bm)
        bm.free()

    def on(self, p, n_hint, lift=0.0):
        """the outer surface under p (a ray from outside along -n_hint), lifted by lift; (point, normal)"""
        n = Vector(n_hint).normalized()
        # (the ray only searches near p: a long one finds the far side through an opening)
        hit, nrm, _, _ = self.tree.ray_cast(Vector(p) + n * .10, -n, .13)
        if hit is None:                                     # off the cloth: stay on the part's own plane (snapping
            return Vector(p) + n * lift, n                  # to some other nearest surface makes shards and spikes)
        if nrm.dot(n) < 0:
            nrm = -nrm
        return hit + nrm * lift, nrm

    def toward(self, origin, direction, lift=0.0, dist=1.0):
        """the first surface hit from `origin` along `direction` (placing things round a body from outside)"""
        hit, nrm, _, _ = self.tree.ray_cast(Vector(origin), Vector(direction).normalized(), dist)
        if hit is None:
            return None, None
        if nrm.dot(Vector(direction)) > 0:
            nrm = -nrm
        return hit + nrm * lift, nrm

    def frame(self, p, n_hint, down=Vector((0, 0, -1))):
        """(centre, u, v, n) at p: n the surface normal, v along `down` in the tangent plane, u across"""
        c, n = self.on(p, n_hint)
        v = Vector(down) - n * Vector(down).dot(n)
        v.normalize()
        u = v.cross(n).normalized()
        return c, u, v, n


def superellipse(s, t, k=6.0):
    """the unit square's point (s, t) in [-1, 1]^2 moved onto a rounded rectangle (squircle exponent k)"""
    m = max(abs(s), abs(t))
    if m < 1e-9:
        return 0.0, 0.0
    r = (abs(s) ** k + abs(t) ** k) ** (1 / k)
    return s * m / r, t * m / r


def panel(surf, frame, w, h, mat, lift=.0025, thick=.0028, n=(14, 10), k=6.0, lift_fn=None, name="panel",
          stitch_inset=.0045, stitch=True):
    """a piece of cloth / coated fabric laid on the coat: a rounded rectangle w x h over the surface, its own
    thickness and rounded edge, stitched round its border. lift_fn(s, t) adds lift (a flap standing off at the
    bottom). Returns the objects."""
    c, u, v, nn = frame
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    nu, nv = n
    grid = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            s, t = -1 + 2 * i / nu, -1 + 2 * j / nv
            x, y = superellipse(s, t, k)
            p = c + u * (x * w / 2) + v * (y * h / 2)
            l = lift + (lift_fn(x, y) if lift_fn else 0.0)
            q, _ = surf.on(p, nn, l)
            row.append((bm.verts.new(q), ((x + 1) * w / 2 / TILE, (y + 1) * h / 2 / TILE)))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid[j][i][0], grid[j][i + 1][0], grid[j + 1][i + 1][0], grid[j + 1][i][0]))
            for loop, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                loop[uvl].uv = grid[b][a][1]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    if sum(f.normal.dot(nn) for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    o = garment.obj(bm, name, mat)
    solid(o, thick)
    out = [o]
    if stitch:
        pts = []
        for a in range(0, 97):
            ang = 2 * math.pi * a / 96
            ca, sa = math.cos(ang), math.sin(ang)
            x = math.copysign(abs(ca) ** (2 / k), ca)          # the same rounded rectangle, walked round its edge
            y = math.copysign(abs(sa) ** (2 / k), sa)
            x *= 1 - 2 * stitch_inset / w
            y *= 1 - 2 * stitch_inset / h
            p = c + u * (x * w / 2) + v * (y * h / 2)
            l = lift + (lift_fn(x, y) if lift_fn else 0.0)
            q, qn = surf.on(p, nn, l + .0002)
            pts.append((q, qn))
        st = garment.trim_strip(pts, .0015, STITCH, lift=.0003, tile=.012, step=.003, name="stitch")
        if st:
            out.append(st)
    return out


def solid(o, t):
    m = o.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = t
    m.offset = -1.0
    m.use_rim = True
    m.use_even_offset = False                             # (even thickness spikes on sharply curved spots)
    m.thickness_clamp = .5
    b = o.modifiers.new("edge", 'BEVEL')
    b.width = t * .45
    b.segments = 2
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(50)
    bpy.context.view_layer.objects.active = o
    for md in (m, b):
        bpy.ops.object.modifier_apply(modifier=md.name)


def tube(pts, r, mat, name="tube", sides=8, tile=.03):
    """a round section swept along points (piping, a rolled edge, cord)"""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings, L = [], 0.0
    for i, p in enumerate(pts):
        t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        t = t.normalized() if t.length > 1e-9 else Vector((1, 0, 0))
        a = t.cross(Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))).normalized()
        b = t.cross(a)
        if i:
            L += (p - pts[i - 1]).length
        rings.append(([bm.verts.new(p + (a * math.cos(2 * math.pi * j / sides) + b * math.sin(2 * math.pi * j / sides)) * r)
                       for j in range(sides)], L / tile))
    for (A, va), (B, vb) in zip(rings, rings[1:]):
        for j in range(sides):
            f = bm.faces.new((A[j], A[(j + 1) % sides], B[(j + 1) % sides], B[j]))
            for loop, (u, v) in zip(f.loops, ((j / sides, va), ((j + 1) / sides, va), ((j + 1) / sides, vb), (j / sides, vb))):
                loop[uvl].uv = (u, v)
    bm.faces.new(rings[0][0][::-1])
    bm.faces.new(rings[-1][0])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return garment.obj(bm, name, mat)


def stud(surf, p, n_hint, r=.0055, lift=.0):
    q, n = surf.on(p, n_hint, lift)
    return [garment.snap(q, n, r, STEEL, name="stud"), ring(q, n, r * 1.25, r * .25, STEEL)]


def ring(p, n, R, r, mat, seg=20, sides=6):
    """a torus lying on the surface (a stud's rim, an eyelet)"""
    F = garment.frame_at(p, n)
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        d = Vector((math.cos(a), math.sin(a), 0))
        rr = []
        for j in range(sides):
            b = 2 * math.pi * j / sides
            q = d * (R + r * math.cos(b)) + Vector((0, 0, r * (1 + math.sin(b))))
            rr.append(bm.verts.new(F @ q + Vector(p)))
        rings.append(rr)
    for i in range(seg):
        A, B = rings[i], rings[(i + 1) % seg]
        for j in range(sides):
            bm.faces.new((A[j], A[(j + 1) % sides], B[(j + 1) % sides], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return garment.obj(bm, "ring", mat)


def box_at(p, R, size, mat, name="tooth"):
    """a small sharp-ish box (zip teeth): 6 faces"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = R @ Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(p)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(size) * .3, segments=1, affect='EDGES')
    return bm


# ------------------------------------------------------------------------------------------------ the parts

def zip_halves(surf, o, P):
    """teeth, tape and hardware down both front edges from the collar's top to the waist"""
    parts = []
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    edge = [e for e in bm.edges if e.is_boundary]
    teeth = bmesh.new()
    top = P.nb + P.collar_h * .86
    for sx in (1, -1):
        # the front edge: open edges on this side, in front, between the waist and the collar's top
        pts = [(v.co.copy(), v.normal.copy()) for e in edge for v in e.verts
               if v.co.x * sx > .015 and v.co.y < -.03 and P.zw + .005 < v.co.z < top and abs(v.co.x) < .14]
        if len(pts) < 10:
            continue
        pts.sort(key=lambda q: -q[0].z)
        # keep the outer surface's edge (the rim has an inner copy): the point furthest forward per height band
        band, chain = {}, []
        for p, n in pts:
            key = round(p.z / .004)
            if key not in band or p.y < band[key][0].y:
                band[key] = (p, n)
        chain = [band[k] for k in sorted(band, reverse=True)]
        chain = garment.smooth_chain(garment.resample(chain, .0044), 2)
        tape = garment.trim_strip(chain, .012, ZIP, offset=.0, lift=-.0035, tile=.03, step=.004, name="ziptape")
        if tape:
            parts.append(tape)
        for i, (p, n) in enumerate(chain):
            if (i + (0 if sx > 0 else 1)) % 2:
                continue
            t = chain[min(i + 1, len(chain) - 1)][0] - chain[max(i - 1, 0)][0]
            t.normalize()
            out = Vector((-sx, 0, 0))                         # toward the opening
            out = (out - t * out.dot(t)).normalized()
            R = Matrix((out, t, out.cross(t))).transposed()
            bm2 = box_at(p + out * .0025 - n * .0012, R, (.0050, .0034, .0028), STEEL)
            me = bpy.data.meshes.new("t")
            bm2.to_mesh(me)
            bm2.free()
            teeth.from_mesh(me)
            bpy.data.meshes.remove(me)
        # the bottom stop (box on the left, pin on the right) and the slider on the left half
        p, n = chain[-1]
        R = garment.frame_at(p, n)
        parts.append(garment.rounded_box((.008, .014, .005), R, p + Vector((-sx * .002, 0, .004)), STEEL, bevel=.0015,
                                         segs=2, name="zipstop"))
        if sx > 0:
            parts += garment.zip_pull(p + Vector((0, 0, .012)) + n * .002, n, STEEL)
    parts.append(garment.obj(teeth, "teeth", STEEL))
    bm.free()
    return parts


def hood(surf, P):
    """the hood down: folded flat over the upper back below the collar, its gathered volume, a centre seam, and the
    face opening's edge rolled over along the top showing the lining"""
    c0 = Vector((0, .14, P.nb - .105))
    fr = surf.frame(c0, Vector((0, 1, .35)))
    c, u, v, n = fr
    w, h = .245, .215

    def bulge(x, y):
        """volume: fullest in the middle, gathered at the top under the collar, soft folds toward the point"""
        body = .016 * (1 - x * x) * (1 - ((y + 1) / 2) ** 2) * (.4 + .6 * (1 - (y + 1) / 2))
        folds = .0035 * math.sin(x * 9.0 + 1.2 * y) * (1 - abs(x)) * (.3 + .7 * (y + 1) / 2)
        return body + folds
    parts = panel(surf, fr, w, h, COAT, lift=.003, thick=.005, n=(30, 22), k=2.6, lift_fn=bulge, name="hood",
                  stitch_inset=.008)
    # the centre seam down its back, stitched both sides
    pts = []
    for k in range(25):
        y = -.92 + 1.84 * k / 24
        q, qn = surf.on(c + v * (y * h / 2), n, .003 + bulge(0, y) + .0004)
        pts.append((q, qn))
    for off in (-.0035, .0035):
        st = garment.trim_strip(pts, .0015, STITCH, offset=off, tile=.012, step=.003, name="stitch")
        if st:
            parts.append(st)
    # the face opening's edge turned over along the top: a band of the lining lying on the hood, its own stitching
    band_c = c + v * (-.80 * h / 2)
    band = (surf.on(band_c, n)[0], u, v, n)
    parts += panel(surf, band, w * .88, .026, "orion_lining", lift=.003 + bulge(0, -.80) + .0015, thick=.0024, k=8.0,
                   lift_fn=lambda x, y: bulge(x * .88, -.80) - bulge(0, -.80), name="hoodedge", stitch_inset=.004)
    return parts


def collar_tab(surf, P):
    parts = []
    z = P.nb + P.collar_h * .55
    # the tab: a strap on the right half, its free end reaching to the front edge, with a stud
    a = Vector((-.075, -.035, z))
    b = Vector((-.045, -.062, z))
    pts = []
    for k in range(9):
        p = a.lerp(b, k / 8)
        q, n = surf.on(p, Vector((p.x, p.y - .01, 0)).normalized(), .003)
        pts.append(q)
    strap, path = garment.strap(type("S", (), {"bvh": surf.tree})(), pts, .026, .004, COAT, lift=.003, name="tab")
    parts.append(strap)
    q, n = path[-3]
    parts += [garment.snap(q + n * .002, n, .0055, STEEL, name="stud")]
    for sx in (1, -1):
        p = Vector((.058 * sx, -.050, z))
        parts += stud(surf, p, Vector((.4 * sx, -1, 0)), .0050, .0005)
    return parts


def hip_pockets(surf, P):
    parts = []
    for sx in (1, -1):
        p = Vector((.170 * sx, -.085, P.zw - .065))
        fr = surf.frame(p, Vector((.75 * sx, -1, 0)))
        # the flap: stands off a little toward its bottom edge (the pocket bellows under it)
        parts += panel(surf, fr, .150, .068, COAT, lift=.0022, thick=.0035, lift_fn=lambda x, y: .0035 * max(0.0, y) ** 1.5,
                       name="flap")
        c, u, v, n = fr
        for s in (-.55, .55):
            parts += stud(surf, c + u * (s * .150 / 2) + v * .018, n, .0055, .0060)
        # the pocket bag's outline below the flap (a panel just proud of the coat)
        bag = surf.frame(c + v * .075, n)
        parts += panel(surf, bag, .142, .11, COAT, lift=.0012, thick=.0016, name="pocket")
    return parts


def zip_line(pts, pull_at=2, tape_w=.0062, tooth=(.0034, .0020, .0016)):
    """a closed zip along points [(co, normal)] lying on a surface: woven tape, moulded teeth interlocking from both
    sides, the slider and pull at index pull_at, bar tacks at the ends"""
    parts = []
    tape = garment.trim_strip(pts, tape_w, ZIP, lift=.0007, tile=.03, step=.003, name="ziptape")
    if tape:
        parts.append(tape)
    teeth = bmesh.new()
    rs = garment.resample(pts, .0024)
    for i, (p, n) in enumerate(rs):
        t = (rs[min(i + 1, len(rs) - 1)][0] - rs[max(i - 1, 0)][0]).normalized()
        side = n.cross(t).normalized() * (1 if i % 2 else -1)
        R = Matrix((side, t, n)).transposed()
        bm2 = box_at(p + side * .0012 + n * .0014, R, tooth, STEEL)
        me = bpy.data.meshes.new("t")
        bm2.to_mesh(me)
        bm2.free()
        teeth.from_mesh(me)
        bpy.data.meshes.remove(me)
    parts.append(garment.obj(teeth, "teeth", STEEL))
    p, n = pts[min(pull_at, len(pts) - 1)]
    parts += garment.zip_pull(p + n * .002, n, STEEL, down=(pts[-1][0] - pts[0][0]).normalized())
    for p, n in (pts[0], pts[-1]):
        parts.append(garment.rounded_box((.008, .0035, .0015), garment.frame_at(p, n), p + n * .0012, STITCH,
                                         bevel=.0007, segs=1, name="tack"))
    return parts


def chest_pocket(surf, P):
    """a diagonal zip pocket on the left chest: welts each side, teeth, a pull"""
    parts = []
    a = Vector((.072, -.13, P.S.z - .085))
    b = Vector((.125, -.12, P.S.z - .215))
    pts = []
    for k in range(32):
        p = a.lerp(b, k / 31)
        pts.append(surf.on(p, Vector((.3, -1, 0)), .0))
    for off in (-.0055, .0055):
        w = garment.trim_strip(pts, .0045, COAT, offset=off, lift=.0016, tile=.03, step=.003, name="welt")
        if w:
            parts.append(w)
    parts += zip_line(pts, pull_at=2)
    return parts


def sleeve_pocket(surf, P):
    """left upper arm: a patch pocket with a flap, and an insignia patch with a light strip above it"""
    parts = []
    S, E = P.S, P.E
    ua = (E - S).normalized()
    mid = S + ua * .115
    out = Vector((0, -1, 0))
    out = (out - ua * out.dot(ua)).normalized()
    fr = surf.frame(mid + out * .06, out, down=ua)
    parts += panel(surf, fr, .085, .105, COAT, lift=.0020, thick=.0026, name="pocket")
    c, u, v, n = fr
    ff = surf.frame(c - v * .040, n, down=ua)
    parts += panel(surf, ff, .092, .040, COAT, lift=.0042, thick=.0030, lift_fn=lambda x, y: .002 * max(0.0, y), name="flap")
    parts += stud(surf, ff[0] + ff[2] * .008, n, .0048, .0075)
    ins = surf.frame(c - v * .090, n, down=ua)
    parts += panel(surf, ins, .060, .036, PATCH, lift=.0018, thick=.0022, k=4.0, name="insignia")
    gc, gu, gv, gn = ins
    parts.append(garment.rounded_box((.040, .0042, .0016), Matrix((gu, gv, gn)).transposed(), gc + gn * .0042, GLOW,
                                     bevel=.0012, segs=2, name="glow"))
    return parts


def elbow_patches(surf, P):
    parts = []
    for sx in (1, -1):
        E = P.mirror(P.E, sx)
        fa = P.mirror(P.fa, sx)
        ua = P.mirror(P.ua, sx)
        back = Vector((0, 1, -.25))
        back = (back - fa * back.dot(fa)).normalized()
        fr = surf.frame(E + fa * .030 + back * .06, back, down=fa)
        parts += panel(surf, fr, .085, .135, PATCH, lift=.0016, thick=.0022, k=3.0, name="elbow")
    return parts


def shoulder_patches(surf, P):
    parts = []
    for sx in (1, -1):
        S = P.mirror(P.S, sx)
        top = Vector((S.x * .97, S.y + .004, S.z + .040))
        fr = surf.frame(top, Vector((.45 * sx, 0, 1)), down=Vector((sx, 0, -.35)))
        parts += panel(surf, fr, .095, .075, PATCH, lift=.0018, thick=.0024, k=4.0, n=(16, 12), name="shoulder")
        c, u, v, n = fr
        R = Matrix((u, v, n)).transposed()
        parts.append(garment.rounded_box((.050, .016, .004), R, c + n * .0048 - v * .008, STEEL, bevel=.0016, segs=2,
                                         name="tab"))
        parts.append(garment.rounded_box((.034, .0045, .0016), R, c + n * .0072 - v * .008, GLOW, bevel=.0010, segs=2,
                                         name="glow"))
        for s in (-.020, .020):
            parts.append(garment.rivet(c + n * .0068 - v * .008 + u * s * 1.1, n, STEEL))
    return parts


def cuff_straps(surf, P):
    parts = []
    for sx in (1, -1):
        W = P.mirror(P.W, sx)
        fa = P.mirror(P.fa, sx)
        c = W - fa * .085
        out = Vector((0, -.2, 1))
        out = (out - fa * out.dot(fa)).normalized()
        side = fa.cross(out).normalized()
        pts = []
        for k in range(13):
            a = math.pi * (k / 12 - .5) * .95
            d = out * math.cos(a) + side * math.sin(a)
            q, n = surf.on(c + d * .06, d, .0)
            pts.append(q)
        strap, path = garment.strap(type("S", (), {"bvh": surf.tree})(), pts, .024, .0035, COAT, lift=.0028, name="cuff")
        parts.append(strap)
        q, n = path[len(path) // 2]
        parts.append(garment.snap(q + n * .0022, n, .0050, STEEL, name="stud"))
        q, n = path[2]
        parts.append(ring(q + n * .0018, n, .0050, .0012, STEEL))
    return parts


def half_belt(surf, P):
    z = P.zw + .022
    pts = []
    for k in range(17):
        x = -.092 + .184 * k / 16
        q, n = surf.on(Vector((x, .15, z)), Vector((0, 1, 0)), .0)
        pts.append(q)
    strap, path = garment.strap(type("S", (), {"bvh": surf.tree})(), pts, .042, .0045, COAT, lift=.0035, name="halfbelt")
    parts = [strap]
    for i in (1, len(path) - 2):
        q, n = path[i]
        parts += [garment.snap(q + n * .0026, n, .0060, STEEL, name="stud")]
    for off in (-.016, .016):
        st = garment.trim_strip([(q + n * .0026, n) for q, n in path], .0015, STITCH, offset=off, tile=.012, step=.003,
                                name="stitch")
        if st:
            parts.append(st)
    return parts


def build(o, P, log=print):
    surf = Surface(o)
    parts = []
    fns = (zip_halves, collar_tab, sleeve_pocket, cuff_straps) if P.crop else         (zip_halves, hood, collar_tab, hip_pockets, chest_pocket, sleeve_pocket, elbow_patches, shoulder_patches,
         cuff_straps, half_belt)
    for fn in fns:
        try:
            got = fn(surf, o, P) if fn is zip_halves else fn(surf, P)
        except Exception as e:                              # (a detail that fails must not lose the coat)
            import traceback
            traceback.print_exc()
            log(f"coat detail {fn.__name__} failed: {e}")
            continue
        got = [g for g in got if g is not None]
        for g in got:                                       # any face edge far longer than the part's own scale
            longest = max(((g.data.vertices[e.vertices[0]].co - g.data.vertices[e.vertices[1]].co).length
                           for e in g.data.edges), default=0)
            if longest > .06:
                log(f"coat detail {fn.__name__}: {g.name} has a {longest * 100:.1f} cm edge")
        parts += got
    return parts
