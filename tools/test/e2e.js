// End-to-end check: title -> ship (every station) -> Earth (combat, car) -> a frontier planet (streaming) -> ship.
// Usage: python3 -m http.server 8765 &  then  node tools/test/e2e.js   (screenshots in test-out/)
// Env: BASE (default http://localhost:8765), QUALITY (low|medium|high), STEPS (comma list to run a subset)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage({ viewport: { width: +(process.env.VW || 1280), height: +(process.env.VH || 720) } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(q => {
    try {
      const s = JSON.parse(localStorage.getItem('worldex_save_v1') || 'null');
      if (!s) localStorage.setItem('worldex_test_quality', q);
    } catch (e) { /* ignore */ }
    window.__TEST_QUALITY = q;
  }, process.env.QUALITY || 'low');
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 80, timeout: 300000 }); console.log('shot', n); };
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const waitPlay = () => p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });

  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(q => { const g = window.__game; g.save.settings.quality = q; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); }, process.env.QUALITY || 'low');
  await wait(1500); await shot('01_title');
  await p.click('[data-act="title-play"]');
  await p.waitForFunction(() => !document.getElementById('loading').classList.contains('hidden'), null, { timeout: 60000 });
  await wait(1200); await shot('02_loading');
  await waitPlay();
  await wait(4000); await shot('03_ship_spawn');
  console.log('ship', await ev(() => { const g = window.__game; return { pos: g.player.pos.toArray().map(v => +v.toFixed(2)), mode: g.player.mode, stations: Object.keys(g.world.stations) }; }));

  // walk forward a bit with real key input to exercise the controller + camera
  await ev(() => { window.__game.input.locked = true; window.__game.input.enabled = true; });
  await p.keyboard.down('KeyW'); await wait(2500); await p.keyboard.up('KeyW');
  console.log('after walk', await ev(() => window.__game.player.pos.toArray().map(v => +v.toFixed(2))));
  await shot('04_ship_walk');

  // visit every station: teleport next to it, press E, screenshot, Esc
  for (const id of ['captain', 'briefing', 'wardrobe', 'engineering', 'record', 'armory', 'gunsmith', 'garage']) {
    await ev(id => { const g = window.__game, s = g.world.stations[id]; g.player.pos.set(...s.pos); g.player.avatar.root.position.set(...s.pos); g.input.locked = true; g.input.enabled = true; }, id);
    await wait(300);
    await p.keyboard.press('KeyE');
    await wait(2500);
    const open = await ev(() => window.__game.menus.open);
    console.log('station', id, 'open=', open);
    await shot('05_station_' + id);
    await p.keyboard.press('Escape');
    await wait(400);
  }
  // hangar overview for lighting / welding sparks / car reflections
  await ev(() => { const g = window.__game; g.player.pos.set(1, 0, -12); g.player.avatar.root.position.set(1, 0, -12); g.player.camYaw = Math.PI * .78; g.player.camPitch = .12; g.input.locked = true; g.input.enabled = true; });
  await wait(3500); await shot('06_hangar');

  // ---- Earth
  await ev(() => window.__game.travel('earth'));
  await waitPlay(); await wait(5000); await shot('07_earth_spawn');
  await ev(() => { const g = window.__game; g.input.locked = true; g.input.enabled = true; g.player.camYaw = Math.PI; g.player.camPitch = .25; });
  await wait(2500); await shot('08_earth_skyline');
  // fight: put the player near the incursion and shoot
  const fight = await ev(async () => {
    const g = window.__game, c = g.world.incursionCenter;
    g.player.pos.set(c.x - 30, 0, c.z + 30); g.player.avatar.root.position.copy(g.player.pos);
    const e = g.enemies.list.find(e => e.alive && e.type === 'trooper');
    const dx = e.pos.x - g.player.pos.x, dz = e.pos.z - g.player.pos.z;
    g.player.camYaw = Math.atan2(-dx, -dz); g.player.camPitch = -.05;
    g.input.rmb = true;
    const hp0 = e.hp;
    for (let i = 0; i < 40; i++) {
      g.input.lmb = true; g.input.lmbHit = true;
      const ddx = e.pos.x - g.player.pos.x, ddz = e.pos.z - g.player.pos.z, d = Math.hypot(ddx, ddz);
      g.player.camYaw = Math.atan2(-ddx, -ddz); g.player.camPitch = Math.atan2(e.pos.y + 1.0 - (g.player.pos.y + 1.6), d);
      await new Promise(r => setTimeout(r, 120));
    }
    g.input.lmb = false; g.input.rmb = false;
    return { hp0, hp: e.hp, alive: e.alive, kills: g.save.stats.kills, shots: g.save.stats.shots, hits: g.save.stats.hits };
  });
  console.log('fight', fight);
  await shot('09_earth_fight');
  // car
  const car = await ev(async () => {
    const g = window.__game; g.player.pos.set(20, 0, 30); g.player.avatar.root.position.copy(g.player.pos);
    const c = g.vehicles.nearest(g.player.pos, 10); if (!c) return 'no car';
    g.vehicles.enter(c); g.input.down.add('KeyW');
    await new Promise(r => setTimeout(r, 3000));
    g.input.down.delete('KeyW');
    return { speed: +c.speed.toFixed(1), pos: c.pos.toArray().map(v => +v.toFixed(1)) };
  });
  console.log('car', car);
  await shot('10_earth_car');
  await ev(() => { const g = window.__game; if (g.vehicles.current) g.vehicles.exit(); });

  // ---- Planet
  await ev(() => window.__game.travel('ares'));
  await waitPlay(); await wait(5000); await shot('11_planet_spawn');
  const stream = await ev(async () => {
    const g = window.__game, w = g.world; const n0 = w.chunks.size;
    g.player.pos.set(600, w.height(600, 600), 600); g.player.avatar.root.position.copy(g.player.pos);
    await new Promise(r => setTimeout(r, 12000));
    return { before: n0, after: w.chunks.size, outposts: w.outposts.size, enemies: g.enemies.list.length };
  });
  console.log('stream', stream);
  await ev(() => { const g = window.__game; g.player.camPitch = .1; });
  await wait(1500); await shot('12_planet_far');
  for (const id of ['vesper', 'thalassa', 'pyrrhos', 'nyx']) {
    if (process.env.ALLPLANETS !== '1') break;
    await ev(id => window.__game.travel(id), id); await waitPlay(); await wait(4000); await shot('13_planet_' + id);
  }
  // ---- back to the ship
  await ev(() => window.__game.travel('ship'));
  await waitPlay(); await wait(3000); await shot('14_back_on_ship');
  const fps = await ev(() => Math.round(window.__game.fps));
  console.log('fps (software renderer)', fps);
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('E2E FAILED', e); process.exit(2); });
