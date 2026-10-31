// The player's ship: the hub that replaces the main menu. Every old menu screen lives at a station here.
// Cockpit bridge with a faceted canopy -> commons with hull portholes -> hangar bay open to space behind a force field.
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

// ------------------------------------------------------------------ live ship screens
// Every mesh whose material is named screen_<kind> shows one shared canvas per kind, redrawn at ~12 Hz and only
// while a screen of that kind is within SCREEN_RANGE of the camera.
const SCREEN_HZ = 12, SCREEN_RANGE = 25;
const KINDS = {
  data: [256, 160, '#62e4ff', '#03111a'], graph: [256, 160, '#52ffbe', '#02130e'], radar: [256, 256, '#58ff94', '#020f07'],
  nav: [256, 160, '#86c8ff', '#030918'], status: [256, 160, '#62e4ff', '#030f18'], amber: [256, 160, '#ffba4e', '#130a02'],
  keys: [128, 48, '#70d8ff', '#020a10'],
};
const WORDS = ['COOLANT LOOP', 'HULL STRESS', 'DRIVE CORE', 'LIFE SUPPORT', 'PWR BUS A', 'PWR BUS B', 'NAV SOLVER', 'COMMS MAST',
  'GRAV PLATES', 'SHIELD ARC', 'FIELD EMITTER', 'O2 SCRUBBER', 'HEAT SINK', 'RCS QUAD 2', 'CARGO LOCKS', 'BAY SEAL'];
const LOG = ['CONTRACT CLOSED', 'SALVAGE LOGGED', 'ROUTE PLOTTED', 'HULL PATCHED', 'CREDITS POSTED', 'DRONE RECOVERED',
  'BEACON TAGGED', 'CACHE OPENED', 'FIELD TEST OK', 'SUPPLY DROP'];

function hash(n) { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); }

class ShipScreens {
  constructor(layout, planetCols, destName) {
    this.kinds = {}; this.planetCols = planetCols; this.destName = destName;
    this.pos = {};
    for (const s of layout.screens || []) (this.pos[s.kind] = this.pos[s.kind] || []).push(V(s.pos));
    this.t = 0; this.acc = 0; this.hist = [[], [], []]; this.lines = [];
    for (let i = 0; i < 14; i++) this.lines.push(this.line(i));
  }

  get(kind) {
    if (this.kinds[kind]) return this.kinds[kind];
    const k = KINDS[kind] || KINDS.data;
    const c = document.createElement('canvas'); c.width = k[0]; c.height = k[1];
    const tex = new THREE.CanvasTexture(c);
    tex.flipY = false; tex.colorSpace = THREE.SRGBColorSpace; tex.generateMipmaps = false; tex.minFilter = THREE.LinearFilter;
    const mat = new THREE.MeshBasicMaterial({ map: tex, color: new THREE.Color(1.45, 1.45, 1.45), name: 'screen_' + kind });
    const s = { kind, c, ctx: c.getContext('2d'), tex, mat, fg: k[2], bg: k[3], dirty: true };
    this.kinds[kind] = s; this.draw(s);
    return s;
  }

  line(i) {
    const r = hash(i * 3.7 + this.t);
    return [WORDS[Math.floor(r * WORDS.length)], (hash(i + this.t * 1.3) * 100).toFixed(1), hash(i * 9.1 + this.t) > .88 ? 'WARN' : 'OK'];
  }

  update(dt, cam) {
    this.acc += dt; this.t += dt;
    if (this.acc < 1 / SCREEN_HZ) return;
    this.acc = 0;
    for (const kind in this.kinds) {
      const ps = this.pos[kind];
      if (ps && !ps.some(p => p.distanceToSquared(cam) < SCREEN_RANGE * SCREEN_RANGE)) continue;
      this.draw(this.kinds[kind]);
    }
  }

  frame(s, title) {
    const { ctx, c } = s, W = c.width, H = c.height;
    const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, s.bg); g.addColorStop(1, '#000000');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = .08; ctx.fillStyle = s.fg;
    for (let y = (this.t * 30) % 4; y < H; y += 4) ctx.fillRect(0, y, W, 1);   // scanlines
    ctx.globalAlpha = 1;
    if (title) {
      ctx.fillStyle = s.fg; ctx.globalAlpha = .9; ctx.fillRect(0, 0, W, 15); ctx.globalAlpha = 1;
      ctx.fillStyle = s.bg; ctx.font = 'bold 10px monospace'; ctx.textBaseline = 'middle';
      ctx.fillText(title, 5, 8);
      ctx.fillText(((this.t * 1000) | 0).toString(16).toUpperCase().padStart(6, '0'), W - 48, 8);
    }
    ctx.strokeStyle = s.fg; ctx.globalAlpha = .35; ctx.strokeRect(1.5, 1.5, W - 3, H - 3); ctx.globalAlpha = 1;
  }

  draw(s) {
    const { ctx, c } = s, W = c.width, H = c.height, t = this.t;
    ctx.save();
    if (s.kind === 'keys') {
      this.frame(s);
      const cols = 8, rows = 3, bw = W / cols, bh = H / rows;
      for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
        const h = hash(i * 7 + j * 13), on = hash(i + j * 5 + Math.floor(t * (1 + h * 3))) > .55;
        ctx.fillStyle = h > .85 ? '#ffb040' : h > .7 ? '#ff5050' : s.fg;
        ctx.globalAlpha = on ? .95 : .18;
        ctx.fillRect(i * bw + 3, j * bh + 3, bw - 6, bh - 6);
      }
    } else if (s.kind === 'data' || s.kind === 'amber') {
      this.frame(s, s.kind === 'amber' ? 'SERVICE LOG // WAYFARER' : 'SYS MONITOR // WAYFARER');
      const lh = 12, scroll = (t * 9) % lh;
      if (t - (this.lastShift || 0) > lh / 9) { this.lastShift = t; this.lines.shift(); this.lines.push(this.line(this.lines.length + Math.floor(t))); }
      ctx.font = '10px monospace'; ctx.textBaseline = 'top';
      this.lines.forEach((L, i) => {
        const y = 20 + i * lh - scroll; if (y < 17 || y > H - 12) return;
        ctx.fillStyle = L[2] === 'WARN' ? '#ff6a4a' : s.fg; ctx.globalAlpha = .85;
        if (s.kind === 'amber') ctx.fillText(('LOG ' + (2200 + i * 7 + Math.floor(t)) + ' ' + LOG[Math.floor(hash(i + Math.floor(t / 2)) * LOG.length)]).slice(0, 34), 6, y);
        else { ctx.fillText(L[0], 6, y); ctx.fillText(L[1].padStart(5, ' '), W - 82, y); ctx.fillText(L[2], W - 34, y); }
      });
      if (Math.floor(t * 2) % 2) { ctx.fillStyle = s.fg; ctx.fillRect(6, H - 12, 7, 9); }
      ctx.globalAlpha = .7; ctx.fillStyle = s.fg; ctx.fillRect(20, H - 9, (W - 30) * (.5 + .5 * Math.sin(t * .7)), 3);
    } else if (s.kind === 'graph') {
      this.frame(s, 'FLUX / THERM / GRAV');
      ctx.globalAlpha = .18; ctx.strokeStyle = s.fg;
      for (let x = 0; x < W; x += 16) { ctx.beginPath(); ctx.moveTo(x - (t * 20) % 16, 16); ctx.lineTo(x - (t * 20) % 16, H); ctx.stroke(); }
      for (let y = 24; y < H; y += 16) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
      const cols = [s.fg, '#ffcf5a', '#ff6ab0'];
      this.hist.forEach((h, k) => {
        h.push(Math.sin(t * (1.3 + k * .7) + k) * .5 + Math.sin(t * (4.1 + k)) * .2 + (hash(t * 10 + k) - .5) * .25);
        while (h.length > 64) h.shift();
        ctx.globalAlpha = .9; ctx.strokeStyle = cols[k]; ctx.lineWidth = 1.5; ctx.beginPath();
        h.forEach((v, i) => { const x = (W - 50) * i / 63, y = 26 + (k + .5) * (H - 34) / 3 - v * 18; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
        ctx.stroke();
      });
      for (let i = 0; i < 5; i++) {
        const v = .35 + .6 * Math.abs(Math.sin(t * (.8 + i * .37) + i));
        ctx.globalAlpha = .85; ctx.fillStyle = i === 4 && v > .85 ? '#ff6a4a' : s.fg;
        ctx.fillRect(W - 46 + i * 9, H - 6 - v * (H - 30), 6, v * (H - 30));
      }
    } else if (s.kind === 'radar') {
      this.frame(s);
      const cx = W / 2, cy = H / 2, R = W * .44, a = t * 1.7;
      ctx.strokeStyle = s.fg; ctx.globalAlpha = .35; ctx.lineWidth = 1;
      for (let k = 1; k <= 4; k++) { ctx.beginPath(); ctx.arc(cx, cy, R * k / 4, 0, Math.PI * 2); ctx.stroke(); }
      ctx.beginPath(); ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R); ctx.stroke();
      for (let k = 0; k < 24; k++) {   // fading sweep wedge
        ctx.globalAlpha = .5 * (1 - k / 24); ctx.fillStyle = s.fg;
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, R, a - (k + 1) * .03, a - k * .03); ctx.fill();
      }
      for (let i = 0; i < 9; i++) {
        const ba = hash(i) * Math.PI * 2 + t * .05 * (hash(i + 4) - .5), br = R * (.2 + .75 * hash(i + 9));
        const age = ((a - ba) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
        ctx.globalAlpha = Math.max(0, 1 - age / 4); ctx.fillStyle = i === 0 ? '#ffb040' : s.fg;
        ctx.beginPath(); ctx.arc(cx + Math.cos(ba) * br, cy + Math.sin(ba) * br, i === 0 ? 4 : 3, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = .9; ctx.fillStyle = s.fg; ctx.font = '11px monospace';
      ctx.fillText('CONTACTS ' + (5 + Math.floor(hash(Math.floor(t / 3)) * 4)), 8, H - 10);
      ctx.fillText('HDG ' + String(Math.floor((a * 57.3) % 360)).padStart(3, '0'), W - 64, H - 10);
    } else if (s.kind === 'nav') {
      this.frame(s, 'ORBIT // ' + this.destName.toUpperCase());
      const cx = W * .38, cy = H * .56, R = H * .3, [a, b, cc] = this.planetCols;
      const g = ctx.createRadialGradient(cx - R * .4, cy - R * .4, R * .1, cx, cy, R);
      g.addColorStop(0, cc); g.addColorStop(.55, b); g.addColorStop(1, a);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.beginPath(); ctx.arc(cx + R * .45, cy + R * .2, R * 1.02, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = s.fg; ctx.globalAlpha = .7; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.ellipse(cx, cy, R * 1.7, R * .7, -.25, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
      const oa = t * .35, sx = cx + Math.cos(oa) * R * 1.7 * Math.cos(-.25) - Math.sin(oa) * R * .7 * Math.sin(-.25);
      const sy = cy + Math.cos(oa) * R * 1.7 * Math.sin(-.25) + Math.sin(oa) * R * .7 * Math.cos(-.25);
      ctx.globalAlpha = 1; ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(sx, sy, 3.5, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = .4 + .4 * Math.sin(t * 6); ctx.strokeStyle = '#ffffff'; ctx.beginPath(); ctx.arc(sx, sy, 7, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = .9; ctx.fillStyle = s.fg; ctx.font = '10px monospace';
      const alt = 412 + Math.sin(oa) * 18;
      ['ALT ' + alt.toFixed(1) + ' KM', 'VEL ' + (7.66 + Math.cos(oa) * .05).toFixed(2) + ' KM/S', 'PERIOD 92 MIN', 'INC 21.4'].forEach((l, i) => ctx.fillText(l, W * .7, 32 + i * 14));
      if (Math.floor(t * 1.5) % 2) { ctx.fillStyle = '#ffcf5a'; ctx.fillText('JUMP READY', W * .7, 32 + 4 * 14 + 4); }
    } else if (s.kind === 'status') {
      this.frame(s, 'SHIP STATUS');
      // top-down ship diagram: nose up, compartments pulse, one section cycling a check
      const cx = W * .32, top = 22, Lh = H - 30, sc = Lh / 64;
      const shape = [[0, 0], [3.5, 8], [7, 12], [7.7, 26], [14, 34], [14, 63], [-14, 63], [-14, 34], [-7.7, 26], [-7, 12], [-3.5, 8]];
      ctx.strokeStyle = s.fg; ctx.globalAlpha = .9; ctx.lineWidth = 1.2; ctx.beginPath();
      shape.forEach(([x, y], i) => { const px = cx + x * sc, py = top + y * sc; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
      ctx.closePath(); ctx.stroke();
      const rooms = [[-5, 2, 10, 9], [-6, 14, 12, 12], [-12, 37, 24, 25]];
      const chk = Math.floor(t / 1.5) % 3;
      rooms.forEach(([x, y, w, h], i) => {
        ctx.globalAlpha = i === chk ? .35 + .3 * Math.sin(t * 8) : .18; ctx.fillStyle = s.fg;
        ctx.fillRect(cx + x * sc, top + y * sc, w * sc, h * sc);
      });
      for (const sx of [-1, 1]) { ctx.globalAlpha = .6; ctx.strokeRect(cx + (sx * 21 - 3) * sc, top + 28 * sc, 6 * sc, 26 * sc); }
      ctx.font = '10px monospace'; ctx.globalAlpha = .9;
      [['HULL', .98], ['SHIELD', .7 + .25 * Math.sin(t * .4)], ['REACTOR', .82 + .05 * Math.sin(t * 2.3)], ['FIELD', .9 + .08 * Math.sin(t * 5)]].forEach(([n, v], i) => {
        const y = 30 + i * 30; ctx.fillStyle = s.fg; ctx.fillText(n, W * .62, y);
        ctx.globalAlpha = .25; ctx.fillRect(W * .62, y + 6, W * .33, 6); ctx.globalAlpha = .9;
        ctx.fillStyle = v < .75 ? '#ffcf5a' : s.fg; ctx.fillRect(W * .62, y + 6, W * .33 * v, 6);
      });
    }
    ctx.restore();
    s.tex.needsUpdate = true;
  }

  dispose() { for (const k in this.kinds) { this.kinds[k].tex.dispose(); this.kinds[k].mat.dispose(); } }
}

// ------------------------------------------------------------------ force field across the open bay
function fieldMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { time: { value: 0 }, col: { value: new THREE.Color(.25, .65, 1.0) } },
    vertexShader: 'varying vec2 vUv;varying vec3 vN,vV;void main(){vUv=uv;vec4 mv=modelViewMatrix*vec4(position,1.);vN=normalize(normalMatrix*normal);vV=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}',
    fragmentShader: `uniform float time;uniform vec3 col;varying vec2 vUv;varying vec3 vN,vV;
      void main(){vec2 p=vUv*vec2(22.,10.);
        float l1=abs(fract(p.y*1.2)-.5),l2=abs(fract(p.y*.6+p.x*1.039)-.5),l3=abs(fract(p.y*.6-p.x*1.039)-.5);
        float grid=smoothstep(.07,.0,min(l1,min(l2,l3)));
        float rip=.5+.5*sin(length(p-vec2(11.,5.))*1.6-time*2.2);
        float scan=pow(1.-abs(fract(vUv.y*1.3-time*.12)-.5)*2.,14.);
        float e=min(min(vUv.x,1.-vUv.x),min(vUv.y,1.-vUv.y));
        float edge=smoothstep(.1,.0,e);
        float fres=pow(1.-abs(dot(normalize(vN),normalize(vV))),2.);
        float flick=.92+.08*sin(time*31.)*sin(time*17.);
        float a=(.03+grid*(.04+.07*rip)+scan*.14+edge*.3+fres*.12)*flick;
        gl_FragColor=vec4(col*a,1.);}`,
  });
}

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
    const pcols = ORBIT_COLORS[dest.id] || ORBIT_COLORS.earth;
    this.screens = new ShipScreens(layout, pcols, dest.name);
    this.field = fieldMaterial();
    const ship = A.clone('ship_interior');
    this.holoMats = new Set();
    ship.traverse(o => {
      if (!o.isMesh) return;
      const n = o.material.name;
      if (n === 'skylight_glass' || n === 'window_glass') {
        o.material = o.material.clone(); o.material.transparent = true; o.material.opacity = .08; o.material.roughness = .02;
        o.material.metalness = 0; o.material.envMapIntensity = 2.0; o.castShadow = false; o.receiveShadow = false; o.renderOrder = 5;
      } else if (n.startsWith('screen_')) {
        o.material = this.screens.get(n.slice(7)).mat; o.castShadow = false; o.receiveShadow = false;
      } else if (n === 'force_field') {
        o.material = this.field; o.castShadow = false; o.receiveShadow = false; o.renderOrder = 6;
      } else if (n.startsWith('stencil')) {
        const m = o.material; m.transparent = true; m.depthWrite = false; m.polygonOffset = true; m.polygonOffsetFactor = -2; m.polygonOffsetUnits = -2;
        o.castShadow = false; o.renderOrder = 2;
      }
      const m = o.material, mn = m.name;
      if (/floor/.test(mn)) { o.castShadow = false; m.envMapIntensity = .8; }
      if (/wall|ceil/.test(mn)) m.envMapIntensity = .5;
      if (/hull_ext/.test(mn)) m.envMapIntensity = .9;
      if (/light_|neon|engine_glow/.test(mn)) { o.castShadow = false; o.receiveShadow = false; }
      if (mn === 'holo') { m.transparent = true; m.opacity = .35; m.depthWrite = false; m.blending = THREE.AdditiveBlending; m.emissiveIntensity = .5; this.holoMats.add(m); o.castShadow = false; }
    });
    sc.add(ship);
    this.ship = ship;
    for (const c of layout.colliders) this.collision.add(c);
    this.collision.floorY = 0;
    progress(.35, 'Bringing reactor online');
    // ---------------- lighting
    sc.add(new THREE.HemisphereLight(0xaec4e6, 0x2a251c, .75));
    for (const L of layout.lights) {
      if (L.kind === 'sun') {
        // sunlight through the canopy and the starboard portholes; the frustum spans the whole hull so the closed
        // hangar stays in shadow (outside a shadow frustum three would light it fully)
        const s = new THREE.DirectionalLight(L.color, L.intensity * 2.2);
        s.position.copy(V(L.pos)); s.target.position.copy(V(L.target));
        s.castShadow = true;
        const q = g.renderer.q;
        s.shadow.mapSize.set(q.shadow, q.shadow);
        Object.assign(s.shadow.camera, { left: -31, right: 31, top: 31, bottom: -31, near: 20, far: 105 });
        s.shadow.bias = -.0005; s.shadow.normalBias = .04;
        sc.add(s, s.target);
        this.sun = s;
        // the hull is static: refresh the big sun shadow map every other frame (moving casters are small)
        s.shadow.autoUpdate = false; s.shadow.needsUpdate = true;
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
    if (!this.sunDir) this.sunDir = new THREE.Vector3(.45, .55, .7).normalize();
    // soft beams where the sun falls through the hull portholes
    this.addBeams();
    // ---------------- sky, the planet below/behind (framed by the open bay) and a moon ahead of the canopy
    const sky = spaceSky({ sunDir: this.sunDir });
    sc.add(sky); this.sky = sky;
    const planet = orbitPlanet(ORBIT_COLORS[dest.id] || ORBIT_COLORS.earth, this.sunDir, 520);
    planet.position.set(-297, -322, -729);
    sc.add(planet); this.planet = planet;
    const moon = orbitPlanet(['#8d8b88', '#5d5b5a', '#b9b6b0'], this.sunDir, 90);
    moon.position.set(-351, 56, 603);
    sc.add(moon); this.moon = moon;
    progress(.55, 'Calibrating armory');
    // ---------------- stations: interactable from all around the station object
    const st = layout.stations;
    const add = (id, action, extra = {}) => {
      const s = st[id];
      this.interactables.push({ id, pos: V(s.at || s.pos), r: (s.rad || .2) + 1.6, label: s.label, verb: s.verb, key: 'E', action, ...extra });
    };
    add('captain', () => g.station('captain'));
    add('briefing', () => g.station('briefing'));
    add('wardrobe', () => g.station('wardrobe'));
    add('engineering', () => g.station('engineering'));
    add('record', () => g.station('record'));
    add('armory', () => g.station('armory'));
    add('gunsmith', () => g.station('gunsmith'));
    add('garage', () => g.station('garage'));
    this.stations = st;
    this.seats = layout.seats || [];
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
    // environment reflections captured in the hangar (car paint, chrome, glass)
    const pm = new THREE.PMREMGenerator(g.renderer.r);
    this.envRT = pm.fromScene(sc, 0.02, .1, 200, { position: new THREE.Vector3(1, 3, -22) });
    sc.environment = this.envRT.texture;
    sc.environmentIntensity = .7;
    pm.dispose();
    this.disposables.push(this.envRT, this.screens, this.field);
    sc.fog = new THREE.Fog(0x05070c, 60, 400);
    // compile every material variant now (behind the loading screen) instead of stalling when a deck first comes into view
    try { g.renderer.r.compile(sc, g.camera); } catch (e) { /* optional warm-up */ }
    progress(1, 'Ready');
  }

  addBeams() {
    const d = this.sunDir, dirIn = d.clone().negate(), L = 6.5;
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      uniforms: { c: { value: new THREE.Color(1.0, .9, .75) } },
      vertexShader: 'varying float vT;varying vec3 vN,vV;void main(){vT=uv.y;vec4 mv=modelViewMatrix*vec4(position,1.);vN=normalize(normalMatrix*normal);vV=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}',
      fragmentShader: 'uniform vec3 c;varying float vT;varying vec3 vN,vV;void main(){float f=pow(vT,1.6);float edge=pow(abs(dot(normalize(vN),normalize(vV))),1.5);gl_FragColor=vec4(c*.06*f*edge,1.);}',
    });
    this.disposables.push(mat);
    for (const ph of this.layout.portholes || []) {
      const n = V(ph.normal);
      if (n.dot(d) < .12) continue;
      const geo = new THREE.CylinderGeometry(ph.r * .95, ph.r * 1.25, L, 16, 1, true);
      const m = new THREE.Mesh(geo, mat);
      m.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dirIn);
      m.position.copy(V(ph.pos)).addScaledVector(dirIn, L / 2);
      m.renderOrder = 6; m.castShadow = false; m.receiveShadow = false;
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
    const o = [{ text: 'Plot a jump', sub: 'Captain’s chair · bridge (forward)' }];
    const ready = g.save.contracts.filter(c => c.done).length;
    if (ready) o.push({ text: ready + ' contract reward' + (ready > 1 ? 's' : '') + ' ready', sub: 'Briefing table · commons' });
    return o;
  }

  spawn() {
    const s = this.layout.stations._spawn;
    const p = V(s.pos), look = V(s.look);
    return { pos: p, yaw: Math.atan2(look.x - p.x, look.z - p.z) };
  }

  update(dt) {
    const g = this.g, t = g.time;
    if (this.sun) { this.shadowTick = (this.shadowTick || 0) + 1; if (this.shadowTick % 2 === 0) this.sun.shadow.needsUpdate = true; }
    if (this.sky) this.sky.position.copy(g.camera.position);
    if (this.planet) { this.planet.rotation.y += dt * .004; this.planet.material.uniforms.time.value = t; }
    if (this.moon) { this.moon.rotation.y += dt * .002; this.moon.material.uniforms.time.value = t; }
    if (this.field) this.field.uniforms.time.value = t;
    if (this.screens) this.screens.update(dt, g.camera.position);
    // holo projections flicker a little
    for (const m of this.holoMats || []) m.opacity = .3 + .06 * Math.sin(t * 7.3) + (Math.random() < .03 ? -.15 : 0);
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
