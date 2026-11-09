"""The Orion belt rig: a tactical belt over the trousers' waistband with its pouches (his) or a drop-leg holster
rig (hers), built like the other gear (coat_details.py):

  belt       webbing laid round the waist over the trousers (the trousers' own ease plus a little), its edges
             stitched, a quick-release buckle at the front (two moulded halves, a light strip on the male half),
             keepers either side
  pouches    his: a pair of magazine pouches on the left hip, a utility pouch on the right, an admin pouch at the
             back; each a soft-cornered body of coated canvas with a flap, a press stud, a bungee and the straps that
             thread it onto the belt, stitched
  holster    hers: a drop-leg platform on the right thigh hanging from the belt, two leg straps with buckles
"""
import math
import bmesh
from mathutils import Vector, Matrix
import garment

WEB, CANVAS, STEEL, PLATE, GLOW, STITCH, CORD = ("orion_strap", "orion_strap", "orion_steel", "orion_plate", "orion_glow",
                                                 "orion_stitch", "orion_lace")


def waist_path(info, z, lift, gap=.040):
    """points round the body at height z (from outside, on the hips), lifted by `lift`, open at the front by `gap`"""
    pts = []
    for k in range(73):
        a = (gap / .16) + (2 * math.pi - 2 * gap / .16) * k / 72      # 0 = front centre
        d = Vector((math.sin(a), -math.cos(a), 0))
        hit, n, _, _ = info.bvh.ray_cast(Vector((0, .012, z)) + d * .5, -d, .6)
        if hit is not None:
            pts.append(hit + n * lift)
    return pts


def soft_box(size, R, at, mat, name, r=.006):
    return garment.rounded_box(size, R, at, mat, bevel=r, segs=3, name=name)


def pouch(surf_tree, p, n, up, w, h, d, flap=True, name="pouch"):
    """a soft pouch sitting on the belt: body, flap with a lip, a press stud, a bungee across, two belt straps, the
    front's edges stitched"""
    n = n.normalized()
    side = up.cross(n).normalized()
    R = Matrix((side, up, n)).transposed()
    c = p + n * (d / 2 + .004) - up * (h * .22)
    out = [soft_box((w, h, d), R, c, CANVAS, name, r=min(.008, d * .35))]
    if flap:
        fc = c + up * (h / 2 - .010) + n * (d / 2 + .0016)
        out.append(soft_box((w + .004, .030, .0035), R, fc, CANVAS, "flap", r=.0016))
        out.append(soft_box((w + .004, .006, d + .006), R, c + up * (h / 2 + .0015), CANVAS, "flaptop", r=.0025))
        out.append(garment.snap(fc + n * .0020 - up * .006, n, .0050, STEEL, name="stud"))
    # the front's stitched edges
    for sx in (-1, 1):
        a = c + n * (d / 2 + .0004) + side * sx * (w / 2 - .004)
        pts = [(a + up * (h / 2 - .006) * t, n) for t in (-1, -.5, 0, .5, .8)]
        st = garment.trim_strip(pts, .0013, STITCH, lift=.0003, tile=.012, step=.003, name="stitch")
        if st:
            out.append(st)
    # bungee across the front
    b0 = c + n * (d / 2 + .0028) + up * (h * .05)
    from coat_details import tube
    out.append(tube([b0 + side * (w / 2 + .002) * t + n * .0015 * (1 - t * t) for t in [x / 8 for x in range(-8, 9)]],
                    .0018, CORD, name="bungee"))
    # the straps that thread it onto the belt (behind, showing over the belt's top and bottom)
    for sx in (-.30, .30):
        sc = p + side * sx * w + n * .0035
        out.append(soft_box((.022, .060, .0030), R, sc, WEB, "molle", r=.0012))
    return out


def build(info, log=print):
    from coat_details import tube
    T, m = info.T, info.m
    waist = T["hips"]["z"] + (.065 if m else .080)
    zb = waist - .030
    bw = .044 if m else .036
    lift = (.010 if m else .006) + .0035                    # over the trousers' ease and cloth
    path = waist_path(info, zb, lift)
    strap, spath = garment.strap(info, path, bw, .0042, WEB, lift=lift, step=.008, name="belt")
    parts = [strap]
    for off in (-(bw / 2 - .004), bw / 2 - .004):
        st = garment.trim_strip([(q + n * .0024, n) for q, n in spath], .0014, STITCH, offset=off, tile=.012, step=.003,
                                name="stitch")
        if st:
            parts.append(st)
    # the buckle at the front: a female receiver and the male half clipped into it
    hit, n, _, _ = info.bvh.ray_cast(Vector((0, -.5, zb)), Vector((0, 1, 0)), .6)
    if hit is not None:
        c = hit + n * (lift + .006)
        up = Vector((0, 0, 1))
        side = up.cross(n).normalized()
        R = Matrix((side, up, n)).transposed()
        parts.append(garment.rounded_box((.060, bw + .006, .010), R, c, STEEL, bevel=.0035, segs=3, name="buckle"))
        parts.append(garment.rounded_box((.022, bw - .006, .006), R, c + n * .0065 + side * .010, PLATE, bevel=.002,
                                         segs=2, name="buckleface"))
        parts.append(garment.rounded_box((.030, .0045, .0018), R, c + n * .0082 - side * .012, GLOW, bevel=.0008,
                                         segs=2, name="glow"))
        for sx in (-1, 1):                                   # keepers either side of the buckle
            parts.append(garment.rounded_box((.012, bw + .010, .006), R, c + side * sx * .052 - n * .003, WEB,
                                             bevel=.0018, segs=2, name="keeper"))
    if m:
        # pouches: two magazine pouches (left hip), a utility pouch (right hip), an admin pouch (back)
        for ang, (w, h, d, nm) in ((60, (.055, .095, .032, "mag")), (82, (.055, .095, .032, "mag")),
                                    (-70, (.090, .080, .045, "utility")), (180, (.110, .060, .030, "admin"))):
            a = math.radians(ang)
            dvec = Vector((math.sin(a), -math.cos(a), 0))
            hit, nn, _, _ = info.bvh.ray_cast(Vector((0, .012, zb)) + dvec * .5, -dvec, .6)
            if hit is None:
                continue
            p = hit + nn * (lift + .0045)
            parts += pouch(None, p, Vector((nn.x, nn.y, 0)), Vector((0, 0, 1)), w, h, d, name=nm)
    else:
        parts += holster(info, zb, lift)
    log(f"belt: {len(parts)} parts")
    return parts


def holster(info, zb, lift):
    """her drop-leg platform on the right thigh: hangers from the belt, the platform, two leg straps"""
    out = []
    K, Hj = info.L["K"], info.L["H"]
    zt = (K.z + Hj.z) / 2 + .03
    hit, n, _, _ = info.bvh.ray_cast(Vector((-.50, -.03, zt)), Vector((1, .12, 0)).normalized(), .6)   # the right thigh
    if hit is None:
        return out
    up = Vector((0, 0, 1))
    side = up.cross(n).normalized()
    R = Matrix((side, up, n)).transposed()
    c = hit + n * .016
    out.append(soft_box((.075, .150, .010), R, c, CANVAS, "platform", r=.004))
    out.append(soft_box((.060, .120, .006), R, c + n * .007, PLATE, "platformplate", r=.003))
    # hangers up to the belt
    top = c + up * .075
    for sx in (-.022, .022):
        a = top + side * sx
        hb, nb, _, _ = info.bvh.find_nearest(Vector((a.x, a.y, zb)))
        if hb is None:
            continue
        b = hb + nb * (lift + .004)
        pts = [a.lerp(b, t) + n * .004 * math.sin(math.pi * t) for t in [k / 10 for k in range(11)]]
        out.append(garment.trim_strip([(p, n) for p in pts], .020, WEB, tile=.05, step=.004, name="hanger"))
    # two leg straps round the thigh with a side-release buckle
    for dz in (.045, -.045):
        z = zt + dz
        pts = []
        for k in range(49):
            a = 2 * math.pi * k / 48
            dd = Vector((math.cos(a), math.sin(a), 0))
            centre = Vector((-(Hj.x + K.x) / 2, .0, z))
            hb, nb, _, _ = info.bvh.ray_cast(centre + dd * .3, -dd, .35)
            if hb is not None and hb.x < -.012:              # (this thigh only: never across to the other leg)
                pts.append(hb)
        if len(pts) > 10:
            s, sp = garment.strap(info, pts, .022, .0025, WEB, lift=.0075, name="legstrap")
            out.append(s)
            q, qn = sp[len(sp) // 4]
            out += garment.buckle(q + qn * .003, qn, .022, STEEL)
    return out
