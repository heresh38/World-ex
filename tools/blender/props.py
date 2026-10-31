"""Prop and machine builders shared by the ship interior, the city and the planets.

Every builder returns a root empty at the prop's floor origin; its meshes are joined per prop so each
prop costs one or two draw calls. Animated machines keep named child nodes (welder_*, turret_head, ...)
that the game rotates procedurally. Custom property 'solid' (on the root) marks props that get an AABB
collider in the exported layout.
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bl
from mathutils import Vector

R90 = math.pi / 2


def _root(name, loc=(0, 0, 0), rot=0.0, solid=True):
    r = bl.empty(name, loc, rot=(0, 0, rot))
    r['solid'] = 1 if solid else 0
    return r


def _pack(root, parts, name=None):
    for o in parts:
        bl.apply_all(o)
    g = bl.join(parts, name or root.name + '_mesh')
    g.parent = root
    return g


def M():
    p = bl.palette()
    p.update(
        panel=bl.mat('panel', '#9ea3aa', .55, .45, image='panel_c.jpg', normal='panel_n.jpg'),
        hull=bl.mat('hull_white', '#e8e2d4', .1, .35),
        leather=bl.mat('leather', '#2a2420', 0, .55),
        screen=bl.mat('screen', '#0a2a3a', 0, .2, emit='#2ad0ff', strength=2.2),
        screen_amber=bl.mat('screen_amber', '#3a2a0a', 0, .2, emit='#ffb340', strength=2.2),
        holo=bl.mat('holo', '#40e0ff', 0, .2, emit='#40e0ff', strength=3, alpha=.45),
        hazard=bl.mat('hazard', '#ffffff', .2, .6, image='hazard_c.jpg'),
        crate=bl.mat('crate', '#4f5a3a', .3, .55, image='panel_c.jpg', normal='panel_n.jpg'),
        crate2=bl.mat('crate_orange', '#b5651d', .3, .5, image='panel_c.jpg', normal='panel_n.jpg'),
        yellow=bl.mat('machine_yellow', '#d9a21b', .4, .4),
        enemy=bl.mat('enemy_plate', '#2c2f36', .7, .4),
    )
    return p


# ------------------------------------------------------------------ ship furniture
SCREEN_COLORS = dict(data='#2ad0ff', graph='#3fffb0', radar='#40ff90', nav='#4fb8ff', status='#2ad0ff',
                     amber='#ffb340', keys='#6fd8ff')


def screen_mat(kind):
    """Runtime-animated screen: ship.js swaps materials named screen_<kind> for live canvas textures."""
    c = SCREEN_COLORS.get(kind, '#2ad0ff')
    return bl.mat('screen_' + kind, '#081820', 0, .25, emit=c, strength=1.6)


def screen(kind, w, h, loc=(0, 0, 0), tilt=0.0, yaw=0.0, name='scr'):
    """Flat screen quad (UV 0..1 across the face) facing -Y before tilt (positive tilts the top away) / yaw."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=(R90 - tilt, 0, yaw))
    o = bpy.context.object
    o.scale = (w, h, 1)
    return bl._finish(o, screen_mat(kind), name)


def captain_chair(loc=(0, 0, 0), rot=0.0, name='ST_captain_chair', side_screen=True):
    m = M(); r = _root(name, loc, rot)
    P = [bl.cyl('base', .5, .08, (0, 0, .04), m['gunmetal'], 8, bevel=.02),
         bl.torus('baseglow', .46, .015, (0, 0, .085), m['cyan'], maj=32, mn=4),
         bl.cyl('post', .13, .4, (0, 0, .3), m['steel'], 12),
         bl.box('pan', (.62, .6, .1), (0, -.02, .5), m['hull'], bevel=.03),
         bl.box('seat', (.58, .58, .1), (0, -.02, .59), m['leather'], bevel=.045, segs=3),
         bl.box('back', (.56, .12, .82), (0, .3, 1.07), m['leather'], bevel=.05, segs=3, rot=(-.14, 0, 0)),
         bl.box('backshell', (.7, .1, 1.0), (0, .4, 1.08), m['hull'], bevel=.04, rot=(-.14, 0, 0)),
         bl.box('spine', (.16, .08, .9), (0, .46, 1.08), m['gunmetal'], bevel=.02, rot=(-.14, 0, 0)),
         bl.box('headrest', (.4, .16, .22), (0, .44, 1.66), m['leather'], bevel=.05),
         bl.box('headwing', (.5, .08, .26), (0, .52, 1.66), m['hull'], bevel=.03)]
    for sx in (1, -1):
        P += [bl.box('arm', (.12, .62, .1), (sx * .38, -.04, .82), m['hull'], bevel=.035),
              bl.box('armpost', (.08, .1, .3), (sx * .38, .15, .66), m['gunmetal']),
              bl.box('armpad', (.13, .34, .04), (sx * .38, -.18, .885), m['dark'], bevel=.012),
              bl.box('trim', (.02, .02, .86), (sx * .355, .47, 1.08), m['cyan'] if sx > 0 else m['amber'], rot=(-.14, 0, 0))]
        P.append(screen('keys', .1, .28, (sx * .38, -.18, .909), tilt=R90, name='armkeys'))
    if side_screen:   # swing-arm display on the right armrest
        P += [bl.box('swing', (.04, .04, .4), (.5, -.2, 1.05), m['gunmetal']),
              bl.box('swingbezel', (.36, .03, .25), (.42, -.4, 1.3), m['dark'], bevel=.01, rot=(0, 0, .69)),
              screen('nav', .32, .21, (.408, -.386, 1.3), tilt=.1, yaw=math.pi + .69, name='swingscr')]
    _pack(r, P)
    bl.empty('IP_sit', (0, -.05, .0), r)
    return r


def holo_table(loc=(0, 0, 0), rot=0.0):
    m = M(); r = _root('ST_holotable', loc, rot)
    P = [bl.cyl('foot', 1.0, .1, (0, 0, .05), m['gunmetal'], 8, bevel=.02),
         bl.cyl('pedestal', .55, .7, (0, 0, .45), m['dark'], 8),
         bl.cyl('collar', .75, .1, (0, 0, .78), m['gunmetal'], 8, bevel=.02),
         bl.cyl('top', 1.4, .12, (0, 0, .86), m['hull'], 8, bevel=.03),
         bl.cyl('rim', 1.46, .05, (0, 0, .935), m['gunmetal'], 8),
         bl.torus('ring', 1.32, .03, (0, 0, .94), m['brass'], maj=48),
         bl.cyl('emitter', 1.05, .02, (0, 0, .935), m['screen'], 32),
         bl.torus('glowring', 1.12, .02, (0, 0, .95), m['cyan'], maj=48),
         bl.torus('baseglow', .95, .015, (0, 0, .11), m['cyan'], maj=32, mn=4)]
    for k in range(8):   # little control screens around the rim, tilted toward the user
        a = k * math.pi / 4 + math.pi / 8
        ca, sa = math.cos(a), math.sin(a)
        kind = ('graph', 'keys', 'data', 'keys')[k % 4]
        P.append(screen(kind, .42, .16, (ca * 1.22, sa * 1.22, .945), tilt=R90 - .25, yaw=a + R90, name='rimscr'))
    _pack(r, P)
    holo = bl.sphere('holo_globe', .55, (0, 0, 1.7), m['holo'], 24, 14)
    holo.parent = r
    return r


def terminal(name, loc=(0, 0, 0), rot=0.0, amber=False, kind=None):
    """Standing console (faces -Y): chamfered body, angled desk with live keys, tilted main screen."""
    m = M(); r = _root(name, loc, rot)
    kind = kind or ('amber' if amber else 'data')
    body = bl.loft('body', [[(x, y, z) for (y, z) in ((.3, 0), (.3, 1.25), (.12, 1.95), (-.05, 1.95), (-.05, 1.1), (-.2, .98), (-.2, .9), (.05, .1), (.05, 0))]
                            for x in (-.52, .52)], m['gunmetal'], smooth=False)
    P = [body,
         bl.box('kick', (1.0, .3, .1), (0, .05, .05), m['dark']),
         bl.box('desk', (1.12, .42, .05), (0, -.22, .97), m['hull'], bevel=.02, rot=(.2, 0, 0)),
         bl.box('bezel', (.98, .05, .66), (0, .115, 1.5), m['dark'], bevel=.025, rot=(-.32, 0, 0)),
         bl.box('hood', (1.06, .3, .05), (0, .02, 1.93), m['hull'], bevel=.02),
         bl.box('sidestrip', (.02, .02, .8), (.53, -.04, .5), m['amber'] if amber else m['cyan']),
         bl.box('sidestrip2', (.02, .02, .8), (-.53, -.04, .5), m['amber'] if amber else m['cyan']),
         bl.box('cable', (.08, .08, 1.0), (.35, .32, .5), m['rubber'])]
    P.append(screen(kind, .88, .54, (0, .085, 1.5), tilt=.32, name='display'))
    P.append(screen('keys', .9, .3, (0, -.225, 1.0), tilt=R90 - .2, name='keys'))
    _pack(r, P)
    return r


def armory_rack(loc=(0, 0, 0), rot=0.0):
    m = M(); r = _root('ST_armory', loc, rot)
    P = [bl.box('back', (3.4, .2, 2.6), (0, .2, 1.3), m['panel'], bevel=.03),
         bl.box('frame', (3.6, .4, .14), (0, .1, 2.66), m['gunmetal'], bevel=.03),
         bl.box('base', (3.6, .6, .3), (0, 0, .15), m['gunmetal'], bevel=.03),
         bl.box('header', (1.4, .06, .26), (0, .07, 2.4), m['dark'], bevel=.01),
         bl.box('sign', (1.2, .05, .06), (0, .05, 2.3), m['amber'])]
    P.append(screen('status', .5, .3, (1.15, .085, 2.3), name='rackscr'))
    for i in range(4):
        P.append(bl.box('hook', (3.2, .12, .04), (0, .05, .7 + i * .45), m['steel']))
    for sx in (-1.6, 1.6):
        P.append(bl.box('side', (.14, .55, 2.66), (sx, .05, 1.33), m['hull'], bevel=.035))
        P.append(bl.box('sideglow', (.02, .02, 2.2), (sx * .97, -.22, 1.3), m['cyan']))
    _pack(r, P)
    for i in range(4):
        bl.empty('SLOT_%d' % i, (-.8 + (i % 2) * 1.6, -.05, .95 + (i // 2) * .9), r)
    return r


def gunsmith_bench(loc=(0, 0, 0), rot=0.0):
    m = M(); r = _root('ST_gunsmith', loc, rot)
    P = [bl.box('top', (2.6, 1.0, .1), (0, 0, .95), m['steel'], bevel=.02),
         bl.box('drawers', (1.0, .9, .85), (.75, 0, .45), m['gunmetal'], bevel=.03),
         bl.box('legs', (.1, .9, .9), (-1.2, 0, .45), m['gunmetal']),
         bl.box('vise', (.25, .2, .18), (-.8, -.3, 1.09), m['yellow'], bevel=.02),
         bl.box('backboard', (2.6, .08, 1.3), (0, .48, 1.65), m['panel']),
         bl.box('lamp', (1.6, .2, .06), (0, .2, 2.25), m['dark']),
         bl.box('lampglow', (1.5, .14, .01), (0, .2, 2.22), bl.mat('lamp_white', '#fff6e8', 0, .4, emit='#fff6e8', strength=8)),
         bl.cyl('holopad', .35, .03, (0, -.05, 1.01), m['screen'], 24),
         bl.box('scrbezel', (.62, .04, .4), (.85, .43, 1.75), m['dark'], bevel=.01)]
    P.append(screen('graph', .56, .34, (.85, .405, 1.75), name='benchscr'))
    for i in range(6):
        P.append(bl.box('tool', (.03, .02, .25), (-1.0 + i * .18, .43, 1.75), m['steel']))
    for d in range(3):
        P.append(bl.box('drawerline', (.9, .01, .015), (.75, -.455, .2 + d * .27), m['brass']))
    _pack(r, P)
    bl.empty('DISPLAY', (0, -.05, 1.3), r)
    return r


def locker_pod(loc=(0, 0, 0), rot=0.0):
    m = M(); r = _root('ST_wardrobe', loc, rot)
    P = [bl.cyl('floor', 1.0, .15, (0, 0, .075), m['gunmetal'], 28),
         bl.cyl('ceiling', 1.0, .3, (0, 0, 2.75), m['hull'], 28),
         bl.cyl('ceilglowdisc', .8, .02, (0, 0, 2.59), bl.mat('lamp_white', '#fff6e8', 0, .4, emit='#fff6e8', strength=8), 28),
         bl.torus('floorglow', .85, .03, (0, 0, .16), m['cyan'], maj=32),
         bl.torus('ceilglow', .85, .03, (0, 0, 2.58), m['cyan'], maj=32)]
    for i in range(5):
        a = math.pi * .35 + i * math.pi * .32
        P.append(bl.box('rib', (.12, .2, 2.6), (math.cos(a) * .95, math.sin(a) * .95, 1.4), m['hull'], rot=(0, 0, a), bevel=.03))
    a = math.pi   # back rib carries a small status screen facing the open side (+X)
    P.append(screen('status', .26, .4, (math.cos(a) * .83, math.sin(a) * .83, 1.55), yaw=R90, name='podscr'))
    _pack(r, P)
    return r


def crate(name='crate', loc=(0, 0, 0), rot=0.0, size=(1.2, 1.2, 1.2), orange=False):
    m = M(); r = _root(name, loc, rot)
    mt = m['crate2'] if orange else m['crate']
    sx, sy, sz = size
    P = [bl.box('box', size, (0, 0, sz / 2), mt, bevel=.04)]
    for z in (.08, sz - .08):
        P.append(bl.box('band', (sx + .03, sy + .03, .08), (0, 0, z), m['gunmetal']))
    P.append(bl.box('label', (sx * .4, .01, sz * .2), (0, -sy / 2 - .01, sz * .6), m['hazard']))
    _pack(r, P)
    return r


def barrel(name='barrel', loc=(0, 0, 0)):
    m = M(); r = _root(name, loc)
    P = [bl.cyl('drum', .35, 1.0, (0, 0, .5), m['crate2'], 18),
         bl.torus('hoop1', .35, .025, (0, 0, .2), m['gunmetal'], maj=18, mn=5),
         bl.torus('hoop2', .35, .025, (0, 0, .8), m['gunmetal'], maj=18, mn=5),
         bl.cyl('lid', .3, .03, (0, 0, 1.01), m['gunmetal'], 18)]
    _pack(r, P)
    return r


def fuel_tank(loc=(0, 0, 0), rot=0.0):
    m = M(); r = _root('fuel_tank', loc, rot)
    P = [bl.cyl('tank', .9, 3.5, (0, 0, 1.4), m['hull'], 24, rot=(0, R90, 0)),
         bl.sphere('capL', .9, (1.75, 0, 1.4), m['hull'], 24, 12, scale=(.4, 1, 1)),
         bl.sphere('capR', .9, (-1.75, 0, 1.4), m['hull'], 24, 12, scale=(.4, 1, 1)),
         bl.box('cradle1', (.3, 1.6, .9), (1.0, 0, .45), m['gunmetal']),
         bl.box('cradle2', (.3, 1.6, .9), (-1.0, 0, .45), m['gunmetal']),
         bl.box('stripe', (3.0, .02, .2), (0, -.9, 1.4), m['hazard']),
         bl.cyl('valve', .12, .4, (0, 0, 2.4), m['brass'], 12)]
    _pack(r, P)
    return r


# ------------------------------------------------------------------ machines
def welder(loc=(0, 0, 0), rot=0.0):
    """Industrial robot arm. Children: welder_turret > welder_arm1 > welder_arm2 > welder_head > welder_tip."""
    m = M(); r = _root('MC_welder', loc, rot)
    base = _pack(r, [bl.cyl('base', .7, .35, (0, 0, .175), m['gunmetal'], 24),
                     bl.cyl('baseRing', .72, .06, (0, 0, .36), m['hazard'], 24)], 'welder_base')
    tur = bl.empty('welder_turret', (0, 0, .4), r)
    _pack(tur, [bl.cyl('turret', .5, .5, (0, 0, .25), m['yellow'], 20),
                bl.box('shoulder', (.6, .55, .5), (0, 0, .7), m['yellow'], bevel=.06)], 'welder_turret_mesh')
    a1 = bl.empty('welder_arm1', (0, 0, .75), tur)
    _pack(a1, [bl.box('link1', (.28, .3, 1.6), (0, 0, .8), m['yellow'], bevel=.05),
               bl.cyl('joint1', .25, .5, (0, 0, 0), m['gunmetal'], 16, rot=(0, R90, 0)),
               bl.box('hose1', (.06, .06, 1.4), (.18, .12, .8), m['rubber'])], 'welder_arm1_mesh')
    a2 = bl.empty('welder_arm2', (0, 0, 1.6), a1)
    _pack(a2, [bl.box('link2', (.22, .24, 1.3), (0, 0, .65), m['yellow'], bevel=.04),
               bl.cyl('joint2', .2, .42, (0, 0, 0), m['gunmetal'], 16, rot=(0, R90, 0))], 'welder_arm2_mesh')
    hd = bl.empty('welder_head', (0, 0, 1.3), a2)
    _pack(hd, [bl.cyl('wrist', .14, .3, (0, 0, .1), m['gunmetal'], 14),
               bl.cyl('torch', .05, .45, (0, 0, .45), m['brass'], 10),
               bl.cyl('nozzle', .03, .08, (0, 0, .7), m['steel'], 8)], 'welder_head_mesh')
    bl.empty('welder_tip', (0, 0, .76), hd)
    return r


def loader(loc=(0, 0, 0), rot=0.0):
    """Cargo loader mech/forklift."""
    m = M(); r = _root('MC_loader', loc, rot)
    P = [bl.box('chassis', (1.8, 2.6, .6), (0, 0, .6), m['yellow'], bevel=.08),
         bl.box('cab', (1.4, 1.2, 1.3), (0, .5, 1.55), m['glass'], bevel=.08),
         bl.box('cabframe', (1.5, 1.3, .12), (0, .5, 2.25), m['yellow'], bevel=.04),
         bl.box('mast', (1.4, .2, 2.8), (0, -1.35, 1.6), m['gunmetal']),
         bl.box('fork1', (.18, 1.3, .08), (.45, -2.0, .35), m['steel']),
         bl.box('fork2', (.18, 1.3, .08), (-.45, -2.0, .35), m['steel']),
         bl.box('warn', (.3, .3, .1), (0, .5, 2.36), m['amber'])]
    for sx in (1, -1):
        for sy in (1, -1):
            P.append(bl.cyl('wheel', .35, .3, (sx * .95, sy * .85, .35), m['rubber'], 16, rot=(0, R90, 0)))
    P.append(bl.box('stripe', (1.82, .02, .2), (0, 1.31, .6), m['hazard']))
    _pack(r, P)
    return r


def generator(loc=(0, 0, 0), rot=0.0, enemy=False):
    m = M(); r = _root('MC_generator', loc, rot)
    g = m['red'] if enemy else m['cyan']
    P = [bl.box('base', (2.2, 2.2, .4), (0, 0, .2), m['gunmetal'], bevel=.05),
         bl.cyl('core', .6, 2.0, (0, 0, 1.4), g, 16),
         bl.box('frame', (1.6, 1.6, .2), (0, 0, 2.5), m['enemy'] if enemy else m['hull'], bevel=.04)]
    for i in range(4):
        a = i * R90 + math.pi / 4
        P.append(bl.box('post', (.2, .2, 2.2), (math.cos(a) * .9, math.sin(a) * .9, 1.4), m['dark'], rot=(0, 0, a)))
    for z in (1.0, 1.6, 2.1):
        P.append(bl.torus('coil', .68, .06, (0, 0, z), m['brass'], maj=20, mn=6))
    _pack(r, P)
    return r


def turret(loc=(0, 0, 0), rot=0.0):
    """Enemy turret. Child 'turret_head' yaws, 'turret_muzzle' marks the barrel tip."""
    m = M(); r = _root('MC_turret', loc, rot)
    _pack(r, [bl.cyl('base', .8, .5, (0, 0, .25), m['enemy'], 16),
              bl.cyl('neck', .35, .8, (0, 0, .9), m['dark'], 12)], 'turret_base')
    h = bl.empty('turret_head', (0, 0, 1.3), r)
    _pack(h, [bl.box('housing', (.9, 1.1, .6), (0, 0, .2), m['enemy'], bevel=.08),
              bl.box('eye', (.5, .02, .12), (0, -.56, .3), m['red']),
              bl.cyl('barrelL', .07, .9, (.22, -.9, .15), m['dark'], 10, rot=(R90, 0, 0)),
              bl.cyl('barrelR', .07, .9, (-.22, -.9, .15), m['dark'], 10, rot=(R90, 0, 0))], 'turret_head_mesh')
    bl.empty('turret_muzzle', (0, -1.4, .15), h)
    return r


def drone(loc=(0, 0, 0)):
    """Flying enemy drone (origin at its centre). Child 'drone_rotor' spins."""
    m = M(); r = _root('MC_drone', loc, solid=False)
    _pack(r, [bl.sphere('body', .45, (0, 0, 0), m['enemy'], 16, 10, scale=(1, 1.2, .7)),
              bl.box('eye', (.32, .05, .1), (0, -.5, .02), m['red']),
              bl.box('armL', (1.2, .15, .06), (0, 0, .1), m['dark']),
              bl.cyl('gun', .05, .5, (0, -.45, -.2), m['gunmetal'], 8, rot=(R90, 0, 0)),
              bl.torus('ductL', .3, .05, (.75, 0, .12), m['enemy'], maj=16, mn=5),
              bl.torus('ductR', .3, .05, (-.75, 0, .12), m['enemy'], maj=16, mn=5),
              bl.cyl('thrL', .2, .02, (.75, 0, .05), m['red'], 12),
              bl.cyl('thrR', .2, .02, (-.75, 0, .05), m['red'], 12)], 'drone_mesh')
    return r


def loot_cache(loc=(0, 0, 0), rot=0.0):
    """Lootable chest: child 'cache_lid' opens (rotates about its hinge)."""
    m = M(); r = _root('MC_cache', loc, rot)
    _pack(r, [bl.box('chest', (1.2, .7, .5), (0, 0, .25), m['hull'], bevel=.05),
              bl.box('band', (1.24, .74, .06), (0, 0, .4), m['brass']),
              bl.box('glow', (.5, .02, .06), (0, -.36, .25), m['amber'])], 'cache_body')
    lid = bl.empty('cache_lid', (0, .35, .5), r)
    _pack(lid, [bl.box('lid', (1.2, .7, .18), (0, -.35, .09), m['hull'], bevel=.05),
                bl.box('lidglow', (.9, .5, .01), (0, -.35, .185), m['amber'])], 'cache_lid_mesh')
    return r


def barricade(loc=(0, 0, 0), rot=0.0, enemy=True):
    m = M(); r = _root('barricade', loc, rot)
    P = [bl.box('wall', (2.6, .4, 1.2), (0, 0, .6), m['enemy'] if enemy else m['hull'], bevel=.06),
         bl.box('top', (2.7, .5, .12), (0, 0, 1.22), m['dark'], bevel=.03),
         bl.box('glow', (2.0, .02, .06), (0, -.21, .9), m['red'] if enemy else m['amber'])]
    for sx in (1.1, -1.1):
        P.append(bl.box('foot', (.3, .9, .2), (sx, 0, .1), m['dark']))
    _pack(r, P)
    return r


def lamp_post(loc=(0, 0, 0), rot=0.0):
    m = M(); r = _root('lamp_post', loc, rot)
    _pack(r, [bl.cyl('pole', .1, 6.0, (0, 0, 3.0), m['gunmetal'], 10),
              bl.box('arm', (.15, 1.6, .15), (0, -.75, 5.95), m['gunmetal']),
              bl.box('head', (.4, .7, .15), (0, -1.45, 5.85), m['dark'], bevel=.04),
              bl.box('light', (.3, .55, .02), (0, -1.45, 5.77), bl.mat('street_light', '#fff1d6', 0, .4, emit='#fff1d6', strength=10)),
              bl.cyl('foot', .22, .4, (0, 0, .2), m['dark'], 10)])
    bl.empty('LIGHT', (0, -1.45, 5.6), r)
    return r


def bench(loc=(0, 0, 0), rot=0.0):
    """Crew bench, seat top at .6 m (the Sit clip's hip height). Faces -Y."""
    m = M(); r = _root('bench', loc, rot)
    pad = bl.mat('leather', '#2a2420', 0, .55)
    _pack(r, [bl.box('frame', (1.9, .55, .1), (0, 0, .49), m['gunmetal'], bevel=.02),
              bl.box('cushion', (1.84, .5, .07), (0, -.01, .57), pad, bevel=.03, segs=3),
              bl.box('back', (1.84, .08, .5), (0, .25, .9), pad, bevel=.03, segs=3),
              bl.box('backshell', (1.9, .06, .56), (0, .3, .9), m['hull'], bevel=.02),
              bl.box('legL', (.1, .45, .45), (.8, .02, .22), m['gunmetal']),
              bl.box('legR', (.1, .45, .45), (-.8, .02, .22), m['gunmetal']),
              bl.box('glow', (1.6, .02, .02), (0, -.27, .44), m['cyan'])])
    return r


def holo_sign(loc=(0, 0, 0), rot=0.0, color='#ff2fa8', w=3.0, h=1.2):
    m = M(); r = _root('holo_sign', loc, rot, solid=False)
    neon = bl.mat('sign_' + color, color, 0, .3, emit=color, strength=6)
    _pack(r, [bl.box('frame', (w + .2, .15, h + .2), (0, 0, 0), m['dark'], bevel=.03),
              bl.box('face', (w, .02, h), (0, -.08, 0), neon)])
    return r


def antenna(loc=(0, 0, 0)):
    m = M(); r = _root('antenna', loc, solid=False)
    _pack(r, [bl.cyl('mast', .08, 6, (0, 0, 3), m['steel'], 8),
              bl.sphere('blink', .15, (0, 0, 6.1), m['red'], 10, 6),
              bl.box('dish', (1.2, .1, .8), (0, 0, 4.5), m['hull'], bevel=.05, rot=(.4, 0, 0))])
    return r


def rock(name, seed, loc=(0, 0, 0), scale=(1, 1, 1)):
    """Displaced icosphere rock, origin at base. Material 'rock' is tinted per planet in-engine."""
    import random
    rnd = random.Random(seed)
    m = bl.mat('rock', '#8a847a', 0, .9, image='rock_c.jpg', normal='rock_n.jpg')
    r = _root(name, loc)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1)
    o = bpy.context.object; o.name = name + '_mesh'
    tex = bpy.data.textures.new('rk%d' % seed, 'VORONOI'); tex.noise_scale = .6 + rnd.random() * .5
    md = o.modifiers.new('d', 'DISPLACE'); md.texture = tex; md.strength = .35 + rnd.random() * .25
    tex2 = bpy.data.textures.new('rn%d' % seed, 'CLOUDS'); tex2.noise_scale = .4
    md2 = o.modifiers.new('d2', 'DISPLACE'); md2.texture = tex2; md2.strength = .25
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    for mm in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=mm.name)
    o.scale = (scale[0], scale[1], scale[2] * (.55 + rnd.random() * .4))
    o.rotation_euler = (rnd.random() * .3, rnd.random() * .3, rnd.random() * 6.28)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    mn = min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        v.co.z -= mn + .15
    o.select_set(False)
    o.data.materials.append(m)
    bl.uv_box(o, 2.5)
    bpy.ops.object.shade_flat()
    o.parent = r
    return r


def crystal(name, seed, color='#9b5cff'):
    import random
    rnd = random.Random(seed)
    m = bl.mat('crystal_' + color, color, .1, .1, emit=color, strength=1.6)
    r = _root(name, solid=False)
    P = []
    for i in range(5 + rnd.randint(0, 4)):
        h = 1.0 + rnd.random() * 2.5
        c = bl.cyl('c', .15 + rnd.random() * .2, h, (0, 0, h / 2), m, 6, r2=.0)
        c.rotation_euler = (rnd.uniform(-.5, .5), rnd.uniform(-.5, .5), rnd.random() * 6)
        c.location = (rnd.uniform(-.5, .5), rnd.uniform(-.5, .5), 0)
        P.append(c)
    _pack(r, P)
    return r


def alien_plant(name, seed, stem='#3d6b3a', glow='#7dffb0'):
    import random
    rnd = random.Random(seed)
    sm = bl.mat('plant_stem', stem, 0, .7)
    gm = bl.mat('plant_glow_' + glow, glow, 0, .4, emit=glow, strength=3)
    r = _root(name, solid=False)
    P = []
    for i in range(3 + rnd.randint(0, 3)):
        h = 1.2 + rnd.random() * 2.2
        a = rnd.random() * 6.28; d = rnd.random() * .5
        x, y = math.cos(a) * d, math.sin(a) * d
        st = bl.cyl('stem', .06, h, (x, y, h / 2), sm, 6, r2=.03)
        st.rotation_euler = (rnd.uniform(-.25, .25), rnd.uniform(-.25, .25), 0)
        P.append(st)
        P.append(bl.sphere('bulb', .2 + rnd.random() * .15, (x, y, h), gm, 8, 6, scale=(1, 1, 1.4)))
    for i in range(4):
        a = i * R90 + rnd.random()
        P.append(bl.box('leaf', (.8, .25, .03), (math.cos(a) * .45, math.sin(a) * .45, .15), sm, rot=(0, .3, a)))
    _pack(r, P)
    return r


def data_core(name='PR_core'):
    """Loot data core: faceted crystal in a brass cage. Material 'core_glow' is tinted by rarity in-engine."""
    m = M(); r = _root(name, solid=False)
    glow = bl.mat('core_glow', '#ffffff', 0, .2, emit='#ffffff', strength=4)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.22)
    c = bpy.context.object; c.scale = (1, 1, 1.5); c = bl._finish(c, glow, 'core')
    P = [c, bl.torus('cage1', .26, .015, (0, 0, 0), m['brass'], rot=(R90, 0, 0), maj=16, mn=4),
         bl.torus('cage2', .26, .015, (0, 0, 0), m['brass'], rot=(R90, 0, R90), maj=16, mn=4)]
    _pack(r, P)
    return r


def ammo_box(name='PR_ammo'):
    m = M(); r = _root(name, solid=False)
    _pack(r, [bl.box('case', (.42, .26, .22), (0, 0, .11), m['gunmetal'], bevel=.02),
              bl.box('lid', (.44, .28, .05), (0, 0, .24), m['hull'], bevel=.015),
              bl.box('stripe', (.43, .27, .04), (0, 0, .12), bl.mat('ammo_glow', '#ffffff', 0, .4, emit='#ffffff', strength=3))])
    return r
