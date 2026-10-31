// Earth - New Meridian: a free-roam island. The city in the middle, three villages, four farms, forests,
// wind farms and the bay, joined by highways. No missions: walk, drive, steal cars, cause trouble.
import * as THREE from 'three';
import { World } from './world.js';
import { atmosphereSky } from './sky.js';
import { mulberry } from '../game/state.js';
import { Avatar } from '../game/avatar.js';
import { MeridianMap, VILLAGES, FARMS, HALF, SIZE, SEA, BLOCK, ROAD, CITY_N as N, PITCH, CITY_EDGE, fbm, RIVER_Z, RIVER_W, RIVER_BANK } from './meridian/layout.js';
import { Population } from './meridian/population.js';
import { Traffic } from './meridian/traffic.js';
import { Wanted } from './meridian/wanted.js';

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), _v = new THREE.Vector3();
const Y = new THREE.Vector3(0, 1, 0);

// Instance every mesh under a kit root at the given matrices (one draw call per material).
function instanceKit(scene, root, mats, { shadow = true, chunk = 0 } = {}) {
  if (!mats.length) return [];
  root.updateMatrixWorld(true);
  const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
  const groups = new Map();
  if (chunk) for (const m of mats) { _p.setFromMatrixPosition(m); const k = Math.floor(_p.x / chunk) + ',' + Math.floor(_p.z / chunk); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(m); }
  else groups.set('all', mats);
  const out = [];
  root.traverse(o => {
    if (!o.isMesh) return;
    const local = new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld);
    for (const list of groups.values()) {
      const im = new THREE.InstancedMesh(o.geometry, o.material, list.length);
      list.forEach((pm, i) => im.setMatrixAt(i, _m.multiplyMatrices(pm, local)));
      im.castShadow = shadow && !/glass|window|light|glow/.test(o.material.name); im.receiveShadow = true;
      im.computeBoundingSphere(); im.computeBoundingBox && im.computeBoundingBox();
      im.geometry.userData.shared = true;
      scene.add(im); out.push(im);
    }
  });
  return out;
}

function terrainMaterial(T) {
  const grass = T.moss.clone(), grassN = T.moss_n.clone(), rock = T.rock, rockN = T.rock_n, sand = T.sand;
  const mat = new THREE.MeshStandardMaterial({ map: grass, normalMap: grassN, roughness: .95, color: 0x8fae6a, envMapIntensity: .25 });
  mat.onBeforeCompile = sh => {
    sh.uniforms.rockMap = { value: rock }; sh.uniforms.rockN = { value: rockN }; sh.uniforms.sandMap = { value: sand };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;varying vec3 vWN;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;vWN=normalize(mat3(modelMatrix)*objectNormal);');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;varying vec3 vWN;uniform sampler2D rockMap,rockN,sandMap;')
      .replace('#include <map_fragment>', `
        vec2 uvG=vWP.xz*.11;vec3 gc=texture2D(map,uvG).rgb*texture2D(map,uvG*.13+.27).rgb*2.4;
        float meadow=.5+.5*sin(vWP.x*.004)*cos(vWP.z*.005);gc*=mix(vec3(1.),vec3(1.12,1.05,.75),meadow*.6);
        float slope=1.-vWN.y;float rk=smoothstep(.22,.42,slope);
        vec3 an=abs(vWN);vec2 uvR=(an.x>an.z?vWP.zy:vWP.xy)*.08;vec3 rc=texture2D(rockMap,uvR).rgb*vec3(.95,.92,.88);
        float beach=1.-smoothstep(${(SEA + 1.2).toFixed(1)},${(SEA + 3.5).toFixed(1)},vWP.y);vec3 sc2=texture2D(sandMap,vWP.xz*.12).rgb*vec3(1.,.95,.85);
        vec3 col=mix(gc,rc*1.15,rk);col=mix(col,sc2,beach);
        diffuseColor.rgb*=col/max(diffuse,vec3(.05));`)
      .replace('#include <normal_fragment_maps>', `
        vec3 nG=texture2D(normalMap,uvG).xyz*2.-1.;vec3 nR=texture2D(rockN,uvR).xyz*2.-1.;
        vec3 mapN=normalize(mix(nG,nR,rk));mapN.xy*=normalScale;normal=normalize(tbn*mapN);`);
  };
  return mat;
}

export class EarthWorld extends World {
  constructor(game) {
    super(game);
    this.kind = 'city'; this.name = 'New Meridian'; this.region = 'Earth';
    this.combat = true; this.allowCars = true; this.surface = 'concrete';
    this.level = 2; this.destPower = 0;
  }

  async build(progress) {
    const g = this.g, A = g.assets, sc = this.scene, rnd = mulberry(4242);
    const T = A.textures;
    const tick = async (p, l) => { progress(p, l); await new Promise(r => setTimeout(r, 0)); };
    await tick(.03, 'Surveying the island');
    const map = this.map = new MeridianMap();
    this.collision.terrain = (x, z) => map.height(x, z);
    // ---------------- light: late golden hour
    this.sunDir = new THREE.Vector3(-.55, .34, -.45).normalize();
    const sky = atmosphereSky('#3a6aa8', '#f2b27a', '#ffd9a8', this.sunDir); sc.add(sky); this.sky = sky;
    sc.fog = new THREE.Fog(0xd9a888, 160, 1300);
    sc.add(new THREE.HemisphereLight(0x9cb8e0, 0x5a4636, .95));
    const sun = new THREE.DirectionalLight(0xffd2a0, 3.0);
    sun.castShadow = true;
    const q = g.renderer.q; sun.shadow.mapSize.set(q.shadow, q.shadow);
    Object.assign(sun.shadow.camera, { left: -80, right: 80, top: 80, bottom: -80, near: 10, far: 600 });
    sun.shadow.bias = -.0004; sun.shadow.normalBias = .06;
    sc.add(sun, sun.target); this.sun = sun;
    await tick(.1, 'Raising hills');
    // ---------------- terrain (8 m mesh over the 4 m height grid) in 4x4 tiles for culling
    const tmat = terrainMaterial(T);
    const TILES = 4, TS = SIZE / TILES, SEG = 88;
    for (let ti = 0; ti < TILES; ti++) for (let tj = 0; tj < TILES; tj++) {
      const geo = new THREE.PlaneGeometry(TS, TS, SEG, SEG); geo.rotateX(-Math.PI / 2);
      const ox = -HALF + TS * (ti + .5), oz = -HALF + TS * (tj + .5);
      const pos = geo.attributes.position;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i) + ox, z = pos.getZ(i) + oz;
        // in the city the concrete slab is the ground; sink the terrain a hair under it
        pos.setY(i, map.height(x, z) - (Math.abs(x) < CITY_EDGE + 20 && Math.abs(z) < CITY_EDGE + 20 ? .15 : 0));
      }
      geo.computeVertexNormals();
      const t = new THREE.Mesh(geo, tmat); t.position.set(ox, 0, oz); t.receiveShadow = true;
      sc.add(t);
    }
    // the bay all around the island
    const water = new THREE.Mesh(new THREE.PlaneGeometry(SIZE * 3, SIZE * 3), new THREE.MeshStandardMaterial({ color: 0x1d4a5e, roughness: .08, metalness: .2, envMapIntensity: 1.2 }));
    water.rotation.x = -Math.PI / 2; water.position.y = SEA; sc.add(water); this.water = water;
    // island edge walls (beyond the beach)
    const E = HALF - 30;
    for (const [x0, z0, x1, z1] of [[-E - 5, -E - 5, E + 5, -E], [-E - 5, E, E + 5, E + 5], [-E - 5, -E, -E, E], [E, -E, E + 5, E]]) this.collision.add([x0, -50, z0, x1, 200, z1], 'edge');
    await tick(.2, 'Paving the city');
    this.buildCity(rnd);
    await tick(.42, 'Laying highways');
    this.buildHighways();
    await tick(.5, 'Building villages');
    this.paths = this.cityPaths();
    this.buildVillages(rnd);
    await tick(.6, 'Planting fields');
    this.buildFarms(rnd);
    await tick(.7, 'Growing forests');
    this.buildForests(rnd);
    this.buildTurbines(rnd);
    await tick(.78, 'Opening the spaceport');
    this.buildSpaceport();
    await tick(.84, 'Waking the city');
    // skyway traffic overhead (decoration) + parked cars at the kerbs
    this.skyway = [];
    const paints = ['#a3121f', '#2a4f7a', '#e8e2d4', '#1c1f24', '#c79a45', '#2f6b55', '#6a4fa0'];
    for (let k = 0; k < 10; k++) {
      const c = A.clone(k % 2 ? 'car_utility' : 'car_sport');
      c.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); o.castShadow = false; if (o.material.name === 'car_paint') o.material.color.set(paints[k % paints.length]); } });
      sc.add(c);
      const axis = k % 2, lane = (Math.floor(rnd() * (2 * N + 2)) - N - 1 + .5) * PITCH, dir = rnd() < .5 ? 1 : -1;
      this.skyway.push({ obj: c, axis, lane: lane + dir * 3, dir, t: (rnd() - .5) * CITY_EDGE * 2, speed: 20 + rnd() * 14, alt: 22 + (k % 3) * 7 });
    }
    g.vehicles.clear();
    for (let k = 0; k < 14; k++) {
      const lane = map.lanes.filter(l => l.city)[Math.floor(rnd() * 40)];
      const s = 20 + rnd() * (lane.total - 40);
      map.lanePoint(lane, s, _p, _v);
      const side = new THREE.Vector3(-_v.z, 0, _v.x);
      _p.addScaledVector(side, 3.4);
      if (Math.abs(_p.x) < 30 && Math.abs(_p.z) < 40) continue;
      g.vehicles.spawn(rnd() < .7 ? 'car_sport' : 'car_utility', paints[Math.floor(rnd() * paints.length)], _p.clone(), Math.atan2(_v.x, _v.z));
    }
    // ---------------- life
    this.population = new Population(g, map, this.paths);
    this.traffic = new Traffic(g, map);
    this.wanted = new Wanted(g, map);
    await tick(.92, 'Drawing the map');
    this.minimap = this.drawMinimap();
    // reflections
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    this.envRT = pm.fromScene(new THREE.Scene().add(atmosphereSky('#3a6aa8', '#f2b27a', '#ffd9a8', this.sunDir)), 0.04);
    sc.environment = this.envRT.texture; sc.environmentIntensity = .9;
    pm.dispose(); this.disposables.push(this.envRT);
    progress(1, 'Ready');
  }

  // ---------------------------------------------------------------- city
  // Layout follows the owner's river-city art: towers downtown, green-roof mid-rises, a river with bridges on the north
  // side, parks with fountains, a central rotunda plaza, glowing cyan kerb lines and house-lined streets at the edge.
  buildCity(rnd) {
    const g = this.g, A = g.assets, sc = this.scene, T = A.textures;
    const ext = CITY_EDGE * 2 + 30;
    const rN = RIVER_Z - BLOCK / 2, rS = RIVER_Z + BLOCK / 2;            // river block row (bridges span it)
    const qN = RIVER_Z - RIVER_W - RIVER_BANK, qS = RIVER_Z + RIVER_W + RIVER_BANK;   // quay edges
    const inRiver = z => z > rN - 1 && z < rS + 1;
    const plane = (w, d, x, z, mat, y = .01) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), mat); m.rotation.x = -Math.PI / 2; m.position.set(x, y, z); m.receiveShadow = true; sc.add(m); return m; };
    const conc = T.concrete.clone(); conc.repeat.set(ext / 6, ext / 6); conc.needsUpdate = true;
    const concN = T.concrete_n.clone(); concN.repeat.copy(conc.repeat); concN.needsUpdate = true;
    const groundMat = new THREE.MeshStandardMaterial({ map: conc, normalMap: concN, roughness: .9, color: 0xbab2a6 });
    // ground: north and south of the river (the quays stop at the water)
    plane(ext, qN + ext / 2, 0, (-ext / 2 + qN) / 2, groundMat);
    plane(ext, ext / 2 - qS, 0, (qS + ext / 2) / 2, groundMat);
    const asph = T.asphalt.clone(); asph.repeat.set(ext / 10, ROAD / 10); asph.needsUpdate = true;
    const asphN = T.asphalt_n.clone(); asphN.repeat.copy(asph.repeat); asphN.needsUpdate = true;
    this.roadMat = new THREE.MeshStandardMaterial({ map: asph, normalMap: asphN, roughness: .8, color: 0x9a9aa0, envMapIntensity: .4 });
    const lineMat = this.lineMat = new THREE.MeshStandardMaterial({ color: 0xe8e2d0, roughness: .6 });
    const glowMat = new THREE.MeshStandardMaterial({ color: 0x0a2a33, emissive: 0x40e0ff, emissiveIntensity: 1.15, roughness: .4 });
    const dashGeo = new THREE.PlaneGeometry(.3, 4); dashGeo.rotateX(-Math.PI / 2);
    const glowGeo = new THREE.PlaneGeometry(.2, 10); glowGeo.rotateX(-Math.PI / 2);
    const dashes = [], glows = [];
    for (let i = -N - 1; i <= N; i++) {
      const c = (i + .5) * PITCH;
      // east-west roads run the full width; north-south roads stop at the river where a bridge carries them
      plane(ext, ROAD, 0, c, this.roadMat, .025);
      const nsA = [-ext / 2, rN], nsB = [rS, ext / 2];
      for (const [z0, z1] of [nsA, nsB]) { const m = plane(ROAD, z1 - z0, c, (z0 + z1) / 2, this.roadMat, .025); }
      for (let t = -ext / 2; t < ext / 2; t += 10) {
        dashes.push([t, c, 1]);
        if (!inRiver(t)) dashes.push([c, t]);
        for (const side of [-1, 1]) {
          glows.push([t + 5, c + side * (ROAD / 2 - .7), 1]);
          if (!inRiver(t)) glows.push([c + side * (ROAD / 2 - .7), t + 5]);
        }
      }
    }
    const dm = new THREE.InstancedMesh(dashGeo, lineMat, dashes.length);
    dashes.forEach((d, i) => { _m.makeRotationY(d[2] ? Math.PI / 2 : 0); _m.setPosition(d[0], .04, d[1]); dm.setMatrixAt(i, _m); });
    dm.receiveShadow = true; sc.add(dm);
    const gm = new THREE.InstancedMesh(glowGeo, glowMat, glows.length);
    glows.forEach((d, i) => { _m.makeRotationY(d[2] ? Math.PI / 2 : 0); _m.setPosition(d[0], .045, d[1]); gm.setMatrixAt(i, _m); });
    sc.add(gm);
    // kit materials: window emission for glass, facade and brick
    const kit = A.models.city_buildings.scene;
    const variants = {};
    const IDS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13];
    for (const i of IDS) {
      const root = kit.getObjectByName('BLD_' + i); root.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(root);
      variants[i] = { root, size: box.getSize(new THREE.Vector3()), mats: [] };
    }
    kit.traverse(o => {
      if (!o.isMesh || o.material.userData.done) return; const mt = o.material; mt.userData.done = true;
      if (mt.name === 'facade') { mt.color.set(0x8f969f); mt.roughness = .35; mt.metalness = .5; mt.emissiveMap = T.facade_e; mt.emissive = new THREE.Color(1, .85, .6); mt.emissiveIntensity = .9; mt.needsUpdate = true; }
      if (mt.name === 'ribbon') { mt.color.set(0xa6b4c4); mt.roughness = .22; mt.metalness = .55; mt.emissiveMap = T.ribbon_e; mt.emissive = new THREE.Color(1, .9, .75); mt.emissiveIntensity = .75; mt.needsUpdate = true; }
      if (mt.name === 'brick') { mt.color.set(0x9a5a44); mt.roughness = .8; mt.metalness = 0; mt.emissiveMap = T.facade_e; mt.emissive = new THREE.Color(1, .82, .55); mt.emissiveIntensity = .8; mt.needsUpdate = true; }
    });
    const place = (V, x, z, rot, s2, hs = 1) => {
      const sw = rot % Math.PI ? V.size.z : V.size.x, sd = rot % Math.PI ? V.size.x : V.size.z;
      V.mats.push(new THREE.Matrix4().compose(_p.set(x, 0, z), _q.setFromAxisAngle(Y, rot), _s.set(s2, s2 * hs, s2)));
      this.collision.add([x - sw * s2 / 2, 0, z - sd * s2 / 2, x + sw * s2 / 2, V.size.y * s2 * hs, z + sd * s2 / 2], 'building');
    };
    const pick = list => list[Math.floor(rnd() * list.length)];
    const parks = [], houses = [];
    const PARKS = new Set(['2,-2', '-3,2', '-1,-2', '3,1', '-2,3']);
    const PLAZA = '1,1';
    for (let bx = -N; bx <= N; bx++) for (let bz = -N; bz <= N; bz++) {
      const cx = bx * PITCH, cz = bz * PITCH, key = bx + ',' + bz;
      if (bx === 0 && bz === 0) continue;                                     // spaceport plaza
      if (inRiver(cz)) continue;                                              // the river
      if (key === PLAZA) { this.plaza = [cx, cz]; continue; }
      if (PARKS.has(key)) { parks.push([cx, cz]); continue; }
      const edge = Math.max(Math.abs(bx), Math.abs(bz));
      if (edge === N && rnd() < .75) { houses.push([cx, cz]); continue; }    // suburbs at the city edge
      const lots = (bx === 1 && bz === 0) || (bx === 0 && bz === 1) ? [[0, 0, true]] : [[-1, -1], [1, -1], [-1, 1], [1, 1]];
      for (const [ox, oz, big] of lots) {
        if (!big && rnd() < .08 && edge > 1) continue;
        let v = big ? 6 : edge <= 1 ? pick([0, 5, 1, 2, 12, 12, 7]) : edge <= 2 ? pick([12, 8, 9, 10, 11, 4, 7, 3]) : pick([8, 9, 10, 11, 11, 13, 13, 6]);
        if (v === 5 && variants[5].used) v = 12;
        variants[v].used = true;
        const V = variants[v], rot = Math.floor(rnd() * 4) * Math.PI / 2;
        const sw = rot % Math.PI ? V.size.z : V.size.x, sd = rot % Math.PI ? V.size.x : V.size.z;
        const lot = big ? BLOCK - 10 : BLOCK / 2 - 4;
        const s2 = Math.min(1, lot / Math.max(sw, sd)) * (big ? 1 : .92 + rnd() * .08);
        const hs = big || v >= 8 ? 1 : (edge >= 3 ? .55 : .85) + rnd() * .4;
        place(V, cx + (big ? 0 : ox * BLOCK / 4), cz + (big ? 0 : oz * BLOCK / 4), rot, s2, hs);
      }
    }
    for (const V of Object.values(variants)) instanceKit(this.scene, V.root, V.mats);
    // bridges over the river on every north-south street, and at the highway crossings outside the city
    const br = kit.getObjectByName('BLD_bridge'), brM = [];
    for (let i = -N - 1; i <= N; i++) {
      const c = (i + .5) * PITCH;
      brM.push(new THREE.Matrix4().compose(_p.set(c, 0, RIVER_Z), _q.identity(), _s.set(1, 1, 1)));
      this.collision.add([c - 10, -1.4, rN - 2, c + 10, 0, rS + 2], 'bridge');
    }
    for (const x of this.map.riverCrossings || []) brM.push(new THREE.Matrix4().compose(_p.set(x.x, x.y, x.z), _q.setFromAxisAngle(Y, x.ang), _s.set(.7, 1, .7)));
    instanceKit(this.scene, br, brM);
    // central plaza: the rotunda and its reflecting pool
    if (this.plaza) {
      const rt = A.clone('city_buildings', 'BLD_rotunda'); rt.position.set(this.plaza[0], 0, this.plaza[1]); sc.add(rt);
      this.collision.add([this.plaza[0] - 11, 0, this.plaza[1] - 11, this.plaza[0] + 11, 10, this.plaza[1] + 11], 'building');
    }
    // street lamps along every road (not over the water)
    const lampM = [];
    for (let i = -N - 1; i <= N; i++) {
      const c = (i + .5) * PITCH;
      for (let t = -N * PITCH; t <= N * PITCH; t += 34) for (const side of [-1, 1]) {
        const off = c + side * (ROAD / 2 + 1.2);
        if (!inRiver(t + 11)) lampM.push(new THREE.Matrix4().compose(_p.set(off, 0, t + 11), _q.setFromAxisAngle(Y, side > 0 ? -Math.PI / 2 : Math.PI / 2), _s.set(1, 1, 1)));
        lampM.push(new THREE.Matrix4().compose(_p.set(t + 11, 0, off), _q.setFromAxisAngle(Y, side > 0 ? Math.PI : 0), _s.set(1, 1, 1)));
      }
    }
    const pk = A.models.props_world.scene;
    instanceKit(this.scene, pk.getObjectByName('PR_lamp'), lampM);
    // parks: lawns, trees, benches and a fountain each; riverside promenades lined with trees
    const rk = A.models.rural.scene;
    const lawnMat = new THREE.MeshStandardMaterial({ map: (() => { const t = A.textures.moss.clone(); t.repeat.set(10, 10); t.needsUpdate = true; return t; })(), color: 0x8fb070, roughness: .95 });
    const treeM = [], mapleM = [], pineM = [], benchM = [], fountM = [], bushM = [];
    for (const [cx, cz] of parks) {
      plane(BLOCK - 6, BLOCK - 6, cx, cz, lawnMat, .03);
      for (let k = 0; k < 16; k++) {
        const a = rnd() * Math.PI * 2, r = 14 + rnd() * 26;
        (k % 3 === 0 ? pineM : k % 3 === 1 ? mapleM : treeM).push(new THREE.Matrix4().compose(_p.set(cx + Math.cos(a) * r, 0, cz + Math.sin(a) * r), _q.setFromAxisAngle(Y, rnd() * 6), _s.setScalar(.8 + rnd() * .5)));
      }
      for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2; benchM.push(new THREE.Matrix4().compose(_p.set(cx + Math.cos(a) * 9, 0, cz + Math.sin(a) * 9), _q.setFromAxisAngle(Y, -a + Math.PI / 2), _s.set(1, 1, 1))); }
      fountM.push(new THREE.Matrix4().compose(_p.set(cx, 0, cz), _q.identity(), _s.set(1, 1, 1)));
      this.collision.add([cx - 4.5, 0, cz - 4.5, cx + 4.5, .7, cz + 4.5], 'fountain');
    }
    for (const z of [qN - 4, qS + 4]) for (let x = -CITY_EDGE + 20; x < CITY_EDGE - 10; x += 14) {
      if (Math.abs(((x / PITCH) % 1 + 1) % 1 - .5) < .12) continue;      // keep the bridge heads clear
      treeM.push(new THREE.Matrix4().compose(_p.set(x, 0, z), _q.setFromAxisAngle(Y, rnd() * 6), _s.setScalar(.75 + rnd() * .3)));
    }
    // suburbs: three rows of houses per block with yards, trees and hedges
    const hm = { RU_house_a: [], RU_house_b: [], RU_house_c: [] };
    for (const [cx, cz] of houses) {
      for (const ox of [-1, 0, 1]) for (const oz of [-1, 1]) {
        const x = cx + ox * 28, z = cz + oz * 22, k = pick(Object.keys(hm)), rot = oz < 0 ? Math.PI : 0;
        hm[k].push(new THREE.Matrix4().compose(_p.set(x, 0, z), _q.setFromAxisAngle(Y, rot), _s.setScalar(1)));
        this.collision.add([x - 6, 0, z - 6, x + 6, 7, z + 6], 'building');
        mapleM.push(new THREE.Matrix4().compose(_p.set(x + 9, 0, z - oz * 6), _q.setFromAxisAngle(Y, rnd() * 6), _s.setScalar(.7 + rnd() * .3)));
        bushM.push(new THREE.Matrix4().compose(_p.set(x - 8, 0, z + oz * 9), _q.identity(), _s.setScalar(1)));
      }
      plane(BLOCK - 6, BLOCK - 6, cx, cz, lawnMat, .02);
    }
    for (const [k, list] of Object.entries(hm)) instanceKit(this.scene, rk.getObjectByName(k), list);
    instanceKit(this.scene, rk.getObjectByName('RU_tree_oak'), treeM);
    instanceKit(this.scene, rk.getObjectByName('RU_tree_maple'), mapleM);
    instanceKit(this.scene, rk.getObjectByName('RU_tree_pine'), pineM);
    instanceKit(this.scene, rk.getObjectByName('RU_bush'), bushM);
    for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2 + .3; benchM.push(new THREE.Matrix4().compose(_p.set(Math.cos(a) * 33, 0, Math.sin(a) * 33), _q.setFromAxisAngle(Y, -a + Math.PI / 2), _s.set(1, 1, 1))); }
    instanceKit(this.scene, pk.getObjectByName('PR_bench'), benchM);
    instanceKit(this.scene, kit.getObjectByName('BLD_fountain'), fountM);
    for (const [x, z, r, n] of [[PITCH - 20, -12, Math.PI / 2, 'PR_sign_magenta'], [12, PITCH - 20, 0, 'PR_sign_cyan'], [-PITCH + 28, 8, -Math.PI / 2, 'PR_sign_cyan']]) {
      const s = A.clone('props_world', n); s.position.set(x, 9, z); s.rotation.y = r; s.scale.setScalar(2.2); this.scene.add(s);
    }
  }

  cityPaths() {
    const paths = [];
    for (let bx = -N; bx <= N; bx++) for (let bz = -N; bz <= N; bz++) {
      const cx = bx * PITCH, cz = bz * PITCH, h = BLOCK / 2 - 1.8;
      if (Math.abs(cz - RIVER_Z) < BLOCK / 2) continue;                       // the river
      paths.push(this.loop([[cx - h, cz - h], [cx + h, cz - h], [cx + h, cz + h], [cx - h, cz + h]]));
    }
    return paths;
  }

  loop(xz) {
    const pts = xz.map(([x, z]) => new THREE.Vector3(x, 0, z));
    let total = 0; for (let i = 0; i < pts.length; i++) total += pts[i].distanceTo(pts[(i + 1) % pts.length]);
    return { pts, total };
  }

  // ---------------------------------------------------------------- highways
  buildHighways() {
    const sc = this.scene, A = this.g.assets, T = A.textures;
    const asph = T.asphalt.clone(); asph.repeat.set(1, 1); asph.needsUpdate = true;
    const mat = new THREE.MeshStandardMaterial({ map: asph, normalMap: T.asphalt_n, roughness: .85, color: 0x8f8f95, polygonOffset: true, polygonOffsetFactor: -2 });
    const dashes = [];
    for (const r of this.map.roads) {
      const P = r.pts, W = r.width / 2, pos = [], uv = [], idx = [];
      let acc = 0;
      for (let i = 0; i < P.length; i++) {
        const a = P[Math.max(0, i - 1)], b = P[Math.min(P.length - 1, i + 1)];
        const tx = b.x - a.x, tz = b.z - a.z, l = Math.hypot(tx, tz) || 1, nx = -tz / l, nz = tx / l;
        if (i) acc += P[i].distanceTo(P[i - 1]);
        for (const s of [-1, 1]) {
          const x = P[i].x + nx * W * s, z = P[i].z + nz * W * s;
          pos.push(x, Math.max(P[i].y, this.map.height(x, z)) + .07, z); uv.push(s < 0 ? 0 : 1, acc / 10);
        }
        if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
        if (i % 2 === 0) dashes.push(new THREE.Matrix4().compose(_p.set(P[i].x, P[i].y + .09, P[i].z), _q.setFromAxisAngle(Y, Math.atan2(tx, tz)), _s.set(1, 1, 1)));
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
      geo.setIndex(idx); geo.computeVertexNormals();
      const m = new THREE.Mesh(geo, mat); m.receiveShadow = true; sc.add(m);
    }
    const dashGeo = new THREE.PlaneGeometry(.25, 4); dashGeo.rotateX(-Math.PI / 2);
    const dm = new THREE.InstancedMesh(dashGeo, this.lineMat, dashes.length);
    dashes.forEach((d, i) => dm.setMatrixAt(i, d)); dm.receiveShadow = true; dm.computeBoundingSphere(); sc.add(dm);
    // road signs at junctions with the ring road
    const signs = this.map.roads.map(r => { const p = r.pts[6]; return new THREE.Matrix4().compose(_p.set(p.x + 8, p.y, p.z), _q.identity(), _s.set(1, 1, 1)); });
    instanceKit(sc, A.models.rural.scene.getObjectByName('RU_sign'), signs);
  }

  // ---------------------------------------------------------------- villages
  buildVillages(rnd) {
    const A = this.g.assets, rk = A.models.rural.scene, map = this.map;
    const kinds = ['RU_house_a', 'RU_house_b', 'RU_house_c'];
    const mats = { RU_house_a: [], RU_house_b: [], RU_house_c: [], RU_shop: [], RU_gas: [], RU_watertower: [], RU_tree_oak: [], RU_tree_maple: [], RU_bush: [] };
    const placed = [];
    const sizeOf = n => { const b = new THREE.Box3().setFromObject(rk.getObjectByName(n)); return b.getSize(new THREE.Vector3()); };
    const sizes = {}; for (const n of Object.keys(mats)) sizes[n] = sizeOf(n);
    const put = (n, x, z, yaw, solid = true, scale = 1) => {
      const y = map.height(x, z);
      mats[n].push(new THREE.Matrix4().compose(_p.set(x, y, z), _q.setFromAxisAngle(Y, yaw), _s.setScalar(scale)));
      if (solid) {
        const s = sizes[n], c = Math.abs(Math.cos(yaw)), sn = Math.abs(Math.sin(yaw));
        const hx = (s.x * c + s.z * sn) / 2 * scale, hz = (s.x * sn + s.z * c) / 2 * scale;
        this.collision.add([x - hx, y - 1, z - hz, x + hx, y + s.y * scale, z + hz], 'house');
      }
      placed.push([x, z]);
    };
    for (const v of VILLAGES) {
      const [vx, vz] = v.pos;
      const pts = [];
      for (const r of map.roads) for (const p of r.pts) if (Math.hypot(p.x - vx, p.z - vz) < v.r) pts.push({ p, r });
      const sidewalkA = [], sidewalkB = [];
      let k = 0;
      for (const { p, r } of pts) {
        const i = r.pts.indexOf(p), a = r.pts[Math.max(0, i - 1)], b = r.pts[Math.min(r.pts.length - 1, i + 1)];
        const tx = b.x - a.x, tz = b.z - a.z, l = Math.hypot(tx, tz) || 1, nx = -tz / l, nz = tx / l;
        if (k % 2 === 0) { sidewalkA.push([p.x + nx * 7.5, p.z + nz * 7.5]); sidewalkB.push([p.x - nx * 7.5, p.z - nz * 7.5]); }
        if (k++ % 4) continue;
        for (const s of [-1, 1]) {
          const x = p.x + nx * 18 * s + (rnd() - .5) * 3, z = p.z + nz * 18 * s + (rnd() - .5) * 3;
          if (placed.some(([px, pz]) => Math.hypot(px - x, pz - z) < 15) || map.nearRoad(x, z, 11)) continue;
          put(kinds[Math.floor(rnd() * 3)], x, z, Math.atan2(-nx * s, -nz * s));
        }
      }
      // village centre: shop, gas station, water tower, trees
      const ang = rnd() * 6.28;
      const tryPut = (n, dist, yawOff = 0) => {
        for (let t = 0; t < 12; t++) {
          const a = ang + t * .8, x = vx + Math.cos(a) * dist, z = vz + Math.sin(a) * dist;
          if (placed.some(([px, pz]) => Math.hypot(px - x, pz - z) < 20) || map.nearRoad(x, z, 14)) continue;
          put(n, x, z, Math.atan2(vx - x, vz - z) + yawOff); return [x, z];
        }
      };
      tryPut('RU_shop', 34); tryPut('RU_gas', 60); tryPut('RU_watertower', 70);
      for (let t = 0; t < 40; t++) {
        const a = rnd() * 6.28, d = v.r * (.5 + rnd() * .9), x = vx + Math.cos(a) * d, z = vz + Math.sin(a) * d;
        if (placed.some(([px, pz]) => Math.hypot(px - x, pz - z) < 9) || map.nearRoad(x, z, 8)) continue;
        put(rnd() < .6 ? 'RU_tree_oak' : rnd() < .5 ? 'RU_tree_maple' : 'RU_bush', x, z, rnd() * 6.28, false, .8 + rnd() * .5);
      }
      if (sidewalkA.length > 3) this.paths.push(this.loop([...sidewalkA, ...sidewalkB.reverse()]));
      this.paths.push(this.loop(Array.from({ length: 12 }, (_, i) => [vx + Math.cos(i / 12 * 6.28) * 40, vz + Math.sin(i / 12 * 6.28) * 40])));
    }
    for (const [n, list] of Object.entries(mats)) instanceKit(this.scene, rk.getObjectByName(n), list, { chunk: 700 });
  }

  // ---------------------------------------------------------------- farms
  buildFarms(rnd) {
    const A = this.g.assets, rk = A.models.rural.scene, map = this.map, T = A.textures;
    const mats = { RU_farmhouse: [], RU_barn: [], RU_silo: [], RU_tractor: [], RU_hay: [], RU_fence: [], RU_wheat: [], RU_corn: [] };
    const fieldTex = (name, rep) => { const t = new THREE.TextureLoader().load('assets/textures/' + name + '.jpg'); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rep[0], rep[1]); t.colorSpace = THREE.SRGBColorSpace; return t; };
    const solid = (x, z, hx, hz, y, h) => this.collision.add([x - hx, y - 1, z - hz, x + hx, y + h, z + hz], 'farm');
    for (const f of FARMS) {
      const [fx, fz] = f.pos, y = f.y;
      // yard in one corner
      const yx = fx - f.w / 2 + 40, yz = fz - f.d / 2 + 40;
      mats.RU_farmhouse.push(new THREE.Matrix4().compose(_p.set(yx, map.height(yx, yz), yz), _q.setFromAxisAngle(Y, Math.PI), _s.set(1, 1, 1))); solid(yx, yz, 6, 7, y, 10);
      mats.RU_barn.push(new THREE.Matrix4().compose(_p.set(yx + 32, map.height(yx + 32, yz), yz), _q.identity(), _s.set(1, 1, 1))); solid(yx + 32, yz, 7, 10, y, 9);
      mats.RU_silo.push(new THREE.Matrix4().compose(_p.set(yx + 48, map.height(yx + 48, yz - 6), yz - 6), _q.identity(), _s.set(1, 1, 1))); solid(yx + 48, yz - 6, 2.5, 2.5, y, 14);
      mats.RU_tractor.push(new THREE.Matrix4().compose(_p.set(yx + 18, map.height(yx + 18, yz + 16), yz + 16), _q.setFromAxisAngle(Y, rnd() * 6), _s.set(1, 1, 1))); solid(yx + 18, yz + 16, 1.6, 1.6, y, 3);
      for (let k = 0; k < 8; k++) { const x = yx + 10 + rnd() * 40, z = yz + 22 + rnd() * 14; mats.RU_hay.push(new THREE.Matrix4().compose(_p.set(x, map.height(x, z), z), _q.setFromAxisAngle(Y, rnd() * 6), _s.set(1, 1, 1))); }
      this.paths.push(this.loop([[yx - 10, yz - 14], [yx + 40, yz - 14], [yx + 40, yz + 14], [yx - 10, yz + 14]]));
      // fields: two big plots with different crops
      const plots = [[fx + f.w * .18, fz + f.d * .12, f.w * .5, f.d * .55, 'wheat_c', 'RU_wheat'], [fx - f.w * .22, fz + f.d * .22, f.w * .4, f.d * .4, 'field_rows_c', 'RU_corn']];
      for (const [px, pz, w, d, tex, crop] of plots) {
        const geo = new THREE.PlaneGeometry(w, d, 24, 24); geo.rotateX(-Math.PI / 2);
        const pos = geo.attributes.position;
        for (let i = 0; i < pos.count; i++) pos.setY(i, map.height(pos.getX(i) + px, pos.getZ(i) + pz) + .06);
        geo.computeVertexNormals();
        const field = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: fieldTex(tex, [w / 12, d / 12]), roughness: .95, polygonOffset: true, polygonOffsetFactor: -1 }));
        field.position.set(px, 0, pz); field.receiveShadow = true; this.scene.add(field);
        const step = crop === 'RU_wheat' ? 3.2 : 4;
        for (let x = -w / 2 + 2; x < w / 2 - 2; x += step) for (let z = -d / 2 + 2; z < d / 2 - 2; z += step) {
          if (rnd() < .15) continue;
          const X = px + x + (rnd() - .5), Z = pz + z + (rnd() - .5);
          mats[crop].push(new THREE.Matrix4().compose(_p.set(X, map.height(X, Z), Z), _q.setFromAxisAngle(Y, rnd() * 6), _s.setScalar(.8 + rnd() * .5)));
        }
      }
      // fence around the property
      const hw = f.w / 2, hd = f.d / 2;
      for (const [x0, z0, x1, z1] of [[-hw, -hd, hw, -hd], [hw, -hd, hw, hd], [hw, hd, -hw, hd], [-hw, hd, -hw, -hd]]) {
        const L = Math.hypot(x1 - x0, z1 - z0), n = Math.floor(L / 6), yaw = Math.atan2(z1 - z0, x1 - x0);
        for (let i = 0; i < n; i++) {
          const t = (i + .5) / n, x = fx + x0 + (x1 - x0) * t, z = fz + z0 + (z1 - z0) * t;
          if (this.map.nearRoad(x, z, 9)) continue;      // gates where roads cross
          mats.RU_fence.push(new THREE.Matrix4().compose(_p.set(x, map.height(x, z), z), _q.setFromAxisAngle(Y, -yaw), _s.set(1, 1, 1)));
        }
      }
    }
    for (const [n, list] of Object.entries(mats)) instanceKit(this.scene, rk.getObjectByName(n), list, { chunk: 700, shadow: n !== 'RU_wheat' && n !== 'RU_corn' });
  }

  // ---------------------------------------------------------------- nature
  buildForests(rnd) {
    const A = this.g.assets, rk = A.models.rural.scene, map = this.map;
    const kinds = ['RU_tree_oak', 'RU_tree_maple', 'RU_tree_birch', 'RU_tree_pine', 'RU_bush'];
    const mats = Object.fromEntries(kinds.map(k => [k, []]));
    for (let x = -HALF + 40; x < HALF - 40; x += 26) for (let z = -HALF + 40; z < HALF - 40; z += 26) {
      const n = fbm(x * .0045 + 3, z * .0045 - 8, 41, 3);
      if (n < .55) continue;
      const X = x + (rnd() - .5) * 16, Z = z + (rnd() - .5) * 16, h = map.height(X, Z);
      if (h < SEA + 2 || map.developed(X, Z) || map.nearRoad(X, Z, 13)) continue;
      const k = h > 40 ? (rnd() < .75 ? 3 : 2) : Math.floor(rnd() * 5);
      mats[kinds[k]].push(new THREE.Matrix4().compose(_p.set(X, h - .2, Z), _q.setFromAxisAngle(Y, rnd() * 6), _s.setScalar(.75 + rnd() * .6)));
      if (k !== 4 && rnd() < .5) this.collision.add([X - .5, h, Z - .5, X + .5, h + 6, Z + .5], 'tree');
    }
    this.treeCount = Object.values(mats).reduce((a, b) => a + b.length, 0);
    for (const [n, list] of Object.entries(mats)) instanceKit(this.scene, rk.getObjectByName(n), list, { chunk: 700 });
  }

  buildTurbines(rnd) {
    const A = this.g.assets, map = this.map;
    this.rotors = [];
    const spots = [];
    for (let t = 0; t < 400 && spots.length < 7; t++) {
      const x = (rnd() - .5) * SIZE * .8, z = (rnd() - .5) * SIZE * .8, h = map.height(x, z);
      if (h < 25 || map.developed(x, z, 40) || map.nearRoad(x, z, 25) || spots.some(([a, b]) => Math.hypot(a - x, b - z) < 120)) continue;
      spots.push([x, z]);
      const tb = A.clone('rural', 'RU_turbine'); tb.position.set(x, h - .5, z); tb.rotation.y = -.8; this.scene.add(tb);
      this.collision.add([x - 1.5, h, z - 1.5, x + 1.5, h + 40, z + 1.5], 'turbine');
      const r = tb.getObjectByName('turbine_rotor'); if (r) { r.rotation.y = 0; this.rotors.push({ r, s: .6 + rnd() * .4 }); }
    }
  }

  // ---------------------------------------------------------------- spaceport, ship, Quartermaster
  buildSpaceport() {
    const g = this.g, A = g.assets, sc = this.scene;
    const port = A.clone('city_buildings', 'BLD_port'); sc.add(port);
    port.traverse(o => { if (o.isMesh) o.receiveShadow = true; });
    this.collision.add([-20, 0, -20, 20, 1.2, 20], 'port');
    for (let i = 0; i < 6; i++) this.collision.add([-5, 0, 20 + i * 2.6, 5, 1.2 - (i + 1) * .2, 22.6 + i * 2.6], 'ramp');
    const js = A.clone('ship_jumper'); js.position.set(0, 1.2, 4); js.rotation.y = Math.PI; sc.add(js); this.jumpship = js;
    this.collision.add([-2.4, 1.2, -4, 2.4, 5, 12], 'ship');
    this.collision.add([-8.6, 2.0, -1.5, 8.6, 2.6, 4], 'ship');
    this.interactables.push({ id: 'ship', pos: new THREE.Vector3(0, 1.2, 12.5), r: 3.2, label: 'The Wayfarer', verb: 'Return to orbit', key: 'E', action: () => g.travel('ship') });
    const qm = new Avatar(A, 'npc_vendor'); qm.root.position.set(9, 1.2, -9); qm.root.rotation.y = -Math.PI * .75; qm.play('IdleRelaxed', 0);
    sc.add(qm.root); this.vendor = qm;
    this.collision.add([8.5, 1.2, -9.5, 9.5, 3, -8.5], 'npc');
    const term = A.clone('props_world', 'PR_terminal'); term.position.set(10.2, 1.2, -10.2); term.rotation.y = -Math.PI * .75; sc.add(term);
    this.interactables.push({ id: 'vendor', pos: new THREE.Vector3(8, 1.2, -8), r: 2.4, label: 'Quartermaster Okafor', verb: 'Trade', key: 'E', action: () => g.station('vendor') });
  }

  // ---------------------------------------------------------------- minimap (pre-rendered island)
  drawMinimap() {
    const S = 512, c = document.createElement('canvas'); c.width = c.height = S;
    const x = c.getContext('2d'), img = x.createImageData(S, S), map = this.map;
    for (let j = 0; j < S; j++) for (let i = 0; i < S; i++) {
      const wx = -HALF + (i + .5) / S * SIZE, wz = -HALF + (j + .5) / S * SIZE, h = map.height(wx, wz);
      let r, g2, b;
      if (h < SEA) { r = 30; g2 = 70; b = 92; }
      else if (Math.abs(wx) < CITY_EDGE && Math.abs(wz) < CITY_EDGE) { r = 92; g2 = 92; b = 98; }
      else { const t = Math.min(1, Math.max(0, h / 70)); r = 70 + t * 70; g2 = 100 + t * 30; b = 58 + t * 50; }
      const k = (j * S + i) * 4; img.data[k] = r; img.data[k + 1] = g2; img.data[k + 2] = b; img.data[k + 3] = 255;
    }
    x.putImageData(img, 0, 0);
    const toPx = (wx, wz) => [(wx + HALF) / SIZE * S, (wz + HALF) / SIZE * S];
    x.strokeStyle = '#2b2b2f'; x.lineWidth = 2.2;
    for (const r of map.roads) { x.beginPath(); r.pts.forEach((p, i) => { const [a, b] = toPx(p.x, p.z); i ? x.lineTo(a, b) : x.moveTo(a, b); }); x.stroke(); }
    x.lineWidth = 1.2;
    for (let i = -N - 1; i <= N; i++) { const c0 = (i + .5) * PITCH; let [a, b] = toPx(c0, -CITY_EDGE), [a2, b2] = toPx(c0, CITY_EDGE); x.beginPath(); x.moveTo(a, b); x.lineTo(a2, b2); x.stroke(); [a, b] = toPx(-CITY_EDGE, c0); [a2, b2] = toPx(CITY_EDGE, c0); x.beginPath(); x.moveTo(a, b); x.lineTo(a2, b2); x.stroke(); }
    x.fillStyle = 'rgba(214,190,140,.7)';
    for (const f of FARMS) { const [a, b] = toPx(f.pos[0] - f.w / 2, f.pos[1] - f.d / 2); x.fillRect(a, b, f.w / SIZE * S, f.d / SIZE * S); }
    x.fillStyle = '#e8e2d4'; x.font = '600 11px Rajdhani, sans-serif'; x.textAlign = 'center';
    for (const v of VILLAGES) { const [a, b] = toPx(v.pos[0], v.pos[1]); x.beginPath(); x.arc(a, b, 5, 0, 7); x.fill(); x.fillText(v.name.toUpperCase(), a, b - 9); }
    return { canvas: c, scale: S / SIZE, half: HALF };
  }

  spawn() { return { pos: new THREE.Vector3(0, 1.2, 16.5), yaw: 0 }; }

  markers() {
    const m = [{ pos: new THREE.Vector3(0, 0, 12), icon: '▲', color: '#1ad8ff' }, { pos: new THREE.Vector3(8, 0, -8), icon: '◉', color: '#7dffb0' }];
    for (const e of this.wanted.police) m.push({ pos: e.pos, icon: '●', color: '#ff4a3d' });
    return m;
  }

  objectives() { return []; }   // free roam: no missions on Earth

  update(dt) {
    const g = this.g, p = g.player;
    this.sky.position.copy(g.camera.position);
    this.sky.material.uniforms.time.value = g.time;
    const c = p.mode === 'car' && g.vehicles.current ? g.vehicles.current.pos : p.pos;
    this.sun.target.position.set(Math.round(c.x / 4) * 4, c.y, Math.round(c.z / 4) * 4);
    this.sun.position.copy(this.sun.target.position).addScaledVector(this.sunDir, 300);
    this.water.position.x = Math.round(c.x / 50) * 50; this.water.position.z = Math.round(c.z / 50) * 50;
    for (const t of this.skyway) {
      t.t += t.speed * t.dir * dt;
      if (t.t > CITY_EDGE) t.t = -CITY_EDGE; if (t.t < -CITY_EDGE) t.t = CITY_EDGE;
      if (t.axis) { t.obj.position.set(t.lane, t.alt, t.t); t.obj.rotation.y = t.dir > 0 ? 0 : Math.PI; }
      else { t.obj.position.set(t.t, t.alt, t.lane); t.obj.rotation.y = t.dir > 0 ? Math.PI / 2 : -Math.PI / 2; }
    }
    for (const r of this.rotors) r.r.rotation.y += dt * r.s;
    this.population.update(dt);
    this.traffic.update(dt);
    this.wanted.update(dt);
    if (this.vendor) this.vendor.update(dt);
    // district name in the HUD
    this.distT = (this.distT || 0) - dt;
    if (this.distT <= 0) {
      this.distT = 1;
      const d = this.map.district(c.x, c.z);
      if (d !== this.districtName) { this.districtName = d; g.hud.setLocation('Earth', d); }
    }
  }

  // crashes stop traffic and scatter pedestrians
  onCrash(pos) { this.traffic.crash(pos); this.population.alarm(pos, 30, pos); }

  // gunfire scares people
  onGunshot(pos) { this.population.alarm(pos, 40, pos); }

  dispose() {
    this.population && this.population.clear();
    this.traffic && this.traffic.clear();
    super.dispose();
  }
}
