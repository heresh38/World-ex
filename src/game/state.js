// Persistent player state (localStorage) + loot generation.
import { ARCHETYPES, RARITY, PERKS, weaponName, CONTRACT_POOL, sightOptions } from './data.js';

const KEY = 'worldex_save_v1';

export const DEFAULT_SETTINGS = {
  quality: 'medium', resScale: 1, dynamicRes: true, sens: 1.0, aimSens: 1.0, aimSmooth: .3, touchSens: 1.0, invertY: false, fov: 70,
  master: .8, music: .6, sfx: .9, muted: false, showFps: false, view: 'first', dayMinutes: 40,
};

let uid = Date.now() % 100000;
export function mulberry(a) {
  return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

export function makeWeapon(arch, rarity, power, rnd = Math.random) {
  const A = ARCHETYPES[arch];
  const perkIds = Object.keys(PERKS);
  const perks = [];
  for (let i = 0; i < RARITY[rarity].perks; i++) {
    let p; let guard = 0;
    do { p = perkIds[Math.floor(rnd() * perkIds.length)]; } while (perks.includes(p) && guard++ < 20);
    perks.push(p);
  }
  const roll = () => 0.9 + rnd() * 0.2;
  return {
    uid: 'w' + (uid++) + Math.floor(rnd() * 1000), arch, rarity, power: Math.round(power), perks,
    name: weaponName(arch, rarity, rnd), shader: 'bone', sight: A.sight || 'default',
    stats: { dmg: roll(), rpm: 0.95 + rnd() * 0.1, stability: roll(), range: roll(), handling: roll() },
  };
}

export function rollRarity(bonus = 0, rnd = Math.random) {
  const r = rnd() + bonus;
  if (r > 0.985) return 4;
  if (r > 0.9) return 3;
  if (r > 0.68) return 2;
  if (r > 0.38) return 1;
  return 0;
}

// loot pool: every archetype of the slot, weighted (horror guns are rarer finds)
export function randomArch(rnd = Math.random, slot = null) {
  const keys = Object.keys(ARCHETYPES).filter(k => slot === null || ARCHETYPES[k].slot === slot);
  const wt = k => ARCHETYPES[k].weight ?? 1;
  let r = rnd() * keys.reduce((a, k) => a + wt(k), 0);
  for (const k of keys) { r -= wt(k); if (r <= 0) return k; }
  return keys[keys.length - 1];
}

// A fully rolled drop: archetype (any class, or a given slot / archetype), rarity, perks, stat rolls and a random sight
// from the gun's compatible optics, so the same gun can drop again and again and every copy is its own weapon.
export function rollWeapon(power, o = {}) {
  const rnd = o.rnd || Math.random;
  const arch = o.arch || randomArch(rnd, o.slot ?? null);
  const rarity = o.rarity ?? rollRarity(o.bonus || 0, rnd);
  const w = makeWeapon(arch, rarity, Math.max(1, power), rnd);
  const s = sightOptions(arch); w.sight = s[Math.floor(rnd() * s.length)];
  if (o.source) w.source = o.source;
  return w;
}

// weighted pick from {key: weight}
export function pickWeighted(table, rnd = Math.random) {
  const tot = Object.values(table).reduce((a, b) => a + b, 0); let r = rnd() * tot;
  for (const [k, v] of Object.entries(table)) { r -= v; if (r <= 0) return k; }
  return Object.keys(table)[0];
}

// how good a copy's stat rolls are (0..100): the average of its five rolls inside their ranges
export function rollQuality(w) {
  const s = w.stats || {}; const n = k => Math.max(0, Math.min(1, ((s[k] ?? 1) - (k === 'rpm' ? .95 : .9)) / (k === 'rpm' ? .1 : .2)));
  return Math.round(['dmg', 'rpm', 'stability', 'range', 'handling'].reduce((a, k) => a + n(k), 0) / 5 * 100);
}

// Vault: big enough for a long run of operation loot. Past the cap the weakest plain spare is broken down for alloy
// (never an equipped, locked (`keep`) or still-unseen (`isNew`) weapon); the caller is told so it can say so.
export const VAULT_CAP = 200;
export function vaultOverflow(s) {
  if (s.inventory.length <= VAULT_CAP) return null;
  const spare = s.inventory.filter(x => !s.equipped.includes(x.uid) && !x.keep && !x.isNew).sort((a, b) => a.rarity - b.rarity || a.power - b.power)[0];
  if (!spare) return null;
  s.inventory.splice(s.inventory.indexOf(spare), 1);
  const alloy = 2 + spare.rarity * 3; s.alloy += alloy;
  return { w: spare, alloy };
}

// Player look: body frame, skin, face morphs, colours and one item per clothing slot (null wear = the model's defaults).
export function defaultCharacter(body = 'female') {
  const m = body === 'male';
  return { v: 3, body, skin: m ? '#c08560' : '#e2b394', eyes: m ? '#6b8a5a' : '#6f8fae', hairColor: m ? '#2a211c' : '#3b2a22', brow: m ? 2 : 0,
    face: { nose: null, mouth: null, eyes: null, ears: null }, sliders: {}, wear: null, tints: {}, glow: null };
}

export function newSave() {
  const s = {
    v: 1, created: Date.now(),
    character: defaultCharacter('female'),
    car: { model: 'board_sport', paint: '#a3121f' },          // the summoned ride is a hover board (vehicles.js BOARDS)
    level: 1, xp: 0, credits: 500, alloy: 20,
    inventory: [], equipped: [null, null, null],
    stats: { kills: 0, precision: 0, deaths: 0, caches: 0, generators: 0, drones: 0, brutes: 0, shots: 0, hits: 0, distance: 0, carDistance: 0, time: 0, visited: [], creditsEarned: 0, bestStreak: 0 },
    contracts: [], contractsDone: 0,
    settings: { ...DEFAULT_SETTINGS },
    lastDest: null,
  };
  const starters = [makeWeapon('auto', 1, 10), makeWeapon('handcannon', 1, 10), makeWeapon('rocket', 0, 10)];
  starters[0].name = 'Ashen Oath'; starters[1].name = 'Last Lantern'; starters[2].name = 'Iron Verdict';
  s.inventory.push(...starters);
  s.equipped = starters.map(w => w.uid);
  grantArmory(s);
  refreshContracts(s);
  return s;
}

// One-time armoury delivery: every kinetic and horror archetype (added after the first saves existed), at the power of
// the best gun the player already owns. Bumping ARMORY_V delivers whatever newer archetypes appear later.
const ARMORY_V = 2;
export function grantArmory(s) {
  if ((s.armoryV || 0) >= ARMORY_V) return [];
  const have = new Set(s.inventory.map(w => w.arch));
  const power = Math.max(10, ...s.inventory.map(w => w.power || 0));
  const out = [];
  for (const [k, A] of Object.entries(ARCHETYPES)) {
    if (A.cls === 'energy' || have.has(k)) continue;
    const w = makeWeapon(k, A.cls === 'horror' ? 2 : 1, power); w.keep = true;      // never auto-dismantled
    s.inventory.push(w); out.push(w);
  }
  s.armoryV = ARMORY_V;
  return out;
}

export function refreshContracts(s) {
  while (s.contracts.length < 3) {
    const pool = CONTRACT_POOL.filter(c => !s.contracts.some(x => x.id === c.id));
    const c = pool[Math.floor(Math.random() * pool.length)];
    const n = c.n[Math.floor(Math.random() * c.n.length)];
    s.contracts.push({ id: c.id, text: c.text.replace('{n}', n), n, p: 0, reward: c.reward + n * 10, done: false });
  }
}

export function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (!s || s.v !== 1) return null;
    s.settings = { ...DEFAULT_SETTINGS, ...s.settings };
    if (!s.character || s.character.v !== 3) {
      // new customisable base bodies: keep the frame, start from the default look
      s.character = defaultCharacter((s.character && s.character.body) || 'female');
    }
    s.stats = { ...newSave().stats, ...s.stats };
    // the player's summoned vehicle became a hover board: old car saves keep their paint and map sport/utility
    if (!s.car || typeof s.car !== 'object') s.car = { model: 'board_sport', paint: '#a3121f' };
    if (!/^board_/.test(s.car.model)) s.car.model = s.car.model === 'car_utility' ? 'board_utility' : 'board_sport';
    if (!/^#[0-9a-f]{6}$/i.test(s.car.paint || '')) s.car.paint = '#a3121f';
    s.armoryDelivered = grantArmory(s).length;           // new weapon classes reach existing saves
    if (s.vanthos) s.vanthos = { shards: [], bosses: [], runs: 0, best: null, logs: [], ...s.vanthos };
    if (s.arena) s.arena = arenaRecord(s.arena);
    return s;
  } catch (e) { return null; }
}

// Shellbreak (worlds/arena) service record + the last match settings
export const ARENA_CFG = { difficulty: 'normal', size: 6, limit: 50, minutes: 10 };
export function arenaRecord(a = {}) {
  return { matches: 0, wins: 0, losses: 0, draws: 0, elims: 0, deaths: 0, assists: 0, bestElims: 0, bestStreak: 0, time: 0, ...a, cfg: { ...ARENA_CFG, ...(a.cfg || {}) } };
}

export function save(s) {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* storage unavailable */ }
}

export function wipe() { try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ } }

export const xpForLevel = l => 600 + l * 250;

export function weaponStats(w) {
  const A = ARCHETYPES[w.arch], R = RARITY[w.rarity], st = w.stats;
  const has = p => w.perks.includes(p);
  return {
    dmg: A.dmg * R.mult * st.dmg * (1 + w.power / 200),
    rpm: A.rpm * st.rpm,
    mag: Math.round(A.mag * (has('overflow') ? 1.4 : 1)),
    reserve: A.reserve,
    reload: A.reload * (has('quickdraw') ? .65 : 1) / (0.9 + st.handling * .1),
    range: A.range * st.range,
    spread: A.spread * (has('steady') ? .6 : 1) / st.stability,
    crit: A.crit * (has('deadeye') ? 1.25 : 1),
  };
}
