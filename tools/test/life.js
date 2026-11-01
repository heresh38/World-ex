// Life on Earth (meridian/population.js, npcnav.js, fauna.js): loads Earth, reports the walk graph and its places,
// then runs the crowd through the day (08:00, 12:30, 18:00, 23:30, 03:00) on the heritage avenue and reports the crowd
// size, goal mix and state distribution (walking / sitting / talking / queueing / at platforms) per hour; checks that
// people sit down, talk in groups, birds take off when the player sprints past or fires, and cats bolt; measures
// Population.update (fauna included) and saves screenshots to test-out/life/. Fails on page errors.
// Two browser sessions (day, then evening + night): each hour change rebuilds lighting / ambience state and one long
// software-rendered session can outgrow the shared memory limit.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/life.js
// NOSHOTS=1 skips the screenshots (numbers only); PHASE=day|night runs one session only.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/life';
const NOSHOTS = !!process.env.NOSHOTS, PHASE = process.env.PHASE || 'all';
fs.mkdirSync(OUT, { recursive: true });
const errs = [], fails = [];
const check = (ok, what, info = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + what + (info !== '' ? ' · ' + (typeof info === 'string' ? info : JSON.stringify(info)) : '')); if (!ok) fails.push(what); };
const SPOT = [-30, 0, -106];             // on the heritage avenue

// one browser with Earth loaded; the page never renders on its own (we step the world, and every screenshot renders
// exactly one frame first: software rendering piling up frames balloons Chrome's memory)
async function session(fn) {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--mute-audio'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400), (e.stack || '').split('\n').slice(0, 4).join(' | ')); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; window.__MAXTEX = 1024; });
  const ev = (f, arg) => p.evaluate(f, arg);
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); g.startGame(true); });
  await waitPlay();
  const t0 = Date.now();
  await ev(() => { window.__game.cineTime = 99; window.__game.travel('earth'); });
  await waitPlay();
  console.log('earth load seconds', Math.round((Date.now() - t0) / 1000));
  await ev(() => { const g = window.__game, r = g.renderer; g.cineTime = null; g.paused = true; g.clock.paused = true; if (g.viewmodel) g.viewmodel.active = false; r.__render = r.render; r.render = () => {}; });
  const T = {
    ev,
    shot: async n => {
      if (NOSHOTS) return;
      await ev(() => { const g = window.__game, r = g.renderer; r.__render.call(r, g.scene, g.camera); });
      await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 84, timeout: 300000 });
      console.log('shot', n);
    },
    // step the world with a fixed dt, the player held at `at`
    sim: (secs, opt = {}) => ev(([secs, opt]) => {
      const g = window.__game, P = g.player, pop = g.world.population;
      if (opt.at) { P.pos.set(...opt.at); P.vel.set(0, 0, 0); P.avatar.root.position.copy(P.pos); }
      if (opt.hour !== undefined) g.clock.set(opt.hour);
      if (opt.reseed) pop.seeded = false;
      pop.perf = { ms: 0, n: 0 };
      const n = Math.round(secs * 30), t = performance.now();
      for (let i = 0; i < n; i++) { if (opt.at) { P.pos.set(...opt.at); P.vel.set(0, 0, 0); } g.update(1 / 30); }
      return { frameMs: +((performance.now() - t) / n).toFixed(2), heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null, ...pop.stats(), fauna: pop.fauna ? pop.fauna.stats() : null };
    }, [secs, opt]),
    // a fixed camera (station framing keeps it there while the world steps)
    cam: (pos, look) => ev(([pos, look]) => {
      const g = window.__game, V = g.camera.position.constructor, c = g.camera; g.stationId = 'test';
      c.position.set(...pos); c.lookAt(...look); c.fov = 55; c.updateProjectionMatrix(); c.updateMatrixWorld();
      g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 55, t0: 0 };
      const w = g.world; if (w.flora) w.flora.update(c, 0, true); if (w.downtown) w.downtown.update(c, 0, true);
    }, [pos, look]),
    step: (secs, at) => ev(([secs, at]) => { const g = window.__game, P = g.player; for (let i = 0; i < Math.round(secs * 30); i++) { if (at) { P.pos.set(...at); P.vel.set(0, 0, 0); } g.update(1 / 30); } }, [secs, at]),
    free: () => ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; }),
  };
  try { await fn(T); } finally { await b.close(); }
}

const res = {};
const hours = async (T, list) => {
  for (const h of list) {
    await T.sim(1, { at: SPOT, hour: h, reseed: true });
    res[h] = await T.sim(45, { at: SPOT });
    console.log('hour', h, JSON.stringify(res[h]));
  }
};

async function day(T) {
  const { ev, shot, sim, cam, step } = T;
  const nav = await ev(() => { const w = window.__game.world, P = w.population; return { ...P.nav.stats(), navMs: Math.round(P.navMs), fauna: !!P.fauna }; });
  console.log('nav', JSON.stringify(nav));
  check(nav.main > 1000, 'walk graph covers the city', nav.main);
  check(nav.seat > 100 && (nav.seatKinds.cafe || 0) > 20, 'seats: benches, cafe chairs, planters', nav.seatKinds);
  check(nav.door > 80 && (nav.doorKinds.work || 0) > 10 && (nav.doorKinds.home || 0) > 20, 'doors (work / home / shop / hotel)', nav.doorKinds);
  check(nav.platform >= 20 && nav.kiosk >= 4 && nav.meet >= 10, 'platform spots, kiosks, meeting points', { platform: nav.platform, kiosk: nav.kiosk, meet: nav.meet });
  check(nav.fauna, 'fauna loaded (fauna.glb)');
  await hours(T, [8, 12.5]);
  const L = res[12.5];
  check((L.states.sit || 0) + (L.states.settle || 0) >= 4, 'people sit down at lunch', L.states);
  check(L.states.flee === undefined, 'nobody panics without a reason');

  // perf at lunch on the heritage avenue (same spot / steps as the baseline measurement of the old crowd)
  await sim(1, { at: [-30, 0, -104], hour: 12.5, reseed: true });
  await sim(1, { at: [-30, 0, -104] });
  const perf = await sim(5, { at: [-30, 0, -104] });
  console.log('PERF lunch', JSON.stringify({ popMs: perf.perfMs, frameMs: perf.frameMs, active: perf.active, near80: perf.near80, heapMB: perf.heapMB }));

  // ---- screenshots and fauna checks at lunch
  await sim(30, { at: SPOT, hour: 12.6, reseed: true });
  await cam([-62, 2.1, -108.5], [10, .8, -110]); await step(1.5, SPOT); await shot('01_heritage_lunch');
  const cafe = await ev(() => { const pop = window.__game.world.population; const q = pop.peds.filter(q => q.state === 'sit' && q.spot && q.spot.kind === 'cafe').sort((a, b) => a.d - b.d)[0]; return q ? [q.pos.x, q.pos.z, q.yaw] : null; });
  check(!!cafe, 'someone sits at a cafe table at lunch');
  if (cafe) { const [x, z, yaw] = cafe, sx = Math.cos(yaw), sz = -Math.sin(yaw); await cam([x + sx * 3.4 + Math.sin(yaw) * 2.2, 1.6, z + sz * 3.4 + Math.cos(yaw) * 2.2], [x, .8, z]); await step(.6, SPOT); await shot('02_cafe'); }
  const grp = await ev(() => { const pop = window.__game.world.population; const G = pop.groups.filter(G => G.members.length >= 2).sort((a, b) => a.members[0].d - b.members[0].d)[0]; return G ? [G.cx, G.cz, G.members.length, G.members[0].pos.y] : null; });
  if (grp) { const [x, z, n, y] = grp; await cam([x + 3.2, y + 1.65, z + 2.6], [x, y + 1.2, z]); await step(.5, SPOT); await shot('03_chat_' + n); }
  else console.log('no talking group near the player for the screenshot');
  const plat = await ev(() => { const pop = window.__game.world.population; const q = pop.peds.find(q => q.state === 'platform'); return q ? [q.pos.x, q.pos.z] : null; });
  if (plat) { await cam([plat[0] + 9, 2.2, plat[1] + (plat[1] < -220 ? -4 : 4)], [plat[0], 1, plat[1]]); await step(.4, SPOT); await shot('04_platform'); }

  // birds: a flock on the ground near the player; then sprint at it
  const flock = await ev(() => {
    const g = window.__game, F = g.world.population.fauna; if (!F) return null;
    for (let k = 0; k < 60; k++) g.update(1 / 30);
    const f = F.flocks.filter(f => f.active && f.state === 'ground').sort((a, b) => Math.hypot(a.x - g.player.pos.x, a.z - g.player.pos.z) - Math.hypot(b.x - g.player.pos.x, b.z - g.player.pos.z))[0];
    return f ? [f.x, f.y, f.z, F.flocks.indexOf(f)] : null;
  });
  check(!!flock, 'a flock of birds pecks on the ground nearby', flock);
  if (flock) {
    const [x, y, z, fi] = flock, stand = [x + 14, 0, z + 1];
    await cam([x + 3.2, y + 1.3, z + 2.4], [x, y + .1, z]); await step(.5, stand); await shot('05_birds_ground');
    const air = await ev(([x, z, fi]) => {
      const g = window.__game, P = g.player, F = g.world.population.fauna, f = F.flocks[fi];
      let px = x + 14; const pz = z + 1;
      for (let i = 0; i < 45; i++) { px -= 8.6 / 30; P.pos.set(px, 0, pz); P.vel.set(-8.6, 0, 0); P.running = true; g.update(1 / 30); }
      P.running = false; P.vel.set(0, 0, 0);
      return f.birds.filter(b => b.state === 'air' || b.state === 'roof').length / f.birds.length;
    }, [x, z, fi]);
    check(air >= .5, 'birds take off when the player sprints at them', air);
    await cam([x + 6, 1.5, z + 5], [x, 5, z]); await step(.2); await shot('06_birds_flight');
  }
  const shotRes = await ev(() => {
    const g = window.__game, F = g.world.population.fauna; if (!F) return null;
    const f = F.flocks.find(f => f.active && f.state === 'ground'); if (!f) return 'none';
    g.world.onGunshot(new (g.camera.position.constructor)(f.x + 12, 1.5, f.z));
    for (let i = 0; i < 20; i++) g.update(1 / 30);
    return f.birds.filter(b => b.state === 'air' || b.state === 'roof').length / f.birds.length;
  });
  check(shotRes === 'none' || shotRes >= .5, 'a gunshot scatters the birds', shotRes);
  // cats
  const cat = await ev(() => {
    const g = window.__game, F = g.world.population.fauna; if (!F || !F.cats.length) return null;
    for (let i = 0; i < 300 && !F.cats.some(c => c.state !== 'off' && c.state !== 'gone'); i++) g.update(1 / 30);
    const c = F.cats.find(c => c.state !== 'off' && c.state !== 'gone'); if (!c) return { found: false, st: F.stats() };
    return { found: true, x: c.pos.x, z: c.pos.z, yaw: c.yaw, i: F.cats.indexOf(c) };
  });
  check(cat && cat.found, 'a stray cat is about', cat);
  if (cat && cat.found) {
    await cam([cat.x + 2.2, .9, cat.z + 1.8], [cat.x, .2, cat.z]);
    await ev(i => { const g = window.__game, c = g.world.population.fauna.cats[i]; g.player.pos.set(c.pos.x + 30, 0, c.pos.z + 30); for (let k = 0; k < 20; k++) g.update(1 / 30); }, cat.i);
    await shot('07_cat');
    const bolted = await ev(i => {
      const g = window.__game, P = g.player, c = g.world.population.fauna.cats[i];
      P.pos.set(c.pos.x + 2.5, 0, c.pos.z + 1); P.vel.set(-5, 0, 0); P.running = true;
      let seen = false; for (let k = 0; k < 40; k++) { g.update(1 / 30); if (c.state === 'bolt' || c.state === 'hide' || c.state === 'gone') seen = true; }
      P.running = false; return { seen, state: c.state };
    }, cat.i);
    check(bolted.seen, 'the cat bolts when approached', bolted);
  }
}

async function night(T) {
  const { shot, sim, cam, step, free } = T;
  await hours(T, [18, 23.5, 3]);
  await free();
  await sim(1, { at: SPOT, hour: 20, reseed: true }); await sim(25, { at: SPOT });
  await cam([-62, 2.1, -108.5], [10, .8, -110]); await step(1, SPOT); await shot('08_heritage_evening');
  await free();
  await sim(1, { at: [-160, 0, 60], hour: 3, reseed: true }); await sim(25, { at: [-160, 0, 60] });
  await cam([-163, 1.7, 100], [-163, 1.5, 0]); await step(1, [-160, 0, 60]); await shot('09_night_street');
}

(async () => {
  if (PHASE !== 'night') await session(day);
  if (PHASE !== 'day') await session(night);
  if (PHASE === 'all') {
    const L = res[12.5], N3 = res[3], E = res[18];
    check(L.active >= 0.8 * L.target && L.active > 2 * N3.active, 'crowd follows the clock (lunch busy, 3 am thin)', { lunch: L.active, night: N3.active, evening: E.active, morning: res[8].active });
    const H = [8, 12.5, 18, 23.5, 3];
    check(H.some(h => res[h].groups > 0), 'conversation groups form', H.map(h => res[h].groups));
    check((res[8].goals.work || 0) > (res[23.5].goals.work || 0), 'morning commute heads for work doors', { morning: res[8].goals, late: res[23.5].goals });
    check(H.some(h => (res[h].states.queue || 0) + (res[h].states.platform || 0) + (res[h].states.browse || 0) > 0), 'queues / platforms / shop windows in use',
      H.map(h => ({ q: res[h].states.queue || 0, pl: res[h].states.platform || 0, br: res[h].states.browse || 0 })));
    check(res[3].states.flee === undefined, 'nobody panics at night without a reason');
  }
  console.log('page errors:', errs.length);
  console.log(fails.length ? 'FAILED: ' + fails.join(', ') : 'ALL PASS');
  process.exit(errs.length || fails.length ? 1 : 0);
})().catch(e => { console.error('LIFE TEST FAILED', e.message); process.exit(2); });
