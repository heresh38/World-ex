// Pedestrian crowd check on Earth: fps, draw calls and triangles with the crowd in view, plus close-ups of a few
// pedestrians (player bodies with random looks). CIV=1 uses the old civilian models for an A/B comparison.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/crowd.js
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/crowd';
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(process.env.VW || 960), height: +(process.env.VH || 540) } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 300)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 300)); } });
  const civ = !!process.env.CIV;
  await p.addInitScript(c => { localStorage.clear(); window.__TEST_QUALITY = 'low'; if (c) window.__civPeds = true; }, civ);
  const ev = (fn, a) => p.evaluate(fn, a);
  const wait = ms => p.waitForTimeout(ms);
  const tag = civ ? 'civ' : 'npc';
  const shot = async n => { await p.screenshot({ path: `${OUT}/${tag}_${n}.jpg`, type: 'jpeg', quality: 80, timeout: 600000 }); console.log('shot', n); };
  const waitPlay = () => p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.applyQuality(); g.startGame(true); });
  await waitPlay();
  await ev(() => window.__game.travel('earth'));
  await waitPlay();
  await ev(() => { const g = window.__game; g.input.locked = true; g.input.enabled = true; g.save.settings.view = 'first'; g.setAvatarLayer(); });
  await wait(4000);
  const info = await ev(() => { const w = window.__game.world, P = w.population.peds; return { heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null, peds: P.length, models: [...new Set(P.map(q => q.av.modelName))], looks: P.slice(0, 6).map(q => q.look && Object.entries(q.look.wear).filter(([k, v]) => v !== 'none').map(([k, v]) => k + ':' + v).join(' ')) }; });
  console.log('crowd', JSON.stringify(info));
  // stand next to the densest group of pedestrians and look at them
  const measure = async name => {
    const r = await ev(async () => {
      const g = window.__game, R = g.renderer.r;
      let n = 0, t0 = performance.now(), calls = 0, tris = 0;
      const f0 = g.frameCount || 0;
      await new Promise(res => { const tick = () => { n++; calls += R.info.render.calls; tris += R.info.render.triangles; if (performance.now() - t0 < 8000) requestAnimationFrame(tick); else res(); }; requestAnimationFrame(tick); });
      const near = g.world.population.peds.filter(q => q.pos.distanceTo(g.player.pos) < 40).length;
      return { fps: +(n / ((performance.now() - t0) / 1000)).toFixed(1), calls: Math.round(calls / n), tris: Math.round(tris / n), pedsWithin40m: near, visible: g.world.population.peds.filter(q => q.av.root.visible).length };
    });
    console.log(name, JSON.stringify(r));
    return r;
  };
  const go = async (i, dist, name) => {
    await ev(([i, dist]) => {
      const g = window.__game, P = g.world.population.peds.filter(q => q.alive);
      const q = P[i % P.length], pl = g.player;
      const yaw = q.yaw;
      pl.pos.set(q.pos.x + Math.sin(yaw) * dist, q.pos.y + .1, q.pos.z + Math.cos(yaw) * dist); pl.vel.set(0, 0, 0);
      pl.avatar.root.position.copy(pl.pos); pl.camYaw = Math.atan2(pl.pos.x - q.pos.x, pl.pos.z - q.pos.z); pl.camPitch = -.05; pl.snapCamera = true;
      q.state = 'idle'; q.idleT = 30;
    }, [i, dist]);
    await wait(2500);
    if (name) await shot(name);
  };
  // numbers first (screenshots of the software-rendered page are the most memory hungry step)
  await go(3, 14, null);
  await measure('street_view');
  for (let i = 0; i < 4; i++) await go(i * 7, 3.2, 'ped' + i);
  await go(3, 14, 'street');
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('CROWD FAILED', e); process.exit(2); });
