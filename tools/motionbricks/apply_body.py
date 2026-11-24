"""MotionBricks' generated motion put back onto our body, measured and rendered (trial).

blender -b --factory-startup -P tools/motionbricks/apply_body.py -- <body.glb> <generated.npz> <alignment.npz>
    <our_clips.npz> <out_dir> [--jobs=a,b] [--res=640x480] [--every=1] [--save=x.blend]

For each job of generated.npz (tools/motionbricks/mb_generate.py): SOMA's joints in MotionBricks' runtime space (which
is Blender's: Z up, facing -Y, metres) are turned back onto our bones through the anatomical frames of alignment.npz
(tools/motionbricks/retarget.py); the fingers and our helper bones keep our idle clip's own pose. Baked as an action
on our armature, measured (the planted feet's slide where the model says a heel or a toe is down, the knees' and the
elbows' bend), and rendered beside the body and from in front at three quarters, following it over a floor of metre
squares: <out_dir>/<job>/<view>_<frame>.png, MBMEASURE lines.
"""
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb, gen_path, align_path, clips_path, out = argv[:5]
opts = dict(a[2:].split("=", 1) for a in argv[5:] if a.startswith("--") and "=" in a)
out = Path(out)
W_RES, H_RES = (int(v) for v in opts.get("res", "640x480").split("x"))
EVERY = int(opts.get("every", "1"))

scene = bpy.context.scene
scene.render.fps = 30
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=glb)
for o in list(bpy.data.objects):
    if o.type in ("CAMERA", "LIGHT") or (o.type == "MESH" and o.parent is None) or o.name in ("C_hair__crop", "C_hair__slick"):
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
AW = np.array(arm.matrix_world)
AWi = np.linalg.inv(AW)

gen = np.load(gen_path)
al = np.load(align_path)
clips = np.load(clips_path)
B2S = al["B2S"]
soma_names = list(gen["names"])
soma_par = gen["parents"]
our = list(al["our_bones"])
rest_w = al["our_rest"]                                    # world rest matrices (dump_body)
rest_a = np.einsum("ab,jbc->jac", AWi, rest_w)             # armature space
pairs = [tuple(p) for p in al["pairs"]]
Lo, Ls = al["Lo"], al["Ls"]
hips_scale = 1.0
# (retarget.py put SOMA's hips at our hips x SOMA's hip height / ours: the ratio, from SOMA's reference and our rest)
soma_hips_ref = al["soma_offsets"][list(al["soma_names"]).index("Hips")][1]
hips_scale = soma_hips_ref / (rest_w[our.index("hips"), 2, 3] * 100.0)

bone_par = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
order = [b.name for b in arm.data.bones]                   # (parents come before their children)
rest_rel = {}
for n in order:
    p = bone_par[n]
    rest_rel[n] = rest_a[our.index(n)] if p is None else np.linalg.inv(rest_a[our.index(p)]) @ rest_a[our.index(n)]
# our idle clip's own local pose for what MotionBricks says nothing about (fingers, helper bones)
idle = np.einsum("ab,jbc->jac", AWi, clips["clip_Idle"][0])
idle_basis = {}
for n in order:
    p = bone_par[n]
    world_p = np.eye(4) if p is None else idle[our.index(p)]
    idle_basis[n] = np.linalg.inv(rest_rel[n]) @ np.linalg.inv(world_p) @ idle[our.index(n)]


def qmat(q):
    x, y, z, w = np.moveaxis(q, -1, 0)
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def soma_globals(seq):
    """local transforms [F, J, 7] -> global rotations [F, J, 3, 3], positions [F, J, 3] (runtime = Blender world)"""
    F, J = seq.shape[:2]
    R = qmat(seq[..., 3:])
    G = np.zeros((F, J, 3, 3))
    P = np.zeros((F, J, 3))
    for j in range(J):
        p = soma_par[j]
        if p < 0:
            G[:, j], P[:, j] = R[:, j], seq[:, j, :3]
        else:
            G[:, j] = G[:, p] @ R[:, j]
            P[:, j] = P[:, p] + np.einsum("fab,fb->fa", G[:, p], seq[:, j, :3])
    return G, P


def solve(job):
    """our bones' world matrices [F, B, 4, 4] (Blender world) for a job, before any clean-up"""
    seq = gen[job + "__seq"]
    F = len(seq)
    G, P = soma_globals(seq)
    world = np.zeros((F, len(our), 4, 4))
    rot = {}
    for k, (sj, ob) in enumerate(pairs):
        Gs = np.einsum("ab,fbc->fac", B2S, G[:, soma_names.index(sj)])          # SOMA's own space
        Go = Gs @ Ls[k] @ Lo[k].T                                                # our bone, conjugated as retarget.py
        rot[ob] = np.einsum("ba,fbc,cd->fad", B2S, Go, B2S)                      # Blender world
    hips = P[:, soma_names.index("Hips")] / hips_scale
    for f in range(F):
        for n in order:
            j = our.index(n)
            p = bone_par[n]
            wp_ = AW if p is None else world[f, our.index(p)]
            if n in rot:
                m = np.eye(4)
                m[:3, :3] = rot[n][f]
                m[:3, 3] = hips[f] if n == "hips" else (wp_ @ rest_rel[n])[:3, 3]
                world[f, j] = m
            else:
                world[f, j] = wp_ @ rest_rel[n] @ idle_basis[n]
    return F, world


def lock_feet(job, world):
    """the feet held where they were put down while the model says the heel or the toe is down (a, b: the generated
    part), the leg bent to reach (two bones, the knee kept in its own plane), eased in and out over three frames"""
    a, b = (int(v) for v in gen[job + "__gen"])
    contacts = gen[job + "__contacts"]
    F = len(world)
    for side, cols in (("L", (0, 1)), ("R", (2, 3))):
        th, sh, ft = (our.index(n + "." + side) for n in ("thigh", "shin", "foot"))
        down = np.zeros(F, bool)
        for k in range(a, min(b + 1, a + len(contacts))):
            down[k] = max(contacts[k - a][cols[0]], contacts[k - a][cols[1]]) > 0.5
        k = 0
        while k < F:
            if not down[k]:
                k += 1
                continue
            e = k
            while e + 1 < F and down[e + 1]:
                e += 1
            anchor = world[k, ft, :3, 3].copy()
            for f in range(max(a, k - 3), min(b, e + 3) + 1):
                w = 1.0 if k <= f <= e else (1.0 - min(abs(f - k), abs(f - e)) / 4.0)
                w = w * w * (3.0 - 2.0 * w)
                hip = world[f, th, :3, 3]
                knee0 = world[f, sh, :3, 3]
                ank0 = world[f, ft, :3, 3]
                want = ank0.copy()
                want[:2] = ank0[:2] + (anchor[:2] - ank0[:2]) * w
                l1 = np.linalg.norm(knee0 - hip)
                l2 = np.linalg.norm(ank0 - knee0)
                d = want - hip
                dist = np.clip(np.linalg.norm(d), 1e-4, (l1 + l2) * 0.999)
                d = d / np.linalg.norm(d)
                pole = (knee0 - hip) - d * np.dot(knee0 - hip, d)
                pole = pole / max(np.linalg.norm(pole), 1e-6)
                x = (l1 * l1 - l2 * l2 + dist * dist) / (2.0 * dist)
                knee = hip + d * x + pole * np.sqrt(max(l1 * l1 - x * x, 0.0))
                ankle = hip + d * dist

                def aim(m, frm, to):
                    old = m[:3, 1] / np.linalg.norm(m[:3, 1])
                    new = (to - frm) / np.linalg.norm(to - frm)
                    ax = np.cross(old, new)
                    sn, cs = np.linalg.norm(ax), np.dot(old, new)
                    if sn < 1e-8:
                        return m
                    ax = ax / sn
                    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
                    R = np.eye(3) + sn * K + (1 - cs) * K @ K
                    out_ = m.copy()
                    out_[:3, :3] = R @ m[:3, :3]
                    return out_

                world[f, th] = aim(world[f, th], hip, knee)
                world[f, sh] = aim(world[f, sh], knee, ankle)
                world[f, sh, :3, 3] = knee
                world[f, ft, :3, 3] = ankle
            k = e + 1
    return world


def bake(job, world):
    F = len(world)
    act = bpy.data.actions.new("MB_" + job)
    arm.animation_data_create()
    arm.animation_data.action = act
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    A = np.einsum("ab,fjbc->fjac", AWi, world)
    for f in range(F):
        for n in order:
            p = bone_par[n]
            wp_ = np.eye(4) if p is None else A[f, our.index(p)]
            basis = np.linalg.inv(rest_rel[n]) @ np.linalg.inv(wp_) @ A[f, our.index(n)]
            pb = arm.pose.bones[n]
            pb.matrix_basis = Matrix(basis.tolist())
            pb.keyframe_insert("location", frame=f + 1)
            pb.keyframe_insert("rotation_quaternion", frame=f + 1)


def measure(job, world, label=""):
    """the planted feet's slide, the knees' and elbows' bend, over the generated part"""
    a, b = (int(v) for v in gen[job + "__gen"])
    contacts = gen[job + "__contacts"]
    out_lines = []
    slide = []
    for side, (ci_heel, ci_toe) in (("L", (0, 1)), ("R", (2, 3))):
        foot = world[:, our.index("foot." + side)]
        heel = foot[:, :3, 3]
        toe = heel + foot[:, :3, 1] * 0.14
        for which, pts, ci in (("heel", heel, ci_heel), ("toe", toe, ci_toe)):
            for k in range(a + 1, b + 1):
                c = contacts[k - a] if k - a < len(contacts) else 0.0
                c = c[ci] if np.ndim(c) else 0.0
                if c > 0.5:
                    v = np.linalg.norm((pts[k] - pts[k - 1])[:2]) * 30.0 * 100.0     # cm/s
                    slide.append(v)
    slide = np.array(slide) if slide else np.zeros(1)

    def angle(u, v):
        u = u / np.linalg.norm(u, axis=-1, keepdims=True)
        v = v / np.linalg.norm(v, axis=-1, keepdims=True)
        return np.degrees(np.arccos(np.clip(np.sum(u * v, -1), -1, 1)))

    knees = np.concatenate([angle(world[a:b + 1, our.index("thigh." + s), :3, 1], world[a:b + 1, our.index("shin." + s), :3, 1]) for s in "LR"])
    elbows = np.concatenate([angle(world[a:b + 1, our.index("upperarm." + s), :3, 1], world[a:b + 1, our.index("forearm." + s), :3, 1]) for s in "LR"])
    print(f"MBMEASURE {job}{label}: generated frames {a}-{b}; planted feet slide {np.median(slide):.1f} cm/s median, "
          f"{np.percentile(slide, 95):.1f} at the 95th, {slide.max():.1f} at most ({len(slide)} planted samples); knees bend "
          f"{knees.min():.0f}-{knees.max():.0f} deg, elbows {elbows.min():.0f}-{elbows.max():.0f} deg; took "
          f"{float(gen[job + '__took']) * 1000:.1f} ms")


def stage():
    # a floor of metre squares, a sun, a camera
    img = bpy.data.images.new("mb_checker", 512, 512)
    px = np.zeros((512, 512, 4), np.float32)
    yy, xx = np.mgrid[0:512, 0:512]
    sq = ((xx // 64 + yy // 64) % 2).astype(np.float32)
    px[..., 0] = px[..., 1] = px[..., 2] = 0.55 + 0.2 * sq
    px[..., 3] = 1.0
    img.pixels = px.ravel()
    mat = bpy.data.materials.new("mb_floor")
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bpy.ops.mesh.primitive_plane_add(size=64.0, location=(0, 0, 0))
    floor = bpy.context.object
    floor.data.materials.append(mat)
    for loop in floor.data.loops:
        v = floor.data.vertices[loop.vertex_index].co
        floor.data.uv_layers.active.data[loop.index].uv = (v.x / 8.0, v.y / 8.0)
    cam_data = bpy.data.cameras.new("mb_cam")
    cam_data.lens = 35
    cam = bpy.data.objects.new("mb_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.show_cavity = True
    scene.display.shadow_focus = 0.9
    scene.render.resolution_x, scene.render.resolution_y = W_RES, H_RES
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    return cam


def look(cam, at, frm):
    cam.location = Vector(frm)
    d = Vector(at) - Vector(frm)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


cam = stage()
jobs = [j for j in opts.get("jobs", "").split(",") if j] or list(gen["jobs"])
for job in jobs:
    F, world = solve(job)
    measure(job, world, " as generated")
    if opts.get("lock", "1") != "0":
        world = lock_feet(job, world)
        measure(job, world, " feet held")
    bake(job, world)
    hips = world[:, our.index("hips"), :3, 3]
    smooth = np.array([hips[max(0, k - 6):k + 7].mean(0) for k in range(F)])
    (out / job).mkdir(parents=True, exist_ok=True)
    for f in range(0, F, EVERY):
        scene.frame_set(f + 1)
        c = smooth[f]
        at = (c[0], c[1], 0.9)
        for view, off in (("side", (3.6, 0.0, 0.55)), ("front", (2.4, -3.0, 0.6))):
            look(cam, at, (c[0] + off[0], c[1] + off[1], 0.9 + off[2]))
            scene.render.filepath = str(out / job / f"{view}_{f:03d}.png")
            bpy.ops.render.render(write_still=True)
    print(f"MBRENDER {job}: {F} frames")
if "save" in opts:
    bpy.ops.wm.save_as_mainfile(filepath=opts["save"])
