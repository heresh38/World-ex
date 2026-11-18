"""The new body against the owner's sheet: builds it (body.py), checks its topology, and renders the sheet's three
views of it at the sheet's own scale beside the sheet, each outline drawn over the other.

blender -b -P tools/blender/hero/orion/lab.py -- <out.png> [--levels=2] [--save=x.blend] [--cage]

  out.png          the comparison: per view the sheet (heights put through the canon's landmarks, as the body is)
                   with the body's outline in red, and the body in clay with the sheet's outline in green
  --cage           the cage alone (no limit fit, no subdivision), wireframe
"""
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
import body as B

SHEET = os.path.join(ROOT, "art", "reference", "player", "orion_tpose_bodysuit.png")
BOX = dict(front=(10, 2), side=(540, 2), back=(720, 2))         # the views' boxes on the sheet (x0, y0)
BACK_C = 249.0
MPP = 0.002                                                       # metres per pixel of the comparison
SIZE = (1000, 1000)                                               # 2 m x 2 m
Z_MID = 0.95


def log(*a):
    print("[orion]", *a, flush=True)


def report(bm, label):
    sides = {}
    for f in bm.faces:
        sides[len(f.verts)] = sides.get(len(f.verts), 0) + 1
    bound = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    poles = {}
    for v in bm.verts:
        n = len(v.link_edges)
        if n != 4:
            poles[n] = poles.get(n, 0) + 1
    log(f"{label}: {len(bm.verts)} verts, faces {dict(sorted(sides.items()))}, boundary edges {bound}, "
        f"non-manifold {nonman}, poles {dict(sorted(poles.items()))}")
    return bound == 0 and nonman == 0


def make_object(X, F, name):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in X], [], [list(f) for f in F])
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    report(bm, name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = True
    return o


def camera(view):
    sc = bpy.context.scene
    cam = sc.camera
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = SIZE[0] * MPP
    d = {"front": Vector((0, -1, 0)), "side": Vector((-1, 0, 0)), "back": Vector((0, 1, 0))}[view]
    cam.location = d * 8 + Vector((0, 0, Z_MID))
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()


def render(view, path, flat):
    sc = bpy.context.scene
    sh = sc.display.shading
    if flat:
        sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (1, 1, 1)
        sh.show_cavity = False; sh.show_shadows = False; sh.show_specular_highlight = False
        sh.background_type = 'VIEWPORT'; sh.background_color = (0, 0, 0)
    else:
        sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (.62, .58, .55)
        sh.show_cavity = True; sh.cavity_type = 'BOTH'
        sh.show_specular_highlight = True
        sh.background_type = 'VIEWPORT'; sh.background_color = (.2, .2, .23)
    camera(view)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path, check_existing=False)
    W, H = im.size
    a = np.array(im.pixels[:], np.float32).reshape(H, W, 4)[::-1]          # top row first
    bpy.data.images.remove(im)
    return a


def sheet_view(view, sheet, mask):
    """the sheet's view resampled onto the comparison's metric grid (heights through the canon's landmarks)"""
    W, H = SIZE
    x0, y0 = BOX[view]
    cols = np.arange(W)
    rows = np.arange(H)
    h = (cols + .5 - W / 2) * MPP                         # horizontal metres (image right positive)
    z = Z_MID + (H / 2 - rows - .5) * MPP
    rz = np.array([B.Concept.row(v) for v in z])         # box rows
    if view == "front":
        cx = B.FRONT_C + h / B.CPX                        # image right = +x
    elif view == "side":
        cx = B.SIDE_C + h / B.CPX                         # image right = -y = front
    else:
        cx = BACK_C + h / B.CPX                           # image right = -x
    R = np.clip(np.round(rz).astype(int)[:, None] + y0, 0, sheet.shape[0] - 1)
    Cc = np.clip(np.round(cx).astype(int)[None, :] + x0, 0, sheet.shape[1] - 1)
    img = sheet[R, Cc]
    img[(rz < 4)[:, None].repeat(W, 1)] = sheet[6, 6]                    # above the sheet's box: the backdrop
    mr = np.clip(np.round(rz).astype(int)[:, None], 0, mask.shape[0] - 1)
    mc = np.clip(np.round(cx).astype(int)[None, :], 0, mask.shape[1] - 1)
    m = mask[mr, mc]
    inside = (cx[None, :] >= 0) & (cx[None, :] < mask.shape[1]) & (rz[:, None] >= 0) & (rz[:, None] < mask.shape[0])
    return img, m & inside


def edge(m):
    e = np.zeros_like(m)
    e[1:, :] |= m[1:, :] != m[:-1, :]
    e[:, 1:] |= m[:, 1:] != m[:, :-1]
    e[:-1, :] |= e[1:, :].copy()
    return e


def outline_report(view, sil, sm):
    """the two outlines measured against each other (cm, body minus sheet): the front view's widths at every 4 cm
    of height and the arm's top and bottom every 4 cm along it; the side view's front and back"""
    W, H = SIZE
    zs = Z_MID + (H / 2 - np.arange(H) - .5) * MPP
    hs = (np.arange(W) + .5 - W / 2) * MPP

    def span(m, r, lo, hi):
        """first and last column of the mask in row r between columns lo..hi (metres)"""
        sel = (hs >= lo) & (hs <= hi)
        c = np.nonzero(m[r] & sel)[0]
        return (hs[c[0]], hs[c[-1]]) if len(c) else None

    lines = []
    if view in ("front", "back"):
        for z in np.arange(0.10, 1.66, 0.04):
            r = int(round((Z_MID - z) / MPP + H / 2 - .5))
            lim = .17 if z > 1.40 else .60
            a, b = span(sil, r, -lim, lim), span(sm, r, -lim, lim)
            if a and b:
                lines.append(f"z {z:.2f}: width {(a[1] - a[0]) * 100:5.1f} vs {(b[1] - b[0]) * 100:5.1f} "
                             f"({(a[1] - a[0] - b[1] + b[0]) * 100:+5.1f})")
        if view == "front":
            # each leg on its own: its width and the gap between the two (the owner: legs "too bulky"; the outer
            # span hid thighs pressed together)
            for z in np.arange(0.10, 0.90, 0.04):
                r = int(round((Z_MID - z) / MPP + H / 2 - .5))

                def legs(m):
                    sel = (hs > -.40) & (hs < .40)
                    on = np.r_[0, (m[r] & sel).astype(np.int8), 0]
                    e = np.flatnonzero(np.diff(on))
                    runs = [(hs[e[i]], hs[e[i + 1] - 1]) for i in range(0, len(e), 2)]
                    return runs if len(runs) == 2 else None
                a, b = legs(sil), legs(sm)
                if a and b:
                    lines.append(f"leg z {z:.2f}: width {(a[1][1] - a[1][0]) * 100:5.1f} vs {(b[1][1] - b[1][0]) * 100:5.1f} "
                                 f"({((a[1][1] - a[1][0]) - (b[1][1] - b[1][0])) * 100:+5.1f}), gap {(a[1][0] - a[0][1]) * 100:5.1f} "
                                 f"vs {(b[1][0] - b[0][1]) * 100:5.1f}")
            for x in np.arange(0.22, 0.90, 0.04):
                c = int(round(x / MPP + W / 2 - .5))
                for side, cc in (("L", c), ("R", W - 1 - c)):
                    ra = np.nonzero(sil[:, cc] & (zs > 1.25) & (zs < 1.75))[0]
                    rb = np.nonzero(sm[:, cc] & (zs > 1.25) & (zs < 1.75))[0]
                    if len(ra) and len(rb) and side == "L":
                        lines.append(f"arm x {x:.2f}: top {zs[ra[0]]:.3f} vs {zs[rb[0]]:.3f} ({(zs[ra[0]] - zs[rb[0]]) * 100:+.1f})"
                                     f", bottom {zs[ra[-1]]:.3f} vs {zs[rb[-1]]:.3f} ({(zs[ra[-1]] - zs[rb[-1]]) * 100:+.1f})")
    else:
        for z in np.arange(0.10, 1.66, 0.04):
            r = int(round((Z_MID - z) / MPP + H / 2 - .5))
            a, b = span(sil, r, -.6, .6), span(sm, r, -.6, .6)
            if a and b:
                lines.append(f"z {z:.2f}: back {-a[0] * 100:5.1f} vs {-b[0] * 100:5.1f} ({(b[0] - a[0]) * 100:+5.1f}), "
                             f"front {-a[1] * 100:5.1f} vs {-b[1] * 100:5.1f} ({(a[1] - b[1]) * 100:+5.1f})")
    with open(os.path.join(os.path.dirname(SIZE_OUT[0]), f"outline_{view}.txt"), "w") as f:
        f.write("\n".join(lines))


SIZE_OUT = [""]


def turnaround(sc, path, samples=64):
    """the body in clay under a studio's light (Cycles): front, three quarters, side, back, as the sheet shows it"""
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
        sc.cycles.device = 'GPU'
    except Exception:
        pass
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new("w"); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (.20, .20, .23, 1); bg.inputs[1].default_value = .12
    mat = bpy.data.materials.new("clay"); mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (.32, .30, .285, 1); b.inputs["Roughness"].default_value = .55
    skin = bpy.data.materials.get("skin")
    for o in sc.objects:                                              # the suit, the head, the eyes keep their own
        if o.type == 'MESH' and o.name not in ("suit", "collar", "head", "eye_L", "eye_R"):
            o.data.materials.clear(); o.data.materials.append(skin if (skin and o.get("skin")) else mat)
            for p in o.data.polygons:
                p.use_smooth = True
    tgt = Vector((0, 0, .95))

    def light(name, energy, loc, size):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.size = size
        ob = bpy.data.objects.new(name, L); ob.location = loc
        ob.rotation_euler = (tgt - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(ob)
    light("key", 260, (2.2, -3.0, 3.2), 2.5)
    light("fill", 70, (-3.0, -2.2, 1.6), 3.0)
    light("rim", 260, (-1.2, 3.2, 2.8), 2.0)
    cam = sc.camera
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.05
    sc.render.resolution_x, sc.render.resolution_y = 900, 1000
    shots = []
    for name, yaw in (("front", 0), ("q", 35), ("side", 90), ("back", 180)):
        y = math.radians(yaw)
        d = Vector((math.sin(y), -math.cos(y), 0))
        cam.location = d * 8 + Vector((0, 0, .94))
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        p = path.replace(".png", f"_{name}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        shots.append(load_png(p)[..., :3])
    img = np.concatenate(shots, axis=1)
    hh, ww = img.shape[:2]
    res = bpy.data.images.new("look", ww, hh, alpha=False)
    res.pixels = np.concatenate([img[::-1], np.ones((hh, ww, 1), np.float32)], axis=2).ravel()
    res.filepath_raw = path; res.file_format = 'PNG'; res.save()
    log("look", path)


def load_png(path):
    im = bpy.data.images.load(path, check_existing=False)
    W, H = im.size
    a = np.array(im.pixels[:], np.float32).reshape(H, W, 4)[::-1]
    bpy.data.images.remove(im)
    return a


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    SIZE_OUT[0] = out
    flags ={a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    t0 = time.time()
    if "--anatomy" in flags:
        # the anatomy itself (anatomy.py), meshed straight from its field
        sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
        sys.path.insert(0, HERE)
        import sdf
        import anatomy as AN
        body = AN.Anatomy()
        lo, hi = body.bounds()
        Vv, Qq = sdf.mesh(body, lo, hi, float(flags.get("--h", .003)), log=log)
        o = make_object(Vv, Qq, "orion_anatomy")
    else:
        C, info = B.build(log=log, game_head="--gamehead" in flags)
        if "--cage" in flags:
            X = np.array(C.V)
        else:
            # the toes and the forefoot's last rings are left (partly) free: an exact fit there overshot between
            # the toes and folded the skin; their targets stand out by what the subdivision takes back (foot.py)
            import foot as FTM
            Vc = np.array(C.V)
            fore = np.zeros(len(Vc))
            for Ff in info["feet"]:
                q = Vc - np.array([Ff.A[0], Ff.A[1], 0.0])
                fore = np.maximum(fore, ((q @ Ff.fw > FTM.MID_F + .004) & (Vc[:, 0] * Ff.sx > 0) & (Vc[:, 2] < .09)) * 1.0)
            free = np.array([1.0 if p.startswith("toe_") else 0.0 for p in C.part])
            free = np.maximum(free, fore * np.array([p in ("foot", "fore") for p in C.part]))
            free = np.maximum(free, C.free())                     # the arm's windows' corners (body.py)
            X = B.solve_cage(C.V, C.F, log=log, free=free)
        o = make_object(X, C.F, "orion_male")
        # each cage face's body region (the game hides the regions worn pieces cover): kept by every face the
        # subdivision makes of it, so a region's border is one of the cage's own edge loops
        reg = o.data.attributes.new("region", 'INT', 'FACE')
        reg.data.foreach_set("value", B.face_regions(C, X))
        if info.get("head") is not None:                     # the eyes' rims: where each lies on the opening, the band
            rim = np.zeros(len(C.V), np.float32); ru = np.zeros(len(C.V), np.float32); rt = np.zeros(len(C.V), np.float32)
            rs = np.zeros(len(C.V), np.float32)
            for side, sxe in (("eye_L", 1), ("eye_R", -1)):
                vs, u_, t_ = info["head"]["feats"][side + "_rim"]
                ren = getattr(C, "renumbered", None)            # (noted before the cage was compacted)
                if ren is not None:
                    vs = [ren[v] for v in vs]
                rim[vs] = 1.0; ru[vs] = u_; rt[vs] = t_; rs[vs] = sxe
            for name, vals in (("rim", rim), ("rim_u", ru), ("rim_t", rt), ("rim_s", rs)):
                o.data.attributes.new(name, 'FLOAT', 'POINT').data.foreach_set("value", vals)
        if info.get("head") is not None:                     # the ears' windows' caps (ear.py cuts them out)
            cap = np.zeros(len(C.F), np.int32)
            for side, k in (("ear_L", 1), ("ear_R", 2)):
                cap[info["head"]["feats"][side][2]] = k
            o.data.attributes.new("earcap", 'INT', 'FACE').data.foreach_set("value", cap)
        if info.get("head") is not None:                     # the game head's vertices (headcage.py)
            hw = o.data.attributes.new("headw", 'FLOAT', 'POINT')
            hw.data.foreach_set("value", np.array([1.0 if p == "head" else 0.0 for p in C.part], np.float32))
        # which toe each vertex is (carried through the subdivision, read back for the skin's last step)
        import foot as FTM
        for k, name in enumerate(FTM.TOE_NAMES):
            at = o.data.attributes.new(f"toe{k}", 'FLOAT', 'POINT')
            at.data.foreach_set("value", np.array([1.0 if p == f"toe_{name}" else 0.0 for p in C.part], np.float32))
        if "--cage" not in flags:
            m = o.modifiers.new("sub", 'SUBSURF')
            m.levels = m.render_levels = int(flags.get("--levels", 2))
        if "--detail" in flags:
            # the anatomy's forms over the subdivided body (anatomy.py): along each vertex's normal
            sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
            sys.path.insert(0, HERE)                     # (head.py puts the older hero folder first: its anatomy.py)
            import anatomy as AN
            dg = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
            o.modifiers.clear()
            o.data = me
            n = len(me.vertices)
            co = np.zeros(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
            nr = np.zeros(n * 3, np.float32); me.vertices.foreach_get("normal", nr); nr = nr.reshape(n, 3)
            face_d = {}
            disp = AN.Anatomy().detail(co)
            # the feet have their own anatomy (footshape.py): the muscles' detail fades out above the ankle
            disp = disp * np.clip((co[:, 2] - .17) / .09, 0, 1) ** 2 * (3 - 2 * np.clip((co[:, 2] - .17) / .09, 0, 1))
            # ... and the hands have theirs (hand.py): the muscles' smooth union leaves the body's whole skin 4.9 mm
            # out (the torso's and limbs' sections were tuned with it), which on a finger 1.6 cm across made it 2.6
            # and fused the fingers up to their middle joints: faded out over the wrist into the palm
            import hand as HM
            for Fh in info["hands"]:
                xh = (co - Fh.W) @ Fh.ax
                on = (co[:, 0] * Fh.sx > 0).astype(np.float32)
                t = np.clip((xh - (-.010)) / .040, 0, 1)
                disp = disp * (1 - on * (t * t * (3 - 2 * t))).astype(np.float32)
            disp = disp + HM.detail(co, info["hands"])
            co += nr * disp[:, None]
            # the flank under each arm smoothed like a sculptor's smooth brush (the owner circled a bulge there twice,
            # 2026-11-17: "the bulge is huge please fix and smooth it out")
            ed_s = np.zeros(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", ed_s)
            co = B.smooth_zone(co, ed_s.reshape(-1, 2), B.FLANK_ZONES, iters=28, lam=.5).astype(np.float32)
            # the feet: the skin laid onto the foot's anatomy (footshape.py)
            import foot as FTM
            if "--nofootskin" not in flags:
                toe_w = np.zeros((n, len(FTM.TOE_NAMES)), np.float32)
                for k in range(len(FTM.TOE_NAMES)):
                    a = me.attributes.get(f"toe{k}")
                    if a is not None:
                        w = np.zeros(n, np.float32); a.data.foreach_get("value", w)
                        toe_w[:, k] = w
                ed = np.zeros(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", ed)
                off = FTM.skin_offsets(co, nr, info["feet"], toe_w, ed.reshape(-1, 2))
                log(f"feet laid on their anatomy: {off.min() * 1000:.1f} .. {off.max() * 1000:.1f} mm")
                co = co + nr * off[:, None]
                co = FTM.separate_toes(co, info["feet"], toe_w, edges=ed.reshape(-1, 2))
            if info.get("head") is not None:
                import headcage as HCG
                a = me.attributes.get("headw")
                hw = np.zeros(n, np.float32); a.data.foreach_get("value", hw)
                edh = np.zeros(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", edh)
                fqh = np.zeros(len(me.polygons) * 4, np.int64); me.polygons.foreach_get("vertices", fqh)
                hf = info["head"]["field"]
                F4 = fqh.reshape(-1, 4)
                co_pre = co.copy()
                ears, pins = {}, None
                capf = None
                if HCG.EAR_OPEN:
                    # the ears (ear.py): each a ring grid on the sculpt's own ear, the window's loop moved onto its base
                    import ear as EAR
                    capf = np.zeros(len(me.polygons), np.int32)
                    me.attributes["earcap"].data.foreach_get("value", capf)
                    for sxe, k in ((1, 1), (-1, 2)):
                        lp = np.array(EAR.cap_loop(F4, capf == k))
                        ring0, inner, ef = EAR.build(hf, sxe, co[lp].astype(np.float64), log=log)
                        ears[sxe] = (lp, ring0, inner, ef)
                    pins = (np.concatenate([ears[s][0] for s in (1, -1)]), np.concatenate([ears[s][1] for s in (1, -1)]))
                # the eyes' rims (the openings' borders) on the sculpt's own opening, the lids' bands filled
                rims, band = [], None
                if me.attributes.get("rim") is not None:
                    getv = lambda nm: (lambda a: (me.attributes[nm].data.foreach_get("value", a), a)[1])(np.zeros(n, np.float32))
                    rimv, rim_u, rim_t, rim_s = getv("rim"), getv("rim_u"), getv("rim_t"), getv("rim_s")
                    e2 = edh.reshape(-1, 2)
                    cnt = np.bincount(F4.ravel(), minlength=n)
                    a_, b_ = F4.ravel(), np.roll(F4, -1, axis=1).ravel()
                    key = np.minimum(a_, b_) * (1 << 32) + np.maximum(a_, b_)
                    uq, inv, kc = np.unique(key, return_inverse=True, return_counts=True)
                    onb = np.zeros(n, bool); bk = uq[kc == 1]
                    onb[(bk >> 32).astype(np.int64)] = True; onb[(bk & 0xFFFFFFFF).astype(np.int64)] = True
                    for sxe in (1, -1):
                        ids = np.flatnonzero(onb & (rim_s * sxe > .5))
                        if len(ids):
                            rims.append((ids, sxe, rim_u[ids], rim_t[ids]))
                    # (the lids' bands filled as a membrane between the rim and the lid made creases sharper than the
                    # folds it took away, 180 edges over 100 degrees against 112: the rim tucked into the eye under a
                    # skirt is the way; until then the bands are laid like the rest)
                    band = None
                    rp = [HCG.rim_points(hf.hd, s_, u_, t_) for _, s_, u_, t_ in rims]
                    if rims:
                        rid = np.concatenate([r[0] for r in rims]); rpt = np.concatenate(rp)
                        pins = (rid, rpt) if pins is None else (np.r_[pins[0], rid], np.r_[pins[1], rpt])
                    log(f"eyes' rims: {sum(len(r[0]) for r in rims)} vertices on the sculpt's opening")
                # the lids' bands (the four rings out from each rim): laid by construction (headcage.place_lids)
                lids = []
                for ids, s_, u_, t_ in rims:
                    rg = HCG.lid_rings(edh.reshape(-1, 2), ids, 8)
                    lids.append(dict(side=s_, u=u_, t=t_, rim=ids, rings=rg[:4], front=rg[3:8]))
                    log(f"lid band ({'left' if s_ > 0 else 'right'}): {len(ids)} columns, "
                        f"{int(sum((r >= 0).sum() for r in rg))} of {8 * len(ids)} ring vertices found")
                co = HCG.lay_on_head(co, nr, hw, hf, edges=edh.reshape(-1, 2), faces=F4, log=log,
                                     pins=pins, band=band, lids=lids).astype(np.float32)
                if "--facekeys" in flags:                       # the face's sliders as morphs (headcage.py)
                    face_d = HCG.face_keys(co_pre, nr, hw, hf, edh.reshape(-1, 2), log=log, ears=ears,
                                           rims=rims, band=band, lids=lids)
                if ears:
                    me, co, face_d = EAR.attach(o, me, co, ears, capf > 0, keys=face_d, log=log)
                    n = len(me.vertices)
            # the thumb's root rounded off (hand.py)
            ed2 = np.zeros(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", ed2)
            co = HM.smooth_root(co, ed2.reshape(-1, 2), info["hands"]).astype(np.float32)
            # the last pass: what still folds or crosses itself in the hands and feet is relaxed there (meshfix.py)
            if "--nountangle" not in flags:
                import meshfix as MF
                qf = np.zeros(len(me.polygons) * 4, np.int64); me.polygons.foreach_get("vertices", qf)
                digits = co[:, 2] < .23                                   # the feet (the hands are not yet checked)
                co = MF.untangle(co, qf.reshape(-1, 4), digits, rounds=int(flags.get("--untangle", 6)), log=log).astype(np.float32)
            me.vertices.foreach_set("co", co.ravel())
            me.update()
            if face_d:
                o.shape_key_add(name="Basis", from_mix=False)
                for name, D in face_d.items():
                    kb = o.shape_key_add(name="face_" + name, from_mix=False)
                    kb.value = 0.0                                # off (Blender adds new keys at 1.0)
                    kb.data.foreach_set("co", (co + D).astype(np.float32).ravel())
                log(f"face keys: {len(face_d)}")
            log(f"anatomy over {n} vertices: {disp.min() * 1000:.1f} .. {disp.max() * 1000:.1f} mm")
            zb = None
            if "--head" in flags or "--suit" in flags:
                import suit as SU
                zb = SU.neckline(o, log=log)                  # where the body turns up into the neck, round it
            if "--head" in flags:
                # the body's neck goes up inside the head (head.py carries the neck from the head's cut down to it):
                # from the neckline to the collar's top it is drawn in under the head's skin, more the higher (the
                # back of the neck leaves the upper back at the 7th vertebra and meets the head's nape inside the
                # collar); under the neckline the body is as built. A cut-off by distance from the head (the first
                # way) left the back's top where it was and drew the rest in: a shelf at the nape
                import head as HD
                import sdf
                hd = HD.Head()
                me = o.data
                n = len(me.vertices)
                co = np.zeros(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
                th, r = SU.around(co)
                z0 = SU.periodic(zb, th) + .004
                z1 = SU.collar_top(th) - .006
                w = SU.smooth01((co[:, 2] - z0) / np.maximum(z1 - z0, .01)) * (1 - SU.smooth01((r - .095) / .03))
                up = np.nonzero((w > 0) & (co[:, 2] > 1.45))[0]
                if len(up):
                    P = co[up].astype(np.float64)
                    for _ in range(6):
                        d = hd(P)
                        g = sdf.grad(hd, P)
                        g /= np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]
                        step = np.maximum(d + .003, 0)
                        P = P - g * step[:, None]
                    mv = P - co[up]
                    ln = np.linalg.norm(mv, axis=1)
                    mv *= np.minimum(1, .06 / np.maximum(ln, 1e-9))[:, None]
                    co[up] = co[up] + mv * w[up, None]
                    me.vertices.foreach_set("co", co.ravel())
                    me.update()
                    log(f"the body's neck drawn in under the head: {len(up)} vertices, up to {ln.max() * 100:.1f} cm")
            if "--suit" in flags:
                SU.build_suit(o, log=log, zb=zb)
            if "--head" in flags:
                # the head (head.py) on the body, groomed (groom.py), its skin and eyes (headlab.py's materials)
                import sdf
                import head as HD
                import headlab as HL
                import groom as GR
                hd = HD.Head()
                lo, hi = hd.bounds()
                lo[2] = max(lo[2], 1.53)
                Vh, Qh = sdf.mesh(hd, lo, hi, float(flags.get("--head_h", .0011)), log=log)
                ho = HL.to_object("head", Vh, Qh)
                ho.data.materials.append(HL.skin_material(False))
                for name, (EV, EF, col) in hd.extras():
                    c = EV.mean(0)
                    e = HL.to_object(name, EV - c, EF, origin=tuple(c))
                    e.data.materials.append(HL.eye_material(name))
                Nh = sdf.normals(hd, Vh)
                mask = GR.groom(Vh, Nh, hd, log=log).astype(np.float32)      # the base model: clean-shaven
                Qhd = GR.to_head(Vh, hd)
                mask = np.maximum(mask, (GR.beard_mask(Qhd, hd, soft=True) * (hd.ear(Qhd) > .6) * .3))   # shaved
                mask = np.maximum(mask, .8 * GR.scalp_shade(Qhd, hd)).astype(np.float32)   # roots shade the scalp
                import headbase as HB                                         # the lips' red part (headlab's)
                lp = HB.lips(Qhd.astype(np.float32), hd.stom_z, hd.k)[0]
                lw = (np.clip(1 - lp / .12, 0, 1) * (np.abs(Qhd[:, 0]) < HB.MOUTH_W + .1)).astype(np.float32)
                la = ho.data.color_attributes.new("lip", 'FLOAT_COLOR', 'POINT')
                la.data.foreach_set("color", np.c_[lw, lw, lw, np.ones_like(lw)].ravel())
                a = ho.data.color_attributes.new("beard", 'FLOAT_COLOR', 'POINT')
                a.data.foreach_set("color", np.c_[mask, mask, mask, np.ones_like(mask)].ravel())
                sc.cycles_curves.shape = 'THICK'
                # the body's skin: the head's, so hands and feet match the face
                skin = ho.data.materials[0]
                o["skin"] = 1
                if "--suit" in flags:                        # the suit's high collar, sewn on at the neckline
                    SU.build_collar(ho, bpy.data.objects["suit"], o, zb, log=log)
    log(f"built in {time.time() - t0:.1f} s")
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = SIZE
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'Standard'
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam); sc.camera = cam
    if "--cage" in flags:
        w = o.modifiers.new("wire", 'WIREFRAME'); w.thickness = .002; w.use_replace = False
    sheet = load_png(SHEET)[..., :3]
    tmp = out.replace(".png", "")
    panels = []
    for view in ("front", "side", "back"):
        sil = render(view, f"{tmp}_{view}_sil.png", True)[..., 0] > .5
        clay = render(view, f"{tmp}_{view}_clay.png", False)[..., :3]
        mask = load_png(os.path.join(HERE, f"concept_mask_{view}.png"))[..., 0] > .5
        sv, sm = sheet_view(view, sheet, mask)
        a = sv.copy(); a[edge(sil)] = (1, .15, .1)
        b = clay.copy(); b[edge(sm)] = (.2, 1, .3)
        # how far apart the outlines are: pixels in one and not the other, as a share of the sheet's
        miss = (sm & ~sil).sum() / max(sm.sum(), 1); extra = (sil & ~sm).sum() / max(sm.sum(), 1)
        log(f"{view}: sheet not covered {miss * 100:.1f} %, body outside the sheet {extra * 100:.1f} %")
        outline_report(view, sil, sm)
        panels += [a, b]
    # crop each panel to the figure's width
    H = SIZE[1]
    strips = []
    for i in range(0, 6, 2):
        a, b = panels[i], panels[i + 1]
        w0, w1 = (60, 940) if i != 2 else (350, 650)
        strips += [a[:, w0:w1], b[:, w0:w1]]
    img = np.concatenate(strips, axis=1)
    hh, ww = img.shape[:2]
    res = bpy.data.images.new("cmp", ww, hh, alpha=False)
    rgba = np.concatenate([img[::-1], np.ones((hh, ww, 1), np.float32)], axis=2)
    res.pixels = rgba.ravel()
    res.filepath_raw = out; res.file_format = 'PNG'; res.save()
    log("wrote", out)
    if "--look" in flags:
        turnaround(sc, out.replace(".png", "_look.png"), int(flags.get("--samples", 64)))
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(flags["--save"]))


if __name__ == "__main__":
    main()
