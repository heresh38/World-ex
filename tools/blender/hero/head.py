"""The head cage: a quad sphere (cube-sphere, 12 x 12 cells per side) shaped to the skull, with the face's edge loops
made in its own topology the way a modeller box-models a head. Cells are picked by their grid index (front face:
column i = x, row j = z, both -6..5), so everything is deterministic and mirror-symmetric:

  eyes    3 x 1 cells (columns 1..3 / -4..-2, row -1) inset three times: concentric loops (lid margin, lids, orbit),
          the middle removed -> each eye opening is an 8-vertex loop
  mouth   4 x 1 cells (columns -2..1, the bottom front row) inset three times (lip line, lips, the ring round the
          mouth), the middle removed -> the lips' 10-vertex slit
  nose    the 2-wide strip between the eyes down to the mouth ring (columns -1..0, rows -5..-1), extruded forward
  ears    2 x 3 cells on each side face, extruded out and back
  neck    4 x 6 cells underneath removed -> the 20-vertex neck opening the body's neck rings meet

Shape is approximate: fit.py projects the subdivided head onto the anatomical target (shape.py).
"""
import bmesh
from mathutils import Vector

N = 12
H = N // 2


def build_head(cage, T):
    bm = cage.bm
    hh = T["head_h"]
    cz = T["chin_z"] + hh * .53
    cy = .006
    rx, ry, rz = T["head_breadth"] / 2, T["head_length"] / 2 * .98, hh * .52
    centre = Vector((0, cy, cz))
    verts, cells = {}, {}

    def vert(g):
        if g not in verts:
            p = Vector(g).normalized()
            verts[g] = cage.v(centre + Vector((p.x * rx, p.y * ry, p.z * rz)), "head")
        return verts[g]

    for axis in range(3):
        o = [k for k in range(3) if k != axis]
        for sgn in (-1, 1):
            for i in range(-H, H):
                for j in range(-H, H):
                    def g(a, b):
                        c = [0, 0, 0]
                        c[axis] = sgn * H
                        c[o[0]], c[o[1]] = a, b
                        return tuple(c)
                    f = cage.quad(*[vert(x) for x in (g(i, j), g(i + 1, j), g(i + 1, j + 1), g(i, j + 1))])
                    if f:
                        cells[(axis, sgn, i, j)] = f
    bmesh.ops.recalc_face_normals(bm, faces=list(cells.values()))
    FRONT, SIDE_L, SIDE_R, BOTTOM = (1, -1), (0, 1), (0, -1), (2, -1)

    def block(face, i0, i1, j0, j1):
        return [cells[(face[0], face[1], i, j)] for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]

    def hole_loop(vs):
        bv = [v for v in vs if v.is_valid and v.is_boundary]
        if not bv:
            return []
        loop, prev = [bv[0]], None
        while len(loop) < 400:
            cur = loop[-1]
            nxt = next((e.other_vert(cur) for e in cur.link_edges if e.is_boundary and e.other_vert(cur) is not prev
                        and e.other_vert(cur) in bv), None)
            if nxt is None or nxt is loop[0]:
                break
            prev = cur
            loop.append(nxt)
        return loop

    def inset_hole(faces, th):
        inner = faces
        for t in th:
            bmesh.ops.inset_region(bm, faces=inner, thickness=t, depth=0.0, use_even_offset=True, use_boundary=True)
        vs = {v for f in inner for v in f.verts}
        bmesh.ops.delete(bm, geom=inner, context='FACES')
        loop = hole_loop(list(vs))
        for v in bm.verts:                                      # the inset's new vertices belong to the head too
            if v not in cage.part_of:
                cage.part_of[v] = "head"
        return loop

    by_pos = {}
    for gk, v in verts.items():
        by_pos[tuple(round(c, 7) for c in v.co)] = gk
    caps = {}

    def extrude(faces, move, part):
        r = bmesh.ops.extrude_face_region(bm, geom=faces)
        nv = [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.delete(bm, geom=faces, context='FACES')
        for v in nv:
            caps[v] = (part, by_pos[tuple(round(c, 7) for c in v.co)])      # the cap vertex's grid cell corner
            move(v)
            cage.part_of[v] = part
        return nv

    feat = {}
    # three insets each (thin: the rows are ~2 cm, the loops are laid out properly by headfit.py)
    feat["eye_L"] = inset_hole(block(FRONT, 1, 3, -1, -1), (.002, .002, .002))
    feat["eye_R"] = inset_hole(block(FRONT, -4, -2, -1, -1), (.002, .002, .002))
    feat["mouth"] = inset_hole(block(FRONT, -2, 1, -6, -6), (.0016, .0016, .0016))
    eye_z, base_z = T["eye_z"], T["chin_z"] + hh * .313

    def nose_move(v):
        t = max(0.0, min(1.0, (eye_z - v.co.z) / (eye_z - base_z)))
        v.co.y -= .006 + .016 * t
    feat["nose"] = extrude(block(FRONT, -1, 0, -5, -1), nose_move, "nose")
    for side, face, sx in (("L", SIDE_L, 1), ("R", SIDE_R, -1)):
        # side faces: i = y index, j = z index; the ear sits a little behind the centre, between brow and nose base
        def ear_move(v, sx=sx):
            v.co.x += sx * .012
            v.co.y += .004
        feat["ear_" + side] = extrude(block(face, 0, 1, -2, 0), ear_move, "ear_" + side)
    nb = block(BOTTOM, -2, 1, -2, 3)
    vs = {v for f in nb for v in f.verts}
    bmesh.ops.delete(bm, geom=nb, context='FACES')
    feat["neck"] = hole_loop(list(vs))
    cage.head_features = feat
    cage.head = dict(centre=centre, radii=(rx, ry, rz), verts=verts, caps=caps, feat=feat)
    return feat
