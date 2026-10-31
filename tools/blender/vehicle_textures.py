"""Vehicle textures: everything the modern cars and hover boards need, made in Blender.

Two kinds of maps:
  * tiling materials baked with textures.bake() and the seamless 4D-torus noise of textures.G
    (seat fabric, quilted inserts, leather, soft-touch dash, carpet, headliner, grille mesh, speaker cloth,
    brushed aluminium, brake disc, grip tape)
  * layout maps rendered with an orthographic camera over flat emission shapes and text objects
    (tyre sidewall + tread, gauge faces, infotainment screen, number plates, head/tail lamp internals,
    bullet hole and cracked-glass decals). Height passes are turned into tangent normal maps with numpy.
Outputs assets/textures/veh_<name>_c.jpg, _n.jpg (normal) and _e.jpg (emissive / alpha mask).
Run: blender --background --python tools/blender/vehicle_textures.py
"""
import bpy, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import bl
from textures import bake, setup, G

OUT = bl.TEXTURES


def lin(c):
    if isinstance(c, str):
        return bl.hexrgb(c)
    if isinstance(c, (int, float)):
        return (c, c, c)
    return c


# ------------------------------------------------------------------ layout renderer
class Layout:
    """Flat 2D layout in a W x H unit rectangle, rendered top-down to px_w x px_h."""

    def __init__(self, W, H, px_w, px_h, mode='c'):
        bl.reset()
        self.W, self.H, self.mode = W, H, mode
        sc = self.sc = bpy.context.scene
        sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.device = 'CPU'
        try:
            sc.cycles.use_denoising = False
        except Exception:
            pass
        sc.render.resolution_x, sc.render.resolution_y = px_w, px_h
        sc.render.resolution_percentage = 100
        sc.view_settings.view_transform = 'Raw' if mode == 'h' else 'Standard'
        sc.view_settings.look = 'None'
        sc.render.film_transparent = False
        sc.render.filter_size = 1.0
        w = bpy.data.worlds.new('w'); sc.world = w
        try:
            w.node_tree.nodes['Background'].inputs[0].default_value = (0, 0, 0, 1)
        except Exception:
            w.color = (0, 0, 0)
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = max(W, H)
        cam.location = (W / 2, H / 2, 50); cam.rotation_euler = (0, 0, 0)
        cam.data.clip_end = 200
        self.z = 0.0
        self._mats = {}

    def m(self, c=0.0, h=0.0, e=0.0):
        """Material for the current pass: c = colour, h = height (0..1), e = emission mask colour."""
        v = {'c': c, 'h': h, 'e': e}[self.mode]
        key = repr(v)
        if key in self._mats:
            return self._mats[key]
        mt = bpy.data.materials.new('L')
        nt = mt.node_tree
        for nd in list(nt.nodes):
            if nd.type != 'OUTPUT_MATERIAL':
                nt.nodes.remove(nd)
        out = [nd for nd in nt.nodes if nd.type == 'OUTPUT_MATERIAL'][0]
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (*lin(v), 1)
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        self._mats[key] = mt
        return mt

    def _z(self):
        self.z += .001
        return self.z

    def poly(self, pts, mat):
        z = self._z()
        o = bl.mesh_from('p', [(x, y, z) for x, y in pts], [tuple(range(len(pts)))], mat)
        return o

    def rect(self, x0, y0, x1, y1, mat):
        return self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], mat)

    def rrect(self, x0, y0, x1, y1, r, mat, seg=6):
        pts = []
        for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
            for k in range(seg + 1):
                a = math.radians(a0 + 90 * k / seg)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return self.poly(pts, mat)

    def circle(self, cx, cy, r, mat, seg=64):
        return self.poly([(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)], mat)

    def arc(self, cx, cy, r0, r1, a0, a1, mat, seg=48):
        """Annulus sector between angles a0..a1 (degrees, maths convention)."""
        z = self._z()
        vs, fs = [], []
        for i in range(seg + 1):
            a = math.radians(a0 + (a1 - a0) * i / seg)
            vs += [(cx + r0 * math.cos(a), cy + r0 * math.sin(a), z), (cx + r1 * math.cos(a), cy + r1 * math.sin(a), z)]
            if i:
                fs.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
        return bl.mesh_from('a', vs, fs, mat)

    def line(self, x0, y0, x1, y1, w, mat):
        dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L * w / 2, dx / L * w / 2
        return self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], mat)

    def text(self, s, x, y, size, mat, rot=0.0, align='CENTER', sx=1.0, sy=1.0, spacing=1.0):
        cu = bpy.data.curves.new('t', 'FONT'); cu.body = s; cu.size = size
        cu.align_x = align; cu.align_y = 'CENTER'; cu.space_character = spacing
        o = bpy.data.objects.new('t', cu); self.sc.collection.objects.link(o)
        o.location = (x, y, self._z()); o.rotation_euler = (0, 0, rot); o.scale = (sx, sy, 1)
        cu.materials.append(mat)
        return o

    def render(self, path):
        self.sc.render.image_settings.file_format = 'PNG' if path.endswith('.png') else 'JPEG'
        if path.endswith('.jpg'):
            self.sc.render.image_settings.quality = 90
        self.sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        return path


def height_to_normal(png, out_jpg, strength=4.0, wrap=True):
    img = bpy.data.images.load(png)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, 0]
    if wrap:
        dx = (np.roll(a, -1, 1) - np.roll(a, 1, 1)) * .5
        dy = (np.roll(a, -1, 0) - np.roll(a, 1, 0)) * .5
    else:
        dx = np.gradient(a, axis=1); dy = np.gradient(a, axis=0)
    nx, ny, nz = -dx * strength, -dy * strength, np.ones_like(a)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([(nx / L + 1) * .5, (ny / L + 1) * .5, (nz / L + 1) * .5, np.ones_like(a)], -1)
    im = bpy.data.images.new('nrm', w, h)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels = rgb.ravel()
    im.filepath_raw = out_jpg; im.file_format = 'JPEG'
    bpy.context.scene.render.image_settings.quality = 90
    im.save()
    os.remove(png)
    print('[texture]', os.path.basename(out_jpg))


def layout(name, W, H, pw, ph, build, kinds=('c',), nstrength=4.0, wrap=False):
    """build(L) draws the layout; it is called once per pass (c colour, h height -> normal, e emission)."""
    for k in kinds:
        L = Layout(W, H, pw, ph, 'h' if k == 'n' else k)
        build(L)
        if k == 'n':
            tmp = os.path.join(OUT, '_h_%s.png' % name)
            L.render(tmp)
            height_to_normal(tmp, os.path.join(OUT, 'veh_%s_n.jpg' % name), nstrength, wrap)
        else:
            L.render(os.path.join(OUT, 'veh_%s_%s.jpg' % (name, k)))
            print('[texture]', 'veh_%s_%s.jpg' % (name, k))


# ------------------------------------------------------------------ layouts
TYRE_BRAND = 'VELTRA'


def tyre(L):
    """2048x512: u = half the circumference, v = profile (0-.3 outer wall, .3-.7 tread, .7-1 inner wall)."""
    W, H = 4.0, 1.0
    rub = L.m('#1a1a1c', .3)
    L.rect(0, 0, W, H, rub)
    # sidewall ribs and a bead ring
    L.rect(0, 0, W, .035, L.m('#121213', .1))
    for v in (.06, .265):
        L.rect(0, v, W, v + .01, L.m('#202022', .45))
    L.rect(0, .7, W, 1, L.m('#19191b', .3))
    # raised letters (squashed to keep world proportions on the 0.1 m tall wall)
    sq = .55
    letter = L.m('#2c2c2f', .75)
    for k in range(2):
        u0 = k * 2.0
        L.text(TYRE_BRAND, u0 + .55, .165, .13, letter, sx=1.0, sy=sq, spacing=1.15)
        L.text('ALLROAD TOURER', u0 + 1.35, .17, .055, letter, sy=sq)
        L.text('225/45 R17 94W', u0 + 1.75, .12, .05, letter, sy=sq)
        L.text('M+S', u0 + 1.95, .2, .045, letter, sy=sq)
        L.text('TUBELESS  RADIAL', u0 + 1.5, .225, .032, letter, sy=sq)
    for k in range(4):
        L.text('DOT 4K7 2626  MAX LOAD 670 KG', .5 + k, .85, .035, L.m('#262628', .6), sy=sq)
    # tread: blocks separated by 4 circumferential grooves and angled sipes
    tread = L.m('#222224', .9)
    groove = L.m('#0c0c0d', .0)
    L.rect(0, .3, W, .7, tread)
    for v in (.36, .455, .545, .64):
        L.rect(0, v - .012, W, v + .012, groove)
    n = 96
    for i in range(n):
        u = W * i / n
        for (va, vb, sk) in ((.3, .348, .02), (.372, .443, -.015), (.467, .533, .0), (.557, .628, .015), (.652, .7, -.02)):
            L.line(u, va, u + sk, vb, .008, groove)
    # shoulder blocks
    for i in range(n):
        u = W * (i + .5) / n
        L.line(u, .28, u + .01, .3, .012, L.m('#141415', .5))
        L.line(u, .7, u + .01, .72, .012, L.m('#141415', .5))


def gauges(L):
    """1024x512 two-dial cluster: speed 0-240 km/h (left), revs 0-8 x1000 (right). 240 deg sweep."""
    W, H = 2.0, 1.0
    face = L.m('#08090b', 0, '#000000')
    L.rect(0, 0, W, H, face)
    tick = L.m('#e8eef4', 1, '#d8ecff')
    redc = L.m('#ff3a2a', 1, '#ff2a1a')
    soft = L.m('#9aa6b2', 1, '#5c7a99')
    for cx, maxv, step, sub, label, red in ((.5, 240, 20, 10, 'km/h', None), (1.5, 8, 1, .5, 'x1000 r/min', 6.5)):
        cy, R = .5, .46
        L.circle(cx, cy, R, L.m('#0e1014', 0, '#000000'))
        L.arc(cx, cy, R - .012, R - .004, -30, 210, L.m('#3a4654', 0, '#16324a'))
        nmaj = int(round(maxv / step))
        for i in range(int(round(maxv / sub)) + 1):
            v = i * sub; f = v / maxv
            a = math.radians(210 - 240 * f)
            major = abs((v / step) - round(v / step)) < 1e-6
            r0 = R - (.085 if major else .055)
            m = redc if red and v >= red else tick
            L.line(cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + (R - .02) * math.cos(a), cy + (R - .02) * math.sin(a), .012 if major else .006, m)
            if major:
                rr = R - .15
                L.text(str(int(v)), cx + rr * math.cos(a), cy + rr * math.sin(a), .06, m)
        if red:
            L.arc(cx, cy, R - .05, R - .02, -30, 210 - 240 * red / maxv, redc)
        L.text(label, cx, cy - .2, .045, soft)
        L.circle(cx, cy, .035, L.m('#1c2026', 0, '#000000'))
    # centre strip between the dials: gear and range
    L.text('D', 1.0, .62, .1, L.m('#e8eef4', 1, '#9fd8ff'))
    L.text('412 km', 1.0, .4, .042, soft)
    L.text('21°C', 1.0, .3, .042, soft)


def screen(L):
    """512x256 infotainment: a navigation map with route, a status bar and media tile."""
    W, H = 2.0, 1.0
    L.rect(0, 0, W, H, L.m('#0a1420', 0, '#0a1420'))
    land = L.m('#13243a', 0, '#13243a')
    L.rect(.02, .04, 1.36, .86, land)
    road = L.m('#5f7894', 0, '#5f7894')
    for i in range(7):
        L.line(.02, .1 + i * .12, 1.36, .14 + i * .1, .012, road)
        L.line(.1 + i * .19, .04, .18 + i * .17, .86, .012, road)
    L.rect(.02, .42, 1.36, .5, L.m('#1e5aa8', 0, '#1e5aa8'))      # the river
    route = L.m('#3ad6ff', 0, '#3ad6ff')
    pts = [(.2, .12), (.45, .3), (.5, .55), (.9, .62), (1.2, .78)]
    for a, b in zip(pts, pts[1:]):
        L.line(a[0], a[1], b[0], b[1], .03, route)
    L.circle(.2, .12, .035, L.m('#ffffff', 0, '#ffffff'))
    L.rect(0, .88, W, 1, L.m('#06090e', 0, '#06090e'))
    white = L.m('#e8eef4', 0, '#e8eef4')
    L.text('18:42', .14, .94, .06, white)
    L.text('NAV    MEDIA    CLIMATE    PHONE', 1.0, .94, .045, L.m('#8fa6be', 0, '#8fa6be'))
    L.rrect(1.42, .5, 1.96, .84, .03, L.m('#16283c', 0, '#16283c'))
    L.text('Meridian FM', 1.69, .74, .05, white)
    L.text('98.4', 1.69, .62, .08, route)
    L.rrect(1.42, .08, 1.96, .44, .03, L.m('#16283c', 0, '#16283c'))
    L.text('21.0°', 1.69, .3, .09, white)
    L.text('AUTO  A/C', 1.69, .16, .04, L.m('#8fa6be', 0, '#8fa6be'))


PLATES = ['NM 4K217', 'MER 08A5', '7TQ 512', 'LX 3390', 'NM 51R2', 'KY 2804', 'VR 77Q1', 'NM 9C40']


def plates(L):
    """1024x512 atlas: 2 columns x 4 rows of invented New Meridian plates (cell 512x128)."""
    W, H = 2.0, 1.0
    L.rect(0, 0, W, H, L.m('#20262c', 0))
    for k, s in enumerate(PLATES):
        c, r = k % 2, k // 2
        x0, y0 = c * 1.0, r * .25
        L.rrect(x0 + .01, y0 + .01, x0 + .99, y0 + .24, .02, L.m('#1b1e22', .4))
        L.rrect(x0 + .018, y0 + .018, x0 + .982, y0 + .232, .016, L.m('#f2f0ea', .5))
        L.rect(x0 + .03, y0 + .03, x0 + .13, y0 + .22, L.m('#1f4a9a', .5))
        L.text('NM', x0 + .08, y0 + .09, .05, L.m('#f2f0ea', .55))
        L.circle(x0 + .08, y0 + .17, .025, L.m('#e3c26c', .55))
        L.text(s, x0 + .56, y0 + .118, .15, L.m('#121418', 1.0), sx=.85)
        L.text('NEW MERIDIAN', x0 + .56, y0 + .035, .03, L.m('#4a5058', .7))


def headlamp(L):
    """512x256: chrome reflector bowl, two projector lenses, LED daytime strip on top, amber indicator."""
    W, H = 2.0, 1.0
    L.rect(0, 0, W, H, L.m('#30343a', 0, '#000000'))
    for i in range(12):
        L.rect(0, i / 12, W, i / 12 + .04, L.m('#4a5058', 0, '#000000'))
    for cx in (.62, 1.12):
        L.circle(cx, .42, .27, L.m('#8a929c', 0, '#000000'))
        L.circle(cx, .42, .22, L.m('#1a1d22', 0, '#3a3a36'))
        L.circle(cx, .42, .16, L.m('#dfe8f2', 0, '#fff6e6'))
        L.circle(cx, .42, .07, L.m('#ffffff', 0, '#ffffff'))
    L.rrect(.1, .8, 1.9, .9, .05, L.m('#f4f8ff', 0, '#eaf4ff'))
    L.rrect(1.5, .18, 1.92, .66, .05, L.m('#c88a2a', 0, '#4a2a00'))
    for i in range(5):
        L.rect(1.55, .24 + i * .085, 1.87, .26 + i * .085, L.m('#e6a84a', 0, '#5a3300'))


def taillamp(L):
    """512x256: dark red lens with LED light bars, a white reverse segment and inner reflector ribs."""
    W, H = 2.0, 1.0
    L.rect(0, 0, W, H, L.m('#3a0608', 0, '#200000'))
    for i in range(16):
        L.rect(0, i / 16 + .02, W, i / 16 + .035, L.m('#5a0a0e', 0, '#300000'))
    for i in range(3):
        L.rrect(.06, .62 + i * .11, 1.94, .68 + i * .11, .03, L.m('#ff3a3a', 0, '#ff2a20'))
    L.rrect(.06, .1, 1.94, .5, .05, L.m('#7a0c12', 0, '#9a0a0a'))
    L.rrect(1.3, .14, 1.88, .46, .04, L.m('#d8d8dc', 0, '#000000'))     # reverse light (dark until reversing)
    for i in range(10):
        L.circle(.16 + i * .11, .3, .035, L.m('#ff5a4a', 0, '#ff3020'))


def bullethole(L):
    """256x256 decal: punched hole, chipped paint ring, small radial cracks. e = alpha mask."""
    W = H = 1.0
    L.rect(0, 0, W, H, L.m('#808080', 0, '#000000'))
    import random
    r = random.Random(7)
    for i in range(14):
        a = r.random() * 2 * math.pi; l = .18 + r.random() * .22
        L.line(.5, .5, .5 + math.cos(a) * l, .5 + math.sin(a) * l, .012 + r.random() * .01, L.m('#3a3a3a', 0, '#5a5a5a'))
    L.circle(.5, .5, .2, L.m('#9a9ea4', 0, '#bdbdbd'), 20)
    L.circle(.5, .5, .15, L.m('#5e6064', 0, '#ffffff'), 18)
    L.circle(.5, .5, .09, L.m('#0a0a0a', 0, '#ffffff'), 16)


def glasscrack(L):
    """512x512 decal: spider-web crack: radial lines + broken concentric rings. e = alpha mask."""
    W = H = 1.0
    L.rect(0, 0, W, H, L.m('#cfd8de', 0, '#000000'))
    import random
    r = random.Random(11)
    rays = []
    for i in range(18):
        a = 2 * math.pi * i / 18 + r.uniform(-.12, .12)
        rays.append(a)
        x, y, rad = .5, .5, 0.0
        while rad < .48:
            step = r.uniform(.03, .07); a += r.uniform(-.15, .15); rad += step
            nx, ny = .5 + math.cos(a) * rad, .5 + math.sin(a) * rad
            L.line(x, y, nx, ny, .005 * (1 - rad) + .002, L.m('#ffffff', 0, '#ffffff'))
            x, y = nx, ny
    for ring in (.06, .12, .2, .3):
        for i in range(18):
            if r.random() < .3:
                continue
            a0 = rays[i]; a1 = rays[(i + 1) % 18] + (2 * math.pi if i == 17 else 0)
            rr = ring * r.uniform(.85, 1.15)
            L.line(.5 + math.cos(a0) * rr, .5 + math.sin(a0) * rr, .5 + math.cos(a1) * rr, .5 + math.sin(a1) * rr, .004, L.m('#ffffff', 0, '#e0e0e0'))
    L.circle(.5, .5, .025, L.m('#ffffff', 0, '#ffffff'), 12)


def badges(L):
    """512x128: emblem disc + model wordmarks used on bonnet, grille and tailgate (chrome on black)."""
    W, H = 4.0, 1.0
    L.rect(0, 0, W, H, L.m('#151618', .0))
    chrome = L.m('#e6eaee', 1.0)
    # emblem: ring with a stylised arrowhead (invented marque)
    L.arc(.5, .5, .36, .44, 0, 360, chrome, 48)
    L.poly([(.5, .82), (.78, .28), (.5, .42), (.22, .28)], chrome)
    # wordmarks, one per quarter-width cell after the emblem: u 0.25-0.5, 0.5-0.75, 0.75-1.0
    for i, s in enumerate(['PIP', 'ARIA', 'CAIRN']):
        L.text(s, 1.5 + i, .5, .34 if len(s) < 5 else .27, chrome, spacing=1.1)


# ------------------------------------------------------------------ baked tiling materials
def tiling(p):
    # woven seat fabric: tight twill + fibre noise
    def fab_h(g):
        b = g.brick(.03125, .015625, offset=.5, mortar=.003)
        return g.math('ADD', g.math('MULTIPLY', b.outputs['Fac'], -.6), g.math('MULTIPLY', g.noise(90, 3, .5, 31), .4))

    def fab_c(g):
        base = g.ramp(g.noise(60, 5, .6, 30), [(.3, '#3a3c40'), (.7, '#55585e')])
        b = g.brick(.03125, .015625, offset=.5, mortar=.003, c1=(1, 1, 1), c2=(.86, .86, .88))
        return g.mix(base, b.outputs['Color'], 1.0, 'MULTIPLY')
    bake(p, 'veh_seatfab', fab_c, fab_h, strength=.5)

    # quilted insert: horizontal channels (4 per tile) with stitched seams
    def quilt_h(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        ch = g.math('SINE', g.math('MULTIPLY', sep.outputs[1], 2 * math.pi * 4))
        pad = g.math('POWER', g.math('ABSOLUTE', ch), .35)
        stitch = g.brick(.03125, .25, offset=0, mortar=.01).outputs['Fac']
        return g.math('SUBTRACT', g.math('ADD', g.math('MULTIPLY', pad, .8), g.math('MULTIPLY', g.noise(80, 3, .5, 33), .15)), g.math('MULTIPLY', stitch, .2))

    def quilt_c(g):
        base = g.ramp(g.noise(50, 5, .6, 32), [(.3, '#2b2c2f'), (.7, '#3e4044')])
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        seam = g.math('LESS_THAN', g.math('ABSOLUTE', g.math('SINE', g.math('MULTIPLY', sep.outputs[1], 2 * math.pi * 4))), .07)
        dash = g.math('GREATER_THAN', g.math('SINE', g.math('MULTIPLY', sep.outputs[0], 2 * math.pi * 64)), 0)
        thread = g.math('MULTIPLY', seam, dash)
        return g.mix(base, (.62, .6, .55), thread)
    bake(p, 'veh_quilt', quilt_c, quilt_h, strength=.9)

    # leather grain
    def lea_h(g):
        v = g.voronoi(70, 34, 'F2', 'Distance')
        return g.math('ADD', g.math('MULTIPLY', v, .5), g.math('MULTIPLY', g.noise(140, 2, .5, 35), .3))

    def lea_c(g):
        a = g.ramp(g.noise(12, 6, .6, 36), [(.3, '#d8d4cf'), (.7, '#ffffff')])
        cr = g.ramp(g.voronoi(70, 34, 'F2', 'Distance'), [(.0, '#b8b4ae'), (.18, '#ffffff')])
        return g.mix(a, cr, 1.0, 'MULTIPLY')
    bake(p, 'veh_leather', lea_c, lea_h, strength=.35)

    # soft-touch dashboard plastic (fine pebble)
    def dash_h(g):
        return g.math('ADD', g.math('MULTIPLY', g.voronoi(120, 37, 'F1', 'Distance'), .6), g.math('MULTIPLY', g.noise(200, 2, .5, 38), .2))

    def dash_c(g):
        return g.ramp(g.noise(20, 6, .6, 39), [(.35, '#e6e6e6'), (.65, '#ffffff')])
    bake(p, 'veh_dash', dash_c, dash_h, strength=.25)

    # carpet
    def car_h(g):
        return g.noise(260, 4, .7, 40)

    def car_c(g):
        a = g.ramp(g.noise(260, 4, .7, 40), [(.3, '#202124'), (.7, '#34363a')])
        b = g.ramp(g.noise(8, 4, .5, 41), [(.3, '#d8d8d8'), (.7, '#ffffff')])
        return g.mix(a, b, 1.0, 'MULTIPLY')
    bake(p, 'veh_carpet', car_c, car_h, strength=.6)

    # headliner felt (light)
    def hl_c(g):
        return g.ramp(g.noise(160, 4, .6, 42), [(.3, '#b9b4ab'), (.7, '#cfcac1')])
    bake(p, 'veh_headliner', hl_c, lambda g: g.noise(160, 4, .6, 42), strength=.25)

    # honeycomb grille mesh
    def gr_h(g):
        b = g.brick(.0625, .0625, offset=.5, mortar=.012, squash=1.0)
        return g.math('SUBTRACT', 1.0, b.outputs['Fac'])

    def gr_c(g):
        b = g.brick(.0625, .0625, offset=.5, mortar=.012, c1=(.01, .01, .012), c2=(.015, .015, .018))
        return g.mix(b.outputs['Color'], (.09, .09, .1), b.outputs['Fac'])
    bake(p, 'veh_grille', gr_c, gr_h, strength=1.2)

    # speaker cloth / perforated metal
    def sp_h(g):
        v = g.voronoi(48, 43, 'F1', 'Distance')
        return g.math('GREATER_THAN', v, .28)

    def sp_c(g):
        v = g.voronoi(48, 43, 'F1', 'Distance')
        return g.mix((.02, .02, .022), (.16, .16, .17), g.math('GREATER_THAN', v, .28))
    bake(p, 'veh_speaker', sp_c, sp_h, strength=.8)

    # brushed aluminium trim (streaks along u)
    def br_c(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        streak = g.noise(4, 2, .5, 44)
        fine = g.voronoi(3, 45, 'F1', 'Distance')
        k = g.math('ADD', g.math('MULTIPLY', streak, .5), g.math('MULTIPLY', g.noise(220, 2, .4, 46), .5))
        return g.ramp(k, [(.3, '#9da2a8'), (.7, '#d2d6db')])
    bake(p, 'veh_brushed', br_c)

    # brake disc: u around, v radius (0 hub .. 1 rim): concentric scoring, drilled holes, dark hat
    def bd_c(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        v = sep.outputs[1]
        grooves = g.math('ADD', g.math('MULTIPLY', g.math('SINE', g.math('MULTIPLY', v, 2 * math.pi * 30)), .25), g.noise(6, 4, .6, 47))
        metal = g.ramp(grooves, [(.2, '#5a5d61'), (.8, '#9a9ea3')])
        hat = g.math('LESS_THAN', v, .38)
        holes = g.math('MULTIPLY', g.math('LESS_THAN', g.voronoi(24, 48, 'F1', 'Distance'), .12), g.math('GREATER_THAN', v, .5))
        c = g.mix(metal, (.12, .12, .13), hat)
        return g.mix(c, (.02, .02, .02), holes)

    def bd_h(g):
        tc = g.uv(); sep = g.n('ShaderNodeSeparateXYZ'); g.nt.links.new(tc, sep.inputs[0])
        holes = g.math('MULTIPLY', g.math('LESS_THAN', g.voronoi(24, 48, 'F1', 'Distance'), .12), g.math('GREATER_THAN', sep.outputs[1], .5))
        return g.math('SUBTRACT', g.math('MULTIPLY', g.math('SINE', g.math('MULTIPLY', sep.outputs[1], 2 * math.pi * 30)), .15), holes)
    bake(p, 'veh_disc', bd_c, bd_h, strength=.8)

    # board grip tape: dark grit
    def gt_h(g):
        return g.math('ADD', g.math('MULTIPLY', g.voronoi(180, 49, 'F1', 'Distance'), -1), g.math('MULTIPLY', g.noise(300, 2, .5, 50), .4))

    def gt_c(g):
        return g.ramp(g.noise(300, 3, .6, 51), [(.3, '#141516'), (.7, '#2a2b2e')])
    bake(p, 'veh_grip', gt_c, gt_h, strength=1.0)


def main():
    p = setup()
    tiling(p)
    layout('tyre', 4, 1, 2048, 512, tyre, ('c', 'n'), nstrength=6.0, wrap=True)
    layout('gauges', 2, 1, 1024, 512, gauges, ('c', 'e'))
    layout('screen', 2, 1, 512, 256, screen, ('c',))
    layout('plates', 2, 1, 1024, 512, plates, ('c', 'n'), nstrength=3.0)
    layout('headlamp', 2, 1, 512, 256, headlamp, ('c', 'e'))
    layout('taillamp', 2, 1, 512, 256, taillamp, ('c', 'e'))
    layout('bullethole', 1, 1, 256, 256, bullethole, ('c', 'e'))
    layout('glasscrack', 1, 1, 512, 512, glasscrack, ('c', 'e'))
    layout('badges', 4, 1, 512, 128, badges, ('c',))


if __name__ == '__main__':
    main()
