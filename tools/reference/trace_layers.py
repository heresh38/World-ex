"""Adds to a traced weapon (tools/reference/sarketh_trace/<gun>.json + .npz, written by trace_sheet.py) what the layered
builder needs (sarketh_guns.layered): the outline inset to a series of depths (`layers`: the shell built as stacked
layers, thin at the edge and full in the middle, so the gun rounds like a carapace in crisp steps) and the grip's flank
(`grip_panel`: where the rubber panel lies), from the gun's own distance field. Run after trace_sheet.py:

    python tools/reference/trace_layers.py [skr_rifle ...]
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from trace_sheet import polys  # noqa: E402

OUT = os.path.join(HERE, 'sarketh_trace')
DEPTHS = [0.0, 1.6, 3.2, 5.0, 7.5, 10.5]                 # px in from the outline, one layer each
# the grip's flank in metres in the sheet's frame (sarketh_guns.TRACED grip fractions; y forward = -, z up): a box the
# outline is cut to, kept a little in from the edge
GRIP = {'skr_rifle': dict(grip=(.700, .560), box=(-.012, .048, -.140, -.056))}


def run(name):
    T = np.load(os.path.join(OUT, name + '.npz'))
    S = json.load(open(os.path.join(OUT, name + '.json')))
    inside, mask, px = T['inside'], T['mask'], float(T['px'])
    S['layers'] = [dict(depth=d, polys=polys(inside > d if d > 0 else mask, 1.2, 10)) for d in DEPTHS]
    g = GRIP.get(name)
    if g:
        H, W = mask.shape
        gu, gv = g['grip'][0] * W, g['grip'][1] * H
        y0, y1, z0, z1 = g['box']
        cols = np.arange(W)[None, :]
        rows = np.arange(H)[:, None]
        yy, zz = (cols - gu) * px, (gv - rows) * px
        inbox = (yy > y0) & (yy < y1) & (zz > z0) & (zz < z1)
        S['grip_panel'] = polys(mask & inbox & (inside > 2.5), 1.2, 20)
    json.dump(S, open(os.path.join(OUT, name + '.json'), 'w'))
    print(name, [len(L['polys']) for L in S['layers']], 'grip panel', len(S.get('grip_panel', [])))


if __name__ == '__main__':
    for n in (sys.argv[1:] or ['skr_rifle']):
        run(n)
