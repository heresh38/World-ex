"""Both naked base characters in one organised project file (after basemesh.py has built each):

blender --background --python tools/blender/hero/basemesh_project.py [-- --out=dir] [--norender]

Collections: Male_Base_Body, Male_Head, Male_Eyes, Male_Hair, Male_Skeleton, Female_Base_Body, Female_Head, Female_Eyes,
Female_Hair, Female_Skeleton, Materials, Reference, Export (the body LODs), Render_Rig. The female stands 1.6 m to
the male's left. Materials carry the sex in front of their name here (the per-sex files keep the game's names).
"""
import os, sys, math
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv}
out = flags.get("--out") if isinstance(flags.get("--out"), str) else os.path.join(
    ROOT, "unreal", "ShatteredOrbit", "SourceArt", "Characters", "OrionBase")

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
shared = {}
for sex in ("male", "female"):
    S = sex.capitalize()
    path = os.path.join(out, sex, f"Orion{S}_Base.blend")
    before_m = set(bpy.data.materials); before_o = set(bpy.data.objects)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c != "Render_Rig"]
    for c in dst.collections:
        base = c.name.split(".")[0]
        if base in ("Materials", "Reference", "Export"):
            if base in shared and shared[base] is not c:
                for o in list(c.objects):
                    c.objects.unlink(o); shared[base].objects.link(o)
                bpy.data.collections.remove(c)
                continue
            shared[base] = c
            c.name = base
        if c.name not in sc.collection.children:
            sc.collection.children.link(c)
    for m in set(bpy.data.materials) - before_m:
        m.name = f"{S}_{m.name.split('.')[0]}"
    for o in set(bpy.data.objects) - before_o:
        if o.name.startswith(("MAT_", "REF_")):
            o.name = f"{o.name.split('.')[0]}" if sex == "male" else f"{o.name.split('.')[0]}_{S}"
    if sex == "female":
        arm = bpy.data.objects.get("SKEL_OrionFemale")
        arm.location.x = 1.6
        for o in set(bpy.data.objects) - before_o:
            if o.name.startswith("MAT_"):
                o.location.z -= .25
            if o.name.startswith("REF_height"):
                o.location.x = 1.6
# put the shared collections last, in a fixed order
for nm in ("Materials", "Reference", "Export"):
    c = bpy.data.collections.get(nm)
    if c:
        sc.collection.children.unlink(c); sc.collection.children.link(c)
for a in bpy.data.objects:
    if a.type == 'ARMATURE':
        a.data.pose_position = 'REST'

if "--norender" not in flags:
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 48
    try:
        sc.cycles.use_denoising = True
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    sc.view_settings.exposure = -.9
    w = bpy.data.worlds.new("studio"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (.055, .058, .065, 1)
    rigc = bpy.data.collections.new("Render_Rig"); sc.collection.children.link(rigc)
    H = 1.84
    for nm, loc, e, colr, size in (("key", (2.6, -3.2, H + .6), 900, (1, .96, .90), 2.2), ("fill", (-2.6, -2.4, H * .6), 200, (.82, .88, 1), 2.6),
                                   ("rim", (-1.6, 2.8, H + .7), 800, (.95, .97, 1), 1.6), ("rim2", (3.0, 2.4, H * .5), 300, (1, .95, .9), 1.6)):
        ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.color = colr; ld.size = size
        lo = bpy.data.objects.new("LIGHT_" + nm, ld); lo.location = loc
        lo.rotation_euler = (Vector((.8, 0, H * .6)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
        rigc.objects.link(lo)
    cam = bpy.data.objects.new("CAM", bpy.data.cameras.new("CAM")); rigc.objects.link(cam); sc.camera = cam
    cam.data.lens = 85; cam.data.sensor_fit = 'VERTICAL'
    sc.render.resolution_x, sc.render.resolution_y = 2600, 1500
    os.makedirs(os.path.join(out, "renders"), exist_ok=True)
    c = Vector((.8, 0, H * .5))
    for name, yaw in (("front", 0), ("q", 32), ("back", 180)):
        yw = math.radians(yaw)
        d = Vector((math.sin(yw), -math.cos(yw), .03))
        dist = H * 1.1 / 2 / math.tan(math.atan(cam.data.sensor_height / 2 / cam.data.lens))
        cam.location = c + d * dist
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(out, "renders", f"Orion_Base_lineup_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("[project] rendered", name, flush=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "Orion_Base_Characters.blend"), relative_remap=True)
print("[project] collections:", [c.name for c in sc.collection.children])
print("[project] saved", os.path.join(out, "Orion_Base_Characters.blend"))
