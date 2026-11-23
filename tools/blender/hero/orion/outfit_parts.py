"""Hard parts of the Orion outfit, to the owner's sheet: faceted armour plates (an outline, a ridge, a thickness,
bevelled edges, wrapped round the limb they lie on) and the knee and shin armour built from them.
"""
import math

import bmesh
from mathutils import Vector, Matrix


def frame(centre, out, up=Vector((0, 0, 1))):
    """a plate's frame: its centre, right, up and out (out = the surface's normal there)"""
    out = out.normalized()
    right = up.cross(out)
    if right.length < 1e-6:
        right = Vector((1, 0, 0))
    right.normalize()
    up2 = out.cross(right).normalized()
    return centre, right, up2, out


def plate(bm, outline, fr, thick=.006, ridge=.010, rings=4, wrap=0.0, bevel=.0018, facet=True):
    """a faceted plate: the outline [(u, v)] (metres, counter-clockwise in the plate's own right/up) filled toward its
    centre in rings, each raised to the ridge (facet: straight between the rings, so the surface breaks into flat
    facets), wrapped round a limb of radius `wrap` (0: flat), given its thickness behind and its edges bevelled"""
    c, r_, u_, o_ = fr
    cu = sum(p[0] for p in outline) / len(outline)
    cv = sum(p[1] for p in outline) / len(outline)

    def place(u, v, h):
        if wrap > 0:
            a = u / wrap
            x, z = wrap * math.sin(a), wrap * math.cos(a) - wrap
        else:
            x, z = u, 0.0
        return c + r_ * x + u_ * v + o_ * (z + h)

    top, bot = [], []
    for k in range(rings + 1):
        s = 1 - k / rings                                  # 1 on the outline, 0 at the centre
        t = 1 - s
        h = ridge * (t if facet else (1 - s * s)) * (1 if k < rings else 1)
        ring_t, ring_b = [], []
        for (u, v) in outline:
            uu, vv = cu + (u - cu) * max(s, .0), cv + (v - cv) * max(s, .0)
            ring_t.append(bm.verts.new(place(uu, vv, h)))
            if k == 0:
                ring_b.append(bm.verts.new(place(uu, vv, -thick)))
        top.append(ring_t)
        if k == 0:
            bot = ring_b
    n = len(outline)
    new_faces = []
    for k in range(rings):
        A, B = top[k], top[k + 1]
        for i in range(n):
            j = (i + 1) % n
            if k + 1 == rings:
                new_faces.append(bm.faces.new((A[i], A[j], B[j])) if B[j] is not B[i] else None)
            else:
                new_faces.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    # the centre ring collapsed to a point: fan it (the last ring's points all coincide at the centre)
    centre_v = top[-1][0]
    for v in top[-1][1:]:
        if (v.co - centre_v.co).length < 1e-7:
            pass
    bmesh.ops.remove_doubles(bm, verts=top[-1], dist=1e-6)
    # the rim (outline to its back) and the back
    for i in range(n):
        j = (i + 1) % n
        new_faces.append(bm.faces.new((bot[i], bot[j], top[0][j], top[0][i])))
    new_faces.append(bm.faces.new(list(reversed(bot))))
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in new_faces if f is not None and f.is_valid])
    if bevel > 0:
        edges = {e for v in top[0] + bot for e in v.link_edges if e.is_valid}
        bmesh.ops.bevel(bm, geom=list(edges), offset=bevel, segments=2, affect='EDGES', profile=.5, clamp_overlap=True)
    return top[0] + bot


def outline_hex(w, h, top_w=None, bot_w=None, chamfer=.22):
    """an elongated hexagon (a coffin shape): w across at its widest, h tall, its top and bottom edges narrower"""
    tw = top_w if top_w is not None else w * .62
    bw = bot_w if bot_w is not None else w * .48
    return [(-bw / 2, -h / 2), (bw / 2, -h / 2), (w / 2, -h / 2 + h * chamfer * 1.6), (w / 2, h / 2 - h * chamfer),
            (tw / 2, h / 2), (-tw / 2, h / 2), (-w / 2, h / 2 - h * chamfer), (-w / 2, -h / 2 + h * chamfer * 1.6)]


def knee_armour(T, leg_surface, log=print):
    """the knee armour of the sheet (each knee, measured on it at 3.7 mm a pixel): the big faceted grey plate over the
    kneecap (13 cm across, 18 tall, a coffin's outline, its middle raised to a ridge) with a dark slot near its top and
    a dark notch at its foot; under it the dark chevron plate cupping the top of the shin; placed on the trousers'
    surface at the knee's front"""
    plates, darks = bmesh.new(), bmesh.new()
    K = Vector(T["knee"])
    for sx in (1, -1):
        kx = K.x * sx
        hit = leg_surface(Vector((kx, K.y - .40, K.z + .005)), Vector((0, 1, 0)))
        if hit is None:
            continue
        p, n = hit
        n = Vector((n.x * .55, n.y, 0)).normalized()
        base = p + n * .012
        fr = frame(base, n)
        plate(plates, outline_hex(.128, .178, top_w=.082, bot_w=.068, chamfer=.20), fr, thick=.010, ridge=.018, rings=3,
              wrap=.085, bevel=.0025)
        c, r_, u_, o_ = fr
        # the slot near its top and the notch at its foot: dark insets standing on the plate's facets
        for v, w, h, lift in ((.052, .044, .013, .0095), (-.068, .030, .010, .0048)):
            plate(darks, [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)],
                  (c + u_ * v + o_ * lift, r_, u_, o_), thick=.003, ridge=.001, rings=1, wrap=.085, bevel=.0010)
        # the chevron plate under it
        hit3 = leg_surface(Vector((kx, K.y - .40, K.z - .112)), Vector((0, 1, 0)))
        if hit3:
            p3, n3 = hit3
            n3 = Vector((n3.x * .55, n3.y, -.05)).normalized()
            out = [(-.058, .024), (-.062, -.002), (-.030, -.034), (0.0, -.044), (.030, -.034), (.062, -.002), (.058, .024)]
            plate(darks, out, frame(p3 + n3 * .009, n3), thick=.007, ridge=.008, rings=2, wrap=.075, bevel=.0022)
    log("knee armour: the plates, their insets and the chevrons under them")
    return plates, darks




# ------------------------------------------------------------------------------------------------ straps on a surface

class Surface:
    """an object's surface (as drawn) to lay parts on: the nearest point and its normal, a ray's hit"""

    def __init__(self, obj):
        import bpy
        from mathutils.bvhtree import BVHTree
        dg = bpy.context.evaluated_depsgraph_get()
        e = obj.evaluated_get(dg)
        me = e.to_mesh()
        b = bmesh.new()
        b.from_mesh(me)
        b.transform(obj.matrix_world)
        e.to_mesh_clear()
        b.normal_update()
        self.bvh = BVHTree.FromBMesh(b)
        b.free()

    def near(self, p):
        loc, nrm, _, _ = self.bvh.find_nearest(p)
        return loc, nrm

    def hit(self, origin, direction, far=1.0):
        loc, nrm, _, _ = self.bvh.ray_cast(origin, direction.normalized(), far)
        return (loc, nrm) if loc is not None else None


def band(bm, surf, path, width, thick=.004, lift=.004, step=.008, closed=False):
    """a strap of webbing laid along a path over a surface: the path resampled, each point pulled onto the surface and
    lifted off it, a ribbon `width` wide across it, given its thickness inward; its ends square"""
    pts = []
    for a, b in zip(path[:-1], path[1:]):
        n = max(1, int((b - a).length / step))
        for k in range(n):
            pts.append(a.lerp(b, k / n))
    if not closed:
        pts.append(path[-1])
    on = []
    for p in pts:
        loc, nrm = surf.near(p)
        if loc is None:
            continue
        on.append((loc + nrm * lift, nrm))
    if len(on) < 2:
        return
    # (each point a little smoothed along the run: a strap does not follow every dimple)
    sm = []
    for i in range(len(on)):
        js = [j % len(on) if closed else min(max(j, 0), len(on) - 1) for j in (i - 1, i, i + 1)]
        p = (on[js[0]][0] + 2 * on[js[1]][0] + on[js[2]][0]) / 4
        n = (on[js[0]][1] + 2 * on[js[1]][1] + on[js[2]][1]).normalized()
        sm.append((p, n))
    rows = []
    for i, (p, n) in enumerate(sm):
        j0, j1 = (i - 1) % len(sm) if closed else max(i - 1, 0), (i + 1) % len(sm) if closed else min(i + 1, len(sm) - 1)
        t = (sm[j1][0] - sm[j0][0]).normalized()
        side = n.cross(t).normalized()
        o = [p + side * width / 2, p - side * width / 2]
        i_ = [q - n * thick for q in o]
        rows.append([bm.verts.new(v) for v in (o[0], o[1], i_[1], i_[0])])
    rng = range(len(rows)) if closed else range(len(rows) - 1)
    for i in rng:
        A, B = rows[i], rows[(i + 1) % len(rows)]
        for k in range(4):
            bm.faces.new((A[k], A[(k + 1) % 4], B[(k + 1) % 4], B[k]))
    if not closed:
        bm.faces.new(list(reversed(rows[0])))
        bm.faces.new(rows[-1])


def ring_path(c, axis, r_hint, surf, n=40, tilt=0.0):
    """a closed path round a limb (centre c, its axis): each point found on the surface by a ray in toward the axis"""
    axis = axis.normalized()
    u = axis.cross(Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((1, 0, 0))).normalized()
    v = axis.cross(u).normalized()
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        d = u * math.cos(a) + v * math.sin(a)
        o = c + d * (r_hint + .15) + axis * (tilt * math.sin(a))
        h = surf.hit(o, -d, .4)
        q = h[0] if h else None
        if q is None or ((q - c) - axis * (q - c).dot(axis)).length > r_hint * 1.45:
            q = surf.near(c + d * r_hint + axis * (tilt * math.sin(a)))[0]
        pts.append(q)
    return pts


# ------------------------------------------------------------------------------------------------ the upper body's parts

def shoulders(coat, T, log=print):
    """the layered armour on each of the coat's shoulders (three lames from the collar out over the shoulder's point,
    the last turning down onto the arm), a small light by the collar in front"""
    plates, lights = bmesh.new(), bmesh.new()
    S = Vector(T["shoulder_joint"])
    for sx in (1, -1):
        for k, (x, w, l, drop) in enumerate(((.115, .118, .070, 0.0), (.175, .128, .072, .012), (.232, .118, .066, .040))):
            top = coat.hit(Vector((sx * x, S.y + .01, 1.90)), Vector((0, 0, -1)), 1.0)
            if top is None:
                continue
            p, n = top
            n = (n + Vector((sx * .35 * k, 0, 0))).normalized()
            fr = frame(p + n * (.006 + .004 * k), n, Vector((sx, 0, -drop * 4)).normalized())
            outline = [(-w / 2, -l / 2), (w / 2, -l / 2), (w / 2 + .004, l / 2 - .012), (w / 2 - .010, l / 2), (-w / 2 + .010, l / 2), (-w / 2 - .004, l / 2 - .012)]
            plate(plates, outline, fr, thick=.006, ridge=.005, rings=2, wrap=.085, bevel=.0018)
        # the light by the collar, on the front of the first lame
        fr_ = coat.hit(Vector((sx * .105, -.40, 1.465)), Vector((0, 1, 0)), 1.0)
        if fr_:
            p, n = fr_
            plate(lights, [(-.009, -.013), (.009, -.013), (.009, .013), (-.009, .013)], frame(p + n * .008, n),
                  thick=.004, ridge=.001, rings=1, wrap=0.0, bevel=.0012)
    log("shoulders: three lames a side, the collar's lights")
    return plates, lights


def harness(vest, T, log=print):
    """the X of straps across the vest (each from a shoulder's front to the other side's hip, crossing over the
    breastbone), the round plate where they cross, a light strip on the right strap's upper run"""
    straps, plates, lights = bmesh.new(), bmesh.new(), bmesh.new()
    for sx in (1, -1):
        a = vest.hit(Vector((sx * .110, -.40, 1.47)), Vector((0, 1, 0)))
        m = vest.hit(Vector((0.0, -.40, 1.300)), Vector((0, 1, 0)))
        b = vest.hit(Vector((-sx * .150, -.40, 1.115)), Vector((0, 1, 0)))
        if not (a and m and b):
            continue
        band(straps, vest, [a[0], m[0], b[0]], .040, thick=.004, lift=.005)
        if sx < 0:                                          # (the light strip on the body's right strap)
            p0, p1 = a[0].lerp(m[0], .20), a[0].lerp(m[0], .55)
            band(lights, vest, [p0, p1], .010, thick=.002, lift=.0105, step=.006)
    c = vest.hit(Vector((0.0, -.40, 1.300)), Vector((0, 1, 0)))
    if c:
        p, n = c
        octo = [(math.cos(math.radians(22.5 + 45 * k)) * .026, math.sin(math.radians(22.5 + 45 * k)) * .026) for k in range(8)]
        plate(plates, octo, frame(p + n * .011, n), thick=.006, ridge=.004, rings=2, wrap=0.0, bevel=.0016)
    log("harness: the X, its plate, the light strip")
    return straps, plates, lights


def back_module(coat, T, log=print):
    """on the coat's upper back: the spine plate between the shoulder blades, its round light at the top and a bar of
    light across its middle, two straps from its top corners to the shoulders"""
    plates, straps, lights = bmesh.new(), bmesh.new(), bmesh.new()
    h = coat.hit(Vector((0.0, .40, 1.320)), Vector((0, -1, 0)))
    if h is None:
        return plates, straps, lights
    p, n = h
    fr = frame(p + n * .010, n)
    plate(plates, [(-.034, -.120), (.034, -.120), (.048, -.040), (.044, .090), (.026, .120), (-.026, .120), (-.044, .090), (-.048, -.040)],
          fr, thick=.008, ridge=.008, rings=3, wrap=.20, bevel=.002)
    c, r_, u_, o_ = fr
    top = c + u_ * .095 + o_ * .016
    disc = [(math.cos(2 * math.pi * k / 16) * .014, math.sin(2 * math.pi * k / 16) * .014) for k in range(16)]
    plate(lights, disc, (top, r_, u_, o_), thick=.004, ridge=.002, rings=2, wrap=0.0, bevel=.001)
    bar = c + u_ * .010 + o_ * .016
    plate(lights, [(-.030, -.004), (.030, -.004), (.030, .004), (-.030, .004)], (bar, r_, u_, o_), thick=.003, ridge=.001, rings=1, wrap=0.0, bevel=.0008)
    for sx in (1, -1):
        a = c + u_ * .110 + r_ * (sx * .030)
        s = coat.hit(Vector((sx * .175, .40, 1.50)), Vector((0, -1, 0)))
        if s:
            band(straps, coat, [a, s[0]], .036, thick=.004, lift=.006)
    log("back: the spine plate, its lights, two straps")
    return plates, straps, lights


# ------------------------------------------------------------------------------------------------ the legs' parts

def leg_straps(legs, T, log=print):
    """a strap round each thigh (a little slanted) with a buckle; two round each shin under the knee armour; on the
    right thigh's outside a holster hung from the belt, on the left a cargo pocket with its flap"""
    straps, boxes, greys = bmesh.new(), bmesh.new(), bmesh.new()
    K, H = Vector(T["knee"]), Vector(T["hip_joint"])
    for sx in (1, -1):
        kx, hx = K.x * sx, H.x * sx
        thigh = Vector((hx + (kx - hx) * .45, (H.y + K.y) / 2, H.z + (K.z - H.z) * .45))
        axis = Vector((kx - hx, K.y - H.y, K.z - H.z))
        band(straps, legs, ring_path(thigh, axis, .09, legs, tilt=.015), .038, thick=.004, lift=.004, closed=True)
        for dz, w in ((.088, .026), (-.150, .028)):
            ring = ring_path(Vector((kx, K.y + .01, K.z + dz)), Vector((0, 0, 1)), .066, legs)
            band(straps, legs, ring, w, thick=.004, lift=.005, closed=True)
        # the grey straps crossing on the outside of the calf
        o = sx * .062
        for (y0, z0), (y1, z1) in (((-.030, -.125), (.050, -.255)), ((.045, -.125), (-.025, -.255))):
            path = [Vector((kx + o, K.y + y0 + (y1 - y0) * t, K.z + z0 + (z1 - z0) * t)) for t in (0, .25, .5, .75, 1)]
            band(greys, legs, path, .020, thick=.0035, lift=.006 if y0 < 0 else .0045, step=.006)
        out = legs.hit(Vector((sx * .5, (H.y + K.y) / 2, H.z + (K.z - H.z) * .32)), Vector((-sx, 0, 0)))
        if out:
            p, n = out
            n = Vector((n.x, n.y * .3, 0)).normalized()
            if sx < 0:                                      # the holster: a long pouch with a strap over its top
                plate(boxes, [(-.032, -.085), (.032, -.085), (.036, .070), (.026, .090), (-.026, .090), (-.036, .070)],
                      frame(p + n * .020, n), thick=.026, ridge=.006, rings=2, wrap=.12, bevel=.004)
            else:                                           # the cargo pocket and its flap
                plate(boxes, [(-.050, -.065), (.050, -.065), (.050, .055), (-.050, .055)], frame(p + n * .012, n),
                      thick=.016, ridge=.005, rings=2, wrap=.12, bevel=.004)
                plate(boxes, [(-.053, -.005), (.053, -.005), (.053, .030), (-.053, .030)],
                      frame(p + n * .018 + Vector((0, 0, .045)), n), thick=.004, ridge=.002, rings=1, wrap=.12, bevel=.002)
    log("legs: thigh and knee straps, the calf's crossed straps, the holster, the cargo pocket")
    return straps, boxes, greys


def build(T, legs_obj, log=print):
    """the hard parts on the built soft ones (the trousers' surface)"""
    import bpy
    from mathutils.bvhtree import BVHTree
    from outfit_mat import to_object
    dg = bpy.context.evaluated_depsgraph_get()
    e = legs_obj.evaluated_get(dg)
    me = e.to_mesh()
    b = bmesh.new()
    b.from_mesh(me)
    b.transform(legs_obj.matrix_world)
    e.to_mesh_clear()
    bvh = BVHTree.FromBMesh(b)
    b.free()

    def leg_surface(origin, direction):
        loc, nrm, _, _ = bvh.ray_cast(origin, direction, 1.0)
        return (loc, nrm) if loc is not None else None

    plates, darks = knee_armour(T, leg_surface, log=log)
    legs = Surface(legs_obj)
    straps, boxes, greys = leg_straps(legs, T, log=log)
    return [to_object(plates, "knee_plates", "orion_plate"), to_object(darks, "shin_plates", "orion_vest"),
            to_object(straps, "leg_straps", "orion_strap"), to_object(boxes, "leg_pouches", "orion_strap"),
            to_object(greys, "leg_greys", "orion_boot_panel")]


def build_upper(T, coat_obj, vest_obj, log=print):
    """the upper body's hard parts on the built coat and vest"""
    from outfit_mat import to_object
    out = []
    if coat_obj is not None:
        coat = Surface(coat_obj)
        sp, sl = shoulders(coat, T, log=log)
        bp, bs, bl = back_module(coat, T, log=log)
        out += [to_object(sp, "coat_shoulders", "orion_vest"), to_object(sl, "coat_lights", "orion_glow"),
                to_object(bp, "coat_back_plate", "orion_vest"), to_object(bs, "coat_back_straps", "orion_strap"),
                to_object(bl, "coat_back_lights", "orion_glow")]
    if vest_obj is not None:
        vest = Surface(vest_obj)
        hs, hp, hl = harness(vest, T, log=log)
        out += [to_object(hs, "vest_harness", "orion_strap"), to_object(hp, "vest_plate", "orion_steel"),
                to_object(hl, "vest_lights", "orion_glow")]
    return out
