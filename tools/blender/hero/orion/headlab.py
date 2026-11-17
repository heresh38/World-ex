"""The head lab: the new head (head.py) meshed finely and rendered from the views a sculptor checks, in clay or in
skin with its eyes, beside the owner's portrait from the same side.

blender -b -P tools/blender/hero/orion/headlab.py -- <out.png> [--h=0.0007] [--views=portrait,front,q,side]
                                                     [--clay] [--samples=96] [--res=800] [--save=x.blend]

  portrait   the owner's portrait's own view (turned to his left, from a touch below), beside it
  front / q / side / back / low
The sheet is the views side by side; each view is also written as <out>_<view>.png.
"""
import bpy, math, os, sys, time
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import sdf  # noqa: E402
import head as H  # noqa: E402

SHEET = os.path.join(ROOT, "art", "reference", "player", "orion_tpose_bodysuit.png")
PORTRAIT = (1200, 0, 1536, 500)                     # the portrait's box on the sheet


def log(*a):
    print("[headlab]", *a, flush=True)


def gpu(sc):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = 'GPU'
                return kind
    except Exception as e:
        log("no graphics card:", e)
    sc.cycles.device = 'CPU'
    return "CPU"


def to_object(name, V, F, origin=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [list(f) for f in F])
    me.update()
    o = bpy.data.objects.new(name, me)
    o.location = origin
    bpy.context.scene.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = True
    return o


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def skin_material(clay=False):
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if clay:
        b.inputs["Base Color"].default_value = (.30, .28, .265, 1)
        b.inputs["Roughness"].default_value = .55
        return m
    # warm olive skin, deeper red where the blood is close (cheeks, nose, lips, ears), the beard's shadow
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    noise = node(nt, "ShaderNodeTexNoise", Scale=900.0, Detail=6.0, Roughness=.6)
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    pores = node(nt, "ShaderNodeTexVoronoi", Scale=2600.0)
    nt.links.new(tc.outputs["Object"], pores.inputs["Vector"])
    base = node(nt, "ShaderNodeRGB")
    base.outputs[0].default_value = (.50, .325, .235, 1)
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    nt.links.new(base.outputs[0], mix.inputs[6])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (.86, .80, .78, 1)
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs[0], mix.inputs[7])
    mix.inputs[0].default_value = 1.0
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Subsurface Weight"].default_value = .35
    b.inputs["Subsurface Radius"].default_value = (.012, .005, .0028)
    b.inputs["Subsurface Scale"].default_value = 1.0
    b.inputs["Roughness"].default_value = .48
    b.inputs["Specular IOR Level"].default_value = .42
    bump = node(nt, "ShaderNodeBump", Strength=.10, Distance=.0004)
    nt.links.new(pores.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def eye_material(name):
    """sclera, a grey-blue iris with its fibres and dark limbal ring, the pupil; a clear wet coat over it"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    vlen = nt.nodes.new("ShaderNodeVectorMath"); vlen.operation = 'NORMALIZE'
    nt.links.new(tc.outputs["Object"], vlen.inputs[0])
    sep2 = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(vlen.outputs[0], sep2.inputs[0])
    neg = nt.nodes.new("ShaderNodeMath")
    neg.operation = 'MULTIPLY'
    nt.links.new(sep2.outputs["Y"], neg.inputs[0]); neg.inputs[1].default_value = -1.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(neg.outputs[0], ramp.inputs["Fac"])
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (.72, .64, .60, 1)
    el[1].position = 1.0; el[1].color = (.004, .004, .005, 1)
    for pos, col in ((.70, (.80, .76, .72, 1)), (.835, (.84, .80, .76, 1)), (.842, (.05, .06, .07, 1)),
                     (.86, (.20, .27, .32, 1)), (.93, (.30, .38, .43, 1)), (.955, (.22, .26, .27, 1)),
                     (.962, (.006, .006, .007, 1))):
        e = el.new(pos); e.color = col
    nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = .05
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = .02
    return m


def studio(sc):
    sc.render.engine = 'CYCLES'
    gpu(sc)
    sc.cycles.use_denoising = True
    w = bpy.data.worlds.new("w"); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (.17, .17, .20, 1); bg.inputs[1].default_value = .35
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    target = Vector((0, H.Y0 - .06, H.Z0 - .02))

    def light(name, energy, loc, color, size):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.color = color; L.size = size
        o = bpy.data.objects.new(name, L); o.location = loc
        o.rotation_euler = (target - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(o)
    # the portrait's light: a broad key high on his left, a soft fill, a cool rim behind
    light("key", 24, (.55, -.85, 2.15), (1, .95, .9), .9)
    light("fill", 5, (-.85, -.55, 1.80), (.8, .87, 1), 1.4)
    light("rim", 20, (-.35, .75, 2.05), (.85, .92, 1), .6)
    light("under", 1.2, (0, -.6, 1.35), (1, .92, .85), 1.0)


VIEWS = {  # yaw (degrees, positive = from his left), pitch, distance, lens
    "portrait": (-27, -4, .78, 85), "front": (0, 0, .70, 85), "q": (35, 0, .70, 85), "side": (90, 0, .70, 85),
    "back": (180, 0, .70, 85), "low": (25, -20, .70, 85), "qr": (-35, 0, .70, 85),
    "close": (-20, -3, .40, 85), "under": (10, -45, .55, 85),
}


def camera(sc, view):
    cam = sc.camera
    yaw, pitch, dist, lens = VIEWS[view]
    target = Vector((0, H.Y0 - .055, H.Z0 - .035))
    y, p = math.radians(yaw), math.radians(pitch)
    d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
    cam.location = target + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def profile_check(sc, out):
    """the head's outline from the side and the front against the sheet's (the sheet's rows put through the canon's
    landmarks as the body's are; its widths at the sheet's scale): <out>_profile.png, the head in white, the sheet's
    outline in green"""
    import body as B
    MPP = .0005
    views = {"side": (Vector((1, 0, 0)), (-.12, .22), "side", B.SIDE_C, -1),
             "front": (Vector((0, 1, 0)), (-.13, .13), "front", B.FRONT_C, 1)}
    z0, z1 = 1.47, 1.89
    panels = []
    for name, (d, (h0, h1), view, c0, sgn) in views.items():
        W, Hh = int((h1 - h0) / MPP), int((z1 - z0) / MPP)
        sc.render.resolution_x, sc.render.resolution_y = W, Hh
        sc.render.engine = 'BLENDER_WORKBENCH'
        sh = sc.display.shading
        sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (1, 1, 1)
        sh.background_type = 'VIEWPORT'; sh.background_color = (0, 0, 0)
        cam = sc.camera
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = max(W, Hh) * MPP
        # the image's right is +x (front view) / -y (side view); its centre at the window's middle
        hc = .5 * (h0 + h1)
        centre = Vector((hc, 0, 0)) if name == "front" else Vector((0, -hc, 0))
        cam.location = centre + Vector((0, 0, .5 * (z0 + z1))) - d * 3
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        path = out.replace(".png", f"_sil_{name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(path)
        sil = np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)[::-1][..., 0] > .5
        im = bpy.data.images.load(os.path.join(HERE, f"concept_mask_{view}.png"))
        mw, mh = im.size
        mask = np.array(im.pixels[:], np.float32).reshape(mh, mw, 4)[::-1][..., 0] > .5
        zs = z1 - (np.arange(Hh) + .5) * MPP
        hs = h0 + (np.arange(W) + .5) * MPP
        rows = np.array([B.Concept.row(z) for z in zs])
        cols = c0 + hs / B.CPX if name == "front" else c0 + hs / B.CPX
        R = np.clip(np.round(rows).astype(int), 0, mh - 1)[:, None]
        C = np.clip(np.round(cols).astype(int), 0, mw - 1)[None, :]
        cm = mask[R, C]
        img = np.zeros((Hh, W, 3), np.float32)
        img[sil] = (.75, .75, .75)
        e = np.zeros_like(cm)
        e[1:] |= cm[1:] != cm[:-1]; e[:, 1:] |= cm[:, 1:] != cm[:, :-1]
        img[e] = (.1, 1, .3)
        panels.append(img)
        # the profile's numbers: per centimetre of height, where the head's front is and the sheet's (side view)
        if name == "side":
            lines = []
            for z in np.arange(1.50, 1.86, .01):
                r = int((z1 - z) / MPP)
                a = np.nonzero(sil[r])[0]; b = np.nonzero(cm[r])[0]
                if len(a) and len(b):
                    lines.append(f"z {z:.2f} (head {(z - H.Z0) * 100:+.1f}): front {hs[a[-1]] * 100:+.1f} vs "
                                 f"{hs[b[-1]] * 100:+.1f} cm ({(hs[a[-1]] - hs[b[-1]]) * 100:+.1f})")
            open(out.replace(".png", "_profile.txt"), "w").write("\n".join(lines))
    Hh = max(p.shape[0] for p in panels)
    sheet = np.concatenate([np.pad(p, ((0, Hh - p.shape[0]), (0, 4), (0, 0))) for p in panels], axis=1)
    img = bpy.data.images.new("prof", sheet.shape[1], sheet.shape[0], alpha=False)
    img.pixels = np.concatenate([sheet[::-1], np.ones(sheet.shape[:2] + (1,), np.float32)], 2).ravel()
    img.filepath_raw = out.replace(".png", "_profile.png"); img.file_format = 'PNG'; img.save()
    log("profile", out.replace(".png", "_profile.png"))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    h = float(flags.get("--h", .0007))
    views = [v for v in str(flags.get("--views", "portrait,front,q,side")).split(",") if v in VIEWS]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    head = H.Head()
    t0 = time.time()
    lo, hi = head.bounds()
    V, Q = sdf.mesh(head, lo, hi, h, log=log)
    log(f"meshed in {time.time() - t0:.1f} s: {len(V)} verts")
    o = to_object("head", V, Q)
    o.data.materials.append(skin_material("--clay" in flags))
    for name, (EV, EF, col) in head.extras():
        c = EV.mean(0)
        e = to_object(name, EV - c, EF, origin=tuple(c))
        e.data.materials.append(eye_material(name))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_start = .01
    if "--profile" in flags:
        profile_check(sc, out)
        cam.data.type = 'PERSP'
    studio(sc)
    sc.cycles.samples = int(flags.get("--samples", 96))
    res = int(flags.get("--res", 800))
    files = []
    for v in views:
        sc.render.resolution_x = int(res * (.672 if v == "portrait" else 1.0))
        sc.render.resolution_y = res
        camera(sc, v)
        sc.render.filepath = out.replace(".png", f"_{v}.png")
        bpy.ops.render.render(write_still=True)
        files.append(sc.render.filepath)
        log("rendered", v)
    # the sheet: the owner's portrait first when the portrait view was asked for
    imgs = []
    if "portrait" in views:
        im = bpy.data.images.load(SHEET)
        W, Hh = im.size
        a = np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)[::-1]
        x0, y0, x1, y1 = PORTRAIT
        crop = a[y0:y1, x0:x1]
        # nearest-neighbour up to the render's height
        ys = (np.arange(res) * (y1 - y0) / res).astype(int)
        xs = (np.arange(int(res * .672)) * (x1 - x0) / (res * .672)).astype(int)
        imgs.append(crop[ys][:, xs])
    if not views:
        return
    for f in files:
        im = bpy.data.images.load(f)
        W, Hh = im.size
        imgs.append(np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)[::-1])
    Hh = max(i.shape[0] for i in imgs)
    sheet = np.concatenate([np.pad(i, ((0, Hh - i.shape[0]), (0, 0), (0, 0))) for i in imgs], axis=1)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0], alpha=True)
    img.pixels = sheet[::-1].ravel()
    img.filepath_raw = out; img.file_format = 'PNG'; img.save()
    log("sheet", out)
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(str(flags["--save"])))


if __name__ == "__main__":
    main()
