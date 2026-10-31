// Soft (alpha-blended, not additive) particles: water droplets, mist, landing dust, engine wash.
// One draw call per pool. Each particle: position, velocity, life, size growth, alpha, colour, gravity, drag.
import * as THREE from 'three';

export class Puffs {
  constructor(scene, max = 1600, { soft = .55 } = {}) {
    this.max = max; this.cursor = 0;
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(max * 3); this.col = new Float32Array(max * 3); this.size = new Float32Array(max); this.alpha = new Float32Array(max);
    this.vel = new Float32Array(max * 3); this.life = new Float32Array(max); this.maxL = new Float32Array(max);
    this.grav = new Float32Array(max); this.drag = new Float32Array(max); this.s0 = new Float32Array(max); this.s1 = new Float32Array(max); this.a0 = new Float32Array(max);
    this.floor = new Float32Array(max).fill(-1e9);
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('color', new THREE.BufferAttribute(this.col, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('size', new THREE.BufferAttribute(this.size, 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('alpha', new THREE.BufferAttribute(this.alpha, 1).setUsage(THREE.DynamicDrawUsage));
    this.mat = new THREE.ShaderMaterial({
      uniforms: { scale: { value: innerHeight / 2 }, soft: { value: soft }, fogColor: { value: new THREE.Color() }, fogNear: { value: 1e5 }, fogFar: { value: 2e5 } },
      vertexShader: `attribute float size;attribute float alpha;attribute vec3 color;varying vec3 vC;varying float vA;varying float vD;uniform float scale;
        void main(){vC=color;vA=alpha;vec4 mv=modelViewMatrix*vec4(position,1.);vD=-mv.z;gl_PointSize=min(512.,size*scale/max(.1,-mv.z));gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `varying vec3 vC;varying float vA;varying float vD;uniform float soft;uniform vec3 fogColor;uniform float fogNear,fogFar;
        void main(){vec2 p=gl_PointCoord-.5;float d=dot(p,p)*4.;if(d>1.)discard;float a=vA*pow(1.-d,soft*2.);
        float f=smoothstep(fogNear,fogFar,vD);gl_FragColor=vec4(mix(vC,fogColor,f),a);}`,
      transparent: true, depthWrite: false,
    });
    this.points = new THREE.Points(g, this.mat); this.points.frustumCulled = false; this.points.renderOrder = 9;
    scene.add(this.points); this.scene = scene; this.live = 0;
  }

  // p: position, n: count, o: {speed, dir, spread, life, size:[s0,s1], alpha, color, gravity, drag, floor, jitter}
  emit(p, n, o = {}) {
    const c = new THREE.Color(o.color === undefined ? 0xffffff : o.color);
    const sp = o.speed || 1, spread = o.spread === undefined ? 1 : o.spread, dir = o.dir || null, life = o.life || 1;
    const sz = o.size || [.1, .2], jit = o.jitter || 0;
    for (let k = 0; k < n; k++) {
      const i = this.cursor; this.cursor = (this.cursor + 1) % this.max;
      this.pos[i * 3] = p.x + (Math.random() - .5) * jit; this.pos[i * 3 + 1] = p.y + (o.jitterY || 0) * Math.random(); this.pos[i * 3 + 2] = p.z + (Math.random() - .5) * jit;
      let vx = (Math.random() - .5) * 2, vy = (Math.random() - .5) * 2, vz = (Math.random() - .5) * 2;
      if (o.ring) { const a = Math.random() * Math.PI * 2; vx = Math.cos(a); vz = Math.sin(a); vy = o.ring * (.5 + Math.random() * .5); }
      if (dir) { vx = dir.x + vx * spread; vy = dir.y + vy * spread; vz = dir.z + vz * spread; }
      const s = sp * (.45 + Math.random() * .75);
      this.vel[i * 3] = vx * s; this.vel[i * 3 + 1] = vy * s; this.vel[i * 3 + 2] = vz * s;
      this.life[i] = this.maxL[i] = life * (.6 + Math.random() * .7);
      this.grav[i] = o.gravity === undefined ? 9.8 : o.gravity; this.drag[i] = o.drag === undefined ? .3 : o.drag;
      const r = .7 + Math.random() * .6; this.s0[i] = sz[0] * r; this.s1[i] = sz[1] * r;
      this.a0[i] = (o.alpha === undefined ? .8 : o.alpha) * (.7 + Math.random() * .3);
      const v = o.vary === undefined ? .1 : o.vary, m = 1 - v + Math.random() * v * 2;
      this.col[i * 3] = c.r * m; this.col[i * 3 + 1] = c.g * m; this.col[i * 3 + 2] = c.b * m;
      this.floor[i] = o.floor === undefined ? -1e9 : o.floor;
    }
  }

  update(dt, fog) {
    let any = 0;
    for (let i = 0; i < this.max; i++) {
      if (this.life[i] <= 0) { if (this.alpha[i]) { this.alpha[i] = 0; this.size[i] = 0; } continue; }
      any++;
      this.life[i] -= dt;
      const t = 1 - Math.max(0, this.life[i] / this.maxL[i]);
      const d = Math.max(0, 1 - this.drag[i] * dt);
      this.vel[i * 3] *= d; this.vel[i * 3 + 2] *= d; this.vel[i * 3 + 1] = this.vel[i * 3 + 1] * d - this.grav[i] * dt;
      this.pos[i * 3] += this.vel[i * 3] * dt; this.pos[i * 3 + 1] += this.vel[i * 3 + 1] * dt; this.pos[i * 3 + 2] += this.vel[i * 3 + 2] * dt;
      if (this.pos[i * 3 + 1] < this.floor[i]) { this.life[i] = 0; this.onLand && this.onLand(this.pos[i * 3], this.pos[i * 3 + 2], this.s0[i]); }
      this.size[i] = this.s0[i] + (this.s1[i] - this.s0[i]) * Math.sqrt(t);
      this.alpha[i] = this.life[i] <= 0 ? 0 : this.a0[i] * Math.min(1, t * 8) * (1 - t * t);
    }
    const g = this.points.geometry;
    g.attributes.position.needsUpdate = true; g.attributes.size.needsUpdate = true; g.attributes.alpha.needsUpdate = true; g.attributes.color.needsUpdate = true;
    this.points.visible = any > 0; this.live = any;
    const u = this.mat.uniforms; u.scale.value = innerHeight / 2;
    if (fog) { u.fogColor.value.copy(fog.color); u.fogNear.value = fog.near; u.fogFar.value = fog.far; }
  }

  dispose() { this.points.removeFromParent(); this.points.geometry.dispose(); this.mat.dispose(); }
}
