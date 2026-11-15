"""Rebuilds single wardrobe pieces on a saved hero build, without rebuilding the body: for working on one garment.

blender -b <saved.blend> -P tools/blender/hero/repiece.py -- male|female [--pieces=top,outer] [--look=dir]
        [--without=outer,vest] [--glb=out.glb] [--save=out.blend]

  <saved.blend>   a rigged, dressed build (build.py -- <sex> --glb=... --save=<saved.blend>)
  --pieces        which to build again (top, legs, feet, hands, hands_armoured, vest, outer): the old object goes, the
                  new one is skinned to the body and finished (finish.py) exactly as in a full build (wardrobe.dress)
  --look          renders the dressed body from the front, the side, the back and three quarters into this folder,
                  with the body's hidden regions really hidden as in the game (so a piece that hides more than it
                  covers shows as a hole): look before importing
  --without       pieces taken off for the look (the jacket and the rig are optional or often off: a top must be
                  whole without them)
  --glb / --save  as reclip.py: the clips are baked again from <sex>/motion.py, then the game's GLB / the blend written
"""
import bpy, json, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import targets, rig as rig_mod


def log(*a):
    print("[repiece]", *a)


def rest(arm):
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()


def rebuild(names, body, arm, T):
    import wardrobe, finish
    makers = {"top": (wardrobe.top, {}), "legs": (wardrobe.legs, {}), "feet": (wardrobe.feet, {}), "hands": (wardrobe.hands, {}),
              "hands_armoured": (wardrobe.hands, {"armoured": True}), "vest": (wardrobe.vest, {}), "outer": (wardrobe.outer, {})}
    info = wardrobe.BodyInfo(body, T)
    made = []
    for name in names:
        fn, kw = makers[name]
        piece = fn(info, **kw)
        made.append(piece)
    info.free()
    for piece in made:
        # the piece it replaces (Blender gave the new one a .001 name while the old one was still there)
        base = piece.name.split(".")[0]
        for old in [o for o in bpy.data.objects if o is not piece and o.name.split(".")[0] == base]:
            bpy.data.objects.remove(old, do_unlink=True)
        piece.name = base
        wardrobe.skin_like_body(piece, body, arm)
        finish.apply(piece, T, log=log)
        log(f"{piece.name}: rebuilt, {len(piece.data.polygons)} faces")
    return made


def look(out, body, arm, without, T):
    """the body as the game shows it: what the worn pieces hide is gone"""
    os.makedirs(out, exist_ok=True)
    meta = json.loads(arm.get("worldex", "{}"))
    wardrobe, defaults = meta.get("wardrobe", {}), dict(meta.get("defaults", {}))
    for slot in without:
        defaults.pop(slot, None)
    worn = {f"C_{slot}__{item}" for slot, item in defaults.items()}
    hidden = set()
    for slot, item in defaults.items():
        hidden.update(wardrobe.get(slot, {}).get(item, {}).get("hide", []))
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith("C_"):
            o.hide_render = o.name.split(".")[0] not in worn
    # a copy of the body without the hidden regions' faces
    shown = body.copy()
    shown.data = body.data.copy()
    bpy.context.scene.collection.objects.link(shown)
    body.hide_render = True
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(shown.data)
    names = [s.material.name if s.material else "" for s in shown.material_slots]
    drop = [f for f in bm.faces if names[f.material_index].replace("skin__", "") in hidden]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.to_mesh(shown.data)
    bm.free()
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.show_backface_culling = False
    sc.render.resolution_x, sc.render.resolution_y = 700, 900
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.world.color = (.30, .32, .40)                      # (a hole shows as this colour, not as a dark shadow)
    cam = bpy.data.objects.new("LookCam", bpy.data.cameras.new("LookCam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = T["height"] * .62
    mid = T["height"] * .70                                # the trunk
    for view, yaw in (("front", 0), ("side", 90), ("back", 180), ("quarter", 40), ("quarter_back", 140)):
        y = math.radians(yaw)
        d = Vector((math.sin(y), -math.cos(y), 0))
        cam.location = d * 6 + Vector((0, 0, mid))
        cam.rotation_euler = (math.radians(90), 0, math.atan2(d.x, -d.y))
        sc.render.filepath = os.path.join(out, f"look_{view}.png")
        bpy.ops.render.render(write_still=True)
    log(f"looked: {sorted(worn)} worn, {sorted(hidden)} hidden -> {out}")
    bpy.data.objects.remove(shown, do_unlink=True)
    body.hide_render = False
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith("C_"):
            o.hide_render = False


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    sex = argv[0]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    T = targets.SEXES[sex]
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = bpy.data.objects["B_body"]
    bpy.context.view_layer.objects.active = arm
    for o in bpy.data.objects:
        o.select_set(False)
    rest(arm)
    if isinstance(flags.get("--pieces"), str):
        rebuild([p for p in flags["--pieces"].split(",") if p], body, arm, T)
    if isinstance(flags.get("--look"), str):
        rest(arm)
        look(flags["--look"], body, arm, flags["--without"].split(",") if isinstance(flags.get("--without"), str) else [], T)
    if isinstance(flags.get("--save"), str) or isinstance(flags.get("--glb"), str):
        import wardrobe
        rig_mod.animate(arm, T, sex, log)                 # the clips again from <sex>/motion.py (as reclip.py)
        arm.animation_data.action = bpy.data.actions["Idle"]
        for o in bpy.data.objects:
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
