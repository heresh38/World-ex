"""Our new male (Project Orion) beside Epic's references, part by part, in the same clay, light and lens (measure
only: Epic's meshes are read from a scratch folder outside the repo and never saved into the project).

blender -b <lab build.blend> -P tools/reference/orion_compare.py -- <ref_dir> <out.png> --part=foot|hand|body|head
    [--res=520] [--samples=32] [--norm] [--refs=manny,mh]

ref_dir holds export_epic_reference.py's FBX (SKM_Manny_Simple.fbx, MH_SKM_Body.fbx, MH_SM_MH_Head.fbx). Each subject
is moved into the part's own frame first (the foot: the ankle joint, heading toward the ball; the hand: the wrist,
along the middle finger's metacarpal, the back of the hand up), so the same camera sees the same side of every one.
Rows: Manny, the MetaHuman body (the template, not ours to copy), ours. --norm scales each reference to our part's
size (the shapes compared, not the sizes).
"""
import bpy, math, os, sys
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
REF, OUT = argv[0], os.path.abspath(argv[1])
FL = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[2:]}
PART = str(FL.get("--part", "foot"))
RES = int(FL.get("--res", 520))
SAMPLES = int(FL.get("--samples", 32))
REFS = str(FL.get("--refs", "manny,mh")).split(",")
HERE = os.path.dirname(os.path.abspath(__file__))
ORION = os.path.join(HERE, "..", "blender", "hero", "orion")
sys.path.insert(0, os.path.join(ORION, ".."))           # hero/ (sdf.py) after orion/: hero has its own anatomy.py
sys.path.insert(0, ORION)

# views per part: (yaw, pitch) in the part's frame (yaw 0 = from the front of the foot / the thumb's side of the hand)
VIEWS = {
    "foot": [(0, 12), (40, 25), (90, 4), (-90, 4), (180, 10), (0, 88), (0, -80)],
    "hand": [(0, 88), (0, -88), (0, 8), (180, 8), (90, 20), (-50, 30)],
    "body": [(0, 0), (90, 0), (180, 0), (35, 0)],
    "head": [(0, 0), (35, 0), (90, 0), (150, 0)],
    "knee": [(0, 0), (45, 0), (90, 0), (180, 0)],
}
DIST = {"foot": .78, "hand": .62, "body": 6.5, "head": 1.05, "knee": 1.25}


def unit(v):
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


def frame_matrix(origin, fwd, up):
    """world -> part frame: origin to 0, fwd to -Y, up to +Z (the body's own convention)"""
    f = unit(fwd)
    u = unit(np.asarray(up, float) - f * float(np.dot(up, f)))
    r = np.cross(u, f)                     # the frame's +X (a left limb's outside when it faces -Y): x = y cross z
    R = np.array([r, -f, u])               # rows: world -> (x, y, z), a rotation
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = -R @ np.asarray(origin, float)
    return Matrix(M.tolist())


def mesh_world(o):
    n = len(o.data.vertices)
    co = np.zeros(n * 3); o.data.vertices.foreach_get("co", co)
    M = np.array(o.matrix_world)
    return co.reshape(n, 3) @ M[:3, :3].T + M[:3, 3]


def flatten(o):
    if o.data.shape_keys:
        for kb in o.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
    for md in list(o.modifiers):
        o.modifiers.remove(md)
    mw = o.matrix_world.copy()
    o.parent = None
    o.data.transform(mw)
    o.matrix_world = Matrix.Identity(4)


def import_ref(files):
    before = set(bpy.data.objects)
    for f in files:
        p = os.path.join(REF, f)
        if os.path.exists(p):
            bpy.ops.import_scene.fbx(filepath=p)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next((o for o in new if o.type == 'ARMATURE'), None)
    bones = {}
    if arm:
        for b in arm.data.bones:
            bones[b.name] = np.array(arm.matrix_world @ b.head_local)
    meshes = [o for o in new if o.type == 'MESH' and ('LOD' not in o.name or 'LOD0' in o.name)]
    for o in new:
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    for o in meshes:
        flatten(o)
    return meshes, bones


def our_frames():
    """our joints (the anatomy's skeleton and the foot's and hand's own frames)"""
    import anatomy as AN
    import foot as FT
    a = AN.A_DIR
    W = AN.S + a * (AN.UPPER_ARM + AN.FOREARM)
    hand_fwd = np.array(a, float)
    back = np.array(AN.A_UP, float)
    t = math.radians(FT.TOE_OUT)
    fwd = np.array([math.sin(t), -math.cos(t), 0.0])
    return dict(foot=(np.array(AN.A, float), fwd, np.array([0, 0, 1.0])),
                hand=(np.array(W, float), hand_fwd, back),
                knee=(np.array(AN.K, float), np.array([0, -1.0, 0]), np.array([0, 0, 1.0])))


def epic_frames(b):
    fr = {}
    if "foot_l" in b and "ball_l" in b:
        f = b["ball_l"] - b["foot_l"]; f[2] = 0
        fr["foot"] = (b["foot_l"], f, np.array([0, 0, 1.0]))
    if "hand_l" in b and "middle_01_l" in b:
        ax = unit(b["middle_01_l"] - b["hand_l"])
        ay = b["index_01_l"] - b["pinky_01_l"]
        ay = unit(ay - ax * float(ay @ ax))
        az = np.cross(ay, ax)                                    # the back of the hand
        # our frame: fwd = the hand's axis, up = the back of the hand; the thumb then lands at -Y like ours
        fr["hand"] = (b["hand_l"], ax, az)
    if "calf_l" in b:
        fr["knee"] = (b["calf_l"], np.array([0, -1.0, 0]), np.array([0, 0, 1.0]))
    return fr


def part_size(P, part):
    if part == "foot":
        m = (P[:, 2] < .14 * 1.0) & (np.abs(P[:, 0]) < .12) & (P[:, 1] > -.35) & (P[:, 1] < .25)
        q = P[m]
        return float(q[:, 1].max() - q[:, 1].min()) if len(q) else 1.0
    if part == "hand":
        m = (np.abs(P[:, 1]) < .09) & (np.abs(P[:, 2]) < .08) & (P[:, 0] > -.02) & (P[:, 0] < .30)
        q = P[m]
        return float(q[:, 0].max()) if len(q) else 1.0
    return 1.0


def to_frame(objs, fr, part, hand_mirror=False):
    """moves the subject's meshes into the part's frame; for the hand the frame's -Y is the hand's axis: turn it to
    +X like our arm (the camera's views are written for that)"""
    M = frame_matrix(*fr)
    if part == "hand":
        # in the frame the hand runs to -Y with the thumb at -X: turn it so it runs to +X, the thumb at -Y (our arm)
        M = Matrix(((0, -1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))) @ M
    for o in objs:
        o.data.transform(M)
        o.data.update()
    crop(objs, part)


def crop(objs, part):
    """only the part and a little of the limb it hangs from (an A-posed hand hangs by the thigh)"""
    import bmesh
    for o in objs:
        bm = bmesh.new(); bm.from_mesh(o.data)
        if part == "hand":
            bad = [v for v in bm.verts if v.co.x < -.08 or (v.co - Vector((.1, 0, 0))).length > .19]
        elif part == "foot":
            bad = [v for v in bm.verts if v.co.z > .26 or abs(v.co.x) > .16 or not (-.32 < v.co.y < .2)]
        elif part == "knee":
            bad = [v for v in bm.verts if abs(v.co.x) > .2 or abs(v.co.z) > .3]
        else:
            bad = []
        bmesh.ops.delete(bm, geom=bad, context='VERTS')
        bm.to_mesh(o.data); bm.free()


def clay_and_lights(sc):
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
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new("cmp_w"); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (.20, .20, .23, 1); bg.inputs[1].default_value = .15
    mat = bpy.data.materials.new("cmp_clay"); mat.use_nodes = True
    bs = mat.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (.36, .34, .32, 1); bs.inputs["Roughness"].default_value = .5
    return mat


def place_lights(sc, tgt, cam_dir, dist):
    for o in [o for o in sc.objects if o.type == 'LIGHT']:
        bpy.data.objects.remove(o, do_unlink=True)
    up = Vector((0, 0, 1))
    side = cam_dir.cross(up)
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    u2 = side.cross(cam_dir).normalized()

    def light(name, energy, d, size):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy * (dist / 3.0) ** 2; L.size = size * dist / 3.0
        ob = bpy.data.objects.new(name, L); ob.location = tgt + d.normalized() * dist * 1.2
        ob.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(ob)
    light("k", 300, cam_dir + side * .9 + u2 * .9, 2.2)
    light("f", 90, cam_dir - side * 1.1 + u2 * .2, 2.6)
    light("r", 260, -cam_dir - side * .6 + u2 * .8, 1.8)


def render_rows(rows, part, out):
    sc = bpy.context.scene
    mat = clay_and_lights(sc)
    cam = bpy.data.objects.new("cmp_cam", bpy.data.cameras.new("cmp_cam"))
    sc.collection.objects.link(cam); sc.camera = cam
    sc.render.resolution_x = sc.render.resolution_y = RES
    if part == "body":
        sc.render.resolution_x = int(RES * .55)
    for name, objs in rows:
        for o in objs:
            o.data.materials.clear(); o.data.materials.append(mat)
            for p in o.data.polygons:
                p.use_smooth = True
    views = VIEWS[part]
    dist = DIST[part]
    # the target: the part's middle in its frame
    tgt = {"foot": Vector((0, -.06, .035)), "hand": Vector((.095, -.01, 0)), "body": Vector((0, 0, .92)),
           "head": Vector((0, -.02, 1.70)), "knee": Vector((0, 0, 0))}[part]
    if part == "body":
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.0
    else:
        cam.data.type = 'PERSP'; cam.data.lens = 85
    cam.data.clip_start = .01
    allobjs = [o for _, objs in rows for o in objs]
    grid = []
    for name, objs in rows:
        for o in allobjs:
            o.hide_render = o not in objs
        row = []
        for i, (yaw, pitch) in enumerate(views):
            y, p = math.radians(yaw), math.radians(pitch)
            d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
            cam.location = tgt + d * dist
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            place_lights(sc, tgt, d, dist)
            f = out.replace(".png", f"_{name}_{i}.png")
            sc.render.filepath = f
            bpy.ops.render.render(write_still=True)
            im = bpy.data.images.load(f, check_existing=False)
            W, H = im.size
            row.append(np.array(im.pixels[:], np.float32).reshape(H, W, 4))
            bpy.data.images.remove(im)
            os.remove(f)
        grid.append(np.concatenate(row, axis=1))
    sheet = np.concatenate(grid[::-1], axis=0)               # pixels are bottom-up: the first row on top
    img = bpy.data.images.new("cmp_sheet", sheet.shape[1], sheet.shape[0], alpha=True)
    img.pixels = sheet.ravel()
    img.filepath_raw = out; img.file_format = 'PNG'; img.save()
    print("[compare]", out, "rows:", ", ".join(n for n, _ in rows), flush=True)


def main():
    sc = bpy.context.scene
    keep = {"orion_male"}
    if PART == "head":
        keep |= {"head", "eye_L", "eye_R"}
    if PART == "body":
        keep |= {"head", "eye_L", "eye_R"}
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    ours = [bpy.data.objects[n] for n in keep if n in bpy.data.objects]
    for o in ours:
        flatten(o)
    rows = []
    ofr = our_frames()
    our_size = 1.0
    if PART in ofr:
        to_frame(ours, ofr[PART], PART)
        our_size = part_size(np.concatenate([mesh_world(o) for o in ours]), PART)
    print(f"[compare] ours: {PART} size {our_size:.4f} m", flush=True)
    for ref in REFS:
        files = {"manny": ["SKM_Manny_Simple.fbx"], "mh": ["MH_SKM_Body.fbx"] + (["MH_SM_MH_Head.fbx"] if PART in ("head", "body") else [])}[ref]
        objs, bones = import_ref(files)
        if not objs:
            continue
        if PART in ("foot", "hand", "knee"):
            fr = epic_frames(bones).get(PART)
            if fr is None:
                continue
            to_frame(objs, fr, PART)
            s = part_size(np.concatenate([mesh_world(o) for o in objs]), PART)
            print(f"[compare] {ref}: {PART} size {s:.4f} m", flush=True)
            if "--norm" in FL and s > 0:
                k = our_size / s
                for o in objs:
                    o.data.transform(Matrix.Scale(k, 4))
                print(f"[compare] {ref} scaled x{k:.3f}", flush=True)
        rows.append((ref, objs))
    rows.append(("ours", ours))
    render_rows(rows, PART, OUT)


main()
