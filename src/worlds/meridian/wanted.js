// Wanted level: crimes add heat, security drones respond (two per star, up to eight), heat fades when you
// lie low. Dying or leaving Earth clears it.
import * as THREE from 'three';

export class Wanted {
  constructor(game, map) {
    this.g = game; this.map = map; this.level = 0; this.calm = 0; this.police = []; this.spawnT = 0;
  }

  crime(n, pos) {
    const was = this.level;
    this.level = Math.min(5, this.level + n);
    this.calm = 0;
    if (this.level > was) { this.g.hud.dirty = true; this.g.audio.alert(pos); }
  }

  reset() {
    this.level = 0; this.calm = 0;
    for (const e of this.police) if (e.alive) e.alive = false;
    this.g.enemies.removeWhere(e => this.police.includes(e));
    this.police = [];
    this.g.hud.dirty = true;
  }

  update(dt) {
    const g = this.g, p = g.player;
    this.police = this.police.filter(e => g.enemies.list.includes(e) && e.alive);
    if (this.level <= 0) {
      if (this.police.length) { g.enemies.removeWhere(e => this.police.includes(e)); this.police = []; }
      return;
    }
    // heat fades after 20 s without a crime and with no drone in sight
    const seen = this.police.some(e => e.seen);
    this.calm += seen ? 0 : dt;
    if (this.calm > 20) { this.level--; this.calm = 12; g.hud.dirty = true; if (!this.level) g.hud.toast('Wanted level cleared'); }
    // response
    this.spawnT -= dt;
    const want = Math.min(8, this.level * 2);
    if (this.spawnT <= 0 && this.police.length < want) {
      this.spawnT = 4;
      const a = Math.random() * Math.PI * 2, r = 70;
      const x = p.pos.x + Math.cos(a) * r, z = p.pos.z + Math.sin(a) * r;
      const e = g.enemies.spawn('drone', new THREE.Vector3(x, this.map.height(x, z), z), 2 + this.level * 2, { police: true });
      e.state = 'combat';
      this.police.push(e);
    }
  }

  // a security drone shot down raises the heat
  onPoliceKilled() { this.crime(1, this.g.player.pos); }
}
