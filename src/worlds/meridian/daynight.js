// Earth's day/night cycle, driven by g.clock (src/game/clock.js). Every frame it moves the sun along its arc (east at
// 06:00, south at noon, west at 20:00) and the moon through the night, and blends a hand-tuned palette of keyframes
// (warm orange dawn -> white noon -> golden hour -> red sunset -> blue/purple dusk -> deep blue night) into the sun /
// moon light, hemisphere light, fog, sky dome (stars + moon at night), water, exposure and bloom.
// The reflection probe (PMREM of a sky copy with a dark street below the horizon) is rebuilt only when the sun has moved
// a few degrees or the light changed noticeably (~twice a real minute at the default day length), never every frame.
// Night city: SKY holds the shared uniforms the window shaders read (meridian/downtown.js and nightWindows() below for
// the older city kit): lit-room fractions per kind of building and hour, so windows switch on and off through the
// evening. Emissive kit materials (street lamps, signs, crown lights, kerb strips) are scaled by night, and every street
// lamp gets a soft pool of light on the ground and a halo (one instanced draw call each, faded out by day).
import * as THREE from 'three';
import { atmosphereSky } from '../sky.js';
import { Clock } from '../../game/clock.js';

// shared uniforms (same objects in every material that uses them)
export const SKY = {
  night: { value: 0 },        // 0 day .. 1 full night
  hour: { value: 12 },
  time: { value: 0 },         // seconds, for flicker
  litHome: { value: .1 }, litOffice: { value: .7 }, litShop: { value: 1 },
  win: { value: .3 },         // window emission gain
};

const smooth = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);
const C = h => new THREE.Color(h);

// palette keyframes by hour (colours are sRGB hex)
const NIGHT = { sun: 0x000000, sunI: 0, hemiS: 0x5a74b8, hemiG: 0x2a2632, hemiI: .95, top: 0x030817, hor: 0x18223f, sunC: 0x000000,
  fog: 0x141b31, fogN: 110, fogF: 1100, exp: 1.32, env: .6, bloom: .62, bloomT: .82, cloud: 0x34405c, glow: 0x3a2618, gnd: 0x06080d };
const KEYS = [
  [0, NIGHT], [4.4, NIGHT],
  [5.3, { sun: 0x000000, sunI: 0, hemiS: 0x6274aa, hemiG: 0x2a2630, hemiI: .95, top: 0x0b1838, hor: 0x434466, sunC: 0x9a5060,
    fog: 0x30334e, fogN: 120, fogF: 1150, exp: 1.26, env: .62, bloom: .55, bloomT: .88, cloud: 0x585470, glow: 0x281a10, gnd: 0x0b0c11 }],
  [6.1, { sun: 0xff8a50, sunI: 1.35, hemiS: 0x8a8ebc, hemiG: 0x4c3a34, hemiI: .8, top: 0x2a4c8a, hor: 0xf29a6a, sunC: 0xffa262,
    fog: 0xb88a7a, fogN: 140, fogF: 1200, exp: 1.12, env: .75, bloom: .42, bloomT: 1, cloud: 0xffc4a4, glow: 0x000000, gnd: 0x2a2224 }],
  [7.3, { sun: 0xffc690, sunI: 2.6, hemiS: 0x9ab6de, hemiG: 0x5a4a3a, hemiI: .88, top: 0x3a6ab0, hor: 0xe8c4a4, sunC: 0xffd6a8,
    fog: 0xd0c0b2, fogN: 170, fogF: 1400, exp: 1.04, env: .85, bloom: .3, bloomT: 1, cloud: 0xfff0e2, glow: 0x000000, gnd: 0x36312e }],
  [10, { sun: 0xfff0dc, sunI: 3.1, hemiS: 0xa6c2ea, hemiG: 0x5e5446, hemiI: .95, top: 0x2c62b2, hor: 0xb6cee6, sunC: 0xfff2dc,
    fog: 0xb8cbe0, fogN: 200, fogF: 1700, exp: 1.0, env: .9, bloom: .25, bloomT: 1, cloud: 0xffffff, glow: 0x000000, gnd: 0x383838 }],
  [13.5, { sun: 0xfff8ee, sunI: 3.3, hemiS: 0xaccaf0, hemiG: 0x645a4c, hemiI: 1.0, top: 0x2a5eb0, hor: 0xbcd4ec, sunC: 0xffffff,
    fog: 0xc0d4e6, fogN: 220, fogF: 1800, exp: 1.0, env: .9, bloom: .22, bloomT: 1, cloud: 0xffffff, glow: 0x000000, gnd: 0x3a3a3a }],
  [16.8, { sun: 0xffeccc, sunI: 3.15, hemiS: 0xa4c0e4, hemiG: 0x60543f, hemiI: .95, top: 0x2f62ac, hor: 0xc8d2dc, sunC: 0xfff0d8,
    fog: 0xc6cfd8, fogN: 200, fogF: 1650, exp: 1.02, env: .9, bloom: .25, bloomT: 1, cloud: 0xfff8f0, glow: 0x000000, gnd: 0x3a3836 }],
  // the original golden hour look
  [18.6, { sun: 0xffd2a0, sunI: 3.0, hemiS: 0x9cb8e0, hemiG: 0x5a4636, hemiI: .95, top: 0x3a6aa8, hor: 0xf2b27a, sunC: 0xffd9a8,
    fog: 0xd9a888, fogN: 160, fogF: 1300, exp: 1.05, env: .9, bloom: .3, bloomT: 1, cloud: 0xffe8d2, glow: 0x000000, gnd: 0x3c302a }],
  [19.55, { sun: 0xff7038, sunI: 1.7, hemiS: 0x8a86b0, hemiG: 0x42302a, hemiI: .8, top: 0x30508c, hor: 0xff8a50, sunC: 0xff9450,
    fog: 0xb07868, fogN: 150, fogF: 1250, exp: 1.1, env: .75, bloom: .4, bloomT: .95, cloud: 0xffa486, glow: 0x100804, gnd: 0x2a1e22 }],
  [20.35, { sun: 0xc06050, sunI: 0, hemiS: 0x6466a8, hemiG: 0x2e2636, hemiI: .9, top: 0x151e4c, hor: 0x6c4a7c, sunC: 0xd8705a,
    fog: 0x3c3658, fogN: 130, fogF: 1150, exp: 1.22, env: .64, bloom: .55, bloomT: .88, cloud: 0x7c5c84, glow: 0x2a1a10, gnd: 0x0c0a12 }],
  [21.4, NIGHT], [24, NIGHT],
].map(([h, k]) => {
  const o = { h };
  for (const [n, v] of Object.entries(k)) o[n] = ['sunI', 'hemiI', 'fogN', 'fogF', 'exp', 'env', 'bloom', 'bloomT'].includes(n) ? v : C(v);
  return o;
});

// lit-room fractions through the day: homes light up in the evening, offices in working hours, shops while open
const LIT = {
  home: [[0, .2], [1.5, .1], [4.5, .05], [6, .22], [7.5, .26], [9, .07], [16, .07], [18, .3], [20, .55], [22, .5], [23.5, .3], [24, .2]],
  office: [[0, .06], [6, .06], [7.5, .55], [9, .8], [17, .8], [19, .35], [21, .14], [24, .06]],
  shop: [[0, .12], [7, .12], [8.5, 1], [21, 1], [22.5, .3], [24, .12]],
};
const curve = (K, h) => { for (let i = 1; i < K.length; i++) if (h <= K[i][0]) { const a = K[i - 1], b = K[i], t = smooth((h - a[0]) / (b[0] - a[0])); return a[1] + (b[1] - a[1]) * t; } return K[0][1]; };

// sun arc: rises in the east (+x) at 06:00, south (+z) at noon, sets in the west at 20:00; below the horizon at night
export function sunDirection(h, out = new THREE.Vector3()) {
  let az, el;
  if (h >= 6 && h <= 20) { const t = (h - 6) / 14; az = Math.PI * t; el = 1.0 * Math.sin(Math.PI * t); }
  else { const t = ((h - 20 + 24) % 24) / 10; az = Math.PI + Math.PI * t; el = -.9 * Math.sin(Math.PI * t); }
  return out.set(Math.cos(az) * Math.cos(el), Math.sin(el), Math.sin(az) * Math.cos(el) * .82 + .18 * Math.cos(el)).normalize();
}
// the moon crosses the sky through the night (east at dusk, high in the south at 01:00, west at dawn)
export function moonDirection(h, out = new THREE.Vector3()) {
  const t = ((h - 19 + 24) % 24) / 12;
  if (t > 1) return out.set(0, -1, 0);
  const az = Math.PI * t, el = .3 + .7 * Math.sin(Math.PI * t);
  return out.set(Math.cos(az) * Math.cos(el), Math.sin(el), Math.sin(az) * Math.cos(el)).normalize();
}

// Older city kit (city.py: facade/ribbon/brick with facade_e/ribbon_e emissive maps): switch window bands on and off
// per 3 m world cell and time slot so the mid-ring towers change through the night too.
export function nightWindows(m) {
  m.emissive = new THREE.Color(1, .8, .56); m.emissiveIntensity = 1;
  m.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, { uNight: SKY.night, uHour: SKY.hour, uLit: SKY.litHome, uWin: SKY.win });
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWinP;')
      .replace('#include <worldpos_vertex>', `#include <worldpos_vertex>
        { vec4 wp4 = vec4(transformed, 1.);
        #ifdef USE_INSTANCING
          wp4 = instanceMatrix * wp4;
        #endif
        vWinP = (modelMatrix * wp4).xyz; }`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
        varying vec3 vWinP;uniform float uNight,uHour,uLit,uWin;
        float wxH(vec3 p){p=fract(p*.3183099+.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        { vec3 cell = floor(vWinP / vec3(3.1, 3.5, 3.1));
          float h1 = wxH(cell * .71 + 3.3), slot = floor(uHour * .7 + h1 * 7.);
          float on = step(wxH(cell * 1.37 + slot * 11.1 + 1.7), uLit);
          vec3 lc = mix(vec3(1., .76, .5), vec3(.82, .9, 1.), step(.8, h1));
          totalEmissiveRadiance *= lc * (on * (.55 + .45 * h1) * uWin * 1.6 + .04); }`);
  };
  m.customProgramCacheKey = () => 'citywin';
  m.needsUpdate = true;
}

const _v = new THREE.Vector3(), _c = new THREE.Color(), _m = new THREE.Matrix4();

export class DayNight {
  // world: EarthWorld with sun, hemi, sky, water, lampMats
  constructor(world) {
    this.w = world; this.g = world.g; this.scene = world.scene;
    if (!this.g.clock) this.g.clock = new Clock(this.g.save);
    this.p = {}; for (const k of Object.keys(KEYS[0])) if (k !== 'h') this.p[k] = typeof KEYS[0][k] === 'number' ? 0 : new THREE.Color();
    this.sunD = new THREE.Vector3(); this.moonD = new THREE.Vector3(); this.lightD = new THREE.Vector3(0, 1, 0);
    this.lightC = new THREE.Color(); this.lightI = 0;
    this.envBuilds = 0; this.envT = 0; this.lastEnv = { dir: new THREE.Vector3(), night: -1, hour: -99 };
    this.glows = [];
    this.touch = !!this.g.renderer.touch;
    // the reflection probe: a sky copy whose lower half is a dark street
    this.envSky = atmosphereSky('#3a6aa8', '#f2b27a', '#ffd9a8', world.sunDir, { groundK: .85 });
    this.envSky.material.uniforms.time.value = 40;
    this.envScene = new THREE.Scene().add(this.envSky);
    this.pmrem = new THREE.PMREMGenerator(this.g.renderer.r);
    this.envRT = null;
    this.scene.environmentIntensity = .9;
  }

  // emissive kit materials scaled between day and night (lamps are off by day)
  registerGlows() {
    const seen = new Set();
    const rule = n => /^street_light$/.test(n) ? [.06, 1.9] : /^dt_plain_glow$/.test(n) ? [.75, 1.25] : /^dt_glow_/.test(n) ? [.55, 1.4]
      : /^street_glow$|^kerb_glow$/.test(n) ? [.7, 1.45] : /^(neon_|sign_|beacon)/.test(n) ? [.65, 1.35] : null;
    this.scene.traverse(o => {
      if (!o.isMesh) return;
      for (const m of [].concat(o.material)) {
        if (!m || seen.has(m) || !m.emissive) continue; seen.add(m);
        const r = rule(m.name || ''); if (r) this.glows.push({ m, base: m.emissiveIntensity, day: r[0], night: r[1] });
      }
    });
  }

  // a soft pool of lamp light on the ground under every street lamp and a halo round the lamp head (VFX only)
  buildLampPools(lamps) {
    if (!lamps.length) return;
    const n = lamps.length;
    const geo = new THREE.PlaneGeometry(1, 1); geo.rotateX(-Math.PI / 2);
    const pmat = new THREE.ShaderMaterial({
      uniforms: { uI: { value: 0 }, uCol: { value: new THREE.Color(1, .74, .45) }, fogColor: { value: new THREE.Color() }, fogNear: { value: 1 }, fogFar: { value: 2 } },
      vertexShader: `varying vec2 vUv;varying float vD;void main(){vUv=uv;vec4 mv=modelViewMatrix*instanceMatrix*vec4(position,1.);vD=-mv.z;gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `varying vec2 vUv;varying float vD;uniform float uI,fogNear,fogFar;uniform vec3 uCol,fogColor;
        void main(){vec2 p=vUv*2.-1.;float r=dot(p,p);if(r>1.)discard;float a=(1.-r);a=a*a*(.35+.65*exp(-r*5.));
          float f=1.-smoothstep(fogNear,fogFar,vD)*.85;gl_FragColor=vec4(uCol*a*uI*f,1.);}`,
      blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -8,
    });
    const pools = new THREE.InstancedMesh(geo, pmat, n);
    const heads = new Float32Array(n * 3), q = new THREE.Quaternion(), s = new THREE.Vector3();
    lamps.forEach((L, i) => {
      heads[i * 3] = L.head.x; heads[i * 3 + 1] = L.head.y; heads[i * 3 + 2] = L.head.z;
      const r = L.r || 9;
      _m.compose(_v.set(L.head.x, (L.ground ?? 0) + .07, L.head.z), q.identity(), s.set(r * 2, 1, r * 2));
      pools.setMatrixAt(i, _m);
    });
    pools.frustumCulled = false; pools.renderOrder = 3; pools.visible = false;
    this.scene.add(pools); this.pools = pools;
    const hg = new THREE.BufferGeometry(); hg.setAttribute('position', new THREE.BufferAttribute(heads, 3));
    const hmat = new THREE.ShaderMaterial({
      uniforms: { uI: { value: 0 }, scale: { value: innerHeight / 2 }, uCol: { value: new THREE.Color(1, .8, .55) } },
      vertexShader: `uniform float scale;varying float vF;void main(){vec4 mv=modelViewMatrix*vec4(position,1.);vF=clamp(1.-(-mv.z-150.)/250.,0.,1.);gl_PointSize=min(256.,2.6*scale/max(.5,-mv.z));gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `uniform float uI;uniform vec3 uCol;varying float vF;void main(){vec2 p=gl_PointCoord-.5;float d=dot(p,p)*4.;if(d>1.)discard;float a=pow(1.-d,2.2);gl_FragColor=vec4(uCol*a*uI*vF,1.);}`,
      blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, toneMapped: true,
    });
    this.halos = new THREE.Points(hg, hmat); this.halos.frustumCulled = false; this.halos.renderOrder = 11; this.halos.visible = false;
    this.scene.add(this.halos);
    this.lampHeads = heads;
  }

  palette(h) {
    let i = 1; while (i < KEYS.length - 1 && h > KEYS[i].h) i++;
    const a = KEYS[i - 1], b = KEYS[i], t = smooth((h - a.h) / Math.max(1e-3, b.h - a.h)), P = this.p;
    for (const k in P) { if (typeof P[k] === 'number') P[k] = a[k] + (b[k] - a[k]) * t; else P[k].copy(a[k]).lerp(b[k], t); }
    return P;
  }

  update(dt, force = false) {
    const g = this.g, w = this.w, clk = g.clock; if (!clk) return;
    const h = clk.hour, P = this.palette(h);
    sunDirection(h, this.sunD); moonDirection(h, this.moonD);
    const sinEl = this.sunD.y;
    const sunK = smooth((sinEl + .035) / .105), moonK = smooth((-.02 - sinEl) / .1);
    const night = smooth((-sinEl + .02) / .2);              // 0 while the sun is up, 1 once it is 11 degrees below
    SKY.night.value = night; SKY.hour.value = h; SKY.time.value = g.time || 0;
    SKY.litHome.value = curve(LIT.home, h); SKY.litOffice.value = curve(LIT.office, h); SKY.litShop.value = curve(LIT.shop, h);
    SKY.win.value = .32 + .68 * smooth((night - .05) / .7);
    // the one shadow-casting light: the sun by day, the moon by night (both are dim around the switch)
    const useSun = sinEl > -.02;
    if (useSun) { this.lightD.copy(this.sunD); this.lightC.copy(P.sun); this.lightI = P.sunI * sunK; }
    else { this.lightD.copy(this.moonD.y > .05 ? this.moonD : _v.set(.2, 1, .3).normalize()); this.lightC.setRGB(.62, .72, 1); this.lightI = .42 * moonK; }
    w.sunDir.copy(this.lightD);
    // (castShadow stays on: toggling it would recompile every material)
    const sun = w.sun; sun.color.copy(this.lightC); sun.intensity = this.lightI;
    if (w.hemi) { w.hemi.color.copy(P.hemiS); w.hemi.groundColor.copy(P.hemiG); w.hemi.intensity = P.hemiI; }
    const fog = this.scene.fog; if (fog) { fog.color.copy(P.fog); fog.near = P.fogN; fog.far = P.fogF; }
    const set = (U, cloudBoost = 1) => {
      U.top.value.copy(P.top); U.hor.value.copy(P.hor); U.sunC.value.copy(P.sunC); U.sunDir.value.copy(this.sunD);
      U.fogC.value.copy(P.fog); U.night.value = night; U.moonDir.value.copy(this.moonD); U.cloudC.value.copy(P.cloud).multiplyScalar(cloudBoost);
      U.glowC.value.copy(P.glow); U.sunK.value = 1;
    };
    if (w.sky) set(w.sky.material.uniforms);
    if (w.water) { const U = w.water.uniforms; U.uSun.value.copy(this.lightD); U.uSunCol.value.copy(this.lightC).multiplyScalar(Math.min(1, .25 + this.lightI / 3)); }
    const R = g.renderer;
    R.r.toneMappingExposure = P.exp;
    if (R.bloom) { R.bloom.strength = P.bloom; R.bloom.threshold = P.bloomT; }
    R.bloomParams = [P.bloom, P.bloomT, .4];
    this.scene.environmentIntensity = P.env;
    for (const G of this.glows) G.m.emissiveIntensity = G.base * (G.day + (G.night - G.day) * night);
    // lamp pools and halos
    const lampK = smooth((night - .08) / .5);
    if (this.pools) {
      this.pools.visible = this.halos.visible = lampK > .01;
      this.pools.material.uniforms.uI.value = .55 * lampK;
      this.halos.material.uniforms.uI.value = 1.6 * lampK;
      this.halos.material.uniforms.scale.value = innerHeight / 2;
      if (fog) { const U = this.pools.material.uniforms; U.fogColor.value.copy(fog.color); U.fogNear.value = fog.near; U.fogFar.value = fog.far; }
    }
    // reflection probe: rebuilt when the sun moved ~3.5 degrees, the night level changed or after a while
    this.envT += dt;
    const L = this.lastEnv;
    if (force || !this.envRT || this.sunD.dot(L.dir) < .9981 || Math.abs(night - L.night) > .06 || (this.envT > 45 && Math.abs(h - L.hour) > .05)) this.rebuildEnv(P, night);
    // the HUD clock (minutes)
    const lab = clk.label(); if (lab !== this.label) { this.label = lab; g.hud.setTime && g.hud.setTime(lab); }
  }

  rebuildEnv(P, night) {
    const U = this.envSky.material.uniforms;
    U.top.value.copy(P.top); U.hor.value.copy(P.hor); U.sunC.value.copy(P.sunC); U.sunDir.value.copy(this.sunD);
    U.fogC.value.copy(P.fog); U.night.value = night * .6; U.moonDir.value.copy(this.moonD); U.cloudC.value.copy(P.cloud);
    U.glowC.value.copy(P.glow); U.gndC.value.copy(P.gnd); U.sunK.value = .6;
    const old = this.envRT;
    this.envRT = this.pmrem.fromScene(this.envScene, .04, .1, 100, { size: this.touch ? 128 : 256 });
    this.scene.environment = this.envRT.texture;
    if (old) old.dispose();
    this.envBuilds++; this.envT = 0;
    this.lastEnv.dir.copy(this.sunD); this.lastEnv.night = night; this.lastEnv.hour = this.g.clock.hour;
  }

  dispose() {
    this.envRT && this.envRT.dispose(); this.pmrem.dispose();
    this.envSky.geometry.dispose(); this.envSky.material.dispose();
    if (this.pools) { this.pools.geometry.dispose(); this.pools.material.dispose(); this.halos.geometry.dispose(); this.halos.material.dispose(); }
  }
}
