// Shellbreak bots: simulated squad soldiers built on the player bodies (player_<sex>.glb in tactical kit, team-tinted
// armour, morph-free shared geometry, one skeleton per body) carrying our own guns with their real stats.
//  * movement: A* on the baked nav graph (src/worlds/arena/nav.js) with string pulling, sprint / walk / ADS-walk /
//    crouch, mantles and drops along graph edges, capsule collision against the map, separation from each other;
//  * objectives: lane pushes, shared squad intel (sightings and gunfire), flanks along the alleys, marksman perches,
//    wingmen that stay near the player;
//  * combat: preferred range per weapon, strafing, cover points (crouch-peek behind waist cover), retreat when hurt,
//    reloads; human aim: 200-400 ms reaction, an aim error that decays instead of snapping, tracking lag when the target
//    moves across the view, accuracy that falls with distance; awareness of hits from behind and of gunfire;
//  * weapons: kinetic bullets with muzzle velocity and drop, energy bolts, horror goo with splash and acid, burst fire,
//    pellets, falloff, precision hits on the head; friendly fire off;
//  * performance: perception ticks scale with distance and visibility, the skinned body only animates in view (or close),
//    projectiles share two instanced draws.
import * as THREE from 'three';
import { Avatar } from './avatar.js';
import { ARCHETYPES } from './data.js';
import { makeWeapon, weaponStats, mulberry } from './state.js';
import { Weapons } from './weapons.js';
import { rayCyl, raySphere } from './combat.js';

export const MODE_DMG = 1.4;                       // every shot in a simulation hits 1.4x (time to eliminate ~0.4 s)
export const SHELL = { hp: 100, shield: 50 };      // everyone's shell (player included)
export const DIFFICULTY = {
  easy: { label: 'Recruit', react: [.34, .52], aimTau: .62, err: 2.3, track: 1.5, turn: 7, see: 62, fov: .3, jitter: 1.7, lead: .4, burst: 1.5 },
  normal: { label: 'Regular', react: [.22, .38], aimTau: .4, err: 1.45, track: 1.0, turn: 10, see: 80, fov: .18, jitter: 1.1, lead: .65, burst: 1.15 },
  hard: { label: 'Veteran', react: [.17, .28], aimTau: .27, err: .9, track: .7, turn: 13, see: 95, fov: .05, jitter: .75, lead: .85, burst: 1 },
};
// weapon pools per role and the range each weapon likes to fight at
const ROLES = {
  rifleman: ['rifle', 'carbine', 'auto', 'pulse', 'rifle', 'carbine'],
  cqb: ['ksmg', 'smg', 'pump', 'shotgun', 'ksmg', 'bile'],
  marksman: ['dmr', 'scout', 'bolt', 'sniper', 'dmr'],
  support: ['hmg', 'rifle', 'spitter', 'auto'],
  sidearm: ['handcannon', 'revolver', 'pistol', 'sidearm'],
};
const PREF = { shotgun: 6, pump: 6, bile: 6, ksmg: 11, smg: 11, pistol: 13, sidearm: 13, revolver: 14, handcannon: 14, spitter: 15,
  rifle: 20, carbine: 22, auto: 19, pulse: 22, hmg: 20, energy: 16, dmr: 30, scout: 30, bolt: 42, sniper: 44, rocket: 24, brood: 22 };
const NAMES = ['Vance', 'Okoro', 'Lindqvist', 'Ash', 'Moreau', 'Tal', 'Brisk', 'Renn', 'Calder', 'Juno', 'Sable', 'Kite', 'Hollis', 'Mire',
  'Pell', 'Draper', 'Quill', 'Ferro', 'Ostrova', 'Dace', 'Wren', 'Abara', 'Soto', 'Nakai', 'Harrow', 'Bexley', 'Corvin', 'Ilse'];
export const TEAM_COL = { ally: '#4aa8ff', enemy: '#ff4a3d' };
const LOOK = {
  male: { wear: { head: 'pioneer', top: 'undersuit', vest: 'vanguard', hands: 'gloves', legs: 'armoured', feet: 'combat', outer: 'none' }, hair: ['buzz', 'undercut', 'textured'] },
  female: { wear: { head: 'cap', top: 'sweater', vest: 'harness', hands: 'gauntlets', legs: 'leggings', feet: 'tech', outer: 'none', dress: 'none' }, hair: ['ponytail', 'bun', 'bob'] },
};
const KIT = { ally: { armor: '#3d7fd6', cloth: '#7d9cc8', legs: '#59647a', glow: '#3aa0ff' }, enemy: { armor: '#c63a2a', cloth: '#c88070', legs: '#6a524a', glow: '#ff4a3d' } };
const SKIN = ['#f1c9ad', '#e2b394', '#c99a74', '#a8744e', '#7f5236', '#5e3a24'];
const HAIR = ['#141110', '#2a211c', '#5a3c28', '#a8794c', '#d6b07a', '#7a2a20'];

const RUN = 6.8, WALK = 4.6, ADSWALK = 2.7, CROUCH = 2.0, GRAV = 19, BR = .38;
const MAX_ROUNDS = 192, MAX_GLOBS = 96;
const _v = new THREE.Vector3(), _a = new THREE.Vector3(), _b = new THREE.Vector3(), _d = new THREE.Vector3(), _e = new THREE.Vector3(),
  _h = new THREE.Vector3(), _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _M = new THREE.Matrix4(), _s = new THREE.Vector3(),
  _ax = new THREE.Vector3(), _col = new THREE.Color(), _sph = new THREE.Sphere(new THREE.Vector3(), 1.3), _frus = new THREE.Frustum(), _pm = new THREE.Matrix4();
const Z = new THREE.Vector3(0, 0, 1);
const wrap = a => Math.atan2(Math.sin(a), Math.cos(a));
const rr = (a, b, r = Math.random) => a + (b - a) * r();

// bend a bone about a world axis (converted into its parent's space); the avatar undoes touched bones every update
function bend(av, bone, axis, ang) {
  if (!bone || !bone.parent || !ang) return;
  bone.parent.getWorldQuaternion(_q);
  _ax.copy(axis).applyQuaternion(_q.invert()).normalize();
  bone.quaternion.premultiply(_q2.setFromAxisAngle(_ax, ang));
  av.touched.add(bone);
}

export class Bot {
  constructor(mgr, o) {
    this.mgr = mgr; this.g = mgr.g; this.isBot = true;
    this.team = o.team; this.name = o.name; this.sex = o.sex; this.role = o.role; this.lane = o.lane; this.wing = !!o.wing;
    this.ally = o.team === mgr.playerTeam;
    this.side = this.ally ? 'player' : 'enemy';         // combat.js: the player's rounds skip side 'player' (no friendly fire)
    this.T = { name: o.name };
    this.radius = .45; this.alive = false; this.dead = true;
    this.pos = new THREE.Vector3(); this.vel = new THREE.Vector3(); this.yaw = 0; this.aimYaw = 0; this.aimPitch = 0;
    this.grounded = true; this.crouch = 0; this.crouchWant = false; this.ads = false; this.climb = null; this.airT = 0;
    this.stats = { elims: 0, deaths: 0, assists: 0, score: 0, streak: 0, best: 0, dmg: 0 };
    this.rnd = mulberry(o.seed || 1);
    this.av = mgr.makeAvatar(this);
    this.av.root.visible = false;
    this.headY = 1.62;
    this.errY = 0; this.errP = 0; this.reactT = 0; this.cool = 0; this.burstN = 0; this.burstGap = 0; this.reloadT = 0; this.pending = 0;
    this.thinkT = Math.random() * .2; this.repathT = 0; this.stuckT = 0; this.stuckN = 0; this.lastProg = new THREE.Vector3(); this.progT = 0;
    this.path = null; this.pi = 0; this.goal = -1; this.goalKind = null; this.holdT = 0; this.peekT = 0; this.strafeT = 0; this.strafe = 1;
    this.target = null; this.seenT = -99; this.lastSeen = new THREE.Vector3(); this.heard = null; this.hurtBy = null; this.hurtT = -99;
    this.lastShotT = -99; this.protectT = 0; this.sinceHit = 99; this.animAcc = 0; this.coverNode = -1; this.laneI = 0;
  }

  // ---------------------------------------------------------------- loadout + spawn
  arm(arch) {
    const A = ARCHETYPES[arch], w = makeWeapon(arch, this.rnd() < .7 ? 1 : 2, 25, this.rnd);
    const sights = A.sights || ['default'];
    w.sight = A.sight || (this.role === 'marksman' ? sights.find(s => /x4|x2/.test(s)) || sights[0] : sights.find(s => /reflex|holo/.test(s)) || sights[0]);
    this.w = w; this.A = A; this.S = weaponStats(w); this.mag = this.S.mag; this.reloadT = 0; this.burstN = 0;
    this.pref = PREF[arch] || 18;
    const av = this.av;
    if (this.gunArch !== arch || !this.holder) {
      const old = this.holder;
      if (old && this.gunArch !== arch) { old.removeFromParent(); old.traverse(o => { if (o.isMesh) o.material.dispose(); }); this.holder = null; }
      av.attachGun(A.model, m => { m.castShadow = true; Weapons.styleMesh(m, w); });
      this.gunArch = arch; this.holder = av.gunHolder;
    } else if (this.holder && !this.holder.parent) { av.handR.add(this.holder); av.gunHolder = this.holder; av.gun = this.holder.children[0]; av.muzzle = av.gun.getObjectByName('muzzle'); }
  }

  pickWeapon() {
    const pool = ROLES[this.role] || ROLES.rifleman;
    return pool[Math.floor(this.rnd() * pool.length)];
  }

  spawnAt(p, yaw) {
    const av = this.av;
    if (av.rag) {
      av.rag = null;
      for (const [b, r] of av.restQ) b.quaternion.copy(r);
      for (const [b, q] of this.mgr.restP(av)) b.position.copy(q);
    }
    this.arm(this.pickWeapon());
    this.pos.copy(p); this.vel.set(0, 0, 0); this.yaw = this.aimYaw = yaw; this.aimPitch = 0;
    this.alive = true; this.dead = false; this.hp = SHELL.hp; this.shield = SHELL.shield; this.sinceHit = 99;
    this.protectT = 2; this.crouch = 0; this.crouchWant = false; this.climb = null; this.ads = false;
    this.target = null; this.seenT = -99; this.heard = null; this.hurtBy = null; this.path = null; this.goal = -1; this.goalKind = null;
    this.coverNode = -1; this.holdT = 0; this.laneI = 0; this.stuckT = 0; this.stuckN = 0; this.lastProg.copy(p); this.progT = 0;
    this.assist = new Map();
    av.mixer.stopAllAction(); av.current = null; av.play('Idle', 0);
    av.root.position.copy(p); av.root.rotation.set(0, yaw, 0); av.root.visible = true; av.model.position.y = 0;
    this.g.combat.targets.add(this);
    this.thinkT = .05 + Math.random() * .15;
  }

  // ---------------------------------------------------------------- combat target interface (combat.js / weapons.js)
  center(out) { return out.set(this.pos.x, this.pos.y + 1.05 - this.crouch * .35, this.pos.z); }
  eye(out) { return out.set(this.pos.x, this.pos.y + 1.6 - this.crouch * .5, this.pos.z); }
  head(out) {
    if (this.av.head && this.animated) { this.av.head.getWorldPosition(out); out.y += .08; return out; }
    return out.set(this.pos.x, this.pos.y + this.headY - this.crouch * .5, this.pos.z);
  }

  hitTest(o, d, max) {
    if (!this.alive) return null;
    let best = -1, crit = false;
    const t = raySphere(o, d, this.head(_h), .16);
    if (t >= 0 && t < max) { best = t; crit = true; }
    const top = this.pos.y + 1.5 - this.crouch * .45;
    const t2 = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, top, .32);
    if (t2 >= 0 && t2 < max && (best < 0 || t2 < best - .05)) { best = t2; crit = false; }
    return best >= 0 ? { dist: best, crit } : null;
  }

  // the player's weapons (side 'player'): damage at parity (the shell normalises weapon power), then the mode multiplier
  takeDamage(dmg, crit, point, dir, side) {
    if (!this.alive) return { killed: false };
    return this.hurt(dmg * this.mgr.playerScale() * MODE_DMG, crit, point, dir, this.mgr.player, this.mgr.playerWeaponLabel());
  }

  hurt(dmg, crit, point, dir, attacker, weapon) {
    if (!this.alive) return { killed: false };
    if (this.protectT > 0) return { killed: false, dealt: 0, immune: false };
    const mgr = this.mgr;
    this.sinceHit = 0;
    const s = Math.min(this.shield, dmg); this.shield -= s;
    const h = dmg - s; this.hp -= h;
    if (attacker) {
      this.assist.set(attacker, (this.assist.get(attacker) || 0) + dmg);
      if (attacker.stats) attacker.stats.dmg += dmg;
    }
    if (point) this.g.fx.blood(point, dir ? _v.copy(dir).negate() : null, crit ? 1.2 : .6, this.shield > 0 ? 0x6ab8ff : 0x7a0a0a);
    if (dir) this.lastHit = { dir: dir.clone(), dmg };
    // awareness: shot from somewhere it was not looking -> turn toward the shooter after a reaction delay
    if (attacker && attacker.alive !== false && attacker !== this.target) {
      this.hurtBy = attacker; this.hurtT = mgr.time;
      attacker.center(this.lastSeen); this.seenT = mgr.time - .3;
      if (!this.target || !this.targetVisible) { this.reactT = Math.max(this.reactT, rr(...mgr.D.react, this.rnd) * 1.2); this.thinkT = Math.min(this.thinkT, .05); }
    }
    if (this.hp <= 0) { this.die(attacker, weapon, crit); return { killed: true, dealt: dmg }; }
    // hurt and outgunned: think about cover now
    if (this.hp + this.shield < 70) this.thinkT = Math.min(this.thinkT, .05);
    return { killed: false, dealt: dmg };
  }

  die(attacker, weapon, crit) {
    if (!this.alive) return;
    this.alive = false; this.dead = true;
    this.g.combat.targets.delete(this);
    const h = this.lastHit, imp = h ? h.dir.clone().setY(Math.max(.15, h.dir.y)).multiplyScalar(Math.min(7, 2.4 + h.dmg * .04)) : new THREE.Vector3(0, 1, 0);
    this.holder = this.av.gunHolder;
    this.av.ragdoll(imp, (x, z) => this.g.world.collision.ground(x, z));
    this.g.fx.blood(this.center(_v).clone(), null, 1.6);
    this.mgr.onDeath(this, attacker, weapon, crit);
  }

  // ---------------------------------------------------------------- perception / decisions (ticked at a rate)
  think() {
    const mgr = this.mgr, D = mgr.D, now = mgr.time;
    this.eye(_e);
    const vx = Math.sin(this.aimYaw), vz = Math.cos(this.aimYaw);
    let best = null, bs = 1e9;
    for (const c of mgr.enemiesOf(this.team)) {
      if (!c.alive) continue;
      c.center(_a);
      const dx = _a.x - _e.x, dz = _a.z - _e.z, d = Math.hypot(dx, dz);
      if (d > D.see) continue;
      const facing = (dx * vx + dz * vz) / (d || 1);
      const shotMe = c === this.hurtBy && now - this.hurtT < 2.5;
      const loud = c.lastShotT !== undefined && now - c.lastShotT < .4 && d < 24;
      if (facing < D.fov && d > 6 && !shotMe && !loud) continue;
      if (!mgr.los(_e, _a) && !mgr.los(_e, c.head ? c.head(_b) : _b.copy(_a).setY(_a.y + .55))) continue;
      let s = d;
      if (c === this.target) s -= 9;
      if (shotMe) s -= 14;
      if (c.isPlayer) s -= 1;
      if (s < bs) { bs = s; best = c; }
    }
    if (best) {
      if (best !== this.target || !this.targetVisible) {
        // a new contact: react, then the aim converges from an error that depends on how far off the view it was
        const wasLooking = this.target === best && now - this.seenT < .8;
        if (!wasLooking) {
          this.reactT = Math.max(this.reactT, rr(...D.react, this.rnd) * (best === this.hurtBy ? .8 : 1));
          const d = best.center(_a).distanceTo(_e);
          const k = D.err * (.035 + Math.min(.06, d * .0012));
          this.errY = (this.rnd() - .5) * 2 * k; this.errP = (this.rnd() - .5) * 1.2 * k;
          this.headAim = this.rnd() < ({ easy: .04, normal: .14, hard: .3 }[mgr.diff] || .14) && d < 35;
        }
      }
      this.target = best; this.targetVisible = true; this.seenT = now; best.center(this.lastSeen);
      mgr.spot(this.team, best);
    } else {
      this.targetVisible = false;
      if (this.target && (!this.target.alive || now - this.seenT > 6)) this.target = null;
    }
    // ---- state
    const hpK = (this.hp + this.shield) / (SHELL.hp + SHELL.shield);
    if (this.targetVisible) {
      this.state = 'fight';
      // out-gunned or reloading: move to cover that faces the threat
      if ((hpK < .55 || this.reloadT > 0) && this.coverNode < 0 && this.rnd() < .7) this.findCover();
    } else if (this.target && now - this.seenT < 4) {
      this.state = 'search';
      if (this.goalKind !== 'search' || this.repathT <= 0) this.setGoal(mgr.nav.nearest(this.lastSeen.x, this.lastSeen.y, this.lastSeen.z, 6), 'search');
    } else if (this.heard && now - this.heard.t < 3.5 && this.goalKind !== 'hold' && this.goalKind !== 'heard') {
      if (this.rnd() < .65) { this.state = 'search'; this.setGoal(mgr.nav.nearest(this.heard.pos.x, this.heard.pos.y, this.heard.pos.z, 6), 'heard'); }
      this.heard = null;
    } else {
      if (this.state === 'fight' || this.state === 'search') this.coverNode = -1;
      this.state = this.holdT > 0 ? 'hold' : 'move';
      if (this.goal < 0 || (!this.path && this.holdT <= 0)) this.pickGoal();
    }
    // reload behind cover / between fights
    if (!this.targetVisible && this.reloadT <= 0 && this.mag < this.S.mag * .45 && now - this.seenT > 1.5) this.startReload();
  }

  findCover() {
    const nav = this.mgr.nav, T = this.lastSeen;
    const l = nav.within(this.pos.x, this.pos.y, this.pos.z, 7, this._cl || (this._cl = []));
    let best = -1, bs = 1e9;
    const tx = T.x - this.pos.x, tz = T.z - this.pos.z, tl = Math.hypot(tx, tz) || 1;
    for (const i of l) {
      const c = nav.cover.get(i); if (!c) continue;
      // the sheltering box must lie toward the threat
      const cx = T.x - nav.x[i], cz = T.z - nav.z[i], cl = Math.hypot(cx, cz) || 1;
      const dot = (c[0] * cx + c[1] * cz) / cl;
      if (dot < .55 || this.mgr.coverTaken(i, this)) continue;
      const d = Math.hypot(nav.x[i] - this.pos.x, nav.z[i] - this.pos.z);
      const s = d - (c[2] === 1 ? 1.5 : 0) + (cl < this.pref * .5 ? 6 : 0);
      if (s < bs) { bs = s; best = i; }
    }
    if (best >= 0) { this.coverNode = best; this.setGoal(best, 'cover'); }
  }

  // objectives when nothing is in sight
  pickGoal() {
    const mgr = this.mgr, nav = mgr.nav, r = this.rnd(), sgn = this.team === 'a' ? 1 : -1;
    // wingmen stay near the player
    if (this.wing && mgr.player.alive && mgr.player.team === this.team) {
      const P = mgr.player.pos, a = this.rnd() * 6.28;
      const n = nav.around(P.x + Math.sin(a) * 4, P.y, P.z + Math.cos(a) * 4, 3, this.rnd);
      if (n >= 0 && Math.hypot(nav.x[n] - this.pos.x, nav.z[n] - this.pos.z) > 5) { this.setGoal(n, 'follow'); return; }
      this.holdT = 1.5 + this.rnd() * 2; this.goalKind = 'hold'; return;
    }
    // marksmen like a perch for a while
    if (this.role === 'marksman' && r < .45) {
      const ps = mgr.map.perches.filter(p => p[2] * sgn < 6);
      const p = ps[Math.floor(this.rnd() * ps.length)];
      if (p) { this.setGoal(nav.nearest(p[0], p[1], p[2], 3), 'perch'); return; }
    }
    // fresh squad intel: go fight there (flankers come in along another lane)
    const intel = mgr.intelFor(this.team);
    if (intel && r < .62) {
      const flank = this.role === 'cqb' || this.lane.includes('alley') || this.rnd() < .3;
      let gx = intel.pos.x, gz = intel.pos.z, gy = intel.pos.y;
      if (flank) {
        const lanes = Object.entries(mgr.map.lanes).filter(([k]) => k !== this.laneOf(intel.pos.x));
        const L = lanes[Math.floor(this.rnd() * lanes.length)][1];
        const wp = L.reduce((b, p) => Math.abs(p[1] - gz) < Math.abs(b[1] - gz) ? p : b, L[0]);
        gx = wp[0]; gz = wp[1] - sgn * 4; gy = 0;
      }
      const n = nav.around(gx, gy, gz, 4, this.rnd);
      if (n >= 0) { this.setGoal(n, flank ? 'flank' : 'intel'); return; }
    }
    // push along the lane toward the enemy end, then patrol back through the middle
    const L = mgr.map.lanes[this.lane] || mgr.map.lanes.mid;
    const pts = sgn > 0 ? L : [...L].reverse();
    let i = this.laneI;
    while (i < pts.length - 1 && (pts[i][1] - this.pos.z) * sgn < 3) i++;
    if (i >= pts.length - 1 && Math.abs(pts[pts.length - 1][1] - this.pos.z) < 6) {
      // reached the far end: swap to another lane and come back
      const keys = Object.keys(mgr.map.lanes); this.lane = keys[Math.floor(this.rnd() * keys.length)];
      this.laneI = 0; this.holdT = .5 + this.rnd(); this.goalKind = 'hold';
      return;
    }
    this.laneI = i;
    const p = pts[i];
    const n = nav.around(p[0], 0, p[1], 3, this.rnd);
    this.setGoal(n, 'lane');
  }

  laneOf(x) { return x < -29 ? 'west_alley' : x < -12 ? 'west' : x < 12 ? 'mid' : x < 30 ? 'east' : 'east_alley'; }

  setGoal(n, kind) {
    if (n < 0) return;
    const nav = this.mgr.nav;
    const a = nav.nearest(this.pos.x, this.pos.y + .2, this.pos.z, 3);
    this.goal = n; this.goalKind = kind; this.repathT = kind === 'search' || kind === 'follow' ? 1.2 : 4;
    const p = a >= 0 ? nav.path(a, n, this.mgr.crowdCost) : null;
    this.path = p; this.pi = p && p.length > 1 ? 1 : 0;
    if (!p) { this.goal = -1; this.goalKind = null; }
    this.stuckT = 0; this.lastProg.copy(this.pos); this.progT = 0;
  }

  startReload() {
    if (this.reloadT > 0 || this.mag >= this.S.mag) return;
    this.reloadT = this.S.reload; this.burstN = 0;
  }

  // ---------------------------------------------------------------- per frame
  update(dt) {
    const mgr = this.mgr, D = mgr.D, now = mgr.time;
    if (!this.alive) {
      if (this.av.rag && this.av.root.visible) { if (mgr.visible(this.pos, 30)) this.av.update(dt); }
      return;
    }
    this.protectT -= dt; this.sinceHit += dt; this.cool -= dt; this.reactT -= dt; this.holdT -= dt; this.repathT -= dt; this.burstGap -= dt;
    if (this.sinceHit > 3.5 && this.shield < SHELL.shield) this.shield = Math.min(SHELL.shield, this.shield + 40 * dt);
    if (this.sinceHit > 6 && this.hp < SHELL.hp) this.hp = Math.min(SHELL.hp, this.hp + 25 * dt);
    if (this.reloadT > 0) { this.reloadT -= dt; if (this.reloadT <= 0) this.mag = this.S.mag; }
    this.thinkT -= dt;
    if (this.thinkT <= 0) {
      const t0 = performance.now();
      this.think();
      mgr.perf.think += performance.now() - t0;
      // near, in view or in a fight: 10 Hz; otherwise slower
      const dc = this.pos.distanceTo(this.g.camera.position);
      this.thinkT = this.targetVisible || dc < 25 ? .1 : dc < 60 ? .18 : .3;
      this.thinkT *= .85 + this.rnd() * .3;
    }
    if (this.climb) { this.updateClimb(dt); this.animate(dt); return; }
    this.move(dt);
    this.aim(dt);
    this.fire(dt);
    this.animate(dt);
  }

  // ---- movement
  move(dt) {
    const mgr = this.mgr, nav = mgr.nav;
    let wx = 0, wz = 0, speed = WALK, faceMove = true;
    this.ads = false;
    const T = this.target, fight = this.state === 'fight' && T && T.alive;
    let want = null;      // a world point to walk toward along the path
    if (fight) {
      T.center(_a);
      const dx = _a.x - this.pos.x, dz = _a.z - this.pos.z, d = Math.hypot(dx, dz) || 1;
      faceMove = false;
      this.ads = d > 9 && this.reloadT <= 0;
      if (this.coverNode >= 0) {
        // at / going to cover: crouch-peek behind waist cover, step out from full cover
        const cx = nav.x[this.coverNode], cz = nav.z[this.coverNode], cd = Math.hypot(cx - this.pos.x, cz - this.pos.z);
        if (cd > .6 && this.path) want = true;
        else {
          const c = nav.cover.get(this.coverNode);
          this.peekT -= dt;
          if (this.peekT <= 0) { this.peeking = !this.peeking; this.peekT = this.peeking ? rr(.9, 1.8, this.rnd) : rr(.5, 1.1, this.rnd); }
          const hide = !this.peeking || this.reloadT > 0;
          if (c && c[2] === 1) this.crouchWant = hide;
          else if (c && !hide) { wx = -c[1] * this.strafe; wz = c[0] * this.strafe; speed = ADSWALK; }     // lean out sideways
          if ((this.hp + this.shield) > 120 && this.reloadT <= 0 && this.rnd() < dt * .3) this.coverNode = -1;      // healthy again: leave
        }
      } else if (d > this.pref + 7 || !this.targetVisible) {
        // close the distance along the graph
        if (!this.path || this.repathT <= 0) { const n = nav.nearest(_a.x, T.pos.y, _a.z, 5); this.setGoal(n, 'chase'); this.repathT = 1; }
        want = true; speed = this.ads ? ADSWALK + 1 : WALK;
      } else {
        // in range: strafe, now and then step in or back, crouch now and then when still
        this.strafeT -= dt;
        if (this.strafeT <= 0) { this.strafe = this.rnd() < .5 ? -1 : 1; this.strafeT = rr(.45, 1.4, this.rnd); this.crouchWant = this.rnd() < .18 && d > 12; }
        const k = d < this.pref - 4 ? -.8 : d > this.pref + 3 ? .5 : 0;
        wx = (-dz / d) * this.strafe + (dx / d) * k; wz = (dx / d) * this.strafe + (dz / d) * k;
        speed = this.ads ? ADSWALK : WALK * .85;
        this.path = null;
      }
    } else if (this.state === 'hold') {
      this.crouchWant = this.goalKind === 'perch' && this.rnd() < .01 ? !this.crouchWant : this.crouchWant;
    } else if (this.path) {
      want = true; speed = this.state === 'search' ? WALK : this.goalKind === 'follow' && this.pathLeft() < 6 ? WALK : RUN;
      this.crouchWant = false;
    }
    if (want && this.path) {
      const r = this.followPath(dt);
      if (r === 'climb') return;
      if (r) { wx = r.x; wz = r.z; }
    }
    if (this.crouchWant && (wx || wz) && speed > CROUCH && !fight) this.crouchWant = false;
    if (this.crouchWant) speed = Math.min(speed, CROUCH);
    this.crouch += ((this.crouchWant ? 1 : 0) - this.crouch) * Math.min(1, dt * 8);
    const l = Math.hypot(wx, wz);
    if (l > 1e-3) { wx /= l; wz /= l; }
    // separation from squadmates and everyone else
    for (const o of mgr.bots) {
      if (o === this || !o.alive) continue;
      const dx = this.pos.x - o.pos.x, dz = this.pos.z - o.pos.z, d2 = dx * dx + dz * dz;
      if (d2 < .81 && d2 > 1e-6 && Math.abs(this.pos.y - o.pos.y) < 1.5) { const d = Math.sqrt(d2), k = (.9 - d) / d * .6; wx += dx * k; wz += dz * k; }
    }
    const P = mgr.player;
    if (P.alive) { const dx = this.pos.x - P.pos.x, dz = this.pos.z - P.pos.z, d2 = dx * dx + dz * dz; if (d2 < .7 && d2 > 1e-6) { const d = Math.sqrt(d2); this.pos.x += dx / d * (.84 - d) * .5; this.pos.z += dz / d * (.84 - d) * .5; } }
    const accel = this.grounded ? 14 : 2;
    this.vel.x += (wx * speed - this.vel.x) * Math.min(1, accel * dt);
    this.vel.z += (wz * speed - this.vel.z) * Math.min(1, accel * dt);
    this.vel.y -= GRAV * dt;
    const res = this.g.world.collision.moveCapsule(this.pos, this.vel, BR, this.crouch > .5 ? 1.15 : 1.8, dt);
    if (!this.grounded && res.grounded) this.airT = 0;
    this.grounded = res.grounded; if (!this.grounded) this.airT += dt;
    if (this.pos.y < -5) { this.pos.y = 0; this.vel.set(0, 0, 0); }
    if (faceMove && Math.hypot(this.vel.x, this.vel.z) > .8) {
      const t = Math.atan2(this.vel.x, this.vel.z);
      this.aimYaw += wrap(t - this.aimYaw) * Math.min(1, dt * 6);
      this.aimPitch += (0 - this.aimPitch) * Math.min(1, dt * 4);
    }
    // stuck watchdog: no progress toward the path for a while -> hop, repath, new goal, finally a nudge onto the graph
    if (want && this.path) {
      this.progT += dt;
      if (this.progT > 1) {
        const moved = this.pos.distanceTo(this.lastProg);
        if (moved < .45) {
          this.stuckN++;
          if (this.stuckN === 1 && this.grounded) this.vel.y = 6;
          else if (this.stuckN === 2) this.setGoal(this.goal, this.goalKind);
          else if (this.stuckN === 4) { this.goal = -1; this.path = null; this.pickGoal(); }
          else if (this.stuckN >= 6) {
            const n = nav.nearest(this.pos.x, this.pos.y, this.pos.z, 6);
            if (n >= 0) { this.pos.set(nav.x[n], nav.y[n], nav.z[n]); this.vel.set(0, 0, 0); }
            mgr.stats.stuck++; this.stuckN = 0; this.path = null; this.goal = -1;
          }
        } else this.stuckN = 0;
        this.lastProg.copy(this.pos); this.progT = 0;
      }
    } else { this.progT = 0; this.lastProg.copy(this.pos); }
  }

  pathLeft() {
    const p = this.path, nav = this.mgr.nav; if (!p) return 0;
    const n = p[p.length - 1]; return Math.hypot(nav.x[n] - this.pos.x, nav.z[n] - this.pos.z);
  }

  // steer along the node list; returns a direction (x, z) or 'climb' when a mantle starts
  followPath(dt) {
    const nav = this.mgr.nav, p = this.path;
    if (!p || this.pi >= p.length) { this.arrive(); return null; }
    let n = p[this.pi];
    let dx = nav.x[n] - this.pos.x, dz = nav.z[n] - this.pos.z, dy = nav.y[n] - this.pos.y;
    let d = Math.hypot(dx, dz);
    const prev = this.pi > 0 ? p[this.pi - 1] : -1;
    const et = prev >= 0 ? nav.edgeType(prev, n) : 0;
    if (et === 2 && dy > .35 && d < 2.3 && this.grounded) {
      // mantle up to the node
      this.climb = { from: this.pos.clone(), to: new THREE.Vector3(nav.x[n], nav.y[n], nav.z[n]), t: 0, dur: .36 + dy * .15 };
      this.vel.set(0, 0, 0);
      this.pi++;
      return 'climb';
    }
    if (d < .55 && Math.abs(dy) < 1.4) {
      this.pi++;
      if (this.pi >= p.length) { this.arrive(); return null; }
      this.pullString();
      n = p[this.pi]; dx = nav.x[n] - this.pos.x; dz = nav.z[n] - this.pos.z; d = Math.hypot(dx, dz);
    }
    return _d.set(dx / (d || 1), 0, dz / (d || 1));
  }

  // skip ahead to the furthest node in a straight, level, clear line
  pullString() {
    const nav = this.mgr.nav, p = this.path, y = this.pos.y;
    let j = this.pi;
    for (let k = this.pi + 1; k < Math.min(p.length, this.pi + 7); k++) {
      const a = p[k - 1], b = p[k];
      if (nav.edgeType(a, b) !== 0 || Math.abs(nav.y[b] - y) > .3) break;
      _a.set(this.pos.x, y + .5, this.pos.z); _b.set(nav.x[b], nav.y[b] + .5, nav.z[b]);
      if (!this.mgr.los(_a, _b, .2)) break;
      _a.y += .9; _b.y += .9;
      if (!this.mgr.los(_a, _b, .2)) break;
      // also clear a body width either side
      j = k;
    }
    this.pi = j;
  }

  arrive() {
    const k = this.goalKind;
    this.path = null;
    if (k === 'perch') { this.holdT = rr(8, 16, this.rnd); this.goalKind = 'hold'; }
    else if (k === 'cover') { /* stays: move() handles the peeking */ }
    else if (k === 'search' || k === 'heard') { this.holdT = rr(1, 2.5, this.rnd); this.goalKind = 'hold'; this.target = this.targetVisible ? this.target : null; }
    else if (k === 'follow') { this.holdT = rr(1, 2.5, this.rnd); this.goalKind = 'hold'; }
    else if (k === 'lane') { this.laneI++; this.goal = -1; }
    else this.goal = -1;
    if (k !== 'cover') this.goal = -1;
  }

  updateClimb(dt) {
    const c = this.climb; c.t += dt / c.dur;
    const t = Math.min(1, c.t), up = Math.min(1, t / .62), fw = Math.max(0, (t - .45) / .55);
    const eu = 1 - Math.pow(1 - up, 3), ef = fw * fw * (3 - 2 * fw);
    this.pos.set(c.from.x + (c.to.x - c.from.x) * ef, c.from.y + (c.to.y + .05 - c.from.y) * eu, c.from.z + (c.to.z - c.from.z) * ef);
    if (t >= 1) { this.climb = null; this.pos.copy(c.to); this.grounded = true; this.vel.set(0, 0, 0); this.pullString(); }
  }

  // ---- aim: converge on the target with a decaying error, lag behind sideways motion
  aim(dt) {
    const mgr = this.mgr, D = mgr.D, T = this.target;
    const engaged = T && T.alive && (this.targetVisible || mgr.time - this.seenT < .7);
    if (!engaged) {
      if (this.heard && mgr.time - this.heard.t < 1.5) {
        const yw = Math.atan2(this.heard.pos.x - this.pos.x, this.heard.pos.z - this.pos.z);
        this.aimYaw += wrap(yw - this.aimYaw) * Math.min(1, dt * 5);
      }
      this.errY *= .9; this.errP *= .9;
      return;
    }
    this.eye(_e);
    const tgt = this.targetVisible ? T.center(_a) : _a.copy(this.lastSeen);
    if (this.targetVisible && this.headAim) T.head ? T.head(_a) : _a.y += .5;
    const dist = _a.distanceTo(_e);
    // lead moving targets for slow projectiles, and lob against gravity
    const vel = this.A.goo || this.A.projectile ? (this.A.vel || 40) : (this.A.vel || 600);
    const tof = dist / vel;
    if (this.targetVisible && T.vel) _a.addScaledVector(T.vel, tof * D.lead);
    const grav = this.A.goo ? (this.A.goo === 'bile' ? 1.3 : this.A.goo === 'brood' ? .85 : 1) : this.A.grav || 0;
    if (grav) _a.y += .5 * 9.81 * grav * tof * tof * .9 - (this.A.goo && this.A.goo !== 'bile' ? 1.2 * tof : 0);
    const dx = _a.x - _e.x, dy = _a.y - _e.y, dz = _a.z - _e.z;
    const wantY = Math.atan2(dx, dz), wantP = Math.atan2(dy, Math.hypot(dx, dz));
    // tracking error: grows with how fast the target sweeps across the view
    if (this.prevWant !== undefined) {
      const om = Math.abs(wrap(wantY - this.prevWant)) / Math.max(dt, 1e-3);
      this.errY += Math.sign(wrap(wantY - this.prevWant)) * -Math.min(1.5, om) * dt * D.track * .45;
    }
    this.prevWant = wantY;
    const decay = Math.exp(-dt / D.aimTau);
    this.errY *= decay; this.errP *= decay;
    const k = Math.min(1, dt * D.turn);
    this.aimYaw += wrap(wantY + this.errY - this.aimYaw) * k;
    this.aimPitch += (wantP + this.errP - this.aimPitch) * k;
    this.aimDist = dist; this.trueY = wantY; this.trueP = wantP;
  }

  // ---- shooting with the weapon's real numbers
  fire(dt) {
    const mgr = this.mgr, D = mgr.D, A = this.A, S = this.S, T = this.target;
    if (this.pending > 0) {        // remaining shots of a burst (pulse rifles)
      this.burstCool -= dt;
      if (this.burstCool <= 0 && this.mag > 0) { this.shoot(); this.pending--; this.burstCool = 60 / (A.burstRpm || 900); }
      return;
    }
    if (!T || !T.alive || !this.targetVisible || this.reactT > 0 || this.reloadT > 0 || this.cool > 0 || this.burstGap > 0 || this.climb) return;
    if (this.mag <= 0) { this.startReload(); return; }
    if (this.crouchWant && this.coverNode >= 0 && !this.peeking) return;
    const dist = this.aimDist || 20;
    // on target? (within the target's angular size, a little generous: humans shoot when it looks close)
    const tol = Math.max(.012, Math.atan2(.42, dist)) * (A.pellets ? 2.4 : 1.6) + (A.splash ? .03 : 0);
    const off = Math.hypot(wrap(this.aimYaw - this.trueY), this.aimPitch - this.trueP);
    if (off > tol) return;
    if (dist > S.range * 2.6 && !A.projectile) return;       // far beyond the weapon's reach: hold fire, close in
    this.cool = 60 / S.rpm;
    if (!A.auto) this.cool *= rr(1.05, 1.5, this.rnd) * (dist > 25 ? 1.2 : 1);
    if (A.burst) { this.shoot(); this.pending = A.burst - 1; this.burstCool = 60 / (A.burstRpm || 900); this.cool += (A.burst - 1) * 60 / (A.burstRpm || 900) + rr(.1, .3, this.rnd); return; }
    this.shoot();
    // recoil control: automatic fire in bursts at range
    if (A.auto && dist > 16) {
      this.burstN++;
      if (this.burstN >= Math.max(3, Math.round(rr(4, 8, this.rnd) / D.burst * (30 / Math.max(15, dist))))) { this.burstN = 0; this.burstGap = rr(.18, .42, this.rnd) * D.burst; }
    }
  }

  shoot() {
    const mgr = this.mgr, D = mgr.D, A = this.A, S = this.S, g = this.g;
    this.mag--; this.lastShotT = mgr.time; this.protectT = 0;
    this.eye(_e);
    const from = this.mgr.visible(this.pos, 60) && this.av.muzzle ? this.av.muzzleWorld(_b) : _b.copy(_e);
    const moving = Math.hypot(this.vel.x, this.vel.z) > .6;
    const spreadDeg = S.spread * (this.ads ? .45 : 1) * (moving ? 1.35 : 1) * (this.grounded ? 1 : 1.6);
    const n = A.pellets || 1;
    const jit = D.jitter * THREE.MathUtils.degToRad(.25 + (this.aimDist || 20) * .012);
    const cy = Math.cos(this.aimPitch);
    for (let k = 0; k < n; k++) {
      const sp = THREE.MathUtils.degToRad(spreadDeg);
      const yw = this.aimYaw + (this.rnd() - .5) * 2 * sp + (k === 0 || n === 1 ? (this.rnd() - .5) * 2 * jit : 0);
      const pt = this.aimPitch + (this.rnd() - .5) * 2 * sp + (k === 0 || n === 1 ? (this.rnd() - .5) * jit : 0);
      _d.set(Math.sin(yw) * Math.cos(pt), Math.sin(pt), Math.cos(yw) * Math.cos(pt));
      mgr.launch(this, _e, from, _d);
    }
    const col = A.cls === 'horror' ? 0x9aff4a : A.cls === 'energy' ? (A.tracer ? new THREE.Color(A.tracer).getHex() : 0x8fd8ff) : 0xffc070;
    if (mgr.visible(this.pos, 70)) g.fx.muzzle(from, _d, col);
    mgr.sound(this, A.sound, from);
    mgr.noise(_e, A.sound === 'sniper' || A.sound === 'boltaction' ? 85 : 60, this);
    if (this.mag <= 0) this.startReload();
    void cy;
  }

  // ---- animation: only bodies in view (or close) are animated; the rest catch up rarely
  animate(dt) {
    const mgr = this.mgr, av = this.av;
    av.root.position.copy(this.pos);
    // the body faces the aim while fighting, the travel direction otherwise
    this.yaw += wrap(this.aimYaw - this.yaw) * Math.min(1, dt * 12);
    av.root.rotation.set(0, this.yaw, 0);
    const vis = mgr.visible(this.pos, 110), dc = _v.copy(this.pos).sub(this.g.camera.position).length();
    this.animAcc += dt;
    const every = !vis ? (dc < 10 ? 0 : .5) : dc > 55 ? 1 / 20 : 0;
    if (this.animAcc < every) { this.animated = false; return; }
    const step = this.animAcc; this.animAcc = 0; this.animated = true;
    const t0 = performance.now();
    const hs = Math.hypot(this.vel.x, this.vel.z);
    if (this.climb || (!this.grounded && this.airT > .15)) av.play('Jump', .12);
    else if (hs > 5.2) av.play('Run', .2, hs / RUN * 1.05);
    else if (hs > .35) {
      const fwd = this.vel.x * Math.sin(this.yaw) + this.vel.z * Math.cos(this.yaw);
      av.play('Walk', .2, (fwd < -.3 ? -1 : 1) * Math.max(.6, hs / WALK) * 1.1);
    } else av.play('Idle', .25);
    av.aimPitch = this.aimPitch * .9;
    av.update(Math.min(step, .1));
    if (this.crouch > .02) this.crouchPose(this.crouch);
    else av.model.position.y = 0;
    mgr.perf.anim += performance.now() - t0; mgr.perf.animN++;
  }

  // procedural crouch over any clip: knees forward, hips down, chest a touch forward
  crouchPose(c) {
    const av = this.av, B = av.bones;
    av.root.updateMatrixWorld(true);
    av.root.getWorldQuaternion(_q2);
    const right = _s.set(1, 0, 0).applyQuaternion(_q2);
    const r = right.clone();
    for (const s of ['L', 'R']) {
      bend(av, B['thigh' + s], r, -1.15 * c);
      av.model.updateMatrixWorld(true);
      bend(av, B['shin' + s], r, 1.9 * c);
      av.model.updateMatrixWorld(true);
      bend(av, B['foot' + s], r, -.75 * c);
    }
    bend(av, B.spine, r, -.25 * c);
    av.model.position.y = -.42 * c;
  }
}

// ======================================================================================== manager
export class BotManager {
  constructor(game, world, opts) {
    this.g = game; this.world = world; this.nav = world.nav; this.map = world.map;
    this.D = DIFFICULTY[opts.difficulty] || DIFFICULTY.normal; this.diff = opts.difficulty;
    this.playerTeam = opts.playerTeam; this.player = opts.player;
    this.bots = []; this.rounds = []; this.globs = []; this.dots = new Map(); this.time = 0;
    this.intel = { a: [], b: [] };
    this.stats = { stuck: 0, shots: 0, hits: 0 };
    this.perf = { think: 0, anim: 0, animN: 0, ms: 0, frames: 0, maxMs: 0 };
    this.sndT = 0; this.sndN = 0;
    this.geoCache = new Map(); this.restCache = new Map();
    this.onDeath = opts.onDeath || (() => {});
    this.crowdCost = i => this.crowd && this.crowd.has(i) ? 2 : 0;
    // tracers: one instanced draw; goo / rockets: another (VFX only)
    const sg = new THREE.CylinderGeometry(1, .35, 1, 6, 1, true); sg.rotateX(Math.PI / 2); sg.translate(0, 0, .5);
    this.streaks = new THREE.InstancedMesh(sg, new THREE.MeshBasicMaterial({ color: 0xffffff, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, toneMapped: false }), MAX_ROUNDS);
    this.streaks.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_ROUNDS * 3), 3);
    this.streaks.frustumCulled = false; this.streaks.count = 0;
    this.blobs = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 10, 8), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: .6, roughness: .3 }), MAX_GLOBS);
    this.blobs.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_GLOBS * 3), 3);
    this.blobs.frustumCulled = false; this.blobs.count = 0; this.blobs.castShadow = false;
    world.scene.add(this.streaks, this.blobs);
  }

  // ---------------------------------------------------------------- bodies
  // A soldier on a player body: tactical kit with team-tinted armour; hidden pieces dropped, face morphs stripped
  // (geometry shared per source mesh), crowd-cheap hair material.
  makeAvatar(bot) {
    const model = bot.sex === 'male' ? 'player_male' : 'player_female';
    const av = new Avatar(this.g.assets, model);
    const L = LOOK[bot.sex], K = KIT[bot.ally ? 'ally' : 'enemy'], r = bot.rnd;
    const wear = {}; for (const s of Object.keys(av.items)) wear[s] = 'none';
    Object.assign(wear, L.wear); wear.hair = L.hair[Math.floor(r() * L.hair.length)];
    if (bot.sex === 'female' && r() < .4) wear.head = 'none';
    const look = { v: 3, body: bot.sex, skin: SKIN[Math.floor(r() * SKIN.length)], eyes: '#5a4a3a', hairColor: HAIR[Math.floor(r() * HAIR.length)], brow: Math.floor(r() * 4),
      face: {}, sliders: {}, wear, tints: { top: K.cloth, legs: K.legs, hands: '#5a5a60', feet: '#4a4a4a', head: K.armor, vest: K.armor }, glow: K.glow };
    av.applyCharacter(look);
    for (const m of av.allMats) {
      if (/^armor_primary__/.test(m.name)) m.color.set(K.armor).multiplyScalar(.85);
      if (m.name === 'visor' && m.emissive) { m.emissive.set(K.glow); m.emissiveIntensity = 1.2; }
    }
    const hidden = [];
    av.model.traverse(o => { if (!o.visible && !o.isBone && o !== av.model) hidden.push(o); });
    for (const o of hidden) o.removeFromParent();
    av.allMats = []; av.morphMeshes = [];
    av.model.traverse(o => {
      if (!o.isMesh) return;
      if (o.material.name === 'hair' && o.material.isMeshPhysicalMaterial) {
        const h = o.material, s = new THREE.MeshStandardMaterial({ name: 'hair', map: h.map, color: h.color.clone(), roughness: .6, alphaTest: .42, side: THREE.DoubleSide });
        h.dispose(); o.material = s;
      }
      if (o.geometry.morphAttributes && Object.keys(o.geometry.morphAttributes).length) {
        let gg = this.geoCache.get(o.geometry);
        if (!gg) { gg = o.geometry.clone(); gg.morphAttributes = {}; gg.userData.shared = true; this.geoCache.set(o.geometry, gg); }
        o.geometry = gg; o.morphTargetInfluences = undefined; o.morphTargetDictionary = undefined;
      }
      o.frustumCulled = true; o.castShadow = true; o.receiveShadow = false;
      av.allMats.push(o.material);
    });
    av.coverU = av.coverU || { value: 0 };
    this.world.scene.add(av.root);
    av.root.scale.setScalar(bot.sex === 'male' ? 1 : 1.0);
    return av;
  }

  restP(av) {
    let m = this.restCache.get(av);
    if (!m) { m = new Map(); av.model.traverse(o => { if (o.isBone) m.set(o, o.position.clone()); }); this.restCache.set(av, m); }
    return m;
  }

  add(o) {
    const b = new Bot(this, o);
    this.restP(b.av);
    this.bots.push(b);
    return b;
  }

  // ---------------------------------------------------------------- queries
  enemiesOf(team) {
    const out = this._en || (this._en = []); out.length = 0;
    for (const b of this.bots) if (b.team !== team && b.alive) out.push(b);
    if (this.player.team !== team && this.player.alive) out.push(this.player);
    return out;
  }

  los(a, b, pad = .1) {
    const d = _v.subVectors(b, a), len = d.length(); if (len < .05) return true;
    d.divideScalar(len);
    return !this.g.world.collision.raycast(a, d, len - pad);
  }

  visible(p, maxD) {
    _sph.center.set(p.x, p.y + 1, p.z);
    if (_sph.center.distanceToSquared(this.g.camera.position) > maxD * maxD) return false;
    return _frus.intersectsSphere(_sph);
  }

  coverTaken(i, me) { for (const b of this.bots) if (b !== me && b.alive && b.coverNode === i) return true; return false; }

  // a sighting (shared with the squad): pings the radar too
  spot(team, c) {
    const L = this.intel[team], t = this.time;
    const e = L.find(x => x.c === c);
    if (e) { e.pos.copy(c.pos); e.t = t; } else L.push({ c, pos: c.pos.clone(), t });
    c.spottedT = t;
  }
  intelFor(team) {
    const L = this.intel[team], t = this.time;
    for (let i = L.length - 1; i >= 0; i--) if (t - L[i].t > 9 || !L[i].c.alive) L.splice(i, 1);
    return L.length ? L[Math.floor(Math.random() * L.length)] : null;
  }

  // gunfire carries: bots that are not fighting turn toward it and may go and look
  noise(pos, r, src) {
    for (const b of this.bots) {
      if (!b.alive || b === src || (src && src.team === b.team)) continue;
      if (b.targetVisible) continue;
      const d = b.pos.distanceTo(pos);
      if (d > r) continue;
      b.heard = { pos: pos.clone(), t: this.time };
      if (d < r * .5) b.thinkT = Math.min(b.thinkT, .15);
    }
    if (src && src.team) { const L = this.intel[src.team === 'a' ? 'b' : 'a']; if (L && src.isPlayer === undefined) { /* heard, not seen: no squad ping */ } }
    if (src) src.lastShotT = this.time;
  }

  playerScale() {
    const w = this.g.weapons && this.g.weapons.equipped();
    return w ? (1 + 25 / 200) / (1 + w.power / 200) : 1;
  }
  playerWeaponLabel() { const w = this.g.weapons && this.g.weapons.equipped(); return w ? w.name : ''; }

  sound(bot, kind, pos) {
    // cap the shot sounds (WebAudio nodes): near shots always, far ones thinned out
    const d = pos.distanceTo(this.g.camera.position);
    if (d > 26 && this.sndN > 6) return;
    this.sndN++;
    this.g.audio.shot(kind, pos, true);
  }

  // ---------------------------------------------------------------- projectiles
  launch(bot, eye, from, dir) {
    const A = bot.A, S = bot.S;
    this.stats.shots++;
    if (A.goo || A.projectile) {
      if (this.globs.length >= MAX_GLOBS) this.globs.shift();
      const sp = A.projectile ? 48 : (A.vel || 30) * (A.goo === 'bile' ? .75 + Math.random() * .5 : 1);
      const v = dir.clone().multiplyScalar(sp); if (A.goo && A.goo !== 'bile') v.y += 1.2;
      this.globs.push({ p: from.clone(), v, bot, A, S, life: A.projectile ? 5 : A.goo === 'bile' ? 1.1 : 3,
        grav: A.projectile ? 0 : A.goo === 'bile' ? 1.3 : A.goo === 'brood' ? .85 : 1, size: A.projectile ? .12 : A.goo === 'brood' ? .1 : A.goo === 'bile' ? .03 : .065,
        col: A.projectile ? 0xffa040 : A.goo === 'brood' ? 0xd8607a : A.goo === 'bile' ? 0xc8e040 : 0x7cff3a, splash: A.splash || 0, dist: 0 });
      return;
    }
    if (this.rounds.length >= MAX_ROUNDS) this.rounds.shift();
    const speed = (A.vel || 600) * (.97 + Math.random() * .06);
    const kinetic = A.cls === 'kinetic';
    this.rounds.push({ p: eye.clone(), v: dir.clone().multiplyScalar(speed), off: from.clone().sub(eye), dist: 0, life: Math.max(1, S.range * 8 / speed + .4),
      grav: A.grav ?? (kinetic ? 1 : 0), bot, A, S, col: A.tracer || (kinetic ? '#ffcf8a' : bot.ally ? '#9fd8ff' : '#ffb0a0'), width: A.dmg > 100 ? .022 : kinetic ? .01 : .016 });
  }

  // nearest hit along a segment: world, enemy bots, the player
  trace(o, d, max, team) {
    let best = max, tgt = null, crit = false;
    for (const b of this.bots) {
      if (!b.alive || b.team === team) continue;
      const h = b.hitTest(o, d, best);
      if (h && h.dist < best) { best = h.dist; tgt = b; crit = h.crit; }
    }
    const P = this.player;
    if (P.alive && P.team !== team && this.g.player.mode === 'foot') {
      const p = this.g.player, top = p.crouch ? 1.15 : 1.8;
      const t = rayCyl(o, d, p.pos.x, p.pos.z, p.pos.y, p.pos.y + top - .25, .38);
      if (t >= 0 && t < best) { best = t; tgt = P; crit = false; }
      _h.set(p.pos.x, p.pos.y + top - .16, p.pos.z);
      const th = raySphere(o, d, _h, .17);
      if (th >= 0 && th < best + .05) { best = Math.min(best, th); tgt = P; crit = true; }
    }
    const wh = this.g.world.collision.raycast(o, d, best);
    if (wh && wh.dist < best) return { hit: true, dist: wh.dist, point: wh.point, normal: wh.normal };
    return tgt ? { target: tgt, crit, dist: best, point: _a.copy(o).addScaledVector(d, best).clone() } : null;
  }

  damage(victim, dmg, crit, point, dir, bot) {
    if (victim.isPlayer) return this.hitPlayer(dmg, crit, point, bot);
    return victim.hurt(dmg, crit, point, dir, bot, bot.w.name);
  }

  hitPlayer(dmg, crit, from, bot) {
    const P = this.player, p = this.g.player;
    if (!P.alive || P.protectT > 0 || this.g.godMode) return { killed: false };
    this.world.lastAttacker = { c: bot, weapon: bot.w.name, crit, t: this.time };
    P.assist.set(bot, (P.assist.get(bot) || 0) + dmg); bot.stats.dmg += dmg;
    p.damage(dmg, bot.pos.clone().setY(bot.pos.y + 1.4));
    return { killed: p.dead };
  }

  splash(at, r, dmg, bot, exclude = null) {
    for (const c of this.enemiesOf(bot.team)) {
      if (c === exclude) continue;
      const d = c.center(_v).distanceTo(at);
      if (d < r + .4) this.damage(c, dmg * (1 - Math.min(1, d / (r + .5)) * .6), false, null, _b.subVectors(_v, at).normalize(), bot);
    }
  }

  // acid from horror guns keeps eating for 3 s
  afflict(victim, total, bot) {
    if (!victim || !victim.alive || total <= 0) return;
    const a = this.dots.get(victim);
    if (a) { a.dps = Math.min(a.dps + total / 3 * .6, total); a.t = 3; a.bot = bot; } else this.dots.set(victim, { dps: total / 3, t: 3, tick: .35, bot });
  }

  updateProjectiles(dt) {
    let n = 0;
    for (let i = this.rounds.length - 1; i >= 0; i--) {
      const r = this.rounds[i];
      r.life -= dt; r.v.y -= 9.81 * r.grav * dt;
      const sp = r.v.length(), step = sp * dt;
      _d.copy(r.v).divideScalar(sp || 1);
      const res = this.trace(r.p, _d, step, r.bot.team);
      if (res) {
        if (res.target) {
          const dist = r.dist + res.dist, S = r.S;
          const fall = dist < S.range ? 1 : Math.max(.5, 1 - (dist - S.range) / (S.range * 2));
          const dmg = S.dmg * MODE_DMG * fall * (res.crit ? S.crit : 1);
          this.damage(res.target, dmg, res.crit, res.point, _d, r.bot);
          this.stats.hits++;
          if (!res.target.isPlayer && this.visible(res.point, 50)) this.g.fx.impact(res.point, _v.copy(_d).negate(), res.crit ? 'crit' : 'enemy');
        } else if (this.visible(res.point, 50)) this.g.fx.impact(res.point, res.normal, 'metal');
        this.rounds.splice(i, 1); continue;
      }
      r.p.addScaledVector(_d, step); r.dist += step;
      if (r.life <= 0 || r.dist > 300) { this.rounds.splice(i, 1); continue; }
      const k = Math.max(0, 1 - r.dist / 14);
      _a.copy(r.p).addScaledVector(r.off, k);
      const len = Math.min(3.5, r.dist * .8, step * 1.2 + .5);
      _b.copy(_a).addScaledVector(_d, -len);
      if (n < MAX_ROUNDS) {
        _q.setFromUnitVectors(Z, _d); _M.compose(_b, _q, _s.set(r.width, r.width, len));
        this.streaks.setMatrixAt(n, _M); _col.set(r.col); this.streaks.setColorAt(n, _col.multiplyScalar(4)); n++;
      }
    }
    this.streaks.count = n;
    if (n) { this.streaks.instanceMatrix.needsUpdate = true; this.streaks.instanceColor.needsUpdate = true; }
    let m = 0;
    for (let i = this.globs.length - 1; i >= 0; i--) {
      const q = this.globs[i];
      q.life -= dt; q.v.y -= 9.81 * q.grav * dt;
      const sp = q.v.length(), step = sp * dt;
      _d.copy(q.v).divideScalar(sp || 1);
      const res = this.trace(q.p, _d, step + q.size, q.bot.team);
      if (res || q.life <= 0) {
        const at = res ? res.point : q.p.clone();
        const A = q.A, S = q.S, bot = q.bot;
        if (A.projectile) {
          this.splash(at, A.splash || 6, S.dmg * MODE_DMG * .6, bot);
          this.g.fx.explosion(at, A.splash || 5); this.g.audio.explosion(at);
        } else {
          if (res && res.target) {
            const dmg = S.dmg * MODE_DMG * (res.crit ? S.crit : 1);
            this.damage(res.target, dmg, res.crit, at, _d, bot); this.stats.hits++;
            this.afflict(res.target, dmg * (A.dot || .5), bot);
          }
          if (A.goo === 'brood') { this.splash(at, A.splash, S.dmg * MODE_DMG * .55, bot); this.g.fx.slime(at, res && res.normal || null, 2, 0x9aff4a); this.g.audio.splat(at, true); }
          else if (A.goo === 'spit') { this.splash(at, A.splash || 1, S.dmg * MODE_DMG * .35, bot, res && res.target); if (this.visible(at, 40)) this.g.fx.slime(at, res && res.normal || null, 1, q.col); }
          else if (this.visible(at, 30) && Math.random() < .4) this.g.fx.slimeDrops(at, res && res.normal || null, 3, 1.5, q.col, .6);
        }
        this.globs.splice(i, 1); continue;
      }
      q.p.addScaledVector(_d, step);
      if (A_trail(q) && Math.random() < dt * 20) this.g.fx.emit(q.p, 2, 1.5, 0xff9040, .3, -1, .12, 1);
      if (m < MAX_GLOBS) {
        _q.setFromUnitVectors(Z, _d); _M.compose(q.p, _q, _s.set(q.size, q.size, q.size * 1.5));
        this.blobs.setMatrixAt(m, _M); this.blobs.setColorAt(m, _col.set(q.col)); m++;
      }
    }
    this.blobs.count = m;
    if (m) { this.blobs.instanceMatrix.needsUpdate = true; this.blobs.instanceColor.needsUpdate = true; }
    // acid ticks
    for (const [v, a] of this.dots) {
      if (!v.alive || a.t <= 0) { this.dots.delete(v); continue; }
      a.t -= dt; a.tick -= dt;
      if (a.tick > 0) continue;
      a.tick += .35;
      this.damage(v, a.dps * .35, false, null, null, a.bot);
    }
  }

  // ---------------------------------------------------------------- frame
  update(dt) {
    const t0 = performance.now();
    this.time += dt;
    const cam = this.g.camera;
    cam.updateMatrixWorld();
    _frus.setFromProjectionMatrix(_pm.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
    this.sndN = 0;
    // nodes other bots are standing on or heading to cost a little extra (they spread out)
    this.crowd = this.crowd || new Set(); this.crowd.clear();
    for (const b of this.bots) if (b.alive && b.goal >= 0) this.crowd.add(b.goal);
    for (const b of this.bots) b.update(dt);
    this.updateProjectiles(dt);
    const ms = performance.now() - t0;
    this.perf.ms += ms; this.perf.frames++; this.perf.maxMs = Math.max(this.perf.maxMs, ms);
  }

  clearShots() { this.rounds.length = 0; this.globs.length = 0; this.dots.clear(); this.streaks.count = 0; this.blobs.count = 0; }

  dispose() {
    for (const b of this.bots) { this.g.combat.targets.delete(b); b.av.dispose(); }
    for (const g of this.geoCache.values()) g.dispose();
    this.streaks.removeFromParent(); this.blobs.removeFromParent();
    this.streaks.geometry.dispose(); this.blobs.geometry.dispose();
    this.bots = [];
  }
}

function A_trail(q) { return !!q.A.projectile; }

export { NAMES, ROLES };
