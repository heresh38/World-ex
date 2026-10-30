// Particle and flash effects. Colours are HDR (>1) and tone-mapping is disabled so they drive the bloom pass.
import * as THREE from 'three';

const MAX = 2400;

export class FX {
  constructor(scene) {
    this.scene = scene;
    // ---- spark particles (one draw call)
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(MAX * 3); this.col = new Float32Array(MAX * 3); this.size = new Float32Array(MAX);
    this.vel = new Float32Array(MAX * 3); this.life = new Float32Array(MAX); this.max = new Float32Array(MAX); this.grav = new Float32Array(MAX);
    this.base = new Float32Array(MAX * 3); this.drag = new Float32Array(MAX);
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('color', new THREE.BufferAttribute(this.col, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('size', new THREE.BufferAttribute(this.size, 1).setUsage(THREE.DynamicDrawUsage));
    const m = new THREE.ShaderMaterial({
      uniforms: { scale: { value: innerHeight / 2 } },
      vertexShader: `attribute float size;attribute vec3 color;varying vec3 vC;uniform float scale;
        void main(){vC=color;vec4 mv=modelViewMatrix*vec4(position,1.);gl_PointSize=size*scale/max(.1,-mv.z);gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `varying vec3 vC;void main(){vec2 p=gl_PointCoord-.5;float d=dot(p,p)*4.;if(d>1.)discard;gl_FragColor=vec4(vC*(1.-d),1.);}`,
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false,
    });
    this.points = new THREE.Points(g, m); this.points.frustumCulled = false; this.points.renderOrder = 10;
    scene.add(this.points);
    this.n = 0; this.cursor = 0;
    // ---- tracers
    this.tracers = [];
    const tg = new THREE.CylinderGeometry(1, 1, 1, 5, 1, true); tg.rotateX(Math.PI / 2); tg.translate(0, 0, .5);
    this.tracerGeo = tg;
    // ---- flash light pool
    this.lights = [];
    for (let i = 0; i < 3; i++) {
      const l = new THREE.PointLight(0xffc070, 0, 14, 2); l.castShadow = false; scene.add(l); this.lights.push({ l, t: 0, max: 0, peak: 0 });
    }
    // ---- glow sprites (muzzle flash, explosion core)
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const x = c.getContext('2d'); const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(.25, 'rgba(255,220,160,.8)'); gr.addColorStop(1, 'rgba(255,120,40,0)');
    x.fillStyle = gr; x.fillRect(0, 0, 64, 64);
    this.glowTex = new THREE.CanvasTexture(c);
    this.sprites = [];
    this.beams = [];
    this.rings = [];
  }

  dispose() {
    this.points.removeFromParent(); this.lights.forEach(o => o.l.removeFromParent());
    this.tracers.forEach(t => t.m.removeFromParent()); this.sprites.forEach(s => s.s.removeFromParent());
    this.rings.forEach(r => r.m.removeFromParent());
  }

  emit(p, count, speed, color, life = .5, gravity = 9, size = .06, spread = 1, dir = null, drag = .5) {
    const c = new THREE.Color(color);
    for (let k = 0; k < count; k++) {
      const i = this.cursor; this.cursor = (this.cursor + 1) % MAX;
      this.pos[i * 3] = p.x; this.pos[i * 3 + 1] = p.y; this.pos[i * 3 + 2] = p.z;
      let vx = (Math.random() - .5) * 2, vy = (Math.random() - .2) * 2, vz = (Math.random() - .5) * 2;
      if (dir) { vx = dir.x + vx * spread; vy = dir.y + vy * spread; vz = dir.z + vz * spread; }
      const s = speed * (.4 + Math.random() * .8);
      this.vel[i * 3] = vx * s; this.vel[i * 3 + 1] = vy * s; this.vel[i * 3 + 2] = vz * s;
      this.life[i] = this.max[i] = life * (.5 + Math.random() * .8);
      this.grav[i] = gravity; this.drag[i] = drag;
      const h = 1 + Math.random() * 2;
      this.base[i * 3] = c.r * h; this.base[i * 3 + 1] = c.g * h; this.base[i * 3 + 2] = c.b * h;
      this.size[i] = size * (.6 + Math.random() * .8);
    }
  }

  flash(p, color = 0xffc070, intensity = 40, dur = .06, dist = 14) {
    const L = this.lights.reduce((a, b) => (a.t < b.t ? a : b));
    L.l.position.copy(p); L.l.color.set(color); L.l.distance = dist; L.t = dur; L.max = dur; L.peak = intensity;
  }

  glow(p, size, color, dur) {
    let s = this.sprites.find(x => x.t <= 0);
    if (!s) {
      const m = new THREE.SpriteMaterial({ map: this.glowTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false });
      s = { s: new THREE.Sprite(m), t: 0 }; this.scene.add(s.s); this.sprites.push(s);
    }
    s.s.visible = true; s.s.position.copy(p); s.s.material.color.set(color).multiplyScalar(3); s.size = size; s.t = s.max = dur;
    s.s.scale.setScalar(size);
  }

  tracer(a, b, color = 0xffd9a0, width = .018, dur = .07) {
    let t = this.tracers.find(x => x.t <= 0);
    if (!t) {
      const m = new THREE.MeshBasicMaterial({ color: 0xffffff, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false, toneMapped: false });
      t = { m: new THREE.Mesh(this.tracerGeo, m), t: 0 }; t.m.frustumCulled = false; this.scene.add(t.m); this.tracers.push(t);
    }
    const len = a.distanceTo(b);
    t.m.position.copy(a); t.m.lookAt(b); t.m.scale.set(width, width, len);
    t.m.material.color.set(color).multiplyScalar(4); t.m.material.opacity = 1; t.m.visible = true; t.t = t.max = dur;
  }

  muzzle(p, dir, color = 0xffc070) {
    this.glow(p, .55, color, .05);
    this.flash(p, color, 30, .05, 10);
    this.emit(p, 4, 6, color, .12, 0, .05, .25, dir);
  }

  impact(p, normal, kind = 'metal') {
    if (kind === 'enemy') { this.emit(p, 10, 4, 0xff6a3a, .3, 6, .05, .8, normal); return; }
    if (kind === 'crit') { this.emit(p, 16, 5, 0xffd04a, .35, 6, .06, .8, normal); this.glow(p, .5, 0xffd04a, .08); return; }
    if (kind === 'dirt') { this.emit(p, 8, 3, 0x8a7a66, .5, 9, .08, .9, normal); return; }
    this.emit(p, 8, 5, 0xffb060, .35, 12, .04, .7, normal);
  }

  explosion(p, r = 5) {
    this.emit(p, 90, 14, 0xff8a30, .9, 6, .18, 1);
    this.emit(p, 40, 6, 0xffe0a0, .5, 2, .3, 1);
    this.glow(p, r * 1.6, 0xff9a40, .35);
    this.flash(p, 0xff8a40, 900, .4, r * 6);
    let rg = this.rings.find(x => x.t <= 0);
    if (!rg) {
      const m = new THREE.MeshBasicMaterial({ color: 0xffa050, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
      rg = { m: new THREE.Mesh(new THREE.SphereGeometry(1, 20, 12), m), t: 0 }; this.scene.add(rg.m); this.rings.push(rg);
    }
    rg.m.position.copy(p); rg.r = r; rg.t = rg.max = .35; rg.m.visible = true;
  }

  // welding: bright bursts of sparks that fall and bounce, plus a flickering arc light
  weld(p, dir) {
    this.emit(p, 6 + (Math.random() * 6 | 0), 5.5, 0xfff0c0, .7, 9.8, .035, .9, dir, .2);
    if (Math.random() < .5) this.glow(p, .35 + Math.random() * .25, 0xbfe6ff, .05);
  }

  update(dt, floorY = null) {
    let any = 0;
    for (let i = 0; i < MAX; i++) {
      if (this.life[i] <= 0) { if (this.size[i]) { this.size[i] = 0; } continue; }
      any++;
      this.life[i] -= dt;
      const f = Math.max(0, this.life[i] / this.max[i]);
      const d = 1 - this.drag[i] * dt;
      this.vel[i * 3] *= d; this.vel[i * 3 + 2] *= d; this.vel[i * 3 + 1] -= this.grav[i] * dt;
      this.pos[i * 3] += this.vel[i * 3] * dt; this.pos[i * 3 + 1] += this.vel[i * 3 + 1] * dt; this.pos[i * 3 + 2] += this.vel[i * 3 + 2] * dt;
      if (floorY !== null) {
        const fy = typeof floorY === 'function' ? floorY(this.pos[i * 3], this.pos[i * 3 + 2]) : floorY;
        if (this.pos[i * 3 + 1] < fy && this.vel[i * 3 + 1] < 0) { this.pos[i * 3 + 1] = fy; this.vel[i * 3 + 1] *= -.35; this.vel[i * 3] *= .6; this.vel[i * 3 + 2] *= .6; }
      }
      const e = f * f;
      this.col[i * 3] = this.base[i * 3] * e; this.col[i * 3 + 1] = this.base[i * 3 + 1] * e * f; this.col[i * 3 + 2] = this.base[i * 3 + 2] * e * f;
      if (this.life[i] <= 0) this.size[i] = 0;
    }
    const g = this.points.geometry;
    g.attributes.position.needsUpdate = true; g.attributes.color.needsUpdate = true; g.attributes.size.needsUpdate = true;
    this.points.visible = any > 0;
    this.points.material.uniforms.scale.value = innerHeight / 2;
    for (const L of this.lights) {
      if (L.t > 0) { L.t -= dt; L.l.intensity = L.peak * Math.max(0, L.t / L.max); } else L.l.intensity = 0;
    }
    for (const t of this.tracers) if (t.t > 0) { t.t -= dt; t.m.material.opacity = Math.max(0, t.t / t.max); if (t.t <= 0) t.m.visible = false; }
    for (const s of this.sprites) if (s.t > 0) { s.t -= dt; s.s.material.opacity = Math.max(0, s.t / s.max); if (s.t <= 0) s.s.visible = false; }
    for (const r of this.rings) if (r.t > 0) {
      r.t -= dt; const k = 1 - r.t / r.max; r.m.scale.setScalar(r.r * (.2 + k)); r.m.material.opacity = (1 - k) * .7; if (r.t <= 0) r.m.visible = false;
    }
  }
}
