"""The head's layout beside Epic's template head (look / measure only; their file stays in a scratch folder): both
heads' silhouettes from the front and the side at true scale, set on the same chin and midline (the side view
on the same ear canal), written as masks for head_layout_sheet.py to draw over each other with the proportion
lines, and their measures printed.

blender -b <headlab save.blend> -P tools/reference/head_layout.py -- <ref_dir> <out_dir>
"""
import bpy, math, os, sys, json
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
REF, OUT = argv[0], os.path.abspath(argv[1])
os.makedirs(OUT, exist_ok=True)
MPP = .0005                       # metres per pixel
W, H = 700, 700                   # 35 x 35 cm


def flat(o):
    for md in list(o.modifiers):
        o.modifiers.remove(md)
    mw = o.matrix_world.copy(); o.parent = None; o.data.transform(mw); o.matrix_world = Matrix.Identity(4)


def pts(objs):
    P = []
    for o in objs:
        n = len(o.data.vertices); co = np.zeros(n * 3); o.data.vertices.foreach_get("co", co)
        P.append(co.reshape(n, 3))
    return np.concatenate(P)


ours = [o for o in bpy.data.objects if o.type == 'MESH' and (o.name == "head" or o.name.startswith("eye"))]
for o in list(bpy.data.objects):
    if o not in ours:
        bpy.data.objects.remove(o, do_unlink=True)
for o in ours:
    flat(o)
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=os.path.join(REF, "MH_SM_MH_Head.fbx"))
new = [o for o in bpy.data.objects if o not in before]
mh = [o for o in new if o.type == 'MESH' and ('LOD' not in o.name or 'LOD0' in o.name)]
for o in new:
    if o not in mh:
        bpy.data.objects.remove(o, do_unlink=True)
for o in mh:
    flat(o)


def landmarks(P):
    """crown, chin (menton), nose tip, the ear canal's rough place (the ears' middle), from the mesh"""
    top = P[np.argmax(P[:, 2])]
    mid = P[np.abs(P[:, 0]) < .004]
    tip = mid[np.argmin(mid[:, 1])]
    lower = mid[(mid[:, 2] < tip[2] - .05) & (mid[:, 2] > tip[2] - .17)]
    pog = lower[np.argmin(lower[:, 1])]
    under = mid[(mid[:, 2] < pog[2]) & (mid[:, 2] > pog[2] - .04) & (mid[:, 1] < pog[1] + .02)]
    men = under[np.argmin(under[:, 2])]
    # the ears: the widest points between the nose tip's height and 6 cm above it
    band = P[(P[:, 2] > tip[2] - .02) & (P[:, 2] < tip[2] + .07)]
    ear = band[np.argmax(np.abs(band[:, 0]))]
    return dict(top=top, men=men, tip=tip, pog=pog, ear=ear)


Lo, Lm = landmarks(pts([o for o in ours if o.name == "head"])), landmarks(pts(mh))
# move Epic's head onto ours: the same chin height, the same midline, and front to back the same middle of the
# head's length half way up it (the ears differ: aligning on them shifted one face 2 cm before the other)
def mid_length(P, L):
    z = L["men"][2] + .5 * (L["top"][2] - L["men"][2])
    s = P[(np.abs(P[:, 2] - z) < .004) & (np.abs(P[:, 0]) < .01)]
    return .5 * (s[:, 1].min() + s[:, 1].max())
dz = Lo["men"][2] - Lm["men"][2]
dy = mid_length(pts([o for o in ours if o.name == "head"]), Lo) - mid_length(pts(mh), Lm)
for o in mh:
    o.data.transform(Matrix.Translation(Vector((0, dy, dz))))
Lm = landmarks(pts(mh))
z0 = Lo["men"][2] - .04                                  # the frame's bottom: 4 cm under the chin
yc = Lo["ear"][1]

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'
sc.display.shading.color_type = 'SINGLE'
sc.display.shading.single_color = (1, 1, 1)
sc.render.film_transparent = False
w = bpy.data.worlds.new("w"); sc.world = w; w.color = (0, 0, 0)
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x, sc.render.resolution_y = W, H
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = W * MPP
info = {}
for name, objs in (("ours", ours), ("mh", mh)):
    for o in ours + mh:
        o.hide_render = o not in objs
    for view, d in (("front", Vector((0, -1, 0))), ("side", Vector((1, 0, 0)))):
        centre = Vector((0, yc, z0 + H * MPP / 2))
        cam.location = centre + d * 2.0
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, f"{name}_{view}.png")
        bpy.ops.render.render(write_still=True)
L = {"ours": Lo, "mh": Lm}
meta = {k: {n: [float(v) for v in p] for n, p in L[k].items()} for k in L}
meta["frame"] = dict(mpp=MPP, w=W, h=H, z0=z0, yc=yc)
json.dump(meta, open(os.path.join(OUT, "layout.json"), "w"), indent=1)
print("[layout] written", OUT)
