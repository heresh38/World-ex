// Frontier worlds: land on each planet and take wide shots of the terrain, the horizon and the sky bodies.
// Usage: python3 -m http.server 8765 &  then  node tools/test/planets.js [ids...]   (screenshots in test-out/)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
fs.mkdirSync(OUT, { recursive: true });
const IDS = process.argv.slice(2).length ? process.argv.slice(2) : ['ares', 'vesper', 'thalassa', 'pyrrhos', 'nyx'];

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await p.click('[data-act="title-play"]');
  await waitPlay();
  for (const id of IDS) {
    const t0 = Date.now();
    await ev(id => window.__game.travel(id), id); await waitPlay();
    console.log(id, 'load s', Math.round((Date.now() - t0) / 1000));
    // a camera on a rise, looking toward the sky body and across the land
    for (const [n, yaw, pitch] of [['a', 0, -.05], ['b', 2.1, .02], ['c', 4.2, -.12]]) {
      await ev(([yaw, pitch]) => { const g = window.__game, w = g.world, V = g.camera.position.constructor;
        const x = 0, z = 0, y = w.height(x, z) + 14; const pos = new V(x, y, z), look = new V(x + Math.sin(yaw) * 100, y + pitch * 100, z + Math.cos(yaw) * 100);
        g.stationId = 'test'; g.camera.position.copy(pos); g.camera.lookAt(look);
        g.camFocus = { pos, look, orbit: false, q: g.camera.quaternion.clone(), p0: pos.clone(), q0: g.camera.quaternion.clone(), fov0: 60, t0: 0 }; }, [yaw, pitch]);
      await p.waitForTimeout(2500);
      await p.screenshot({ path: `${OUT}/pl_${id}_${n}.jpg`, type: 'jpeg', quality: 82, timeout: 300000 });
    }
    // look toward the sky body
    await ev(() => { const g = window.__game, w = g.world, V = g.camera.position.constructor, d = w.sky.material.uniforms.bDir.value;
      const pos = new V(0, w.height(0, 0) + 6, 0), look = pos.clone().addScaledVector(d, 100);
      g.camera.position.copy(pos); g.camera.lookAt(look);
      g.camFocus = { pos, look, orbit: false, q: g.camera.quaternion.clone(), p0: pos.clone(), q0: g.camera.quaternion.clone(), fov0: 60, t0: 0 }; });
    await p.waitForTimeout(2000);
    await p.screenshot({ path: `${OUT}/pl_${id}_sky.jpg`, type: 'jpeg', quality: 82, timeout: 300000 });
    await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; });
  }
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('PLANETS FAILED', e); process.exit(2); });
