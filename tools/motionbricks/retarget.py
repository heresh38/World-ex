"""Our body's clips onto the SOMA skeleton MotionBricks knows, and back (trial).

python tools/motionbricks/retarget.py <our_clips.npz> <soma_skeleton.npz> <out_dir> [--clips=Idle,Walk,...] [--cycles=6]

Our clips (tools/motionbricks/dump_body.py: Blender's world, metres, Z up, the body facing -Y) become SOMA BVH files
(cm, Y up, facing +Z, left +X) that MotionBricks loads like its own clips, and `alignment.npz` holds what turns SOMA's
motion back onto our bones (tools/motionbricks/apply_body.py).

SOMA's skeleton is MotionBricks' own rig file (soma_base_skel_minimal_no_root.usd, Apache 2.0; dumped by
mb_generate.py --dump-skeleton: names, parents, reference local transforms, a T-pose), never a sample clip (those are
for evaluation only). How a bone is carried across: each skeleton's bone gets an ANATOMICAL frame in its own reference
pose (along the bone, and the body's forward laid square to it; for a foot and a thumb, up): ours in its rest and
SOMA's in its reference, both T-poses. Its frame in the bone's own axes is then fixed (L), so a pose of ours, G_ours, is SOMA's
G_soma = G_ours L_ours L_soma^T, and back G_ours = G_soma L_soma L_ours^T: the two reference poses need not match and
no bone's own axes have to agree. SOMA's joints between ours (Spine2, Neck2) are the mean of what their neighbours
say; the ones we have nothing for (fingers, jaw, eyes, toes) keep the reference frame's own turn on their parent.
Our clips are made in place: a clip that walks gets its root moved on at the speed its planted feet move back.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import somabvh as sb  # noqa: E402

# Blender (x, y, z) -> SOMA BVH (x, z, -y): left stays +X, up Z -> Y, forward -Y -> +Z
B2S = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])

# SOMA joint <- our bone, and the second direction of its anatomical frame (the body's forward, or up for a foot)
PAIRS = [
    ("Hips", "hips", "fwd"), ("Spine1", "spine", "fwd"), ("Chest", "chest", "fwd"),
    ("Neck1", "neck", "fwd"), ("Head", "head", "fwd"),
    ("LeftShoulder", "clavicle.L", "fwd"), ("LeftArm", "upperarm.L", "fwd"), ("LeftForeArm", "forearm.L", "fwd"),
    ("LeftHand", "hand.L", "fwd"),
    ("RightShoulder", "clavicle.R", "fwd"), ("RightArm", "upperarm.R", "fwd"), ("RightForeArm", "forearm.R", "fwd"),
    ("RightHand", "hand.R", "fwd"),
    ("LeftLeg", "thigh.L", "fwd"), ("LeftShin", "shin.L", "fwd"), ("LeftFoot", "foot.L", "up"),
    ("RightLeg", "thigh.R", "fwd"), ("RightShin", "shin.R", "fwd"), ("RightFoot", "foot.R", "up"),
]
# the fingers go across too (MotionBricks reads the thumb's and the middle finger's ends), but come back as ours: it
# does not move them
FINGERS = []
for _s, _o in (("Left", "L"), ("Right", "R")):
    FINGERS += [(f"{_s}HandThumb{i}", f"thumb_0{i}.{_o}", "up") for i in (1, 2, 3)]
    for _f in ("Index", "Middle", "Ring", "Pinky"):
        FINGERS += [(f"{_s}Hand{_f}{i + 1}", f"{_f.lower()}_0{i}.{_o}", "fwd") for i in (1, 2, 3)]
# SOMA joint -> the child its bone points at
SOMA_CHILD = {"Hips": "Spine1", "Spine1": "Spine2", "Chest": "Neck1", "Neck1": "Neck2", "Head": "HeadEnd",
              "LeftShoulder": "LeftArm", "LeftArm": "LeftForeArm", "LeftForeArm": "LeftHand", "LeftHand": "LeftHandMiddle1",
              "RightShoulder": "RightArm", "RightArm": "RightForeArm", "RightForeArm": "RightHand",
              "RightHand": "RightHandMiddle1", "LeftLeg": "LeftShin", "LeftShin": "LeftFoot", "LeftFoot": "LeftToeBase",
              "RightLeg": "RightShin", "RightShin": "RightFoot", "RightFoot": "RightToeBase"}
for _s in ("Left", "Right"):
    SOMA_CHILD.update({f"{_s}HandThumb1": f"{_s}HandThumb2", f"{_s}HandThumb2": f"{_s}HandThumb3",
                       f"{_s}HandThumb3": f"{_s}HandThumbEnd"})
    for _f in ("Index", "Middle", "Ring", "Pinky"):
        SOMA_CHILD.update({f"{_s}Hand{_f}2": f"{_s}Hand{_f}3", f"{_s}Hand{_f}3": f"{_s}Hand{_f}4",
                           f"{_s}Hand{_f}4": f"{_s}Hand{_f}End"})
BETWEEN = {"Spine2": ("Spine1", "Chest"), "Neck2": ("Neck1", "Head")}
# how fast each of our looping clips moves over the ground (m/s): measured from its planted feet when not given
WALKERS = ("Stroll", "Walk", "Run", "CrouchWalk")


def frame(d, s):
    d = d / np.linalg.norm(d)
    s = s - d * np.dot(s, d)
    s = s / np.linalg.norm(s)
    return np.stack([d, s, np.cross(d, s)], -1)


def quat(m):
    """rotation matrices [..., 3, 3] -> quaternions (w, x, y, z)"""
    m = np.asarray(m)
    w = np.sqrt(np.maximum(0.0, 1.0 + m[..., 0, 0] + m[..., 1, 1] + m[..., 2, 2])) / 2.0
    x = np.sqrt(np.maximum(0.0, 1.0 + m[..., 0, 0] - m[..., 1, 1] - m[..., 2, 2])) / 2.0
    y = np.sqrt(np.maximum(0.0, 1.0 - m[..., 0, 0] + m[..., 1, 1] - m[..., 2, 2])) / 2.0
    z = np.sqrt(np.maximum(0.0, 1.0 - m[..., 0, 0] - m[..., 1, 1] + m[..., 2, 2])) / 2.0
    x = np.copysign(x, m[..., 2, 1] - m[..., 1, 2])
    y = np.copysign(y, m[..., 0, 2] - m[..., 2, 0])
    z = np.copysign(z, m[..., 1, 0] - m[..., 0, 1])
    return np.stack([w, x, y, z], -1)


def mat(q):
    w, x, y, z = np.moveaxis(q / np.linalg.norm(q, axis=-1, keepdims=True), -1, 0)
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def mean_rot(a, b):
    qa, qb = quat(a), quat(b)
    qb = np.where((np.sum(qa * qb, -1) < 0)[..., None], -qb, qb)
    return mat(qa + qb)


def ground_speed(bones, clip):
    """m/s the planted feet move back (Blender +Y) in an in-place clip, at 30 frames a second: the ball of the foot
    (14 cm along it from the ankle) while it is within a centimetre of its lowest (the ankle rolls up through the
    stance: taken from the ankle the walk read 3.0 m/s, the run 4.9, against 3.3 and 5.8 where the foot is down)"""
    v = []
    for f in ("foot.L", "foot.R"):
        m = clip[:, bones.index(f)]
        p = m[:, :3, 3] + m[:, :3, 1] * 0.14
        low = p[:, 2] < p[:, 2].min() + 0.01
        dy = np.diff(p[:, 1]) * 30.0
        ok = low[1:] & low[:-1]
        if ok.any():
            v.append(np.median(dy[ok]))
    return float(np.mean(v)) if v else 0.0


def soma_skeleton(path):
    """MotionBricks' SOMA rig (mb_generate.py --dump-skeleton) as a BVH skeleton (cm, a Root at the ground over the
    Hips, as MotionBricks' own clips have) and its reference pose: local rotations, global rotations and positions"""
    d = np.load(path)
    names = ["Root"] + [str(n) for n in d["names"]]
    parents = [-1] + [int(p) + 1 for p in d["parents"]]
    ref = d["reference"]
    offsets = np.concatenate([np.zeros((1, 3)), ref[:, :3] * 100.0])
    x, y, z, w = ref[:, 3], ref[:, 4], ref[:, 5], ref[:, 6]
    R = mat(np.stack([w, x, y, z], -1))
    R = np.concatenate([np.eye(3)[None], R])
    channels = [["Xposition", "Yposition", "Zposition", "Zrotation", "Yrotation", "Xrotation"] if i < 2
                else ["Zrotation", "Yrotation", "Xrotation"] for i in range(len(names))]
    skel = sb.Skeleton(names, parents, offsets, channels)
    G, P = sb.global_transforms(skel, R[None], offsets[None])
    return skel, R, G[0], P[0]


def main():
    src, soma_path, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    opts = dict(a[2:].split("=", 1) for a in sys.argv[4:] if a.startswith("--") and "=" in a)
    out.mkdir(parents=True, exist_ok=True)
    d = np.load(src)
    bones = list(d["bones"])
    rest = d["rest"]
    want = [c for c in opts.get("clips", "").split(",") if c] or list(d["clips"])
    cycles = int(opts.get("cycles", 6))

    skel, R0, Gs_ref, Ps_ref = soma_skeleton(soma_path)
    si = skel.index
    fwd, up = np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0])

    # the anatomical frames in each skeleton's own axes
    Lo, Ls = {}, {}
    for sj, ob, kind in PAIRS + FINGERS:
        Go = B2S @ rest[bones.index(ob), :3, :3] @ B2S.T
        do = B2S @ rest[bones.index(ob), :3, 1]                  # (a Blender bone runs along its own Y)
        ds = Ps_ref[si[SOMA_CHILD[sj]]] - Ps_ref[si[sj]]
        sec = fwd if kind == "fwd" else up
        Lo[sj] = Go.T @ frame(do, sec)
        Ls[sj] = Gs_ref[si[sj]].T @ frame(ds, sec)
    np.savez(out / "alignment.npz", pairs=np.array([[p[0], p[1]] for p in PAIRS]),
             Lo=np.array([Lo[p[0]] for p in PAIRS]), Ls=np.array([Ls[p[0]] for p in PAIRS]), B2S=B2S,
             soma_names=np.array(skel.names), soma_parents=np.array(skel.parents), soma_ref_local=R0,
             soma_offsets=skel.offsets, our_bones=np.array(bones), our_rest=rest)

    hips_scale = Ps_ref[si["Hips"]][1] / (rest[bones.index("hips"), 2, 3] * 100.0)
    for name in want:
        clip = d["clip_" + name]
        speed = 0.0
        if name in WALKERS:
            speed = float(opts.get("speed_" + name, ground_speed(bones, clip)))
            loop = clip[:-1] if np.abs(clip[0] - clip[-1]).max() < 1e-4 else clip
            clip = np.concatenate([loop] * cycles)
        F = len(clip)
        Go = np.einsum("ab,fjbc,dc->fjad", B2S, clip[:, :, :3, :3], B2S)          # [F, B, 3, 3] in SOMA space
        G = np.zeros((F, len(skel.names), 3, 3))
        done = np.zeros(len(skel.names), bool)
        pair = {p[0]: bones.index(p[1]) for p in PAIRS + FINGERS}
        for j, n in enumerate(skel.names):
            if n in pair:
                G[:, j] = Go[:, pair[n]] @ Lo[n] @ Ls[n].T
                done[j] = True
        for j, n in enumerate(skel.names):
            p = skel.parents[j]
            if n in BETWEEN:
                lo, hi = (si[x] for x in BETWEEN[n])
                a = G[:, lo] @ (Gs_ref[lo].T @ Gs_ref[j])
                b = G[:, hi] @ (Gs_ref[hi].T @ Gs_ref[j])
                G[:, j] = mean_rot(a, b)
            elif not done[j]:
                G[:, j] = (G[:, p] if p >= 0 else np.eye(3)) @ R0[j]
        L = np.zeros_like(G)
        for j in range(len(skel.names)):
            p = skel.parents[j]
            L[:, j] = G[:, j] if p < 0 else np.swapaxes(G[:, p], -1, -2) @ G[:, j]
        pos = np.tile(skel.offsets[None], (F, 1, 1)).copy()
        hips = np.einsum("ab,fb->fa", B2S, clip[:, bones.index("hips"), :3, 3]) * 100.0 * hips_scale
        hips[:, 2] += speed * 100.0 * np.arange(F) / 30.0
        pos[:, si["Root"]] = 0.0
        pos[:, si["Hips"]] = hips
        sb.write(out / f"{name}.bvh", skel, L, pos, 1.0 / 30.0)
        print(f"{name}: {F} frames, {speed:.2f} m/s")


if __name__ == "__main__":
    main()
