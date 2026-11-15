"""The Void Sentinel armour (the owner's "Void Sentinel" concept sheet, art/reference/operation/void_sentinel_armor.png):
the reward set of the first operation, one piece per wardrobe slot, built on each body's own surface.

  head    C_head__void_sentinel   a sealed helmet: an angular peak over a V-shaped violet visor, jaw guards, a
                                  muzzle, swept temple fins, nape lames (hers slimmer, a narrower visor)
  vest    C_vest__void_sentinel   the cuirass: a chest shield over two pectoral plates, chevron lames down the belly,
                                  slanted flank lames, a gorget, a yoke over the shoulders, back and spine plates,
                                  a plated belt with pouches, three-lame pauldrons and upper-arm plates
  hands   C_hands__void_sentinel  gauntlets: elbow cops, vambraces, a cuff, hand and knuckle plates, finger plates
  legs    C_legs__void_sentinel   tassets, a fauld plate, cuisses, layered knee cops, greaves and calf plates
  feet    C_feet__void_sentinel   armoured boots on the boot last: toe cap, instep lames, heel cup, ankle guards,
                                  shaft plates, a cuff, a lugged sole
  outer   C_outer__void_sentinel  the cloak: a cowl round the neck and over the shoulders, a long tattered cape with
                                  our own emblem on the back

How it is made (the helmet's method, headgear.py, carried to the whole body): under everything a close black
under-suit (the body's own faces pushed out); over it a BASE surface (the suit's shape eased and draped smooth, so
armour reads as armour and not as painted muscle); every plate is a piece of that base cut to an outline
(headgear.cut_plate: the open edge is slid exactly onto the outline, lifted, given thickness and a chamfered rim).
Outlines are convex polygons in each limb's own coordinates (`Cyl`: along the bone / round it), so both bodies get
the same plates at their own size. Plates lie in layers: an upper plate's lift clears the top of the one under it.
Lines of light are ribbons laid on the plates. Plates are rigid: each one follows ONE bone (the bone that carries
most of it), so armour never stretches like rubber; only what spans a joint (the suit, the belt, the yoke, the
tassets) keeps the body's blended weights. The pauldrons ride half on the clavicle, half on the upper arm.

Materials (names are an API): vs_suit (under-suit), vs_plate (gunmetal: the paint is in the corner colour, finish.py),
vs_plate_dark (the black plates), vs_trim (dark steel: belt, cuffs, frames), vs_glow (the violet light: every line),
vs_visor (the visor's lit glass), vs_cloak, vs_emblem, vs_sole.

Add the set to a saved, rigged build (fast; the way reclip.py re-bakes clips):
  blender -b <saved.blend> -P tools/blender/hero/void_sentinel.py -- male|female [--only=vest,legs,...]
          [--save=out.blend] [--glb=out.glb] [--frames=dir [--clips=Idle,Run] [--n=3]]
A full build (build.py -> wardrobe.dress) makes the same pieces.
"""
import json
import math
import os
import sys
import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

F32 = np.float32
SET = "void_sentinel"
SUIT, PLATE, DARK, TRIM, GLOW, VISOR, CLOAK, EMBLEM, SOLE = ("vs_suit", "vs_plate", "vs_plate_dark", "vs_trim", "vs_glow",
                                                             "vs_visor", "vs_cloak", "vs_emblem", "vs_sole")
# (colour, roughness, metallic). The plates are a light neutral: their paint is in the corner colour (finish.py)
PALETTE = {
    SUIT: ((.013, .013, .016), .78, 0.0),
    PLATE: ((.62, .63, .65), .36, .60),
    DARK: ((.62, .63, .65), .42, .50),
    TRIM: ((.045, .047, .054), .32, .85),
    GLOW: ((.40, .14, 1.0), .30, 0.0),
    VISOR: ((.30, .10, .85), .08, .30),
    CLOAK: ((.014, .014, .017), .90, 0.0),
    EMBLEM: ((.42, .42, .46), .55, .20),
    SOLE: ((.008, .008, .008), .90, 0.0),
}
# the paint on the neutral plates (multipliers), and what a quick look (workbench) shows for each material
PAINT = {PLATE: (.250, .262, .295), DARK: (.060, .062, .072)}
LOOK = {SUIT: (.03, .03, .035), PLATE: (.23, .24, .27), DARK: (.075, .078, .09), TRIM: (.11, .115, .13),
        GLOW: (.55, .22, 1.0), VISOR: (.45, .16, .95), CLOAK: (.045, .045, .05), EMBLEM: (.42, .42, .46), SOLE: (.02, .02, .02)}
TEXTURED = {SUIT: "knit", PLATE: "polymer", DARK: "polymer", CLOAK: "twill", SOLE: "rubber"}
SLOTS = ("head", "vest", "hands", "legs", "feet", "outer")

# how a part follows the skeleton (the per-vertex attribute `vs_bind`, read by after_skin)
BIND = ("auto", "soft", "chest", "spine", "hips", "head", "neck", "clavicle", "upperarm", "forearm", "hand", "thigh",
        "shin", "foot", "pauldron", "cape", "knee", "elbow",
        "index_01", "index_02", "middle_01", "middle_02", "ring_01", "ring_02", "pinky_01", "pinky_02")
# plates that sit ON a joint ride half on each bone: they stay over the joint as it bends and keep their shape
HALF = {"pauldron": ("clavicle", "upperarm"), "knee": ("thigh", "shin"), "elbow": ("upperarm", "forearm")}
CENTRE = ("chest", "spine", "hips", "head", "neck")


def materials():
    import wardrobe
    for name, (col, rough, metal) in PALETTE.items():
        wardrobe.PALETTE.setdefault(name, (col, rough, metal))
        m = wardrobe.material(name)
        b = m.node_tree.nodes.get("Principled BSDF")
        if name in (GLOW, VISOR) and b is not None:
            b.inputs["Emission Color"].default_value = (*col, 1)
            b.inputs["Emission Strength"].default_value = 6.0 if name == GLOW else 2.5
        m.diffuse_color = (*LOOK[name], 1)


def textures(T, out_dir):
    """the set's own cloth / polymer textures (fabric.py), this body's own files: hero_<sex>_vs_<name>_*.png"""
    import zlib
    import fabric
    for name, kind in TEXTURED.items():
        if name not in bpy.data.materials:
            continue
        col, rough, metal = PALETTE[name]
        paths = fabric.make(kind, col, rough, out_dir, f"hero_{T['sex']}_{name}", metal, seed=zlib.crc32(name.encode()) % 9973)
        fabric.texture_material(name, paths, None)
        bpy.data.materials[name].diffuse_color = (*LOOK[name], 1)


# ------------------------------------------------------------------------------------------------ outlines

def A(v):
    return np.array(tuple(v), F32)


def poly(u, v, pts):
    """signed distance-like value of a convex polygon in (u, v): negative inside (the largest of its edges' half
    planes)"""
    pts = [(float(x), float(y)) for x, y in pts]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    if area < 0:
        pts.reverse()
    d = None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        ex, ey = x1 - x0, y1 - y0
        ln = math.hypot(ex, ey)
        e = (u - x0) * (ey / ln) + (v - y0) * (-ex / ln)
        d = e if d is None else np.maximum(d, e)
    return d


def inter(*d):
    return np.maximum.reduce(d)


class Cyl:
    """a limb's (or the trunk's) own coordinates: t along the axis from a (metres), u round it as an arc length at the
    nominal radius R (0 on `ref`, positive toward `pos`), rho from the axis. mirror: the right side maps onto the left"""

    def __init__(self, a, b, ref, R, pos=None, mirror=True):
        self.a = A(a)
        ax = A(b) - self.a
        self.L = float(np.linalg.norm(ax))
        self.ax = (ax / self.L).astype(F32)
        e1 = A(ref)
        e1 = e1 - self.ax * float(e1 @ self.ax)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(self.ax, e1)
        if pos is not None and float(e2 @ A(pos)) < 0:
            e2 = -e2
        self.e1, self.e2, self.R, self.mirror = e1.astype(F32), e2.astype(F32), float(R), mirror

    def __call__(self, P):
        Q = np.array(P, F32)
        if self.mirror:
            Q[:, 0] = np.abs(Q[:, 0])
        d = Q - self.a
        t = d @ self.ax
        r = d - t[:, None] * self.ax
        th = np.arctan2(r @ self.e2, r @ self.e1)
        return th * self.R, t, np.sqrt((r * r).sum(1))

    def point(self, u, t, rad=None):
        th = u / self.R
        rr = self.R if rad is None else rad
        return Vector((self.a + self.ax * t + (self.e1 * math.cos(th) + self.e2 * math.sin(th)) * rr).tolist())


# ------------------------------------------------------------------------------------------------ parts

class Parts(list):
    def add(self, o, bind="auto"):
        if o is None:
            return None
        tag(o, bind)
        self.append(o)
        return o


def tag(o, bind):
    me = o.data
    at = me.attributes.get("vs_bind") or me.attributes.new("vs_bind", 'INT', 'POINT')
    at.data.foreach_set("value", [BIND.index(bind)] * len(me.vertices))


def mirrored(parts):
    """the right-hand copies of parts built on the left"""
    out = Parts()
    for p in parts:
        c = p.copy()
        c.data = p.data.copy()
        bpy.context.scene.collection.objects.link(c)
        for v in c.data.vertices:
            v.co.x = -v.co.x
        c.data.flip_normals()
        out.append(c)
    return out


def shell(info, keep, off, cuts=()):
    """the body's faces where keep(centre, region), cut clean along planes (co, no[, both sides]: what lies on the
    +no side goes; both sides = the same cut mirrored onto the right limb), then pushed out along the normals by off
    (a number or a function)"""
    from coat import strip_shape_layers
    bm = info.bm.copy()
    bm.faces.ensure_lookup_table()
    drop = [f for f, r in zip(bm.faces, info.face_region) if not keep(f.calc_center_median(), r)]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    strip_shape_layers(bm)
    for cut in cuts:
        co, no = Vector(cut[0]), Vector(cut[1]).normalized()
        sides = ((1, co, no), (-1, Vector((-co.x, co.y, co.z)), Vector((-no.x, no.y, no.z)))) if len(cut) > 2 and cut[2] else ((0, co, no),)
        for sx, c_, n_ in sides:
            faces = [f for f in bm.faces if sx == 0 or f.calc_center_median().x * sx > 0]
            geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + faces
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=c_, plane_no=n_, clear_outer=True)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.normal_update()
    moved = [v.co + v.normal * (off(v.co) if callable(off) else off) for v in bm.verts]
    for v, p in zip(bm.verts, moved):
        v.co = p
    bm.normal_update()
    return bm


def suit(bm, name, keep=.5, tile=True):
    """the under-suit: the shell itself, one-sided (nothing looks into it: every opening is covered by the next
    piece) and thinned (most of it lies under the plates)"""
    import wardrobe
    import fabric
    from boots import decimate
    o = wardrobe.to_object(bm.copy(), name, SUIT)
    if keep < 1.0:                                            # (the open edges and the rings next to them keep every
        bm2 = bmesh.new()                                     # vertex: a collapse there leaves the hem ragged)
        bm2.from_mesh(o.data)
        hold = {v.index for v in bm2.verts if v.is_boundary}
        for _ in range(2):
            hold |= {e.other_vert(v).index for v in bm2.verts if v.index in hold for e in v.link_edges}
        free = [v.index for v in bm2.verts if v.index not in hold]
        bm2.free()
        g = o.vertex_groups.new(name="thin")
        g.add(free, 1.0, 'REPLACE')
        md = o.modifiers.new("thin", 'DECIMATE')
        md.ratio = keep
        md.vertex_group = "thin"
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=md.name)
        o.vertex_groups.remove(o.vertex_groups["thin"])
        for p_ in o.data.polygons:
            p_.use_smooth = True
    if tile:
        fabric.world_uvs(o, fabric.TILE["knit"])
    return o


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def rim(o, thick, chamfer, level=0, keep=1.0, region=None):
    """finishes a cut sheet (it lies where the plate's TOP is) as a plate with no hidden faces: the sheet thinned
    (level: un-subdivide passes for a sheet cut from a refined grid; keep: a collapse for any other), then one
    chamfer facet out and down along the whole outline and a wall down to the plate's underside. The outline and
    the chamfer's lower edge are hard edges: the top keeps its own smooth shading, the rim reads as a cut."""
    from boots import decimate
    if keep < 1.0:
        decimate(o, keep)
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    if level:
        bmesh.ops.unsubdivide(bm, verts=bm.verts[:], iterations=level)
    bm.normal_update()
    # thinning leaves small zigzags in the outline: ease them (each open vertex half way to the middle of its two
    # neighbours along the outline), twice
    for _ in range(2):
        new = {}
        for v in bm.verts:
            if v.is_boundary:
                nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
                if len(nb) == 2:
                    new[v] = v.co.lerp((nb[0].co + nb[1].co) / 2, .5)
        for v, co_ in new.items():
            v.co = co_
    for _ in range(3):                                           # (thinning leaves ears: faces hanging on the outline by a point)
        ears = [f for f in bm.faces if sum(1 for e in f.edges if e.is_boundary) >= 2 and len(f.verts) == 3]
        ears += [f for f in bm.faces if all(v.is_boundary for v in f.verts) and len(f.verts) == 4 and sum(1 for e in f.edges if e.is_boundary) >= 3]
        if not ears:
            break
        bmesh.ops.delete(bm, geom=list(set(ears)), context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.normal_update()
    N = {v: v.normal.copy() for v in bm.verts}                   # the surface's normal, evened out (at the open edge a
    for _ in range(2):                                           # vertex's own normal is noisy: the rim came out frayed)
        N = {v: (N[v] + sum((N[e.other_vert(v)] for e in v.link_edges), Vector())).normalized() for v in bm.verts}
    vn = {v: N[v] for v in bm.verts if v.is_boundary}
    be = [e for e in bm.edges if e.is_boundary]
    out = {}
    for e in be:
        f = e.link_faces[0]
        o_ = (e.verts[1].co - e.verts[0].co).normalized().cross(f.normal)
        if o_.dot(e.verts[0].co.lerp(e.verts[1].co, .5) - f.calc_center_median()) < 0:
            o_ = -o_
        for v in e.verts:
            out[v] = out.get(v, Vector()) + o_
    for _ in range(2):                                           # ... and the way out, evened along the outline
        new = {}
        for v, o_ in out.items():
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            new[v] = o_ + sum((out[w] for w in nb if w in out), Vector()) * .5
        out = new
    a_, b_ = {}, {}
    for v, o_ in out.items():
        o_ = o_ - vn[v] * o_.dot(vn[v])
        o_ = o_.normalized() if o_.length > 1e-6 else Vector()
        a_[v] = bm.verts.new(v.co + o_ * chamfer - vn[v] * chamfer)
        b_[v] = bm.verts.new(v.co + o_ * chamfer - vn[v] * thick)
    for e in be:
        f = e.link_faces[0]
        v0, v1 = e.verts
        lp = next(l for l in f.loops if l.edge == e)
        if lp.vert == v0:                                         # the top runs v0 -> v1 here: the rim runs back
            v0, v1 = v1, v0
        bm.faces.new((v0, v1, a_[v1], a_[v0]))
        bm.faces.new((a_[v0], a_[v1], b_[v1], b_[v0]))
        e.smooth = False
        ea = bm.edges.get((a_[v0], a_[v1]))
        if ea is not None:
            ea.smooth = False
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p_ in me.polygons:
        p_.use_smooth = True


class Base:
    """the surface the plates are cut from: a shell eased out and draped smooth over the body (it spans the hollows,
    never comes nearer the skin than `clear`), refined once"""

    def __init__(self, info, bm, ease=.0015, drape=10, clear=.0055, refine=3, field=None, own=False, reach=.010, keep=1.0, level=4):
        import wardrobe
        self.info = info
        self.bm = bm if own else bm.copy()
        bm = self.bm
        if not own:
            bm.normal_update()
            for v, p in zip(bm.verts, [v.co + v.normal * ease for v in bm.verts]):
                v.co = p
            if drape:
                wardrobe.drape_out(bm, info, drape, min_off=clear)
            if refine:
                bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=refine, use_grid_fill=True, smooth=1.0)
                for _ in range(2):
                    bmesh.ops.smooth_vert(bm, verts=[v for v in bm.verts if not v.is_boundary], factor=.5,
                                          use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        self.tree = BVHTree.FromBMesh(bm)
        self.field = field
        self.reach = reach
        self.keep = keep
        self.level = level if not own else (level if level != 4 else 0)
        self.parts = Parts()

    def plate(self, name, region, lift, thick=.0045, mat=PLATE, bevel=.0020, bind="auto", keep=None, level=None, step=None):
        """a plate: the base inside `region`, its top `lift + thick` above the base, a chamfered rim.
        step=(inset, material[, height]): a second, smaller plate on top of it (the same outline drawn in by `inset`),
        3-4 mm proud with its own chamfer: the stepped layer that makes a plate read as built, not as a shell"""
        from headgear import cut_plate
        import fabric
        o = cut_plate(self.bm, self.tree, region, lift + thick, 0, mat, "vs_" + name, 0, 1.0, field=self.field, reach=self.reach,
                      sheet=True)
        if o is None:
            return None
        rim(o, thick, min(bevel, thick * .6), self.level if level is None else level, self.keep if keep is None else keep, region)
        if mat in TEXTURED:
            fabric.world_uvs(o, fabric.TILE[TEXTURED[mat]])
        self.parts.add(o, bind)
        if step:
            inset, mat2 = step[0], step[1]
            h = step[2] if len(step) > 2 else .0034
            self.plate(name + "_step", lambda P: region(P) + inset, lift + thick + .0002, h, mat2, min(bevel, .0016), bind, keep, level)
        return o

    def on(self, p):
        loc, n, _, _ = self.tree.find_nearest(Vector(p))
        if self.field is not None:
            import sdf
            n = Vector(sdf.normals(self.field, np.array([loc[:]], F32))[0].tolist())
        return loc, n

    def light(self, name, pts, top, width=.0022, bind="auto", mirror=True, mat=GLOW):
        """a slit of light: a thin flat ribbon along pts (snapped onto the base) lying in the top of a plate whose top
        is `top` above the base; with its mirror image on the right"""
        import garment
        path = []
        for p in pts:
            loc, n = self.on(p)
            path.append((loc + n * top, n))
        o = garment.trim_strip(path, width, mat, lift=.0005, step=.012, name="vs_" + name)
        if o is None:
            return
        self.parts.add(o, bind)
        if mirror:
            for c in mirrored([o]):
                self.parts.add(c, bind)

    def free(self):
        self.bm.free()


def boxed(parts, name, size, R, at, mat=TRIM, bevel=.004, bind="auto"):
    import garment
    return parts.add(garment.rounded_box(size, R, at, mat, bevel=bevel, segs=2, name="vs_" + name), bind)


# ------------------------------------------------------------------------------------------------ the cuirass

def span_cleft(bm, z0, z1, y0=.012):
    """her breastplate is ONE plate: in every thin horizontal slice of the front between z0 and z1 the surface is
    pushed out to that slice's convex outline (the cleft and the hollows beside the bust are spanned), then eased"""
    from mathutils import geometry
    vs = [v for v in bm.verts if z0 <= v.co.z <= z1 and v.co.y < y0 + .03 and abs(v.co.x) < .16]
    rows = {}
    for v in vs:
        rows.setdefault(int(v.co.z / .007), []).append(v)
    o = Vector((0, y0))
    for row in rows.values():
        pts = [Vector((v.co.x, v.co.y)) for v in row]
        if len(pts) < 6:
            continue
        H = [pts[i] for i in geometry.convex_hull_2d(pts)]
        for v in row:
            d = Vector((v.co.x, v.co.y)) - o
            r = d.length
            if r < 1e-6:
                continue
            d /= r
            best = r
            for a_, b_ in zip(H, H[1:] + H[:1]):
                hit = geometry.intersect_line_line_2d(o, o + d * .6, a_, b_)
                if hit is not None:
                    best = max(best, (hit - o).length)
            k_ = min(1.0, (v.co.z - z0) / .02, (z1 - v.co.z) / .02)       # eased in at the top and the bottom
            rr = r + (best - r) * max(0.0, k_)
            v.co.x, v.co.y = d.x * rr, y0 + d.y * rr
    # ... and down every meridian the same way (no hollow under or over the bust: one dome from the collar bones to
    # the under-bust line)
    cols = {}
    for v in vs:
        d = Vector((v.co.x, v.co.y)) - o
        cols.setdefault(int(math.degrees(math.atan2(abs(d.x), -d.y)) / 7.0), []).append(v)
    for col in cols.values():
        pts = [Vector((v.co.z, (Vector((v.co.x, v.co.y)) - o).length)) for v in col]
        if len(pts) < 5:
            continue
        H = [pts[i] for i in geometry.convex_hull_2d(pts)]
        for v, q in zip(col, pts):
            best = q.y
            for a_, b_ in zip(H, H[1:] + H[:1]):
                if min(a_.x, b_.x) - 1e-6 <= q.x <= max(a_.x, b_.x) + 1e-6 and abs(b_.x - a_.x) > 1e-6:
                    best = max(best, a_.y + (b_.y - a_.y) * (q.x - a_.x) / (b_.x - a_.x))
            k_ = max(0.0, min(1.0, (v.co.z - z0) / .02, (z1 - v.co.z) / .02))
            d = Vector((v.co.x, v.co.y)) - o
            if d.length > 1e-6:
                d = d.normalized() * (q.y + (best - q.y) * k_)
                v.co.x, v.co.y = d.x, y0 + d.y
    for _ in range(10):
        bmesh.ops.smooth_vert(bm, verts=vs, factor=.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.normal_update()


def torso_frame(info):
    T = info.T
    R = (T["chest"]["w"] + T["chest"]["d"]) / 4
    return Cyl((0, .012, 0), (0, .012, 1), (0, -1, 0), R, pos=(1, 0, 0))


def vest(info, log=print):
    import wardrobe
    T, m = info.T, info.m
    C, U, Wt, Hp = T["chest"], T["underbust"], T["waist"], T["hips"]
    zc, zu, zw, zh, znb = C["z"], U["z"], Wt["z"], Hp["z"], T["neck_base_z"]
    k = C["w"] / .355
    S, E, a_ = info.A["S"], info.A["E"], info.A["a"]
    dorsal, thumb = info.A["dorsal"], info.A["thumb"]

    def keep(c, r):
        if r in ("chest", "midriff"):
            return True
        if r in ("upperarm", "forearm"):
            return (Vector((abs(c.x), c.y, c.z)) - E).dot(a_) < .03
        if r == "pelvis":
            return c.z > zh + .005
        if r == "neck":
            return c.z < znb + .060
        return False
    sh = shell(info, keep, .0035, cuts=[((0, 0, znb + .036), (0, 0, 1)), ((0, 0, zh + .030), (0, 0, -1)), (E - a_ * .004, a_, True)])
    parts = Parts()
    parts.add(suit(sh, "vs_suit_torso"), "soft")
    shaped = sh.copy()
    if not m:
        for v, co_ in zip(shaped.verts, [v.co + v.normal * .003 for v in shaped.verts]):
            v.co = co_
        span_cleft(shaped, zu - .020, zc + .100)
    base = Base(info, shaped, ease=.0015, drape=36 if m else 6, clear=.0058)
    shaped.free()
    tor = torso_frame(info)
    half = math.pi * tor.R                                   # the arc from the front centre to the back centre

    lim = C["w"] / 2 + .045                                  # the trunk only: the upper arm (it is part of this base)
                                                             # lies at the same angle and height as the flanks, and
    def front(P):                                            # a patch of it bound to the chest stays behind in the air
        u, z, r = tor(P)
        return u, np.where(r > lim, z + 10.0, z)

    def back(P):
        u, z, r = tor(P)
        return half - u, np.where(r > lim, z + 10.0, z)

    # ---- the front: ONE upper plate across the chest (hers too: an armoured plate, no cups: her base spans the
    # cleft), a darker panel stepped on it, a keel down the middle, and two collar plates in a V above it
    zt, zm, zb = zc + .090, zc + .020, zu + .004
    chest = [(-.040 * k, zt), (-.150 * k, zt - .012), (-.170 * k, zc + .002), (-.152 * k, zc - .062), (-.030 * k, zc - .076),
             (.030 * k, zc - .076), (.152 * k, zc - .062), (.170 * k, zc + .002), (.150 * k, zt - .012), (.040 * k, zt)]
    base.plate("chest", lambda P: poly(*front(P), chest), .0070, .0050, PLATE, bind="chest", step=(.016, DARK))
    chest_top = .0070 + .0050 + .0002 + .0034
    base.plate("keel", lambda P: poly(*front(P), [(-.016 * k, zt + .004), (.016 * k, zt + .004), (.021 * k, zm), (.007 * k, zb), (-.007 * k, zb), (-.021 * k, zm)]),
               chest_top + .0004, .0052, PLATE, .0030, bind="chest")
    keel_top = chest_top + .0004 + .0052
    neck = A((0, .02, 0))
    rn = T["neck_w"] / 2 + .034

    def rho(P):
        return np.sqrt(P[:, 0] ** 2 + (P[:, 1] - neck[1]) ** 2)
    Sn = A(S)

    def from_joint(P):
        Q = np.array(P, F32)
        Q[:, 0] = np.abs(Q[:, 0])
        return np.sqrt(((Q - Sn) ** 2).sum(1))
    # the yoke over each shoulder (never past the shoulder joint: the top of the upper arm is as high as this, and a
    # patch of it bound to the chest stays behind in the air when the arm comes down)
    base.plate("yoke", lambda P: inter(rn + .007 - rho(P), .074 - from_joint(P), zc + .099 - P[:, 2], .012 - np.abs(P[:, 0]),
                                       np.abs(P[:, 0]) - (S.x + .012)), .0080, .0050, DARK, bind="chest")
    base.plate("collar", lambda P: inter(poly(*front(P), [(.022 * k, zt + .016), (.128 * k, zt + .034), (.128 * k, zt + .056), (.022 * k, zt + .046)]),
                                         P[:, 1] - .0), .0132, .0036, PLATE, .0018, bind="chest")
    base.plate("gorget", lambda P: inter(rho(P) - rn, znb - .045 - P[:, 2]), .0095, .0055, PLATE, .0026, bind="chest")
    # ---- the belly: three chevron lames, each tucked under the one above
    z0, z1 = zh + .097, zu - .012
    step = (z1 - z0) / 3
    wl = .060 * k
    for i in range(3):
        top = z1 - step * i + (.010 if i else 0.0)
        bot = z1 - step * (i + 1)
        base.plate(f"lame{i}", lambda P, top=top, bot=bot: poly(*front(P), [(-wl, top), (wl, top), (wl, bot + .014), (0, bot), (-wl, bot + .014)]),
                   .0146 - .0048 * i, .0026, PLATE if i != 1 else DARK, .0012, bind="spine")
    # the flanks: slanted lames from beside the belly round to the back
    u0, u1 = .072 * k, half * .56
    fz0, fz1 = z0, zc - .076
    fstep = (fz1 - fz0) / 3
    rise = (u1 - u0) * .20
    for i in range(3):
        b0, t0 = fz0 + fstep * i + .004, fz0 + fstep * (i + 1) - .004
        base.plate(f"flank{i}", lambda P, b0=b0, t0=t0: poly(*front(P), [(u0, b0), (u1, b0 + rise), (u1, t0 + rise), (u0, t0)]),
                   .0060, .0042, DARK if i != 1 else PLATE, bind="spine" if i < 2 else "chest")
    # ---- the back: a spine of chevrons, shoulder-blade plates, two lower plates each side
    sp0, sp1, ns = z0, zc + .090, 5
    sst = (sp1 - sp0) / ns
    for i in range(ns):
        b0, t0 = sp0 + sst * i, sp0 + sst * (i + 1) - .006
        base.plate(f"spine{i}", lambda P, b0=b0, t0=t0: poly(*back(P), [(-.024, b0 + .010), (0, b0), (.024, b0 + .010), (.024, t0), (-.024, t0)]),
                   .0100, .0050, PLATE, bind="chest" if b0 > zu else "spine")
    base.plate("blade", lambda P: poly(*back(P), [(.034, zt), (.150 * k, zt - .010), (.166 * k, zc + .010), (.140 * k, zc - .055), (.034, zc - .030)]),
               .0070, .0050, PLATE, bind="chest", step=(.014, DARK))
    ub1 = half * .44 - .008
    lz = (zc - .066 - z0) / 2
    for i in range(2):
        b0, t0 = z0 + lz * i + .004, z0 + lz * (i + 1) - .004
        base.plate(f"loin{i}", lambda P, b0=b0, t0=t0: poly(*back(P), [(.034, b0), (ub1, b0 + .012), (ub1, t0 + .012), (.034, t0)]),
                   .0060, .0042, DARK, bind="spine")
    # ---- the belt: a band of dark steel, a plate at the front, pouches at the hips
    base.plate("belt", lambda P: inter(zh + .036 - P[:, 2], P[:, 2] - (zh + .088)), .0130, .0060, TRIM, .0020, bind="hips")
    base.plate("buckle", lambda P: poly(*front(P), [(-.034, zh + .100), (.034, zh + .100), (.046, zh + .062), (.030, zh + .024), (-.030, zh + .024), (-.046, zh + .062)]),
               .0200, .0050, PLATE, .0020, bind="hips")
    import garment
    for ang in (52, 84):
        u = math.radians(ang) * tor.R
        loc, n = base.on(tor.point(u, zh + .062, tor.R * 1.05))
        R_ = garment.frame_at(loc, n)
        pc = boxed(parts, "pouch", (.046, .060, .024), R_, loc + n * (.0190 + .012), SUIT, bevel=.006, bind="hips")
        fl = boxed(parts, "pouchflap", (.050, .022, .027), R_, loc + n * (.0190 + .0125) + Vector((0, 0, .021)), TRIM, bevel=.005, bind="hips")
        for c in mirrored([pc, fl]):
            parts.add(c, "hips")
    # ---- light: many small slits. Along each collar plate, two on the keel, one under each side of the chest
    # plate, one on every flank lame, the buckle, the spine
    base.light("collar_l", [tor.point(.040 * k, zt + .034), tor.point(.110 * k, zt + .047)], .0132 + .0036, .0022, "chest")
    base.light("keel_a", [tor.point(0, zm + .040), tor.point(0, zm + .012)], keel_top, .0026, "chest", mirror=False)
    base.light("keel_b", [tor.point(0, zm - .012), tor.point(0, zb + .018)], keel_top, .0026, "chest", mirror=False)
    base.light("chest_l", [tor.point(.070 * k, zc - .052), tor.point(.128 * k, zc - .040)], chest_top, .0022, "chest")
    base.light("chest_u", [tor.point(.060 * k, zt - .030), tor.point(.105 * k, zt - .034)], chest_top, .0022, "chest")
    for i in range(3):
        zf = fz0 + fstep * (i + .5)
        fu = u0 + (u1 - u0) * (.30 + .12 * i)
        base.light(f"flank_l{i}", [tor.point(fu - .022, zf + rise * .30), tor.point(fu + .022, zf + rise * .46)], .0060 + .0042, .0020,
                   "spine" if i < 2 else "chest")
    base.light("buckle", [tor.point(-.016, zh + .062), tor.point(.016, zh + .062)], .0200 + .0050, .0030, "hips", mirror=False)
    for i in (1, 3):
        zl = sp0 + sst * (i + .55)
        base.light(f"spine_l{i}", [tor.point(half - .010, zl), tor.point(half + .010, zl)], .0100 + .0050, .0024,
                   "chest" if zl > zu else "spine", mirror=False)

    # ---- the upper-arm plate (it lies on the same base)
    Ra = T["upper_arm_r"] + .010
    arm = Cyl(S, E, dorsal, Ra, pos=thumb)
    La = arm.L
    base.plate("rerebrace", lambda P: poly(arm(P)[0], arm(P)[1], [(-Ra * 1.55, .150), (0, .136), (Ra * 1.55, .150), (Ra * 1.55, La - .058), (0, La - .040), (-Ra * 1.55, La - .058)]),
               .0060, .0045, DARK, bind="upperarm", step=(.012, PLATE))
    base.light("arm_slit", [arm.point(0, .185, Ra + .01), arm.point(0, La - .095, Ra + .01)], .0060 + .0045 + .0036, .0022, "upperarm")
    parts += base.parts
    base.free()
    sh.free()
    parts += pauldrons(info, log)
    log(f"void sentinel: cuirass {len(parts)} parts")
    return wardrobe.join(parts, "C_vest__" + SET)


def pauldrons(info, log=print):
    """three lames over each shoulder on their own rounded form (not the body's): the cap, a middle lame and a pointed
    lower one, each tucked under the one above; a line of light across the middle lame"""
    import sdf
    from boots import mesh_from
    from headgear import relax_on
    T, m = info.T, info.m
    S, a_ = info.A["S"], info.A["a"]
    d_, f_ = info.A["dorsal"], info.A["thumb"]
    s = 1.12 if m else .94
    R = np.array((tuple(a_), tuple(d_), tuple(f_)), F32)       # rows: along the arm, up-and-out, forward
    c = A(S + a_ * (.040 * s) + d_ * .022)
    rad = A((.108 * s, .074 * s, .090 * s))

    def form(P):
        return sdf.ellipsoid(P, c, rad, R)
    lo, hi = c - .14 * s, c + .14 * s
    bm = mesh_from(form, lo, hi, .0040, "pauldron", PLATE)
    relax_on(bm, form, 12)
    base = Base(info, bm, field=form, own=True, reach=.0075, keep=.12)

    def loc(P):
        q = (P - c) @ R.T
        return q[:, 0], q[:, 1], q[:, 2]                      # t along the arm, w up-and-out, sd forward

    def lame(P, t0, t1, point=0.0, under=-.030):
        t, w, sd = loc(P)
        return inter(t0 - t, t - (t1 - point * np.abs(sd) / (.09 * s)), under - w)
    base.plate("pauldron_cap", lambda P: lame(P, -.20, -.004 * s, 0.0, -.004 * s), .0120, .0052, PLATE, .0026, bind="pauldron",
               step=(.016, DARK))
    base.plate("pauldron_mid", lambda P: lame(P, -.030 * s, .046 * s, 0.0, -.008 * s), .0062, .0040, DARK, .0020, bind="pauldron")
    base.plate("pauldron_low", lambda P: lame(P, .020 * s, .100 * s, .030 * s, -.012 * s), .0010, .0036, PLATE, .0018, bind="pauldron")
    # the rim of the cap: a raised band along its lower edge
    base.plate("pauldron_rim", lambda P: lame(P, -.026 * s, -.004 * s, 0.0, -.004 * s), .0176, .0030, TRIM, .0014, bind="pauldron")

    def strip(t, half_):
        return [Vector((c + R.T @ A((t, .0, sd))).tolist()) + d_ * .09 for sd in np.linspace(-half_, half_, 5)]
    base.light("pauldron_l0", strip(-.060 * s, .034 * s), .0120 + .0052 + .0036, .0022, "pauldron", mirror=False)
    base.light("pauldron_l1", strip(.014 * s, .046 * s), .0062 + .0040, .0024, "pauldron", mirror=False)
    base.light("pauldron_l2", strip(.064 * s, .026 * s), .0010 + .0036, .0020, "pauldron", mirror=False)
    left = base.parts
    base.free()
    out = Parts(left)
    for c_ in mirrored(left):
        out.add(c_, "pauldron")
    return out


# ------------------------------------------------------------------------------------------------ the legs

def legs(info, log=print):
    import wardrobe
    T, m = info.T, info.m
    Hp = T["hips"]
    zh, zcr = Hp["z"], T["crotch_z"]
    H, K, An = info.L["H"], info.L["K"], info.L["A"]
    boot_top = An.z + (.145 if m else .165)

    def keep(c, r):
        if r == "thigh":
            return True
        if r in ("shin", "foot"):
            return c.z > An.z + .02
        if r in ("pelvis", "midriff"):
            return c.z < zh + .10
        return False
    sh = shell(info, keep, .0042, cuts=[((0, 0, zh + .078), (0, 0, 1)), ((0, 0, An.z + .045), (0, 0, -1))])
    parts = Parts()
    parts.add(suit(sh, "vs_suit_legs"), "soft")
    base = Base(info, sh, ease=.0015, drape=24, clear=.0062)
    Rt = (T["thigh"]["w"] + T["thigh"]["d"]) / 4 + .006
    Rs = (T["calf"]["w"] + T["calf"]["d"]) / 4 + .006
    fwd = (0, -1, 0)
    th = Cyl(H, K, fwd, Rt, pos=(1, 0, 0))                    # u: 0 at the front, positive to the outside
    thb = Cyl(H, K, (0, 1, 0), Rt, pos=(1, 0, 0))             # the back of the thigh
    sn = Cyl(K, An, fwd, Rs, pos=(1, 0, 0))
    snb = Cyl(K, An, (0, 1, 0), Rs, pos=(1, 0, 0))
    Lt, Ls = th.L, sn.L
    kq = Rt / .105                                           # widths scale with the leg

    def uv(f, P):
        u, t, _ = f(P)
        return u, t
    # ---- the hips: a plate hanging at each side from under the belt, one at the front, two behind
    # the tassets: two lames hanging at each hip from under the belt, the lower tucked under the upper
    base.plate("tasset", lambda P: poly(*uv(th, P), [(.030 * kq, -.070), (.180 * kq, -.085), (.198 * kq, .010), (.160 * kq, .064), (.064 * kq, .070), (.022 * kq, .030)]),
               .0105, .0048, PLATE, bind="soft", step=(.014, DARK))
    base.plate("tasset_low", lambda P: poly(*uv(th, P), [(.052 * kq, .046), (.172 * kq, .040), (.150 * kq, .124), (.072 * kq, .134)]),
               .0050, .0042, DARK, bind="thigh")
    wf = .050 * (Hp["w"] / .345)
    base.plate("fauld", lambda P: inter(poly(np.abs(P[:, 0]) * 0 + P[:, 0], P[:, 2], [(-wf, zh + .034), (wf, zh + .034), (wf * .80, zcr + .050), (0, zcr + .004), (-wf * .80, zcr + .050)]),
                                        P[:, 1] - H.y), .0080, .0048, DARK, bind="hips")
    base.plate("seat", lambda P: inter(poly(np.abs(P[:, 0]), P[:, 2], [(.016, zh + .034), (.128 * kq, zh + .034), (.140 * kq, zcr + .070), (.085 * kq, zcr + .030), (.016, zcr + .060)]),
                                       H.y + .02 - P[:, 1]), .0060, .0042, DARK, bind="hips")
    # ---- the thigh: the cuisse in front, a plate outside, one behind
    c0, c1 = .140, Lt - .078
    main = [(-.070 * kq, c0 + .012), (.004, c0), (.082 * kq, c0 + .016), (.090 * kq, c1 - .030), (.010, c1), (-.066 * kq, c1 - .026)]
    notch = [(.046 * kq, c1 + .02), (.110 * kq, c1 - .074), (.110 * kq, c1 + .02)]      # the angled cut-out, low on the outside
    base.plate("cuisse", lambda P: inter(poly(*uv(th, P), main), -poly(*uv(th, P), notch)), .0090, .0052, PLATE, .0024, bind="thigh",
               step=(.013, DARK))
    base.plate("cuisse_out", lambda P: poly(*uv(th, P), [(.100 * kq, c0 + .030), (.192 * kq, c0 + .044), (.186 * kq, c1 - .052), (.104 * kq, c1 - .040)]),
               .0060, .0042, DARK, bind="thigh")
    base.plate("ham", lambda P: poly(*uv(thb, P), [(-.070 * kq, .120), (.070 * kq, .120), (.060 * kq, Lt - .110), (-.060 * kq, Lt - .110)]),
               .0050, .0040, DARK, bind="thigh")
    # ---- the knee: a cop on the shin's own bone, a lame above it on the thigh, one below
    ks = Rs / .0705
    base.plate("knee_up", lambda P: poly(*uv(sn, P), [(-.056 * ks, -.098), (.056 * ks, -.098), (.064 * ks, -.070), (-.064 * ks, -.070)]),
               .0075, .0042, DARK, bind="thigh")
    base.plate("knee", lambda P: poly(*uv(sn, P), [(-.048 * ks, -.052), (.048 * ks, -.052), (.066 * ks, -.002), (.048 * ks, .048), (-.048 * ks, .048), (-.066 * ks, -.002)]),
               .0150, .0056, PLATE, .0028, bind="knee", step=(.013, DARK))
    # ---- the shin: the greave in front, a plate over the calf
    g0, g1 = .078, Ls - (boot_top - An.z) - .012
    base.plate("greave", lambda P: poly(*uv(sn, P), [(-.060 * ks, g0 + .010), (0, g0), (.060 * ks, g0 + .010), (.050 * ks, g1 - .012), (0, g1), (-.050 * ks, g1 - .012)]),
               .0085, .0052, PLATE, .0024, bind="shin")
    base.plate("greave_ridge", lambda P: poly(*uv(sn, P), [(-.010 * ks, g0 + .022), (.010 * ks, g0 + .022), (.007 * ks, g1 - .020), (-.007 * ks, g1 - .020)]),
               .0085 + .0052 + .0002, .0042, DARK, .0020, bind="shin")
    base.plate("calf", lambda P: poly(*uv(snb, P), [(-.058 * ks, .070), (.058 * ks, .070), (.046 * ks, g1 - .020), (-.046 * ks, g1 - .020)]),
               .0055, .0042, DARK, bind="shin")
    # ---- light: two dashes on each knee cop, one down the cuisse, one down each side of the greave, one on the tasset
    ktop = .0150 + .0056 + .0002 + .0034
    for su in (-1, 1):
        base.light(f"knee_l{su}", [sn.point(su * .010 * ks, -.002, Rs + .02), sn.point(su * .034 * ks, -.002, Rs + .02)], ktop, .0024, "knee")
        base.light(f"greave_l{su}", [sn.point(su * .034 * ks, g0 + .050, Rs + .01), sn.point(su * .030 * ks, g1 - .070, Rs + .01)], .0085 + .0052, .0020, "shin")
    base.light("cuisse_l", [th.point(-.030 * kq, c0 + .060, Rt + .01), th.point(-.026 * kq, c1 - .090, Rt + .01)], .0090 + .0052 + .0036, .0022, "thigh")
    base.light("tasset_l", [th.point(.090 * kq, -.030, Rt + .02), th.point(.130 * kq, -.022, Rt + .02)], .0105 + .0048 + .0036, .0022, "soft")
    parts += base.parts
    base.free()
    sh.free()
    log(f"void sentinel: legs {len(parts)} parts")
    return wardrobe.join(parts, "C_legs__" + SET)


# ------------------------------------------------------------------------------------------------ the gauntlets

def hands(info, log=print):
    import wardrobe
    import skeleton
    T, m = info.T, info.m
    Ar = info.A
    E, W, a_, d_, f_ = Ar["E"], Ar["W"], Ar["a"], Ar["dorsal"], Ar["thumb"]
    Hd = info.H
    pl, pw = T["palm"]["l"], T["palm"]["w"]

    def q(c):
        return Vector((abs(c.x), c.y, c.z))

    def keep_arm(c, r):
        t = (q(c) - E).dot(a_)
        return r in ("forearm", "upperarm", "hand") and -.05 < t < (W - E).dot(a_) + .03

    def keep_hand(c, r):
        return r in ("hand", "forearm") and (q(c) - W).dot(a_) > -.03
    arm_sh = shell(info, keep_arm, .0042, cuts=[(E - a_ * .026, -a_, True), (W + a_ * .012, a_, True)])
    hand_sh = shell(info, keep_hand, .0026, cuts=[(W - a_ * .010, -a_, True)])
    parts = Parts()
    parts.add(suit(arm_sh, "vs_suit_arm"), "soft")
    parts.add(suit(hand_sh, "vs_glove", .35), "soft")
    # ---- the forearm
    base = Base(info, arm_sh, ease=.0015, drape=20, clear=.0060)
    Rf = T["forearm_r"] + .008
    L = (W - E).length
    out = Cyl(E, W, d_, Rf, pos=f_)                           # the top of the forearm (the back of the hand's side)
    inn = Cyl(E, W, -d_, Rf, pos=f_)                          # the underside
    elb = Cyl(E, W, d_ * .45 - f_, Rf, pos=d_)                # the elbow's point: behind and a little out

    def uv(f, P):
        u, t, _ = f(P)
        return u, t
    w = Rf * 1.36
    # the elbow cop: over the point of the elbow, which is the forearm's own bone: it lies wholly on the forearm's
    # side of the joint and rides the forearm (a cup across the joint is left standing in the air when the arm bends)
    base.plate("couter", lambda P: poly(*uv(elb, P), [(-.027, .012), (-.017, .004), (.017, .004), (.027, .012), (.024, .034), (.009, .044), (-.009, .044), (-.024, .034)]),
               .0052, .0040, PLATE, .0018, bind="forearm")
    base.plate("vambrace", lambda P: poly(*uv(out, P), [(-w, .066), (0, .050), (w, .066), (w * .80, L - .042), (0, L - .032), (-w * .80, L - .042)]),
               .0085, .0050, PLATE, .0024, bind="forearm", step=(.011, DARK))
    base.plate("vambrace_in", lambda P: poly(*uv(inn, P), [(-Rf * .95, .074), (Rf * .95, .074), (Rf * .72, L - .048), (-Rf * .72, L - .048)]),
               .0050, .0040, DARK, bind="forearm")
    base.plate("cuff", lambda P: inter(L - .028 - out(P)[1], out(P)[1] - (L + .006)), .0072, .0045, TRIM, .0016, bind="forearm")
    for su in (-1, 1):                                        # two slits along the vambrace
        base.light(f"vambrace_l{su}", [out.point(su * Rf * .34, .100, Rf + .01), out.point(su * Rf * .30, L - .078, Rf + .01)],
                   .0085 + .0050 + .0036, .0020, "forearm")
    parts += base.parts
    base.free()
    # ---- the hand: a plate over its back, one over the knuckles, two on every finger
    hb = Base(info, hand_sh, ease=.0006, drape=0, clear=.003, refine=1, reach=.0075, level=2)
    Wn, an, dn, fn = A(W), A(a_), A(d_), A(f_)

    def hand(P):
        Q = np.array(P, F32)
        Q[:, 0] = np.abs(Q[:, 0])
        d = Q - Wn
        return d @ fn, d @ an, d @ dn
    def back(P, pts):
        u, v, wv = hand(P)
        return inter(poly(u, v, pts), .003 - wv)
    hb.plate("handback", lambda P: back(P, [(-pw * .44, .016), (pw * .44, .016), (pw * .50, pl * .72), (-pw * .50, pl * .72)]),
             .0036, .0032, PLATE, .0012, bind="hand")
    hb.plate("knuckles", lambda P: back(P, [(-pw * .53, pl * .79), (pw * .53, pl * .79), (pw * .50, pl * 1.06), (-pw * .50, pl * 1.06)]),
             .0050, .0036, DARK, .0014, bind="hand")
    for name in skeleton.FINGERS:
        F = Hd["fingers"][name]
        J = F["joints"]
        rw = F["width"] / 2 + .0016
        for i in range(2):
            seg = Cyl(J[i], J[i + 1], d_, rw, pos=f_)
            Ls = seg.L

            def region(P, seg=seg, Ls=Ls, rw=rw):
                u, t, rho = seg(P)                             # (narrow and close: the next finger's back is 2 cm away)
                return inter(poly(u, t, [(-rw * .86, Ls * .16), (rw * .86, Ls * .16), (rw * .86, Ls * .88), (-rw * .86, Ls * .88)]), rho - (rw + .0045))
            bone = ("pinky" if name == "little" else name) + f"_0{i + 1}"
            hb.plate(f"{name}{i}", region, .0022, .0022, PLATE if i == 0 else DARK, .0008, bind=bone, level=2)
    hb.light("hand_slit", [Vector(W + a_ * (pl * .30) + d_ * .03), Vector(W + a_ * (pl * .60) + d_ * .03)], .0036 + .0032, .0020, "hand")
    parts += hb.parts
    hb.free()
    arm_sh.free()
    hand_sh.free()
    log(f"void sentinel: gauntlets {len(parts)} parts")
    return wardrobe.join(parts, "C_hands__" + SET)


# ------------------------------------------------------------------------------------------------ the boots

def feet(info, log=print):
    """armoured boots on the Orion boots' own last (boots.py: measured from this foot, straight shaft, her stacked
    heel), plated: the left one built, the right its mirror"""
    import wardrobe
    import boots
    import fabric
    from coat import bisect, keep_largest
    from headgear import relax_on
    m = info.m
    shaft_h = .145 if m else .165
    M = boots.Measure(info, shaft_h)
    sole_top = .017
    last = boots.last_sdf(M, sole_top)
    M.last = last
    lo = (M.cx - .09, M.toe_y - .05, -.01)
    hi = (M.cx + .09, M.heel_y + .06, M.top + .04)
    bm = boots.mesh_from(last, lo, hi, .0030, "boot", SUIT)
    relax_on(bm, last, 8)
    bisect(bm, bm.faces[:], (0, 0, M.top), (0, 0, 1), clear=True)
    bisect(bm, bm.faces[:], (0, 0, sole_top - .002), (0, 0, -1), clear=True)
    keep_largest(bm)
    bm.normal_update()
    left = Parts()
    inner = wardrobe.to_object(bm.copy(), "vs_boot", SUIT)
    boots.decimate(inner, .05)                                # (one side only: the plates and the cuff close it)
    fabric.world_uvs(inner, fabric.TILE["knit"])
    left.add(inner, "soft")
    base = Base(info, bm, field=last, own=True, reach=.0075, keep=.12)
    y0, y1, ya, za, cx, top = M.toe_y, M.heel_y, M.ank.y, M.ank.z, M.cx, M.top
    SS = M.shin_slices()
    sx_, sy_ = SS[0][1], SS[0][2]
    fr = Cyl((sx_, sy_, 0), (sx_, sy_, 1), (0, -1, 0), .052, pos=(1, 0, 0), mirror=False)
    bk = Cyl((sx_, sy_, 0), (sx_, sy_, 1), (0, 1, 0), .052, pos=(1, 0, 0), mirror=False)
    x_, y_, z_ = (lambda P: P[:, 0]), (lambda P: P[:, 1]), (lambda P: P[:, 2])
    # the toe cap: its back edge a shallow chevron
    low = za + .004                                           # (the foot's plates stop under the ankle: the shaft's front
                                                              # lies at the same y and would come along as a blade)
    base.plate("toecap", lambda P: inter(y_(P) - (y0 + .082) + .30 * np.abs(x_(P) - cx), sole_top - .010 - z_(P), z_(P) - low),
               .0036, .0050, PLATE, .0024, bind="foot", step=(.012, DARK))
    base.plate("instep0", lambda P: inter(y0 + .078 - .30 * np.abs(x_(P) - cx) + .008 - y_(P), y_(P) - (y0 + .128) + .30 * np.abs(x_(P) - cx), sole_top - .010 - z_(P), z_(P) - low),
               .0052, .0042, DARK, .0016, bind="foot")
    base.plate("instep1", lambda P: inter(y0 + .124 - .30 * np.abs(x_(P) - cx) + .008 - y_(P), y_(P) - (ya - .022), sole_top - .010 - z_(P), z_(P) - (za + .010)),
               .0068, .0042, PLATE, .0016, bind="foot")
    base.plate("heelcup", lambda P: inter(y1 - .060 - y_(P), z_(P) - (za + .030)), .0045, .0048, PLATE, .0018, bind="foot")
    hexa = [(.030 * math.cos(math.radians(k * 60)), .030 * math.sin(math.radians(k * 60))) for k in range(6)]
    base.plate("ankle_out", lambda P: inter(poly(y_(P) - (ya + .006), z_(P) - (za + .004), hexa), cx + .010 - x_(P)), .0085, .0045, TRIM, .0016, bind="shin")
    base.plate("ankle_in", lambda P: inter(poly(y_(P) - (ya + .006), z_(P) - (za + .004), hexa), x_(P) - (cx - .010)), .0085, .0045, TRIM, .0016, bind="shin")
    base.plate("shaft_front", lambda P: poly(fr(P)[0], z_(P), [(-.050, za + .052), (0, za + .036), (.050, za + .052), (.046, top - .030), (-.046, top - .030)]),
               .0070, .0050, PLATE, .0020, bind="shin")
    base.plate("shaft_back", lambda P: poly(bk(P)[0], z_(P), [(-.046, za + .052), (.046, za + .052), (.042, top - .030), (-.042, top - .030)]),
               .0050, .0042, DARK, bind="shin")
    base.plate("bootcuff", lambda P: top - .024 - z_(P), .0085, .0050, TRIM, .0018, bind="shin")
    base.light("boot_slit", [fr.point(0, za + .075, .07), fr.point(0, top - .050, .07)], .0070 + .0050, .0022, "shin", mirror=False)
    for sx2 in (-1, 1):                                       # a dash on each ankle plate
        base.light(f"ankle_l{sx2}", [Vector((cx + sx2 * .08, ya - .008, za + .004)), Vector((cx + sx2 * .08, ya + .020, za + .004))],
                   .0085 + .0045, .0022, "shin", mirror=False)
    left += base.parts
    base.free()
    heel = 0.0 if m else boots.HEEL_F
    sole_fn = boots.outsole_sdf(M, sole_top, heel=heel)
    sb = boots.mesh_from(sole_fn, (M.cx - .09, M.toe_y - .05, -.012 - heel), (M.cx + .09, M.heel_y + .05, sole_top + .01), .0018, "sole", SOLE)
    so = wardrobe.to_object(sb, "vs_sole", SOLE)
    boots.decimate(so, .05)
    fabric.world_uvs(so, .06)
    left.add(so, "foot")                                      # (the heel block reaches up beside the ankle: weights taken
                                                              # from the skin there leave shards behind when the foot points)
    out = Parts(left)
    for c_ in mirrored(left):
        out.append(c_)
    log(f"void sentinel: boots {len(out)} parts")
    return wardrobe.join(out, "C_feet__" + SET)


# ------------------------------------------------------------------------------------------------ the helm

def helm_form(M, m):
    """the helm's own form: flat planes round this skull (each one touching the cranium fitted to it, or passing
    through this face's nose / chin with room), meeting in hard edges: a keel down the face, cheeks converging on a
    pointed chin, a six-sided crown. His edges are almost sharp, hers eased: a narrower, sleeker helm, the chin
    more pointed. Under it the neck seal."""
    import sdf
    c = np.array(M["c"], F32)
    r = M["r"]
    ez, cz, nz, nr, ny = M["ez"], M["cz"], M["nz"], M["neck_r"], M["neck_y"]
    g = .019 if m else .015
    W, D, H = (float(r[0]) + g) * (1.0 if m else .95), float(r[1]) + g, float(r[2]) + g
    fr = M["front"]
    planes = []

    def nrm(az, el):
        a, e = math.radians(az), math.radians(el)
        return np.array((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)), F32)

    def add(az, el, scale=1.0, through=None):
        for s_ in ((1,) if az in (0, 180) else (1, -1)):
            n = nrm(az * s_, el)
            if through is None:
                d = float(math.sqrt((n[0] * W) ** 2 + (n[1] * D) ** 2 + (n[2] * H) ** 2)) * scale
            else:
                d = float(n @ (np.array((through[0] * s_, through[1], through[2]), F32) - c))
            planes.append((n, d))
    nose_y = min(fr["nose"], fr["mouth"]) - .015
    chin_y = fr["chin"] - .012
    cy = float(c[1])
    add(0, 90, .955)
    add(0, 56)
    add(64, 52)
    add(124, 50)
    add(180, 54)
    add(0, 30, .990)
    add(72, 26, .985)
    add(132, 24, .990)
    add(180, 26)
    prow = 33 if m else 29
    add(prow, 5, through=(0, nose_y, ez - .034))                 # the face: two planes meeting in a keel
    add(90, 0, .985)
    add(144, 0)
    add(180, 0)
    add(prow + 5, -(40 if m else 49), through=(0, chin_y, cz - (.008 if m else .014)))    # the mandible, to a pointed chin
    add(102, -(24 if m else 34), through=(W * (.88 if m else .78), cy, cz + .018))
    add(150, -30, through=(W * .6, cy + D * .78, cz + .004))
    add(180, -34, through=(0, cy + D * .9, cz + .006))
    k = .0030 if m else .0110

    def form(P):
        q = P - c
        d = None
        for n, dd in planes:
            e = q @ n - dd
            d = e if d is None else sdf.smax(d, e, k)
        d = sdf.smax(d, (cz - .036) - P[:, 2], k)
        neck = sdf.round_cone(P, np.array((0, ny, cz - .002), F32), np.array((0, ny + .006, nz - .032), F32), nr + .016, nr + .030)
        return np.minimum(d, neck)
    return form, dict(W=W, D=D, H=H, c=c)


def head(info, log=print):
    """the helm: plates cut from its faceted form. Two slanted slits of light from the temples down to a point at the
    bridge of the nose and a short slit under the point; a brow plate overhanging them; cheek plates and mandibles
    converging on the chin, a keel on it; a crest from the brow over the crown to the nape; crown, temple and back
    plates; three stepped lames at the nape; a vent block at each jaw hinge."""
    import wardrobe
    import headgear
    import fabric
    from boots import mesh_from, decimate
    m = info.m
    M = headgear.head_measures(info)
    form, G = helm_form(M, m)
    c, ez, cz, nz = G["c"], M["ez"], M["cz"], M["nz"]
    W, D, H = G["W"], G["D"], G["H"]
    cy = float(c[1])
    lo = (-W - .05, cy - D - .07, nz - .06)
    hi = (W + .05, cy + D + .05, float(c[2]) + H + .04)
    parts = Parts()
    bm = mesh_from(form, lo, hi, .0032, "helm", SUIT)
    under = wardrobe.to_object(bm.copy(), "vs_helm_base", SUIT)
    decimate(under, .05)
    fabric.world_uvs(under, fabric.TILE["knit"])
    parts.add(under, "head")
    base = Base(info, bm, field=form, own=True, reach=.0075, keep=.10)
    R_ = (W + D) / 2
    rad = math.radians

    def U(P):
        return np.arctan2(np.abs(P[:, 0]), -(P[:, 1] - cy)) * R_

    def Z(P):
        return P[:, 2]

    def X(P):
        return np.abs(P[:, 0])

    def fore(P):
        return P[:, 1] - cy                                       # negative on the front half
    ut = rad(64 if m else 60) * R_
    zv = ez - (.022 if m else .020)                               # the point of the V, at the bridge of the nose
    rise = .046 if m else .058                                    # how far the slits climb to the temples (hers steeper)

    def zl(P):
        return zv + rise * U(P) / ut

    def hh(P):
        return (.0036 if m else .0026) + ((.0085 if m else .0048)) * U(P) / ut

    def slit(P):
        return inter(np.abs(Z(P) - zl(P)) - hh(P), U(P) - ut, fore(P))

    def stem(P):
        return inter(X(P) - (.0026 if m else .0022), Z(P) - (zv - .009), (zv - (.034 if m else .030)) - Z(P), fore(P))
    base.plate("visor", lambda P: np.minimum(slit(P), stem(P)), .0004, .0012, VISOR, .0, bind="head", keep=.5)
    base.plate("brow", lambda P: inter(zl(P) + hh(P) + .0036 - Z(P), Z(P) - (zl(P) + hh(P) + (.024 if m else .015)), U(P) - ut * 1.10, fore(P)),
               .0095 if m else .0058, .0052, PLATE, .0030, bind="head")
    base.plate("cheek", lambda P: inter(Z(P) - (zl(P) - hh(P) - .0036), (ez - (.066 if m else .060)) - Z(P), U(P) - rad(74) * R_, .0066 - X(P), fore(P)),
               .0040, .0042, DARK, .0020, bind="head")
    base.plate("mandible", lambda P: inter((cz - .030) - Z(P), Z(P) - (ez - (.072 if m else .066)), U(P) - rad(104) * R_, .0105 - X(P)),
               .0055, .0050, PLATE, .0028, bind="head", step=(.012, DARK) if m else None)
    base.plate("chin", lambda P: inter(X(P) - (.0086 if m else .0066), (cz - .032) - Z(P), Z(P) - (ez - (.072 if m else .066)), fore(P)),
               .0090, .0046, TRIM, .0024, bind="head")
    base.plate("vent", lambda P: poly(U(P), Z(P), [(rad(86) * R_, cz + .010), (rad(106) * R_, cz + .014), (rad(106) * R_, cz + .040), (rad(86) * R_, cz + .036)]),
               .0112, .0040, TRIM, .0018, bind="head")
    wc = .0088 if m else .0064
    base.plate("crest", lambda P: inter(X(P) - wc, np.where(fore(P) < 0, ez + .036 - Z(P), cz + .060 - Z(P))), .0078, .0060 if m else .0046, PLATE, .0032, bind="head")
    base.plate("crown", lambda P: inter(wc + .0048 - X(P), ez + .032 - Z(P), np.where(U(P) < ut * 1.1, zl(P) + hh(P) + .030 - Z(P), -1.0)),
               .0030, .0046, DARK, .0022, bind="head", step=(.014, PLATE) if m else None)
    base.plate("temple", lambda P: poly(U(P), Z(P), [(ut + .007, ez - .016), (rad(116) * R_, ez - .010), (rad(116) * R_, ez + .026), (ut + .007, ez + .026)]),
               .0060, .0046, PLATE, .0022, bind="head")
    base.plate("back", lambda P: inter(rad(121) * R_ - U(P), cz + .054 - Z(P), Z(P) - (ez + .026)), .0030, .0046, DARK, .0020, bind="head")
    for k_, (z0, z1) in enumerate(((cz + .014, cz + .048), (cz - .018, cz + .018), (cz - .046, cz - .014))):
        base.plate(f"nape{k_}", lambda P, z0=z0, z1=z1: inter(z0 - Z(P), Z(P) - z1, rad(109) * R_ - U(P)), .0040 + .0042 * k_, .0046,
                   PLATE if k_ != 1 else DARK, .0022, bind="head")

    def at(a, z):
        return Vector((math.sin(a) * (R_ + .03), cy - math.cos(a) * (R_ + .03), z))
    top_m = .0055 + .0050 + (.0036 if m else 0.0)
    base.light("cheek_a", [at(rad(40), cz + .030), at(rad(62), cz + .044)], top_m, .0022, "head")
    base.light("cheek_b", [at(rad(46), cz + .010), at(rad(64), cz + .020)], top_m, .0020, "head")
    base.light("vent_l", [at(rad(92), cz + .026), at(rad(102), cz + .028)], .0112 + .0040, .0020, "head")
    parts += base.parts
    base.free()
    log(f"void sentinel: helm {len(parts)} parts")
    return wardrobe.join(parts, "C_head__" + SET)


# ------------------------------------------------------------------------------------------------ the cloak

def outer(info, log=print):
    """the cloak, one layer of cloth (the material shows both sides): a cowl bunched round the neck and lying on the
    shoulders (it goes under the pauldrons), and a cape hung from behind the pauldrons: across the shoulder blades,
    plumb down the back, then flaring so its ragged hem hangs 10-14 cm behind the calves; long uneven tatters, holes
    near the hem, our emblem on the back. Its lower half follows the legs a little (see cape_weights)."""
    import wardrobe
    import fabric
    from mathutils import noise as mnoise
    from headgear import cut_plate
    T, m = info.T, info.m
    C, Wt, Hp = T["chest"], T["waist"], T["hips"]
    zc, zw, zh, znb = C["z"], Wt["z"], Hp["z"], T["neck_base_z"]
    K, S = info.L["K"], info.A["S"]
    ny = .02
    rn_ = T["neck_w"] / 2
    r0 = rn_ + .020
    parts = Parts()
    bpy.data.materials[CLOAK].use_backface_culling = False
    # ---- the cowl and the mantle, one cloth laid on what is under it: close up the neck (lower at the throat),
    # bunched in folds where it turns out, then over the shoulders, the top of the chest and the shoulder blades
    n_th, n_r = 96, 14
    bm = bmesh.new()
    rows = []
    for k_ in range(n_r + 1):
        u = k_ / n_r
        ring = []
        for j in range(n_th):
            th = 2 * math.pi * j / n_th                        # 0 = the front, round by the left
            cf = math.cos(th)
            r_out = .106 + .016 * abs(math.sin(th)) + (.080 if cf < 0 else 0.0) * cf * cf
            z_in = znb + .060 - .034 * max(0.0, cf) ** 2
            # (from just outside the neck's skin: a point inside it finds its nearest skin now here, now there, and
            # the cloth's top edge stood up in teeth)
            rr = rn_ + .006 + (r_out - rn_ - .006) * u ** 1.25
            q = Vector((math.sin(th) * rr, ny - math.cos(th) * rr, z_in - max(0.0, rr - rn_ - .006) * 1.20))
            loc, nrm, _, _ = info.bvh.find_nearest(q)
            nz1 = mnoise.noise(Vector((th * 1.3, u * 2.5, 3.1)))
            gather = (.0060 * math.sin(13 * th + 2.6 * nz1) + .0035 * math.sin(29 * th + 4.0 * nz1)) * math.exp(-((u - .34) / .30) ** 2) * min(1.0, u / .22)      # (none at the top edge: it stood up in teeth)
            roll = .016 * math.exp(-((u - .30) / .15) ** 2) + .007 * math.exp(-((u - .62) / .10) ** 2)
            ring.append(bm.verts.new(loc + nrm * (.030 + roll + gather)))
        rows.append(ring)
    for a_, b_ in zip(rows, rows[1:]):
        for j in range(n_th):
            bm.faces.new((a_[j], b_[j], b_[(j + 1) % n_th], a_[(j + 1) % n_th]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.smooth_vert(bm, verts=[v for v in bm.verts if not v.is_boundary], factor=.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.normal_update()
    if sum((f.calc_center_median() - Vector((0, ny, f.calc_center_median().z))).dot(f.normal) * f.calc_area() for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    mantle = wardrobe.to_object(bm, "vs_mantle", CLOAK)
    fabric.world_uvs(mantle, fabric.TILE["twill"])
    parts.add(mantle, "soft")
    # ---- the cape
    zs_ = np.linspace(znb - .02, .10, 90)
    P = np.array([v.co[:] for f, r in zip(info.bm.faces, info.face_region) if r in ("chest", "midriff", "pelvis", "thigh", "shin")
                  for v in f.verts], F32)
    back = np.array([float(P[np.abs(P[:, 2] - z) < .02][:, 1].max()) if (np.abs(P[:, 2] - z) < .02).any() else ny + .08 for z in zs_])
    line = np.maximum(np.maximum.accumulate(back) - .010, back) + .029      # plumb, clear of the back plates
    for _ in range(6):
        line[1:-1] = (line[:-2] + 2 * line[1:-1] + line[2:]) / 4
    z_mid, z_side = znb - .046, S.z + .022                    # its top edge: under the mantle at the spine, up behind
    z_end = K.z - (.150 if m else .130)                       # each pauldron at the sides
    calf = float(P[(P[:, 2] > z_end - .02) & (P[:, 2] < z_end + .12)][:, 1].max())
    y_hem = calf + .125                                       # the hem hangs clear behind the calves
    y_drop = float(np.interp(z_end, zs_[::-1], line[::-1]))
    nx, nz_ = 60, 88
    rng = np.random.default_rng(7 if m else 11)
    s_ = np.linspace(-1, 1, nx + 1)
    hem = np.zeros(nx + 1)
    for _ in range(22):                                       # long uneven tatters ...
        c0, wd, dp = rng.uniform(-1, 1), rng.uniform(.03, .13), rng.uniform(.05, .30)
        hem = np.maximum(hem, dp * np.clip(1 - np.abs(s_ - c0) / wd, 0, 1) ** .7)
    hem += .030 * np.abs(np.sin(s_ * 37.0 + rng.uniform(0, 6))) + .020 * rng.uniform(0, 1, nx + 1)     # ... and frays
    hem = z_end + hem
    holes = [(rng.uniform(-.8, .8), rng.uniform(.70, .90), rng.uniform(.03, .07), rng.uniform(.018, .040)) for _ in range(6)]
    hw0 = S.x + .040
    bm = bmesh.new()
    grid = []
    for i in range(nz_ + 1):
        t = i / nz_
        row = []
        for j in range(nx + 1):
            sv = float(s_[j])
            z_top = z_mid + (z_side - z_mid) * abs(sv) ** 2.2
            z = z_top + (z_end - z_top) * t
            yb = float(np.interp(z, zs_[::-1], line[::-1]))
            fold = (.004 + .034 * t * t) * math.sin(11.0 * sv + 2.2 * mnoise.noise(Vector((sv * 1.7, t * 1.6, .7)))) \
                * (.6 + .4 * mnoise.noise(Vector((sv * 2.3, 3.0, t))))
            x = sv * (hw0 + .095 * t ** .8)
            y = yb - (.050 + .020 * (1 - t)) * abs(sv) ** 2.4 + fold + max(0.0, y_hem - y_drop) * t ** 1.7
            row.append(bm.verts.new((x, y, max(z, float(hem[j])))))
        grid.append(row)
    for i in range(nz_):
        t = (i + .5) / nz_
        for j in range(nx):
            a_, b_, c_, d_ = grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]
            if a_.co.z - d_.co.z < 1e-5 and b_.co.z - c_.co.z < 1e-5:
                continue                                       # below the hem
            sv = (s_[j] + s_[j + 1]) / 2
            if any(((sv - hs) / hr) ** 2 + ((t - ht) / hr2) ** 2 < 1 for hs, ht, hr, hr2 in holes):
                continue                                       # a hole worn through near the hem
            bm.faces.new((a_, d_, c_, b_))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    if sum(f.normal.y * f.calc_area() for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()
    # the emblem (ours): a tall kite between two swept blades over a short chevron, laid on the cloth (cut from a
    # refined copy of the cloth there, so its outline is crisp)
    ze = zc - .075
    e_ = 1.45 if m else 1.25
    fine = bm.copy()
    bmesh.ops.delete(fine, geom=[f for f in fine.faces if abs(f.calc_center_median().x) > .15 * e_ or abs(f.calc_center_median().z - ze) > .18 * e_], context='FACES')
    bmesh.ops.delete(fine, geom=[v for v in fine.verts if not v.link_faces], context='VERTS')
    bmesh.ops.subdivide_edges(fine, edges=fine.edges[:], cuts=3, use_grid_fill=True, smooth=1.0)
    fine.normal_update()
    tree = BVHTree.FromBMesh(fine)
    Zc = lambda Q: (Q[:, 2] - ze) / e_
    X = lambda Q: Q[:, 0] / e_
    AX = lambda Q: np.abs(Q[:, 0]) / e_
    marks = (("kite", lambda Q: e_ * poly(X(Q), Zc(Q), [(-.005, .118), (.005, .118), (.025, .022), (.005, -.104), (-.005, -.104), (-.025, .022)])),
             ("blade", lambda Q: e_ * poly(AX(Q), Zc(Q), [(.030, .046), (.088, .090), (.072, .030), (.032, -.022)])),
             ("chevron", lambda Q: e_ * poly(AX(Q), Zc(Q), [(.007, -.118), (.042, -.076), (.042, -.097), (.007, -.142)])))
    for name, region in marks:
        o = cut_plate(fine, tree, region, .0014, 0, EMBLEM, "vs_emblem_" + name, 0, 1.0, reach=.008, sheet=True)
        if o is not None:
            from boots import decimate
            decimate(o, .12)
            parts.add(o, "cape")
    fine.free()
    cape = wardrobe.to_object(bm, "vs_cape", CLOAK)
    fabric.world_uvs(cape, fabric.TILE["twill"])
    parts.add(cape, "cape")
    log(f"void sentinel: cloak {len(parts)} parts")
    o = wardrobe.join(parts, "C_outer__" + SET)
    o["vs_cape"] = [float(zc), float(zw), float(zh), float(K.z), float(z_end)]
    return o


# ------------------------------------------------------------------------------------------------ the set

BUILDERS = {"head": head, "vest": vest, "hands": hands, "legs": legs, "feet": feet, "outer": outer}


def build(info, log=print, only=None):
    """every piece of the set on this body (wardrobe.dress skins and finishes them like any other piece)"""
    materials()
    out = []
    for slot in SLOTS:
        if slot in BUILDERS and (only is None or slot in only):
            out.append(BUILDERS[slot](info, log))
    return out


def meta(m):
    """the wardrobe's entries for the set (merged into the armature's `worldex`): every region a piece covers is
    hidden, so no skin shows through in any pose; `set` marks them as earned, never handed out"""
    return {
        "head": {SET: {"label": "Void Sentinel Helm", "hide": ["head", "neck"], "hideHair": True, "set": SET}},
        "vest": {SET: {"label": "Void Sentinel Cuirass", "hide": ["chest", "midriff", "upperarm"], "replaces": ["top"], "set": SET}},
        "hands": {SET: {"label": "Void Sentinel Gauntlets", "hide": ["forearm", "hand"], "set": SET}},
        "legs": {SET: {"label": "Void Sentinel Greaves", "hide": ["pelvis", "thigh", "shin"], "set": SET}},
        "feet": {SET: {"label": "Void Sentinel Boots", "hide": ["foot"], "set": SET}},
        "outer": {SET: {"label": "Void Sentinel Cloak", "hide": [], "set": SET}},
    }


def after_skin(piece, arm=None):
    """armour is rigid: every plate follows one bone (see BIND). Run after the weights came from the body."""
    import finish
    me = piece.data
    at = me.attributes.get("vs_bind")
    if at is None:
        return
    n = len(me.vertices)
    rule = np.zeros(n, np.int32)
    at.data.foreach_get("value", rule)
    isl = finish.islands(me)
    co = np.empty(n * 3, F32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    names = [g.name for g in piece.vertex_groups]
    index = {nm: i for i, nm in enumerate(names)}
    W = np.zeros((n, len(names)), F32)
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    ids, inv = np.unique(isl, return_inverse=True)
    soft = np.nonzero(rule == BIND.index("soft"))[0]
    if len(soft):
        ed = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get("vertices", ed)
        ed = ed.reshape(-1, 2)
        cnt = np.zeros(n, F32)
        np.add.at(cnt, ed[:, 0], 1)
        np.add.at(cnt, ed[:, 1], 1)
        S_ = W.copy()
        for _ in range(4):
            acc = np.zeros_like(S_)
            np.add.at(acc, ed[:, 0], S_[ed[:, 1]])
            np.add.at(acc, ed[:, 1], S_[ed[:, 0]])
            S_ = .5 * S_ + .5 * acc / np.maximum(cnt, 1)[:, None]
        S_[S_ < .02] = 0
        S_ /= np.maximum(S_.sum(1, keepdims=True), 1e-9)
        idx = [int(i) for i in soft]
        for g in piece.vertex_groups:
            g.remove(idx)
        for gi in range(len(names)):
            col = S_[soft, gi]
            for i, w_ in zip(soft[col > 0], col[col > 0]):
                piece.vertex_groups[gi].add([int(i)], float(w_), 'REPLACE')
    new = {}                                                   # vertex -> [(group, weight)]

    def sided(bone, x):
        return bone if bone in CENTRE else bone + (".L" if x >= 0 else ".R")
    for k in range(len(ids)):
        sel = np.nonzero(inv == k)[0]
        r = BIND[int(np.bincount(rule[sel]).argmax())]
        x = float(co[sel, 0].mean())
        if r == "soft":
            continue
        if r == "auto":
            tot = W[sel].sum(0)
            if tot.sum() <= 0:
                continue
            top = int(tot.argmax())
            if tot[top] / tot.sum() < .55:
                continue
            w = [(top, 1.0)]
        elif r in HALF:
            w = [(index[sided(b_, x)], .5) for b_ in HALF[r]]
        elif r == "cape":
            w = None
        else:
            w = [(index[sided(r, x)], 1.0)]
        for i in sel:
            new[int(i)] = w
    if not new:
        return
    verts = list(new)
    for g in piece.vertex_groups:
        g.remove(verts)
    by = {}
    for i, w in new.items():
        if w is None:
            continue
        for gi, wt in w:
            by.setdefault((gi, wt), []).append(i)
    for (gi, wt), vs in by.items():
        piece.vertex_groups[gi].add(vs, wt, 'REPLACE')
    cape = [i for i, w in new.items() if w is None]
    if cape:
        cape_weights(piece, cape, co, index)


def cape_weights(piece, verts, co, index):
    """the cape hangs from the trunk: the chest above the nipple line, the spine down to the waist, the hips below;
    under the hips each half takes a growing share of its own thigh (and under the knee a little of its shin), so a
    leg swinging back pushes the cloth out behind it instead of passing through it"""
    zc, zw, zh, zk, ze = piece.get("vs_cape", (1.3, 1.1, .95, .5, .35))
    G = {n: piece.vertex_groups[index[n]] for n in ("chest", "spine", "hips", "thigh.L", "thigh.R", "shin.L", "shin.R")}

    def sm(x):
        x = max(0.0, min(1.0, x))
        return x * x * (3 - 2 * x)
    for i in verts:
        x, z = float(co[i, 0]), float(co[i, 2])
        w = {}
        if z >= zc:
            w["chest"] = 1.0
        elif z >= zw:
            k = (z - zw) / (zc - zw)
            w["chest"], w["spine"] = k, 1 - k
        elif z >= zh:
            k = (z - zh) / (zw - zh)
            w["spine"], w["hips"] = k, 1 - k
        else:
            # (a modest share: a thigh coming FORWARD takes its half of the cloth with it just the same, and a big
            # share tucks the cape under the seat in a crouch)
            a = .28 * sm((zh - z) / max(zh - zk, 1e-3))          # the legs' share, full at the knee
            wl = sm((x + .06) / .12)
            lo = 0.0
            w["hips"] = 1 - a
            w["thigh.L"], w["thigh.R"] = a * wl * (1 - lo), a * (1 - wl) * (1 - lo)
            w["shin.L"], w["shin.R"] = a * wl * lo, a * (1 - wl) * lo
        for n, v in w.items():
            if v > 1e-4:
                G[n].add([i], v, 'REPLACE')


# ------------------------------------------------------------------------------------------------ on a saved build

def frames(arm, out, clips, n, T, shown):
    """quick looks (workbench): the rest pose from six sides, then n frames of each clip from the front quarter"""
    sc = bpy.context.scene
    os.makedirs(out, exist_ok=True)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = not shown(o)
    cam = bpy.data.objects.new("VsCam", bpy.data.cameras.new("VsCam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    h = T["height"]
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_shadows = False
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_specular_highlight = True
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.world.color = (.20, .20, .22)

    def shoot(name, yaw, pitch=0.0, scale=1.12, centre=.5, res=(560, 900)):
        cam.data.ortho_scale = h * scale
        sc.render.resolution_x, sc.render.resolution_y = res
        y, p = math.radians(yaw), math.radians(pitch)
        d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
        c = Vector((0, 0, h * centre))
        cam.location = c + d * 6
        cam.rotation_euler = (math.radians(90) - p, 0, math.atan2(d.x, -d.y))
        sc.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    sc.frame_set(1)
    for name, yaw in (("rest_front", 0), ("rest_q", 35), ("rest_left", 90), ("rest_back", 180), ("rest_right", 270), ("rest_qb", 215)):
        shoot(name, yaw)
    shoot("rest_chest", 0, 4, .40, .76, (760, 760))
    shoot("rest_bust", 20, 8, .46, .80, (700, 760))
    shoot("rest_bust_back", 200, 8, .46, .80, (700, 760))
    shoot("rest_legs", 25, 5, .58, .27, (700, 900))
    for nm_, yaw_ in (("helm_front", 0), ("helm_q", 35), ("helm_side", 90), ("helm_back", 180)):
        shoot(nm_, yaw_, 3, .24, .915, (760, 760))
    shoot("rest_arm", 60, 25, .34, .62, (760, 760))
    shoot("rest_feet", 40, 12, .26, .07, (760, 620))
    for clip in clips:
        act = bpy.data.actions.get(clip)
        if not act:
            continue
        arm.animation_data.action = act
        f0, f1 = act.frame_range
        for i in range(n):
            sc.frame_set(int(round(f0 + (f1 - f0) * (i + .5) / n)))
            shoot(f"{clip}_{i}", 35 if i % 2 == 0 else 215, 4)
            shoot(f"{clip}_{i}_side", 90, 0)
            shoot(f"{clip}_{i}_back", 180, 0)
            for k_, spec in enumerate(filter(None, os.environ.get("VS_ZOOM", "").split(";"))):   # centre,scale,yaw: a closer look
                zc_, zs_, zy_ = (float(x) for x in spec.split(","))
                shoot(f"{clip}_{i}_zoom{k_}", zy_, 5, zs_, zc_, (900, 900))
    arm.animation_data.action = bpy.data.actions.get("Idle")
    bpy.data.objects.remove(cam)


def main():
    import targets
    import wardrobe
    import finish
    import hair as hair_mod
    argv = sys.argv[sys.argv.index("--") + 1:]
    sex = argv[0]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    T = targets.SEXES[sex]

    def log(*a):
        print("[void_sentinel]", *a)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = bpy.data.objects["B_body"]
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    only = flags["--only"].split(",") if isinstance(flags.get("--only"), str) else None
    for o in list(bpy.data.objects):
        if o.name.endswith("__" + SET) and (only is None or o.name.split("__")[0][2:] in only):
            bpy.data.objects.remove(o)
    info = wardrobe.BodyInfo(body, T)
    pieces = build(info, log, only)
    info.free()
    textures(T, hair_mod.tex_dir(T))
    for p in pieces:
        wardrobe.skin_like_body(p, body, arm)
        if p.name.startswith("C_head__"):
            for g in list(p.vertex_groups):
                p.vertex_groups.remove(g)
            p.vertex_groups.new(name="head").add(list(range(len(p.data.vertices))), 1.0, 'REPLACE')
        after_skin(p, arm)
        finish.apply(p, T, log=log)
        log(f"{p.name}: {tris(p)} triangles, materials {[s.material.name for s in p.material_slots]}")
    total = sum(tris(o) for o in bpy.data.objects if o.name.endswith("__" + SET))
    log(f"the set: {total} triangles")
    data = json.loads(arm.get("worldex", "{}"))
    for slot, items in meta(T["sex"] == "male").items():
        data.setdefault("wardrobe", {}).setdefault(slot, {}).update(items)
    arm["worldex"] = json.dumps(data)
    arm.animation_data.action = bpy.data.actions.get("Idle")
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=flags["--save"])
        log(f"saved {flags['--save']}")
    if isinstance(flags.get("--glb"), str):
        import rig as rig_mod
        rig_mod.write_glb(flags["--glb"])
        log(f"wrote {flags['--glb']}")
    if isinstance(flags.get("--frames"), str):
        clips = flags["--clips"].split(",") if isinstance(flags.get("--clips"), str) else []
        worn = {"vest": "top", "outer": "outer", "hands": "hands", "legs": "legs", "feet": "feet", "head": "hair"}
        have = {o.name.split("__")[0][2:] for o in bpy.data.objects if o.name.endswith("__" + SET)}
        gone = {worn[s] for s in have} | ({"vest", "outer", "top"} if "vest" in have else set()) | {"head"}

        def shown(o):
            if os.environ.get("VS_SOLO"):                      # (a look at one piece alone)
                return o.name == os.environ["VS_SOLO"]
            if o.name.startswith("B_"):
                return len(have) < len(SLOTS)                  # the whole set hides every region of the body
            if o.name.endswith("__" + SET):
                return True
            if o.name.startswith("C_"):
                slot = o.name.split("__")[0][2:]
                return slot not in gone and o.name != "C_hands__orion_armoured"
            return False
        frames(arm, flags["--frames"], clips, int(flags.get("--n", 3)), T, shown)


if __name__ == "__main__":
    main()
