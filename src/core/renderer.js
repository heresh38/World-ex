// Renderer, post-processing (bloom + FXAA) and an adaptive resolution governor that holds the frame rate.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';

// A NaN/Inf pixel (an over-bright specular in the half-float buffer, a bad normal) is spread over the whole screen by the
// bloom blur and turns the frame black. Every full-screen pass that reads the scene drops such pixels first.
// (GLSL ES 1.00-safe: no isnan; the comparison is false for both NaN and Inf.)
const SAFE_FN = `vec4 wxSafe(vec4 c){ return (abs(c.r) < 6e4 && abs(c.g) < 6e4 && abs(c.b) < 6e4 && abs(c.a) < 6e4) ? max(c, vec4(0.)) : vec4(0.,0.,0.,1.); }\n`;
function sanitize(mat) {
  const fs = mat.fragmentShader, at = fs.indexOf('void main');
  if (at < 0 || fs.includes('wxSafe')) return;
  mat.fragmentShader = (fs.slice(0, at) + SAFE_FN + fs.slice(at)).replace(/texture2D\(\s*tDiffuse,\s*vUv\s*\)/g, 'wxSafe(texture2D( tDiffuse, vUv ))');
  mat.needsUpdate = true;
}

export const QUALITY = {
  low: { pixel: 0.75, shadow: 1024, bloom: false, fxaa: false, shadowsOn: true, draw: 0.6 },
  medium: { pixel: 1.0, shadow: 2048, bloom: true, fxaa: true, shadowsOn: true, draw: 0.8 },
  high: { pixel: 1.5, shadow: 4096, bloom: true, fxaa: true, shadowsOn: true, draw: 1.0 },
};

export class Renderer {
  constructor(canvas, settings) {
    this.settings = settings;
    this.r = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance', stencil: false });
    this.r.outputColorSpace = THREE.SRGBColorSpace;
    this.r.toneMapping = THREE.ACESFilmicToneMapping;
    this.r.toneMappingExposure = 1.0;
    this.r.shadowMap.enabled = true;
    this.r.shadowMap.type = THREE.PCFSoftShadowMap;
    this.scale = 1;          // dynamic resolution multiplier (0.5..1)
    this.touch = matchMedia && matchMedia('(pointer: coarse)').matches;
    this.fpsAvg = 60;
    this.scene = null; this.camera = null;
    this.composer = null;
    this.applyQuality();
    addEventListener('resize', () => this.resize());
  }

  get q() { return QUALITY[this.settings.quality] || QUALITY.medium; }

  applyQuality() {
    const q = this.q;
    this.r.shadowMap.enabled = q.shadowsOn;
    // phones have 3x screens: 1 css pixel would look smeared, so they get at least 1.5 (2 on high)
    const pix = this.touch ? Math.max(q.pixel, this.settings.quality === 'high' ? 2 : 1.5) : q.pixel;
    this.basePixel = Math.min(devicePixelRatio || 1, pix) * (this.settings.resScale || 1);
    this.buildComposer();
    this.resize();
  }

  buildComposer() {
    if (this.composer) this.composer.dispose();
    const q = this.q;
    const size = new THREE.Vector2(innerWidth, innerHeight);
    const rt = new THREE.WebGLRenderTarget(size.x, size.y, { type: THREE.HalfFloatType, samples: 0 });
    this.composer = new EffectComposer(this.r, rt);
    this.renderPass = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
    this.composer.addPass(this.renderPass);
    // first-person viewmodel: drawn after the world with depth cleared so it never clips into walls
    this.overlayPass = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
    this.overlayPass.clear = false; this.overlayPass.clearDepth = true; this.overlayPass.enabled = false;
    this.composer.addPass(this.overlayPass);
    this.bloom = null;
    if (q.bloom) {
      const bp = this.bloomParams || [0.35, 1.0, 0.4];
      this.bloom = new UnrealBloomPass(new THREE.Vector2(size.x / 2, size.y / 2), bp[0], bp[2], bp[1]);
      this.composer.addPass(this.bloom);
      sanitize(this.bloom.materialHighPassFilter);
    }
    const out = new OutputPass(); sanitize(out.material);
    this.composer.addPass(out);
    this.fxaa = null;
    if (q.fxaa) {
      this.fxaa = new ShaderPass(FXAAShader);
      this.composer.addPass(this.fxaa);
    }
  }

  setBloom(strength, threshold = 1.0, radius = 0.4) {
    this.bloomParams = [strength, threshold, radius];
    if (!this.bloom) return;
    this.bloom.strength = strength; this.bloom.threshold = threshold; this.bloom.radius = radius;
  }

  resize() {
    const w = innerWidth, h = innerHeight, pr = this.basePixel * this.scale;
    this.r.setPixelRatio(pr);
    this.r.setSize(w, h, false);
    this.composer.setPixelRatio(pr);
    this.composer.setSize(w, h);
    if (this.fxaa) {
      this.fxaa.material.uniforms.resolution.value.set(1 / (w * pr), 1 / (h * pr));
    }
    if (this.camera) { this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); }
  }

  // Adaptive resolution: nudge the internal resolution to keep ~60 fps.
  govern(dt) {
    if (!this.settings.dynamicRes) return;
    const fps = 1 / Math.max(dt, 1e-4);
    this.fpsAvg += (fps - this.fpsAvg) * 0.05;
    this._t = (this._t || 0) + dt;
    if (this._t < 1.5) return;
    this._t = 0;
    let s = this.scale;
    const floor = this.touch ? .75 : .55;          // never drop a phone below ~1.1x: blur reads worse than a few fps
    if (this.fpsAvg < 52 && s > floor) s = Math.max(floor, s - 0.1);
    else if (this.fpsAvg > 59 && s < 1) s = Math.min(1, s + 0.05);
    if (s !== this.scale) { this.scale = s; this.resize(); }
  }

  // Draws a second scene into a screen rectangle (CSS pixels) on top of the frame, keeping the frame's colour.
  preview(scene, cam, rect) {
    const r = this.r, w = rect.width, h = rect.height;
    if (w < 24 || h < 24) return;
    const x = rect.left, y = innerHeight - rect.bottom;
    r.setRenderTarget(null);
    r.setScissorTest(true); r.setScissor(x, y, w, h); r.setViewport(x, y, w, h);
    const ac = r.autoClear; r.autoClear = false; r.clearDepth();
    cam.aspect = w / h; cam.updateProjectionMatrix();
    r.render(scene, cam);
    r.autoClear = ac; r.setScissorTest(false); r.setViewport(0, 0, innerWidth, innerHeight);
  }

  render(scene, camera, overlay = null) {
    this.scene = scene; this.camera = camera;
    this.renderPass.scene = scene; this.renderPass.camera = camera;
    this.overlayPass.enabled = !!overlay;
    if (overlay) { this.overlayPass.scene = overlay; this.overlayPass.camera = camera; }
    this.composer.render();
  }
}
