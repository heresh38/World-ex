"""Our hand rendered in a reference picture's own frame (handref.py's json: the wrist crease's centre, the
direction to the middle fingertip, the scale), orthographic, so the two can be laid one over the other (handsheet.py).
blender -b <build.blend> -P handlay.py -- <ref.json> <W> <H> <palm|back> <out_prefix> [--hand=right|left] [--clay]
writes <out>_sil.png (our silhouette's alpha), <out>_clay.png (clay, optional), <out>_joints.json (pixels)"""
import bpy, json, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import body as B
import hand as HM

argv = sys.argv[sys.argv.index("--") + 1:]
ref = json.load(open(argv[0]))
Wpx, Hpx, view, out = int(argv[1]), int(argv[2]), argv[3], os.path.abspath(argv[4])
flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[5:]}
sx = -1 if flags.get("--hand", "right") == "right" else 1
S_, a, up, back = B.arm_axis(sx)
F = HM.Frame(S_ + a * (B.UPPER_ARM + B.FOREARM), a, up, sx)
# the middle finger's tip, the hand's length in the plane of the palm
fing = {f[0]: f for f in HM.FINGERS}
_, kx, ky, L, wd, spread = fing["middle"]
tip = HM.joints_of(F, kx, ky, L, spread)[-1]
AZ = F.az
d = tip - F.W
d = d - AZ * float(d @ AZ)
AX = d / np.linalg.norm(d)
AY = F.ay - AX * float(F.ay @ AX); AY /= np.linalg.norm(AY)
Lours = float(np.linalg.norm(tip - F.W - AZ * float((tip - F.W) @ AZ)))
s = ref["scale_cm_px"] / 100.0 * float(flags.get("--k", 1.0))    # metres per pixel
o = np.array(ref["origin"], float); ex = np.array(ref["ex"], float); ey = np.array(ref["ey"], float)
if "--x0" in flags:
    o = o - np.array([float(flags["--x0"]), 0.0])


def h_of(p):
    q = np.asarray(p, float) - o
    return F.W + AX * float(q @ ex) * s + AY * float(q @ ey) * s


def p_of(h):
    q = np.asarray(h, float) - F.W
    return o + ex * float(q @ AX) / s + ey * float(q @ AY) / s


right = h_of((1, 0)) - h_of((0, 0)); right /= np.linalg.norm(right)
upv = h_of((0, -1)) - h_of((0, 0)); upv /= np.linalg.norm(upv)
zc = np.cross(right, upv)
toward = -AZ if view == "palm" else AZ                            # where the camera stands
if float(zc @ toward) < 0:
    print("[lay] MIRRORED: this hand in this view is the other hand's mirror")
centre = h_of((Wpx / 2, Hpx / 2))
sc = bpy.context.scene
for ob in [ob for ob in sc.objects if ob.type in ('LIGHT', 'CAMERA')]:
    bpy.data.objects.remove(ob, do_unlink=True)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'
cam.data.ortho_scale = max(Wpx, Hpx) * s
cam.data.clip_start = .01; cam.data.clip_end = 2.0
cam.location = Vector(centre + toward * .6)
R = Matrix(((right[0], upv[0], zc[0]), (right[1], upv[1], zc[1]), (right[2], upv[2], zc[2])))
cam.rotation_euler = R.to_euler()
sc.render.resolution_x, sc.render.resolution_y = Wpx, Hpx
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
# the silhouette
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (1, 1, 1)
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.color_mode = 'RGBA'
sc.render.filepath = out + "_sil.png"
bpy.ops.render.render(write_still=True)
if "--clay" in flags:
    clay = bpy.data.materials.new("clayh"); clay.use_nodes = True
    bs = clay.node_tree.nodes["Principled BSDF"]; bs.inputs["Base Color"].default_value = (.62, .55, .50, 1)
    bs.inputs["Roughness"].default_value = .5
    for ob in sc.objects:
        if ob.type == 'MESH':
            ob.data.materials.clear(); ob.data.materials.append(clay)
            for pg in ob.data.polygons:
                pg.use_smooth = True
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 48; sc.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences; prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
        for dv in prefs.devices:
            dv.use = dv.type == 'OPTIX'
        sc.cycles.device = 'GPU'
    except Exception:
        pass
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (.05, .05, .06, 1)

    def light(name, energy, loc, size):
        Ld = bpy.data.lights.new(name, 'AREA'); Ld.energy = energy; Ld.size = size
        ob = bpy.data.objects.new(name, Ld); ob.location = Vector(loc)
        ob.rotation_euler = (Vector(centre) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(ob)
    light("key", 30, centre + toward * .5 + upv * .25 - right * .2, .6)
    light("fill", 10, centre + toward * .4 - upv * .2 + right * .35, 1.0)
    sc.render.filepath = out + "_clay.png"
    bpy.ops.render.render(write_still=True)
J = {}
for name, kx_, ky_, L_, wd_, sp_ in HM.FINGERS:
    J[name] = [p_of(p).round(1).tolist() for p in HM.joints_of(F, kx_, ky_, L_, sp_)]
J["thumb"] = [p_of(p).round(1).tolist() for p in HM.thumb_joints(F)]
J["wrist"] = p_of(F.W).round(1).tolist()
json.dump(dict(joints=J, length_cm=Lours * 100), open(out + "_joints.json", "w"), indent=1)
print(f"[lay] {view}: ours {Lours * 100:.2f} cm wrist -> middle tip; px {s * 1000:.4f} mm")
