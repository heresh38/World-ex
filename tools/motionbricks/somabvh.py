"""SOMA BVH files read and written with numpy (MotionBricks trial).

A BVH here is the SOMA skeleton MotionBricks reads: joints with offsets in their parent's frame (cm), the root `Root` and
`Hips` with six channels (position, then Z Y X rotation), every other joint three (Z Y X), Y up. Rotations compose as
R = Rz @ Ry @ Rx (the channels in the order they are listed, the first outermost).
"""
import numpy as np


class Skeleton:
    def __init__(self, names, parents, offsets, channels):
        self.names = names                  # [J]
        self.parents = parents              # [J], -1 for the root
        self.offsets = np.asarray(offsets, dtype=np.float64)   # [J, 3] cm, in the parent's frame
        self.channels = channels            # [J] lists of channel names
        self.index = {n: i for i, n in enumerate(names)}

    def header(self):
        out = ["HIERARCHY"]
        children = {i: [] for i in range(len(self.names))}
        for i, p in enumerate(self.parents):
            if p >= 0:
                children[p].append(i)

        def emit(i, depth):
            pad = "  " * depth
            kind = "ROOT" if self.parents[i] < 0 else "JOINT"
            out.append(f"{pad}{kind} {self.names[i]}")
            out.append(f"{pad}{{")
            o = self.offsets[i]
            out.append(f"{pad}  OFFSET {o[0]:.6f} {o[1]:.6f} {o[2]:.6f}")
            out.append(f"{pad}  CHANNELS {len(self.channels[i])} " + " ".join(self.channels[i]))
            if not children[i]:
                out.append(f"{pad}  End Site")
                out.append(f"{pad}  {{")
                out.append(f"{pad}    OFFSET 0.000000 0.000000 0.000000")
                out.append(f"{pad}  }}")
            for c in children[i]:
                emit(c, depth + 1)
            out.append(f"{pad}}}")

        emit(0, 0)
        return "\n".join(out)


def read(path):
    """-> (Skeleton, frames [F, C] channel values, frame time)"""
    names, parents, offsets, channels = [], [], [], []
    stack = []
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    i = 0
    end_site = 0
    while i < len(lines):
        t = lines[i].split()
        i += 1
        if not t:
            continue
        if t[0] in ("ROOT", "JOINT"):
            names.append(t[1])
            parents.append(stack[-1] if stack else -1)
            stack.append(len(names) - 1)
        elif t[0] == "End":
            end_site += 1
            stack.append(None)
        elif t[0] == "OFFSET":
            if stack and stack[-1] is not None:
                offsets.append([float(v) for v in t[1:4]])
        elif t[0] == "CHANNELS":
            channels.append(t[2:2 + int(t[1])])
        elif t[0] == "}":
            stack.pop()
        elif t[0] == "MOTION":
            break
    frames = int(lines[i].split()[-1])
    dt = float(lines[i + 1].split()[-1])
    data = np.array([[float(v) for v in l.split()] for l in lines[i + 2:i + 2 + frames]], dtype=np.float64)
    return Skeleton(names, parents, offsets, channels), data, dt


def _axis(a, deg):
    r = np.radians(deg)
    c, s = np.cos(r), np.sin(r)
    n = len(r)
    m = np.zeros((n, 3, 3))
    if a == "X":
        m[:, 0, 0] = 1; m[:, 1, 1] = c; m[:, 1, 2] = -s; m[:, 2, 1] = s; m[:, 2, 2] = c
    elif a == "Y":
        m[:, 1, 1] = 1; m[:, 0, 0] = c; m[:, 0, 2] = s; m[:, 2, 0] = -s; m[:, 2, 2] = c
    else:
        m[:, 2, 2] = 1; m[:, 0, 0] = c; m[:, 0, 1] = -s; m[:, 1, 0] = s; m[:, 1, 1] = c
    return m


def local_transforms(skel, data):
    """-> local rotations [F, J, 3, 3] and translations [F, J, 3] (cm)"""
    F, J = len(data), len(skel.names)
    rot = np.tile(np.eye(3), (F, J, 1, 1))
    pos = np.tile(skel.offsets[None], (F, 1, 1)).copy()
    col = 0
    for j, ch in enumerate(skel.channels):
        r = np.tile(np.eye(3), (F, 1, 1))
        for name in ch:
            v = data[:, col]
            col += 1
            if name.endswith("position"):
                pos[:, j, "XYZ".index(name[0])] = v
            else:
                r = r @ _axis(name[0], v)
        rot[:, j] = r
    return rot, pos


def global_transforms(skel, rot, pos):
    """local -> global rotations [F, J, 3, 3] and positions [F, J, 3]"""
    F, J = rot.shape[:2]
    G = np.zeros_like(rot)
    P = np.zeros_like(pos)
    for j in range(J):
        p = skel.parents[j]
        if p < 0:
            G[:, j] = rot[:, j]
            P[:, j] = pos[:, j]
        else:
            G[:, j] = G[:, p] @ rot[:, j]
            P[:, j] = P[:, p] + np.einsum("fab,fb->fa", G[:, p], pos[:, j])
    return G, P


def euler_zyx(m):
    """rotation matrices [..., 3, 3] = Rz Ry Rx -> degrees (z, y, x)"""
    sy = np.clip(-m[..., 2, 0], -1.0, 1.0)
    y = np.arcsin(sy)
    x = np.arctan2(m[..., 2, 1], m[..., 2, 2])
    z = np.arctan2(m[..., 1, 0], m[..., 0, 0])
    return np.degrees(np.stack([z, y, x], -1))


def write(path, skel, rot, pos, dt):
    """local rotations [F, J, 3, 3], positions [F, J, 3] (cm; only the six-channel joints' are written) -> BVH"""
    F = len(rot)
    eul = euler_zyx(rot)
    rows = []
    for f in range(F):
        vals = []
        for j, ch in enumerate(skel.channels):
            for name in ch:
                if name.endswith("position"):
                    vals.append(pos[f, j, "XYZ".index(name[0])])
                else:
                    vals.append(eul[f, j, "ZYX".index(name[0])])
        rows.append(" ".join(f"{v:.6f}" for v in vals))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(skel.header() + "\n")
        fh.write(f"MOTION\nFrames: {F}\nFrame Time: {dt:.6f}\n")
        fh.write("\n".join(rows) + "\n")
