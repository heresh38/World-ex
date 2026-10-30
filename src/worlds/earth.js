// Earth — New Meridian City. Grid city built from the Blender building kit with instancing,
// skyway traffic, pedestrians, the spaceport (Quartermaster + your jumpship) and an incursion district.
import * as THREE from 'three';
import { World } from './world.js';
import { atmosphereSky } from './sky.js';
import { mulberry } from '../game/state.js';
import { Avatar } from '../game/avatar.js';

const BLOCK = 92, ROAD = 18, N = 4;              // blocks from -N..N
const PITCH = BLOCK + ROAD;
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), _v = new THREE.Vector3();

export class EarthWorld extends World {
  constructor(game) {
    super(game);
    this.kind = 'city'; this.name = 'New Meridian City'; this.region = 'Earth';
    this.combat = true; this.allowCars = true; this.surface = 'concrete';
    this.level = 2; this.destPower = 0;
  }

  async build(progress) {
    const g = this.g, A = g.assets, sc = this.scene, rnd = mulberry(4242);
    const T = A.textures;
    progress(.05, 'Plotting streets');
    // ---------------- lighting: late golden hour
    this.sunDir = new THREE.Vector3(-.55, .32, -.45).normalize();
    const sky = atmosphereSky('#3a6aa8', '#f2b27a', '#ffd9a8', this.sunDir); sc.add(sky); this.sky = sky;
    sc.fog = new THREE.Fog(0xd9a07a, 120, 900);
    sc.add(new THREE.HemisphereLight(0x9cb8e0, 0x5a4636, .9));
    const sun = new THREE.DirectionalLight(0xffd2a0, 3.0);
    sun.castShadow = true;
    const q = g.renderer.q; sun.shadow.mapSize.set(q.shadow, q.shadow);
    Object.assign(sun.shadow.camera, { left: -70, right: 70, top: 70, bottom: -70, near: 10, far: 500 });
    sun.shadow.bias = -.0004; sun.shadow.normalBias = .06;
    sc.add(sun, sun.target); this.sun = sun;
    // ---------------- ground: concrete everywhere, asphalt road strips
    const ext = (N + 1.5) * PITCH * 2;
    const conc = T.concrete.clone(); conc.repeat.set(ext / 6, ext / 6); conc.needsUpdate = true;
    const concN = T.concrete_n.clone(); concN.repeat.copy(conc.repeat); concN.needsUpdate = true;
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(ext * 1.6, ext * 1.6), new THREE.MeshStandardMaterial({ map: conc, normalMap: concN, roughness: .9, color: 0xbab2a6 }));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; sc.add(ground);
    const asph = T.asphalt.clone(); asph.repeat.set(ext / 10, ROAD / 10); asph.needsUpdate = true;
    const asphN = T.asphalt_n.clone(); asphN.repeat.copy(asph.repeat); asphN.needsUpdate = true;
    const roadMat = new THREE.MeshStandardMaterial({ map: asph, normalMap: asphN, roughness: .8, color: 0x9a9aa0, envMapIntensity: .4 });
    const lineMat = new THREE.MeshStandardMaterial({ color: 0xe8e2d0, roughness: .6 });
    const dashGeo = new THREE.PlaneGeometry(.3, 4); dashGeo.rotateX(-Math.PI / 2);
    const dashes = [];
    for (let i = -N - 1; i <= N; i++) {
      const c = (i + .5) * PITCH;
      for (const ax of [0, 1]) {
        const r = new THREE.Mesh(new THREE.PlaneGeometry(ext, ROAD), roadMat);
        r.rotation.x = -Math.PI / 2; if (ax) r.rotation.z = Math.PI / 2;
        r.position.set(ax ? c : 0, .02, ax ? 0 : c); r.receiveShadow = true; sc.add(r);
        for (let t = -ext / 2; t < ext / 2; t += 10) dashes.push(ax ? [c, t] : [t, c, 1]);
      }
    }
    const dm = new THREE.InstancedMesh(dashGeo, lineMat, dashes.length);
    dashes.forEach((d, i) => { _m.makeRotationY(d[2] ? Math.PI / 2 : 0); _m.setPosition(d[0], .035, d[1]); dm.setMatrixAt(i, _m); });
    dm.receiveShadow = true; sc.add(dm);
    progress(.2, 'Raising towers');
    // ---------------- buildings (instanced per variant per primitive)
    const kit = A.models.city_buildings.scene;
    const variants = [];
    for (let i = 0; i < 8; i++) {
      const root = kit.getObjectByName('BLD_' + i);
      const meshes = []; root.traverse(o => { if (o.isMesh) meshes.push(o); });
      root.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(root);
      const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
      variants.push({ meshes, inv, size: box.getSize(new THREE.Vector3()), placements: [] });
    }
    // facade emissive windows
    const facadeE = T.facade_e, ribbonE = T.ribbon_e;
    for (const v of variants) for (const m of v.meshes) {
      const mt = m.material;
      if (mt.name === 'facade') { mt.color.set(0x8f969f); mt.roughness = .35; mt.metalness = .5; mt.emissiveMap = facadeE; mt.emissive = new THREE.Color(1, .85, .6); mt.emissiveIntensity = .9; mt.needsUpdate = true; }
      if (mt.name === 'ribbon') { mt.color.set(0x9aa1aa); mt.roughness = .3; mt.metalness = .45; mt.emissiveMap = ribbonE; mt.emissive = new THREE.Color(1, .9, .75); mt.emissiveIntensity = .9; mt.needsUpdate = true; }
    }
    const lots = [];
    const incursion = { bx: N - 1, bz: -N + 1 };   // north-east district
    this.incursionCenter = new THREE.Vector3(incursion.bx * PITCH, 0, incursion.bz * PITCH);
    for (let bx = -N; bx <= N; bx++) for (let bz = -N; bz <= N; bz++) {
      const cx = bx * PITCH, cz = bz * PITCH;
      if (bx === 0 && bz === 0) continue;             // spaceport plaza
      if (bx === incursion.bx && bz === incursion.bz) continue; // open combat yard
      if ((bx === 1 && bz === 0) || (bx === 0 && bz === 1)) { lots.push({ x: cx, z: cz, v: 6, rot: rnd() < .5 ? 0 : Math.PI, park: true }); continue; }
      const edge = Math.max(Math.abs(bx), Math.abs(bz));
      for (const [ox, oz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
        if (rnd() < .12 && edge > 1) continue;  // occasional plaza / gap
        let v;
        const r = rnd();
        if (edge <= 1) v = [0, 5, 1, 2, 7][Math.floor(r * 5)]; else v = [3, 4, 7, 6, 1, 2, 0][Math.floor(r * 7)];
        if (v === 5 && lots.some(l => l.v === 5)) v = 0;
        lots.push({ x: cx + ox * BLOCK / 4, z: cz + oz * BLOCK / 4, v, rot: Math.floor(rnd() * 4) * Math.PI / 2 });
      }
    }
    const lotSize = BLOCK / 2 - 4;
    for (const L of lots) {
      const v = variants[L.v];
      const sw = L.rot % Math.PI ? v.size.z : v.size.x, sd = L.rot % Math.PI ? v.size.x : v.size.z;
      const big = L.park ? BLOCK - 10 : lotSize;
      const sc2 = Math.min(1, big / Math.max(sw, sd)) * (L.park ? 1 : .92 + rnd() * .08);
      const hs = L.park ? 1 : .85 + rnd() * .4;
      _q.setFromAxisAngle(_v.set(0, 1, 0), L.rot); _s.set(sc2, sc2 * hs, sc2);
      const mat = new THREE.Matrix4().compose(_p.set(L.x, 0, L.z), _q, _s);
      v.placements.push(mat);
      // collider (exact AABB for right-angle rotations)
      const hx = sw * sc2 / 2, hz = sd * sc2 / 2, hy = v.size.y * sc2 * hs;
      this.collision.add([L.x - hx, 0, L.z - hz, L.x + hx, hy, L.z + hz], 'building');
    }
    for (const v of variants) {
      if (!v.placements.length) continue;
      for (const m of v.meshes) {
        const local = new THREE.Matrix4().multiplyMatrices(v.inv, m.matrixWorld);
        const im = new THREE.InstancedMesh(m.geometry, m.material, v.placements.length);
        v.placements.forEach((pm, i) => im.setMatrixAt(i, _m.multiplyMatrices(pm, local)));
        im.castShadow = true; im.receiveShadow = true; im.computeBoundingSphere();
        im.geometry.userData.shared = true;
        sc.add(im);
      }
    }
    progress(.45, 'Lighting the streets');
    // ---------------- street props: lamps along every road, benches near the port
    const propKit = A.models.props_world.scene;
    const instanceProp = (name, mats) => {
      const root = propKit.getObjectByName(name); root.updateMatrixWorld(true);
      const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
      root.traverse(o => {
        if (!o.isMesh) return;
        const local = new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld);
        const im = new THREE.InstancedMesh(o.geometry, o.material, mats.length);
        mats.forEach((pm, i) => im.setMatrixAt(i, _m.multiplyMatrices(pm, local)));
        im.castShadow = !/light/.test(o.material.name); im.receiveShadow = true; im.computeBoundingSphere();
        im.geometry.userData.shared = true;
        sc.add(im);
      });
    };
    const lampM = [];
    for (let i = -N - 1; i <= N; i++) {
      const c = (i + .5) * PITCH;
      for (let t = -N * PITCH; t <= N * PITCH; t += 34) {
        for (const side of [-1, 1]) {
          const off = c + side * (ROAD / 2 + 1.2);
          lampM.push(new THREE.Matrix4().compose(_p.set(off, 0, t + 11), _q.setFromAxisAngle(_v.set(0, 1, 0), side > 0 ? -Math.PI / 2 : Math.PI / 2), _s.set(1, 1, 1)));
          lampM.push(new THREE.Matrix4().compose(_p.set(t + 11, 0, off), _q.setFromAxisAngle(_v.set(0, 1, 0), side > 0 ? Math.PI : 0), _s.set(1, 1, 1)));
        }
      }
    }
    instanceProp('PR_lamp', lampM);
    const benchM = [];
    for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2 + .3; benchM.push(new THREE.Matrix4().compose(_p.set(Math.cos(a) * 33, 0, Math.sin(a) * 33), _q.setFromAxisAngle(_v.set(0, 1, 0), -a + Math.PI / 2), _s.set(1, 1, 1))); }
    instanceProp('PR_bench', benchM);
    // ---------------- spaceport with the player's jumpship
    const port = A.clone('city_buildings', 'BLD_port'); sc.add(port);
    port.traverse(o => { if (o.isMesh) { o.receiveShadow = true; } });
    this.collision.add([-20, 0, -20, 20, 1.2, 20], 'port');
    // the access ramp (south side) as shallow steps the capsule can climb
    for (let i = 0; i < 6; i++) this.collision.add([-5, 0, 20 + i * 2.6, 5, 1.2 - (i + 1) * .2, 22.6 + i * 2.6], 'ramp');
    const js = A.clone('ship_jumper'); js.position.set(0, 1.2, 4); js.rotation.y = Math.PI; sc.add(js); this.jumpship = js;
    this.collision.add([-2.4, 1.2, -4, 2.4, 5, 12], 'ship');
    this.collision.add([-8.6, 2.0, -1.5, 8.6, 2.6, 4], 'ship');
    const ramp = new THREE.Vector3(0, 1.2, 12.5);   // rear ramp (the ship's nose points north)
    this.interactables.push({ id: 'ship', pos: ramp, r: 3.2, label: 'The Wayfarer', verb: 'Return to orbit', key: 'E', action: () => g.travel('ship') });
    // Quartermaster vendor
    const qm = new Avatar(A, 'npc_vendor'); qm.root.position.set(9, 1.2, -9); qm.root.rotation.y = -Math.PI * .75; qm.play('IdleRelaxed', 0);
    sc.add(qm.root); this.vendor = qm;
    this.collision.add([8.5, 1.2, -9.5, 9.5, 3, -8.5], 'npc');
    const term = A.clone('props_world', 'PR_terminal'); term.position.set(10.2, 1.2, -10.2); term.rotation.y = -Math.PI * .75; sc.add(term);
    this.interactables.push({ id: 'vendor', pos: new THREE.Vector3(8, 1.2, -8), r: 2.4, label: 'Quartermaster Okafor', verb: 'Trade', key: 'E', action: () => g.station('vendor') });
    // neon signs on the shop blocks around the plaza
    for (const [x, z, r, n] of [[PITCH - 20, -12, Math.PI / 2, 'PR_sign_magenta'], [12, PITCH - 20, 0, 'PR_sign_cyan'], [-PITCH + 28, 8, -Math.PI / 2, 'PR_sign_cyan']]) {
      const s = A.clone('props_world', n); s.position.set(x, 9, z); s.rotation.y = r; s.scale.setScalar(2.2); sc.add(s);
    }
    progress(.6, 'Waking the city');
    // ---------------- skyway traffic (flying lanes above the roads)
    this.traffic = [];
    const models = ['car_sport', 'car_utility'], paints = ['#a3121f', '#2a4f7a', '#e8e2d4', '#1c1f24', '#c79a45', '#2f6b55', '#6a4fa0'];
    for (let k = 0; k < 16; k++) {
      const c = A.clone(models[k % 2]);
      c.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); if (o.material.name === 'car_paint') o.material.color.set(paints[k % paints.length]); o.castShadow = false; } });
      const axis = k % 2, lane = (Math.floor(rnd() * (2 * N + 2)) - N - 1 + .5) * PITCH, dir = rnd() < .5 ? 1 : -1;
      const alt = 9 + (k % 4) * 5;
      sc.add(c);
      this.traffic.push({ obj: c, axis, lane: lane + dir * 3, dir, t: (rnd() - .5) * ext, speed: 18 + rnd() * 14, alt });
    }
    // parked cars by the plaza the player can take
    g.vehicles.clear();
    g.vehicles.spawn('car_sport', g.save.car.paint, new THREE.Vector3(26, 0, 30), 0);
    g.vehicles.spawn('car_utility', '#2a4f7a', new THREE.Vector3(-26, 0, 30), Math.PI);
    // ---------------- pedestrians
    this.peds = [];
    const pedCols = [['#2a4a6a', '#c79a45'], ['#6a2a2a', '#e8e2d4'], ['#2f6b55', '#3a3f47'], ['#e8e2d4', '#1b2440'], ['#7a3f22', '#c79a45'], ['#3a3f47', '#ff2fa8']];
    for (let k = 0; k < 10; k++) {
      const av = new Avatar(A, k % 2 ? 'player_female' : 'npc_vendor');
      av.recolor({ primary: pedCols[k % 6][0], secondary: pedCols[k % 6][1], glow: ['#7dffb0', '#ffae2f', '#1ad8ff'][k % 3] });
      av.root.scale.setScalar(.97 + rnd() * .06);
      const ring = 28 + (k % 3) * 2.5, a0 = rnd() * Math.PI * 2, dir = k % 2 ? 1 : -1;
      sc.add(av.root);
      this.peds.push({ av, ring, a: a0, dir, speed: (1.1 + rnd() * .4) / ring });
    }
    progress(.75, 'Tracking the incursion');
    // ---------------- incursion district: barricades + raider squads
    this.squadT = 0; this.cleared = 0; this.incursionAlive = 0;
    const ic = this.incursionCenter;
    for (let k = 0; k < 7; k++) {
      const b = A.clone('props_world', 'PR_barricade');
      const a = k / 7 * Math.PI * 2, r = 18 + (k % 2) * 8;
      b.position.set(ic.x + Math.cos(a) * r, 0, ic.z + Math.sin(a) * r); b.rotation.y = -a + Math.PI / 2; sc.add(b);
      this.collision.addObject(b, 'cover');
    }
    for (let k = 0; k < 6; k++) {
      const c = A.clone('props_world', k % 2 ? 'PR_crate' : 'PR_crate_orange');
      c.position.set(ic.x + (rnd() - .5) * 50, 0, ic.z + (rnd() - .5) * 50); c.rotation.y = rnd() * 3; sc.add(c);
      this.collision.addObject(c, 'cover');
    }
    const gen = A.clone('props_world', 'PR_antenna'); gen.position.set(ic.x + 6, 0, ic.z - 4); sc.add(gen);
    this.spawnIncursion();
    // reflections for car paint and glass
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    this.envRT = pm.fromScene(new THREE.Scene().add(atmosphereSky('#3a6aa8', '#f2b27a', '#ffd9a8', this.sunDir)), 0.04);
    sc.environment = this.envRT.texture; sc.environmentIntensity = .9;
    pm.dispose(); this.disposables.push(this.envRT);
    progress(1, 'Ready');
  }

  spawnIncursion() {
    const g = this.g, ic = this.incursionCenter;
    const group = [];
    const types = ['trooper', 'trooper', 'trooper', 'trooper', 'brute', 'trooper', 'drone', 'drone'];
    for (let k = 0; k < types.length; k++) {
      const a = k / types.length * Math.PI * 2;
      const p = new THREE.Vector3(ic.x + Math.cos(a) * 10, 0, ic.z + Math.sin(a) * 10);
      const e = g.enemies.spawn(types[k], p, this.level, { group, onDeath: () => { this.incursionAlive--; if (this.incursionAlive <= 0) this.onCleared(); } });
      group.push(e);
    }
    this.incursionAlive = types.length;
  }

  onCleared() {
    const g = this.g;
    this.cleared++;
    g.hud.banner('Incursion repelled', 'District secured');
    g.gain('credits', 300, false); g.gain('xp', 400);
    g.combat.spawnPickup(this.incursionCenter.clone().setY(1), 'core', { rarity: Math.random() < .3 ? 3 : 2, level: this.level });
    this.squadT = 90;   // a fresh cell moves in after a while
    g.audio.levelUp();
  }

  spawn() {
    return { pos: new THREE.Vector3(0, 1.2, 16.5), yaw: 0 };
  }

  markers() {
    const m = [{ pos: new THREE.Vector3(0, 0, 12), icon: '▲', color: '#1ad8ff' }, { pos: new THREE.Vector3(8, 0, -8), icon: '◉', color: '#7dffb0' }];
    if (this.incursionAlive > 0) m.push({ pos: this.incursionCenter, icon: '✖', color: '#ff4a3d' });
    return m;
  }

  objectives() {
    const o = [];
    if (this.incursionAlive > 0) o.push({ text: 'Repel the incursion', sub: `North-east district · ${this.incursionAlive} hostiles remain`, p: 1 - this.incursionAlive / 8 });
    else o.push({ text: 'District secure', sub: this.squadT > 0 ? `Raiders regroup in ${Math.ceil(this.squadT)}s` : 'Raiders inbound' });
    o.push({ text: 'Visit the Quartermaster', sub: 'Spaceport · weapons for credits' });
    return o;
  }

  update(dt) {
    const g = this.g, p = g.player;
    this.sky.position.copy(g.camera.position);
    this.sky.material.uniforms.time.value = g.time;
    // shadow box follows the player
    const c = p.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : p.pos;
    this.sun.target.position.set(Math.round(c.x / 4) * 4, 0, Math.round(c.z / 4) * 4);
    this.sun.position.copy(this.sun.target.position).addScaledVector(this.sunDir, 250);
    // traffic
    const ext = (N + 1.5) * PITCH;
    for (const t of this.traffic) {
      t.t += t.speed * t.dir * dt;
      if (t.t > ext) t.t = -ext; if (t.t < -ext) t.t = ext;
      if (t.axis) { t.obj.position.set(t.lane, t.alt, t.t); t.obj.rotation.y = t.dir > 0 ? 0 : Math.PI; }
      else { t.obj.position.set(t.t, t.alt, t.lane); t.obj.rotation.y = t.dir > 0 ? Math.PI / 2 : -Math.PI / 2; }
    }
    // pedestrians stroll around the plaza ring
    for (const d of this.peds) {
      d.a += d.speed * d.dir * dt;
      const x = Math.cos(d.a) * d.ring, z = Math.sin(d.a) * d.ring;
      d.av.root.position.set(x, 0, z);
      d.av.root.rotation.y = Math.atan2(-Math.sin(d.a) * d.dir, Math.cos(d.a) * d.dir);
      d.av.play('WalkRelaxed', 0, 1);
      const dist = Math.hypot(x - p.pos.x, z - p.pos.z);
      d.av.update(dist < 80 ? dt : 0);
    }
    if (this.vendor) { this.vendor.update(dt); }
    if (this.incursionAlive <= 0 && this.squadT > 0) { this.squadT -= dt; if (this.squadT <= 0) this.spawnIncursion(); }
  }
}
