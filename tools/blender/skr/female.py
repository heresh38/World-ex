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

# what of his set she does not wear: his rows of plates down every limb and round the trunk, his chest, his pauldron and
# his collar of shards, the neck's ring (the sheet's female: a few long flowing plates, the rest bare dark hide)
SKIP = {'pec', 'pec_m', 'pec_l', 'pec2', 'collar', 'collar0', 'collar1', 'collar2', 'collar3', 'collar4', 'ribs', 'flank', 'oblique',
        'pauldron', 'pauldron2', 'pauldron3', 'pauldron_rise', 'back', 'lowback', 'uarm', 'farm', 'thigh', 'shin', 'girdle', 'girdle_r',
        'tasset', 'tasset_b', 'hipcrest', 'trap2', 'wing2', 'neckring', 'scapula', 'foot', 'glute'}
TORSO = {'hips', 'spine', 'chest', 'neck'}
DARK = {'crest_a', 'crest_c'}          # her crest dark but for its lowest blade (the sheet's female)


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

    def shard(self, name, pts, w, face, bone, *args, thick=.006, **kw):
        if name in SKIP:
            return []
        if name in DARK:
            kw['mat'] = 'dark'
        if bone == 'head':                                   # the helmet's: moved and scaled with her head
            s = self.head[2]
            P = [self.head_out(q) for q in pts]
        else:
            s = self.scale_of(self.where(pts[0])[0])
            P = [self.P(q) for q in pts]
        return self.A.shard(name, P, w * s, face, bone, *args, thick=thick * s, **kw)

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
    F.own.update(thick_k=1.3, tip_k=1.0, point_k=.85)      # her plates a little thinner than his
    male_layout.layout(F, JM)
    j = lambda b, e=0: np.asarray(J[b][e], float)
    ch, hp = j('chest'), j('hips')
    sh, el, wr = j('upperarm.L'), j('forearm.L'), j('hand.L')
    hj, kn, hk, ba = j('thigh.L'), j('shin.L'), j('foot.L'), j('toes.L')
    # her own (the sheet's female): a rounded plate over each breast, a pale band over each collarbone, one rounded
    # pauldron with a point, a long flowing plate from the hip down the outside of each thigh with a dark one behind it, a
    # few plates down the outside of the arm and the front of the shin; the trunk and the inside of every limb bare
    A.slot = 'chest'
    A.blade('bust', ch + (.030, -.122, .178), ch + (.118, -.086, .066), .100, 'chest', lift=.004, ridge=.006, thick=.007, peak=.45, base=.72,
            point=.7, angular=.1)
    A.blade('bustlow', ch + (.046, -.124, .084), ch + (.112, -.094, .034), .056, 'chest', mat='dark', lift=.008, ridge=.004, peak=.45)
    A.blade('clav', ch + (.040, -.080, .238), sh + (.010, -.020, .040), .040, 'chest', lift=.006, ridge=.005, thick=.007, peak=.4, base=.6)
    A.blade('oblique_f', ch + (.100, -.040, -.060), hp + (.108, -.030, .110), .036, 'spine', lift=.003, tip=.008, free=.85, ridge=.005,
            peak=.35)
    A.slot = 'shoulders'
    A.blade('pauldron_f', sh + (-.040, -.012, .080), sh + (.096, .010, -.118), .120, 'upperarm.L', lift=.008, ridge=.008, thick=.010, peak=.42,
            tip=.010, bend=(.018, 0, 0), base=.75, point=.75, angular=.15)
    A.blade('pauldron_f2', sh + (.010, .004, .040), sh + (.110, .024, -.150), .084, 'upperarm.L', mat='dark', lift=.020, ridge=.006, peak=.42,
            tip=.012, base=.7, point=.8, angular=.15)
    A.shard('pauldron_fpt', [sh + (-.030, .030, .060), sh + (-.016, .046, .118), sh + (-.006, .066, .165)], .060, (1, -.6, .2),
            'upperarm.L', thick=.009, base=.75, peak=.35, point=.9, lower=.65, edge=.22)
    A.slot = 'arms'
    fa = ('forearm.L',)
    A.blade('uarm_f', sh + (.046, -.006, -.130), el + (.030, .006, .070), .056, 'upperarm.L', lift=.004, ridge=.006, peak=.35, tip=.008,
            free=.9, only=('upperarm.L',))
    A.blade('farm_f1', wr + (.026, .004, .030), el + (.032, .028, -.030), .062, 'forearm.L', lift=.005, tip=.014, free=.80, ridge=.007,
            peak=.40, base=.5, only=fa)
    A.blade('farm_f2', wr + (.014, .030, .060), el + (.016, .052, -.060), .048, 'forearm.L', lift=.009, tip=.012, free=.80, ridge=.006,
            peak=.40, base=.5, mat='dark', only=fa)
    A.blade('farm_f3', wr + (.020, -.004, -.004), wr + (.030, .014, .100), .050, 'forearm.L', lift=.012, tip=.010, free=.80, ridge=.006,
            peak=.40, base=.55, only=fa)
    A.slot = 'belt'
    A.blade('hipwide', hp + (.112, -.052, .110), hj + (.070, -.040, -.200), .096, 'hips', lift=.010, ridge=.008, thick=.009, tip=.010,
            free=.9, peak=.35, base=.6)
    A.blade('hipback', hp + (.112, .050, .090), hj + (.080, .030, -.170), .072, 'hips', mat='dark', lift=.006, ridge=.005, peak=.4, base=.6)
    A.slot = 'legs'
    th_ = ('thigh.L',)
    A.blade('thigh_f', hj + (.076, -.030, -.170), kn + (.040, -.030, .070), .080, 'thigh.L', lift=.012, ridge=.008, thick=.009, peak=.35,
            base=.5, tip=.010, free=.9, only=th_)
    A.blade('thigh_f2', hj + (.020, -.070, -.120), kn + (.008, -.046, .110), .060, 'thigh.L', lift=.006, ridge=.006, peak=.38, base=.5,
            mat='dark', only=th_)
    A.blade('thigh_f3', hj + (.084, .020, -.250), kn + (.052, .010, .120), .056, 'thigh.L', lift=.008, ridge=.006, peak=.38, base=.5,
            only=th_)
    sn = ('shin.L',)
    A.blade('shin_f', kn + (.008, -.040, -.090), hk + (.008, -.028, .140), .058, 'shin.L', lift=.006, ridge=.007, thick=.008, peak=.38,
            base=.5, only=sn)
    A.blade('shin_f2', kn + (.040, -.004, -.110), hk + (.030, .004, .150), .046, 'shin.L', lift=.006, ridge=.006, peak=.38, base=.5,
            mat='dark', only=sn)
    A.slot = 'feet'
    ft = ('foot.L',)
    A.blade('meta_f', hk + (.004, -.026, -.040), ba + (.004, -.028, .070), .046, 'foot.L', lift=.005, ridge=.006, thick=.008, peak=.4,
            base=.55, only=ft)
