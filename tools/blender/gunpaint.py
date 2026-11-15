"""A gun's own maps, painted on what bakekit.py baked from it (the owner's gun rules, docs/art/GUN_TEXTURE_RULES.md:
"wear storytelling", "manufacturing detail"; the art-production specification, section 6: "Do not apply random
scratches uniformly across every surface. Wear must tell a believable story").

The tiling sets (surface_maps.py) say what each part is made of. These say what has HAPPENED to this gun and what was
made on it, texel by texel, from where each texel is (its position, its normal, how buried it is, how the surface
turns there, which material it is):

  <gun>_u_m1.png   R ambient occlusion . G edge wear (rubbed where the surface turns outward, more where it is exposed
                   and where hands and things reach) . B dirt (in the hollows and inside corners, soot at the muzzle)
  <gun>_u_m2.png   R handling (polished by the hand: grip, fore end, comb, controls) . G heat (the muzzle and the gas
                   block: straw, then blue) . B paint (markings filled with paint)
  <gun>_u_m3.png   relief, .5 = none: below it engraved (the maker's mark, the model, the serial number, proof marks),
                   above it raised (a weld's bead, a mould's seam). The game bends the light by it.

A gun's spec says where its places are (in the gun's own frame, metres, after its scale): see RIFLE. Text is
Blender's own text object turned to a mesh and filled; the maker's mark is drawn (a broken ring and a point: the
orbit). All of it is ours.
"""
import math
import os
import bpy
import numpy as np

import bakekit

F32 = np.float32


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def noise3(P, scale, seed=0.0):
    """value noise in space (so it has no seam at a UV island's edge), 0..1; P: (N, 3) metres"""
    q = P / scale
    i = np.floor(q)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(P), F32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                h = np.sin((i[:, 0] + dx) * 127.1 + (i[:, 1] + dy) * 311.7 + (i[:, 2] + dz) * 74.7 + seed * 19.19) * 43758.5453
                h = h - np.floor(h)
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += (h * w).astype(F32)
    return out


def fbm3(P, scale, seed=0.0, octaves=2):
    out, amp, tot = np.zeros(len(P), F32), 1.0, 0.0
    for o in range(octaves):
        out += amp * noise3(P, scale / 2 ** o, seed + o * 7.3)
        tot += amp
        amp *= .5
    return out / tot


def text_mask(text, px=96):
    """a line of text as a mask (rows from the top), `px` texels to the font's unit; returns (mask, width / height)"""
    cu = bpy.data.curves.new("MarkText", 'FONT')
    cu.body = text
    cu.size = 1.0
    cu.space_character = 1.12
    o = bpy.data.objects.new("MarkText", cu)
    bpy.context.scene.collection.objects.link(o)
    me = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    V = np.array([(v.co.x, v.co.y) for v in me.vertices], F32)
    me.calc_loop_triangles()
    T = np.array([t.vertices[:] for t in me.loop_triangles], np.int32)
    bpy.data.objects.remove(o)
    bpy.data.curves.remove(cu)
    lo, hi = V.min(0), V.max(0)
    k = px * 2                                                   # (drawn at twice the size, then halved: soft edges)
    W, H = int((hi[0] - lo[0]) * k) + 4, int((hi[1] - lo[1]) * k) + 4
    P = (V - lo) * k + 2
    m = np.zeros((H, W), F32)
    for a, b, c in T:
        x0, x1 = max(0, int(min(P[a, 0], P[b, 0], P[c, 0]))), min(W - 1, int(max(P[a, 0], P[b, 0], P[c, 0])) + 1)
        y0, y1 = max(0, int(min(P[a, 1], P[b, 1], P[c, 1]))), min(H - 1, int(max(P[a, 1], P[b, 1], P[c, 1])) + 1)
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        d = (P[b, 1] - P[c, 1]) * (P[a, 0] - P[c, 0]) + (P[c, 0] - P[b, 0]) * (P[a, 1] - P[c, 1])
        if abs(d) < 1e-9:
            continue
        u = ((P[b, 1] - P[c, 1]) * (X - P[c, 0]) + (P[c, 0] - P[b, 0]) * (Y - P[c, 1])) / d
        v = ((P[c, 1] - P[a, 1]) * (X - P[c, 0]) + (P[a, 0] - P[c, 0]) * (Y - P[c, 1])) / d
        inside = (u >= 0) & (v >= 0) & (u + v <= 1)
        m[y0:y1 + 1, x0:x1 + 1] = np.maximum(m[y0:y1 + 1, x0:x1 + 1], inside)
    m = m[:H // 2 * 2, :W // 2 * 2]
    m = (m[0::2, 0::2] + m[1::2, 0::2] + m[0::2, 1::2] + m[1::2, 1::2]) / 4
    m = np.maximum(m, np.maximum(np.roll(m, 1, 1), np.roll(m, 1, 0)) * .9)      # (a cutter has a width: strokes a texel bolder)
    return m[::-1].copy(), m.shape[1] / m.shape[0]


def ring_mark(n=256):
    """the maker's mark: a broken ring and a point (the orbit); a square mask"""
    y, x = (np.mgrid[0:n, 0:n].astype(F32) + .5) / n * 2 - 1
    r = np.hypot(x, y)
    a = np.degrees(np.arctan2(-y, x)) % 360
    ring = smooth(.11, .07, np.abs(r - .72)) * (1 - smooth(8, 3, np.abs(((a - 52 + 180) % 360) - 180) - 14))     # a gap at the upper right
    shard = smooth(.09, .05, np.abs(r - .93)) * smooth(8, 3, np.abs(((a - 52 + 180) % 360) - 180) - 5)            # the piece that broke away
    point = smooth(.20, .15, np.hypot(x + .08, y - .06))
    return np.clip(ring + shard + point, 0, 1)


class Marks:
    """what is made on the gun: placed in space, so it falls on whatever faces that way there"""

    def __init__(self, maps):
        self.pos, self.nrm, self.cover = maps["pos"], maps["nrm"], maps["cover"]
        shape = self.cover.shape
        self.engrave = np.zeros(shape, F32)
        self.raise_ = np.zeros(shape, F32)
        self.paint = np.zeros(shape, F32)

    def stamp(self, mask, aspect, origin, right, up, height, into="engrave", depth=.012):
        """a mask laid on the gun: its lower left at `origin`, reading along `right`, `height` metres tall"""
        r, u = np.array(right, F32), np.array(up, F32)
        n = np.cross(r, u)
        q = self.pos - np.array(origin, F32)
        a, b, d = q @ r, q @ u, q @ n
        hit = self.cover & (a > 0) & (a < height * aspect) & (b > 0) & (b < height) & (np.abs(d) < depth) & ((self.nrm @ n) > .55)
        if not hit.any():
            print(f"[gunpaint] a mark at {origin} met nothing", flush=True)
            return 0
        H, W = mask.shape
        ix = np.clip((a[hit] / (height * aspect) * W).astype(np.int32), 0, W - 1)
        iy = np.clip(((1 - b[hit] / height) * H).astype(np.int32), 0, H - 1)
        target = getattr(self, "raise_" if into == "raise" else into)
        target[hit] = np.maximum(target[hit], mask[iy, ix])
        return int(hit.sum())

    def text(self, s, origin, right, up, height, into="engrave", px=96):
        m, aspect = text_mask(s, px)
        got = self.stamp(m, aspect, origin, right, up, height, into)
        print(f"[gunpaint] '{s}' ({into}): {got} texels", flush=True)

    def bead(self, a, b, side, width=.0022):
        """a weld's bead from a to b (space), on what faces `side`: a ridge in overlapping ripples"""
        a, b, n = np.array(a, F32), np.array(b, F32), np.array(side, F32)
        ab = b - a
        L = float(np.linalg.norm(ab))
        q = self.pos - a
        t = (q @ ab) / (L * L)
        off = q - t[..., None] * ab
        off = off - (off @ n)[..., None] * n
        dist = np.linalg.norm(off, axis=2)
        hit = self.cover & (t > 0) & (t < 1) & (dist < width) & (np.abs(q @ n) < .012) & ((self.nrm @ n) > .4)
        prof = (1 - (dist / width) ** 2) * (.72 + .28 * np.cos(t * L / .0016 * 2 * math.pi))
        self.raise_[hit] = np.maximum(self.raise_[hit], prof[hit])


def _fill(a, cover, rounds=6, rest=0.0):
    """values spread out past each island's edge (so a blurred or smaller copy of the map does not pull black in);
    what no island reaches is `rest` (the relief's is .5: black there is a pit at every island's far side)"""
    out, c = a * cover, cover.astype(F32)
    for _ in range(rounds):
        num, den = bakekit._blur(out, 2), bakekit._blur(c, 2)
        grow = (c < .5) & (den > .02)
        out = np.where(grow, num / np.maximum(den, 1e-6), out)
        c = np.where(grow, 1.0, c)
    return np.where(c > .5, out, rest)


def _save(path, rgb):
    H, W = rgb.shape[:2]
    if rgb.ndim == 2:
        rgb = np.repeat(rgb[..., None], 3, 2)
    im = bpy.data.images.new("GunPaint", W, H, alpha=False)
    im.colorspace_settings.name = 'Non-Color'
    px = np.ones((H, W, 4), F32)
    px[..., :3] = np.clip(rgb, 0, 1)[::-1]
    im.pixels.foreach_set(px.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def paint(name, maps, spec, out_dir, log=print):
    """spec: scale, muzzle, gas (points), bore (z of the barrel's axis), hands (a list of (materials, test(P, N)) that
    say where a hand lies), tracks (boxes a moving part rubs), marks(Marks) (a function that places the markings)."""
    cover, pos, nrm, ao = maps["cover"], maps["pos"], maps["nrm"], maps["ao"]
    names = list(maps["materials"])
    mat = maps["mat"]
    curv, texel = bakekit.curvature(maps)
    sel = cover
    P, N = pos[sel], nrm[sel]
    A, C = ao[sel], curv[sel]
    M = mat[sel]

    def is_(*keys):
        if "*" in keys:
            return np.ones(len(M), bool)
        ids = [i for i, n_ in enumerate(names) if any(n_ == k or n_.startswith(k + "__") for k in keys)]
        return np.isin(M, ids)
    metal = is_("gun_steel", "gun_parkerized", "gun_metal", "gun_dark", "gun_trim", "gun_brass")
    big = fbm3(P, .035, 1.0, 2)
    mid = fbm3(P, .009, 2.0, 2)
    fine = noise3(P, .0018, 3.0)

    # ---- edge wear: where the surface turns outward, in a band, broken up, more where it is open to the world
    # (a line at the very corner, a texel or two wide, bare all the way only at the most exposed corners: a band a
    # chamfer wide and bare from end to end read as a stroke of white paint)
    edge = smooth(220, 700, C)
    band = np.zeros(cover.shape, F32)
    band[sel] = edge
    wide = bakekit.spread(band, cover, .0011 / texel)[sel]
    band = np.maximum(band, bakekit.spread(band, cover, .0004 / texel) * .6)[sel]
    open_ = smooth(.55, .95, A)
    wear = band * (.22 + .78 * smooth(.40, .80, big)) * (.35 + .65 * open_) * (.55 + .45 * smooth(.2, .8, mid))
    # a COAT (the light guns' ceramic, a paint) does not rub thin like a blue: it chips, a millimetre in from the rim
    coat = is_("gun_body", "gun_paint")
    chipped = np.maximum(band, wide * .85) * (.30 + .70 * smooth(.35, .75, big)) * (.40 + .60 * open_) * (.5 + .5 * smooth(.2, .8, mid)) * 1.25
    wear = np.where(coat, np.clip(chipped, 0, 1), wear)
    # (nothing is rubbed on a flat with no cause: a patch there read as a stain, a stroke as a soft block, since a mask
    # at .4 mm a texel cannot draw a hairline. Hairlines are the tiling set's and the per-copy scratch layer's.)

    # ---- dirt: in the hollows and the inside corners; dust on what looks up out of a recess
    hollow = smooth(.60, .22, A)
    inside = np.zeros(cover.shape, F32)
    inside[sel] = smooth(-140, -520, C)
    inside = bakekit.spread(inside, cover, .0010 / texel)[sel]
    dust = smooth(.3, .8, N[:, 2]) * smooth(.80, .50, A) * .3
    dirt = np.clip((.80 * hollow + .5 * inside + dust) * (.35 + .65 * smooth(.25, .75, mid)), 0, 1)

    # ---- handling: where a hand lies, the finish is polished
    hand = np.zeros(len(P), F32)
    for keys, test in spec.get("hands", ()):
        hand = np.maximum(hand, np.where(is_(*keys), test(P, N), 0).astype(F32))
    hand = hand * (.45 + .55 * smooth(.3, .7, mid)) * (.6 + .4 * open_)
    for lo, hi, amount in spec.get("tracks", ()):               # where a part slides or is worked: rubbed bright
        lo_, hi_ = np.array(lo, F32), np.array(hi, F32)
        soft = np.minimum(P - lo_, hi_ - P) / np.maximum((hi_ - lo_) * .25, 1e-6)       # (fading toward the box's sides: no edge of its own)
        box = np.clip(soft.min(axis=1), 0, 1)
        streak = .55 + .45 * noise3(P * np.array((40.0, 1.0, 40.0), F32), .02, 5.0)     # drawn out along the gun
        wear = np.maximum(wear, box * amount * streak * (.5 + .5 * open_))
        hand = np.maximum(hand, box * amount * .6)

    # ---- heat: the muzzle and the gas block (metal near the barrel's axis only), and the soot there
    heat = np.zeros(len(P), F32)
    if "muzzle" in spec:
        mz = np.array(spec["muzzle"], F32)
        axis = np.hypot(P[:, 0], P[:, 2] - spec["bore"])
        along = np.abs(P[:, 1] - mz[1])
        heat = np.exp(-along / .060) * smooth(.035, .016, axis)
        if "gas" in spec:
            heat = np.maximum(heat, .75 * np.exp(-np.linalg.norm(P - np.array(spec["gas"], F32), axis=1) / .028))
        scorch = smooth(.35, .85, heat) * (1 - metal) * (.45 + .55 * mid) * .7      # a coat or a polymer does not blue: it soots
        heat = heat * metal * (.75 + .25 * mid)
        dirt = np.clip(dirt + smooth(.45, .9, heat) * (.35 + .65 * hollow) + scorch, 0, 1)

    # ---- what is made on it
    mk = Marks(maps)
    if spec.get("marks"):
        spec["marks"](mk, maps)
    eng, rai, pnt = mk.engrave[sel], mk.raise_[sel], mk.paint[sel]
    for keys, test in spec.get("seams", ()):                    # a mould's seam: a fine raised line where its halves met
        rai = np.maximum(rai, np.where(is_(*keys), test(P, N), 0).astype(F32))
    relief = .5 - .42 * eng * (1 - pnt * .5) + .40 * rai
    dirt = np.clip(dirt + eng * (1 - pnt) * .95, 0, 1)          # grime packs into an engraving: it is what makes it read
    wear = wear * (1 - eng) + rai * .35 * open_                 # a bead's crown is rubbed

    def lay(values, neutral=0.0):
        a = np.full(cover.shape, neutral, F32)
        a[sel] = values
        return _fill(a, cover, rest=neutral)
    os.makedirs(out_dir, exist_ok=True)
    occ = np.clip(A * 1.12, 0, 1) ** 1.25
    _save(os.path.join(out_dir, f"{name}_u_m1.png"), np.dstack([lay(occ, 1.0), lay(np.clip(wear, 0, 1)), lay(dirt)]))
    _save(os.path.join(out_dir, f"{name}_u_m2.png"), np.dstack([lay(np.clip(hand, 0, 1)), lay(np.clip(heat, 0, 1)), lay(pnt)]))
    _save(os.path.join(out_dir, f"{name}_u_m3.png"), lay(relief, .5))
    log(f"[gunpaint] {name}: {cover.shape[0]} px, {1000 * texel:.3f} mm a texel; rubbed {100 * (wear > .3).mean():.1f} %, "
        f"dirt {100 * (dirt > .3).mean():.1f} %, handled {100 * (hand > .3).mean():.1f} %, hot {100 * (heat > .3).mean():.1f} %, "
        f"engraved {int((eng > .5).sum())} texels, raised {int((rai > .3).sum())}, painted {int((pnt > .5).sum())}")
    return dict(wear=wear, dirt=dirt, hand=hand, heat=heat, relief=relief)


# ------------------------------------------------------------------------------------------------ the assault rifle

S = .82                      # the rifle's scale (weapons.GUN_SCALE): its places below are given as built, x S


def _rifle_marks(mk, maps):
    L, R_ = (0, 1, 0), (0, -1, 0)                                # reading direction on the left side / on the right
    U = (0, 0, 1)
    x = .0145                                                    # just inside the flank's surface, each side
    # the left flank: the maker and the model on the rear panel, the mark and the serial number on the front one
    mk.text("NEXUS PRIME ARSENAL", (x, -.013, .0572), L, U, .0038)
    mk.text("RIFLE 7 MM  MK IV", (x, -.013, .0518), L, U, .0034)
    mk.stamp(ring_mark(), 1.0, (x, -.048, .0508), L, U, .0100)
    mk.text("NPA 041773", (x, -.120, .0530), L, U, .0046)
    # the selector's three places, engraved and filled with paint
    for s_, (dy, dz) in (("S", (-.0215, .0045)), ("F", (-.0265, -.0105)), ("A", (-.0095, -.0170))):       # (beyond the lever's tip)
        o = (x, .046 * S + dy, .052 * S + dz)
        mk.text(s_, o, L, U, .0042)
        mk.text(s_, o, L, U, .0042, into="paint")
    # the right flank: the calibre and two proof marks by the port
    mk.text("CAL 7 MM", (-x, .072, .0296), R_, U, .0040)
    for i in range(2):
        mk.stamp(ring_mark(96), 1.0, (-x, .030 - i * .0065, .0300), R_, U, .0042)
    # welds: where each trunnion block is fixed to the pressed receiver
    for y in (-.168 * S, .100 * S):
        for sg in (1, -1):
            mk.bead((sg * x, y, .030), (sg * x, y, .064), (sg, 0, 0))


RIFLE = dict(
    scale=S,
    muzzle=(0, -.69 * S, .06 * S), bore=.06 * S, gas=(0, -.455 * S, .075 * S),
    hands=[
        (("gun_polymer_od", "gun_rubber"), lambda P, N: np.ones(len(P), F32)),                                          # the pistol grip
        (("gun_wood",), lambda P, N: smooth(-.200, -.225, P[:, 1]) * smooth(-.36, -.34, P[:, 1]) * smooth(.3, -.2, N[:, 2])),   # under the fore end
        (("gun_wood",), lambda P, N: smooth(.13, .16, P[:, 1]) * smooth(.36, .30, P[:, 1]) * smooth(-.2, .5, N[:, 2]) * .8),    # the wrist and the comb
        (("gun_steel",), lambda P, N: (np.linalg.norm(P - np.array((.0145, .046 * S, .052 * S), F32), axis=1) < .016) * .9),     # the selector
        (("gun_steel",), lambda P, N: smooth(-.050, -.058, P[:, 1]) * smooth(-.085, -.075, P[:, 1]) * smooth(.022, .012, P[:, 2]) * .8),   # the magazine catch, the trigger
        (("gun_steel", "gun_parkerized"), lambda P, N: smooth(-.024, -.032, P[:, 0]) * smooth(-.125, -.095, P[:, 1]) * smooth(-.08, -.10, P[:, 1])),   # the charging handle
    ],
    tracks=[
        ((-.022, -.134 * S, .066 * S), (-.010, .012 * S, .082 * S), .75),     # the bolt's slot, the handle run along it ten thousand times
        ((-.020, -.140, -.004), (.020, -.066, .016), .32),                    # the magazine well's mouth and the magazine's shoulders
    ],
    seams=[(("gun_polymer_od",), lambda P, N: smooth(.0007, .0003, np.abs(P[:, 0])) * smooth(.3, .6, np.abs(N[:, 1]) + np.abs(N[:, 2])))],
    marks=_rifle_marks,
)

SPECS = {"gun_rifle": RIFLE}


# ------------------------------------------------------------------------------------------------ every other gun
# The rifle's places were written by hand. For the rest, a gun's builder already says where its muzzle and its fore
# end are, where each moving part turns, and which material is its grip: its spec is made from that, and a clear,
# flat place for its markings is FOUND on the baked flank (never guessed: a mark laid over a vent or an edge is worse
# than none).

GRIPS = ("gun_grip", "gun_rubber", "gun_polymer_od")
PLATES = ("gun_body", "gun_paint", "gun_metal", "gun_dark", "gun_steel", "gun_parkerized")
LIGHT = ("gun_auto", "gun_pulse", "gun_scout", "gun_handcannon", "gun_shotgun", "gun_sniper", "gun_smg", "gun_sidearm",
         "gun_energy", "gun_hmg", "gun_rocket")           # the light guns: the Sarketh's own make, marked their way
RUBS = dict(mag=.30, bolt=.55, charge=.55, slide=.5, pump=.5, crane=.35, hatch=.35)


def clear_patch(maps, side, w, h, near=None, allow=None, pad=.0015, tol=.0012, cell=.001):
    """a clear, flat place on a flank: side +1 the left (x > 0), -1 the right; `w` metres along the gun, `h` up; the
    one nearest `near` (y, z). Every millimetre of it is open (not under another part), faces out, is one of the
    `allow`ed materials and lies in one plane within `tol`. Returns dict(x, y0, y1, z0, z1) or None."""
    from numpy.lib.stride_tricks import sliding_window_view
    cover, pos, nrm, ao, mat = maps["cover"], maps["pos"], maps["nrm"], maps["ao"], maps["mat"]
    ok = cover & (nrm[..., 0] * side > .93) & (ao > .7)
    if allow is not None:
        ok &= np.isin(mat, allow)
    P = pos[ok]
    if len(P) < 200:
        return None
    y0, z0 = float(P[:, 1].min()), float(P[:, 2].min())
    ny, nz = int((P[:, 1].max() - y0) / cell) + 1, int((P[:, 2].max() - z0) / cell) + 1
    flat = ((P[:, 1] - y0) / cell).astype(np.int64) * nz + ((P[:, 2] - z0) / cell).astype(np.int64)
    out = P[:, 0] * side
    hi, lo = np.full(ny * nz, -1e9, F32), np.full(ny * nz, 1e9, F32)
    np.maximum.at(hi, flat, out)
    np.minimum.at(lo, flat, out)
    full = max(2, int(.25 * (cell / max(maps.get("texel", .00022), 1e-6)) ** 2))
    good = ((np.bincount(flat, minlength=ny * nz) >= full) & (hi - lo < tol)).reshape(ny, nz)
    hi = hi.reshape(ny, nz)
    nw, nh = int((w + 2 * pad) / cell) + 1, int((h + 2 * pad) / cell) + 1
    if ny < nw or nz < nh:
        return None
    all_ = sliding_window_view(good, (nw, nh)).all(axis=(2, 3))
    top = sliding_window_view(np.where(good, hi, -1e9), (nw, nh)).max(axis=(2, 3))
    low = sliding_window_view(np.where(good, hi, 1e9), (nw, nh)).min(axis=(2, 3))
    cand = all_ & (top - low < tol)
    if not cand.any():
        return None
    if near is None:
        near = (float(np.median(P[:, 1])), float(np.median(P[:, 2])))
    cy = y0 + (np.arange(cand.shape[0]) + nw / 2) * cell
    cz = z0 + (np.arange(cand.shape[1]) + nh / 2) * cell
    d = (cy[:, None] - near[0]) ** 2 + ((cz[None, :] - near[1]) * 2.0) ** 2
    d[~cand] = 1e9
    i, j = np.unravel_index(int(np.argmin(d)), d.shape)
    return dict(x=side * float(top[i, j]), y0=y0 + i * cell + pad, y1=y0 + (i + nw) * cell - pad,
                z0=z0 + j * cell + pad, z1=z0 + (j + nh) * cell - pad)


def _stroke(m, a, b, t):
    """a stroke from a to b (x, y in 0..1 of the mask's HEIGHT, y up), `t` thick"""
    H, W = m.shape
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    x, y = (x + .5) / H, 1 - (y + .5) / H
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    L2 = max((bx - ax) ** 2 + (by - ay) ** 2, 1e-9)
    k = np.clip(((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2, 0, 1)
    d = np.hypot(x - ax - k * (bx - ax), y - ay - k * (by - ay))
    np.maximum(m, smooth(t * .5 + 1.2 / H, t * .5 - 1.2 / H, d), out=m)


def sarketh_mark(n=256):
    """the Sarketh's emblem, as on their cloth (sarketh_surface.emblem): the faceless helm from the front: the
    brow's chevron coming down to a point, the face a lozenge with the vent's slit, three dashes either side"""
    m = np.zeros((n, n), F32)
    _stroke(m, (.10, .86), (.50, .68), .095)
    _stroke(m, (.90, .86), (.50, .68), .095)
    for a, b in (((.50, .60), (.70, .36)), ((.70, .36), (.50, .08)), ((.50, .08), (.30, .36)), ((.30, .36), (.50, .60))):
        _stroke(m, a, b, .075)
    _stroke(m, (.50, .47), (.50, .22), .06)
    for i in range(3):
        y = .50 - i * .13
        _stroke(m, (.08, y), (.20, y), .06)
        _stroke(m, (.80, y), (.92, y), .06)
    return m


def sarketh_glyphs(seed, count=9, px=64):
    """a line of the Sarketh's writing, as it is cut into what they make: each sign a stem with one to three ticks
    and sometimes a point (the rows of short dashes of their armour, written down). Ours; it says nothing in any
    tongue. Returns (mask, width / height)."""
    rng = np.random.default_rng(seed)
    cw = .62
    m = np.zeros((px, int(px * cw * count)), F32)
    for i in range(count):
        ox = (i + .5) * cw
        kind = int(rng.integers(0, 4))
        lo, hi = ((.12, .88), (.12, .56), (.44, .88), (.12, .88))[kind]
        lean = float(rng.uniform(-.06, .06)) if kind != 3 else .0
        _stroke(m, (ox - lean, lo), (ox + lean, hi), .105)
        for _ in range(int(rng.integers(1, 4))):
            y = float(rng.uniform(lo + .06, hi - .06))
            sd = 1 if rng.random() < .5 else -1
            L = float(rng.uniform(.14, .24))
            up = float(rng.uniform(-.08, .12))
            _stroke(m, (ox, y), (ox + sd * L, y + up), .09)
        if rng.random() < .35:
            px_, py_ = ox + float(rng.choice((-1, 1))) * .2, (.9 if kind == 1 else .1)
            _stroke(m, (px_, py_), (px_ + .001, py_), .13)
    return m, m.shape[1] / m.shape[0]


def _sarketh_marks(seed):
    def marks(mk, maps):
        names = list(maps["materials"])

        def ids(keys):
            return [i for i, n_ in enumerate(names) if any(n_ == k or n_.startswith(k + "__") for k in keys)]
        # (on the pale shells first: grime packed into a cut reads dark on them; on their dark iron it is lost)
        tries = [(a, k) for a in (ids(PLATES[:2]), ids(PLATES)) if a for k in (1.0, .8, .62)]
        L, R_, U = (0, 1, 0), (0, -1, 0), (0, 0, 1)
        for allow, k in tries:                                   # the left flank: the emblem, their line beside it
            p = clear_patch(maps, 1, .066 * k, .020 * k, allow=allow)
            if p:                                                # (cut BIG: a stroke under a texel of the map is a smudge)
                mk.stamp(sarketh_mark(), 1.0, (p["x"], p["y0"], p["z0"]), L, U, .020 * k)
                g, asp = sarketh_glyphs(seed, 7)
                h = .0090 * k
                got = mk.stamp(g, asp, (p["x"], p["y0"] + .026 * k, p["z0"] + (.020 * k - h) / 2), L, U, h)
                print(f"[gunpaint] the Sarketh's mark and line on the left at y {p['y0']:.3f} z {p['z0']:.3f} (x{k}): {got} texels", flush=True)
                break
        else:                                                    # a small gun: the emblem alone, where it fits
            for allow, k in [(a, k) for a in (ids(PLATES[:2]), ids(PLATES)) if a for k in (.016, .012, .009)]:
                p = clear_patch(maps, 1, k, k, allow=allow)
                if p:
                    got = mk.stamp(sarketh_mark(), 1.0, (p["x"], p["y0"], p["z0"]), L, U, k)
                    print(f"[gunpaint] the Sarketh's mark alone on the left at y {p['y0']:.3f} z {p['z0']:.3f} ({1000 * k:.0f} mm): {got} texels", flush=True)
                    break
            else:
                print("[gunpaint] no clear place for a mark on the left flank", flush=True)
        for allow, k in tries:                                   # the right: a second line (this copy's own)
            p = clear_patch(maps, -1, .042 * k, .012 * k, allow=allow)
            if p:
                g, asp = sarketh_glyphs(seed + 1, 7)
                got = mk.stamp(g, asp, (p["x"], p["y1"], p["z0"] + .0015 * k), R_, U, .0090 * k)
                print(f"[gunpaint] their line on the right at y {p['y1']:.3f} z {p['z0']:.3f} (x{k}): {got} texels", flush=True)
                break
        else:
            for allow, k in [(a, k) for a in (ids(PLATES[:2]), ids(PLATES)) if a for k in (.5, .4)]:
                p = clear_patch(maps, -1, .042 * k, .012 * k, allow=allow)
                if p:
                    g, asp = sarketh_glyphs(seed + 1, 4)
                    got = mk.stamp(g, asp, (p["x"], p["y1"], p["z0"] + .0015 * k), R_, U, .0090 * k * 1.6)
                    print(f"[gunpaint] a short line on the right at y {p['y1']:.3f} z {p['z0']:.3f}: {got} texels", flush=True)
                    break
            else:
                print("[gunpaint] no clear place for a line on the right flank", flush=True)
    return marks


def auto_spec(name, info):
    """a gun's spec from what its builder says: info = dict(scale, muzzle, fore, moving=[(name, pivot)]) as built
    (before the scale)"""
    S = float(info.get("scale", 1.0))
    mz = np.array(info["muzzle"], F32) * S
    fore = np.array(info["fore"], F32) * S

    def fore_hand(P, N):                                         # the off hand: round the fore point, its sides and underside
        d = np.hypot((P[:, 1] - fore[1]) / .085, (P[:, 2] - fore[2]) / .05)
        return smooth(1.2, .6, d) * smooth(.5, -.3, N[:, 2]) * .75
    tracks = []
    for nm, pv in info.get("moving", ()):
        amount = RUBS.get(nm.split(".")[0])
        if amount:
            c = np.array(pv, F32) * S
            tracks.append((tuple(c - (.02, .034, .022)), tuple(c + (.02, .034, .022)), amount))
    seed = sum(ord(ch) * (i + 7) for i, ch in enumerate(name))
    return dict(scale=S, muzzle=tuple(float(v) for v in mz), bore=float(mz[2]),
                hands=[(GRIPS, lambda P, N: np.ones(len(P), F32)), (("*",), fore_hand)],
                tracks=tracks, marks=_sarketh_marks(seed) if name in LIGHT else None)


def spec_for(name, info=None):
    """the gun's spec: its own where one is written, else made from its builder's facts for the guns the pipeline
    has reached (SO_GUN_OWN=all reaches every gun; a name or a list reaches those)"""
    if name in SPECS:
        return SPECS[name]
    reach = os.environ.get("SO_GUN_OWN", "")
    if info and (name in LIGHT or reach == "all" or name in reach.split(",")):
        return auto_spec(name, info)
    return None
