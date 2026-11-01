// Skippable in-engine cutscenes (landing / take-off). Worlds call runCinematic() from their optional arrive()/depart()
// hooks, which Game.travel awaits. While one runs, Game.loop calls g.cine(dt) instead of the gameplay update, the HUD
// and viewmodel are hidden, the screen gets letterbox bars and Space / Enter / Esc / click / tap skips to the end.
import * as THREE from 'three';

let css = false;
function overlay() {
  if (!css) {
    css = true;
    const st = document.createElement('style');
    st.textContent = `.cine-bars{position:fixed;inset:0;pointer-events:none;z-index:40}
      .cine-bars:before,.cine-bars:after{content:'';position:absolute;left:0;right:0;height:0;background:#000;transition:height .6s ease}
      .cine-bars:before{top:0}.cine-bars:after{bottom:0}.cine-bars.on:before,.cine-bars.on:after{height:9vh}
      .cine-skip{position:absolute;right:28px;bottom:calc(9vh + 14px);font:600 13px Rajdhani,sans-serif;letter-spacing:.22em;color:rgba(232,226,212,.75);
        text-transform:uppercase;opacity:0;transition:opacity .8s ease .6s}.cine-bars.on .cine-skip{opacity:1}
      .cine-title{position:absolute;left:36px;bottom:calc(9vh + 12px);font:700 15px Rajdhani,sans-serif;letter-spacing:.3em;color:#e8e2d4;text-transform:uppercase;opacity:0;transition:opacity 1s ease .4s}
      .cine-title small{display:block;font-weight:500;font-size:11px;letter-spacing:.24em;color:#1ad8ff;margin-top:2px}.cine-bars.on .cine-title{opacity:.92}`;
    document.head.appendChild(st);
  }
  const el = document.createElement('div'); el.className = 'cine-bars';
  el.innerHTML = '<div class="cine-title"></div><div class="cine-skip">Space · skip</div>';
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add('on'));
  return el;
}

// shot: {duration, title?, sub?, update(t, dt) -> void, finish(skipped) -> void}
// Returns a promise that resolves when the shot ends (or is skipped).
export function runCinematic(g, shot) {
  return new Promise(resolve => {
    const prevState = g.state, el = overlay();
    if (shot.title) el.querySelector('.cine-title').innerHTML = shot.title + (shot.sub ? '<small>' + shot.sub + '</small>' : '');
    const fov0 = g.camera.fov;
    g.hud.show(false); g.hud.prompt(null);
    if (g.touch) g.touch.show(false);
    g.state = 'cinematic';
    const t0 = performance.now();
    let done = false;
    const finish = skipped => {
      if (done) return; done = true;
      removeEventListener('keydown', onKey, true); removeEventListener('pointerdown', onPtr, true);
      g.cine = null;
      try { shot.finish && shot.finish(skipped); } catch (e) { console.error(e); }
      el.classList.remove('on'); setTimeout(() => el.remove(), 700);
      g.camera.fov = fov0; g.camera.updateProjectionMatrix();
      if (g.state === 'cinematic') g.state = prevState;
      resolve(skipped);
    };
    const onKey = e => { if (['Space', 'Enter', 'Escape', 'KeyE'].includes(e.code)) { e.preventDefault(); e.stopPropagation(); finish(true); } };
    const onPtr = () => { if (performance.now() - t0 > 250) finish(true); };
    addEventListener('keydown', onKey, true); addEventListener('pointerdown', onPtr, true);
    g.cine = dt => {
      // g.cineTime (seconds) pins the shot clock: tests use it to grab frames at exact moments on slow renderers
      const t = g.cineTime != null ? g.cineTime : (performance.now() - t0) / 1000;
      try { shot.update(Math.min(t, shot.duration), dt); } catch (e) { console.error(e); finish(true); return; }
      if (t >= shot.duration) finish(false);
    };
    g.skipCinematic = () => finish(true);
  });
}

// helpers for shots
export const ease = t => { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); };
export const easeOut = t => { t = Math.max(0, Math.min(1, t)); return 1 - Math.pow(1 - t, 3); };
export const easeIn = t => { t = Math.max(0, Math.min(1, t)); return t * t * t; };
export function bezier(out, a, b, c, d, t) {
  const u = 1 - t;
  return out.set(0, 0, 0).addScaledVector(a, u * u * u).addScaledVector(b, 3 * u * u * t).addScaledVector(c, 3 * u * t * t).addScaledVector(d, t * t * t);
}
export const _m4 = new THREE.Matrix4();
