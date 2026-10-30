// Asset loading with real byte-level progress. GLBs are streamed with fetch() and parsed by GLTFLoader.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

const MODEL_DIR = 'assets/models/';
const TEX_DIR = 'assets/textures/';

export class Assets {
  constructor(renderer) {
    this.r = renderer;
    this.gltf = new GLTFLoader();
    this.texLoader = new THREE.TextureLoader();
    this.models = {}; this.textures = {}; this.json = {};
    this.maxAniso = renderer.capabilities.getMaxAnisotropy();
  }

  async fetchBytes(url, onBytes) {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to load ' + url + ' (' + res.status + ')');
    const total = +res.headers.get('content-length') || 0;
    if (!res.body || !total) { const b = await res.arrayBuffer(); onBytes(b.byteLength, b.byteLength); return b; }
    const reader = res.body.getReader(); const chunks = []; let got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value); got += value.length; onBytes(got, total);
    }
    const out = new Uint8Array(got); let o = 0;
    for (const c of chunks) { out.set(c, o); o += c.length; }
    return out.buffer;
  }

  // jobs: [{type:'model'|'texture'|'json', name, file, weight}] ; onProgress(0..1, label)
  async loadAll(jobs, onProgress) {
    const todo = jobs.filter(j => !(j.type === 'model' ? this.models[j.name] : j.type === 'texture' ? this.textures[j.name] : this.json[j.name]));
    const weight = todo.reduce((s, j) => s + (j.weight || 1), 0) || 1;
    const prog = new Map();
    const report = (label) => {
      let s = 0; for (const j of todo) s += (prog.get(j) || 0) * (j.weight || 1);
      onProgress && onProgress(s / weight, label);
    };
    report('');
    // limited concurrency keeps progress smooth and avoids hammering the server
    let i = 0;
    const worker = async () => {
      while (i < todo.length) {
        const j = todo[i++];
        if (j.type === 'model') {
          const buf = await this.fetchBytes(MODEL_DIR + j.file, (g, t) => { prog.set(j, .9 * g / t); report(j.label || j.name); });
          const g = await this.gltf.parseAsync(buf, MODEL_DIR);
          this.prepModel(g);
          this.models[j.name] = g;
        } else if (j.type === 'texture') {
          this.textures[j.name] = await this.loadTexture(j.file, j.color !== false);
        } else if (j.type === 'json') {
          this.json[j.name] = await (await fetch(MODEL_DIR + j.file)).json();
        }
        prog.set(j, 1); report(j.label || j.name);
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    onProgress && onProgress(1, '');
  }

  loadTexture(file, color = true) {
    return new Promise((res, rej) => this.texLoader.load(TEX_DIR + file, t => {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      t.anisotropy = Math.min(8, this.maxAniso);
      res(t);
    }, undefined, () => rej(new Error('texture ' + file))));
  }

  prepModel(g) {
    g.scene.traverse(o => {
      if (o.isMesh) {
        o.castShadow = true; o.receiveShadow = true;
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of ms) {
          if (m.map) m.map.anisotropy = Math.min(8, this.maxAniso);
          if (m.transparent || (m.opacity !== undefined && m.opacity < 1)) {
            m.transparent = true; m.depthWrite = false; o.castShadow = false;
          }
          if (/glass|holo|canopy/.test(m.name)) { o.castShadow = false; m.envMapIntensity = 1.5; }
          if (m.emissive && m.emissiveIntensity > 0 && m.emissive.getHex() !== 0) {
            o.castShadow = false;
            // Blender emission strengths are authored for Cycles; scale them so only the hottest parts bloom
            m.emissiveIntensity = Math.min(2.4, m.emissiveIntensity * .38);
          }
        }
      }
    });
  }

  // Deep clone; skinned meshes need SkeletonUtils.
  clone(name, sub = null) {
    const g = this.models[name];
    if (!g) throw new Error('model not loaded: ' + name);
    const src = sub ? g.scene.getObjectByName(sub) : g.scene;
    if (!src) throw new Error('node ' + sub + ' missing in ' + name);
    let skinned = false; src.traverse(o => { if (o.isSkinnedMesh) skinned = true; });
    const c = skinned ? SkeletonUtils.clone(src) : src.clone(true);
    c.position.set(0, 0, 0); c.rotation.set(0, 0, 0);
    return c;
  }

  clips(name) { return this.models[name].animations; }
}
