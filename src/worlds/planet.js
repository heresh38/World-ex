// Frontier planets: endlessly generated terrain streamed in chunks around the player.
// Each chunk is seeded from (planet seed, chunk x, chunk z) so the world is stable however far you roam.
import * as THREE from 'three';
import { World } from './world.js';
import { atmosphereSky } from './sky.js';
import { mulberry } from '../game/state.js';

const CH = 64, RES = 24, RADIUS = 4;
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), _v = new THREE.Vector3();

function hash2(x, z, s) { let h = (Math.imul(x, 374761393) + Math.imul(z, 668265263) + Math.imul(s, 982451653)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967295; }
function vnoise(x, z, s) {
  const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi, u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash2(xi, zi, s), b = hash2(xi + 1, zi, s), c = hash2(xi, zi + 1, s), d = hash2(xi + 1, zi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x, z, s, o = 5) { let t = 0, a = .5, n = 0; for (let i = 0; i < o; i++) { t += a * vnoise(x, z, s + i * 17); n += a; x *= 2.02; z *= 2.02; a *= .5; } return t / n; }

// Global instanced pools so scatter costs one draw call per prop type regardless of chunk count.
class Pool {
  constructor(scene, root, cap) {
    root.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
    this.parts = []; this.cap = cap; this.free = []; for (let i = cap - 1; i >= 0; i--) this.free.push(i);
    root.traverse(o => {
      if (!o.isMesh) return;
      const im = new THREE.InstancedMesh(o.geometry, o.material, cap);
      im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      im.castShadow = !/glow|crystal/.test(o.material.name); im.receiveShadow = true; im.frustumCulled = false;
      im.geometry.userData.shared = true;
      for (let i = 0; i < cap; i++) im.setMatrixAt(i, new THREE.Matrix4().makeScale(0, 0, 0));
      scene.add(im);
      this.parts.push({ im, local: new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld) });
    });
  }
  add(mat) {
    const i = this.free.pop(); if (i === undefined) return -1;
    for (const p of this.parts) { p.im.setMatrixAt(i, _m.multiplyMatrices(mat, p.local)); p.im.instanceMatrix.needsUpdate = true; }
    return i;
  }
  remove(i) {
    if (i < 0) return; _m.makeScale(0, 0, 0);
    for (const p of this.parts) { p.im.setMatrixAt(i, _m); p.im.instanceMatrix.needsUpdate = true; }
    this.free.push(i);
  }
}

export class PlanetWorld extends World {
  constructor(game, dest) {
    super(game);
    this.dest = dest; this.kind = 'planet'; this.name = dest.region; this.region = dest.name;
    this.combat = true; this.allowCars = true;
    this.surface = dest.ground === 'ice' ? 'snow' : dest.ground === 'sand' ? 'sand' : 'dirt';
    this.level = dest.level; this.destPower = dest.power;
    this.seed = dest.seed;
    this.chunks = new Map(); this.queue = [];
    this.outposts = new Map(); this.cleared = new Set(); this.opened = new Set();
    this.caches = [];
    this.droneT = 25;
    this.stats = { generators: 0, kills: 0 };
    this.lava = dest.hazard === 'lava' ? -6 : null;
  }

  height(x, z) {
    const D = this.dest, s = this.seed, f = D.freq;
    let h = (fbm(x * f, z * f, s) - .5) * D.amp * 2;
    const r = 1 - Math.abs(fbm(x * f * .5 + 31, z * f * .5 - 17, s + 7, 4) * 2 - 1);
    h += r * r * D.amp * 1.4;
    h += (fbm(x * f * 4, z * f * 4, s + 3, 3) - .5) * 3;
    // flatten the landing zone
    const d = Math.hypot(x, z), k = Math.min(1, Math.max(0, (d - 30) / 50));
    const base = (fbm(0, 0, s) - .5) * D.amp * 2;
    return base + (h - base) * k * k * (3 - 2 * k);
  }

  async build(progress) {
    const g = this.g, A = g.assets, D = this.dest, sc = this.scene, T = A.textures;
    progress(.05, 'Entering atmosphere');
    this.collision.terrain = (x, z) => {
      const h = this.height(x, z);
      return this.lava !== null ? Math.max(h, this.lava - .6) : h;
    };
    // ---------------- sky, fog, light
    const el = D.sunEl;
    this.sunDir = new THREE.Vector3(Math.cos(el) * .7, Math.sin(el), Math.cos(el) * -.7).normalize();
    const sky = atmosphereSky(D.sky[1], D.sky[0], D.sun, this.sunDir); sc.add(sky); this.sky = sky;
    sc.fog = new THREE.Fog(new THREE.Color(D.fog), 60, CH * RADIUS * .95);
    sc.add(new THREE.HemisphereLight(new THREE.Color(D.sky[0]), new THREE.Color(D.groundTint).multiplyScalar(.4), 1.1));
    const sun = new THREE.DirectionalLight(new THREE.Color(D.sun), 2.6);
    sun.castShadow = true; const q = g.renderer.q; sun.shadow.mapSize.set(q.shadow, q.shadow);
    Object.assign(sun.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 10, far: 400 });
    sun.shadow.bias = -.0005; sun.shadow.normalBias = .08;
    sc.add(sun, sun.target); this.sun = sun;
    // ---------------- terrain material: ground on flats, rock on slopes, world-space tiling
    const gMap = T[D.ground], gN = T[D.ground + '_n'], rMap = T.rock, rN = T.rock_n;
    const mat = new THREE.MeshStandardMaterial({ map: gMap, normalMap: gN, roughness: .92, color: new THREE.Color(D.groundTint), envMapIntensity: .3 });
    const rockTint = new THREE.Color(D.rock);
    mat.onBeforeCompile = sh => {
      sh.uniforms.rockMap = { value: rMap }; sh.uniforms.rockN = { value: rN }; sh.uniforms.rockTint = { value: rockTint };
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;varying vec3 vWN;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;vWN=normalize(mat3(modelMatrix)*objectNormal);');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;varying vec3 vWN;uniform sampler2D rockMap,rockN;uniform vec3 rockTint;')
        .replace('#include <map_fragment>', `
          vec2 uvG=vWP.xz*.125;vec4 gc=texture2D(map,uvG)*texture2D(map,uvG*.137+.31);gc.rgb*=1.75;
          float slope=1.-vWN.y;float rk=smoothstep(.18,.38,slope);
          vec3 an=abs(vWN);vec2 uvR=(an.x>an.z?vWP.zy:vWP.xy)*.09;
          vec4 rc=texture2D(rockMap,uvR);
          diffuseColor.rgb*=mix(gc.rgb,rc.rgb*rockTint*2.2/max(diffuse,vec3(.05)),rk);`)
        .replace('#include <normal_fragment_maps>', `
          vec3 nG=texture2D(normalMap,uvG).xyz*2.-1.;vec3 nR=texture2D(rockN,uvR).xyz*2.-1.;
          vec3 mapN=normalize(mix(nG,nR,rk));mapN.xy*=normalScale;normal=normalize(tbn*mapN);`);
    };
    // tbn is only defined when the material uses a tangent-less normal map with derivatives (USE_NORMALMAP_TANGENTSPACE)
    this.terrainMat = mat;
    // ---------------- scatter pools
    const kit = A.models.props_world.scene;
    const tint = (root, col) => { root.traverse(o => { if (o.isMesh && o.material.name === 'rock') { o.material = o.material.clone(); o.material.color.set(col); } }); };
    const rockKit = [];
    for (let i = 0; i < 6; i++) { const r = kit.getObjectByName('PR_rock_' + i).clone(true); tint(r, D.rock); rockKit.push(r); }
    this.pools = { rock: rockKit.map(r => new Pool(sc, r, 260)) };
    this.pools.crystal = D.crystal >= 0 ? new Pool(sc, kit.getObjectByName('PR_crystal_' + D.crystal), 240) : null;
    this.pools.plant = D.plants >= 0 ? new Pool(sc, kit.getObjectByName('PR_plant_' + D.plants), 400) : null;
    progress(.2, 'Mapping terrain');
    // ---------------- landing site: jumpship + beacon
    const gy = this.height(0, 0);
    const js = A.clone('ship_jumper'); js.position.set(0, gy, 0); js.rotation.y = Math.PI * .8; sc.add(js); this.jumpship = js;
    const yaw = js.rotation.y, fw = new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw));
    // fuselage + wing colliders (oriented roughly by yaw)
    for (let t = -6; t <= 6; t += 3) { const c = fw.clone().multiplyScalar(t); this.collision.add([c.x - 2, gy, c.z - 2, c.x + 2, gy + 4, c.z + 2], 'ship'); }
    const rampPos = fw.clone().multiplyScalar(-10).setY(gy);
    this.landing = rampPos.clone();
    this.interactables.push({ id: 'ship', pos: rampPos, r: 3.5, label: 'The Wayfarer', verb: 'Return to orbit', key: 'E', action: () => g.travel('ship') });
    // lava sea
    if (this.lava !== null) {
      const lm = new THREE.MeshStandardMaterial({ color: 0x220800, emissive: new THREE.Color(1.0, .32, .05), emissiveIntensity: 2.2, roughness: .6 });
      const lv = new THREE.Mesh(new THREE.PlaneGeometry(CH * RADIUS * 3, CH * RADIUS * 3, 1, 1), lm);
      lv.rotation.x = -Math.PI / 2; lv.position.y = this.lava; sc.add(lv); this.lavaMesh = lv;
      this.lavaLight = new THREE.HemisphereLight(0x000000, 0xff5a1a, .5); sc.add(this.lavaLight);
    }
    // ---------------- generate the initial ring synchronously (with progress)
    const want = this.wanted(0, 0);
    let i = 0;
    for (const k of want) {
      this.makeChunk(k[0], k[1]);
      if (++i % 6 === 0) { progress(.2 + .7 * i / want.length, 'Generating terrain ' + Math.round(i / want.length * 100) + '%'); await new Promise(r => setTimeout(r, 0)); }
    }
    // reflections
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    this.envRT = pm.fromScene(new THREE.Scene().add(atmosphereSky(D.sky[1], D.sky[0], D.sun, this.sunDir)), .04);
    sc.environment = this.envRT.texture; sc.environmentIntensity = .6;
    pm.dispose(); this.disposables.push(this.envRT);
    g.vehicles.clear();
    progress(1, 'Ready');
  }

  wanted(cx, cz) {
    const out = [];
    for (let dx = -RADIUS; dx <= RADIUS; dx++) for (let dz = -RADIUS; dz <= RADIUS; dz++) {
      if (dx * dx + dz * dz > RADIUS * RADIUS + 1) continue;
      out.push([cx + dx, cz + dz, dx * dx + dz * dz]);
    }
    return out.sort((a, b) => a[2] - b[2]);
  }

  makeChunk(cx, cz) {
    const key = cx + ',' + cz;
    if (this.chunks.has(key)) return;
    const g = this.g, D = this.dest;
    const geo = new THREE.PlaneGeometry(CH, CH, RES, RES); geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position;
    const ox = cx * CH + CH / 2, oz = cz * CH + CH / 2;
    for (let i = 0; i < pos.count; i++) pos.setY(i, this.height(pos.getX(i) + ox, pos.getZ(i) + oz));
    geo.computeVertexNormals();
    // fix seams: recompute edge normals from the height function
    const nrm = geo.attributes.normal, e = CH / RES;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i) + ox, z = pos.getZ(i) + oz;
      if (Math.abs(pos.getX(i)) < CH / 2 - .01 && Math.abs(pos.getZ(i)) < CH / 2 - .01) continue;
      _v.set(this.height(x - e, z) - this.height(x + e, z), 2 * e, this.height(x, z - e) - this.height(x, z + e)).normalize();
      nrm.setXYZ(i, _v.x, _v.y, _v.z);
    }
    const mesh = new THREE.Mesh(geo, this.terrainMat);
    mesh.position.set(ox, 0, oz); mesh.receiveShadow = true; mesh.castShadow = false;
    this.scene.add(mesh);
    const ch = { key, cx, cz, mesh, inst: [], boxes: [], enemies: [], props: [] };
    // ---- seeded scatter
    const rnd = mulberry((this.seed * 7919) ^ (cx * 73856093) ^ (cz * 19349663));
    const place = (pool, x, z, s, ry, tilt = 0) => {
      const y = this.height(x, z);
      if (this.lava !== null && y < this.lava + .2) return null;
      const id = pool.add(_m.compose(_p.set(x, y, z), _q.setFromEuler(new THREE.Euler(tilt * (rnd() - .5), ry, tilt * (rnd() - .5))), _s.set(s, s, s)));
      ch.inst.push([pool, id]);
      return y;
    };
    const nearSite = (x, z) => Math.hypot(x, z) < 28;
    const nr = 4 + Math.floor(rnd() * 6);
    for (let k = 0; k < nr; k++) {
      const x = cx * CH + rnd() * CH, z = cz * CH + rnd() * CH; if (nearSite(x, z)) continue;
      const vi = Math.floor(rnd() * 6), s = .6 + rnd() * (vi > 3 ? 1.6 : 1.1);
      const y = place(this.pools.rock[vi], x, z, s, rnd() * 6.28, .3);
      const r = (1.2 + vi * .3) * s * .8;
      if (y !== null && r > .9) ch.boxes.push(this.collision.add([x - r, y - 1, z - r, x + r, y + (1 + vi * .3) * s * .9, z + r], 'rock'));
    }
    if (this.pools.crystal) for (let k = 0, n = Math.floor(rnd() * 4); k < n; k++) {
      const x = cx * CH + rnd() * CH, z = cz * CH + rnd() * CH; if (nearSite(x, z)) continue;
      place(this.pools.crystal, x, z, .7 + rnd() * 1.1, rnd() * 6.28, .5);
    }
    if (this.pools.plant) for (let k = 0, n = 2 + Math.floor(rnd() * 7); k < n; k++) {
      const x = cx * CH + rnd() * CH, z = cz * CH + rnd() * CH; if (nearSite(x, z)) continue;
      place(this.pools.plant, x, z, .8 + rnd() * .9, rnd() * 6.28, .3);
    }
    // ---- outposts and caches
    const dist = Math.hypot(ox, oz);
    if (dist > 110 && rnd() < .2 && !this.cleared.has(key)) this.buildOutpost(ch, ox + (rnd() - .5) * 20, oz + (rnd() - .5) * 20, rnd);
    else if (dist > 60 && rnd() < .12 && !this.opened.has(key)) this.buildCache(ch, ox + (rnd() - .5) * 40, oz + (rnd() - .5) * 40);
    this.chunks.set(key, ch);
  }

  buildOutpost(ch, x, z, rnd) {
    const g = this.g, A = g.assets, sc = this.scene;
    const y = this.height(x, z);
    if (this.lava !== null && y < this.lava + 1) return;
    const op = { key: ch.key, pos: new THREE.Vector3(x, y, z), enemies: [], gen: null, alive: 0, cleared: false };
    // barricade ring + generator + turret + squad
    for (let k = 0; k < 5; k++) {
      const a = k / 5 * Math.PI * 2 + rnd(), r = 11 + rnd() * 4;
      const bx = x + Math.cos(a) * r, bz = z + Math.sin(a) * r;
      const b = A.clone('props_world', 'PR_barricade'); b.position.set(bx, this.height(bx, bz), bz); b.rotation.y = -a + Math.PI / 2;
      sc.add(b); ch.props.push(b); ch.boxes.push(this.collision.addObject(b, 'cover'));
    }
    for (let k = 0; k < 3; k++) {
      const bx = x + (rnd() - .5) * 14, bz = z + (rnd() - .5) * 14;
      const c = A.clone('props_world', rnd() < .5 ? 'PR_crate' : 'PR_crate_orange'); c.position.set(bx, this.height(bx, bz), bz); c.rotation.y = rnd() * 3;
      sc.add(c); ch.props.push(c); ch.boxes.push(this.collision.addObject(c, 'cover'));
    }
    const ant = A.clone('props_world', 'PR_antenna'); ant.position.set(x - 4, y, z + 3); sc.add(ant); ch.props.push(ant);
    const L = this.level + Math.floor(Math.hypot(x, z) / 500);
    const group = [];
    const onDeath = e => {
      op.alive--;
      if (e.type === 'generator') this.onGenerator(op);
    };
    op.gen = g.enemies.spawn('generator', op.pos.clone(), L, { group, onDeath }); group.push(op.gen);
    const tp = new THREE.Vector3(x + 6, this.height(x + 6, z - 5), z - 5);
    group.push(g.enemies.spawn('turret', tp, L, { group, onDeath }));
    const n = 3 + Math.floor(rnd() * 3) + (this.level > 10 ? 1 : 0);
    for (let k = 0; k < n; k++) {
      const a = rnd() * Math.PI * 2, r = 4 + rnd() * 7;
      const px = x + Math.cos(a) * r, pz = z + Math.sin(a) * r;
      const type = k === 0 && rnd() < .5 + this.level * .02 ? 'brute' : 'trooper';
      group.push(g.enemies.spawn(type, new THREE.Vector3(px, this.height(px, pz), pz), L, { group, onDeath }));
    }
    if (rnd() < .6) group.push(g.enemies.spawn('drone', new THREE.Vector3(x, y, z + 8), L, { group, onDeath }));
    op.enemies = group; op.alive = group.length;
    ch.enemies.push(...group);
    // loot cache unlocks when the generator falls
    op.cache = this.buildCache(ch, x - 3, z - 6, true);
    this.outposts.set(ch.key, op);
  }

  onGenerator(op) {
    const g = this.g;
    op.cleared = true; this.cleared.add(op.key);
    this.stats.generators++;
    g.save.stats.generators++;
    g.contractEvent('outposts', 1);
    g.hud.banner('Outpost disabled', 'Generator destroyed · cache unlocked');
    g.gain('xp', 250); g.gain('credits', 120, false);
    if (op.cache) op.cache.locked = false;
  }

  buildCache(ch, x, z, locked = false) {
    const g = this.g, A = g.assets;
    const y = this.height(x, z);
    if (this.lava !== null && y < this.lava + .5) return null;
    const c = A.clone('props_world', 'PR_cache'); c.position.set(x, y, z); c.rotation.y = Math.random() * 6; this.scene.add(c);
    ch.props.push(c); ch.boxes.push(this.collision.addObject(c, 'cache'));
    const lid = c.getObjectByName('cache_lid');
    const cache = { obj: c, lid, locked, open: false, key: ch.key, pos: c.position.clone(), t: 0 };
    const it = { id: 'cache', pos: c.position, r: 2.2, label: 'Supply Cache', key: 'E',
      get verb() { return cache.locked ? 'Locked · destroy the generator' : 'Open'; },
      enabled: () => !cache.open, action: () => this.openCache(cache) };
    cache.it = it;
    this.interactables.push(it);
    this.caches.push(cache);
    return cache;
  }

  openCache(cache) {
    const g = this.g;
    if (cache.locked) { g.audio.ui('deny'); g.hud.toast('Cache sealed — destroy the outpost generator'); return; }
    cache.open = true; this.opened.add(cache.key);
    g.save.stats.caches++; g.contractEvent('caches', 1);
    g.audio.ui('open');
    const far = Math.hypot(cache.pos.x, cache.pos.z);
    const rarity = Math.random() < .08 + far / 6000 ? 3 : Math.random() < .5 ? 2 : 1;
    g.combat.spawnPickup(cache.pos.clone().setY(cache.pos.y + .6), 'core', { rarity, level: this.level });
    g.combat.spawnPickup(cache.pos.clone().setY(cache.pos.y + .6), 'ammo');
    g.gain('credits', 60 + Math.round(far / 20), false); g.gain('xp', 80);
    g.fx.emit(cache.pos.clone().setY(cache.pos.y + .8), 40, 4, 0xffae2f, .8, 3, .08);
  }

  unloadChunk(ch) {
    for (const [pool, id] of ch.inst) pool.remove(id);
    for (const b of ch.boxes) this.collision.remove(b);
    ch.props.forEach(p => p.removeFromParent());
    const op = this.outposts.get(ch.key);
    if (op) this.outposts.delete(ch.key);
    // enemies belonging to the chunk go with it (unless already fighting the player)
    const set = new Set(ch.enemies);
    this.g.enemies.removeWhere(e => set.has(e) && (e.state !== 'combat' || !e.alive));
    const its = new Set(this.caches.filter(c => c.key === ch.key).map(c => c.it));
    this.interactables = this.interactables.filter(it => !its.has(it));
    this.caches = this.caches.filter(c => c.key !== ch.key);
    this.scene.remove(ch.mesh); ch.mesh.geometry.dispose();
    this.chunks.delete(ch.key);
  }

  spawn() {
    const p = this.landing.clone(); p.y = this.height(p.x, p.z);
    return { pos: p, yaw: Math.atan2(-p.x, -p.z) + .5 };
  }

  markers() {
    const p = this.g.player.pos, m = [{ pos: this.landing, icon: '▲', color: '#1ad8ff' }];
    let best = null, bd = 1e9;
    for (const op of this.outposts.values()) if (!op.cleared) { const d = op.pos.distanceTo(p); if (d < bd) { bd = d; best = op; } }
    if (best) m.push({ pos: best.pos, icon: '✖', color: '#ff4a3d' });
    for (const c of this.caches) if (!c.open && !c.locked && c.pos.distanceTo(p) < 140) m.push({ pos: c.pos, icon: '◆', color: '#ffae2f' });
    return m;
  }

  objectives() {
    const g = this.g;
    const open = [...this.outposts.values()].filter(o => !o.cleared).length;
    const o = [{ text: 'Frontier patrol', sub: `${this.stats.generators} generators destroyed · ${open} outposts on scanners` }];
    for (const c of g.save.contracts.filter(c => !c.done).slice(0, 2)) o.push({ text: c.text, sub: 'Contract', p: c.p / c.n });
    if (this.lava !== null) o.push({ text: 'Hazard: molten lowlands', sub: 'Stay on high ground' });
    return o;
  }

  update(dt) {
    const g = this.g, p = g.player;
    this.sky.position.copy(g.camera.position);
    this.sky.material.uniforms.time.value = g.time;
    const c = p.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : p.pos;
    this.sun.target.position.set(Math.round(c.x / 4) * 4, c.y, Math.round(c.z / 4) * 4);
    this.sun.position.copy(this.sun.target.position).addScaledVector(this.sunDir, 200);
    if (this.lavaMesh) {
      this.lavaMesh.position.x = Math.round(c.x / CH) * CH; this.lavaMesh.position.z = Math.round(c.z / CH) * CH;
      this.lavaMesh.material.emissiveIntensity = 2 + Math.sin(g.time * 1.3) * .3;
      if (!p.dead && p.mode === 'foot' && p.pos.y < this.lava + .1) { this.lavaT = (this.lavaT || 0) - dt; if (this.lavaT <= 0) { this.lavaT = .3; p.damage(14, p.pos); } }
      if (p.mode === 'car' && g.vehicles.current && g.vehicles.current.pos.y < this.lava + .1) g.vehicles.current.damage(30 * dt);
    }
    // streaming: queue missing chunks, build 1 per frame; drop far ones
    const ccx = Math.floor(c.x / CH), ccz = Math.floor(c.z / CH);
    if (ccx !== this.lcx || ccz !== this.lcz) {
      this.lcx = ccx; this.lcz = ccz;
      const want = this.wanted(ccx, ccz), keys = new Set(want.map(w => w[0] + ',' + w[1]));
      this.queue = want.filter(w => !this.chunks.has(w[0] + ',' + w[1]));
      for (const ch of [...this.chunks.values()]) {
        if (!keys.has(ch.key) && Math.max(Math.abs(ch.cx - ccx), Math.abs(ch.cz - ccz)) > RADIUS + 1) this.unloadChunk(ch);
      }
    }
    if (this.queue.length) { const w = this.queue.shift(); this.makeChunk(w[0], w[1]); }
    // caches: animate lids
    for (const cc of this.caches) if (cc.open && cc.lid && cc.t < 1) { cc.t = Math.min(1, cc.t + dt * 2); cc.lid.rotation.x = -cc.t * 1.9; }
    // roaming drone pairs
    this.droneT -= dt;
    if (this.droneT <= 0) {
      this.droneT = 40 + Math.random() * 30;
      if (g.enemies.list.filter(e => e.type === 'drone' && e.alive).length < 6) {
        const a = Math.random() * Math.PI * 2, r = 70;
        for (let k = 0; k < 2; k++) {
          const x = p.pos.x + Math.cos(a) * r + k * 4, z = p.pos.z + Math.sin(a) * r;
          const e = g.enemies.spawn('drone', new THREE.Vector3(x, this.height(x, z), z), this.level);
          e.state = 'combat';
        }
      }
    }
  }

  dispose() {
    super.dispose();
    for (const ch of this.chunks.values()) ch.mesh.geometry.dispose();
  }
}
