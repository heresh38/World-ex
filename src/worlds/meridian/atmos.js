// Earth's ambient VFX, all near the camera only: leaves and cherry petals drifting down from big trees (coloured by
// species, they settle on the ground and fade), steam rising from downtown rooftop plant and smoke from house chimneys
// (more in the morning and evening), spray and mist over the park fountains, and moths circling the street lamps at
// night. Particles only (no meshes): leaves are shader-drawn point sprites, steam/smoke/spray use the shared Puffs pool
// (src/game/puffs.js). Budgets are small and fixed; touch devices get about half.
import * as THREE from 'three';
import { Puffs } from '../../game/puffs.js';
import { SKY } from './daynight.js';

// chimney tops of the rural houses in their own space (tools/blender/rural.py gable_house: x = w/4, y = H + 0.6 roof
// rise + 1.1, z = -d/5)
const CHIMNEY = { RU_house_a: [2, 6.1, -2], RU_house_b: [2.25, 9.1, -2.2], RU_house_c: [1.75, 5.7, -1.8], RU_farmhouse: [2.5, 9.7, -2.4] };
const _v = new THREE.Vector3(), _c = new THREE.Color();
const hash = (x, z) => { const s = Math.sin(x * 12.9898 + z * 78.233) * 43758.5453; return s - Math.floor(s); };

export class Atmos {
  constructor(world) {
    this.w = world; this.g = world.g; this.scene = world.scene;
    const touch = this.touch = !!this.g.renderer.touch;
    this.smoke = new Puffs(this.scene, touch ? 260 : 520, { soft: .9 });
    this.spray = new Puffs(this.scene, touch ? 220 : 420, { soft: .3 });
    this.buildSources();
    this.buildLeaves(touch ? 90 : 180);
    this.buildMoths(touch ? 60 : 120);
    this.t = 0; this.scanT = 0; this.near = { trees: [], vents: [], chims: [], founts: [], lamps: [] };
  }

  buildSources() {
    const w = this.w;
    // house chimneys (suburbs, villages, farms)
    this.chimneys = [];
    for (const [kind, m] of w.houses || []) {
      const c = CHIMNEY[kind]; if (!c) continue;
      _v.set(c[0], c[1], c[2]).applyMatrix4(m);
      const h = hash(_v.x, _v.z);
      this.chimneys.push({ x: _v.x, y: _v.y, z: _v.z, h, acc: 0 });
    }
    // rooftop plant on downtown towers: steam from the top of the central roof structure
    this.vents = [];
    const dt = w.downtown;
    if (dt) {
      const tops = new Map();
      for (const P of dt.placed) {
        if (P.h < 18 || /construction|obs_tower|derelict|crescent|twist|parkade|hist_bank/.test(P.name)) continue;
        if (hash(P.x * 1.3, P.z * .7) > .62) continue;
        let top = tops.get(P.name);
        if (top === undefined) { top = this.roofTop(dt.designs.get(P.name)); tops.set(P.name, top); }
        if (!top) continue;
        const c = Math.cos(P.yaw), s = Math.sin(P.yaw);
        const x = P.x + top[0] * c + top[2] * s, z = P.z - top[0] * s + top[2] * c;
        this.vents.push({ x, y: top[1] + .3, z, h: hash(x, z), acc: 0, big: P.h > 60 });
      }
    }
    // fountains: jet top, basin water level and radius from the kit (city.py BLD_fountain)
    const fk = this.g.assets.models.city_buildings && this.g.assets.models.city_buildings.scene.getObjectByName('BLD_fountain');
    let top = 2.4, water = .55, r = 3.6;
    if (fk) {
      fk.updateMatrixWorld(true);
      const inv = new THREE.Matrix4().copy(fk.matrixWorld).invert(), all = new THREE.Box3(), wb = new THREE.Box3(), bb = new THREE.Box3();
      fk.traverse(o => {
        if (!o.isMesh) return;
        o.geometry.computeBoundingBox(); bb.copy(o.geometry.boundingBox).applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld));
        all.union(bb); if (o.material.name === 'fountain_water') wb.union(bb);
      });
      if (!all.isEmpty()) top = all.max.y * .92;
      if (!wb.isEmpty()) { water = wb.max.y; r = Math.max(1.5, (wb.max.x - wb.min.x) / 2); }
    }
    this.fountains = (w.fountainSpots || []).map(f => ({ x: f.x, z: f.z, top, water, r, acc: 0, macc: 0 }));
  }

  // highest point of a design's roof clutter near the middle of its footprint (its own space): [x, y, z]
  roofTop(D) {
    if (!D) return null;
    const b = D.box, cx = (b.min.x + b.max.x) / 2, cz = (b.min.z + b.max.z) / 2, hx = (b.max.x - b.min.x) * .3, hz = (b.max.z - b.min.z) * .3;
    const inv = new THREE.Matrix4().copy(D.root.matrixWorld).invert(), m = new THREE.Matrix4();
    let best = null;
    D.root.traverse(o => {
      if (!o.isMesh) return;
      m.multiplyMatrices(inv, o.matrixWorld);
      const P = o.geometry.attributes.position;
      for (let i = 0; i < P.count; i += 2) {
        _v.fromBufferAttribute(P, i).applyMatrix4(m);
        if (Math.abs(_v.x - cx) < hx && Math.abs(_v.z - cz) < hz && (!best || _v.y > best[1])) best = [_v.x, _v.y, _v.z];
      }
    });
    if (best && best[1] > b.max.y - .5 && b.max.y - best[1] < .5) {
      // the very top is an antenna or a spire: steam from just under it instead
      best[1] = Math.max(b.min.y, best[1] - 2);
    }
    return best;
  }

  // ---------------------------------------------------------------- falling leaves / petals (shader-drawn point sprites)
  buildLeaves(n) {
    this.L = { n, pos: new Float32Array(n * 3), col: new Float32Array(n * 3), size: new Float32Array(n), ang: new Float32Array(n), alpha: new Float32Array(n),
      vel: new Float32Array(n * 3), life: new Float32Array(n), ph: new Float32Array(n), spin: new Float32Array(n), rest: new Float32Array(n), ground: new Float32Array(n), cursor: 0, acc: 0 };
    const L = this.L, g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(L.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('color', new THREE.BufferAttribute(L.col, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('size', new THREE.BufferAttribute(L.size, 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('ang', new THREE.BufferAttribute(L.ang, 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('alpha', new THREE.BufferAttribute(L.alpha, 1).setUsage(THREE.DynamicDrawUsage));
    this.leafMat = new THREE.ShaderMaterial({
      uniforms: { scale: { value: innerHeight / 2 }, uLight: { value: new THREE.Color(1, 1, 1) }, fogColor: { value: new THREE.Color() }, fogNear: { value: 1 }, fogFar: { value: 2 } },
      vertexShader: `attribute float size,ang,alpha;attribute vec3 color;varying vec3 vC;varying float vA,vAng,vD;uniform float scale;
        void main(){vC=color;vA=alpha;vAng=ang;vec4 mv=modelViewMatrix*vec4(position,1.);vD=-mv.z;gl_PointSize=min(64.,size*scale/max(.2,-mv.z));gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `varying vec3 vC;varying float vA,vAng,vD;uniform vec3 uLight,fogColor;uniform float fogNear,fogFar;
        void main(){if(vA<.02)discard;vec2 p=(gl_PointCoord-.5)*2.;float c=cos(vAng),s=sin(vAng);vec2 q=vec2(c*p.x-s*p.y,s*p.x+c*p.y);
          q.x/=max(.25,abs(cos(vAng*1.7)));                     // tumbling: the leaf turns edge-on now and then
          float wdt=.42*(1.-q.y*q.y);if(abs(q.y)>.95||abs(q.x)>wdt)discard;
          vec3 col=vC*(.8+.25*sin(vAng*2.3))*(1.-.35*smoothstep(.06,0.,abs(q.x)));
          col*=uLight;col=mix(col,fogColor,smoothstep(fogNear,fogFar,vD));
          gl_FragColor=vec4(col,1.);}`,
    });
    this.leaves = new THREE.Points(g, this.leafMat); this.leaves.frustumCulled = false; this.leaves.renderOrder = 4;
    this.scene.add(this.leaves);
  }

  leafColor(k) {
    const n = k.name || '', r = Math.random();
    if (/cherry/.test(n)) return _c.setRGB(1, .72 + r * .12, .8 + r * .1);
    if (/autumn|gold/.test(n)) return _c.setRGB(.85 + r * .15, .35 + r * .3, .08 + r * .08);
    if (/birch|willow|ash/.test(n)) return _c.setRGB(.6 + r * .25, .62 + r * .15, .18 + r * .1);
    if (/spruce|pine|snow|emergent|understory/.test(n)) return null;     // evergreens don't drop much
    return r < .4 ? _c.setRGB(.55 + r * .3, .4 + r * .2, .15) : _c.setRGB(.3 + r * .2, .45 + r * .2, .12);
  }

  spawnLeaf(tr) {
    const L = this.L, c = this.leafColor(tr.k); if (!c) return;
    const i = L.cursor; L.cursor = (L.cursor + 1) % L.n;
    const a = Math.random() * 6.28, r = Math.random() * tr.k.w * .45 * tr.s;
    L.pos[i * 3] = tr.x + Math.cos(a) * r; L.pos[i * 3 + 1] = tr.y + tr.k.h * tr.s * (.45 + Math.random() * .4); L.pos[i * 3 + 2] = tr.z + Math.sin(a) * r;
    L.vel[i * 3] = (Math.random() - .5) * .4; L.vel[i * 3 + 1] = -(.5 + Math.random() * .5); L.vel[i * 3 + 2] = (Math.random() - .5) * .4;
    L.col[i * 3] = c.r; L.col[i * 3 + 1] = c.g; L.col[i * 3 + 2] = c.b;
    L.size[i] = /cherry/.test(tr.k.name) ? .07 + Math.random() * .04 : .1 + Math.random() * .07;
    L.life[i] = 1; L.ph[i] = Math.random() * 6.28; L.spin[i] = (Math.random() - .5) * 5; L.rest[i] = 0; L.alpha[i] = 1;
    L.ground[i] = this.w.collision.ground ? this.w.collision.ground(L.pos[i * 3], L.pos[i * 3 + 2]) : 0;
  }

  updateLeaves(dt) {
    const L = this.L, t = this.t, wind = .6 + .4 * Math.sin(t * .37) * Math.sin(t * .19 + 1.3);
    let any = false;
    for (let i = 0; i < L.n; i++) {
      if (L.life[i] <= 0) { if (L.alpha[i]) L.alpha[i] = 0; continue; }
      any = true;
      if (L.rest[i] > 0) { L.rest[i] -= dt; L.alpha[i] = Math.min(1, L.rest[i] / 2); if (L.rest[i] <= 0) L.life[i] = 0; continue; }
      const k = i * 3, ph = L.ph[i] += dt * (1.6 + (i % 5) * .2);
      L.pos[k] += (L.vel[k] + Math.sin(ph) * .7 + wind * .55) * dt;
      L.pos[k + 1] += (L.vel[k + 1] + Math.cos(ph * 2) * .25) * dt;
      L.pos[k + 2] += (L.vel[k + 2] + Math.cos(ph * .8) * .5 + wind * .3) * dt;
      L.ang[i] += L.spin[i] * dt;
      if (L.pos[k + 1] < L.ground[i] + .04) { L.pos[k + 1] = L.ground[i] + .04; L.rest[i] = 6 + Math.random() * 6; L.ang[i] = Math.random() * 6.28; }
    }
    const G = this.leaves.geometry.attributes;
    G.position.needsUpdate = G.alpha.needsUpdate = G.ang.needsUpdate = G.color.needsUpdate = G.size.needsUpdate = true;
    this.leaves.visible = any;
  }

  // ---------------------------------------------------------------- moths round the lamps at night
  buildMoths(n) {
    this.M = { n, pos: new Float32Array(n * 3), lamp: new Int32Array(n).fill(-1), r: new Float32Array(n), sp: new Float32Array(n), ph: new Float32Array(n) };
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(this.M.pos, 3).setUsage(THREE.DynamicDrawUsage));
    this.mothMat = new THREE.ShaderMaterial({
      uniforms: { scale: { value: innerHeight / 2 }, uI: { value: 0 } },
      vertexShader: `uniform float scale;void main(){vec4 mv=modelViewMatrix*vec4(position,1.);gl_PointSize=clamp(.07*scale/max(.2,-mv.z),1.,6.);gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `uniform float uI;void main(){vec2 p=gl_PointCoord-.5;if(dot(p,p)>.25)discard;gl_FragColor=vec4(vec3(1.,.9,.7)*uI,1.);}`,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    this.moths = new THREE.Points(g, this.mothMat); this.moths.frustumCulled = false; this.moths.visible = false; this.moths.renderOrder = 12;
    this.scene.add(this.moths);
    for (let i = 0; i < n; i++) { this.M.r[i] = .25 + Math.random() * .8; this.M.sp[i] = (1.5 + Math.random() * 3) * (Math.random() < .5 ? -1 : 1); this.M.ph[i] = Math.random() * 6.28; }
  }

  updateMoths(dt, k) {
    const M = this.M, heads = this.w.daynight && this.w.daynight.lampHeads, lamps = this.near.lamps;
    this.moths.visible = k > .05 && !!heads && lamps.length > 0;
    if (!this.moths.visible) return;
    this.mothMat.uniforms.uI.value = 1.4 * k; this.mothMat.uniforms.scale.value = innerHeight / 2;
    const per = Math.max(1, Math.floor(M.n / Math.max(1, lamps.length)));
    for (let i = 0; i < M.n; i++) {
      const li = lamps[Math.floor(i / per)];
      const k3 = i * 3;
      if (li === undefined) { M.pos[k3 + 1] = -999; continue; }
      const ph = M.ph[i] += dt * M.sp[i], r = M.r[i] * (1 + .3 * Math.sin(ph * 2.3 + i));
      M.pos[k3] = heads[li * 3] + Math.cos(ph) * r + Math.sin(ph * 5.1 + i) * .08;
      M.pos[k3 + 1] = heads[li * 3 + 1] - .35 + Math.sin(ph * 1.7 + i * .7) * .35;
      M.pos[k3 + 2] = heads[li * 3 + 2] + Math.sin(ph) * r + Math.cos(ph * 4.3 + i) * .08;
    }
    this.moths.geometry.attributes.position.needsUpdate = true;
  }

  // ---------------------------------------------------------------- per frame
  update(dt) {
    const g = this.g, cam = g.camera.position, fog = this.scene.fog, night = SKY.night.value, hour = SKY.hour.value;
    this.t += dt;
    // every half second: what is near the camera
    this.scanT -= dt;
    if (this.scanT <= 0) {
      this.scanT = .5;
      const N = this.near; N.trees.length = 0;
      if (this.w.flora && cam.y < 60) this.w.flora.near(cam.x, cam.z, 50, (x, y, z, k) => { if (N.trees.length < 40 && k.h > 6) N.trees.push({ x, y, z, k, s: 1 }); });
      const by = (list, r, max) => list.map(s => [(s.x - cam.x) ** 2 + (s.z - cam.z) ** 2, s]).filter(a => a[0] < r * r).sort((a, b) => a[0] - b[0]).slice(0, max).map(a => a[1]);
      N.vents = by(this.vents, 420, this.touch ? 6 : 12);
      N.chims = by(this.chimneys, 230, this.touch ? 6 : 12);
      N.founts = by(this.fountains, 90, 2);
      const H = this.w.daynight && this.w.daynight.lampHeads;
      N.lamps = [];
      if (H && night > .2) {
        const c = [];
        for (let i = 0; i < H.length / 3; i++) { const d = (H[i * 3] - cam.x) ** 2 + (H[i * 3 + 2] - cam.z) ** 2 + (H[i * 3 + 1] - cam.y) ** 2; if (d < 55 * 55) c.push([d, i]); }
        c.sort((a, b) => a[0] - b[0]); N.lamps = c.slice(0, 10).map(a => a[1]);
      }
    }
    // light level for particles that are not lit by the renderer
    const day = 1 - night, lightK = .16 + .84 * day;
    const sunC = this.w.sun.color;
    // leaves: a few per second per nearby tree, fewer at night
    const L = this.L, N = this.near;
    if (N.trees.length) {
      L.acc += dt * Math.min(14, N.trees.length * .45) * (.35 + .65 * day);
      while (L.acc >= 1) { L.acc -= 1; this.spawnLeaf(N.trees[Math.floor(Math.random() * N.trees.length)]); }
    }
    this.leafMat.uniforms.uLight.value.setRGB(.25 + .75 * lightK * (.7 + .3 * sunC.r), .25 + .75 * lightK * (.7 + .3 * sunC.g), .3 + .7 * lightK * (.7 + .3 * sunC.b));
    this.leafMat.uniforms.scale.value = innerHeight / 2;
    if (fog) { const U = this.leafMat.uniforms; U.fogColor.value.copy(fog.color); U.fogNear.value = fog.near; U.fogFar.value = fog.far; }
    this.updateLeaves(dt);
    // rooftop steam: heavier on cool nights and mornings; drifts with the wind
    const wind = _v.set(.8, 0, .45), gust = .6 + .4 * Math.sin(this.t * .37) * Math.sin(this.t * .19 + 1.3);
    const cool = .55 + .45 * Math.max(night, 1 - Math.min(1, Math.abs(hour - 7) / 3));
    const steamC = _c.setRGB(.86, .88, .9).multiplyScalar(lightK * .9 + .1);
    for (const v of N.vents) {
      v.acc += dt * (v.big ? 1.6 : 1) * cool * (.5 + v.h);
      while (v.acc >= 1) { v.acc -= 1; this.smoke.emit(_v.set(v.x + (Math.random() - .5) * 1.5, v.y, v.z + (Math.random() - .5) * 1.5), 1, { speed: .9, dir: { x: .8 * gust, y: 1.4, z: .45 * gust }, spread: .25, life: 7, size: [2, 9], alpha: .2, color: steamC.getHex(), gravity: -.25, drag: .25, vary: .06 }); }
    }
    // chimney smoke: morning and evening fires, a few houses at night
    const fires = .15 + .85 * Math.max(1 - Math.min(1, Math.abs(hour - 7.5) / 2), 1 - Math.min(1, Math.abs(hour - 19.5) / 3.5), night * .5);
    const smokeC = _c.setRGB(.62, .6, .58).multiplyScalar(lightK * .85 + .15);
    for (const c of N.chims) {
      if (c.h > fires) continue;
      c.acc += dt * 1.6;
      while (c.acc >= 1) { c.acc -= 1; this.smoke.emit(_v.set(c.x, c.y, c.z), 1, { speed: .5, dir: { x: .5 * gust, y: 1.1, z: .3 * gust }, spread: .2, life: 6.5, size: [.5, 4.5], alpha: .32, color: smokeC.getHex(), gravity: -.2, drag: .3, vary: .1 }); }
    }
    this.smoke.update(dt, fog);
    // fountain spray: jets from the centre falling back into the basin, mist drifting off
    const sprayC = _c.setRGB(.82, .9, .96).multiplyScalar(lightK * .9 + .1).getHex();
    for (const f of N.founts) {
      f.acc += dt * (this.touch ? 30 : 60);
      while (f.acc >= 1) {
        f.acc -= 1; const a = Math.random() * 6.28, r = Math.random() * .25;
        this.spray.emit(_v.set(f.x + Math.cos(a) * r, f.top, f.z + Math.sin(a) * r), 1, { speed: 3.2, dir: { x: Math.cos(a) * .35, y: 1.6, z: Math.sin(a) * .35 }, spread: .18, life: 1.4, size: [.05, .09], alpha: .55, color: sprayC, gravity: 9.8, drag: .2, floor: f.water, vary: .05 });
      }
      f.macc += dt * 3;
      while (f.macc >= 1) { f.macc -= 1; const a = Math.random() * 6.28, r = Math.random() * f.r * .6; this.spray.emit(_v.set(f.x + Math.cos(a) * r, f.water + .3, f.z + Math.sin(a) * r), 1, { speed: .3, dir: { x: .5, y: .3, z: .3 }, spread: .4, life: 3, size: [.6, 2.4], alpha: .1, color: sprayC, gravity: -.1, drag: .5 }); }
    }
    this.spray.update(dt, fog);
    this.updateMoths(dt, Math.max(0, (night - .3) / .7));
  }

  stats() { return { leaves: this.L.alpha.reduce((a, b) => a + (b > 0 ? 1 : 0), 0), smoke: this.smoke.live, spray: this.spray.live, vents: this.vents.length, chimneys: this.chimneys.length, fountains: this.fountains.length, moths: this.moths.visible ? this.M.n : 0 }; }

  dispose() {
    this.smoke.dispose(); this.spray.dispose();
    for (const o of [this.leaves, this.moths]) { o.removeFromParent(); o.geometry.dispose(); o.material.dispose(); }
  }
}
