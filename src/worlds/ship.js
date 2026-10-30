// The player's ship: the hub that replaces the main menu. Every old menu screen lives at a station here.
import * as THREE from 'three';
import { World } from './world.js';
import { spaceSky, orbitPlanet } from './sky.js';
import { DESTINATIONS, ARCHETYPES } from '../game/data.js';
import { Weapons } from '../game/weapons.js';

const V = a => new THREE.Vector3(a[0], a[1], a[2]);
const _v = new THREE.Vector3(), _d = new THREE.Vector3();

const ORBIT_COLORS = {
  earth: Object.assign(['#1e5aa8', '#2a6a3a', '#c9b48a'], { ocean: true }),
  ares: ['#b2481e', '#d98a52', '#6a2a14'], vesper: ['#c9dbe6', '#8fb0c4', '#f4fbff'],
  thalassa: ['#2c8a6a', '#1b5a48', '#7dd8a8'], pyrrhos: ['#3a1a10', '#c23a10', '#ffb040'], nyx: ['#4a2a7a', '#9a6ad8', '#1a0d33'],
};

export class ShipWorld extends World {
  constructor(game) {
    super(game);
    this.kind = 'ship'; this.name = 'The Wayfarer'; this.region = 'In orbit';
    this.surface = 'metal'; this.combat = false;
  }

  async build(progress) {
    const g = this.g, A = g.assets, sc = this.scene;
    const layout = A.json.ship_interior;
    this.layout = layout;
    const orbitId = g.save.lastDest || 'earth';
    const dest = DESTINATIONS.find(d => d.id === orbitId) || DESTINATIONS[0];
    this.region = 'In orbit · ' + dest.name;
    progress(.1, 'Pressurising decks');
    const ship = A.clone('ship_interior');
    ship.traverse(o => {
      if (!o.isMesh) return;
      const n = o.material.name;
      if (n === 'skylight_glass' || n === 'window_glass') {
        o.material = o.material.clone(); o.material.transparent = true; o.material.opacity = .08; o.material.roughness = .02;
        o.material.metalness = 0; o.material.envMapIntensity = 2.0; o.castShadow = false; o.receiveShadow = false; o.renderOrder = 5;
      }
      if (/floor/.test(n)) { o.castShadow = false; o.material.envMapIntensity = .8; }
      if (/wall|ceil/.test(n)) o.material.envMapIntensity = .5;
      if (/light_panel|neon|screen|holo/.test(n)) { o.castShadow = false; o.receiveShadow = false; }
      if (n === 'holo') { o.material.transparent = true; o.material.depthWrite = false; o.material.blending = THREE.AdditiveBlending; }
    });
    sc.add(ship);
    this.ship = ship;
    for (const c of layout.colliders) this.collision.add(c);
    this.collision.floorY = 0;
    progress(.35, 'Bringing reactor online');
    // ---------------- lighting
    sc.add(new THREE.HemisphereLight(0xaec4e6, 0x2a251c, .9));
    for (const L of layout.lights) {
      if (L.kind === 'sun') {
        const s = new THREE.DirectionalLight(L.color, L.intensity * 2.2);
        s.position.copy(V(L.pos)); s.target.position.copy(V(L.target));
        s.castShadow = true;
        const q = g.renderer.q;
        s.shadow.mapSize.set(q.shadow, q.shadow);
        Object.assign(s.shadow.camera, { left: -26, right: 26, top: 26, bottom: -26, near: 5, far: 90 });
        s.shadow.bias = -.0005; s.shadow.normalBias = .04;
        sc.add(s, s.target);
        this.sun = s;
        this.sunDir = V(L.pos).sub(V(L.target)).normalize();
      } else if (L.kind === 'spot') {
        const s = new THREE.SpotLight(L.color, L.intensity * 3, 34, L.angle, .55, 2);
        s.position.copy(V(L.pos)); s.target.position.copy(V(L.target));
        sc.add(s, s.target);
      } else if (L.kind === 'point') {
        const p = new THREE.PointLight(L.color, L.intensity * 4, L.dist * 1.4, 2); p.position.copy(V(L.pos)); sc.add(p);
      } else if (L.kind === 'weld') {
        this.weldPos = V(L.pos);
      }
    }
    // volumetric light shafts falling from each skylight along the sun direction
    this.addShafts();
    // ---------------- sky + planet below
    const sky = spaceSky({ sunDir: this.sunDir });
    sc.add(sky); this.sky = sky;
    const planet = orbitPlanet(ORBIT_COLORS[dest.id] || ORBIT_COLORS.earth, this.sunDir, 520);
    planet.position.set(-150, -560, 520);
    sc.add(planet); this.planet = planet;
    progress(.55, 'Calibrating armory');
    // ---------------- stations
    const st = layout.stations;
    const near = id => V(st[id].pos);
    const add = (id, action, extra = {}) => this.interactables.push({ id, pos: near(id), r: 1.7, label: st[id].label, verb: st[id].verb, key: 'E', action, ...extra });
    add('captain', () => g.station('captain'));
    add('briefing', () => g.station('briefing'));
    add('wardrobe', () => g.station('wardrobe'));
    add('engineering', () => g.station('engineering'));
    add('record', () => g.station('record'));
    add('armory', () => g.station('armory'));
    add('gunsmith', () => g.station('gunsmith'));
    add('garage', () => g.station('garage'));
    this.stations = st;
    // armory rack guns
    this.rack = ship.getObjectByName('ST_armory');
    this.bench = ship.getObjectByName('ST_gunsmith');
    this.refreshArmory();
    // garage car
    this.refreshCar();
    // machines
    this.welder = {
      turret: ship.getObjectByName('welder_turret'), a1: ship.getObjectByName('welder_arm1'), a2: ship.getObjectByName('welder_arm2'),
      head: ship.getObjectByName('welder_head'), tip: ship.getObjectByName('welder_tip'),
    };
    this.weldLight = new THREE.PointLight(0x9fd8ff, 0, 14, 2);
    sc.add(this.weldLight);
    this.weldT = 0; this.weldOn = false;
    this.holo = ship.getObjectByName('holo_globe');
    this.nav = ship.getObjectByName('nav_holo');
    progress(.75, 'Capturing reflections');
    // environment reflections captured from the hangar itself (car paint, chrome, glass)
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    const envScene = sc;
    const prevSky = sky.visible;
    this.envRT = pm.fromScene(envScene, 0.02, .1, 200, { position: new THREE.Vector3(2, 3, -16) });
    sky.visible = prevSky;
    sc.environment = this.envRT.texture;
    sc.environmentIntensity = .7;
    pm.dispose();
    this.disposables.push(this.envRT);
    sc.fog = new THREE.Fog(0x05070c, 60, 400);
    progress(1, 'Ready');
  }

  addShafts() {
    const d = this.sunDir, top = 10.9, h = top;
    const sx = -d.x / d.y, sz = -d.z / d.y;
    const geo = new THREE.BoxGeometry(3.3, h, 3.3, 1, 1, 1);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i) + h / 2;            // 0 at floor .. h at roof
      const down = top - y;
      pos.setX(i, pos.getX(i) + sx * down); pos.setZ(i, pos.getZ(i) + sz * down); pos.setY(i, y);
    }
    geo.computeVertexNormals();
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      uniforms: { c: { value: new THREE.Color(1.0, .9, .75) }, top: { value: top } },
      vertexShader: 'varying float vY;varying vec3 vN,vV;void main(){vY=position.y;vec4 mv=modelViewMatrix*vec4(position,1.);vN=normalize(normalMatrix*normal);vV=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}',
      fragmentShader: 'uniform vec3 c;uniform float top;varying float vY;varying vec3 vN,vV;void main(){float f=smoothstep(0.,top,vY)*.75+.25;float edge=pow(1.-abs(dot(vN,vV)),1.5);gl_FragColor=vec4(c*.028*f*(.4+edge),1.);}',
    });
    for (let x = -10; x <= 10; x += 4) for (let z = -6; z >= -28; z -= 4) {
      const m = new THREE.Mesh(geo, mat); m.position.set(x, 0, z); m.renderOrder = 6; m.frustumCulled = false;
      this.scene.add(m);
    }
  }

  refreshArmory() {
    const g = this.g;
    (this.rackGuns || []).forEach(o => o.removeFromParent());
    this.rackGuns = [];
    if (!this.rack) return;
    // the three equipped weapons and the best spare hang on the rack
    const list = [0, 1, 2].map(i => g.weapons.equipped(i)).filter(Boolean);
    const spare = g.save.inventory.filter(w => !g.save.equipped.includes(w.uid)).sort((a, b) => b.power - a.power)[0];
    if (spare) list.push(spare);
    list.slice(0, 4).forEach((w, i) => {
      const slot = this.rack.getObjectByName('SLOT_' + i); if (!slot) return;
      const gun = g.assets.clone(ARCHETYPES[w.arch].model);
      gun.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); Weapons.styleMesh(o, w); } });
      gun.rotation.set(0, Math.PI / 2, 0); gun.scale.setScalar(1.3);
      slot.add(gun); this.rackGuns.push(gun);
    });
    // gunsmith display: current primary floating on the holo pad
    const disp = this.bench && this.bench.getObjectByName('DISPLAY');
    if (disp) {
      if (this.display) this.display.removeFromParent();
      const w = g.weapons.equipped(0);
      if (w) {
        const gun = g.assets.clone(ARCHETYPES[w.arch].model);
        gun.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); Weapons.styleMesh(o, w); } });
        gun.scale.setScalar(1.6); disp.add(gun); this.display = gun;
      }
    }
  }

  refreshCar() {
    const g = this.g;
    if (this.car) this.car.removeFromParent();
    const c = g.assets.clone(g.save.car.model);
    c.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); if (o.material.name === 'car_paint') { o.material.color.set(g.save.car.paint); o.material.envMapIntensity = 1.6; } } });
    c.position.copy(V(this.layout.stations.garage.car)); c.position.y = .35;
    c.rotation.y = 0;
    this.scene.add(c); this.car = c;
  }

  objectives() {
    const g = this.g;
    const o = [{ text: 'Plot a jump', sub: 'Captain\u2019s chair \u00b7 bridge (forward)' }];
    const ready = g.save.contracts.filter(c => c.done).length;
    if (ready) o.push({ text: ready + ' contract reward' + (ready > 1 ? 's' : '') + ' ready', sub: 'Briefing table \u00b7 commons' });
    return o;
  }

  spawn() {
    const s = this.layout.stations._spawn;
    const p = V(s.pos), look = V(s.look);
    return { pos: p, yaw: Math.atan2(look.x - p.x, look.z - p.z) };
  }

  update(dt) {
    const g = this.g, t = g.time;
    if (this.sky) this.sky.position.copy(g.camera.position);
    if (this.planet) { this.planet.rotation.y += dt * .004; this.planet.material.uniforms.time.value = t; }
    if (this.holo) { this.holo.rotation.y += dt * .5; this.holo.position.y = 1.7 + Math.sin(t * 1.3) * .05; }
    if (this.nav) this.nav.rotation.y -= dt * .7;
    if (this.display) { this.display.rotation.y += dt * .6; }
    if (this.car) this.car.position.y = .35 + Math.sin(t * 1.8) * .04;
    // ---- welding robot: reach, weld a seam, retract; sparks + flicker light + crackle
    const W = this.welder;
    if (W.a1) {
      this.weldT += dt;
      const cyc = this.weldT % 7.0;
      const reach = cyc < 1.2 ? cyc / 1.2 : cyc < 5.2 ? 1 : cyc < 6.2 ? 1 - (cyc - 5.2) : 0;
      const e = reach * reach * (3 - 2 * reach);
      const seam = cyc > 1.2 && cyc < 5.2 ? Math.sin((cyc - 1.2) / 4 * Math.PI * 2) * .22 : 0;
      W.turret.rotation.y = seam - .1 * (1 - e);
      W.a1.rotation.x = -.15 - .55 * e;
      W.a2.rotation.x = -.35 - .95 * e;
      W.head.rotation.x = -.25 - .45 * e;
      this.weldOn = cyc > 1.4 && cyc < 5.1;
      if (this.weldOn) {
        W.tip.getWorldPosition(_v);
        _d.set(0, .6, 1).normalize();
        g.fx.weld(_v, _d);
        this.weldLight.position.copy(_v);
        this.weldLight.intensity = 14 + Math.random() * 30;
        this.weldLight.color.setHSL(.55, .6, .75 + Math.random() * .2);
      } else this.weldLight.intensity *= .7;
      g.audio.weldLoop(); g.audio.updateWeld(_v, this.weldOn);
    }
  }
}
