// Frontier planets: endlessly generated terrain streamed in chunks around the player.
// Each chunk is seeded from (planet seed, chunk x, chunk z) so the world is stable however far you roam.
import * as THREE from 'three';
import { World } from './world.js';
import { atmosphereSky } from './sky.js';
import { mulberry } from '../game/state.js';
import { Flora } from './meridian/flora.js';
import { FADE_TIME, APPEAR, fadeMaterial, fadeGeometry, fadeAttr } from '../core/lodfade.js';

const CH = 64, RES = 24, RADIUS = 4;
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), _v = new THREE.Vector3();

function hash2(x, z, s) { let h = (Math.imul(x, 374761393) + Math.imul(z, 668265263) + Math.imul(s, 982451653)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967295; }
function vnoise(x, z, s) {
  const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi, u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash2(xi, zi, s), b = hash2(xi + 1, zi, s), c = hash2(xi, zi + 1, s), d = hash2(xi + 1, zi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function smooth(a, b, x) { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); }
// landform style and sky dressing per frontier world
const STYLE = { ares: 'mesa', vesper: 'glacier', thalassa: 'jungle', pyrrhos: 'volcanic', nyx: 'crystal' };
const SKYBODY = {
  ares: { dir: [-.45, .38, -.8], size: .2, color: '#e7d3b0', band: '#b08a62', ring: [1.45, 2.5], ringColor: '#d8c2a4', tilt: [.25, 1, .45] },
  vesper: { dir: [.6, .22, -.75], size: .26, color: '#9fb6d8', band: '#5e7aa6', ring: null },
  thalassa: { dir: [.3, .45, .85], size: .17, color: '#f0e2c8', band: '#c79a6a', ring: [1.5, 2.6], ringColor: '#e8dccb', tilt: [-.3, 1, .2] },
  pyrrhos: { dir: [-.7, .25, .6], size: .07, color: '#b05030', band: '#702414', ring: null },
  nyx: { dir: [-.5, .5, -.7], size: .06, color: '#e8e0ff', band: '#a898d8', ring: null, moon2: [.55, .32, -.75] },
};
// Blender-grown trees per landform (tools/blender/trees.py via flora.js): [pool, per-chunk count, max slope, scale]
const TREES = { glacier: [['snow', 2.2, .55, .9], ['rock_snow', .8, 9, 1]], jungle: [['jungle', 9, .7, .9], ['bush', 5, .8, 1.1]], mesa: [['savanna', 1.1, .35, 1]] };
const HAZE = { ares: .00062, vesper: .0011, thalassa: .0008, pyrrhos: .00095, nyx: .0007 };

function fbm(x, z, s, o = 5) { let t = 0, a = .5, n = 0; for (let i = 0; i < o; i++) { t += a * vnoise(x, z, s + i * 17); n += a; x *= 2.02; z *= 2.02; a *= .5; } return t / n; }

// Global instanced pools so scatter costs one draw call per prop type regardless of chunk count. Props of chunks
// streamed in while playing dither in over APPEAR seconds (core/lodfade.js) and dither out before their slot is reused.
class Pool {
  constructor(scene, root, cap) {
    root.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
    this.parts = []; this.cap = cap; this.free = []; for (let i = cap - 1; i >= 0; i--) this.free.push(i);
    this.fade = fadeAttr(cap); this.dying = [];
    root.traverse(o => {
      if (!o.isMesh) return;
      const im = new THREE.InstancedMesh(fadeGeometry(o.geometry, this.fade), fadeMaterial(o.material), cap);
      im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      im.castShadow = !/glow|crystal/.test(o.material.name); im.receiveShadow = true; im.frustumCulled = false;
      for (let i = 0; i < cap; i++) im.setMatrixAt(i, new THREE.Matrix4().makeScale(0, 0, 0));
      scene.add(im);
      this.parts.push({ im, local: new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld) });
    });
  }
  add(mat, appear = false) {
    const i = this.free.pop(); if (i === undefined) return -1;
    for (const p of this.parts) { p.im.setMatrixAt(i, _m.multiplyMatrices(mat, p.local)); p.im.instanceMatrix.needsUpdate = true; }
    this.fade.array[i * 3 + 2] = appear ? Math.max(1e-3, FADE_TIME.value) : 0; this.fade.needsUpdate = true;
    return i;
  }
  remove(i) {
    if (i < 0) return;
    this.fade.array[i * 3 + 2] = -Math.max(1e-3, FADE_TIME.value); this.fade.needsUpdate = true;
    this.dying.push(i);
  }
  // free the slots whose fade-out has finished
  tick(now) {
    if (!this.dying.length) return;
    const F = this.fade.array;
    this.dying = this.dying.filter(i => {
      if (now + F[i * 3 + 2] < APPEAR) return true;
      _m.makeScale(0, 0, 0);
      for (const p of this.parts) { p.im.setMatrixAt(i, _m); p.im.instanceMatrix.needsUpdate = true; }
      F[i * 3 + 2] = 0; this.fade.needsUpdate = true; this.free.push(i); return false;
    });
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

  // Landforms per world (see STYLE): domain-warped fbm for the base, ridged multifractal mountains that rise
  // with distance from the landing zone so the horizon is full of peaks, and a style pass on top:
  // mesas (terraced plateaus and canyons), glaciers (smooth ice sheets under knife ridges), jungle hills,
  // volcanic crags with calderas, crystal plains with dunes.
  height(x, z) {
    const D = this.dest, s = this.seed, f = D.freq, st = STYLE[D.id] || 'hills';
    // domain warp so nothing lines up with the noise grid
    const wx = x + (fbm(x * f * .7 + 11, z * f * .7 - 5, s + 41, 3) - .5) * 120;
    const wz = z + (fbm(x * f * .7 - 23, z * f * .7 + 9, s + 43, 3) - .5) * 120;
    let h = (fbm(wx * f, wz * f, s) - .5) * D.amp * 2;
    // ridged multifractal mountains, masked into ranges
    let rid = 0, amp = 1, wgt = 1, fx = wx * f * .55, fz = wz * f * .55;
    for (let i = 0; i < 5; i++) {
      let n = 1 - Math.abs(vnoise(fx, fz, s + 90 + i * 13) * 2 - 1); n *= n; n *= wgt;
      wgt = Math.min(1, n * 1.6); rid += n * amp; amp *= .5; fx *= 2.1; fz *= 2.1;
    }
    const range = smooth(.42, .72, fbm(wx * f * .18 + 7, wz * f * .18 - 3, s + 61, 3));
    const far = smooth(120, 700, Math.hypot(x, z));
    const mount = rid * range * D.amp * (st === 'crystal' ? 1.2 : st === 'jungle' ? 2.2 : 3.4) * (.35 + .65 * far);
    h += mount;
    if (st === 'mesa') {
      // flat-topped plateaus with cliff steps, cut by dry canyons
      const step = D.amp * .55, t = (h + D.amp * 2) / step, fr = t - Math.floor(t);
      h = (Math.floor(t) + smooth(.55, .8, fr)) * step - D.amp * 2;
      const cn = Math.abs(fbm(wx * f * 1.3 + 3, wz * f * 1.3 + 8, s + 71, 4) - .5);
      h -= smooth(.06, 0, cn) * D.amp * 1.1;
    } else if (st === 'glacier') {
      h = h * .75 + Math.pow(Math.max(0, h) / (D.amp * 3), 1.5) * D.amp * .9;
    } else if (st === 'volcanic') {
      // calderas: craters on top of the highest cones
      const cx = Math.floor(x / 420), cz = Math.floor(z / 420);
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
        const kx = cx + i, kz = cz + j; if (hash2(kx, kz, s + 5) < .55) continue;
        const px = (kx + .2 + hash2(kx, kz, s + 6) * .6) * 420, pz = (kz + .2 + hash2(kx, kz, s + 7) * .6) * 420;
        const d = Math.hypot(x - px, z - pz), R = 70 + hash2(kx, kz, s + 8) * 60;
        if (d < R * 2.2) h += D.amp * 2.2 * smooth(R * 2.2, R * .7, d) - D.amp * 1.6 * smooth(R * .75, R * .35, d);
      }
    } else if (st === 'crystal') {
      // long wind-swept dunes on open plains
      const a = .6, ux = x * Math.cos(a) - z * Math.sin(a), uz = x * Math.sin(a) + z * Math.cos(a);
      h += Math.pow(Math.abs(Math.sin(ux * .045 + fbm(ux * .01, uz * .01, s + 9, 2) * 5)), 1.6) * 3.2 * (1 - range);
    }
    h += (fbm(x * f * 4, z * f * 4, s + 3, 3) - .5) * 3;
    // flatten the landing zone
    const d = Math.hypot(x, z), k = Math.min(1, Math.max(0, (d - 30) / 50));
    const base = this.base0 !== undefined ? this.base0 : (this.base0 = this.baseAtOrigin());
    return base + (h - base) * k * k * (3 - 2 * k);
  }

  baseAtOrigin() { const D = this.dest, b = (fbm(0, 0, this.seed) - .5) * D.amp * 2; return this.lava != null ? Math.max(b, this.lava + 3) : b; }

  // Low-detail terrain from the edge of the streamed chunks out to the horizon. Rebuilt around the player as they
  // travel, a few rings per frame into a spare buffer so there is never a hitch, then swapped in.
  buildFar(cx, cz, sync = false) {
    const RINGS = 40, SEG = 112;
    if (!this.farMesh) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(RINGS * SEG * 3), 3));
      const idx = [];
      for (let r = 0; r < RINGS - 1; r++) for (let k = 0; k < SEG; k++) {
        const a = r * SEG + k, b = r * SEG + (k + 1) % SEG, c = a + SEG, d = b + SEG; idx.push(a, c, b, b, c, d);
      }
      geo.setIndex(idx);
      this.farMesh = new THREE.Mesh(geo, this.terrainMat); this.farMesh.frustumCulled = false; this.farMesh.receiveShadow = false;
      this.scene.add(this.farMesh);
    }
    this.farJob = { cx, cz, r: 0, buf: new Float32Array(RINGS * SEG * 3), RINGS, SEG };
    if (sync) while (this.farJob) this.stepFar(RINGS);
  }

  stepFar(n) {
    const J = this.farJob, r0 = CH * (RADIUS - 1.5), r1 = 1900;
    for (let i = 0; i < n && J.r < J.RINGS; i++, J.r++) {
      const r = J.r, rad = r0 * Math.pow(r1 / r0, r / (J.RINGS - 1));
      for (let k = 0; k < J.SEG; k++) {
        const a = k / J.SEG * Math.PI * 2, x = J.cx + Math.cos(a) * rad, z = J.cz + Math.sin(a) * rad, o = (r * J.SEG + k) * 3;
        // the inner rings sit a little low so the detailed chunks always win where they overlap
        J.buf[o] = x; J.buf[o + 1] = this.height(x, z) - (r < 3 ? 1.2 : .3); J.buf[o + 2] = z;
      }
    }
    if (J.r < J.RINGS) return;
    const geo = this.farMesh.geometry; geo.attributes.position.array.set(J.buf); geo.attributes.position.needsUpdate = true;
    geo.computeVertexNormals(); geo.computeBoundingSphere();
    this.farAt = [J.cx, J.cz]; this.farJob = null;
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
    const sky = atmosphereSky(D.sky[1], D.sky[0], D.sun, this.sunDir, { fog: D.fog, body: SKYBODY[D.id] }); sc.add(sky); this.sky = sky;
    // exponential haze: clear nearby, mountains fade into the air on the horizon
    sc.fog = new THREE.FogExp2(new THREE.Color(D.fog), HAZE[D.id] || .0008);
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
    const st = STYLE[D.id] || 'hills';
    // snow on the peaks (everywhere but the volcanic and jungle worlds), strata bands in mesa cliffs
    const snowLine = st === 'glacier' ? -999 : st === 'mesa' ? D.amp * 3.2 : st === 'crystal' ? D.amp * 2.6 : st === 'volcanic' || st === 'jungle' ? 9999 : D.amp * 2.4;
    mat.onBeforeCompile = sh => {
      sh.uniforms.rockMap = { value: rMap }; sh.uniforms.rockN = { value: rN }; sh.uniforms.rockTint = { value: rockTint };
      sh.uniforms.snowLine = { value: snowLine }; sh.uniforms.strata = { value: st === 'mesa' ? 1 : st === 'volcanic' ? .5 : .2 };
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;varying vec3 vWN;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;vWN=normalize(mat3(modelMatrix)*objectNormal);');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;varying vec3 vWN;uniform sampler2D rockMap,rockN;uniform vec3 rockTint;uniform float snowLine,strata;')
        .replace('#include <map_fragment>', `
          vec2 uvG=vWP.xz*.125;vec4 gc=texture2D(map,uvG)*texture2D(map,uvG*.137+.31);gc.rgb*=1.75;
          float slope=1.-vWN.y;float rk=smoothstep(.18,.38,slope);
          vec3 an=abs(vWN);vec2 uvR=(an.x>an.z?vWP.zy:vWP.xy)*.09;
          vec4 rc=texture2D(rockMap,uvR);
          // sedimentary bands in cliffs
          float band=sin(vWP.y*1.7+texture2D(rockMap,vWP.xz*.004).r*6.)*.5+.5;
          rc.rgb*=mix(1.,.72+band*.5,strata);
          diffuseColor.rgb*=mix(gc.rgb,rc.rgb*rockTint*2.2/max(diffuse,vec3(.05)),rk);
          // snow settles on flatter ground above the snow line, thinning on steep rock
          float sn=smoothstep(snowLine-6.,snowLine+10.,vWP.y+texture2D(rockMap,vWP.xz*.02).r*14.)*smoothstep(.62,.28,slope);
          diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.86,.9,.96)/max(diffuse,vec3(.05)),sn);`)
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
    this.poolList = [...this.pools.rock, this.pools.crystal, this.pools.plant].filter(Boolean);
    this.treeSpec = TREES[STYLE[D.id]] || null;
    if (this.treeSpec) {
      await A.loadAll([{ type: 'model', name: 'trees', file: 'trees.glb' }]);
      this.flora = new Flora(g, sc, A.models.trees);
      for (const [pool, n] of this.treeSpec) this.flora.reserve(pool, Math.ceil(n * 90 / 3) + 40);
      this.flora.build();
    }
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
    this.envRT = pm.fromScene(new THREE.Scene().add(atmosphereSky(D.sky[1], D.sky[0], D.sun, this.sunDir, { fog: D.fog })), .04);
    this.buildFar(0, 0, true);
    sc.environment = this.envRT.texture; sc.environmentIntensity = .6;
    pm.dispose(); this.disposables.push(this.envRT);
    g.vehicles.clear();
    // a hidden chunk with the fading terrain material so its shader is compiled behind the loading screen
    const probe = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), this.chunkFadeMat()); probe.visible = false; probe.receiveShadow = true; sc.add(probe);
    this.built = true;
    this.warmTextures();
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
    const appear = !!this.built;
    const mesh = new THREE.Mesh(geo, appear ? this.chunkFadeMat() : this.terrainMat);
    mesh.position.set(ox, 0, oz); mesh.receiveShadow = true; mesh.castShadow = false;
    this.scene.add(mesh);
    if (appear) (this.fading = this.fading || []).push(mesh);
    const ch = { key, cx, cz, mesh, inst: [], boxes: [], enemies: [], props: [] };
    // ---- seeded scatter
    const rnd = mulberry((this.seed * 7919) ^ (cx * 73856093) ^ (cz * 19349663));
    const place = (pool, x, z, s, ry, tilt = 0) => {
      const y = this.height(x, z);
      if (this.lava !== null && y < this.lava + .2) return null;
      const id = pool.add(_m.compose(_p.set(x, y, z), _q.setFromEuler(new THREE.Euler(tilt * (rnd() - .5), ry, tilt * (rnd() - .5))), _s.set(s, s, s)), appear);
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
    // trees: snowy conifers on the glacier shelf, jungle canopy, lone savanna trees on the mesas (streamed with the chunk)
    if (this.flora) for (const [pool, dens, maxSlope, sc0] of this.treeSpec) for (let k = 0, n = Math.floor(dens * (.4 + rnd() * 1.2)); k < n; k++) {
      const x = cx * CH + rnd() * CH, z = cz * CH + rnd() * CH; if (Math.hypot(x, z) < 34) continue;
      const y = this.height(x, z), sl = Math.hypot(this.height(x + 2, z) - this.height(x - 2, z), this.height(x, z + 2) - this.height(x, z - 2)) / 4;
      if (sl > maxSlope || (this.lava !== null && y < this.lava + 1)) continue;
      const h = this.flora.addLive(pool, x, y - .3, z, rnd, sc0 * (.8 + rnd() * .45), appear); if (!h) continue;
      ch.inst.push([{ remove: hh => this.flora.removeLive(hh) }, h]);
      const r = h.k.species === 'rock' ? h.k.w * .6 : h.k.species === 'bush' ? 0 : Math.max(.15, h.k.trunk * .9);
      if (r) ch.boxes.push(this.collision.add([x - r, y - .5, z - r, x + r, y + (h.k.species === 'rock' ? h.k.h * .8 : 4), z + r], h.k.species === 'rock' ? 'rock' : 'tree'));
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
    // some outposts have been overrun by the Writhe: a few raiders hold out against hosts, a mite swarm and a bladder
    const overrun = rnd() < .25;
    op.overrun = overrun;
    const squad = overrun ? ['trooper', 'trooper', 'host', 'host', 'bladder', ...Array(5 + Math.floor(rnd() * 4)).fill('mite'),
      ...(this.level > 8 && rnd() < .35 ? ['amalgam'] : rnd() < .5 ? ['host'] : [])] : null;
    for (let k = 0; k < (squad ? squad.length : n); k++) {
      const a = rnd() * Math.PI * 2, r = (squad && squad[k] !== 'trooper' ? 9 : 4) + rnd() * 7;
      const px = x + Math.cos(a) * r, pz = z + Math.sin(a) * r;
      const type = squad ? squad[k] : k === 0 && rnd() < .5 + this.level * .02 ? 'brute' : 'trooper';
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
    if (ch.mesh.material !== this.terrainMat) { ch.mesh.material.dispose(); this.fading = this.fading.filter(m => m !== ch.mesh); }
    this.chunks.delete(ch.key);
  }

  // A terrain chunk streamed in while playing dithers in over APPEAR seconds above the horizon mesh (which lies a
  // little lower underneath it), then goes back to the shared material. The copies share the terrain's program; only
  // their uBorn uniform differs.
  chunkFadeMat() {
    const src = this.terrainMat, m = src.clone(), born = { value: Math.max(1e-3, FADE_TIME.value) };
    m.onBeforeCompile = (sh, r) => {
      src.onBeforeCompile(sh, r);
      sh.uniforms.uBorn = born; sh.uniforms.uFadeT = FADE_TIME;
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform float uBorn, uFadeT;')
        .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
          if ( fract( 52.9829189 * fract( dot( floor( gl_FragCoord.xy ), vec2( .06711056, .00583715 ) ) ) ) > ( uFadeT - uBorn ) / ${APPEAR.toFixed(2)} ) discard;`);
    };
    m.customProgramCacheKey = () => 'terrainfade';
    m.userData.born = born;
    return m;
  }

  fadeChunks() {
    if (!this.fading || !this.fading.length) return;
    this.fading = this.fading.filter(mesh => {
      if (FADE_TIME.value - mesh.material.userData.born.value < APPEAR) return true;
      mesh.material.dispose(); mesh.material = this.terrainMat; return false;
    });
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
    FADE_TIME.value = g.time;
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
    if (this.flora) this.flora.update(g.camera, dt);
    for (const pl of this.poolList) pl.tick(FADE_TIME.value);
    this.fadeChunks();
    // (the low-detail horizon terrain follows the player: before, worlds with trees never rebuilt it and a hole
    // opened where the landing zone's chunks had been)
    if (this.farJob) this.stepFar(3);
    else if (this.farAt && Math.hypot(c.x - this.farAt[0], c.z - this.farAt[1]) > 48) this.buildFar(Math.round(c.x / 16) * 16, Math.round(c.z / 16) * 16);
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
