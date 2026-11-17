"""The portrait's camera and how far the head's landmarks are from the owner's portrait
(art/reference/player/orion_tpose_bodysuit.png, right): the face's landmarks read off the portrait by eye (sheet
pixels), the head's own (head.py's frame, cm), a camera solved between them (weak perspective: a turn, a scale, a
shift), then every landmark's miss in centimetres on the head.

python tools/blender/hero/orion/portrait_fit.py            (system Python: numpy, scipy)
Writes portrait_camera.json beside it (the camera headlab.py renders the portrait view from).
"""
import json, math, os
import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))

# (name, sheet pixel x, y, head frame x, y, z in cm: x to his left, y forward negative, z up from the pupils)
MARKS = [
    ("pupil_R", 1351, 164, -3.2, -9.45, 0.0), ("pupil_L", 1418, 166, 3.2, -9.45, 0.0),
    ("en_R", 1365, 166, -1.66, -9.2, -.06), ("ex_R", 1335, 164, -4.70, -8.2, .14),
    ("en_L", 1404, 166, 1.66, -9.2, -.06), ("ex_L", 1428, 166, 4.70, -8.2, .14),
    ("nasion", 1384, 158, 0.0, -10.4, .55), ("pronasale", 1394, 199, 0.0, -12.95, -3.9),
    ("subnasale", 1398, 209, 0.0, -10.95, -5.0), ("alare_R", 1376, 204, -1.75, -10.9, -4.4),
    ("cheilion_R", 1364, 231, -2.65, -9.6, -7.39), ("cheilion_L", 1411, 228, 2.65, -9.6, -7.39),
    ("stomion", 1390, 231, 0.0, -11.0, -7.25), ("labrale_sup", 1390, 225, 0.0, -11.0, -6.35),
    ("labrale_inf", 1388, 240, 0.0, -11.05, -8.35),
    ("tragion_R", 1295, 184, -7.2, 0.0, -1.0), ("ear_top_R", 1272, 158, -7.4, .8, 1.4),
    ("lobe_R", 1282, 208, -7.3, -.3, -5.1), ("gonion_R", 1306, 228, -6.0, -1.6, -8.7),
    ("brow_in_R", 1378, 150, -1.5, -11.0, 1.4), ("brow_peak_R", 1344, 145, -3.8, -10.8, 1.9),
    ("brow_in_L", 1400, 153, 1.5, -11.0, 1.4),
]


def rot(yaw, pitch, roll):
    cy, sy, cp, sp, cr, sr = (math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll),
                              math.sin(roll))
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Ry = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
    return Rz @ Rx @ Ry


def project(params, P):
    """the head's points to the portrait's pixels: turned (yaw about z, pitch about x, roll), seen from the front
    (-y) with the image's right = +x and down = -z, scaled and shifted"""
    yaw, pitch, roll, s, tu, tv = params
    Q = (rot(yaw, pitch, roll) @ P.T).T
    return np.c_[tu + s * Q[:, 0], tv - s * Q[:, 2]]


def main():
    uv = np.array([[m[1], m[2]] for m in MARKS], float)
    P = np.array([[m[3], m[4], m[5]] for m in MARKS], float)
    res = lambda p: (project(p, P) - uv).ravel()
    p0 = [math.radians(-25), 0.0, 0.0, 10.0, 1390, 170]
    fit = least_squares(res, p0)
    p = fit.x
    err = (project(p, P) - uv)
    print(f"camera: yaw {math.degrees(p[0]):.1f}, pitch {math.degrees(p[1]):.1f}, roll {math.degrees(p[2]):.1f} deg, "
          f"{p[3]:.2f} px/cm")
    print(f"rms miss {np.sqrt((err ** 2).sum(1).mean()) / p[3]:.2f} cm")
    for m, e in zip(MARKS, err):
        print(f"  {m[0]:12s} miss {e[0] / p[3]:+5.2f} cm across, {-e[1] / p[3]:+5.2f} cm up")
    json.dump(dict(yaw=p[0], pitch=p[1], roll=p[2], scale=p[3], tu=p[4], tv=p[5]),
              open(os.path.join(HERE, "portrait_camera.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
