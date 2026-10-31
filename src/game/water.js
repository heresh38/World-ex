// Shared water: a physically-shaded surface (two scrolling Blender-baked ocean normal maps, Fresnel sky reflection,
// sun glint, depth tint from a terrain depth texture, shoreline foam) plus DYNAMIC RING RIPPLES injected by impacts,
// splash VFX (droplets, spray plumes, mist, foam patches) and splash sounds.
//
// API (worlds create one as `world.water`; the game exposes it as `g.water`):
//   water.level                     surface height (m)
//   water.heightAt(x, z)            surface y, or null when there is no water at (x, z)
//   water.depthAt(x, z)             water depth there (<= 0 on land)
//   water.splash(pos, kind, opts)   kind: 'bullet' | 'bolt' | 'drop' | 'wade' | 'wake' | 'body' | 'car' | 'explosion', or a size
//                                   number (< .2 bullet, < .6 wake, < 1.5 body, < 3.5 car, else explosion). opts: {scale,
//                                   dir (Vector3 travel direction), silent}. No-op when pos is not on water; splashes that
//                                   land on top of a bigger one from the same instant are merged into it.
//   water.hitTest(from, to, kind)   first point where the segment from -> to crosses into the water, as {point, dist, normal};
//                                   null when it does not. Spawns the splash for `kind` (pass null for no splash).
//   water.update(dt)                ripples, VFX, and the automatic hooks below (call once per frame from the world)
// Automatic hooks: the player wading / swimming (buoyancy at chest depth), cars of g.vehicles and world.traffic entering
// and ploughing through water, ragdolls and corpses falling in, enemies and pedestrians wading, and every fx.explosion
// near the surface (the FX instance is wrapped once per world).
import * as THREE from 'three';
import { Puffs } from './puffs.js';

const MAXR = 24;
const UP = new THREE.Vector3(0, 1, 0);
const _a = new THREE.Vector3(), _b = new THREE.Vector3();

// amp (m), wavelength (m), speed (m/s), decay (1/s), life (s), foam radius (m), droplets, droplet speed, spray [w, h] (m), mist puffs, sound
const KINDS = {
  drop: { amp: .02, wl: .25, c: .8, decay: 1.6, life: 1.6, foam: 0, drops: 0, ds: 0, spray: null, mist: 0, sound: null },
  bullet: { amp: .055, wl: .32, c: 1.1, decay: 1.3, life: 2.6, foam: .45, drops: 16, ds: 3.4, spray: [.45, 1.3], mist: 0, sound: 'small' },
  bolt: { amp: .06, wl: .35, c: 1.1, decay: 1.2, life: 2.6, foam: .5, drops: 14, ds: 3, spray: [.5, 1.1], mist: 0, sound: 'small' },
  wade: { amp: .04, wl: .42, c: .85, decay: 1.1, life: 2.4, foam: .3, drops: 3, ds: 1.4, spray: null, mist: 0, sound: 'wade' },
  wake: { amp: .07, wl: .7, c: 1.6, decay: .9, life: 2.2, foam: .9, drops: 6, ds: 2.5, spray: null, mist: 0, sound: null },
  body: { amp: .2, wl: .9, c: 2.1, decay: .65, life: 5, foam: 1.7, drops: 80, ds: 5.5, spray: [2.2, 3.4], mist: 6, sound: 'big' },
  car: { amp: .32, wl: 1.25, c: 2.8, decay: .55, life: 6, foam: 3.4, drops: 150, ds: 8, spray: [5, 5.5], mist: 14, sound: 'huge' },
  explosion: { amp: .42, wl: 1.5, c: 3.6, decay: .5, life: 6.5, foam: 4.4, drops: 220, ds: 12.5, spray: [6.5, 12], mist: 24, column: true, sound: 'huge' },
};

const RANK = { drop: 0, wake: 1, wade: 1, bullet: 2, bolt: 2, body: 3, car: 4, explosion: 5 };
function soundFor(k) { return k.sound; }

export class Water {
  // Loads the Blender-baked water textures once (cached on the asset store).
  static async load(assets) {
    const T = assets.textures;
    const want = [['water_n1', 'water_n1.jpg', false], ['water_n2', 'water_n2.jpg', false], ['water_foam', 'water_foam.jpg', false], ['water_spray', 'water_spray.png', true]];
    await Promise.all(want.filter(([n]) => !T[n]).map(async ([n, f, c]) => { T[n] = await assets.loadTexture(f, c); }));
    return T;
  }

  // opts: {level, ground(x,z), bounds:[x0,z0,x1,z1], res, inside(x,z)?, deep, shallow, caps (open-water whitecaps 0..1),
  //        swell (strength of the long swell layer), clarity (how far you see into shallow water, m)}
  constructor(game, scene, opts) {
    this.g = game; this.scene = scene; this.o = opts;
    this.level = opts.level; this.ground = opts.ground; this.inside = opts.inside || null;
    this.time = 0; this.meshes = [];
    const T = game.assets.textures;
    this.depthTex = this.makeDepthTexture(opts.bounds, opts.res || 256);
    this.rip = Array.from({ length: MAXR }, () => new THREE.Vector4(0, 0, -99, 0));
    this.ripP = Array.from({ length: MAXR }, () => new THREE.Vector4(1, 1, 1, 0));
    this.ripLife = new Float32Array(MAXR);
    this.uniforms = {
      tN1: { value: T.water_n1 }, tN2: { value: T.water_n2 }, tFoam: { value: T.water_foam }, tDepth: { value: this.depthTex },
      uTime: { value: 0 }, uBounds: { value: new THREE.Vector4(...opts.bounds) }, uLevel: { value: this.level },
      uRip: { value: this.rip }, uRipP: { value: this.ripP },
      uDeep: { value: new THREE.Color(opts.deep || 0x05222c) }, uShallow: { value: new THREE.Color(opts.shallow || 0x1d6260) },
      uFoamCol: { value: new THREE.Color(opts.foamColor || 0xeef4f2) }, uCaps: { value: opts.caps === undefined ? .2 : opts.caps },
      uSwell: { value: opts.swell === undefined ? .55 : opts.swell }, uClarity: { value: opts.clarity || 3.5 },
      uSun: { value: (opts.sunDir || new THREE.Vector3(.3, .6, .2)).clone().normalize() }, uSunCol: { value: new THREE.Color(opts.sunColor || 0xffe0b8) },
    };
    this.material = this.makeMaterial();
    // VFX pools
    this.drops = new Puffs(scene, 1400, { soft: .25 });
    this.mist = new Puffs(scene, 260, { soft: .9 });
    this.drops.onLand = (x, z, s) => { if (s > .05 && Math.random() < .05) this.ripple(x, z, KINDS.drop, .6); };
    this.sprays = [];
    this.sprayTex = T.water_spray;
    this.light = new THREE.Color(opts.vfxLight || 0xe8ecf0);
    this.state = new WeakMap(); this.pollT = 0; this.recent = [];
    this.player = { depth: -1, stepT: 0, idleT: 0 };
    // every explosion near the surface throws up a column of water
    const fx = game.fx;
    if (fx && !fx.__water) {
      const orig = fx.explosion.bind(fx);
      fx.explosion = (p, r = 5) => { orig(p, r); fx.__water && fx.__water.onExplosion(p, r); };
    }
    if (fx) fx.__water = this;
  }

  // ---------------------------------------------------------------- queries
  depthAt(x, z) {
    if (this.inside && !this.inside(x, z)) return -1;
    return this.level - this.ground(x, z);
  }

  heightAt(x, z) { return this.depthAt(x, z) > .02 ? this.level : null; }

  hitTest(from, to, kind = 'bullet') {
    const L = this.level, a = from.y - L, b = to.y - L;
    if ((a >= 0) === (b >= 0)) return null;
    const t = a / (a - b);
    const x = from.x + (to.x - from.x) * t, z = from.z + (to.z - from.z) * t;
    if (this.heightAt(x, z) === null) return null;
    const point = new THREE.Vector3(x, L, z);
    if (kind) this.splash(point, kind, { dir: _a.subVectors(to, from).normalize().clone() });
    return { point, dist: from.distanceTo(point), normal: UP.clone() };
  }

  // ---------------------------------------------------------------- surface
  makeDepthTexture([x0, z0, x1, z1], res) {
    const data = new Uint8Array(res * res * 4);
    for (let j = 0; j < res; j++) for (let i = 0; i < res; i++) {
      const x = x0 + (i + .5) / res * (x1 - x0), z = z0 + (j + .5) / res * (z1 - z0);
      const d = this.depthAt(x, z), k = (j * res + i) * 4;
      data[k] = Math.max(0, Math.min(255, Math.round(d / 16 * 255)));
      data[k + 1] = d > 0 ? 255 : 0; data[k + 2] = 0; data[k + 3] = 255;
    }
    const t = new THREE.DataTexture(data, res, res, THREE.RGBAFormat);
    t.magFilter = t.minFilter = THREE.LinearFilter; t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping; t.needsUpdate = true;
    return t;
  }

  makeMaterial() {
    const U = this.uniforms;
    const m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .06, metalness: 0, transparent: true, envMapIntensity: 1.15 });
    m.name = 'water_surface';
    m.onBeforeCompile = sh => {
      Object.assign(sh.uniforms, U);
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
        varying vec3 vWP;
        uniform sampler2D tN1,tN2,tFoam,tDepth;uniform float uTime,uLevel,uCaps,uSwell,uClarity;uniform vec4 uBounds;
        uniform vec4 uRip[${MAXR}];uniform vec4 uRipP[${MAXR}];
        uniform vec3 uDeep,uShallow,uFoamCol,uSun,uSunCol;
        vec2 wSlope(sampler2D t,vec2 uv){vec3 n=texture2D(t,uv).xyz*2.-1.;return n.xy/max(.25,n.z);}`)
        .replace('#include <map_fragment>', `
        vec2 wp=vWP.xz;float wDist=length(cameraPosition-vWP);
        float det=1.-smoothstep(45.,420.,wDist);
        // two ripple layers crossing at an angle plus the long swell
        const mat2 rot=mat2(.8,.6,-.6,.8);
        vec2 s=wSlope(tN1,wp*.105+uTime*vec2(.022,.014))*.55*det;
        s+=transpose(rot)*wSlope(tN1,rot*wp*.067-uTime*vec2(.016,-.012))*.45*det;
        s+=wSlope(tN2,wp*.0105+uTime*vec2(.0045,.0028))*uSwell;
        s+=wSlope(tN2,wp*.0031-uTime*vec2(.0013,.002))*uSwell*.6;
        s*=.32+.68*det;
        // impact ripples: outward-travelling ring packets with trailing rings, plus a foam patch at the centre
        float rFoam=0.;
        for(int i=0;i<${MAXR};i++){
          vec4 R=uRip[i];if(R.w<=0.)continue;
          vec4 P=uRipP[i];float age=uTime-R.z;if(age<0.)continue;
          vec2 d=wp-R.xy;float r=length(d)+1e-3;
          float front=P.x*age;float sig=P.y*.9+.22*front;
          float x=r-front;if(x>sig*3.)continue;
          float k=6.2832/P.y;
          float env=exp(-x*x/(sig*sig))+.4*step(x,0.)*exp(x/(sig*2.5));
          float a=R.w*exp(-age*P.z)/(1.+.25*r);
          s-=d/r*(a*env*k*cos(k*x)*det);
          float fr=P.w*(.45+.55*min(1.,age*2.5));
          rFoam+=(1.-smoothstep(fr*.35,fr,r))*exp(-age*.75)*min(1.,R.w*8.)*step(.01,P.w);
        }
        vec3 wN=normalize(vec3(s.x,1.,s.y));
        // depth from the terrain depth texture (deep sea outside the mapped area)
        vec2 duv=(wp-uBounds.xy)/(uBounds.zw-uBounds.xy);
        vec4 dt4=texture2D(tDepth,clamp(duv,0.,1.));
        float inb=step(0.,duv.x)*step(duv.x,1.)*step(0.,duv.y)*step(duv.y,1.);
        float wDepth=mix(40.,dt4.r*16.,inb);
        // colour: shallow -> deep absorption, a little sky in the shallows
        vec3 wCol=mix(uShallow,uDeep,1.-exp(-wDepth/uClarity*.9));
        // foam: shoreline lace, open-water caps on swell crests, impact patches
        vec2 fuv=wp*.085+vec2(uTime*.012,-uTime*.008)+s*.05;
        float fT=texture2D(tFoam,fuv).r,fT2=texture2D(tFoam,wp*.031-uTime*.004).r;
        float shore=(1.-smoothstep(.05,1.1,wDepth))*inb;
        float shoreF=shore*smoothstep(.15,.6,fT*(.55+.45*sin(uTime*1.3+wDepth*7.)))*.85;
        float caps=uCaps*smoothstep(.55,.95,fT2)*smoothstep(4.,18.,wDepth)*det;
        float impact=clamp(rFoam,0.,1.)*(.35+.9*fT);
        float wFoam=clamp(shoreF+caps*.6+impact,0.,1.);
        diffuseColor.rgb=mix(wCol,uFoamCol,wFoam);
        vec3 V=normalize(cameraPosition-vWP);float fres=pow(1.-max(0.,dot(V,wN)),5.);
        diffuseColor.a=clamp(mix(.42,.96,smoothstep(0.,3.,wDepth))+fres*.5+wFoam,0.,1.);`)
        .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor=mix(roughnessFactor,.7,wFoam)+(1.-det)*.05;')
        .replace('#include <normal_fragment_maps>', 'normal=normalize((viewMatrix*vec4(wN,0.)).xyz);')
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        // light scattered inside the wave crests, facing the sun
        float scat=pow(max(0.,dot(normalize(vec3(-uSun.x,.2,-uSun.z)),V)),3.)*clamp(s.x*uSun.x+s.y*uSun.z+.25,0.,1.);
        totalEmissiveRadiance+=uShallow*uSunCol*(.10+.55*scat)*(1.-wFoam)+uFoamCol*wFoam*.12;`);
    };
    return m;
  }

  // a surface mesh (any flat geometry at y = 0 in its own space; positioned at the water level)
  addSurface(geo, { follow = false } = {}) {
    const w = new THREE.Mesh(geo, this.material);
    w.position.y = this.level; w.receiveShadow = true; w.renderOrder = 2; w.userData.follow = follow;
    this.scene.add(w); this.meshes.push(w);
    return w;
  }

  // ---------------------------------------------------------------- ripples + splashes
  ripple(x, z, K, scale = 1) {
    const cam = this.g.camera.position;
    let best = -1, bs = -1e9;
    for (let i = 0; i < MAXR; i++) {
      const age = this.time - this.rip[i].z;
      if (this.rip[i].w <= 0 || age > this.ripLife[i]) { best = i; break; }
      // replace the weakest, farthest ripple
      const sc = age / this.ripLife[i] + Math.hypot(this.rip[i].x - cam.x, this.rip[i].y - cam.z) / 60 - this.rip[i].w;
      if (sc > bs) { bs = sc; best = i; }
    }
    this.rip[best].set(x, z, this.time, K.amp * scale);
    this.ripP[best].set(K.c * Math.sqrt(scale), K.wl * Math.sqrt(scale), K.decay / Math.sqrt(scale), K.foam * scale);
    this.ripLife[best] = K.life * Math.max(1, scale);
  }

  splash(pos, kind = 'bullet', opts = {}) {
    if (typeof kind === 'number') kind = kind < .2 ? 'bullet' : kind < .6 ? 'wake' : kind < 1.5 ? 'body' : kind < 3.5 ? 'car' : 'explosion';
    if (!pos || this.heightAt(pos.x, pos.z) === null || pos.y > this.level + 8 || pos.y < this.level - 8) return;
    const K = KINDS[kind] || KINDS.bullet, sc = opts.scale || 1, rank = RANK[kind] || 0;
    // merge with a splash that just happened here (several systems may report the same impact)
    const now = this.time;
    this.recent = this.recent.filter(r => now - r.t < .25);
    for (const r of this.recent) if (r.rank >= rank && Math.hypot(r.x - pos.x, r.z - pos.z) < 1.5 + r.rank) return;
    this.recent.push({ x: pos.x, z: pos.z, t: now, rank });
    const y = this.level, p = _b.set(pos.x, y, pos.z).clone();
    this.ripple(p.x, p.z, K, sc);
    if (K.column || kind === 'car' || kind === 'body') this.ripple(p.x + .4, p.z - .3, K, sc * .6);    // a second, slower train
    const L = this.light;
    if (K.drops) {
      const dir = opts.dir ? _a.set(-opts.dir.x * .35, 1, -opts.dir.z * .35) : _a.set(0, 1, 0);
      this.drops.emit(p, Math.round(K.drops * Math.min(2, sc)), { speed: K.ds * Math.sqrt(sc), dir, spread: K.column ? .55 : .7, life: 1.4,
        size: [.05 * Math.sqrt(sc), .07 * Math.sqrt(sc)], alpha: .85, color: L, gravity: 9.8, drag: .15, floor: y - .05, jitter: K.foam * .5 * sc });
      if (kind !== 'bullet' && kind !== 'bolt' && kind !== 'wade')            // the sheet: a ring of drops thrown outward
        this.drops.emit(p, Math.round(K.drops * .6 * Math.min(2, sc)), { speed: K.ds * .6 * Math.sqrt(sc), ring: .9, spread: .15, life: 1.1,
          size: [.07 * sc, .1 * sc], alpha: .8, color: L, gravity: 9.8, drag: .4, floor: y - .05, jitter: K.foam * .6 * sc });
    }
    if (K.mist) this.mist.emit(_a.set(p.x, y + .5, p.z), Math.round(K.mist * Math.min(2, sc)), { speed: 1.4 * sc, spread: 1, dir: _b.set(0, .8, 0), life: 2.6,
      size: [1.2 * sc, 4.5 * sc], alpha: .32, color: L, gravity: -.25, drag: 1.2, jitter: K.foam * sc, jitterY: K.spray ? K.spray[1] * .5 * sc : 1 });
    if (K.spray) {
      const [w, h] = K.spray;
      this.spray(p, w * sc, h * sc, K.column ? .9 : .45, 0);
      if (K.column) { for (let k = 0; k < 4; k++) this.spray(_a.set(p.x + (Math.random() - .5) * 2.5 * sc, y, p.z + (Math.random() - .5) * 2.5 * sc), w * .55 * sc, h * (.5 + Math.random() * .3) * sc, 1.2 + Math.random() * .4, (Math.random() - .5) * .9); }
      else if (kind === 'car' || kind === 'body') { for (const s of [-1, 1]) this.spray(p, w * .7 * sc, h * .8 * sc, .8, s * .45); }
    }
    if (!opts.silent && soundFor(K) && this.g.audio.splash) this.g.audio.splash(p, soundFor(K));
  }

  spray(p, w, h, dur, rot) {
    let s = this.sprays.find(x => x.t <= 0);
    if (!s) {
      const m = new THREE.SpriteMaterial({ map: this.sprayTex, transparent: true, depthWrite: false, fog: true, color: this.light });
      s = { s: new THREE.Sprite(m), t: 0 }; s.s.center.set(.5, .02); s.s.renderOrder = 11; this.scene.add(s.s); this.sprays.push(s);
    }
    s.s.visible = true; s.s.position.copy(p); s.s.material.rotation = rot; s.w = w; s.h = h; s.t = s.max = dur;
    s.s.scale.set(w * .3, h * .1, 1);
  }

  onExplosion(p, r) {
    // water right under (or around) the blast: sample the centre and a ring
    let lv = this.heightAt(p.x, p.z);
    if (lv === null) for (let k = 0; k < 6 && lv === null; k++) { const a = k / 6 * Math.PI * 2; if (this.heightAt(p.x + Math.cos(a) * r * .7, p.z + Math.sin(a) * r * .7) !== null) lv = this.level; }
    if (lv === null) return;
    const h = p.y - lv;
    if (h > r * .9 || h < -4) return;
    this.splash(_a.set(p.x, lv, p.z), 'explosion', { scale: Math.max(.45, Math.min(1.5, r / 5)) * (1 - Math.max(0, h) / (r * 1.4)) });
  }

  // ---------------------------------------------------------------- per frame
  update(dt) {
    const g = this.g;
    this.time += dt; this.uniforms.uTime.value = this.time;
    const cam = g.camera.position;
    for (const m of this.meshes) if (m.userData.follow) { m.position.x = Math.round(cam.x / 50) * 50; m.position.z = Math.round(cam.z / 50) * 50; }
    for (let i = 0; i < MAXR; i++) if (this.rip[i].w > 0 && this.time - this.rip[i].z > this.ripLife[i]) this.rip[i].w = 0;
    if (g.player && g.state === 'play') this.updatePlayer(dt);
    this.pollT -= dt;
    if (this.pollT <= 0) { this.poll(.1 - this.pollT); this.pollT = .1; }
    for (const s of this.sprays) if (s.t > 0) {
      s.t -= dt; const k = 1 - s.t / s.max;
      const up = 1 - Math.pow(1 - Math.min(1, k * 3.2), 3);
      s.s.scale.set(s.w * (.35 + .65 * up + k * .25), s.h * up * (1 - .25 * k * k), 1);
      s.s.material.opacity = Math.min(1, (1 - k) * 1.6) * .92;
      if (s.t <= 0) s.s.visible = false;
    }
    this.drops.update(dt, this.scene.fog); this.mist.update(dt, this.scene.fog);
  }

  // the player: entry splash, wading ripples and sloshing, buoyancy (swims at chest depth)
  updatePlayer(dt) {
    const p = this.g.player, P = this.player;
    if (p.mode !== 'foot' || p.dead || p.climb) { P.depth = -1; p.swimming = false; return; }
    const lv = this.heightAt(p.pos.x, p.pos.z);
    const depth = lv === null ? -1 : lv - p.pos.y;
    const hs = Math.hypot(p.vel.x, p.vel.z);
    if (P.depth <= .05 && depth > .05) {
      if (p.vel.y < -3.5) this.splash(_a.set(p.pos.x, lv, p.pos.z), 'body', { scale: Math.max(.35, Math.min(1.1, -p.vel.y / 11)) });
      else this.splash(_a.set(p.pos.x, lv, p.pos.z), 'wade', { scale: 1.3 });
    }
    if (depth > .05) {
      P.stepT -= dt; P.idleT -= dt;
      const swim = depth > 1.15;
      if (hs > .5 && P.stepT <= 0) {
        P.stepT = swim ? .55 : p.running ? .28 : .4;
        const back = _a.set(p.pos.x - p.vel.x * .05, lv, p.pos.z - p.vel.z * .05);
        this.ripple(back.x, back.z, swim ? KINDS.wake : KINDS.wade, Math.min(1.6, .7 + depth * .5 + hs * .06));
        if (!swim && depth < .9) this.drops.emit(_a.set(p.pos.x, lv + .05, p.pos.z), 4 + (p.running ? 4 : 0), { speed: 1.2 + hs * .25, dir: _b.set(p.vel.x * .08, 1, p.vel.z * .08), spread: .6, life: .7, size: [.04, .05], alpha: .8, color: this.light, floor: lv - .05 });
        if (this.g.audio.splash) this.g.audio.splash(back, swim ? 'swim' : 'wade');
      } else if (hs <= .5 && P.idleT <= 0) { P.idleT = 1.3; this.ripple(p.pos.x, p.pos.z, KINDS.wade, .55); }
      // buoyancy: float with the head above the surface; light drag in the water
      if (swim) {
        p.vel.y = Math.max(p.vel.y < -6 ? p.vel.y * .6 : -1.5, Math.min(2.6, (depth - 1.2) * 3.2));
        const f = Math.max(0, 1 - dt * 1.2); p.vel.x *= f; p.vel.z *= f;
      }
      p.swimming = swim;
    } else p.swimming = false;
    P.depth = depth;
  }

  // cars, ragdolls and wading NPCs (10 Hz)
  poll(dt) {
    const g = this.g, w = g.world, cam = g.camera.position;
    const cars = new Set();
    for (const c of (g.vehicles && g.vehicles.cars) || []) cars.add(c);
    for (const t of (w && w.traffic && w.traffic.cars) || []) if (t.car) cars.add(t.car);
    for (const c of cars) {
      if (!c.pos) continue;
      const S = this.stateOf(c), lv = this.heightAt(c.pos.x, c.pos.z);
      const wet = lv !== null && c.pos.y < lv + .25;
      const v = c.vel || _a.set(0, 0, 0), sp = Math.hypot(v.x, v.z);
      if (wet && !S.wet) this.splash(_b.set(c.pos.x, lv, c.pos.z), 'car', { scale: Math.max(.55, Math.min(1.6, .6 + (sp + Math.abs(v.y || 0)) / 22)) });
      else if (wet && sp > 2) {
        S.t -= dt;
        if (S.t <= 0) { S.t = .22; this.ripple(c.pos.x - v.x * .1, c.pos.z - v.z * .1, KINDS.wake, Math.min(2, .8 + sp / 15)); if (sp > 8) this.drops.emit(_b.set(c.pos.x, lv + .2, c.pos.z), 10, { speed: 2 + sp * .2, dir: _a.set(0, 1, 0), spread: .9, life: 1, size: [.08, .12], alpha: .7, color: this.light, floor: lv - .05, jitter: 3 }); }
      }
      S.wet = wet;
    }
    const bodies = [];
    for (const e of (g.enemies && g.enemies.list) || []) bodies.push(e);
    for (const q of (w && w.population && w.population.peds) || []) bodies.push(q);
    let wades = 0;
    for (const e of bodies) {
      if (!e.pos) continue;
      const S = this.stateOf(e);
      const rag = e.av && e.av.rag && e.av.rag.p && e.av.rag.p.hips;
      if (rag) {
        const lv = this.heightAt(rag.x, rag.z), wet = lv !== null && rag.y < lv + .1;
        if (wet && !S.ragWet && S.ragSeen) this.splash(_b.set(rag.x, lv, rag.z), 'body', { scale: .8 });
        S.ragWet = wet; S.ragSeen = true;
        continue;
      }
      if (e.alive === false) continue;
      const lv = this.heightAt(e.pos.x, e.pos.z);
      if (lv === null || e.pos.y > lv) { S.last = null; continue; }
      if (S.last && wades < 4 && Math.hypot(e.pos.x - cam.x, e.pos.z - cam.z) < 90) {
        const moved = Math.hypot(e.pos.x - S.last.x, e.pos.z - S.last.z);
        S.t -= dt;
        if (moved > .05 && S.t <= 0) { S.t = .45; wades++; this.ripple(e.pos.x, e.pos.z, KINDS.wade, Math.min(1.4, .8 + (lv - e.pos.y) * .4)); }
      }
      S.last = S.last || new THREE.Vector3(); S.last.copy(e.pos);
    }
  }

  stateOf(o) { let s = this.state.get(o); if (!s) { s = { wet: null, t: 0 }; this.state.set(o, s); } return s; }

  dispose() {
    this.drops.dispose(); this.mist.dispose();
    this.sprays.forEach(s => { s.s.removeFromParent(); s.s.material.dispose(); });
    this.meshes.forEach(m => m.removeFromParent());
    this.material.dispose(); this.depthTex.dispose();
    if (this.g.fx && this.g.fx.__water === this) this.g.fx.__water = null;
  }
}
