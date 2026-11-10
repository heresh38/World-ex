"""Head armour for the hero bodies (the optional `head` slot): built on each body's own head, nothing shared.

  helmet    a full sealed helmet in the Orion style, covering the whole head and the neck down into the collar.
            While it is worn the hair is hidden (both bodies are bald under it) and so is the head's skin, so
            nothing can show through; the hair comes back when it comes off. It is modelled as signed distances
            (sdf.py, meshed with Surface Nets) on this body's measured head:
              base     the inner helmet: the cranium (an ellipsoid fitted to this skull) grown out, the face and jaw
                       volume, a ribbed flexible neck seal flaring into the collar (matte black)
              plates   each one a thin layer of the base surface cut to its outline (so it hugs the helmet exactly
                       and its edges are crisp): two crown plates either side of a raised crest, cheek plates, a
                       faceplate with vent slots, stepped ear plates, overlapping lames over the back of the neck.
                       His in the steel-grey polymer of his armour, squarer, a heavy crest; hers in the white of her
                       jacket, slimmer, a tapered faceplate, a swept fin
              visor    a dark mirrored band across the eyes, wrapping to the temples, in a raised steel frame, with
                       light strips under it and a light ring in each ear plate
  headset   comms: two oval ear cups with cushions, a padded band over the crown clearing the hair, sliders, a boom
            mic from the left cup to the corner of the mouth, a status light. The hair stays.
Both are rigid (bound to the head bone only; see wardrobe.dress).
"""
import math
import bmesh
import numpy as np
from mathutils import Vector, Matrix
import garment

STEEL, GLOW, CUP, PAD = "orion_steel", "orion_glow", "orion_plate", "orion_leather"
BASE, VISOR = "orion_black", "orion_visor"
F32 = np.float32


# ------------------------------------------------------------------------------------------------ the cranium

def cranium(info):
    """an axis-aligned ellipsoid (centre, radii) fitted to the vault of the skull (algebraic least squares on the head
    vertices above the brow, x centred by symmetry)"""
    T = info.T
    ez = T["eye_z"]
    P = []
    for f, r in zip(info.bm.faces, info.face_region):
        if r != "head":
            continue
        for v in f.verts:
            c = v.co
            if c.z > ez + .025 and not (abs(c.x) > .058 and c.z < ez + .05):      # the vault, clear of the ears
                P.append((c.x, c.y, c.z))
    P = np.unique(np.array(P), axis=0)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    A = np.stack([x * x, y * y, z * z, y, z], 1)
    sol, *_ = np.linalg.lstsq(A, np.ones(len(P)), rcond=None)
    a, b, c, d, e = sol
    cy, cz = -d / (2 * b), -e / (2 * c)
    k = 1 + b * cy * cy + c * cz * cz
    rx, ry, rz = math.sqrt(k / a), math.sqrt(k / b), math.sqrt(k / c)
    return Vector((0.0, cy, cz)), Vector((rx, ry, rz))




def head_measures(info):
    """what the helmet is built round: the cranium ellipsoid, the eyes, chin and neck (radius and line)"""
    T = info.T
    c, r = cranium(info)
    ez, cz, nz = T["eye_z"], T["chin_z"], T["neck_base_z"]
    zm = (cz - .03 + nz) / 2                      # the neck half way between the chin and its base
    rad = []
    for a in range(0, 360, 30):
        d = Vector((math.sin(math.radians(a)), -math.cos(math.radians(a)), 0))
        hit, _, _, _ = info.bvh.ray_cast(Vector((0, .02, zm)) + d * .3, -d, .3)
        if hit is not None:
            rad.append((hit - Vector((0, .02, zm))).length)
    neck_r = float(np.median(rad)) if rad else .06
    front = {}
    for key, z in (("nose", ez - .034), ("mouth", ez - .068), ("chin", cz + .020)):
        hit, _, _, _ = info.bvh.ray_cast(Vector((0, -.4, z)), Vector((0, 1, 0)), .6)
        front[key] = float(hit.y) if hit is not None else float(c[1] - r[1])
    return dict(c=np.array(c, F32), r=np.array(r, F32), ez=ez, cz=cz, nz=nz, neck_r=neck_r, neck_y=.02, front=front)


def helmet_layout(M, m):
    """the helmet's base surface (a signed distance) and its plates: (name, region, lift, thickness, material, bevel)
    with each region a signed distance over the base surface (negative inside the plate)"""
    import sdf
    c, r, ez, cz, nz, nr = M["c"], M["r"], M["ez"], M["cz"], M["nz"], M["neck_r"]
    ny = M["neck_y"]
    g = .026 if m else .022                                       # clearance over the skull (pads and liner): close
    face_c = np.array((0, c[1] - (.020 if m else .016), (ez + cz) / 2 - .005), F32)
    fr = M["front"]
    nose_y = min(fr["nose"], fr["mouth"]) - .017                  # the shell's front: clear of the nose's tip and the lips
    chin_y = fr["chin"] - .016

    def base(P, ribs=True):
        dome = sdf.ellipsoid(P, c, r + g)
        if m:                                                     # his: a muzzle that narrows to the chin, not a bucket
            cyb = float(face_c[1] - .004)
            face = sdf.round_box(P, np.array((0, cyb, face_c[2] - .010), F32),
                                 (r[0] * .74 + .016, cyb - nose_y, (ez - cz) / 2 + .050), .044)
            jaw = sdf.round_cone(P, np.array((0, cyb, ez - .040), F32), np.array((0, chin_y + .046, cz - .012), F32), r[0] * .74 + .014, .046)
            face = sdf.smin(sdf.smax(face, cz - .030 - P[:, 2] + .0 * P[:, 0], .02), jaw, .03)
        else:                                                     # hers: tapering to a small chin
            rc = .040
            face = sdf.round_cone(P, face_c + np.array((0, .006, .040), F32), np.array((0, chin_y + rc, cz - .006), F32),
                                  r[0] * .80 + .016, rc)
            face = sdf.smin(face, sdf.ellipsoid(P, np.array((0, nose_y + .030, ez - .045), F32), (.045, .030, .050)), .03)
        head = sdf.smin(dome, face, .045)
        z = P[:, 2]
        neck = sdf.round_cone(P, np.array((0, ny, cz - .005), F32), np.array((0, ny + .006, nz - .035), F32), nr + .020, nr + .036)
        if ribs:                                                  # the flexible seal's ribs (not under the plates)
            neck = neck + .0018 * np.sin((z - nz) / .0110 * 2 * np.pi) * sdf.smoothstep(nz - .03, nz - .02, z) * (1 - sdf.smoothstep(cz - .045, cz - .030, z))
        return sdf.smin(head, neck, .030)

    def az(P):
        return np.arctan2(P[:, 0], -(P[:, 1] - c[1]))

    R_ = float((r[0] + r[1]) / 2 + g)
    rad = math.radians

    def band(P, z0, z1, a0, a1):
        a = np.abs(az(P))
        return np.maximum.reduce([z0 - P[:, 2], P[:, 2] - z1, (a - a1) * R_, (a0 - a) * R_])

    # ---- clean and sleek, made to go with the outfit: a close smooth shell and a peak over the eyes like a hood's
    # edge, swept guards along the jaw, three lames at the nape, a slim spine in the lining's blue, one line of light
    # under the brow. No vents, discs or sensors.
    #   his   tactical, for the black coat: a level visor band wrapped round the eyes down to the nose, under it a
    #         mandible guard in two chamfered steps with a breather, a rail along each temple
    #   hers  ONE face shield from the brow to the chin, full and rounded, for the white jacket
    z_top = ez + (.020 if m else .028)
    z_bot = (ez - .036) if m else (cz + .012)
    a_top, a_bot = rad(72 if m else 70), rad(72 if m else 25)     # (his a level band: no taper)

    def mand_w(P):
        """his mandible guard's half width: the same all the way down (every edge of his plates runs level or upright:
        cut on a slant, a plate's edge comes out in steps)"""
        return np.full(len(P), rad(46), F32)

    def shield_w(P):
        t = np.clip((z_top - P[:, 2]) / (z_top - z_bot), 0, 1)
        return a_top + (a_bot - a_top) * t ** (1.5 if m else 2.3)

    def visor(P, grow=0.0):
        zc, hh = (z_top + z_bot) / 2, (z_top - z_bot) / 2
        return sdf.smax(np.abs(P[:, 2] - zc) - (hh + grow), (np.abs(az(P)) - shield_w(P)) * R_ - grow, .006 if m else .014)

    crest_w = .0050 if m else .0042
    crest_end = float(c[1] + r[1] * (.72 if m else .85))
    plate_mat = "orion_plate" if m else "orion_plate_white"
    P_ = []                                                       # (name, region, lift, thick, material, bevel)
    # the crown, either side of the spine, down to the peak in front and the lames behind
    P_.append(("crown", lambda P: np.maximum.reduce([z_top + .006 - P[:, 2], crest_w + .004 - np.abs(P[:, 0]),
                                                     -visor(P, .006)]), .002, .0055, plate_mat, .0018))
    # the peak over the shield, round to the temples (the edge of a hood)
    P_.append(("brow", lambda P: np.maximum.reduce([z_top + .003 - P[:, 2], P[:, 2] - (z_top + (.022 if m else .016)),
                                                    (np.abs(az(P)) - a_top * 1.10) * R_]), .0100 if m else .0060, .0050, plate_mat, .0018))
    P_.append(("back", lambda P: np.maximum(band(P, cz + .050, z_top + .004, rad(116), rad(181)), -visor(P, .006)),
               .002, .0055, plate_mat, .0018))
    # the jaw guards: from the shield's edge back to the nape, rising toward the ear
    def guard(P):
        a = np.abs(az(P))
        # (his is cut square, level under the visor: slanted edges crossing at a sharp angle leave a saw's teeth)
        top = (z_bot - .005) if m else z_top - .010 - .030 * np.clip((rad(112) - a) / rad(60), 0, 1)
        inner = mand_w(P) + rad(1) if m else shield_w(P)
        return np.maximum.reduce([cz + .002 - P[:, 2], P[:, 2] - top, (inner + rad(5) - a) * R_, (a - rad(114)) * R_])
    P_.append(("cheek", guard, .0045, .0055, plate_mat, .0018))
    if m:
        mand = lambda P, g_=0.0: np.maximum.reduce([cz - .004 - P[:, 2], P[:, 2] - (z_bot - .005), (np.abs(az(P)) - mand_w(P)) * R_]) + g_
        P_.append(("mandible", lambda P: mand(P), .0060, .0065, plate_mat, .0028))
        # its raised centre, coming to the chin
        P_.append(("muzzle", lambda P: np.maximum(mand(P, .007), (np.abs(az(P)) - mand_w(P) * .52) * R_), .0125, .0045, plate_mat, .0024))
        P_.append(("breather", lambda P: np.maximum.reduce([np.abs(P[:, 2] - (cz + .030)) - .0085, (np.abs(az(P)) - rad(8)) * R_]),
                   .0170, .0030, "orion_steel", .0012))
        # a rail along each temple, behind the visor's end
        P_.append(("rail", lambda P: np.maximum.reduce([np.abs(P[:, 2] - (ez + .004)) - .0085, (rad(a_top / rad(1) + 6) - np.abs(az(P))) * R_,
                                                       (np.abs(az(P)) - rad(122)) * R_]), .0085, .0050, "orion_steel", .0022))
    for k, (z0, z1) in enumerate(((cz + .014, cz + .048), (cz - .018, cz + .018), (cz - .050, cz - .014))):
        P_.append((f"lame{k}", lambda P, z0=z0, z1=z1: band(P, z0, z1, rad(112), rad(181)), .004 + .0045 * k, .0055, plate_mat, .0016))
    P_.append(("crest", lambda P: np.maximum.reduce([np.abs(P[:, 0]) - crest_w, z_top + .012 - P[:, 2], P[:, 1] - crest_end]),
               .004, .0060 if m else .0048, plate_mat, .0016))
    # the shield: the lens a little proud of the base in a slim dark frame; the light under the peak
    P_.append(("visor", lambda P: visor(P), .0015, .0040, VISOR, .0012))
    P_.append(("visorframe", lambda P: np.abs(visor(P) + .0014) - .0022, .0032, .0052, "orion_steel", .0010))
    P_.append(("browlight", lambda P: np.maximum(np.abs(P[:, 2] - (z_top - .0075)) - .0008, (np.abs(az(P)) - a_top * .66) * R_),
               .0056, .0010, "orion_glow", .0003))
    if m:                                                         # his: the coat's slanted light, once, on the left guard
        P_.append(("guardlight", lambda P: np.maximum.reduce([
            np.abs(P[:, 2] - (ez - .034) - (az(P) - rad(86)) * R_ * .85) - .0011, (rad(74) - az(P)) * R_, (az(P) - rad(98)) * R_]),
            .0092, .0012, "orion_glow", .0004))
    else:                                                         # hers: a short line under the shield's point
        P_.append(("chinlight", lambda P: np.maximum(np.abs(P[:, 2] - (z_bot - .0070)) - .0009, (np.abs(az(P)) - rad(9)) * R_),
                   .0056, .0010, "orion_glow", .0003))
    return base, P_, dict(lens=[], ears=[], vents=[], plate=plate_mat, front_y=float(c[1] - r[1] - g))


def relax_on(bm, fn, iters=16, k=.6):
    """tangential relaxation of a Surface Nets mesh, re-projected onto the exact surface each pass: an even,
    smoothly shading tessellation (Surface Nets alone leaves stair rows that show as rings in the shading)"""
    import sdf
    bm.verts.ensure_lookup_table()
    V = np.array([v.co[:] for v in bm.verts], F32)
    nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    border = np.array([v.is_boundary for v in bm.verts])
    for _ in range(iters):
        avg = np.array([V[n].mean(0) if n else V[i] for i, n in enumerate(nbr)], F32)
        Nn = sdf.normals(fn, V)
        d = avg - V
        d -= Nn * (d * Nn).sum(1)[:, None]                    # along the surface only
        V = np.where(border[:, None], V, V + d * k)
        V = sdf.project(fn, V, 3)
    for v, p in zip(bm.verts, V):
        v.co = Vector(p.tolist())
    bm.normal_update()


def cut_plate(base_bm, tree, region, lift, thick, mat, name, bevel, keep=.45, field=None):
    """a plate laid on the base surface: the base faces inside `region`, their open edges slid exactly onto the
    region's outline along the surface (then smoothed), lifted by `lift`, given `thick` and a chamfered rim"""
    from wardrobe import to_object
    from boots import decimate
    bm = base_bm.copy()
    bm.verts.ensure_lookup_table()
    co = np.array([v.co[:] for v in bm.verts], F32)
    rv = region(co)
    drop = [f for f in bm.faces if np.mean([rv[v.index] for v in f.verts]) > 0]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    # (slivers: faces hanging by two open edges)
    for _ in range(2):
        bad = [f for f in bm.faces if sum(1 for e in f.edges if e.is_boundary) >= 2]
        if not bad:
            break
        bmesh.ops.delete(bm, geom=bad, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    if not bm.faces:
        bm.free()
        return None
    e = 2e-4

    def grad(P):
        G = np.zeros_like(P)
        for k in range(3):
            d = np.zeros(3, F32)
            d[k] = e
            G[:, k] = (region(P + d) - region(P - d)) / (2 * e)
        return G

    # only the edge that lies on the outline moves (the base's own open edge at the neck stays where it is); each
    # step along the surface is capped at two cells, so a weak or kinked gradient can never throw a point away
    edge = [v for v in bm.verts if v.is_boundary and abs(float(region(np.array([v.co[:]], F32))[0])) < .006]
    cap = .006
    for it in range(10):
        P = np.array([v.co[:] for v in edge], F32)
        if not len(P):
            break
        val = region(P)
        G = grad(P)
        for v, d, g_ in zip(edge, val, G):
            _, n, _, _ = tree.find_nearest(v.co)
            gv = Vector(g_)
            gt = gv - n * gv.dot(n)
            if gt.length_squared > .04:                         # (|gradient| > .2: a usable direction)
                step = gt * (float(d) / gt.length_squared) * .8
                if step.length > cap:
                    step *= cap / step.length
                v.co -= step
            loc, _, _, _ = tree.find_nearest(v.co)
            v.co = loc
        if it in (2, 4, 6):                                       # smooth along the outline, then snap again
            new = {}
            for v in edge:
                nb = [x.other_vert(v) for x in v.link_edges if x.is_boundary]
                if len(nb) == 2:
                    new[v] = v.co * .5 + (nb[0].co + nb[1].co) * .25
            for v, p in new.items():
                v.co = tree.find_nearest(p)[0]
    # anything that would not settle on the outline goes (its faces would be a ragged tab)
    far = [v for v in edge if abs(float(region(np.array([v.co[:]], F32))[0])) > .004]
    if far:
        bmesh.ops.delete(bm, geom=list({f for v in far for f in v.link_faces}), context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    if not bm.faces:
        bm.free()
        return None
    bm.verts.ensure_lookup_table()
    P = np.array([v.co[:] for v in bm.verts], F32)
    if field is not None:                                        # lifted along the field's smooth normal
        import sdf
        Nn = sdf.normals(field, P)
    else:
        Nn = np.array([tree.find_nearest(v.co)[1][:] for v in bm.verts], F32)
    for v, p, n in zip(bm.verts, P, Nn):
        v.co = Vector((p + n * lift).tolist())
    o = to_object(bm, name, mat)
    if keep < 1.0:
        decimate(o, keep)
    m = o.modifiers.new("solid", 'SOLIDIFY')
    m.thickness = thick
    m.offset = 1.0
    m.use_rim = True
    m.use_even_offset = False      # (even thickness spikes at sharp corners; a clamp would ripple it with edge length)
    b = o.modifiers.new("chamfer", 'BEVEL')
    b.width = bevel
    b.segments = 2
    b.limit_method = 'ANGLE'
    import bpy
    b.angle_limit = math.radians(40)
    bpy.context.view_layer.objects.active = o
    for md in (m, b):
        bpy.ops.object.modifier_apply(modifier=md.name)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def helmet(info, log=print):
    from wardrobe import to_object
    from boots import mesh_from, decimate
    from mathutils.bvhtree import BVHTree
    import fabric
    m = info.m
    M = head_measures(info)
    base_fn, plates, extra = helmet_layout(M, m)
    c, r = M["c"], M["r"]
    lo = (-r[0] - .09, c[1] - r[1] - .09, M["nz"] - .07)
    hi = (r[0] + .09, c[1] + r[1] + .09, c[2] + r[2] + .07)
    parts = []
    seal = mesh_from(base_fn, lo, hi, .0030, "base", BASE)          # the visible inner helmet with the ribbed seal
    o = to_object(seal, "helmet_base", BASE)
    decimate(o, .40)
    parts.append(o)
    # the plates are cut from the smooth base (no ribs) on an even grid, never decimated (no faceting in them)
    smooth_fn = lambda P: base_fn(P, ribs=False)
    base_bm = mesh_from(smooth_fn, lo, hi, .0038, "cut", BASE)
    relax_on(base_bm, smooth_fn)
    tree = BVHTree.FromBMesh(base_bm)
    for name, region, lift, thick, mat, bevel in plates:
        o = cut_plate(base_bm, tree, region, lift, thick, mat, "helmet_" + name, bevel, 1.0, field=smooth_fn)
        if o is not None:
            parts.append(o)
    from coat_details import tube
    import sdf as sdfm
    # ear plates: a turned disc in two steps with a light ring and a steel cap, set square on the surface
    for ep, rr in extra["ears"]:
        loc, n, _, _ = tree.find_nearest(Vector(ep.tolist()))
        n = Vector(sdfm.normals(smooth_fn, np.array([loc[:]], F32))[0].tolist())
        parts.append(oval_cup(loc - n * .004, n, rr * 2, rr * 2, .011, extra["plate"], n=64, edge=.004))
        parts.append(oval_cup(loc + n * .006, n, rr * 1.30, rr * 1.30, .008, "orion_steel", n=64, edge=.003))
        R_ = garment.frame_at(loc, n)
        ring = [loc + n * .0075 + R_ @ Vector((x, y, 0)) for x, y in oval(rr * 1.56, rr * 1.56, 64, k=2.0)]
        parts.append(tube(ring + ring[:1], .0014, "orion_glow", name="earlight", sides=6))
        parts.append(oval_cup(loc + n * .013, n, rr * .55, rr * .55, .004, "orion_steel", n=48, edge=.002))
    # the faceplate's vent slats: raised steel bars across the mouth
    for z, w in extra["vents"]:
        p = Vector((0.0, extra["front_y"] - .05, z))
        hit, n, _, _ = tree.ray_cast(p, Vector((0, 1, 0)), .2)
        if hit is None:
            continue
        side = Vector((0, 0, 1)).cross(n).normalized()
        Rm = Matrix((side, n.cross(side).normalized(), n)).transposed()
        parts.append(garment.rounded_box((w, .0050, .0070), Rm, hit + n * .0125, "orion_steel", bevel=.0020, segs=2, name="slat"))
    # the temple sensors' lenses
    for p, sx in extra["lens"]:
        loc, n, _, _ = tree.find_nearest(Vector(p))
        for k, dz in enumerate((.005, -.004)):
            cc = loc + n * .0145 + Vector((0, 0, dz))
            R = garment.frame_at(cc, n)
            parts.append(garment.rounded_box((.0065, .0065, .003), R, cc, VISOR if k == 0 else "orion_glow", bevel=.0028, segs=3, name="lens"))
    base_bm.free()
    for o in parts:
        if o.data.materials and o.data.materials[0].name in ("orion_plate", "orion_plate_white", BASE, "orion_steel"):
            fabric.world_uvs(o, fabric.TILE["polymer"])
    log(f"headgear: helmet {len(parts)} parts")
    return parts


def headset(info):
    from coat_details import tube
    T, m = info.T, info.m
    ez = T["eye_z"]
    centre, radii = cranium(info)
    out = []
    cups = {}
    for sx in (1, -1):
        # the ear: the head's outer surface beside it
        hit, n, _, _ = info.bvh.ray_cast(Vector((sx * .30, .012, ez - .004)), Vector((-sx, 0, 0)), .4)
        if hit is None:
            continue
        axis = Vector((sx, 0, 0))
        cc = Vector((sx * (abs(hit.x) + .016), hit.y, hit.z))
        R = garment.frame_at(cc, axis, Vector((0, 0, 1)))
        out.append(oval_cup(cc - axis * .001, axis, .066, .078, .027, CUP))
        ring = [cc - axis * .002 + R @ Vector((x, y, 0)) for x, y in oval(.056, .068, 48)]
        out.append(tube(ring + ring[:1], .0068, PAD, name="cushion", sides=10))
        out.append(garment.rounded_box((.040, .010, .004), R, cc + axis * .0265 + Vector((0, 0, .018)), STEEL, bevel=.0015, segs=2, name="cupplate"))
        cups[sx] = cc
    if len(cups) == 2:
        # the band: over the crown in the cups' plane, clear of the hair
        clear = .024 if m else .030                               # (her hair is fuller on top)
        pts = []
        for k in range(41):
            a = math.pi * k / 40                                   # from the left cup over the top to the right
            d = Vector((math.cos(a), 0, math.sin(a)))
            o_ = Vector((0, cups[1].y, centre.z)) + d * .5
            hit, n, _, _ = info.bvh.ray_cast(o_, -d, .6)
            if hit is None:
                continue
            pts.append(hit + d * clear)
        lo = max(cups[1].z, cups[-1].z) + .036
        pts = [p for p in pts if p.z > lo]
        if len(pts) > 6:
            pts = [Vector((cups[1].x * .94, cups[1].y, lo - .004))] + pts + [Vector((cups[-1].x * .94, cups[-1].y, lo - .004))]
            band = garment.trim_strip([(p, (p - Vector((0, cups[1].y, centre.z))).normalized()) for p in pts], .028, PAD,
                                      lift=0.0, step=.006, name="band")
            if band:
                from coat_details import solid
                solid(band, .006)
                out.append(band)
            out.append(tube(pts, .0032, STEEL, name="bandwire", sides=8))
            for sx in (1, -1):                                     # sliders into the cups
                cc = cups[sx]
                out.append(tube([Vector((sx * abs(cc.x) * .97, cc.y, lo - .004)), cc + Vector((sx * .004, 0, .034))], .004, STEEL,
                                name="slider", sides=8))
        # the boom mic: from the left cup round to the corner of the mouth
        cc = cups[1]
        hit, n, _, _ = info.bvh.find_nearest(Vector((.030, -.090, T["chin_z"] + .035)))
        mouth = hit + n * .016
        start = cc + Vector((.010, -.026, -.016))
        mid = start.lerp(mouth, .5) + Vector((.022, -.010, -.010))
        boom = [start.lerp(mid, k / 8) if k <= 8 else mid.lerp(mouth, (k - 8) / 8) for k in range(17)]
        out.append(tube(boom, .0026, STEEL, name="boom", sides=8))
        R = garment.frame_at(mouth, n)
        out.append(garment.rounded_box((.016, .022, .014), R, mouth, PAD, bevel=.006, segs=3, name="foam"))
        out.append(garment.rounded_box((.012, .004, .002), garment.frame_at(cc, Vector((1, 0, 0))), cc + Vector((.0262, -.020, -.012)),
                                       GLOW, bevel=.0008, segs=2, name="light"))
    return out


def oval(w, h, n, k=2.6):
    """a rounded-rect / ellipse outline (superellipse exponent k), n points, w x h"""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s_ = math.cos(a), math.sin(a)
        out.append((w / 2 * math.copysign(abs(c) ** (2 / k), c), h / 2 * math.copysign(abs(s_) ** (2 / k), s_)))
    return out


def oval_cup(base, axis, w, h, depth, mat, n=48, edge=.010):
    """an ear cup: an oval body from the cushion side out to a softly rounded outer face"""
    from wardrobe import to_object
    R = garment.frame_at(base, axis, Vector((0, 0, 1)))
    bm = bmesh.new()
    rings = []
    L = 10
    for j in range(L + 1):
        d = depth * j / L
        sc = 1.0
        if d > depth - edge:                                   # a quarter round onto the outer face
            u = (d - (depth - edge)) / edge
            sc = 1.0 - (1.0 - math.sqrt(max(0.0, 1 - u * u))) * (edge / (min(w, h) / 2))
        rings.append([bm.verts.new(base + R @ Vector((x * sc, y * sc, d))) for x, y in oval(w, h, n)])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / n)
        for i in range(n):
            f = (c, ring[i], ring[(i + 1) % n])
            bm.faces.new(f[::-1] if flip else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return to_object(bm, "cup", mat)


def build(info, log=print):
    from wardrobe import join
    h = join(helmet(info, log), "C_head__orion_helmet")
    s = join(headset(info), "C_head__orion_headset")
    log(f"headgear: helmet {len(h.data.polygons)} faces, headset {len(s.data.polygons)} faces")
    return [h, s]
