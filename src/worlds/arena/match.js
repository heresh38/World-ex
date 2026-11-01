// Shellbreak match rules: two squads of ghost-shells, first to the score limit (or ahead when the clock runs out).
// Owns the combatants (the player as a proxy + BotManager bots), eliminations / assists / streaks, the elimination feed,
// respawns at squad spawns chosen away from enemy sight lines with brief spawn protection, the end of the match and its
// rewards (XP, credits, a rolled weapon through state.js rollWeapon -> Game.addWeapon) and the saved service record.
import * as THREE from 'three';
import { BotManager, SHELL, NAMES, DIFFICULTY } from '../../game/bots.js';
import { rollWeapon, rollRarity, arenaRecord } from '../../game/state.js';

export const RESPAWN_BOT = 3.5, RESPAWN_PLAYER = 4.5, PROTECT = 2.0;
export const MODE_NAME = 'Shellbreak';
const ROLE_ORDER = ['rifleman', 'cqb', 'marksman', 'rifleman', 'support', 'cqb', 'sidearm', 'rifleman'];
const LANE_ORDER = ['mid', 'west', 'east', 'mid', 'west_alley', 'east_alley', 'west', 'east'];
const _v = new THREE.Vector3(), _a = new THREE.Vector3();

// the player seen as a combatant by the bots and the scoreboard
class PlayerC {
  constructor(g, team, name) {
    this.g = g; this.isPlayer = true; this.team = team; this.name = name; this.deployed = false;
    this.stats = { elims: 0, deaths: 0, assists: 0, score: 0, streak: 0, best: 0, dmg: 0 };
    this.protectT = 0; this.assist = new Map(); this.lastShotT = -99; this.ally = true;
  }
  get alive() { return this.deployed && !this.g.player.dead; }
  get pos() { return this.g.player.pos; }
  get vel() { return this.g.player.vel; }
  center(out) { const p = this.g.player; return out.set(p.pos.x, p.pos.y + (p.crouch ? .72 : 1.1), p.pos.z); }
  head(out) { const p = this.g.player; return out.set(p.pos.x, p.pos.y + (p.crouch ? .98 : 1.62), p.pos.z); }
  eye(out) { return this.g.camera.getWorldPosition(out); }
}

export class Match {
  constructor(world, cfg) {
    this.w = world; this.g = world.g; this.cfg = cfg;
    this.playerTeam = cfg.team || (Math.random() < .5 ? 'a' : 'b');
    this.enemyTeam = this.playerTeam === 'a' ? 'b' : 'a';
    this.score = { a: 0, b: 0 }; this.timeLeft = cfg.minutes * 60; this.state = 'loadout'; this.t = 0;
    this.feed = []; this.queue = []; this.recent = new Map();
    this.player = new PlayerC(this.g, this.playerTeam, cfg.callsign || 'You');
    this.mgr = new BotManager(this.g, world, { difficulty: cfg.difficulty, playerTeam: this.playerTeam, player: this.player,
      onDeath: (b, k, wpn, crit) => this.onKill(b, k, wpn, crit) });
    const names = [...NAMES].sort(() => Math.random() - .5);
    const mk = (team, i, wing) => this.mgr.add({ team, name: names.pop(), sex: (i + (team === 'a' ? 0 : 1)) % 2 ? 'female' : 'male', role: ROLE_ORDER[i % ROLE_ORDER.length],
      lane: LANE_ORDER[(i + (team === this.playerTeam ? 1 : 0)) % LANE_ORDER.length], wing, seed: 1000 + i * 7 + (team === 'a' ? 0 : 500) });
    // allies: squad size - 1 (the player fills the last seat); touch: never more than 11 bots in all
    const per = Math.max(1, Math.min(6, cfg.size | 0));
    for (let i = 0; i < per - 1; i++) mk(this.playerTeam, i, i < 2 && per >= 4);
    for (let i = 0; i < per; i++) mk(this.enemyTeam, i, false);
    if (this.g.touch) while (this.mgr.bots.length > 11) { const b = this.mgr.bots.pop(); b.av.dispose(); }
    this.all = [this.player, ...this.mgr.bots];
  }

  get bots() { return this.mgr.bots; }
  combatants(team) { return this.all.filter(c => c.team === team); }

  // ---------------------------------------------------------------- spawning
  // Score every squad spawn: far from living enemies, never in an enemy's sight line, near squadmates, not just used.
  pickSpawn(team) {
    const map = this.w.map, pts = map.spawns[team];
    const enemies = this.all.filter(c => c.team !== team && c.alive), mates = this.all.filter(c => c.team === team && c.alive);
    let best = pts[0], bs = -1e9;
    for (const p of pts) {
      _v.set(p[0], p[1] + 1.6, p[2]);
      let s = Math.random() * 5, minD = 1e9;
      for (const e of enemies) {
        const d = e.pos.distanceTo(_v); minD = Math.min(minD, d);
        if (d < 55 && this.mgr.los(e.center(_a).setY(e.pos.y + 1.6), _v)) s -= 120;
        if (d < 12) s -= 60;
      }
      s += Math.min(minD, 45);
      for (const m of mates) if (m.pos.distanceTo(_v) < 14) s += 4;
      const used = this.recent.get(p); if (used && this.t - used < 4) s -= 25;
      if (s > bs) { bs = s; best = p; }
    }
    this.recent.set(best, this.t);
    // a little scatter so two respawns at one point do not stack
    const jx = (Math.random() - .5) * 1.2, jz = (Math.random() - .5) * 1.2;
    return { pos: new THREE.Vector3(best[0] + jx, best[1], best[2] + jz), yaw: best[3] };
  }

  spawnBot(b) { const s = this.pickSpawn(b.team); b.spawnAt(s.pos, s.yaw); }

  spawnPlayer() {
    const g = this.g, s = this.pickSpawn(this.playerTeam);
    g.player.spawn(s.pos, s.yaw);
    g.player.camYaw = s.yaw + Math.PI; g.player.camPitch = -.05;
    g.weapons.refill(); g.weapons.refreshModel(); g.weapons.select && g.weapons.slot !== 0 && g.weapons.equipped(0) && g.weapons.select(0);
    this.player.deployed = true; this.player.protectT = PROTECT; this.player.assist = new Map();
    this.w.lastAttacker = null;
  }

  // ---------------------------------------------------------------- flow
  start() {
    this.state = 'live'; this.t = 0;
    for (const b of this.bots) this.spawnBot(b);
    this.spawnPlayer();
    this.g.hud.banner(MODE_NAME, 'First squad to ' + this.cfg.limit + ' eliminations', 3);
    this.g.audio.ui && this.g.audio.ui('confirm');
  }

  restart() {
    this.score = { a: 0, b: 0 }; this.timeLeft = this.cfg.minutes * 60; this.feed = []; this.queue = []; this.result = null;
    for (const c of this.all) { c.stats = { elims: 0, deaths: 0, assists: 0, score: 0, streak: 0, best: 0, dmg: 0 }; }
    for (const b of this.bots) { if (b.alive) { b.alive = false; this.g.combat.targets.delete(b); } }
    this.mgr.clearShots();
    this.start();
  }

  update(dt) {
    if (this.state !== 'live') {
      // after the end the bodies settle; nothing thinks
      if (this.state === 'over') for (const b of this.bots) if (b.av.rag && b.av.root.visible) b.av.update(dt);
      return;
    }
    this.t += dt;
    this.timeLeft -= dt;
    this.player.protectT -= dt;
    if (this.player.protectT > 0 && this.g.weapons.lastFire < .05) this.player.protectT = 0;    // firing ends protection
    this.mgr.update(dt);
    // respawns
    for (let i = this.queue.length - 1; i >= 0; i--) {
      const q = this.queue[i]; q.t -= dt;
      if (q.t > 0) continue;
      if (q.c.isPlayer) { if (this.w.ui && this.w.ui.modal) continue; this.spawnPlayer(); }
      else this.spawnBot(q.c);
      this.queue.splice(i, 1);
    }
    if (this.timeLeft <= 0) this.end('time');
  }

  respawnIn(c) { const q = this.queue.find(x => x.c === c); return q ? Math.max(0, q.t) : 0; }

  // ---------------------------------------------------------------- eliminations
  onKill(victim, killer, weapon, crit) {
    if (this.state !== 'live') return;
    victim.stats.deaths++; victim.stats.streak = 0;
    const valid = killer && killer !== victim && killer.team !== victim.team;
    if (valid) {
      killer.stats.elims++; killer.stats.streak++; killer.stats.best = Math.max(killer.stats.best, killer.stats.streak);
      killer.stats.score += 100 + (crit ? 25 : 0);
      this.score[killer.team]++;
    }
    // assists: everyone else on the other squad who dealt a real share of the damage
    for (const [c, d] of victim.assist || []) {
      if (c === killer || c.team === victim.team || d < 40) continue;
      c.stats.assists++; c.stats.score += 50;
      if (c.isPlayer) this.w.ui && this.w.ui.assist(victim);
    }
    victim.assist = new Map();
    this.feed.push({ k: valid ? killer : null, v: victim, weapon: weapon || '', crit: !!crit, t: this.t });
    if (this.feed.length > 6) this.feed.shift();
    this.w.ui && this.w.ui.onFeed();
    if (valid && killer.isPlayer) this.w.ui && this.w.ui.confirm(victim, crit);
    this.queue.push({ c: victim, t: victim.isPlayer ? RESPAWN_PLAYER : RESPAWN_BOT });
    if (this.score[this.playerTeam] >= this.cfg.limit || this.score[this.enemyTeam] >= this.cfg.limit) this.end('score');
  }

  onPlayerDied() {
    const la = this.w.lastAttacker;
    const k = la && this.t - la.t < 6 ? la : null;
    this.killedBy = k ? { name: k.c.name, weapon: k.weapon } : null;
    this.onKill(this.player, k ? k.c : null, k ? k.weapon : '', k ? k.crit : false);
  }

  // ---------------------------------------------------------------- end + rewards
  end(reason) {
    if (this.state === 'over') return;
    this.state = 'over'; this.reason = reason;
    const g = this.g, s = g.save, me = this.player.stats;
    const us = this.score[this.playerTeam], them = this.score[this.enemyTeam];
    const outcome = us > them ? 'win' : us < them ? 'loss' : 'draw';
    // rewards: XP and credits for the match, a weapon rolled by the shared loot system (better odds for a win)
    const xp = 400 + me.elims * 60 + me.assists * 25 + (outcome === 'win' ? 600 : outcome === 'draw' ? 300 : 150);
    const credits = 150 + me.elims * 18 + me.assists * 6 + (outcome === 'win' ? 350 : 120);
    const power = Math.max(1, g.power() + Math.round((Math.random() - .25) * 6) + (outcome === 'win' ? 2 : 0));
    const w = rollWeapon(power, { rarity: rollRarity(outcome === 'win' ? .14 + Math.min(.1, me.elims * .006) : .04), source: MODE_NAME });
    g.gain('xp', xp); g.gain('credits', credits, false); g.addWeapon(w);
    // service record
    const A = s.arena = arenaRecord(s.arena);
    A.matches++; A[outcome === 'win' ? 'wins' : outcome === 'loss' ? 'losses' : 'draws']++;
    A.elims += me.elims; A.deaths += me.deaths; A.assists += me.assists; A.time += this.t;
    A.bestElims = Math.max(A.bestElims, me.elims); A.bestStreak = Math.max(A.bestStreak, me.best);
    s.stats.kills += me.elims;
    s.stats.bestStreak = Math.max(s.stats.bestStreak || 0, me.best);
    g.persist();
    this.result = { outcome, us, them, xp, credits, weapon: w, reason, stats: { ...me }, time: this.t };
    this.mgr.clearShots();
    this.w.onMatchEnd && this.w.onMatchEnd(this.result);
  }

  // scoreboard rows, best first
  table(team) {
    return this.combatants(team).map(c => ({ name: c.name, me: !!c.isPlayer, alive: c.alive, ...c.stats }))
      .sort((a, b) => b.score - a.score || b.elims - a.elims || a.deaths - b.deaths);
  }

  dispose() { this.mgr.dispose(); }
}

export { SHELL, DIFFICULTY };
