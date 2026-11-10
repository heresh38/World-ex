"""Steps 4-7 of basemesh.py: UVs, textures, the project's collections and LODs, the FBX export and the renders."""
import os, math, json, heapq
import bpy, bmesh
import numpy as np
from mathutils import Vector
import skeleton, shape as shape_mod, skinmaps, rig as rig_mod
from headshape import Y0

F32 = np.float32
AXIAL = ("head", "neck", "chest", "midriff", "pelvis")


def only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.hide_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


# ------------------------------------------------------------------------------------------------------ 4 UVs
def seams_and_unwrap(o, T, log):
    me = o.data
    regs = [s.material.name.replace("skin__", "") for s in o.material_slots]
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    bm.normal_update()
    reg = lambda f: regs[f.material_index]
    for e in bm.edges:
        e.seam = False
    # 1. the regions' borders
    for e in bm.edges:
        if len(e.link_faces) == 2 and reg(e.link_faces[0]) != reg(e.link_faces[1]):
            e.seam = True
    ez = T["eye_z"]
    A = skeleton.arm(T)
    dor = Vector(A["dorsal"])
    # 2. the trunk and head: the back's midline (the face and the front of the body stay whole); over the crown to
    # the hairline
    for e in bm.edges:
        a, b = e.verts
        if abs(a.co.x) < 1e-5 and abs(b.co.x) < 1e-5 and len(e.link_faces) == 2:
            r = reg(e.link_faces[0])
            if r not in AXIAL:
                continue
            c = (a.co + b.co) / 2
            n = (e.link_faces[0].normal + e.link_faces[1].normal)
            if r == "head":
                if c.y > Y0 - .01 or c.z > ez + .068:
                    e.seam = True
            elif n.y > 0.0:
                e.seam = True
    # the face its own island (so it can have the texels): the cut runs under the hair over the forehead's top and
    # down behind each ear to the neck
    hsz = T["head_h"] / .23
    is_face = lambda f: (lambda c: c.y < Y0 + .050 * hsz and c.z < ez + .068 * hsz)(f.calc_center_median())
    for e in bm.edges:
        if len(e.link_faces) == 2 and reg(e.link_faces[0]) == "head" and reg(e.link_faces[1]) == "head":
            if is_face(e.link_faces[0]) != is_face(e.link_faces[1]):
                e.seam = True
    # 3. hands: one island for the back, one for the palm; feet: the sole apart
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f0, f1 = e.link_faces
        r = reg(f0)
        if r == "hand" and reg(f1) == "hand":
            sx = 1 if (f0.calc_center_median().x > 0) else -1
            d = Vector((dor.x * sx, dor.y, dor.z))
            if (f0.normal.dot(d) > 0) != (f1.normal.dot(d) > 0):
                e.seam = True
        elif r == "foot" and reg(f1) == "foot":
            if (f0.normal.z < -.55) != (f1.normal.z < -.55):
                e.seam = True
    # 4. limbs (and the foot's upper): a cut along the hidden side, the shortest way between the piece's two ends
    def components(region):
        faces = [f for f in bm.faces if reg(f) == region]
        seen = set(); comps = []
        for f in faces:
            if f in seen:
                continue
            comp = []; stack = [f]; seen.add(f)
            while stack:
                g = stack.pop(); comp.append(g)
                for e in g.edges:
                    if e.seam:
                        continue
                    for h in e.link_faces:
                        if h not in seen and reg(h) == region:
                            seen.add(h); stack.append(h)
            comps.append(comp)
        return comps

    def cut(comp, hidden):
        verts = {v for f in comp for v in f.verts}
        edges = {e for f in comp for e in f.edges}
        border = [e for e in edges if e.seam or e.is_boundary]
        bv = {v for e in border for v in e.verts}
        # the border's loops
        loops = []; seen = set()
        adj = {}
        for e in border:
            a, b = e.verts
            adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
        for v in bv:
            if v in seen:
                continue
            L = []; stack = [v]; seen.add(v)
            while stack:
                u = stack.pop(); L.append(u)
                for w_ in adj[u]:
                    if w_ not in seen:
                        seen.add(w_); stack.append(w_)
            loops.append(L)
        if len(loops) < 2:
            return 0
        loops.sort(key=len, reverse=True)
        src, dst = loops[0], set(loops[1])
        dist = {v: 0.0 for v in src}; prev = {}
        pq = [(0.0, i, v) for i, v in enumerate(src)]
        heapq.heapify(pq); cnt = len(pq)
        end = None
        while pq:
            d, _, u = heapq.heappop(pq)
            if d > dist.get(u, 1e9):
                continue
            if u in dst:
                end = u; break
            for e in u.link_edges:
                if e not in edges:
                    continue
                w_ = e.other_vert(u)
                hid = max(0.0, ((u.normal + w_.normal) * .5).dot(hidden))
                nd = d + e.calc_length() * (1 + 4 * (1 - hid))
                if nd < dist.get(w_, 1e9):
                    dist[w_] = nd; prev[w_] = (u, e); cnt += 1
                    heapq.heappush(pq, (nd, cnt, w_))
        n = 0
        while end in prev:
            end, e = prev[end]
            e.seam = True; n += 1
        return n

    for region in ("upperarm", "forearm", "thigh", "shin", "foot"):
        for comp in components(region):
            c = sum((f.calc_center_median() for f in comp), Vector()) / len(comp)
            sx = 1 if c.x > 0 else -1
            if region in ("upperarm", "forearm"):
                hidden = Vector((-sx * .55, .25, -.8)).normalized()
            elif region == "foot":
                if sum(f.normal.z for f in comp) / len(comp) < -.5:
                    continue                                              # (the sole: a disc already)
                hidden = Vector((0, 1, 0))
            else:
                hidden = Vector((-sx, .3, 0)).normalized()
            cut(comp, hidden)
    bm.to_mesh(me); bm.free()
    # unwrap, even texel density, then the head and hands larger, pack
    only(o)
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=.002)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')
    # islands (faces joined across non-seam edges); scale by region about each island's centre
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    seen = set(); islands = []
    for f in bm.faces:
        if f in seen:
            continue
        comp = []; stack = [f]; seen.add(f)
        while stack:
            g = stack.pop(); comp.append(g)
            for e in g.edges:
                if e.seam:
                    continue
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h); stack.append(h)
        islands.append(comp)
    scale = {"head": 1.25, "hand": 1.35, "neck": 1.2, "foot": 1.1}
    for comp in islands:
        k = scale.get(regs[comp[0].material_index], 1.0)
        if regs[comp[0].material_index] == "head":
            cz = sum((f.calc_center_median() for f in comp), Vector()) / len(comp)
            if cz.y < Y0 - .02:                                          # the face
                k = 2.9
        if k == 1.0:
            continue
        pts = [l[uv].uv for f in comp for l in f.loops]
        c = sum(pts, Vector((0, 0))) / len(pts)
        for f in comp:
            for l in f.loops:
                l[uv].uv = c + (l[uv].uv - c) * k
    bm.to_mesh(me); bm.free()
    only(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=.0035, shape_method='AABB')
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=True, margin=.0035)
    bpy.ops.object.mode_set(mode='OBJECT')
    # how much of the square is used, and the stretch
    uvs = np.zeros(len(me.loops) * 2, F32); me.uv_layers.active.data.foreach_get("uv", uvs); uvs = uvs.reshape(-1, 2)
    area = 0.0
    for p in me.polygons:
        q = uvs[p.loop_start:p.loop_start + p.loop_total]
        x, y = q[:, 0], q[:, 1]
        area += abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2
    log(f"uv: {len(islands)} islands, {area * 100:.0f}% of the square used, range {uvs.min():.3f}..{uvs.max():.3f}")
    return len(islands), area


def eye_uvs(eo, T):
    """front projection per eyeball; the cornea's bulge"""
    body = shape_mod.Body(T)
    g = body.head_geometry()
    ec, er = g["eye_c"], g["eye_r"]
    me = eo.data
    uvl = me.uv_layers.active or me.uv_layers.new(name="UVMap")
    for v in me.vertices:
        sx = 1 if v.co.x > 0 else -1
        c = Vector((ec.x * sx, ec.y, ec.z))
        d = v.co - c
        if d.length < 1e-9:
            continue
        ang = math.acos(max(-1, min(1, -d.y / d.length)))          # from the forward pole
        lim = math.asin(.485)                                       # the iris's rim (the texture's .485)
        bulge = .0009 * max(0.0, math.cos(min(1.0, ang / (lim * 1.12)) * math.pi / 2)) ** 1.5
        v.co = c + d.normalized() * (er + bulge)
    for p in me.polygons:
        for li in p.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            sx = 1 if v.x > 0 else -1
            uvl.data[li].uv = (.5 + (v.x - ec.x * sx) / (2 * er), .5 + (v.z - ec.z) / (2 * er))
    me.update()


# ------------------------------------------------------------------------------------------------------ 5 textures
def new_image(name, size, floatbuf=True):
    img = bpy.data.images.new(name, size, size, alpha=True, float_buffer=floatbuf)
    img.colorspace_settings.name = 'Non-Color'
    return img


def bake(o, size, log, ao_samples=24):
    """position, normal (world, smooth) and occlusion per texel"""
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    saved = [s.material for s in o.material_slots]
    hidden = []
    for ob in sc.objects:
        if ob is not o and ob.type == 'MESH' and not ob.hide_render:
            ob.hide_render = True; hidden.append(ob)
    arm = o.parent
    arm.data.pose_position = 'REST'
    out = {}
    for kind in ("P", "N", "AO"):
        img = new_image("bake_" + kind, size)
        mat = bpy.data.materials.new("bake_" + kind); mat.use_nodes = True
        nt = mat.node_tree; nt.nodes.clear()
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
        outn = nt.nodes.new('ShaderNodeOutputMaterial')
        if kind == "AO":
            bs = nt.nodes.new('ShaderNodeBsdfDiffuse'); nt.links.new(bs.outputs[0], outn.inputs[0])
        else:
            geo = nt.nodes.new('ShaderNodeNewGeometry'); add = nt.nodes.new('ShaderNodeVectorMath')
            em = nt.nodes.new('ShaderNodeEmission')
            if kind == "P":
                add.operation = 'ADD'; add.inputs[1].default_value = (2, 2, 1)
                nt.links.new(geo.outputs['Position'], add.inputs[0])
            else:
                add.operation = 'MULTIPLY_ADD'; add.inputs[1].default_value = (.5, .5, .5); add.inputs[2].default_value = (.5, .5, .5)
                nt.links.new(geo.outputs['Normal'], add.inputs[0])
            nt.links.new(add.outputs[0], em.inputs['Color']); nt.links.new(em.outputs[0], outn.inputs[0])
        nt.nodes.active = tex
        for s in o.material_slots:
            s.material = mat
        only(o)
        sc.cycles.samples = ao_samples if kind == "AO" else 1
        sc.render.bake.margin = 0
        sc.render.bake.use_clear = True
        bpy.ops.object.bake(type='AO' if kind == "AO" else 'EMIT')
        px = np.empty(size * size * 4, F32); img.pixels.foreach_get(px)
        out[kind] = px.reshape(size, size, 4)
        bpy.data.images.remove(img); bpy.data.materials.remove(mat)
        log(f"baked {kind}")
    for s, m in zip(o.material_slots, saved):
        s.material = m
    for ob in hidden:
        ob.hide_render = False
    mask = out["P"][..., 0] > .5                                    # (x + 2: every baked texel is above 1)
    Pm = out["P"][..., :3] - np.array((2, 2, 1), F32)
    Nm = out["N"][..., :3] * 2 - 1
    AO = out["AO"][..., 0]
    return Pm, Nm, AO, mask


def landmarks(T):
    body = shape_mod.Body(T)
    g = body.head_geometry()
    hs, X = g["hs"], g["X"]
    m = T["sex"] == "male"
    Hd = body.hand; A = Hd["arm"]; L = body.leg
    a, dor = Vector(A["a"]), Vector(A["dorsal"])
    C = T["chest"]
    joint_lines = []
    for f, ch in list(Hd["fingers"].items()) + [("thumb", Hd["thumb"])]:
        J = [Vector(j) for j in ch["joints"]]
        w = ch["width"] / 2
        for i in (1, 2):
            dirn = (J[i + 1] - J[i - 1]).normalized()
            joint_lines.append((tuple(J[i] - dirn * w * .55), tuple(J[i] + dirn * w * .55), w * 1.25))
    lip_full = (1.25 if m else 1.5)
    fine = shape_mod.Body(T)
    fine.fine = True                                                 # (the ear with all its folds: headshape.ear_anatomy)

    def ear_detail(P):
        """how far the detailed ear's surface stands over (+) / under (-) the fitted one, at points on the fitted one"""
        h = body.part("head", P) - fine.part("head", P)
        return np.clip(h, -.0032, .0026).astype(F32)
    return dict(
        detail_fn=ear_detail,
        hs=hs, y0=Y0, chin_z=g["chin"], neck_z=g["chin"] - .012, eye=tuple(g["eye_c"]), eye_r=g["eye_r"],
        stomion=tuple(g["stomion"]), mouth_w=g["mouth_w"],
        lip_up=.0058 * (1.3 if m else 1.0) * hs * (1.0 if m else 1.18), lip_lo=.0064 * lip_full * hs * .95,
        cheek=tuple(X(.046, -.074, .088)), nose_tip=tuple(g["pronasale"] + Vector((0, .004, 0))),
        alar=tuple(g["subnasale"] + Vector((.014, .008, .006))), ear=tuple(g["tragion"] + Vector((.010, .014, .004))),
        chin=tuple(g["pogonion"]), forehead=tuple(X(0, -.092, .165)),
        knuckles=[tuple(Vector(ch["joints"][0]) - a * .015 + dor * T["palm"]["t"] * .4) for ch in Hd["fingers"].values()]
                 + [tuple(Vector(ch["joints"][1]) + dor * ch["width"] * .4) for ch in Hd["fingers"].values()],
        fingertips=[tuple(ch["joints"][3]) for ch in Hd["fingers"].values()] + [tuple(Hd["thumb"]["joints"][3])],
        elbow=tuple(Vector(A["E"]) + dor * .02), knee=tuple(L["K"] + Vector((0, -.03, 0))),
        heel=tuple(L["A"] + Vector((0, .04, -.05))),
        palm=tuple(Vector(A["W"]) + a * T["palm"]["l"] * .5 - dor * T["palm"]["t"] * .5), palm_n=tuple(-dor), dorsal=tuple(dor),
        wrist=tuple(A["W"]), midtip=tuple(Hd["fingers"]["middle"]["joints"][3]),
        nipple=((.105 * T["biacromial"] / .41, -C["d"] * .50, C["z"] - .012) if m else (.080, -body.rib_d * .48 - .036, C["z"] - .008)),
        areola_r=.012 if m else .019, nipple_r=.0035 if m else .0050, nipple_h=.0016 if m else .0030,
        joint_lines=joint_lines,
    )


def save_png(arr, path, srgb):
    """arr (h, w) or (h, w, 3) in 0..1, rows bottom-up (Blender's order)"""
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, 2)
    rgba = np.concatenate([arr.astype(F32), np.ones((h, w, 1), F32)], 2)
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    if srgb:                                         # the buffer of an 8-bit sRGB image holds display values
        c = rgba[..., :3]
        rgba[..., :3] = np.where(c <= .0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 1e-9), 1 / 2.4) - .055)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path; img.file_format = 'PNG'
    img.save()
    return img


def textures(o, eo, T, sex, out, size, log, tex=None, stem=None, eye_stem=None):
    """stem / eye_stem: the files' names without the map's suffix (the game's own: hero_<sex>_skin, hero_<sex>_eye)"""
    tex = tex or os.path.join(out, "textures"); os.makedirs(tex, exist_ok=True)
    Pm, Nm, AO, mask = bake(o, size, log)
    L = landmarks(T)
    # the nipple's landmark onto the surface: the texel nearest to it in front of the chest
    S = skinmaps.skin(Pm, Nm, AO, mask, L, sex == "male", log)
    pad = max(8, size // 256)
    col = skinmaps.pad(S["col"], mask, pad)
    nrm = skinmaps.pad(S["normal"], mask, pad); nrm[~(mask | (np.abs(nrm).sum(2) > 0))] = (0, 0, 1)
    orm = np.stack([skinmaps.pad(AO, mask, pad), skinmaps.pad(S["rough"], mask, pad), np.zeros_like(AO)], 2)
    sss = skinmaps.pad(S["sss"], mask, pad)
    name = stem or f"T_Orion{sex.capitalize()}_Skin"
    imgs = dict(
        col=save_png(col, os.path.join(tex, name + "_BaseColor.png"), True),
        nrm=save_png(nrm * .5 + .5, os.path.join(tex, name + "_Normal.png"), False),
        orm=save_png(orm, os.path.join(tex, name + "_ORM.png"), False),
        sss=save_png(sss, os.path.join(tex, name + "_Subsurface.png"), False))
    iris = (.150, .085, .040) if sex == "male" else (.105, .150, .100)
    imgs["eye"] = save_png(skinmaps.eye_texture(1024, iris, 1 if sex == "male" else 2),
                           os.path.join(tex, (eye_stem or f"T_Orion{sex.capitalize()}_Eye") + "_BaseColor.png"), True)
    log(f"textures written: {tex}")
    return imgs


def hair_materials(sex):
    """the strand cards in Blender's own renders: the atlas is the strands' value, the hair's colour is ours (Unreal's
    hair material does the same); the alpha stays the atlas's"""
    tint = dict(male=(.050, .034, .024), female=(.105, .060, .034))[sex]
    for m in bpy.data.materials:
        if not m.name.startswith("hair") or not m.use_nodes:
            continue
        nt = m.node_tree
        bs = nt.nodes.get("Principled BSDF")
        img = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None)
        if not bs or not img:
            continue
        for l in list(bs.inputs["Base Color"].links) + list(bs.inputs["Alpha"].links):
            nt.links.remove(l)
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
        nt.links.new(img.outputs["Color"], mul.inputs[6])
        k = 1.9 if m.name in ("hair__brow", "hair__lash") else 2.6            # (the atlas's strands are mid grey)
        mul.inputs[7].default_value = (tint[0] * k, tint[1] * k, tint[2] * k, 1)
        nt.links.new(mul.outputs[2], bs.inputs["Base Color"])
        nt.links.new(img.outputs["Alpha"], bs.inputs["Alpha"])
        bs.inputs["Roughness"].default_value = .38
        try:
            bs.inputs["Specular IOR Level"].default_value = .35
            m.surface_render_method = 'DITHERED'
        except Exception:
            pass


def materials(o, eo, imgs, log):
    def skin_nodes(mat):
        mat.use_nodes = True
        nt = mat.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(bs.outputs[0], out.inputs[0])
        tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = imgs["col"]
        to = nt.nodes.new('ShaderNodeTexImage'); to.image = imgs["orm"]
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = imgs["nrm"]
        ts = nt.nodes.new('ShaderNodeTexImage'); ts.image = imgs["sss"]
        sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(to.outputs[0], sep.inputs[0])
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 1.1
        nt.links.new(tn.outputs[0], nm.inputs['Color'])
        nt.links.new(tc.outputs[0], bs.inputs['Base Color'])
        nt.links.new(sep.outputs[1], bs.inputs['Roughness'])
        nt.links.new(nm.outputs[0], bs.inputs['Normal'])
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = .14
        nt.links.new(ts.outputs[0], mul.inputs[0])
        try:
            nt.links.new(mul.outputs[0], bs.inputs['Subsurface Weight'])
            bs.inputs['Subsurface Radius'].default_value = (1.0, .35, .18)
            bs.inputs['Subsurface Scale'].default_value = .006
            bs.inputs['Specular IOR Level'].default_value = .36
        except Exception:
            pass
    for s in o.material_slots:
        skin_nodes(s.material)
    for s in eo.material_slots:
        mat = s.material; mat.use_nodes = True
        nt = mat.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(bs.outputs[0], out.inputs[0])
        tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = imgs["eye"]
        nt.links.new(tc.outputs[0], bs.inputs['Base Color'])
        bs.inputs['Roughness'].default_value = .06
        try:
            bs.inputs['Coat Weight'].default_value = 1.0; bs.inputs['Coat Roughness'].default_value = .02
            bs.inputs['Specular IOR Level'].default_value = .6
        except Exception:
            pass


def game_skin(o, T, sex, log, size=4096):
    """the game's body (build.py): its UVs, its skin maps and the eye's, written beside the body's other textures
    (hair.tex_dir) and wired into the skin__<region> / eye materials the GLB carries (base colour, occlusion-roughness,
    normal: the Unreal import makes the instances from them). The corner colour goes white: the lips and lids are in
    the maps now."""
    import hair as hair_mod
    arm = o.parent
    eo = bpy.data.objects["B_eyes"]
    act = arm.animation_data.action if arm.animation_data else None
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    arm.data.pose_position = 'REST'
    seams_and_unwrap(o, T, log)
    eye_uvs(eo, T)
    imgs = textures(o, eo, T, sex, None, size, log, tex=hair_mod.tex_dir(T), stem=f"hero_{sex}_skin", eye_stem=f"hero_{sex}_eye")
    materials(o, eo, imgs, log)
    for ca in o.data.color_attributes:
        n = len(ca.data)
        ca.data.foreach_set("color", np.ones(n * 4, F32))
    arm.data.pose_position = 'POSE'
    if act is not None:
        arm.animation_data.action = act
    only(arm)


# ------------------------------------------------------------------------------------------------------ 6 project
def collection(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    par = parent or bpy.context.scene.collection
    if c.name not in par.children:
        par.children.link(c)
    return c


def move(o, c):
    for cc in list(o.users_collection):
        cc.objects.unlink(o)
    c.objects.link(o)


def lods(o, sex, col, log):
    out = []
    for i, ratio in enumerate((.5, .25, .12), 1):
        d = o.copy(); d.data = o.data.copy()
        d.name = d.data.name = f"SK_Orion{sex.capitalize()}_Body_LOD{i}"
        col.objects.link(d)
        only(d)
        if d.data.shape_keys:
            bpy.ops.object.shape_key_remove(all=True)
        md = d.modifiers.new("lod", 'DECIMATE'); md.ratio = ratio; md.use_collapse_triangulate = True
        # the decimation goes before the armature
        while d.modifiers[0] != md:
            bpy.ops.object.modifier_move_up(modifier=md.name)
        bpy.ops.object.modifier_apply(modifier=md.name)
        d.hide_render = True; d.hide_viewport = True
        out.append(d)
        log(f"LOD{i}: {len(d.data.vertices)} vertices, {sum(len(p.vertices) - 2 for p in d.data.polygons)} triangles")
    return out


def organise(sex, T, o, arm, log):
    S = sex.capitalize()
    eo = bpy.data.objects["B_eyes"]; br = bpy.data.objects["B_brows"]
    hair = [x for x in bpy.data.objects if x.name.startswith("C_hair__")]
    cb = collection(f"{S}_Base_Body"); ch = collection(f"{S}_Head"); ce = collection(f"{S}_Eyes")
    chr_ = collection(f"{S}_Hair"); cs = collection(f"{S}_Skeleton")
    cm = collection("Materials"); cr = collection("Reference"); cx = collection("Export")
    move(o, cb); move(br, ch); move(eo, ce); move(arm, cs)
    for h in hair:
        move(h, chr_)
    o.name = o.data.name = f"SK_Orion{S}_Body"
    eo.name = eo.data.name = f"SK_Orion{S}_Eyes"
    br.name = br.data.name = f"SK_Orion{S}_BrowsLashes"
    for h in hair:
        h.name = h.data.name = f"SK_Orion{S}_Hair"
    arm.name = f"SKEL_Orion{S}"
    # material swatches
    mats = []
    for ob in [o, eo, br] + hair:
        for s in ob.material_slots:
            if s.material and s.material not in mats:
                mats.append(s.material)
    for i, m in enumerate(mats):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.04, location=(-1.2 + (i % 6) * .1, 0, 2.3 - (i // 6) * .1))
        sp = bpy.context.active_object
        sp.name = "MAT_" + m.name; sp.data.materials.append(m); sp.hide_render = True
        move(sp, cm)
    # reference: the height, and where the concept sheet goes
    for nm, z in (("REF_height_%.2fm" % T["height"], T["height"]), ("REF_ground", 0.0)):
        e = bpy.data.objects.new(nm, None); e.empty_display_type = 'PLAIN_AXES'; e.empty_display_size = .5
        e.location = (0, 0, z); cr.objects.link(e)
    e = bpy.data.objects.new("REF_concept_sheet", None); e.empty_display_type = 'IMAGE'; e.location = (1.4, .2, 1.0)
    e["note"] = "the Orion concept sheet: put the image here (it was sent in chat, it is not in the repository)"
    cr.objects.link(e)
    L = lods(o, sex, cx, log)
    return dict(body=o, eyes=eo, brows=br, hair=hair, arm=arm, lods=L)


# ------------------------------------------------------------------------------------------------------ 7 export
def export_fbx(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objs:
        hv, hr = ob.hide_viewport, ob.hide_get()
        ob.hide_viewport = False; ob.hide_set(False)
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH", "ARMATURE"}, global_scale=1.0, apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y", axis_up="Z", use_space_transform=True,
        bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type="FACE", use_tspace=True, use_triangles=False,
        add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X", use_armature_deform_only=True,
        armature_nodetype="NULL", bake_anim=False, colors_type="LINEAR", path_mode="STRIP", embed_textures=False)


def render_sheet(P, T, out_png, views, res, log, samples=48):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = samples
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.render.film_transparent = False
    sc.view_settings.exposure = -.9
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    w = bpy.data.worlds.new("studio"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (.055, .058, .065, 1); bg.inputs[1].default_value = 1.0
    H = T["height"]
    rigc = collection("Render_Rig")
    for nm, loc, e, colr, size in (("key", (1.9, -2.6, H + .5), 400, (1, .96, .90), 1.6), ("fill", (-2.4, -1.8, H * .6), 80, (.82, .88, 1), 2.2),
                                   ("rim", (-1.4, 2.6, H + .7), 420, (.95, .97, 1), 1.2), ("rim2", (2.0, 2.2, H * .5), 130, (1, .95, .9), 1.2)):
        ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.color = colr; ld.size = size
        lo = bpy.data.objects.new("LIGHT_" + nm, ld); lo.location = loc
        lo.rotation_euler = (Vector((0, 0, H * .62)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
        rigc.objects.link(lo)
    cam = bpy.data.objects.new("CAM", bpy.data.cameras.new("CAM")); rigc.objects.link(cam); sc.camera = cam
    cam.data.type = 'PERSP'; cam.data.lens = 85
    P["arm"].data.pose_position = 'REST'
    body = shape_mod.Body(T); g = body.head_geometry()
    hc = Vector((0, Y0 - .015, g["chin"] + .118 * g["hs"]))
    VIEW = {"front": (0, 0, None), "back": (180, 0, None), "left": (90, 0, None), "right": (-90, 0, None), "q": (35, 4, None), "qb": (145, 4, None),
            "face": (0, 0, .34), "face_q": (38, 3, .34), "face_side": (90, 0, .34), "face_qr": (-38, 3, .34), "face_low": (25, -22, .34),
            "torso": (20, 0, .78), "hands": (0, 0, None)}
    tiles = []
    for name in views:
        yaw, pitch, span = VIEW[name]
        yw, pt = math.radians(yaw), math.radians(pitch)
        d = Vector((math.sin(yw) * math.cos(pt), -math.cos(yw) * math.cos(pt), math.sin(pt)))      # from the target to the camera
        if span is None:
            c = Vector((0, 0, H * .5)); span = H * 1.08; sc.render.resolution_y = res
            sc.render.resolution_x = int(res * (.50 if name in ('left', 'right') else .86))     # (the A-pose's arm span fits)
        elif name == "torso":
            c = Vector((0, 0, H * .70)); sc.render.resolution_x = int(res * .8); sc.render.resolution_y = res
        else:
            c = hc; sc.render.resolution_x = int(res * .8); sc.render.resolution_y = res
        dist = span / (2 * math.tan(cam.data.angle_y / 2)) if sc.render.resolution_y >= sc.render.resolution_x else span
        cam.data.sensor_fit = 'VERTICAL'
        dist = span / 2 / math.tan(math.atan(cam.data.sensor_height / 2 / cam.data.lens))
        cam.location = c + d * dist
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        p = out_png[:-4] + f"_{name}.png"
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.append(p)
        log(f"rendered {name}")
    return tiles


def render_only(sex, T, out, flags, log):
    """the renders again from the saved per-sex file"""
    S = sex.capitalize()
    P = dict(arm=bpy.data.objects[f"SKEL_Orion{S}"])
    for l in [o for o in bpy.data.objects if o.type == 'LIGHT' or o.name == "CAM"]:
        bpy.data.objects.remove(l)
    res = int(flags.get("--res", 1400)) if isinstance(flags.get("--res"), str) else 1400
    views = flags["--views"].split(",") if isinstance(flags.get("--views"), str) else ["front", "back"]
    render_sheet(P, T, os.path.join(out, "renders", f"Orion{S}.png"), views, res, log)


def finish(sex, T, out, flags, log):
    size = int(flags.get("--size", 4096)) if isinstance(flags.get("--size"), str) else 4096
    o = bpy.data.objects["B_body"]; arm = bpy.data.objects["Armature"]; eo = bpy.data.objects["B_eyes"]
    arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    arm.data.pose_position = 'REST'
    n_isl, uv_area = seams_and_unwrap(o, T, log)
    eye_uvs(eo, T)
    imgs = textures(o, eo, T, sex, out, size, log)
    materials(o, eo, imgs, log)
    hair_materials(sex)
    P = organise(sex, T, o, arm, log)
    S = sex.capitalize()
    # export: LOD0 with everything on the skeleton, then each body LOD
    fbx = os.path.join(out, "fbx"); os.makedirs(fbx, exist_ok=True)
    export_fbx([P["arm"], P["body"], P["eyes"], P["brows"]] + P["hair"], os.path.join(fbx, f"SK_Orion{S}.fbx"))
    for i, d in enumerate(P["lods"], 1):
        export_fbx([P["arm"], d], os.path.join(fbx, f"SK_Orion{S}_Body_LOD{i}.fbx"))
        d.hide_viewport = True
    log("fbx written")
    tris = lambda ob: sum(len(p.vertices) - 2 for p in ob.data.polygons)
    man = dict(
        sex=sex, height_m=T["height"], units="metres (FBX exported with unit scale: centimetres in Unreal)",
        body=dict(vertices=len(P["body"].data.vertices), quads=len(P["body"].data.polygons), triangles=tris(P["body"]),
                  uv_islands=n_isl, uv_coverage=round(uv_area, 3),
                  shape_keys=[k.name for k in P["body"].data.shape_keys.key_blocks] if P["body"].data.shape_keys else []),
        lods=[dict(name=d.name, vertices=len(d.data.vertices), triangles=tris(d)) for d in P["lods"]],
        eyes=dict(triangles=tris(P["eyes"])), brows_lashes=dict(triangles=tris(P["brows"])),
        hair=[dict(name=h.name, triangles=tris(h)) for h in P["hair"]],
        skeleton=dict(bones=len(P["arm"].data.bones), names=[b.name for b in P["arm"].data.bones if b.use_deform]),
        materials=[s.material.name for s in P["body"].material_slots],
        textures=dict(size=size, normal_convention="OpenGL (+Y): flip green on import into Unreal",
                      files=sorted(os.listdir(os.path.join(out, "textures")))),
    )
    json.dump(man, open(os.path.join(out, f"Orion{S}_manifest.json"), "w"), indent=1)
    if "--norender" not in flags:
        rdir = os.path.join(out, "renders"); os.makedirs(rdir, exist_ok=True)
        res = int(flags.get("--res", 1400)) if isinstance(flags.get("--res"), str) else 1400
        views = flags["--views"].split(",") if isinstance(flags.get("--views"), str) else \
            ["front", "back", "left", "right", "q", "face", "face_q", "face_side"]
        render_sheet(P, T, os.path.join(rdir, f"Orion{S}.png"), views, res, log)
    bpy.ops.file.pack_all() if False else None
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"Orion{S}_Base.blend"), relative_remap=True)
    log("saved", os.path.join(out, f"Orion{S}_Base.blend"))
