// Base class for the three kinds of place: the ship hub, Earth's city and the generated planets.
import * as THREE from 'three';
import { CollisionWorld } from '../core/physics.js';

export class World {
  constructor(game) {
    this.g = game;
    this.scene = new THREE.Scene();
    this.collision = new CollisionWorld();
    this.interactables = [];      // {pos, r, label, verb, key, action, enabled?}
    this.combat = false; this.allowCars = false; this.surface = 'metal';
    this.name = ''; this.region = '';
    this.disposables = [];
  }

  async build(progress) { }
  spawn() { return { pos: new THREE.Vector3(), yaw: 0 }; }
  update(dt) { }
  objectives() { return []; }
  markers() { return []; }

  // a place to sit: pos is the floor point under the seat (where the Sit clip puts the body), yaw the facing
  addSeat(pos, yaw, label = 'Seat') {
    const p = pos.clone(), fwd = new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw));
    (this.seatSpots = this.seatSpots || []).push({ pos: p, yaw, label });     // pedestrians sit here too (population.js)
    this.interactables.push({ id: 'seat', pos: p.clone().addScaledVector(fwd, .35), r: 1.25, label, verb: 'Sit', key: 'E',
      enabled: () => this.g.player.mode === 'foot', action: () => this.g.player.sit({ pos: p, yaw }) });
  }

  // nearest interactable the player is facing
  focus(p) {
    let best = null, bd = 1e9;
    for (const it of this.interactables) {
      if (it.enabled && !it.enabled()) continue;
      const pos = typeof it.pos === 'function' ? it.pos() : it.pos;
      const d = Math.hypot(pos.x - p.pos.x, pos.z - p.pos.z);
      if (d > (it.r || 1.8) || Math.abs(pos.y - p.pos.y) > 2.5) continue;
      if (d < bd) { bd = d; best = it; }
    }
    return best;
  }

  dispose() {
    this.scene.traverse(o => {
      if (o.geometry && !o.geometry.userData.shared) o.geometry.dispose();
      if (o.isSkinnedMesh && o.skeleton) o.skeleton.dispose();      // bone texture (re-made on the next render if reused)
    });
    this.disposables.forEach(d => d.dispose && d.dispose());
  }
}
