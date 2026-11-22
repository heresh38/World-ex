"""The Sarketh in the game (the owner's own design, art/reference/sarketh/sarketh_design_sheet.png; the owner,
2026-11-21: "work on getting the new sarketh models we made"): one skinned creature from the build (build.py), the way
every creature reaches the game (SourceArt/Characters/<Folder>: export_fbx.py --single, then
Content/Python/import_assets.py `character()`):

    blender -b -P tools/blender/skr/game.py -- male|female <Folder> [--h=.0045] [--budget=40000] [--save=x.blend]
            [--glb=<path>]       (the GLB defaults to SourceArt/Characters/src/skr_<sex>.glb)
    blender -b -P tools/blender/export_fbx.py -- <glb> unreal/ShatteredOrbit/SourceArt/Characters/<Folder> --single
    blender -b -P tools/blender/asset_check.py -- <glb> --class=enemy --flat-ok=skr_glow

What it does, in order:
  build      the sculpted body and every armour slot on one skeleton (build.py), at the game's density (h, the
             surface's cell: the sculpt's own is 3 mm)
  one mesh   the body and its armour joined (the slots stay modular in the build: a set is made slot by slot there)
  budget     the dark body (organic) collapsed to its share (a third: the armour carries the silhouette); the armour's
             flat faces dissolved first, then collapsed evenly to the rest (held at its turning edges the collapse
             stalled at four times the budget: 500 shards are nearly all rim)
  normals    the body smooth; the armour split along its hard edges (a plate's rim crisp, its face smooth)
  clips      the Sarketh's own motion (motion.py: Idle, Walk, Run, Attack, Death, Cast, Blink) with the feet on the
             ground
  export     the armature and the mesh with the clips to a GLB in metres; the maps are the game's own copies of the
             Sarketh's sets (import_assets SKR: skr_skin, skr_armour, skr_dark), so none are embedded
"""
import math
import os
import sys
import time

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import bl            # noqa: E402
import build as B    # noqa: E402
import motion as M   # noqa: E402

T0 = time.time()
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))


def log(*a):
    print('[skr_game %5.1fs]' % (time.time() - T0), *a, flush=True)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def opts():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = {'sex': 'male', 'folder': 'Sarketh', 'h': .0045, 'budget': 40000, 'save': None, 'glb': None, 'look': None,
         'views': ''}
    pos = []
    for x in a:
        if x.startswith('--'):
            k, _, v = x[2:].partition('=')
            o[k] = v if v else True
        else:
            pos.append(x)
    if pos:
        o['sex'] = pos[0]
    if len(pos) > 1:
        o['folder'] = pos[1]
    o['h'], o['budget'] = float(o['h']), int(o['budget'])
    return o


def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def apply_modifier(ob, md):
    select_only([ob])
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_move_to_index(modifier=md.name, index=0)
        bpy.ops.object.modifier_apply(modifier=md.name)


def collapse(ob, ratio, keep_edges=None):
    """collapses ob to ratio of its triangles; keep_edges: a vertex group whose weight makes a vertex dear"""
    md = ob.modifiers.new('budget', 'DECIMATE')
    md.decimate_type = 'COLLAPSE'
    md.ratio = max(0.01, min(1.0, ratio))
    md.use_collapse_triangulate = True
    if keep_edges:
        md.vertex_group = keep_edges
        md.invert_vertex_group = True                 # (the weighted vertices are the ones kept)
        md.vertex_group_factor = 6.0
    apply_modifier(ob, md)


def dissolve_flat(ob, degrees=1.5):
    md = ob.modifiers.new('flat', 'DECIMATE')
    md.decimate_type = 'DISSOLVE'
    md.angle_limit = math.radians(degrees)
    md.delimit = {'MATERIAL', 'SEAM', 'UV'}
    apply_modifier(ob, md)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(ob.data)
    bm.free()


def edge_group(ob, name='edges', degrees=28):
    """a vertex group on every vertex of an edge that turns (a plate's outline and rim): what the collapse keeps"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    keep = set()
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > math.radians(degrees):
            keep.update(v.index for v in e.verts)
    bm.free()
    g = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
    g.add(list(keep), 1.0, 'REPLACE')
    return name


def hard_edges(ob, degrees=34):
    """the faces smooth, split along the edges that turn sharply (the exporter writes them as split normals)"""
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    bm = bmesh.new()
    bm.from_mesh(me)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) != 2 or e.calc_face_angle(0.0) > math.radians(degrees))
    bm.to_mesh(me)
    bm.free()


def main():
    o = opts()
    bl.reset()
    body, parts, arm = B.build(o)
    armour = [p for p in parts.values() if p.type == 'MESH' and len(p.data.polygons)]
    tb, ta = tris(body), sum(tris(p) for p in armour)
    log(f'built: body {tb} triangles, armour {ta} in {len(armour)} parts')

    # the armour into one, its flat faces dissolved, then the budget between the two
    select_only(armour, armour[0])
    bpy.ops.object.join()
    plates = bpy.context.view_layer.objects.active
    plates.name = 'SKR_armour'
    dissolve_flat(plates)
    ta = tris(plates)
    share_body = .35                                       # (the armour carries the silhouette the sheet draws)
    want_body, want_plates = int(o['budget'] * share_body), int(o['budget'] * (1 - share_body))
    if ta < want_plates:
        want_body = o['budget'] - ta
    log(f'flat faces dissolved: armour {ta}; the budget: body {want_body}, armour {min(ta, want_plates)}')
    collapse(body, want_body / max(tb, 1))
    if ta > want_plates:
        # (with every edge that turns held dear the collapse stalled at four times the budget: 500 shards are nearly
        # all rim; collapsed evenly the small rims go first and every shard keeps its outline and its face)
        collapse(plates, want_plates / ta)
    hard_edges(plates)
    for p in body.data.polygons:
        p.use_smooth = True
    log(f'reduced: body {tris(body)}, armour {tris(plates)}')

    # one mesh on the skeleton
    select_only([body, plates], body)
    bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = f'skr_{o["sex"]}'
    for g in [g for g in mesh.vertex_groups if g.name == 'edges']:
        mesh.vertex_groups.remove(g)
    if not any(m.type == 'ARMATURE' for m in mesh.modifiers):
        md = mesh.modifiers.new('Armature', 'ARMATURE')
        md.object = arm
    mesh.parent = arm
    log(f'{mesh.name}: {tris(mesh)} triangles, materials {[s.material.name for s in mesh.material_slots if s.material]}')

    # the clips
    M.bake(arm, log=log)
    arm.name = 'Armature'

    # the export: the armature and the mesh only
    out = o['glb'] or os.path.join(ROOT, 'unreal', 'ShatteredOrbit', 'SourceArt', 'Characters', 'src', f'skr_{o["sex"]}.glb')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    keep = bl.MODELS
    bl.MODELS = os.path.dirname(out)
    try:
        bl.export(os.path.basename(out), animations=True, selected=[arm, mesh], export_image_format='NONE',
                  export_vertex_color='ACTIVE', export_attributes=True)
    finally:
        bl.MODELS = keep
    log(f'glb: {out} ({os.path.getsize(out) / 1e6:.1f} MB)')
    if o['save']:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(o['save']))
        log(f'saved {o["save"]}')


if __name__ == '__main__':
    main()
