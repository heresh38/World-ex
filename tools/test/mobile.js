// Phone check: iPhone-sized landscape viewport with touch. Drives the on-screen stick and buttons with
// pointer events, checks first person + the viewmodel, a station, Earth combat and the car. Screenshots in test-out/mobile.
const { chromium, devices } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/mobile';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const iphone = devices['iPhone 13 landscape'] || { viewport: { width: 844, height: 390 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true };
  const ctx = await b.newContext({ ...iphone, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 300)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 300)); } });
  const ev = (fn, a) => p.evaluate(fn, a);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 80, timeout: 600000 }); console.log('shot', n); };
  const waitPlay = () => p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
  // synthetic pointer on an element (down, optional moves, up)
  const pointer = (sel, opts) => ev(async ([sel, o]) => {
    const el = document.querySelector(sel); const r = el.getBoundingClientRect();
    const x = r.left + r.width / 2 + (o.dx0 || 0), y = r.top + r.height / 2 + (o.dy0 || 0), id = o.id || 7;
    const fire = (type, cx, cy) => el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: id, pointerType: 'touch', clientX: cx, clientY: cy, isPrimary: true }));
    fire('pointerdown', x, y);
    for (const [mx, my] of (o.moves || [])) fire('pointermove', x + mx, y + my);
    await new Promise(r => setTimeout(r, o.hold || 50));
    if (!o.keep) fire('pointerup', x + ((o.moves || []).slice(-1)[0] || [0])[0], y + ((o.moves || []).slice(-1)[0] || [0, 0])[1]);
  }, [sel, opts || {}]);

  await p.goto(BASE + '/index.html?touch=1');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.applyQuality(); });
  await shot('01_title');
  await p.tap('[data-act="title-play"]');
  await waitPlay(); await wait(3000);
  console.log('touch mode', await ev(() => ({ touch: !!window.__game.touch, locked: window.__game.input.locked, fp: window.__game.firstPerson(), view: window.__game.save.settings.view })));
  await shot('02_ship_fp');
  // walk forward with the stick (hold the knob up for 3 s)
  const z0 = await ev(() => window.__game.player.pos.z);
  await pointer('#touch .t-stick', { dx0: -60, dy0: 40, moves: [[0, -20], [0, -45], [0, -60]], hold: 3000, id: 11 });
  const z1 = await ev(() => window.__game.player.pos.z);
  console.log('stick moved player by', (z1 - z0).toFixed(2), 'm');
  // look by dragging the right side
  const yaw0 = await ev(() => window.__game.player.camYaw);
  await pointer('#touch .t-look', { moves: [[30, 0], [80, 0], [120, 10]], hold: 300, id: 12 });
  console.log('look drag changed yaw by', (await ev(() => window.__game.player.camYaw) - yaw0).toFixed(3));
  // interact at the briefing table with the E button
  await ev(() => { const g = window.__game, s = g.world.stations.briefing; g.player.pos.set(...s.pos); });
  await wait(1500);
  await pointer('#touch [data-b="use"]', { hold: 200 });
  await wait(2500);
  console.log('station open', await ev(() => window.__game.menus.open));
  await shot('03_station');
  await p.tap('[data-act="leave"]'); await wait(800);
  console.log('station closed', await ev(() => !window.__game.menus.open));
  // third-person toggle via the view button, then back
  await pointer('#touch [data-b="view"]', { hold: 100 }); await wait(1500);
  console.log('view after toggle', await ev(() => window.__game.save.settings.view));
  await shot('04_ship_third');
  await pointer('#touch [data-b="view"]', { hold: 100 }); await wait(500);
  // Earth: first person with the gun, fire button, car
  await ev(() => window.__game.travel('earth'));
  await waitPlay(); await wait(3000);
  await shot('05_earth_fp');
  const shots0 = await ev(() => window.__game.save.stats.shots);
  await pointer('#touch [data-b="fire"]', { hold: 2500, moves: [[5, 0]] });
  console.log('fire button shots', (await ev(() => window.__game.save.stats.shots)) - shots0, 'viewmodel active', await ev(() => window.__game.viewmodel.active));
  await shot('06_earth_firing');
  await pointer('#touch [data-b="aim"]', { hold: 100 }); await wait(1200);
  await shot('07_earth_ads');
  await pointer('#touch [data-b="aim"]', { hold: 100 });
  await pointer('#touch [data-b="car"]', { hold: 100 }); await wait(1500);
  await pointer('#touch [data-b="use"]', { hold: 100 }); await wait(1000);
  console.log('in car', await ev(() => window.__game.player.mode));
  await pointer('#touch .t-stick', { dx0: -60, dy0: 40, moves: [[0, -30], [0, -60]], hold: 2500, id: 13 });
  console.log('car speed', await ev(() => window.__game.vehicles.current ? window.__game.vehicles.current.speed.toFixed(1) : 'none'));
  await shot('08_car');
  // pause via the menu button
  await pointer('#touch [data-b="menu"]', { hold: 100 }); await wait(800);
  console.log('paused', await ev(() => window.__game.paused));
  await shot('09_pause');
  await p.tap('[data-act="resume"]'); await wait(500);
  // portrait warning
  await p.setViewportSize({ width: 390, height: 844 }); await wait(800);
  await shot('10_portrait');
  console.log('errors', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('MOBILE FAILED', e); process.exit(2); });
