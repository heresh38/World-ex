// Spaceport + water check: travel to Earth (landing cinematic), look at the airport from several angles, shoot into the
// river, fire a rocket at the water, drop a car in, wade / swim, then return to orbit (take-off cinematic).
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/airport_water.js   (shots in test-out/)
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
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'medium'; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 82, timeout: 300000 }); console.log('shot', n); };
  const unpause = () => ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; });
  const waitState = async (s, t = 900000) => { await p.waitForFunction(st => window.__game && window.__game.state === st, s, { timeout: t, polling: 250 }); };
  const waitPlay = async () => { await waitState('play'); await unpause(); };
  await p.goto(BASE + '/index.html');
  await waitState('title', 300000);
  await ev(() => { const g = window.__game; g.save.settings.quality = 'medium'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); });
  await p.click('[data-act="title-play"]');
  await waitPlay();

  // ---------------- landing cinematic
  const t0 = Date.now();
  await ev(() => { window.__travel = window.__game.travel('earth'); });
  await waitState('cinematic');
  console.log('load seconds', Math.round((Date.now() - t0) / 1000));
  await wait(1200); await shot('aw01_landing_descent');
  await wait(1800); await shot('aw02_landing_touchdown');
  await wait(1500); await shot('aw03_landing_ramp');
  await waitPlay();
  await wait(800);
  const arrived = await ev(() => { const g = window.__game, w = g.world, P = g.player.pos;
    return { pos: [P.x, P.y, P.z].map(v => +v.toFixed(1)), district: w.map.district(P.x, P.z), ship: w.jumpship.position.toArray().map(v => +v.toFixed(1)),
      colliders: w.airport.colliders.length, water: !!g.water, cine: !!g.cine, hud: !g.hud.el.classList.contains('hidden') }; });
  console.log('arrived', JSON.stringify(arrived));
  await shot('aw04_first_person_at_pad');

  // ---------------- airport views (free camera)
  const cam = async (n, pos, look, ms = 3000) => {
    await ev(([pos, look]) => { const g = window.__game, V = g.camera.position.constructor; g.stationId = 'test'; const c = g.camera; c.position.set(...pos); c.lookAt(...look);
      g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 60, t0: 0 }; }, [pos, look]);
    await wait(ms); await shot(n);
  };
  const A = await ev(() => { const { x, z } = window.__game.world.padPos; return [x, z]; });
  const W = (x, y, z) => [A[0] + x, y, A[1] + z];
  await cam('aw05_overview_from_city', W(-80, 140, -330), W(-40, 0, 40));
  await cam('aw06_terminal_landside', W(35, 6, -150), W(0, 8, -80));
  await cam('aw07_apron_ship_terminal', W(40, 8, 40), W(-10, 4, -40));
  await cam('aw08_runway_threshold', W(-420, 12, 100), W(-200, 0, 100));
  await cam('aw09_tower_fuel', W(90, 18, 30), W(150, 20, -66));
  await cam('aw10_hangars', W(-180, 10, 70), W(-260, 6, -10));
  await cam('aw11_terminal_hall', W(-30, 3, -72), W(20, 2.5, -45));
  await cam('aw12_vendor_kiosk', W(14, 2.2, -38), W(14, 1.4, -51));
  await cam('aw13_dusk_runway_lights', W(260, 25, 160), W(-100, 0, 100));
  await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; });

  // ---------------- water: shoot into the river from the south quay
  const RZ = -330;
  const setP = (x, y, z, yaw, pitch, third = false) => ev(([x, y, z, yaw, pitch, third]) => {
    const g = window.__game, P = g.player; P.pos.set(x, y, z); P.vel.set(0, 0, 0); P.avatar.root.position.copy(P.pos); P.yaw = yaw; P.camYaw = yaw + Math.PI; P.camPitch = pitch; P.snapCamera = true;
    if (third && g.save.settings.view !== 'third') g.toggleView(); if (!third && g.save.settings.view === 'third') g.toggleView();
    g.paused = false; g.input.locked = true; g.input.enabled = true; }, [x, y, z, yaw, pitch, third]);
  await setP(0, 0, RZ + 38, Math.PI, -.55);
  await wait(1500);
  await ev(() => { const g = window.__game; window.__fire = setInterval(() => { g.input.lmb = true; g.input.lmbHit = true; g.input.locked = true; g.paused = false; }, 30); });
  await wait(1600);
  await shot('aw14_bullets_into_river');
  await ev(() => { clearInterval(window.__fire); window.__game.input.lmb = false; });
  await wait(600); await shot('aw15_bullet_ripples');
  const wstats = await ev(() => { const w = window.__game.water; return { ripples: w.rip.filter(r => r.w > 0).length, drops: w.drops.live, level: w.level, heightRiver: w.heightAt(0, -330), heightLand: w.heightAt(0, 0) }; });
  console.log('water after shots', JSON.stringify(wstats));
  // a rocket at the water (the real rocket path: launchRocket -> updateRockets -> hitTest -> explosion at the surface)
  await ev(async () => {
    const g = window.__game, V = g.camera.position.constructor;
    const st = await import('/src/game/state.js');
    const w = st.makeWeapon('rocket', 2, g.power() || 10);
    g.weapons.launchRocket(new V(4, 3, -292), new V(10, -3, -322), st.weaponStats(w), w);
  });
  await wait(900); await shot('aw16_rocket_column');
  await wait(1400); await shot('aw17_rocket_aftermath');
  // a car dropped into the river
  await ev(() => { const g = window.__game, V = g.camera.position.constructor; window.__car = g.vehicles.spawn('car_sport', '#a3121f', new V(-14, 7, -318), .6); });
  await wait(1500); await shot('aw18_car_splash');
  await wait(2500);
  const carState = await ev(() => { const c = window.__car; return { y: +c.pos.y.toFixed(2), wet: !!c.wet }; });
  console.log('car', JSON.stringify(carState));
  await shot('aw19_car_floating');
  // wade in, then swim (third person)
  await setP(20, -1, RZ + 34, Math.PI, -.25, true);
  await ev(() => { const g = window.__game; window.__walk = setInterval(() => { g.input.keys && g.input.keys.add && g.input.keys.add('KeyW'); }, 50); });
  await ev(() => { const g = window.__game; g.input.key = (c => (orig => k => k === 'KeyW' || orig(k))(g.input.key.bind(g.input)))(); });
  await wait(2500); await shot('aw20_wading');
  await wait(3500);
  const swim = await ev(() => { const P = window.__game.player; return { y: +P.pos.y.toFixed(2), swimming: !!P.swimming, depth: +(window.__game.water.level - P.pos.y).toFixed(2) }; });
  console.log('swim', JSON.stringify(swim));
  await shot('aw21_swimming');
  await ev(() => { const g = window.__game; clearInterval(window.__walk); delete g.input.key; });

  // ---------------- take-off cinematic
  await ev(() => { const g = window.__game, w = g.world; const sp = w.spawn(); const P = g.player; P.pos.copy(sp.pos); P.avatar.root.position.copy(sp.pos); if (g.save.settings.view === 'third') g.toggleView(); });
  await wait(500);
  await ev(() => { const it = window.__game.world.interactables.find(i => i.id === 'ship'); it.action(); });
  await waitState('cinematic');
  await wait(1500); await shot('aw22_takeoff_spool');
  await wait(1800); await shot('aw23_takeoff_climb');
  await waitPlay();
  const back = await ev(() => ({ world: window.__game.world.constructor.name, state: window.__game.state }));
  console.log('back', JSON.stringify(back));
  await wait(1500); await shot('aw24_back_on_ship');
  console.log('errors', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})();
