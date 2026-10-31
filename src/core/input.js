// Keyboard / mouse with pointer lock. `pressed(code)` is true only on the frame a key went down.
export class Input {
  constructor(canvas) {
    this.canvas = canvas;
    this.down = new Set(); this.hit = new Set();
    this.mx = 0; this.my = 0; this.wheel = 0;
    this.lmb = false; this.rmb = false; this.lmbHit = false;
    this.locked = false; this.enabled = true;
    this.axisX = 0; this.axisY = 0; this.axisRun = false; this.touch = false;   // analog stick (touch)
    this.onLockChange = null;
    addEventListener('keydown', e => {
      if (e.code === 'Tab' || e.code === 'Space' || e.code.startsWith('Arrow')) e.preventDefault();
      if (!this.down.has(e.code)) this.hit.add(e.code);
      // any key (not Esc) re-grabs the mouse when the game wants it, so play never stalls on a lost lock
      if (!this.locked && this.enabled && this.wantLock && e.code !== 'Escape' && !this.touch && !document.querySelector('.pn:not(.hidden) input:focus')) this.lock();
      this.down.add(e.code);
    });
    addEventListener('keyup', e => this.down.delete(e.code));
    addEventListener('blur', () => { this.down.clear(); this.lmb = this.rmb = false; });
    addEventListener('mousemove', e => {
      if (!this.locked) return;
      this.mx += e.movementX || 0; this.my += e.movementY || 0;
    });
    canvas.addEventListener('mousedown', e => {
      if (!this.locked && this.enabled && this.wantLock) { this.lock(); return; }
      if (e.button === 0) { this.lmb = true; this.lmbHit = true; }
      if (e.button === 2) this.rmb = true;
    });
    addEventListener('mouseup', e => { if (e.button === 0) this.lmb = false; if (e.button === 2) this.rmb = false; });
    addEventListener('contextmenu', e => e.preventDefault());
    addEventListener('wheel', e => { this.wheel += Math.sign(e.deltaY); }, { passive: true });
    document.addEventListener('pointerlockchange', () => {
      this.locked = document.pointerLockElement === canvas;
      if (!this.locked) { this.lmb = this.rmb = false; }
      this.onLockChange && this.onLockChange(this.locked);
    });
    this.wantLock = false;
  }

  lock() {
    if (this.touch) return;
    try {
      const p = this.canvas.requestPointerLock({ unadjustedMovement: true });
      if (p && p.catch) p.catch(() => { try { this.canvas.requestPointerLock(); } catch (e) { /* ignore */ } });
    } catch (e) { try { this.canvas.requestPointerLock(); } catch (e2) { /* ignore */ } }
  }

  unlock() { if (document.pointerLockElement) document.exitPointerLock(); }

  key(c) { return this.down.has(c); }
  pressed(c) { return this.hit.has(c); }
  consume(c) { this.hit.delete(c); }

  // Called once at the end of every frame.
  endFrame() { this.hit.clear(); this.mx = 0; this.my = 0; this.wheel = 0; this.lmbHit = false; }
}
