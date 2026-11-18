"""The undersuit (Project Orion male): its own layer made ON the body's skin, as the owner asked (2026-11-16: "The
undersuit should follow the body rather than determine its shape"), patterned after the T-pose sheet
(art/reference/player/orion_tpose_bodysuit.png): a charcoal base, lighter grey panels (the chest's wings across the
collarbones, the shoulders' caps, the upper arms' outsides, the flanks, the thighs' outer fronts, the knees, the
shins, the back's broad centre narrowing to the waist, the hips' sides), seams round every panel and down the abdomen's
lines, a high mock-neck collar sewn on at the neckline.

Made in Blender from the finished body: its skin subdivided once more, offset 2.5 mm, cut at the neckline, the wrists
and the ankles along exact lines (`iso_cut`: a cut by whole faces zig-zagged), given a thickness. Each vertex carries
two signed distances in metres (the `suit` colour attribute: red = how far inside a panel, green = how far from a drawn
seam line) and the material draws the borders from them at the pixel: sharp, even lines on any face size (a 0..1 mask
per vertex stepped like stairs across the faces). The collar (`build_collar`) is a tube of its own round the neck,
laid outside the suit, the body and the head (`CLEAR` off the head's skin), bridging the hollows a stretched fabric
bridges (the nape's, the notch's), its foot tucked under the suit along the neckline (`neckline`: where the body
turns up into the neck), its top hugging the neck under the jaw. A proper cut pattern with UVs comes with the game
mesh.
"""
import math
import numpy as np

OFFSET = .0025
THICK = .0015
AXIS = (0.0, -.018)          # the neck's vertical axis (x, y): the neckline and the collar are laid out round it
CLEAR = .0035                # the collar off the head's skin
N_ANG = 144                  # angles round the neck
W_SEAM = .0011               # half-width of a seam's line (metres)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def around(P):
    """angle round the neck's axis (0 = front, pi/2 = his left, pi = back) and the distance from it"""
    P = np.asarray(P)
    dx, dy = P[..., 0] - AXIS[0], P[..., 1] - AXIS[1]
    return np.arctan2(dx, -dy) % (2 * np.pi), np.hypot(dx, dy)


def collar_top(th):
    """the collar's top edge (z, metres): under the chin in front, higher at the nape"""
    return 1.597 + .036 * (1 - np.cos(th)) / 2


def neckline_design(th):
    """the lowest the neckline may lie: just over the jugular notch in front (1.515), on the trapezius beside the neck
    (1.585), a little over the 7th vertebra behind (1.578: at the vertebra itself it hung down the back as a lobe)"""
    return 1.56575 - .0315 * np.cos(th) - .01925 * np.cos(2 * th)


def periodic(vals, th):
    """a value per angle (N_ANG of them, evenly round) read at any angle"""
    a = np.asarray(th) % (2 * np.pi) / (2 * np.pi) * N_ANG
    i0 = np.floor(a).astype(int) % N_ANG
    t = a - np.floor(a)
    return vals[i0] * (1 - t) + vals[(i0 + 1) % N_ANG] * t


def circ_smooth(v, sigma):
    """a value per angle smoothed round the circle (Gaussian, sigma in samples)"""
    k = int(3 * sigma) + 1
    w = np.exp(-.5 * (np.arange(-k, k + 1) / sigma) ** 2)
    w /= w.sum()
    return np.convolve(np.r_[v[-k:], v, v[:k]], w, mode="same")[k:-k]


def _rays(tree, origins, dirs, rmax, last=True):
    """per ray: the distance to the first (or the last within rmax) surface crossed; nan where none"""
    from mathutils import Vector
    out = np.full(len(origins), np.nan)
    for i, (o, d) in enumerate(zip(origins, dirs)):
        o, d = Vector(o), Vector(d)
        s, travelled, r = o.copy(), 0.0, np.nan
        for _ in range(16):
            hit = tree.ray_cast(s, d, rmax - travelled)
            if hit[0] is None:
                break
            r = (hit[0] - o).length
            if not last:
                break
            travelled = r + 1e-4
            s = o + d * travelled
        out[i] = r
    return out


def _last_hit(tree, o, d, rmax):
    """the last surface crossed within rmax along a ray: (point, normal) or None"""
    from mathutils import Vector
    o, d = Vector(o), Vector(d)
    s, travelled, last = o.copy(), 0.0, None
    for _ in range(16):
        hit = tree.ray_cast(s, d, rmax - travelled)
        if hit[0] is None:
            break
        last = hit
        travelled = (hit[0] - o).length + 1e-4
        s = o + d * travelled
    return None if last is None else (tuple(last[0]), tuple(last[1]))


def neckline(body, log=print):
    """the neckline: per angle round the neck (N_ANG of them), the height where the collar's foot meets the body,
    the lowest point not under the design's line at which the skin is the neck's (near the axis and steep: on the
    trapezius' top a ray along it hits anywhere), then dilated and smoothed round the neck"""
    import bpy
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(body, dg)
    th = np.linspace(0, 2 * np.pi, N_ANG, endpoint=False)
    zs = np.arange(1.47, 1.63, .0015)
    O = np.zeros((N_ANG, len(zs), 3))
    O[:, :, 0], O[:, :, 1], O[:, :, 2] = AXIS[0], AXIS[1], zs[None, :]
    D = np.zeros((N_ANG, len(zs), 3))
    D[:, :, 0], D[:, :, 1] = np.sin(th)[:, None], -np.cos(th)[:, None]
    R = _rays(tree, O.reshape(-1, 3), D.reshape(-1, 3), .30, last=False).reshape(N_ANG, len(zs))
    rlim = .100 + .022 * (1 - np.cos(th)) / 2
    zb = np.zeros(N_ANG)
    for i in range(N_ANG):
        ok = (R[i, :-1] < rlim[i]) & (np.abs(np.diff(R[i])) / np.diff(zs) < 1.3) & (zs[:-1] >= neckline_design(th[i]))
        j = np.nonzero(ok)[0]
        zb[i] = zs[j[0]] if len(j) else neckline_design(th[i])
    zb = np.maximum.reduce([np.roll(zb, k) for k in range(-4, 5)])
    zb = circ_smooth(zb, 5.0)
    log(f"neckline: {zb[0]:.3f} in front, {zb[N_ANG // 4]:.3f} at the side, {zb[N_ANG // 2]:.3f} behind")
    return zb


def iso_cut(bm, f):
    """cut the mesh along the zero of f (a value per vertex, in bm's vertex order) and keep where it is negative: each
    edge that crosses is split where f crosses zero (linearly along it), the faces between split there, the rest of the
    other side deleted"""
    import bmesh
    bm.verts.ensure_lookup_table()
    lay = bm.verts.layers.float.new("_iso")
    for v, val in zip(bm.verts, f):
        v[lay] = float(val) if val != 0 else -1e-9
    cross = [e for e in bm.edges if (e.verts[0][lay] > 0) != (e.verts[1][lay] > 0)]
    new = []
    for e in cross:
        a, b = e.verts
        fa, fb = a[lay], b[lay]
        t = fa / (fa - fb)
        pa, pb = a.co.copy(), b.co.copy()
        ne, nv = bmesh.utils.edge_split(e, a, t)
        nv.co = pa.lerp(pb, t)
        nv[lay] = 0.0
        new.append(nv)
    if new:
        bmesh.ops.connect_verts(bm, verts=new, check_degenerate=False)
    drop = [fc for fc in bm.faces if max(v[lay] for v in fc.verts) > 1e-12]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.verts.layers.float.remove(lay)
    return len(new)


def smooth_vectors(F, edges, n_iter, lam=.5):
    """a value per vertex (n x k) averaged with its neighbours along the edges, n_iter times"""
    n = len(F)
    e0, e1 = edges[:, 0], edges[:, 1]
    cnt = np.bincount(e0, minlength=n) + np.bincount(e1, minlength=n)
    cnt = np.maximum(cnt, 1)
    F = F.astype(np.float64)
    for _ in range(n_iter):
        acc = np.zeros_like(F)
        for c in range(F.shape[1]):
            acc[:, c] = np.bincount(e0, weights=F[e1, c], minlength=n) + np.bincount(e1, weights=F[e0, c], minlength=n)
        F = (1 - lam) * F + lam * acc / cnt[:, None]
    return F


def leg_any(z):
    """the lower leg's height range (the calves' plates)"""
    return (z > .12) & (z < .52)


def panel_fields(P, N):
    """per vertex, in metres: (how far inside a panel, negative outside; how far from a drawn seam line) from its
    place on the body (world metres, the sheet's posture) and its smoothed normal. A panel is the intersection (min)
    of its edges' signed distances, the panels their union (max); a normal's share is turned into metres by the
    curvature's radius there"""
    x, y, z = np.abs(P[:, 0]), P[:, 1], P[:, 2]
    sx = np.where(P[:, 0] < 0, -1.0, 1.0)
    nx, ny, nz = N[:, 0] * sx, N[:, 1], N[:, 2]

    def I(*a, k=.012):
        """a panel's edges together, its corners rounded (k: 1.2 cm for a panel; sharp corners where three edges
        met left slivers of a panel, the back's on the shoulder; a few mm for the small plates)"""
        out = a[0]
        for v in a[1:]:
            h = np.clip(.5 + .5 * (v - out) / k, 0, 1)
            out = v * (1 - h) + out * h - k * h * (1 - h)
        return out
    arm = np.minimum(x - .235, z - 1.25)                               # > 0 on the arms (the thighs' outsides
    # reach x .236 at their widest: by x alone a hole was cut in the thigh's panel)
    torso = np.minimum(-arm, z - .94)
    leg = np.minimum(-arm, .94 - z)
    L = .10                                                             # the trunk's radius: metres per unit of normal

    def band(a, b, half):
        """(signed distance across the line a-b in the front's (x, z) plane, minus half its width: > 0 inside; how far
        along it, metres)"""
        ax, az = a
        dx, dz = b[0] - ax, b[1] - az
        ln = math.hypot(dx, dz)
        along = ((x - ax) * dx + (z - az) * dz) / ln
        across = ((x - ax) * dz - (z - az) * dx) / ln
        return half - np.abs(across), along, ln

    s = []
    # the chest's wings (the sheet's close-up): from the zip at mid-chest rising outward to the front of the
    # shoulder, a dark strap between them and the shoulder's cap; the pecs under them dark plates, outlined
    w_in, w_out = (.022, 1.432), (.178, 1.505)
    wb, _, _ = band(w_in, w_out, .025)
    s.append(I(torso, (-ny - .12) * L, wb, x - .022, .172 - x))
    # the shoulders' caps and the upper arms' outsides
    shd = np.sqrt((x - .232) ** 2 + (y + .022) ** 2 + ((z - 1.53) * 1.2) ** 2)
    s.append(I(.075 - shd, (nz - .05) * .08, .032 - y))
    s.append(I(arm, .44 - x, (nz - .55) * .05))
    # the sides: a broad panel down the side of the trunk from under the arm, leaning forward as it falls, and from
    # the hip forward along the groin to the crotch (the sheet's taper)
    yc = -.050 - .09 * (1.36 - z)                                         # over the obliques, seen from the front
    side_i = len(s)
    s.append(I(torso, z - .985, 1.37 - z, (nx - .30) * L, .058 - np.abs(y - yc)))
    gb, ga, gl = band((.165, 1.005), (.058, .885), .021)
    s.append(I(gb, ga + .01, gl - ga, (-ny + .35) * L, z - .86))
    # the thighs: a band across the front from the outer hip down to the inside above the knee
    tb, ta, tl = band((.185, .935), (.112, .600), .028)
    s.append(I(tb, ta, tl - ta, (-ny + .05) * .07, .94 - z))
    # the hips' outsides behind: from the hip down the outer back of the thigh, narrowing toward the knee
    s.append(I(1.0 - z, z - .66, (nx - .25) * .08, (ny + .10) * .08, .03 + .06 * np.clip((z - .66) / .3, 0, 1)
               - np.abs(y - (.035 + .02 * np.clip((z - .66) / .3, 0, 1)))))
    # the knee: a rounded pad on its front only
    kz = np.abs(z - .515) / .055
    ky = np.clip(-ny - .45, 0, 1) / .55
    knee_i = len(s)
    s.append(I(leg, (1 - (kz ** 2 + (1 - ky) ** 2)) * .03, (-ny - .25) * .05))
    # the shins' outsides: a strip narrowing to the ankle
    shin_i = len(s)
    s.append(I(leg, z - .15, .43 - z, (-ny - .15) * .05, (nx - .05 - .25 * (.43 - z)) * .05))
    # the back: a broad V narrowing to the waist, split by the spine's dark strip and by a dark strap each side from
    # the shoulder blade's outer top down to the waist (the sheet's inner V)
    half = np.interp(z, [1.22, 1.30, 1.36, 1.42, 1.50], [.047, .100, .140, .165, .175])   # wide to the scapulae
    bk = I(torso, (ny - .45) * L, half - x, z - 1.05, 1.56 - z, x - .017)
    sb, sa, sl = band((.146, 1.50), (.048, 1.235), .016)
    s.append(I(bk, -I(sb, sa + .02, sl + .02 - sa)))
    pan = np.maximum.reduce(s)
    # the seams. A seam is drawn where a SIGNED field crosses zero (a panel's, a plate's, an outline's): the field
    # is linear across a face, so the line is sharp and whole at any face size. An unsigned distance to a line
    # reaches zero only at the vertices it passes through and broke into dashes; only the midlines, which run
    # through the body's own midline vertices, are drawn that way (d)
    front = (ny < -.3) & (torso > 0)
    back = (ny > .3) & (torso > 0)
    d = np.full(len(P), .05)
    d = np.where(front, np.minimum(d, np.hypot(x, np.maximum(1.0 - z, 0))), d)       # the zip
    d = np.where(back, np.minimum(d, np.hypot(x, np.maximum(1.0 - z, 0))), d)        # down the back's strip
    K = .004                                                             # the small plates' corners
    # outlines only (no tone of their own): the zip's strip, the pecs' plates under the wings (the lower edge along
    # the pec's own), the knee pad's inner plate, the shins' strips cut in three
    ol = []
    ol.append(I(.016 - x, z - 1.15, (-ny - .3) * L, k=K))
    pz = 1.338 + 3.6 * np.maximum(x - .02, 0) ** 2 + .006                # just over the pec's lower edge
    wl = w_in[1] + (x - w_in[0]) * (w_out[1] - w_in[1]) / (w_out[0] - w_in[0]) - .027   # under the wing
    ol.append(I(z - pz, wl - z, x - .024, .165 - x, (-ny - .3) * L, k=K))
    ol.append(I(s[knee_i] - .010, leg, k=K))
    ol.append(I(s[shin_i], z - .238, .327 - z, k=K))
    outline = np.maximum.reduce(ol)
    # the finer plates (the sheet's angular plates over the muscles): a shade lighter than the dark base, set
    # close together (each one's own edge is a seam: two plates side by side make the sheet's double line)
    pl = []
    # the rectus: a plate per block of the six-pack, and one below the navel narrowing down
    for z_lo, z_hi in ((1.170, 1.228), (1.228, 1.284), (1.284, 1.330)):
        pl.append(I((-ny - .3) * L, x - .010, .076 - x, z - z_lo - .0025, z_hi - .0025 - z, k=K))
    low = .076 - .046 * np.clip((1.1675 - z) / .22, 0, 1)
    pl.append(I((-ny - .3) * L, x - .010, low - x, 1.1675 - z, z - .945, k=K))
    # the obliques: a ladder of plates, down and in toward the rectus
    for z0 in (1.340, 1.262, 1.184, 1.106):
        ob, oa, ol_ = band((.152, z0), (.084, z0 - .082), .021)
        pl.append(I(ob, oa, ol_ - oa, (-ny - .05) * L, torso, .170 - x, x - .080, -s[side_i] - .004, k=K))
    # the calves: the two heads of the calf behind, the inner one lower
    for xc, zt, zb_ in ((.136, .455, .300), (.192, .470, .335)):
        hw = .025 * (.40 + .60 * np.clip((z - zb_) / (zt - zb_) * 1.5, 0, 1))      # narrowing to the tendon
        pl.append(I((ny - .30) * .06, hw - np.abs(x - xc), zt - z, z - zb_, .5 - z, k=K))
    # the upper arm: the triceps behind; the forearm: a bracer on its top by the wrist
    pl.append(I(arm, x - .275, .425 - x, (ny - .35 - .30 * np.clip((x - .275) / .15, 0, 1)) * .05, k=K))
    bracer = I(arm, x - .560, .680 - x, (nz - .35) * .04, k=K)
    pl.append(bracer)
    tone = np.maximum.reduce(pl)
    # --- what makes it a made thing, not a blob (the owner, 2026-11-17: "bland and lifeless like a blob ... more
    # details, more colours, more everything"): each a signed field in metres, > 0 inside
    ex = {}
    # steel-blue piping round the main panels: the chest's wings, the sides, the thighs' bands, the back's V
    ex["piped"] = np.maximum.reduce([s[0], s[side_i], s[5], s[9]])
    # the knee: a hard shell over the pad
    ex["knee"] = s[knee_i]
    ex["shoulder"] = s[1]
    ex["bracer"] = bracer
    # studs where a made suit fastens its panels: each a point on the suit (the nearest of its vertices facing that
    # way), mirrored; > 0 within its radius
    ex["stud"] = np.full(len(P), -.05)
    STUDS = [((.160, 1.497), "front"), ((.150, 1.478), "front"),                  # the chest's wings, outer end
             ((.568, -.042), "top"), ((.568, -.018), "top"), ((.672, -.042), "top"), ((.672, -.018), "top"),  # bracers
             ((.082, .515), "front"), ((.128, .515), "front"),                    # either side of the knee's shell
             ((.150, 1.470), "back"), ((.030, 1.470), "back")]                     # the back's top corners
    face = {"front": ny < -.55, "back": ny > .55, "top": nz > .6}
    for (a_, b_), f_ in STUDS:
        for sgn in (1, -1):
            cand = face[f_] & (P[:, 0] * sgn > 0)
            if f_ == "top":
                dd_ = np.hypot(x - a_, y - b_) + 1e3 * ~cand
            else:
                dd_ = np.hypot(x - a_, z - b_) + 1e3 * ~cand
            c_ = P[int(np.argmin(dd_))]
            ex["stud"] = np.maximum(ex["stud"], STUD_R - np.linalg.norm(P - c_, axis=1))
    # flex zones in ribbed knit: behind the knee, inside the elbow
    kb = I(leg, .042 - np.abs(z - .520), (ny - .25) * .05, k=K)
    eb = I(arm, .030 - np.abs(x - .470), (-ny - .15) * .05, k=K)
    ex["flex"] = np.maximum(kb, eb)
    # vents under the arms: a perforated patch down the side of the chest
    ex["vent"] = I(torso, .048 - np.abs(z - 1.318), (nx - .55) * .08, .020 - np.abs(y + .012), k=K)
    # the lights (steel blue, small: humanity's, not the Sarketh's rows of dashes): a line along each forearm's
    # bracer, a short strip on the spine between the shoulder blades, two status points on the left chest's wing
    li = [I(.0016 - np.abs(y + .030), x - .585, .655 - x, (nz - .6) * .05, arm, k=.001),
          I(.0017 - x, z - 1.385, 1.455 - z, (ny - .5) * .05, k=.001)]
    for zc_, xc_ in ((1.474, .072), (1.481, .088)):
        li.append(np.minimum(.0026 - np.hypot(x - xc_, z - zc_), (-ny - .3) * .05) * (P[:, 0] > 0) +
                  -1.0 * (P[:, 0] <= 0))
    ex["light"] = np.maximum.reduce(li)
    # the emblem on the left upper arm (its top in the T-pose, its outside when the arm hangs): the broken ring
    # and the point (the orbit), the guns' maker's mark, in muted gold; reading with the shoulder up
    su, sv = (P[:, 1] + .022) / .030, (.300 - P[:, 0]) / .030            # its own frame, 3 cm a unit
    rr = np.hypot(su, sv)
    ang = np.degrees(np.arctan2(sv, su)) % 360
    gap = np.abs(((ang - 52 + 180) % 360) - 180)
    ring = np.minimum(.09 - np.abs(rr - .72), np.radians(gap - 14) * .72)
    shard = np.minimum(.07 - np.abs(rr - .93), np.radians(5 - gap) * .93)
    point = .175 - np.hypot(su + .08, sv - .06)
    on_top = (nz - .55) * 2.0
    ex["emblem"] = np.where(P[:, 0] > .2, np.minimum(np.maximum.reduce([ring, shard, point]) * .030, on_top * .01), -1.0)
    # the zip down the front, its pull under the collar
    ex["zip"] = I(.0045 - x, z - 1.000, 1.520 - z, (-ny - .3) * L, k=.001)
    # (on an arm: its ribs run across it, along x)
    ex["armmask"] = np.clip((x - .235) / .02, 0, 1) * np.clip((z - 1.25) / .05, 0, 1)
    return pan, d, tone, outline, ex


N_COL = 6                    # colours the muscles' panels are told apart by (each a signed field: a seam where it is 0)


def muscle_panels(P, edges, log=print):
    """the suit cut along the muscles under it, as the sheet's undersuit is (a panel over each muscle, raised, its
    edges a seam): each vertex belongs to the muscle raising the skin most there (anatomy.py, the body's own),
    or to none. A seam is drawn where a SIGNED field is 0, so the panels are coloured (neighbours differ, greedy
    over the mesh's adjacency) and for each colour c: (the strongest of colour c) - (the strongest of the others).
    Returns those fields (n, N_COL) in metres and each vertex's panel tone (0..1, the panel's own; -1 the floor).
    Two passes over the muscles, keeping only running maxima (a table of every muscle at every vertex of the
    finer suit was 340 MB)"""
    import anatomy as AN
    A = AN.Anatomy()
    Q = A.posture(np.asarray(P, np.float32))
    Q[:, 0] = np.abs(Q[:, 0])
    n, nm = len(Q), len(A.M)

    def raises():
        for j, m in enumerate(A.M):
            depth, m.depth = m.depth, .09
            r = m.raise_(Q)
            m.depth = depth
            yield j, r
    top = np.full(n, MUSCLE_FLOOR, np.float32)
    best = np.full(n, nm, np.int64)                                     # nm: the floor's own panel
    for j, r in raises():
        sel = r > top
        top = np.where(sel, r, top); best = np.where(sel, j, best)
    # the panels' neighbours across the mesh's edges; colour them so no two neighbours share one
    e0, e1 = edges[:, 0], edges[:, 1]
    diff = best[e0] != best[e1]
    nb = {}
    for a, b in zip(best[e0][diff], best[e1][diff]):
        nb.setdefault(int(a), set()).add(int(b)); nb.setdefault(int(b), set()).add(int(a))
    col = {}
    for node in sorted(nb, key=lambda k: -len(nb[k])):
        used = {col[v] for v in nb[node] if v in col}
        col[node] = next(c for c in range(64) if c not in used)
    ncol = max(col.values()) + 1 if col else 1
    if ncol > N_COL:
        log(f"suit: the muscles' panels needed {ncol} colours, {N_COL} drawn")
    cid = np.array([col.get(j, 0) % N_COL for j in range(nm + 1)])
    mine = np.full((N_COL, n), -.05, np.float32)
    mine[cid[nm]] = np.maximum(mine[cid[nm]], MUSCLE_FLOOR)
    for j, r in raises():
        mine[cid[j]] = np.maximum(mine[cid[j]], r)
    G = np.zeros((n, N_COL), np.float32)
    # each field turned into metres by its own slope over the mesh (a difference of two muscles' heights falls
    # faster or slower across their edge than a distance: the seam would be drawn thin here and wide there)
    Pp = np.asarray(P, np.float64)
    elen = np.maximum(np.linalg.norm(Pp[e0] - Pp[e1], axis=1), 1e-6)
    cnt = np.maximum(np.bincount(e0, minlength=n) + np.bincount(e1, minlength=n), 1)
    for c in range(N_COL):
        other = np.max(np.delete(mine, c, axis=0), axis=0)
        g = (mine[c] - other).astype(np.float64)
        sl = np.abs(g[e0] - g[e1]) / elen
        slope = (np.bincount(e0, weights=sl, minlength=n) + np.bincount(e1, weights=sl, minlength=n)) / cnt
        G[:, c] = (g / np.maximum(slope, .25)).astype(np.float32)
    rng = np.random.default_rng(7)
    shade = rng.random(nm + 1).astype(np.float32)
    shade[nm] = -1.0                                                     # the floor: no muscle's panel
    log(f"suit: {len(nb)} muscle panels, {ncol} colours")
    return G, shade[best]


def relief(pan, tone, ex, G, shade):
    """how far each part of the suit stands off its fabric (metres, along the surface's own normal): the owner,
    2026-11-17, "more 3d and less flat". Each muscle's panel a little off the floor between them, the seams real
    grooves; the polymer panels a bonded layer with a bevelled edge; the plates; the shoulder caps and the knee's
    shell domed; the piping a cord; the zip's tape; a housing round each light"""
    ss = lambda v, lo, hi: (lambda t: t * t * (3 - 2 * t))(np.clip((v - lo) / (hi - lo), 0, 1))
    seam_m = np.min(np.abs(G), axis=1)                                  # to the nearest muscles' seam (metres)
    musc = (shade > -.5).astype(np.float32)
    h = .0005 * musc * ss(seam_m, .0004, .0020)                        # each muscle's panel, rounded over its edge
    h -= .00045 * np.exp(-(seam_m / .0008) ** 2)                        # the seam pressed in
    h += RELIEF["panel"] * ss(pan, -.0002, .0014)
    h += RELIEF["plate"] * ss(tone, -.0002, .0011)
    h += RELIEF["shoulder"] * ss(ex["shoulder"], .0, .014)              # domed caps over the deltoids
    h += RELIEF["knee"] * (.55 * ss(ex["knee"], -.0002, .0025) + .45 * ss(ex["knee"], .002, .016))   # a shell
    h += RELIEF["pipe"] * np.exp(-((ex["piped"] + .0028) / .0009) ** 2) * (pan < 0)
    h += RELIEF["zip"] * ss(ex["zip"], -.0002, .0007)
    lt = ex["light"]
    h += RELIEF["housing"] * ss(lt, -.0050, -.0028) - .0007 * ss(lt, -.0006, .0002)   # a housing, the lens set in
    h += .0003 * ss(ex["emblem"], -.0002, .0004)
    h += RELIEF["bracer"] * ss(ex["bracer"], -.0002, .0016)
    sd = np.clip(ex["stud"], 0, STUD_R)
    h += RELIEF["stud"] * np.sqrt(np.clip(1 - ((STUD_R - sd) / STUD_R) ** 2, 0, 1)) * (ex["stud"] > 0)
    return h.astype(np.float32)


RELIEF = dict(panel=.0016, plate=.0010, shoulder=.0016, knee=.0040, pipe=.0011, zip=.0006, housing=.0022,
              bracer=.0018, stud=.0012)


STUD_R = .0034               # a stud's radius (metres)
MUSCLE_FLOOR = .003          # metres of a muscle's raise below which the skin is no muscle's panel


def build_suit(body, log=print, zb=None):
    """the suit as its own object over `body` (its finished, subdivided mesh): the skin's copy subdivided once more,
    offset, cut along the neckline's line (`zb`: per angle round the neck; the collar covers the cut), the wrists
    and the ankles, its panels and seams as signed distances on the vertices, a thickness"""
    import bpy, bmesh
    o = bpy.data.objects.new("suit", body.data.copy())
    bpy.context.scene.collection.objects.link(o)
    sub = o.modifiers.new("sub", 'SUBSURF'); sub.subdivision_type = 'SIMPLE'; sub.levels = sub.render_levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); o.data = me
    n = len(me.vertices)
    co = np.zeros(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
    nr = np.zeros(n * 3, np.float32); me.vertices.foreach_get("normal", nr); nr = nr.reshape(n, 3)
    # offset off the skin, and where the skin has a sharp groove (between the trapezius and the collarbone) the
    # fabric spans it: the offset face smoothed, but only ever moved outward (a crease narrower than the offset
    # folded the offset face into a slit; every convex form is kept)
    ed0 = np.zeros(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", ed0); ed0 = ed0.reshape(-1, 2)
    off = co + nr * OFFSET
    span = smooth_vectors(off, ed0, 10)
    lift = np.maximum(((span - off) * nr).sum(1), 0.0)
    co = (off + nr * lift[:, None]).astype(np.float32)
    me.vertices.foreach_set("co", co.ravel())
    log(f"suit: grooves spanned, up to {lift.max() * 1000:.1f} mm")
    # where it ends: under the collar (the neckline's line a little above its foot), the wrists, the ankles
    x, z = np.abs(co[:, 0]), co[:, 2]
    a = np.array([math.cos(math.radians(6.0)), 0.0, -math.sin(math.radians(6.0))])
    along = np.c_[x - .178, co[:, 1] + .030, z - 1.486] @ a              # along the arm from the shoulder joint
    f = np.maximum(.118 - z, np.where(x > .30, along - .522, -1.0))
    th, r = around(co)
    ztop = (periodic(zb, th) if zb is not None else neckline_design(th)) + .012
    f = np.maximum(f, np.where((r < .16) & (z > 1.45), z - ztop, -1.0))
    bm = bmesh.new(); bm.from_mesh(me)
    k = iso_cut(bm, f)
    bm.to_mesh(me); bm.free()
    me.update()
    # its panels and seams, from the cut mesh's own places and its normals smoothed to the limb's and the trunk's
    # gross shape (the muscles' forms turned them enough to punch holes in a panel drawn sharp: the thigh's)
    nn = len(me.vertices)
    P = np.zeros(nn * 3, np.float32); me.vertices.foreach_get("co", P); P = P.reshape(nn, 3)
    Nn = np.zeros(nn * 3, np.float32); me.vertices.foreach_get("normal", Nn); Nn = Nn.reshape(nn, 3)
    ed = np.zeros(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", ed); ed = ed.reshape(-1, 2)
    Nn = smooth_vectors(Nn, ed, 160)
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-9)[:, None]
    pan, d, tone, outline, ex = panel_fields(P, Nn)
    m = me.color_attributes.new("suit", 'FLOAT_COLOR', 'POINT')
    m.data.foreach_set("color", np.c_[np.clip(pan, -.05, .05), np.clip(d, 0, .05), np.clip(tone, -.05, .05),
                                      np.clip(outline, -.05, .05)]
                       .astype(np.float32).ravel())
    c = lambda v: np.clip(v, -.05, .05)
    for name, keys in (("suit2", ("piped", "knee", "flex", "vent")), ("suit3", ("light", "emblem", "zip", "armmask"))):
        a2 = me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
        a2.data.foreach_set("color", np.c_[tuple(c(ex[k]) for k in keys)].astype(np.float32).ravel())
    G, shade = muscle_panels(P, ed, log=log)
    a4 = me.color_attributes.new("suit4", 'FLOAT_COLOR', 'POINT')
    a4.data.foreach_set("color", c(G[:, :4]).astype(np.float32).ravel())
    a5 = me.color_attributes.new("suit5", 'FLOAT_COLOR', 'POINT')
    a5.data.foreach_set("color", np.c_[c(G[:, 4]), c(G[:, 5]), shade, c(ex["shoulder"])].astype(np.float32).ravel())
    a6 = me.color_attributes.new("suit6", 'FLOAT_COLOR', 'POINT')
    a6.data.foreach_set("color", np.c_[c(ex["stud"]), c(ex["bracer"]), np.full(nn, -.05), np.full(nn, -.05)]
                        .astype(np.float32).ravel())
    # twice as fine for the relief (1.4 mm: a raised edge needs it), the fields laid out above carried down
    # linearly (laid out on the finer mesh, the normals' smoothing would reach half as far and the muscles' forms
    # would punch holes in the panels again)
    sub2 = o.modifiers.new("sub2", 'SUBSURF'); sub2.subdivision_type = 'SIMPLE'; sub2.levels = sub2.render_levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); o.data = me
    nf = len(me.vertices)

    def read(name):
        v = np.zeros(nf * 4, np.float32); me.color_attributes[name].data.foreach_get("color", v)
        return v.reshape(nf, 4)
    s1, s2, s3, s4, s5, s6 = (read(k) for k in ("suit", "suit2", "suit3", "suit4", "suit5", "suit6"))
    exf = dict(piped=s2[:, 0], knee=s2[:, 1], light=s3[:, 0], emblem=s3[:, 1], zip=s3[:, 2], shoulder=s5[:, 3],
               stud=s6[:, 0], bracer=s6[:, 1])
    rel = relief(s1[:, 0], s1[:, 2], exf, np.c_[s4, s5[:, :2]], s5[:, 2])
    Pf = np.zeros(nf * 3, np.float32); me.vertices.foreach_get("co", Pf); Pf = Pf.reshape(nf, 3)
    Nf = np.zeros(nf * 3, np.float32); me.vertices.foreach_get("normal", Nf); Nf = Nf.reshape(nf, 3)
    me.vertices.foreach_set("co", (Pf + Nf * rel[:, None]).astype(np.float32).ravel())
    me.update()
    log(f"suit: {nf} vertices for its relief, {rel.min() * 1000:.1f} .. {rel.max() * 1000:.1f} mm")
    mod = o.modifiers.new("thick", 'SOLIDIFY'); mod.thickness = THICK; mod.offset = 1.0
    o.data.materials.clear()
    o.data.materials.append(suit_material())
    for fc in me.polygons:
        fc.use_smooth = True
    o["neckline"] = [float(v) for v in (zb if zb is not None else neckline_design(np.linspace(0, 2 * np.pi, N_ANG,
                                                                                               endpoint=False)))]
    log(f"suit: {nn} vertices, {k} cut along its lines, panels {(pan > 0).mean() * 100:.0f} % of it")
    return o


def _upper_hull(xs, ys):
    """the upper concave envelope of points sorted by x (monotone chain), read back at every x"""
    hull = []
    for p in zip(xs, ys):
        while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (p[1] - hull[-2][1])
                                  - (hull[-1][1] - hull[-2][1]) * (p[0] - hull[-2][0])) >= 0:
            hull.pop()
        hull.append(p)
    hx, hy = np.array([h[0] for h in hull]), np.array([h[1] for h in hull])
    return np.interp(xs, hx, hy)


def build_collar(head, suit, body, zb, log=print, n_h=26):
    """the sheet's high mock-neck collar: a tube round the neck from the neckline (`zb`, its foot 3 mm inside the
    suit along the suit's normal, its thickness growing from nothing there) to under the jaw (higher at the nape), laid outside the suit, the body and the head (`CLEAR` off
    its skin), bridging what a stretched fabric bridges (each vertical line of it is the upper envelope of what lies
    under it: across the nape's hollow, over the notch), its top rolled thicker, a stitched line under its rim and at
    its foot, the zip's line down its front"""
    import bpy
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    trees = {k: BVHTree.FromObject(v, dg) for k, v in (("suit", suit), ("body", body), ("head", head))}
    th = np.linspace(0, 2 * np.pi, N_ANG, endpoint=False)
    zt = collar_top(th)
    T = np.linspace(0, 1, n_h)
    Z = zb[None, :] + (zt - zb)[None, :] * T[:, None]                       # (n_h, N_ANG)
    O = np.zeros((n_h, N_ANG, 3))
    O[:, :, 0], O[:, :, 1], O[:, :, 2] = AXIS[0], AXIS[1], Z
    D = np.zeros((n_h, N_ANG, 3))
    D[:, :, 0], D[:, :, 1] = np.sin(th)[None, :], -np.cos(th)[None, :]
    O0, D0 = O[0].copy(), D[0].copy()
    O, D = O.reshape(-1, 3), D.reshape(-1, 3)
    rs = {k: _rays(t, O, D, .16).reshape(n_h, N_ANG) for k, t in trees.items()}
    # the mesh is the collar's OUTER face (its thickness goes inward): at its foot it lies 0.6 mm over the suit, so it
    # comes out of the suit without an edge (built as the inner face with the thickness outward, its foot stood 1-2 mm
    # proud of the suit: a lip); the thickness grows from next to nothing at the foot, the rim folded over thicker
    Z = Z.copy()
    rise = Z - Z[0][None, :]
    wt = (.06 + .94 * smooth01(rise / .009)) * (.62 + .38 * smooth01((T[:, None] - .86) / .1))
    thick = .0034 * wt
    clear = CLEAR - (CLEAR - .0012) * smooth01((T[:, None] - .88) / .12)   # the rim close to the skin (no gap to see into)
    need = np.fmax(np.fmax(rs["suit"] + .0006, rs["body"] + .0035 + thick), rs["head"] + clear + thick)
    for j in range(n_h):                                                    # nothing hit: the ring's neighbours
        bad = np.isnan(need[j])
        if bad.any() and (~bad).any():
            need[j, bad] = np.interp(np.nonzero(bad)[0], np.nonzero(~bad)[0], need[j, ~bad], period=N_ANG)
    # the foot: the suit's face at the neckline moved 3 mm in along its own normal (on the trapezius' flat top a
    # tuck toward the axis stayed on the suit)
    R = need.copy()
    for i in range(N_ANG):
        hit = _last_hit(trees["suit"], O0[i], D0[i], .16)
        if hit is None:
            R[0, i] = need[0, i] - .004
            continue
        p = np.array(hit[0]) - np.array(hit[1]) * .003
        R[0, i] = math.hypot(p[0] - AXIS[0], p[1] - AXIS[1])
        Z[0, i] = min(p[2], Z[1, i] - .0005)
    for i in range(N_ANG):                                                  # each vertical line: the fabric's envelope
        R[:, i] = _upper_hull(Z[:, i], R[:, i])
    for j in range(1, n_h):
        R[j] = circ_smooth(R[j], 1.5)
    for _ in range(2):
        R[1:-1] = .25 * R[:-2] + .5 * R[1:-1] + .25 * R[2:]
    R[1:] = np.fmax(R[1:], np.fmax(np.fmax(rs["suit"][1:] + .0004, rs["body"][1:] + .002 + thick[1:]),
                                   rs["head"][1:] + np.minimum(clear[1:], .0025) + thick[1:]))
    V = np.zeros((n_h, N_ANG, 3))
    V[:, :, 0] = AXIS[0] + np.sin(th)[None, :] * R
    V[:, :, 1] = AXIS[1] - np.cos(th)[None, :] * R
    V[:, :, 2] = Z
    F = []
    for j in range(n_h - 1):
        for i in range(N_ANG):
            i2 = (i + 1) % N_ANG
            F.append((j * N_ANG + i, j * N_ANG + i2, (j + 1) * N_ANG + i2, (j + 1) * N_ANG + i))
    me = bpy.data.meshes.new("collar")
    me.from_pydata([tuple(v) for v in V.reshape(-1, 3)], [], F)
    me.update()
    o = bpy.data.objects.new("collar", me)
    bpy.context.scene.collection.objects.link(o)
    # the stitches: 6 mm under the rim, 6.5 mm over the tucked foot (along the fabric), the zip down the front
    seg = np.linalg.norm(np.diff(V, axis=0), axis=2)
    up_len = np.r_[np.zeros((1, N_ANG)), np.cumsum(seg, axis=0)]
    down_len = up_len[-1][None, :] - up_len
    d = np.minimum(np.abs(down_len - .006), np.abs(up_len - .0065))
    front = np.cos(th)[None, :] > .3
    d = np.where(front, np.minimum(d, np.abs(V[:, :, 0])), d)
    nn = n_h * N_ANG
    col = np.c_[np.full(nn, -.05), np.clip(d.ravel(), 0, .05), np.full(nn, -.05), np.full(nn, -.05)]
    m = me.color_attributes.new("suit", 'FLOAT_COLOR', 'POINT')
    m.data.foreach_set("color", col.astype(np.float32).ravel())
    # the suit's other fields, so the collar is the suit's own fabric (without them each read 0, half way inside a
    # light: the collar glowed pale blue): one panel, no muscle seams, a steel-blue piping 9 mm under its rim
    seg = np.linalg.norm(np.diff(V, axis=0), axis=2)                     # (n_h - 1, N_ANG)
    dtop = np.vstack([np.cumsum(seg[::-1], axis=0)[::-1], np.zeros((1, V.shape[1]))])
    piped = (.0060 - dtop).ravel()
    neg = np.full(nn, -.05)
    for name, cols in (("suit2", (piped, neg, neg, neg)), ("suit3", (neg, neg, neg, np.zeros(nn))),
                       ("suit4", (np.full(nn, .05), neg, neg, neg)), ("suit5", (neg, neg, np.full(nn, .35), np.zeros(nn))),
                       ("suit6", (neg, neg, neg, neg))):
        a2 = me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
        a2.data.foreach_set("color", np.c_[cols].astype(np.float32).ravel())
    vg = o.vertex_groups.new(name="thick")
    for j in range(n_h):
        for i in range(N_ANG):
            vg.add([j * N_ANG + i], float(wt[j, i]), 'REPLACE')
    mod = o.modifiers.new("thick", 'SOLIDIFY'); mod.thickness = .0034; mod.offset = -1.0
    mod.vertex_group = "thick"; mod.thickness_vertex_group = 0.0
    sm = o.modifiers.new("smooth", 'SUBSURF'); sm.levels = sm.render_levels = 1
    o.data.materials.append(suit.data.materials[0] if suit.data.materials else suit_material())
    for fc in me.polygons:
        fc.use_smooth = True
    log(f"collar: {n_h} rings from the neckline to under the jaw, {np.nanmin(R) * 100:.1f}-{np.nanmax(R) * 100:.1f} cm "
        f"off the neck's axis; the fabric stands off the head's skin {np.nanmin(R[1:] - rs['head'][1:]) * 1000:.1f}-"
        f"{np.nanmax(R[1:] - rs['head'][1:]) * 1000:.1f} mm")
    return o


def suit_material():
    """the undersuit as the owner's sheet shows it: near-black satin cut into a panel over each muscle (each a
    shade of its own, its edge bevelled into a pressed seam), the grey panels a charcoal-grey polymer with an etched
    micro pattern and a coat, plates in grip rubber, the knee a hard shell; steel-blue piping round the main panels,
    small steel-blue lights, a muted-gold emblem and zip pull; topstitching, a zip with teeth, ribbed flex zones,
    perforated vents; dust in the seams, rubbed edges, a slow change of tone over the whole (the owner,
    2026-11-17: "bland and lifeless like a blob ... the image has far more detail than our undersuit")"""
    import bpy
    m = bpy.data.materials.new("suit")
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]
    W = W_SEAM

    def attr(name):
        a = N.new("ShaderNodeAttribute"); a.attribute_name = name
        sp = N.new("ShaderNodeSeparateColor"); L.new(a.outputs["Color"], sp.inputs[0])
        return sp.outputs[0], sp.outputs[1], sp.outputs[2], a.outputs["Alpha"]

    def M(op, a, bb=None, c=None):
        n = N.new("ShaderNodeMath"); n.operation = op
        for k, v in enumerate((a, bb, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                L.new(v, n.inputs[k])
        return n.outputs[0]

    def step(v, lo=-.0007, hi=.0007):
        """0 outside .. 1 inside a signed field (metres): sharp at the pixel whatever the faces"""
        r = N.new("ShaderNodeMapRange"); r.interpolation_type = 'SMOOTHSTEP'
        L.new(v, r.inputs["Value"])
        r.inputs["From Min"].default_value = lo; r.inputs["From Max"].default_value = hi
        return r.outputs[0]

    def line(v, w, at=0.0):
        """1 where the field is `at`, gone a few w away"""
        q = M('DIVIDE', M('SUBTRACT', v, at), w)
        return M('EXPONENT', M('MULTIPLY', M('MULTIPLY', q, q), -1.0))

    def mixc(fac, a, c):
        n = N.new("ShaderNodeMix"); n.data_type = 'RGBA'
        for idx, v in ((6, a), (7, c)):
            if isinstance(v, tuple):
                n.inputs[idx].default_value = v
            else:
                L.new(v, n.inputs[idx])
        if isinstance(fac, (int, float)):
            n.inputs[0].default_value = fac
        else:
            L.new(fac, n.inputs[0])
        return n.outputs[2]

    def mixf(fac, a, c):
        """a + (c - a) * fac"""
        if isinstance(a, (int, float)) and isinstance(c, (int, float)):
            return M('MULTIPLY_ADD', fac, c - a, a)
        return M('ADD', a, M('MULTIPLY', M('SUBTRACT', c, a), fac))

    def scale(col, f):
        n = N.new("ShaderNodeVectorMath"); n.operation = 'SCALE'
        L.new(col, n.inputs[0]); L.new(f, n.inputs["Scale"])
        return n.outputs["Vector"]

    tc = N.new("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    xyz = N.new("ShaderNodeSeparateXYZ"); L.new(obj, xyz.inputs[0])
    ox, oz = xyz.outputs[0], xyz.outputs[2]

    def noise(sc, detail=2.0, rough=.5):
        n = N.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = sc
        n.inputs["Detail"].default_value = detail; n.inputs["Roughness"].default_value = rough
        L.new(obj, n.inputs["Vector"])
        return n.outputs["Fac"]

    def voronoi(sc, feature='F1'):
        n = N.new("ShaderNodeTexVoronoi"); n.feature = feature
        n.inputs["Scale"].default_value = sc
        L.new(obj, n.inputs["Vector"])
        return n.outputs["Distance"]

    def wave(sc, direction='X', distortion=0.0):
        n = N.new("ShaderNodeTexWave"); n.wave_type = 'BANDS'; n.bands_direction = direction
        n.inputs["Scale"].default_value = sc; n.inputs["Distortion"].default_value = distortion
        L.new(obj, n.inputs["Vector"])
        return n.outputs["Fac"]

    pan, mid, tone, outl = attr("suit")
    piped, knee, flex, vent = attr("suit2")
    light, emb, zipf, armm = attr("suit3")
    g0, g1, g2, g3 = attr("suit4")
    g4, g5, shade, _ = attr("suit5")
    stud, bracer_f, _s6b, _s6c = attr("suit6")
    # --- where each thing is
    P = step(pan)
    T = step(tone)
    K = step(knee)
    musc = step(shade, -.6, -.4)                                       # on a muscle's panel (the floor is -1)
    gs = (g0, g1, g2, g3, g4, g5)
    mseam = line(gs[0], W * 1.15)
    mlip = line(gs[0], W * 3.0)
    for g in gs[1:]:
        mseam = M('MAXIMUM', mseam, line(g, W * 1.15))
        mlip = M('MAXIMUM', mlip, line(g, W * 3.0))
    seam = M('MAXIMUM', M('MAXIMUM', line(pan, W * .7), line(mid, W * .6)),
             M('MAXIMUM', line(tone, W * .7), line(outl, W * .7)))
    lip = M('MAXIMUM', M('MAXIMUM', line(pan, W * 2.4), line(mid, W * 2.2)),
            M('MAXIMUM', line(tone, W * 2.4), line(outl, W * 2.4)))
    seam_all = M('MAXIMUM', seam, mseam)
    lip_all = M('MAXIMUM', lip, mlip)
    pipe = M('MULTIPLY', line(piped, .00085, -.0028), M('SUBTRACT', 1.0, P))
    dots = step(M('SUBTRACT', .23, voronoi(430.0)), -.02, .02)          # stitch holes, 2.3 mm apart
    stitch = M('MULTIPLY', M('MAXIMUM', line(pan, .00030, .0021), line(knee, .00030, .0021)), dots)
    Z = step(zipf, -.0003, .0003)
    teeth = M('MULTIPLY', M('MULTIPLY', Z, step(M('SUBTRACT', .0019, M('ABSOLUTE', ox)), -.0002, .0002)),
              step(M('SUBTRACT', wave(125.0, 'Z'), .5), -.08, .08))
    pull = M('MULTIPLY', Z, step(M('SUBTRACT', oz, 1.489), -.0004, .0004))
    E = step(emb, -.0003, .0003)
    Lg = step(light, -.0003, .0003)
    V = step(vent)
    holes = M('MULTIPLY', V, step(M('SUBTRACT', .30, voronoi(480.0)), -.03, .03))
    F = step(flex)
    rib = mixf(armm, wave(105.0, 'Z'), wave(105.0, 'X'))
    knit = M('ADD', M('MULTIPLY', wave(330.0, 'DIAGONAL', 3.0), .6), M('MULTIPLY', noise(900.0, 3.0), .4))
    geo = N.new("ShaderNodeNewGeometry")
    nxyz = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Normal"], nxyz.inputs[0])

    def rs(d, k):
        """a thread every 5 mm across axis d, gone where the surface faces along d (its cuts there are contours)"""
        across = M('SUBTRACT', 1.0, M('MULTIPLY', M('ABSOLUTE', nxyz.outputs[k]), 1.6))
        return M('MULTIPLY', step(M('SUBTRACT', wave(63.0, d), .93), -.02, .02), M('MAXIMUM', across, 0.0))
    hexl = M('MAXIMUM', M('MAXIMUM', rs('X', 0), rs('Y', 1)), rs('Z', 2))
    grip = step(M('SUBTRACT', .26, voronoi(620.0)), -.03, .03)
    macro = noise(3.0, 2.0)
    wearn = noise(70.0, 6.0, .6)
    edge_wear = M('MULTIPLY', M('MULTIPLY', line(pan, .0010, .0006), M('MAXIMUM', P, K)),
                  step(M('SUBTRACT', wearn, .52), -.04, .04))
    dust = step(M('SUBTRACT', noise(45.0, 4.0), .45), -.08, .08)
    # --- colour (linear)
    musc_c = mixc(shade, (.011, .012, .015, 1), (.032, .033, .040, 1))      # each muscle's panel its own shade
    col = mixc(musc, (.0085, .0092, .0115, 1), musc_c)                         # the floor between: near black
    col = mixc(T, col, (.026, .028, .033, 1))                                  # grip rubber plates
    col = mixc(P, col, (.044, .052, .066, 1))                                  # steel-blue-grey polymer panels
    col = mixc(M('MULTIPLY', P, hexl), col, (.066, .076, .094, 1))            # its ripstop grid
    col = mixc(K, col, (.040, .042, .049, 1))                                  # the knee's shell
    col = scale(col, M('ADD', .90, M('MULTIPLY', macro, .20)))                # a slow change of tone
    col = scale(col, M('ADD', .88, M('MULTIPLY', knit, .24)))                 # the knit
    col = mixc(F, col, scale(col, M('ADD', .75, M('MULTIPLY', rib, .55))))   # ribbed flex zones
    col = mixc(M('MULTIPLY', edge_wear, .55), col, (.11, .11, .12, 1))        # rubbed edges
    col = mixc(pipe, col, (.045, .120, .240, 1))                               # steel-blue piping
    col = mixc(stitch, col, (.085, .087, .095, 1))                             # thread
    col = mixc(seam_all, col, (.0020, .0020, .0026, 1))                        # the seams pressed in ...
    col = mixc(M('MULTIPLY', seam_all, M('MULTIPLY', dust, .45)), col, (.05, .046, .040, 1))   # ... dust in them
    col = mixc(holes, col, (.002, .002, .0025, 1))                             # vents
    col = mixc(Z, col, (.010, .010, .012, 1))                                  # zip tape
    col = mixc(teeth, col, (.17, .17, .18, 1))                                 # its teeth
    col = mixc(M('MAXIMUM', pull, E), col, (.40, .29, .11, 1))                 # muted gold: the pull, the emblem
    col = mixc(Lg, col, (.10, .22, .40, 1))                                    # the lights' lens
    SD = step(stud, -.0002, .0002)
    col = mixc(SD, col, (.12, .12, .13, 1))                                    # studs: gunmetal
    col = mixc(line(stud, .00025), col, (.004, .004, .005, 1))                 # the ring they sit in
    L.new(col, b.inputs["Base Color"])
    # --- the surface
    r = mixf(musc, .58, .50)
    r = mixf(T, r, .76)
    r = mixf(P, r, .42)
    r = mixf(M('MULTIPLY', P, hexl), r, .55)
    r = mixf(K, r, .32)
    r = mixf(pipe, r, .40)
    r = mixf(seam_all, r, .80)
    r = mixf(holes, r, .90)
    r = mixf(M('MAXIMUM', M('MAXIMUM', teeth, pull), E), r, .26)
    r = mixf(SD, r, .30)
    r = M('ADD', r, M('MULTIPLY', M('SUBTRACT', knit, .5), .08))
    L.new(r, b.inputs["Roughness"])
    met = mixf(K, 0.0, .30)
    met = mixf(M('MAXIMUM', teeth, pull), met, .90)
    met = mixf(E, met, .65)
    met = mixf(SD, met, .85)
    L.new(met, b.inputs["Metallic"])
    L.new(mixf(P, 0.0, .15), b.inputs["Coat Weight"])
    b.inputs["Coat Roughness"].default_value = .25
    b.inputs["Sheen Weight"].default_value = .30
    b.inputs["Sheen Roughness"].default_value = .45
    b.inputs["Specular IOR Level"].default_value = .35                # fabric: a softer highlight than a plastic's
    b.inputs["Emission Color"].default_value = (.20, .48, 1.0, 1)
    L.new(M('MULTIPLY', Lg, 7.0), b.inputs["Emission Strength"])
    # --- the relief: seams pressed in, their edges bevelled up, piping a cord, teeth, ribs, holes, grip, knit
    h = M('MULTIPLY', knit, .12)
    h = M('ADD', h, M('MULTIPLY', seam_all, -1.3))
    h = M('ADD', h, M('MULTIPLY', lip_all, .75))
    h = M('ADD', h, M('MULTIPLY', pipe, .45))
    h = M('ADD', h, M('MULTIPLY', stitch, -.35))
    h = M('ADD', h, M('MULTIPLY', teeth, .6))
    h = M('ADD', h, M('MULTIPLY', holes, -.9))
    h = M('ADD', h, M('MULTIPLY', M('MULTIPLY', F, rib), .45))
    h = M('ADD', h, M('MULTIPLY', M('MULTIPLY', T, grip), .22))
    h = M('ADD', h, M('MULTIPLY', M('MULTIPLY', P, hexl), .20))          # the ripstop's threads stand
    h = M('ADD', h, M('MULTIPLY', E, .12))
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = .45
    bump.inputs["Distance"].default_value = .0010
    L.new(h, bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m
