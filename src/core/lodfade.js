// Screen-door level-of-detail fades for instanced kits (flora.js, downtown.js, planet.js scatter pools).
// Each instance carries `aFade` = (s, e, born):
//   (0, 0, 0)        drawn solid (the attribute's default, so meshes without it are unaffected)
//   (s, e, .)  s,e>0 fades OUT between s and e metres (horizontal distance from the camera to the instance origin)
//   (-s, -e, .)      fades IN between s and e, drawing exactly the pixels the (s, e) partner drops (same dither),
//                    so two tiers cross-fade with no holes and no double cover
//   born > 0         the instance appears over APPEAR seconds after the time `born` (streamed props), on uFadeT;
//   born < 0         it disappears over APPEAR seconds after the time -born (unloaded props)
// The fade is evaluated per frame in the vertex shader, so the CPU only re-buckets every few metres and the transition
// is continuous. The dither is interleaved gradient noise in screen space; the shadow pass is not dithered.
import * as THREE from 'three';

export const FADE_TIME = { value: 0 };          // seconds, set by the systems that stream instances (g.time)
export const APPEAR = 1.6;

const VERT_DECL = `
#ifdef USE_INSTANCING
  attribute vec3 aFade;
  uniform float uFadeT;
#endif
varying vec2 vFd;`;
const VERT_MAIN = `
vFd = vec2( 0. );
#ifdef USE_INSTANCING
if ( aFade.x != 0. || aFade.z != 0. ) {
  vec3 fIp = ( modelMatrix * vec4( instanceMatrix[ 3 ].xyz, 1. ) ).xyz;
  float fS = abs( aFade.x ), fE = abs( aFade.y );
  float fT = aFade.x == 0. ? 0. : clamp( ( distance( fIp.xz, cameraPosition.xz ) - fS ) / max( fE - fS, .001 ), 0., 1. );
  vFd.x = aFade.x < 0. ? - max( fT, 1e-4 ) : fT;
  if ( aFade.z > 0. ) vFd.y = 1. - clamp( ( uFadeT - aFade.z ) / ${APPEAR.toFixed(2)}, 0., 1. );
  else if ( aFade.z < 0. ) vFd.y = clamp( ( uFadeT + aFade.z ) / ${APPEAR.toFixed(2)}, 0., 1. ) * 1.001;
}
#endif`;
const FRAG_DECL = 'varying vec2 vFd;';
const FRAG_TEST = `
if ( vFd.x != 0. || vFd.y > 0. ) {
  float fDth = fract( 52.9829189 * fract( dot( floor( gl_FragCoord.xy ), vec2( .06711056, .00583715 ) ) ) );
  if ( vFd.x > 0. ? fDth < vFd.x : ( vFd.x < 0. && fDth >= - vFd.x ) ) discard;
  if ( fDth < vFd.y ) discard;
}`;

// patch a shader object (inside onBeforeCompile)
export function fadeShader(sh) {
  sh.uniforms.uFadeT = FADE_TIME;
  sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\n' + VERT_DECL)
    .replace('#include <begin_vertex>', '#include <begin_vertex>\n' + VERT_MAIN);
  sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\n' + FRAG_DECL)
    .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\n' + FRAG_TEST);
}

// A faded copy of a material (the original stays untouched for meshes that carry no aFade attribute: an unbound
// attribute reads whatever generic value another program left at that location). Existing onBeforeCompile hooks run
// first; uniforms they capture stay shared with the original. Cached per source material.
const COPIES = new WeakMap();
export function fadeMaterial(src) {
  if (!src || src.userData.lodFade) return src;
  let m = COPIES.get(src);
  if (m) return m;
  m = src.clone();
  m.userData = { ...src.userData, lodFade: true, fadeOf: src };
  const prev = src.onBeforeCompile, key = src.customProgramCacheKey();
  m.onBeforeCompile = function (sh, r) { prev.call(src, sh, r); fadeShader(sh); };
  m.customProgramCacheKey = () => key + '|lodfade';
  COPIES.set(src, m);
  return m;
}

// geometry view with its own aFade attribute (vertex data stays shared with the source geometry)
export function fadeGeometry(geo, attr) {
  const g = new THREE.BufferGeometry();
  for (const k in geo.attributes) g.setAttribute(k, geo.attributes[k]);
  for (const k in geo.morphAttributes) g.morphAttributes[k] = geo.morphAttributes[k];
  g.setIndex(geo.index);
  for (const gr of geo.groups) g.addGroup(gr.start, gr.count, gr.materialIndex);
  g.drawRange = { ...geo.drawRange };
  g.boundingBox = geo.boundingBox; g.boundingSphere = geo.boundingSphere;
  g.setAttribute('aFade', attr);
  g.userData.shared = true;
  return g;
}

export function fadeAttr(n) {
  const a = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3);
  a.setUsage(THREE.DynamicDrawUsage);
  return a;
}
