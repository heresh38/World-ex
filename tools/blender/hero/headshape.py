"""The head's anatomical target (signed distance, negative inside), mixed into shape.Body.

Built from adult anthropometric norms (head height vertex-menton 23 cm male / 22 cm female, breadth eu-eu, length
g-op from targets.py; face height n-gn, nose height n-sn and protrusion, mouth width ch-ch, eye fissure length,
bizygomatic and bigonial breadth, ear length), all in a head frame:

  x  lateral (the left side; evaluated on |x|)
  y  front-back, 0 = the head frame's centre line (Y0 behind the body's midline origin), front negative
  z  height above the menton (chin bottom)

Lengths are written for the male head (23 cm) and scaled by hs = head_h / .23; the female head differs where the
sexes differ (softer brow, glabella less forward, narrower jaw and chin, smaller nose, fuller lips).

Pieces: cranium (ellipsoid: length, breadth, vertex), the face as a loft of horizontal sections menton -> forehead
(midline profile depth, half width, back limit; superellipse sections), brow ridges, orbits hollowed round the
eyeballs with eyelid shells, cheekbones and the zygomatic arch, the mandible's border and ramus, the chin, the nose
(dorsum, tip, alae, nostrils), the lips and the ears.
"""
import math
import numpy as np
from mathutils import Vector
from sdf import smin, smax, ellipsoid, round_cone, Loft, sphere

F32 = np.float32
ARCH = 13.0         # dental arch: the mouth's surface recedes ARCH * x^2 (male frame) at the corners
Y0 = .006            # the head frame's y origin in body space (the ear canal sits just behind it)


def V(v):
    return np.asarray(tuple(v), F32)


# face sections (male, 23 cm head): z above menton, midline front y, half width, back limit y, section centre y,
# front superellipse exponent
FACE = [
    (-.003, -.066, .020, -.042, -.054, 2.0),
    (.006, -.086, .030, -.032, -.050, 2.2),
    (.016, -.0930, .037, -.022, -.044, 2.4),     # pogonion: the chin's front
    (.030, -.0915, .044, -.010, -.030, 2.4),     # labiomental fold
    (.045, -.0950, .0495, .030, -.016, 2.6),     # lower lip, gonion level (the back reaches into the neck)
    (.058, -.0970, .0545, .036, -.016, 2.6),     # upper lip
    (.072, -.0955, .0595, .045, -.018, 2.7),     # subnasale
    (.090, -.0935, .0650, .045, -.020, 2.7),
    (.104, -.0925, .0680, .060, -.022, 2.4),     # zygion: the cheekbones' breadth
    (.121, -.0905, .0680, .070, -.026, 2.0),     # the eyes (the orbits recede from the nose root)
    (.136, -.0965, .0655, .070, -.028, 2.5),     # glabella
    (.156, -.0950, .0620, .070, -.030, 2.5),
    (.182, -.0880, .0555, .070, -.030, 2.3),     # forehead toward the hairline
]


class HeadShape:
    """mixin for shape.Body: head_geometry(), head_part(P, ear=True), ear()"""

    def head_geometry(self):
        if hasattr(self, "_g"):
            return self._g
        T, m = self.T, self.m
        h = T["head_h"]
        hs = h / .23
        chin = T["chin_z"]
        ez = T["eye_z"]
        X = lambda x, y, z: Vector((x * hs, Y0 + y * hs, chin + z * hs))
        ezr = (ez - chin) / hs                                   # eye height in the male frame
        self._g = g = dict(
            hs=hs, h=h, chin=chin, ez=ez, X=X,
            eye_c=Vector((T["interpupil"] / 2, Y0 + (-.0822 + .0122) * hs, ez)), eye_r=.0122,
            nasion=X(0, -.0905, ezr + .003),
            glabella=X(0, -.0965 if m else -.0935, ezr + .015),
            pronasale=X(0, -.1195 if m else -.1150, .088),
            subnasale=X(0, -.0965, .071),
            stomion=X(0, -.1000 if m else -.0995, .050),
            mouth_w=(.052 if m else .048) * hs,
            pogonion=X(0, -.0935 if m else -.0915, .016),
            menton=X(0, -.070, 0),
            gonion=X(.049 if m else .045, -.004, .040),
            tragion=X(.0715, .004, .100),
            vertex_z=chin + h,
            centre=Vector((0, Y0, ez)),
        )
        return g

    def _head_build(self):
        g = self.head_geometry()
        m, hs, chin = self.m, g["hs"], g["chin"]
        T = self.T
        rows = []
        for z, yf, hw, yb, cw, nf in FACE:
            if not m:
                k = .90 if z < .05 else (.95 if z < .09 else 1.0)    # her jaw and chin narrower
                hw *= k
                if .125 < z < .165:
                    yf += .003                                      # less glabella
            rows.append((z, yf, hw, yb, cw, nf))
        zs = np.array([r[0] for r in rows])
        z0, z1 = zs[0], zs[-1]
        self._face = Loft(V((0, Y0, chin + z0 * hs)), V((0, Y0, chin + z1 * hs)), dict(
            t=(zs - z0) / (z1 - z0),
            rv_pos=[r[2] * hs for r in rows],
            rw_neg=[(r[4] - r[1]) * hs for r in rows],
            rw_pos=[(r[3] - r[4]) * hs for r in rows],
            cw=[r[4] * hs for r in rows],
            nb=[r[5] for r in rows], n=[2.0] * len(rows)), v_axis=(1, 0, 0), cap=.5)
        # nose: a pyramid lofted up the dorsum (sections: z, dorsum front y, half width at the face, front exponent
        # < 2 for the triangular section); the tip's lobule and the alae are added in head_part
        nk = 1.0 if m else .86
        nf = .96 if m else .92                                   # her nose a little less projecting
        NOSE = [(.074, -.1040, .0115, 1.6), (.082, -.1160, .0110, 1.8), (.088, -.1195, .0115, 2.0),
                (.094, -.1135, .0135, 1.6), (.103, -.1060, .0140, 1.35), (.113, -.0990, .0125, 1.3),
                (.124, -.0915, .0105, 1.3)]
        cwn = -.080
        nz = np.array([r[0] for r in NOSE])
        self._nose = Loft(V((0, Y0, chin + nz[0] * hs)), V((0, Y0, chin + nz[-1] * hs)), dict(
            t=(nz - nz[0]) / (nz[-1] - nz[0]), rv_pos=[r[2] * hs * nk for r in NOSE],
            rw_neg=[(cwn - r[1]) * hs * nf for r in NOSE],
            rw_pos=[.010 * hs] * len(NOSE), cw=[cwn * hs] * len(NOSE), nb=[r[3] for r in NOSE], n=[2.0] * len(NOSE)),
            v_axis=(1, 0, 0), cap=.3)
        # lips: an upper and a lower roll across the mouth (fuller on her); the stomion is their front
        st, mw = g["stomion"], g["mouth_w"]
        full = 1.0 if m else 1.2
        tt = [0, .1, .25, .42, .5, .58, .75, .9, 1]
        yo = .0058 * .8
        self._lips = (
            Loft(V(st + Vector((-mw / 2, yo, .0006))), V(st + Vector((mw / 2, yo, .0006))), dict(
                t=tt, rv_pos=[.0008, .0028, .0050, .0058, .0052, .0058, .0050, .0028, .0008],
                rv_neg=[.0006, .0012, .0018, .0020, .0020, .0020, .0018, .0012, .0006],
                rw_pos=[f * full * .8 for f in (.0010, .0026, .0046, .0056, .0058, .0056, .0046, .0026, .0010)],
                rw_neg=[.004] * 9), v_axis=(0, 0, 1), cap=.9),
            Loft(V(st + Vector((-mw * .46, yo + .001, -.0008))), V(st + Vector((mw * .46, yo + .001, -.0008))), dict(
                t=tt, rv_pos=[.0006, .0012, .0016, .0018, .0018, .0018, .0016, .0012, .0006],
                rv_neg=[f * full for f in (.0008, .0030, .0052, .0062, .0064, .0062, .0052, .0030, .0008)],
                rw_pos=[f * full * .8 for f in (.0010, .0028, .0048, .0056, .0058, .0056, .0048, .0028, .0010)],
                rw_neg=[.004] * 9), v_axis=(0, 0, 1), cap=.9))

    def head_part(self, P, ear=True):
        if not hasattr(self, "_face"):
            self._head_build()
        T, m = self.T, self.m
        g = self.head_geometry()
        hs, chin, X = g["hs"], g["chin"], g["X"]
        # cranium: length g-op and breadth eu-eu from the targets, the vertex at the head height
        cz = chin + .142 * hs
        d = ellipsoid(P, V((0, Y0, cz)), (T["head_breadth"] / 2, T["head_length"] / 2, g["vertex_z"] - cz))
        # the occiput's slightly fuller back
        d = smin(d, ellipsoid(P, V(X(0, .050, .140)), (.058 * hs, .045 * hs, .062 * hs)), .02)
        d = smin(d, self._face(P), .018)
        # brow ridges (his stronger) over each orbit, the glabella between them
        k = 1.0 if m else .45
        d = smin(d, round_cone(P, V(X(.003, -.0945, .136)), V(X(.047, -.0795, .1335)), .0058 * hs * (.55 + .45 * k),
                               .0046 * hs * (.6 + .4 * k)), .012)
        # cheekbones (malar eminence) and the zygomatic arch back to the ear
        d = smin(d, ellipsoid(P, V(X(.047, -.0680, .102)), (.018 * hs, .007 * hs, .013 * hs)), .022)
        d = smin(d, round_cone(P, V(X(.050, -.060, .101)), V(X(.063, -.010, .103)), .0050 * hs, .0045 * hs), .020)
        # the cheek's soft fullness over the masseter and buccal pad (keeps the face from looking gaunt)
        d = smin(d, ellipsoid(P, V(X(.043, -.046, .064)), (.015 * hs, .026 * hs, .026 * hs)), .03)
        # mandible: the lower border chin -> angle, the ramus up toward the ear; the chin's mound (squarer on him)
        jw = 1.0 if m else .8
        d = smin(d, round_cone(P, V(X(.004, -.084, .013)), V(g["gonion"]), .0070 * hs * jw, .0090 * hs * jw), .020)
        d = smin(d, round_cone(P, V(g["gonion"]), V(X(.060, .000, .085)), .0100 * hs * jw, .0080 * hs), .018)
        d = smin(d, ellipsoid(P, V(g["pogonion"] + Vector((0, .009, -.002))),
                              ((.019 if m else .015) * hs, .0065 * hs, (.010 if m else .009) * hs)), .014)
        # lips
        Q = P.copy()
        Q[:, 1] -= ARCH / hs * Q[:, 0] ** 2                         # the lips follow the dental arch
        d = smin(d, self._lips[0](Q), .004)
        d = smin(d, self._lips[1](Q), .004)
        # orbits hollowed round the eyeball, the lids a thin shell over it
        ec, er = g["eye_c"], g["eye_r"]
        d = smax(d, -ellipsoid(P, V(ec + Vector((.0005, -.0105, .0012))), (.0150 * hs, .0058 * hs, .0100 * hs)), .006)
        d = smin(d, sphere(P, V(ec), er + .0014), .006)
        # nose: dorsum from the root to the tip, the tip's lobule, the alae; nostrils hollowed
        tip, sub = g["pronasale"], g["subnasale"]
        nk = 1.0 if m else .86
        d = smin(d, self._nose(P), .008)
        d = smin(d, ellipsoid(P, V(tip + Vector((0, .0066, -.0015))), (.0062 * nk, .0055, .0062)), .006)
        d = smin(d, ellipsoid(P, V(sub + Vector((.0122 * nk, .0062, .0066))), (.0062 * nk, .0070, .0058)), .006)
        d = smax(d, -ellipsoid(P, V(sub + Vector((.0060 * nk, .0068, .0008))), (.0034 * nk, .0048, .0020)), .0018)
        if ear:
            d = smin(d, self.ear(P, g), .006)
        return d

    def ear(self, P, g=None):
        g = g or self.head_geometry()
        hs = g["hs"]
        c = g["tragion"] + Vector((.006 * hs, .012 * hs, .005 * hs))
        tilt = math.radians(14)
        R = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]], F32)
        outer = ellipsoid(P, V(c), (.0085 * hs, .0170 * hs, .0305 * hs), R)
        bowl = ellipsoid(P, V(c + Vector((.008 * hs, -.002 * hs, -.004 * hs))), (.006 * hs, .010 * hs, .013 * hs), R)
        return smax(outer, -bowl, .003)
