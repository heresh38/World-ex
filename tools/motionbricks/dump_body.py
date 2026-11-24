"""Our body's skeleton and clips, sampled for retargeting (MotionBricks trial).

blender -b --factory-startup -P tools/motionbricks/dump_body.py -- <body.glb> <out.npz> [--clips=Idle,Walk,...] [--fps=30]

Writes, in Blender's world frame (Z up, the body facing -Y): every bone's name and parent, its rest matrix in world space,
and for each clip every bone's world matrix at each frame (fps frames a second), plus the clip's name. Nothing of the
body is changed.
"""
import sys, json
import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
src, out = argv[0], argv[1]
opts = dict(a[2:].split("=", 1) for a in argv[2:] if a.startswith("--") and "=" in a)
fps = int(opts.get("fps", 30))
want = [c for c in opts.get("clips", "").split(",") if c]

scene = bpy.context.scene
scene.render.fps = fps
scene.render.fps_base = 1.0
bpy.ops.import_scene.gltf(filepath=src)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
bones = [b.name for b in arm.data.bones]
parents = [arm.data.bones[n].parent.name if arm.data.bones[n].parent else "" for n in bones]
W = arm.matrix_world
rest = np.array([np.array(W @ arm.data.bones[n].matrix_local) for n in bones], dtype=np.float32)

actions = sorted(a.name for a in bpy.data.actions)
print("ACTIONS", actions)
data = {"bones": np.array(bones), "parents": np.array(parents), "rest": rest, "fps": np.array(fps)}
if arm.animation_data is None:
    arm.animation_data_create()
names = []
for a in bpy.data.actions:
    # (the glTF importer names an action <clip>_<armature> or <clip>; take the clip's own name)
    clip = a.name.split("|")[-1]
    for suffix in ("_" + arm.name, "." + arm.name):
        clip = clip.replace(suffix, "")
    if want and clip not in want:
        continue
    arm.animation_data.action = a
    if hasattr(arm.animation_data, "action_slot") and a.slots:
        arm.animation_data.action_slot = a.slots[0]
    f0, f1 = (int(round(v)) for v in a.frame_range)
    frames = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        frames.append([np.array(W @ arm.pose.bones[n].matrix) for n in bones])
    data["clip_" + clip] = np.array(frames, dtype=np.float32)
    names.append(clip)
    print("CLIP", clip, f1 - f0 + 1, "frames")
data["clips"] = np.array(names)
np.savez_compressed(out, **data)
print("BONES", json.dumps(list(zip(bones, parents))))
