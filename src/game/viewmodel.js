// First-person viewmodel: Blender arms + the equipped gun, drawn in a second pass over the world
// (depth cleared) so it never clips into walls. Handles sway, bob, recoil, reload, swap and aim-down-sights.
import * as THREE from 'three';
import { ARCHETYPES } from './data.js';
import { Weapons } from './weapons.js';
import { GunRig } from './reload.js';

const HIP = new THREE.Vector3(.17, -.2, -.44);
const _v = new THREE.Vector3(), _q = new THREE.Quaternion(), _e = new THREE.Euler();
const REST6 = [0, 0, 0, 0, 0, 0];

export class Viewmodel {
  constructor(game) {
    this.g = game;
    this.scene = new THREE.Scene();
    this.hemi = new THREE.HemisphereLight(0xdfe8ff, 0x3a3328, 1.4);
    this.key = new THREE.DirectionalLight(0xffffff, 2.2);
    this.key.position.set(-1, 2, 1);
    this.rig = new THREE.Group();                 // follows the camera
    this.rig.add(this.key, this.key.target);
    this.scene.add(this.hemi, this.rig);
    this.holder = new THREE.Group(); this.rig.add(this.holder);
    this.gunSpace = new THREE.Group(); this.gunSpace.rotation.y = Math.PI; this.holder.add(this.gunSpace);
    const arms = game.assets.clone('viewmodel_arms');
    arms.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); o.frustumCulled = false; o.castShadow = false; } });
    this.armR = arms.getObjectByName('arm_R'); this.armL = arms.getObjectByName('arm_L');
    this.gunSpace.add(this.armR, this.armL);
    this.mats = {}; [this.armR, this.armL].forEach(a => a.traverse(o => { if (o.isMesh) this.mats[o.material.name] = o.material; }));
    this.gun = null; this.uid = null; this.sight = new THREE.Vector3(0, .1, 0);
    this.ads = 0; this.kickZ = 0; this.kickR = 0; this.swayX = 0; this.swayY = 0; this.bobT = 0; this.lower = 1;
    this.active = false;
  }

  // first-person sleeves follow what you wear: gloves/top tint, glow colour
  recolor(c) {
    const male = c.body === 'male', w = c.wear || {}, t = c.tints || {};
    const P = male ? ['#2a2d33', '#1c1e22', '#ffae2f'] : ['#3a3d44', '#2b2e33', '#1ad8ff'];
    const tint = (base, h) => { const col = new THREE.Color(base); if (h) col.multiply(new THREE.Color(h)); return col; };
    const m = this.mats;
    if (m.armor_primary) m.armor_primary.color.copy(tint(P[0], w.hands !== 'none' ? t.hands : t.top));
    if (m.armor_secondary) m.armor_secondary.color.copy(tint(P[1], t.top));
    if (m.undersuit) m.undersuit.color.copy(tint(P[1], t.top));
    const g = c.glow || P[2];
    if (m.glow) { m.glow.color.set(g); m.glow.emissive.set(g); }
  }

  setWeapon(w) {
    const uid = w ? w.uid + ':' + w.shader + ':' + (w.sight || '') : null;   // a new optic remounts the gun
    if (uid === this.uid) return;
    this.uid = uid;
    if (this.gun) { this.gun.removeFromParent(); this.gun = null; }
    this.gr = null;
    this.armL.visible = this.armR.visible = !!w;
    if (!w) return;
    const g = this.g.assets.clone(ARCHETYPES[w.arch].model);
    g.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); o.frustumCulled = false; o.castShadow = false; Weapons.styleMesh(o, w); } });
    this.gunSpace.add(g); this.gun = g;
    this.muzzle = g.getObjectByName('muzzle');
    const fg = g.getObjectByName('foregrip'), sg = g.getObjectByName('sight');
    this.foreRest = fg ? fg.position.clone() : new THREE.Vector3(0, -.02, .3);
    this.armL.position.copy(this.foreRest); this.armL.quaternion.identity();
    this.gr = new GunRig(g, w.arch, this.g.assets);      // reload parts (mag, bolt, slide, hatch...) posed by weapons.rl
    if (sg) this.sight.copy(sg.position);
    this.scoped = !!g.getObjectByName('scope');
    this.lower = 1;      // raise animation
  }

  kick(strength) { this.kickZ = Math.min(.12, this.kickZ + .03 * strength); this.kickR = Math.min(.25, this.kickR + .05 * strength); }

  muzzleWorld(out) {
    if (this.muzzle) { this.rig.updateMatrixWorld(true); return this.muzzle.getWorldPosition(out); }
    return out.copy(this.g.camera.position);
  }

  update(dt, input) {
    const g = this.g, p = g.player, cam = g.camera;
    this.active = g.firstPerson() && p.armed && !!this.gun;
    this.rig.visible = this.active;
    // magnified optics: once fully aimed the scope picture replaces the gun (like looking through the glass)
    const inScope = this.active && this.scoped && this.ads > .82 && p.aiming;
    g.hud.scope(inScope);
    if (inScope) this.rig.visible = false;
    if (!this.active) return;
    this.rig.position.copy(cam.position); this.rig.quaternion.copy(cam.quaternion);
    this.scene.environment = g.scene.environment;
    // aim-down-sights blend
    const wpn = g.weapons, P = wpn.rl.pose();
    const adsT = p.aiming && !(wpn.reloading > 0) ? 1 : 0;
    this.ads += (adsT - this.ads) * Math.min(1, dt * 14);
    // sway from look input, bob from movement
    const hs = Math.hypot(p.vel.x, p.vel.z);
    this.swayX += ((-input.mx * .0006) - this.swayX) * Math.min(1, dt * 10);
    this.swayY += ((input.my * .0006) - this.swayY) * Math.min(1, dt * 10);
    if (p.grounded) this.bobT += dt * hs * 1.15;
    const bobA = Math.min(1, hs / 7) * (1 - this.ads * .85) * (p.running ? 1.6 : 1);
    const bx = Math.sin(this.bobT) * .012 * bobA, by = -Math.abs(Math.cos(this.bobT)) * .014 * bobA;
    this.kickZ *= Math.pow(.0005, dt); this.kickR *= Math.pow(.0008, dt);
    // reload / cycling pose (reload.js): holder offsets, the off hand and the gun's moving parts
    const G = P ? P.gun : REST6;
    if (this.gr) this.gr.apply(P);
    if (P && P.handW > 0) { this.armL.position.copy(P.hand); this.armL.quaternion.setFromEuler(_e.set(P.handRot[0], P.handRot[1], P.handRot[2])); this.armPosed = true; }
    else if (this.armPosed) { this.armL.position.copy(this.foreRest); this.armL.quaternion.identity(); this.armPosed = false; }
    // weapon swap lower/raise
    this.lower = Math.max(0, this.lower - dt * 4);
    if (wpn.swap > 0) this.lower = Math.max(this.lower, wpn.swap / .35);
    const run = p.running && !p.aiming ? 1 : 0;
    this.runT = (this.runT || 0) + (run - (this.runT || 0)) * Math.min(1, dt * 8);
    // position: hip vs ADS (sight on the camera axis)
    const adsPos = _v.set(this.sight.x, -this.sight.y, -.3 + this.sight.z);
    const pos = HIP.clone().lerp(adsPos, this.ads);
    pos.x += bx + this.swayX * (1 - this.ads * .7) + this.runT * .05;
    pos.y += by + this.swayY * (1 - this.ads * .7) - this.lower * .35 - this.runT * .04;
    pos.z += this.kickZ * (1 - this.ads * .5);
    pos.x += G[0]; pos.y += G[1]; pos.z += G[2];
    this.holder.position.copy(pos);
    _e.set(this.kickR * (1 - this.ads * .6) + G[3] - this.lower * .6 - this.runT * .35, this.swayX * 2 + this.runT * .6 + G[4], G[5] + this.runT * .25);
    this.holder.quaternion.setFromEuler(_e);
  }
}
