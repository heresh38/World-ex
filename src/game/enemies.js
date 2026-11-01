// Enemies: troopers, brutes (humanoid, skinned), drones, turrets and outpost generators, the VANTHOS alien species and
// the Writhe, a parasitic infestation hostile to every other faction (mites swarm and burrow into fresh corpses,
// which rise again as hosts; bladders burst into brood; amalgams are hosts fused into one armoured mass).
import * as THREE from 'three';
import { Avatar } from './avatar.js';
import { raySphere, rayCyl } from './combat.js';

const _v = new THREE.Vector3(), _d = new THREE.Vector3(), _h = new THREE.Vector3(), _a = new THREE.Vector3();

const TYPES = {
  trooper: { model: 'enemy_trooper', gun: 'gun_pulse', hp: 110, speed: 3.4, range: 32, dmg: 6, burst: 3, gap: [1.2, 2.2], xp: 40, scale: 1, name: 'Raider Trooper', loot: .14, human: true },
  brute: { model: 'enemy_brute', gun: 'gun_shotgun', hp: 420, speed: 2.8, range: 15, dmg: 5, pellets: 5, burst: 1, gap: [1.6, 2.4], xp: 120, scale: 1.22, name: 'Raider Brute', loot: .45, human: true },
  drone: { hp: 70, speed: 7, range: 30, dmg: 5, burst: 2, gap: [1.0, 1.8], xp: 35, name: 'Seeker Drone', loot: .15 },
  turret: { hp: 260, range: 40, dmg: 6, burst: 4, gap: [1.4, 2.0], xp: 60, name: 'Sentry Turret', loot: .3 },
  generator: { hp: 900, xp: 200, name: 'Raider Generator', loot: 1 },
  // VANTHOS alien species (alien_*.glb): spit glowing bolts at range, claw up close
  stalker: { blood: 0x5a2a8a, model: 'alien_stalker', gun: null, hp: 140, speed: 5.4, range: 18, dmg: 7, burst: 2, gap: [1.4, 2.4], xp: 50, scale: 1.05, name: 'Stalker', loot: .18, faction: 'alien', pref: 3, melee: [18, 2.2, .9], bolt: 0xb46cff },
  hulk: { blood: 0x8a4a1a, model: 'alien_hulk', gun: null, hp: 950, speed: 3.1, range: 22, dmg: 9, pellets: 4, burst: 1, gap: [2, 3], xp: 220, scale: 1.5, name: 'Carapace Hulk', loot: .6, faction: 'alien', pref: 2, melee: [45, 3.2, 1.6], bolt: 0xff7a2a },
  mutant: { blood: 0x4a8a2a, model: 'alien_mutant', gun: null, hp: 260, speed: 4, range: 30, dmg: 8, burst: 3, gap: [1.2, 2], xp: 90, scale: 1, name: 'Lab Mutant', loot: .3, faction: 'alien', pref: 12, bolt: 0x7dffb0 },
  swimmer: { blood: 0x1a6a7a, model: 'alien_swimmer', gun: null, hp: 160, speed: 5.6, range: 20, dmg: 7, burst: 2, gap: [1.3, 2.2], xp: 55, scale: .98, name: 'Drowned Swimmer', loot: .2, faction: 'alien', pref: 4, melee: [16, 2.2, .9], bolt: 0x3ae6ff },
  elite: { blood: 0x6a1a5a, model: 'alien_elite', gun: null, hp: 1500, speed: 4.3, range: 34, dmg: 12, burst: 4, gap: [1.4, 2.2], xp: 420, scale: 1.32, name: 'Spire Elite', loot: 1, faction: 'alien', pref: 6, melee: [55, 3.2, 1.3], bolt: 0xff3fb4 },
  // The Writhe (writhe_*.glb). ai: swarm | lurch | bladder | brute. Ichor is yellow-green.
  mite: { blood: 0xc8c030, model: 'writhe_mite', gun: null, hp: 14, speed: 7.2, range: 12, dmg: 0, burst: 0, gap: [9, 9], xp: 8, scale: 1, name: 'Writhe Mite', loot: .02, faction: 'writhe', ai: 'swarm',
    small: true, hitR: .34, cy: .3, radius: .3, leap: [10, 5.5, 1.2], pop: true },
  host: { blood: 0x9aa024, model: 'writhe_host', gun: null, hp: 200, speed: 3.3, range: 22, dmg: 5, burst: 3, gap: [1.8, 3.2], xp: 45, scale: 1, name: 'Writhe Host', loot: .12, faction: 'writhe', ai: 'lurch',
    melee: [24, 2.4, 1.1], aimErr: 2.8, armed: .45 },
  bladder: { blood: 0xb0c838, model: 'writhe_bladder', gun: null, hp: 170, speed: 1.9, range: 14, dmg: 0, burst: 0, gap: [9, 9], xp: 40, scale: 1, name: 'Writhe Bladder', loot: .1, faction: 'writhe', ai: 'bladder',
    hitR: .55, hitH: 1.75, cy: 1.0, radius: .6, blast: [4.6, 48], brood: [3, 5], pop: true },
  amalgam: { blood: 0x8a9020, model: 'writhe_amalgam', gun: null, hp: 2400, speed: 2.5, range: 26, dmg: 9, pellets: 5, burst: 1, gap: [3, 4.6], xp: 380, scale: 1.42, name: 'Writhe Amalgam', loot: .8, faction: 'writhe', ai: 'brute',
    hitR: .7, hitH: 2.75, cy: 1.5, radius: .85, melee: [55, 3.7, 1.9], bolt: 0xd8e040 },
};
const WRITHE = new Set(['mite', 'host', 'bladder', 'amalgam']);

// ---------------------------------------------------------------- organic materials (writhe_* / alien_*)
// The creature GLBs ship without images; the shared hx_* sets are applied here by material name, once per material.
const TEXSET = { writhe_skin: 'hx_skin', writhe_flesh: 'hx_flesh', writhe_sac: 'hx_sac', writhe_bone: 'hx_bone', writhe_plate: 'hx_chitin', writhe_rag: 'hx_rag',
  alien_skin: 'hx_flesh', alien_hide: 'hx_skin', alien_plate: 'hx_chitin', alien_bone: 'hx_bone', alien_sac: 'hx_sac' };
const TEX = {};
const WR = { uT: { value: 0 } };   // shared clock for the tentacle wriggle
function tex(file, color) {
  if (TEX[file]) return TEX[file];
  const t = new THREE.TextureLoader().load('assets/textures/' + file);
  t.flipY = false; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4;
  t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  return (TEX[file] = t);
}
function fleshify(av) {
  const glow = [];
  for (const m of av.allMats) {
    const set = TEXSET[m.name];
    if (set) {
      m.map = tex(set + '_c.jpg', true); m.normalMap = tex(set + '_n.jpg', false);
      m.roughnessMap = m.metalnessMap = tex(set + '_m.jpg', false);
      m.roughness = 1; m.metalness = 1; m.normalScale = new THREE.Vector2(1, -1); m.envMapIntensity = 1.3;
      m.color.setRGB(.82, .8, .78);   // vertex colours carry the hue; keep wet flesh from washing out under torches
    }
    if (/^(writhe|alien)_/.test(m.name)) {
      // tentacles and tendrils (`_writhe` vertex attribute) wriggle after skinning
      m.onBeforeCompile = sh => {
        sh.uniforms.uWrT = WR.uT;
        sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute float _writhe;\nuniform float uWrT;')
          .replace('#include <skinning_vertex>', `#include <skinning_vertex>
            { vec3 q = transformed * 6.0; float w = _writhe * _writhe;
              transformed += w * .045 * vec3(sin(uWrT * 3.1 + q.y * 1.7 + q.z), sin(uWrT * 2.6 + q.x * 1.3 + q.z * 1.9), sin(uWrT * 3.6 + q.x + q.y * 1.5)); }`);
      };
      m.customProgramCacheKey = () => 'writhe-flesh';
      m.needsUpdate = true;
    }
    if (/^(writhe_glow|alien_glow|alien_acid)$/.test(m.name) && m.emissive) glow.push({ m, base: m.emissiveIntensity || 1 });
  }
  return glow;
}

export class Enemy {
  constructor(game, type, pos, level, opts = {}) {
    this.g = game; this.type = type; this.T = TYPES[type]; this.level = level;
    this.side = 'enemy'; this.alive = true; this.pos = pos.clone(); this.home = pos.clone();
    this.vel = new THREE.Vector3(); this.yaw = Math.random() * 6.28;
    this.maxHp = this.hp = Math.round(this.T.hp * (1 + level * .12));
    this.dmgMul = 1 + level * .08;
    this.state = 'idle'; this.alertT = 0; this.fireT = 1 + Math.random() * 2; this.burstLeft = 0; this.burstT = 0;
    this.thinkT = Math.random() * .4; this.seen = false; this.strafe = Math.random() < .5 ? 1 : -1; this.strafeT = 0;
    this.deadT = 0; this.hitT = 9; this.onDeath = opts.onDeath || null; this.group = opts.group || null;
    this.radius = this.T.radius || (type === 'brute' ? .7 : type === 'generator' ? 1.3 : type === 'turret' ? .9 : .5 * (this.T.scale || 1));
    this.faction = this.T.faction || 'raider';
    this.seed = Math.random() * 100; this.lockT = 0; this.corpseLife = this.T.human ? 22 : 4;
    if (this.T.model) {
      this.av = new Avatar(game.assets, this.T.model);
      const gun = opts.gun !== undefined ? opts.gun : this.T.gun !== null ? this.T.gun : (this.T.armed && Math.random() < this.T.armed ? (Math.random() < .5 ? 'gun_pulse' : 'gun_auto') : null);
      if (gun) {
        // hosts hold their gun in the raised-arm Aim pose; solve the hand offset from that pose
        const idle = this.av.actions.Idle;
        if (this.av.actions.Aim) this.av.actions.Idle = this.av.actions.Aim;
        this.av.attachGun(gun, m => { if (m.material.name === 'gun_glow') { m.material.color.set('#ff3326'); m.material.emissive.set('#ff3326'); } if (m.material.name === 'gun_body') m.material.color.set(WRITHE.has(type) ? '#4a3a30' : '#2c2f36'); });
        this.av.actions.Idle = idle;
        this.armed = true;
      }
      for (const n of ['Attack', 'Jump']) { const a = this.av.actions[n]; if (a) { a.setLoop(THREE.LoopOnce); a.clampWhenFinished = true; } }
      if (/^(writhe|alien)_/.test(this.T.model)) this.glowMats = fleshify(this.av);
      this.av.play('Idle', 0);
      if (this.av.current) this.av.current.time = Math.random() * this.av.current.getClip().duration;
      this.obj = this.av.root;
    } else {
      const sub = { drone: 'PR_drone', turret: 'PR_turret', generator: 'PR_generator' }[type];
      this.obj = game.assets.clone('props_world', sub);
      this.head = this.obj.getObjectByName('turret_head');
      if (opts.police) {
        // city security drone: same airframe, white and blue livery, no loot
        this.police = true; this.T = { ...this.T, name: 'Security Drone', loot: 0 };
        this.obj.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); const m = o.material;
          if (m.emissive && m.emissive.r > .5 && m.emissive.b < .5) { m.color.set('#3aa0ff'); m.emissive.set('#3aa0ff'); }
          else if (m.name === 'enemy_plate') m.color.set('#d9dde2'); } });
      }
      this.muzzle = this.obj.getObjectByName('turret_muzzle');
      if (type === 'drone') { this.pos.y += 6 + Math.random() * 3; this.hover = this.pos.y - game.world.collision.ground(pos.x, pos.z); }
    }
    this.obj.position.copy(this.pos); this.obj.rotation.y = this.yaw;
    game.scene.add(this.obj);
    game.combat.targets.add(this);
    if (type === 'turret' || type === 'generator') {
      this.box = game.world.collision.add(new THREE.Box3().setFromCenterAndSize(
        _v.set(pos.x, pos.y + (type === 'generator' ? 1.4 : 1), pos.z), _d.set(type === 'generator' ? 2.2 : 1.6, type === 'generator' ? 2.8 : 2, type === 'generator' ? 2.2 : 1.6)), 'enemy');
    }
    // resident behaviour while idle (VANTHOS): sleep (lies where it fell, like a corpse, until something comes close or
    // makes noise), feed (hunched over remains), perch (on a ledge or rubble top, watching), patrol / roam (walks a
    // route; roaming packs share one), or the default wander around home
    this.beh = opts.beh || null; this.route = opts.route || null; this.pack = opts.pack || null; this.packOff = opts.packOff || null; this.ri = 0;
    if (this.beh === 'sleep' && this.av && this.av.actions.Death) {
      this.av.play('Death', 0); const a = this.av.actions.Death; a.time = a.getClip().duration - .02; this.av.update(0); a.paused = true;
    } else if (this.beh === 'sleep') this.beh = 'perch';
    if (opts.face !== undefined) this.yaw = opts.face;
    // a corpse rising as a host: play the death fall backwards
    if (opts.rise && this.av && this.av.actions.Death) {
      this.riseT = 1.7; this.av.play('Death', 0);
      const a = this.av.actions.Death; a.time = a.getClip().duration * .98; a.timeScale = -.75; a.paused = false;
      this.state = 'combat';
    }
  }

  center(out) {
    out.copy(this.pos);
    if (this.type === 'drone') return out;
    out.y += this.T.cy !== undefined ? this.T.cy : this.type === 'generator' ? 1.4 : this.type === 'turret' ? 1.2 : (this.type === 'brute' ? 1.2 : 1.0 * (this.T.scale || 1));
    return out;
  }

  hitTest(o, d, max) {
    let best = -1, crit = false;
    if (this.av && this.T.small) {
      const t = raySphere(o, d, this.center(_h), this.T.hitR); if (t >= 0 && t < max) best = t;
    } else if (this.av) {
      const s = this.T.scale;
      if (this.av.head) {
        this.av.head.getWorldPosition(_h); _h.y += .1 * s;
        const t = raySphere(o, d, _h, .17 * s);
        if (t >= 0 && t < max) { best = t; crit = true; }
      }
      const t2 = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + (this.T.hitH || 1.52 * s), this.T.hitR || .32 * s);
      if (t2 >= 0 && t2 < max && (best < 0 || t2 < best - .05)) { best = t2; crit = false; }
    } else if (this.type === 'drone') {
      const t = raySphere(o, d, this.pos, .75); if (t >= 0 && t < max) best = t;
      // the red eye is a weak point
      _h.set(Math.sin(this.yaw) * .5, 0, Math.cos(this.yaw) * .5).add(this.pos);
      const te = raySphere(o, d, _h, .22); if (te >= 0 && te < max && (best < 0 || te <= best + .1)) { best = te; crit = true; }
    } else if (this.type === 'turret') {
      const t = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + 1.9, .75); if (t >= 0 && t < max) best = t;
    } else {
      const t = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y, this.pos.y + 2.8, 1.1); if (t >= 0 && t < max) best = t;
      _h.set(this.pos.x, this.pos.y + 1.4, this.pos.z);
      const tc = raySphere(o, d, _h, .62); if (tc >= 0 && tc < max && tc <= best + .05) { best = tc; crit = true; }
    }
    return best >= 0 ? { dist: best, crit } : null;
  }

  // Boss hooks (operation.js): `immune` blocks all damage (the shield takes the hit), `hpFloor` stops the health at a
  // threshold once and calls `onFloor` (phase change), `vuln` multiplies damage taken (a staggered boss).
  takeDamage(dmg, crit, point, dir, side) {
    if (!this.alive) return { killed: false };
    if (this.immune) {
      this.hitT = 0; if (this.state === 'idle') this.alert();
      this.onImmuneHit && this.onImmuneHit(point, side);
      return { killed: false, immune: true, dealt: 0 };
    }
    dmg *= this.vuln || 1;
    this.hp -= dmg; this.hitT = 0;
    if (this.hpFloor && this.hp <= this.hpFloor) { this.hp = this.hpFloor; this.hpFloor = 0; this.onFloor && this.onFloor(this); }
    this.byRival = side === 'rival';
    if (dir) this.lastHit = { dir: dir.clone(), dmg };
    if (this.av && point) this.g.fx.blood(point, dir ? dir.clone().negate() : null, crit ? 1.4 : .8, this.T.blood);
    if (this.faction === 'writhe' && point && Math.random() < .3) this.g.audio.squelch && this.g.audio.squelch(point, .5);
    if (this.state === 'idle') this.alert();
    if (this.hp <= 0) { this.die(crit); return { killed: true, dealt: dmg }; }
    return { killed: false, dealt: dmg };
  }

  alert() {
    if (this.state !== 'idle') return;
    this.state = 'combat';
    if (this.beh === 'sleep' && this.av && this.av.actions.Death) {
      const a = this.av.actions.Death; a.paused = false; a.timeScale = -1.1; this.riseT = 1.25;
    }
    this.beh = null; this.pack = null;
    if (this.faction === 'writhe' && this.g.audio.shriek) { if (this.type !== 'mite') this.g.audio.shriek(this.pos, this.type === 'amalgam' ? .55 : this.type === 'bladder' ? .75 : 1); }
    else this.g.audio.alert(this.pos);
    this.g.music && (this.g.audio.combat = 1);
    // wake the squad
    if (this.group) for (const e of this.group) if (e !== this && e.alive && e.state === 'idle') { e.state = 'combat'; }
  }

  die(crit) {
    this.alive = false; this.state = 'dead'; this.deadT = 0;
    const g = this.g;
    g.combat.targets.delete(this);
    if (this.box) { g.world.collision.remove(this.box); this.box = null; }
    if (this.T.pop) {
      // soft-bodied: bursts instead of falling
      if (this.type === 'bladder') this.burst();
      else { const c = this.center(_v).clone(); this.gore(c, .55); g.audio.squelch && g.audio.squelch(c, .7); }
      this.obj.visible = false; this.corpseLife = .3;
    } else if (this.av) {
      const h = this.lastHit, imp = h ? h.dir.clone().setY(Math.max(.15, h.dir.y)).multiplyScalar(Math.min(9, 2.5 + h.dmg * .05)) : new THREE.Vector3(0, 1, 0);
      if (crit) imp.multiplyScalar(1.3);
      this.av.ragdoll(imp, (x, z) => this.g.world.collision.ground(x, z));
      this.g.fx.blood(this.center(_v).clone(), null, 2.2, this.T.blood);
      this.g.fx.bloodPool(this.pos.clone(), (this.T.scale || 1) * 1.1, this.T.blood);
      if (this.faction === 'writhe') { g.audio.squelch && g.audio.squelch(this.center(_v), 1); this.gore(this.center(_v).clone(), this.type === 'amalgam' ? 1.6 : .7); }
      // the parasite abandons a dead host: a mite crawls out of the chest
      if (this.type === 'host' && Math.random() < .35) g.enemies.later(.7, () => { const m = g.enemies.spawn('mite', this.pos.clone(), this.level, { extra: true }); m.state = 'combat'; });
    }
    if (this.type === 'drone' || this.type === 'turret' || this.type === 'generator') {
      const p = this.center(_v).clone();
      g.fx.explosion(p, this.type === 'generator' ? 8 : 3); g.audio.explosion(p);
      if (this.type === 'generator') g.combat.splash(p, 7, 60, 'world');
    }
    if (!this.byRival) g.onEnemyKilled(this, crit);          // rival-faction kills give the player nothing
    if (this.police && g.world.wanted) g.world.wanted.onPoliceKilled();
    if (!this.consumed) g.combat.drop(this.center(_v).clone(), this.type, this.level, this.T.loot);
    this.onDeath && this.onDeath(this);
  }

  // ichor and meat: the new fx.gore when available, plain blood otherwise
  gore(p, size) {
    const fx = this.g.fx;
    if (fx.gore) fx.gore(p, this.T.blood, size); else { fx.blood(p, null, 2 * size, this.T.blood); fx.bloodPool(p, size, this.T.blood); }
  }

  // bladder: the sac ruptures, scalding everything near, and the brood spills out
  burst() {
    const g = this.g, c = this.center(_v).clone(), [r, dmg] = this.T.blast;
    this.gore(c, 2.2);
    g.fx.glow(c, r * 1.3, 0xc8ff4a, .3); g.fx.flash(c, 0xb8ff40, 300, .3, r * 4);
    g.audio.squelch && g.audio.squelch(c, 2.2);
    const p = g.player, pd = _a.copy(p.pos).setY(p.pos.y + 1).distanceTo(c);
    if (pd < r && !p.dead) p.damage(dmg * (1 - pd / r * .6) * this.dmgMul * g.dmgScale(), c);
    for (const e of g.enemies.list) {
      if (!e.alive || e === this || e.faction === 'writhe' || e.type === 'generator') continue;
      const d = e.center(_a).distanceTo(c);
      if (d < r + e.radius) e.takeDamage(dmg * (1 - Math.min(1, d / r) * .6) * this.dmgMul, false, e.center(_a).clone(), _d.subVectors(e.pos, c).normalize(), 'rival');
    }
    const [n0, n1] = this.T.brood, n = n0 + Math.floor(Math.random() * (n1 - n0 + 1));
    for (let k = 0; k < n; k++) {
      const a = k / n * 6.28 + Math.random();
      const m = g.enemies.spawn('mite', this.pos.clone().add(_a.set(Math.cos(a) * .5, .3, Math.sin(a) * .5)), this.level, { extra: true });
      m.state = 'combat'; m.vel.set(Math.cos(a) * 4, 4 + Math.random() * 2, Math.sin(a) * 4); m.airT = m.airMax = .6;
    }
  }

  canSee(target) {
    _a.copy(this.pos); _a.y += this.type === 'drone' ? 0 : this.T.small ? .4 : 1.5;
    _h.copy(target); _h.y += 1.4;
    return this.g.world.collision.lineOfSight(_a, _h);
  }

  // Nearest hostile: the player, or (where factions fight) the closest enemy of another faction. The Writhe is at war
  // with everything everywhere, and every other faction turns on it when it is near.
  pickTarget() {
    const g = this.g, p = g.player;
    const writhe = this.faction === 'writhe';
    if (!g.world.factionWar && !writhe && !g.enemies.writheAlive) return p;
    if (this.rivalT > 0 && this.rival && this.rival.alive) return this.rivalProxy;
    let best = null, bd = 30 * 30;
    for (const e of g.enemies.list) {
      if (!e.alive || e.faction === this.faction || e.type === 'generator' || e.riseT > 0) continue;
      if (!g.world.factionWar && !writhe && e.faction !== 'writhe') continue;
      if (writhe && (e.police || (e.type === 'drone' && !this.armed && !this.T.bolt))) continue;
      const d = (e.pos.x - this.pos.x) ** 2 + (e.pos.z - this.pos.z) ** 2;
      if (d < bd) { bd = d; best = e; }
    }
    const pd = (p.pos.x - this.pos.x) ** 2 + (p.pos.z - this.pos.z) ** 2;
    if (!best || pd < bd * 1.4) { this.rival = null; return p; }
    this.rival = best; this.rivalT = 2;
    this.rivalProxy = { pos: best.pos, vel: best.vel, aiming: false, dead: false, rival: best,
      damage: d => best.takeDamage(d, false, null, null, 'rival') };
    if (this.state === 'idle') this.state = 'combat';
    return this.rivalProxy;
  }

  shoot(p) {
    const T = this.T;
    let from;
    if (this.av) from = this.av.muzzleWorld(_a).clone();
    else if (this.muzzle) from = this.muzzle.getWorldPosition(_a).clone();
    else from = this.pos.clone();
    const aim = _h.copy(p.pos); aim.y += 1.1;
    // lead slightly and add inaccuracy (better when the player is still); hosts barely aim at all
    aim.addScaledVector(p.vel, .25);
    const dist = from.distanceTo(aim);
    const err = (p.aiming ? .9 : 1.25) * (.6 + dist * .03) * (Math.hypot(p.vel.x, p.vel.z) > 4 ? 1.6 : 1) * (T.aimErr || 1);
    const n = T.pellets || 1;
    for (let k = 0; k < n; k++) {
      _d.copy(aim).add(_v.set((Math.random() - .5) * err, (Math.random() - .5) * err * .6, (Math.random() - .5) * err)).sub(from).normalize();
      this.g.combat.bolt(from, _d, this.type === 'brute' ? 34 : this.type === 'amalgam' ? 22 : 40, T.dmg * this.dmgMul * (p.rival ? 1 : this.g.dmgScale()), T.bolt || (this.type === 'brute' ? 0xff7a1a : 0xff3326), p.rival);
    }
    if (this.type === 'amalgam') { this.g.audio.shot('bile', from, true); this.g.fx.emit(from, 10, 3, 0xc8e040, .4, 6, .07); }
    else { this.g.audio.shot('bolt', from, true); this.g.fx.flash(from, 0xff4020, 15, .05, 6); }
  }

  // play a clip; one-shot clips restart when asked again, and `lock` holds them against the locomotion blend
  act(name, fade = .12, lock = 0, speed = 1) {
    const av = this.av, a = av.actions[name]; if (!a) return;
    if (av.current === a && (name === 'Attack' || name === 'Jump')) { a.reset(); a.timeScale = speed; a.play(); }
    else av.play(name, fade, speed);
    this.lockT = Math.max(this.lockT, lock);
  }

  locomote(hs, aim = false) {
    if (this.lockT > 0) return;
    if (hs > 4.5) this.av.play('Run', .2, hs / 7); else if (hs > .4) this.av.play('Walk', .2, Math.max(.6, hs / 3.4));
    else this.av.play(aim && this.av.actions.Aim ? 'Aim' : 'Idle', .25);
  }

  update(dt) {
    const g = this.g;
    this.rivalT = (this.rivalT || 0) - dt;
    this.lockT -= dt;
    if (this.alive && (this.thinkT <= dt || !this.tgt)) this.tgt = this.pickTarget();
    const p = this.tgt && (!this.tgt.rival || this.tgt.rival.alive) ? this.tgt : g.player;
    if (!this.alive) {
      this.deadT += dt;
      if (this.av && this.obj.visible) this.av.update(dt);
      else if (this.type === 'drone') { this.pos.y -= dt * 9; this.obj.rotation.z += dt * 4; this.obj.position.copy(this.pos); if (this.pos.y < g.world.collision.ground(this.pos.x, this.pos.z)) this.obj.visible = false; }
      else if (!this.av) this.obj.visible = this.deadT < .2 ? true : false;
      // a mite burrowing in makes the corpse convulse
      if (this.infestT > 0 && this.av && this.av.rag && this.av.rag.ok) {
        this.infestT -= dt;
        const rag = this.av.rag;
        if (Math.random() < dt * 8) { rag.asleep = false; rag.t = Math.min(rag.t, 3); for (const k of ['chest', 'head', 'handL', 'handR']) if (rag.prev[k]) rag.prev[k].add(_v.set((Math.random() - .5) * .06, -.05 * Math.random(), (Math.random() - .5) * .06)); }
      }
      return this.deadT < this.corpseLife;
    }
    if (this.glowMats) { const k = .6 + .4 * Math.sin(g.time * 3 + this.seed); for (const o of this.glowMats) o.m.emissiveIntensity = o.base * k; }
    this.hitT += dt;
    // staggered (a boss whose shield just broke): stands reeling, no attacks
    if (this.stunT > 0 && this.av) {
      this.stunT -= dt; this.lockT = 0;
      this.move(dt, 0, 0, 0, 4);
      this.av.play('Idle', .2, .45); this.av.aimPitch = -.35;
      this.av.update(dt);
      return true;
    }
    const dx = p.pos.x - this.pos.x, dz = p.pos.z - this.pos.z, dist = Math.hypot(dx, dz);
    this.thinkT -= dt;
    if (this.thinkT <= 0) {
      this.thinkT = .35 + Math.random() * .2;
      // how far a resident notices you depends on what it is doing (sleepers only when you are almost on them)
      const sense = this.state !== 'idle' ? 1 : this.beh === 'sleep' ? .22 : this.beh === 'feed' ? .6 : this.beh === 'perch' ? 1.25 : 1;
      const range = ((this.T.range || 0) + 14) * sense;
      this.seen = !p.dead && dist < range && this.type !== 'generator' && this.canSee(p.pos);
      if (this.seen && this.state === 'idle') this.alert();
      if (this.state === 'combat' && dist > 90) this.state = 'idle';
    }
    // getting up from the ground (a sleeper woken, a corpse the parasite took)
    if (this.riseT > 0 && this.av && !this.T.ai) {
      this.riseT -= dt; this.vel.set(0, 0, 0); this.move(dt, 0, 0, 0);
      if (this.riseT <= 0) { this.av.actions.Death.timeScale = 1; this.av.play('Idle', .3); }
      this.av.update(dt);
      return true;
    }
    // asleep: nothing moves (the pose is held), so nothing to update
    if (this.beh === 'sleep' && this.state === 'idle') return true;
    const facePlayer = () => { const t = Math.atan2(dx, dz); let d = t - this.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); this.yaw += d * Math.min(1, dt * 8); };
    if (this.type === 'generator') { this.obj.rotation.y += dt * .3; return true; }
    if (this.type === 'turret') {
      if (this.state === 'combat') { facePlayer(); if (this.head) this.head.rotation.y = this.yaw - this.obj.rotation.y; }
      this.fireLogic(dt, p, dist);
      return true;
    }
    if (this.type === 'drone') {
      const gy = g.world.collision.ground(this.pos.x, this.pos.z);
      let tx = 0, tz = 0;
      if (this.state === 'combat') {
        // orbit the player at ~14m
        const ang = Math.atan2(-dx, -dz) + this.strafe * dt * .6;
        const want = 14;
        tx = (p.pos.x + Math.sin(ang) * want - this.pos.x); tz = (p.pos.z + Math.cos(ang) * want - this.pos.z);
        facePlayer();
      } else { tx = this.home.x + Math.sin(g.time * .3 + this.home.z) * 8 - this.pos.x; tz = this.home.z + Math.cos(g.time * .3 + this.home.x) * 8 - this.pos.z; this.yaw += dt * .5; }
      const l = Math.hypot(tx, tz) || 1, sp = Math.min(this.T.speed, l);
      this.vel.x += (tx / l * sp - this.vel.x) * dt * 2; this.vel.z += (tz / l * sp - this.vel.z) * dt * 2;
      this.pos.x += this.vel.x * dt; this.pos.z += this.vel.z * dt;
      const ty = Math.max(gy + 5, (p.pos.y + 6)) + Math.sin(g.time * 2 + this.home.x) * .6;
      this.pos.y += (ty - this.pos.y) * dt * 1.5;
      this.obj.position.copy(this.pos); this.obj.rotation.set(this.vel.z * .03, this.yaw, -this.vel.x * .03);
      this.fireLogic(dt, p, dist);
      return true;
    }
    if (this.T.ai) return this.updateWrithe(dt, p, dist, dx, dz, facePlayer);
    // humanoids
    const T = this.T; let mx = 0, mz = 0, speed = T.speed, run = false;
    if (this.state === 'combat') {
      facePlayer();
      const fx = dx / (dist || 1), fz = dz / (dist || 1);
      const charge = (this.type === 'brute' && this.hp < this.maxHp * .5) || (!!T.melee && dist < 26);
      const pref = T.pref !== undefined ? T.pref : this.type === 'brute' ? (charge ? 1.5 : 7) : 16;
      this.strafeT -= dt; if (this.strafeT <= 0) { this.strafeT = 1.5 + Math.random() * 2; this.strafe = -this.strafe; }
      if (dist > pref + 4 || !this.seen) { mx = fx; mz = fz; run = dist > pref + 12 || charge; }
      else if (dist < pref - 4) { mx = -fx * .7; mz = -fz * .7; }
      mx += -fz * this.strafe * .6; mz += fx * this.strafe * .6;
      if (charge) {
        const [mdmg, reach, cd] = T.melee || [38, 2.2, 1.2];
        speed = T.melee ? T.speed * 1.5 : 7.5; run = true;
        if (dist < reach) { this.meleeT = (this.meleeT || 0) - dt; if (this.meleeT <= 0) { this.meleeT = cd; this.act('Attack', .08, .5); p.damage(mdmg * this.dmgMul * (p.rival ? 1 : g.dmgScale()), this.pos); g.fx.emit(_v.copy(p.pos).setY(p.pos.y + 1.2), 12, 5, T.bolt || 0xff7a1a, .3, 5); } }
      }
      else if (run) speed = T.speed * 1.8;
      if (this.seen) this.fireLogic(dt, p, dist);
    } else this.wander(dt);
    const ml = Math.hypot(mx, mz); if (ml > 1) { mx /= ml; mz /= ml; }
    if (this.state !== 'combat') { mx = this.wmx || 0; mz = this.wmz || 0; }
    this.move(dt, mx, mz, speed);
    this.locomote(Math.hypot(this.vel.x, this.vel.z));
    this.av.aimPitch = this.state === 'combat' ? Math.atan2(p.pos.y - this.pos.y, Math.max(1, dist)) * .8 : 0;
    // only animate skinned meshes that are near enough to matter
    this.av.update(dist < 120 ? dt : 0);
    return true;
  }

  // idle wander near home (sets the move direction in wmx/wmz)
  wander(dt, rad = 10, k = .5) {
    const b = this.beh;
    if (b === 'perch' || b === 'feed' || b === 'sleep') {
      this.wmx = 0; this.wmz = 0;
      if (b === 'perch') this.yaw += Math.sin(this.g.time * .4 + this.seed) * dt * .35;
      if (b === 'feed' && this.av && this.av.actions.Attack) {
        this.feedT = (this.feedT || Math.random() * 2) - dt;
        if (this.feedT <= 0) { this.feedT = 1.4 + Math.random() * 2.4; this.act('Attack', .2, 1.1, .55 + Math.random() * .3); if (Math.random() < .3 && this.g.audio.squelch) this.g.audio.squelch(this.pos, .35); }
      }
      return;
    }
    if ((b === 'patrol' || b === 'roam') && (this.route || this.pack)) {
      const P = this.pack, pts = P ? P.pts : this.route, i = P ? P.i : this.ri;
      let tx = pts[i % pts.length].x, tz = pts[i % pts.length].z;
      if (P && this.packOff) { tx += this.packOff.x; tz += this.packOff.z; }
      const wx = tx - this.pos.x, wz = tz - this.pos.z, wl = Math.hypot(wx, wz);
      if (wl < (P ? 5 : 2)) { if (P) { if (P.lead === this || !P.lead || !P.lead.alive) { P.lead = this; P.i++; } } else this.ri++; }
      const kk = b === 'roam' ? .42 : .3;
      this.wmx = wl > .5 ? wx / wl * kk : 0; this.wmz = wl > .5 ? wz / wl * kk : 0;
      if (wl > .5) { const t = Math.atan2(wx, wz); let d = t - this.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); this.yaw += d * Math.min(1, dt * 3); }
      return;
    }
    this.wanderT = (this.wanderT || 0) - dt;
    if (this.wanderT <= 0) { this.wanderT = 3 + Math.random() * 4; this.wx = this.home.x + (Math.random() - .5) * rad; this.wz = this.home.z + (Math.random() - .5) * rad; }
    const wx = this.wx - this.pos.x, wz = this.wz - this.pos.z, wl = Math.hypot(wx, wz);
    this.wmx = 0; this.wmz = 0;
    if (wl > 1) { this.wmx = wx / wl * k; this.wmz = wz / wl * k; const t = Math.atan2(wx, wz); let d = t - this.yaw; d = Math.atan2(Math.sin(d), Math.cos(d)); this.yaw += d * Math.min(1, dt * 4); }
  }

  move(dt, mx, mz, speed, accel = 8) {
    const T = this.T;
    this.vel.x += (mx * speed - this.vel.x) * Math.min(1, dt * accel); this.vel.z += (mz * speed - this.vel.z) * Math.min(1, dt * accel);
    this.vel.y -= 18 * dt;
    const r = this.g.world.collision.moveCapsule(this.pos, this.vel, T.small ? .25 : .4 * (T.scale || 1), T.small ? .5 : 1.8 * (T.scale || 1), dt);
    this.obj.position.copy(this.pos); this.obj.rotation.y = this.yaw;
    return r;
  }

  // ---------------------------------------------------------------- the Writhe
  updateWrithe(dt, p, dist, dx, dz, facePlayer) {
    const g = this.g, T = this.T;
    const fx = dx / (dist || 1), fz = dz / (dist || 1);
    let mx = 0, mz = 0, speed = T.speed;
    // a corpse getting back up
    if (this.riseT > 0) {
      this.riseT -= dt; this.vel.set(0, 0, 0); this.move(dt, 0, 0, 0);
      if (Math.random() < dt * 6) g.fx.blood(this.center(_v), null, .4, T.blood);
      if (this.riseT <= 0) { this.av.actions.Death.timeScale = 1; this.av.play('Idle', .3); g.audio.shriek && g.audio.shriek(this.pos, 1.1); }
      this.av.update(dt);
      return true;
    }
    const ai = T.ai;
    if (ai === 'swarm') return this.updateMite(dt, p, dist, fx, fz);
    if (this.state === 'combat') {
      facePlayer();
      if (ai === 'lurch') {
        // erratic: bursts of speed, sudden stops, a sideways weave, a lunge when close
        const t = g.time + this.seed;
        this.stopT = (this.stopT || 0) - dt;
        if (this.stopT < -2.5 - Math.random() * 3) this.stopT = .35 + Math.random() * .5;
        const surge = this.stopT > 0 ? .05 : .45 + .55 * Math.max(0, Math.sin(t * 2.3)) ** .5;
        const shoot = this.armed && this.seen && dist > 7 && dist < T.range + 4;
        if (dist > (shoot ? 12 : 1.6)) { mx = fx; mz = fz; }
        const wv = Math.sin(t * 1.7) * .7; mx += -fz * wv; mz += fx * wv;
        speed = T.speed * surge * (dist < 12 ? 1.6 : 1);
        this.lungeCd = (this.lungeCd || 0) - dt;
        if (this.lungeT > 0) { this.lungeT -= dt; speed = 8.5; mx = fx; mz = fz; }
        else if (dist < 6.5 && dist > 2 && this.lungeCd <= 0 && this.seen) { this.lungeT = .45; this.lungeCd = 3 + Math.random() * 2; this.act('Attack', .08, .8, 1.1); this.hitPending = .42; g.audio.shriek && g.audio.shriek(this.pos, 1.3); }
        const [mdmg, reach, cd] = T.melee;
        this.meleeT = (this.meleeT || 0) - dt;
        if (dist < reach && this.meleeT <= 0 && !(this.hitPending > 0)) { this.meleeT = cd; this.act('Attack', .08, .8, 1.2); this.hitPending = .38; }
        if (this.hitPending > 0) { this.hitPending -= dt; if (this.hitPending <= 0 && dist < reach + .8) this.strike(p, mdmg, 1); }
        if (shoot) this.fireLogic(dt, p, dist);
      } else if (ai === 'bladder') {
        // waddle in; close enough (or cornered) it swells and ruptures
        if (this.swellT > 0) { this.swellT -= dt; speed = 0; if (this.swellT <= 0) { this.byRival = true; this.consumed = true; this.hp = 0; this.die(false); return true; } }
        else if (dist < 3.4) { this.swellT = .9; this.act('Attack', .1, 2); g.audio.gurgle && g.audio.gurgle(this.pos); }
        else { mx = fx; mz = fz; }
        this.gurgleT = (this.gurgleT || 0) - dt; if (this.gurgleT <= 0) { this.gurgleT = 2.5 + Math.random() * 3; g.audio.gurgle && g.audio.gurgle(this.pos); }
      } else if (ai === 'brute') {
        // stomps in, charges the last stretch, slams; spits bile at range
        const [mdmg, reach, cd] = T.melee;
        if (dist > reach - .6) { mx = fx; mz = fz; }
        speed = dist < 16 ? T.speed * 2.5 : T.speed;
        this.meleeT = (this.meleeT || 0) - dt;
        if (dist < reach && this.meleeT <= 0) { this.meleeT = cd; this.act('Attack', .1, 1.1, .9); this.hitPending = .48; g.audio.roar && g.audio.roar(this.pos); }
        if (this.hitPending > 0) { this.hitPending -= dt; speed *= .3; if (this.hitPending <= 0) this.slam(p, mdmg, reach); }
        if (this.seen && dist > 9) this.fireLogic(dt, p, dist);
        this.roarT = (this.roarT || 4) - dt; if (this.roarT <= 0) { this.roarT = 6 + Math.random() * 6; g.audio.roar && g.audio.roar(this.pos); }
      }
    } else { this.wander(dt, ai === 'bladder' ? 5 : 10, ai === 'lurch' ? .35 : .4); mx = this.wmx; mz = this.wmz; }
    const ml = Math.hypot(mx, mz); if (ml > 1) { mx /= ml; mz /= ml; }
    this.move(dt, mx, mz, speed, ai === 'lurch' ? 5 : 8);
    if (this.alive) this.locomote(Math.hypot(this.vel.x, this.vel.z), this.armed && this.state === 'combat' && dist > 7);
    this.av.aimPitch = this.armed && this.state === 'combat' ? Math.atan2(p.pos.y - this.pos.y, Math.max(1, dist)) * .6 : 0;
    this.av.update(dist < 120 ? dt : 0);
    return true;
  }

  strike(p, dmg, k) {
    const g = this.g;
    p.damage(dmg * k * this.dmgMul * (p.rival ? 1 : g.dmgScale()), this.pos);
    g.fx.blood(_v.copy(p.pos).setY(p.pos.y + 1.2), null, .8, p.rival ? p.rival.T.blood : 0x6e0a0a);
    g.audio.squelch && g.audio.squelch(p.pos, .6);
  }

  // amalgam ground slam: everything in front within reach takes it
  slam(p, dmg, reach) {
    const g = this.g;
    _h.set(Math.sin(this.yaw) * 1.6, 0, Math.cos(this.yaw) * 1.6).add(this.pos);
    g.fx.emit(_v.copy(_h).setY(_h.y + .2), 26, 6, 0x8a7a66, .7, 9, .1, 1); g.fx.blood(_v, null, 1.2, this.T.blood);
    const pl = g.player;
    if (!pl.dead && pl.pos.distanceTo(_h) < reach) { pl.damage(dmg * this.dmgMul * g.dmgScale(), this.pos); pl.shake = Math.min(1, (pl.shake || 0) + .7); }
    for (const e of g.enemies.list) {
      if (!e.alive || e.faction === 'writhe' || e.type === 'generator') continue;
      if (e.pos.distanceTo(_h) < reach + e.radius) e.takeDamage(dmg * this.dmgMul, false, e.center(_a).clone(), _d.subVectors(e.pos, this.pos).normalize(), 'rival');
    }
  }

  // mites: skitter in a weaving swarm, leap at the target and burst on it; burrow into fresh corpses to raise hosts
  updateMite(dt, p, dist, fx, fz) {
    const g = this.g, T = this.T, E = g.enemies;
    let mx = 0, mz = 0, speed = T.speed;
    this.airT = (this.airT || 0) - dt;
    this.leapCd = (this.leapCd || 0) - dt;
    // look for a corpse when nothing living is close
    this.scanT = (this.scanT || Math.random() * .5) - dt;
    if (!this.corpse && this.scanT <= 0 && (this.state !== 'combat' || dist > 9)) {
      this.scanT = .5;
      const c = E.corpseNear(this.pos, this.state === 'combat' ? 16 : 24);
      if (c) { this.corpse = c; c.claimed = this; }
    }
    if (this.corpse && (this.corpse.deadT > this.corpse.corpseLife - 1.5 || this.corpse.claimed !== this)) this.corpse = null;
    if (this.corpse) {
      const c = this.corpse, cx = c.pos.x - this.pos.x, cz = c.pos.z - this.pos.z, cd = Math.hypot(cx, cz);
      if (this.burrowT > 0) {
        this.burrowT -= dt; this.vel.set(0, this.vel.y, 0);
        if (Math.random() < dt * 10) g.fx.blood(this.center(_v), null, .35, T.blood);
        this.obj.scale.setScalar(Math.max(.05, this.burrowT / 1.1));
        if (this.burrowT <= 0) { E.reanimate(c, this); return true; }
      } else if (cd < .9) {
        this.burrowT = 1.1; c.infestT = 2.2; c.corpseLife = Math.max(c.corpseLife, c.deadT + 4);
        this.act('Attack', .05, 1.2); g.audio.squelch && g.audio.squelch(this.pos, .8);
      } else { mx = cx / cd; mz = cz / cd; const t = Math.atan2(cx, cz); this.yaw += Math.atan2(Math.sin(t - this.yaw), Math.cos(t - this.yaw)) * Math.min(1, dt * 10); }
    } else if (this.state === 'combat') {
      const t = Math.atan2(fx, fz); this.yaw += Math.atan2(Math.sin(t - this.yaw), Math.cos(t - this.yaw)) * Math.min(1, dt * 10);
      if (this.airT <= 0) {
        const wv = Math.sin(g.time * 6 + this.seed) * .8;
        mx = fx - fz * wv; mz = fz + fx * wv;
        // keep apart from the rest of the swarm
        for (const o of E.list) if (o !== this && o.alive && o.type === 'mite') {
          const ox = this.pos.x - o.pos.x, oz = this.pos.z - o.pos.z, d2 = ox * ox + oz * oz;
          if (d2 < 1.4 && d2 > 1e-4) { const d = Math.sqrt(d2); mx += ox / d * (1.2 - d); mz += oz / d * (1.2 - d); }
        }
        const [ldmg, lrange] = T.leap;
        if (dist < lrange && dist > 1.2 && this.leapCd <= 0 && this.grounded && this.seen) {
          const fl = .42 + dist * .02;
          this.vel.set(fx * dist / fl, 5.2, fz * dist / fl); this.airT = this.airMax = fl + .2; this.leapCd = T.leap[2] + Math.random() * .6; this.leaping = true;
          this.act('Jump', .05, fl); g.audio.chitter && g.audio.chitter(this.pos, 1.4);
        }
      }
      // contact while leaping: bite and burst on the victim
      if (this.leaping) {
        _h.copy(p.pos); _h.y += .9;
        if (this.center(_v).distanceTo(_h) < 1.05) {
          this.leaping = false; p.damage(T.leap[0] * this.dmgMul * (p.rival ? 1 : g.dmgScale()), this.pos);
          this.byRival = true; this.consumed = true; this.hp = 0; this.die(false); return true;
        }
      }
      this.chitT = (this.chitT || Math.random() * 2) - dt; if (this.chitT <= 0) { this.chitT = 1.5 + Math.random() * 2.5; if (dist < 30) g.audio.chitter && g.audio.chitter(this.pos, 1); }
    } else { this.wander(dt, 6, .3); mx = this.wmx; mz = this.wmz; speed = 2.5; }
    const ml = Math.hypot(mx, mz); if (ml > 1) { mx /= ml; mz /= ml; }
    if (this.airT > 0) {
      this.vel.y -= 12 * dt; const r = g.world.collision.moveCapsule(this.pos, this.vel, .25, .5, dt); this.obj.position.copy(this.pos); this.obj.rotation.y = this.yaw;
      // landed: stop sliding at leap speed
      if (r.grounded && (this.airMax || .6) - this.airT > .15) { this.airT = 0; this.vel.x *= .3; this.vel.z *= .3; this.leaping = false; this.grounded = true; }
    }
    else { const r = this.move(dt, mx, mz, speed, 10); this.grounded = r.grounded; this.leaping = false; }
    if (this.lockT <= 0 && this.airT <= 0) { const hs = Math.hypot(this.vel.x, this.vel.z); this.av.play(hs > .5 ? 'Run' : 'Idle', .12, hs > .5 ? Math.max(.6, hs / 6) : 1); }
    this.av.update(dist < 90 ? dt : 0);
    return true;
  }

  fireLogic(dt, p, dist) {
    if (!this.seen || p.dead || dist > (this.T.range || 30) + 6) return;
    this.fireT -= dt;
    if (this.burstLeft > 0) {
      this.burstT -= dt;
      if (this.burstT <= 0) { this.shoot(p); this.burstLeft--; this.burstT = .14; }
    } else if (this.fireT <= 0) {
      this.burstLeft = this.T.burst; this.burstT = 0;
      this.fireT = this.T.gap[0] + Math.random() * (this.T.gap[1] - this.T.gap[0]);
    }
  }

  dispose() {
    this.g.combat.targets.delete(this);
    if (this.box) this.g.world.collision.remove(this.box);
    // skinned enemies free their bone textures and cloned materials (an operation spawns dozens per run)
    if (this.av && this.av.dispose) this.av.dispose(); else this.obj.removeFromParent();
  }
}

export class EnemyManager {
  constructor(game) { this.g = game; this.list = []; this.timers = []; this.writheAlive = 0; }
  spawn(type, pos, level, opts) { const e = new Enemy(this.g, type, pos, level, opts); if (opts && opts.extra) e.extra = true; this.list.push(e); return e; }

  later(t, fn) { this.timers.push({ t, fn }); }

  // fresh human dead (troopers, brutes) the Writhe can still use
  corpseNear(pos, r) {
    let best = null, bd = r * r;
    for (const e of this.list) {
      if (e.alive || !e.T.human || !e.av || e.claimed || e.deadT > e.corpseLife - 3 || e.reanimated) continue;
      const d = (e.pos.x - pos.x) ** 2 + (e.pos.z - pos.z) ** 2;
      if (d < bd) { bd = d; best = e; }
    }
    return best;
  }

  // a mite has burrowed into a corpse: the body is taken and rises as a host (raiders keep their gun)
  reanimate(corpse, mite) {
    const g = this.g;
    mite.byRival = true; mite.consumed = true; mite.alive = false; mite.state = 'dead'; mite.obj.visible = false; mite.corpseLife = 0;
    g.combat.targets.delete(mite);
    mite.onDeath && mite.onDeath(mite);
    corpse.reanimated = true; corpse.corpseLife = 0;
    // stand up where the ragdoll's pelvis lies
    const at = corpse.pos.clone();
    if (corpse.av && corpse.av.bones.hips) { corpse.av.bones.hips.getWorldPosition(_v); at.x = _v.x; at.z = _v.z; }
    at.y = g.world.collision.ground(at.x, at.z);
    const h = this.spawn('host', at, Math.max(corpse.level, mite.level), { rise: true, extra: true, gun: corpse.T.gun || null });
    h.yaw = Math.random() * 6.28;
    g.fx.blood(h.center(_v), null, 1.6, h.T.blood);
    g.audio.squelch && g.audio.squelch(at, 1.4);
    if (g.hud && g.hud.feed && at.distanceTo(g.player.pos) < 60) g.hud.feed('A corpse rises', '#c8ff4a');
    return h;
  }

  // a loud sound (a gunshot, an explosion): idle creatures within r come to look; sleepers only when it is close
  noise(pos, r) {
    for (const e of this.list) {
      if (!e.alive || e.state !== 'idle') continue;
      const k = e.beh === 'sleep' ? .45 : e.beh === 'feed' ? .75 : 1;
      if ((e.pos.x - pos.x) ** 2 + (e.pos.z - pos.z) ** 2 < (r * k) ** 2) e.alert();
    }
  }

  update(dt) {
    WR.uT.value += dt;
    for (let i = this.timers.length - 1; i >= 0; i--) { const t = this.timers[i]; t.t -= dt; if (t.t <= 0) { this.timers.splice(i, 1); t.fn(); } }
    let combat = 0, wr = 0;
    const pp = this.g.player.pos;
    this.frame = (this.frame || 0) + 1; this.asleep = 0;
    for (let i = this.list.length - 1; i >= 0; i--) {
      const e = this.list[i];
      const md = Math.abs(e.pos.x - pp.x) + Math.abs(e.pos.z - pp.z);
      // stray spawns (brood, risen hosts) are dropped once the player has left them far behind
      if (e.extra && e.alive && e.state !== 'combat' && md > 260) { e.dispose(); this.list.splice(i, 1); continue; }
      // idle creatures far away cost almost nothing: beyond ~250 m they are frozen and hidden (the fog hides them
      // anyway), beyond ~95 m they think and move four times less often (their animation is not advanced)
      if (e.alive && e.state === 'idle' && !(e.riseT > 0)) {
        if (md > 250) { if (e.obj.visible) e.obj.visible = false; e.skipDt = 0; this.asleep++; if (e.faction === 'writhe') wr++; continue; }
        if (!e.obj.visible && !e.hidden) e.obj.visible = true;
        if (md > 95) {
          e.skipDt = (e.skipDt || 0) + dt;
          if ((this.frame + (e.seed | 0)) % 4) { this.asleep++; if (e.faction === 'writhe') wr++; continue; }
          const d2 = Math.min(.25, e.skipDt); e.skipDt = 0;
          if (!e.update(d2)) { e.dispose(); this.list.splice(i, 1); }
          if (e.faction === 'writhe') wr++;
          continue;
        }
      } else if (e.alive && !e.obj.visible && !e.hidden && !e.T.pop) e.obj.visible = true;
      if (!e.update(dt)) { e.dispose(); this.list.splice(i, 1); continue; }
      if (e.alive && e.state === 'combat') combat++;
      if (e.alive && e.faction === 'writhe') wr++;
    }
    this.combatCount = combat; this.writheAlive = wr;
  }
  clear() { this.list.forEach(e => e.dispose()); this.list = []; this.timers = []; this.writheAlive = 0; }
  removeWhere(fn) { for (let i = this.list.length - 1; i >= 0; i--) if (fn(this.list[i])) { this.list[i].dispose(); this.list.splice(i, 1); } }
}

export { TYPES as ENEMY_TYPES };
