"""The skin's last pass (Project Orion): what QC (qc.py) calls an anomaly is found on the subdivided skin and relaxed
where it is, and nowhere else: a face passing through another, a fold (two neighbouring faces turned back on each
other). Each such vertex and the few rings of skin round it are smoothed (Taubin's two steps, so the skin does not
shrink) a little at a time, then everything is measured again, until nothing is left or the rounds run out.

Used by lab.py after the anatomy and the feet's own forms are laid on the skin; mask says where it may work (the
hands and feet, where the digits lie close)."""
import numpy as np
from mathutils.bvhtree import BVHTree


def adjacency(faces, n):
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 3]], faces[:, [3, 0]]])
    e = np.sort(e, axis=1)
    e = np.unique(e, axis=0)
    return e


def face_normals(co, faces):
    a, b, c, d = (co[faces[:, k]] for k in range(4))
    n = np.cross(c - a, d - b)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def folds(co, faces, edges_faces, thresh_deg):
    """vertices on an edge whose two faces turn by more than thresh_deg"""
    fn = face_normals(co, faces)
    fa, fb, ev = edges_faces
    dots = np.clip((fn[fa] * fn[fb]).sum(1), -1, 1)
    bad = np.degrees(np.arccos(dots)) > thresh_deg
    return np.unique(ev[bad].ravel())


def edge_faces(faces):
    """per interior edge: its two faces and its two vertices"""
    nf = len(faces)
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 3]], faces[:, [3, 0]]])
    fid = np.tile(np.arange(nf), 4)
    es = np.sort(e, axis=1)
    key = es[:, 0].astype(np.int64) * (1 << 32) + es[:, 1]
    order = np.argsort(key, kind="stable")
    key, fid, es = key[order], fid[order], es[order]
    same = key[1:] == key[:-1]
    i = np.nonzero(same)[0]
    return fid[i], fid[i + 1], es[i]


def crossings(co, faces, idx_faces):
    """vertices of faces (among idx_faces) passing through other faces that share no vertex with them"""
    polys = faces.tolist()
    tree = BVHTree.FromPolygons([tuple(p) for p in co], polys, all_triangles=False)
    sub = BVHTree.FromPolygons([tuple(p) for p in co], [polys[i] for i in idx_faces], all_triangles=False)
    bad = set()
    for a, b in sub.overlap(tree):
        fa = polys[idx_faces[a]]; fb = polys[b]
        if set(fa) & set(fb):
            continue
        bad.update(fa); bad.update(fb)
    return np.array(sorted(bad), np.int64)


def untangle(co, faces, mask, fold_deg=75.0, rounds=6, steps=6, grow=3, log=print):
    """relaxes the skin where it folds or passes through itself, within mask (per vertex), and returns it"""
    co = np.asarray(co, np.float64).copy()
    faces = np.asarray(faces, np.int64)
    n = len(co)
    edges = adjacency(faces, n)
    ef = edge_faces(faces)
    deg = np.bincount(edges[:, 0], minlength=n) + np.bincount(edges[:, 1], minlength=n)
    in_mask = np.asarray(mask, bool)
    idx_faces = np.nonzero(in_mask[faces].all(1))[0]
    total = 0
    for r in range(rounds):
        bad = np.union1d(folds(co, faces, ef, fold_deg), crossings(co, faces, idx_faces))
        bad = bad[in_mask[bad]]
        if not len(bad):
            log(f"skin untangled after {r} rounds ({total} vertices relaxed)")
            return co
        total += len(bad)
        w = np.zeros(n); w[bad] = 1.0
        for g in range(grow):                                      # a falloff round each bad place
            nb = np.zeros(n)
            np.maximum.at(nb, edges[:, 0], w[edges[:, 1]]); np.maximum.at(nb, edges[:, 1], w[edges[:, 0]])
            w = np.maximum(w, nb * .7)
        w *= in_mask
        for s in range(steps):
            for lam in (.5, -.53):
                acc = np.zeros((n, 3))
                np.add.at(acc, edges[:, 0], co[edges[:, 1]]); np.add.at(acc, edges[:, 1], co[edges[:, 0]])
                avg = acc / np.maximum(deg, 1)[:, None]
                co += (avg - co) * (lam * w)[:, None]
    bad = np.union1d(folds(co, faces, ef, fold_deg), crossings(co, faces, idx_faces))
    bad = bad[in_mask[bad]]
    log(f"skin untangled: {total} vertices relaxed, {len(bad)} still folded or crossing")
    return co
