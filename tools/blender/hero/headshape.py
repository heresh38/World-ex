"""The head's anatomical target (signed distance, negative inside), mixed into shape.Body.

Built from adult anthropometric norms (head height vertex-menton 23 cm male / 22 cm female, breadth eu-eu, length
g-op from targets.py; face height n-gn, nose height n-sn and protrusion, mouth width ch-ch, eye fissure length,
bizygomatic and bigonial breadth, ear length), all in a head frame:

  x  lateral (the left side; evaluated on |x|)
  y  front-back, 0 = the head frame's centre line (Y0 behind the body's midline origin), front negative
  z  height above the menton (chin bottom)

Lengths are written for the male head (23 cm) and scaled by hs = head_h / .23; the female head differs where the
sexes differ (softer brow, glabella less forward, a narrow jaw with a high soft angle, a small round chin, rounder cheeks,
a smaller nose, fuller lips).

Pieces: cranium (ellipsoid: length, breadth, vertex), the face as a loft of horizontal sections menton -> forehead
(midline profile depth, half width, back limit; superellipse sections), brow ridges, orbits hollowed round the
eyeballs with eyelid shells, cheekbones and the zygomatic arch, the mandible's border and ramus, the chin, the nose
(dorsum, tip, alae, nostrils), the lips and the ears.
"""
import math
import numpy as np
from mathutils import Vector
from sdf import smin, smax, ellipsoid, round_cone, Loft

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
    (.045, -.0950, .0500, .030, -.016, 2.6),     # the face's sides taper straight from the cheekbones to the jaw angles     # lower lip, gonion level (the back reaches into the neck)
    (.058, -.0970, .0540, .036, -.016, 2.6),     # upper lip
    (.072, -.0955, .0582, .045, -.018, 2.7),     # subnasale
    (.090, -.0935, .0635, .045, -.020, 2.7),
    (.104, -.0925, .0680, .060, -.022, 2.4),     # zygion: the cheekbones' breadth
    (.121, -.0905, .0680, .070, -.026, 2.0),     # the eyes (the orbits recede from the nose root)
    (.136, -.0965, .0655, .070, -.028, 2.5),     # glabella
    (.156, -.0950, .0620, .070, -.030, 2.5),
    (.182, -.0880, .0555, .070, -.030, 2.3),     # forehead toward the hairline
]


# face customisation shape keys: name -> the factor set that defines the key's full (weight 1) shape
FACE_KEYS = {
    "nose_width": dict(nose_width=1.25), "nose_length": dict(nose_length=1.15), "lips_full": dict(lips_full=1.4),
    "mouth_width": dict(mouth_width=1.12), "eye_size": dict(eye_size=1.15), "eye_tilt": dict(eye_tilt=2.5),
    "jaw_width": dict(jaw_width=1.12), "chin": dict(chin=1.35), "cheekbones": dict(cheekbones=1.35),
    "brow": dict(brow=1.7), "ear_size": dict(ear_size=1.15), "ear_out": dict(ear_out=1.5),
}

import anatomy
import os
OFF = set(os.environ.get("HERO_OFF", "").split(","))      # (debug: pieces left out, to see what each one does)

# his lower jaw with the surface anatomy (FACE rows by height): half width, section centre y, front exponent
# the face with the surface anatomy (same heights as FACE): midline front y, half width, back limit, section centre y,
# front exponent. The midline follows soft-tissue norms about a vertical through the subnasale (glabella 8 mm behind
# it, the nose's tip 17 ahead, the upper lip 3, the lower lip 1, the fold under it 7 behind, the chin 3.5 behind: the
# forehead does not overhang the mouth); the sections are rounder (the muzzle leads, the cheeks sweep back); below the
# mouth the jaw is an arch whose widest point moves back toward the angle, and it carries the chin itself (a chin
# blended on as a ball stands off the jaw). Every column runs smooth: a zigzag between rows shows as a band.
AFACE = [
    (-.003, -.0740, .0260, -.042, -.052, 2.3),
    (.006, -.0945, .0390, -.032, -.045, 2.45),
    (.016, -.1000, .0490, -.022, -.036, 2.5),      # pogonion (a broad, square chin)
    (.030, -.0962, .0530, -.010, -.026, 2.4),      # the fold under the lower lip
    (.045, -.0985, .0562, .030, -.020, 2.3),
    (.058, -.1035, .0588, .036, -.018, 2.2),
    (.072, -.1030, .0615, .045, -.018, 2.15),      # subnasale
    (.090, -.0985, .0655, .045, -.020, 2.2),
    (.104, -.0940, .0680, .060, -.022, 2.2),
    (.121, -.0825, .0680, .070, -.026, 2.2),
    (.136, -.0900, .0655, .070, -.028, 2.3),
    (.156, -.0915, .0620, .070, -.030, 2.4),
    (.182, -.0850, .0555, .070, -.030, 2.3),
]


# her face with the surface anatomy: very round (FACE's heights): the half widths stay full from the cheekbones down
# to the mouth and come round to a small chin in one curve; every section an ellipse (no planes, no corners)
ROUND_HW = [.0165, .0280, .0395, .0505, .0592, .0645, .0668, .0680, .0680, .0668, .0645, .0605, .0540]


class HeadShape:
    """mixin for shape.Body: head_geometry(), head_part(P, ear=True), ear()"""

    def head_geometry(self):
        if hasattr(self, "_g"):
            return self._g
        T, m = self.T, self.m
        F = self.face
        h = T["head_h"]
        hs = h / .23
        chin = T["chin_z"]
        ez = T["eye_z"]
        # her lower face is shorter: below the mouth (z .05) the heights are drawn up by a quarter, the chin ~13 mm higher
        # (his lower third a tenth shorter: the mouth-to-chin height of the adult norm)
        zf = (lambda z: z if z >= .05 else .05 - (.05 - z) * (.90 if m else .74))
        X = lambda x, y, z: Vector((x * hs, Y0 + y * hs, chin + zf(z) * hs))
        ezr = (ez - chin) / hs                                   # eye height in the male frame
        self._g = g = dict(
            hs=hs, h=h, chin=chin, ez=ez, X=X, zf=zf,
            eye_c=Vector((T["interpupil"] / 2, Y0 + ((-.0865 if m else -.0885) + .0122) * hs, ez)), eye_r=.0122,
            # the lid opening above / below the eye centre: big, open, rounded eyes (hers a little bigger)
            eye_hu=(.0047 if m else .0063) * hs,
            eye_hl=(.0055 if m else .0062) * hs,
            nasion=X(0, -.0905, ezr + .003),
            glabella=X(0, -.0965 if m else -.0925, ezr + .015),
            pronasale=X(0, -.080 + ((-.1225 if m else -.1190) + .080) * F("nose_length"), .088),
            subnasale=X(0, -.1045, .071),
            stomion=X(0, -.1035 if m else -.1005, .050),
            mouth_w=(.052 if m else .049) * hs * F("mouth_width"),
            pogonion=X(0, -.1000 - .006 * (F("chin") - 1), .016),
            menton=X(0, -.070, 0),
            # (the jaw's back edge runs in from the ear lobe to the angle: no flap beside the mouth)
            gonion=X((.051 if m else .045) * F("jaw_width"), .004 if m else .002,
                     .033 if m else .041),   # hers higher, softer
            tragion=X(.0715, .004, .100),
            vertex_z=chin + h,
            centre=Vector((0, Y0, ez)),
        )
        # the lids: a shell round the eyeball, wider than it (the fissure runs past the globe: the inner corner sits
        # well in front of it with the tear duct, the outer corner wraps back onto it); the lid margins are pinned
        # on this same shell (fit.place_features), so the opening lies in the surface with the lid's own thickness
        w = T["eye_w"] / 2 * F("eye_size") * (1.0 if m else 1.07)        # (her eyes larger)
        wm, wl = w * .975, w * .96
        g["lid"] = dict(R=g["eye_r"] + .0018, wm=wm, wl=wl, rxm=wm / .80, rxl=wl / .96)
        return g

    @property
    def face(self):
        """face customisation factors (1 = the base face): T["face"] overrides; see FACE_KEYS"""
        f = self.T.get("face", {})
        return lambda k: f.get(k, 1.0)

    def _head_build(self):
        g = self.head_geometry()
        m, hs, chin = self.m, g["hs"], g["chin"]
        T, F = self.T, self.face
        rows = []
        for i, (z, yf, hw, yb, cw, nf) in enumerate(FACE):
            yf, nf = AFACE[i][1], AFACE[i][5]
            if m:
                hw, yb, cw = AFACE[i][2:5]
            else:
                hw, nf = ROUND_HW[i], (2.0 if z < .10 else nf)
                if .125 < z < .165:
                    yf += .003                                      # less glabella
            if z < .06:
                hw *= 1 + (F("jaw_width") - 1) * min(1.0, (.06 - z) / .03)
            rows.append((g["zf"](z), yf, hw, yb, cw, nf))
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
        nk = (1.08 if m else .74) * F("nose_width")
        nf = (.98 if m else .84) * F("nose_length")              # her nose a little less projecting
        # a straight bridge, a tip that leads, a level underside
        NOSE = [(.0725, -.1100, .0120, 2.0), (.0775, -.1195, .0135, 2.2), (.0850, -.1232, .0130, 2.3),
                (.0930, -.1165, .0120, 1.8), (.1030, -.1070, .0112, 1.5), (.1130, -.0985, .0102, 1.4),
                (.1240, -.0872, .0092, 1.4)]
        cwn = -.080
        nz = np.array([r[0] for r in NOSE])
        self._nose = Loft(V((0, Y0, chin + nz[0] * hs)), V((0, Y0, chin + nz[-1] * hs)), dict(
            t=(nz - nz[0]) / (nz[-1] - nz[0]), rv_pos=[r[2] * hs * nk for r in NOSE],
            rw_neg=[(cwn - r[1]) * hs * nf for r in NOSE],
            rw_pos=[.010 * hs] * len(NOSE), cw=[cwn * hs] * len(NOSE), nb=[r[3] for r in NOSE], n=[2.0] * len(NOSE)),
            v_axis=(1, 0, 0), cap=.3)
        # lips: an upper and a lower roll across the mouth (fuller on her); the stomion is their front
        st, mw = g["stomion"], g["mouth_w"]
        full = (1.25 if m else 1.85) * F("lips_full")
        up = 1.3 if m else 1.25                                    # the upper lip's height
        tt = [0, .1, .25, .42, .5, .58, .75, .9, 1]
        yo = .0042
        self._lips = (
            Loft(V(st + Vector((-mw / 2, yo, .0006))), V(st + Vector((mw / 2, yo, .0006))), dict(
                t=tt, rv_pos=[f * up for f in (.0008, .0028, .0050, .0058, .0052, .0058, .0050, .0028, .0008)],
                rv_neg=[.0006, .0012, .0018, .0020, .0020, .0020, .0018, .0012, .0006],
                rw_pos=[f * full * 1.2 for f in (.0010, .0026, .0046, .0056, .0058, .0056, .0046, .0026, .0010)],
                rw_neg=[.004] * 9), v_axis=(0, 0, 1), cap=.9),
            Loft(V(st + Vector((-mw * .46, yo + .001, -.0008))), V(st + Vector((mw * .46, yo + .001, -.0008))), dict(
                t=tt, rv_pos=[.0006, .0012, .0016, .0018, .0018, .0018, .0016, .0012, .0006],
                rv_neg=[f * full for f in (.0008, .0030, .0052, .0062, .0064, .0062, .0052, .0030, .0008)],
                rw_pos=[f * full * 1.2 for f in (.0010, .0028, .0048, .0056, .0058, .0056, .0048, .0028, .0010)],
                rw_neg=[.004] * 9), v_axis=(0, 0, 1), cap=.9))

    def head_part(self, P, ear=True):
        if not hasattr(self, "_face"):
            self._head_build()
        T, m, F = self.T, self.m, self.face
        g = self.head_geometry()
        hs, chin, X = g["hs"], g["chin"], g["X"]
        # cranium: length g-op and breadth eu-eu from the targets, the vertex at the head height
        cz = chin + .142 * hs
        d = ellipsoid(P, V((0, Y0, cz)), (T["head_breadth"] / 2, T["head_length"] / 2, g["vertex_z"] - cz))
        # the occiput's slightly fuller back
        d = smin(d, ellipsoid(P, V(X(0, .050, .140)), (.058 * hs, .045 * hs, .062 * hs)), .02)
        d = smin(d, self._face(P), .018)
        # brow ridges (his stronger) over each orbit, the glabella between them
        k = (1.3 if m else .15) * F("brow")
        d = smin(d, round_cone(P, V(X(.003, -.0870, .139)), V(X(.047, -.0740, .1385)), .0054 * hs * (.55 + .45 * k),
                               .0036 * hs * (.6 + .4 * k)), .012)
        # cheekbones (malar eminence) and the zygomatic arch back to the ear
        cb = F("cheekbones")
        cz_ = .102 if m else .107                                    # hers higher and rounder
        d = smin(d, ellipsoid(P, V(X(.047, -.0680 - .004 * (cb - 1) - (0 if m else .002), cz_)),
                              (.018 * hs * cb, (.007 if m else .008) * hs * cb, (.013 if m else .015) * hs * cb)), .022)
        d = smin(d, round_cone(P, V(X(.050, -.060, .101)), V(X(.063, -.010, .103)), .0050 * hs, .0045 * hs), .020)
        # the cheek's soft fullness over the masseter and buccal pad (keeps the face from looking gaunt)
        cp = .96 if m else .96 * 1.22                                    # (his lean, the planes show; hers full and round)
        if "cheekpad" not in OFF:                                   # (high and soft: it must not end in a line by the chin)
            d = smin(d, ellipsoid(P, V(X(.036, -.040, .066)), (.013 * hs * cp, .026 * hs * cp, .034 * hs * cp)), .04)
        if not m:
            # her softer face: the round "apple" of the cheek under the eye
            d = smin(d, ellipsoid(P, V(X(.033, -.073, .091)), (.016 * hs, .0085 * hs, .0135 * hs)), .02)
        # behind and below the ear: the mastoid and the upper neck muscles fill the skull's underside (no dent)
        # (small: it must not widen the neck under the ear)
        d = smin(d, ellipsoid(P, V(X(.034, .038, .084)), (.014 * hs, .026 * hs, .028 * hs)), .018)
        # mandible: the lower border chin -> angle, the ramus up toward the ear; the chin's mound (squarer on him)
        jw = 1.08 if m else .48                                     # her jaw slight, no angle to see
        # (the angle stays inside the face's outline: a fat end cap there shows as a knob under the ear)
        # (the border is a slim edge under the face's own taper: a fat one, blended wide, piles
        # up with the cheek and the neck into a flap beside the mouth; blended tight, it creases)
        jr = (.0058, .0062, .022) if m else (.0072, .0076, .026)
        if "jawline" not in OFF:
            d = smin(d, round_cone(P, V(X(.004, -.084, .013)), V(g["gonion"]), jr[0] * hs * jw, jr[1] * hs * jw), jr[2])   # the jawline
        if "ramus" not in OFF:
            d = smin(d, round_cone(P, V(g["gonion"]), V(X(.060, .004, .088)), .0064 * hs * jw, .0070 * hs), .016 if m else .018)
        # the chin: carried by the jaw's own sections, only a small mound on top
        d = smin(d, ellipsoid(P, V(g["pogonion"] + Vector((0, .0065, -.001))),
                              ((.021 if m else .011) * hs * F("chin"), .0050 * hs, (.010 if m else .008) * hs * F("chin"))), .010)
        # lips
        Q = P.copy()
        Q[:, 1] -= ARCH / hs * Q[:, 0] ** 2                         # the lips follow the dental arch
        d = smin(d, self._lips[0](Q), .004)
        d = smin(d, self._lips[1](Q), .004)
        # orbits hollowed round the eyeball, the lids a thin shell over it
        ec, er = g["eye_c"], g["eye_r"]
        op = (g["eye_hu"] + g["eye_hl"]) / (.0106 * hs)              # the orbit opened to the lid opening
        L = g["lid"]
        d = smax(d, -ellipsoid(P, V(ec + Vector((.0005, -.0095, .0012))), (.0150 * hs, (.0050 if m else .0033) * hs, .0098 * hs * op)), .005)
        q = P - V(ec)
        rx = np.where(q[:, 0] >= 0, L["rxl"], L["rxm"]).astype(F32)
        R_ = L["R"]
        k0 = np.sqrt((q[:, 0] / rx) ** 2 + (q[:, 1] / R_) ** 2 + (q[:, 2] / R_) ** 2)
        k1 = np.sqrt((q[:, 0] / rx ** 2) ** 2 + (q[:, 1] / R_ ** 2) ** 2 + (q[:, 2] / R_ ** 2) ** 2)
        dl = k0 * (k0 - 1) / np.maximum(k1, 1e-9)
        # the upper lid meets the brow's soft tissue in a crease; the lower lid runs soft into the cheek
        t = np.clip((q[:, 2] + .003) / .006, 0, 1)
        tx = np.clip(1.35 - np.abs(q[:, 0]) / (.0115 * hs), 0, 1)
        d = smin(d, dl, .0060 - (.0032 if m else .0015) * t * t * (3 - 2 * t) * tx * tx * (3 - 2 * tx))
        hh = np.where(q[:, 2] >= 0, g["eye_hu"], g["eye_hl"]) * 1.2
        ww = np.where(q[:, 0] >= 0, L["wl"], L["wm"]) * 1.04
        rho = np.sqrt((q[:, 0] / ww) ** 2 + (q[:, 2] / hh) ** 2)
        wgt = 1 - np.clip((rho - .86) / .30, 0, 1) ** 2 * (3 - 2 * np.clip((rho - .86) / .30, 0, 1))
        wgt = wgt * (q[:, 1] < 0)
        d = d + (dl - d) * wgt
        # nose: dorsum from the root to the tip, the tip's lobule, the alae; nostrils hollowed
        tip, sub = g["pronasale"], g["subnasale"]
        nk = (1.08 if m else .74) * F("nose_width")
        d = smin(d, self._nose(P), .008)
        d = smin(d, ellipsoid(P, V(tip + Vector((0, .0075, -.0025))), (.0070 * nk, .0050, .0058)), .008)
        d = smin(d, ellipsoid(P, V(sub + Vector((.0122 * nk, .0072, .0064))), (.0048 * nk, .0074, .0060)), .004)
        # nostrils that go up into the nose, not a dent under it
        d = smax(d, -ellipsoid(P, V(sub + Vector((.0064 * nk, .0060, .0022))), (.0036 * nk, .0052, .0040)), .0016)
        if ear:
            d = smin(d, self.ear(P, g), .006)
        return d

    def ear(self, P, g=None):
        return self.ear_anatomy(P, g or self.head_geometry())

    def ear_anatomy(self, P, g):
        """the outer ear as its parts: the auricle's plate standing off the head toward the back on a root, the helix
        (its rim, from the crus above the canal over the top and down the back into the lobe), the antihelix with its
        two crura, the scapha between them, the concha's bowl, the tragus and antitragus, the lobe. Everything is a
        relief on the plate's outer face (no overhang a base mesh's quads would fold over)."""
        es = g["hs"] * self.face("ear_size")
        c = g["tragion"] + Vector((.006 * es + .006 * (self.face("ear_out") - 1), .012 * es, .005 * es))
        tilt = math.radians(14)
        R = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]], F32)
        q = ((P - V(c)) @ R.T) / es                              # local, in ear units: 0 out, 1 back, 2 up
        u, v, w = q[:, 1], q[:, 2], q[:, 0]
        cant = .26
        wp = w - cant * u                                       # height over the plate's mid surface
        L = np.stack([u, v, wp], 1).astype(F32)                 # the plate's own frame (sheared: fine at this size)

        def tube(pts, r, k=.0012):
            out = None
            for (a, ra), (b, rb) in zip(zip(pts[:-1], r[:-1]), zip(pts[1:], r[1:])):
                dd = round_cone(L, V(a), V(b), ra, rb)
                out = dd if out is None else smin(out, dd, k)
            return out

        # the plate: an egg, narrower toward the lobe
        nar = 1 - .22 * np.clip(-v / .03, 0, 1) ** 1.5
        a_, b_ = .0160 * nar, .0300
        k0 = np.sqrt((u / a_) ** 2 + (v / b_) ** 2 + (wp / .0030) ** 2)
        k1 = np.sqrt((u / a_ ** 2) ** 2 + (v / b_ ** 2) ** 2 + (wp / .0030 ** 2) ** 2)
        d = k0 * (k0 - 1) / np.maximum(k1, 1e-9)
        # the root that carries it off the head (the back of the concha)
        root = ellipsoid(np.stack([u, v, w], 1).astype(F32), V((.0005, .002, -.0050)), (.0120, .0210, .0085))
        d = smin(d, root, .004)
        h = .0012                                                # the rim's centre line over the mid surface
        helix = tube([(-.0030, .0050, h), (-.0085, .0105, h), (-.0118, .0185, h), (-.0085, .0262, h), (.0005, .0285, h),
                      (.0090, .0245, h), (.0138, .0150, h), (.0146, .0030, h), (.0128, -.0085, h), (.0090, -.0165, h)],
                     [.0018, .0023, .0026, .0027, .0027, .0027, .0026, .0025, .0022, .0018])
        fine = getattr(self, "fine", False)
        if not fine:
            # the base mesh: a full rim, one bowl, the tragus and the lobe (what its quads can carry cleanly)
            rim = tube([(-.0085, .0105, h), (-.0112, .0185, h), (-.0080, .0255, h), (.0005, .0278, h),
                        (.0088, .0240, h), (.0132, .0150, h), (.0140, .0030, h), (.0122, -.0085, h), (.0085, -.0165, h)],
                       [.0026, .0030, .0031, .0031, .0031, .0030, .0029, .0026, .0022], k=.002)
            d = smin(d, rim, .0030)
            d = smin(d, ellipsoid(L, V((.0015, -.0235, .0004)), (.0072, .0078, .0036)), .004)
            d = smax(d, -ellipsoid(L, V((.0005, .0040, .0052)), (.0072, .0135, .0058)), .0035)
            d = smin(d, ellipsoid(L, V((-.0098, -.0010, .0020)), (.0040, .0052, .0028)), .0035)
            return d * es
        d = smin(d, helix, .0020)
        anti = tube([(.0048, -.0120, h), (.0075, -.0040, h), (.0078, .0060, h), (.0050, .0150, h), (.0008, .0215, h)],
                    [.0018, .0022, .0023, .0021, .0016])
        d = smin(d, anti, .0020)
        d = smin(d, tube([(.0074, .0075, h), (.0020, .0125, h), (-.0050, .0140, h)], [.0020, .0018, .0014]), .0020)   # lower crus
        # the lobe: soft and full
        d = smin(d, ellipsoid(L, V((.0015, -.0235, .0004)), (.0072, .0078, .0034)), .003)
        # the concha's bowl, behind the tragus, down toward the canal
        bowl = ellipsoid(L, V((-.0015, .0005, .0042)), (.0062, .0090, .0062))
        d = smax(d, -bowl, .0022)
        d = smax(d, -ellipsoid(L, V((.0090, .0165, .0036)), (.0022, .0060, .0024)), .0016)       # the scapha's groove
        # tragus (a flap over the canal from the front) and antitragus
        d = smin(d, ellipsoid(L, V((-.0098, -.0010, .0022)), (.0036, .0046, .0026)), .0022)
        d = smin(d, ellipsoid(L, V((.0030, -.0122, .0020)), (.0030, .0026, .0020)), .0020)
        return d * es
