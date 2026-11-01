// Player weapons: every shot is a real projectile. Kinetic bullets fly at muzzle velocity and drop with gravity,
// energy bolts fly straight, horror guns spit arcing goo (acid globs, bile spray, spore pods that hatch homing
// parasites) that splashes, stains surfaces and keeps eating with damage over time. Also: bursts, pellets, rockets
// with splash, perks, reload, switching, mounted sights and the material looks (edge wear, living flesh).
import * as THREE from 'three';
import { ARCHETYPES, RARITY, SHADERS, SIGHTS, weaponSight, sightZoom } from './data.js';
import { weaponStats } from './state.js';

const _o = new THREE.Vector3(), _d = new THREE.Vector3(), _m = new THREE.Vector3(), _t = new THREE.Vector3(), _a = new THREE.Vector3(),
  _b = new THREE.Vector3(), _c = new THREE.Vector3(), _col = new THREE.Color(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _M = new THREE.Matrix4();
const Z = new THREE.Vector3(0, 0, 1);
const G = 9.81;
const MAX_ROUNDS = 256, MAX_GOO = 160;

// living guns share one clock; 'gape' spikes when they fire
const BIO = { t: { value: 0 }, gape: 0 };

// edge-wear looks per material (what shows through where the `_wear` attribute is high)
const WEAR = {
  gun_steel: [0x8d9298, .2, 1], gun_parkerized: [0x7d8084, .32, .9], gun_polymer: [0x4a4c50, .45, 0], gun_polymer_od: [0x23251f, .5, 0],
  gun_wood: [0xa8794a, .72, 0], gun_optic: [0x7d8084, .3, .9], gun_body: [0x9a9da3, .24, .95], gun_metal: [0xa3a8b0, .2, 1],
  gun_dark: [0x6c7076, .3, .9], gun_grip: [0x3a3b3e, .6, .2],
};
const GOO = {
  spit: { color: 0x7cff3a, size: .065, grav: 1, life: 3 },
  bile: { color: 0xc8e040, size: .032, grav: 1.3, life: 1.1 },
  brood: { color: 0xd8607a, size: .1, grav: .85, life: 2.4 },
  larva: { color: 0xc0506a, size: .045, grav: 0, life: 4.5 },
};

function addWear(m, look) {
  const col = new THREE.Color(look[0]);
  m.onBeforeCompile = sh => {
    sh.uniforms.uWearC = { value: col }; sh.uniforms.uWearR = { value: look[1] }; sh.uniforms.uWearM = { value: look[2] };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute float _wear;\nvarying float vWear;\nvarying vec3 vWP;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWear = _wear; vWP = position;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
uniform vec3 uWearC; uniform float uWearR, uWearM; varying float vWear; varying vec3 vWP;
float wHash(vec3 p) { p = fract(p * .3183099 + .1); p *= 17.; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float wNoise(vec3 x) { vec3 i = floor(x), f = fract(x); f = f * f * (3. - 2. * f);
  return mix(mix(mix(wHash(i), wHash(i + vec3(1, 0, 0)), f.x), mix(wHash(i + vec3(0, 1, 0)), wHash(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(wHash(i + vec3(0, 0, 1)), wHash(i + vec3(1, 0, 1)), f.x), mix(wHash(i + vec3(0, 1, 1)), wHash(i + vec3(1, 1, 1)), f.x), f.y), f.z); }`)
      .replace('#include <map_fragment>', `#include <map_fragment>
float wn = wNoise(vWP * 220.) * .55 + wNoise(vWP * 50.) * .45;
float wv = smoothstep(.32, .72, vWear * (.45 + wn));
diffuseColor.rgb = mix(diffuseColor.rgb, uWearC, wv);`)
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor = mix(roughnessFactor, uWearR, wv);')
      .replace('#include <metalnessmap_fragment>', '#include <metalnessmap_fragment>\nmetalnessFactor = mix(metalnessFactor, uWearM, wv);');
  };
  m.customProgramCacheKey = () => 'gunwear';
}

// living flesh: slow peristaltic wobble along the gun, wet darkening in the crevices
function addFlesh(m) {
  m.onBeforeCompile = sh => {
    sh.uniforms.uBioT = BIO.t;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform float uBioT;\nattribute float _wear;\nvarying float vWear;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
vWear = _wear;
transformed += objectNormal * (sin(uBioT * 3.1 + position.z * 55. + position.x * 40.) * .0011 + sin(uBioT * 1.7 - position.z * 18.) * .0016);`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vWear;')
      .replace('#include <map_fragment>', '#include <map_fragment>\ndiffuseColor.rgb *= 1. - vWear * .5;')
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor = max(.06, roughnessFactor - vWear * .25);');
  };
  m.customProgramCacheKey = () => 'bioflesh';
}

function animateBio(mesh) {
  const m = mesh.material, base = m.emissiveIntensity || 1, phase = Math.random() * 6;
  mesh.onBeforeRender = () => {
    const t = performance.now() / 1000; BIO.t.value = t;
    const beat = .5 + .5 * Math.sin(t * 2.3 + phase * .05);
    const dict = mesh.morphTargetDictionary, inf = mesh.morphTargetInfluences;
    if (dict && inf) {
      if (dict.pulse !== undefined) inf[dict.pulse] = beat;
      if (dict.gape !== undefined) inf[dict.gape] = Math.max(BIO.gape, .06 + .06 * Math.sin(t * 1.3));
    }
    if (m.name === 'bio_glow') m.emissiveIntensity = base * (.45 + .75 * beat + BIO.gape * .6);
  };
}

export class Weapons {
  constructor(game) {
    this.g = game;
    Weapons.assets = game.assets;
    Weapons.shareTextures(game.assets);
    this.slot = 0; this.cool = 0; this.reloading = 0; this.swap = 0; this.burstLeft = 0; this.burstCool = 0;
    this.ammo = {};       // uid -> {mag, reserve}
    this.lastFire = 9; this.rampage = 0; this.rampageT = 0;
    this.rockets = [];
    this.rounds = []; this.goo = []; this.afflicted = new Map(); this.dripT = 0;
    // bullet / bolt streaks: one instanced draw
    const sg = new THREE.CylinderGeometry(1, .35, 1, 6, 1, true); sg.rotateX(Math.PI / 2); sg.translate(0, 0, .5);
    this.streaks = new THREE.InstancedMesh(sg, new THREE.MeshBasicMaterial({ color: 0xffffff, blending: THREE.AdditiveBlending, transparent: true,
      depthWrite: false, toneMapped: false }), MAX_ROUNDS);
    this.streaks.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_ROUNDS * 3), 3);
    this.streaks.frustumCulled = false; this.streaks.count = 0;
    // goo globs, droplets, spore pods and parasites: one instanced draw
    // textured with the shared Writhe sac set (veined, glistening membrane) and lit from within by the same map, so a
    // pod or glob never reads as a black ball in shade; instanceColor tints each kind
    const gtex = (f, srgb) => { const t = new THREE.TextureLoader().load('assets/textures/' + f); t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace; t.anisotropy = 4; return t; };
    const gmap = gtex('hx_sac_c.jpg', true);
    this.globs = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .32, metalness: 0,
      map: gmap, normalMap: gtex('hx_sac_n.jpg', false), emissive: 0xffffff, emissiveMap: gmap, emissiveIntensity: .2 }), MAX_GOO);
    this.globs.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_GOO * 3), 3);
    // the inner glow takes each glob's own tint (spit green, bile yellow, brood pink) instead of the raw map colour
    this.globs.material.onBeforeCompile = sh => {
      sh.fragmentShader = sh.fragmentShader.replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n#ifdef USE_COLOR\ntotalEmissiveRadiance *= vColor.rgb;\n#endif');
    };
    this.globs.frustumCulled = false; this.globs.count = 0; this.globs.castShadow = false;
  }

  // Every gun GLB embeds its own copy of the shared texture sets (wpn_steel_*, wpn_wood_*, bio_flesh_*...): keep one
  // texture per image name across all gun models and release the duplicates' decoded images (saves ~250 MB).
  static shareTextures(assets) {
    if (!assets || !assets.models || Weapons.texShared) return;
    Weapons.texShared = true;
    const byName = new Map(), dropped = new Set();
    const KEYS = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap', 'aoMap', 'clearcoatMap', 'clearcoatNormalMap'];
    for (const [name, gltf] of Object.entries(assets.models)) {
      if (!/^gun_/.test(name) || !gltf || !gltf.scene) continue;
      gltf.scene.traverse(o => {
        if (!o.isMesh) return;
        for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
          for (const k of KEYS) {
            const t = m[k]; if (!t || !t.name) continue;
            const keep = byName.get(t.name);
            if (!keep) { byName.set(t.name, t); continue; }
            if (keep === t) continue;
            m[k] = keep;
            if (!dropped.has(t)) { dropped.add(t); const d = t.source && t.source.data; if (d && d.close) d.close(); t.dispose(); }
          }
        }
      });
    }
    Weapons.texStats = { kept: byName.size, dropped: dropped.size };
  }

  equipped(i = this.slot) {
    const id = this.g.save.equipped[i];
    return this.g.save.inventory.find(w => w.uid === id) || null;
  }

  ammoOf(w) {
    if (!w) return null;
    if (!this.ammo[w.uid]) { const s = weaponStats(w); this.ammo[w.uid] = { mag: s.mag, reserve: s.reserve }; }
    return this.ammo[w.uid];
  }

  refill() {
    for (let i = 0; i < 3; i++) { const w = this.equipped(i); if (w) { const s = weaponStats(w); this.ammo[w.uid] = { mag: s.mag, reserve: s.reserve }; } }
  }

  firingRecently() { return this.lastFire < .9; }

  // ADS magnification: the mounted optic decides (factory sights use the archetype's zoom)
  zoom() { const w = this.equipped(); return w ? sightZoom(w) : 1; }

  refreshModel() {
    const p = this.g.player; if (!p || !p.avatar) return;
    const w0 = p.armed ? this.equipped() : null;
    if (this.g.viewmodel) this.g.viewmodel.setWeapon(w0);
    if (!p.armed || p.mode === 'car' || p.mode === 'sit') { p.avatar.attachGun(null); return; }   // stowed while riding/seated
    const w = this.equipped(); if (!w) { p.avatar.attachGun(null); return; }
    const A = ARCHETYPES[w.arch];
    p.avatar.attachGun(A.model, mesh => Weapons.styleMesh(mesh, w));
    this.g.setAvatarLayer && this.g.setAvatarLayer();
  }

  // Called for every mesh of a gun clone (viewmodel, avatar, ship rack, inspect stage). Rarity colours the energy
  // line's glow, the shader colours gun_body; kinetic and horror materials keep their own look. The first call also
  // mounts the weapon's chosen sight on the gun.
  static styleMesh(mesh, w) {
    const m = mesh.material, rc = RARITY[w.rarity].color;
    if (m.name === 'gun_glow') { m.color.set(rc); m.emissive.set(rc); m.emissiveIntensity = 1.8; }
    if (m.name === 'gun_body') { const sh = SHADERS.find(s => s.id === w.shader) || SHADERS[0]; m.color.set(sh.body); }
    // optics are glass: see straight through red dots and scope lenses
    if (m.name === 'gun_lens') { m.transparent = true; m.opacity = .14; m.depthWrite = false; m.emissiveIntensity = .2; m.color.set(0x9fd8ff); }
    if (WEAR[m.name] && mesh.geometry.attributes._wear) addWear(m, WEAR[m.name]);
    if (/^bio_/.test(m.name)) {
      if (m.name === 'bio_flesh' && mesh.geometry.attributes._wear) addFlesh(m);
      animateBio(mesh);
    }
    if (!mesh.userData.att) { let root = mesh; while (root.parent) root = root.parent; Weapons.dress(root, w); }
  }

  // Mount the chosen optic (gun_attach.glb ATT_<id>) on the gun's 'rail' empty, hide the factory sight it replaces,
  // move the 'sight' eye point onto the optic and add or remove the 'scope' marker for magnified glass.
  static dress(root, w) {
    if (root.userData.dressed) return;
    root.userData.dressed = true;
    const id = weaponSight(w);
    const rail = root.getObjectByName('rail');
    if (id === 'default' || !rail || !Weapons.assets) return;
    let att;
    try { att = Weapons.assets.clone('gun_attach', 'ATT_' + id); } catch (e) { return; }
    att.position.copy(rail.position);
    rail.parent.add(att);
    const optic = root.getObjectByName('OPTIC'); if (optic) optic.visible = false;
    const eye = att.getObjectByName('ATT_' + id + '_sight'), sight = root.getObjectByName('sight');
    if (eye && sight) sight.position.copy(rail.position).add(eye.position);
    const scope = root.getObjectByName('scope'); if (scope) scope.name = 'scope_off';
    if (SIGHTS[id].scope) { const s = new THREE.Object3D(); s.name = 'scope'; rail.parent.add(s); }
    att.traverse(o => {
      if (o.name.startsWith('ATT_')) o.name = 'att_' + o.name.slice(4);
      if (o.isMesh) { o.userData.att = true; o.material = o.material.clone(); o.castShadow = true; o.frustumCulled = false; Weapons.styleMesh(o, w); }
    });
  }

  select(i) {
    if (i === this.slot || !this.equipped(i)) return;
    this.slot = i; this.swap = .35; this.reloading = 0; this.burstLeft = 0;
    this.refreshModel(); this.g.audio.reload(1);
    this.g.hud.dirty = true;
  }

  update(dt, input) {
    const p = this.g.player;
    this.cool -= dt; this.swap -= dt; this.lastFire += dt; this.burstCool -= dt;
    BIO.gape = Math.max(0, BIO.gape - dt * 2.5);
    if (this.rampageT > 0) { this.rampageT -= dt; if (this.rampageT <= 0) this.rampage = 0; }
    this.updateRockets(dt);
    this.updateRounds(dt);
    this.updateGoo(dt);
    this.updateAfflictions(dt);
    this.g.fx && this.g.fx.updateSlime && this.g.fx.updateSlime(dt);
    // autoload perk: stowed weapons top up
    for (let i = 0; i < 3; i++) {
      if (i === this.slot) continue; const w = this.equipped(i);
      if (w && w.perks.includes('autoload')) { const a = this.ammoOf(w), s = weaponStats(w); if (a.mag < s.mag && a.reserve > 0) { const n = Math.min(s.mag - a.mag, a.reserve); a.mag += n; a.reserve -= n; } }
    }
    if (!p.armed || p.mode !== 'foot' || p.dead) return;
    if (input.enabled) {
      for (let i = 0; i < 3; i++) if (input.pressed('Digit' + (i + 1))) this.select(i);
      if (input.wheel) { let n = this.slot; for (let k = 0; k < 3; k++) { n = (n + (input.wheel > 0 ? 1 : 2)) % 3; if (this.equipped(n)) break; } this.select(n); }
    }
    const w = this.equipped(); if (!w) return;
    const A = ARCHETYPES[w.arch], S = weaponStats(w), a = this.ammoOf(w);
    if (A.cls === 'horror') this.drip(dt, A);
    if (this.reloading > 0) {
      this.reloading -= dt;
      const gun = p.avatar.gun; if (gun) gun.rotation.x = Math.sin(Math.min(1, 1 - this.reloading / S.reload) * Math.PI) * .9;
      if (this.reloading <= 0) {
        const n = Math.min(S.mag - a.mag, a.reserve); a.mag += n; a.reserve -= n;
        this.g.audio.reload(1); this.g.hud.dirty = true;
        if (gun) gun.rotation.x = 0;
      }
      return;
    }
    if (input.enabled && input.pressed('KeyR') && a.mag < S.mag && a.reserve > 0) { this.startReload(S); return; }
    if (this.swap > 0) return;
    // continue a pulse burst
    if (this.burstLeft > 0 && this.burstCool <= 0 && a.mag > 0) { this.fire(w, A, S, a); this.burstLeft--; this.burstCool = 60 / A.burstRpm; return; }
    const trigger = input.enabled && input.locked && (A.auto ? input.lmb : input.lmbHit);
    if (!trigger || this.cool > 0 || this.burstLeft > 0) return;
    if (a.mag <= 0) {
      if (a.reserve > 0) this.startReload(S); else if (input.lmbHit) this.g.audio.empty();
      return;
    }
    const frenzy = w.perks.includes('frenzy') && p.shield <= 0 ? 1.2 : 1;
    this.cool = 60 / (S.rpm * frenzy);
    if (A.burst) { this.fire(w, A, S, a); this.burstLeft = A.burst - 1; this.burstCool = 60 / A.burstRpm; this.cool += (A.burst - 1) * 60 / A.burstRpm; }
    else this.fire(w, A, S, a);
  }

  startReload(S) {
    this.reloading = this.reloadTotal = S.reload; this.burstLeft = 0; this.g.audio.reload(0);
  }

  // muzzle position of whatever the player sees (viewmodel in first person)
  muzzle(out) {
    const g = this.g;
    if (g.firstPerson && g.firstPerson()) return g.viewmodel.muzzleWorld(out);
    return g.player.avatar.muzzleWorld(out);
  }

  // aim direction with the weapon's spread cone applied
  spreadDir(out, S, mult = 1) {
    const p = this.g.player;
    const moving = Math.hypot(p.vel.x, p.vel.z) > .5;
    const sp = THREE.MathUtils.degToRad(S.spread * mult * (p.aiming ? .45 : 1) * (moving ? 1.35 : 1) * (p.grounded ? 1 : 1.6));
    p.camForward(out);
    const rx = (Math.random() - .5) * 2 * sp, ry = (Math.random() - .5) * 2 * sp;
    _t.set(Math.cos(p.camYaw), 0, -Math.sin(p.camYaw));
    out.addScaledVector(_t, rx); out.y += ry;
    return out.normalize();
  }

  fire(w, A, S, a) {
    const g = this.g, p = g.player, cam = g.camera;
    a.mag--; this.lastFire = 0; g.hud.dirty = true;
    g.save.stats.shots++;
    p.recoil = Math.min(1.5, p.recoil + (A.recoil || (A.dmg > 100 ? 1 : .35)) / S.spread * .3 + .15);
    p.camPitch += (A.pitch || .0035) * (p.aiming ? .6 : 1);
    this.muzzle(_m);
    if (g.firstPerson()) g.viewmodel.kick(A.kick ?? 1);
    p.camForward(_d);
    if (A.cls === 'horror') { BIO.gape = 1; g.fx.slimeDrops(_m, _d, 6, 2.5, GOO[A.goo].color, .8); g.fx.glow(_m, .35, GOO[A.goo].color, .08); }
    else g.fx.muzzle(_m, _d, w.arch === 'rocket' ? 0xffa040 : A.cls === 'energy' ? (A.tracer ? new THREE.Color(A.tracer).getHex() : 0x8fd8ff) : 0xffc070);
    g.audio.shot(A.sound);
    g.world.onGunshot && g.world.onGunshot(_m.clone());
    if (A.projectile) { this.launchRocket(_m.clone(), this.aimPoint(), S, w); return; }
    const shot = { hit: false, crit: false, killed: false };
    const pellets = A.pellets || 1;
    for (let k = 0; k < pellets; k++) {
      this.spreadDir(_d, S);
      _o.copy(cam.position).addScaledVector(_d, p.camCur * .9);
      if (A.goo) this.spawnGoo(A.goo, _o, _m, _d, S, w, A);
      else this.spawnRound(_o, _m, _d, S, w, A, shot);
    }
  }

  // ------------------------------------------------------------------ bullets and bolts (travel time, gravity)
  spawnRound(origin, muzzle, dir, S, w, A, shot) {
    if (this.rounds.length >= MAX_ROUNDS) this.rounds.shift();
    const speed = (A.vel || 600) * (.97 + Math.random() * .06);
    const kinetic = A.cls === 'kinetic';
    const col = new THREE.Color(A.tracer || (kinetic ? '#ffcf8a' : RARITY[w.rarity].id === 'exotic' ? '#ffd070' : '#ffd9a0'));
    if (!kinetic) col.lerp(new THREE.Color(RARITY[w.rarity].color), .25);
    this.rounds.push({
      p: origin.clone(), v: dir.clone().multiplyScalar(speed), off: muzzle.clone().sub(origin), dist: 0,
      life: Math.max(1.2, S.range * 8 / speed + .5), max: Math.max(320, S.range * 8),
      grav: A.grav ?? 1, w, S, A, shot, col, width: w.arch === 'sniper' || w.arch === 'bolt' ? .022 : kinetic ? .009 : .016,
      len: kinetic ? 3.5 : 5,
    });
  }

  updateRounds(dt) {
    const g = this.g;
    if (this.streaks.parent !== g.scene && g.scene) g.scene.add(this.streaks);
    let n = 0;
    for (let i = this.rounds.length - 1; i >= 0; i--) {
      const r = this.rounds[i];
      r.life -= dt;
      r.v.y -= G * r.grav * dt;
      const speed = r.v.length(), step = speed * dt;
      if (!(speed > 0) || !Number.isFinite(speed + r.p.x + r.p.y + r.p.z)) { this.rounds.splice(i, 1); continue; }
      _d.copy(r.v).divideScalar(speed);
      const res = g.combat.trace(r.p, _d, step, 'player');
      if (res.target || res.hit) { g.water && g.water.hitTest(r.p, res.point); this.roundHit(r, res, _d); this.rounds.splice(i, 1); continue; }
      _a.copy(r.p); r.p.addScaledVector(_d, step); r.dist += step;
      g.water && g.water.hitTest(_a, r.p);
      if (r.life <= 0 || r.dist > r.max) { this.rounds.splice(i, 1); continue; }
      // the streak starts at the muzzle and converges onto the true (camera) path over the first metres
      const k = Math.max(0, 1 - r.dist / 14);
      _a.copy(r.p).addScaledVector(r.off, k);
      const len = Math.min(r.len, r.dist * .8, step * 1.2 + .5);
      _b.copy(_a).addScaledVector(_d, -len);
      if (n < MAX_ROUNDS) {
        _q.setFromUnitVectors(Z, _d);
        _M.compose(_b, _q, _s.set(r.width, r.width, len));
        this.streaks.setMatrixAt(n, _M); this.streaks.setColorAt(n, _col.setRGB(r.col.r * 4, r.col.g * 4, r.col.b * 4)); n++;
      }
    }
    this.streaks.count = n;
    if (n) { this.streaks.instanceMatrix.needsUpdate = true; this.streaks.instanceColor.needsUpdate = true; }
  }

  roundHit(r, res, dir) {
    const g = this.g, w = r.w, S = r.S, end = res.point;
    if (res.target) {
      const dist = r.dist + res.dist;
      const fall = dist < S.range ? 1 : Math.max(.5, 1 - (dist - S.range) / (S.range * 2));
      let dmg = S.dmg * fall * (1 + this.rampage * .15);
      if (res.crit) dmg *= S.crit;
      const out = res.target.takeDamage(dmg, res.crit, end, dir, 'player');
      g.fx.impact(end, dir.clone().negate(), res.crit ? 'crit' : 'enemy');
      g.hud.hitNumber(end, out, dmg, res.crit);
      if (res.crit && w.perks.includes('explosive') && !out.immune) { g.combat.splash(end, 2.5, dmg * .3, 'player', res.target); g.fx.emit(end, 14, 6, 0xff8a40, .3, 4, .08); }
      if (out.killed) this.onKill(w, res.crit, res.target);
      const sh = r.shot;
      if (!sh.hit) g.save.stats.hits++;
      sh.hit = true;
      g.hud.hitMarker(res.crit, out.killed, out.immune); if (!out.immune) g.audio.hit(res.crit, out.killed);
    } else {
      g.fx.impact(end, res.normal, res.terrain ? 'dirt' : 'metal');
      // shooting up a car in traffic
      if (res.box && res.box.car && res.box.car.alive) {
        const car = res.box.car; car.damage(S.dmg * .6);
        if (!car.alive && g.world.wanted) g.world.wanted.crime(1, end);
        if (car.traffic) car.traffic.stopT = 4;
      }
    }
  }

  // ------------------------------------------------------------------ horror: goo projectiles
  spawnGoo(kind, origin, muzzle, dir, S, w, A) {
    if (this.goo.length >= MAX_GOO) this.goo.shift();
    const K = GOO[kind];
    const speed = (A.vel || 30) * (kind === 'bile' ? .75 + Math.random() * .5 : 1);
    // goo is slow: it visibly leaves the maw (start near the muzzle, aim at the crosshair point)
    const v = dir.clone().multiplyScalar(speed);
    if (kind !== 'bile') v.y += 1.2;          // a slight lob so the arc reads
    this.goo.push({ kind, p: muzzle.clone().addScaledVector(dir, .05), v, life: K.life, w, S, A, t: 0, size: K.size * (kind === 'bile' ? .7 + Math.random() * .6 : 1), color: K.color });
  }

  updateGoo(dt) {
    const g = this.g;
    if (this.globs.parent !== g.scene && g.scene) g.scene.add(this.globs);
    let n = 0;
    for (let i = this.goo.length - 1; i >= 0; i--) {
      const q = this.goo[i], K = GOO[q.kind];
      q.life -= dt; q.t += dt;
      if (q.kind === 'larva') this.steerLarva(q, dt);
      else q.v.y -= G * K.grav * dt;
      const speed = q.v.length(), step = speed * dt;
      if (!Number.isFinite(speed) || !Number.isFinite(q.p.x + q.p.y + q.p.z)) { this.goo.splice(i, 1); continue; }   // never feed NaN to the renderer
      _d.copy(q.v).divideScalar(Math.max(1e-4, speed));
      const res = g.combat.trace(q.p, _d, step + q.size, 'player');
      if (res.target || res.hit || q.life <= 0) {
        const at = res.target || res.hit ? res.point : q.p;
        this.gooHit(q, res, at, _d);
        this.goo.splice(i, 1); continue;
      }
      _a.copy(q.p); q.p.addScaledVector(_d, step);
      g.water && g.water.hitTest(_a, q.p);
      if (q.kind !== 'bile' && Math.random() < dt * 14) g.fx.slimeDrops(q.p, null, 1, .6, q.color, .6);
      if (q.kind === 'larva' && Math.random() < dt * 20) g.fx.emit(q.p, 1, .3, 0x8aff4a, .3, 0, .04, 1);
      if (n < MAX_GOO) {
        // wobbling, velocity-stretched blob
        const wob = 1 + Math.sin(q.t * 30 + i) * .12;
        _q.setFromUnitVectors(Z, _d);
        _M.compose(q.p, _q, _s.set(q.size * wob, q.size / wob, q.size * (1.25 + Math.min(1, speed / 40) * .5)));
        this.globs.setMatrixAt(n, _M); this.globs.setColorAt(n, _col.set(q.color)); n++;   // a Color: Vector3.set(hex) gave (hex, NaN, NaN) -> black globs / NaN frames
      }
    }
    this.globs.count = n;
    if (n) { this.globs.instanceMatrix.needsUpdate = true; this.globs.instanceColor.needsUpdate = true; }
  }

  steerLarva(q, dt) {
    const g = this.g;
    if (!q.target || !q.target.alive || Math.random() < dt * .5) {
      let best = 26, bt = null;
      for (const t of g.combat.targets) { if (!t.alive || t.side === 'player') continue; const d = t.center(_a).distanceTo(q.p); if (d < best) { best = d; bt = t; } }
      q.target = bt;
    }
    const sp = 9;
    if (q.target) {
      q.target.center(_a).sub(q.p); const d = _a.length(); _a.normalize();
      q.v.lerp(_a.multiplyScalar(sp), Math.min(1, dt * 3.5));
      q.v.x += Math.sin(q.t * 17) * dt * 12; q.v.y += Math.cos(q.t * 13) * dt * 8;
      if (d < (q.target.radius || .5) + .45) { this.larvaBite(q); q.life = -1; }
    } else {
      // nothing to hunt: drift down and crawl around
      q.v.y -= G * .6 * dt; q.v.x += (Math.random() - .5) * dt * 20; q.v.z += (Math.random() - .5) * dt * 20;
    }
  }

  larvaBite(q) {
    const g = this.g, t = q.target; if (!t || !t.alive) return;
    const dmg = q.S.dmg * .16 * (1 + this.rampage * .15);
    const c = t.center(_b).clone();
    const out = t.takeDamage(dmg, false, c, q.v.clone().normalize(), 'player');
    g.hud.hitNumber(c, out, dmg, false); g.hud.hitMarker(false, out.killed, out.immune);
    if (!out.immune) this.afflict(t, dmg * (q.A.dot || .4), q.w);
    g.fx.slime(c, null, .6, 0x9aff4a);
    if (out.killed) this.onKill(q.w, false, t);
  }

  gooHit(q, res, at, dir) {
    const g = this.g, S = q.S, A = q.A, w = q.w;
    const normal = res.normal || (res.target ? dir.clone().negate() : new THREE.Vector3(0, 1, 0));
    const mult = 1 + this.rampage * .15;
    if (q.kind === 'larva') {
      if (q.life > -1) g.fx.slime(at, res.normal || null, .5, 0x8aff4a);
      return;
    }
    if (q.kind === 'brood') {
      // the pod bursts: caustic splash and a brood of parasites that hunt nearby enemies
      const kills = g.combat.splash(at, A.splash, S.dmg * .5 * mult, 'player');
      kills.forEach(t => this.onKill(w, false, t));
      g.fx.slime(at, normal, 2.2, 0x9aff4a); g.fx.slimeDrops(at, normal, 20, 5, 0x9a2a3a, 1.4);
      g.fx.flash(at, 0x8aff4a, 120, .25, 9); g.water && g.water.splash(at, 3);
      g.audio.splat(at, true);
      if (kills.length) { g.hud.hitMarker(false, true); g.audio.hit(false, true); }
      const up = _a.copy(normal).multiplyScalar(.3);
      for (let k = 0; k < (A.swarm || 5); k++) {
        if (this.goo.length >= MAX_GOO) break;
        const v = new THREE.Vector3((Math.random() - .5) * 6, 3 + Math.random() * 3, (Math.random() - .5) * 6);
        this.goo.push({ kind: 'larva', p: at.clone().add(up), v, life: GOO.larva.life + Math.random(), w, S, A, t: Math.random() * 5, size: GOO.larva.size * (.8 + Math.random() * .4), color: GOO.larva.color });
      }
      return;
    }
    // spit glob / bile droplet
    const big = q.kind === 'spit';
    if (res.target) {
      let dmg = S.dmg * mult; if (res.crit) dmg *= S.crit;
      const out = res.target.takeDamage(dmg, res.crit, at, dir, 'player');
      g.hud.hitNumber(at, out, dmg, res.crit); g.hud.hitMarker(res.crit, out.killed, out.immune); if (!out.immune) g.audio.hit(res.crit, out.killed);
      if (!out.immune) this.afflict(res.target, dmg * (A.dot || .5), w);
      if (out.killed) this.onKill(w, res.crit, res.target);
      if (big) { const kills = g.combat.splash(at, A.splash || 1, dmg * .35, 'player', res.target); kills.forEach(t => this.onKill(w, false, t)); }
      g.fx.slime(at, normal, big ? 1 : .45, q.color);
    } else {
      if (big) { const kills = g.combat.splash(at, A.splash || 1, S.dmg * .35 * mult, 'player'); kills.forEach(t => this.onKill(w, false, t)); }
      if (big || Math.random() < .45) g.fx.slime(at, normal, big ? 1 : .55, q.color);
      else g.fx.slimeDrops(at, normal, 3, 1.5, q.color, .6);
    }
    if (big || Math.random() < .25) g.audio.splat(at, false);
  }

  // acid / bile keeps eating: damage over 3 s, refreshed and stacked by further hits
  afflict(t, total, w) {
    if (!t || !t.alive || total <= 0) return;
    const a = this.afflicted.get(t);
    const dps = total / 3;
    if (a) { a.dps = Math.min(a.dps + dps * .6, dps * 3); a.t = 3; a.w = w; }
    else this.afflicted.set(t, { dps, t: 3, tick: .35, w });
  }

  updateAfflictions(dt) {
    const g = this.g;
    for (const [t, a] of this.afflicted) {
      if (!t.alive || a.t <= 0) { this.afflicted.delete(t); continue; }
      a.t -= dt; a.tick -= dt;
      if (a.tick > 0) continue;
      a.tick += .35;
      const c = t.center(_b).clone(), dmg = a.dps * .35;
      g.fx.fizz(c.clone().add(_a.set((Math.random() - .5) * .4, (Math.random() - .3) * .6, (Math.random() - .5) * .4)));
      const out = t.takeDamage(dmg, false, null, null, 'player');
      g.hud.hitNumber(c, out, dmg, false);
      if (out.killed) { this.onKill(a.w, false, t); g.hud.hitMarker(false, true); this.afflicted.delete(t); }
    }
  }

  // living guns drool from the maw
  drip(dt, A) {
    this.dripT -= dt;
    if (this.dripT > 0 || !this.g.fx) return;
    this.dripT = .18 + Math.random() * .35 - BIO.gape * .15;
    this.muzzle(_m);
    this.g.fx.slimeDrops(_m, null, 1, .2, GOO[A.goo].color, .5);
  }

  aimPoint() {
    const g = this.g, p = g.player;
    p.camForward(_d);
    _o.copy(g.camera.position).addScaledVector(_d, p.camCur * .9);
    return g.combat.trace(_o, _d, 300, 'player').point;
  }

  onKill(w, crit, target) {
    const g = this.g;
    if (w.perks.includes('rampage')) { this.rampage = Math.min(3, this.rampage + 1); this.rampageT = 4; }
    if (w.perks.includes('vampire')) g.player.health = Math.min(g.player.maxHealth, g.player.health + 25);
  }

  launchRocket(from, to, S, w) {
    const g = this.g;
    const dir = to.clone().sub(from).normalize();
    const m = new THREE.Mesh(new THREE.SphereGeometry(.12, 8, 6), new THREE.MeshBasicMaterial({ color: new THREE.Color(0xffa040).multiplyScalar(4), toneMapped: false }));
    m.position.copy(from); g.scene.add(m);
    this.rockets.push({ m, dir, speed: 48, life: 5, dmg: S.dmg * (1 + this.rampage * .15), w, splash: ARCHETYPES[w.arch].splash, owner: 'player' });
  }

  updateRockets(dt) {
    const g = this.g;
    for (let i = this.rockets.length - 1; i >= 0; i--) {
      const r = this.rockets[i];
      r.life -= dt;
      const step = r.speed * dt;
      const res = g.combat.trace(r.m.position, r.dir, step, r.owner);
      g.fx.emit(r.m.position, 3, 1.5, 0xff9040, .35, -1, .14, 1);
      if (res.hit || res.target || r.life <= 0) {
        const p = res.hit || res.target ? res.point : r.m.position;
        const kills = g.combat.splash(p, r.splash, r.dmg, r.owner);
        g.fx.explosion(p, r.splash); g.audio.explosion(p); g.water && g.water.splash(p, 3);
        const dd = p.distanceTo(g.player.pos); if (dd < 30) g.player.shake = Math.min(1, g.player.shake + (1 - dd / 30));
        if (kills) { g.hud.hitMarker(false, true); g.audio.hit(false, true); kills.forEach(() => this.onKill(r.w, false)); }
        r.m.removeFromParent(); r.m.geometry.dispose(); this.rockets.splice(i, 1);
        continue;
      }
      _a.copy(r.m.position); r.m.position.addScaledVector(r.dir, step);
      // water: a rocket that crosses the surface detonates there (fx.explosion near water raises the column)
      const wet = g.water && g.water.hitTest(_a, r.m.position, null);
      if (wet) { r.m.position.copy(wet.point); r.life = 0; }
    }
  }

  // world change: drop everything in flight
  clearRockets() {
    this.rockets.forEach(r => r.m.removeFromParent()); this.rockets = [];
    this.rounds = []; this.goo = []; this.afflicted.clear();
    this.streaks.count = 0; this.globs.count = 0;
    this.streaks.removeFromParent(); this.globs.removeFromParent();
  }
}
