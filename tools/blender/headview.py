"""Quick look at the player heads (anatomy.Head) without Blender: front / three-quarter / side / low views.

python tools/blender/headview.py out.png male|female [size]
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import anatomy, sdfview

out, sex = sys.argv[1], sys.argv[2]
size = int(sys.argv[3]) if len(sys.argv) > 3 else 320
H = anatomy.Head(sex)
center = np.array([0, -.01, -.005]) * H.s
center = np.array([0, -.03, -.01]) * H.s
sdfview.sheet(lambda P: H(P), center, .5, ['front', 'three', 'side', 'low'], out, size=size)
