// Spaceport + water check: travel to Earth (landing cinematic), look at the spaceport from several angles, shoot into the
// river, fire a rocket at the water, drop a car in, wade / swim, then return to orbit (take-off cinematic).
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/spaceport_water.js   (shots in test-out/)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(process.env.W || 1024), height: +(process.env.H || 576) } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  // other work in progress may list a model that is not built yet: stand in with a sibling so the game still boots
  await p.route('**/assets/models/*.glb', async route => {
    const f = new URL(route.request().url()).pathname.split('/').pop(), path = require('path').join(__dirname, '../../assets/models/', f);
    if (fs.existsSync(path)) return route.continue();
    const alt = f.replace(/_npc\.glb$/, '.glb'), ap = require('path').join(__dirname, '../../assets/models/', alt);
    console.log('missing model', f, '-> serving', fs.existsSync(ap) ? alt : 'player_female.glb');
    return route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: fs.readFileSync(fs.existsSync(ap) ? ap : require('path').join(__dirname, '../../assets/models/player_female.glb')) });
  });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 82, timeout: 300000 }); console.log('shot', n); };
  const unpause = () => ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; });
  const waitState = async (s, t = 900000) => { await p.waitForFunction(st => window.__game && window.__game.state === st, s, { timeout: t, polling: 250 }); };
  const waitPlay = async () => { await waitState('play'); await unpause(); };
  await p.goto(BASE + '/index.html');
  await waitState('title', 300000);
  await ev(Q => { const g = window.__game; g.save.settings.quality = Q; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); }, process.env.Q || 'medium');
  await p.click('[data-act="title-play"]');
  await waitPlay();

  // ---------------- landing cinematic
  const t0 = Date.now();
  await ev(() => { window.__travel = window.__game.travel('earth'); });
  await waitState('cinematic');
  console.log('load seconds', Math.round((Date.now() - t0) / 1000));
  await wait(1200); await shot('sp01_landing_descent');
  await wait(1800); await shot('sp02_landing_touchdown');
  await wait(1500); await shot('sp03_landing_ramp');
  await waitPlay();
  await wait(800);
  const arrived = await ev(() => { const g = window.__game, w = g.world, P = g.player.pos;
    return { pos: [P.x, P.y, P.z].map(v => +v.toFixed(1)), district: w.map.district(P.x, P.z), ship: w.jumpship.position.toArray().map(v => +v.toFixed(1)),
      colliders: w.spaceport.colliders.length, water: !!g.water, cine: !!g.cine, hud: !g.hud.el.classList.contains('hidden') }; });
  console.log('arrived', JSON.stringify(arrived));
  await shot('sp04_first_person_at_pad');

  // ---------------- spaceport views (free camera)
  const cam = async (n, pos, look, ms = 3000) => {
    await ev(([pos, look]) => { const g = window.__game, V = g.camera.position.constructor; g.stationId = 'test'; const c = g.camera; c.position.set(...pos); c.lookAt(...look);
      g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 60, t0: 0 }; }, [pos, look]);
    await wait(ms); await shot(n);
  };
  const A = await ev(() => { const { x, z } = window.__game.world.padPos; return [x, z]; });
  const W = (x, y, z) => [A[0] + x, y, A[1] + z];
  await cam('sp05_overview_from_city', W(-80, 140, -330), W(-40, 0, 60));
  await cam('sp06_terminal_landside', W(35, 6, -150), W(0, 8, -80));
  await cam('sp07_pad1_ship_terminal', W(40, 8, 40), W(-10, 4, -40));
  await cam('sp08_heavy_pads_deflectors', W(-110, 16, 178), W(-185, 5, 95));
  await cam('sp09_gantry_hauler', W(-120, 6, 60), W(-170, 8, 100));
  await cam('sp10_container_yard_crane', W(196, 14, 150), W(266, 6, 60));
  await cam('sp11_control_tower', W(92, 20, -24), W(130, 32, -66));
  await cam('sp12_hangars_courier', W(-215, 9, 52), W(-300, 7, -10));
  await cam('sp13_terminal_hall', W(-30, 3, -72), W(20, 2.5, -45));
  await cam('sp14_vendor_kiosk', W(14, 2.2, -38), W(14, 1.4, -51));
  await ev(() => { window.__game.world.ambient.t = 7.5; });
  await cam('sp15_ambient_shuttle_landing', W(95, 12, 40), W(150, 14, 98), 1500);
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
  await shot('sp16_bullets_into_river');
  await ev(() => { clearInterval(window.__fire); window.__game.input.lmb = false; });
  await wait(600); await shot('sp17_bullet_ripples');
  const wstats = await ev(() => { const w = window.__game.water; return { ripples: w.rip.filter(r => r.w > 0).length, drops: w.drops.live, level: w.level, heightRiver: w.heightAt(0, -330), heightLand: w.heightAt(0, 0) }; });
  console.log('water after shots', JSON.stringify(wstats));
  // a rocket at the water (the real rocket path: launchRocket -> updateRockets -> hitTest -> explosion at the surface)
  await ev(async () => {
    const g = window.__game, V = g.camera.position.constructor;
    const st = await import('/src/game/state.js');
    const w = st.makeWeapon('rocket', 2, g.power() || 10);
    g.weapons.launchRocket(new V(4, 3, -292), new V(10, -3, -322), st.weaponStats(w), w);
  });
  await wait(900); await shot('sp18_rocket_column');
  await wait(1400); await shot('sp19_rocket_aftermath');
  // a car dropped into the river
  await ev(() => { const g = window.__game, V = g.camera.position.constructor; window.__car = g.vehicles.spawn('car_sport', '#a3121f', new V(-14, 7, -318), .6); });
  await wait(1500); await shot('sp20_car_splash');
  await wait(2500);
  const carState = await ev(() => { const c = window.__car; return { y: +c.pos.y.toFixed(2), wet: !!c.wet }; });
  console.log('car', JSON.stringify(carState));
  await shot('sp21_car_floating');
  // wade in, then swim (third person)
  await setP(20, -1, RZ + 34, Math.PI, -.25, true);
  await ev(() => { const g = window.__game; window.__walk = setInterval(() => { g.input.keys && g.input.keys.add && g.input.keys.add('KeyW'); }, 50); });
  await ev(() => { const g = window.__game; g.input.key = (c => (orig => k => k === 'KeyW' || orig(k))(g.input.key.bind(g.input)))(); });
  await wait(2500); await shot('sp22_wading');
  await wait(3500);
  const swim = await ev(() => { const P = window.__game.player; return { y: +P.pos.y.toFixed(2), swimming: !!P.swimming, depth: +(window.__game.water.level - P.pos.y).toFixed(2) }; });
  console.log('swim', JSON.stringify(swim));
  await shot('sp23_swimming');
  await ev(() => { const g = window.__game; clearInterval(window.__walk); delete g.input.key; });

  // ---------------- take-off cinematic
  await ev(() => { const g = window.__game, w = g.world; const sp = w.spawn(); const P = g.player; P.pos.copy(sp.pos); P.avatar.root.position.copy(sp.pos); if (g.save.settings.view === 'third') g.toggleView(); });
  await wait(500);
  await ev(() => { const it = window.__game.world.interactables.find(i => i.id === 'ship'); it.action(); });
  await waitState('cinematic');
  await wait(1500); await shot('sp24_takeoff_spool');
  await wait(1800); await shot('sp25_takeoff_climb');
  await waitPlay();
  const back = await ev(() => ({ world: window.__game.world.constructor.name, state: window.__game.state }));
  console.log('back', JSON.stringify(back));
  await wait(1500); await shot('sp26_back_on_ship');
  console.log('errors', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})();
