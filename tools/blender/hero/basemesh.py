"""The naked base characters as a production asset (the same bodies the game builds, without the outfit).

blender --background --python tools/blender/hero/basemesh.py -- male|female [--out=dir] [--nokeys] [--stage=a.blend]
        [--from=a.blend] [--size=4096] [--norender] [--renderonly --views=front,back]

  1 body     the cage fitted to the anatomical target (build.py's steps), the face keys, the eyeballs and sockets
  2 rig      skeleton with fingers and clavicles, heat weights, skin__<region> sections, brows and lashes (rig.py)
  3 hair     this body's hair cards and cap (hair.py), skinned like the body
  4 uv       seams (the back of the head and trunk, the inside of each limb, round each hand and sole), unwrap, pack
  5 textures position / normal / occlusion baked, then our own skin maps written from them (skinmaps.py)
  6 project  collections <Sex>_Base_Body / _Head / _Eyes / _Hair / _Skeleton, Materials, Reference, Export; LODs
  7 export   FBX for Unreal (body + eyes + brows + hair on the skeleton, one file per LOD), the .blend, the renders

--stage saves after step 3 (the slow part); --from starts from such a file.
Nothing the game builds is touched: the output goes to SourceArt/Characters/OrionBase/<sex> (or --out).
"""
import os, sys, math, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import bpy, bmesh
import numpy as np
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
T0 = time.time()


def log(*a):
    print("[base %5.0fs]" % (time.time() - T0), *a, flush=True)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["male"]
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    return argv[0], flags


# ---------------------------------------------------------------------------------------------- 1-3 body, rig, hair
def build_body(sex, T, keys=True):
    import build as B, shape as shape_mod, fit as fit_mod, headfit, rig as rig_mod
    bpy.ops.wm.read_factory_settings(use_empty=True)
    c = B.build_cage(T)
    B.check(c.bm, f"{sex} cage")
    body = shape_mod.Body(T)
    placed = headfit.place_head(c, body, T, log=log)
    placed = B.mirror_topology(c, placed)
    c.bm.verts.index_update()
    hold = [v.index for v in placed if v.is_valid] + [v.index for v in c.bm.verts
                                                      if c.part_of.get(v) in ("finger", "thumb", "toe") and v not in placed]
    o = fit_mod.cage_object(c, f"hero_{sex}")
    fit_mod.fit(o, body, T, relax=3, log=lambda *a: log("cage", *a), hold=hold)
    fit_mod.subdivide(o, 2)
    fit_mod.fit(o, body, T, relax=16, log=log, per_part=False)
    if keys:
        fit_mod.face_keys(o, shape_mod.Body, T, log=log)
    eyes = fit_mod.eyeballs(body, T, f"hero_{sex}")
    fit_mod.eye_sockets(o, eyes, log=log)
    arm = rig_mod.rig(o, eyes, T, sex, log=log)
    # the hair (wardrobe's own builder), on the rest pose
    import wardrobe, hair as hair_mod
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    info = wardrobe.BodyInfo(o, T)
    h = hair_mod.build(info, T, hair_mod.tex_dir(T), log=log)
    info.free()
    wardrobe.skin_like_body(h, o, arm)
    log(f"hair: {h.name} {len(h.data.polygons)} faces")
    bm = bmesh.new(); bm.from_mesh(o.data)
    B.check(bm, f"{sex} mesh"); bm.free()
    return o, arm


def main():
    sex, flags = args()
    import targets
    T = targets.SEXES[sex]
    out = flags.get("--out") if isinstance(flags.get("--out"), str) else os.path.join(
        ROOT, "unreal", "ShatteredOrbit", "SourceArt", "Characters", "OrionBase", sex)
    os.makedirs(out, exist_ok=True)
    os.environ["HERO_TEX"] = os.path.join(out, "tex_src")           # (hair.py's textures: this asset's own copies)
    if "--renderonly" in flags:
        bpy.ops.wm.open_mainfile(filepath=os.path.join(out, f"Orion{sex.capitalize()}_Base.blend"))
        import basemesh_finish
        basemesh_finish.render_only(sex, T, out, flags, log)
        return
    if isinstance(flags.get("--from"), str):
        bpy.ops.wm.open_mainfile(filepath=flags["--from"])
        log("opened", flags["--from"])
    else:
        build_body(sex, T, keys="--nokeys" not in flags)
        if isinstance(flags.get("--stage"), str):
            bpy.ops.wm.save_as_mainfile(filepath=flags["--stage"])
            log("stage saved", flags["--stage"])
    if "--stageonly" in flags:
        return
    import basemesh_finish
    basemesh_finish.finish(sex, T, out, flags, log)


if __name__ == "__main__":
    main()
