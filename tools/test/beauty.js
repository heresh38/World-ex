// Presentation screenshots at a chosen quality (default high): hangar lighting, welding sparks, car paint, Earth, a planet.
// Usage: node tools/test/beauty.js   (env: BASE, QUALITY, OUT, WORLDS=comma list)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/beauty';
const Q = process.env.QUALITY || 'high';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(process.env.VW || 960), height: +(process.env.VH || 540) } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 300)); });
  const ev = (fn, a) => p.evaluate(fn, a);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 88, timeout: 600000 }); console.log('shot', n); };
  const waitPlay = () => p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
  // let the scene settle (several real frames) before a screenshot
  const settle = async (frames = 6) => { await ev(async n => { for (let i = 0; i < n; i++) await new Promise(r => requestAnimationFrame(r)); }, frames); };

  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(q => { const g = window.__game; Object.assign(g.save.settings, { quality: q, dynamicRes: false }); g.renderer.settings = g.save.settings; g.renderer.applyQuality(); }, Q);
  await settle(3); await shot('a_title');
  await ev(() => window.__game.startGame(false));
  await waitPlay();
  const pose = (x, z, camYaw, pitch, yaw) => ev(([x, z, cy, cp, yw]) => {
    const g = window.__game, pl = g.player; pl.pos.set(x, g.world.collision.ground(x, z), z); pl.avatar.root.position.copy(pl.pos);
    pl.yaw = yw ?? cy + Math.PI; pl.avatar.root.rotation.set(0, pl.yaw, 0); pl.camYaw = cy; pl.camPitch = cp; pl.snapCamera = true;
    g.input.locked = true; g.input.enabled = true;
  }, [x, z, camYaw, pitch, yaw]);
  // hangar wide: skylights, shafts, welder, car
  await pose(2, -7, .15, .28); await settle(10); await shot('b_hangar_wide');
  await pose(-3.5, -19.5, Math.PI * .2, .12); await settle(10); await shot('c_welder');
  await pose(2.2, -16.5, -Math.PI * .5, -.05, Math.PI * .5); await settle(8); await shot('d_car');
  await pose(0, 3.5, Math.PI, .05, 0); await settle(8); await shot('e_commons');
  await pose(1.5, 12.5, Math.PI, .1, 0); await settle(8); await shot('f_bridge');
  await ev(() => window.__game.station('captain')); await wait(1500); await settle(8); await shot('g_captain');
  await ev(() => window.__game.closeStation());
  for (const w of (process.env.WORLDS || 'earth,ares,thalassa').split(',')) {
    await ev(w => window.__game.travel(w), w); await waitPlay();
    await settle(4);
    await ev(() => { const g = window.__game; g.input.locked = true; g.input.enabled = true; g.player.camPitch = .15; });
    await settle(10); await shot('h_' + w);
    await ev(() => { const g = window.__game; g.player.camYaw += Math.PI * .8; g.player.camPitch = .05; });
    await settle(8); await shot('i_' + w + '_2');
  }
  console.log('errors', errs.length);
  await b.close();
})().catch(e => { console.error('BEAUTY FAILED', e); process.exit(2); });
