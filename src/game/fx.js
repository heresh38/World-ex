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
    this.initBlood(scene);
  }

  // ---------------------------------------------------------------- blood: droplets, splatter and pools
  initBlood(scene) {
    const BM = this.BM = 900;
    const g = new THREE.BufferGeometry();
    this.bPos = new Float32Array(BM * 3); this.bVel = new Float32Array(BM * 3); this.bLife = new Float32Array(BM); this.bCol = new Float32Array(BM * 3); this.bSize = new Float32Array(BM);
    g.setAttribute('position', new THREE.BufferAttribute(this.bPos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('color', new THREE.BufferAttribute(this.bCol, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('size', new THREE.BufferAttribute(this.bSize, 1).setUsage(THREE.DynamicDrawUsage));
    const m = new THREE.ShaderMaterial({
      uniforms: { scale: { value: innerHeight / 2 } },
      vertexShader: `attribute float size;attribute vec3 color;varying vec3 vC;uniform float scale;
        void main(){vC=color;vec4 mv=modelViewMatrix*vec4(position,1.);gl_PointSize=size*scale/max(.1,-mv.z);gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `varying vec3 vC;void main(){vec2 p=gl_PointCoord-.5;float d=dot(p,p)*4.;if(d>1.)discard;gl_FragColor=vec4(vC*(1.1-d*.4),1.);}`,
      transparent: false, depthWrite: true,
    });
    this.bPoints = new THREE.Points(g, m); this.bPoints.frustumCulled = false; scene.add(this.bPoints);
    this.bCursor = 0;
    // splat texture: an irregular stain with drips
    const c = document.createElement('canvas'); c.width = c.height = 128; const x = c.getContext('2d');
    x.fillStyle = '#fff';
    for (let k = 0; k < 14; k++) { const a = Math.random() * 6.28, r = Math.random() * 30; x.beginPath(); x.arc(64 + Math.cos(a) * r, 64 + Math.sin(a) * r, 10 + Math.random() * 18, 0, 7); x.fill(); }
    for (let k = 0; k < 18; k++) { const a = Math.random() * 6.28, r = 40 + Math.random() * 20; x.beginPath(); x.arc(64 + Math.cos(a) * r, 64 + Math.sin(a) * r, 1.5 + Math.random() * 4, 0, 7); x.fill(); }
    const tex = new THREE.CanvasTexture(c);
    const DM = this.DM = 260;
    const geo = new THREE.PlaneGeometry(1, 1); geo.rotateX(-Math.PI / 2);
    this.decals = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ map: tex, transparent: true, alphaTest: .3, roughness: .25, metalness: .1,
      depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4 }), DM);
    this.decals.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(DM * 3), 3);
    const zero = new THREE.Matrix4().makeScale(0, 0, 0);
    for (let i = 0; i < DM; i++) this.decals.setMatrixAt(i, zero);
    this.decals.frustumCulled = false; this.decals.receiveShadow = true; scene.add(this.decals);
    this.dCursor = 0; this.growing = [];
  }

  blood(p, dir = null, amount = 1, color = 0x6e0a0a) {
    if (!this.bPoints) return;
    const c = new THREE.Color(color), n = Math.round(14 * amount);
    for (let k = 0; k < n; k++) {
      const i = this.bCursor; this.bCursor = (this.bCursor + 1) % this.BM;
      this.bPos[i * 3] = p.x; this.bPos[i * 3 + 1] = p.y; this.bPos[i * 3 + 2] = p.z;
      const sp = 1.5 + Math.random() * 3.5 * amount;
      let vx = (Math.random() - .5) * 2, vy = Math.random() * 1.2, vz = (Math.random() - .5) * 2;
      if (dir) { vx = vx * .6 + dir.x * 1.6; vy = vy * .6 + dir.y + .4; vz = vz * .6 + dir.z * 1.6; }
      this.bVel[i * 3] = vx * sp; this.bVel[i * 3 + 1] = vy * sp; this.bVel[i * 3 + 2] = vz * sp;
      this.bLife[i] = .6 + Math.random() * .8; this.bSize[i] = .025 + Math.random() * .05;
      const v = .55 + Math.random() * .5; this.bCol[i * 3] = c.r * v; this.bCol[i * 3 + 1] = c.g * v; this.bCol[i * 3 + 2] = c.b * v;
    }
    // splatter on the ground in the direction of the spray
    if (this.groundFn && Math.random() < .55 * amount) {
      const d = dir || new THREE.Vector3();
      const x = p.x + d.x * (.6 + Math.random() * 1.4) + (Math.random() - .5), z = p.z + d.z * (.6 + Math.random() * 1.4) + (Math.random() - .5);
      this.decal(x, this.groundFn(x, z), z, .5 + Math.random() * .7 * amount, color);
    }
  }

  bloodPool(p, size = 1, color = 0x5a0808) {
    const y = this.groundFn ? this.groundFn(p.x, p.z) : p.y;
    const i = this.decal(p.x, y, p.z, .1, color);
    this.growing.push({ i, x: p.x, y, z: p.z, t: 0, size: 1.4 * size + Math.random() * .6, rot: Math.random() * 6 });
  }

  decal(x, y, z, s, color) {
    const i = this.dCursor; this.dCursor = (this.dCursor + 1) % this.DM;
    const m = new THREE.Matrix4().compose(new THREE.Vector3(x, y + .03, z), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.random() * 6), new THREE.Vector3(s, 1, s));
    this.decals.setMatrixAt(i, m); this.decals.instanceMatrix.needsUpdate = true;
    const c = new THREE.Color(color).multiplyScalar(.75 + Math.random() * .3);
    this.decals.setColorAt(i, c); this.decals.instanceColor.needsUpdate = true;
    return i;
  }

  updateBlood(dt) {
    if (!this.bPoints) return;
    let any = false;
    for (let i = 0; i < this.BM; i++) {
      if (this.bLife[i] <= 0) continue;
      any = true; this.bLife[i] -= dt;
      this.bVel[i * 3 + 1] -= 9.8 * dt;
      this.bPos[i * 3] += this.bVel[i * 3] * dt; this.bPos[i * 3 + 1] += this.bVel[i * 3 + 1] * dt; this.bPos[i * 3 + 2] += this.bVel[i * 3 + 2] * dt;
      if (this.groundFn) { const gy = this.groundFn(this.bPos[i * 3], this.bPos[i * 3 + 2]); if (this.bPos[i * 3 + 1] < gy + .02) { this.bLife[i] = 0; } }
      if (this.bLife[i] <= 0) this.bSize[i] = 0;
    }
    const g = this.bPoints.geometry;
    g.attributes.position.needsUpdate = true; g.attributes.size.needsUpdate = true; g.attributes.color.needsUpdate = true;
    this.bPoints.visible = any; this.bPoints.material.uniforms.scale.value = innerHeight / 2;
    for (let k = this.growing.length - 1; k >= 0; k--) {
      const G = this.growing[k]; G.t += dt;
      const s = G.size * Math.min(1, .15 + G.t / 4);
      this.decals.setMatrixAt(G.i, new THREE.Matrix4().compose(new THREE.Vector3(G.x, G.y + .025, G.z), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), G.rot), new THREE.Vector3(s, 1, s)));
      this.decals.instanceMatrix.needsUpdate = true;
      if (G.t > 4) this.growing.splice(k, 1);
    }
  }

  dispose() {
    if (this.bPoints) { this.bPoints.removeFromParent(); this.decals.removeFromParent(); }
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

  // ---------------------------------------------------------------- slime (horror weapons): gooey droplets, wet stains, acid fizz
  // Droplets reuse the blood point pool; stains are their own instanced decals, oriented to the surface and faintly glowing.
  initSlime() {
    const SM = this.SM = 160;
    const geo = new THREE.PlaneGeometry(1, 1); geo.rotateX(-Math.PI / 2);
    const tex = this.decals ? this.decals.material.map : null;
    this.slimeDecals = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ map: tex, transparent: true, alphaTest: .3, roughness: .12, metalness: 0,
      emissive: 0x2a6a10, emissiveMap: tex, emissiveIntensity: .6, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -5 }), SM);
    this.slimeDecals.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(SM * 3), 3);
    const zero = new THREE.Matrix4().makeScale(0, 0, 0);
    for (let i = 0; i < SM; i++) this.slimeDecals.setMatrixAt(i, zero);
    this.slimeDecals.frustumCulled = false; this.slimeDecals.receiveShadow = true; this.scene.add(this.slimeDecals);
    this.sCursor = 0; this.slimeLife = new Float32Array(SM); this.slimeInfo = [];
  }

  slimeDrops(p, dir = null, n = 8, speed = 2.5, color = 0x7cff3a, size = 1) {
    if (!this.bPoints) return;
    const c = new THREE.Color(color);
    for (let k = 0; k < n; k++) {
      const i = this.bCursor; this.bCursor = (this.bCursor + 1) % this.BM;
      this.bPos[i * 3] = p.x; this.bPos[i * 3 + 1] = p.y; this.bPos[i * 3 + 2] = p.z;
      let vx = (Math.random() - .5) * 2, vy = Math.random() * 1.2, vz = (Math.random() - .5) * 2;
      if (dir) { vx = vx * .7 + dir.x * 1.4; vy = vy * .7 + dir.y * 1.4 + .3; vz = vz * .7 + dir.z * 1.4; }
      const sp = speed * (.4 + Math.random() * .9);
      this.bVel[i * 3] = vx * sp; this.bVel[i * 3 + 1] = vy * sp; this.bVel[i * 3 + 2] = vz * sp;
      this.bLife[i] = .5 + Math.random() * .8; this.bSize[i] = (.02 + Math.random() * .045) * size;
      const v = .7 + Math.random() * .5; this.bCol[i * 3] = c.r * v; this.bCol[i * 3 + 1] = c.g * v; this.bCol[i * 3 + 2] = c.b * v;
    }
  }

  // a wet stain on any surface (normal = surface normal); fades away after ~25 s
  slimeDecal(p, normal, s, color = 0x7cff3a) {
    if (!this.slimeDecals) this.initSlime();
    const i = this.sCursor; this.sCursor = (this.sCursor + 1) % this.SM;
    const n = normal ? normal.clone().normalize() : new THREE.Vector3(0, 1, 0);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), n)
      .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.random() * 6.28));
    const pos = p.clone().addScaledVector(n, .02 + Math.random() * .01);
    this.slimeInfo[i] = { pos, q, s };
    this.slimeDecals.setMatrixAt(i, new THREE.Matrix4().compose(pos, q, new THREE.Vector3(s, 1, s)));
    this.slimeDecals.setColorAt(i, new THREE.Color(color).multiplyScalar(.8 + Math.random() * .3));
    this.slimeDecals.instanceMatrix.needsUpdate = true; this.slimeDecals.instanceColor.needsUpdate = true;
    this.slimeLife[i] = 25;
  }

  // a glob bursting: droplets, an acid glow and a stain on the surface it hit
  slime(p, normal = null, size = 1, color = 0x7cff3a) {
    this.slimeDrops(p, normal, Math.round(10 * size), 3 * Math.sqrt(size), color, size);
    this.emit(p, Math.round(6 * size), 2.2, color, .45, 3, .07 * size, 1, normal, .8);
    this.glow(p, .6 * size, color, .12);
    if (normal) this.slimeDecal(p, normal, (.45 + Math.random() * .4) * size, color);
  }

  // acid eating at something: rising fizz
  fizz(p, color = 0x9cff4a) { this.emit(p, 3, .8, color, .5, -1.5, .05, .8, null, 1); }

  updateSlime(dt) {
    if (!this.slimeDecals) return;
    let dirty = false;
    for (let i = 0; i < this.SM; i++) {
      if (this.slimeLife[i] <= 0) continue;
      this.slimeLife[i] -= dt;
      const L = this.slimeLife[i];
      if (L < 4) {
        const I = this.slimeInfo[i], k = Math.max(0, L / 4) * I.s;
        this.slimeDecals.setMatrixAt(i, new THREE.Matrix4().compose(I.pos, I.q, new THREE.Vector3(k, 1, k))); dirty = true;
      }
    }
    if (dirty) this.slimeDecals.instanceMatrix.needsUpdate = true;
  }

  // welding: bright bursts of sparks that fall and bounce, plus a flickering arc light
  weld(p, dir) {
    this.emit(p, 6 + (Math.random() * 6 | 0), 5.5, 0xfff0c0, .7, 9.8, .035, .9, dir, .2);
    if (Math.random() < .5) this.glow(p, .35 + Math.random() * .25, 0xbfe6ff, .05);
  }

  update(dt, floorY = null) {
    if (typeof floorY === 'function') this.groundFn = floorY;
    this.updateBlood(dt);
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
