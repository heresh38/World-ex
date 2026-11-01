// VANTHOS, the Fallen Metropolis: the first major open-world destination.
// A ruined circular city around the Spire. Districts are independent modules (districts.js) placed by the city plan
// (map.js). Buildings are instanced city-wide so the skyline is always there; the living parts of each district
// (enemy packs, lights, triggers) stream in and out with the player. Three levels: streets, rooftops and elevated
// highways (lifts and ramps), and the metro below (metro.js, procedural dungeons).
import * as THREE from 'three';
import { World } from '../world.js';
import { atmosphereSky } from '../sky.js';
import { mulberry } from '../../game/state.js';
import { VanthosMap, CROWN_R, OUTER_R, SPIRE_R, CRATER_R, HIGHWAYS, MAJOR, STREET, BW, BD, WATER_Y, fbm } from './map.js';
import { DISTRICTS } from './districts.js';
import { Water } from '../../game/water.js';
import { Operation } from './operation.js';

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), _v = new THREE.Vector3();
const Y = new THREE.Vector3(0, 1, 0);
const STREAM_IN = 230, STREAM_OUT = 340;

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
    this.sites = []; this.caches = []; this.lights = []; this.triggers = []; this.shards = []; this.lifts = [];
    this.kitMats = new Map(); this.kitInfo = new Map();
    this.eventT = 150; this.event = null;
    const sv = game.save; sv.vanthos = { shards: [], bosses: [], runs: 0, best: null, logs: [], ...(sv.vanthos || {}) };
  }

  levelAt(x, z, D) {
    const r = Math.hypot(x, z);
    return this.level + Math.floor((1 - Math.min(1, r / 1800)) * 9) + ((D && D.danger) || 0);
  }

  height(x, z) { return this.map.height(x, z); }

  async build(progress) {
    const g = this.g, A = g.assets, sc = this.scene, T = A.textures, map = this.map;
    const tick = async (f, l) => { progress(f, l); await new Promise(r => setTimeout(r, 0)); };
    this.collision.terrain = (x, z) => map.height(x, z);
    // ---------------- dusk over a dead city
    this.sunDir = new THREE.Vector3(-.55, .28, -.78).normalize();
    const sky = atmosphereSky('#2a2140', '#c9765a', '#ffb58a', this.sunDir); sc.add(sky); this.sky = sky;
    sc.fog = new THREE.Fog(new THREE.Color('#7a5e6a'), 120, 2600); this.fogBase = [120, 2600];
    sc.add(new THREE.HemisphereLight(0xb7a2c8, 0x3a2e2a, 1.0));
    const sun = new THREE.DirectionalLight(0xffc29a, 2.4);
    sun.castShadow = true; const q = g.renderer.q; sun.shadow.mapSize.set(q.shadow, q.shadow);
    Object.assign(sun.shadow.camera, { left: -70, right: 70, top: 70, bottom: -70, near: 10, far: 500 });
    sun.shadow.bias = -.0005; sun.shadow.normalBias = .08;
    sc.add(sun, sun.target); this.sun = sun;
    await tick(.08, 'Mapping the ruins');
    await Water.load(A);
    this.buildTerrain();
    await tick(.2, 'Tracing the highways');
    this.buildRoads();
    this.buildHighways();
    await tick(.32, 'Raising the Spire');
    this.buildSpire();
    // ---------------- districts (independent modules)
    const kit = A.models.vanthos.scene;
    for (const n of ['VX_res_a', 'VX_res_b', 'VX_res_c', 'VX_res_ruin', 'VX_res_market', 'VX_com_a', 'VX_com_b', 'VX_com_c', 'VX_com_ruin',
      'VX_ind_factory', 'VX_ind_refinery', 'VX_ind_warehouse', 'VX_ind_power', 'VX_mil_bunker', 'VX_mil_tower', 'VX_mil_depot',
      'VX_lab_a', 'VX_lab_containment', 'VX_hospital', 'VX_organism']) {
      const root = kit.getObjectByName(n); root.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(root), c = root.getWorldPosition(new THREE.Vector3());
      this.kitInfo.set(n, { root, size: box.getSize(new THREE.Vector3()), off: box.getCenter(new THREE.Vector3()).sub(c) });
      this.kitMats.set(n, []);
    }
    this.styleKit(kit);
    let di = 0;
    for (const D of DISTRICTS) {
      await tick(.36 + di++ * .06, 'Restoring ' + D.name);
      D.populate.call(D, this.context(D));
    }
    for (const [n, mats] of this.kitMats) instanceKit(sc, this.kitInfo.get(n).root, mats);
    await tick(.86, 'Charting the districts');
    this.minimap = this.drawMinimap();
    // landing site: the jumpship on the southern highway, in the Outskirts
    const a = HIGHWAYS[0], r = 1720, lx = Math.cos(a) * r + 30, lz = Math.sin(a) * r;
    const ly = map.height(lx, lz);
    const js = A.clone('ship_jumper'); js.position.set(lx, ly, lz); js.rotation.y = -a + Math.PI / 2; sc.add(js);
    for (let t = -6; t <= 6; t += 3) this.collision.add([lx - 2, ly, lz - 2 + t, lx + 2, ly + 4, lz + 2 + t], 'ship');
    this.landing = new THREE.Vector3(lx - 12, ly, lz);
    this.interactables.push({ id: 'ship', pos: this.landing, r: 3.5, label: 'The Wayfarer', verb: 'Return to orbit', key: 'E', action: () => g.travel('ship') });
    // the mission: Operation Heartline (operation.js) runs from the landing zone to the Spire on every visit
    await tick(.9, 'Briefing the operation');
    this.op = new Operation(this); this.op.build();
    // a pool of point lights shared by every district (nearest ones are switched on)
    this.lightPool = [];
    for (let i = 0; i < 6; i++) { const L = new THREE.PointLight(0xffffff, 0, 40, 1.6); sc.add(L); this.lightPool.push(L); }
    // reflections
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    this.envRT = pm.fromScene(new THREE.Scene().add(atmosphereSky('#2a2140', '#c9765a', '#ffb58a', this.sunDir)), .04);
    sc.environment = this.envRT.texture; sc.environmentIntensity = .7;
    pm.dispose(); this.disposables.push(this.envRT);
    g.vehicles.clear();
    progress(1, 'Ready');
  }

  styleKit(kit) {
    const T = this.g.assets.textures;
    this.pulseMats = [];
    kit.traverse(o => {
      if (!o.isMesh || o.material.userData.styled) return;
      const m = o.material; m.userData.styled = true;
      if (m.name === 'facade') { m.color.set(0x7d838b); m.emissiveMap = T.facade_e; m.emissive = new THREE.Color(1, .7, .45); m.emissiveIntensity = .35; m.needsUpdate = true; }
      if (m.name === 'ribbon') { m.color.set(0x8a96a6); m.emissiveMap = T.ribbon_e; m.emissive = new THREE.Color(.6, .8, 1); m.emissiveIntensity = .3; m.needsUpdate = true; }
      if (/alien_glow|alien_acid|core_glow|holo_ad/.test(m.name)) this.pulseMats.push({ m, base: m.emissiveIntensity || 1, ph: Math.random() * 6 });
    });
  }

  // ---------------------------------------------------------------- district context (the API districts build with)
  context(D) {
    const g = this.g, A = g.assets, map = this.map, sc = this.scene;
    const rnd = mulberry(D.id.split('').reduce((a, c) => a * 31 + c.charCodeAt(0), 7) >>> 0);
    const lots = map.lots.filter(l => l.district === D);
    for (let i = lots.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [lots[i], lots[j]] = [lots[j], lots[i]]; }
    const blocks = map.blocks.filter(b => b.district === D);
    const self = this;
    const groundAt = (x, z) => Math.max(map.height(x, z), map.flooded(x, z) > .3 ? -2.4 : -99);
    const ctx = {
      rnd,
      takeLot(pred) { const i = pred ? lots.findIndex(pred) : 0; if (i < 0 || !lots.length) return null; return lots.splice(i, 1)[0]; },
      building(kit, x, z, rot, fit) {
        const K = self.kitInfo.get(kit); if (!K) return null;
        const sw = Math.abs(Math.cos(rot)) > .5 ? K.size.x : K.size.z, sd = Math.abs(Math.cos(rot)) > .5 ? K.size.z : K.size.x;
        const s = fit ? Math.min(1, fit / Math.max(sw, sd)) : 1;
        const y = Math.min(map.height(x, z), 0);
        self.kitMats.get(kit).push(new THREE.Matrix4().compose(_p.set(x, y, z), _q.setFromAxisAngle(Y, rot), _s.set(s, s, s)));
        const h = K.size.y * s;
        self.collision.add([x - sw * s / 2, y - 3, z - sd * s / 2, x + sw * s / 2, y + h, z + sd * s / 2], 'building');
        return { h: y + h, top: y + h, x, z, w: sw * s, d: sd * s };
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
        if (side < 2) return { x: b.x + (side ? 1 : -1) * (BW / 2 + STREET / 2), z: b.z + along * BD };
        return { x: b.x + along * BW, z: b.z + (side === 3 ? 1 : -1) * (BD / 2 + STREET / 2) };
      },
      horror(x, z) { self.horrorT = 70; g.hud.toast('The emergency lights flicker. Something is moving inside.'); g.audio.alert && g.audio.alert(new THREE.Vector3(x, 1, z)); },
    };
    return ctx;
  }

  // ---------------------------------------------------------------- terrain, roads, highways
  buildTerrain() {
    const sc = this.scene, T = this.g.assets.textures, map = this.map;
    const S = 4800, N = 300;
    const geo = new THREE.PlaneGeometry(S, S, N, N); geo.rotateX(-Math.PI / 2);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) pos.setY(i, map.height(pos.getX(i), pos.getZ(i)) - (Math.hypot(pos.getX(i), pos.getZ(i)) < map.edge(Math.atan2(pos.getZ(i), pos.getX(i))) - 60 ? .06 : 0));
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ map: T.asphalt, normalMap: T.asphalt_n, roughness: .9, color: 0x8a8486 });
    mat.onBeforeCompile = sh => {
      sh.uniforms.rockMap = { value: T.rock }; sh.uniforms.sandMap = { value: T.sand };
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;uniform sampler2D rockMap,sandMap;')
        .replace('#include <map_fragment>', `
          vec2 uv=vWP.xz*.08;vec3 city=texture2D(map,uv).rgb*texture2D(map,uv*.21+.3).rgb*1.6;
          vec3 waste=mix(texture2D(sandMap,vWP.xz*.05).rgb*vec3(.8,.7,.65),texture2D(rockMap,vWP.xz*.03).rgb*vec3(.7,.62,.6),smoothstep(4.,30.,vWP.y));
          float r=length(vWP.xz);float out1=smoothstep(1780.,1960.,r+sin(atan(vWP.z,vWP.x)*3.)*110.);
          float crater=1.-smoothstep(${(CRATER_R - 30).toFixed(1)},${(CRATER_R + 20).toFixed(1)},r);
          vec3 burnt=texture2D(rockMap,vWP.xz*.06).rgb*vec3(.45,.36,.42);
          diffuseColor.rgb*=mix(mix(city,waste,out1),burnt,crater*step(${SPIRE_R.toFixed(1)},r));`);
    };
    const t = new THREE.Mesh(geo, mat); t.receiveShadow = true; sc.add(t); this.terrain = t;
    // flood water over the sunken district
    const D = DISTRICTS.find(d => d.id === 'flooded');
    const wgeo = new THREE.RingGeometry(CROWN_R - 10, OUTER_R + 10, 64, 1, -D.a1 * Math.PI / 180, (D.a1 - D.a0) * Math.PI / 180);
    wgeo.rotateX(-Math.PI / 2);
    // shared water surface (src/game/water.js): murky flood water with ripples and splashes; depth sampled over the sector
    const arc = []; for (let k = 0; k <= 12; k++) { const a = (D.a0 + (D.a1 - D.a0) * k / 12) * Math.PI / 180; for (const R of [CROWN_R - 12, OUTER_R + 12]) arc.push([Math.cos(a) * R, Math.sin(a) * R]); }
    const bounds = [Math.min(...arc.map(a => a[0])), Math.min(...arc.map(a => a[1])), Math.max(...arc.map(a => a[0])), Math.max(...arc.map(a => a[1]))];
    this.water = new Water(this.g, sc, { level: WATER_Y, ground: (x, z) => map.height(x, z), inside: (x, z) => map.flooded(x, z) > .02, bounds, res: 320,
      deep: 0x0b1916, shallow: 0x34402f, foamColor: 0xd9d6c6, caps: 0, swell: .32, clarity: 1.4, sunDir: this.sunDir, sunColor: 0xffc29a, vfxLight: 0xd8cfc8 });
    this.water.addSurface(wgeo);
    // world edge walls in the badlands
    for (let k = 0; k < 24; k++) {
      const a = k / 24 * Math.PI * 2, R = 2380;
      const x = Math.cos(a) * R, z = Math.sin(a) * R;
      this.collision.add([x - 340, -50, z - 340, x + 340, 300, z + 340], 'edge');
    }
  }

  buildRoads() {
    const sc = this.scene, T = this.g.assets.textures, map = this.map;
    const asph = T.asphalt.clone(); asph.wrapS = asph.wrapT = THREE.RepeatWrapping; asph.repeat.set(40, 40); asph.needsUpdate = true;
    const roadMat = new THREE.MeshStandardMaterial({ map: asph, roughness: .85, color: 0x5a5658, polygonOffset: true, polygonOffsetFactor: -2 });
    // the two ring roads
    for (const R of [CROWN_R, OUTER_R]) {
      const geo = new THREE.RingGeometry(R - MAJOR / 2, R + MAJOR / 2, 256, 1); geo.rotateX(-Math.PI / 2);
      const pos = geo.attributes.position;
      for (let i = 0; i < pos.count; i++) pos.setY(i, Math.max(map.height(pos.getX(i), pos.getZ(i)), -2.35) + .05);
      const m = new THREE.Mesh(geo, roadMat); m.receiveShadow = true; sc.add(m);
    }
    // block pads: lighter concrete lots with kerbs; the dark ground between them reads as streets and alleys
    const conc = T.concrete.clone(); conc.wrapS = conc.wrapT = THREE.RepeatWrapping; conc.repeat.set(8, 10); conc.needsUpdate = true;
    const padGeo = new THREE.PlaneGeometry(BW, BD); padGeo.rotateX(-Math.PI / 2);
    const pad = new THREE.InstancedMesh(padGeo, new THREE.MeshStandardMaterial({ map: conc, color: 0x9a948c, roughness: .92, polygonOffset: true, polygonOffsetFactor: -1 }), map.blocks.length);
    map.blocks.forEach((b, i) => pad.setMatrixAt(i, _m.makeTranslation(b.x, Math.max(map.height(b.x, b.z), -2.38) + .04, b.z)));
    pad.receiveShadow = true; pad.computeBoundingSphere(); sc.add(pad);
    // blocked intersections and rubble on the streets
    const kit = this.g.assets.models.vanthos.scene, rb = [], rd = [];
    const rnd = mulberry(77);
    for (let i = 0; i < 70; i++) {
      const b = map.blocks[Math.floor(rnd() * map.blocks.length)];
      const x = b.x + BW / 2 + STREET / 2, z = b.z + BD / 2 + STREET / 2;
      (i % 3 ? rb : rd).push(new THREE.Matrix4().compose(_p.set(x, Math.max(map.height(x, z), -2.4), z), _q.setFromAxisAngle(Y, rnd() * 6), _s.set(1, 1, 1)));
      if (i % 3 === 0) this.collision.add([x - 7, -3, z - 2, x + 7, 1.2, z + 2], 'barrier');
    }
    instanceKit(sc, kit.getObjectByName('VX_rubble'), rb);
    instanceKit(sc, kit.getObjectByName('VX_roadblock'), rd);
  }

  buildHighways() {
    const sc = this.scene, T = this.g.assets.textures, map = this.map, A = this.g.assets;
    const kit = A.models.vanthos.scene;
    const asph = T.asphalt.clone(); asph.wrapS = asph.wrapT = THREE.RepeatWrapping; asph.repeat.set(2, 1); asph.needsUpdate = true;
    const mat = new THREE.MeshStandardMaterial({ map: asph, roughness: .85, color: 0x605a5c, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2 });
    const segs = [], broken = [], H = 12;
    const E0 = 700, E1 = 1320;                   // elevated between these radii
    for (const [hi, a] of HIGHWAYS.entries()) {
      const dx = Math.cos(a), dz = Math.sin(a), nx = -dz, nz = dx;
      // ground ribbon (with the ramps) from the Crown out to the badlands
      const pts = [];
      for (let r = 130; r <= 2300; r += 10) {
        let y = Math.max(map.height(dx * r, dz * r), -2.35) + .06;
        if (r > E0 - 90 && r < E1 + 90) {
          const t = r < E0 ? (r - (E0 - 90)) / 90 : r > E1 ? ((E1 + 90) - r) / 90 : 1;
          y = Math.max(y, H * Math.min(1, Math.max(0, t)));
        }
        pts.push([r, y]);
      }
      const pos = [], uv = [], idx = [];
      pts.forEach(([r, y], i) => {
        for (const s of [-1, 1]) { pos.push(dx * r + nx * s * MAJOR / 2, y, dz * r + nz * s * MAJOR / 2); uv.push(s < 0 ? 0 : 1, r / 25); }
        if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
      });
      // skip the deck where a section has collapsed (the gap players must route around)
      const gapR = 960 + hi * 70;
      const keep = []; for (let i = 0; i < idx.length; i += 6) { const r = pts[Math.floor(idx[i] / 2)][0]; if (Math.abs(r - gapR) > 25) keep.push(...idx.slice(i, i + 6)); }
      const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
      geo.setIndex(keep); geo.computeVertexNormals();
      const m = new THREE.Mesh(geo, mat); m.receiveShadow = true; m.castShadow = true; sc.add(m);
      // pillars, barriers and broken section from the kit; walkable colliders along the deck and ramps
      const rot = Math.atan2(-dx, -dz);
      for (let r = E0 + 25; r < E1; r += 50) {
        const M = new THREE.Matrix4().compose(_p.set(dx * r, 0, dz * r), _q.setFromAxisAngle(Y, rot), _s.set(1, 1, 1));
        if (Math.abs(r - gapR) < 26) broken.push(M); else segs.push(M);
      }
      // walkable deck: fine steps on the ramps (step-up height), coarser on the flat elevated part
      for (let r = E0 - 90; r <= E1 + 90; r += (r < E0 || r > E1) ? 1.5 : 6) {
        if (Math.abs(r - gapR) < 25) continue;
        const t = r < E0 ? (r - (E0 - 90)) / 90 : r > E1 ? ((E1 + 90) - r) / 90 : 1, y = H * Math.min(1, Math.max(0, t));
        if (y < .35) continue;
        for (const s2 of [-6.5, 6.5]) { const x = dx * r + nx * s2, z = dz * r + nz * s2; this.collision.add([x - 6, y - 1.4, z - 6, x + 6, y, z + 6], 'deck'); }
      }
    }
    instanceKit(sc, kit.getObjectByName('VX_hwy'), segs);
    instanceKit(sc, kit.getObjectByName('VX_hwy_broken'), broken);
  }

  buildSpire() {
    const g = this.g, A = g.assets, sc = this.scene;
    const sp = A.clone('vanthos', 'VX_spire'); sc.add(sp); this.spire = sp;
    sp.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    // foundation: a walkable disc, its cap 29 m up (VX_spire foundcap); towers as solid boxes
    for (let x = -88; x <= 88; x += 22) for (let z = -88; z <= 88; z += 22) if (Math.hypot(x, z) < 86) this.collision.add([x - 11, -2, z - 11, x + 11, 29, z + 11], 'spire');
    // the rim: the square grid above leaves the edge of the round cap (r 88) unwalkable in places
    for (let k = 0; k < 48; k++) { const a = k / 48 * Math.PI * 2, x = Math.cos(a) * 81, z = Math.sin(a) * 81; this.collision.add([x - 6, -2, z - 6, x + 6, 29, z + 6], 'spire'); }
    const towers = [[0, 240], [1.26, 290], [2.51, 300 * .62], [3.77, 260], [5.03, 230 * .62]];
    for (const [a, h] of towers) { const x = Math.cos(a) * 52, z = -Math.sin(a) * 52; this.collision.add([x - 19, 28, z - 19, x + 19, 28 + h, z + 19], 'spire'); }
    this.collision.add([-25, 28, -25, 25, 360, 25], 'spire');
    this.coreLight = new THREE.PointLight(0x7fe8ff, 8000, 900, 1.4); this.coreLight.position.set(0, 380, 0); sc.add(this.coreLight);
    // the lift up to the foundation (powered during the operation); the Spire Warden and its reliquary are operation.js
    const lift = this.makeLift(0, 100, 29, 0, 76);
    this.spireLiftBase = lift.base;
    this.spireLift = new THREE.Vector3(0, 0, 100); this.spireLift.y = this.map.height(0, 100);
  }

  // ---------------------------------------------------------------- interactables
  makeLift(x, z, top, rx = x - 6, rz = z) {
    const g = this.g, A = g.assets, sc = this.scene;
    const y0 = Math.max(this.map.height(x, z), -2.4);
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

  // ---------------------------------------------------------------- streaming of the living city
  spawnSite(st) {
    const g = this.g;
    st.spawned = true; st.live = [];
    const lvl = this.levelAt(st.pos.x, st.pos.z, st.D);
    const group = [];
    for (let k = 0; k < st.n; k++) {
      const type = st.types[k % st.types.length];
      const a = k / st.n * Math.PI * 2, r = st.n > 1 ? 3 + Math.random() * 4 : 0;
      const p = st.pos.clone().add(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r));
      if (st.pos.y < 20) p.y = Math.max(this.map.height(p.x, p.z), -2.4);
      const e = g.enemies.spawn(type, p, lvl, { group, onDeath: () => this.onSiteDeath(st, e) });
      if (st.o.boss) {
        const B = st.o.boss; e.T = { ...e.T, name: B.name, scale: (e.T.scale || 1) * B.scale, loot: 1 };
        e.maxHp = e.hp = Math.round(e.maxHp * B.hpMul); e.boss = B.name;
        if (e.av) e.av.root.scale.setScalar(B.scale);
      }
      if (st.o.awake) e.state = 'combat';
      if (st.o.ambush && e.av) { e.ambush = true; }
      group.push(e); st.live.push(e);
    }
  }

  onSiteDeath(st, e) {
    const g = this.g;
    if (e.boss) {
      g.save.vanthos.bosses.push(e.boss);
      g.hud.banner(e.boss + ' defeated', 'Its vault is open', 4);
      g.gain('xp', 1500); g.gain('credits', 900, true);
      g.combat.spawnPickup(e.pos.clone().setY(e.pos.y + 1), 'core', { rarity: 4, level: e.level });
    }
    if (st.live.every(x => !x.alive)) st.cleared = true;
  }

  stream() {
    const p = this.g.player.pos;
    for (const st of this.sites) {
      if (st.cleared || st.off) continue;           // `off`: kept clear for the operation's route and arenas
      const d = Math.hypot(st.pos.x - p.x, st.pos.z - p.z);
      if (!st.spawned && d < STREAM_IN) this.spawnSite(st);
      else if (st.spawned && d > STREAM_OUT) {
        const set = new Set(st.live);
        this.g.enemies.removeWhere(e => set.has(e) && e.state !== 'combat');
        st.live = st.live.filter(e => e.alive && this.g.enemies.list.includes(e));
        if (!st.live.length) st.spawned = false;
      }
    }
  }

  onFoundation() { const p = this.g.player.pos; return p.y > 20 && Math.hypot(p.x, p.z) < 97; }

  // leaving for the metro keeps the operation's stage (the city is rebuilt on the way back up)
  depart(id) { if (id === 'vanthos_metro' && this.op && !this.op.complete) this.g.opResume = this.op.snapshot(); }

  barTargets() { return this.op ? this.op.barTargets() : []; }

  // ---------------------------------------------------------------- world event on the outer highway
  startEvent() {
    const g = this.g, p = g.player.pos;
    let best = null, bd = 1e9;
    for (const a of HIGHWAYS) for (let r = 1500; r < 2200; r += 50) {
      const x = Math.cos(a) * r, z = Math.sin(a) * r, d = Math.hypot(x - p.x, z - p.z);
      if (d > 90 && d < bd) { bd = d; best = [x, z, a]; }
    }
    if (!best || bd > 600) return;
    const [x, z, a] = best;
    const apc = A => { const o = g.assets.clone('vanthos', 'VX_apc'); o.position.set(x, this.map.height(x, z), z); o.rotation.y = -a; this.scene.add(o); return o; };
    const obj = apc();
    const st = { D: DISTRICTS.find(d => d.id === 'outskirts'), types: ['trooper', 'brute', 'trooper'], pos: new THREE.Vector3(x + 6, this.map.height(x, z), z), n: 7, o: { awake: false }, live: [], cleared: false, spawned: false };
    this.sites.push(st); this.spawnSite(st);
    this.event = { st, pos: st.pos, obj, t: 0 };
    g.hud.banner('World event', 'Raider convoy on the outer highway', 4);
  }

  // ---------------------------------------------------------------- per frame
  update(dt) {
    const g = this.g, p = g.player;
    if (this.water) this.water.update(dt);
    this.sky.position.copy(g.camera.position);
    this.sky.material.uniforms.time.value = g.time;
    const c = p.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : p.pos;
    this.sun.target.position.set(Math.round(c.x / 4) * 4, c.y, Math.round(c.z / 4) * 4);
    this.sun.position.copy(this.sun.target.position).addScaledVector(this.sunDir, 260);
    // district: HUD name, faction wars, danger
    const D = this.map.district(c.x, c.z);
    if (D !== this.D) {
      this.D = D; g.hud.setLocation(this.region, D.name);
      g.hud.toast(D.name + ' — ' + D.blurb);
    }
    this.factionWar = !!D.factionWar;
    // stream enemy packs every few frames
    this.streamT = (this.streamT || 0) - dt;
    if (this.streamT <= 0) { this.streamT = .5; this.stream(); }
    if (this.op) { this.op.update(dt); g.hud.bossBar(this.op.bossBar()); }
    // ambushers stay still and hidden until the player is close
    for (const e of g.enemies.list) if (e.ambush && e.state === 'idle' && e.alive && e.pos.distanceTo(p.pos) < 16) { e.ambush = false; e.alert(); g.hud.toast('Ambush!'); }
    // the nearest district lights take the pooled point lights
    this.lightT = (this.lightT || 0) - dt;
    if (this.lightT <= 0) { this.lightT = .4; this.near = this.lights.map(L => [L, L.pos.distanceToSquared(p.pos)]).sort((a, b) => a[1] - b[1]).slice(0, this.lightPool.length).map(x => x[0]); }
    (this.near || []).forEach((L, i) => {
      const P = this.lightPool[i]; P.position.copy(L.pos); P.color.copy(L.color);
      P.intensity = L.intensity * 60 * (L.flicker ? (Math.sin(g.time * 23 + i) > .2 ? 1 : .15) : 1);
    });
    for (let i = (this.near || []).length; i < this.lightPool.length; i++) this.lightPool[i].intensity = 0;
    // triggers (the hospital, ...)
    for (const t of this.triggers) if (!t.done && Math.hypot(t.x - p.pos.x, t.z - p.pos.z) < t.r) { t.done = true; t.fn(); }
    // horror: fog closes in, then lifts
    if (this.horrorT > 0) { this.horrorT -= dt; const k = Math.min(1, this.horrorT / 5, (70 - this.horrorT) / 3); this.scene.fog.near = this.fogBase[0] * (1 - k) + 6 * k; this.scene.fog.far = this.fogBase[1] * (1 - k) + 70 * k; }
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
    // alien growth breathes, holograms flicker, the core throbs
    for (const P of this.pulseMats) P.m.emissiveIntensity = P.base * (.7 + .3 * Math.sin(g.time * 2.2 + P.ph));
    this.coreLight.intensity = 8000 * (.85 + .15 * Math.sin(g.time * 1.3));
    // world event
    this.eventT -= dt;
    // (the convoy only rolls once the operation is done: it would swamp the route)
    if (!this.event && this.eventT <= 0) { this.eventT = 240 + Math.random() * 120; if (Math.hypot(p.pos.x, p.pos.z) > 1250 && (!this.op || this.op.complete)) this.startEvent(); }
    if (this.event && this.event.st.cleared) {
      const e = this.event; this.event = null;
      g.hud.banner('Convoy destroyed', 'Salvage dropped', 3); g.gain('xp', 600); g.gain('credits', 300, true);
      g.combat.spawnPickup(e.pos.clone().setY(e.pos.y + 1), 'core', { rarity: 3, level: this.levelAt(e.pos.x, e.pos.z) });
    }
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
    const p = this.g.player.pos, m = [{ pos: new THREE.Vector3(0, 0, 0), icon: '◆', color: '#7fe8ff' }, { pos: this.landing, icon: '▲', color: '#1ad8ff' }];
    if (this.op) m.push(...this.op.markers());
    if (this.event) m.push({ pos: this.event.pos, icon: '✖', color: '#ff4a3d' });
    for (const q of this.metros || []) if (q.distanceTo(p) < 260) m.push({ pos: q, icon: 'M', color: '#e3c26c' });
    for (const c of this.caches) if (!c.open && c.pos.distanceTo(p) < 140) m.push({ pos: c.pos, icon: '◆', color: '#ffae2f' });
    return m;
  }

  objectives() {
    const g = this.g, p = g.player.pos, D = this.D || DISTRICTS[0];
    const o = [...(this.op ? this.op.objectives() : []),
      { text: D.name, sub: 'Threat level ' + this.levelAt(p.x, p.z, D) + (D.factionWar ? ' · rival factions at war' : '') },
      { text: 'Memory shards', sub: g.save.vanthos.shards.length + ' / 12 · hidden in the Flooded District' }];
    if (this.event) o.push({ text: 'World event: raider convoy', sub: 'Outer highway' });
    return o;
  }

  drawMinimap() {
    const S = 600, W = 4800, half = W / 2, c = document.createElement('canvas'); c.width = c.height = S;
    const x = c.getContext('2d'), map = this.map;
    const toPx = (wx, wz) => [(wx + half) / W * S, (wz + half) / W * S];
    x.fillStyle = '#3a302c'; x.fillRect(0, 0, S, S);
    const cols = { crown: '#5a5f6e', old: '#6a5a50', commercial: '#4e5a6e', flooded: '#2c4a56', research: '#5e6a6a', military: '#4e5446', industrial: '#5e5248', outskirts: '#4a4440' };
    for (let j = 0; j < S; j += 3) for (let i = 0; i < S; i += 3) {
      const wx = -half + i / S * W, wz = -half + j / S * W, r = Math.hypot(wx, wz);
      if (r > map.edge(Math.atan2(wz, wx)) - 40) continue;
      x.fillStyle = r < CRATER_R ? '#241c22' : (cols[map.district(wx, wz).id] || '#555'); x.fillRect(i, j, 3, 3);
    }
    x.fillStyle = 'rgba(200,190,180,.55)';
    for (const b of map.blocks) { const [a, bb] = toPx(b.x - BW / 2, b.z - BD / 2); x.fillRect(a, bb, BW / W * S, BD / W * S); }
    x.strokeStyle = '#1e1a1c'; x.lineWidth = MAJOR / W * S;
    for (const R of [CROWN_R, OUTER_R]) { x.beginPath(); x.arc(S / 2, S / 2, R / W * S, 0, 7); x.stroke(); }
    for (const a of HIGHWAYS) { const [a1, b1] = toPx(Math.cos(a) * 130, Math.sin(a) * 130), [a2, b2] = toPx(Math.cos(a) * 2300, Math.sin(a) * 2300); x.beginPath(); x.moveTo(a1, b1); x.lineTo(a2, b2); x.stroke(); }
    x.fillStyle = '#7fe8ff'; x.beginPath(); x.arc(S / 2, S / 2, 5, 0, 7); x.fill();
    return { canvas: c, scale: S / W, half };
  }

  dispose() {
    const h = this.g.hud; h.bossBar(null); h.clearRadio(); h.hideLore();
    this.op && this.op.dispose(); this.water && this.water.dispose(); super.dispose();
  }
}
