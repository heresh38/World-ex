"""The male's outfit, built fresh to the owner's own sheets (the owner, 2026-11-22: "i want this exact outfit in the
game, 100% the same with the same colours"): art/reference/player/orion_tpose_outfit.png (the T-pose, front, side
and back: what every piece is MEASURED against) and art/reference/image-1794017268247.png (the Project Orion sheet: the
same outfit three quarters, the back, and close on the collar, for what the T-pose leaves unclear). Built on the Orion
male's game build, over the undersuit (always worn), never from the retired hero body's wardrobe.

blender -b <SourceArt/Characters/src/orion_male/game.blend> -P tools/blender/hero/orion/outfit.py -- <out_dir>
        [--pieces=all|coat,...] [--compare] [--save=<x.blend>]

  --compare   per view (front, side, back) the sheet with the dressed body's outline in red, and the dressed body with
              the sheet's outline in green, side by side (out_dir/compare.png), with how much of the sheet's figure the
              body leaves uncovered and how much of the body stands outside it, overall and per band of height

The outfit sheet stands its figure a little apart from where the bodysuit sheet (the body's own) does: it is put back
on the body's frame per view (outfit_sheet.py measured it on the head: 20 px to the left in front, 33 px in the side
view, 70 px in the back view, and 1 % shorter about the soles).
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
HERO = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
for p in (HERE, HERO, os.path.dirname(HERO)):
    if p not in sys.path:
        sys.path.insert(0, p)
import body as B          # noqa: E402  (the Orion body: its sheet's scale and centre columns)
import lab as L           # noqa: E402  (the body's own comparison: cameras, renders, outlines)

OUTFIT = os.path.join(ROOT, "art", "reference", "player", "orion_tpose_outfit.png")
# the outfit sheet's figure against the bodysuit sheet's (box pixels): shifted, and 5 px lower at the crown with
# the soles where they are (outfit_sheet.py, registered on the head)
DX = dict(front=-20.0, side=-33.0, back=-70.0)
MASKS = os.path.join(HERE, "outfit_male_masks.npz")      # (outfit_sheet.py: the figure's mask per view, its box)
CROWN_DROP, CROWN_ROW, SOLE_ROW = 5.0, 13.0, 493.5


def log(*a):
    print("[outfit]", *a, flush=True)


def outfit_row(rz):
    """a bodysuit sheet's box row as the outfit sheet's"""
    return rz + CROWN_DROP * (SOLE_ROW - rz) / (SOLE_ROW - CROWN_ROW)


def sheet_view(view, sheet, mask):
    """the outfit sheet's view on the comparison's metric grid (L.sheet_view's, through the registration)"""
    W, H = L.SIZE
    x0, y0 = L.BOX[view]
    h = (np.arange(W) + .5 - W / 2) * L.MPP
    z = L.Z_MID + (H / 2 - np.arange(H) - .5) * L.MPP
    rz = outfit_row(np.array([B.Concept.row(v) for v in z]))
    c0 = {"front": B.FRONT_C, "side": B.SIDE_C, "back": L.BACK_C}[view] + DX[view]
    cx = c0 + h / B.CPX
    R = np.clip(np.round(rz).astype(int)[:, None] + y0, 0, sheet.shape[0] - 1)
    Cc = np.clip(np.round(cx).astype(int)[None, :] + x0, 0, sheet.shape[1] - 1)
    img = sheet[R, Cc].copy()
    img[(rz < 4)[:, None].repeat(W, 1)] = sheet[6, 6]
    # the figure's mask: outfit_sheet's boxes, so their own offsets
    bx0, by0 = int(MASK_BOX[view][0]), int(MASK_BOX[view][1])
    mr = np.round(rz).astype(int)[:, None] + y0 - by0
    mc = np.round(cx).astype(int)[None, :] + x0 - bx0
    inside = (mr >= 0) & (mr < mask.shape[0]) & (mc >= 0) & (mc < mask.shape[1])
    m = mask[np.clip(mr, 0, mask.shape[0] - 1), np.clip(mc, 0, mask.shape[1] - 1)] & inside
    return img, m


MASK_BOX = {}


def save_png(a, path):
    """an RGB array (top row first, 0..1) written through Blender's own images"""
    H, W = a.shape[:2]
    im = bpy.data.images.new("_save", W, H, alpha=True)
    px = np.ones((H, W, 4), np.float32)
    px[..., :3] = np.clip(a, 0, 1)
    im.pixels.foreach_set(px[::-1].ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def colour_render(view, path):
    """the dressed body in its materials' colours (workbench, studio light), over the sheet's backdrop colour"""
    sc = bpy.context.scene
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.show_specular_highlight = True
    sh.show_shadows = False
    sh.background_type = 'VIEWPORT'
    sh.background_color = (.040, .040, .050)
    L.camera(view)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return L.load_png(path)[..., :3]


def compare(out_dir):
    """the dressed body against the outfit sheet, view by view"""
    sheet = L.load_png(OUTFIT)[..., :3]
    M = np.load(MASKS)
    MASK_BOX.update({v: M[v + "_box"] for v in ("front", "side", "back")})
    sc = bpy.context.scene
    if sc.camera is None:
        cam = bpy.data.objects.new("cmp_cam", bpy.data.cameras.new("cmp_cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = L.SIZE
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    rows = []
    W, H = L.SIZE
    zs = L.Z_MID + (H / 2 - np.arange(H) - .5) * L.MPP
    for view in ("front", "side", "back"):
        img, sm = sheet_view(view, sheet, M[view])
        sil = L.render(view, os.path.join(out_dir, f"_sil_{view}.png"), True)[..., 0] > .5
        clay = L.render(view, os.path.join(out_dir, f"_clay_{view}.png"), False)[..., :3]
        col = colour_render(view, os.path.join(out_dir, f"_col_{view}.png"))
        a = img.copy()
        a[L.edge(sil)] = (1, .15, .1)
        b = clay.copy()
        b[L.edge(sm)] = (.2, 1, .3)
        rows.append(np.concatenate([a, b, col], 1))
        miss = (sm & ~sil).sum() / max(1, sm.sum())
        over = (sil & ~sm).sum() / max(1, sil.sum())
        log(f"{view}: sheet not covered {100 * miss:.1f} %, body outside the sheet {100 * over:.1f} %")
        for z0, z1, name in ((1.45, 1.80, "head and collar"), (1.10, 1.45, "chest and arms"), (.80, 1.10, "waist"),
                             (.45, .80, "thighs"), (.10, .45, "shins"), (-.05, .10, "feet")):
            band = (zs >= z0) & (zs < z1)
            s_, b_ = sm[band], sil[band]
            log(f"    {name:16s} {z0:.2f}..{z1:.2f}: sheet not covered {100 * (s_ & ~b_).sum() / max(1, s_.sum()):5.1f} %, "
                f"outside {100 * (b_ & ~s_).sum() / max(1, b_.sum()):5.1f} %")
    out = np.concatenate(rows, 0)[::2, ::2]
    save_png(out, os.path.join(out_dir, "compare.png"))
    for f in os.listdir(out_dir):
        if f.startswith("_sil_") or f.startswith("_clay_") or f.startswith("_col_"):
            os.remove(os.path.join(out_dir, f))
    log(f"compare -> {os.path.join(out_dir, 'compare.png')}")


def extents():
    """the sheet's figure measured on the body's frame, every centimetre of height: in front its left and right edge
    and the gap between the legs (metres across, the body's left +x), in the side view its front and back (metres,
    -y front); the arms are cut away above the armpits (only the trunk's run that holds the middle)"""
    W, H = L.SIZE
    sheet = L.load_png(OUTFIT)[..., :3]
    M = np.load(MASKS)
    MASK_BOX.update({v: M[v + "_box"] for v in ("front", "side", "back")})
    hs = (np.arange(W) + .5 - W / 2) * L.MPP
    zs = L.Z_MID + (H / 2 - np.arange(H) - .5) * L.MPP
    out = {}
    for view in ("front", "side", "back"):
        _, m = sheet_view(view, sheet, M[view])
        rows = {}
        for r in range(H):
            z = round(float(zs[r]), 3)
            if z < -.02 or z > 1.9:
                continue
            cs = np.nonzero(m[r])[0]
            if not len(cs):
                continue
            runs = np.split(cs, np.nonzero(np.diff(cs) > 1)[0] + 1)
            spans = [(float(hs[c[0]]), float(hs[c[-1]])) for c in runs if len(c) > 2]
            rows[z] = spans
        out[view] = rows
    return out


def arm_extents():
    """the sheet's arm in the front view every 2.5 cm along it, from the shoulder out: its top and bottom height
    (metres), and the same of the body as rendered (the sleeve's thickness over the arm)"""
    W, H = L.SIZE
    sheet = L.load_png(OUTFIT)[..., :3]
    M = np.load(MASKS)
    MASK_BOX.update({v: M[v + "_box"] for v in ("front", "side", "back")})
    _, m = sheet_view("front", sheet, M["front"])
    hs = (np.arange(W) + .5 - W / 2) * L.MPP
    zs = L.Z_MID + (H / 2 - np.arange(H) - .5) * L.MPP
    out = []
    for x in np.arange(.20, .95, .025):
        for sx in (1, -1):
            c = int(np.argmin(np.abs(hs - sx * x)))
            col = m[:, c] & (zs > 1.25)[:, None].ravel()
            r = np.nonzero(col)[0]
            out.append((round(float(sx * x), 3), (round(float(zs[r].max()), 3), round(float(zs[r].min()), 3)) if len(r) else None))
    return out


def front_opening(lo=.40, hi=1.0):
    """where the coat hangs open in front (the sheet's front view): per height, the runs of the colours that are
    neither the coat's black nor its grey facings: the blue lining and the trousers between the panels"""
    W, H = L.SIZE
    sheet = L.load_png(OUTFIT)[..., :3]
    M = np.load(MASKS)
    MASK_BOX.update({v: M[v + "_box"] for v in ("front", "side", "back")})
    img, m = sheet_view("front", sheet, M["front"])
    hs = (np.arange(W) + .5 - W / 2) * L.MPP
    zs = L.Z_MID + (H / 2 - np.arange(H) - .5) * L.MPP
    out = []
    for z in np.arange(lo, hi, .025):
        r = int(np.argmin(np.abs(zs - z)))
        px = img[r]
        blue = (px[:, 2] - px[:, 0] > .07) & m[r]
        light = (px.mean(1) > .38) & m[r]
        bl = hs[blue]
        li = hs[light]
        out.append((round(float(z), 3), [round(float(v), 3) for v in (bl.min(), bl.max())] if len(bl) else None,
                    sorted({round(float(v), 2) for v in li}) if len(li) else None))
    return out


# ---------------------------------------------------------------------------------------------- the body measured

def coords(me, mw):
    co = np.zeros(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co @ np.array(mw)[:3, :3].T + np.array(mw)[:3, 3]


def evaluated_coords(o):
    """an object's vertices as drawn at rest (its armature modifier at the rest pose)"""
    dg = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    co = coords(me, o.matrix_world)
    e.to_mesh_clear()
    return co


def measure(body, arm, suit):
    """what the pieces read of this body, measured on it, its skeleton and its undersuit"""
    T = {}
    bones = arm.data.bones
    M = arm.matrix_world
    head = lambda n: M @ Vector(bones[n].head_local)
    T["shoulder_joint"] = tuple(head("upperarm.L"))
    T["elbow"], T["wrist"] = tuple(head("forearm.L")), tuple(head("hand.L"))
    T["hip_joint"], T["knee"], T["ankle"] = tuple(head("thigh.L")), tuple(head("shin.L")), tuple(head("foot.L"))
    me = body.data
    co = coords(me, body.matrix_world)
    reg = np.zeros(len(me.polygons), np.int32)
    me.attributes["region"].data.foreach_get("value", reg)
    vreg = np.full(len(me.vertices), -1, np.int32)
    for f in me.polygons:
        for vi in f.vertices:
            if vreg[vi] < 0:
                vreg[vi] = reg[f.index]
    heads = co[vreg == 0]
    T["chin_z"] = float(heads[(np.abs(heads[:, 0]) < .015) & (heads[:, 1] < -.04)][:, 2].min())
    neck = co[vreg == 1]
    T["neck_base_z"] = float(neck[neck[:, 1] < 0][:, 2].min())
    # the undersuit's stand collar at the chin's height (lower, the suit runs out over the shoulders)
    sc = evaluated_coords(suit)
    band = sc[(sc[:, 2] > T["chin_z"] - .004) & (sc[:, 2] < T["chin_z"] + .010) & (np.abs(sc[:, 0]) < .11)]
    mid = band[np.abs(band[:, 0]) < .012]
    yc = float((mid[:, 1].max() + mid[:, 1].min()) / 2)
    side = band[np.abs(band[:, 1] - yc) < .015]
    T["collar_y"], T["collar_ry"] = yc, float((mid[:, 1].max() - mid[:, 1].min()) / 2)
    T["collar_rx"] = float(np.abs(side[:, 0]).max())
    # the coat's own: where its skirt begins, its hem behind, its vent's top, where the sleeves end
    T["coat_waist"], T["hem_back"], T["vent_top"], T["cuff_x"] = 1.0, .435, .80, .705
    # the skirt's front edges at the hem (the sheet: at the thighs' outer front), the collar's top at the front ends
    # and how much higher it stands behind the head
    T["skirt_edge_x"], T["skirt_edge_y"] = .215, -.135
    T["collar_top"], T["collar_back"] = 1.600, .060
    # the trousers' waistband (under the belt) and the boots' tops
    T["trouser_top"], T["boot_top"] = 1.07, .245
    # the belt over the coat: its middle's height and the trunk's middle (y) there
    T["belt_z"] = 1.088
    band = sc[np.abs(sc[:, 2] - T["belt_z"]) < .006]
    band = band[np.abs(band[:, 0]) < .25]
    T["belt_yc"] = float((band[:, 1].max() + band[:, 1].min()) / 2)
    log(f"measured: chin {T['chin_z']:.3f}, neck's base {T['neck_base_z']:.3f}, the suit's collar "
        f"{2 * T['collar_rx']:.3f} x {2 * T['collar_ry']:.3f} round y {yc:.3f}")
    return T


def sleeve_ease(suit, T):
    """how far the coat's sleeve stands off the suit along the arm: half of what the sheet's arm is thicker than the
    suit's, every 2.5 cm out from the shoulder (front view), never under 7 mm"""
    sc = evaluated_coords(suit)
    out = []
    for x, ext in arm_extents():
        if x < 0 or ext is None or x > .72:
            continue
        col = sc[(np.abs(sc[:, 0] - x) < .006) & (sc[:, 2] > 1.25)]
        if not len(col):
            continue
        thick_s = ext[0] - ext[1]
        thick_b = col[:, 2].max() - col[:, 2].min()
        out.append((x, float(min(.032, max(.007, (thick_s - thick_b) / 2)))))
    out.sort()
    sm = [(x, sum(e for xx, e in out if abs(xx - x) < .04) / max(1, sum(1 for xx, e in out if abs(xx - x) < .04))) for x, e in out]
    log("sleeve ease: " + ", ".join(f"{x:.2f}:{e * 1000:.0f}mm" for x, e in sm[::3]))
    return sm


def suited_base(body, suit):
    """a copy of the body whose faces carry their region (material index = the region) and whose surface lies on
    the undersuit's outside wherever the suit is: every piece is grown from it, so it is worn OVER the suit"""
    import bmesh
    from mathutils.bvhtree import BVHTree
    sc = bpy.context.scene
    base = body.copy()
    base.data = body.data.copy()
    base.modifiers.clear()
    base.parent = None
    base.matrix_world = body.matrix_world.copy()
    sc.collection.objects.link(base)
    base.name = base.data.name = "outfit_base"
    if base.data.shape_keys:
        base.shape_key_clear()
    me = base.data
    reg = np.zeros(len(me.polygons), np.int32)
    me.attributes["region"].data.foreach_get("value", reg)
    me.materials.clear()
    for r in ("head", "neck", "chest", "midriff", "pelvis", "upperarm", "forearm", "hand", "thigh", "shin", "foot"):
        me.materials.append(bpy.data.materials.get("base__" + r) or bpy.data.materials.new("base__" + r))
    me.polygons.foreach_set("material_index", reg)
    dg = bpy.context.evaluated_depsgraph_get()
    se = suit.evaluated_get(dg)
    sm = se.to_mesh()
    sbm = bmesh.new()
    sbm.from_mesh(sm)
    sbm.transform(suit.matrix_world)
    bvh = BVHTree.FromBMesh(sbm)
    sbm.free()
    se.to_mesh_clear()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    covered = {1, 2, 3, 4, 5, 6, 8, 9}                     # (the regions the suit is over)
    mw, inv = base.matrix_world, base.matrix_world.inverted()
    n_moved = 0
    for v in bm.verts:
        if not any(f.material_index in covered for f in v.link_faces):
            continue
        p = mw @ v.co
        n = (mw.to_3x3() @ v.normal).normalized()
        hit, _, _, _ = bvh.ray_cast(p - n * .002, n, .030)
        if hit is not None and (hit - p).dot(n) > 0:
            v.co = inv @ (hit + n * .0006)
            n_moved += 1
    bm.to_mesh(me)
    bm.free()
    me.update()
    log(f"base: {n_moved} vertices onto the suit")
    return base


def build(names, body, suit, arm, T):
    base = suited_base(body, suit)
    made = []
    E = extents()
    if "coat" in names:
        import outfit_coat
        T["sleeve"] = sleeve_ease(suit, T)
        made += outfit_coat.build(base, T, E, log=log)
    if "legs" in names:
        import outfit_legs
        made += outfit_legs.build(base, T, log=log)
    if "legs" in names:
        import outfit_parts
        legs_obj = next((o for o in made if o.name == "C_legs__orion"), None)
        if legs_obj is not None:
            made += outfit_parts.build(T, legs_obj, log=log)
    if "hands" in names:
        import outfit_hands
        made += outfit_hands.build(base, arm, T, log=log)
    if "torso" in names:
        import outfit_torso
        import outfit_parts
        coat_obj = next((o for o in made if o.name == "C_outer__orion"), None)
        made += outfit_torso.build(base, T, coat_obj, log=log)
        vest_obj = next((o for o in made if o.name == "C_vest__orion"), None)
        made += outfit_parts.build_upper(T, coat_obj, vest_obj, log=log)
    bpy.data.objects.remove(base, do_unlink=True)
    return made

# ---------------------------------------------------------------------------------------------- for the game

# each wardrobe slot's piece and the parts joined into it; parts that are hard (plates, lights, pouches, the screens)
# ride one bone whole
SLOTS = {
    "C_outer__orion": (["C_outer__orion", "belt_band", "belt_pouches", "belt_lights", "coat_shoulders", "coat_lights",
                        "coat_back_plate", "coat_back_straps", "coat_back_lights"],
                       {"belt_pouches", "belt_lights", "coat_shoulders", "coat_lights", "coat_back_plate", "coat_back_lights"}),
    "C_vest__orion": (["C_vest__orion", "vest_harness", "vest_plate", "vest_lights"], {"vest_plate", "vest_lights"}),
    "C_top__orion": (["C_top__orion"], set()),
    "C_legs__orion": (["C_legs__orion", "knee_plates", "shin_plates", "leg_straps", "leg_pouches", "leg_greys"],
                      {"knee_plates", "shin_plates", "leg_pouches"}),
    "C_feet__orion": (["C_feet__orion", "boot_soles", "boot_plates", "boot_straps", "boot_laces", "boot_eyelets"],
                      {"boot_plates", "boot_straps", "boot_laces", "boot_eyelets"}),
    "C_hands__orion": (["C_hands__orion", "hand_bracers", "hand_screens", "hand_lights"], {"hand_screens", "hand_lights"}),
}
WARDROBE = {
    "outer": {"orion": {"label": "Orion Field Coat", "hide": []}},
    "vest": {"orion": {"label": "Orion Plate Vest", "hide": []}},
    "top": {"orion": {"label": "Orion Neck Gaiter", "hide": ["neck"]}},
    "legs": {"orion": {"label": "Orion Cargo Trousers", "hide": []}},
    "feet": {"orion": {"label": "Orion Combat Boots", "hide": ["foot"]}},
    "hands": {"orion": {"label": "Orion Fingerless Gloves", "hide": []}},
}
DEFAULTS = {"outer": "orion", "vest": "orion", "top": "orion", "legs": "orion", "feet": "orion", "hands": "orion"}
# each piece's faces in the game (a player with all it wears is 120 000 triangles: asset_check CLASSES["player"]);
# the vest is mostly under the coat
FACES = {"C_outer__orion": 20000, "C_vest__orion": 3500, "C_top__orion": 3400, "C_legs__orion": 7000,
         "C_feet__orion": 14000, "C_hands__orion": 4000}
# the cloth maps (fabric.py) each material wears: (kind, seed)
CLOTH = {"orion_coat": "twill", "orion_coat_light": "twill", "orion_lining": "ripstop", "orion_cloth": "ripstop",
         "orion_black": "knit", "orion_vest": "polymer", "orion_strap": "canvas", "orion_leather": "leather",
         "orion_glove": "leather", "orion_sole": "rubber", "orion_plate": "polymer", "orion_boot_panel": "polymer",
         "orion_steel": "polymer"}


def apply_modifiers(o):
    bpy.context.view_layer.objects.active = o
    for ob in bpy.context.scene.objects:
        ob.select_set(ob is o)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def textures(out_dir):
    """every outfit material on its cloth maps (fabric.py), in the material's own colour"""
    import fabric
    import outfit_mat as OM
    for name, kind in CLOTH.items():
        if name not in bpy.data.materials:
            continue
        col, rough, metal, _ = OM.PALETTE[name]
        paths = fabric.make(kind, col, rough, out_dir, f"orion_outfit_{name[6:]}", metal,
                            seed=__import__("zlib").crc32(name.encode()) % 9973, linear=True, force=True)
        fabric.texture_material(name, paths)


def skin(o, body, arm, rigid_faces):
    """weights from the body's nearest surface; the hard parts each whole on the bone that holds most of them"""
    import wardrobe
    wardrobe.skin_like_body(o, body, arm)
    if not rigid_faces:
        return
    me = o.data
    # the hard parts' islands (connected through edges), each to its strongest bone
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    seen = set()
    groups = {g.index: g.name for g in o.vertex_groups}
    for f0 in rigid_faces:
        if f0 in seen:
            continue
        stack, island = [bm.faces[f0]], set()
        seen.add(f0)
        while stack:
            f = stack.pop()
            island.update(v.index for v in f.verts)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen and g.index in rigid_faces:
                        seen.add(g.index)
                        stack.append(g)
        tot = {}
        for vi in island:
            for g in me.vertices[vi].groups:
                tot[g.group] = tot.get(g.group, 0.0) + g.weight
        if not tot:
            continue
        best = max(tot, key=tot.get)
        for vi in island:
            for g in list(me.vertices[vi].groups):
                o.vertex_groups[g.group].remove([vi])
            o.vertex_groups[best].add([vi], 1.0, 'REPLACE')
    bm.free()


# ---------------------------------------------------------------------------------------------- the paint

# the coat's and the trousers' grey: the material wears the lighter grey, the vertex paint (which the game multiplies
# in, VertexColorAmount) darkens it to the black everywhere but the worn patches (the sheet: on the sleeves, the
# shoulders, the upper back, the thighs and the shins) and the skirt's lighter centre panel behind
PAINT_BASE = {"orion_coat": ((.200, .198, .210), (.050, .050, .058)), "orion_cloth": ((.120, .120, .130), (.025, .025, .029))}
BACK_PANEL = (.095, .074, .085)                           # (the sheet's warm mid grey down the skirt's back)


def camo(p, scale, prob, seed):
    """an angular patch pattern: Voronoi cells (their borders a little warped), a cell a patch by its own chance"""
    from mathutils import noise
    q = p * scale + noise.noise_vector(p * scale * .7 + Vector((seed, 1.3, 2.9))) * .35
    d, pts = noise.voronoi(q, distance_metric='DISTANCE')
    c = pts[0]
    h = (math.sin(c.x * 12.9898 + c.y * 78.233 + c.z * 37.719 + seed) * 43758.5453) % 1.0
    edge = min(1.0, max(0.0, (d[1] - d[0]) / .06))
    return (1.0 if h < prob else 0.0) * edge ** .2


# hard parts (kept whole, never collapsed) that still bend with the body's own weights: the shoulders' lames span the
# collar and the arm, and held rigid on one bone they stood up like horns when the arm came down from the T-pose
FOLLOW = {"coat_shoulders"}
# the parts whose convex edges are rubbed through (plates); straps, bands, cloth and lights keep their paint whole
WEAR_OBJECTS = {"knee_plates", "shin_plates", "boot_plates", "coat_shoulders", "coat_back_plate", "vest_plate"}


def edge_wear(o, lo=35.0, hi=95.0, most=.7):
    """per vertex, how hard a convex edge there turns (0 none, 1 a corner): where a plate's paint is rubbed through to
    the metal (a crease that folds in, and the smooth turn of a cloth, take nothing)"""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    w = [0.0] * len(bm.verts)
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        ang = math.degrees(f1.normal.angle(f2.normal, 0.0))
        if ang < lo or (f2.calc_center_median() - f1.calc_center_median()).dot(f1.normal) > 0:
            continue
        k = most * min(1.0, (ang - lo) / (hi - lo))
        for v in e.verts:
            w[v.index] = max(w[v.index], k)
    bm.free()
    return w


def paint_coat(o, T):
    import bmesh
    me = o.data
    col = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
    base, dark = PAINT_BASE["orion_coat"]
    own = {i for i, m in enumerate(me.materials) if m and m.name.split(".")[0] == "orion_coat"}
    S = Vector(T["shoulder_joint"])
    zw = T["coat_waist"]
    for poly in me.polygons:
        if poly.material_index not in own:
            for li in poly.loop_indices:
                col.data[li].color = (1.0, 1.0, 1.0, 1.0)
            continue
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co
            arm = abs(p.x) > S.x + .02 and p.z > S.z - .20
            back = p.y > .02
            if p.z < zw - .02 and back and abs(p.x) < .12 + .05 * (zw - p.z):
                c = BACK_PANEL                             # the skirt's centre panel behind
                k = 1.0
            else:
                prob = .30 if arm else (.30 if p.z > S.z - .05 else (.22 if back and p.z > zw else .08))
                k = camo(p, 15.0, prob, 3.0)
                c = None
            if c is None:
                rgb = [d / b + (1 - d / b) * k for d, b in zip(dark, base)]
            else:
                rgb = [cc / b for cc, b in zip(c, base)]
            col.data[li].color = (min(1, rgb[0]), min(1, rgb[1]), min(1, rgb[2]), 1.0)


def paint_legs(o, T):
    me = o.data
    col = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
    base, dark = PAINT_BASE["orion_cloth"]
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            p = me.vertices[vi].co
            prob = .09 if p.y < .0 else .05
            k = camo(p, 16.0, prob, 7.0)
            rgb = [d / b + (1 - d / b) * k for d, b in zip(dark, base)]
            col.data[li].color = (rgb[0], rgb[1], rgb[2], 1.0)


def paint_white(o):
    """no paint over the material's own colour; a plate's rubbed edges in the alpha"""
    me = o.data
    col = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
    wear = edge_wear(o) if o.name in WEAR_OBJECTS else [0.0] * len(me.vertices)
    for li, lp in enumerate(me.loops):
        col.data[li].color = (1.0, 1.0, 1.0, 1.0 - wear[lp.vertex_index])


T_PAINT = {}


def finish(body, arm, out_dir, T=None):
    """the built parts as the game's wardrobe pieces: joined per slot, their thickness applied, UVs and cloth maps,
    the paint, skinned to the body (hard parts rigid), parented to the armature, the wardrobe written on it"""
    import fabric
    import outfit_mat as OM
    T_PAINT.update(T or {})
    for name, (base, dark) in PAINT_BASE.items():           # (the painted materials wear the lighter grey)
        c, r, m, e = OM.PALETTE[name]
        OM.PALETTE[name] = (base, r, m, e)
    textures(os.path.join(out_dir, "tex"))
    for piece, (parts, hard) in SLOTS.items():
        objs = [bpy.data.objects[n] for n in parts if n in bpy.data.objects]
        if not objs:
            continue
        for o in objs:
            apply_modifiers(o)
        # the soft shells down to the piece's budget (less what its hard parts take): a collapse keeps the silhouette
        n_hard = sum(len(o.data.polygons) for o in objs if o.name in hard)
        n_soft = sum(len(o.data.polygons) for o in objs if o.name not in hard)
        n_soft = sum(2 * len(o.data.polygons) for o in objs if o.name not in hard)        # (quads: two triangles each)
        ratio = (FACES[piece] - n_hard) / max(1, n_soft)
        if ratio < .95:
            for o in objs:
                if o.name in hard:
                    continue
                d = o.modifiers.new("lod", 'DECIMATE')
                d.ratio = max(.05, ratio)
                d.use_collapse_triangulate = True
                apply_modifiers(o)
        for o in objs:
            tile = fabric.TILE.get(CLOTH.get(o.data.materials[0].name if o.data.materials else "", ""), .06)
            fabric.world_uvs(o, tile)
            o["hard"] = o.name in hard and o.name not in FOLLOW
            # the paint (every part of a piece carries it, or the join leaves the others black)
            if o.name == "C_outer__orion":
                paint_coat(o, T_PAINT)
            elif o.name == "C_legs__orion":
                paint_legs(o, T_PAINT)
            else:
                paint_white(o)
            for name in [c.name for c in o.data.color_attributes if c.name != "Col"]:
                o.data.color_attributes.remove(o.data.color_attributes[name])
        # join, remembering which faces came from the hard parts
        main = objs[0]
        hard_faces = set()
        offset = 0
        for o in objs:
            n = len(o.data.polygons)
            if o.get("hard"):
                hard_faces.update(range(offset, offset + n))
            offset += n
        for ob in bpy.context.scene.objects:
            ob.select_set(ob in objs)
        bpy.context.view_layer.objects.active = main
        if len(objs) > 1:
            bpy.ops.object.join()
        main.name = main.data.name = piece
        skin(main, body, arm, hard_faces)
        log(f"{piece}: {len(main.data.polygons)} faces, {len(hard_faces)} of them hard")
    meta = json.loads(arm.get("worldex", "{}"))
    meta.update({"wardrobe": WARDROBE, "defaults": DEFAULTS})
    arm["worldex"] = json.dumps(meta)


def rest(arm):
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0])
    os.makedirs(out, exist_ok=True)
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    rest(arm)
    for o in bpy.data.objects:                              # (the lab's views show what is worn, nothing else)
        if o.type == 'MESH' and o.name.startswith("C_") and o.name != "C_suit__orion":
            o.hide_render = True
    body = bpy.data.objects["orion_male"]
    suit = bpy.data.objects["C_suit__orion"]
    want = flags.get("--pieces", "")
    names = ["coat", "legs", "torso", "hands"] if want in (True, "all") else [p for p in str(want).split(",") if p]
    if names:
        T = measure(body, arm, suit)
        for o in build(names, body, suit, arm, T):
            o.hide_render = False
    if "--compare" in flags:
        compare(out)
    if "--arms" in flags:
        for x, ext in arm_extents():
            log(f"arm at x {x:+.3f}: sheet top/bottom {ext}")
    if "--opening" in flags:
        for z, blue, light in front_opening():
            log(f"z {z:.3f}: blue lining x {blue}; light grey at x {light}")
    if "--extents" in flags:
        with open(os.path.join(out, "extents.json"), "w") as f:
            json.dump(extents(), f)
        log(f"extents -> {os.path.join(out, 'extents.json')}")
    if "--finish" in flags:
        finish(bpy.data.objects["orion_male"], arm, out, T if names else measure(bpy.data.objects["orion_male"], arm, bpy.data.objects["C_suit__orion"]))
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(flags["--save"]))
        log(f"saved {flags['--save']}")


if __name__ == "__main__":
    main()
