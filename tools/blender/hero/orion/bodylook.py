"""the lab's body in clay under the head lab's studio light, close on each part (a sheet of named views):
blender -b x.blend -P bodylook.py -- out.png [--views=a,b,c] [--suit] [--samples=48]
  --suit: keep the suit objects (C_suit__orion with its baked maps, or the lab's suit) and the eyes; else clay only"""
import bpy, math, os, sys
import numpy as np
from mathutils import Vector
sys.path.insert(0, "C:/Dev/World-ex/tools/blender"); sys.path.insert(0, "C:/Dev/World-ex/tools/blender/hero/orion")
import headlab as HL
argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
VIEWS = {  # name: (target (x, y, z), yaw deg (0 = from in front), pitch, distance, lens mm)
    "torso": ((0, 0, 1.28), 0, 0, 1.6, 60), "torso_q": ((0, 0, 1.28), 40, 0, 1.6, 60),
    "back": ((0, 0, 1.28), 180, 0, 1.6, 60), "back_q": ((0, 0, 1.28), 140, 0, 1.6, 60),
    "arm": ((0.46, -0.03, 1.45), 0, 35, 1.35, 50), "arm_b": ((0.46, -0.03, 1.45), 180, 35, 1.35, 50),
    "shoulder": ((0.22, -0.03, 1.47), 25, 15, 0.9, 60), "knee": ((0.15, -0.05, 0.52), 20, 10, 0.6, 60),
    "thigh": ((0.15, -0.08, 0.76), 15, 10, 0.85, 60), "chest": ((0.08, -0.09, 1.42), 20, 10, 0.65, 60),
    "neck": ((0, -0.03, 1.58), 35, 5, 0.7, 85), "hip": ((0.14, -0.06, 1.02), 40, 5, 0.8, 60),
    "legs": ((0, 0, 0.52), 0, 0, 2.0, 60), "legs_s": ((0, 0, 0.52), 90, 0, 2.0, 60),
    "legs_b": ((0, 0, 0.52), 180, 0, 2.0, 60), "head": ((0, -0.02, 1.70), 0, 0, 0.75, 85),
    "head_q": ((0, -0.02, 1.70), 40, 0, 0.75, 85), "head_s": ((0, -0.02, 1.70), 90, 0, 0.75, 85),
    "feet": ((0, -0.05, 0.08), 30, -30, 0.9, 60), "hand": ((0.80, -0.01, 1.40), 20, 55, 0.5, 60),
    "full": ((0, 0, 0.95), 25, 0, 4.2, 50), "full_b": ((0, 0, 0.95), 160, 0, 4.2, 50),
    "arm_f": ((0.50, -0.03, 1.45), 0, 0, 1.3, 50), "arm_t": ((0.50, -0.03, 1.45), 0, 88, 1.3, 50),
    "arm_u": ((0.50, -0.03, 1.45), 0, -60, 1.3, 50), "arm_q": ((0.50, -0.03, 1.45), 55, 20, 1.3, 50),
    "arm_bq": ((0.50, -0.03, 1.45), 125, 20, 1.3, 50), "arm_e": ((0.50, -0.03, 1.45), 85, 10, 1.6, 50),
    "elbow": ((0.49, -0.03, 1.45), 20, 30, 0.6, 60), "wrist": ((0.76, -0.03, 1.42), 20, 40, 0.5, 60),
}
views = flags.get("--views", "torso,torso_q,back,arm,legs,legs_b,head,head_q").split(",")
sc = bpy.context.scene
keep = ("B_eyes", "B_hair", "B_lashes", "C_suit", "suit", "collar", "eye_") if "--suit" in flags else ("B_eyes", "B_hair", "B_lashes", "eye_")
body = next((o for o in sc.objects if o.type == 'MESH' and "region" in o.data.attributes and not o.name.startswith(("B_", "C_"))), None)
if body is None:
    body = next(o for o in sc.objects if o.type == 'MESH' and o.name.startswith("B_chest"))
for ob in list(sc.objects):
    if ob.type in ('LIGHT', 'CAMERA', 'CURVES') or (ob.type == 'MESH' and ob is not body and not ob.name.startswith(keep)
                                                    and not (body.name.startswith("B_") and ob.name.startswith("B_"))):
        bpy.data.objects.remove(ob, do_unlink=True)
clay = bpy.data.materials.new("clay"); clay.use_nodes = True
b = clay.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (.30, .28, .265, 1); b.inputs["Roughness"].default_value = .55
for ob in sc.objects:
    if ob.type == 'MESH' and (ob is body or ob.name.startswith("B_")) and not ob.name.startswith(("B_eyes", "B_hair", "B_lashes")):
        if ob.data.shape_keys:
            for kb in ob.data.shape_keys.key_blocks:
                kb.value = 0
        ob.data.materials.clear(); ob.data.materials.append(clay)
        for p in ob.data.polygons:
            p.use_smooth = True
    if ob.type == 'MESH' and ob.name in ("suit", "collar") and "--suit" in flags:
        pass
sc.render.engine = 'CYCLES'
HL.gpu(sc)
sc.cycles.samples = int(flags.get("--samples", 48))
sc.cycles.use_denoising = True
try:
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Base Contrast'
except Exception:
    pass
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (.18, .18, .21, 1); bg.inputs[1].default_value = .25
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.clip_start = .01
sc.render.resolution_x, sc.render.resolution_y = 720, 900
lights = []


def light(name, energy, size):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.size = size
    ob = bpy.data.objects.new(name, L); sc.collection.objects.link(ob); lights.append(ob); return ob


key, fill, rim = light("key", 1.0, 1.2), light("fill", 1.0, 2.0), light("rim", 1.0, 1.0)


def place(ob, T, pos, energy):
    ob.location = pos; ob.data.energy = energy
    ob.rotation_euler = (Vector(T) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()


def rot(d, deg):
    a = math.radians(deg); c, s_ = math.cos(a), math.sin(a)
    return Vector((d.x * c - d.y * s_, d.x * s_ + d.y * c, d.z))
shots = []
for name in views:
    T, yaw, pitch, dist, lens = VIEWS[name]
    T = Vector(T)
    cam.data.lens = lens
    y, p = math.radians(yaw), math.radians(pitch)
    d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
    cam.location = T + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    # the lights follow the view: a key from the camera's left and above, a soft fill from its right, a rim behind
    dh = Vector((d.x, d.y, 0)).normalized()
    place(key, T, T + rot(dh, 62) * 2.0 + Vector((0, 0, .9)), 120 * dist / 1.25)
    place(fill, T, T + rot(dh, -50) * 2.4 + Vector((0, 0, .3)), 22 * dist / 1.25)
    place(rim, T, T - rot(dh, 30) * 2.0 + Vector((0, 0, 1.6)), 90 * dist / 1.25)
    f = out.replace(".png", f"_{name}.png"); sc.render.filepath = f
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(f); W, Hh = im.size
    shots.append(np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)); bpy.data.images.remove(im)
sheet = np.concatenate(shots, 1)
img = bpy.data.images.new("s", sheet.shape[1], sheet.shape[0], alpha=True); img.pixels = sheet.ravel()
img.filepath_raw = out; img.file_format = 'PNG'; img.save()
print("[bodylook]", out)
