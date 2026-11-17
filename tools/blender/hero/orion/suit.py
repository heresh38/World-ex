"""The undersuit (Project Orion male): its own layer made ON the body's skin, as the owner asked (2026-11-16: "The
undersuit should follow the body rather than determine its shape"), patterned after the T-pose sheet
(art/reference/player/orion_tpose_bodysuit.png): a charcoal base, lighter grey panels (the chest's wings across the
collarbones, the shoulders' caps, the upper arms' outsides, the flanks, the thighs' outer fronts, the knees, the
shins, the back's broad centre narrowing to the waist, the hips' sides), seams round every panel and down the abdomen's
lines, a high collar.

Made in Blender from the finished body: its skin offset 2.5 mm, cut at the collar, the wrists and the ankles, given
a thickness; each vertex carries its panel (the `suit` colour attribute: red = panel, green = seam) for the
material. A first pass: the panels are drawn from the body's positions and normals; a proper cut pattern with UVs
comes with the game mesh.
"""
import math
import numpy as np

OFFSET = .0025
THICK = .0015


def panel_masks(P, N):
    """per vertex: (panel 0..1, seam 0..1) from its place on the body (world metres, the sheet's posture)"""
    x, y, z = np.abs(P[:, 0]), P[:, 1], P[:, 2]
    sx = np.sign(P[:, 0])
    nx, ny, nz = N[:, 0] * sx, N[:, 1], N[:, 2]
    arm = x > .23
    torso = (~arm) & (z > .93)
    leg = (~arm) & (z <= .93)
    pan = np.zeros(len(P), bool)
    # the chest's wings across the collarbones, open at the zip down the middle
    wing_low = 1.425 + .32 * np.maximum(.10 - x, 0) - .55 * np.maximum(x - .13, 0) ** 1.3
    pan |= torso & (ny < -.25) & (x > .028) & (z > wing_low) & (z < 1.545)
    # the shoulders' caps and the upper arms' outsides
    sh = np.sqrt((x - .232) ** 2 + (y + .022) ** 2 + ((z - 1.53) * 1.2) ** 2) < .075
    pan |= sh & (nz > .05)
    pan |= arm & (x < .44) & (nz > .55)
    # the flanks: a stripe from under the arm down to the hip, leaning forward as it falls
    yc = -.025 - .10 * (1.36 - z)
    pan |= torso & (z > 1.0) & (z < 1.37) & (nx > .45) & (np.abs(y - yc) < .045)
    # the hips' sides and the thighs' outer fronts
    pan |= (z > .86) & (z < 1.02) & (nx > .55) & (y > -.06)
    pan |= leg & (z > .56) & (z < .90) & (nx > .25) & (ny < .30)
    # the knees and the shins' outsides
    pan |= leg & (z > .455) & (z < .575) & (ny < -.55)
    pan |= leg & (z > .14) & (z < .43) & (ny < -.15) & (nx > .05)
    # the back: a broad centre narrowing to the waist
    half = .045 + .13 * np.clip((z - 1.22) / .30, 0, 1)
    pan |= torso & (ny > .45) & (x < half) & (z > 1.05) & (z < 1.56)
    # the collar stays dark
    pan &= ~((z > 1.545) & (x < .10))
    seam = np.zeros(len(P), np.float32)
    # the abdomen's lines (seams on the dark base), the spine's seam, the zip
    front = (ny < -.5) & torso
    seam += front * (np.exp(-((x - .078) / .0035) ** 2) * (z > 1.0) * (z < 1.33))
    for zz in (1.17, 1.228, 1.284):
        seam += front * np.exp(-((z - zz) / .0035) ** 2) * (x < .08)
    seam += front * np.exp(-(x / .003) ** 2) * (z > 1.0)
    seam += (ny > .5) * torso * np.exp(-(x / .003) ** 2)
    return pan.astype(np.float32), np.clip(seam, 0, 1)


def build_suit(body, log=print):
    """the suit as its own object over `body` (its finished, subdivided mesh)"""
    import bpy, bmesh
    me = body.data.copy()
    o = bpy.data.objects.new("suit", me)
    bpy.context.scene.collection.objects.link(o)
    n = len(me.vertices)
    co = np.zeros(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
    nr = np.zeros(n * 3, np.float32); me.vertices.foreach_get("normal", nr); nr = nr.reshape(n, 3)
    pan, seam = panel_masks(co, nr)
    co = co + nr * OFFSET
    me.vertices.foreach_set("co", co.ravel())
    # what it covers: below the collar, short of the wrists and the ankles
    x, y, z = np.abs(co[:, 0]), co[:, 1], co[:, 2]
    collar = 1.585 + .06 * np.clip((y - .0) / .07, 0, 1)
    covered = (z < collar) & (z > .118) & ~((x > .70))
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    drop = [f for f in bm.faces if not all(covered[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.to_mesh(me); bm.free()
    # carry the panels: a colour attribute per vertex, after the cut (vertex indices kept by the order)
    keep = np.array([True] * len(me.vertices))
    m = me.color_attributes.new("suit", 'FLOAT_COLOR', 'POINT')
    # the vertices surviving the cut keep their original order: map by position
    from mathutils import kdtree
    kd = kdtree.KDTree(len(co))
    for i, p in enumerate(co):
        kd.insert(p, i)
    kd.balance()
    cols = np.zeros((len(me.vertices), 4), np.float32)
    for v in me.vertices:
        _, i, _ = kd.find(v.co)
        cols[v.index] = (pan[i], seam[i], 0, 1)
    # the panels' borders are seams too
    nb = [[] for _ in range(len(me.vertices))]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b); nb[b].append(a)
    border = np.array([any(abs(cols[j, 0] - cols[i, 0]) > .5 for j in nb[i]) for i in range(len(me.vertices))])
    cols[:, 1] = np.maximum(cols[:, 1], border * .85)
    m.data.foreach_set("color", cols.ravel())
    mod = o.modifiers.new("thick", 'SOLIDIFY'); mod.thickness = THICK; mod.offset = 1.0
    o.data.materials.clear()
    o.data.materials.append(suit_material())
    for p in me.polygons:
        p.use_smooth = True
    log(f"suit: {len(me.vertices)} vertices, panels {cols[:, 0].mean() * 100:.0f} % of it")
    return o


def suit_material():
    import bpy
    m = bpy.data.materials.new("suit")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "suit"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attr.outputs["Color"], sep.inputs[0])
    base = nt.nodes.new("ShaderNodeMix"); base.data_type = 'RGBA'
    base.inputs[6].default_value = (.028, .028, .032, 1)                # charcoal
    base.inputs[7].default_value = (.105, .102, .112, 1)                # the grey panels
    nt.links.new(sep.outputs[0], base.inputs[0])
    seamc = nt.nodes.new("ShaderNodeMix"); seamc.data_type = 'RGBA'
    nt.links.new(base.outputs[2], seamc.inputs[6])
    seamc.inputs[7].default_value = (.012, .012, .014, 1)
    nt.links.new(sep.outputs[1], seamc.inputs[0])
    nt.links.new(seamc.outputs[2], b.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(sep.outputs[0], rough.inputs["Value"])
    rough.inputs["To Min"].default_value = .62; rough.inputs["To Max"].default_value = .46
    nt.links.new(rough.outputs[0], b.inputs["Roughness"])
    b.inputs["Sheen Weight"].default_value = .08
    # the weave: a fine bump, and the seams pressed in
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexNoise"); wave.inputs["Scale"].default_value = 1400.0
    wave.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = 'MULTIPLY_ADD'
    nt.links.new(sep.outputs[1], add.inputs[0]); add.inputs[1].default_value = -1.0
    nt.links.new(wave.outputs["Fac"], add.inputs[2])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = .35
    bump.inputs["Distance"].default_value = .0012
    nt.links.new(add.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m
