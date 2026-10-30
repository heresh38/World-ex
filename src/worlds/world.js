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
    });
    this.disposables.forEach(d => d.dispose && d.dispose());
  }
}
