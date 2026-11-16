"""The gate every asset passes before it may be called Technically complete (the owner's ruling of 2026-11-14:
"No unverified AI assets, poor topology, unfinished textures or unoptimised models in the final game"; the
art-production specification, docs/art/ASSET_PIPELINE.md; the checklist, docs/art/ASSET_AUDIT.md sections 8 and 11).

It does not matter what made the asset (our Blender scripts, a sculpt, a painted set, an AI-assisted start): what is
measured is the game-ready model as it goes to the import. Every line is a NUMBER against a limit, never "looks fine":

  topology      triangles against the class's budget, degenerate faces, loose vertices and edges, faces wound against
                their neighbours (flipped normals), edges shared by more than two faces, sliver triangles
  UVs           the unique set (UV 1): inside 0..1, nothing overlapping, one texel density, stretch, how much of the
                atlas is used, how much of it lies on faces hidden under other parts (from the baked occlusion)
  textures      every material has colour, normal and roughness / metal maps; their sizes; the roughness is a MAP
                with a range, never one value; the asset's own baked maps are there
  optimisation  triangles and materials against the budget, draw calls (a material a part), the triangles' size

  blender --background --python tools/blender/asset_check.py -- <model.glb> [--class=weapon] [--own=<name>]
          [--textures=assets/textures] [--size=4096] [--json=report.json] [--flat-ok=gun_glow,gun_lens]

FAIL = the asset stays below Technically complete. WARN = written into its report, with the reason it stands. The
budgets are the project's own (ASSET_AUDIT.md section 11): change them THERE and here together, not per asset.
It cannot judge what an eye judges (silhouette, proportion, whether the wear tells the truth): that is the review in
the game (`SOCaptureSeries 1 29`) and the owner's word.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

F32 = np.float32

# triangles, materials; own = the class is made on the baked pipeline (a unique UV 1 and its own maps)
CLASSES = {
    "weapon": dict(tris=200000, materials=12, own=True),        # a gun in the hands, with its moving parts (the owner, 2026-11-15)
    "player": dict(tris=120000, materials=24, own=True),        # a body with everything it wears
    "boss": dict(tris=150000, materials=12, own=True),
    "enemy": dict(tris=40000, materials=6, own=True),           # a standard enemy, many on screen
    "vehicle": dict(tris=80000, materials=10, own=True),
    "prop": dict(tris=15000, materials=4, own=False),
    "building": dict(tris=250000, materials=16, own=False),     # Nanite: the limit is its fallback and its materials
}
LIMITS = dict(overlap=.01, density_spread=1.6, stretch_share=.10, flipped_share=.002, sliver_share=.05,
              hidden_share=.25, atlas_used=.50, rough_range=.01)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(cls="weapon", own=None, textures="assets/textures", size=4096, json=None,
               flat_ok="gun_glow,gun_lens,gun_glass,gun_dot,gun_tritium,gun_sightpaint,gun_sightorange")     # lights, glass, a dab of sight paint
    files = []
    for x in a:
        if x.startswith("--"):
            k, _, v = x[2:].partition("=")
            opt[{"class": "cls", "flat-ok": "flat_ok"}.get(k, k)] = v
        else:
            files.append(x)
    if not files:
        raise SystemExit(__doc__)
    opt["size"] = int(opt["size"])
    return files[0], opt


class Report:
    def __init__(self):
        self.rows = []

    def add(self, group, name, value, limit, state, note=""):
        self.rows.append(dict(group=group, check=name, value=value, limit=limit, state=state, note=note))

    def check(self, group, name, value, limit, ok, shown=None, note="", warn=False):
        self.add(group, name, shown if shown is not None else value, limit, "ok" if ok else ("WARN" if warn else "FAIL"), note)

    def count(self, state):
        return sum(1 for r in self.rows if r["state"] == state)

    def show(self, title):
        print(f"[asset_check] {title}")
        g = None
        for r in self.rows:
            if r["group"] != g:
                g = r["group"]
                print(f"[asset_check]   {g}")
            mark = {"ok": " ok ", "WARN": "WARN", "FAIL": "FAIL", "info": "    "}[r["state"]]
            print(f"[asset_check]   {mark}  {r['check']:<46} {str(r['value']):<22} {('limit ' + str(r['limit'])) if r['limit'] != '' else '':<16} {r['note']}")
        f, w = self.count("FAIL"), self.count("WARN")
        print(f"[asset_check] RESULT: {'FAIL' if f else 'PASS'} ({f} failed, {w} warnings)")
        return f


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(path))
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and len(o.data.polygons)]


def triangles(objs):
    """every triangle of every object in the world: P (T, 3, 3) metres, U0 / U1 (T, 3, 2) or None, material names"""
    Ps, U0s, U1s, Ms, names, parts = [], [], [], [], [], []
    has1 = True
    for o in objs:
        me = o.data
        me.calc_loop_triangles()
        n = len(me.loop_triangles)
        vi = np.empty(n * 3, np.int32)
        li = np.empty(n * 3, np.int32)
        mi = np.empty(n, np.int32)
        me.loop_triangles.foreach_get("vertices", vi)
        me.loop_triangles.foreach_get("loops", li)
        me.loop_triangles.foreach_get("material_index", mi)
        co = np.empty(len(me.vertices) * 3, F32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        W = np.array(o.matrix_world, F32)
        co = co @ W[:3, :3].T + W[:3, 3]
        Ps.append(co[vi].reshape(n, 3, 3))
        for k, store in ((0, U0s), (1, U1s)):
            if len(me.uv_layers) > k:
                uv = np.empty(len(me.loops) * 2, F32)
                me.uv_layers[k].data.foreach_get("uv", uv)
                store.append(uv.reshape(-1, 2)[li].reshape(n, 3, 2))
            elif k == 1:
                has1 = False
        slot = [s.material.name if s.material else "" for s in o.material_slots] or [""]
        for s in slot:
            if s not in names:
                names.append(s)
        Ms.append(np.array([names.index(slot[min(i, len(slot) - 1)]) for i in mi], np.int32))
        parts.append((o.name, n, sorted(set(slot[min(i, len(slot) - 1)] for i in set(mi.tolist())))))
    return (np.concatenate(Ps), np.concatenate(U0s) if U0s else None, np.concatenate(U1s) if has1 and U1s else None,
            np.concatenate(Ms), names, parts)


def area3(P):
    return .5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)


def area2(U):
    a, b = U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]
    return .5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])


def topology(objs, P, R, budget):
    T = len(P)
    A = area3(P)
    R.check("topology", "triangles", T, budget["tris"], T <= budget["tris"])
    dead = int((A < 1e-12).sum())
    R.check("topology", "degenerate triangles (no area)", dead, 0, dead == 0)
    loose_v = loose_e = flipped = many = edges = open_ = 0
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)     # (an export splits vertices at every seam: welded to judge)
        loose_v += sum(1 for v in bm.verts if not v.link_faces)
        for e in bm.edges:
            n = len(e.link_faces)
            edges += 1
            if n == 0:
                loose_e += 1
            elif n == 1:
                open_ += 1
            elif n > 2:
                many += 1
            elif not e.is_contiguous:
                flipped += 1
        bm.free()
    R.check("topology", "loose vertices / edges", f"{loose_v} / {loose_e}", 0, loose_v + loose_e == 0)
    share = flipped / max(edges, 1)
    R.check("topology", "edges between faces wound against each other", f"{flipped} ({100 * share:.2f} %)", f"{100 * LIMITS['flipped_share']:.1f} %",
            share <= LIMITS["flipped_share"], note="flipped normals" if flipped else "")
    R.check("topology", "edges shared by more than two faces", f"{many} ({100 * many / max(edges, 1):.2f} %)", "1 %", many / max(edges, 1) <= .01, warn=True)
    R.add("topology", "open edges (shells laid on shells: by construction)", f"{open_} ({100 * open_ / max(edges, 1):.1f} %)", "", "info")
    e = np.stack([np.linalg.norm(P[:, 1] - P[:, 0], axis=1), np.linalg.norm(P[:, 2] - P[:, 1], axis=1), np.linalg.norm(P[:, 0] - P[:, 2], axis=1)], 1)
    long_ = e.max(1)
    aspect = long_ * long_ / np.maximum(2 * A, 1e-18)               # the longest edge over the height on it
    sliver = float(((aspect > 40) & (A > 1e-12)).mean())
    R.check("topology", "sliver triangles (longer than 40 x their height)", f"{100 * sliver:.1f} %", f"{100 * LIMITS['sliver_share']:.0f} %",
            sliver <= LIMITS["sliver_share"], warn=True)
    return A, e


def raster(U, size):
    """how many triangles cover each texel's centre (rows from v = 0): overlaps and the atlas's use"""
    hit = np.zeros((size, size), np.uint8)
    X = U * size
    lo = np.floor(X.min(1)).astype(np.int32)
    hi = np.ceil(X.max(1)).astype(np.int32)
    for t in range(len(U)):
        x0, y0 = max(lo[t, 0], 0), max(lo[t, 1], 0)
        x1, y1 = min(hi[t, 0], size), min(hi[t, 1], size)
        if x1 <= x0 or y1 <= y0:
            continue
        a, b, c = X[t]
        d = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(d) < 1e-9:
            continue
        px = np.arange(x0, x1, dtype=F32)[None, :] + .5
        py = np.arange(y0, y1, dtype=F32)[:, None] + .5
        w1 = ((px - a[0]) * (c[1] - a[1]) - (py - a[1]) * (c[0] - a[0])) / d
        w2 = ((b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])) / d
        inside = (w1 > 1e-6) & (w2 > 1e-6) & (w1 + w2 < 1 - 1e-6)
        hit[y0:y1, x0:x1] += inside.astype(np.uint8)
    return hit


def uvs(P, U1, A, R, opt, seen=None):
    """seen: a flag per triangle (from the asset's own baked occlusion): density is judged on what is seen, since
    islands under other parts may be shrunk on purpose (bakekit.unwrap shrink)"""
    if U1 is None:
        R.check("UVs", "a unique set on UV 1", "none", "needed", False, note="the baked pipeline needs it (bakekit.unwrap)")
        return None
    inside = float(U1.min()) >= -1e-4 and float(U1.max()) <= 1 + 1e-4
    R.check("UVs", "UV 1 inside 0..1", f"{U1.min():.3f} .. {U1.max():.3f}", "0 .. 1", inside)
    A2 = area2(U1)
    ok = (A > 1e-12) & (A2 > 1e-14)
    if seen is not None:
        ok = ok & seen
    d = np.sqrt(A2[ok] / A[ok])                                     # UV units a metre
    order = np.argsort(d)
    w = np.cumsum(A[ok][order]) / A[ok].sum()
    p5, p50, p95 = (float(d[order][np.searchsorted(w, q)]) for q in (.05, .5, .95))
    spread = p95 / max(p5, 1e-9)
    texel = 1000.0 / (p50 * opt["size"])
    R.check("UVs", "texel density, densest over thinnest (5 % / 95 %)", f"{spread:.2f}", LIMITS["density_spread"], spread <= LIMITS["density_spread"])
    R.add("UVs", f"a texel at {opt['size']} px", f"{texel:.3f} mm", "", "info")
    # stretch: how unevenly a triangle is drawn out in its two directions
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    x1 = np.linalg.norm(e1, axis=1)
    ex = e1 / np.maximum(x1, 1e-12)[:, None]
    x2 = (e2 * ex).sum(1)
    y2 = np.linalg.norm(e2 - x2[:, None] * ex, axis=1)
    u1, u2 = U1[:, 1] - U1[:, 0], U1[:, 2] - U1[:, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        j11, j21 = u1[:, 0] / x1, u1[:, 1] / x1                      # J = [u1 u2] * inverse([[x1, x2], [0, y2]])
        j12, j22 = (u2[:, 0] - j11 * x2) / y2, (u2[:, 1] - j21 * x2) / y2
        s = j11 * j11 + j12 * j12 + j21 * j21 + j22 * j22
        det = np.abs(j11 * j22 - j12 * j21)
        root = np.sqrt(np.maximum(s * s / 4 - det * det, 0))
        st = np.sqrt((s / 2 + root) / np.maximum(s / 2 - root, 1e-30))
    st = np.where(ok & np.isfinite(st), st, 1.0)
    flat = (A > 1e-12) & (A2 <= 1e-14)                               # drawn to a line or a point on UV 1: nothing can be painted on it
    gone = float(A[flat & seen].sum() / A.sum()) if seen is not None else float(A[flat].sum() / A.sum())
    R.check("UVs", "surface collapsed to nothing on UV 1", f"{100 * gone:.2f} %", "1 %", gone <= .01)
    over = float(A[st > 1.25].sum() / A.sum())
    R.check("UVs", "surface stretched more than 25 % on UV 1", f"{100 * over:.1f} %", f"{100 * LIMITS['stretch_share']:.0f} %", over <= LIMITS["stretch_share"])
    R.add("UVs", "surface stretched more than 10 %", f"{100 * float(A[st > 1.10].sum() / A.sum()):.1f} %", "", "info")
    size = 2048
    hit = raster(U1, size)
    used = float((hit > 0).mean())
    overlap = float((hit > 1).sum() / max((hit > 0).sum(), 1))
    R.check("UVs", "UV 1 overlapping itself", f"{100 * overlap:.2f} %", f"{100 * LIMITS['overlap']:.0f} %", overlap <= LIMITS["overlap"])
    R.check("UVs", "of the atlas used", f"{100 * used:.0f} %", f"{100 * LIMITS['atlas_used']:.0f} %", used >= LIMITS["atlas_used"], warn=True)
    return hit


def pixels(img, size=1024):
    c = img.copy()
    if c.size[0] > size:
        c.scale(size, size)
    a = np.empty(c.size[0] * c.size[1] * 4, F32)
    c.pixels.foreach_get(a)
    w, h = c.size
    bpy.data.images.remove(c)
    return a.reshape(h, w, 4)


def upstream(socket, depth=0):
    """the image a material's input is fed from, however many nodes lie between"""
    if depth > 8 or not socket.is_linked:
        return None
    n = socket.links[0].from_node
    if n.type == 'TEX_IMAGE':
        return n.image
    for i in n.inputs:
        img = upstream(i, depth + 1)
        if img:
            return img
    return None


def textures(names, M, R, opt, budget):
    used = [n for i, n in enumerate(names) if (M == i).any()]
    R.check("textures", "materials", len(used), budget["materials"], len(used) <= budget["materials"])
    flat_ok = tuple(x for x in opt["flat_ok"].split(",") if x)
    for n in used:
        m = bpy.data.materials.get(n)
        bsdf = next((x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'), None) if m and m.use_nodes else None
        if n.startswith(flat_ok):
            R.add("textures", f"{n}", "light or glass: no maps by design", "", "info")
            continue
        if not bsdf:
            R.check("textures", f"{n}", "no surface", "", False)
            continue
        col, nrm, rgh = upstream(bsdf.inputs["Base Color"]), upstream(bsdf.inputs["Normal"]), upstream(bsdf.inputs["Roughness"])
        missing = [k for k, v in (("colour", col), ("normal", nrm), ("roughness", rgh)) if v is None]
        if missing:
            R.check("textures", f"{n}: maps", "missing " + ", ".join(missing), "colour, normal, roughness", False, note="one flat value: unfinished")
            continue
        sizes = "/".join(str(i.size[0]) for i in (col, nrm, rgh))
        g = pixels(rgh)[..., 1]
        lo, hi = float(np.percentile(g, 2)), float(np.percentile(g, 98))
        ok = hi - lo >= LIMITS["rough_range"] * 5 and float(g.std()) >= LIMITS["rough_range"]
        R.check("textures", f"{n}: roughness range (2 % .. 98 %)", f"{lo:.2f} .. {hi:.2f}", "a map, not a value", ok, note=f"maps {sizes} px")
    return used


def own_maps(name, hit, R, opt):
    d = opt["textures"]
    files = [os.path.join(d, f"{name}_u_{k}.png") for k in ("m1", "m2", "m3")]
    have = [f for f in files if os.path.exists(f)]
    R.check("textures", "the asset's own baked maps (_u_m1, _u_m2, _u_m3)", f"{len(have)} of 3", 3, len(have) == 3)
    if len(have) < 3 or hit is None:
        return
    img = bpy.data.images.load(os.path.abspath(files[0]))
    R.add("textures", "own maps written at", f"{img.size[0]} px", "", "info")
    a = pixels(img, hit.shape[0])[..., 0]                            # occlusion; an image's rows start at v = 0, as the raster's do
    cover = hit > 0
    hidden = float((a[cover] < .03).mean())
    R.check("UVs", "of the atlas on faces hidden under other parts", f"{100 * hidden:.0f} %", f"{100 * LIMITS['hidden_share']:.0f} %",
            hidden <= LIMITS["hidden_share"], warn=True, note="shells laid on shells: weld the model, or bakekit.unwrap(shrink=)" if hidden > LIMITS["hidden_share"] else "")


def optimisation(parts, A, e, R):
    calls = sum(len(m) for _, _, m in parts)
    R.add("optimisation", "draw calls (a material a part)", calls, "", "info", ", ".join(f"{n} {t}" for n, t, _ in parts))
    R.add("optimisation", "a triangle's edge, median", f"{1000 * float(np.median(e)):.1f} mm", "", "info")
    tiny = float((A < 2.5e-7).mean())                                # under a quarter of a square millimetre
    R.check("optimisation", "triangles under 0.25 mm2 (nobody sees them)", f"{100 * tiny:.1f} %", "15 %", tiny <= .15, warn=True)
    R.add("optimisation", "levels of detail in the file", "none", "", "info", "a gun in the hands needs none; a world asset does")


def main():
    path, opt = args()
    budget = CLASSES[opt["cls"]]
    name = opt["own"] or os.path.splitext(os.path.basename(path))[0]
    objs = load(path)
    P, U0, U1, M, names, parts = triangles(objs)
    R = Report()
    A, e = topology(objs, P, R, budget)
    R.check("UVs", "a tiling set on UV 0", "yes" if U0 is not None else "none", "needed", U0 is not None)
    seen = None
    m1 = os.path.join(opt["textures"], f"{name}_u_m1.png")
    if budget["own"] and U1 is not None and os.path.exists(m1):     # (which triangles lie under other parts: their own occlusion says)
        img = bpy.data.images.load(os.path.abspath(m1))
        ao = pixels(img, 2048)[..., 0]
        c = U1.mean(1)
        xy = np.clip((c * ao.shape[0]).astype(np.int32), 0, ao.shape[0] - 1)
        seen = ao[xy[:, 1], xy[:, 0]] >= .03
        R.add("UVs", "triangles under other parts (never seen)", f"{100 * float((~seen).mean()):.0f} %", "", "info")
    # lights, glass and sight paint carry no maps (flat by design): their texel density says nothing, so it is judged
    # on the rest (a glass sight's broad panes held the spread over its limit with nothing on them to see)
    flat_ok = tuple(x for x in opt["flat_ok"].split(",") if x)
    textured = np.array([not str(n).startswith(flat_ok) for n in names], bool)[M] if len(names) else None
    if textured is not None:
        seen = textured if seen is None else (seen & textured)
    hit = uvs(P, U1, A, R, opt, seen) if budget["own"] else None
    textures(names, M, R, opt, budget)
    if budget["own"]:
        own_maps(name, hit, R, opt)
    optimisation(parts, A, e, R)
    failed = R.show(f"{name} as a {opt['cls']} ({os.path.basename(path)})")
    if opt["json"]:
        os.makedirs(os.path.dirname(os.path.abspath(opt["json"])), exist_ok=True)
        with open(opt["json"], "w", encoding="utf-8") as f:
            json.dump(dict(asset=name, cls=opt["cls"], budget=budget, limits=LIMITS, rows=R.rows,
                           result="FAIL" if failed else "PASS"), f, indent=1)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
