"""Close-ups of a saved build (lab.py --save=x.blend): a part from several sides, in clay.

blender -b <build.blend> -P tools/blender/hero/orion/closeup.py -- <out.png> --part=hand|foot|head|torso [--res=700]
"""
import bpy, math, os, sys
import numpy as np
from mathutils import Vector

PARTS = {   # target, distance, views (yaw, pitch)
    "hand": ((0.80, -0.03, 1.42), .42, [(0, 75), (0, 0), (60, 15), (180, -60), (-40, 10)]),
    "foot": ((0.205, -0.03, 0.06), .55, [(0, 10), (60, 15), (90, 5), (200, 10)]),
    "head": ((0.0, -0.06, 1.72), .75, [(0, 0), (35, 0), (90, 0)]),
    "torso": ((0.0, -0.03, 1.25), 1.6, [(0, 0), (35, 0), (90, 0), (180, 0)]),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    part = str(flags.get("--part", "hand"))
    res = int(flags.get("--res", 700))
    sc = bpy.context.scene
    tgt, dist, views = PARTS[part]
    tgt = Vector(tgt)
    cam = sc.camera
    cam.data.type = 'PERSP'
    cam.data.lens = 85
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.cycles.samples = int(flags.get("--samples", 48))
    files = []
    for i, (yaw, pitch) in enumerate(views):
        y, p = math.radians(yaw), math.radians(pitch)
        d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
        cam.location = tgt + d * dist
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        f = out.replace(".png", f"_{i}.png")
        sc.render.filepath = f
        bpy.ops.render.render(write_still=True)
        files.append(f)
    imgs = []
    for f in files:
        im = bpy.data.images.load(f)
        W, H = im.size
        imgs.append(np.array(im.pixels[:], np.float32).reshape(H, W, 4))
    sheet = np.concatenate(imgs, axis=1)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0], alpha=True)
    img.pixels = sheet.ravel()
    img.filepath_raw = out; img.file_format = 'PNG'; img.save()
    print("[closeup]", out, flush=True)


if __name__ == "__main__":
    main()
