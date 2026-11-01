// WORLD EX — boot, title, loading, world travel, ship stations, game loop, progression and saving.
import * as THREE from 'three';
import { Renderer } from './core/renderer.js';
import { Input } from './core/input.js';
import { Audio } from './core/audio.js';
import { Assets } from './core/assets.js';
import { Player } from './game/player.js';
import { Weapons } from './game/weapons.js';
import { Combat } from './game/combat.js';
import { EnemyManager } from './game/enemies.js';
import { Vehicles } from './game/vehicles.js';
import { FX } from './game/fx.js';
import { Inspect } from './ui/inspect.js';
import { Viewmodel } from './game/viewmodel.js';
import { TouchControls, isTouchDevice } from './ui/touch.js';
import { HUD } from './ui/hud.js';
import { Menus } from './ui/menus.js';
import { ShipWorld } from './worlds/ship.js';
import { EarthWorld } from './worlds/earth.js';
import { PlanetWorld } from './worlds/planet.js';
import { VanthosWorld } from './worlds/vanthos/world.js';
import { MetroWorld } from './worlds/vanthos/metro.js';
import { spaceSky, orbitPlanet, planetMaps } from './worlds/sky.js';
import { DESTINATIONS, ARCHETYPES, armorStats } from './game/data.js';
import { newSave, load, save, wipe, xpForLevel, refreshContracts, DEFAULT_SETTINGS, vaultOverflow } from './game/state.js';
import { Clock } from './game/clock.js';

// Models are loaded per world: BOOT_MODELS before the ship (everything the hub and the player always need), the
// rest when a world is entered (WORLD_MODELS). Leaving a world frees its large models again, so memory stays bounded.
const BOOT_MODELS = [
  ['ship_interior', 'ship_interior.glb', 10], ['viewmodel_arms', 'viewmodel_arms.glb', 1], ['ship_jumper', 'ship_jumper.glb', 2],
  ['board_sport', 'board_sport.glb', 1], ['board_utility', 'board_utility.glb', 1], ['props_world', 'props_world.glb', 2],
  ['enemy_trooper', 'enemy_trooper.glb', 1], ['enemy_brute', 'enemy_brute.glb', 1], ['npc_vendor', 'npc_vendor.glb', 1],
  ...Object.values(ARCHETYPES).map(a => [a.model, a.model + '.glb', 1]), ['gun_attach', 'gun_attach.glb', 1],
];
const CREATURES = [...['stalker', 'hulk', 'mutant', 'swimmer', 'elite'].map(k => ['alien_' + k, 'alien_' + k + '.glb', 1]),
  ...['mite', 'host', 'bladder', 'amalgam'].map(k => ['writhe_' + k, 'writhe_' + k + '.glb', 1])];
const WORLD_MODELS = {
  ship: [],
  earth: [['cars', 'cars.glb', 8], ['trees', 'trees.glb', 8], ['spaceport', 'spaceport.glb', 6], ['city_buildings', 'city_buildings.glb', 2], ['downtown', 'downtown.glb', 4], ['downtown_street', 'downtown_street.glb', 1],
    ['rural', 'rural.glb', 1], ['player_female_npc', 'player_female_npc.glb', 4], ['player_male_npc', 'player_male_npc.glb', 3],
    ['civ_female', 'civ_female.glb', 1], ['civ_male', 'civ_male.glb', 1], ['car_sport', 'car_sport.glb', 1], ['car_utility', 'car_utility.glb', 1],
    ['ship_dropship', 'ship_dropship.glb', 1]],
  vanthos: [['vanthos', 'vanthos.glb', 4], ['cars', 'cars.glb', 8], ...CREATURES],
  vanthos_metro: [['vanthos', 'vanthos.glb', 4], ...CREATURES],
  planet: [['trees', 'trees.glb', 8], ['cars', 'cars.glb', 8], ...CREATURES],
};
const worldModels = id => WORLD_MODELS[id] || WORLD_MODELS.planet;
const ALL_WORLD_MODELS = new Set(Object.values(WORLD_MODELS).flat().map(m => m[0]));
const playerModel = body => body === 'male' ? ['player_male', 'player_male.glb', 10] : ['player_female', 'player_female.glb', 10];
const TEXTURES = ['concrete', 'asphalt', 'rock', 'sand', 'ice', 'moss', 'facade_e', 'ribbon_e'];

class Game {
  constructor() {
    this.THREE_REV = THREE.REVISION;
    const sv = load();
    this.hasSave = !!sv;
    this.save = sv || newSave();
    this.canvas = document.getElementById('view');
    this.renderer = new Renderer(this.canvas, this.save.settings);
    this.input = new Input(this.canvas);
    this.audio = new Audio(this.save.settings);
    this.assets = new Assets(this.renderer.r);
    this.camera = new THREE.PerspectiveCamera(this.save.settings.fov, innerWidth / innerHeight, .1, 2000);
    this.renderer.camera = this.camera;
    this.hud = new HUD(this);
    this.menus = new Menus(this);
    this.time = 0; this.fps = 60; this.state = 'boot'; this.paused = false;
    this.scene = null; this.world = null;
    this.input.onLockChange = locked => this.onLockChange(locked);
    this.touch = isTouchDevice() ? new TouchControls(this) : null;
    if (this.touch && !sv) { this.save.settings.quality = 'medium'; this.save.settings.fov = 74; }
    // phones (and the low preset) cap textures at 1024 px: GPU memory is what kills a mobile tab on the big worlds
    this.assets.maxTex = window.__MAXTEX || (this.touch ? 1024 : this.save.settings.quality === 'low' ? 1024 : Infinity);
    addEventListener('keydown', e => this.onKey(e));
    window.__game = this;
    this.loop = this.loop.bind(this);
  }

  async boot() {
    const bar = document.querySelector('#boot .boot-bar i');
    try {
      await this.assets.loadAll([{ type: 'model', name: 'ship_jumper', file: 'ship_jumper.glb' }], p => { if (bar) bar.style.width = (30 + p * 70) + '%'; });
    } catch (e) { return this.fatal(e); }
    this.buildTitleScene();
    this.state = 'title';
    this.menus.showTitle(this.hasSave);
    document.getElementById('boot').style.opacity = 0;
    setTimeout(() => document.getElementById('boot').remove(), 700);
    this.last = performance.now();
    requestAnimationFrame(this.loop);
  }

  fatal(e) {
    console.error(e);
    const b = document.getElementById('boot') || document.body;
    b.innerHTML = `<div style="font:600 16px Rajdhani,sans-serif;letter-spacing:.2em;color:#ff4a3d;text-align:center;padding:20px">FAILED TO START<br><small style="color:#aaa;letter-spacing:0">${String(e.message || e)}</small></div>`;
  }

  // ---------------------------------------------------------------- title scene (live 3D behind the menu)
  buildTitleScene() {
    const sc = new THREE.Scene();
    const sunDir = new THREE.Vector3(-.6, .35, -.7).normalize();
    sc.add(spaceSky({ sunDir }));
    const pl = orbitPlanet(Object.assign(['#1e5aa8', '#2a6a3a', '#c9b48a'], { ocean: true }), sunDir, 300);
    pl.position.set(120, -260, -380); sc.add(pl);
    const ship = this.assets.clone('ship_jumper'); sc.add(ship);
    const sun = new THREE.DirectionalLight(0xfff1dc, 3.5); sun.position.copy(sunDir).multiplyScalar(50); sc.add(sun);
    sc.add(new THREE.HemisphereLight(0x6a8ac0, 0x101018, .35));
    const rim = new THREE.PointLight(0x1ad8ff, 40, 30, 2); rim.position.set(0, 4, 14); sc.add(rim);
    const pm = new THREE.PMREMGenerator(this.renderer.r);
    sc.environment = pm.fromScene(new THREE.Scene().add(spaceSky({ sunDir })), .05).texture; pm.dispose();
    this.title = { sc, ship, planet: pl };
    this.scene = sc;
  }

  updateTitle(dt) {
    const T = this.title, t = this.time;
    T.ship.position.set(Math.sin(t * .1) * 2, Math.sin(t * .4) * .4, 0);
    T.ship.rotation.set(Math.sin(t * .3) * .05, t * .06 + 2.2, Math.sin(t * .25) * .12);
    T.planet.rotation.y += dt * .01; T.planet.material.uniforms.time.value = t;
    const a = t * .05;
    this.camera.position.set(Math.sin(a) * 22 - 6, 4 + Math.sin(t * .15) * 1.5, Math.cos(a) * 22);
    this.camera.lookAt(-4, 0, 0);
    if (this.camera.fov !== 50) { this.camera.fov = 50; this.camera.updateProjectionMatrix(); }
  }

  titleSettings() {
    // reuse the engineering panel over the title
    this.menus.hideTitle();
    this.openStationPanelOnly('engineering');
    this.menus.panel.querySelector('.pn-foot').innerHTML = '<button class="btn" data-act="leave">Back to title</button>';
  }

  titleCredits() {
    this.menus.hideTitle();
    const el = this.menus.panel; el.classList.remove('hidden'); this.menus.open = 'credits';
    el.innerHTML = `<div class="pn"><div class="pn-k">WORLD EX</div><div class="pn-h">Credits</div><div class="pn-body">
      <p class="guide"><b>Design, code, models and sound</b> — made for this project. Every character, weapon, vehicle, building, machine and texture was modelled with Python scripts run in headless Blender (<b>tools/blender</b>). Every sound is synthesised live with WebAudio.</p>
      <p class="guide"><b>Engine</b> — Three.js r${THREE.REVISION}.</p>
      <p class="guide"><b>Fonts</b> — Rajdhani and Inter (Google Fonts, falls back to system fonts offline).</p></div>
      <div class="pn-foot"><button class="btn" data-act="leave">Back to title</button></div></div>`;
  }

  // ---------------------------------------------------------------- start / travel
  async startGame(fresh) {
    if (this.state !== 'title') return;
    this.audio.start(); this.audio.applyVolumes();
    if (fresh) { wipe(); this.save = newSave(); this.renderer.settings = this.save.settings; this.audio.settings = this.save.settings; }
    this.state = 'loading';
    this.menus.hideTitle(); this.menus.close();
    this.input.wantLock = true;
    await this.fade(true);
    const ship = { name: 'The Wayfarer', desc: 'Your ship and home. Walk the decks to reach every station.' };
    this.menus.showLoading(ship, 'Boarding');
    this.audio.music('ship');
    try {
      await this.assets.loadAll([
        ...[...BOOT_MODELS, playerModel(this.save.character.body)].map(([name, file, weight]) => ({ type: 'model', name, file, weight, label: 'Loading ' + name.replace(/_/g, ' ') })),
        ...TEXTURES.map(t => ({ type: 'texture', name: t, file: t.endsWith('_e') ? t + '.jpg' : t + '_c.jpg', weight: .3, label: 'Texture ' + t })),
        ...['concrete', 'asphalt', 'rock', 'sand', 'ice', 'moss'].map(t => ({ type: 'texture', name: t + '_n', file: t + '_n.jpg', color: false, weight: .3 })),
        { type: 'json', name: 'ship_interior', file: 'ship_interior.json', weight: .2 },
        ...['earth_day', 'earth_clouds', 'earth_night', 'earth_ms'].map(t => ({ type: 'texture', name: t, file: t + '.jpg', color: t === 'earth_day', weight: .4, label: 'Charting Earth', max: 2048 })),
      ], (p, l) => this.menus.loading(p * .7, l));
      const T = this.assets.textures;
      planetMaps.earth = { day: T.earth_day, clouds: T.earth_clouds, night: T.earth_night, ms: T.earth_ms };
      for (const t of Object.values(planetMaps.earth)) { t.wrapS = THREE.RepeatWrapping; t.wrapT = THREE.ClampToEdgeWrapping; t.anisotropy = this.renderer.r.capabilities.getMaxAnisotropy(); t.needsUpdate = true; }
    } catch (e) { return this.fatal(e); }
    this.fx = null;
    this.player = new Player(this);
    this.weapons = new Weapons(this);
    this.combat = new Combat(this);
    this.enemies = new EnemyManager(this);
    this.vehicles = new Vehicles(this);
    this.viewmodel = new Viewmodel(this);
    this.inspect = new Inspect(this);
    this.viewmodel.recolor(this.save.character);
    this.player.setBody(this.save.character.body);
    await this.enterWorld('ship', p => this.menus.loading(.7 + p * .3, 'Preparing decks'));
    this.menus.hideLoading();
    this.state = 'play';
    await this.fade(false);
    this.hud.banner('The Wayfarer', 'Welcome aboard, Captain', 3.5);
    if (this.save.armoryDelivered) {
      const n = this.save.armoryDelivered; delete this.save.armoryDelivered; this.persist();
      setTimeout(() => this.hud.toast(n + ' new weapons delivered to your armoury — kinetic and living. Press I to see them'), 4200);
    }
    if (!this.save.stats.visited.length) setTimeout(() => this.hud.toast('Walk to the captain’s chair on the bridge to plot a jump'), 3800);
  }

  fade(on) { return new Promise(r => { document.getElementById('fade').classList.toggle('on', on); setTimeout(r, 480); }); }

  async travel(id) {
    if (this.state !== 'play') return;
    // grab the pointer now, while the click that started the trip still counts as a user gesture,
    // so the player has full control the moment the new world appears
    this.paused = false; this.menus.hidePause();
    if (this.stationId) { this.menus.close(); this.stationId = null; this.camFocus = null; this.camera.clearViewOffset(); }
    this.input.enabled = true; this.input.wantLock = true; this.input.lock();
    this.state = 'loading';
    this.persist();
    if (this.vehicles.current) this.vehicles.exit();
    if (this.world && this.world.depart) { try { await this.world.depart(id); } catch (e) { console.error(e); } }   // take-off cinematic
    const toShip = id === 'ship';
    const dest = toShip ? { name: 'The Wayfarer', desc: 'Breaking atmosphere. The ship will hold orbit above ' + (DESTINATIONS.find(d => d.id === this.save.lastDest) || DESTINATIONS[0]).name + '.' } : DESTINATIONS.find(d => d.id === id);
    if (!toShip) this.audio.warp();
    await this.fade(true);
    this.menus.showLoading(dest, toShip ? 'Returning to orbit' : (dest.kind === 'city' ? 'Descending to' : 'Jumping to'));
    await new Promise(r => setTimeout(r, 60));
    await this.enterWorld(id, (p, l) => this.menus.loading(p, l));
    await new Promise(r => setTimeout(r, 250));
    this.menus.hideLoading();
    this.state = 'play';
    this.paused = false; this.input.enabled = true;
    if (this.player.mode === 'seat') this.player.mode = 'foot';
    if (!this.input.locked) this.input.lock();
    const arrive = this.world.arrive ? this.world.arrive() : null;   // landing cinematic (runs under the fade-in)
    await this.fade(false);
    if (arrive) await arrive;
    const w = this.world;
    this.hud.banner(w.name, w.region, 3.5);
  }

  async enterWorld(id, progress) {
    // tear down
    if (this.world) {
      this.enemies.clear(); this.combat.reset(); this.vehicles.clear(); this.weapons.clearRockets();
      this.audio.stopAllLoops();
      this.fx && this.fx.dispose();
      this.world.dispose();
    }
    // free the large models the next world does not use, then fetch the ones it needs
    const need = worldModels(id), keep = new Set(need.map(m => m[0]));
    this.assets.unload([...ALL_WORLD_MODELS].filter(n => !keep.has(n)));
    const fetchP = need.length ? .55 : 0;
    try {
      await this.assets.loadAll(need.map(([name, file, weight]) => ({ type: 'model', name, file, weight, label: 'Loading ' + name.replace(/_/g, ' ') })),
        (p, l) => progress(p * fetchP, l));
    } catch (e) { return this.fatal(e); }
    const buildProgress = progress;
    progress = (p, l) => buildProgress(fetchP + p * (1 - fetchP), l);
    let w;
    if (id === 'ship') w = new ShipWorld(this);
    else if (id === 'earth') w = new EarthWorld(this);
    else if (id === 'vanthos') w = new VanthosWorld(this, DESTINATIONS.find(d => d.id === id));
    else if (id === 'vanthos_metro') w = new MetroWorld(this, this.metroEntry);
    else w = new PlanetWorld(this, DESTINATIONS.find(d => d.id === id));
    this.world = w; this.scene = w.scene;
    this.fx = new FX(w.scene);
    await w.build(progress);
    w.scene.add(this.player.avatar.root);
    // seats exported with a layout (ship) become sit points
    for (const st of (w.layout && w.layout.seats) || []) w.addSeat(new THREE.Vector3(st.pos[0], st.pos[1], st.pos[2]), st.yaw, st.label || 'Seat');
    // shadow cameras also see layer 1, where the player's body lives in first person
    w.scene.traverse(o => { if (o.isLight && o.shadow) o.shadow.camera.layers.enable(1); });
    const sp = w.spawn();
    this.player.spawn(sp.pos, sp.yaw);
    this.player.armed = w.combat;
    this.weapons.refill(); this.weapons.refreshModel();
    this.hud.setMode(w.combat); this.hud.setLocation(w.region, w.name);
    this.hud.show(true); this.hud.dirty = true;
    if (id !== 'ship') {
      if (id !== 'vanthos_metro') this.save.lastDest = id;
      if (!this.save.stats.visited.includes(id)) this.save.stats.visited.push(id);
    }
    this.audio.resetBus && this.audio.resetBus();
    this.audio.ambience(id === 'ship' ? 'ship' : id === 'earth' ? 'city' : 'wind');
    this.audio.musicKind = null; this.audio.music(id === 'ship' ? 'ship' : id === 'earth' ? 'earth' : 'planet');
    if (id === 'ship') this.audio.weldLoop();
    this.renderer.setBloom(id === 'ship' ? .38 : .3, 1.0, .4);
    this.renderer.r.toneMappingExposure = id === 'ship' ? 1.0 : 1.05;
    // compile shaders up front so the first frame does not hitch
    // (async: the browser compiles in parallel where it can, and the loading screen keeps animating meanwhile)
    try { await Promise.race([this.renderer.r.compileAsync(w.scene, this.camera), new Promise(r => setTimeout(r, 8000))]); } catch (e) { /* optional */ }
    this.persist();
  }

  // ---------------------------------------------------------------- first / third person
  // First person is the default. The third-person view stays available on T (and in the settings).
  carFirstPerson() { const p = this.player; return !!p && this.save.settings.view !== 'third' && p.mode === 'car' && !this.stationId; }

  firstPerson() {
    const p = this.player;
    // third person still looks through a magnified scope while aiming (the optic picture needs the first-person view)
    const scoping = p && p.aiming && this.weapons && this.weapons.zoom() >= 2;
    return !!p && (this.save.settings.view !== 'third' || scoping) && p.mode === 'foot' && !p.dead && !this.stationId;
  }

  toggleView() {
    const s = this.save.settings;
    s.view = s.view === 'third' ? 'first' : 'third';
    this.hud.toast(s.view === 'third' ? 'Third-person view' : 'First-person view');
    this.player.snapCamera = true;
    this.setAvatarLayer(); this.persist();
  }

  // In first person the body moves to layer 1: the camera skips it but it still casts a shadow.
  setAvatarLayer() {
    const p = this.player; if (!p || !p.avatar) return;
    const fp = this.firstPerson() || this.carFirstPerson() || (p.mode === 'sit' && this.save.settings.view !== 'third' && !this.stationId);
    const key = (p.avatar.gunHolder ? p.avatar.gunHolder.uuid : '-') + (p.avatar.wearKey || '');
    if (fp === this._fpLayer && p.avatar === this._fpAvatar && key === this._fpKey) return;
    this._fpLayer = fp; this._fpAvatar = p.avatar; this._fpKey = key;
    p.avatar.root.traverse(o => { if (o.isMesh) { if (fp) o.layers.set(1); else o.layers.set(0); } });
  }

  // ---------------------------------------------------------------- ship stations
  station(id) {
    const p = this.player, st = this.world.stations && this.world.stations[id];
    this.input.unlock(); this.input.enabled = false;
    this.stationId = id;
    const V = a => new THREE.Vector3(a[0], a[1], a[2]);
    if (st) {
      const look = V(st.look), pos = V(st.pos);
      const dir = look.clone().sub(pos).setY(0).normalize(), side = new THREE.Vector3(dir.z, 0, -dir.x);
      if (id === 'captain') {
        p.mode = 'seat'; p.pos.copy(V(st.seat)); p.yaw = Math.atan2(dir.x, dir.z);
        p.avatar.root.position.copy(p.pos); p.avatar.root.rotation.set(0, p.yaw, 0); p.avatar.play('Sit', .3);
        this.focusOn(p.pos.clone().addScaledVector(dir, -2.4).addScaledVector(side, 1.1).setY(2.3), p.pos.clone().addScaledVector(dir, 7).setY(1.3));
      } else if (id === 'wardrobe') {
        this.placeInWardrobe();
      } else {
        p.yaw = Math.atan2(dir.x, dir.z); p.avatar.root.rotation.set(0, p.yaw, 0);
        // three-quarter shot of the station over the player's shoulder
        const far = id === 'garage' ? 6.5 : 3.6;
        const v = dir.clone().negate().applyAxisAngle(new THREE.Vector3(0, 1, 0), -.55);
        const target = look.clone(); if (id === 'garage') target.y = .9;
        this.focusOn(target.clone().addScaledVector(v, far).setY(target.y + (id === 'garage' ? 1.8 : .75)), target);
      }
    }
    this.audio.ui('open');
    this.menus.openStation(id);
    this.hud.prompt(null);
  }

  placeInWardrobe() {
    const st = this.world.stations && this.world.stations.wardrobe; if (!st) return;
    const p = this.player, V = a => new THREE.Vector3(a[0], a[1], a[2]);
    p.pos.copy(V(st.stand)); p.yaw = Math.PI / 2; p.mode = 'seat';
    p.avatar.root.position.copy(p.pos); p.avatar.root.rotation.set(0, p.yaw, 0); p.avatar.play('IdleRelaxed', .2);
    this.wardrobeSpin = 0;
    this.wardrobeFocus((this.menus.open === 'wardrobe' && this.menus.tab) || 'face');
  }

  // wardrobe camera: close on the face for face/hair, full body otherwise
  wardrobeFocus(tab) {
    const p = this.player; if (this.stationId !== 'wardrobe') return;
    const hz = this.save.character.body === 'male' ? 1.72 : 1.57;
    if (tab === 'face' || tab === 'hair') this.focusOn(p.pos.clone().add(new THREE.Vector3(1.05, hz + .1, 0)), p.pos.clone().add(new THREE.Vector3(0, hz + .04, 0)), true);
    else this.focusOn(p.pos.clone().add(new THREE.Vector3(3.1, 1.25, 0)), p.pos.clone().add(new THREE.Vector3(0, 1.0, 0)), true);
  }

  // Blend the camera to a framed shot of a station (time based, so it lands the same at any frame rate).
  focusOn(pos, look, orbit = false) {
    const m = new THREE.Matrix4().lookAt(pos, look, new THREE.Vector3(0, 1, 0));
    this.camFocus = { pos, look, orbit, q: new THREE.Quaternion().setFromRotationMatrix(m),
      p0: this.camera.position.clone(), q0: this.camera.quaternion.clone(), fov0: this.camera.fov, t0: performance.now() };
    // shift the projection so the framed station sits right of the panel
    this.camera.setViewOffset(innerWidth, innerHeight, -innerWidth * .2, 0, innerWidth, innerHeight);
  }

  get water() { return (this.world && this.world.water) || null; }   // shared water API (src/game/water.js)

  get armor() { return armorStats(this.save.character, (this.player && this.player.avatar && this.player.avatar.wardrobe) || {}); }

  openInventory() {
    if (this.state !== 'play' || this.stationId || this.paused || !this.player || this.player.dead) return;
    if (this.vehicles.current) return;
    this.audio.ui('open'); this.hud.prompt(null);
    this.openStationPanelOnly('inventory');
  }

  openStationPanelOnly(id) {
    this.input.unlock(); this.input.enabled = false; this.stationId = id; this.camFocus = null; this.camera.clearViewOffset();
    this.menus.openStation(id);
  }

  closeStation() {
    const id = this.stationId;
    this.menus.close(); this.stationId = null; this.camFocus = null; this.camera.clearViewOffset();
    if (this.state === 'title') { this.menus.showTitle(load() !== null); return; }
    const p = this.player;
    if (p.mode === 'seat') {
      const st = this.world.stations && this.world.stations[id];
      p.mode = 'foot';
      if (st) { const v = st.pos; p.pos.set(v[0], v[1], v[2]); p.avatar.root.position.copy(p.pos); p.avatar.root.rotation.set(0, p.yaw, 0); }
    }
    if (id !== 'inventory' && id !== 'engineering') { p.camYaw = p.yaw + Math.PI; p.snapCamera = true; }
    if (id === 'inventory' && this.inspect) this.inspect.clear();
    this.input.enabled = true;
    if (this.world.refreshArmory) this.world.refreshArmory();
    this.audio.ui('back');
    this.persist();
    this.input.lock();
  }

  // ---------------------------------------------------------------- progression
  power() {
    const ws = [0, 1, 2].map(i => this.weapons ? this.weapons.equipped(i) : null).filter(Boolean);
    if (!ws.length) return 0;
    return Math.round(ws.reduce((s, w) => s + w.power, 0) / ws.length);
  }

  dmgScale() {
    const dp = this.world.destPower || 0;
    return Math.max(.55, Math.min(1.9, 1 + (dp - this.power()) / 110));
  }

  gain(kind, n, show = true) {
    const s = this.save;
    if (kind === 'credits') { s.credits += n; s.stats.creditsEarned += n; if (show) this.hud.feed('+' + n + ' credits', '#e3c26c'); return; }
    if (kind === 'xp') {
      s.xp += n;
      while (s.xp >= xpForLevel(s.level)) {
        s.xp -= xpForLevel(s.level); s.level++;
        this.audio.levelUp(); this.hud.banner('Level ' + s.level, 'Infusion cap raised · +5 alloy', 3);
        s.alloy += 5;
      }
      this.hud.dirty = true;
    }
  }

  addWeapon(w) {
    const s = this.save;
    // every new weapon is its own copy (unique uid) and wears a NEW tag until it is looked at in the inventory
    if (s.inventory.some(x => x.uid === w.uid)) w.uid += 'd' + Math.floor(Math.random() * 1e6);
    if (w.isNew === undefined) w.isNew = true;
    w.got = w.got || Date.now();
    s.inventory.push(w);
    // keep the vault bounded (VAULT_CAP): only a plain old spare is broken down, and the player is told
    const o = vaultOverflow(s);
    if (o) this.hud.feed('Vault full · ' + o.w.name + ' dismantled (+' + o.alloy + ' alloy)', '#9aa0a8');
    // empty slot? equip immediately
    const slot = ARCHETYPES[w.arch].slot;
    if (!s.equipped[slot]) { s.equipped[slot] = w.uid; this.weapons.refreshModel(); }
    this.persist();
  }

  onLoadoutChanged() { this.hud.dirty = true; if (this.world.refreshArmory) this.world.refreshArmory(); }

  contractEvent(id, n) {
    for (const c of this.save.contracts) {
      if (c.done || c.id !== id) continue;
      c.p += n;
      if (c.p >= c.n) { c.p = c.n; c.done = true; this.hud.banner('Contract complete', c.text, 3); this.audio.levelUp(); }
    }
  }

  claimContract(i) {
    const c = this.save.contracts[i]; if (!c || !c.done) return;
    this.save.contracts.splice(i, 1); this.save.contractsDone++;
    this.gain('credits', c.reward); this.gain('xp', 300);
    this.save.alloy += 5;
    refreshContracts(this.save);
    this.audio.pickup(3);
  }

  onEnemyKilled(e, crit) {
    const s = this.save.stats;
    s.kills++; if (crit) { s.precision++; this.contractEvent('precision', 1); }
    if (e.type === 'brute') { s.brutes++; this.contractEvent('brutes', 1); }
    if (e.type === 'drone') { s.drones++; this.contractEvent('drones', 1); }
    this.contractEvent('kills', 1);
    if (this.world.kind === 'city') this.contractEvent('earth', 1);
    this.gain('xp', e.T.xp + e.level * 4);
  }

  onPlayerDeath() {
    if (this.world.wanted) this.world.wanted.reset();
    this.hud.banner('You fell', 'Ghost-shell revival in 4 seconds', 4);
    this.input.enabled = true;
    setTimeout(async () => {
      if (!this.player.dead) return;
      await this.fade(true);
      const sp = this.world.spawn();
      this.player.spawn(sp.pos, sp.yaw);
      this.weapons.refill(); this.weapons.refreshModel();
      // calm any fight that was in progress so revival is fair
      for (const e of this.enemies.list) if (e.alive && e.pos.distanceTo(sp.pos) < 60) e.state = 'idle';
      await this.fade(false);
    }, 4000);
  }

  // ---------------------------------------------------------------- settings / save
  applySettings(k) {
    const s = this.save.settings;
    if (k === 'quality' || k === 'resScale') { this.renderer.settings = s; this.renderer.applyQuality(); }
    if (['master', 'music', 'sfx', 'muted'].includes(k)) this.audio.applyVolumes();
    if (k === 'fov') { this.camera.fov = s.fov; this.camera.updateProjectionMatrix(); }
    if (k === 'dynamicRes' && !s.dynamicRes) { this.renderer.scale = 1; this.renderer.resize(); }
    this.hud.dirty = true;
    this.persist();
  }

  persist() { if (this.state !== 'boot') save(this.save); }

  wipe() { wipe(); location.reload(); }

  async quitToTitle() {
    this.persist();
    this.menus.hidePause(); this.paused = false;
    await this.fade(true);
    location.reload();
  }

  resume() {
    this.paused = false; this.menus.hidePause(); this.input.enabled = true; this.input.lock();
  }

  // ---------------------------------------------------------------- input routing
  onKey(e) {
    if (e.code === 'F3') { this.save.settings.showFps = !this.save.settings.showFps; this.hud.dirty = true; e.preventDefault(); }
    if ((e.code === 'KeyI' || e.code === 'Tab') && this.state === 'play') {
      if (this.stationId === 'inventory') { this.closeStation(); return; }
      if (!this.stationId) { this.openInventory(); return; }
    }
    if (e.code === 'Escape') {
      if (this.state === 'title' && this.menus.open) { this.menus.close(); this.menus.showTitle(load() !== null); return; }
      if (this.state !== 'play') return;
      if (this.stationId) { this.closeStation(); return; }
      if (this.paused) { this.resume(); return; }
      this.pause();
    }
    if (this.state === 'title' && (e.code === 'Enter' || e.code === 'Space') && !this.menus.open) this.startGame(false);
  }

  pause() {
    if (this.state !== 'play' || this.stationId) return;
    this.paused = true; this.input.enabled = false; this.input.unlock();
    if (this.touch) this.touch.show(false);
    this.menus.showPause();
  }

  onLockChange(locked) {
    // browser released the pointer (Esc) while playing -> pause menu
    if (!locked && this.state === 'play' && !this.stationId && !this.paused && !this.player.dead) this.pause();
  }

  // ---------------------------------------------------------------- main loop
  loop(now) {
    requestAnimationFrame(this.loop);
    let dt = (now - this.last) / 1000; this.last = now;
    if (!(dt > 0)) dt = 1 / 60;
    dt = Math.min(dt, 1 / 20);
    this.time += dt;
    this.fps += (1 / Math.max(dt, 1e-3) - this.fps) * .05;
    if (this.state === 'title' || (this.state === 'loading' && !this.world)) {
      this.updateTitle(dt);
      this.renderer.render(this.title.sc, this.camera);
      this.input.endFrame();
      return;
    }
    if (this.state === 'loading') { this.input.endFrame(); return; }
    if (this.cine) this.cine(dt); else if (!this.paused) this.update(dt);   // cutscenes (src/game/cinematic.js) own the frame
    this.renderer.render(this.scene, this.camera, this.viewmodel && this.viewmodel.active && !this.cine ? this.viewmodel.scene : null);
    if (this.stationId === 'inventory' && this.inspect) this.inspect.render(dt);
    this.renderer.govern(dt);
    this.input.endFrame();
  }

  update(dt) {
    const p = this.player, input = this.input, w = this.world;
    this.save.stats.time += dt;
    if (!this.clock || this.clock.save !== this.save) this.clock = new Clock(this.save);
    this.clock.update(dt);
    if (input.enabled && input.locked) p.look(input, dt);
    // interactions
    const canAct = input.enabled && !this.stationId && !p.dead;
    let focus = null;
    if (canAct && p.mode === 'foot') focus = w.focus(p);
    let carNear = null;
    if (canAct && p.mode === 'foot' && w.allowCars) carNear = this.vehicles.nearest(p.pos);
    if (focus) this.hud.prompt(focus);
    else if (carNear) this.hud.prompt({ key: 'E', verb: carNear.board ? 'Ride' : 'Drive', label: carNear.S.name });
    else if (p.mode === 'sit' && !this.stationId) this.hud.prompt({ key: 'E', verb: 'Stand up', label: '' });
    else if (p.mode === 'car') this.hud.prompt(null);
    else this.hud.prompt(null);
    if (canAct && input.pressed('KeyE')) {
      if (p.mode === 'car') this.vehicles.exit();
      else if (focus) { focus.action(); input.consume('KeyE'); }     // the same press must not also stand you up
      else if (carNear) this.vehicles.enter(carNear);
    }
    if (canAct && input.pressed('KeyV') && w.allowCars) this.vehicles.summon();
    if (input.enabled && !this.stationId && input.pressed('KeyT')) this.toggleView();
    p.update(dt, input, w.collision);
    this.weapons.update(dt, input);
    this.vehicles.update(dt, input);
    if (p.mode === 'car') {
      // chase camera drifts behind the car when the mouse is idle
      const c = this.vehicles.current;
      // (not while a touch stick is steering: the stick is camera-relative, a moving camera would keep turning the ride)
      if (c && Math.abs(input.mx) < 1 && c.speed > 3 && !(input.axisX || input.axisY)) { let d = (c.yaw + Math.PI) - p.camYaw; d = Math.atan2(Math.sin(d), Math.cos(d)); p.camYaw += d * Math.min(1, dt * 2.5); p.camPitch += (-.18 - p.camPitch) * Math.min(1, dt * 2); }
    }
    this.enemies.update(dt);
    this.combat.update(dt);
    w.update(dt);
    p.updateCamera(dt, w.collision);
    // station framing shot overrides the follow camera
    if (this.camFocus) {
      const f = this.camFocus;
      if (f.orbit) p.avatar.root.rotation.y = p.yaw + (this.wardrobeSpin || 0);
      let k = Math.min(1, (performance.now() - f.t0) / 900); k = k * k * (3 - 2 * k);
      this.camera.position.lerpVectors(f.p0, f.pos, k);
      this.camera.quaternion.slerpQuaternions(f.q0, f.q, k);
      this.camera.fov = f.fov0 + (55 - f.fov0) * k; this.camera.updateProjectionMatrix();
    }
    this.setAvatarLayer();
    this.viewmodel.update(dt, input);
    if (this.touch) { this.touch.show(!this.stationId && !p.dead); this.touch.update(); }
    this.fx.update(dt, (x, z) => w.collision.ground(x, z));
    this.hud.markers = w.markers();
    this.objT = (this.objT || 0) - dt;
    if (this.objT <= 0) { this.objT = .5; this.hud.setObjectives(w.objectives()); }
    this.audio.combat += ((this.enemies.combatCount > 0 ? 1 : 0) - this.audio.combat) * Math.min(1, dt * .5);
    this.hud.setHint(!input.locked && !this.stationId && !this.paused ? 'Click to take control' : (p.mode === 'car' ? (this.vehicles.current && this.vehicles.current.board ? 'E step off · Shift boost · Space jump' : 'E exit · Shift boost · Space handbrake') : ''));
    this.hud.update(dt);
    this.autosaveT = (this.autosaveT || 0) + dt;
    if (this.autosaveT > 20) { this.autosaveT = 0; this.persist(); }
  }
}

const game = new Game();
game.boot();

// title: first click anywhere starts audio and the game
document.getElementById('title').addEventListener('click', e => {
  if (!e.target.closest('[data-act]')) game.startGame(false);
});

// wardrobe: drag to spin the character (mouse or touch)
let drag = null;
addEventListener('pointerdown', e => { if (game.stationId === 'wardrobe' && !e.target.closest('.pn,.wallet')) drag = e.clientX; });
addEventListener('pointermove', e => { if (drag !== null) { game.wardrobeSpin = (game.wardrobeSpin || 0) + (e.clientX - drag) * .01; drag = e.clientX; } });
addEventListener('pointerup', () => { drag = null; });
addEventListener('pointercancel', () => { drag = null; });
