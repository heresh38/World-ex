"""the left arm's sections on a lab build, every 2 cm along the arm from the shoulder joint: the vertical extent
(the arm's outside to its inside in the T-pose), the depth (the biceps' face to the triceps'), where its top and bottom
lie against the arm's axis (cm). Tune body.ARM_VOL and arm_mod against these, not by eye (the anatomy's relief takes
about 1.9 mm off every surface and puts the bellies back): an adult man's mid upper arm is about 11-12 x 12-13, his
forearm's belly 9.5 x 11 a hand below the elbow, his wrist 4.6 x 6.4.
blender -b <lab build>.blend -P tools/blender/hero/orion/armsec.py [-- --right]"""
import bpy, sys, math
import numpy as np
sys.path.insert(0, "C:/Dev/World-ex/tools/blender/hero/orion")
import body as B
sc = bpy.context.scene
body = next((o for o in sc.objects if o.type == 'MESH' and "region" in o.data.attributes and not o.name.startswith(("B_", "C_"))), None)
me = body.data
n = len(me.vertices)
co = np.zeros(n * 3, np.float32); me.vertices.foreach_get("co", co); P = co.reshape(-1, 3).astype(float)
SX = -1 if "--right" in sys.argv else 1                    # --right: the right arm (the mirror)
S, a, up, back = B.arm_axis(SX)
rel = P - S
t = rel @ a; u = rel @ up; b = rel @ back
print(f"verts {n}; the arm from S={S} along {a}")
print(" s(cm)  station        vert(cm)  depth(cm)  u_top  u_bot  b_front  b_back  perim(cm)")
def hull_perim(pts):
    from scipy.spatial import ConvexHull
    try:
        h = ConvexHull(pts); return float(h.area)  # 2D: area is the perimeter
    except Exception:
        return float('nan')
names = {0.0: "shoulder joint", B.UPPER_ARM: "elbow", B.UPPER_ARM + B.FOREARM: "wrist", B.UPPER_ARM + B.FOREARM + .10: "knuckles"}
for s in np.arange(0.02, 0.72, 0.02):
    m = (np.abs(t - s) < .006) & (np.abs(u) < .12) & (np.abs(b) < .12) & (P[:, 0] * SX > 0.12)
    if s < .10:
        m &= (P[:, 0] * SX > B.SHOULDER[0] + .03)
    if m.sum() < 6:
        continue
    uu, bb = u[m], b[m]
    pts = np.stack([bb, uu], 1)
    try:
        per = hull_perim(pts)
    except Exception:
        per = float('nan')
    nm = ""
    for k, v in names.items():
        if abs(k - s) < .011: nm = v
    print(f" {s*100:5.1f}  {nm:14s}  {100*(uu.max()-uu.min()):6.2f}   {100*(bb.max()-bb.min()):6.2f}   {100*uu.max():5.2f} {100*uu.min():6.2f}  {100*bb.min():6.2f}  {100*bb.max():6.2f}   {100*per:6.2f}")
