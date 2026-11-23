"""The Orion outfit's materials, in the owner's sheet's own colours (sampled from the lit parts of each in
orion_tpose_outfit.png and image-1794017268247.png), and the small mesh helpers every piece uses. Material names are an
API (the game's import keys its instances, wear and grime by them): the outfit keeps the `orion_*` names the importer
already knows where one fits.
"""
import bmesh
import bpy

# name: (linear base colour, roughness, metallic, emission strength)
PALETTE = {
    # (the sheet sampled part by part on its LIT side: it is lit by a strong key light in a dark studio, and its medians
    # taken for albedos read black in the game's daylight)
    "orion_coat": ((.050, .050, .058), .80, 0.0, 0.0),        # the coat's black twill (painted: outfit.PAINT_BASE)
    "orion_coat_light": ((.260, .240, .255), .76, 0.0, 0.0),  # its light grey: the lapels, the front facings, the hood
    "orion_coat_patch": ((.200, .198, .210), .78, 0.0, 0.0),  # the worn grey patches on its sleeves and body
    "orion_lining": ((.030, .100, .300), .62, 0.0, 0.0),      # the blue lining
    "orion_black": ((.020, .020, .023), .72, 0.0, 0.0),       # the gaiter's knit
    "orion_cloth": ((.025, .025, .029), .82, 0.0, 0.0),       # the trousers' ripstop (painted)
    "orion_vest": ((.060, .058, .066), .45, .15, 0.0),        # the vest's armoured cells, the knees' chevrons
    "orion_plate": ((.300, .292, .310), .40, .25, 0.0),       # the knee plates' satin grey metal
    "orion_strap": ((.025, .026, .030), .62, 0.0, 0.0),       # webbing: straps, the belt, the harness
    "orion_steel": ((.350, .350, .370), .32, .9, 0.0),        # buckles, eyelets, the buckle's frame
    "orion_leather": ((.045, .043, .048), .36, 0.0, 0.0),     # the boots' leather (glossy)
    "orion_boot_panel": ((.200, .210, .240), .45, .30, 0.0),  # the boots' grey plates and straps, the calf's straps
    "orion_sole": ((.040, .040, .044), .86, 0.0, 0.0),        # rubber (the sheet's: a grey-black)
    "orion_glove": ((.030, .029, .033), .52, 0.0, 0.0),       # the gloves' leather
    "orion_glow": ((.10, .55, 1.0), .30, 0.0, 6.0),          # the cyan-blue lights
}


def material(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    col, rough, metal, emit = PALETTE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*col, 1)
        b.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = (*[min(1.0, c * 1.6) for c in col], 1)   # (the workbench views show it a little lighter)
    return m


def to_object(bm, name, mat):
    """a bmesh (world space) as an object with one material, smooth shaded (a face grown from the suited body still
    carries its body region as its material index: every face starts on the piece's own material)"""
    for f in bm.faces:
        f.material_index = 0
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(material(mat))
    for p in me.polygons:
        p.use_smooth = True
    return o


def face_out(bm, base):
    """every face of a worn piece turned to face away from the body it is worn on (recalc_face_normals guesses on an
    open mesh, and turning the whole mesh by one vote cannot right a sleeve and a skirt at once: the coat's bodice
    and sleeves showed their blue lining outside)"""
    from mathutils.bvhtree import BVHTree
    b = bmesh.new()
    b.from_mesh(base.data)
    b.transform(base.matrix_world)
    bvh = BVHTree.FromBMesh(b)
    b.free()
    bm.normal_update()
    flip = []
    for f in bm.faces:
        c = f.calc_center_median()
        loc, nrm, _, _ = bvh.find_nearest(c)
        if loc is None:
            continue
        out = c - loc
        if out.length < 1e-6:
            out = nrm
        if f.normal.dot(out) < 0:
            flip.append(f)
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    bm.normal_update()
    return len(flip)


def taubin(bm, iters=30, lam=.5, mu=-.53):
    """volume-keeping smoothing (Taubin's lambda / mu): what is smaller than about ten edges goes (the anatomy under a
    cloth: the abs, the pectorals' edges, the arm's muscles), the garment's own form stays; open edges are held"""
    import numpy as np
    bm.verts.ensure_lookup_table()
    n = len(bm.verts)
    P = np.array([v.co[:] for v in bm.verts], np.float64)
    nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    deg = np.array([max(1, len(x)) for x in nbr], np.float64)
    rows = np.repeat(np.arange(n), [len(x) for x in nbr])
    cols = np.array([i for x in nbr for i in x], np.int64)
    fixed = np.array([v.is_boundary or not v.link_edges for v in bm.verts])
    for _ in range(iters):
        for f in (lam, mu):
            S = np.zeros_like(P)
            np.add.at(S, rows, P[cols])
            d = S / deg[:, None] - P
            d[fixed] = 0.0
            P += f * d
    for v, p in zip(bm.verts, P):
        v.co = p
    bm.normal_update()


def hold_out(bm, base, ease):
    """every point of a garment at least `ease` outside the body it is worn on (along the body's normal there)"""
    from mathutils.bvhtree import BVHTree
    b = bmesh.new()
    b.from_mesh(base.data)
    b.transform(base.matrix_world)
    bvh = BVHTree.FromBMesh(b)
    b.free()
    moved = 0
    for v in bm.verts:
        loc, nrm, _, _ = bvh.find_nearest(v.co)
        if loc is None:
            continue
        side = (v.co - loc).dot(nrm)
        if side < ease:
            v.co = v.co + nrm * (ease - side)
            moved += 1
    bm.normal_update()
    return moved
