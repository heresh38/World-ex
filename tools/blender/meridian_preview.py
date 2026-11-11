"""blender -b south.blend -P south_preview.py -- outdir [names...]: quick workbench views along the new route (plan E, N, z)"""
import bpy, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
only = set(argv[1:])
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.name.endswith("_col") or o.name == "MR_blockers":
        o.hide_render = True
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = False
sh.show_cavity = True
sc.render.resolution_x, sc.render.resolution_y = 960, 540
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 18
cam.data.clip_start = .1
cam.data.clip_end = 3000
SHOTS = {
    "01_pad": ((0, -2304, 1.7), (0, -2200, 4)),
    "02_toll": ((4, -2150, 1.7), (0, -2110, 3)),
    "03_gatehouse": ((0, -1978, 1.7), (0, -1940, 4)),
    "04_lobby": ((0, -1957, 1.7), (2, -1925, 1.6)),
    "05_wing": ((-14, -1950, 1.7), (-40, -1936, 1.4)),
    "06_yard": ((0, -1916, 1.7), (0, -1840, 3)),
    "07_arch": ((0, -1836, 1.7), (0, -1790, 2)),
    "08_alley": ((0, -1786, 1.7), (0, -1700, 4)),
    "09_forecourt": ((0, -1636, 1.7), (0, -1598, 4)),
    "10_mall_in": ((0, -1594, 1.7), (0, -1500, 3)),
    "11_mall_gallery": ((-15, -1566, 6.7), (4, -1470, 4)),
    "12_rotunda": ((-13, -1478, 1.7), (2, -1448, 2)),
    "13_foodcourt": ((0, -1360, 1.7), (0, -1300, 2)),
    "14_yard_stair": ((0, -1290, 1.7), (0, -1245, -2)),
    "15_hall": ((0, -1233, -4.3), (0, -1200, -4.6)),
    "16_platform": ((1, -1196, -4.3), (0, -1120, -4.8)),
    "17_tunnel": ((0, -1086, -5.5), (0, -1030, -5.5)),
    "18_fall": ((0, -1028, -5.5), (2, -1010, -5.2)),
    "19_corridor": ((7, -1019, -5.5), (7, -980, -5.6)),
    "20_canal": ((0, -877, -3.3), (0, -800, -2)),
    "21_pump": ((3, -745, -3.3), (0, -700, -1)),
    "22_spillway": ((2, -575, -3.3), (30, -555, -1)),
    "23_causeway": ((45, -552, 1.7), (30, -500, 2)),
    "24_join": ((2, -420, 1.7), (0, -330, 3)),
    "30_top_stacks": ((0, -1890, 150), (0, -1889.9, 0)),
    "31_top_mall": ((0, -1450, 260), (0, -1449.9, 0)),
    "32_top_sluice": ((10, -700, 300), (10, -699.9, 0)),
}


def B(p):
    return Vector((p[1], -p[0], p[2]))


for name, (eye, at) in SHOTS.items():
    if only and name not in only and name.split("_")[0] not in only:
        continue
    cam.location = B(eye)
    d = B(at) - B(eye)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    hide = name.startswith("3")
    for o in bpy.data.objects:                       # from above: take the lid off (roofs, the ground over the station)
        if o.name in ("MR_ground",):
            o.hide_render = hide and name != "32_top_sluice"
    sc.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
print("[preview] done")
