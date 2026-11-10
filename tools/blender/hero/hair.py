"""Hair for the hero bodies as strand cards (the way game hair is built): a strand atlas texture (ours, numpy) and
hundreds of narrow cards rooted in the scalp, layered for volume, each following the head's curve along a style
direction field; under them a thin cap with the same strands so no scalp shows between cards.

  atlas    RGBA, 4 columns of strand clumps running down V (root at v = 0, tips taper and fade); the Unreal hair
           material (M_SOHair) reads the strand tangent along V and dithers the alpha
  male     short, swept back and up from the hairline, lifted at the front, tapered at the sides and nape
  female   pulled back along the scalp to a tie at the crown's back, then a ponytail of long cards falling behind

Materials: hair (cards, masked, two-sided) and hair__cap (the cap); the game tints both (HAIR_TONE).
"""
import math
import os
import random
import bmesh
import bpy
import numpy as np
from mathutils import Vector

ATLAS_COLS = 4


def atlas(path, size=1024, seed=3):
    """the strand atlas: per column a clump of strands; RGB = strand colour (light, the game tints it), A = coverage"""
    if os.path.exists(path):
        return path
    rng = np.random.RandomState(seed)
    H = W = size
    col = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)
    cw = W // ATLAS_COLS
    v = np.arange(H, dtype=np.float32) / H
    # each column is one clump of separate strands (gaps between them): wide at the root, drawn together toward a
    # pointed, ragged tip; column 3 is a loose wisp. The card's silhouette comes from the strands, never a rectangle
    for c, (n_strands, spread, conv) in enumerate(((80, .30, .80), (110, .34, .70), (60, .22, .85), (22, .16, .5))):
        cx0 = c * cw + cw / 2
        for _ in range(n_strands):
            off = rng.normal(0, spread * cw / 2)
            off = float(np.clip(off, -.46 * cw, .46 * cw))
            length = rng.uniform(.55, 1.0) if c < 3 else rng.uniform(.4, 1.0)
            width = rng.uniform(.7, 1.6)
            wave_a = rng.uniform(0, 2.5)
            wave_f = rng.uniform(1.5, 5)
            ph = rng.uniform(0, 6.3)
            shade = rng.uniform(.7, 1.2)
            xs = cx0 + off * (1 - conv * v) + rng.uniform(-.04, .04) * cw * v + wave_a * np.sin(v * wave_f * 2 * np.pi + ph)
            n = int(length * H)
            t = v[:n]
            taper = 1.0 - np.clip((t - length * .5) / (length * .5), 0, None)   # thins and fades toward the tip
            wpx = np.maximum(.5, width * (.35 + .65 * taper))
            start = rng.uniform(0, .14)                             # ragged roots: strands start at staggered depths
            root_fade = np.clip((t - start) / .10, 0, 1)            # and fade in, so a card never ends in a flat edge
            k = (.3 + .7 * taper) * (.25 + .75 * root_fade)
            for dx in range(-3, 4):                                 # (wpx <= 1.6 px: three columns either side)
                X = np.floor(xs[:n]).astype(int) + dx
                ok = (X >= c * cw) & (X < (c + 1) * cw)
                d = np.abs(X + .5 - xs[:n])
                a = np.maximum(0.0, 1.0 - d / wpx) * k
                rows = np.nonzero(ok & (a > alpha[np.arange(n), np.clip(X, 0, W - 1)]))[0]
                alpha[rows, X[rows]] = a[rows]
                col[rows, X[rows]] = (shade * (.5 + .5 * t[rows]))[:, None]    # roots darker
    col = np.clip(col, 0, 1)
    img = np.dstack([col, alpha])[::-1]                      # Blender's pixel rows start at the bottom
    im = bpy.data.images.new(os.path.splitext(os.path.basename(path))[0], W, H, alpha=True)
    im.pixels.foreach_set(img.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    return path


def hair_material(name, tex_path, cap=False):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(tex_path, check_existing=True)
    nt.links.new(img.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = .45
    if not cap:
        # alpha clip: Greater Than on the alpha (the glTF exporter writes alphaMode MASK)
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = 'GREATER_THAN'
        gt.inputs[1].default_value = .35
        nt.links.new(img.outputs["Alpha"], gt.inputs[0])
        nt.links.new(gt.outputs[0], b.inputs["Alpha"])
        m.use_backface_culling = False
    m.diffuse_color = (.04, .03, .02, 1)
    return m


# ------------------------------------------------------------------------------------------------ cards

class Scalp:
    def __init__(self, info, keep):
        """info: wardrobe.BodyInfo; keep(co) -> bool: the hair area"""
        self.info = info
        bm = info.bm
        self.pts = [(f.calc_center_median(), f.normal.copy()) for f, r in zip(bm.faces, info.face_region)
                    if r == "head" and keep(f.calc_center_median())]

    def surface(self, p, lift):
        loc, nrm, _, _ = self.info.bvh.find_nearest(p)
        return loc + nrm * lift, nrm


def hairline_band(info, keep, line_z, rnd):
    """roots for the hairline's wisps: from 7 mm below the line to 16 mm above it, thinning out toward the bottom so
    the edge is a density gradient, never a ruled line"""
    pts = Scalp(info, keep).pts
    out = []
    for r, n in pts:
        h = r.z - line_z(r)
        if h > .016 or (r.y > .02 and h < -.002):       # (no baby hairs down the nape)
            continue
        if rnd.random() < min(1.0, max(.08, (h + .007) / .012)):
            out.append((r, n))
    return out


def grow(scalp, root, nrm, direction, length, lift0, lift1, steps=6, gravity=0.0, stop=None, bulge=False):
    """a guide over the scalp: each step goes along direction(p) projected on the tangent plane, re-lifted from the
    surface (lift grows from lift0 to lift1 along the strand)"""
    pts = [(root + nrm * lift0, nrm)]
    p, n = root, nrm
    step = length / steps
    for k in range(1, steps + 1):
        d = Vector(direction(p))
        d = d - n * d.dot(n)
        if gravity:
            d += Vector((0, 0, -gravity * k / steps))
        if d.length < 1e-6:
            break
        d.normalize()
        p = p + d * step
        f = k / steps
        if bulge:                                        # full in the middle, pulled tight at the far end (a tie)
            f = math.sin(math.pi * min(1.0, f) ** 1.3)    # zero again at the tie: no ring of lifted tips round it
        lift = lift0 + (lift1 - lift0) * f
        p, n = scalp.surface(p, 0.0)
        pts.append((p + n * lift, n))
        if stop and stop(p):
            break
    return pts


def card(bm, uv, pts, width, col, tip_width=.55, twist=0.0):
    """a ribbon along pts [(co, surface normal)], lying on the surface; UV u in the atlas column, v root -> tip"""
    rows = []
    n_pts = len(pts)
    u0, u1 = col / ATLAS_COLS + .01, (col + 1) / ATLAS_COLS - .01
    for i, (p, n) in enumerate(pts):
        t = (pts[min(i + 1, n_pts - 1)][0] - pts[max(i - 1, 0)][0])
        if t.length < 1e-9:
            continue
        t.normalize()
        side = n.cross(t).normalized()
        if twist:
            side = (side * math.cos(twist) + n * math.sin(twist)).normalized()
        w = width * (1 - (1 - tip_width) * i / max(1, n_pts - 1))
        rows.append((bm.verts.new(p - side * w / 2), bm.verts.new(p + side * w / 2), i / max(1, n_pts - 1)))
    for (a0, b0, v0), (a1, b1, v1) in zip(rows, rows[1:]):
        f = bm.faces.new((a0, b0, b1, a1))
        for loop, (u, v) in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            loop[uv].uv = (u, 1 - v)


def ponytail_tie(T):
    """where her ponytail is tied (the back of the crown)"""
    from mathutils import Vector as V
    return V((0, .085, T["height"] - .045))


def build(info, T, tex_dir, log=print):
    """the hair object for this body (C_hair__short / C_hair__ponytail) with its cap"""
    from wardrobe import from_faces, join
    import garment
    m = T["sex"] == "male"
    ez, top = T["eye_z"], T["height"]
    rnd = random.Random(7 if m else 11)
    os.makedirs(tex_dir, exist_ok=True)
    tex = atlas(tex_path(T, "hair_strands"))
    mat_cards = hair_material("hair", tex)
    mat_cap = hair_material("hair__cap", scalp_texture(tex_path(T, "hair_scalp")))

    shrink = 0.0

    def hairline(c):
        return c.z > line_z(c) + shrink

    def line_z(c):
        """the hair's edge: a soft M at the front (the temples recede), sideburns in front of the ears, the nape low
        at the back; a touch of noise so it is not a ruled line"""
        x, y = abs(c.x), c.y
        temple = .012 * math.exp(-((x - .034) / .012) ** 2)
        front = ez + (.044 if m else .027) + .016 * (x / .06) ** 2 + temple * (1 if m else .4) + .003 * math.sin(c.x * 140) + .002 * math.sin(c.x * 330 + 1.3)
        if y > -.01:                                     # behind the front: falls toward the ears and the nape
            k = min(1.0, (y + .01) / .07)
            back = ez - (.010 if m else .02) - (.050 if m else .06) * max(0.0, y - .03) / .06
            line = front * (1 - k) + back * k
        else:
            line = front
        return line

    def area(c):
        return hairline(c) and not (abs(c.x) > .062 and -.012 < c.y < .045 and c.z < ez + .035)   # clear of the ears
    scalp = Scalp(info, area)

    def area_low(c):                                      # the hair area grown 7 mm past the line (fine baby hairs)
        return line_z(c) - .007 < c.z and not (abs(c.x) > .062 and -.012 < c.y < .045 and c.z < ez + .035)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    centre = Vector((0, .006, ez + .03))
    if m:
        def direction(p):
            back = Vector((0, 1, 0))
            up = Vector((0, 0, 1))
            side = Vector((math.copysign(1, p.x), 0, 0))
            front = max(0.0, -(p.y + .02) / .08)                         # the hairline sweeps back and up
            sides = max(0.0, (abs(p.x) - .045) / .03)
            nape = max(0.0, min(1.0, (p.y - .015) / .05))             # behind the ears: straight down the back
            d = back * 1.0 + up * (.6 * front) - up * (.8 * sides) + side * (.15 * sides)
            return d * (1 - nape) - up * nape          # (no side component: it would part the back down the middle)
        def put(root, nrm, L, lift0, lift1, w, col, guide_dir=None, steps=6, twist=0.0, tip=.55):
            if root.y > .02 and root.z < ez + .03:          # the nape is cut close: it lies on the neck
                k = max(0.0, min(1.0, (ez + .03 - root.z) / .04))
                lift0, lift1 = lift0 * (1 - .6 * k), (lift0 + (lift1 - lift0) * (1 - k)) * (1 - .6 * k)
            # behind the ears the cut ends at the hairline: nothing hangs down the neck
            pts = grow(scalp, root, nrm, guide_dir or direction, L, lift0, lift1, steps=steps,
                       stop=lambda p: p.y > .0 and p.z < line_z(p) - .003)
            if len(pts) > 2:
                card(bm, uv, pts, w, col, tip_width=tip, twist=twist)

        def length_at(p):
            front = max(0.0, -(p.y + .02) / .08)
            low = max(0.0, (ez + .07 - p.z) / .06)               # the sides and nape are cut shorter
            return (.068 + .030 * front) * (1 - .70 * min(1.0, low))
        # primary clumps: several cards from neighbouring roots sharing a guide; their tips gather
        for _ in range(170):
            root, nrm = rnd.choice(scalp.pts)
            L = length_at(root) * rnd.uniform(.85, 1.15)
            base_dir = Vector(direction(root))
            jitter = Vector((rnd.uniform(-.18, .18), rnd.uniform(-.08, .08), rnd.uniform(-.05, .25)))
            g = lambda p, bd=base_dir, j=jitter: bd + j
            for c in range(rnd.randint(4, 7)):
                off = Vector((rnd.uniform(-.008, .008), rnd.uniform(-.008, .008), rnd.uniform(-.004, .004)))
                r2, n2 = scalp.surface(root + off, 0.0)
                lift = rnd.uniform(.003, .016)
                put(r2, n2, L * rnd.uniform(.85, 1.05), lift, lift + .008, rnd.uniform(.012, .018), rnd.randrange(3),
                    guide_dir=g, twist=rnd.uniform(-.2, .2), tip=.85)
        # secondary: single, narrower cards between the clumps
        for _ in range(900):
            root, nrm = rnd.choice(scalp.pts)
            lift = rnd.uniform(.0015, .012)
            put(root, nrm, length_at(root) * rnd.uniform(.7, 1.05), lift, lift + .005, rnd.uniform(.009, .014),
                rnd.randrange(3), twist=rnd.uniform(-.15, .15), tip=.9)
        # flyaways: a few thin wisps lifting off the top
        for _ in range(45):
            root, nrm = rnd.choice(scalp.pts)
            if root.z < ez + .08:
                continue
            put(root, nrm, length_at(root) * rnd.uniform(.6, 1.0), .010, .022, .008, 3, twist=rnd.uniform(-.8, .8), tip=.9)
        # the hairline: short, fine wisps rooted along the edge (the line is drawn by roots, not by the cap's border)
        band = hairline_band(info, area_low, line_z, rnd)
        for _ in range(520):
            root, nrm = rnd.choice(band)
            put(root, nrm, rnd.uniform(.018, .034), .0006, .003, rnd.uniform(.006, .010), rnd.choice((2, 3)),
                twist=rnd.uniform(-.2, .2), tip=.9, steps=4)
        name = "C_hair__short"
    else:
        tie = ponytail_tie(T)

        def direction(p):
            return tie - p
        def vol(root):
            """how much the hair stands off the scalp here: pulled tight and flat from the forehead and temples back
            (a front that lifts rolls over into a quiff and reads as folded), full only over the crown"""
            f = max(0.0, min(1.0, (root.y + .075) / .085))
            return .16 + .84 * f * f * (3 - 2 * f)
        for lift0, lift1, n_cards, w in ((.001, .008, 560, .018), (.0015, .016, 480, .020), (.002, .024, 360, .022),
                                         (.003, .030, 200, .022)):     # roots on the scalp, volume above
            for _ in range(n_cards):
                root, nrm = rnd.choice(scalp.pts)
                L = (root - tie).length * 1.05
                pts = grow(scalp, root, nrm, direction, L, lift0, max(lift0 + .0008, lift1 * vol(root)), steps=10,
                           stop=lambda p: (p - tie).length < .010, bulge=True)
                if len(pts) > 2:
                    # (a broad card rooted at the forehead's edge ends there as a block: the edge is made of fine ones)
                    edge = root.y < -.02 and root.z < line_z(root) + .014
                    card(bm, uv, pts, w * rnd.uniform(.8, 1.2) * (.38 if edge else 1.0), rnd.choice((2, 3)) if edge else rnd.randrange(3),
                         twist=rnd.uniform(-.2, .2), tip_width=.9)
        band = hairline_band(info, area_low, line_z, rnd)
        for _ in range(760):
            root, nrm = rnd.choice(band)
            pts = grow(scalp, root, nrm, direction, rnd.uniform(.016, .038), .0006, .002, steps=4)
            if len(pts) > 2:
                card(bm, uv, pts, rnd.uniform(.0035, .0065), rnd.choice((2, 3)), twist=rnd.uniform(-.2, .2), tip_width=.9)
        # the front: combed straight back from the hairline into the tie, close to the head, in narrow cards (one
        # direction, nothing across it, nothing lifted: a fringe over these cards read as a tangle, a lifted front as
        # a fold)
        fr = [(r, n) for r, n in scalp.pts if r.y < -.020 and line_z(r) - .002 < r.z < line_z(r) + .034]
        for _ in range(980):
            root, nrm = rnd.choice(fr)
            L = (root - tie).length * 1.02
            pts = grow(scalp, root, nrm, direction, L, .0008, rnd.uniform(.0025, .0055), steps=12,
                       stop=lambda p: (p - tie).length < .012, bulge=True)
            if len(pts) > 2:
                card(bm, uv, pts, rnd.uniform(.0038, .0075), rnd.choice((0, 1, 2, 2, 3, 3)), twist=rnd.uniform(-.06, .06), tip_width=.9)
        # the ponytail: long cards from the tie, out and up a little, then falling behind, spreading toward the ends
        tail_dir = Vector((0, .6, .12)).normalized()
        for i in range(420):
            a = rnd.uniform(0, 2 * math.pi)
            r0 = rnd.uniform(0, .024)
            off = Vector((math.cos(a) * r0, math.sin(a) * r0 * .6, math.sin(a) * r0 * .6))
            L = rnd.uniform(.40, .54)                    # to the shoulder blades
            spread = rnd.uniform(.015, .055)
            pts = []
            steps = 16
            p = tie + off + tail_dir * .012
            d = tail_dir.copy()
            for k in range(steps + 1):
                t = k / steps
                outward = off.normalized() if off.length > 1e-6 else Vector((0, 1, 0))
                n_ = (outward + Vector((0, .3, 0))).normalized()
                swell = math.sin(math.pi * min(1.0, t * 1.4)) * .010   # body: the tail puffs out below the tie
                pts.append((p + outward * (spread * t * t + swell), n_))
                d = (d + Vector((0, -.012, -.30))).normalized()
                p = p + d * (L / steps)
            card(bm, uv, pts, rnd.uniform(.022, .034), rnd.randrange(ATLAS_COLS), tip_width=.75)
        name = "C_hair__ponytail"
    o = garment.obj(bm, "cards", "orion_black")
    o.data.materials.clear()
    o.data.materials.append(mat_cards)
    # the cap: the scalp's hair area pushed out a touch, in the strand texture (tiled), under the cards
    shrink = .004                                         # the cap's soft edge starts just inside the hairline
    cap = from_faces(info, "cap", lambda c, r: r == "head" and area(c), lambda co, n, r: .0008, "orion_black",
                     hem=0, wrinkle=0)
    cap.data.materials.clear()
    cap.data.materials.append(mat_cap)
    soft_cap(cap, info)
    parts = [cap, o]
    if not m:
        parts.append(tie_band(tie + tail_dir * .010, tail_dir, .021, .0055))
        # the tail's root is solid hair (a dome in the cap texture) so no hollow shows inside the band
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=.019, location=tie + tail_dir * .006)
        plug = bpy.context.active_object
        plug.scale = (1, 1, 1)
        plug.data.materials.append(mat_cap)
        plug.data.uv_layers[0].name = "UVMap"
        for d in plug.data.uv_layers[0].data:
            d.uv = (d.uv.x * 4, 0.0)                      # the scalp texture's solid fill (v = 0)
        for poly in plug.data.polygons:
            poly.use_smooth = True
        parts.append(plug)
    log(f"hair: {len(o.data.polygons)} card quads")
    return join(parts, name)


def scalp_texture(path, size=512, seed=5):
    """the cap's texture: u runs along the hairline (tiles), v inward from the edge (0) to 12 mm in (1). Fine strands
    start at staggered depths so the edge breaks up into single hairs, over a fill that fades in toward v = 1"""
    if os.path.exists(path):
        return path
    rng = np.random.RandomState(seed)
    H = W = size
    v = (np.arange(H, dtype=np.float32) + .5) / H
    alpha = np.tile((np.clip((v - .35) / .55, 0, 1) ** 1.5)[:, None], (1, W)) * .9
    col = np.tile((.35 + .3 * v)[:, None], (1, W))
    for _ in range(900):
        x0 = rng.uniform(0, W)
        start = rng.uniform(0, .9) ** .7                     # most strands start a little way in
        wpx = rng.uniform(.6, 1.3)
        lean = rng.uniform(-.08, .08) * W
        wave = rng.uniform(0, 2)
        ph = rng.uniform(0, 6.3)
        rows = np.nonzero(v >= start)[0]
        t = v[rows]
        xs = x0 + lean * (t - start) + wave * np.sin(t * 9 + ph)
        k = np.clip((t - start) / .08, 0, 1) * rng.uniform(.6, 1.0)
        for dx in range(-2, 3):
            X = (np.floor(xs).astype(int) + dx) % W
            a = np.maximum(0.0, 1 - np.abs(X + .5 - (xs % W)) / wpx) * k
            upd = a > alpha[rows, X]
            alpha[rows[upd], X[upd]] = a[upd]
            col[rows[upd], X[upd]] = rng.uniform(.6, 1.1) * (.5 + .5 * t[upd])
    img = np.dstack([np.repeat(np.clip(col, 0, 1)[..., None], 3, 2), alpha])[::-1]
    im = bpy.data.images.new(os.path.splitext(os.path.basename(path))[0], W, H, alpha=True)
    im.pixels.foreach_set(img.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    return path


def soft_cap(o, info, depth=.018, smooth=8):
    """the cap's border made a smooth curve (whole faces leave a staircase), then UVs: v = distance in from the
    border / depth (the scalp texture fades in), u along the border (angle round the head)"""
    import heapq
    bm = bmesh.new()
    bm.from_mesh(o.data)
    border = [v for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
    for _ in range(smooth):                              # smooth the border along itself, back onto the scalp
        new = {}
        for v in border:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                new[v] = v.co * .5 + (nb[0].co + nb[1].co) * .25
        for v, co in new.items():
            loc, nrm, _, _ = info.bvh.find_nearest(co)
            v.co = loc + nrm * .0008
    dist = {v: 0.0 for v in border}                      # distance in from the border over the mesh
    heap = [(0.0, v.index, v) for v in border]
    heapq.heapify(heap)
    while heap:
        d, _, v = heapq.heappop(heap)
        if d > dist.get(v, 1e9):
            continue
        for e in v.link_edges:
            w = e.other_vert(v)
            nd = d + e.calc_length()
            if nd < dist.get(w, 1e9):
                dist[w] = nd
                heapq.heappush(heap, (nd, w.index, w))
    uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")    # (the cards' layer name: join merges by name)
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            u = math.atan2(co.x, -(co.y - .01)) * .085 / .02     # ~2 cm of edge per texture tile
            loop[uv].uv = (u, 1 - min(1.0, dist.get(loop.vert, depth) / depth))
    bm.to_mesh(o.data)
    bm.free()


def tie_band(c, axis, R, r, segs=28, sides=10):
    """the hair tie: an elastic band (a flattened torus) round the ponytail's root"""
    from wardrobe import material
    axis = axis.normalized()
    u = axis.cross(Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((1, 0, 0))).normalized()
    v = axis.cross(u)
    bm = bmesh.new()
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        radial = u * math.cos(a) + v * math.sin(a)
        ring = []
        for j in range(sides):
            b = 2 * math.pi * j / sides
            ring.append(bm.verts.new(c + radial * (R + r * .7 * math.cos(b)) + axis * (r * 1.4 * math.sin(b))))
        rings.append(ring)
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % segs]
        for j in range(sides):
            f = bm.faces.new((A[j], A[(j + 1) % sides], B[(j + 1) % sides], B[j]))
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("tie")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("tie", me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(material("orion_black"))
    me.uv_layers.new(name="UVMap")
    return o


def cap_uv(o):
    """the cap's UVs: strands running from the front of the head toward the back (v along y), tiled"""
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active.data
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl[li].uv = ((math.atan2(co.x, co.z - 1.0) * .25) % 1.0 * .25, co.y * 4.0)


# ------------------------------------------------------------------------------------------------ brows and lashes

def lash_texture(path, size=256, seed=9):
    """eyelashes: ~14 thick, tapered, slightly curved strands per card (v = 0 at the lid), dark at the root"""
    if os.path.exists(path):
        return path
    rng = np.random.RandomState(seed)
    H = W = size
    v = (np.arange(H, dtype=np.float32) + .5) / H
    alpha = np.zeros((H, W), np.float32)
    col = np.zeros((H, W), np.float32)
    for k in range(14):
        x0 = (k + .5 + rng.uniform(-.3, .3)) / 14 * W
        length = rng.uniform(.70, 1.0)
        w0 = rng.uniform(4.5, 7.0)
        bend = rng.uniform(-.10, .10) * W
        n = int(length * H)
        t = v[:n] / length
        xs = x0 + bend * t * t
        wpx = np.maximum(.6, w0 * (1 - t) ** .8)
        for dx in range(-8, 9):
            X = np.floor(xs).astype(int) + dx
            ok = (X >= 0) & (X < W)
            a = np.clip(1.2 - np.abs(X + .5 - xs) / wpx, 0, 1) * np.clip(1.4 - t, 0, 1)
            rows = np.nonzero(ok & (a > alpha[np.arange(n), np.clip(X, 0, W - 1)]))[0]
            alpha[rows, X[rows]] = a[rows]
            col[rows, X[rows]] = .35 + .4 * t[rows]
    img = np.dstack([col, col, col, alpha])[::-1]
    im = bpy.data.images.new(os.path.splitext(os.path.basename(path))[0], W, H, alpha=True)
    im.pixels.foreach_set(img.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    return path


def tex_dir(T=None):
    """the generated textures' folder: SourceArt/Characters/src/tex/<sex> (each body has its own files, nothing shared)"""
    base = os.environ.get("HERO_TEX") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "unreal", "ShatteredOrbit", "SourceArt",
        "Characters", "src", "tex")
    return os.path.normpath(os.path.join(base, T["sex"]) if T else base)


def tex_path(T, kind):
    """hero_<sex>_<kind>.png in the body's own folder"""
    d = tex_dir(T)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"hero_{T['sex']}_{kind}.png")


def ribbon(bm, uv, pts, side, w0, w1, col, mat=0, full=False):
    """a card along pts whose width runs along `side` (one vector or one per point), w0 at the root to w1 at the tip;
    UV u across atlas column col, v root -> tip"""
    n = len(pts)
    u0, u1 = (0.0, 1.0) if full else (col / ATLAS_COLS + .01, (col + 1) / ATLAS_COLS - .01)
    rows = []
    for i, p in enumerate(pts):
        s = side[i] if isinstance(side, list) else side
        w = w0 + (w1 - w0) * i / (n - 1)
        rows.append((bm.verts.new(p - s * w / 2), bm.verts.new(p + s * w / 2), i / (n - 1)))
    for (a0, b0, v0), (a1, b1, v1) in zip(rows, rows[1:]):
        f = bm.faces.new((a0, b0, b1, a1))
        f.material_index = mat
        f.smooth = True
        for loop, (u, v) in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            loop[uv].uv = (u, 1 - v)


def eye_frames(body, eyes):
    """per eye (left first): centre, radius and the lid margin (the body's boundary loop round it) split into the upper
    and lower lid, each ordered from the inner corner (canthus) to the outer"""
    from wardrobe import boundary_loops
    me = body.data
    P = [v.co.copy() for v in eyes.data.vertices]
    out = []
    for sx in (1, -1):
        side = [p for p in P if p.x * sx > 0]
        c = sum(side, Vector()) / len(side)
        r = max((p - c).length for p in side)
        if "eye_margins" in body.keys():                      # (fit.eye_sockets closed the opening behind the lids)
            import json
            L = min(([Vector(p) for p in M] for M in json.loads(body["eye_margins"])),
                    key=lambda M: (sum(M, Vector()) / len(M) - c).length)
            m0 = sum(L, Vector()) / len(L)
            L.sort(key=lambda p: math.atan2(p.z - m0.z, p.x - m0.x))
        else:
            loop = min(boundary_loops(body), key=lambda L: (sum((me.vertices[i].co for i in L), Vector()) / len(L) - c).length)
            L = [me.vertices[i].co.copy() for i in loop]
        inner = min(range(len(L)), key=lambda i: abs(L[i].x))
        outer = max(range(len(L)), key=lambda i: abs(L[i].x))
        a = L[inner:] + L[:inner]                                  # starts at the inner corner
        k = (outer - inner) % len(L)
        arc1, arc2 = a[:k + 1], a[k:] + a[:1]
        arc2.reverse()                                             # both from inner to outer
        up, lo = (arc1, arc2) if sum(p.z for p in arc1) / len(arc1) > sum(p.z for p in arc2) / len(arc2) else (arc2, arc1)
        out.append((sx, c, r, up, lo))
    return out


def visible_edge(bvh, ebvh, p, up, step=.00025, reach=.0035):
    """the lid's visible edge near the margin point p: the lid skin can overhang the margin (which then hides behind
    it), so step from p toward the opening's middle (down for the upper lid, up for the lower) until a ray from the
    front meets the eye before the skin; the root is the last skin point (a hair inside the edge)"""
    last = None
    ray = Vector((0, 1, 0))
    for k in range(int(reach / step)):
        q = Vector((p.x, -.4, p.z - up * k * step))
        hb = bvh.ray_cast(q, ray)[0]
        he = ebvh.ray_cast(q, ray)[0]
        if he is not None and (hb is None or he.y < hb.y - .0002):
            break
        if hb is not None:
            last = hb
    else:
        return p                                         # (no eye in reach: a corner, keep the margin point)
    return (last + Vector((0, -.0003, 0))) if last is not None else p


def along(arc, t):
    """the point at fraction t of a polyline's length, and its tangent"""
    seg = [(arc[i + 1] - arc[i]).length for i in range(len(arc) - 1)]
    s = t * sum(seg)
    for i, d in enumerate(seg):
        if s <= d or i == len(seg) - 1:
            f = min(1.0, s / d) if d > 1e-9 else 0
            return arc[i].lerp(arc[i + 1], f), (arc[i + 1] - arc[i]).normalized()
        s -= d


def face_hair(body, eyes, arm, T, log=print):
    """B_brows: eyebrows and eyelashes as strand cards in the head hair's atlas (materials hair__brow, hair__lash),
    part of the body (they stay whatever hair is worn), all on the head bone"""
    from mathutils.bvhtree import BVHTree
    m = T["sex"] == "male"
    rnd = random.Random(23 if m else 29)
    tex = atlas(tex_path(T, "hair_strands"))
    sbm = bmesh.new()
    sbm.from_mesh(body.data)
    bvh = BVHTree.FromBMesh(sbm)
    ebm = bmesh.new()
    ebm.from_mesh(eyes.data)
    ebvh = BVHTree.FromBMesh(ebm)
    ebm.free()
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    lash_faces = 0
    fwd = Vector((0, -1, 0))
    for sx, c, r, up, lo in eye_frames(body, eyes):
        # lashes: two staggered rows of small clumps on the upper lid, curling forward and up, longest past the middle
        # and swept outward at the outer corner; a sparse short row on the lower lid
        for lid, n_cards, (Lmin, Lmax), curl in ((up, 72, (.0090, .0130) if not m else (.0072, .0105), 1),
                                                 (lo, 22, (.0028, .0045), -1)):
            for k in range(n_cards):
                t = .06 + .90 * (k + rnd.uniform(-.3, .3)) / (n_cards - 1)
                t = min(.97, max(.03, t))
                p, tan = along(lid, t)
                radial = (p - c).normalized()
                p = visible_edge(bvh, ebvh, p, curl)          # where the lid's skin meets the eye, seen from the front
                outward = Vector((sx, 0, 0)) * (max(0.0, t - .55) * 1.2)
                d0 = (radial * .45 + fwd * .85 + outward).normalized()
                L = (Lmin + (Lmax - Lmin) * math.sin(math.pi * min(1.0, t * 1.15))) * rnd.uniform(.85, 1.1)
                upv = Vector((0, 0, curl))
                pts = []
                for i in range(5):
                    s = i / 4
                    pts.append(p + d0 * (L * s) + upv * (L * .6 * s * s))
                ribbon(bm, uv, pts, tan, .0040 if curl > 0 else .0022, .0034 if curl > 0 else .0018, 2, mat=1, full=True)
                lash_faces += 4
        # brows: short hairs over the brow band, lying on the skin: the inner head grows up, the body and tail outward
        ix = .013 if m else .014
        ex, ez_ = abs(c.x), c.z
        inner = Vector((ix, 0, ez_ + (.015 if m else .017)))
        peak = Vector((ex + .006, 0, ez_ + (.023 if m else .024)))
        tail = Vector((ex + .027, 0, ez_ + (.015 if m else .019)))
        thick = (.012, .0135, .0060) if m else (.0065, .0058, .0024)

        def curve(u):
            if u < .62:
                f = u / .62
                return inner.lerp(peak, f), thick[0] + (thick[1] - thick[0]) * f
            f = (u - .62) / .38
            return peak.lerp(tail, f), thick[1] + (thick[2] - thick[1]) * f
        for _ in range(1100 if m else 460):
            u = rnd.random() ** .9
            q, h = curve(u)
            a_ = (rnd.random() + rnd.random()) / 2 - .5           # denser along the middle: soft, feathered edges
            h *= math.sqrt(min(1.0, u / .08)) if u < .08 else 1.0   # the inner head rounds off
            q = Vector((q.x * sx, -.2, q.z + a_ * h))
            hit, nrm, _, _ = bvh.ray_cast(q, Vector((0, 1, 0)))          # onto the brow from the front
            if hit is None:
                continue
            ang = math.radians(75 - 95 * min(1.0, u / .35)) if u < .35 else math.radians(-20 - 25 * (u - .35) / .65)
            dirn = Vector((math.cos(ang) * sx, 0, math.sin(ang)))      # in the face plane: up at the head, out at the tail
            dirn = (dirn - nrm * dirn.dot(nrm)).normalized()
            L = rnd.uniform(.0055, .0100 if m else .0085) * (1.0 if u > .1 else .8)
            pts = []
            p = hit
            for i in range(4):
                loc, n2, _, _ = bvh.find_nearest(p)
                pts.append(loc + n2 * (.0003 + .0009 * i / 3))
                p = loc + dirn * (L / 3)
            side = nrm.cross(dirn).normalized()
            ribbon(bm, uv, pts, side, .0026 if m else .0014, .0010, rnd.choice((0, 1, 2, 2) if m else (2, 2, 3)))
    sbm.free()
    me = bpy.data.meshes.new("B_brows")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("B_brows", me)
    bpy.context.scene.collection.objects.link(o)
    brow = hair_material("hair__brow", tex)
    lash = hair_material("hair__lash", lash_texture(tex_path(T, "hair_lash")))
    me.materials.append(brow)
    me.materials.append(lash)
    vg = o.vertex_groups.new(name="head")
    vg.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    o.parent = arm
    mod = o.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    log(f"face hair: {len(me.polygons)} card quads ({lash_faces} lashes)")
    return o
