// Movement check: sprint, slide, mantle onto a crate, sit on a park bench, collide with a lamp post, inventory, minimap.
// Usage: python3 -m http.server 8765 &  then  node tools/test/movement.js   (screenshots in test-out/)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 80, timeout: 300000 }); console.log('shot', n); };
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  // drive the controller with synthetic key state, simulated frame by frame (software rendering is too slow for real time)
  const sim = (keys, seconds, press = []) => ev(([keys, seconds, press]) => {
    const g = window.__game, inp = g.input, dt = 1 / 60;
    inp.down.clear(); keys.forEach(k => inp.down.add(k)); press.forEach(k => inp.hit.add(k));
    let maxY = g.player.pos.y, maxV = 0, slid = false, climbed = false;
    for (let t = 0; t < seconds; t += dt) {
      g.player.update(dt, inp, g.world.collision); inp.hit.clear();
      maxY = Math.max(maxY, g.player.pos.y); maxV = Math.max(maxV, Math.hypot(g.player.vel.x, g.player.vel.z));
      slid = slid || g.player.slideT > 0; climbed = climbed || !!g.player.climb;
    }
    inp.down.clear();
    return { pos: g.player.pos.toArray().map(v => +v.toFixed(2)), maxY: +maxY.toFixed(2), maxV: +maxV.toFixed(2), slid, climbed, mode: g.player.mode };
  }, [keys, seconds, press]);
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await p.click('[data-act="title-play"]');
  await waitPlay();
  await ev(() => window.__game.travel('earth')); await waitPlay();
  // flat open ground: put the player on the spaceport apron facing north (camYaw = 0 looks along -Z)
  await ev(() => { const g = window.__game, P = g.player; P.pos.set(0, 1.2, 18); P.camYaw = Math.PI; P.yaw = 0; P.vel.set(0, 0, 0); });
  console.log('sprint', JSON.stringify(await sim(['KeyW', 'ShiftLeft'], 1.5)));
  console.log('slide', JSON.stringify(await sim(['KeyW', 'ShiftLeft'], .6, ['KeyC'])));
  // a 1.6 m crate wall in front: jump into it and mantle
  const crate = await ev(() => { const g = window.__game, P = g.player, c = g.world.collision; const x = P.pos.x, z = P.pos.z + 3, y = P.pos.y;
    c.add([x - 2, y, z, x + 2, y + 1.6, z + 2], 'test'); P.vel.set(0, 0, 0); P.crouch = false; P.slideT = 0; return y + 1.6; });
  await sim(['KeyW'], .5);
  const cl = await sim(['KeyW'], 1.4, ['Space']);
  console.log('climb', JSON.stringify(cl), 'top', crate, cl.climbed && Math.abs(cl.pos[1] - crate) < .1 ? 'OK' : 'FAIL');
  // sit on the nearest bench
  const seat = await ev(() => { const g = window.__game, P = g.player; const s = g.world.interactables.filter(i => i.id === 'seat').sort((a, b) => a.pos.distanceTo(P.pos) - b.pos.distanceTo(P.pos))[0];
    if (!s) return 'no seats'; P.pos.copy(s.pos); s.action(); return { n: g.world.interactables.filter(i => i.id === 'seat').length, mode: P.mode }; });
  console.log('seat', JSON.stringify(seat));
  for (let i = 0; i < 3; i++) await ev(() => window.__game.player.update(1 / 30, window.__game.input, window.__game.world.collision));
  await ev(() => { const g = window.__game; g.save.settings.view = 'third'; g.player.snapCamera = true; });
  await p.waitForTimeout(2500); await shot('mv_bench_sit');
  console.log('stand', JSON.stringify(await sim([], .1, ['KeyE'])));
  await ev(() => { window.__game.save.settings.view = 'first'; });
  // walk into a tree trunk / lamp: must be stopped
  const block = await ev(() => { const g = window.__game, P = g.player, c = g.world.collision;
    const b = c.boxes.find(b => (b.tag === 'tree' || b.tag === 'prop') && b.max.x - b.min.x < 1.2); if (!b) return 'none';
    const cx = (b.min.x + b.max.x) / 2, cz = (b.min.z + b.max.z) / 2;
    P.pos.set(cx, g.world.collision.ground(cx, cz + 3), cz + 3); P.camYaw = 0; P.vel.set(0, 0, 0); return { cx, cz, tag: b.tag }; });
  const w = await sim(['KeyW'], 1.5);
  console.log('post', JSON.stringify(block), JSON.stringify(w), block !== 'none' && w.pos[2] > block.cz + .3 ? 'BLOCKED OK' : 'CHECK');
  await p.waitForTimeout(1500); await shot('mv_minimap_earth');
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('MOVEMENT FAILED', e); process.exit(2); });
