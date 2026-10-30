// Static game data: weapon archetypes, rarities, perks, destinations, contracts.
export const RARITY = [
  { id: 'common', name: 'Common', color: '#d8d8d8', mult: 1.0, perks: 0 },
  { id: 'uncommon', name: 'Uncommon', color: '#5fd068', mult: 1.06, perks: 1 },
  { id: 'rare', name: 'Rare', color: '#4fa3ff', mult: 1.12, perks: 1 },
  { id: 'legendary', name: 'Legendary', color: '#b46cff', mult: 1.2, perks: 2 },
  { id: 'exotic', name: 'Exotic', color: '#ffcf3f', mult: 1.3, perks: 3 },
];

// dmg per bullet at power parity; rpm; mag; reserve; reload s; range m (falloff start); spread deg; crit mult
export const ARCHETYPES = {
  auto: { name: 'Auto Rifle', model: 'gun_auto', sound: 'auto', dmg: 15, rpm: 600, mag: 36, reserve: 360, reload: 2.0, range: 32, spread: 1.2, crit: 1.6, auto: true, zoom: 1.35, slot: 0 },
  pulse: { name: 'Pulse Rifle', model: 'gun_pulse', sound: 'pulse', dmg: 19, rpm: 450, burst: 3, burstRpm: 900, mag: 30, reserve: 300, reload: 2.1, range: 38, spread: .7, crit: 1.7, auto: true, zoom: 1.4, slot: 0 },
  scout: { name: 'Scout Rifle', model: 'gun_scout', sound: 'scout', dmg: 42, rpm: 220, mag: 15, reserve: 150, reload: 2.2, range: 60, spread: .25, crit: 1.8, auto: false, zoom: 2.2, slot: 0 },
  handcannon: { name: 'Hand Cannon', model: 'gun_handcannon', sound: 'handcannon', dmg: 58, rpm: 140, mag: 11, reserve: 110, reload: 1.8, range: 30, spread: .5, crit: 2.0, auto: false, zoom: 1.3, slot: 1 },
  shotgun: { name: 'Shotgun', model: 'gun_shotgun', sound: 'shotgun', dmg: 22, pellets: 8, rpm: 70, mag: 6, reserve: 40, reload: 2.6, range: 10, spread: 5.5, crit: 1.2, auto: false, zoom: 1.15, slot: 1 },
  sniper: { name: 'Sniper Rifle', model: 'gun_sniper', sound: 'sniper', dmg: 180, rpm: 60, mag: 4, reserve: 24, reload: 2.8, range: 140, spread: .05, crit: 2.6, auto: false, zoom: 4.5, slot: 1 },
  rocket: { name: 'Rocket Launcher', model: 'gun_rocket', sound: 'rocket', dmg: 420, rpm: 40, mag: 1, reserve: 6, reload: 2.4, range: 200, spread: 0, crit: 1.0, auto: false, zoom: 1.5, slot: 2, projectile: true, splash: 6 },
};
export const SLOT_NAMES = ['Primary', 'Special', 'Heavy'];

export const PERKS = {
  overflow: { name: 'Overflow', desc: 'Magazine +40%.' },
  rampage: { name: 'Rampage', desc: 'Kills grant +15% damage, stacking 3x for 4s.' },
  quickdraw: { name: 'Quickload', desc: 'Reload 35% faster.' },
  explosive: { name: 'Shrapnel Rounds', desc: 'Precision hits deal bonus splash damage.' },
  vampire: { name: 'Siphon', desc: 'Kills restore 25% health.' },
  steady: { name: 'Gyro Stock', desc: 'Spread and recoil reduced 40%.' },
  deadeye: { name: 'Deadeye', desc: 'Precision damage +25%.' },
  autoload: { name: 'Autoloader', desc: 'Stowed weapons reload themselves.' },
  frenzy: { name: 'Overclock', desc: 'Fire rate +20% while shields are down.' },
};

const PREFIX = ['Ashen', 'Gilded', 'Silent', 'Iron', 'Hollow', 'Vesper', 'Last', 'Bright', 'Feral', 'Distant', 'Saint', 'Ninth', 'Grey', 'Ember', 'Cold', 'Long', 'Red', 'Sable', 'Quiet', 'True'];
const NOUN = ['Oath', 'Lantern', 'Verdict', 'Heron', 'Requiem', 'Anvil', 'Meridian', 'Covenant', 'Thorn', 'Halcyon', 'Tide', 'Cinder', 'Harbinger', 'Psalm', 'Warden', 'Vigil', 'Gambit', 'Spire', 'Nocturne', 'Arbiter'];
export const EXOTIC_NAMES = { auto: 'Sunforge Litany', pulse: 'Ninefold Choir', scout: 'Farsight Herald', handcannon: 'The Undertaker', shotgun: 'Gravedigger’s Hymn', sniper: 'Pale Horizon', rocket: 'Starfall Engine' };

export function weaponName(arch, rarity, rnd) {
  if (rarity === 4) return EXOTIC_NAMES[arch];
  return PREFIX[Math.floor(rnd() * PREFIX.length)] + ' ' + NOUN[Math.floor(rnd() * NOUN.length)];
}

export const SHADERS = [
  { id: 'bone', name: 'Bone Ceramic', body: '#e8e2d4' }, { id: 'gunmetal', name: 'Gunmetal', body: '#3a3f47' },
  { id: 'brass', name: 'Old Brass', body: '#b58a3c' }, { id: 'crimson', name: 'Crimson Lacquer', body: '#8c1d26' },
  { id: 'midnight', name: 'Midnight', body: '#1b2440' }, { id: 'jade', name: 'Jade', body: '#2f6b55' },
  { id: 'ivory', name: 'Ivory & Ink', body: '#f6f1e6' }, { id: 'rust', name: 'Rust Belt', body: '#7a3f22' },
];

export const ARMOR_COLORS = ['#e8e2d4', '#3a3f47', '#1b2440', '#8c1d26', '#2f6b55', '#b58a3c', '#6a4fa0', '#d9d4c8', '#14161a', '#c76a2a', '#2a6fa8', '#7a7f87'];
export const GLOW_COLORS = ['#1ad8ff', '#ffae2f', '#ff2fa8', '#7dffb0', '#b46cff', '#ff4a3d', '#ffffff', '#ffe066'];
export const PAINTS = ['#a3121f', '#2a4f7a', '#e8e2d4', '#1c1f24', '#c79a45', '#2f6b55', '#6a4fa0', '#d96a1b', '#8a9099', '#0f4b5c'];

// Destinations. Earth is the city hub; every other world is an endlessly generated frontier.
export const DESTINATIONS = [
  { id: 'earth', name: 'Earth', region: 'New Meridian City', kind: 'city', level: 1, power: 0, orb: 'radial-gradient(circle at 35% 35%,#7fc4ff,#1e5aa8 45%,#0a2142 70%)',
    desc: 'Humanity’s last great city. Restock, trade with the Quartermaster at the spaceport and clear the incursion in the outer districts.' },
  { id: 'ares', name: 'Ares Verge', region: 'Red Dust Expanse', kind: 'planet', level: 4, power: 20, seed: 1301,
    orb: 'radial-gradient(circle at 35% 35%,#ffb27a,#b2481e 45%,#3d1308 72%)',
    desc: 'Wind-carved mesas and buried colony ruins. Raider cells dig in around stolen generators.',
    sky: ['#e9a46c', '#7a3a24'], fog: '#c9875c', ground: 'sand', rock: '#a0604a', groundTint: '#d39a6e', sun: '#ffd2a0', sunEl: .45,
    amp: 26, freq: .006, flora: 'rock', crystal: 2, plants: -1, hazard: null },
  { id: 'vesper', name: 'Vesper', region: 'The Pale Shelf', kind: 'planet', level: 8, power: 60, seed: 2207,
    orb: 'radial-gradient(circle at 35% 35%,#f2fbff,#8fb8d0 45%,#2a4a62 72%)',
    desc: 'A frozen moon of glacier fields and frost-split ridges. Visibility is low; listen for drones.',
    sky: ['#cfe6f5', '#5f86a3'], fog: '#c3d9e8', ground: 'ice', rock: '#7d8fa0', groundTint: '#e8f2f8', sun: '#e8f4ff', sunEl: .3,
    amp: 34, freq: .005, flora: 'rock', crystal: 1, plants: -1, hazard: null },
  { id: 'thalassa', name: 'Thalassa Reach', region: 'Glowroot Basin', kind: 'planet', level: 12, power: 100, seed: 3119,
    orb: 'radial-gradient(circle at 35% 35%,#9effd0,#2c8a6a 45%,#0b2f2a 72%)',
    desc: 'A humid jungle moon lit by bioluminescent flora. Heavy patrols guard the old relay towers.',
    sky: ['#86c9b4', '#1f4a46'], fog: '#5f9c8a', ground: 'moss', rock: '#5a6a5a', groundTint: '#7fa860', sun: '#e6ffd8', sunEl: .55,
    amp: 22, freq: .008, flora: 'plants', crystal: -1, plants: 0, hazard: null },
  { id: 'pyrrhos', name: 'Pyrrhos', region: 'Cinder Rift', kind: 'planet', level: 16, power: 140, seed: 4421,
    orb: 'radial-gradient(circle at 35% 35%,#ffcf7a,#c23a10 40%,#1c0805 72%)',
    desc: 'A volcanic world under a burning sky. The heaviest resistance holds the forge camps.',
    sky: ['#d06a3a', '#2a0d08'], fog: '#5a2618', ground: 'rock', rock: '#3b302c', groundTint: '#5a4a44', sun: '#ffb070', sunEl: .25,
    amp: 40, freq: .006, flora: 'rock', crystal: 2, plants: 2, hazard: 'lava' },
  { id: 'nyx', name: 'Nyx Expanse', region: 'Shardfields', kind: 'planet', level: 20, power: 180, seed: 5503,
    orb: 'radial-gradient(circle at 35% 35%,#e0b8ff,#6a3aa8 45%,#1a0d33 72%)',
    desc: 'Endless violet plains of singing crystal under a twin-moon night. Elite cells only.',
    sky: ['#6a4f9a', '#120a24'], fog: '#3a2a5c', ground: 'sand', rock: '#4a3f60', groundTint: '#7a6a9a', sun: '#d9c8ff', sunEl: .2,
    amp: 18, freq: .007, flora: 'crystal', crystal: 0, plants: 1, hazard: null },
];

export const CONTRACT_POOL = [
  { id: 'kills', text: 'Defeat {n} hostiles', n: [20, 35, 50], reward: 600 },
  { id: 'precision', text: 'Land {n} precision kills', n: [10, 15, 25], reward: 700 },
  { id: 'caches', text: 'Open {n} supply caches', n: [3, 5], reward: 650 },
  { id: 'outposts', text: 'Destroy {n} raider generators', n: [2, 3, 4], reward: 900 },
  { id: 'brutes', text: 'Defeat {n} Brutes', n: [3, 6], reward: 800 },
  { id: 'drones', text: 'Shoot down {n} drones', n: [6, 10], reward: 650 },
  { id: 'distance', text: 'Drive {n} km in a hover car', n: [2, 4], reward: 500 },
  { id: 'earth', text: 'Clear {n} hostiles on Earth', n: [12, 20], reward: 700 },
];

export const TIPS = [
  'Hold Right Mouse to aim down sights. Precision hits on heads deal heavy bonus damage.',
  'Shields recharge after a few seconds out of fire. Break line of sight to recover.',
  'Data cores drop from defeated enemies. Their glow shows the rarity of the weapon inside.',
  'Press V on Earth or any planet to summon your hover car.',
  'The Gunsmith Bench upgrades weapon power with alloy recovered from dismantled gear.',
  'Raider generators power their outposts. Destroy them to finish an outpost and loot the cache.',
  'Every frontier world is generated endlessly in all directions. Push further for richer caches.',
  'Brutes charge when wounded. Keep moving and aim for the glowing visor.',
  'Your ship is your home: use the captain’s chair to travel, the wardrobe pod to restyle your armour.',
];
