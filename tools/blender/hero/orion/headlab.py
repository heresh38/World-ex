"""The head lab: the new head (head.py) meshed finely and rendered from the views a sculptor checks, in clay or in
skin with its eyes, beside the owner's portrait from the same side.

blender -b -P tools/blender/hero/orion/headlab.py -- <out.png> [--h=0.0007] [--views=portrait,front,q,side]
    [--groom] (hair and brows; the base model is clean-shaven) [--beard] (the beard, an option of the creator)
                                                     [--clay] [--samples=96] [--res=800] [--save=x.blend]

  portrait   the owner's portrait's own view (turned to his left, from a touch below), beside it
  front / q / side / back / low
The sheet is the views side by side; each view is also written as <out>_<view>.png.
"""
import bpy, math, os, sys, time
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import sdf  # noqa: E402
import head as H  # noqa: E402

SHEET = os.path.join(ROOT, "art", "reference", "player", "orion_tpose_bodysuit.png")
PORTRAIT = (1200, 0, 1536, 500)                     # the portrait's box on the sheet


def log(*a):
    print("[headlab]", *a, flush=True)


def gpu(sc):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = 'GPU'
                return kind
    except Exception as e:
        log("no graphics card:", e)
    sc.cycles.device = 'CPU'
    return "CPU"


def to_object(name, V, F, origin=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [list(f) for f in F])
    me.update()
    o = bpy.data.objects.new(name, me)
    o.location = origin
    bpy.context.scene.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = True
    return o


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def skin_material(clay=False):
    """a man's tanned olive skin: the colour a little deeper and redder where blood lies close (cheeks, nose, ears,
    lips), darker in the eyes' hollows and where the beard grows, light carried under the skin (subsurface, a few
    millimetres in red, less in green and blue), an oily sheen over the nose and forehead and a dry one elsewhere,
    pores and fine creases in the normal"""
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if clay:
        b.inputs["Base Color"].default_value = (.30, .28, .265, 1)
        b.inputs["Roughness"].default_value = .55
        return m
    tc = nt.nodes.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(pos, sep.inputs[0])

    def math_(op, a, bv=None, c=None):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = op
        for i, v in enumerate((a, bv, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    def blob(cx, cy, cz, rx, ry, rz, mirror=True):
        """exp(-|((p - c) / r)|^2) in the head's frame (world metres), mirrored across the midline"""
        x = sep.outputs[0]
        if mirror:
            x = math_('ABSOLUTE', x)
        dx = math_('DIVIDE', math_('SUBTRACT', x, cx), rx)
        dy = math_('DIVIDE', math_('SUBTRACT', sep.outputs[1], cy), ry)
        dz = math_('DIVIDE', math_('SUBTRACT', sep.outputs[2], cz), rz)
        sq = math_('ADD', math_('ADD', math_('MULTIPLY', dx, dx), math_('MULTIPLY', dy, dy)), math_('MULTIPLY', dz, dz))
        return math_('EXPONENT', math_('MULTIPLY', sq, -1.0))

    Y0, Z0 = H.Y0, H.Z0
    # where the blood shows: the cheeks, the nose, the ears, the lips
    red = math_('ADD', math_('MULTIPLY', blob(.036, Y0 - .088, Z0 - .03, .02, .02, .018), .42),
                math_('MULTIPLY', blob(0, Y0 - .12, Z0 - .038, .011, .014, .012, False), .38))   # the nose redder
    red = math_('ADD', red, math_('MULTIPLY', blob(0, Y0 - .108, Z0 - .102, .016, .01, .01, False), .14))  # the chin
    red = math_('ADD', red, math_('MULTIPLY', blob(.072, Y0 + .005, Z0 - .01, .012, .025, .035), .5))
    red = math_('ADD', red, math_('MULTIPLY', blob(.0186, Y0 - .0821, Z0 + .0002, .0024, .0024, .0024), .95))
    red = math_('MINIMUM', red, 1.0)
    # the eyes' hollows a little darker
    dark = math_('ADD', math_('MULTIPLY', blob(.032, Y0 - .09, Z0 + .002, .02, .012, .012), .5),
                 math_('MULTIPLY', blob(.03, Y0 - .088, Z0 - .009, .015, .008, .005), .35))
    # inside the nostrils: dark (the light carried under the skin lit them red)
    dark = math_('MINIMUM', math_('ADD', dark, math_('MULTIPLY', blob(.0068, Y0 - .1165, Z0 - .0442, .0035, .0058, .0028),
                                                       .95)), 1.0)
    base = node(nt, "ShaderNodeRGB"); base.outputs[0].default_value = (.33, .215, .155, 1)   # olive, tanned
    flush = node(nt, "ShaderNodeRGB"); flush.outputs[0].default_value = (.365, .19, .14, 1)
    mix_r = nt.nodes.new("ShaderNodeMix"); mix_r.data_type = 'RGBA'
    nt.links.new(red, mix_r.inputs[0]); nt.links.new(base.outputs[0], mix_r.inputs[6]); nt.links.new(flush.outputs[0], mix_r.inputs[7])
    shadow = node(nt, "ShaderNodeRGB"); shadow.outputs[0].default_value = (.19, .118, .085, 1)
    mix_d = nt.nodes.new("ShaderNodeMix"); mix_d.data_type = 'RGBA'
    nt.links.new(dark, mix_d.inputs[0]); nt.links.new(mix_r.outputs[2], mix_d.inputs[6]); nt.links.new(shadow.outputs[0], mix_d.inputs[7])
    # mottling: the colour's own small variation
    noise = node(nt, "ShaderNodeTexNoise", Scale=180.0, Detail=8.0, Roughness=.55)
    nt.links.new(pos, noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (.88, .84, .82, 1); ramp.color_ramp.elements[1].color = (1.06, 1.0, .98, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mott = nt.nodes.new("ShaderNodeMix"); mott.data_type = 'RGBA'; mott.blend_type = 'MULTIPLY'
    mott.inputs[0].default_value = 1.0
    broad = node(nt, "ShaderNodeTexNoise", Scale=22.0, Detail=3.0, Roughness=.5)
    nt.links.new(pos, broad.inputs["Vector"])
    bramp = nt.nodes.new("ShaderNodeValToRGB")
    bramp.color_ramp.elements[0].color = (.93, .92, .94, 1); bramp.color_ramp.elements[1].color = (1.05, 1.02, .99, 1)
    nt.links.new(broad.outputs["Fac"], bramp.inputs["Fac"])
    var = nt.nodes.new("ShaderNodeMix"); var.data_type = 'RGBA'; var.blend_type = 'MULTIPLY'
    var.inputs[0].default_value = 1.0
    nt.links.new(mix_d.outputs[2], var.inputs[6]); nt.links.new(bramp.outputs[0], var.inputs[7])
    # the forehead a little lighter and yellower than the cheeks
    fore = blob(0, Y0 - .095, Z0 + .055, .05, .03, .025, False)
    light_ = nt.nodes.new("ShaderNodeMix"); light_.data_type = 'RGBA'
    nt.links.new(math_('MULTIPLY', fore, .35), light_.inputs[0])
    nt.links.new(var.outputs[2], light_.inputs[6])
    light_.inputs[7].default_value = (.36, .245, .17, 1)
    spots = node(nt, "ShaderNodeTexVoronoi", Scale=230.0)
    nt.links.new(pos, spots.inputs["Vector"])
    ssep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(spots.outputs["Color"], ssep.inputs[0])
    spot = math_('MULTIPLY', math_('GREATER_THAN', ssep.outputs[0], .955),
                 math_('SUBTRACT', 1.0, math_('MINIMUM', math_('MULTIPLY', spots.outputs["Distance"], 4.0), 1.0)))
    spotc = nt.nodes.new("ShaderNodeMix"); spotc.data_type = 'RGBA'
    nt.links.new(math_('MULTIPLY', spot, .4), spotc.inputs[0])
    nt.links.new(light_.outputs[2], spotc.inputs[6])
    spotc.inputs[7].default_value = (.2, .12, .085, 1)
    nt.links.new(spotc.outputs[2], mott.inputs[6]); nt.links.new(ramp.outputs[0], mott.inputs[7])
    # the beard's shadow under the skin
    battr = nt.nodes.new("ShaderNodeAttribute"); battr.attribute_name = "beard"
    bsep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(battr.outputs["Color"], bsep.inputs[0])
    shade = nt.nodes.new("ShaderNodeMix"); shade.data_type = 'RGBA'
    nt.links.new(mott.outputs[2], shade.inputs[6])
    shade.inputs[7].default_value = (.15, .125, .115, 1)       # under the skin a shaved beard is grey-blue
    nt.links.new(math_('MULTIPLY', bsep.outputs[0], .72), shade.inputs[0])
    lattr = nt.nodes.new("ShaderNodeAttribute"); lattr.attribute_name = "lip"
    lsep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(lattr.outputs["Color"], lsep.inputs[0])
    lipc = nt.nodes.new("ShaderNodeMix"); lipc.data_type = 'RGBA'
    nt.links.new(math_('MULTIPLY', lsep.outputs[0], .85), lipc.inputs[0])
    nt.links.new(shade.outputs[2], lipc.inputs[6])
    lipc.inputs[7].default_value = (.25, .13, .115, 1)          # a man's lips: a deeper, browner red
    nt.links.new(lipc.outputs[2], b.inputs["Base Color"])
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, .49, .33)
    b.inputs["Subsurface Scale"].default_value = .0022
    # oily on the nose and forehead, drier on the cheeks
    oil = math_('MINIMUM', math_('ADD', blob(0, Y0 - .115, Z0 - .025, .015, .03, .03, False),
                                 blob(0, Y0 - .095, Z0 + .045, .04, .03, .025, False)), 1.0)
    rough = math_('SUBTRACT', .58, math_('MULTIPLY', oil, .16))
    rough = math_('SUBTRACT', rough, math_('MULTIPLY', lsep.outputs[0], .14))
    rvar = node(nt, "ShaderNodeTexNoise", Scale=300.0, Detail=4.0, Roughness=.6)
    nt.links.new(pos, rvar.inputs["Vector"])
    rough = math_('ADD', rough, math_('MULTIPLY', math_('SUBTRACT', rvar.outputs["Fac"], .5), .14))
    nt.links.new(rough, b.inputs["Roughness"])
    b.inputs["Coat Weight"].default_value = .12                 # a second, sharper sheen: the skin's oil
    b.inputs["Coat Roughness"].default_value = .34
    b.inputs["Specular IOR Level"].default_value = .5
    # pores and fine creases
    pores = node(nt, "ShaderNodeTexVoronoi", Scale=2300.0)
    nt.links.new(pos, pores.inputs["Vector"])
    fine = node(nt, "ShaderNodeTexNoise", Scale=1400.0, Detail=4.0, Roughness=.7)
    nt.links.new(pos, fine.inputs["Vector"])
    pit = math_('POWER', math_('SUBTRACT', 1.0, math_('MINIMUM', math_('MULTIPLY', pores.outputs["Distance"], 2.6), 1.0)), 2.0)
    hsum = math_('SUBTRACT', math_('MULTIPLY', fine.outputs["Fac"], .3), math_('MULTIPLY', pit, 1.1))   # pores: pits
    grain = node(nt, "ShaderNodeTexVoronoi", Scale=1500.0)
    grain.feature = 'DISTANCE_TO_EDGE'
    try:
        grain.inputs["Detail"].default_value = 1.0           # plates of more than one size
    except KeyError:
        pass
    warp = node(nt, "ShaderNodeTexNoise", Scale=400.0, Detail=2.0)
    nt.links.new(pos, warp.inputs["Vector"])
    wpos = nt.nodes.new("ShaderNodeVectorMath"); wpos.operation = 'MULTIPLY_ADD'
    nt.links.new(warp.outputs["Color"], wpos.inputs[0]); wpos.inputs[1].default_value = (.0005, .0005, .0005)
    nt.links.new(pos, wpos.inputs[2])
    nt.links.new(wpos.outputs[0], grain.inputs["Vector"])
    groove = math_('SUBTRACT', 1.0, math_('MINIMUM', math_('MULTIPLY', grain.outputs["Distance"], 9.0), 1.0))
    gvar = node(nt, "ShaderNodeTexNoise", Scale=60.0, Detail=2.0)
    nt.links.new(pos, gvar.inputs["Vector"])
    gdepth = math_('ADD', .15, math_('MULTIPLY', gvar.outputs["Fac"], .4))     # deeper here, finer there
    hsum = math_('SUBTRACT', hsum, math_('MULTIPLY', groove, gdepth))      # the skin's grain
    # the skin's own unevenness under the pores (a few millimetres), the forehead's fine lines
    mid = node(nt, "ShaderNodeTexNoise", Scale=260.0, Detail=3.0, Roughness=.5)
    nt.links.new(pos, mid.inputs["Vector"])
    hsum = math_('ADD', hsum, math_('MULTIPLY', mid.outputs["Fac"], 1.6))
    lines = math_('SINE', math_('MULTIPLY', sep.outputs[2], 2 * math.pi / .0085))
    wob = node(nt, "ShaderNodeTexNoise", Scale=90.0, Detail=2.0)
    nt.links.new(pos, wob.inputs["Vector"])
    lines = math_('MULTIPLY', math_('MULTIPLY', lines, wob.outputs["Fac"]),
                  blob(0, Y0 - .098, Z0 + .045, .045, .03, .016, False))
    hsum = math_('ADD', hsum, math_('MULTIPLY', lines, .5))
    # the lips' fine vertical lines
    lwob = node(nt, "ShaderNodeTexNoise", Scale=700.0, Detail=2.0)
    nt.links.new(pos, lwob.inputs["Vector"])
    lipl = math_('MULTIPLY', math_('SINE', math_('ADD', math_('MULTIPLY', sep.outputs[0], 2 * math.pi / .0011),
                                                  math_('MULTIPLY', lwob.outputs["Fac"], 6.0))),
                 math_('MULTIPLY', lwob.outputs["Fac"], .4))
    hsum = math_('ADD', hsum, math_('MULTIPLY', lipl, lsep.outputs[0]))
    bump = node(nt, "ShaderNodeBump", Strength=.45, Distance=.0003)
    nt.links.new(hsum, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Coat Normal"])     # the sheen follows the pores too (or it is plastic)
    return m


def eye_material(name):
    """sclera, a grey-blue iris with its fibres and dark limbal ring, the pupil; a clear wet coat over it"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    vlen = nt.nodes.new("ShaderNodeVectorMath"); vlen.operation = 'NORMALIZE'
    nt.links.new(tc.outputs["Object"], vlen.inputs[0])
    sep2 = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(vlen.outputs[0], sep2.inputs[0])
    neg = nt.nodes.new("ShaderNodeMath")
    neg.operation = 'MULTIPLY'
    nt.links.new(sep2.outputs["Y"], neg.inputs[0]); neg.inputs[1].default_value = -1.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(neg.outputs[0], ramp.inputs["Fac"])
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = (.6, .53, .5, 1)       # the white of the eye is not white
    el[1].position = 1.0; el[1].color = (.004, .004, .005, 1)
    for pos, col in ((.70, (.66, .62, .58, 1)), (.835, (.7, .66, .62, 1)), (.842, (.05, .06, .07, 1)),
                     (.86, (.20, .27, .32, 1)), (.93, (.30, .38, .43, 1)), (.955, (.22, .26, .27, 1)),
                     (.962, (.006, .006, .007, 1))):
        e = el.new(pos); e.color = col
    nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = .05
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = .02
    return m


def studio(sc, beauty=False):
    sc.render.engine = 'CYCLES'
    gpu(sc)
    sc.cycles.use_denoising = True
    w = bpy.data.worlds.new("w"); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (.17, .17, .20, 1); bg.inputs[1].default_value = .35
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    target = Vector((0, H.Y0 - .06, H.Z0 - .02))

    def light(name, energy, loc, color, size):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.color = color; L.size = size
        L.shape = 'DISK'                     # a round softbox: the eyes' catchlights round, not square
        o = bpy.data.objects.new(name, L); o.location = loc
        o.rotation_euler = (target - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(o)
    if beauty:              # the owner's quality reference's light: a key in front to one side, a hard rim behind
        bg.inputs[0].default_value = (.01, .01, .012, 1); bg.inputs[1].default_value = .05
        light("key", 34, (-.25, -1.05, 2.0), (1, .96, .92), .75)
        light("rim", 48, (.7, .55, 1.95), (.95, .97, 1), .35)
        light("fill", 2.5, (.9, -.45, 1.6), (.85, .9, 1), 1.2)
        return
    # the portrait's light: a broad key high on his left, a soft fill, a cool rim behind
    light("key", 24, (.55, -.85, 2.15), (1, .95, .9), .9)
    light("fill", 5, (-.85, -.55, 1.80), (.8, .87, 1), 1.4)
    light("rim", 20, (-.35, .75, 2.05), (.85, .92, 1), .6)
    light("under", 1.2, (0, -.6, 1.35), (1, .92, .85), 1.0)


VIEWS = {  # yaw (degrees, positive = from his left), pitch, distance, lens
    "portrait": (-27, -4, .78, 85), "front": (0, 0, .70, 85), "q": (35, 0, .70, 85), "side": (90, 0, .70, 85),
    "back": (180, 0, .70, 85), "low": (25, -20, .70, 85), "qr": (-35, 0, .70, 85),
    "close": (-20, -3, .40, 85), "under": (10, -45, .55, 85),
    "face": (0, -2, .40, 85), "faceq": (32, -2, .40, 85), "faces": (90, -2, .42, 85),
    "eye": (-18, -2, .17, 85, (-.032, -.083, .001)), "skin": (-35, -4, .2, 85, (-.04, -.088, -.025)),
    "nose": (0, -4, .24, 85, (0, -.11, -.022)), "noseq": (-38, -4, .24, 85, (0, -.11, -.022)),
    "noses": (-90, -2, .26, 85, (0, -.105, -.022)), "noseu": (-15, -38, .24, 85, (0, -.11, -.03)),
}


def camera(sc, view):
    cam = sc.camera
    yaw, pitch, dist, lens = VIEWS[view][:4]
    off = VIEWS[view][4] if len(VIEWS[view]) > 4 else (0, -.055, -.035)        # where it looks (from the head's origin)
    target = Vector((off[0], H.Y0 + off[1], H.Z0 + off[2]))
    y, p = math.radians(yaw), math.radians(pitch)
    d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
    cam.location = target + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def profile_check(sc, out):
    """the head's outline from the side and the front against the sheet's (the sheet's rows put through the canon's
    landmarks as the body's are; its widths at the sheet's scale): <out>_profile.png, the head in white, the sheet's
    outline in green"""
    import body as B
    MPP = .0005
    views = {"side": (Vector((1, 0, 0)), (-.12, .22), "side", B.SIDE_C, -1),
             "front": (Vector((0, 1, 0)), (-.13, .13), "front", B.FRONT_C, 1)}
    z0, z1 = 1.47, 1.89
    panels = []
    for name, (d, (h0, h1), view, c0, sgn) in views.items():
        W, Hh = int((h1 - h0) / MPP), int((z1 - z0) / MPP)
        sc.render.resolution_x, sc.render.resolution_y = W, Hh
        sc.render.engine = 'BLENDER_WORKBENCH'
        sh = sc.display.shading
        sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (1, 1, 1)
        sh.background_type = 'VIEWPORT'; sh.background_color = (0, 0, 0)
        cam = sc.camera
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = max(W, Hh) * MPP
        # the image's right is +x (front view) / -y (side view); its centre at the window's middle
        hc = .5 * (h0 + h1)
        centre = Vector((hc, 0, 0)) if name == "front" else Vector((0, -hc, 0))
        cam.location = centre + Vector((0, 0, .5 * (z0 + z1))) - d * 3
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        path = out.replace(".png", f"_sil_{name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(path)
        sil = np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)[::-1][..., 0] > .5
        im = bpy.data.images.load(os.path.join(HERE, f"concept_mask_{view}.png"))
        mw, mh = im.size
        mask = np.array(im.pixels[:], np.float32).reshape(mh, mw, 4)[::-1][..., 0] > .5
        zs = z1 - (np.arange(Hh) + .5) * MPP
        hs = h0 + (np.arange(W) + .5) * MPP
        rows = np.array([B.Concept.row(z) for z in zs])
        cols = c0 + hs / B.CPX if name == "front" else c0 + hs / B.CPX
        R = np.clip(np.round(rows).astype(int), 0, mh - 1)[:, None]
        C = np.clip(np.round(cols).astype(int), 0, mw - 1)[None, :]
        cm = mask[R, C]
        img = np.zeros((Hh, W, 3), np.float32)
        img[sil] = (.75, .75, .75)
        e = np.zeros_like(cm)
        e[1:] |= cm[1:] != cm[:-1]; e[:, 1:] |= cm[:, 1:] != cm[:, :-1]
        img[e] = (.1, 1, .3)
        panels.append(img)
        # the profile's numbers: per centimetre of height, where the head's front is and the sheet's (side view)
        if name == "side":
            lines = []
            for z in np.arange(1.50, 1.86, .01):
                r = int((z1 - z) / MPP)
                a = np.nonzero(sil[r])[0]; b = np.nonzero(cm[r])[0]
                if len(a) and len(b):
                    lines.append(f"z {z:.2f} (head {(z - H.Z0) * 100:+.1f}): front {hs[a[-1]] * 100:+.1f} vs "
                                 f"{hs[b[-1]] * 100:+.1f} cm ({(hs[a[-1]] - hs[b[-1]]) * 100:+.1f})")
            open(out.replace(".png", "_profile.txt"), "w").write("\n".join(lines))
    Hh = max(p.shape[0] for p in panels)
    sheet = np.concatenate([np.pad(p, ((0, Hh - p.shape[0]), (0, 4), (0, 0))) for p in panels], axis=1)
    img = bpy.data.images.new("prof", sheet.shape[1], sheet.shape[0], alpha=False)
    img.pixels = np.concatenate([sheet[::-1], np.ones(sheet.shape[:2] + (1,), np.float32)], 2).ravel()
    img.filepath_raw = out.replace(".png", "_profile.png"); img.file_format = 'PNG'; img.save()
    log("profile", out.replace(".png", "_profile.png"))


def pfit(sc, out):
    """the head from the portrait's own camera (portrait_fit.py), laid half over the owner's portrait:
    <out>_pfit.png (the portrait, the head, the two blended)"""
    import json
    cam = json.load(open(os.path.join(HERE, "portrait_camera.json")))
    import math as m
    yaw, pitch, roll, s_, tu, tv = cam["yaw"], cam["pitch"], cam["roll"], cam["scale"], cam["tu"], cam["tv"]
    cy, sy, cp, sp, cr, sr = m.cos(yaw), m.sin(yaw), m.cos(pitch), m.sin(pitch), m.cos(roll), m.sin(roll)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Ry = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
    R = Rz @ Rx @ Ry
    x0, y0, x1, y1 = PORTRAIT
    W, Hh = (x1 - x0) * 2, (y1 - y0) * 2
    # the head point under the crop's centre; the camera looks along the turned head's +y
    qc = np.array([((x0 + x1) / 2 - tu) / s_, 0.0, (tv - (y0 + y1) / 2) / s_])
    pc = R.T @ qc
    fwd = R.T @ np.array([0, 1, 0.0])
    up = R.T @ np.array([0, 0, 1.0])
    world = Vector((pc[0] / 100, pc[1] / 100 + H.Y0, pc[2] / 100 + H.Z0))
    c = sc.camera
    c.data.type = 'ORTHO'
    c.data.ortho_scale = max(W, Hh) / 2 / s_ / 100
    c.location = world - Vector(fwd) * 1.0
    from mathutils import Matrix
    zc = -Vector(fwd); yc = Vector(up); xc = yc.cross(zc)
    c.rotation_euler = Matrix((xc, yc, zc)).transposed().to_euler()
    sc.render.resolution_x, sc.render.resolution_y = W, Hh
    sc.render.filepath = out.replace(".png", "_pfit_head.png")
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(sc.render.filepath)
    head = np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)[::-1]
    im = bpy.data.images.load(SHEET)
    SW, SH = im.size
    a = np.array(im.pixels[:], np.float32).reshape(SH, SW, 4)[::-1]
    crop = a[y0:y1, x0:x1].repeat(2, 0).repeat(2, 1)
    mix = crop * .5 + head * .5
    sheet = np.concatenate([crop, head, mix], axis=1)
    img = bpy.data.images.new("pfit", sheet.shape[1], sheet.shape[0], alpha=True)
    img.pixels = sheet[::-1].ravel()
    img.filepath_raw = out.replace(".png", "_pfit.png"); img.file_format = 'PNG'; img.save()
    c.data.type = 'PERSP'
    log("pfit", img.filepath_raw)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    flags = {a.split("=")[0]: (a.split("=", 1)[1] if "=" in a else True) for a in argv[1:]}
    h = float(flags.get("--h", .0007))
    views = [v for v in str(flags.get("--views", "portrait,front,q,side")).split(",") if v in VIEWS]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    head = H.Head()
    t0 = time.time()
    lo, hi = head.bounds()
    V, Q = sdf.mesh(head, lo, hi, h, log=log)
    log(f"meshed in {time.time() - t0:.1f} s: {len(V)} verts")
    o = to_object("head", V, Q)
    o.data.materials.append(skin_material("--clay" in flags))
    if head.anatomy:                       # the lips' red part, per vertex, from the lips' own volume
        import headbase as HB
        Qh = np.c_[V[:, 0] * 100, (V[:, 1] - H.Y0) * 100, (V[:, 2] - H.Z0) * 100].astype(np.float32)
        lp = HB.lips(Qh, head.stom_z, head.k)[0]
        lw = (np.clip(1 - lp / .12, 0, 1) * (np.abs(Qh[:, 0]) < HB.MOUTH_W + .1)).astype(np.float32)
        a = o.data.color_attributes.new("lip", 'FLOAT_COLOR', 'POINT')
        a.data.foreach_set("color", np.c_[lw, lw, lw, np.ones_like(lw)].ravel())
    if "--groom" in flags:
        import groom as GR
        N = sdf.normals(head, V)
        mask = GR.groom(V, N, head, log=log, beard_on="--beard" in flags).astype(np.float32)   # clean-shaven base
        Qh = GR.to_head(V, head)
        if "--beard" not in flags:          # shaved: the beard's faint shadow under the skin
            mask = (GR.beard_mask(Qh, head, soft=True) * (head.ear(Qh) > .6) * .3).astype(np.float32)
        mask = np.maximum(mask, .8 * GR.scalp_shade(Qh, head))    # the hair's roots shade the scalp (a fade reads)
        a = o.data.color_attributes.new("beard", 'FLOAT_COLOR', 'POINT')
        a.data.foreach_set("color", np.c_[mask, mask, mask, np.ones_like(mask)].ravel())
        sc.cycles_curves.shape = 'THICK'
        log("groomed")
    for name, (EV, EF, col) in head.extras():
        c = EV.mean(0)
        e = to_object(name, EV - c, EF, origin=tuple(c))
        e.data.materials.append(eye_material(name))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_start = .01
    if "--profile" in flags:
        profile_check(sc, out)
        cam.data.type = 'PERSP'
    studio(sc, beauty=flags.get("--light") == "beauty")
    sc.cycles.samples = int(flags.get("--samples", 96))
    res = int(flags.get("--res", 800))
    if "--pfit" in flags:
        pfit(sc, out)
    files = []
    for v in views:
        sc.render.resolution_x = int(res * (.672 if v == "portrait" else 1.0))
        sc.render.resolution_y = res
        camera(sc, v)
        sc.render.filepath = out.replace(".png", f"_{v}.png")
        bpy.ops.render.render(write_still=True)
        files.append(sc.render.filepath)
        log("rendered", v)
    # the sheet: the owner's portrait first when the portrait view was asked for
    imgs = []
    if "portrait" in views:
        im = bpy.data.images.load(SHEET)
        W, Hh = im.size
        a = np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)[::-1]
        x0, y0, x1, y1 = PORTRAIT
        crop = a[y0:y1, x0:x1]
        # nearest-neighbour up to the render's height
        ys = (np.arange(res) * (y1 - y0) / res).astype(int)
        xs = (np.arange(int(res * .672)) * (x1 - x0) / (res * .672)).astype(int)
        imgs.append(crop[ys][:, xs])
    if not views:
        return
    for f in files:
        im = bpy.data.images.load(f)
        W, Hh = im.size
        imgs.append(np.array(im.pixels[:], np.float32).reshape(Hh, W, 4)[::-1])
    Hh = max(i.shape[0] for i in imgs)
    sheet = np.concatenate([np.pad(i, ((0, Hh - i.shape[0]), (0, 0), (0, 0))) for i in imgs], axis=1)
    img = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0], alpha=True)
    img.pixels = sheet[::-1].ravel()
    img.filepath_raw = out; img.file_format = 'PNG'; img.save()
    log("sheet", out)
    if isinstance(flags.get("--save"), str):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(str(flags["--save"])))


if __name__ == "__main__":
    main()
