"""The foot's anatomy (footshape.py) meshed on its own, to tune it against the references before the cage is laid on
it: blender -b -P tools/blender/hero/orion/footlab.py -- <out.blend> [--h=0.0012]
then tools/reference/orion_compare.py on that file (--part=foot)."""
import bpy, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import sdf  # noqa: E402
import foot as FT  # noqa: E402
import footshape as FS  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(argv[0])
fl = {a.split("=")[0]: a.split("=", 1)[1] for a in argv[1:] if "=" in a}
h = float(fl.get("--h", .0012))
bpy.ops.wm.read_factory_settings(use_empty=True)
F = FT.Frame((0.207, 0.034, 0.095), 1)
fs = FS.FootShape(F)
lo, hi = fs.bounds()
hi[2] = .26
t0 = time.time()
V, Q = sdf.mesh(fs, lo, hi, h)
print(f"[footlab] {len(V)} verts in {time.time() - t0:.1f} s", flush=True)
me = bpy.data.meshes.new("orion_male")
me.from_pydata(V.tolist(), [], Q.tolist())
me.update()
o = bpy.data.objects.new("orion_male", me)
bpy.context.scene.collection.objects.link(o)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("[footlab] saved", out, flush=True)
