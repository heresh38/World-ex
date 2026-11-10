"""The outfit's finish: nothing worn is one flat, factory-new colour. Run on every wardrobe piece (after it is built
and skinned); writes the corner colour attribute `Col` that the export carries as the vertex colour, which Unreal's
master material (M_SOStandard) reads as:
  RGB   multiplies the material colour: the paint scheme on the hard plates (their material colour is a light
        neutral, the scheme lives here), per-plate tone variation, grime in the recesses, dust on upward faces, dirt
        rising toward the ground on boots, trouser hems and the coat's hem, a little fading on cloth
  A     1 - edge wear: convex edges and plate rims rubbed through to bare metal, broken up by noise, more where
        things knock (upper and front-facing surfaces); the material instances set how far (EdgeWear, WearMetal) and
        add scratches and grime from the shared wear mask (import_assets.py ARMOUR_WEAR)
Each body has its own scheme (his gunmetal with desert-tan accents and a signal-orange marking, hers off-white with
the deep blue of her jacket's lining); the zones are picked per piece in object space.
"""
import math
import numpy as np
import bpy

F32 = np.float32
HARD = ("orion_plate", "orion_plate_white", "orion_steel")
PLATE = ("orion_plate", "orion_plate_white")
# the plate materials are a light neutral (wardrobe.PALETTE); these are the actual paint colours, as multipliers
SCHEME = {
    "male": dict(primary=(.36, .37, .40), accent=(.80, .66, .48), mark=(.95, .40, .10)),
    "female": dict(primary=(1.0, 1.0, .985), accent=(.16, .30, .70), mark=(.06, .06, .07)),
}


def _hash(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF).astype(F32) / 65535.0


def noise(P, scale, seed=0):
    """smooth value noise in [0, 1] (trilinear over a hashed lattice)"""
    q = P / scale
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(P), F32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm(P, scale, seed=0, octaves=3):
    v, a, tot = 0.0, 1.0, 0.0
    for k in range(octaves):
        v = v + a * noise(P, scale / (2 ** k), seed + k * 17)
        tot += a
        a *= .5
    return v / tot


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def islands(me):
    """connected component per vertex (each plate, strap or part its own island)"""
    n = len(me.vertices)
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    ed = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    for a, b in ed.reshape(-1, 2):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return np.array([find(i) for i in range(n)])


def convexity(me, co, no):
    ed = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    d = co[ed[:, 1]] - co[ed[:, 0]]
    L = np.linalg.norm(d, axis=1) + 1e-9
    d /= L[:, None]
    conv = np.zeros(len(co))
    cnt = np.zeros(len(co))
    np.add.at(conv, ed[:, 0], -(no[ed[:, 0]] * d).sum(1))
    np.add.at(conv, ed[:, 1], (no[ed[:, 1]] * d).sum(1))
    np.add.at(cnt, ed[:, 0], 1)
    np.add.at(cnt, ed[:, 1], 1)
    return conv / np.maximum(cnt, 1)


def diffuse(me, val, iters, keep=.62):
    """spread a per-vertex value over the mesh: each pass a vertex takes max(itself, keep x its neighbours' mean),
    so a band fades in from the edges a few rings deep"""
    ed = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    cnt = np.zeros(len(val))
    np.add.at(cnt, ed[:, 0], 1)
    np.add.at(cnt, ed[:, 1], 1)
    v = val.astype(F32).copy()
    for _ in range(iters):
        acc = np.zeros(len(v))
        np.add.at(acc, ed[:, 0], v[ed[:, 1]])
        np.add.at(acc, ed[:, 1], v[ed[:, 0]])
        v = np.maximum(v, keep * acc / np.maximum(cnt, 1))
    return v


# the helmets are painted to their outfits: his in the coat's charcoal, hers in the jacket's white, both with the
# lining's blue down the spine (hers along the peak as well)
HELMET = {
    "male": dict(primary=(.082, .084, .092), accent=(.060, .130, .420), mark=(.082, .084, .092)),
    "female": dict(primary=(1.0, 1.0, .985), accent=(.16, .30, .70), mark=(1.0, 1.0, .985)),
}


def accent_zone(piece, P, isl, sex):
    """0..1 accent paint per vertex, by piece (object space: +X her/his left, -Y forward, +Z up)"""
    m = sex == "male"
    a = np.zeros(len(P), F32)
    name = piece.name
    if name.startswith("C_head__orion_helmet"):
        # the brow ridge and the left cheek / ear plate in the accent; a marking stripe down the right of the crown
        top = P[:, 2].max()
        # whole plates take the accent (a zone painted across a plate ends in a ragged line): the spine, and on hers
        # the peak over the shield
        ids, inv = np.unique(isl, return_inverse=True)
        cnt = np.maximum(np.bincount(inv), 1).astype(F32)
        mean = lambda v: (np.bincount(inv, weights=v) / cnt)[inv]
        ax, sx_, my, mz = mean(np.abs(P[:, 0])), mean(P[:, 0]), mean(P[:, 1]), mean(P[:, 2])
        a = np.maximum(a, ((ax < .008) & (mz > top - .09)).astype(F32))
        if not m:
            a = np.maximum(a, ((np.abs(sx_) < .01) & (ax > .02) & (my < P[:, 1].min() + .07) & (mz > top - .125) & (mz < top - .075)).astype(F32))
    elif name.startswith("C_hands__orion_armoured"):         # the knuckle guard and finger plates
        a = np.maximum(a, (P[:, 2] > P[:, 2].min() + .02).astype(F32) * 0.6)
    return a


def mark_zone(piece, P, sex):
    """a small painted marking (a chevron on the helmet's right side)"""
    if not piece.name.startswith("C_head__orion_helmet"):
        return np.zeros(len(P), F32)
    top = P[:, 2].max()
    x, y, z = P[:, 0], P[:, 1], P[:, 2] - (top - .08)
    chevron = (x < -.06) & (np.abs(y + .015 - np.abs(z) * .9) < .006) & (np.abs(z) < .022)
    return chevron.astype(F32)


def apply(piece, T, log=print):
    me = piece.data
    sex = T["sex"]
    S = HELMET[sex] if piece.name.startswith("C_head__orion_helmet") else SCHEME[sex]
    n = len(me.vertices)
    if not n:
        return
    co = np.empty(n * 3, F32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    no = np.empty(n * 3, F32)
    me.vertices.foreach_get("normal", no)
    no = no.reshape(-1, 3)
    conv = convexity(me, co, no)
    isl = islands(me)
    # per island: a slight tone shift (no two plates quite the same), and its own wear seed
    ids, inv = np.unique(isl, return_inverse=True)
    rng = np.random.default_rng(abs(hash(piece.name)) % (2 ** 32))
    tone = (1.0 + rng.uniform(-.055, .045, len(ids)))[inv].astype(F32)
    hue = rng.uniform(-.02, .02, (len(ids), 3))[inv].astype(F32)
    ground = smooth(.42, .02, co[:, 2])                        # 1 at the ground .. 0 above the knee
    up = np.clip(no[:, 2], 0, 1)
    front = np.clip(-no[:, 1], 0, 1)
    breakup = fbm(co, .05, 3)
    chips = fbm(co, .022, 7, octaves=2)
    cavity = smooth(.02, .16, -conv)
    edge = smooth(.08, .30, conv)
    band = diffuse(me, edge, 4)                              # the rubbed band along every rim and edge
    acc = accent_zone(piece, co, isl, sex)
    mark = mark_zone(piece, co, sex)
    # vertex -> material via the corners
    npoly = len(me.polygons)
    mi = np.empty(npoly, np.int64)
    me.polygons.foreach_get("material_index", mi)
    lt = np.empty(npoly, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    vi = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", vi)
    lm = np.repeat(mi, lt)
    names = [s.material.name if s.material else "" for s in piece.material_slots]
    out = np.ones((len(me.loops), 4), F32)
    for k, name in enumerate(names):
        sel = lm == k
        if not sel.any():
            continue
        v = vi[sel]
        rgb = np.ones((len(v), 3), F32)
        a = np.ones(len(v), F32)
        if name in PLATE:
            base = np.array(S["primary"], F32) * (1 - acc[v, None]) + np.array(S["accent"], F32) * acc[v, None]
            base = base * (1 - mark[v, None]) + np.array(S["mark"], F32) * mark[v, None]
            rgb = base * tone[v, None] * (1 + hue[v])
            expo = .7 + .5 * up[v] + .3 * front[v]               # what gets knocked: upper and front faces
            wear = band[v] ** 1.4 * (.25 + .95 * breakup[v]) * expo
            wear = np.maximum(wear, smooth(.62, .80, chips[v]) * band[v] * .8)   # chips, only near the edges
            a = 1 - np.clip(wear, 0, 1)
        elif name == "orion_steel":
            rgb = np.ones((len(v), 3), F32) * tone[v, None]
            a = 1 - np.clip(edge[v] * (.5 + .8 * breakup[v]), 0, 1)
        elif name.startswith("orion_glow") or name.startswith("hair") or name.startswith("orion_visor"):
            pass
        else:                                                # cloth, leather, rubber: fading and soiling
            fade = 1 + .07 * (up[v] * breakup[v])                # sun-faded where it faces up
            rgb = np.ones((len(v), 3), F32) * (tone[v, None] * .5 + .5) * fade[:, None]
        # grime in the recesses, dust on what faces up, dirt from the ground
        g = cavity[v] * (.25 + .35 * breakup[v])
        rgb = rgb * (1 - g[:, None] * np.array((.55, .58, .62), F32))
        dust = up[v] * smooth(.45, .9, fbm(co[v], .03, 11, 2)) * .22
        rgb = rgb * (1 - dust[:, None]) + np.array((.62, .56, .46), F32) * dust[:, None] * rgb.mean(1, keepdims=True) * 1.6
        dirt = ground[v] * (.35 + .45 * breakup[v])
        rgb = rgb * (1 - dirt[:, None] * np.array((.42, .48, .58), F32))
        out[sel, :3] = np.clip(rgb, 0, 1)
        out[sel, 3] = np.clip(a, 0, 1)
    attr = me.color_attributes.get("Col")
    if attr is not None and (attr.domain != "CORNER" or attr.data_type != "BYTE_COLOR"):
        me.color_attributes.remove(attr)                    # (pieces cut from the body inherit its per-vertex Col)
        attr = None
    if attr is None:
        attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    attr.data.foreach_set("color", out.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = list(me.color_attributes).index(attr)
    log(f"finish: {piece.name} paint / wear / grime on {len(me.loops)} corners")
