// VANTHOS, the Fallen Metropolis: a dead city, years after its people. A ruined circle around the Spire: most of the
// skyline has come down into rubble mounds and debris fields, the few buildings still standing are gutted, sheared and
// leaning (ruins.js, designs from tools/blender/ruins.py), nature is taking the streets back (trees from trees.glb via
// meridian/flora.js, weeds, moss, vines) and the creatures already live here: residents sleep, feed, perch, patrol and
// roam through the streets and halls (districts.js), streamed in around the player and throttled when far.
// Districts are independent modules placed by the city plan (map.js); the ground is textured (ground.js); a hazy, dim
// dusk with drifting ash and a procedural soundscape (ambience.js); the metro below (metro.js); the linear operation
// "Heartline" runs from the landing zone to the Spire (operation.js).
import * as THREE from 'three';
import { World } from '../world.js';
import { atmosphereSky } from '../sky.js';
import { mulberry } from '../../game/state.js';
import { VanthosMap, CROWN_R, OUTER_R, SPIRE_R, CRATER_R, HIGHWAYS, MAJOR, STREET, BW, BD, WATER_Y } from './map.js';
import { DISTRICTS } from './districts.js';
import { Water } from '../../game/water.js';
import { Operation } from './operation.js';
import { Ruins } from './ruins.js';
import { Ground } from './ground.js';
import { Flora } from '../meridian/flora.js';
import { VanthosAmbience } from './ambience.js';

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3();
const Y = new THREE.Vector3(0, 1, 0);
const STREAM_IN = 230, STREAM_OUT = 340, SPAWN_PER_FRAME = 3;
const FOG = '#4f4b45', FOG_NEAR = 16, FOG_FAR = 520;
// what grows back: young birch and ash, scrub, autumn-sick maples; willows where the water stands
const GROW = { tree: ['TR_birch_a', 'TR_birch_b', 'TR_birch_c', 'TR_ash_young', 'TR_ash_young', 'TR_understory_a', 'TR_understory_b', 'TR_maple_autumn_b', 'TR_ash_b'],
  bush: ['TR_bush_a', 'TR_bush_b', 'TR_understory_b'], water: ['TR_willow_a', 'TR_willow_b'] };
// operation arenas are kept clear of standing ruins (their anchors, see operation.js)
const polar = (deg, r) => [Math.cos(deg * Math.PI / 180) * r, Math.sin(deg * Math.PI / 180) * r];
const ARENAS = [polar(103, 1478), polar(105.8, 990), polar(110, 572), [0, 100]];

// one InstancedMesh per kit mesh, for all placements of a kit root
function instanceKit(scene, root, mats, shadow = true) {
  if (!mats.length) return;
  root.updateMatrixWorld(true);
  const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
  root.traverse(o => {
    if (!o.isMesh) return;
    const local = new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld);
    const im = new THREE.InstancedMesh(o.geometry, o.material, mats.length);
    mats.forEach((pm, i) => im.setMatrixAt(i, _m.multiplyMatrices(pm, local)));
    im.castShadow = shadow; im.receiveShadow = true; im.geometry.userData.shared = true;
    im.computeBoundingSphere();
    scene.add(im);
  });
}

export class VanthosWorld extends World {
  constructor(game, dest) {
    super(game);
    this.dest = dest; this.kind = 'metropolis'; this.name = dest.region; this.region = dest.name;
    this.combat = true; this.allowCars = true; this.surface = 'metal';
    this.level = dest.level; this.destPower = dest.power;
    this.map = new VanthosMap(dest.seed || 4401);
    this.baseHeight = this.map.height.bind(this.map);
    this.sites = []; this.caches = []; this.lights = []; this.triggers = []; this.shards = []; this.lifts = [];
    this.kitMats = new Map(); this.kitInfo = new Map(); this.spawnQ = [];
    this.event = null;
    const sv = game.save; sv.vanthos = { shards: [], bosses: [], runs: 0, best: null, logs: [], ...(sv.vanthos || {}) };
  }

  levelAt(x, z, D) {
    const r = Math.hypot(x, z);
    return this.level + Math.floor((1 - Math.min(1, r / 1800)) * 9) + ((D && D.danger) || 0);
  }

  height(x, z) { return this.map.height(x, z); }
  // ground while the city is being laid out (rubble mounds placed so far included, the flood floor clamped)
  groundBase(x, z) { return Math.max(this.baseHeight(x, z), this.ruins ? this.ruins.moundAt(x, z) : -99, -2.4); }

  async build(progress) {
    const g = this.g, A = g.assets, sc = this.scene, map = this.map;
    const tick = async (f, l) => { progress(f, l); await new Promise(r => setTimeout(r, 0)); };
    await A.loadAll(Ground.jobs(), (p, l) => progress(p * .06, l));
    this.collision.terrain = (x, z) => map.height(x, z);
    // ---------------- an overcast dusk over a dead city: low, weak sun, ash haze, everything far melts into it
    this.sunDir = new THREE.Vector3(-.52, .2, -.83).normalize();
    const sky = atmosphereSky('#2f3236', '#5a564e', '#7d6d58', this.sunDir, { fog: FOG }); sc.add(sky); this.sky = sky;
    sky.material.uniforms.cloudC.value.set(.55, .55, .56);
    sc.fog = new THREE.Fog(new THREE.Color(FOG), FOG_NEAR, FOG_FAR); this.fogBase = [FOG_NEAR, FOG_FAR];
    sc.add(new THREE.HemisphereLight(0x7c8088, 0x231f1a, .7));
    const sun = new THREE.DirectionalLight(0xb5a68c, 1.25);
    sun.castShadow = true; const q = g.renderer.q; sun.shadow.mapSize.set(q.shadow, q.shadow);
    Object.assign(sun.shadow.camera, { left: -70, right: 70, top: 70, bottom: -70, near: 10, far: 500 });
    sun.shadow.bias = -.0005; sun.shadow.normalBias = .08;
    sc.add(sun, sun.target); this.sun = sun;
    await tick(.08, 'Mapping the ruins');
    await Water.load(A);
    this.ground = new Ground(this).materials();
    this.buildTerrain();
    await tick(.14, 'Tracing the dead streets');
    this.buildRoads();
    this.buildHighways();
    const kit = A.models.vanthos.scene;
    this.ruins = new Ruins(this);
    this.styleKit(kit);
    await tick(.2, 'Raising the Spire');
    this.buildSpire();
    for (const [x, z, rot, bus] of this.hwyWrecks || []) this.ruins.place(bus ? 'VR_bus_burnt' : Math.random() < .5 ? 'VR_car_burnt' : 'VR_car_rust', x, z, rot);
    // ---------------- districts (independent modules)
    for (const n of ['VX_ind_factory', 'VX_ind_refinery', 'VX_ind_power', 'VX_mil_bunker', 'VX_mil_tower', 'VX_mil_depot',
      'VX_lab_a', 'VX_lab_containment', 'VX_hospital', 'VX_organism']) {
      const root = kit.getObjectByName(n); root.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(root), c = root.getWorldPosition(new THREE.Vector3());
      this.kitInfo.set(n, { root, size: box.getSize(new THREE.Vector3()), off: box.getCenter(new THREE.Vector3()).sub(c) });
      this.kitMats.set(n, []);
    }
    this.flora = new Flora(g, sc, A.models.trees);
    let di = 0;
    for (const D of DISTRICTS) {
      await tick(.26 + di++ * .065, 'Walking ' + D.name);
      D.populate.call(D, this.context(D));
    }
    for (const [n, mats] of this.kitMats) instanceKit(sc, this.kitInfo.get(n).root, mats);
    await tick(.8, 'Letting the weeds back in');
    this.overgrow();
    this.ruins.finish();
    this.flora.build();
    // from here on the height function includes the rubble mounds (the terrain mesh was built from the bare ground)
    map.height = (x, z) => Math.max(this.baseHeight(x, z), this.ruins.moundAt(x, z));
    await tick(.86, 'Charting the districts');
    this.minimap = this.drawMinimap();
    // landing site: the jumpship on the southern highway, in the Outskirts
    const a = HIGHWAYS[0], r = 1720, lx = Math.cos(a) * r + 30, lz = Math.sin(a) * r;
    const ly = map.height(lx, lz);
    const js = A.clone('ship_jumper'); js.position.set(lx, ly, lz); js.rotation.y = -a + Math.PI / 2; sc.add(js);
    for (let t = -6; t <= 6; t += 3) this.collision.add([lx - 2, ly, lz - 2 + t, lx + 2, ly + 4, lz + 2 + t], 'ship');
    this.landing = new THREE.Vector3(lx - 12, ly, lz);
    this.interactables.push({ id: 'ship', pos: this.landing, r: 3.5, label: 'The Wayfarer', verb: 'Return to orbit', key: 'E', action: () => g.travel('ship') });
    // a fair start: nothing lives right at the landing zone
    for (const st of this.sites) if (Math.hypot(st.pos.x - lx, st.pos.z - lz) < 110) st.off = true;
    // the mission: Operation Heartline (operation.js) runs from the landing zone to the Spire on every visit
    await tick(.9, 'Briefing the operation');
    this.op = new Operation(this); this.op.build();
    // a pool of point lights shared by every district (nearest ones are switched on)
    this.lightPool = [];
    for (let i = 0; i < 5; i++) { const L = new THREE.PointLight(0xffffff, 0, 40, 1.6); sc.add(L); this.lightPool.push(L); }
    // reflections: the dim sky
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    this.envRT = pm.fromScene(new THREE.Scene().add(atmosphereSky('#2f3236', '#5a564e', '#7d6d58', this.sunDir, { fog: FOG, ground: '#1c1a17', groundK: .8 })), .04);
    sc.environment = this.envRT.texture; sc.environmentIntensity = .45;
    pm.dispose(); this.disposables.push(this.envRT);
    this.buildAsh();
    this.buildShafts();
    this.ambience = new VanthosAmbience(this);
    g.vehicles.clear();
    this.warmTextures();
    progress(1, 'Ready');
  }

  // the old kit (landmarks, the Spire, the metro pieces): no lit windows, no neon, darker and dirtier
  styleKit(kit) {
    const R = this.ruins, find = n => { let m = null; this.g.assets.models.vanthos_ruins.scene.traverse(o => { if (o.isMesh) for (const x of [].concat(o.material)) if (x.name === n) m = x; }); return m; };
    const conc = find('vr_conc'), frame = find('vr_frame');
    const rep = (t, k) => { if (!t) return null; const c = t.clone(); c.repeat.set(k, k); c.wrapS = c.wrapT = THREE.RepeatWrapping; c.needsUpdate = true; return c; };
    const fac = conc && { map: rep(conc.map, 1.7), normalMap: rep(conc.normalMap, 1.7) }, rib = frame && { map: rep(frame.map, 2), normalMap: rep(frame.normalMap, 2) };
    this.pulseMats = [];
    kit.traverse(o => {
      if (!o.isMesh) return;
      for (const m of [].concat(o.material)) {
        if (m.userData.styled) continue; m.userData.styled = true;
        const n = m.name;
        if ((n === 'facade' && fac) || (n === 'ribbon' && rib)) {
          const S = n === 'facade' ? fac : rib;
          m.map = S.map; m.normalMap = S.normalMap; m.emissiveMap = null; m.emissive.setRGB(0, 0, 0); m.emissiveIntensity = 0;
          m.color.set(n === 'facade' ? 0x9a948c : 0x8a8884); m.roughness = .9; m.metalness = n === 'ribbon' ? .3 : 0;
        } else if (/^neon_|^holo_ad/.test(n)) { m.emissive.setRGB(0, 0, 0); m.emissiveIntensity = 0; m.color.set(0x1d1e20); }
        else if (/^(concrete|vx_concrete_dark|vx_panel|roof|vx_lab_white|vx_rust|darkmetal|steel|hazard)$/.test(n)) { m.color.multiplyScalar(.55); m.envMapIntensity = .4; }
        else if (n === 'core_glow') { m.emissive.set(0xa01428); m.color.set(0x400810); }
        else if (/^(roof_green|roof_leaves)$/.test(n)) m.color.multiplyScalar(.6);
        else if (/glass/.test(n)) { m.color.set(0x1a1e20); m.opacity = Math.min(m.opacity, .45); }
        if (/alien_glow|alien_acid/.test(n)) this.pulseMats.push({ m, base: m.emissiveIntensity || 1, ph: Math.random() * 6 });
        m.needsUpdate = true;
      }
    });
  }

  // ---------------------------------------------------------------- district context (the API districts build with)
  context(D) {
    const g = this.g, A = g.assets, map = this.map, sc = this.scene;
    const rnd = mulberry(D.id.split('').reduce((a, c) => a * 31 + c.charCodeAt(0), 7) >>> 0);
    // the operation's arenas keep their lots empty
    const lots = map.lots.filter(l => l.district === D && !ARENAS.some(([x, z]) => Math.hypot(l.x - x, l.z - z) < 48));
    for (let i = lots.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [lots[i], lots[j]] = [lots[j], lots[i]]; }
    const blocks = map.blocks.filter(b => b.district === D);
    const self = this;
    const groundAt = (x, z) => this.groundBase(x, z);
    const STANDING = new Set(['tower', 'mid', 'low', 'hall', 'stub', 'rubble']);
    const ctx = {
      rnd,
      takeLot(pred) { const i = pred ? lots.findIndex(pred) : 0; if (i < 0 || !lots.length) return null; return lots.splice(i, 1)[0]; },
      half: (name, rot) => self.ruins.half(name, rot),
      building(kit, x, z, rot, fit) {
        const K = self.kitInfo.get(kit); if (!K) return null;
        const sw = Math.abs(Math.cos(rot)) > .5 ? K.size.x : K.size.z, sd = Math.abs(Math.cos(rot)) > .5 ? K.size.z : K.size.x;
        const s = fit ? Math.min(1, fit / Math.max(sw, sd)) : 1;
        const y = Math.min(self.baseHeight(x, z), 0);
        self.kitMats.get(kit).push(new THREE.Matrix4().compose(_p.set(x, y, z), _q.setFromAxisAngle(Y, rot), _s.set(s, s, s)));
        const h = K.size.y * s;
        self.collision.add([x - sw * s / 2, y - 3, z - sd * s / 2, x + sw * s / 2, y + h, z + sd * s / 2], 'building');
        // rubble and growth gather around what is still standing
        if (rnd() < .7) self.ruins.place('VR_debris', x + sw * s * .6, z + (rnd() - .5) * sd * s, rnd() * 6, { collide: false });
        return { h: y + h, top: y + h, x, z, w: sw * s, d: sd * s };
      },
      ruin(name, x, z, rot, o = {}) {
        const M = self.ruins.meta(name); if (!M) return null;
        if (o.y === undefined && STANDING.has(M.kind)) o = { ...o, y: Math.max(self.baseHeight(x, z), -2.4) };
        return self.ruins.place(name, x, z, rot, o);
      },
      tree(kind, x, z, scale = 1) {
        const pool = GROW[kind] || [kind], name = pool[Math.floor(rnd() * pool.length)];
        const y = groundAt(x, z);
        if (self.map.flooded(x, z) > .3 && kind !== 'water' && rnd() < .7) return ctx.tree('water', x, z, scale);
        const v = self.flora.add(name, x, y - .2, z, rnd, scale * (.75 + rnd() * .5), { collide: false });
        if (v && kind !== 'bush' && !/bush|understory_b/.test(v)) self.collision.add([x - .3, y - 1, z - .3, x + .3, y + 5, z + .3], 'tree');
        return v;
      },
      prop(kit, x, z, rot, o = {}) {
        const obj = A.clone('vanthos', kit); if (!obj) return null;
        obj.position.set(x, o.y !== undefined ? o.y : groundAt(x, z), z); obj.rotation.y = rot || 0;
        if (o.scale) obj.scale.setScalar(o.scale);
        obj.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
        sc.add(obj);
        if (o.solid) self.collision.addObject(obj, 'prop', .15);
        return obj;
      },
      pack(types, x, z, n, o = {}) { self.sites.push({ D, types, pos: new THREE.Vector3(x, groundAt(x, z), z), n, o, live: [], cleared: false, spawned: false }); },
      resident(types, x, z, n, beh, o = {}) {
        const pos = new THREE.Vector3(x, o.y !== undefined ? o.y : groundAt(x, z), z);
        let route = null;
        if (beh === 'patrol' || beh === 'roam') {
          route = [pos.clone()];
          const want = beh === 'roam' ? 4 : 3, far = beh === 'roam' ? 420 : 120;
          for (let k = 0; k < 30 && route.length < want; k++) { const s = ctx.street(); if (Math.hypot(s.x - x, s.z - z) < far && Math.hypot(s.x - x, s.z - z) > 25) route.push(new THREE.Vector3(s.x, 0, s.z)); }
          if (route.length < 2) { route = null; beh = 'wander'; }
        }
        self.sites.push({ D, types, pos, n, o: { ...o, beh, route, res: true }, live: [], cleared: false, spawned: false });
      },
      cache(x, z, tier, label) { self.makeCache(x, groundAt(x, z), z, tier, label || ['', 'Supply cache', 'Sealed locker', 'Secure vault', 'Armoury crate'][tier]); },
      lift(x, z, top) { self.makeLift(x, z, top); },
      metro(x, z) { self.makeMetro(x, groundAt(x, z), z, D); },
      light(x, y, z, color, intensity = 3, flicker = false) { self.lights.push({ pos: new THREE.Vector3(x, groundAt(x, z) + y, z), color: new THREE.Color(color), intensity, flicker }); },
      trigger(x, z, r, fn) { self.triggers.push({ x, z, r, fn, done: false }); },
      boss(type, x, y, z, name, hpMul, scale) {
        if (g.save.vanthos.bosses.includes(name)) return;
        self.sites.push({ D, types: [type], pos: new THREE.Vector3(x, y || groundAt(x, z), z), n: 1, o: { boss: { name, hpMul, scale } }, live: [], cleared: false, spawned: false });
      },
      shard(x, z) { self.makeShard(x, groundAt(x, z), z); },
      street() {
        const b = blocks[Math.floor(rnd() * blocks.length)] || { x: 0, z: 0 };
        const side = Math.floor(rnd() * 4);
        const along = (rnd() - .5) * .8;
        if (side < 2) return { x: b.x + (side ? 1 : -1) * (BW / 2 + STREET / 2), z: b.z + along * BD, rot: 0 };
        return { x: b.x + along * BW, z: b.z + (side === 3 ? 1 : -1) * (BD / 2 + STREET / 2), rot: Math.PI / 2 };
      },
      spots: kind => self.ruins.spots[kind] || [],
      horror(x, z) { self.horrorT = 70; g.hud.toast('The emergency lights flicker. Something is moving inside.'); g.audio.alert && g.audio.alert(new THREE.Vector3(x, 1, z)); },
    };
    return ctx;
  }

  // weeds through the kerbs and lots, trees on the ruins' rubble and roofs, the odd dead lamp
  overgrow() {
    const rnd = mulberry(913), R = this.ruins, map = this.map;
    for (const b of map.blocks) {
      // along the kerb of the block (the sidewalk edge) and scattered inside
      for (let k = 0; k < 26; k++) {
        const side = k % 4, t = rnd() - .5;
        let x, z;
        if (side < 2) { x = b.x + (side ? 1 : -1) * (BW / 2 - .6 - rnd() * 1.5); z = b.z + t * BD; }
        else { x = b.x + t * BW; z = b.z + (side === 3 ? 1 : -1) * (BD / 2 - .6 - rnd() * 1.5); }
        if (map.flooded(x, z) > .4) continue;
        R.place(rnd() < .65 ? 'VR_weeds_a' : 'VR_weeds_b', x, z, rnd() * 6.28, { collide: false, scale: .7 + rnd() * .6 });
      }
      for (let k = 0; k < 8; k++) {
        const x = b.x + (rnd() - .5) * BW * .9, z = b.z + (rnd() - .5) * BD * .9;
        if (map.flooded(x, z) > .4) continue;
        R.place(rnd() < .5 ? 'VR_weeds_a' : 'VR_weeds_b', x, z, rnd() * 6.28, { collide: false, scale: .8 + rnd() * .6 });
      }
    }
    for (const p of R.spots.tree) if (rnd() < .6) this.flora.add(GROW.tree[Math.floor(rnd() * GROW.tree.length)], p.x, p.y - .15, p.z, rnd, .55 + rnd() * .45, { collide: false });
    // rare dead lamps that still sputter
    for (const p of R.spots.glow) if (rnd() < .25) this.lights.push({ pos: p.clone(), color: new THREE.Color(0xff3a20), intensity: 1.2, flicker: true, dead: true });
  }

  // ---------------------------------------------------------------- terrain, roads, highways
  buildTerrain() {
    const sc = this.scene, map = this.map;
    const S = 4800, N = 300;
    const geo = new THREE.PlaneGeometry(S, S, N, N); geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position, uv = geo.attributes.uv;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), z = pos.getZ(i);
      pos.setY(i, this.baseHeight(x, z) - (Math.hypot(x, z) < map.edge(Math.atan2(z, x)) - 60 ? .06 : 0));
      uv.setXY(i, x / 6, z / 6);
    }
    geo.setAttribute('aL', new THREE.Float32BufferAttribute(new Float32Array(pos.count * 3), 3));
    geo.computeVertexNormals();
    const t = new THREE.Mesh(geo, this.ground.terrainMaterial(CRATER_R, SPIRE_R)); t.receiveShadow = true; sc.add(t); this.terrain = t;
    // flood water over the sunken district
    const D = DISTRICTS.find(d => d.id === 'flooded');
    const wgeo = new THREE.RingGeometry(CROWN_R - 10, OUTER_R + 10, 64, 1, -D.a1 * Math.PI / 180, (D.a1 - D.a0) * Math.PI / 180);
    wgeo.rotateX(-Math.PI / 2);
    // shared water surface (src/game/water.js): murky, still flood water with ripples and splashes
    const arc = []; for (let k = 0; k <= 12; k++) { const a = (D.a0 + (D.a1 - D.a0) * k / 12) * Math.PI / 180; for (const R of [CROWN_R - 12, OUTER_R + 12]) arc.push([Math.cos(a) * R, Math.sin(a) * R]); }
    const bounds = [Math.min(...arc.map(a => a[0])), Math.min(...arc.map(a => a[1])), Math.max(...arc.map(a => a[0])), Math.max(...arc.map(a => a[1]))];
    this.water = new Water(this.g, sc, { level: WATER_Y, ground: (x, z) => map.height(x, z), inside: (x, z) => map.flooded(x, z) > .02, bounds, res: 320,
      deep: 0x070c0a, shallow: 0x232a20, foamColor: 0xa8a598, caps: 0, swell: .18, clarity: 1.0, sunDir: this.sunDir, sunColor: 0xb5a68c, vfxLight: 0x9a958c });
    this.water.addSurface(wgeo);
    // world edge walls in the badlands
    for (let k = 0; k < 24; k++) {
      const a = k / 24 * Math.PI * 2, R = 2380;
      const x = Math.cos(a) * R, z = Math.sin(a) * R;
      this.collision.add([x - 340, -50, z - 340, x + 340, 300, z + 340], 'edge');
    }
  }

  buildRoads() {
    const sc = this.scene, map = this.map, G = this.ground;
    const hf = (x, z) => Math.max(this.baseHeight(x, z), -2.35) + .05;
    // the street grid of every district: the east and north street of each block (west / south where no neighbour)
    const acc = Ground.acc(), key = b => b.district.id + ':' + b.gx + ',' + b.gz, have = new Set(map.blocks.map(key));
    const seg = (x0, z0, x1, z1) => { const L = Math.hypot(x1 - x0, z1 - z0), n = Math.max(2, Math.ceil(L / 12)), pts = []; for (let i = 0; i <= n; i++) pts.push([x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * i / n]); Ground.ribbon(acc, pts, STREET, hf); };
    for (const b of map.blocks) {
      const ex = BW / 2 + STREET / 2, ez = BD / 2 + STREET / 2, nb = (dx, dz) => have.has(b.district.id + ':' + (b.gx + dx) + ',' + (b.gz + dz));
      seg(b.x + ex, b.z - ez - STREET / 2, b.x + ex, b.z + ez - STREET / 2);
      seg(b.x - ex - STREET / 2, b.z + ez, b.x + ex - STREET / 2, b.z + ez);
      if (!nb(-1, 0)) seg(b.x - ex, b.z - ez - STREET / 2, b.x - ex, b.z + ez - STREET / 2);
      if (!nb(0, -1)) seg(b.x - ex - STREET / 2, b.z - ez, b.x + ex - STREET / 2, b.z - ez);
    }
    const streets = Ground.mesh(acc, G.street); sc.add(streets);
    // the two ring roads
    const ring = Ground.acc();
    for (const R of [CROWN_R, OUTER_R]) {
      const pts = []; for (let k = 0; k <= 400; k++) { const a = k / 400 * Math.PI * 2; pts.push([Math.cos(a) * R, Math.sin(a) * R]); }
      Ground.ribbon(ring, pts, MAJOR, hf, true);
    }
    sc.add(Ground.mesh(ring, G.wide));
    // block slabs: a broken sidewalk band around a lot of soil, rubble dust and grass, kerbs down to the street
    const P = [], U = [], L = [], I = [], hw = BW / 2, hd = BD / 2, K = .16;
    for (const b of map.blocks) {
      const y = Math.max(this.baseHeight(b.x, b.z), -2.38) + K, y0 = y - K - .3, o = P.length / 3;
      const N = 4;
      for (let j = 0; j <= N; j++) for (let i = 0; i <= N; i++) {
        const lx = -hw + i / N * BW, lz = -hd + j / N * BD, x = b.x + lx, z = b.z + lz;
        P.push(x, y, z); U.push(x / 4, z / 4); L.push(lx, lz, 0);
      }
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) { const a = o + j * (N + 1) + i; I.push(a, a + N + 1, a + 1, a + 1, a + N + 1, a + N + 2); }
      // kerb faces
      const C = [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]];
      for (let k = 0; k < 4; k++) {
        const [ax, az] = C[k], [bx, bz] = C[(k + 1) % 4], q = P.length / 3;
        for (const [lx, lz, yy] of [[ax, az, y], [bx, bz, y], [bx, bz, y0], [ax, az, y0]]) { P.push(b.x + lx, yy, b.z + lz); U.push((b.x + lx + b.z + lz) / 4, yy / 4); L.push(lx, lz, 0); }
        I.push(q, q + 2, q + 1, q, q + 3, q + 2);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); geo.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2));
    geo.setAttribute('aL', new THREE.Float32BufferAttribute(L, 3)); geo.setIndex(I); geo.computeVertexNormals();
    const pads = new THREE.Mesh(geo, G.blockMaterial(hw, hd)); pads.receiveShadow = true; sc.add(pads);
    for (const b of map.blocks) this.collision.add([b.x - hw, -3, b.z - hd, b.x + hw, Math.max(this.baseHeight(b.x, b.z), -2.38) + K, b.z + hd], 'kerb');
  }

  buildHighways() {
    const sc = this.scene, map = this.map, A = this.g.assets;
    const kit = A.models.vanthos.scene;
    const segs = [], broken = [], H = 12;
    const E0 = 700, E1 = 1320;                   // elevated between these radii
    const acc = Ground.acc();
    for (const [hi, a] of HIGHWAYS.entries()) {
      const dx = Math.cos(a), dz = Math.sin(a);
      const gapR = 960 + hi * 70;
      // ground ribbon (with the ramps) from the Crown out to the badlands, split at the collapsed section
      let run = [];
      for (let r = 130; r <= 2300; r += 10) {
        let y = Math.max(this.baseHeight(dx * r, dz * r), -2.35) + .06;
        if (r > E0 - 90 && r < E1 + 90) {
          const t = r < E0 ? (r - (E0 - 90)) / 90 : r > E1 ? ((E1 + 90) - r) / 90 : 1;
          y = Math.max(y, H * Math.min(1, Math.max(0, t)));
        }
        if (Math.abs(r - gapR) <= 25) { if (run.length > 1) Ground.ribbon(acc, run, MAJOR, (x, z, p) => p[2]); run = []; continue; }
        run.push([dx * r, dz * r, y]);
      }
      if (run.length > 1) Ground.ribbon(acc, run, MAJOR, (x, z, p) => p[2]);
      // pillars, barriers and broken section from the kit; walkable colliders along the deck and ramps
      const rot = Math.atan2(-dx, -dz), nx = -dz, nz = dx;
      for (let r = E0 + 25; r < E1; r += 50) {
        const M = new THREE.Matrix4().compose(_p.set(dx * r, 0, dz * r), _q.setFromAxisAngle(Y, rot), _s.set(1, 1, 1));
        if (Math.abs(r - gapR) < 26) broken.push(M); else segs.push(M);
      }
      for (let r = E0 - 90; r <= E1 + 90; r += (r < E0 || r > E1) ? 1.5 : 6) {
        if (Math.abs(r - gapR) < 25) continue;
        const t = r < E0 ? (r - (E0 - 90)) / 90 : r > E1 ? ((E1 + 90) - r) / 90 : 1, y = H * Math.min(1, Math.max(0, t));
        if (y < .35) continue;
        for (const s2 of [-6.5, 6.5]) { const x = dx * r + nx * s2, z = dz * r + nz * s2; this.collision.add([x - 6, y - 1.4, z - 6, x + 6, y, z + 6], 'deck'); }
      }
      // abandoned traffic on the dead highway
      const rnd = mulberry(hi * 77 + 5);
      for (let k = 0; k < 26; k++) {
        const r = 1380 + rnd() * 880, s = (rnd() - .5) * 18, x = dx * r + nx * s, z = dz * r + nz * s;
        (this.hwyWrecks = this.hwyWrecks || []).push([x, z, rot + (rnd() - .5) * .8 + (rnd() < .5 ? Math.PI : 0), rnd() < .12]);
      }
    }
    const m = Ground.mesh(acc, this.ground.wide); m.castShadow = true; sc.add(m);
    instanceKit(sc, kit.getObjectByName('VX_hwy'), segs);
    instanceKit(sc, kit.getObjectByName('VX_hwy_broken'), broken);
  }

  buildSpire() {
    const g = this.g, A = g.assets, sc = this.scene;
    const sp = A.clone('vanthos', 'VX_spire'); sc.add(sp); this.spire = sp;
    // the Spire looms through the haze from anywhere in the city: its materials see a thinner fog
    const done = new Map();
    sp.traverse(o => {
      if (!o.isMesh) return;
      o.castShadow = true; o.receiveShadow = true;
      o.material = [].concat(o.material).map(m0 => {
        if (done.has(m0)) return done.get(m0);
        const m = m0.clone();
        if (m.name === 'core_glow') this.coreMat = m;
        m.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace('#include <fog_fragment>', `#ifdef USE_FOG
          float fogFactor = smoothstep( fogNear, fogFar * 5.5, vFogDepth ) * .92;
          gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );
          #endif`); };
        m.customProgramCacheKey = () => 'spirefog';
        done.set(m0, m); return m;
      });
      if (o.material.length === 1) o.material = o.material[0];
    });
    // foundation: a walkable disc, its cap 29 m up (VX_spire foundcap); towers as solid boxes
    for (let x = -88; x <= 88; x += 22) for (let z = -88; z <= 88; z += 22) if (Math.hypot(x, z) < 86) this.collision.add([x - 11, -2, z - 11, x + 11, 29, z + 11], 'spire');
    for (let k = 0; k < 48; k++) { const a = k / 48 * Math.PI * 2, x = Math.cos(a) * 81, z = Math.sin(a) * 81; this.collision.add([x - 6, -2, z - 6, x + 6, 29, z + 6], 'spire'); }
    const towers = [[0, 240], [1.26, 290], [2.51, 300 * .62], [3.77, 260], [5.03, 230 * .62]];
    for (const [a, h] of towers) { const x = Math.cos(a) * 52, z = -Math.sin(a) * 52; this.collision.add([x - 19, 28, z - 19, x + 19, 28 + h, z + 19], 'spire'); }
    this.collision.add([-25, 28, -25, 25, 360, 25], 'spire');
    // the core: a slow, sick red heartbeat high in the haze
    this.coreLight = new THREE.PointLight(0xff3424, 3000, 700, 1.4); this.coreLight.position.set(0, 380, 0); sc.add(this.coreLight);
    // the lift up to the foundation (powered during the operation); the Spire Warden and its reliquary are operation.js
    const lift = this.makeLift(0, 100, 29, 0, 76);
    this.spireLiftBase = lift.base;
    this.spireLift = new THREE.Vector3(0, 0, 100); this.spireLift.y = this.baseHeight(0, 100);
  }

  // drifting ash: a box of slow flakes around the camera (VFX)
  buildAsh() {
    const n = this.g.renderer.touch ? 500 : 900, pos = new Float32Array(n * 3), S = 60;
    for (let i = 0; i < n; i++) { pos[i * 3] = (Math.random() - .5) * S; pos[i * 3 + 1] = Math.random() * 30; pos[i * 3 + 2] = (Math.random() - .5) * S; }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.ShaderMaterial({
      uniforms: { uT: { value: 0 }, uC: { value: new THREE.Vector3() }, uS: { value: S } }, transparent: true, depthWrite: false,
      vertexShader: `uniform float uT, uS; uniform vec3 uC; varying float vA;
        void main(){ vec3 p = position; p.y = mod(p.y - uT * (.45 + fract(position.x * 7.1) * .35), 30.);
          p.x += sin(uT * .3 + position.z) * 2. + uT * .8; p.z += cos(uT * .23 + position.x) * 2. + uT * .3;
          vec3 w = vec3(uC.x + mod(p.x - uC.x + uS * .5, uS) - uS * .5, uC.y - 8. + p.y, uC.z + mod(p.z - uC.z + uS * .5, uS) - uS * .5);
          vec4 mv = viewMatrix * vec4(w, 1.); gl_Position = projectionMatrix * mv;
          float d = -mv.z; vA = smoothstep(1., 4., d) * (1. - smoothstep(18., 30., d));
          gl_PointSize = clamp(220. / d, 1., 5.); }`,
      fragmentShader: `varying float vA; void main(){ vec2 c = gl_PointCoord - .5; float a = smoothstep(.5, .1, length(c)) * vA * .55; gl_FragColor = vec4(vec3(.62, .6, .57), a); }`,
    });
    const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; pts.renderOrder = 4;
    this.scene.add(pts); this.ash = pts; this.disposables.push(geo, mat);
  }

  // light shafts falling through the broken roofs of the halls (additive VFX cards, faded by distance and view angle)
  buildShafts() {
    const halls = this.ruins.designs.get('VR_hall'); if (!halls || !halls.list.length) return;
    const L = 15, D = this.sunDir.clone().negate();
    const local = [[7, 13.5, -4], [12, 13, 3], [16, 12.5, -2], [4, 13.8, 5]];
    const pos = [], uv = [], idx = [];
    const side = new THREE.Vector3().crossVectors(D, Y).normalize(), up2 = new THREE.Vector3().crossVectors(side, D).normalize();
    for (const m of halls.list) {
      const e = m.elements;
      for (const [lx, ly, lz] of local) {
        const top = new THREE.Vector3(lx, ly, lz).applyMatrix4(m), bot = top.clone().addScaledVector(D, L);
        for (const ax of [side, up2]) {
          const o = pos.length / 3;
          for (const [p, w, v] of [[top, 1.4, 0], [bot, 2.6, 1]]) for (const s2 of [-1, 1]) { const q = p.clone().addScaledVector(ax, s2 * w); pos.push(q.x, q.y, q.z); uv.push(s2 < 0 ? 0 : 1, v); }
          idx.push(o, o + 1, o + 2, o + 1, o + 3, o + 2);
        }
      }
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); geo.setIndex(idx);
    const mat = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false,
      uniforms: { uT: { value: 0 } },
      vertexShader: `varying vec2 vUv; varying float vD; void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.); vD = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform float uT; varying vec2 vUv; varying float vD;
        void main(){ float a = sin(vUv.x * 3.14159) ; a *= a; a *= (1. - vUv.y) * smoothstep(0., .15, vUv.y + .02);
          a *= smoothstep(2., 8., vD) * (1. - smoothstep(60., 110., vD));
          a *= .75 + .25 * sin(uT * .6 + vUv.y * 4.);
          gl_FragColor = vec4(vec3(.62, .58, .5) * a * .22, 1.); }` });
    const mesh = new THREE.Mesh(geo, mat); mesh.renderOrder = 3; this.scene.add(mesh); this.shafts = mesh; this.disposables.push(geo, mat);
  }

  // ---------------------------------------------------------------- interactables
  makeLift(x, z, top, rx = x - 6, rz = z) {
    const g = this.g, A = g.assets, sc = this.scene;
    const y0 = Math.max(this.baseHeight(x, z), -2.4);
    const base = A.clone('vanthos', 'VX_lift'); base.position.set(x, y0, z); sc.add(base);
    const roof = A.clone('vanthos', 'VX_lift'); roof.position.set(rx, top, rz); sc.add(roof);
    const up = new THREE.Vector3(rx, top + .2, rz), down = new THREE.Vector3(x + 2, y0, z);
    const b = { id: 'lift', pos: base.position, r: 2.4, label: 'Lift', verb: 'Ride to the roof', key: 'E', action: () => this.teleport(up) };
    const r = { id: 'lift', pos: roof.position, r: 2.4, label: 'Lift', verb: 'Ride down', key: 'E', action: () => this.teleport(down) };
    this.interactables.push(b, r);
    this.lifts.push({ base: base.position, roof: roof.position });
    return { base: b, roof: r };
  }

  teleport(p) {
    const g = this.g;
    g.player.pos.copy(p); g.player.vel.set(0, 0, 0); g.player.avatar.root.position.copy(p); g.player.snapCamera = true;
    g.audio.ui('confirm'); g.fx.emit(p.clone().setY(p.y + 1), 30, 3, 0x40e0ff, .6, 3, .06);
  }

  makeMetro(x, y, z, D) {
    const g = this.g, A = g.assets;
    const e = A.clone('vanthos', 'VX_metro_entrance'); e.position.set(x, y, z); this.scene.add(e);
    const seed = Math.abs(Math.round(x * 13 + z * 7)) % 100000;
    const it = { id: 'metro', pos: e.position, r: 3, label: 'Metro entrance', verb: 'Descend into the metro', key: 'E',
      action: () => { g.metroEntry = { x: x + 6, y, z, district: D.id, seed, level: this.levelAt(x, z, D) }; g.travel('vanthos_metro'); } };
    this.interactables.push(it);
    this.metros = this.metros || []; this.metros.push(e.position);
  }

  makeCache(x, y, z, tier, label, unlocked = null) {
    const g = this.g, A = g.assets;
    const c = A.clone('props_world', 'PR_cache'); c.position.set(x, y, z); c.rotation.y = Math.random() * 6; this.scene.add(c);
    this.collision.addObject(c, 'cache');
    const cache = { obj: c, lid: c.getObjectByName('cache_lid'), open: false, pos: c.position.clone(), t: 0, tier, label };
    cache.it = { id: 'cache', pos: c.position, r: 2.2, label, key: 'E',
      get verb() { return unlocked && !unlocked() ? 'Sealed · defeat the guardian' : 'Open'; },
      enabled: () => !cache.open, action: () => { if (unlocked && !unlocked()) { g.audio.ui('deny'); return; } this.openCache(cache); } };
    this.interactables.push(cache.it); this.caches.push(cache);
  }

  openCache(cache) {
    const g = this.g;
    cache.open = true; g.save.stats.caches++; g.contractEvent('caches', 1); g.audio.ui('open');
    const lvl = this.levelAt(cache.pos.x, cache.pos.z);
    const rarity = Math.min(4, Math.max(1, cache.tier - 1 + (Math.random() < .25 ? 1 : 0)));
    for (let k = 0; k < (cache.tier >= 3 ? 2 : 1); k++) g.combat.spawnPickup(cache.pos.clone().setY(cache.pos.y + .6), 'core', { rarity, level: lvl });
    g.combat.spawnPickup(cache.pos.clone().setY(cache.pos.y + .6), 'ammo');
    g.combat.spawnPickup(cache.pos.clone().setY(cache.pos.y + .6), 'ammo');
    g.gain('credits', 40 * cache.tier + lvl * 5, false); g.gain('xp', 60 * cache.tier);
    g.fx.emit(cache.pos.clone().setY(cache.pos.y + .8), 40, 4, 0xffae2f, .8, 3, .08);
  }

  makeShard(x, y, z) {
    const id = Math.round(x) + ',' + Math.round(z);
    if (this.g.save.vanthos.shards.includes(id)) return;
    const s = this.g.assets.clone('props_world', 'PR_core'); s.position.set(x, Math.max(y, -2.4) + .6, z); s.scale.setScalar(.8);
    s.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); if (o.material.emissive) o.material.emissive.set(0x3ae6ff); } });
    this.scene.add(s); this.shards.push({ id, obj: s, pos: s.position });
  }

  // ---------------------------------------------------------------- the living (and the dead) of the city
  // A site's creatures are queued and spawned a few per frame (no hitch when a district streams in). Residents carry a
  // behaviour (sleep / feed / perch / patrol / roam / wander); roaming packs share one route and leader.
  spawnSite(st, now = false) {
    st.spawned = true; st.live = []; st.group = [];
    st.lvl = this.levelAt(st.pos.x, st.pos.z, st.D);
    st.pack = st.o.beh === 'roam' && st.o.route ? { pts: st.o.route, i: 1, lead: null } : null;
    for (let k = 0; k < st.n; k++) {
      if (now) this.spawnOne(st, k); else this.spawnQ.push([st, k]);
    }
  }

  spawnOne(st, k) {
    const g = this.g, o = st.o;
    if (!st.spawned) return null;
    const type = st.types[k % st.types.length];
    const a = k / st.n * Math.PI * 2 + (st.pos.x % 1), sp = o.spread !== undefined ? o.spread : 3 + (k % 3) * 1.6, r = st.n > 1 ? sp * (.5 + Math.random() * .5) : 0;
    const p = st.pos.clone().add(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r));
    if (o.y !== undefined) p.y = Math.max(o.y, this.collision.support ? this.collision.support(p.x, p.z, o.y + 1) : o.y);
    else if (st.pos.y < 20) p.y = Math.max(this.map.height(p.x, p.z), -2.4);
    const beh = type === 'turret' ? null : o.beh;
    const opts = { group: st.group, onDeath: e => this.onSiteDeath(st, e), beh, face: Math.random() * 6.28 };
    if (beh === 'patrol') opts.route = o.route;
    if (st.pack) { opts.pack = st.pack; opts.packOff = new THREE.Vector3(Math.cos(a) * 3, 0, Math.sin(a) * 3); opts.beh = 'roam'; }
    if (o.armed && type === 'host') opts.gun = Math.random() < .5 ? 'gun_pulse' : 'gun_auto';
    const e = g.enemies.spawn(type, p, st.lvl, opts);
    if (o.boss) {
      const B = o.boss; e.T = { ...e.T, name: B.name, scale: (e.T.scale || 1) * B.scale, loot: 1 };
      e.maxHp = e.hp = Math.round(e.maxHp * B.hpMul); e.boss = B.name;
      if (e.av) e.av.root.scale.setScalar(B.scale);
    }
    if (o.op) e.op = true;
    if (o.awake) e.state = 'combat';
    if (o.ambush && e.av) e.ambush = true;
    st.group.push(e); st.live.push(e);
    return e;
  }

  onSiteDeath(st, e) {
    const g = this.g;
    if (e.boss) {
      g.save.vanthos.bosses.push(e.boss);
      g.hud.banner(e.boss + ' defeated', 'Its vault is open', 4);
      g.gain('xp', 1500); g.gain('credits', 900, true);
      g.combat.spawnPickup(e.pos.clone().setY(e.pos.y + 1), 'core', { rarity: 4, level: e.level });
    }
    if (st.live.length >= st.n && st.live.every(x => !x.alive)) st.cleared = true;
  }

  stream() {
    const p = this.g.player.pos;
    for (const st of this.sites) {
      if (st.cleared || st.off) continue;           // `off`: kept clear (the landing zone, the operation's own spots)
      const d = Math.hypot(st.pos.x - p.x, st.pos.z - p.z);
      if (!st.spawned && d < STREAM_IN) this.spawnSite(st);
      else if (st.spawned && d > STREAM_OUT && !st.o.keep) {
        const set = new Set(st.live);
        this.g.enemies.removeWhere(e => set.has(e) && e.state !== 'combat');
        st.live = st.live.filter(e => e.alive && this.g.enemies.list.includes(e));
        this.spawnQ = this.spawnQ.filter(q => q[0] !== st);
        if (!st.live.length) st.spawned = false;
      }
    }
  }

  onGunshot(pos) { this.g.enemies.noise && this.g.enemies.noise(pos, 55); }

  onFoundation() { const p = this.g.player.pos; return p.y > 20 && Math.hypot(p.x, p.z) < 97; }

  // leaving for the metro keeps the operation's stage (the city is rebuilt on the way back up)
  depart(id) { if (id === 'vanthos_metro' && this.op && !this.op.complete) this.g.opResume = this.op.snapshot(); }

  barTargets() { return this.op ? this.op.barTargets() : []; }

  // ---------------------------------------------------------------- per frame
  update(dt) {
    const g = this.g, p = g.player;
    if (!this.musicSet) { this.musicSet = true; g.audio.musicKind = null; g.audio.music('dread'); }
    if (this.water) this.water.update(dt);
    this.sky.position.copy(g.camera.position);
    this.sky.material.uniforms.time.value = g.time;
    const c = p.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : p.pos;
    this.sun.target.position.set(Math.round(c.x / 4) * 4, c.y, Math.round(c.z / 4) * 4);
    this.sun.position.copy(this.sun.target.position).addScaledVector(this.sunDir, 260);
    if (this.ruins) this.ruins.update(g.camera, dt);
    if (this.flora) this.flora.update(g.camera, dt);
    if (this.shafts) this.shafts.material.uniforms.uT.value = g.time;
    if (this.ash) { const u = this.ash.material.uniforms; u.uT.value = g.time; u.uC.value.copy(g.camera.position); }
    if (this.ambience) this.ambience.update(dt);
    // district: HUD name, faction wars, danger
    const D = this.map.district(c.x, c.z);
    if (D !== this.D) {
      this.D = D; g.hud.setLocation(this.region, D.name);
      g.hud.toast(D.name + ' — ' + D.blurb);
    }
    this.factionWar = !!D.factionWar;
    // stream residents every few frames, spawn the queue a few per frame
    this.streamT = (this.streamT || 0) - dt;
    if (this.streamT <= 0) { this.streamT = .5; this.stream(); }
    for (let k = 0; k < SPAWN_PER_FRAME && this.spawnQ.length; k++) { const [st, i] = this.spawnQ.shift(); this.spawnOne(st, i); }
    if (this.op) { this.op.update(dt); g.hud.bossBar(this.op.bossBar()); }
    // ambushers stay still and hidden until the player is close
    for (const e of g.enemies.list) if (e.ambush && e.state === 'idle' && e.alive && e.pos.distanceTo(p.pos) < 16) { e.ambush = false; e.alert(); g.hud.toast('Ambush!'); }
    // the nearest district lights take the pooled point lights
    this.lightT = (this.lightT || 0) - dt;
    if (this.lightT <= 0) { this.lightT = .4; this.near = this.lights.map(L => [L, L.pos.distanceToSquared(p.pos)]).filter(x => x[1] < 140 * 140).sort((a, b) => a[1] - b[1]).slice(0, this.lightPool.length).map(x => x[0]); }
    (this.near || []).forEach((L, i) => {
      const P = this.lightPool[i]; P.position.copy(L.pos); P.color.copy(L.color);
      const fl = L.dead ? (Math.sin(g.time * 29 + i) > .6 && Math.sin(g.time * .7 + i * 3) > .3 ? 1 : .04) : L.flicker ? (Math.sin(g.time * 23 + i) > .2 ? 1 : .15) : 1;
      P.intensity = L.intensity * 60 * fl;
    });
    for (let i = (this.near || []).length; i < this.lightPool.length; i++) this.lightPool[i].intensity = 0;
    // triggers (the hospital, ...)
    for (const t of this.triggers) if (!t.done && Math.hypot(t.x - p.pos.x, t.z - p.pos.z) < t.r) { t.done = true; t.fn(); }
    // horror: fog closes in, then lifts
    if (this.horrorT > 0) { this.horrorT -= dt; const k = Math.min(1, this.horrorT / 5, (70 - this.horrorT) / 3); this.scene.fog.near = this.fogBase[0] * (1 - k) + 4 * k; this.scene.fog.far = this.fogBase[1] * (1 - k) + 60 * k; }
    // shards
    for (let i = this.shards.length - 1; i >= 0; i--) {
      const s = this.shards[i]; s.obj.rotation.y += dt * 1.5; s.obj.position.y = s.pos.y + Math.sin(g.time * 2 + i) * .15;
      if (s.obj.position.distanceTo(p.pos) < 1.8) {
        g.save.vanthos.shards.push(s.id); s.obj.removeFromParent(); this.shards.splice(i, 1);
        g.audio.ui('confirm'); g.hud.feed('Memory shard ' + g.save.vanthos.shards.length + ' / 12', '#3ae6ff'); g.gain('xp', 120);
      }
    }
    // caches
    for (const cc of this.caches) if (cc.open && cc.lid && cc.t < 1) { cc.t = Math.min(1, cc.t + dt * 2); cc.lid.rotation.x = -cc.t * 1.9; }
    // alien growth breathes; the core beats, slow and wrong
    for (const P of this.pulseMats) P.m.emissiveIntensity = P.base * (.7 + .3 * Math.sin(g.time * 2.2 + P.ph));
    const beat = Math.max(0, Math.sin(g.time * 1.1)) ** 6 + Math.max(0, Math.sin(g.time * 1.1 - .5)) ** 10 * .6;
    this.coreLight.intensity = 1800 + 2600 * beat;
    if (this.coreMat) this.coreMat.emissiveIntensity = .5 + 1.6 * beat;
  }

  spawn() {
    const g = this.g;
    if (g.metroReturn) { const r = g.metroReturn; g.metroReturn = null; return { pos: new THREE.Vector3(r.x, Math.max(this.map.height(r.x, r.z), r.y), r.z), yaw: 0 }; }
    // revival: the operation's last checkpoint (short of the current arena)
    const cp = this.op && this.op.spawnPoint();
    if (cp) return { pos: cp, yaw: Math.atan2(-cp.x, -cp.z) };
    return { pos: this.landing.clone(), yaw: Math.atan2(-this.landing.x, -this.landing.z) };
  }

  markers() {
    const p = this.g.player.pos, m = [{ pos: new THREE.Vector3(0, 0, 0), icon: '◆', color: '#ff4a5a' }, { pos: this.landing, icon: '▲', color: '#1ad8ff' }];
    if (this.op) m.push(...this.op.markers());
    for (const q of this.metros || []) if (q.distanceTo(p) < 260) m.push({ pos: q, icon: 'M', color: '#e3c26c' });
    for (const c of this.caches) if (!c.open && c.pos.distanceTo(p) < 140) m.push({ pos: c.pos, icon: '◆', color: '#ffae2f' });
    return m;
  }

  objectives() {
    const g = this.g, p = g.player.pos, D = this.D || DISTRICTS[0];
    return [...(this.op ? this.op.objectives() : []),
      { text: D.name, sub: 'Threat level ' + this.levelAt(p.x, p.z, D) + (D.factionWar ? ' · creatures at war' : '') },
      { text: 'Memory shards', sub: g.save.vanthos.shards.length + ' / 12 · hidden in the Flooded District' }];
  }

  drawMinimap() {
    const S = 600, W = 4800, half = W / 2, c = document.createElement('canvas'); c.width = c.height = S;
    const x = c.getContext('2d'), map = this.map;
    const toPx = (wx, wz) => [(wx + half) / W * S, (wz + half) / W * S];
    x.fillStyle = '#2a2622'; x.fillRect(0, 0, S, S);
    const cols = { crown: '#4a4a4e', old: '#4e463e', commercial: '#40464e', flooded: '#22343a', research: '#46504e', military: '#3e4238', industrial: '#4a423a', outskirts: '#3a3632' };
    for (let j = 0; j < S; j += 3) for (let i = 0; i < S; i += 3) {
      const wx = -half + i / S * W, wz = -half + j / S * W, r = Math.hypot(wx, wz);
      if (r > map.edge(Math.atan2(wz, wx)) - 40) continue;
      x.fillStyle = r < CRATER_R ? '#1e161a' : (cols[map.district(wx, wz).id] || '#444'); x.fillRect(i, j, 3, 3);
    }
    x.fillStyle = 'rgba(170,160,150,.4)';
    for (const b of map.blocks) { const [a, bb] = toPx(b.x - BW / 2, b.z - BD / 2); x.fillRect(a, bb, BW / W * S, BD / W * S); }
    x.strokeStyle = '#141210'; x.lineWidth = MAJOR / W * S;
    for (const R of [CROWN_R, OUTER_R]) { x.beginPath(); x.arc(S / 2, S / 2, R / W * S, 0, 7); x.stroke(); }
    for (const a of HIGHWAYS) { const [a1, b1] = toPx(Math.cos(a) * 130, Math.sin(a) * 130), [a2, b2] = toPx(Math.cos(a) * 2300, Math.sin(a) * 2300); x.beginPath(); x.moveTo(a1, b1); x.lineTo(a2, b2); x.stroke(); }
    x.fillStyle = '#ff4a5a'; x.beginPath(); x.arc(S / 2, S / 2, 5, 0, 7); x.fill();
    return { canvas: c, scale: S / W, half };
  }

  // tests / debugging
  stats() {
    const res = this.sites.filter(s => s.o.res), live = this.g.enemies.list.filter(e => e.alive);
    return { ruins: this.ruins.stats(), sites: this.sites.length, residents: res.reduce((n, s) => n + s.n, 0), residentSites: res.length,
      alive: live.length, asleep: this.g.enemies.asleep || 0, trees: this.flora ? this.flora.count : 0, queue: this.spawnQ.length };
  }

  dispose() {
    const h = this.g.hud; h.bossBar(null); h.clearRadio(); h.hideLore();
    this.ambience && this.ambience.dispose();
    this.op && this.op.dispose(); this.water && this.water.dispose(); super.dispose();
  }
}
