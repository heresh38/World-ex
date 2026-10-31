// Inventory inspect view: the selected weapon turning in a studio light rig, or an orbit shot of the player's own
// character for the armour tab. Drawn by the main renderer into the `.inv-stage` rectangle of the panel.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { ARCHETYPES } from '../game/data.js';
import { Weapons } from '../game/weapons.js';

export class Inspect {
  constructor(game) {
    this.g = game;
    this.scene = new THREE.Scene();
    this.cam = new THREE.PerspectiveCamera(28, 1, .05, 50);
    this.cam.position.set(0, .12, 2.2); this.cam.lookAt(0, 0, 0);
    const key = new THREE.DirectionalLight(0xfff1e0, 2.6); key.position.set(1.5, 2, 2.5);
    const rim = new THREE.DirectionalLight(0x8fc8ff, 2.2); rim.position.set(-2, 1, -2);
    this.scene.add(key, rim, new THREE.HemisphereLight(0xbfd4ff, 0x201810, .5));
    this.charCam = new THREE.PerspectiveCamera(30, 1, .1, 400);
    this.charCam.layers.enable(1);
    this.mode = null; this.uid = null; this.spin = 0; this.drag = null; this.vel = 0;
    addEventListener('pointerdown', e => { if (e.target.closest('.inv-stage')) { this.drag = e.clientX; this.vel = 0; } });
    addEventListener('pointermove', e => { if (this.drag !== null) { const d = (e.clientX - this.drag) * .01; this.spin += d; this.vel = d; this.drag = e.clientX; } });
    addEventListener('pointerup', () => { this.drag = null; });
  }

  envMap() {
    if (this.env) return;
    const pm = new THREE.PMREMGenerator(this.g.renderer.r);
    this.env = pm.fromScene(new RoomEnvironment(), .04).texture;
    pm.dispose();
    this.scene.environment = this.env; this.scene.environmentIntensity = .9;
  }

  setWeapon(w) {
    this.mode = w ? 'weapon' : null;
    if (!w || w.uid + w.shader === this.uid) return;
    this.uid = w.uid + w.shader;
    this.envMap();
    if (this.gun) { this.gun.removeFromParent(); this.gun = null; }
    const gun = this.g.assets.clone(ARCHETYPES[w.arch].model);
    gun.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); Weapons.styleMesh(o, w); o.frustumCulled = false; } });
    // centre and fit: the longest side spans ~1.25 units
    const box = new THREE.Box3().setFromObject(gun), size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
    const pivot = new THREE.Group(); gun.position.sub(c); pivot.add(gun);
    pivot.scale.setScalar(1.25 / Math.max(size.x, size.y, size.z, .01));
    this.scene.add(pivot); this.gun = pivot; this.spin = .6;
  }

  setCharacter() { this.mode = 'character'; this.spin = this.spin || 0; }
  clear() { this.mode = null; }

  render(dt) {
    if (!this.mode) return;
    const el = document.querySelector('.inv-stage'); if (!el) return;
    const rect = el.getBoundingClientRect(); if (rect.width < 24) return;
    if (this.drag === null) { this.vel *= .92; this.spin += this.vel + dt * .35; }
    const R = this.g.renderer;
    if (this.mode === 'weapon' && this.gun) {
      // gun points along +Z in model space: show it side-on, turning
      this.gun.rotation.set(Math.sin(this.g.time * .7) * .06, Math.PI / 2 + Math.sin(this.spin) * 1.1, 0);
      R.preview(this.scene, this.cam, rect);
    } else if (this.mode === 'character') {
      const p = this.g.player; if (!p || !this.g.scene) return;
      const a = p.yaw + this.spin, c = p.pos;
      this.charCam.position.set(c.x + Math.sin(a) * 4.3, c.y + 1.15, c.z + Math.cos(a) * 4.3);
      this.charCam.lookAt(c.x, c.y + .9, c.z);
      R.preview(this.g.scene, this.charCam, rect);
    }
  }
}
