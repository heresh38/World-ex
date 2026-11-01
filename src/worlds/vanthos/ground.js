// VANTHOS ground: the textured surfaces of the dead city (tools/blender/vanthos_textures.py sets vr_asphalt / vr_pavers /
// vr_dirt / vr_grass, sampled in world space with anisotropic filtering).
//   streets   one merged ribbon mesh per road class; u runs across the road, v along it. Cracked asphalt with worn,
//             broken lane paint (dashed centre line, edge lines; multi-lane on the ring roads and highways), dark kerb
//             gutters, grass and weeds pushing in from the edges and through the cracks, drifts of ash and dirt
//   blocks    every city block is a raised slab: a broken sidewalk band of pavers around the edge (kerb faces down to the
//             street) and a lot inside of soil, rubble dust and wild grass
//   terrain   the rest (the crater, empty ground, the badlands): soil, grass and rock, scorched near the Spire
// Each material blends its maps with value noise in world space, so no surface reads as one flat colour.
import * as THREE from 'three';

export const GROUND_TEX = ['vr_asphalt', 'vr_pavers', 'vr_dirt', 'vr_grass'];

const NOISE = `
float vhash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f);
  return mix(mix(vhash(i), vhash(i + vec2(1., 0.)), f.x), mix(vhash(i + vec2(0., 1.)), vhash(i + vec2(1., 1.)), f.x), f.y); }
float vfbm(vec2 p){ return vnoise(p) * .55 + vnoise(p * 2.13 + 7.1) * .3 + vnoise(p * 4.7 + 3.3) * .15; }`;

// world-space sampled material. `body` is GLSL that sets `vec3 alb` (albedo) and `float wN` (how much of the primary
// normal map to keep) from the samplers t0..t3 and vWP / vL (the custom attribute).
function splatMaterial(T, maps, body, opts = {}) {
  const mat = new THREE.MeshStandardMaterial({ map: T[maps[0] + '_c'], normalMap: T[maps[0] + '_n'], roughness: .92, metalness: 0, envMapIntensity: .25,
    normalScale: new THREE.Vector2(opts.ns || 1, opts.ns || 1), polygonOffset: !!opts.offset, polygonOffsetFactor: opts.offset || 0, polygonOffsetUnits: opts.offset || 0 });
  const uni = { t1: { value: T[maps[1] + '_c'] }, t2: { value: T[maps[2] + '_c'] }, t3: { value: T[(maps[3] || maps[2]) + '_c'] }, ...(opts.uniforms || {}) };
  mat.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, uni);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;\nattribute vec3 aL;\nvarying vec3 vL;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP = (modelMatrix * vec4(transformed, 1.)).xyz; vL = aL;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP; varying vec3 vL;\nuniform sampler2D t1, t2, t3;\n' + (opts.decl || '') + NOISE)
      .replace('#include <map_fragment>', `vec3 alb; float wN = 1.;\n${body}\ndiffuseColor.rgb *= alb;`)
      .replace('#include <normal_fragment_maps>', '#include <normal_fragment_maps>\nnormal = normalize(mix(nonPerturbedNormal, normal, wN));');
  };
  mat.customProgramCacheKey = () => 'vxground-' + (opts.key || maps.join());
  return mat;
}

// ---------------------------------------------------------------- streets: u across, v along, aL = (across 0..1, along m, metres to the segment end)
const STREET_BODY = `
  vec2 w = vWP.xz;
  vec3 asph = texture2D(map, vMapUv).rgb;
  float n1 = vfbm(w * .045), n2 = vfbm(w * .19 + 11.), n3 = vnoise(w * .9);
  float across = vL.x * uW, along = vL.y, edge = min(across, uW - across);
  // lane paint, worn to fragments: centre / lane dividers dashed, edge lines solid; none in the junction boxes
  float paint = 0.;
  float lw = uW / uLanes;
  float k = abs(fract(across / lw + .5) - .5) * lw;                          // distance to the nearest lane line
  float inner = step(lw * .5, edge);
  float dash = step(fract(along / 9.), .45);
  paint += (1. - smoothstep(.06, .1, k)) * dash * inner;
  float el = abs(edge - 1.1); paint += 1. - smoothstep(.06, .1, el);
  paint *= smoothstep(6., 10., vL.z) * smoothstep(.38, .62, n2) * smoothstep(.2, .5, n3);
  vec3 pc = mix(vec3(.62, .58, .45), vec3(.75, .62, .25), step(abs(across - uW * .5), .3) * uYellow);
  vec3 c = mix(asph, pc * (.55 + .3 * n1), clamp(paint, 0., 1.) * .8);
  // gutters along the kerb: dark, damp, silted
  float gut = 1. - smoothstep(.2, 1.1, edge);
  c *= 1. - gut * .45;
  // dirt and ash drifted against the kerbs and in wide fans across the road
  float drift = clamp(smoothstep(.5, .78, n1 + (1. - smoothstep(0., 3.5, edge)) * .35), 0., 1.);
  vec3 dirt = texture2D(t2, w * .16).rgb;
  c = mix(c, dirt, drift * .85);
  // grass from the kerbs and in the cracks; big patches where the road has given up
  float gr = clamp((1. - smoothstep(.0, 2.4, edge)) * smoothstep(.35, .6, n2) + smoothstep(.62, .78, n1 * .7 + n2 * .45), 0., 1.);
  vec3 grass = texture2D(t1, w * .25).rgb;
  c = mix(c, grass, gr * .9);
  alb = c * (.85 + .3 * vnoise(w * .02));
  wN = 1. - max(drift, gr) * .6;`;

// ---------------------------------------------------------------- block slabs: aL = (local x m, local z m, block half size packed: w/2 in x, d/2 in y? )
const BLOCK_BODY = `
  vec2 w = vWP.xz;
  float edge = min(uHalf.x - abs(vL.x), uHalf.y - abs(vL.y));
  float n1 = vfbm(w * .05 + 3.), n2 = vfbm(w * .21 + 17.), n3 = vnoise(w * 1.3);
  vec3 pav = texture2D(map, vMapUv).rgb;
  vec3 dirt = texture2D(t1, w * .16).rgb, grass = texture2D(t2, w * .25).rgb;
  float walk = 1. - smoothstep(3.8, 4.8 + n3 * .8, edge);                     // the sidewalk band
  float lot = 1. - walk;
  float gr = smoothstep(.45, .7, n2 * .7 + n1 * .5) * (lot + walk * .45);
  float du = smoothstep(.4, .7, n1) * (.5 + .5 * lot);
  vec3 c = mix(pav, dirt, max(lot * (.75 + .25 * n2), du * .8));
  c = mix(c, grass, clamp(gr * (.55 + .45 * walk), 0., 1.) * .85);
  c *= 1. - lot * smoothstep(.55, .75, n3 * .5 + n1 * .6) * .35;               // ash and soot stains in the lots
  c *= mix(1., .55, 1. - smoothstep(.0, .35, edge));                          // kerb edge
  alb = c * (.85 + .3 * vnoise(w * .02 + 5.));
  wN = walk * (1. - gr * .7) + lot * .4;`;

// ---------------------------------------------------------------- open ground
function terrainBody(crater, spire) {
  return `
  vec2 w = vWP.xz;
  float r = length(w);
  float n1 = vfbm(w * .012), n2 = vfbm(w * .09 + 5.), n3 = vfbm(w * .35 + 9.);
  vec3 dirt = texture2D(map, vMapUv).rgb, grass = texture2D(t1, w * .25).rgb, rock = texture2D(t2, w * .03).rgb * vec3(.55, .5, .47);
  vec3 c = mix(dirt, grass, smoothstep(.52, .74, n1 * .6 + n2 * .5) * .85);
  c = mix(c, dirt * vec3(1.05, 1., .95), smoothstep(.6, .8, n3) * .5);
  c = mix(c, rock, smoothstep(4., 30., vWP.y) * .85);
  float crater = 1. - smoothstep(${(crater - 30).toFixed(1)}, ${(crater + 20).toFixed(1)}, r);
  vec3 burnt = dirt * vec3(.42, .36, .38) + vec3(.02, 0., .015);
  c = mix(c, burnt, crater * step(${spire.toFixed(1)}, r) * (.8 + .2 * n2));
  alb = c * (.85 + .3 * vnoise(w * .015));
  wN = .8;`;
}

export class Ground {
  constructor(world) { this.w = world; this.g = world.g; }

  static jobs() { return GROUND_TEX.flatMap(t => [{ type: 'texture', name: t + '_c', file: t + '_c.jpg', weight: .3, label: 'Texture ' + t }, { type: 'texture', name: t + '_n', file: t + '_n.jpg', color: false, weight: .2 }]); }

  materials() {
    const T = this.g.assets.textures;
    this.street = splatMaterial(T, ['vr_asphalt', 'vr_grass', 'vr_dirt'], STREET_BODY, { uniforms: { uW: { value: 14 }, uLanes: { value: 2 }, uYellow: { value: 1 } }, decl: 'uniform float uW, uLanes, uYellow;', offset: -2, key: 'street', ns: 1.2 });
    this.wide = splatMaterial(T, ['vr_asphalt', 'vr_grass', 'vr_dirt'], STREET_BODY, { uniforms: { uW: { value: 25 }, uLanes: { value: 4 }, uYellow: { value: 1 } }, decl: 'uniform float uW, uLanes, uYellow;', offset: -2, key: 'street', ns: 1.2 });
    this.wide.side = THREE.DoubleSide;
    return this;
  }

  blockMaterial(hw, hd) {
    const T = this.g.assets.textures;
    return splatMaterial(T, ['vr_pavers', 'vr_dirt', 'vr_grass'], BLOCK_BODY, { uniforms: { uHalf: { value: new THREE.Vector2(hw, hd) } }, decl: 'uniform vec2 uHalf;', offset: -1, key: 'block', ns: 1.3 });
  }

  terrainMaterial(crater, spire) {
    const T = this.g.assets.textures;
    const rock = T.rock;
    T.vr_rock_c = rock;
    return splatMaterial(T, ['vr_dirt', 'vr_grass', 'vr_rock'], terrainBody(crater, spire), { key: 'terrain', ns: 1 });
  }

  // a road ribbon along a polyline of [x, z] points (width W), heights from hf; appended into the arrays of `acc`
  static ribbon(acc, pts, W, hf, closed = false) {
    const P = acc.pos, U = acc.uv, L = acc.l, I = acc.idx;
    let along = 0; const base = P.length / 3;
    const n = pts.length, total = (() => { let t = 0; for (let i = 1; i < n; i++) t += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return t; })();
    for (let i = 0; i < n; i++) {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
      let tx = b[0] - a[0], tz = b[1] - a[1]; const tl = Math.hypot(tx, tz) || 1; tx /= tl; tz /= tl;
      if (i) along += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      const nx = -tz, nz = tx, endD = closed ? 99 : Math.min(along, total - along);
      for (const s of [-1, 1]) {
        const x = pts[i][0] + nx * s * W / 2, z = pts[i][1] + nz * s * W / 2;
        P.push(x, hf(x, z, pts[i]), z); U.push(x / 8, z / 8); L.push(s < 0 ? 0 : 1, along, endD);
      }
      if (i) { const k = base + i * 2; I.push(k - 2, k - 1, k, k - 1, k + 1, k); }
    }
  }

  static mesh(acc, mat) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(acc.pos, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(acc.uv, 2));
    geo.setAttribute('aL', new THREE.Float32BufferAttribute(acc.l, 3));
    geo.setIndex(acc.idx); geo.computeVertexNormals();
    // keep normals up on the flat parts (a ribbon's computed normals are fine on ramps)
    const m = new THREE.Mesh(geo, mat); m.receiveShadow = true;
    return m;
  }

  static acc() { return { pos: [], uv: [], l: [], idx: [] }; }
}
