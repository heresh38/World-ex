"""The world's material sets, drawn through the texture engine (pbr.py) to the owner's texture rules
(docs/art/TEXTURE_RULES.md). These replace what descended from the old browser build (textures.py and
nexus_textures.py baked them through Cycles at 512 / 1024 px, colour and a nearly flat normal): the same names, so
nothing that uses them is built again.

  Nexus Prime's kit (nexus.py, box-mapped 4 to 8 m a tile; drawn for 6):
    nx_stone    dark slate ashlar: riven faces in terraces, quartz veins, fractures, chipped arrises, recessed
                joints, mineral runs down the face, lichen by the joints
    nx_paving   plaza slabs, 2 x 1 m: a honed dark stone you can see the grains of, paths worn smoother, cracked
                slabs, pits, stains, dirt along the joints
    nx_panel    hull plate: panels with rolled edges and seams, a rivet every 20 cm along each edge, brushed,
                scratched, edges rubbed bright, oxidation at the seams, oil run down from them, dents
    nx_trim     brushed steel trim: drawn out one way, handled (smudges in the roughness), freckled, dented
    nx_window   a facade's bays, 4 x 3 a tile: frames standing proud of the glass, dark panes with the dirt run
                down them, lit rooms (blinds, a ceiling's light, what stands in the room) and an emissive map of
                the lit glass only
    nx_rock     cliff: strata of different hardness standing out as ledges, joints across them, pitting, mineral
                runs, lichen
  The reliquary (vanthos.py; near white, the material's colour multiplies them):
    panel       plate, as nx_panel in a pale finish
    concrete    cast concrete: sand and aggregate, bug holes, hairline cracks, the form boards' lines, water runs

Run: blender --background --python tools/blender/world_maps.py [-- name ...]     (PBR_SIZE=1024 for a quick look)
then SO_IMPORT_ONLY=worldmaps brings them into the game.
"""
import math
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pbr import F32, Tile, above, hexc, mix, smooth                # noqa: E402


def pits(T, share, size_px=1.0):
    """sparse small holes: 0..1"""
    p = (T.rng.uniform(0, 1, (T.Z, T.Z)) > 1 - share).astype(F32)
    return np.clip(T.blur_px(p, size_px) * (4 + 5 * size_px * size_px), 0, 1)


def panel_uv(T, nx, ny, stagger):
    """metres from each panel's own corner (across, down) and the panel's size"""
    Z = T.Z
    v = (np.arange(Z, dtype=F32)[:, None] + .5) / Z * ny
    u = (np.arange(Z, dtype=F32)[None, :] + .5) / Z * nx + np.floor(v) * stagger
    W, H = T.m / nx, T.m / ny
    return (u - np.floor(u)) * W, (v - np.floor(v)) * H * np.ones((1, Z), F32), W, H


def rivets(T, nx, ny, stagger, inset=.030, pitch=.20, r=.007):
    """a row of rivet heads along every edge of every panel: 0..1 domes"""
    pu, pv, W, H = panel_uv(T, nx, ny, stagger)
    out = np.zeros((T.Z, T.Z), F32)
    for across, along, size in ((np.minimum(pu, W - pu), pv, H), (np.minimum(pv, H - pv), pu, W)):
        n = max(1, round(size / pitch))
        a = (along / (size / n)) % 1.0 - .5
        d = np.hypot(across - inset, a * (size / n))
        out = np.maximum(out, np.clip(1 - (d / r) ** 2, 0, 1) ** .5)
    return out


# ------------------------------------------------------------------------------------------------ stone

def nx_stone():
    T = Tile("nx_stone", 6.0)
    J, edge, ra, rb = T.grid(4, 8, stagger=.5, joint=.010, wander=.004)
    cleft = T.noise(.40, 5)
    terr = T.blur_px(np.floor(cleft * 6) / 6, 1.2)               # riven slate: the face comes away in thin sheets
    fine = T.noise(.025, 3)
    grain = T.grain(1)
    chip = smooth(.034, .004, edge) * above(T.noise(.07, 3), .40, .25)      # arrises knocked off
    veins = T.cracks(.55, share=.16, width=.0016)
    frac = T.cracks(1.0, share=.20, width=.0012)
    hole = pits(T, .0012, 1.5)
    rain = T.streaks(70, (.3, 2.4), (.01, .09), (.25, 1.0)) * above(T.noise(1.2, 3), .5, .5)     # (in places, not everywhere)
    lich = above(T.noise(.22, 4), .12, .2) * smooth(.16, .01, edge)
    big = T.noise(1.6, 3)
    _, _, mica = T.cells(.0035)                                   # the slate's own flecks, 3 to 4 mm
    lam = T.brushed(.20)                                          # and its lamination, lying along the block
    alb = hexc('#2b303a') * (1 + .26 * (ra - .5) + .10 * big + .07 * fine + .05 * grain + .09 * lam)[..., None]
    alb = mix(alb, hexc('#4a5262'), smooth(.86, .97, mica) * .55)
    alb = mix(alb, hexc('#171a20'), smooth(.14, .03, mica) * .5)
    alb = alb * (1 + (rb - .5)[..., None] * np.array((.05, .0, -.06), F32))     # (some blocks a shade warmer, some bluer)
    alb = mix(alb, hexc('#424958'), smooth(-.2, .6, terr) * .28)  # the sheets that stand highest are rubbed paler
    alb = mix(alb, hexc('#98a0a8'), veins * .55)
    alb = mix(alb, hexc('#0f1116'), frac * .85)
    alb = mix(alb, hexc('#767e88'), chip * .55)                   # slate breaks pale
    alb = mix(alb, hexc('#15171a'), J * .9)
    alb = mix(alb, hexc('#a9b0a8'), rain * .20)                   # what the rain leaves
    alb = mix(alb, hexc('#5c6442'), lich * .55)
    rough = .60 + .10 * fine + .10 * chip + .20 * J - .12 * smooth(.2, .9, terr) + .08 * rain + .16 * lich - .10 * smooth(.86, .97, mica)
    T.write(alb, [(terr, .0032), (cleft, .0040), (fine, .0006), (grain, .00010), (lam, .00025), (mica - .5, .00012), (-chip, .0065), (-frac, .0030), (-J, .0130),
                  (veins, .0003), (ra - .5, .0045), (-hole, .0020), (lich, .0006)], rough, 0.0,
            relief=2.4, dust=(hexc('#6b6a66'), .35), legacy_normal_jpg=True)


def nx_paving():
    T = Tile("nx_paving", 6.0)
    J, edge, ra, rb = T.grid(3, 6, stagger=.5, joint=.006, wander=.002)
    _, _, cid = T.cells(.0045)                                    # the stone's own grains, 4 to 5 mm
    big = T.noise(2.0, 3)
    path = above(T.noise(1.3, 3), .42, .35)                       # where feet have gone: smoother, a shade paler
    crack = T.cracks(1.5, share=.12, width=.0016)
    hole = pits(T, .0010, 1.2)
    stain = above(T.noise(.45, 4), .07, .2)
    ring = T.dents(40, (.03, .12))
    ring = smooth(.25, .40, ring) * smooth(.60, .45, ring)        # the edge a dried puddle leaves
    scr = T.lines(700, (.05, .7), (.0004, .0010))
    by_joint = smooth(.06, .0, edge)
    alb = hexc('#353a43') * (1 + .18 * (ra - .5) + .07 * big)[..., None]
    alb = mix(alb, hexc('#5d646e'), smooth(.78, .95, cid) * .65)
    alb = mix(alb, hexc('#1c1f24'), smooth(.22, .05, cid) * .65)
    alb = mix(alb, hexc('#474d57'), path * .30)
    alb = mix(alb, hexc('#17191c'), np.clip(stain * .6 + by_joint * .45 + J * .9, 0, 1))
    alb = mix(alb, hexc('#0e0f12'), crack * .85)
    alb = mix(alb, hexc('#8a8f96'), np.clip(scr * .5 + ring * .25, 0, 1) * .5)
    rough = .50 - .24 * path + .22 * J + .16 * by_joint + .10 * scr + .14 * stain + .10 * (cid - .5) * (1 - path)
    T.write(alb, [(-J, .0085), (ra - .5, .0035), (cid - .5, .00022), (-crack, .0030), (-hole, .0016), (-scr, .00022),
                  (T.noise(.7, 3), .0016), (rb - .5, .0010)], rough, 0.0, relief=2.2, dust=(hexc('#5f5c55'), .45), legacy_normal_jpg=True)


def nx_rock():
    T = Tile("nx_rock", 8.0)
    Z = T.Z
    v = (np.arange(Z, dtype=F32)[:, None] + .5) / Z
    nb = 17                                                       # the beds: no two the same thickness, lying not quite level
    thick = T.rng.uniform(.25, 2.4, nb) ** 1.5
    top = np.concatenate([[0.0], np.cumsum(thick) / thick.sum()]).astype(F32)
    s = (v + T.noise(3.0, 3) * .055 + T.noise(.5, 3) * .010) % 1.0
    bed = np.clip(np.searchsorted(top, s, side='right') - 1, 0, nb - 1)
    f = (s - top[bed]) / (top[bed + 1] - top[bed])
    hard = T.rng.uniform(0, 1, nb).astype(F32)[bed]               # each bed its own hardness: the hard ones stand out
    tone = T.rng.uniform(0, 1, nb).astype(F32)[bed]
    lip = smooth(0, .12, f) * smooth(1, .78, f)                   # a bed's face, rounded where it meets the next
    joint = T.cracks(.9, share=.45, width=.0030, warp=.25)
    frac = T.cracks(.25, share=.25, width=.0012)
    erod = T.noise(.30, 5)
    fine = T.noise(.03, 3)
    grain = T.grain(1)
    hole = pits(T, .0020, 2.0)
    rain = T.streaks(60, (.5, 3.0), (.02, .12), (.25, 1.0))
    lich = above(T.noise(.35, 4), .14, .2)
    moss = above(T.noise(.5, 4), .08, .2) * smooth(.2, .0, f)     # where a ledge holds water
    alb = mix(np.zeros((Z, Z, 3), F32) + hexc('#4d4b48'), hexc('#716a5e'), tone)
    alb = alb * (1 + .10 * erod + .08 * fine + .05 * grain)[..., None]
    alb = mix(alb, hexc('#2c2a28'), smooth(.25, .0, f) * .5)      # the shadowed foot of each bed
    alb = mix(alb, hexc('#161514'), np.clip(joint + frac * .8, 0, 1) * .85)
    alb = mix(alb, hexc('#9a8f7c'), rain * .25)
    alb = mix(alb, hexc('#8a8f5e'), lich * .45)
    alb = mix(alb, hexc('#3d4a2a'), moss * .7)
    rough = .80 + .08 * fine - .10 * hard * lip + .10 * lich + .12 * moss
    T.write(alb, [(hard * lip, .060), (erod, .018), (fine, .0025), (grain, .0003), (-joint, .030), (-frac, .006), (-hole, .004),
                  (moss, .004), (T.noise(2.5, 3), .05)], rough, 0.0, relief=1.2, dust=(hexc('#7c7568'), .4), legacy_normal_jpg=True)


def concrete():
    T = Tile("concrete", 4.0)
    sand = T.grain(1)
    agg_d, _, agg_id = T.cells(.012)                              # aggregate just under the skin
    agg = smooth(.55, .15, agg_d)
    big = T.noise(1.5, 4)
    mott = T.noise(.30, 4)
    bug = (pits(T, .0009, 2.0) + pits(T, .0003, 4.0)) * (.15 + .85 * above(T.noise(.7, 3), .4, .5))   # bug holes: air caught against the form, in clusters
    crack = T.cracks(.9, share=.16, width=.0009)
    Z = T.Z
    y = (np.arange(Z, dtype=F32)[:, None] + .5) / Z * T.m
    board = np.abs(((y / .60) % 1.0) - .5) * 2                     # the form boards, 60 cm high
    seam = smooth(.985, 1.0, board) * np.ones((1, Z), F32)
    wood = T.brushed(.6) * (1 - seam)                              # the boards' grain, printed in the face
    rain = T.streaks(46, (.4, 2.6), (.02, .12), (.25, 1.0))
    damp = above(T.noise(.8, 3), .14, .25)
    wear = above(T.noise(.5, 4), .30, .3)
    alb = np.zeros((Z, Z, 3), F32) + hexc('#c2beb6')
    alb = alb * (1 + .07 * big + .06 * mott + .035 * sand + .03 * wood)[..., None]
    alb = mix(alb, hexc('#9d9a94'), agg * wear * .5)               # worn: the aggregate shows
    alb = mix(alb, hexc('#6f6c66'), np.clip(bug, 0, 1) * .8)
    alb = mix(alb, hexc('#4a4743'), crack * .85)
    alb = mix(alb, hexc('#8b8477'), rain * .30)
    alb = mix(alb, hexc('#99958c'), damp * .35)
    alb = mix(alb, hexc('#8c8982'), seam * .5)
    rough = .86 - .10 * wear + .05 * sand - .08 * damp + .06 * rain
    T.write(alb, [(sand, .00018), (agg * wear, .0005), (mott, .0012), (big, .003), (-np.clip(bug, 0, 1), .0035), (-crack, .0020),
                  (seam, .0015), (wood, .00025)], rough, 0.0, dust=(hexc('#8f8a80'), .4), legacy_normal_jpg=True)


# ------------------------------------------------------------------------------------------------ metal

def plate(name, metres, nx, ny, base, bare, seam, tone=.10):
    T = Tile(name, metres)
    J, edge, ra, rb = T.grid(nx, ny, stagger=.5, joint=.008)
    roll = smooth(0, .014, edge)                                  # each panel's rolled edge
    riv = rivets(T, nx, ny, .5)
    brush = T.brushed(.5)
    cross = T.brushed(.12, axis=0)
    big = T.noise(1.5, 3)
    scr = T.lines(1100, (.03, .5), (.0003, .0009), along=.6)
    deep = T.lines(46, (.1, .7), (.0010, .0022))
    oil = T.streaks(46, (.3, 2.2), (.01, .07), (.25, 1.0))
    ox = above(T.noise(.28, 4), .14, .22) * smooth(.20, .0, edge)
    rub = smooth(.022, .003, edge) * (.35 + .65 * above(T.noise(.09, 3), .55, .4))      # edges rubbed bright
    rub = np.maximum(rub, riv * .7)
    dent = T.dents(34, (.012, .05))
    smear = above(T.noise(.10, 3), .22, .3)                       # handled: prints and smears in the roughness
    alb = np.zeros((T.Z, T.Z, 3), F32) + hexc(base)
    alb = alb * (1 + tone * (ra - .5) * 2 + .10 * brush + .04 * cross + .05 * big)[..., None]
    alb = mix(alb, hexc(bare), np.clip(.6 * scr + deep + rub * .75, 0, 1) * .8)
    alb = mix(alb, hexc('#6f4a30'), ox * .65)
    alb = mix(alb, hexc('#1f2226'), oil * .45)
    alb = mix(alb, hexc(seam), J * .92)
    rough = .42 + .12 * brush + .05 * cross - .16 * rub - .12 * scr + .32 * ox - .12 * oil + .22 * J + .10 * smear
    metal = np.clip(1 - .85 * ox - .6 * J, 0, 1)
    T.write(alb, [(roll, .0030), (-J, .0100), (riv, .0040), (brush, .00005), (cross, .00002), (-scr, .00007), (-deep, .0004),
                  (-dent, .0030), (big, .0020), (ox * T.grain(1), .00025)], rough, metal, dust=(hexc('#4d4a45'), .35),
            legacy_normal_jpg=True)


def nx_panel():
    plate("nx_panel", 6.0, 2, 3, '#4a4f57', '#a0a4ac', '#131518')


def panel():
    plate("panel", 4.0, 2, 4, '#c6c9cd', '#eceef0', '#3a3d41', tone=.05)


def nx_trim():
    T = Tile("nx_trim", 6.0)
    brush = T.brushed(1.2)
    fine = T.brushed(.25)
    big = T.noise(1.5, 3)
    scr = T.lines(1500, (.03, .6), (.0003, .0008), along=.75)
    deep = T.lines(50, (.1, .8), (.0010, .0020))
    smear = above(T.noise(.09, 3), .28, .3)
    freck = pits(T, .0030, 1.5) * above(T.noise(.6, 3), .5, .4)   # oxide freckles, in patches
    dent = T.dents(40, (.01, .05))
    band = T.noise(.9, 2)
    alb = np.zeros((T.Z, T.Z, 3), F32) + hexc('#8c8880')
    alb = alb * (1 + .12 * brush + .07 * fine + .05 * big + .04 * band)[..., None]
    alb = mix(alb, hexc('#c9c5bb'), np.clip(.6 * scr + deep, 0, 1) * .7)
    alb = mix(alb, hexc('#5a4634'), freck * .7)
    alb = mix(alb, hexc('#6f6c66'), smear * .22)
    rough = .30 + .14 * brush + .08 * fine - .10 * scr + .16 * smear + .35 * freck
    T.write(alb, [(brush, .00006), (fine, .00003), (-scr, .00007), (-deep, .0004), (-dent, .0025), (big, .0015), (-freck, .0002)],
            rough, np.clip(1 - .8 * freck, 0, 1), dust=(hexc('#55524c'), .25), legacy_normal_jpg=True)


# ------------------------------------------------------------------------------------------------ glass

def nx_window():
    T = Tile("nx_window", 6.0)
    Z = T.Z
    nx, ny = 4, 3
    pu, pv, W, H = panel_uv(T, nx, ny, 0.0)
    v = (np.arange(Z, dtype=F32)[:, None] + .5) / Z * ny
    u = (np.arange(Z, dtype=F32)[None, :] + .5) / Z * nx
    ix, iy = np.floor(u).astype(np.int32) % nx, np.floor(v).astype(np.int32) % ny
    rnd = lambda: T.rng.uniform(0, 1, (ny, nx)).astype(F32)[iy, ix]             # noqa: E731
    r_lit, r_col, r_blind, r_room = rnd(), rnd(), rnd(), rnd()
    edge = np.minimum(np.minimum(pu, W - pu), np.minimum(pv, H - pv))
    frame = smooth(.085, .065, edge)                              # the frame: 7 to 8 cm of metal round each bay
    mull = smooth(.022, .012, np.abs(pu - W / 2)) * (1 - frame)   # a mullion down the middle of the bay
    sill = smooth(.14, .11, H - pv) * (1 - frame)                 # (pv runs down: the foot of the bay)
    glass = (1 - frame) * (1 - mull)
    order = np.argsort(T.rng.uniform(0, 1, nx * ny)).reshape(ny, nx)             # three bays in the twelve are lit
    lit = (order[iy, ix] < 3).astype(F32) * glass
    blind_drop = r_blind * .7                                     # how far the blind is drawn down the bay
    fy = pv / H
    blind = (fy < blind_drop).astype(F32) * glass
    slat = .5 + .5 * np.cos(pv / .024 * 2 * math.pi)              # slats 24 mm apart
    room = T.noise(.5, 3)
    ceiling = np.exp(-((fy - .12) / .05) ** 2) * smooth(.1, .3, np.abs(pu / W - .5) * 2 + .2)
    col_h = T.rng.uniform(.0, .09, (ny, nx, 3)).astype(F32)[iy, ix, np.clip((pu / W * 3).astype(np.int32), 0, 2)]
    things = smooth(.80, .83, fy + col_h) * .6                   # what stands below the sill line in the room, dark against the light
    warm = np.where(r_col[..., None] < .78, hexc('#ffc98a'), hexc('#cfe6f2'))    # lamp light, or a cold tube's
    inside = warm * (.50 + .12 * room + .5 * ceiling)[..., None] * (1 - .35 * smooth(.2, .9, fy))[..., None] * (1 - things)[..., None]
    inside = inside * (1 - blind * (.45 + .25 * slat))[..., None]
    brush = T.brushed(.4)
    dirt = T.streaks(110, (.2, 1.4), (.008, .06), (.25, 1.0))
    grime = above(T.noise(.35, 4), .30, .3)
    refl = T.noise(1.2, 2)
    dark = hexc('#0b1220') * (1 + .5 * refl)[..., None]           # an unlit pane: the night sky's blue in it
    alb = dark * (1 - lit)[..., None] + inside * lit[..., None]
    alb = mix(alb, hexc('#4a5560'), (1 - lit) * glass * blind * (.35 + .25 * slat))       # a drawn blind in a dark room
    alb = mix(alb, hexc('#2c3138') * 1.0, frame + mull)
    alb = alb * (1 + .12 * brush * (frame + mull))[..., None]
    alb = mix(alb, hexc('#3a3832'), np.clip(dirt * .5 + grime * .25, 0, 1) * glass * .55)
    alb = mix(alb, hexc('#1b1d20'), sill * .5)
    emis = inside * (lit * (1 - .45 * np.clip(dirt * .5 + grime * .25, 0, 1)))[..., None]
    rough = .10 + .22 * np.clip(dirt * .6 + grime * .4, 0, 1) * glass + (frame + mull) * (.34 + .1 * brush)
    metal = np.clip(frame + mull, 0, 1) * .9
    T.write(alb, [(frame, .045), (mull, .030), (sill, .012), (brush * (frame + mull), .00005), (T.noise(.8, 2) * glass, .0006)],
            rough, metal, emissive=emis, relief=1.0, cavity=.45, legacy_normal_jpg=True)


SETS = dict(nx_stone=nx_stone, nx_paving=nx_paving, nx_panel=nx_panel, nx_trim=nx_trim, nx_window=nx_window, nx_rock=nx_rock,
            panel=panel, concrete=concrete)

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for n_ in (argv or SETS):
        SETS[n_]()
