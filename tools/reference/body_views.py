"""Whole-body reference views (measure only; Epic's meshes stay in a scratch folder, never in the project).

blender -b -P body_views.py -- <ref_dir> <out_dir> [glb_dir]
  ref_dir: the FBX exported by export_epic_reference.py (MH_SKM_Body.fbx, MH_SM_MH_Head.fbx, SKM_Manny_Simple.fbx,
           SKM_Quinn_Simple.fbx); out_dir gets one clay render per subject and view (true scale, feet on the floor,
           orthographic, the same camera for every subject) for body_sheet.py to grid and overlay.
"""
import bpy, sys, math, os
import numpy as np
from mathutils import Matrix, Vector

a = sys.argv[sys.argv.index('--') + 1:]
REF, OUT = a[0], a[1]
GLB = a[2] if len(a) > 2 else "C:/Dev/World-ex/assets/models"
os.makedirs(OUT, exist_ok=True)
VIEWS = {'front': 0.0, 'side': 90.0, 'back': 180.0}
RES = (900, 1100)
ORTHO = 2.05          # metres across the frame height


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def clay(objs):
    m = bpy.data.materials.new('clay'); m.diffuse_color = (.8, .78, .75, 1)
    for o in objs:
        o.data.materials.clear(); o.data.materials.append(m)


def flatten(objs):
    """Bake world transforms into the meshes (rest pose: armature modifiers removed, shape keys at 0)."""
    for o in objs:
        if o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = 0.0
        for md in list(o.modifiers):
            o.modifiers.remove(md)
        mw = o.matrix_world.copy(); o.parent = None; o.data.transform(mw); o.matrix_world = Matrix.Identity(4)
        o.rotation_mode = 'XYZ'


def render(name, objs, front_is_neg_y=True):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_cavity = True
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = RES
    cam = bpy.data.objects.get('cam') or bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ORTHO * RES[0] / RES[1] if RES[0] > RES[1] else ORTHO
    cam.data.sensor_fit = 'VERTICAL'; cam.data.ortho_scale = ORTHO
    for view, yaw in VIEWS.items():
        y = math.radians(yaw)
        d = Vector((math.sin(y), -math.cos(y), 0))           # camera direction from the subject (front = -Y)
        cam.location = d * 6 + Vector((0, 0, ORTHO / 2 - .02))
        cam.rotation_euler = (math.radians(90), 0, math.atan2(d.x, -d.y))
        sc.render.filepath = os.path.join(OUT, f"{name}_{view}.png")
        bpy.ops.render.render(write_still=True)


def fbx(*files):
    before = set(bpy.data.objects)
    for f in files:
        bpy.ops.import_scene.fbx(filepath=os.path.join(REF, f))
    return [o for o in bpy.data.objects if o not in before and o.type == 'MESH']


def lod0(objs):
    keep = [o for o in objs if 'LOD' not in o.name or 'LOD0' in o.name]
    for o in objs:
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    return keep


# Epic: MetaHuman archetype body + template head (male), Manny, Quinn
clear(); objs = lod0(fbx("MH_SKM_Body.fbx", "MH_SM_MH_Head.fbx")); flatten(objs); clay(objs); render("epic_metahuman", objs)
clear(); objs = lod0(fbx("SKM_Manny_Simple.fbx")); flatten(objs); clay(objs); render("epic_manny", objs)
clear(); objs = lod0(fbx("SKM_Quinn_Simple.fbx")); flatten(objs); clay(objs); render("epic_quinn", objs)
# ours: the base body only (B_* regions), rest pose
for sex in ("male", "female"):
    clear()
    bpy.ops.import_scene.gltf(filepath=os.path.join(GLB, f"player_{sex}.glb"))
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.split('.')[0].startswith('B_')]
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and o not in objs]:
        bpy.data.objects.remove(o, do_unlink=True)
    flatten(objs); clay(objs); render(f"ours_{sex}", objs)
print("body views done")
