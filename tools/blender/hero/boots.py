"""The Orion combat boots, built on their own last (not the foot's skin pushed out, which follows the toes like a
slipper):

  last       measured from the body's foot and lower leg in slices (width and height at every point along the foot,
             the shin's section up the shaft) plus the room a boot needs, lofted, the foot and the shaft blended at
             the ankle, meshed as one smooth surface (Surface Nets, projected onto the exact field)
  upper      the last cut open at the top and along the lacing throat, given leather thickness; overlays stitched on:
             the toe cap, the heel counter, the quarters' seams; a padded collar rolled round the top, a pull loop
  closure    a gusseted tongue under the throat, eyelets up the lower eyestays and speed hooks up the shaft, a round
             lace criss-crossing between them, tied off at the top
  outsole    lofted from the boot's own footprint, a welt round it, a raised heel with its breast, toe spring, and a
             chevron lug tread cut into the bottom; a midsole band in a lighter rubber

Left boot built, the right one is its mirror image. Materials: orion_leather, orion_sole, orion_midsole, orion_lace,
orion_steel, orion_stitch, orion_cloth (the tongue's padding).
"""
import math
import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix
import sdf
import garment

F32 = np.float32
LEATHER, SOLE, MIDSOLE, LACE, STEEL, STITCH, TONGUE = ("orion_leather", "orion_sole", "orion_midsole", "orion_lace",
                                                        "orion_steel", "orion_stitch", "orion_cloth")


class Measure:
    """the left foot and lower leg from the body mesh: slices along the foot (y) and up the shin (z)"""

    def __init__(self, info, shaft_h):
        T = info.T
        F = info.F
        self.ank = F["ankle"]
        self.ball = F["ball"]
        bm = info.bm
        foot, shin = [], []
        for f, r in zip(bm.faces, info.face_region):
            for v in f.verts:
                if v.co.x <= 0:
                    continue
                if r == "foot":
                    foot.append(tuple(v.co))
                elif r == "shin" and v.co.z < self.ank.z + shaft_h + .04:
                    shin.append(tuple(v.co))
        self.foot = np.unique(np.array(foot, F32), axis=0)
        self.shin = np.unique(np.array(shin, F32), axis=0)
        self.toe_y = float(self.foot[:, 1].min())
        self.heel_y = float(self.foot[:, 1].max())
        self.cx = float(np.median(self.foot[:, 0]))
        self.top = self.ank.z + shaft_h
        # the throat (lacing) follows the front of the shin, not the foot's middle (the toes sit to the inside)
        self.tx = float(np.median(self.shin[:, 0])) if len(self.shin) else self.cx

    def foot_slices(self, n=14, ease_w=.008, ease_top=.009):
        """along the foot from the heel to the toe tip: t, centre x, half widths (lateral, medial), top"""
        ys = np.linspace(self.heel_y, self.toe_y, n)
        out = []
        low = self.foot[self.foot[:, 2] < self.ank.z - .018]    # behind the ankle the shaft covers the ankle bones;
        for y in ys:                                            # in front the foot keeps its full instep height
            P = low if y > self.ank.y - .015 else self.foot
            sel = P[np.abs(P[:, 1] - y) < .010]
            if len(sel) < 4:
                sel = P[np.argsort(np.abs(P[:, 1] - y))[:12]]
            xl, xm = sel[:, 0].max(), sel[:, 0].min()
            top = sel[:, 2].max()
            out.append((y, (xl + xm) / 2, (xl - xm) / 2 + ease_w, top + ease_top))
        return out

    def shin_slices(self, n=10, ease=.012):
        """the shaft: a straight tube on one axis, from the sole to the top. It is as wide and as deep in front as
        the widest measured section of the lower leg (it covers the ankle bones, never follows them in and out),
        and its back is one straight line from the heel up to the calf, so it has no waist, bulb or kink anywhere.
        Rows: z, centre x, centre y, half width, front depth, back depth"""
        P = self.shin
        meas = []
        for z in np.linspace(self.ank.z - .02, self.top, n):
            sel = P[np.abs(P[:, 2] - z) < .010]
            if len(sel) < 6:
                sel = P[np.argsort(np.abs(P[:, 2] - z))[:16]]
            meas.append((z, (sel[:, 0].max() + sel[:, 0].min()) / 2, (sel[:, 1].max() + sel[:, 1].min()) / 2,
                         (sel[:, 0].max() - sel[:, 0].min()) / 2, sel[:, 1].min(), sel[:, 1].max()))
        cx = float(np.mean([m[1] for m in meas]))
        cy = float(np.mean([m[2] for m in meas]))
        heel = self.foot[(self.foot[:, 1] > self.heel_y - .035) & (self.foot[:, 2] < self.ank.z - .018)]
        hw = ((heel[:, 0].max() - heel[:, 0].min()) / 2) if len(heel) else 0.0
        w = max(max(m[3] + abs(m[1] - cx) for m in meas), hw) + ease
        front = cy - min(m[4] for m in meas) + ease
        back_lo = self.heel_y + .013 - cy                    # (past the heel's skin by more than the leather)
        back_hi = max(max(m[5] for m in meas) - cy + ease, back_lo)
        z0, z1 = .012, self.top
        out = []
        for k in range(n):
            t = k / (n - 1)
            k_ = .93 + .07 * t                              # a gentle straight taper toward the ankle (no curve, no lump)
            out.append((z0 + (z1 - z0) * t, cx, cy, w * k_, front * (.96 + .04 * t), back_lo + (back_hi - back_lo) * t))
        return out


def last_sdf(M, sole_top):
    """the boot's last: the foot loft and the shaft loft, smoothly joined at the ankle"""
    FS = M.foot_slices()
    # a rounded toe: the last narrows over the last fifth instead of keeping the toes' spread to the tip
    n_ = len(FS)
    FS = [(y, c, w * math.sqrt(max(.60, 1 - max(0.0, (i / (n_ - 1) - .72) / .28) ** 2 * .45)), top)
          for i, (y, c, w, top) in enumerate(FS)]
    y0, y1 = FS[0][0] + .012, FS[-1][0] - .016             # (a little behind the heel, well beyond the toe tip)
    t = [(y0 - y) / (y0 - y1) for y, *_ in FS]
    zb = sole_top - .004
    cxs = [c for _, c, _, _ in FS]
    cx0 = sum(cxs) / len(cxs)
    foot = sdf.Loft((cx0, y0, zb), (cx0, y1, zb), dict(
        t=t,
        rv_pos=[w + max(0.0, c - cx0) for _, c, w, _ in FS],      # toward +x (the outside of the left foot)
        rv_neg=[w + max(0.0, cx0 - c) for _, c, w, _ in FS],
        rw_pos=[max(.020, top - zb) for _, _, _, top in FS],      # up
        rw_neg=[.006] * len(FS),
        cv=[0.0] * len(FS),
        n=[2.0] * len(FS), nb=[3.0] * len(FS)), v_axis=(1, 0, 0), cap=.95)
    SS = M.shin_slices()
    zs = [z for z, *_ in SS]
    a = (SS[0][1], SS[0][2], SS[0][0])
    b = (SS[-1][1], SS[-1][2], SS[-1][0] + .015)
    tt = [(z - zs[0]) / (zs[-1] + .015 - zs[0]) for z in zs]
    shaft = sdf.Loft(a, b, dict(
        t=tt,
        rv_pos=[w for *_, w, _, _ in SS], rv_neg=[w for *_, w, _, _ in SS],
        rw_pos=[bk for *_, bk in SS],                              # w = u x v: +y here (the back of the leg)
        rw_neg=[fr for *_, fr, _ in SS],
        n=[2.2] * len(SS)), v_axis=(1, 0, 0), cap=.2)
    # the heel counter's firm, round back and the ankle's bones under the leather
    heel = lambda P: sdf.ellipsoid(P, (M.cx, M.heel_y - .030, sole_top + .028), (.031, .024, .032))
    # (a tight blend: where the two surfaces run side by side a wide smooth-min swells them by up to k/4 - a bulb)
    return lambda P: sdf.smin(foot(P), shaft(P), .022)


HEEL_F = .030          # her boots' stacked heel (m below the flat sole); hero/female/motion.py stands her on it


def outsole_sdf(M, sole_top, welt=.0025, heel=0.0):
    """the outsole on the boot's own footprint: the last's outline where it meets the sole (traced round its centre)
    plus an even welt all round, so sole and upper read as one boot (flush at the heel, no ledge); a flat heel block,
    a barely lifted waist under the arch, a little toe spring, chevron lugs cut into the bottom"""
    zs = sole_top + .002
    ys = M.foot[:, 1]
    c = Vector((float(np.median(M.foot[:, 0])), float((ys.min() + ys.max()) / 2), zs))
    n_a = 240
    ang = np.linspace(-math.pi, math.pi, n_a, endpoint=False)
    rad = np.zeros(n_a)
    for i, a in enumerate(ang):
        d = np.array([math.cos(a), math.sin(a), 0.0], F32)
        lo, hi = 0.0, .25                                   # inside -> outside along the ray
        for _ in range(36):
            mid = (lo + hi) / 2
            if M.last(np.array([np.array(c, F32) + d * mid], F32))[0] < 0:
                lo = mid
            else:
                hi = mid
        rad[i] = (lo + hi) / 2 + welt
    for _ in range(3):                                      # (a smooth outline)
        rad = (np.roll(rad, 1) + 2 * rad + np.roll(rad, -1)) / 4
    angw = np.concatenate([ang - 2 * math.pi, ang, ang + 2 * math.pi])
    radw = np.concatenate([rad, rad, rad])
    y_heel, y_toe = float(ys.max()), float(ys.min())
    L = y_heel - y_toe
    toe_spring = .007

    def fn(P):
        dx, dy, z = P[:, 0] - c.x, P[:, 1] - c.y, P[:, 2]
        th = np.arctan2(dy, dx)
        out = np.sqrt(dx * dx + dy * dy) - np.interp(th, angw, radw)
        u = np.clip((y_heel - P[:, 1]) / L, 0, 1)            # 0 at the heel, 1 at the toe
        waist = sdf.smoothstep(.30, .36, u) * (1 - sdf.smoothstep(.52, .62, u))
        bot = -.003 + .0025 * waist + toe_spring * np.clip((u - .82) / .18, 0, 1) ** 2
        if heel:                                             # a stacked heel: a block under the heel, its breast at u ~ .27
            bot = bot - heel * (1 - sdf.smoothstep(.255, .285, u))
        slab = np.maximum(z - (sole_top + .002), bot - z)
        d = sdf.smax(out, slab, .0025)
        xs = np.abs(P[:, 0] - c.x)
        ph = ((P[:, 1] / .014 + xs * .9 / .014) % 1.0 - .5)
        groove = np.abs(ph) * .014 - .0028
        cut = np.maximum(groove, (z - (bot + .005)))
        return sdf.smax(d, -cut, .0008)
    return fn


def mesh_from(fn, lo, hi, h, name, mat):
    V, Q = sdf.mesh(fn, np.asarray(lo, F32), np.asarray(hi, F32), h, project_iters=3)
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(map(float, v))) for v in V]
    for q in Q:
        try:
            bm.faces.new([vs[i] for i in q])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm


def decimate(o, ratio):
    m = o.modifiers.new("dec", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = ratio
    m.use_collapse_triangulate = False
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=m.name)
    for p in o.data.polygons:
        p.use_smooth = True


def relax(bm, it=2, k=.5):
    for _ in range(it):
        P = {v: v.co.copy() for v in bm.verts}
        for v in bm.verts:
            if v.is_boundary or not v.link_edges:
                continue
            m = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
            v.co = P[v].lerp(m, k)


def build_left(info, m=True, log=print):
    from coat import bisect, keep_largest, orient_out, thick
    from wardrobe import to_object, material
    from coat_details import Surface, panel, ring
    shaft_h = .145 if m else .165
    M = Measure(info, shaft_h)
    sole_top = .017
    last = last_sdf(M, sole_top)
    M.last = last
    lo = (M.cx - .09, M.toe_y - .05, -.01)
    hi = (M.cx + .09, M.heel_y + .06, M.top + .04)
    bm = mesh_from(last, lo, hi, .0026, "upper", LEATHER)
    relax(bm, 2, .4)
    # the opening at the top, the bottom under the sole, the lacing throat
    bisect(bm, bm.faces[:], (0, 0, M.top), (0, 0, 1), clear=True)
    bisect(bm, bm.faces[:], (0, 0, sole_top - .002), (0, 0, -1), clear=True)
    z_throat = M.ank.z + .005 if m else M.ank.z + .015          # the lacing starts over the instep
    y_front = M.ank.y - .015
    throat_w = .0085
    front = lambda f: f.calc_center_median().y < y_front and f.calc_center_median().z > z_throat - .03
    keep_tongue = [tuple(v.co) for f in bm.faces if front(f) and abs(f.calc_center_median().x - M.cx) < .030
                   and f.calc_center_median().z > z_throat - .012 for v in f.verts]
    bisect(bm, [f for f in bm.faces if front(f)], (M.tx - throat_w, 0, 0), (1, 0, 0))
    bisect(bm, [f for f in bm.faces if front(f)], (M.tx + throat_w, 0, 0), (1, 0, 0))
    bisect(bm, [f for f in bm.faces if front(f)], (0, 0, z_throat), (0, 0, 1))
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if front(f) and abs(f.calc_center_median().x - M.tx) < throat_w
                               and f.calc_center_median().z > z_throat], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    keep_largest(bm)
    bm.normal_update()
    o = to_object(bm, "boot", LEATHER)
    decimate(o, .12)                                          # (Surface Nets is dense: keep the shape, lose the excess)
    o.data.materials.append(material(TONGUE))                 # (the inside: the lining)
    thick(o, .0032)
    import fabric
    fabric.world_uvs(o, fabric.TILE.get("leather", .06))
    parts = [o]
    surf = Surface(o)
    parts += overlays(o, M, sole_top, surf)
    parts += collar(M, surf)
    parts += closure(M, surf, z_throat, throat_w, y_front, m)
    # the outsole and its midsole band
    heel = 0.0 if m else HEEL_F
    sole_fn = outsole_sdf(M, sole_top, heel=heel)
    sb = mesh_from(sole_fn, (M.cx - .09, M.toe_y - .05, -.012 - heel), (M.cx + .09, M.heel_y + .05, sole_top + .01), .0018,
                   "sole", SOLE)
    so = to_object(sb, "sole", SOLE)
    decimate(so, .12)
    fabric.world_uvs(so, .06)
    parts.append(so)
    parts += midsole_band(so, sole_top)
    return parts


def overlays(o, M, sole_top, surf):
    """the toe cap and the heel counter: the upper's outer surface beyond a clean cut line, a layer proud of it,
    stitched round"""
    from coat import bisect, keep_largest
    from coat_details import solid
    out = []
    cuts = [                                                # (keep side: the plane's -no side)
        ("toecap", (0, M.ball.y - .012, sole_top + .030), (0, 1, .55)),
        ("heelcounter", (0, M.heel_y - .058, sole_top + .052), (0, -1, .75)),
    ]
    for name, co, no in cuts:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != 0], context='FACES')
        bm.normal_update()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z < sole_top + .001], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bisect(bm, bm.faces[:], co, no, clear=True)
        if not bm.faces:
            bm.free()
            continue
        keep_largest(bm)
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * .0007                        # (a thin overlay: the boot still reads as one piece)
        chains = garment.boundary_chains(bm, test=lambda c: c.z > sole_top + .004)
        ob = garment.obj(bm, name, LEATHER)
        decimate(ob, .30)
        solid(ob, .0012)
        out.append(ob)
        for ch in chains:
            pts = garment.smooth_chain([(p + n * .0002, n) for p, n in ch], 3)
            st = inset(ob, pts, .0035)
            if st:
                out.append(st)
    return out


def inset(o, chain, d):
    from coat import inset_strip
    return inset_strip(o, chain, d, STITCH)


def collar(M, surf):
    """a padded collar rolled round the top of the shaft, and the pull loop at the back"""
    out = []
    bm = bmesh.new()
    seg, sides = 48, 10
    rings = []
    z = M.top - .0035
    # the top edge's outline: sample the upper's rim
    cx, cy = M.tx, M.ank.y + .005
    for i in range(seg):
        a = 2 * math.pi * i / seg
        d = Vector((math.cos(a), math.sin(a), 0))
        q, n = surf.on(Vector((cx, cy, z)) + d * .07, d, 0.0)
        r = (Vector((q.x, q.y, 0)) - Vector((cx, cy, 0))).length
        ring_ = []
        for j in range(sides):
            b = 2 * math.pi * j / sides
            rr = r - .0006 + .0030 * math.cos(b)
            ring_.append(bm.verts.new((cx + d.x * rr, cy + d.y * rr, z + .0042 * math.sin(b))))
        rings.append(ring_)
    for i in range(seg):
        A, B = rings[i], rings[(i + 1) % seg]
        for j in range(sides):
            bm.faces.new((A[j], A[(j + 1) % sides], B[(j + 1) % sides], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out.append(garment.obj(bm, "collar", LEATHER))
    # pull loop: a webbing loop standing up at the back
    back, n = surf.toward(Vector((cx, cy + .40, M.top - .032)), Vector((0, -1, 0)))
    if back is None:
        return out
    loop = []
    for k in range(17):
        t = k / 16                                          # up the shaft's back, over the collar by 1.5 cm, lying close
        z = -.004 + .050 * t
        off = .0022 + .0018 * math.sin(math.pi * min(1.0, t * 1.25))
        loop.append((back + Vector((0, 0, z)) + n * off, n))
    s = garment.trim_strip(loop, .016, "orion_strap", lift=.0, tile=.05, step=.003, name="pullloop")
    if s:
        from coat_details import solid
        solid(s, .0022)
        out.append(s)
    return out


def closure(M, surf, z_throat, w, y_front, m):
    """tongue, eyelets, speed hooks and the lace"""
    out = []
    # the tongue: a padded strip under the throat, its top standing a little above the collar
    pts_l, pts_r = [], []
    n_e, n_h = (5, 3) if m else (6, 3)
    z0, z1 = z_throat + .010, M.top - .010
    zs = [z0 + (z1 - z0) * k / (n_e + n_h - 1) for k in range(n_e + n_h)]
    cx = M.tx
    # the tongue: a padded panel under the throat following the boot's own front (sampled off the last across its
    # width, set in behind the leather), its top standing a little above the collar
    nz, nx = 20, 8
    W = w + .010
    grid = []
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for k in range(nz + 1):
        z = z_throat - .012 + (M.top + .012 - z_throat + .012) * k / nz
        row = []
        for i in range(nx + 1):
            x = cx - W + 2 * W * i / nx
            q = last_front(M.last, x, min(z, M.top - .002), y_front - .12, M.ank.y)
            if z > M.top - .002:                           # above the collar: carried straight up
                q = Vector((q.x, q.y - .002, z))
            dx = .002
            qa = last_front(M.last, x + dx, min(z, M.top - .002), y_front - .12, M.ank.y)
            qb = last_front(M.last, x, min(z, M.top - .002) + dx, y_front - .12, M.ank.y)
            n = (qa - q).cross(qb - q).normalized()
            if n.y > 0:
                n = -n
            # padded: it bulges forward into the throat (laces rest on it) and runs in under the leather each side
            depth = .0008 + .0040 * (abs(x - cx) / W) ** 2
            row.append((bm.verts.new(q - n * depth), (i / nx, k / nz * 2)))
        grid.append(row)
    for k in range(nz):
        for i in range(nx):
            f = bm.faces.new((grid[k][i][0], grid[k][i + 1][0], grid[k + 1][i + 1][0], grid[k + 1][i][0]))
            for loop, (a_, b_) in zip(f.loops, ((i, k), (i + 1, k), (i + 1, k + 1), (i, k + 1))):
                loop[uvl].uv = grid[b_][a_][1]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    if sum(f.normal.y for f in bm.faces) > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    t_obj = garment.obj(bm, "tongue", TONGUE)
    from coat_details import solid
    solid(t_obj, .0035)
    out.append(t_obj)
    for side in (1, -1):
        holes = []
        for i, z in enumerate(zs):
            q, n = surf.toward(Vector((cx + side * (w + .0055), M.ank.y - .40, z)), Vector((0, 1, 0)), .0004)
            if q is None:                                   # (straight in from the front: right at the throat's edge)
                continue
            holes.append((q, n, i >= n_e))
            if i < n_e:                                     # an eyelet: a ring through the leather
                from coat_details import ring
                out.append(ring(q, n, .0032, .0011, STEEL, seg=12, sides=4))
            else:                                           # a speed hook: a post and an open hook
                R = garment.frame_at(q, n)
                out.append(garment.rounded_box((.0040, .0040, .0050), R, q + n * .0025, STEEL, bevel=.0012, segs=2,
                                               name="hookpost"))
                out.append(garment.rounded_box((.0090, .0030, .0022), R, q + n * .0055 + R @ Vector((-side * .003, 0, 0)),
                                               STEEL, bevel=.0010, segs=2, name="hook"))
        (pts_l if side > 0 else pts_r).extend(holes)
    # the lace: from each eyelet across to the next one up on the other side, over the tongue
    path = []
    for i in range(len(zs) - 1):
        a = pts_l[i] if i % 2 == 0 else pts_r[i]
        b = pts_r[i + 1] if i % 2 == 0 else pts_l[i + 1]
        for k in range(9):
            s = k / 8
            n = (a[1] + b[1]).normalized()                  # (straight across the throat: no ray, it would go in)
            path.append(a[0].lerp(b[0], s) + n * (.0016 + .0012 * math.sin(math.pi * s)))
    out.append(lace_tube(path, .0018, "lace"))
    path2 = []
    for i in range(len(zs) - 1):
        a = pts_r[i] if i % 2 == 0 else pts_l[i]
        b = pts_l[i + 1] if i % 2 == 0 else pts_r[i + 1]
        for k in range(9):
            s = k / 8
            n = (a[1] + b[1]).normalized()
            path2.append(a[0].lerp(b[0], s) + n * (.0022 + .0016 * math.sin(math.pi * s)))
    out.append(lace_tube(path2, .0018, "lace"))
    # tied off at the top: a knot and two loops hanging down the front
    top = (pts_l[-1][0] + pts_r[-1][0]) / 2
    knot, kn = surf.on(top, Vector((0, -1, .3)), .006)
    for side in (1, -1):
        # the bow's loops lie against the boot, out to the side and down a little; short tails
        loop = []
        for k in range(13):
            a = 2 * math.pi * k / 12
            loop.append(knot + Vector((side * (.011 * (1 - math.cos(a)) / 2 + .002), -.002 - .0015 * math.sin(a),
                                       -.006 * (1 - math.cos(a)) / 2 + .005 * math.sin(a))))
        out.append(lace_tube(loop, .0016, "lace"))
        tail = [knot + Vector((side * .003 * k / 6, -.0025, -.016 * k / 6)) for k in range(7)]
        out.append(lace_tube(tail, .0015, "lace"))
    out.append(garment.rounded_box((.007, .006, .006), garment.frame_at(knot, kn), knot, LACE, bevel=.0025, segs=2,
                                   name="knot"))
    return out


def last_front(fn, x, z, y_out, y_in, it=40):
    """the last's front surface at (x, z): bisection along y between a point outside and one inside"""
    lo, hi = y_out, y_in
    for _ in range(it):
        mid = (lo + hi) / 2
        if fn(np.array([[x, mid, z]], F32))[0] > 0:
            lo = mid
        else:
            hi = mid
    return Vector((x, (lo + hi) / 2, z))


def lace_tube(pts, r, name, sides=6):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings = []
    L = 0.0
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
        if t.length < 1e-9:
            t = Vector((0, 0, 1))
        t.normalize()
        a = t.cross(Vector((0, 0, 1)) if abs(t.z) < .9 else Vector((1, 0, 0))).normalized()
        b = t.cross(a)
        if i:
            L += (p - pts[i - 1]).length
        rings.append(([bm.verts.new(p + (a * math.cos(2 * math.pi * j / sides) + b * math.sin(2 * math.pi * j / sides)) * r)
                       for j in range(sides)], L / .02))
    for (A, va), (B, vb) in zip(rings, rings[1:]):
        for j in range(sides):
            f = bm.faces.new((A[j], A[(j + 1) % sides], B[(j + 1) % sides], B[j]))
            for loop, (u, v) in zip(f.loops, ((j / sides, va), ((j + 1) / sides, va), ((j + 1) / sides, vb), (j / sides, vb))):
                loop[uvl].uv = (u, v)
    bm.faces.new(rings[0][0][::-1])
    bm.faces.new(rings[-1][0])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return garment.obj(bm, name, LACE)


def midsole_band(so, sole_top):
    """the band of lighter rubber round the sole just under the upper: the sole's own faces there take the midsole
    material (no second skin, so no edges or spikes of its own)"""
    from wardrobe import material
    me = so.data
    me.materials.append(material(MIDSOLE))
    k = len(me.materials) - 1
    for p in me.polygons:
        if sole_top - .0075 < p.center.z < sole_top - .0012 and abs(p.normal.z) < .75:
            p.material_index = k
    return []


def build(info, log=print):
    """both boots (the right one mirrored), joined by the caller"""
    left = build_left(info, info.m, log=log)
    right = []
    for p in left:
        c = p.copy()
        c.data = p.data.copy()
        bpy.context.scene.collection.objects.link(c)
        me = c.data
        for v in me.vertices:
            v.co.x = -v.co.x
        me.flip_normals()
        right.append(c)
    return left + right
