"""The texture engine: every set the game uses is written through here, to the owner's texture rules
(docs/art/TEXTURE_RULES.md, 2026-11-14: 4K, sharp up close, no seams or visible repetition; albedo, normal,
roughness, metallic, ambient occlusion, height, emissive where it applies; micro detail, imperfections, dirt where
dirt collects, edge wear, scratches, dust, weathering, colour and age variation; never plastic, flat or clean).

A surface is DRAWN, in metres: a Tile knows how many metres it covers, every feature is given its real size (a pore
is a millimetre, a slab's lift a centimetre), and the height is kept in metres. From that one height come the three
maps that make a painted surface a solid one, and they agree with each other because they have one source:

  normal   the true slope of the height (x `relief`): no "strength" to guess, and fine and broad shapes are both
           there because both are in the height
  AO       how far a point lies under its surroundings, at five radii from a texel to a hand's breadth
  height   the same field, 0..1 over its own range (the range in metres goes to assets/textures/pbr_sets.json, so
           the material can give parallax its true depth)

Files, in assets/textures: <name>_c.jpg albedo (sRGB) . _n.png normal (OpenGL) . _m.png (R ambient occlusion, G
roughness, B metallic: linear) . _h.png height . _e.jpg emissive (only where given).

Everything is periodic (a tile has no seam). What breaks the REPEAT of a tile is not here: it is the material's
second, larger-scale variation and its detail layer (import_assets.py).

The tools: noise (fbm at a feature size), cells (scattered points: nearest, second nearest, an id each: stones,
dishes, cracks), cracks (a network along warped cell borders, in patches), grid (courses of blocks or panels: joints,
distance to the nearest edge, an id per block), lines (scratches, mostly one way or any), dents, brushed (drawn out
one way), streaks (what runs DOWN a wall from a point), blur (any radius, cheap).
"""
import json
import math
import os
import sys
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "hero")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import bl                                                       # noqa: E402
import fabric                                                   # noqa: E402

F32 = np.float32
SIZE = int(os.environ.get("PBR_SIZE", "4096"))


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)], F32)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    """a toward colour b by t (t: a field)"""
    return a * (1 - t[..., None]) + np.asarray(b, F32) * t[..., None]


def pct(a, p):
    return float(np.percentile(a[::8, ::8], p))


def above(a, share, soft=.04):
    """the top `share` (0..1) of a field, as a soft mask"""
    t = pct(a, 100 * (1 - share))
    return smooth(t, t + soft * (pct(a, 99.5) - pct(a, .5) + 1e-9), a)


def _box(a, r, axis):
    if r < 1:
        return a
    n = a.shape[axis]
    r = min(r, n // 2 - 1)
    pad = np.concatenate([a.take(range(n - r - 1, n), axis=axis), a, a.take(range(0, r), axis=axis)], axis=axis)
    c = np.cumsum(pad, axis=axis, dtype=np.float64)
    return ((c.take(range(2 * r + 1, 2 * r + 1 + n), axis=axis) - c.take(range(0, n), axis=axis)) / (2 * r + 1)).astype(F32)


class Tile:
    def __init__(self, name, metres, seed=None, size=None):
        self.name, self.m = name, float(metres)
        self.Z = size or SIZE
        self.rng = np.random.RandomState(sum(map(ord, name)) * 31 % 9973 if seed is None else seed)
        self.texel = self.m / self.Z

    def px(self, metres):
        return metres / self.texel

    # ---- fields
    def noise(self, feature, octaves=4):
        """smooth noise whose biggest shapes are `feature` metres across, ~[-1, 1]"""
        return fabric._noise((self.Z, self.Z), max(1.0, self.m / feature), self.rng, octaves)

    def grain(self, soften=0):
        """a value per texel (the finest thing a map can hold), ~[-1, 1]"""
        g = self.rng.uniform(-1, 1, (self.Z, self.Z)).astype(F32)
        return self.blur_px(g, soften) * (1 + 1.6 * soften) if soften else g

    def blur_px(self, a, r):
        r = int(round(r))
        if r < 1:
            return a
        for axis in (0, 1):
            a = _box(_box(a, r, axis), max(1, r // 2), axis)
        return a

    def blur(self, a, metres):
        return self.blur_px(a, self.px(metres) * .6)

    def cells(self, feature, warp=0.0, warp_feature=None):
        """scattered points about `feature` metres apart: (distance to the nearest, to the second nearest, both in
        units of the spacing; the nearest one's own random value). warp: metres the borders wander."""
        Z, rng = self.Z, self.rng
        g = max(2, int(round(self.m / feature)))
        pts = rng.uniform(0, 1, (g, g, 2)).astype(F32)
        ids = rng.uniform(0, 1, (g, g)).astype(F32)
        y, x = np.mgrid[0:Z, 0:Z].astype(F32) * (g / Z)
        if warp:
            k = warp / feature
            x = x + self.noise(warp_feature or feature * 3, 3) * k
            y = y + self.noise(warp_feature or feature * 3, 3) * k
        iy, ix = np.floor(y).astype(np.int32), np.floor(x).astype(np.int32)
        d1 = np.full((Z, Z), 9.0, F32)
        d2 = np.full((Z, Z), 9.0, F32)
        rid = np.zeros((Z, Z), F32)
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cy, cx = iy + oy, ix + ox
                p = pts[cy % g, cx % g]
                d = np.hypot(cy + p[..., 0] - y, cx + p[..., 1] - x)
                near = d < d1
                d2 = np.where(near, d1, np.minimum(d2, d))
                rid = np.where(near, ids[cy % g, cx % g], rid)
                d1 = np.where(near, d, d1)
        return d1, d2, rid

    def cracks(self, feature, share=.3, width=.0012, warp=None):
        """a crack network: along the borders of warped cells `feature` metres across, only in patches (`share` of
        the surface), tapering where a patch ends; 1 in a crack"""
        d1, d2, _ = self.cells(feature, warp=feature * .35 if warp is None else warp, warp_feature=feature * 1.5)
        where = above(self.noise(feature * 4, 3), share, .25)
        w = width / feature * 2.0
        return smooth(w * (.35 + .65 * where), 0, d2 - d1) * smooth(0, .3, where)

    def grid(self, nx, ny, stagger=0.0, joint=.006, wander=0.0):
        """courses of blocks / slabs / panels, nx across and ny down the tile (stagger: each course shifted by this
        share of a block). Returns (1 in a joint, metres to the nearest edge of the block, a random value per block,
        another)."""
        Z = self.Z
        v = (np.arange(Z, dtype=F32)[:, None] + .5) / Z * ny
        row = np.floor(v)
        u = (np.arange(Z, dtype=F32)[None, :] + .5) / Z * nx + row * stagger
        if wander:
            u = u + self.noise(self.m / nx * 2, 2) * wander / (self.m / nx)
            v = v + self.noise(self.m / ny * 2, 2) * wander / (self.m / ny)
            row = np.floor(v)
        fu, fv = u - np.floor(u), v - row
        du = np.minimum(fu, 1 - fu) * (self.m / nx)
        dv = np.minimum(fv, 1 - fv) * (self.m / ny)
        edge = np.minimum(du, dv)
        ix, iy = np.floor(u).astype(np.int32) % nx, row.astype(np.int32) % ny
        ra = self.rng.uniform(0, 1, (ny, nx)).astype(F32)[iy, ix]
        rb = self.rng.uniform(0, 1, (ny, nx)).astype(F32)[iy, ix]
        return smooth(joint / 2 + self.texel, joint / 2 - self.texel, edge), edge, ra, rb

    def lines(self, n, length, width, bend=0.0, along=None, spread=.12):
        """n scratches, each `length` (lo, hi) metres long and `width` (lo, hi) metres wide. along: the share that
        runs nearly along U (None: any way)."""
        Z, rng = self.Z, self.rng
        out = np.zeros((Z, Z), F32)
        for _ in range(n):
            x0, y0 = rng.uniform(0, Z, 2)
            a = rng.normal(0, spread) if (along is not None and rng.uniform() < along) else rng.uniform(0, math.pi)
            L = self.px(rng.uniform(*length))
            w = max(.55, self.px(rng.uniform(*width)))
            k = rng.uniform(-bend, bend)
            h = int(min(L / 2 + 6, Z // 2 - 2))
            ys = np.arange(int(y0) - h, int(y0) + h + 1)
            xs = np.arange(int(x0) - h, int(x0) + h + 1)
            X, Y = np.meshgrid((xs - x0).astype(F32), (ys - y0).astype(F32))
            t = X * math.cos(a) + Y * math.sin(a)
            d = np.abs(-X * math.sin(a) + Y * math.cos(a) + k * t * t / max(L, 1))
            m = np.exp(-(d / w) ** 2) * np.clip(1 - (np.abs(t) / (L / 2)) ** 4, 0, 1) * rng.uniform(.45, 1.0)
            idx = np.ix_(ys % Z, xs % Z)
            out[idx] = np.maximum(out[idx], m.astype(F32))
        return out

    def dents(self, n, radius):
        Z, rng = self.Z, self.rng
        out = np.zeros((Z, Z), F32)
        for _ in range(n):
            x0, y0 = rng.uniform(0, Z, 2)
            r = max(1.0, self.px(rng.uniform(*radius)))
            h = int(min(r * 2.5 + 2, Z // 2 - 2))
            ys = np.arange(int(y0) - h, int(y0) + h + 1)
            xs = np.arange(int(x0) - h, int(x0) + h + 1)
            X, Y = np.meshgrid((xs - x0).astype(F32), (ys - y0).astype(F32))
            m = np.exp(-(X * X + Y * Y) / (r * r)) * rng.uniform(.4, 1.0)
            idx = np.ix_(ys % Z, xs % Z)
            out[idx] = np.maximum(out[idx], m.astype(F32))
        return out

    def brushed(self, length, axis=1):
        """noise drawn out `length` metres along U (axis 1) or V (axis 0), ~[-1, 1]"""
        b = self.rng.uniform(-1, 1, (self.Z, self.Z)).astype(F32)
        b = _box(_box(b, int(self.px(length) / 2), axis), int(self.px(length) / 4), axis)
        b = (b + np.roll(b, 1, 1 - axis)) / 2
        return b / (3 * b.std() + 1e-9)

    def streaks(self, n, length, width, strength=(.4, 1.0)):
        """what runs DOWN a wall: n stains, each from a point, `length` metres down and `width` wide, strongest
        where it starts; 0..1"""
        Z, rng = self.Z, self.rng
        out = np.zeros((Z, Z), F32)
        for _ in range(n):
            x0, y0 = rng.uniform(0, Z, 2)
            L = max(4.0, self.px(rng.uniform(*length)))
            w = max(1.0, self.px(rng.uniform(*width)))
            hw, hl = int(min(w * 3 + 2, Z // 2 - 2)), int(min(L + 2, Z - 2))
            ys = np.arange(int(y0), int(y0) + hl)
            xs = np.arange(int(x0) - hw, int(x0) + hw + 1)
            X, Y = np.meshgrid((xs - x0).astype(F32), (ys - y0).astype(F32))
            t = Y / L
            m = np.exp(-(X / (w * (1 + .8 * t))) ** 2) * np.clip(1 - t, 0, 1) ** 1.3 * np.clip(t * 12, 0, 1) * rng.uniform(*strength)
            idx = np.ix_(ys % Z, xs % Z)
            out[idx] = np.maximum(out[idx], m.astype(F32))
        return out

    # ---- the maps
    def occlusion(self, H, reach=1.0):
        """how far each point lies under its surroundings, at five radii: 1 open, toward 0 buried"""
        occ = np.zeros_like(H)
        for r, w in ((1.5, .22), (4, .22), (10, .22), (26, .18), (70, .16)):
            b = self.blur_px(H, r * reach)
            occ += w * np.clip((b - H) / (r * reach * self.texel) * 1.4, 0, 1)
        return 1 - np.clip(occ * 1.5, 0, .92)

    def write(self, albedo, height, rough, metal=0.0, emissive=None, relief=1.5, cavity=.30, dust=None, legacy_normal_jpg=False,
              legacy_mask_jpg=False, reach=1.0):
        """albedo: sRGB values as they are saved. height: [(field, metres deep), ...] (a field goes up with its
        value). rough / metal: fields or numbers. cavity: how much darker what is buried is (dirt lies there).
        dust: (colour, amount): pale dust on what is open and faces up out of the hollows."""
        Z = self.Z
        H = np.zeros((Z, Z), F32)
        for f, depth in height:
            H = H + f.astype(F32) * depth
        gx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) / (2 * self.texel) * relief
        gy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) / (2 * self.texel) * relief
        nrm = np.dstack([-gx, gy, np.ones_like(H)])
        nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
        nrm = nrm * .5 + .5
        ao = self.occlusion(H * relief, reach)
        alb = albedo * (1 - cavity * (1 - ao))[..., None]
        r = np.zeros((Z, Z), F32) + rough
        r = r + .10 * (1 - ao)                                   # what is buried is duller
        if dust is not None:
            col, amount = dust
            d = np.clip(1 - ao * 1.02, 0, 1) * amount            # (dust settles INTO the hollows and stays)
            alb = mix(alb, col, d)
            r = r + .12 * d
        met = np.zeros((Z, Z), F32) + metal
        for a_ in (alb, nrm, r, met, ao):
            assert np.isfinite(a_).all(), f"{self.name}: non-finite texels"
        lo, hi = float(H.min()), float(H.max())
        self._save("c", alb, True, jpg=True)
        self._save("n", nrm, False)
        if legacy_normal_jpg:                                    # (a kit's Blender material still names the .jpg)
            self._save("n", nrm, False, jpg=True)
        self._save("m", np.dstack([ao, np.clip(r, .04, 1), np.clip(met, 0, 1)]), False)
        if legacy_mask_jpg:                                      # (the guns' Blender materials name the .jpg)
            self._save("m", np.dstack([ao, np.clip(r, .04, 1), np.clip(met, 0, 1)]), False, jpg=True)
        self._save("h", np.repeat(((H - lo) / max(hi - lo, 1e-9))[..., None], 3, 2), False)
        if emissive is not None:
            self._save("e", emissive, True, jpg=True)
        _register(self.name, dict(tile=self.m, depth=round(hi - lo, 5), size=Z, emissive=emissive is not None))
        print(f"[pbr] {self.name}: {Z} px, {self.m:g} m a tile, {1000 * self.texel:.2f} mm a texel, relief {1000 * (hi - lo):.1f} mm", flush=True)

    def _save(self, kind, arr, srgb, jpg=False):
        path = os.path.join(bl.TEXTURES, f"{self.name}_{kind}.{'jpg' if jpg else 'png'}")
        os.makedirs(bl.TEXTURES, exist_ok=True)
        H, W = arr.shape[:2]
        key = f"pbr_{self.name}_{kind}"
        im = bpy.data.images.new(key, W, H, alpha=False)
        im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
        px = np.ones((H, W, 4), F32)
        px[..., :3] = np.clip(arr, 0, 1)[::-1]
        im.pixels.foreach_set(px.ravel())
        im.filepath_raw = path
        im.file_format = 'JPEG' if jpg else 'PNG'
        try:
            im.save(quality=95)
        except TypeError:
            bpy.context.scene.render.image_settings.quality = 95
            im.save()
        bpy.data.images.remove(im)


def _register(name, info):
    path = os.path.join(bl.TEXTURES, "pbr_sets.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data[name] = info
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
