// In-game time of day, shared by lighting, NPC routines and ambience. One full day lasts DAY_SECONDS of real time
// (or settings.dayMinutes, Engineering terminal > Graphics > Day length).
// API: hour (0-24 float), day (count), daylight() 0..1, isNight(), between(a, b), set(hour), paused, speed (multiplier),
// label() 'HH:MM'. Earth's lighting (src/worlds/meridian/daynight.js) and ambience follow it.
// Persisted in save.clock so a reload keeps the time. Tests: g.clock.set(21); g.clock.paused = true.
export const DAY_SECONDS = 40 * 60;           // 40 real minutes per in-game day

export class Clock {
  constructor(save) {
    this.save = save;
    const c = save.clock || (save.clock = { hour: 9.5, day: 1 });
    this.hour = Number.isFinite(c.hour) ? c.hour : 9.5;
    this.day = c.day || 1;
    this.speed = 1; this.paused = false;
  }

  update(dt) {
    if (this.paused) return;
    const len = (this.save.settings && this.save.settings.dayMinutes) * 60 || DAY_SECONDS;
    this.hour += dt * this.speed * 24 / len;
    if (this.hour >= 24) { this.hour -= 24; this.day++; }
    this.save.clock.hour = this.hour; this.save.clock.day = this.day;
  }

  set(hour) { this.hour = ((hour % 24) + 24) % 24; this.save.clock.hour = this.hour; }

  // 0 at night, 1 at full day, smooth ramps around dawn (5:30-7:30) and dusk (18:30-20:30)
  daylight() {
    const h = this.hour, s = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);
    return Math.min(s((h - 5.5) / 2), s((20.5 - h) / 2));
  }

  isNight() { return this.daylight() < .15; }

  // true while the hour lies in [a, b), wrapping past midnight (between(22, 6))
  between(a, b) { const h = this.hour; return a <= b ? h >= a && h < b : h >= a || h < b; }

  label() { const h = Math.floor(this.hour), m = Math.floor((this.hour - h) * 60); return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0'); }
}
