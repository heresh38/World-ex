// Earth's positional ambience (src/core/soundscape.js): emitters for the park fountains and the rotunda pool, cafe
// terraces on the heritage avenue and the plazas (murmur, cups, soft music in the evening), the two construction sites
// (working hours), both trams (hum, rail joints, the bell when they leave a stop), the highways, the river quays, and
// birds by day / crickets at night in the parks, suburbs and villages. The distant city bed (audio.cityMix) follows the
// hour and how far into the city the listener is. Only the nearest few emitters play (4 voices on touch, 6 otherwise).
import { Soundscape } from '../../core/soundscape.js';
import { SKY } from './daynight.js';
import { RIVER_Z, RIVER_W, RIVER_BANK, CITY_EDGE, VILLAGES } from './layout.js';

const smooth = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);
const window_ = (a, b, ramp = .75) => h => Math.min(smooth((h - a) / ramp + 1), smooth((b - h) / ramp + 1));

export class EarthAmbience {
  constructor(world) {
    this.w = world; this.g = world.g;
    const S = this.s = new Soundscape(this.g.audio, { voices: this.g.renderer.touch ? 4 : 6 });
    const night = () => SKY.night.value;
    // fountains
    for (const f of world.fountainSpots || []) S.add({ kind: 'fountain', pos: { x: f.x, y: 1, z: f.z }, r: 45, gain: .7 });
    // cafe terraces: one emitter per cluster of tables
    const dt = world.downtown, cl = new Map();
    for (const it of (dt && dt.furn.DT_cafe) || []) {
      const x = it.m.elements[12], z = it.m.elements[14], k = Math.round(x / 30) + ',' + Math.round(z / 30);
      const c = cl.get(k) || { x: 0, z: 0, n: 0 }; c.x += x; c.z += z; c.n++; cl.set(k, c);
    }
    const open = window_(7.5, 23.5, 1), music = window_(17.5, 23.5, 1);
    for (const c of cl.values()) S.add({ kind: 'cafe', pos: { x: c.x / c.n, y: 1.2, z: c.z / c.n }, r: 42, gain: .55 + Math.min(.35, c.n * .05), active: open, music: () => music(this.g.clock.hour) });
    // construction sites (crane foot) during working hours
    for (const cr of (dt && dt.cranes) || []) S.add({ kind: 'construction', pos: { x: cr.jib.position.x, y: 6, z: cr.jib.position.z }, r: 110, gain: .8, active: window_(7, 17.5, .5) });
    // trams follow their model
    for (const t of (dt && dt.trams) || []) S.add({ kind: 'tram', tram: t, pos: p => { p.x = t.o.position.x; p.y = 1.5; p.z = t.z; return p; }, r: 90, gain: .9, active: window_(5.5, 24.6, .5) });
    // highways: a source every ~140 m along each road outside the city
    for (const r of world.map.roads || []) {
      let acc = 1e9;
      for (let i = 1; i < r.pts.length; i++) {
        const a = r.pts[i], b = r.pts[i - 1]; acc += Math.hypot(a.x - b.x, a.z - b.z);
        if (acc < 140) continue; acc = 0;
        if (Math.abs(a.x) < CITY_EDGE && Math.abs(a.z) < CITY_EDGE) continue;
        S.add({ kind: 'traffic', pos: { x: a.x, y: a.y + 1, z: a.z }, r: 160, gain: .55, active: h => .35 + .65 * window_(6, 22.5, 1.5)(h) });
      }
    }
    // the river: lapping along both quays
    for (let x = -CITY_EDGE + 30; x < CITY_EDGE - 20; x += 70) for (const s of [-1, 1]) S.add({ kind: 'river', pos: { x, y: -1, z: RIVER_Z + s * (RIVER_W + RIVER_BANK - 2) }, r: 40, gain: .5 });
    // birds and crickets: parks, suburbs, villages
    for (const p of world.parkSpots || []) S.add({ kind: 'nature', pos: { x: p.x, y: 4, z: p.z }, r: 70, gain: .7, night });
    for (const p of world.suburbSpots || []) S.add({ kind: 'nature', pos: { x: p.x, y: 4, z: p.z }, r: 70, gain: .6, night });
    for (const v of VILLAGES) S.add({ kind: 'nature', pos: { x: v.pos[0], y: world.map.height(v.pos[0], v.pos[1]) + 4, z: v.pos[1] }, r: 140, gain: .7, night });
    this.mixT = 0;
  }

  update(dt) {
    const g = this.g, cam = g.camera.position, A = g.audio;
    const e = g.camera.matrixWorld.elements, yaw = Math.atan2(e[8], e[10]);     // audio.listener's convention
    this.s.update(dt, cam, yaw, g.clock ? g.clock.hour : 12);
    this.mixT -= dt;
    if (this.mixT <= 0) {
      this.mixT = 1;
      const day = 1 - SKY.night.value, ed = Math.max(Math.abs(cam.x), Math.abs(cam.z));
      A.cityMix && A.cityMix(day, SKY.night.value * .8 + Math.min(1, Math.max(0, cam.y - 30) / 120) * .6, 1 - smooth((ed - CITY_EDGE) / 400));
    }
  }

  stats() { return this.s.stats(); }
  dispose() { this.s.dispose(); }
}
