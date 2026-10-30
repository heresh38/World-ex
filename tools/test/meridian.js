// New Meridian free-roam check: city, village and farm views, pedestrians, traffic, shooting a civilian
// (wanted level + security drones), hijacking a car. Screenshots in test-out/meridian.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/meridian';
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(process.env.VW || 960), height: +(process.env.VH || 540) } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 300), (e.stack || '').split('\n').slice(0, 3).join(' | ')); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 300)); } });
  const ev = (fn, a) => p.evaluate(fn, a);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 80, timeout: 600000 }); console.log('shot', n); };
  const waitPlay = () => p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(q => { const g = window.__game; g.save.settings.quality = q; g.save.settings.dynamicRes = false; g.renderer.applyQuality(); g.startGame(true); }, process.env.QUALITY || 'low');
  await waitPlay();
  const t0 = Date.now();
  await ev(() => window.__game.travel('earth'));
  await waitPlay();
  console.log('earth load seconds', Math.round((Date.now() - t0) / 1000));
  await ev(() => { const g = window.__game; g.input.locked = true; g.input.enabled = true; g.save.settings.view = 'third'; g.setAvatarLayer(); });
  await wait(6000);
  console.log('world', await ev(() => { const g = window.__game, w = g.world; return { trees: w.treeCount, peds: w.population.activeCount, traffic: w.traffic.cars.length, parked: g.vehicles.cars.filter(c => !c.ai).length, district: w.districtName, lanes: w.map.lanes.length, roads: w.map.roads.length }; }));
  await shot('01_spaceport');
  const view = async (x, z, yaw, pitch, name) => {
    await ev(([x, z, yaw, pitch]) => { const g = window.__game, pl = g.player; pl.pos.set(x, g.world.map.height(x, z) + .1, z); pl.vel.set(0, 0, 0); pl.avatar.root.position.copy(pl.pos); pl.camYaw = yaw; pl.camPitch = pitch; pl.snapCamera = true; }, [x, z, yaw, pitch]);
    await wait(7000); await shot(name);
    console.log(name, await ev(() => { const g = window.__game, w = g.world; return { district: w.districtName, peds: w.population.activeCount, traffic: w.traffic.cars.length, fps: Math.round(g.fps) }; }));
  };
  await view(-150, 60, Math.PI * .75, .05, '02_city_street');
  await view(-900, 600, -.5, .12, '03_village');
  await view(-640, -560, 2.4, .15, '04_farm');
  await view(600, 600, .8, .25, '05_countryside');
  // shoot a civilian: wanted level + security drones
  await view(-150, 60, Math.PI * .75, .05, '06_city_again');
  const crime = await ev(async () => {
    const g = window.__game, w = g.world;
    const q = w.population.peds.find(q => q.active && q.alive);
    if (!q) return 'no ped';
    const out = q.takeDamage(999, false, q.pos.clone(), new (q.pos.constructor)(0, 0, 1), 'player');
    await new Promise(r => setTimeout(r, 6000));
    return { killed: out.killed, wanted: w.wanted.level, police: w.wanted.police.length, fleeing: w.population.peds.filter(p => p.active && p.state === 'flee').length };
  });
  console.log('crime', crime);
  await shot('07_wanted');
  // hijack the nearest traffic car
  const jack = await ev(async () => {
    const g = window.__game, w = g.world;
    const t = w.traffic.cars[0]; if (!t) return 'no traffic';
    const c = t.car; g.player.pos.copy(c.pos).add(new (c.pos.constructor)(2, 0, 0)); g.player.avatar.root.position.copy(g.player.pos);
    g.vehicles.enter(c);
    g.input.down.add('KeyW'); await new Promise(r => setTimeout(r, 3000)); g.input.down.delete('KeyW');
    return { mode: g.player.mode, ai: c.ai, speed: +c.speed.toFixed(1), trafficLeft: w.traffic.cars.length };
  });
  console.log('hijack', jack);
  await shot('08_hijacked');
  console.log('errors', errs.length);
  await b.close(); process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('MERIDIAN FAILED', e); process.exit(2); });
