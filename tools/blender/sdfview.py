"""Quick look at an SDF without Blender: numpy sphere tracing with soft key/fill light and AO. Dev tool.

python sdfview.py out.png module:function [view ...]   views: front side three back top  (camera looks at the bbox centre)
"""
import numpy as np, sys, importlib
import sdf


def render(fn, center, dist, yaw, pitch=0.0, size=384, fov=.5, steps=96, col=(.85, .7, .62), cfn=None):
    cy, sy = np.cos(yaw), np.sin(yaw); cp, sp = np.cos(pitch), np.sin(pitch)
    # camera looks at center from direction (yaw 0 = front, character faces -Y)
    fwd = np.array([sy * cp, cy * cp, -sp])          # from camera to target
    eye = np.asarray(center) - fwd * dist
    right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    j, i = np.mgrid[0:size, 0:size]
    u = (i / size - .5) * 2 * np.tan(fov / 2); v = -(j / size - .5) * 2 * np.tan(fov / 2)
    D = fwd[None] + u.reshape(-1, 1) * right[None] + v.reshape(-1, 1) * up[None]
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    O = np.repeat(eye[None], len(D), 0)
    t = np.full(len(D), dist * .6); hit = np.zeros(len(D), bool); alive = np.ones(len(D), bool)
    for _ in range(steps):
        idx = np.nonzero(alive)[0]
        if not len(idx):
            break
        P = (O[idx] + D[idx] * t[idx, None]).astype(np.float32)
        d = fn(P)
        t[idx] += d * .8
        h = d < 2e-4
        hit[idx[h]] = True; alive[idx[h]] = False
        far = t[idx] > dist * 1.6
        alive[idx[far]] = False
    img = np.zeros((len(D), 3)) + np.array([.16, .17, .19])
    idx = np.nonzero(hit)[0]
    if len(idx):
        P = (O[idx] + D[idx] * t[idx, None]).astype(np.float32)
        N = sdf.normals(fn, P)
        L1 = np.array([-.5, -.8, .6]); L1 /= np.linalg.norm(L1)
        L2 = np.array([.7, -.3, .1]); L2 /= np.linalg.norm(L2)
        ao = np.ones(len(P))
        for k in range(1, 5):
            hh = .004 * k
            ao -= (hh - fn((P + N * hh).astype(np.float32))) / hh * (.5 ** k) * .9
        ao = np.clip(ao, .3, 1)
        dif = np.clip(N @ L1, 0, 1) * .85 + np.clip(N @ L2, 0, 1) * .25 + .18
        H = L1 - D[idx]; H /= np.linalg.norm(H, axis=1, keepdims=True)
        spec = np.clip((N * H).sum(1), 0, 1) ** 40 * .25
        C = cfn(P) if cfn else np.array(col)[None]
        img[idx] = np.clip((C * dif[:, None]) * ao[:, None] + spec[:, None], 0, 1)
    return (img.reshape(size, size, 3) ** (1 / 1.4) * 255).astype(np.uint8)


VIEWS = {'front': (0, 0), 'three': (-.65, 0), 'side': (-np.pi / 2, 0), 'back': (np.pi, 0), 'top': (0, .9),
         'low': (-.4, -.35), 'rside': (np.pi / 2, 0)}


def sheet(fn, center, dist, views, path, size=384, cfn=None):
    from PIL import Image
    ims = [render(fn, center, dist, *VIEWS[v], size=size, cfn=cfn) for v in views]
    Image.fromarray(np.concatenate(ims, 1)).save(path)
    print('wrote', path)
