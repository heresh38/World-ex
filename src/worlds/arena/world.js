// Shellbreak: the Wayfarer's combat simulation. Two squads of ghost-shells on Brennick Works (tools/blender/arena.py),
// a ruined arms foundry yard rendered at dusk. Builds the map (merged GLB + JSON colliders, nav graph, spawns, light
// anchors), owns the Match (match.js: rules, bots, spawns, rewards) and the mode UI (src/ui/arena.js: loadout, score,
// feed, scoreboard, end screen). Weapon power is at parity here and every shell is 100 health + 50 shield.
import * as THREE from 'three';
import { World } from '../world.js';
import { atmosphereSky } from '../sky.js';
import { NavGraph } from './nav.js';
import { Match, MODE_NAME } from './match.js';
import { ArenaUI } from '../../ui/arena.js';
import { TEAM_COL } from '../../game/bots.js';
import { Puffs } from '../../game/puffs.js';

export const ARENA_MAP = 'arena_brennick';
export const DEFAULT_CFG = { difficulty: 'normal', size: 6, limit: 50, minutes: 10 };

export class ArenaWorld extends World {
  constructor(game) {
    super(game);
    this.kind = 'sim'; this.combat = true; this.allowCars = false; this.surface = 'concrete';
    this.name = 'Brennick Works'; this.region = MODE_NAME + ' · combat simulation';
    this.parity = true; this.hideDamageNumbers = true; this.noInventory = true;
  }

  async build(progress) {
    const g = this.g, A = g.assets, sc = this.scene;
    progress(.05, 'Compiling the simulation');
    this.map = A.json[ARENA_MAP];
    // squad bodies: both player frames (the player's own is loaded already)
    const other = g.save.character.body === 'male' ? 'player_female' : 'player_male';
    this.otherBody = A.models[other] ? null : other;
    await A.ensure(other);
    progress(.35, 'Raising the foundry');
    const root = A.clone(ARENA_MAP);
    sc.add(root);
    const cfg = this.cfg = Object.assign({}, DEFAULT_CFG, (g.save.arena && g.save.arena.cfg) || {}, g.arenaCfg || {});
    this.match = new Match(this, cfg);
    const mine = this.match.playerTeam;
    root.traverse(o => {
      if (!o.isMesh) return;
      const far = /ARENA_far/.test(o.name) || (o.parent && /ARENA_far/.test(o.parent.name));
      const glass = /ARENA_glass/.test(o.name) || (o.parent && /ARENA_glass/.test(o.parent.name));
      o.receiveShadow = !far; o.castShadow = !far && !glass;
      for (const m of [].concat(o.material)) {
        if (/^ar_team_/.test(m.name)) {
          const c = new THREE.Color(m.name === 'ar_team_' + mine ? TEAM_COL.ally : TEAM_COL.enemy);
          m.color.copy(c); m.emissive.copy(c); m.emissiveIntensity = 2.2; m.toneMapped = false;
        }
        if (m.name === 'ar_window') { m.transparent = true; m.depthWrite = false; m.side = THREE.DoubleSide; m.envMapIntensity = 1.4; }
        if (m.name === 'ar_signs') { m.transparent = true; m.depthWrite = false; m.polygonOffset = true; m.polygonOffsetFactor = -2; }
        if (m.name === 'ar_lamp') m.emissiveIntensity = 2.2;
        if (far) m.envMapIntensity = .3;
      }
    });
    // ---- collisions + navigation
    const c = this.collision;
    c.floorY = 0;
    for (const b of this.map.colliders) c.add([b[0], b[1], b[2], b[3], b[4], b[5]], b[6]);
    const tn = performance.now();
    this.nav = new NavGraph(this.map.nav);
    this.navMs = performance.now() - tn;
    // ---- sky, light
    progress(.6, 'Lighting the yard');
    const S = this.map.sun, sunDir = new THREE.Vector3(...S.dir).normalize();
    this.sunDir = sunDir;
    // dusk grade: deep blue overhead, a warm band low in the west, a dusty mauve haze that swallows the far city;
    // cool fill from the sky, warm bounce from the ground, a low gold sun
    const FOG = '#977f76', SUNC = '#ffb26e';
    const skyOpts = { fog: FOG, ground: '#2a2420', groundK: .6 };
    const sky = atmosphereSky(this.map.sky[1], this.map.sky[0], SUNC, sunDir, { fog: FOG });
    sky.material.uniforms.cloudC.value.set('#e8b8a0');
    sc.add(sky); this.sky = sky;
    sc.fog = new THREE.FogExp2(new THREE.Color(FOG), .0034);
    sc.add(new THREE.HemisphereLight(new THREE.Color('#8ea4cc'), new THREE.Color('#6a4a34'), 1.05));
    // chimney smoke over the district (soft sprite VFX)
    this.smoke = new Puffs(sc, g.touch ? 220 : 480, { soft: .8 }); this.smokeT = 0;
    this.smokeFog = { color: new THREE.Color(FOG), near: 80, far: 520 };
    const sun = new THREE.DirectionalLight(new THREE.Color(S.color), S.intensity);
    sun.position.copy(sunDir).multiplyScalar(90); sun.target.position.set(0, 0, 0);
    sun.castShadow = true; const q = g.renderer.q; sun.shadow.mapSize.set(q.shadow, q.shadow);
    Object.assign(sun.shadow.camera, { left: -62, right: 62, top: 62, bottom: -62, near: 20, far: 200 });
    sun.shadow.bias = -.0004; sun.shadow.normalBias = .05;
    sc.add(sun, sun.target); this.sun = sun;
    // point lights from the map's anchors (hall lamps first); phones keep two
    const L = [...this.map.lights].sort((a, b) => b.intensity - a.intensity).slice(0, g.touch ? 2 : 6);
    for (const l of L) {
      const col = l.team ? (l.team === mine ? TEAM_COL.ally : TEAM_COL.enemy) : l.color;
      const pl = new THREE.PointLight(new THREE.Color(col), l.intensity * 1.6, l.dist * 1.3, 1.6);
      pl.position.set(...l.pos); sc.add(pl);
    }
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    this.envRT = pm.fromScene(new THREE.Scene().add(atmosphereSky(this.map.sky[1], this.map.sky[0], SUNC, sunDir, skyOpts)), .04);
    sc.environment = this.envRT.texture; sc.environmentIntensity = .5;
    pm.dispose(); this.disposables.push(this.envRT);
    // ---- the player's shell
    const p = g.player;
    this.oldShield = p.maxShield; p.maxShield = 50; p.maxHealth = 100;
    this.ui = new ArenaUI(g, this);
    this.warmTextures();
    this.pendingMenu = true;          // the HUD is shown by Game.enterWorld after build: hide it on the first update
    progress(1, 'Ready');
  }

  spawn() {
    const sp = this.match.pickSpawn(this.match.playerTeam);
    return { pos: sp.pos, yaw: sp.yaw };
  }

  // ---------------------------------------------------------------- loadout -> deploy, end -> again / leave
  // behind the loadout / results screens: no HUD, no gun on screen (the player waits seated, out of the way)
  menuMode(on) {
    const g = this.g;
    g.hud.show(!on);
    if (on && !g.player.dead) g.player.mode = 'seat';
    else if (!on && g.player.mode === 'seat') g.player.mode = 'foot';
  }

  deploy() {
    const g = this.g, m = this.match;
    this.ui.hideLoadout();
    this.menuMode(false);
    g.camFocus = null; g.camera.clearViewOffset();
    g.input.enabled = true; g.input.wantLock = true; g.input.lock();
    if (m.state === 'loadout') m.start();
    else if (m.state === 'live' && this.g.player.dead) { /* next respawn uses the new loadout */ }
    g.weapons.refill(); g.weapons.refreshModel(); g.hud.dirty = true;
  }

  onMatchEnd(res) {
    const g = this.g;
    g.input.enabled = false; g.input.unlock();
    this.menuMode(true);
    this.ui.showEnd(res);
  }

  again() {
    const g = this.g;
    this.ui.hideEnd();
    this.menuMode(false);
    g.input.enabled = true; g.input.wantLock = true; g.input.lock();
    this.match.restart();
  }

  leave() { this.ui.hideEnd(); this.ui.hideLoadout(); this.g.travel('ship'); }

  // main.js hooks
  holdPause() { return this.ui && (this.ui.modal || this.match.state !== 'live'); }
  hideTouch() { return this.ui && this.ui.modal; }
  scoreKey(e, down) { this.ui && this.ui.scoreKey(e, down); }
  onPlayerDeath() {
    this.match.onPlayerDied();
    this.g.hud.banner('Shell broken', this.match.killedBy ? 'by ' + this.match.killedBy.name + (this.match.killedBy.weapon ? ' · ' + this.match.killedBy.weapon : '') : 'Re-sleeving', 2.5);
  }
  onGunshot(pos) { if (this.match.state === 'live') { this.match.mgr.noise(pos, 60, this.match.player); this.match.player.lastShotT = this.match.mgr.time; } }

  // minimap blips (hud.js): squadmates always, enemies when spotted by the squad or firing unsuppressed
  blips() {
    const out = this._bl || (this._bl = []); out.length = 0;
    const m = this.match; if (!m || m.state === 'loadout') return out;
    const t = m.mgr.time;
    for (const b of m.bots) {
      if (!b.alive) continue;
      if (b.ally) out.push({ x: b.pos.x, z: b.pos.z, color: TEAM_COL.ally, r: 3 });
      else if (t - (b.spottedT ?? -99) < 1.2 || t - b.lastShotT < 1.5) out.push({ x: b.pos.x, z: b.pos.z, color: TEAM_COL.enemy, r: 3 });
    }
    return out;
  }

  update(dt) {
    const m = this.match;
    if (this.pendingMenu) {
      this.pendingMenu = false; this.menuMode(true);
      this.g.renderer.r.toneMappingExposure = .98; this.g.renderer.setBloom(.34, .92, .45);   // after Game.enterWorld's defaults
    }
    if (this.sky) this.sky.material.uniforms.time.value += dt;
    this.updateSmoke(dt);
    if (m.state === 'loadout' || (m.state === 'over' && this.ui.endShown)) this.flyover(dt);
    m.update(dt);
    this.ui.update(dt);
  }

  updateSmoke(dt) {
    const S = this.map.smoke || [];
    this.smokeT -= dt;
    if (this.smokeT <= 0 && S.length) {
      this.smokeT = this.g.touch ? .35 : .18;
      const c = S[Math.floor(Math.random() * S.length)];
      this.smoke.emit({ x: c[0], y: c[1], z: c[2] }, 1, { dir: new THREE.Vector3(.35, 1, .1), speed: 2.2, spread: .25, life: 14, size: [c[3] * 2.2, c[3] * 9],
        alpha: .32, color: Math.random() < .5 ? 0x5e5652 : 0x77706a, gravity: -.15, drag: .03, jitter: c[3] });
    }
    this.smoke.update(dt, this.smokeFog);
  }

  // a slow orbit high over the yard behind the loadout and end screens
  flyover(dt) {
    const g = this.g;
    this.flyT = (this.flyT || 0) + dt * .045;
    const a = this.flyT + (this.match.playerTeam === 'a' ? Math.PI : 0);
    const pos = new THREE.Vector3(Math.sin(a) * 46, 34, Math.cos(a) * 62), look = new THREE.Vector3(0, 2, 0);
    const mx = new THREE.Matrix4().lookAt(pos, look, new THREE.Vector3(0, 1, 0));
    const qq = new THREE.Quaternion().setFromRotationMatrix(mx);
    g.camFocus = { pos, look, orbit: false, q: qq, p0: pos, q0: qq, fov0: 55, t0: 0 };
  }

  objectives() { return []; }
  markers() { return []; }

  dispose() {
    const g = this.g;
    if (this.ui) this.ui.dispose();
    if (this.match) this.match.dispose();
    if (this.smoke) this.smoke.dispose();
    g.camFocus = null;
    if (this.oldShield) g.player.maxShield = this.oldShield;
    super.dispose();
    if (this.otherBody) g.assets.unload([this.otherBody]);
  }
}
