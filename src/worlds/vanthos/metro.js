// VANTHOS underground: procedural metro dungeons below every entrance. A seeded maze of 20 m cells (tunnels, junction
// halls, platform stations) with the district's creatures, loot at the dead ends and the way back up at the start.
import * as THREE from 'three';
import { World } from '../world.js';
import { mulberry } from '../../game/state.js';

const CELL = 20;
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3();
const Y = new THREE.Vector3(0, 1, 0);
// the Writhe (host, mite, bladder) has spread through the flooded and research tunnels and into the old lines
const FAUNA = { old: ['stalker', 'host', 'mite'], commercial: ['stalker'], flooded: ['swimmer', 'host', 'mite', 'mite', 'bladder'],
  research: ['mutant', 'host', 'mite', 'mite', 'bladder'], military: ['trooper', 'brute'],
  industrial: ['hulk', 'stalker'], crown: ['elite', 'stalker'], outskirts: ['stalker', 'trooper', 'host'] };

function instanceKit(scene, root, mats) {
  if (!mats.length) return;
  root.updateMatrixWorld(true);
  const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
  root.traverse(o => {
    if (!o.isMesh) return;
    const local = new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld);
    const im = new THREE.InstancedMesh(o.geometry, o.material, mats.length);
    mats.forEach((pm, i) => im.setMatrixAt(i, _m.multiplyMatrices(pm, local)));
    im.receiveShadow = true; im.geometry.userData.shared = true; im.computeBoundingSphere();
    scene.add(im);
  });
}

export class MetroWorld extends World {
  constructor(game, entry) {
    super(game);
    this.entry = entry || { x: 0, y: 0, z: 0, district: 'old', seed: 1, level: 8 };
    this.kind = 'metro'; this.name = 'Underground metro'; this.region = 'Vanthos';
    this.combat = true; this.allowCars = false; this.surface = 'metal';
    this.caches = [];
  }

  // seeded maze: a random tree on a grid, a few loops, rooms where corridors branch
  generate() {
    const rnd = this.rnd = mulberry(this.entry.seed * 7919 + 13);
    const N = 9, cells = new Map(), key = (i, j) => i + ',' + j;
    const start = [4, 8];
    cells.set(key(...start), { i: start[0], j: start[1], links: new Set() });
    const frontier = [start];
    const target = 22 + Math.floor(rnd() * 10);
    const D = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    while (cells.size < target && frontier.length) {
      const k = Math.floor(rnd() * frontier.length), [i, j] = frontier[k];
      const opts = D.map(([a, b]) => [i + a, j + b]).filter(([a, b]) => a >= 0 && b >= 0 && a < N && b < N && !cells.has(key(a, b)));
      if (!opts.length) { frontier.splice(k, 1); continue; }
      const [a, b] = opts[Math.floor(rnd() * opts.length)];
      cells.set(key(a, b), { i: a, j: b, links: new Set() });
      cells.get(key(i, j)).links.add(key(a, b)); cells.get(key(a, b)).links.add(key(i, j));
      frontier.push([a, b]);
    }
    // a few extra loops
    for (const c of cells.values()) for (const [a, b] of D) {
      const n = cells.get(key(c.i + a, c.j + b));
      if (n && rnd() < .08) { c.links.add(key(n.i, n.j)); n.links.add(key(c.i, c.j)); }
    }
    this.cells = cells; this.startKey = key(...start); this.key = key;
  }

  async build(progress) {
    const g = this.g, A = g.assets, sc = this.scene;
    progress(.1, 'Descending');
    this.generate();
    this.collision.floorY = 0; this.collision.terrain = () => 0;
    sc.background = new THREE.Color(0x050608);
    sc.fog = new THREE.Fog(0x08090c, 6, 70);
    sc.add(new THREE.HemisphereLight(0x5a6070, 0x15100c, .35));
    const kit = A.models.vanthos.scene;
    const tun = [], jun = [], sta = [];
    const ox = c => (c.i - 4) * CELL, oz = c => (c.j - 8) * CELL;
    const lights = [];
    for (const c of this.cells.values()) {
      const x = ox(c), z = oz(c), L = [...c.links].map(k => this.cells.get(k));
      const dirs = L.map(n => [Math.sign(n.i - c.i), Math.sign(n.j - c.j)]);
      const straightX = dirs.length === 2 && dirs.every(d => d[1] === 0), straightZ = dirs.length === 2 && dirs.every(d => d[0] === 0);
      const key = this.key(c.i, c.j);
      c.kind = key === this.startKey ? 'station' : (straightX || straightZ) ? 'tunnel' : dirs.length === 1 && this.rnd() < .4 ? 'station' : 'junction';
      const rot = (straightX || (c.kind === 'station' && dirs.length && dirs[0][1] === 0)) ? Math.PI / 2 : 0;
      const M = new THREE.Matrix4().compose(_p.set(x, 0, z), _q.setFromAxisAngle(Y, rot), c.kind === 'station' ? _s.set(.82, 1, .5) : _s.set(1, 1, 1));
      (c.kind === 'tunnel' ? tun : c.kind === 'station' ? sta : jun).push(M);
      // walls: everything in the cell except the open corridor towards each link
      const open = new Set(dirs.map(d => d.join(',')));
      const w = 5;           // half-width of the corridor
      const add = (x0, z0, x1, z1) => this.collision.add([x + x0, -1, z + z0, x + x1, 10, z + z1], 'wall');
      add(-10, -10, -w, -w); add(w, -10, 10, -w); add(-10, w, -w, 10); add(w, w, 10, 10);     // corners
      if (!open.has('1,0')) add(w, -w, 10, w);
      if (!open.has('-1,0')) add(-10, -w, -w, w);
      if (!open.has('0,1')) add(-w, w, w, 10);
      if (!open.has('0,-1')) add(-w, -10, w, -w);
      if (c.kind === 'tunnel' || this.rnd() < .5) lights.push(new THREE.Vector3(x, 6.5, z));
      c.pos = new THREE.Vector3(x, 0, z); c.links2 = L;
    }
    instanceKit(sc, kit.getObjectByName('VX_tunnel'), tun);
    instanceKit(sc, kit.getObjectByName('VX_junction'), jun);
    instanceKit(sc, kit.getObjectByName('VX_station'), sta);
    this.lampSpots = lights;
    this.lightPool = [];
    for (let i = 0; i < 5; i++) { const L = new THREE.PointLight(0xffb070, 0, 26, 1.6); sc.add(L); this.lightPool.push(L); }
    // the player's torch
    this.torch = new THREE.SpotLight(0xfff2e0, 60, 45, .55, .5, 1.2); sc.add(this.torch, this.torch.target);
    progress(.5, 'Waking the tunnels');
    // creatures, dead-end loot, the way out
    const start = this.cells.get(this.startKey);
    this.startPos = start.pos.clone();
    const fauna = FAUNA[this.entry.district] || ['stalker'];
    this.packs = [];
    for (const c of this.cells.values()) {
      if (c === start) continue;
      const deadEnd = c.links.size === 1;
      if (deadEnd) this.makeCache(c.pos.x + 2, c.pos.z + 2, c.kind === 'station' ? 3 : 2);
      if (this.rnd() < (c.kind === 'tunnel' ? .3 : .6)) this.packs.push({ pos: c.pos.clone(), n: 1 + Math.floor(this.rnd() * (c.kind === 'tunnel' ? 2 : 4)), live: false });
    }
    // the deepest room holds a stronger creature
    let far = start, fd = 0;
    for (const c of this.cells.values()) { const d = c.pos.distanceTo(start.pos); if (d > fd) { fd = d; far = c; } }
    this.packs.push({ pos: far.pos.clone(), n: 1, boss: true, live: false });
    this.interactables.push({ id: 'exit', pos: start.pos.clone().add(new THREE.Vector3(0, .5, 6)), r: 3.5, label: 'Stairway', verb: 'Climb to the surface', key: 'E',
      action: () => { g.metroReturn = { x: this.entry.x, y: this.entry.y, z: this.entry.z }; g.travel('vanthos'); } });
    this.fauna = fauna;
    g.vehicles.clear();
    progress(1, 'Ready');
  }

  makeCache(x, z, tier) {
    const g = this.g;
    const c = g.assets.clone('props_world', 'PR_cache'); c.position.set(x, 0, z); this.scene.add(c);
    this.collision.addObject(c, 'cache');
    const cache = { obj: c, lid: c.getObjectByName('cache_lid'), open: false, pos: c.position.clone(), t: 0, tier };
    cache.it = { id: 'cache', pos: c.position, r: 2.2, label: 'Abandoned locker', key: 'E', verb: 'Open', enabled: () => !cache.open,
      action: () => { cache.open = true; g.audio.ui('open'); g.save.stats.caches++;
        g.combat.spawnPickup(cache.pos.clone().setY(.6), 'core', { rarity: Math.min(4, tier), level: this.entry.level + 2 });
        g.combat.spawnPickup(cache.pos.clone().setY(.6), 'ammo'); g.gain('credits', 80 * tier, false); g.gain('xp', 90 * tier); } };
    this.interactables.push(cache.it); this.caches.push(cache);
  }

  spawn() { return { pos: this.startPos.clone().add(new THREE.Vector3(0, .2, 3)), yaw: Math.PI }; }

  markers() { return [{ pos: this.startPos, icon: '▲', color: '#1ad8ff' }]; }

  objectives() {
    const left = this.caches.filter(c => !c.open).length;
    return [{ text: 'Explore the metro', sub: left + ' lockers left · the stairway is at the start platform' },
      { text: 'Something big nests in the deepest hall', sub: 'Underground: no signal, no backup' }];
  }

  update(dt) {
    const g = this.g, p = g.player;
    // torch follows the camera
    this.torch.position.copy(g.camera.position);
    g.camera.getWorldDirection(_p); this.torch.target.position.copy(g.camera.position).addScaledVector(_p, 10);
    // nearest lamps
    this.lampT = (this.lampT || 0) - dt;
    if (this.lampT <= 0) {
      this.lampT = .4;
      const near = this.lampSpots.map(l => [l, l.distanceToSquared(p.pos)]).sort((a, b) => a[1] - b[1]).slice(0, this.lightPool.length);
      near.forEach(([l], i) => { this.lightPool[i].position.copy(l); this.lightPool[i].intensity = 140; });
    }
    for (const L of this.lightPool) L.intensity *= Math.random() < .02 ? .2 : 1;
    // packs wake up as the player approaches
    for (const pk of this.packs) {
      if (pk.live || pk.pos.distanceTo(p.pos) > 46) continue;
      pk.live = true;
      const group = [];
      const off = Math.floor(this.rnd() * this.fauna.length);
      for (let k = 0; k < pk.n; k++) {
        const type = pk.boss ? (this.fauna[0] === 'trooper' ? 'brute' : this.fauna.includes('hulk') ? 'hulk' : this.fauna.includes('host') ? 'amalgam' : 'elite') : this.fauna[(k + off) % this.fauna.length];
        // mites crawl out of the dark in clutches
        for (let m = 0, cnt = type === 'mite' ? 3 : 1; m < cnt; m++) {
          const e = g.enemies.spawn(type, pk.pos.clone().add(new THREE.Vector3((Math.random() - .5) * 6, 0, (Math.random() - .5) * 6)), this.entry.level + (pk.boss ? 3 : 1), { group });
          if (pk.boss) { e.maxHp = e.hp = e.maxHp * (type === 'amalgam' ? 1.5 : 3); e.T = { ...e.T, name: 'Nest ' + e.T.name, loot: 1 }; }
          group.push(e);
        }
      }
    }
    for (const cc of this.caches) if (cc.open && cc.lid && cc.t < 1) { cc.t = Math.min(1, cc.t + dt * 2); cc.lid.rotation.x = -cc.t * 1.9; }
  }
}
