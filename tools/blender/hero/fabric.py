"""Our own cloth textures for the hero outfits (numpy, tileable, saved as PNG next to the hair maps):

  twill       the coat's cloth: a 2/1 twill (diagonal ribs), threads with their own tone, slubs, a waxed mottling
  ripstop     the lining: a plain weave with heavier threads every few millimetres (the grid)
  canvas      coated canvas for the reinforcement patches and straps: a fine pebble under a satin coating
  tape        the zip tape's tight weave
  thread      stitching: a run of twisted stitches with gaps (alpha), along V

Each makes three maps: _c (albedo in the material's colour, sRGB), _n (OpenGL normal) and _m (glTF metal/rough: G
rough, B metal). texture_material() builds the Blender material that the glTF exporter writes with all three (and
the alpha clip for thread). TILE is the world size one texture repeat covers (UVs are laid out in metres / TILE).
"""
import math
import os
import bpy
import numpy as np

TILE = {"twill": .08, "ripstop": .06, "canvas": .06, "tape": .03, "thread": .012, "leather": .06, "rubber": .06,
        "braid": .02, "knit": .05, "polymer": .10}
SIZE = 1024


def _noise(shape, scale, rng, octaves=3):
    """tileable value noise (bilinear on a periodic lattice), summed octaves, ~[-1, 1]"""
    H, W = shape
    out = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = max(2, int(scale * 2 ** o))
        lat = rng.uniform(-1, 1, (n, n)).astype(np.float32)
        y = np.linspace(0, n, H, endpoint=False)
        x = np.linspace(0, n, W, endpoint=False)
        y0, x0 = np.floor(y).astype(int), np.floor(x).astype(int)
        fy, fx = (y - y0)[:, None], (x - x0)[None, :]
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        a = lat[y0 % n][:, x0 % n]
        b = lat[y0 % n][:, (x0 + 1) % n]
        c = lat[(y0 + 1) % n][:, x0 % n]
        d = lat[(y0 + 1) % n][:, (x0 + 1) % n]
        out += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        tot += amp
        amp *= .5
    return out / tot


def _normal(height, strength):
    """OpenGL tangent-space normal map from a periodic height field"""
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * .5 * strength
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * .5 * strength
    n = np.dstack([-dx, dy, np.ones_like(height)])        # (rows run down the image: +y up in UV)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * .5 + .5


def weave(threads, pattern, rng, size=SIZE, bump=1.0):
    """a woven cloth: `threads` warp and weft threads per repeat, pattern(i, j) -> warp on top. Returns height,
    per-pixel thread tone (each thread its own shade) and a fibre mask"""
    p = size / threads
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    i = np.floor(x / p).astype(int)                       # warp thread (runs along v)
    j = np.floor(y / p).astype(int)                       # weft thread (runs along u)
    fx, fy = (x / p) % 1.0, (y / p) % 1.0
    warp_top = pattern(i, j)
    # a thread's round profile across, rising over / dipping under its crossings along
    prof_w = np.clip(np.cos((fx - .5) * math.pi), 0, 1) ** .7      # (clipped: a hair below 0 ** .7 is NaN)
    prof_f = np.clip(np.cos((fy - .5) * math.pi), 0, 1) ** .7
    along_w = .55 + .45 * np.cos((fy - .5) * math.pi)
    along_f = .55 + .45 * np.cos((fx - .5) * math.pi)
    hw = prof_w * along_w
    hf = prof_f * along_f
    height = np.where(warp_top, hw + .25, hf + .25)
    tone_w = rng.uniform(.88, 1.10, threads)[i % threads]
    tone_f = rng.uniform(.90, 1.08, threads)[j % threads]
    tone = np.where(warp_top, tone_w, tone_f)
    # fibre: fine streaks along each thread
    fib = rng.uniform(-1, 1, (size, size)).astype(np.float32)
    fib_w = (fib + np.roll(fib, 1, 0) + np.roll(fib, 2, 0) + np.roll(fib, -1, 0)) / 4
    fib_f = (fib + np.roll(fib, 1, 1) + np.roll(fib, 2, 1) + np.roll(fib, -1, 1)) / 4
    fibre = np.where(warp_top, fib_w, fib_f)
    return height * bump + .06 * fibre, tone, fibre


def save(path, rgb, alpha=None, srgb=True):
    H, W = rgb.shape[:2]
    a = np.ones((H, W), np.float32) if alpha is None else alpha
    img = np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)])[::-1]
    name = os.path.splitext(os.path.basename(path))[0]
    im = bpy.data.images.get(name) or bpy.data.images.new(name, W, H, alpha=alpha is not None)
    if im.size[0] != W:
        im.scale(W, H)
    im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    im.pixels.foreach_set(img.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    return path


def make(kind, colour, rough, out_dir, prefix, metal=0.0, seed=1):
    """writes <prefix>_<kind>_c/_n/_m.png in out_dir (skips existing) and returns the three paths"""
    paths = [os.path.join(out_dir, f"{prefix}_{kind}_{s}.png") for s in ("c", "n", "m")]
    if all(os.path.exists(p) for p in paths):
        return paths
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.RandomState(seed)
    col = np.array(colour, np.float32)
    alpha = None
    if kind == "twill":                                   # 2/1 twill: the warp floats over two wefts, steps by one
        h, tone, fib = weave(256, lambda i, j: (i - j) % 3 != 0, rng)
        mott = _noise((SIZE, SIZE), 3, rng, 4)            # waxed cloth: soft darker / lighter patches
        slub = np.clip(_noise((SIZE, SIZE), 24, rng, 2), 0, 1) ** 3
        alb = col * (tone * (.92 + .08 * mott) * (1 + .25 * slub))[..., None]
        r = np.clip(rough + .10 * (1 - h) + .08 * mott - .06 * fib, .3, 1)
        nrm = _normal(h, 2.4)
    elif kind == "ripstop":                               # plain weave, a heavier thread every 16
        h, tone, fib = weave(320, lambda i, j: (i + j) % 2 == 0, rng, bump=.6)
        y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
        p = SIZE / 320 * 16
        grid = (np.exp(-(((x % p) - p * .5) / 2.2) ** 2) + np.exp(-(((y % p) - p * .5) / 2.2) ** 2)).clip(0, 1)
        h = h + .9 * grid
        alb = col * (tone * (1 + .10 * grid))[..., None]
        r = np.clip(rough - .12 * grid + .05 * fib, .2, 1)
        nrm = _normal(h, 2.0)
    elif kind == "canvas":                                # coated: a fine pebble under a soft sheen
        peb = _noise((SIZE, SIZE), 90, rng, 2)
        h = np.abs(peb) ** .6 + .3 * _noise((SIZE, SIZE), 8, rng, 3)
        alb = col * (.95 + .07 * _noise((SIZE, SIZE), 5, rng, 3))[..., None]
        r = np.clip(rough + .12 * peb, .2, 1)
        nrm = _normal(h, 1.6)
    elif kind == "tape":
        h, tone, fib = weave(200, lambda i, j: (i + j) % 2 == 0, rng)
        alb = col * tone[..., None]
        r = np.clip(rough + .05 * fib, .2, 1)
        nrm = _normal(h, 2.0)
    elif kind == "leather":                               # oiled full grain: fine pebble, pores, soft creases
        peb = _noise((SIZE, SIZE), 120, rng, 2)
        pores = (rng.uniform(0, 1, (SIZE, SIZE)) > .985).astype(np.float32)
        crease = np.abs(_noise((SIZE, SIZE), 6, rng, 4))
        line = 1 - np.clip(crease * 14, 0, 1)                # thin, soft creases (not cracks)
        h = .55 * np.abs(peb) ** .7 - .35 * pores + .18 * line
        mott = _noise((SIZE, SIZE), 4, rng, 4)
        alb = col * (.94 + .07 * mott - .02 * line)[..., None]
        r = np.clip(rough + .08 * peb + .06 * line + .05 * mott, .25, 1)
        nrm = _normal(h, 2.2)
    elif kind == "rubber":                                # moulded rubber: a fine stipple
        st = _noise((SIZE, SIZE), 200, rng, 1)
        h = .4 * st + .2 * _noise((SIZE, SIZE), 10, rng, 3)
        alb = col * (.96 + .05 * _noise((SIZE, SIZE), 6, rng, 3))[..., None]
        r = np.clip(rough + .05 * st, .3, 1)
        nrm = _normal(h, 1.4)
    elif kind == "braid":                                 # a braided lace: diagonal strands both ways (along v)
        y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32) / SIZE
        a = np.sin((y * 24 + x * 2) * 2 * math.pi)
        b = np.sin((y * 24 - x * 2) * 2 * math.pi)
        h = np.maximum(a, b) * .5 + .5
        alb = col * (.85 + .25 * h)[..., None]
        r = np.clip(rough - .1 * h, .3, 1)
        nrm = _normal(h, 3.0)
    elif kind == "knit":                                  # jersey: columns of V-shaped loops
        y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
        cols, rows = 220, 300
        u = (x / SIZE * cols) % 1.0
        v = (y / SIZE * rows) % 1.0
        leg = np.abs(u - .5) * 2                            # the V: each loop's two legs lean in toward its middle
        vv = np.abs(v - .5) * 2
        h = np.clip(1 - np.abs(leg - vv * .6 - .25) * 2.2, 0, 1) ** .8
        tone = 1 + .05 * _noise((SIZE, SIZE), 30, rng, 2)
        alb = col * tone[..., None] * (.92 + .10 * h)[..., None]
        r = np.clip(rough + .06 * (1 - h), .3, 1)
        nrm = _normal(h, 1.8)
    elif kind == "polymer":                               # moulded plate: smooth satin, faint micro-scratches
        y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
        h = .15 * _noise((SIZE, SIZE), 6, rng, 3)
        for _ in range(90):                                # a few fine straight scratches
            x0, y0 = rng.uniform(0, SIZE, 2)
            a = rng.uniform(0, math.pi)
            L = rng.uniform(20, 140)
            d = np.abs((x - x0) * math.sin(a) - (y - y0) * math.cos(a))
            along = (x - x0) * math.cos(a) + (y - y0) * math.sin(a)
            h -= .25 * np.exp(-(d / .7) ** 2) * ((along > 0) & (along < L))
        alb = col * (.97 + .04 * _noise((SIZE, SIZE), 4, rng, 3))[..., None]
        r = np.clip(rough + .10 * np.clip(-h, 0, 1) + .03 * _noise((SIZE, SIZE), 20, rng, 2), .15, 1)
        nrm = _normal(h, .8)
    elif kind == "thread":                                # 3 stitches per repeat along v, the thread twisted
        S = 512
        y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
        per = (y * 3) % 1.0
        on = (per > .08) & (per < .80)                    # a stitch, then the gap where it dives in
        across = np.abs(x - .5) * 2
        body = np.clip(1 - across ** 2 / .55, 0, 1)
        twist = .5 + .5 * np.sin((y * 3 * 18 + x * 6) * 2 * math.pi)
        end = np.clip(np.minimum(per - .08, .80 - per) / .06, 0, 1)
        h = body * (.75 + .25 * twist) * end * on
        alpha = (body > .05) * on * np.clip(end * 2, 0, 1)
        alb = np.broadcast_to(col, (S, S, 3)) * (.8 + .25 * twist)[..., None]
        r = np.full((S, S), rough, np.float32) - .1 * twist
        nrm = _normal(h, 4.0)
    else:
        raise ValueError(kind)
    for arr in (alb, nrm, r):
        assert np.isfinite(arr).all(), f"{kind}: non-finite texels"
    mr = np.dstack([np.ones_like(r), r, np.full_like(r, metal)])
    save(paths[0], alb, alpha)
    save(paths[1], nrm, srgb=False)
    save(paths[2], mr, srgb=False)
    return paths


def texture_material(name, paths, alpha_clip=None):
    """a Blender material with the three maps wired the way the glTF exporter reads them"""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(n)
    b = nt.nodes.get("Principled BSDF")
    c = nt.nodes.new("ShaderNodeTexImage")
    c.image = bpy.data.images.load(paths[0], check_existing=True)
    nt.links.new(c.outputs["Color"], b.inputs["Base Color"])
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(paths[1], check_existing=True)
    n.image.colorspace_settings.name = 'Non-Color'
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    r = nt.nodes.new("ShaderNodeTexImage")
    r.image = bpy.data.images.load(paths[2], check_existing=True)
    r.image.colorspace_settings.name = 'Non-Color'
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(r.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    if alpha_clip is not None:
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = 'GREATER_THAN'
        gt.inputs[1].default_value = alpha_clip
        nt.links.new(c.outputs["Alpha"], gt.inputs[0])
        nt.links.new(gt.outputs[0], b.inputs["Alpha"])
        m.use_backface_culling = False
    return m


def world_uvs(o, tile, angle=66.0):
    """UVs for a cloth piece with none: unwrapped by angle, then scaled so one UV unit is `tile` metres everywhere"""
    import bmesh
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=.002, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    a3 = sum(f.calc_area() for f in bm.faces)
    a2 = 0.0
    for f in bm.faces:
        pts = [l[uv].uv for l in f.loops]
        a2 += abs(sum(pts[k].x * pts[(k + 1) % len(pts)].y - pts[(k + 1) % len(pts)].x * pts[k].y
                      for k in range(len(pts)))) / 2
    k = math.sqrt(a3 / max(a2, 1e-12)) / tile
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = l[uv].uv * k
    bm.to_mesh(me)
    bm.free()


TEXTURED = {                       # material name -> (cloth, alpha clip)
    "orion_coat": ("twill", None),
    "orion_white": ("twill", None),
    "orion_lining": ("ripstop", None),
    "orion_strap": ("canvas", None),
    "orion_zip": ("tape", None),
    "orion_stitch": ("thread", .5),
    "orion_leather": ("leather", None),
    "orion_sole": ("rubber", None),
    "orion_midsole": ("rubber", None),
    "orion_lace": ("braid", None),
    "orion_cloth": ("ripstop", None),
    "orion_black": ("knit", None),
    "orion_plate": ("polymer", None),
}


def apply(T, out_dir):
    """gives the outfit's cloth materials their textures (made once per body, in its own folder and names)"""
    import zlib
    from wardrobe import PALETTE
    prefix = f"hero_{T['sex']}"
    for name, (kind, clip) in TEXTURED.items():
        if name not in bpy.data.materials:
            continue
        col, rough, metal = PALETTE[name]
        paths = make(kind, col, rough, out_dir, f"{prefix}_{name[6:]}", metal, seed=zlib.crc32(name.encode()) % 9973)
        texture_material(name, paths, clip)
