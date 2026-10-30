// Renderer, post-processing (bloom + FXAA) and an adaptive resolution governor that holds the frame rate.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';

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
    this.basePixel = Math.min(devicePixelRatio || 1, q.pixel) * (this.settings.resScale || 1);
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
    this.bloom = null;
    if (q.bloom) {
      this.bloom = new UnrealBloomPass(new THREE.Vector2(size.x / 2, size.y / 2), 0.55, 0.5, 0.92);
      this.composer.addPass(this.bloom);
    }
    this.composer.addPass(new OutputPass());
    this.fxaa = null;
    if (q.fxaa) {
      this.fxaa = new ShaderPass(FXAAShader);
      this.composer.addPass(this.fxaa);
    }
  }

  setBloom(strength, threshold = 0.92, radius = 0.5) {
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
    if (this.fpsAvg < 52 && s > 0.55) s = Math.max(0.55, s - 0.1);
    else if (this.fpsAvg > 59 && s < 1) s = Math.min(1, s + 0.05);
    if (s !== this.scale) { this.scale = s; this.resize(); }
  }

  render(scene, camera) {
    this.scene = scene; this.camera = camera;
    this.renderPass.scene = scene; this.renderPass.camera = camera;
    this.composer.render();
  }
}
