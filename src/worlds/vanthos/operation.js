// Operation Heartline: VANTHOS played as a linear, replayable mission. Land on the southern highway, wake a relay,
// recover a flight recorder, burn a Writhe nest, power the Spire lift and break the Spire Warden on the foundation.
// Every visit starts a fresh run (save.vanthos.runs / best); a trip down the metro keeps the current stage.
//
// Each stage: a waypoint + HUD objective with distance, an arrival beat over the radio (HUD subtitles), scripted
// waves (not distance streaming) and an interaction (hold an uplink, pull a recorder, open a gas main, power a lift).
// The boss fight: at 50 % the Warden is shielded (immune) until its three shield conduits are destroyed while adds
// pour in; the shield breaks, it staggers; a shorter second shield phase (two conduits) comes at 20 %. Its reliquary
// grants 2-3 rolled weapons (any class, weighted rarity, perks, stat rolls and a random compatible sight).
import * as THREE from 'three';
import { rayCyl } from '../../game/combat.js';
import { rollWeapon, pickWeighted } from '../../game/state.js';
import { ARCHETYPES, RARITY, PERKS, SIGHTS, weaponSight } from '../../game/data.js';

const V = THREE.Vector3, DEG = Math.PI / 180;
const _a = new V(), _b = new V(), _c = new V();
const polar = (deg, r) => new V(Math.cos(deg * DEG) * r, 0, Math.sin(deg * DEG) * r);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export const fmtTime = t => t == null ? '—' : Math.floor(t / 60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');

export const OP_NAME = 'Operation Heartline';
const WREN = ['Wren Asheby · Wayfarer', '#1ad8ff'], REC = ['Flight Nine · recorder', '#ffae2f'], WARDEN = ['The Spire Warden', '#ff5ac8'];
const BOSS = 'The Spire Warden';
const FOUND_Y = 29;            // top of the Spire foundation cap

const STAGES = [
  { id: 'relay', title: 'The Relay', place: 'The Outskirts' },
  { id: 'shuttle', title: 'Flight Nine', place: 'Commercial District' },
  { id: 'nest', title: 'The Brood Road', place: 'The Crown' },
  { id: 'lift', title: 'The Spire Lift', place: 'The Crater' },
  { id: 'warden', title: BOSS, place: 'Spire foundation' },
];

// optional terminal logs (E: read), one per stage
const LOGS = {
  relay: { title: 'Raider log · day 41', html: '<p>The mast still hears the ships in orbit. Brakk wants to sell the frequencies to whoever pays.</p><p>I say we keep listening. Somebody is coming back for this city. Somebody always does.</p>' },
  shuttle: { title: 'Passenger manifest · Flight 9', html: '<p>Evacuation priority B. 212 seats, 212 boarded.</p><p><i>Row 14 · seat C · ASHEBY, TOBIN · status: BOARDED</i></p>', wren: 'Fourteen C... that was Tobin. My brother. Keep moving, Captain. Please.' },
  nest: { title: 'Heating authority notice', html: '<p>Crown Main 6: pressure fault on the district heating line. Isolate before any work.</p><p>Do not ignite. Do not ignite. Do not —</p><p><i>(the rest of the screen is scorched)</i></p>' },
  lift: { title: 'Spire maintenance · night shift', html: '<p>Core output exceeds city draw by 340 %. Where is the power going?</p><p>Crew on the foundation report a sound like breathing. Lift held at the top until further notice.</p>' },
};

// ---------------------------------------------------------------- shield conduit: a shootable pylon (combat target)
class Conduit {
  constructor(op, p, k) {
    const g = op.g;
    this.op = op; this.g = g; this.k = k; this.side = 'enemy'; this.type = 'conduit'; this.alive = false; this.state = 'dormant';
    this.pos = p.clone(); this.radius = 1.2; this.T = { name: 'Shield Conduit' }; this.barY = 3.3; this.barColor = '#ff3fb4';
    this.hp = this.maxHp = 1; this.hitT = 99; this.flash = 0;
    this.obj = g.assets.clone('vanthos', 'VX_conduit'); this.obj.position.copy(p); this.obj.rotation.y = k * 1.3;
    this.mats = [];
    this.obj.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true;
      if (o.material.name === 'conduit_glow') { o.material = o.material.clone(); this.mats.push(o.material); } } });
    op.w.scene.add(this.obj);
    op.w.collision.add([p.x - .8, p.y, p.z - .8, p.x + .8, p.y + 5.4, p.z + .8], 'conduit');
    this.emitter = new V(p.x, p.y + 5.45, p.z);
    this.set('dormant');
  }
  set(s) {
    this.state = s;
    for (const m of this.mats) {
      if (s === 'dead') { m.emissive.set(0x220818); m.color.set(0x2a1a22); m.emissiveIntensity = 1; }
      else { m.emissive.set(0xff3fb4); m.color.set(0xff3fb4); m.emissiveIntensity = s === 'active' ? 3 : .25; }
    }
  }
  activate(hp) {
    this.hp = this.maxHp = hp; this.alive = true; this.hitT = 0; this.set('active');
    this.g.combat.targets.add(this);
    this.g.fx.glow(this.emitter, 6, 0xff3fb4, .5); this.g.fx.emit(this.emitter, 30, 5, 0xff3fb4, .6, 2, .08);
  }
  center(out) { return out.set(this.pos.x, this.pos.y + 2.9, this.pos.z); }
  hitTest(o, d, max) { const t = rayCyl(o, d, this.pos.x, this.pos.z, this.pos.y + .2, this.pos.y + 5.8, 1.2); return t >= 0 && t < max ? { dist: t, crit: false } : null; }
  takeDamage(dmg, crit, point, dir, side) {
    if (!this.alive || side === 'rival') return { killed: false };
    this.hp -= dmg; this.hitT = 0; this.flash = 1;
    if (point) this.g.fx.emit(point, 5, 4, 0xff6ad0, .3, 4, .05, .8);
    if (this.hp <= 0) { this.destroy(); return { killed: true, dealt: dmg }; }
    return { killed: false, dealt: dmg };
  }
  destroy() {
    const g = this.g;
    this.alive = false; this.hp = 0; g.combat.targets.delete(this); this.set('dead');
    const c = this.center(_a).clone();
    g.fx.explosion(c, 5); g.fx.emit(this.emitter, 60, 9, 0xff3fb4, .9, 4, .1); g.audio.explosion(c);
    const pd = c.distanceTo(g.player.pos); if (pd < 30) g.player.shake = Math.min(1, (g.player.shake || 0) + (1 - pd / 30) * .8);
    this.op.onConduitDown(this);
  }
  update(dt, t) {
    this.hitT += dt; this.flash = Math.max(0, this.flash - dt * 5);
    if (this.state !== 'active') return;
    const k = 2.2 + Math.sin(t * 7 + this.k) * .8 + this.flash * 5;
    for (const m of this.mats) m.emissiveIntensity = k;
  }
  dispose() { this.g.combat.targets.delete(this); }
}

// ---------------------------------------------------------------- VFX: the Warden's barrier and the conduit tethers
function shieldMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { uT: { value: 0 }, uHit: { value: 0 }, uA: { value: 0 }, uColor: { value: new THREE.Color(0xff3fb4) } },
    vertexShader: `varying vec3 vN; varying vec3 vV; varying vec3 vP;
      void main(){ vec4 wp = modelMatrix * vec4(position, 1.); vP = position; vN = normalize(mat3(modelMatrix) * normal);
        vV = normalize(cameraPosition - wp.xyz); gl_Position = projectionMatrix * viewMatrix * wp; }`,
    fragmentShader: `uniform float uT, uHit, uA; uniform vec3 uColor; varying vec3 vN, vV, vP;
      void main(){
        float f = pow(1. - abs(dot(normalize(vN), normalize(vV))), 2.4);
        vec3 p = vP * 5.5;
        float cell = abs(sin(p.x + uT * .7) * sin(p.y * 1.2 - uT * .9) * sin(p.z + uT * .5));
        float lines = smoothstep(.82, 1., 1. - cell);
        float band = smoothstep(.75, 1., sin(vP.y * 7. - uT * 3.5) * .5 + .5);
        float a = clamp((f * .95 + lines * .28 + band * .18 + uHit * (.35 + f)) * uA, 0., 1.);
        gl_FragColor = vec4(uColor * (1.6 + uHit * 2.5), a); }`,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, toneMapped: false,
  });
}

export class Operation {
  constructor(w) {
    this.w = w; this.g = w.g;
    this.i = 0; this.phase = 'travel'; this.clock = 0; this.now = 0; this.intro = false; this.complete = false;   // clock: run time; now: timers
    this.waves = []; this.timers = []; this.cp = null; this.liftReady = false;
    this.conduits = []; this.boss = null; this.adds = [];
    this.hold = { p: 0, inside: true }; this.said = new Set();
    // returning from the metro: carry on with the stage you were on
    const g = this.g;
    this.resumed = g.metroReturn && g.opResume ? g.opResume : null;
    g.opResume = null;
    if (this.resumed) { this.i = this.resumed.i; this.clock = this.resumed.clock || 0; this.intro = true; this.liftReady = this.i >= 4; }
  }

  get S() { return this.stages[this.i]; }
  get done() { return this.complete; }
  snapshot() { return { i: this.complete ? 0 : this.i, clock: this.clock }; }
  after(t, fn) { this.timers.push({ t: this.now + t, fn }); }
  say(lines, cb) {
    const h = this.g.hud;
    lines.forEach(([who, text], k) => h.radio(who[0], text, { color: who[1], tag: this.i, cb: k === lines.length - 1 ? cb : null }));
  }
  sayOnce(id, lines) { if (this.said.has(id)) return; this.said.add(id); this.say(lines); }
  level() { const S = this.S, D = this.w.map.district(S.pos.x, S.pos.z); return Math.min(this.w.levelAt(S.pos.x, S.pos.z, D), this.w.level + 2 + this.i * 2); }
  ground(x, z) { return Math.max(this.w.map.height(x, z), -2.4); }

  // no collider overlapping a circle of radius r at standing height
  isClear(x, y, z, r) {
    for (const b of this.w.collision.near(x, z, r)) {
      if (b.max.y < y + .3 || b.min.y > y + 2.2) continue;
      if (x + r > b.min.x && x - r < b.max.x && z + r > b.min.z && z - r < b.max.z) return false;
    }
    return true;
  }
  // nearest open ground to p (spiral search)
  clearSpot(p, r) {
    for (let rad = 0; rad <= 120; rad += 4) {
      const n = rad ? Math.ceil(rad * Math.PI / 4) : 1;
      for (let k = 0; k < n; k++) {
        const a = k / n * Math.PI * 2, x = p.x + Math.cos(a) * rad, z = p.z + Math.sin(a) * rad, y = this.ground(x, z);
        if (this.isClear(x, y, z, r)) return new V(x, y, z);
      }
    }
    return new V(p.x, this.ground(p.x, p.z), p.z);
  }
  // a spawn point around c: open ground, ideally with a line of sight to the arena (refY: stand on boxes, e.g. the foundation)
  spawnSpot(c, rMin, rMax, refY = null) {
    let first = null;
    for (let k = 0; k < 36; k++) {
      const a = Math.random() * Math.PI * 2, r = rMin + Math.random() * (rMax - rMin);
      const x = c.x + Math.cos(a) * r, z = c.z + Math.sin(a) * r;
      const y = refY != null ? this.w.collision.support(x, z, refY + .5) : this.ground(x, z);
      if (refY != null && Math.abs(y - refY) > .8) continue;
      if (!this.isClear(x, y, z, .9)) continue;
      const p = new V(x, y, z);
      if (this.w.collision.lineOfSight(_a.set(x, y + 1.5, z), _b.set(c.x, c.y + 1.5, c.z))) return p;
      first = first || p;
    }
    return first || c.clone().add(new V((Math.random() - .5) * 6, 0, (Math.random() - .5) * 6));
  }

  // ---------------------------------------------------------------- build: anchors, props, interactables
  build() {
    const w = this.w, g = this.g, A = g.assets, sc = w.scene, op = this;
    const prop = (kit, p, rot = 0, solid = true) => {
      const o = A.clone('vanthos', kit); o.position.copy(p); o.rotation.y = rot; sc.add(o);
      o.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
      if (solid) w.collision.addObject(o, 'prop', .2);
      return o;
    };
    const face = (from, to) => Math.atan2(to.x - from.x, to.z - from.z);       // rotation.y that points local +Z at `to`
    const local = (o, x, z) => { const c = Math.cos(o.rotation.y), s = Math.sin(o.rotation.y); return new V(o.position.x + x * c + z * s, o.position.y, o.position.z - x * s + z * c); };
    const L = w.landing;
    // ---- stage anchors on a route from the landing zone to the Spire (~1.6 km)
    const relay = this.clearSpot(polar(103, 1478), 7);
    const shuttle = this.clearSpot(polar(105.8, 990), 5);
    const nest = this.clearSpot(polar(110, 572), 7);
    const lift = new V(0, this.ground(0, 100), 100);
    const found = new V(-13, FOUND_Y, 52);
    this.stages = STAGES.map(s => ({ ...s }));
    const [S1, S2, S3, S4, S5] = this.stages;
    for (const S of [S1, S2, S3]) S.place = null;
    S1.pos = relay; S1.r = 70; S2.pos = shuttle; S2.r = 70; S3.pos = nest; S3.r = 75; S4.pos = lift; S4.r = 60; S5.pos = found; S5.r = 95;
    for (const S of [S1, S2, S3]) S.place = w.map.district(S.pos.x, S.pos.z).name;     // the district it really lies in
    // checkpoints: just short of each arena, on the side you come from
    const back = (p, from, d) => this.clearSpot(p.clone().add(from.clone().sub(p).setY(0).normalize().multiplyScalar(d)), 1.2);
    S1.cp = back(relay, L, 40); S2.cp = back(shuttle, relay, 42); S3.cp = back(nest, shuttle, 45); S4.cp = this.clearSpot(new V(0, 0, 124), 1.2);
    S5.cp = S4.cp;
    this.route = [L, relay, shuttle, nest, lift];
    // ---- stage 1: the relay mast, console facing the landing zone
    this.relay = prop('VX_relay', relay, face(relay, L));
    this.relayGlow = []; this.relay.traverse(o => { if (o.isMesh && o.material.name === 'relay_glow') { o.material = o.material.clone(); this.relayGlow.push(o.material); } });
    S1.console = local(this.relay, 0, 3.6);
    this.addIt({ pos: S1.console, r: 2.6, label: 'Relay console', get verb() { return 'Start the uplink'; },
      enabled: () => this.i === 0 && this.phase === 'ready', action: () => this.relayStart() });
    // ---- stage 2: Flight Nine, nose-down under the broken highway
    const sh = prop('VX_shuttle', shuttle, 105 * DEG + .6, false);
    for (const t of [-9, -3, 3, 9, 13]) {          // fuselage colliders along its axis (the luggage stays walkable)
      const c = local(sh, .296 * t, .955 * t); w.collision.add([c.x - 2.4, c.y, c.z - 2.4, c.x + 2.4, c.y + 4.6, c.z + 2.4], 'prop');
    }
    S2.recorder = this.clearSpot(local(sh, -6, -4), 1.2); S2.recorder.y += .7;
    this.recorder = A.clone('props_world', 'PR_core'); this.recorder.position.copy(S2.recorder); this.recorder.scale.setScalar(.9);
    this.recorder.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); if (o.material.emissive) { o.material.emissive.set(0xffae2f); o.material.color.set(0xffae2f); } } });
    sc.add(this.recorder);
    this.addIt({ pos: S2.recorder, r: 2.4, label: 'Flight recorder', verb: 'Pull the recorder',
      enabled: () => this.i === 1 && this.phase === 'recorder', action: () => this.shuttlePull() });
    // ---- stage 3: the nest across the Crown ring road, and the gas-main valve
    this.nestLights = [];
    for (let k = 0; k < 5; k++) {
      const a = k * 1.256 + .4, p = this.clearSpot(nest.clone().add(new V(Math.cos(a) * (9 + k * 2), 0, Math.sin(a) * (9 + k * 2))), 2);
      prop(k % 2 ? 'VX_growth_s' : 'VX_growth_l', p, k * 1.7, false);
      if (k < 3) { w.lights.push({ pos: p.clone().setY(p.y + 2.5), color: new THREE.Color(0xb8ff40), intensity: 2.4, flicker: true }); this.nestLights.push(w.lights[w.lights.length - 1]); }
    }
    S3.valve = this.clearSpot(nest.clone().add(nest.clone().sub(shuttle).setY(0).normalize().multiplyScalar(-14)), 1.5);
    const valve = prop('VX_terminal', S3.valve, face(S3.valve, shuttle));
    this.valveMat = []; valve.traverse(o => { if (o.isMesh && o.material.name === 'terminal_screen') { o.material = o.material.clone(); o.material.emissive.set(0xff6a2a); o.material.color.set(0xff6a2a); this.valveMat.push(o.material); } });
    this.addIt({ pos: local(valve, 0, 1), r: 2.4, label: 'Crown Main 6 valve', verb: 'Open the gas main',
      enabled: () => this.i === 2 && this.phase === 'valve', action: () => this.nestPurge() });
    // ---- stage 4: the lift console beside the Spire lift
    S4.console = new V(5, this.ground(5, 104), 104);
    const lc = prop('VX_terminal', S4.console, 0);
    this.addIt({ pos: local(lc, 0, 1), r: 2.4, label: 'Spire lift controls', verb: 'Restore lift power',
      enabled: () => this.i === 3 && this.phase === 'ready', action: () => this.liftStart() });
    const base = w.spireLiftBase;
    if (base) {
      const ride = base.action;
      Object.defineProperty(base, 'verb', { configurable: true, get() { return op.liftReady ? 'Ride to the foundation' : 'No power · restore it at the lift controls'; } });
      base.label = 'Spire lift';
      base.action = () => { if (!this.liftReady) { g.audio.ui('deny'); g.hud.toast('The lift has no power'); return; } ride(); this.onLiftRide(); };
    }
    // ---- stage 5: three shield conduits around the foundation and the Warden's reliquary
    this.conduits = [180, -108, -36].map((d, k) => new Conduit(this, polar(d, 72).setY(FOUND_Y), k));
    const rq = new V(-13, FOUND_Y, 47);
    this.reliq = { obj: prop('VX_reliquary', rq, 0), pos: rq, open: false, t: 0, sealed: true };
    this.reliq.lid = this.reliq.obj.getObjectByName('reliquary_lid');
    this.reliq.mats = []; this.reliq.obj.traverse(o => { if (o.isMesh && o.material.name === 'reliquary_glow') { o.material = o.material.clone(); this.reliq.mats.push(o.material); } });
    this.sealReliquary(true);
    this.addIt({ pos: local(this.reliq.obj, 0, 1.4), r: 2.8, label: 'The Warden’s reliquary',
      get verb() { return op.reliq.sealed ? 'Sealed · defeat the Warden' : 'Open the reliquary'; }, enabled: () => !this.reliq.open, action: () => this.openReliquary() });
    this.addIt({ pos: local(this.reliq.obj, 2.4, 1.4), r: 2.4, label: 'Signal the Wayfarer', verb: 'Return to orbit',
      enabled: () => this.complete && this.reliq.open, action: () => g.travel('ship') });
    // ---- optional terminal logs near each arena
    const logAt = [[relay, 'relay', 9], [shuttle, 'shuttle', 12], [nest, 'nest', 16], [lift, 'lift', 9]];
    for (const [c, id, d] of logAt) {
      const p = id === 'lift' ? new V(-6, this.ground(-6, 108), 108) : this.clearSpot(c.clone().add(new V(d * .7, 0, d * .7)), 1.4);
      const t = prop('VX_terminal', p, face(p, c));
      this.addIt({ pos: local(t, 0, 1), r: 2.2, label: 'Terminal · ' + LOGS[id].title, verb: 'Read the log', action: () => this.readLog(id) });
    }
    // ---- keep ambient packs off the route and out of the arenas (the operation's waves own those fights)
    const segD = (p, a, b) => { const abx = b.x - a.x, abz = b.z - a.z, t = Math.max(0, Math.min(1, ((p.x - a.x) * abx + (p.z - a.z) * abz) / (abx * abx + abz * abz))); return Math.hypot(p.x - a.x - abx * t, p.z - a.z - abz * t); };
    let off = 0;
    for (const st of w.sites) {
      if (st.o.boss) continue;
      const nearArena = this.stages.some(s => Math.hypot(st.pos.x - s.pos.x, st.pos.z - s.pos.z) < 150);
      let nearRoute = false; for (let k = 0; k < this.route.length - 1; k++) if (segD(st.pos, this.route[k], this.route[k + 1]) < 90) nearRoute = true;
      if (nearArena || nearRoute || Math.hypot(st.pos.x, st.pos.z) < 160) { st.off = true; off++; }
    }
    this.offSites = off;
  }

  addIt(it) { it.id = 'op'; it.key = 'E'; this.w.interactables.push(it); (this.its = this.its || []).push(it); return it; }

  sealReliquary(on) {
    this.reliq.sealed = on;
    for (const m of this.reliq.mats) { m.emissive.set(on ? 0x8a1a3a : 0xffcf3f); m.color.set(on ? 0x5a1a2a : 0xffcf3f); m.emissiveIntensity = on ? .6 : 3; }
  }

  // ---------------------------------------------------------------- waves
  wave(types, n, o = {}) {
    const g = this.g, c = o.center || this.S.pos, lvl = o.level || this.level();
    const list = [];
    for (let k = 0; k < n; k++) {
      const type = types[k % types.length];
      const p = this.spawnSpot(c, o.rMin ?? 24, o.rMax ?? 40, o.refY ?? null);
      const e = g.enemies.spawn(type, p, lvl, { group: list });
      e.op = true; e.state = 'combat'; e.home.copy(c);
      if (o.name && k === 0) e.T = { ...e.T, name: o.name };
      list.push(e);
    }
    if (list.length) { const e = list[0]; if (e.faction === 'writhe' && g.audio.shriek) g.audio.shriek(e.pos, 1); else g.audio.alert(e.pos); }
    const wv = { list, req: o.req !== false, lowT: 0, alive() { return this.list.filter(e => e.alive).length; } };
    this.waves.push(wv);
    return wv;
  }

  // stragglers: required waves whose last few enemies are stuck behind buildings come to the player
  tidyWaves(dt) {
    const g = this.g, p = g.player.pos;
    for (const wv of this.waves) {
      for (const e of wv.list) {
        if (!e.alive) continue;
        if (e.pos.y < -30 || !Number.isFinite(e.pos.x)) { e.alive = false; g.combat.targets.delete(e); g.enemies.removeWhere(x => x === e); }
      }
      const n = wv.alive();
      if (!wv.req || !n || n > 2) { wv.lowT = 0; continue; }
      wv.lowT += dt;
      if (wv.lowT > 22) {
        wv.lowT = 0;
        for (const e of wv.list) if (e.alive && e.pos.distanceTo(p) > 18) {
          const q = this.spawnSpot(p, 12, 20, this.i === 4 ? FOUND_Y : null);
          e.pos.copy(q); e.obj.position.copy(q); e.vel.set(0, 0, 0); e.state = 'combat';
        }
      }
    }
    this.waves = this.waves.filter(wv => wv.alive() > 0);
  }

  reqAlive() { let n = 0; for (const wv of this.waves) if (wv.req) n += wv.alive(); return n; }

  // ---------------------------------------------------------------- stage flow
  arrive(S) {
    // lines still queued from earlier stages are stale once you are here (a fast board ride outruns the radio)
    const h = this.g.hud; h.radioQ = h.radioQ.filter(q => q.tag === undefined || q.tag >= this.i);
    this.phase = 'arrived'; this.cp = S.cp; this.g.hud.banner(S.title, S.place + ' · objective ' + (this.i + 1) + ' / ' + this.stages.length, 3); }

  finishStage(lines) {
    const g = this.g, S = this.S;
    this.phase = 'done'; this.cp = S.cp;
    g.audio.levelUp(); g.gain('xp', 300 + this.i * 120); g.gain('credits', 120 + this.i * 60, true);
    g.hud.feed('Objective complete · ' + S.title, '#e3c26c');
    if (lines) this.say(lines);
    this.after(2.5, () => { if (this.i < this.stages.length - 1) { this.i++; this.phase = 'travel'; } });
    g.persist();
  }

  update(dt) {
    const g = this.g, w = this.w, p = g.player.pos;
    if (!this.stages) return;
    if (!this.complete) this.clock += dt;
    this.now += dt;
    for (let k = this.timers.length - 1; k >= 0; k--) if (this.timers[k].t <= this.now) { const t = this.timers.splice(k, 1)[0]; t.fn(); }
    this.tidyT = (this.tidyT || 0) - dt; if (this.tidyT <= 0) { this.tidyT = 1; this.tidyWaves(1); }
    for (const c of this.conduits) c.update(dt, g.time);
    this.updateVfx(dt);
    if (this.recorder && this.recorder.parent) { this.recorder.rotation.y += dt * 1.6; this.recorder.position.y = this.S2y(); }
    if (this.reliq.open && this.reliq.t < 1) { this.reliq.t = Math.min(1, this.reliq.t + dt * 1.4); if (this.reliq.lid) this.reliq.lid.rotation.x = -this.reliq.t * 1.75; }
    // intro over the radio once the arrival banner has passed
    if (!this.intro && this.clock > 1.2) {
      this.intro = true;
      this.say([[WREN, 'Wheels down. That’s Vanthos, Captain. What’s left of her.'],
        [WREN, 'I’m blind through this static. There’s a relay mast on the Outer Ring. Wake it and I’ll be your eyes.']]);
      this.after(4.6, () => g.hud.banner(OP_NAME, 'Reach the Spire · five objectives', 3.5));
    }
    if (this.resumed && !this.said.has('resume')) { this.said.add('resume'); this.say([[WREN, 'Good, you’re topside again. Picking up where we left off.']]); }
    if (this.complete) return;
    const S = this.S, d = Math.hypot(p.x - S.pos.x, p.z - S.pos.z);
    const top = w.onFoundation();
    switch (S.id) {
      case 'relay': this.relayTick(dt, d); break;
      case 'shuttle': this.shuttleTick(dt, d); break;
      case 'nest': this.nestTick(dt, d); break;
      case 'lift': this.liftTick(dt, d, p); break;
      case 'warden': this.wardenTick(dt, top); break;
    }
  }
  S2y() { return this.stages[1].recorder.y + Math.sin(this.g.time * 2.2) * .12; }

  // ---- 1: wake the relay (hold the uplink while raiders come)
  relayTick(dt, d) {
    const g = this.g, S = this.S;
    if (this.phase === 'travel' && d < S.r) {
      this.arrive(S); this.phase = 'ready';
      this.say([[WREN, 'Raider tags all over that mast. They’ve been listening in on our channels.'], [WREN, 'Patch into the console and hold the area while it handshakes.']]);
    }
    if (this.phase === 'hold') {
      const pd = g.player.pos.distanceTo(S.pos);
      this.hold.inside = pd < 20 && !g.player.dead;
      if (this.hold.inside) this.hold.p = Math.min(1, this.hold.p + dt / 32);
      const marks = [[.3, () => this.wave(['trooper', 'trooper', 'brute'], 3)], [.6, () => this.wave(['trooper', 'trooper'], 3)], [.85, () => this.wave(['trooper', 'brute'], 2)]];
      for (const [m, fn] of marks) if (this.hold.p >= m && !this.said.has('r' + m)) { this.said.add('r' + m); fn(); }
      if (this.hold.p >= .5) this.sayOnce('relay50', [[WREN, 'Halfway. The old city grid still answers to my codes. Who knew.']]);
      for (const m of this.relayGlow) { m.emissive.setRGB(1 - this.hold.p * .9, .68 + this.hold.p * .17, .18 + this.hold.p * .82); m.emissiveIntensity = 4 + Math.sin(g.time * 9) * 2; }
      if (this.hold.p >= 1) {
        for (const m of this.relayGlow) { m.emissive.set(0x1ad8ff); m.color.set(0x1ad8ff); m.emissiveIntensity = 6; }
        g.fx.emit(S.pos.clone().setY(S.pos.y + 18), 40, 6, 0x1ad8ff, .8, 1, .08);
        this.finishStage([[WREN, 'Link’s up. I can see the whole southern sprawl now.'],
          [WREN, 'There’s an evac shuttle down under the broken highway. Flight Nine. It never made orbit. Its recorder might tell us what happened that night.']]);
      }
    }
  }
  relayStart() {
    this.phase = 'hold'; this.hold = { p: 0, inside: true }; this.g.audio.ui('confirm');
    this.say([[WREN, 'Uplink running. Here they come. Keep them off the mast.']]);
    this.wave(['trooper', 'trooper', 'trooper'], 3, { rMin: 30, rMax: 46 });
  }

  // ---- 2: Flight Nine (ambush in the wreck, pull the recorder, survive the second wave)
  shuttleTick(dt, d) {
    const S = this.S;
    if (this.phase === 'travel' && d < S.r) {
      this.arrive(S); this.phase = 'fight1';
      this.say([[WREN, 'Flight Nine. I had friends booked on that one.'], [WREN, 'Movement in the wreck. Stalkers. They nest in anything that was ever warm.']]);
      this.after(2, () => { this.w1 = this.wave(['stalker'], 4, { rMin: 6, rMax: 20 }); });
    }
    if (this.phase === 'fight1' && this.w1 && this.w1.alive() === 0) {
      this.phase = 'recorder';
      this.say([[WREN, 'Clear. The recorder sits behind the cockpit. Pull it.']]);
    }
    if (this.phase === 'fight2' && this.w2 && this.w2.alive() === 0) {
      this.finishStage([[WREN, 'Got the data. The Spire wasn’t attacked, Captain. Something inside it woke up and took the reactor.'],
        [WREN, 'Head for the Crown ring road. My scans show growth across the road. Writhe.']]);
    }
  }
  shuttlePull() {
    const g = this.g;
    this.phase = 'log'; g.audio.ui('open');
    this.recorder.removeFromParent();
    g.hud.feed('Flight recorder recovered', '#ffae2f');
    this.say([[REC, 'Vanthos Control, Flight Nine. We are heavy, two hundred and twelve souls, requesting the outer corridor—'],
      [REC, 'Control? Control, the Spire is open. The core is... it’s looking at us.'], [REC, 'Brace, brace, brace—'],
      [WREN, '...It went for the ships first. Hostiles inbound. The noise woke the whole block.']]);
    this.after(5, () => { this.w2 = this.wave(['stalker', 'stalker', 'hulk', 'stalker'], 4, { rMin: 26, rMax: 42 }); this.phase = 'fight2'; });
  }

  // ---- 3: the Brood Road (three Writhe waves, an amalgam, then light the gas main)
  nestTick(dt, d) {
    const S = this.S;
    if (this.phase === 'travel' && d < S.r) {
      this.arrive(S); this.phase = 'w1';
      this.say([[WREN, 'Writhe nest. That stuff eats the dead and wears them. Don’t let the little ones touch you.'],
        [WREN, 'There’s a district heating main under that road. Thin them out, then light it.']]);
      this.nw = this.wave(['mite', 'mite', 'host', 'mite', 'mite', 'host', 'mite', 'mite'], 8, { rMin: 10, rMax: 28 });
    }
    if (this.phase === 'w1' && this.nw.alive() <= 1) {
      this.phase = 'w2'; this.say([[WREN, 'More coming up out of the drains!']]);
      this.nw = this.wave(['host', 'bladder', 'mite', 'mite', 'host', 'bladder', 'mite', 'mite'], 8, { rMin: 14, rMax: 32 });
    }
    if (this.phase === 'w2' && this.nw.alive() <= 1) {
      this.phase = 'w3'; this.say([[WREN, 'Something big is pushing up through the street. That’s a knot of hosts, fused.']]);
      this.nw = this.wave(['amalgam', 'mite', 'mite', 'mite', 'mite'], 5, { rMin: 16, rMax: 28, name: 'The Knot' });
    }
    if (this.phase === 'w3' && this.nw.alive() === 0) {
      this.phase = 'valve';
      this.say([[WREN, 'The valve terminal is on the kerb. Open the main and step back.']]);
    }
  }
  nestPurge() {
    const g = this.g, S = this.S;
    this.phase = 'purge'; g.audio.ui('confirm');
    for (const m of this.valveMat) { m.emissive.set(0x40ff8a); m.color.set(0x40ff8a); }
    this.say([[WREN, 'Burn, you wretched thing. The old city is still good for something.']]);
    for (let k = 0; k < 9; k++) this.after(.4 + k * .28, () => {
      const a = k * 2.4, r = 4 + (k % 4) * 6, q = S.pos.clone().add(new V(Math.cos(a) * r, 1, Math.sin(a) * r));
      g.fx.explosion(q, 6); g.audio.explosion(q);
      for (const e of g.enemies.list) if (e.alive && e.faction === 'writhe' && e.pos.distanceTo(q) < 14) e.takeDamage(1e6, false, e.center(_c).clone(), null, 'rival');
    });
    this.fireT = 14;
    for (const L of this.nestLights) { L.color.set(0xff7a2a); L.intensity = 4; }
    this.after(3.6, () => this.finishStage([[WREN, 'The Spire’s lift on the south face still has a car. No power, though. I’ll talk you through it.']]));
  }

  // ---- 4: the Spire lift (restore power while three factions converge, then ride up)
  liftTick(dt, d, p) {
    const g = this.g, S = this.S;
    if (this.phase === 'travel' && Math.hypot(p.x, p.z) < 300 && p.y < 20)
      this.sayOnce('rim', [[WREN, 'That crater used to be the Reactor Gardens. My father worked nights down there.'], [WREN, 'Hear that hum? The core is still beating. It shouldn’t be.']]);
    if (this.phase === 'travel' && d < S.r && p.y < 20) {
      this.arrive(S); this.phase = 'ready';
      this.say([[WREN, 'Lift console’s dead. Prime it from the panel and I’ll reroute what’s left of the grid.']]);
    }
    if (this.phase === 'hold') {
      this.hold.inside = g.player.pos.distanceTo(S.console) < 22 && !g.player.dead;
      if (this.hold.inside) this.hold.p = Math.min(1, this.hold.p + dt / 42);
      const marks = [[.2, () => this.wave(['stalker', 'stalker', 'stalker'], 3)], [.42, () => { this.wave(['mite', 'mite', 'host', 'mite', 'mite', 'host'], 6, { rMin: 20, rMax: 34 });
        this.say([[WREN, 'Raiders, aliens and the Writhe, all at once. Let them chew on each other.']]); }],
        [.66, () => this.wave(['trooper', 'brute', 'stalker', 'trooper'], 4)], [.88, () => this.wave(['mutant', 'mutant'], 2)]];
      for (const [m, fn] of marks) if (this.hold.p >= m && !this.said.has('l' + m)) { this.said.add('l' + m); fn(); }
      if (this.hold.p >= 1) {
        this.phase = 'ride'; this.liftReady = true; g.audio.levelUp();
        g.fx.emit(S.pos.clone().setY(S.pos.y + 6.5), 40, 5, 0x1ad8ff, .8, 1, .08);
        this.say([[WREN, 'Lift’s live. Whatever took the Spire is waiting on the foundation. Ride up when you’re ready.']]);
      }
    }
  }
  liftStart() {
    this.phase = 'hold'; this.hold = { p: 0, inside: true }; this.g.audio.ui('confirm');
    this.say([[WREN, 'Rerouting. It will take a minute, and every creature in the Crown can hear it.']]);
    this.wave(['trooper', 'trooper', 'trooper'], 3, { rMin: 28, rMax: 44 });
  }
  onLiftRide() {
    if (this.i === 3 && this.phase === 'ride') this.finishStage(null);
  }

  // ---- 5: the Spire Warden
  wardenTick(dt, top) {
    const g = this.g, S = this.S;
    if (this.phase === 'travel' && top) {
      this.arrive(S); this.cp = S.cp;
      this.spawnBoss();
      this.phase = 'intro';
      this.say([[WREN, 'There it is. The Spire Warden. It’s wired into the core. It has been drinking the whole city’s power.'],
        [WARDEN, '( a low sound, like the whole city breathing in )']]);
      g.audio.roar && g.audio.roar(this.boss.pos);
      this.after(3.5, () => { if (this.boss && this.boss.alive) { this.boss.alert(); this.phase = 'fight'; } });
    }
    const B = this.boss;
    if (!B) return;
    if (B.alive && B.pos.y < FOUND_Y - 6) { B.pos.copy(this.bossHome); B.vel.set(0, 0, 0); B.obj.position.copy(B.pos); }
    // adds while shielded
    if (this.phase === 'shield') {
      this.addT -= dt;
      const alive = this.adds.filter(e => e.alive).length;
      if (this.addT <= 0 && alive < 7) {
        this.addT = 13;
        const pool = ['stalker', 'stalker', 'mite', 'mite', 'mite', 'mutant'];
        const types = Array.from({ length: 3 + (Math.random() < .5 ? 1 : 0) }, () => pool[Math.floor(Math.random() * pool.length)]);
        const wv = this.wave(types, types.length, { center: new V(0, FOUND_Y, 0), rMin: 74, rMax: 84, refY: FOUND_Y, req: false });
        this.adds.push(...wv.list);
      }
    }
    if (this.phase === 'stagger' && B.alive && Math.random() < dt * 8) g.fx.emit(B.center(_a).clone().add(_b.set((Math.random() - .5) * 2, Math.random() * 1.5, (Math.random() - .5) * 2)), 6, 3, 0xff8ad6, .3, 2, .05);
    if (this.phase === 'stagger' && !(B.stunT > 0)) { this.phase = 'fight'; B.vuln = 1; }
  }

  spawnBoss() {
    const g = this.g, w = this.w, S = this.S;
    const lvl = Math.min(w.level + 10, w.levelAt(0, 0));
    this.bossHome = new V(-13, FOUND_Y, 40);
    const e = g.enemies.spawn('elite', this.bossHome, lvl, { onDeath: () => this.onBossDeath() });
    const scale = 1.7;
    e.T = { ...e.T, name: BOSS, scale: (e.T.scale || 1) * scale, loot: 0, xp: 1500 };
    e.maxHp = e.hp = Math.round(e.maxHp * 3.6); e.boss = BOSS; e.op = true;
    if (e.av) e.av.root.scale.setScalar(scale);
    e.yaw = 0; e.hpFloor = e.maxHp * .5; e.onFloor = () => this.raiseShield(1);
    e.onImmuneHit = (point) => {
      this.shieldHit = 1;
      if (point) g.fx.emit(point, 8, 5, 0xff3fb4, .35, 3, .06, .9);
      if ((this.pingT || 0) < this.now) { this.pingT = this.now + .09; g.audio.shieldPing && g.audio.shieldPing(point || e.pos); }
    };
    this.boss = e; this.shieldK = 0;
  }

  raiseShield(k) {
    const g = this.g, B = this.boss;
    this.shieldK = k; this.phase = 'shield'; this.addT = 2.5;
    B.immune = true; B.stunT = 0; B.vuln = 1;
    const hp = Math.round((1100 + this.level() * 60) * (k === 1 ? 1 : .7));
    const set = k === 1 ? this.conduits : this.conduits.slice().sort(() => Math.random() - .5).slice(0, 2);
    for (const c of set) c.activate(hp);
    g.fx.glow(B.center(_a).clone(), 9, 0xff3fb4, .5); g.fx.flash(B.center(_a), 0xff3fb4, 600, .4, 30);
    g.audio.roar && g.audio.roar(B.pos);
    g.hud.banner('Shielded', k === 1 ? 'Destroy the three shield conduits' : 'Two conduits back online', 3);
    this.say(k === 1 ? [[WREN, 'It’s pulling power through those pylons. The shield is fed from the core. Break the conduits!']]
      : [[WREN, 'It’s drawing again! Two conduits are back online.']]);
  }

  onConduitDown(c) {
    const g = this.g, left = this.conduits.filter(x => x.alive).length;
    g.hud.feed('Shield conduit destroyed' + (left ? ' · ' + left + ' left' : ''), '#ff8ad6');
    if (left) { this.say([[WREN, left === 1 ? 'Last one!' : 'One down. Keep going.']]); return; }
    this.dropShield();
  }

  dropShield() {
    const g = this.g, B = this.boss; if (!B || !B.alive) return;
    B.immune = false; B.stunT = 4.5; B.vuln = 1.5;
    B.hpFloor = this.shieldK === 1 ? B.maxHp * .2 : 0; B.onFloor = () => this.raiseShield(2);
    this.phase = 'stagger';
    const c = B.center(_a).clone();
    g.fx.emit(c, 120, 10, 0xff3fb4, .9, 3, .09); g.fx.glow(c, 10, 0xff8ad6, .4); g.fx.flash(c, 0xff3fb4, 900, .4, 30); g.audio.explosion(c);
    g.hud.banner('Shield broken', 'The Warden is reeling · hit it now', 2.6);
    this.say([[WREN, 'Shield’s down. It’s reeling. Hit it now!']]);
  }

  onBossDeath() {
    const g = this.g, sv = g.save.vanthos;
    this.phase = 'loot';
    const t = this.clock;
    sv.runs = (sv.runs || 0) + 1; this.newBest = sv.best == null || t < sv.best; sv.best = sv.best == null ? t : Math.min(sv.best, t);
    sv.lastRun = { time: Math.round(t), at: Date.now() };
    if (!sv.bosses.includes(BOSS)) sv.bosses.push(BOSS);
    this.runTime = t;
    for (const c of this.conduits) if (c.alive) { c.alive = false; g.combat.targets.delete(c); c.set('dead'); } else c.set('dead');
    // the link to the core collapses: whatever it called up dies with it
    this.after(1.2, () => { for (const e of this.adds) if (e.alive) e.takeDamage(1e6, false, e.center(_c).clone(), null, 'rival'); });
    this.sealReliquary(false);
    g.fx.emit(this.reliq.pos.clone().setY(FOUND_Y + 1.5), 50, 4, 0xffcf3f, 1, -1, .08);
    g.gain('xp', 1500); g.gain('credits', 600, true);
    g.hud.banner(BOSS + ' defeated', 'Its reliquary is unsealed', 4);
    this.say([[WREN, '...It’s done. The core is going quiet. Vanthos is quiet.'], [WREN, 'The Warden kept a reliquary. Take what it hoarded. You earned it.']]);
    g.persist();
  }

  // ---------------------------------------------------------------- loot
  // 2-3 weapons, any archetype or class, weighted rarity, rolled perks / stats / sight, power around the player's
  rollRewards(n = null, o = {}) {
    const g = this.g, pw = g.power(), out = [];
    n = n || (2 + (Math.random() < .5 ? 1 : 0));
    for (let k = 0; k < n; k++) {
      const rarity = +pickWeighted({ 1: 22, 2: 40, 3: 29, 4: 9 });
      const w = rollWeapon(pw + Math.round(Math.random() * 7 - 1) + (rarity >= 3 ? 2 : 0), { rarity, arch: o.arch, source: 'Spire reliquary' });
      out.push(w);
    }
    return out;
  }

  openReliquary() {
    const g = this.g, sv = g.save;
    if (this.reliq.sealed) { g.audio.ui('deny'); g.hud.toast('Sealed. The Warden still holds it'); return; }
    if (this.reliq.open) return;
    this.reliq.open = true; this.complete = true; this.phase = 'complete';
    const ws = this.rollRewards();
    for (const w of ws) { g.addWeapon(w); g.hud.feed(w.name + ' · ' + ARCHETYPES[w.arch].name + ' · ' + w.power, RARITY[w.rarity].color); }
    const credits = 900 + this.level() * 30, alloy = 10 + Math.floor(Math.random() * 9);
    g.gain('credits', credits, true); sv.alloy += alloy; g.gain('xp', 1800);
    this.rewards = { weapons: ws, credits, alloy };
    g.audio.pickup(Math.max(...ws.map(w => w.rarity))); g.audio.ui('open');
    const c = this.reliq.pos.clone().setY(FOUND_Y + 1.4);
    g.fx.emit(c, 80, 6, 0xffcf3f, 1.2, -2, .1); g.fx.glow(c, 7, 0xffcf3f, .6); g.fx.flash(c, 0xffcf3f, 500, .5, 20);
    const v = sv.vanthos;
    g.hud.banner('Operation complete', OP_NAME + ' · ' + fmtTime(this.runTime) + (this.newBest ? ' · new best' : ' · best ' + fmtTime(v.best)), 3.6);
    const rows = ws.map(w => `<div class="r"><span style="color:${RARITY[w.rarity].color}">${esc(w.name)}</span><em>${RARITY[w.rarity].name} ${esc(ARCHETYPES[w.arch].name)} · ${esc(SIGHTS[weaponSight(w)].name)}${w.perks.length ? ' · ' + w.perks.map(p => PERKS[p].name).join(', ') : ''}</em></div>`).join('');
    this.after(3.4, () => g.hud.lore(OP_NAME + ' · complete', 'The Spire is silent', `<p>Time <b>${fmtTime(this.runTime)}</b> · best <b>${fmtTime(v.best)}</b> · runs <b>${v.runs}</b></p>${rows}
      <div class="r"><span>${credits} credits · ${alloy} alloy</span><em>Signal the Wayfarer to leave</em></div>`, 16));
    this.say([[WREN, 'Wayfarer is coming round. Signal when you want out, or stay a while. The city is yours.']]);
    g.persist();
  }

  readLog(id) {
    const g = this.g, v = g.save.vanthos, L = LOGS[id];
    g.audio.ui('open');
    g.hud.lore('Recovered log', L.title, L.html, 14);
    if (!v.logs.includes(id)) { v.logs.push(id); g.gain('xp', 80); }
    if (L.wren) this.sayOnce('log_' + id, [[WREN, L.wren]]);
  }

  // ---------------------------------------------------------------- VFX
  updateVfx(dt) {
    const g = this.g, B = this.boss, sc = this.w.scene;
    const shielded = B && B.alive && B.immune;
    if (shielded && !this.shield) {
      this.shield = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 4), shieldMaterial()); this.shield.renderOrder = 5; this.shield.frustumCulled = false;
      sc.add(this.shield);
      const tg = new THREE.CylinderGeometry(1, 1, 1, 6, 1, true); tg.rotateX(Math.PI / 2); tg.translate(0, 0, .5);
      this.tethers = this.conduits.map(() => { const m = new THREE.Mesh(tg, new THREE.MeshBasicMaterial({ color: new THREE.Color(0xff3fb4).multiplyScalar(3), transparent: true, opacity: .8, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false })); m.frustumCulled = false; sc.add(m); return m; });
    }
    if (this.shield) {
      const u = this.shield.material.uniforms;
      u.uT.value = g.time; this.shieldHit = Math.max(0, (this.shieldHit || 0) - dt * 4); u.uHit.value = this.shieldHit;
      u.uA.value += ((shielded ? 1 : 0) - u.uA.value) * Math.min(1, dt * (shielded ? 3 : 8));
      this.shield.visible = u.uA.value > .01 && !!B;
      if (B) { const s = (B.T.scale || 1); B.center(_a); this.shield.position.set(B.pos.x, B.pos.y + 1.1 * s, B.pos.z); this.shield.scale.set(1.15 * s, 1.35 * s, 1.15 * s); }
      this.conduits.forEach((c, k) => {
        const m = this.tethers[k]; m.visible = shielded && c.alive;
        if (!m.visible) return;
        _b.set(B.pos.x, B.pos.y + 1.4 * (B.T.scale || 1), B.pos.z);
        m.position.copy(c.emitter); m.lookAt(_b);
        const wob = .07 + Math.abs(Math.sin(g.time * 23 + k * 2)) * .06 + c.flash * .1;
        m.scale.set(wob, wob, c.emitter.distanceTo(_b));
        m.material.opacity = .45 + Math.random() * .4;
      });
    }
    if (this.fireT > 0) {
      this.fireT -= dt; const S3 = this.stages[2];
      if (Math.random() < dt * 14) { const a = Math.random() * 6.28, r = Math.random() * 16; g.fx.emit(S3.pos.clone().add(_a.set(Math.cos(a) * r, .3, Math.sin(a) * r)), 5, 2, Math.random() < .5 ? 0xff7a2a : 0xffc04a, .9, -3, .16, .5); }
    }
  }

  // ---------------------------------------------------------------- HUD feeds
  markers() {
    const out = [];
    if (!this.stages) return out;
    if (this.complete) { if (!this.reliq.open) out.push({ pos: this.reliq.pos, icon: '◆', color: '#ffcf3f' }); return out; }
    const S = this.S, ph = this.phase, gold = '#ffcf3f';
    let tgt = S.pos;
    if (S.id === 'relay' && ph === 'ready') tgt = S.console;
    if (S.id === 'shuttle' && ph === 'recorder') tgt = S.recorder;
    if (S.id === 'nest' && ph === 'valve') tgt = S.valve;
    if (S.id === 'lift' && (ph === 'ready' || ph === 'hold')) tgt = S.console;
    if (S.id === 'lift' && ph === 'ride') tgt = this.w.spireLift;
    if (S.id === 'warden' && ph === 'travel') tgt = this.w.spireLift;
    if (S.id === 'warden' && ph === 'loot') tgt = this.reliq.pos;
    if (!(S.id === 'warden' && (ph === 'fight' || ph === 'shield' || ph === 'stagger' || ph === 'intro'))) out.push({ pos: tgt, icon: '◈', color: gold });
    for (const c of this.conduits) if (c.alive) out.push({ pos: c.pos, icon: '✦', color: '#ff5ac8' });
    if (this.boss && this.boss.alive && S.id === 'warden') out.push({ pos: this.boss.pos, icon: '☗', color: '#ff4a3d' });
    // the last few of a wave you must clear
    const left = []; for (const wv of this.waves) if (wv.req) for (const e of wv.list) if (e.alive) left.push(e);
    if (left.length && left.length <= 3) for (const e of left) out.push({ pos: e.pos, icon: '✖', color: '#ff4a3d' });
    return out;
  }

  objectives() {
    if (!this.stages) return [];
    const g = this.g, p = g.player.pos, S = this.S, N = this.stages.length;
    const dist = q => { const d = Math.hypot(q.x - p.x, q.z - p.z); return d < 1000 ? Math.round(d) + ' m' : (d / 1000).toFixed(1) + ' km'; };
    const head = (text, extra = {}) => [{ text, sub: OP_NAME + ' · ' + (this.i + 1) + ' / ' + N + ' · ' + S.place, ...extra }];
    if (this.complete) return [{ text: 'Operation complete · ' + fmtTime(this.runTime), sub: OP_NAME + ' · run ' + g.save.vanthos.runs + ' · best ' + fmtTime(g.save.vanthos.best) },
      { text: this.reliq.open ? 'Signal the Wayfarer to return to orbit' : 'Open the Warden’s reliquary', sub: 'On the foundation' }];
    const left = this.reqAlive(), ph = this.phase;
    switch (S.id + ':' + ph) {
      case 'relay:travel': return head('Reach the relay mast · ' + dist(S.pos));
      case 'relay:ready': return head('Start the uplink at the relay console · ' + dist(S.console));
      case 'relay:hold': return head((this.hold.inside ? 'Hold the relay · ' : 'Return to the mast · uplink paused · ') + Math.round(this.hold.p * 100) + '%', { p: this.hold.p });
      case 'shuttle:travel': return head('Find Flight Nine · ' + dist(S.pos));
      case 'shuttle:fight1': case 'shuttle:fight2': case 'shuttle:log': return head('Clear the wreck' + (left ? ' · ' + left + ' hostiles' : ''));
      case 'shuttle:recorder': return head('Pull the flight recorder · ' + dist(S.recorder));
      case 'nest:travel': return head('Reach the Crown ring road · ' + dist(S.pos));
      case 'nest:w1': case 'nest:w2': case 'nest:w3': return head('Burn out the nest · ' + left + ' Writhe');
      case 'nest:valve': return head('Open the gas main · ' + dist(S.valve));
      case 'nest:purge': return head('Stand clear of the gas main');
      case 'lift:travel': return head('Reach the Spire lift · ' + dist(S.pos));
      case 'lift:ready': return head('Restore lift power at the controls · ' + dist(S.console));
      case 'lift:hold': return head((this.hold.inside ? 'Defend the lift controls · ' : 'Return to the lift · rerouting paused · ') + Math.round(this.hold.p * 100) + '%', { p: this.hold.p });
      case 'lift:ride': return head('Ride the lift to the foundation · ' + dist(this.w.spireLift));
      case 'warden:travel': return head('Ride the lift to the foundation · ' + dist(this.w.spireLift));
      case 'warden:intro': case 'warden:fight': case 'warden:stagger': return head('Defeat the Spire Warden', { p: this.boss ? this.boss.hp / this.boss.maxHp : 1 });
      case 'warden:shield': { const n = this.conduits.filter(c => c.alive).length; return head('Destroy the shield conduits · ' + n + ' left', { p: this.boss ? this.boss.hp / this.boss.maxHp : 1 }); }
      case 'warden:loot': return head('Open the Warden’s reliquary · ' + dist(this.reliq.pos));
      default: return head(S.title);
    }
  }

  // shield conduits get floating health bars while they are live
  barTargets() { const p = this.g.player.pos; return this.conduits.filter(c => c.alive && c.pos.distanceTo(p) < 120); }

  bossBar() {
    const B = this.boss;
    if (!B || !this.w.onFoundation() || this.complete) return null;
    if (!B.alive) return null;
    const left = this.conduits.filter(c => c.alive).length;
    const state = this.phase === 'shield' ? 'Immune · destroy the shield conduits · ' + left + ' left' : this.phase === 'stagger' ? 'Shield broken · reeling' : this.phase === 'intro' ? 'Waking' : '';
    return { name: BOSS, hp: B.hp, max: B.maxHp, shield: !!B.immune, state, mark: B.hpFloor ? B.hpFloor / B.maxHp : 0 };
  }

  // revival point after a fall
  spawnPoint() { return this.cp ? this.cp.clone() : null; }

  dispose() {
    for (const c of this.conduits) c.dispose();
    if (this.shield) { this.shield.geometry.dispose(); this.shield.material.dispose(); }
    if (this.tethers) this.tethers.forEach(t => t.material.dispose());
  }
}
