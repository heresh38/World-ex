"""Face customisation morphs (glTF morph targets) for the player heads.

Every morph is a smooth space warp in head-local coordinates (metres, front = -Y), so the same function moves the head
skin, the brows and (where it makes sense) the eyeballs and they stay glued together. Presets in one group are mutually
exclusive in the game (weight 0/1); sliders run from -1 to 1.
"""
import numpy as np

F32 = np.float32

GROUPS = {
    'nose': ['nose_button', 'nose_aquiline', 'nose_broad', 'nose_narrow', 'nose_long', 'nose_snub'],
    'mouth': ['mouth_full', 'mouth_thin', 'mouth_wide', 'mouth_small', 'mouth_smile', 'mouth_pout'],
    'eyes': ['eyes_round', 'eyes_almond', 'eyes_upturned', 'eyes_downturned', 'eyes_hooded', 'eyes_large'],
    'ears': ['ears_small', 'ears_large', 'ears_pointed', 'ears_elven', 'ears_round'],
}
SLIDERS = ['jaw_width', 'chin_length', 'chin_width', 'cheekbones', 'brow_height', 'eye_spacing', 'face_width', 'nose_size']


def fall(L, c, r):
    """Compact smooth falloff: 1 at c, 0 beyond r."""
    d2 = ((L - np.asarray(c, F32)) ** 2).sum(1) / (r * r)
    return np.clip(1 - d2, 0, 1) ** 3


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


class Morphs:
    def __init__(self, head, sex):
        self.h = head; self.s = head.s; self.m = sex == 'male'
        self.lz = 0.0 if self.m else .002

    def S(self, *v):
        return np.array(v, F32) * self.s

    # ---------------------------------------------------------------- eyes helper
    def _eye(self, L, fn, inner=True):
        """Apply fn(a, b, w) -> (a2, b2) in each eye's opening plane, keeping each vertex's distance to the eye centre."""
        out = L.copy()
        h, s = self.h, self.s
        for sx in (1, -1):
            E = (h.eye * np.array([sx, 1, 1])).astype(F32)
            q = L - E
            r = np.sqrt((q ** 2).sum(1))
            w = np.clip(1 - ((r - h.eye_r) / (.012 * s)) ** 2, 0, 1) ** 2 * (r > h.eye_r * .9) * sstep(.006 * s, -.004 * s, q[:, 1])
            if not w.any():
                continue
            a = q[:, 0] * sx; b = q[:, 2]
            a2, b2 = fn(a, b, w)
            q2 = q.copy(); q2[:, 0] = a2 * sx; q2[:, 2] = b2
            # keep radius (lids slide over the eyeball)
            r2 = np.sqrt((q2 ** 2).sum(1))
            q2 *= (r / np.maximum(r2, 1e-9))[:, None]
            out = out + (q2 - q) * (w > 0)[:, None]
        return out

    # ---------------------------------------------------------------- morph table
    def apply(self, name, L, part='skin'):
        """Displaced copy of head-local points L for morph `name`. part: skin | eyeball | brow."""
        s, S, lz = self.s, self.S, self.lz
        x, y, z = L[:, 0], L[:, 1], L[:, 2]
        D = np.zeros_like(L)
        tip = S(0, -.091, -.021)
        if part == 'eyeball' and name not in ('eye_spacing', 'face_width'):
            return L.copy()
        if name == 'nose_button':
            f = fall(L, tip, .02 * s); D[:, 1] += .0045 * s * f; D[:, 2] += .004 * s * f
            f2 = fall(L, S(0, -.078, .0), .016 * s); D[:, 1] += .0018 * s * f2
        elif name == 'nose_aquiline':
            D[:, 1] -= .0032 * s * fall(L, S(0, -.08, .0), .011 * s)
            D[:, 2] -= .003 * s * fall(L, tip, .013 * s)
        elif name == 'nose_broad':
            f = fall(L, S(0, -.083, -.022), .024 * s); D[:, 0] += x * .4 * f
        elif name == 'nose_narrow':
            f = fall(L, S(0, -.08, -.012), .03 * s); D[:, 0] -= x * .3 * f
        elif name == 'nose_long':
            f = fall(L, tip, .022 * s); D[:, 1] -= .004 * s * f; D[:, 2] -= .006 * s * f
        elif name == 'nose_snub':
            f = fall(L, tip, .016 * s); D[:, 2] += .003 * s * f; D[:, 1] += .001 * s * f
            D[:, 0] += x * .18 * fall(L, S(0, -.084, -.027), .016 * s)
        elif name == 'nose_size':
            f = fall(L, S(0, -.083, -.012), .035 * s); c = S(0, -.07, -.012)
            D += (L - c) * .22 * f[:, None]
        elif name in ('mouth_full', 'mouth_thin', 'mouth_wide', 'mouth_small', 'mouth_smile', 'mouth_pout'):
            zm = (-.0503 + lz) * s
            f = fall(L, S(0, -.074, -.05 + lz), .03 * s)
            if name == 'mouth_full':
                g = fall(L, S(0, -.077, -.05 + lz), .02 * s)
                D[:, 1] -= .0028 * s * g; D[:, 2] += (z - zm) * .35 * g
            elif name == 'mouth_thin':
                g = fall(L, S(0, -.077, -.05 + lz), .02 * s)
                D[:, 1] += .0016 * s * g; D[:, 2] -= (z - zm) * .32 * g
            elif name == 'mouth_wide':
                D[:, 0] += x * .22 * f
            elif name == 'mouth_small':
                D[:, 0] -= x * .17 * f
            elif name == 'mouth_smile':
                for sx in (1, -1):
                    g = fall(L, S(sx * .021, -.071, -.0505 + lz), .011 * s)
                    D[:, 2] += .0032 * s * g; D[:, 0] += sx * .001 * s * g; D[:, 1] += .0008 * s * g
            elif name == 'mouth_pout':
                g = fall(L, S(0, -.078, -.05 + lz), .016 * s)
                D[:, 1] -= .0035 * s * g
                for sx in (1, -1):
                    D[:, 2] -= .0015 * s * fall(L, S(sx * .021, -.071, -.0505 + lz), .01 * s)
        elif name.startswith('eyes_'):
            if part == 'eyeball':
                return L.copy()
            if name == 'eyes_round':
                return self._eye(L, lambda a, b, w: (a, b * (1 + .32 * w)))
            if name == 'eyes_almond':
                return self._eye(L, lambda a, b, w: (a * (1 + .1 * w), b * (1 - .18 * w) + .0006 * s * w * np.sign(a)))
            if name in ('eyes_upturned', 'eyes_downturned'):
                t = .16 if name == 'eyes_upturned' else -.13

                def rotf(a, b, w):
                    c, sn = np.cos(t * w), np.sin(t * w)
                    return a * c - b * sn, a * sn + b * c
                return self._eye(L, rotf)
            if name == 'eyes_hooded':
                return self._eye(L, lambda a, b, w: (a, b - .0019 * s * w * (b > -.001 * s)))
            if name == 'eyes_large':
                return self._eye(L, lambda a, b, w: (a * (1 + .13 * w), b * (1 + .16 * w)))
        elif name.startswith('ears_'):
            out = L.copy()
            for sx in (1, -1):
                c = (self.h.ear * np.array([sx, 1, 1])).astype(F32)
                ear = sstep(.06 * s, .068 * s, x * sx) * fall(L, c, .045 * s)
                root = c - np.array([sx * .006 * s, 0, 0], F32)
                q = L - root
                if name == 'ears_small':
                    D += q * (-.2 * ear)[:, None]
                elif name == 'ears_large':
                    D += q * (.18 * ear)[:, None]
                elif name in ('ears_pointed', 'ears_elven'):
                    k = 1.0 if name == 'ears_pointed' else 1.9
                    t = np.clip((L[:, 2] - c[2]) / (.026 * s), 0, 1.6) * ear
                    D[:, 2] += .012 * k * s * t ** 2
                    D[:, 1] += .009 * k * s * t ** 2
                    D[:, 0] += sx * .003 * k * s * t ** 2
                elif name == 'ears_round':
                    t = np.clip((L[:, 2] - c[2]) / (.026 * s), 0, 1) * ear
                    D[:, 2] -= .004 * s * t ** 2; D[:, 1] -= .002 * s * t ** 2
                    D[:, 0] += sx * .002 * s * ear
            return out + D
        elif name == 'jaw_width':
            g = sstep(-.02 * s, -.065 * s, z) * sstep(.012 * s, .04 * s, np.abs(x)) * sstep(.03 * s, 0, y) * (z > -.12 * s)
            D[:, 0] += x * .14 * g
        elif name == 'chin_length':
            f = fall(L, S(0, -.06, -.095 + lz), .03 * s); D[:, 2] -= .008 * s * f; D[:, 1] -= .002 * s * f
        elif name == 'chin_width':
            f = fall(L, S(0, -.06, -.09 + lz), .03 * s); D[:, 0] += x * .3 * f
        elif name == 'cheekbones':
            for sx in (1, -1):
                f = fall(L, S(sx * .048, -.05, -.004), .022 * s)
                D[:, 0] += sx * .0035 * s * f; D[:, 1] -= .002 * s * f; D[:, 2] += .001 * s * f
        elif name == 'brow_height':
            for sx in (1, -1):
                E = self.h.eye * np.array([sx, 1, 1])
                f = fall(L, E + S(0, -.008, .02), .022 * s) * (z > E[2] + .0085 * s)
                D[:, 2] += .0032 * s * f
        elif name == 'eye_spacing':
            for sx in (1, -1):
                E = self.h.eye * np.array([sx, 1, 1])
                f = fall(L, E, .03 * s) if part != 'eyeball' else (np.abs(x - E[0]) < .02 * s).astype(F32)
                D[:, 0] += sx * .0028 * s * f
        elif name == 'face_width':
            g = sstep(.07 * s, .0, y) * sstep(-.11 * s, -.06 * s, z) * sstep(.09 * s, .04 * s, z)
            D[:, 0] += x * .07 * g
        return L + D

    def names(self):
        out = []
        for g in GROUPS.values():
            out += g
        return out + SLIDERS
