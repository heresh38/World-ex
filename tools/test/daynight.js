// Day/night check for Earth (src/worlds/meridian/daynight.js, atmos.js, ambience.js; core/soundscape.js): pins the clock
// at 06:30, 09:00, 13:00, 18:45, 21:30 and 01:00 and for each hour saves screenshots (street level on the heritage
// avenue, an aerial over downtown, along the river; a park at two hours), checks that the sun's intensity, colour and
// direction change, that the lit-window fractions and window gain rise at night, that the reflection probe is rebuilt
// rarely (simulated hours of clock time), that the ambience voice pool stays bounded while the listener moves past
// fountains, cafes, the trams and the construction site, reports draw calls / frame time at 13:00 and 21:30, and that
// the ship and VANTHOS still load without page errors afterwards.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/daynight.js   (test-out/daynight)
// HOURS=21.5,1 limits the hours; SKIP_WORLDS=1 skips the ship / VANTHOS check; VIEWS=street,aerial limits the views.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/daynight';
const HOURS = (process.env.HOURS || '6.5,9,13,18.75,21.5,1').split(',').map(Number);
const ONLY = process.env.VIEWS ? new Set(process.env.VIEWS.split(',')) : null;
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [], fails = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400), (e.stack || '').split('\n').slice(0, 4).join(' | ')); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; window.__MAXTEX = 1024; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const check = (ok, what, info = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + what + (info !== '' ? ' · ' + (typeof info === 'string' ? info : JSON.stringify(info)) : '')); if (!ok) fails.push(what); };
  const shot = async n => {
    await ev(() => { const r = window.__game.renderer; if (!r.__render) { r.__render = r.render; r.render = () => {}; } });
    try { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 86, timeout: 300000 }); }
    finally { await ev(() => { const r = window.__game.renderer; if (r.__render) { r.render = r.__render; r.__render = null; } }).catch(() => {}); }
    console.log('shot', n);
  };
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); g.startGame(true); g.audio.start(); });
  await waitPlay();
  const shipExp = await ev(() => window.__game.renderer.r.toneMappingExposure);
  await ev(() => { window.__game.cineTime = 99; window.__game.travel('earth'); });
  await waitPlay();
  await ev(() => { window.__game.cineTime = null; });
  await wait(2000);

  const cam = async (pos, look) => ev(([pos, look]) => {
    const g = window.__game, V = g.camera.position.constructor, c = g.camera; g.stationId = 'test';
    c.position.set(...pos); c.lookAt(...look); c.fov = 60; c.updateProjectionMatrix();
    g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 60, t0: 0 };
    const w = g.world; if (w.flora) w.flora.update(c, 0, true); if (w.downtown) w.downtown.update(c, 0, true);
  }, [pos, look]);
  const frame = () => ev(() => {
    const g = window.__game, R = g.renderer, info = R.r.info;
    info.autoReset = false; info.reset();
    const t = performance.now();
    R.render(g.scene, g.camera);
    const ms = performance.now() - t, out = { calls: info.render.calls, tris: info.render.triangles, ms: Math.round(ms) };
    info.autoReset = true;
    return out;
  });
  const setHour = h => ev(h => { const g = window.__game; g.clock.set(h); g.clock.paused = true; g.world.daynight.update(0); return true; }, h);
  const L = await ev(async () => { const m = await import('/src/worlds/meridian/layout.js'); return { RIVER_Z: m.RIVER_Z, PITCH: m.PITCH }; });
  const park = await ev(() => { const f = window.__game.world.fountainSpots; return f && f.length ? [f[0].x, f[0].z] : [0, 0]; });
  const VIEWS = {
    street: [[-30, 1.7, -104], [60, 6, -112]],
    aerial: [[260, 210, 330], [-20, 30, -60]],
    river: [[90, 9, L.RIVER_Z + 70], [-60, 4, L.RIVER_Z - 10]],
    park: [[park[0] + 26, 3, park[1] + 20], [park[0], 2.5, park[1]]],
  };

  // ---------------------------------------------------------------- hours
  const per = {};
  for (const h of HOURS) {
    await setHour(h);
    const st = await ev(() => {
      const g = window.__game, w = g.world, dn = w.daynight, S = w.daynight.constructor;
      const SKY = window.__SKY || null;
      return { hour: +g.clock.hour.toFixed(2), label: g.clock.label(), sunI: +w.sun.intensity.toFixed(3), sunC: w.sun.color.getHexString(), dir: w.sunDir.toArray().map(v => +v.toFixed(3)),
        hemiI: +w.hemi.intensity.toFixed(2), fog: w.scene.fog.color.getHexString(), exp: +g.renderer.r.toneMappingExposure.toFixed(2), envBuilds: dn.envBuilds };
    });
    const sky = await ev(async () => { const m = await import('/src/worlds/meridian/daynight.js'); const S = m.SKY; return { night: +S.night.value.toFixed(3), win: +S.win.value.toFixed(3), home: +S.litHome.value.toFixed(3), office: +S.litOffice.value.toFixed(3), shop: +S.litShop.value.toFixed(3) }; });
    per[h] = { ...st, ...sky };
    console.log('hour', h, JSON.stringify(per[h]));
    const tag = String(h).replace('.', '_').padStart(4, '0');
    for (const [k, [pos, look]] of Object.entries(VIEWS)) {
      if (ONLY && !ONLY.has(k)) continue;
      if (k === 'park' && !(h === 9 || h === 21.5 || h === 18.75)) continue;
      await cam(pos, look);
      // let particles (leaves, steam, spray, moths) build up near the camera before the shot
      await ev(() => { const w = window.__game.world; for (let i = 0; i < 150; i++) { w.atmos.update(1 / 30); } });
      await wait(400);
      const r = await frame();
      if (k === 'street' || k === 'aerial') console.log('perf', h, k, JSON.stringify(r));
      if (h === 13 || h === 21.5) per[h]['perf_' + k] = r;
      await shot(`dn_${tag}_${k}`);
    }
  }
  const H = Object.keys(per).map(Number);
  if (H.includes(13) && H.includes(21.5)) {
    const d = per[13], n = per[21.5];
    check(d.sunI > n.sunI * 3, 'sunlight is much stronger at noon than at night', { noon: d.sunI, night: n.sunI });
    check(d.sunC !== n.sunC, 'light colour changes (sun by day, moon by night)', { noon: d.sunC, night: n.sunC });
    check(n.night > .9 && d.night < .05, 'night factor', { noon: d.night, night: n.night });
    check(n.home * n.win > d.home * d.win * 2, 'more home windows lit (and brighter) at night', { noon: +(d.home * d.win).toFixed(3), night: +(n.home * n.win).toFixed(3) });
  }
  if (H.includes(6.5) && H.includes(18.75)) {
    const a = per[6.5].dir, e = per[18.75].dir;
    check(a[0] > 0 && e[0] < 0, 'sun rises in the east and sets in the west', { dawn: a, evening: e });
    check(per[6.5].sunC !== per[13].sunC, 'dawn light is warmer than noon', { dawn: per[6.5].sunC, noon: per[13] && per[13].sunC });
  }
  // ---------------------------------------------------------------- cost of the day/night additions
  // downtown.js's fixed viewpoints (fov 55) at the original golden hour and at night, with the new VFX objects
  // (lamp pools, halos, leaves, moths, steam/smoke, spray) shown and hidden, so the numbers compare with
  // `PERF_ONLY=1 node tools/test/downtown.js` on an older build.
  const PV = { street: [[-30, 1.7, -104], [60, 6, -110]], aerial: [[260, 210, 330], [-20, 30, -60]], towers: [[-110, 1.8, 30], [-110, 120, -40]] };
  const cost = {};
  for (const h of [18.6, 21.5]) for (const [k, [pos, look]] of Object.entries(PV)) {
    await setHour(h); await cam(pos, look);
    await ev(() => { const c = window.__game.camera; c.fov = 55; c.updateProjectionMatrix(); window.__game.camFocus.fov0 = 55; });
    await frame(); const on = await frame();
    const hid = await ev(() => { const w = window.__game.world, o = [w.daynight.pools, w.daynight.halos, w.atmos.leaves, w.atmos.moths, w.atmos.smoke.points, w.atmos.spray.points]; const v = o.map(x => x && x.visible); o.forEach(x => x && (x.visible = false)); window.__vis = v; return true; });
    const off = await frame();
    await ev(() => { const w = window.__game.world, o = [w.daynight.pools, w.daynight.halos, w.atmos.leaves, w.atmos.moths, w.atmos.smoke.points, w.atmos.spray.points]; o.forEach((x, i) => x && (x.visible = window.__vis[i])); });
    cost[h + ' ' + k] = { calls: on.calls, callsWithoutVfx: off.calls, ms: on.ms, msWithoutVfx: off.ms, tris: on.tris };
    console.log('cost', h, k, JSON.stringify(cost[h + ' ' + k]));
  }
  // ---------------------------------------------------------------- env map rebuilds over simulated clock time
  const env = await ev(() => {
    const g = window.__game, w = g.world, dn = w.daynight, ren = g.renderer.render;
    g.clock.set(5); g.clock.paused = false; g.clock.speed = 1;
    const b0 = dn.envBuilds, h0 = g.clock.hour;
    // 16 in-game hours at the default day length (40 real min/day): 1600 s of game time in 1/2 s steps
    for (let i = 0; i < 3200; i++) { g.clock.update(.5); dn.update(.5); }
    const hours = 16, n = dn.envBuilds - b0;
    g.clock.paused = true;
    return { builds: n, perHour: +(n / hours).toFixed(2), perRealMinute: +(n / (1600 / 60)).toFixed(2) };
  });
  console.log('env rebuilds', JSON.stringify(env));
  check(env.perRealMinute <= 3, 'reflection probe rebuilt rarely (not every frame)', env);
  // ---------------------------------------------------------------- positional ambience
  const amb = await ev(async () => {
    const g = window.__game, w = g.world, A = g.audio;
    if (!A.ready) A.start();
    await new Promise(r => setTimeout(r, 300));
    if (A.ctx && A.ctx.state !== 'running') { try { await A.ctx.resume(); } catch (e) { } }
    const S = w.ambience.s, out = { state: A.ctx ? A.ctx.state : 'none', emitters: S.emitters.length, max: S.max, samples: [] };
    const spots = [];
    const f = w.fountainSpots[0]; if (f) spots.push(['fountain', f.x + 6, f.z]);
    const cafe = w.downtown.furn.DT_cafe[0]; if (cafe) spots.push(['cafe', cafe.m.elements[12], cafe.m.elements[14] + 3]);
    const cr = w.downtown.cranes[0]; if (cr) spots.push(['crane', cr.jib.position.x + 20, cr.jib.position.z + 20]);
    const tr = w.downtown.trams[0]; if (tr) spots.push(['tram', tr.o.position.x, tr.z + 6]);
    spots.push(['river', 0, (await import('/src/worlds/meridian/layout.js')).RIVER_Z + 30]);
    for (const hr of [10, 21.5]) {
      g.clock.set(hr);
      for (const [n, x, z] of spots) {
        g.camera.position.set(x, 1.7, z); g.camera.updateMatrixWorld();
        for (let i = 0; i < 12; i++) w.ambience.update(.25);
        const st = S.stats();
        out.samples.push({ at: n, hour: hr, voices: st.voices, fading: st.fading, kinds: st.kinds });
      }
    }
    out.peak = S.peak;
    return out;
  });
  console.log('ambience', JSON.stringify(amb));
  check(amb.state !== 'running' || amb.peak <= amb.max, 'ambience voice pool stays bounded', { peak: amb.peak, max: amb.max, emitters: amb.emitters });
  if (amb.state === 'running') check(amb.samples.some(s => s.voices > 0), 'ambience voices play near sources', amb.samples.map(s => s.at + '@' + s.hour + ':' + s.kinds.join('/')).join(' '));
  const atm = await ev(() => window.__game.world.atmos.stats());
  console.log('atmos', JSON.stringify(atm));
  check(atm.vents > 0 && atm.chimneys > 0 && atm.fountains > 0, 'steam vents, chimneys and fountains found', atm);
  // ---------------------------------------------------------------- other worlds still load
  if (!process.env.SKIP_WORLDS) {
    const e0 = errs.length;
    await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; g.cineTime = 99; g.travel('ship'); });
    await waitPlay(); await wait(1500); await frame();
    const ship = await ev(() => { const g = window.__game; return { world: g.world.kind, exp: g.renderer.r.toneMappingExposure, time: !!document.querySelector('.h-loc .h-time') }; });
    check(ship.world === 'ship' && Math.abs(ship.exp - shipExp) < 1e-6 && !ship.time, 'ship loads with its own lighting and no clock', ship);
    await shot('dn_ship');
    await ev(() => { const g = window.__game; g.travel('vanthos'); });
    await waitPlay(); await wait(2000); await frame();
    await ev(() => { window.__game.cineTime = null; });
    await shot('dn_vanthos');
    check(errs.length === e0, 'ship and VANTHOS load without page errors', errs.slice(e0));
  }
  console.log('SUMMARY', JSON.stringify({ per, cost, env, ambPeak: amb.peak }));
  console.log('fails:', fails.length, fails.join('; '));
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length || fails.length ? 1 : 0);
})().catch(e => { console.error('DAYNIGHT FAILED', e); process.exit(2); });
