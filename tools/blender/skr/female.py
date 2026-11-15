"""The female Sarketh's armour (the owner's sheet, "female"): the same armour as the male's, cut to HER body (her own
skeleton, her own sculpt in anatomy.py: narrower shoulders and waist, wider hips, a slighter frame), with pieces of her
own where the body differs: plates shaped over the chest instead of his pectoral plates, wider plates over the hips, a
lighter pauldron, the crest swept further back.

How the male's layout is carried onto her: every point it names is taken in the male skeleton's frame (which bone it lies
by, how far along it, how far off it) and set down in the same place on her bone, the offset scaled to her build; a
width scales the same way. The helmet is rigid: moved and scaled with her head. Anything that does not suit her is
skipped by name and her own pieces added after it.
"""
import numpy as np
import anatomy
import male as male_layout

SKIP = {'pec', 'pec2', 'ribfront', 'hipflare', 'pauldron', 'pauldron2', 'pauldron3', 'belly0', 'belly1', 'belly2', 'belly3', 'scapula2', 'lowback', 'glute'}
TORSO = {'hips', 'spine', 'chest', 'neck'}


class Fit:
    """an Armour seen through the male -> female mapping"""

    def __init__(self, A, JM, JF):
        object.__setattr__(self, 'A', A)
        object.__setattr__(self, 'JM', {k: (np.asarray(v[0], float), np.asarray(v[1], float)) for k, v in JM.items()})
        object.__setattr__(self, 'JF', {k: (np.asarray(v[0], float), np.asarray(v[1], float)) for k, v in JF.items()})
        hm, hf = self.JM['head'][0], self.JF['head'][0]
        object.__setattr__(self, 'head', (hm, hf, .92))
        object.__setattr__(self, '_bones', [b for b in JM if b != 'root'])
        object.__setattr__(self, 'own', {})               # her own values for what the male layout sets on the kit

    def __getattr__(self, k):
        return getattr(self.A, k)

    def __setattr__(self, k, v):
        setattr(self.A, k, self.own.get(k, v))

    # ---- the mapping
    def scale_of(self, b):
        if b == 'head':
            return .92
        if b in TORSO:
            return .80
        return .80                                          # her limbs are slighter

    def where(self, p):
        p = np.asarray(p, float)
        best = None
        for b in self._bones:
            a, c = self.JM[b]
            d = c - a
            t = float(np.clip(np.dot(p - a, d) / max(np.dot(d, d), 1e-9), 0, 1))
            q = a + d * t
            dist = np.linalg.norm(p - q)
            if best is None or dist < best[0]:
                best = (dist, b, t, p - q)
        return best[1:]

    def P(self, p):
        b, t, o = self.where(p)
        a, c = self.JF[b]
        return a + (c - a) * t + o * self.scale_of(b)

    def Wd(self, w, p):
        return w * self.scale_of(self.where(p)[0])

    def head_in(self, P):                                   # her space -> his, for the helmet's fields
        hm, hf, s = self.head
        return (np.asarray(P, np.float32) - hf.astype(np.float32)) / s + hm.astype(np.float32)

    def head_out(self, p):
        hm, hf, s = self.head
        return (np.asarray(p, float) - hm) * s + hf

    # ---- the kit, mapped
    def blade(self, name, a, b, w, *args, field=None, bend=(0, 0, 0), **kw):
        if name in SKIP:
            return []
        s = self.scale_of(self.where(a)[0])
        if field is not None:
            fm = field
            field = lambda P: fm(self.head_in(P)) * self.head[2]
            a2, b2 = self.head_out(a), self.head_out(b)
        else:
            a2, b2 = self.P(a), self.P(b)
        return self.A.blade(name, a2, b2, w * s, *args, field=field, bend=tuple(np.asarray(bend, float) * s), **kw)

    def wrap(self, name, a, b, bone, *args, **kw):
        if name in SKIP:
            return []
        if 'reach' in kw:
            kw['reach'] = kw['reach'] * self.scale_of(bone)
        return self.A.wrap(name, self.P(a), self.P(b), bone, *args, **kw)

    def claw(self, name, a, b, r, bone, *args, **kw):
        return self.A.claw(name, self.P(a), self.P(b), r * self.scale_of(bone), bone, *args, **kw)

    def light(self, name, pts, width, *args, **kw):
        return self.A.light(name, [self.P(p) for p in pts], width, *args, **kw)

    def stud(self, name, p, r, *args, **kw):
        return self.A.stud(name, self.P(p), r, *args, **kw)

    def shell(self, name, bone, base_fn, lo, hi, off, thick, keep, mat_of, grooves=(), slits=(), **kw):
        s = self.head[2]
        bf = lambda P: base_fn(self.head_in(P)) * s
        kp = lambda P: keep(self.head_in(P)) * s
        mo = lambda c: mat_of(self.head_in(np.asarray([c]))[0])
        gr = [(self.head_out(p0), n, w * s) for p0, n, w in grooves]
        sl = [(self.head_out(a).astype(np.float32), self.head_out(b).astype(np.float32), r * s) for a, b, r in slits]
        return self.A.shell(name, bone, bf, self.head_out(lo), self.head_out(hi), off * s, thick * s, kp, mo, gr, sl, **kw)


def layout(A, J):
    JM = anatomy.joints('male')
    F = Fit(A, JM, J)
    F.own.update(thick_k=2.1, tip_k=.6, point_k=.55)       # her plates a little thinner
    male_layout.layout(F, JM)
    j = lambda b, e=0: np.asarray(J[b][e], float)
    ch, hp = j('chest'), j('hips')
    # her own: plates over the chest, each curved round its side of it, a V between them
    A.slot = 'chest'
    A.blade('bust', ch + (.024, -.124, .172), ch + (.120, -.090, .066), .096, 'chest', lift=.004, ridge=.005, thick=.006, peak=.45, base=.7)
    A.blade('bustlow', ch + (.040, -.128, .080), ch + (.110, -.098, .030), .060, 'chest', mat='dark', lift=.006, ridge=.004, peak=.45)
    A.blade('ribs_f', ch + (.130, -.040, .110), ch + (.135, .000, .000), .040, 'chest', lift=.003)
    # her own pauldron: one lighter layer
    A.slot = 'shoulders'
    sh = j('upperarm.L')
    A.blade('pauldron_f', sh + (-.034, -.016, .074), sh + (.092, .010, -.110), .098, 'upperarm.L', lift=.006, ridge=.006, thick=.007, peak=.32,
            tip=.006, bend=(.014, 0, 0))
    A.blade('pauldron_f2', sh + (.004, .004, .046), sh + (.104, .024, -.130), .070, 'upperarm.L', mat='dark', lift=.016, ridge=.005, peak=.32,
            tip=.008)
    # wide plates over the hips
    A.slot = 'belt'
    A.blade('hipwide', hp + (.120, -.050, .100), hp + (.182, -.010, -.080), .092, 'hips', lift=.010, ridge=.005, tip=.006, peak=.4)
    A.blade('hipback', hp + (.110, .060, .080), hp + (.150, .070, -.070), .070, 'hips', mat='dark', lift=.008, ridge=.004, peak=.4)
