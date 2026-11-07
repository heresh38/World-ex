"""Body cross-sections (width, depth, approximate girth) at landmark heights, for ours and Epic's references.
blender -b -P body_measure.py -- <ref_dir> <out.json> [glb_dir]"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Matrix

a = sys.argv[sys.argv.index('--') + 1:]
REF, OUT = a[0], a[1]
GLB = a[2] if len(a) > 2 else "C:/Dev/World-ex/assets/models"


def pts(objs):
    P = []
    for o in objs:
        if o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = 0
        P.append(np.array([tuple(o.matrix_world @ v.co) for v in o.data.vertices]))
    return np.concatenate(P)


def girth(w, d):
    a, b = w / 2, d / 2
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))


def section(P, z, xlim, xc=0.0):
    band = P[np.abs(P[:, 2] - z) < .006]
    band = band[np.abs(band[:, 0] - xc) < xlim]
    if len(band) < 10:
        return None
    w = band[:, 0].max() - band[:, 0].min(); d = band[:, 1].max() - band[:, 1].min()
    return dict(w=round(w * 100, 1), d=round(d * 100, 1), girth=round(girth(w, d) * 100, 1),
                front=round(band[:, 1].min() * 100, 1), back=round(band[:, 1].max() * 100, 1))


def measure(P):
    H = P[:, 2].max()
    r = {"height": round(H * 100, 1)}
    # torso sections (arms excluded by a width limit that grows with the shoulders)
    for name, f, lim in (("chest", .72, .17), ("underbust", .68, .16), ("waist", .615, .16), ("hips", .51, .2)):
        r[name] = section(P, H * f, lim)
    # limbs (left side, +X): thigh just under the crotch, calf, upper arm (arm hangs: take points far out at mid arm)
    r["thigh"] = section(P, H * .43, .16, xc=.1)
    r["calf"] = section(P, H * .2, .1, xc=.1)
    zarm = H * .71
    band = P[np.abs(P[:, 2] - zarm) < .006]
    arm = band[band[:, 0] > band[:, 0].max() - .13]
    if len(arm):
        xs = np.sort(arm[:, 0]); gaps = np.diff(xs); cut = xs[np.argmax(gaps) + 1] if len(gaps) and gaps.max() > .01 else xs.min()
        arm = arm[arm[:, 0] >= cut]
        w = arm[:, 0].max() - arm[:, 0].min(); d = arm[:, 1].max() - arm[:, 1].min()
        r["upper_arm"] = dict(w=round(w * 100, 1), d=round(d * 100, 1), girth=round(girth(w, d) * 100, 1))
    r["shoulder_width"] = round(float(np.ptp(P[np.abs(P[:, 2] - H * .8) < .01][:, 0])) * 100, 1)
    return r


out = {}
for key, files in (("manny", ["SKM_Manny_Simple.fbx"]), ("quinn", ["SKM_Quinn_Simple.fbx"]), ("metahuman_body", ["MH_SKM_Body.fbx", "MH_SM_MH_Head.fbx"])):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for f in files:
        bpy.ops.import_scene.fbx(filepath=os.path.join(REF, f))
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and ('LOD' not in o.name or 'LOD0' in o.name)]
    out[key] = measure(pts(objs))
for sex in ("male", "female"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(GLB, f"player_{sex}.glb"))
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.split('.')[0].startswith('B_')]
    out["ours_" + sex] = measure(pts(objs))
json.dump(out, open(OUT, "w"), indent=1)
print("measured")
