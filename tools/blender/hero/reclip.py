"""Re-bakes a hero body's clips on a saved build, without rebuilding the body: for working on motion.

blender -b <saved.blend> -P tools/blender/hero/reclip.py -- male|female [--glb=out.glb] [--save=out.blend]
        [--frames=dir --clips=Walk,Run --n=8 --views=side,front]

  <saved.blend>   a rigged, dressed build (build.py -- <sex> --glb=... --save=<saved.blend>)
  --glb           write the game's GLB again (the same file build.py writes: SourceArt/Characters/src/hero_<sex>.glb)
  --save          save the blend with the new clips
  --frames        render --n frames of each of --clips (default: all) from each of --views into this folder
                  (<clip>_<view>_<i>.png, workbench, orthographic): a quick look at the motion

The clips come from <sex>/motion.py through gait.py exactly as in a full build (rig.animate).
"""
import bpy, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import targets, rig as rig_mod


def log(*a):
    print("[reclip]", *a)


def frames(arm, out, clips, n, views, height):
    sc = bpy.context.scene
    os.makedirs(out, exist_ok=True)
    for o in bpy.data.objects:                       # only what the body wears by default (no helmet over the head)
        base = o.name.split(".")[0]
        if base.startswith("C_head__") or base == "C_hands__orion_armoured":
            o.hide_render = True
    cam = bpy.data.objects.new("ClipCam", bpy.data.cameras.new("ClipCam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = height * 1.5
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_shadows = True
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 420, 620
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("W")
    floor = bpy.data.objects.new("ClipFloor", bpy.data.meshes.new("ClipFloor"))
    floor.data.from_pydata([(-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)], [], [(0, 1, 2, 3)])
    sc.collection.objects.link(floor)
    yaws = {"side": 90, "front": 0, "back": 180, "quarter": 40, "top": None}
    for name in clips:
        act = bpy.data.actions.get(name)
        if not act:
            log(f"no clip {name}")
            continue
        arm.animation_data.action = act
        f0, f1 = act.frame_range
        for view in views:
            for i in range(n):
                sc.frame_set(int(round(f0 + (f1 - f0) * i / n)))
                hips = arm.matrix_world @ arm.pose.bones["hips"].head
                c = Vector((0, hips.y * .0, height * .5))
                if yaws[view] is None:
                    cam.location = c + Vector((0, 0, 6))
                    cam.rotation_euler = (0, 0, 0)
                else:
                    y = math.radians(yaws[view])
                    d = Vector((math.sin(y), -math.cos(y), 0))
                    cam.location = c + d * 6
                    cam.rotation_euler = (math.radians(90), 0, math.atan2(d.x, -d.y))
                sc.render.filepath = os.path.join(out, f"{name}_{view}_{i:02d}.png")
                bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    bpy.data.objects.remove(floor)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    sex = argv[0]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    T = targets.SEXES[sex]
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    bpy.context.view_layer.objects.active = arm
    for o in bpy.data.objects:
        o.select_set(False)
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    made = rig_mod.animate(arm, T, sex, log)
    arm.animation_data.action = bpy.data.actions["Idle"]
    if isinstance(flags.get("--frames"), str):
        names = flags["--clips"].split(",") if isinstance(flags.get("--clips"), str) else [a.name for a, _ in made]
        views = flags["--views"].split(",") if isinstance(flags.get("--views"), str) else ["side"]
        frames(arm, flags["--frames"], names, int(flags.get("--n", 8)), views, T["height"])
        arm.animation_data.action = bpy.data.actions["Idle"]
    if isinstance(flags.get("--save"), str) or isinstance(flags.get("--glb"), str):
        import wardrobe
        for o in bpy.data.objects:                   # (a build saved before the pieces were checked: see fill_unweighted)
            if o.type == "MESH" and o.vertex_groups:
                n = wardrobe.fill_unweighted(o)
                if n:
                    log(f"{o.name}: {n} unweighted vertices filled")
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=flags["--save"])
    if isinstance(flags.get("--glb"), str):
        rig_mod.write_glb(flags["--glb"])
        log(f"wrote {flags['--glb']}")


if __name__ == "__main__":
    main()
