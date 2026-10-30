# Open World Drive — notes for Claude Code

Single-page Three.js game (r186 from jsDelivr). The shipped artifact is `index.html`, produced by `python3 tools/build.py`. Never hand-edit `index.html`; edit `src/patches/*.js` (or `src/base.html` for engine-level fixes) and rebuild.

## Build pipeline (tools/build.py)
1. Reads `src/base.html` (the original engine page, ~1 MB, data blocks emptied).
2. Strips the old arena mode, then inserts all patch modules (in `MODULES` order) right before `function frame(){requestAnimationFrame(frame);` — i.e. inside `startApp`, after the engine's functions exist but before the world is built (`setTimeout(()=>{buildTerrain();...})`).
3. Applies text fixes: texture means, `GTEX` slot → `tex/*.jpg` mapping, disables the old model loaders (`loadCarsHQ`, `loadShips`, …), forces `TREEV=true` so trees come from our generator, blanks old credits.
4. Runs `tools/names.py` (keeps all player-facing text our own — no terms from other games).
5. Adds a test-only eval hook (`window.__ev`, active only when `window.__TEST` is set).

## Patch conventions
- Override pattern: `{const o=fn;fn=function(){ ...; return o.apply(this,arguments)}}`. Wrap, don't replace, unless the module owns that system.
- One per-frame hook: `preRender`. Every world (city, generated landing zones `GEN`, frontier `bioFrame`) calls it, so put per-frame logic there — this is what keeps shooting/scoping/reloading identical everywhere.
- Name things with the module's version suffix (`hvBuild97`, `col96Push`, …) to avoid collisions in the shared scope.
- Car contract (`modelRoot(name)` must return `{root, ch, wh, fp, tl, paints, rc, meta}`): `root.children = [ch, pivot0..3, …]`; the first child group of `ch` with exactly one child group is the steering pivot (traffic takeover code relies on this); `tl` is the brake-light material; paint materials carry `userData.paint`.
- Seats: `root.userData.seat97 = {hip, wheel, roof, W, L, wr, tilt}` in car-local space (forward +z, driver at +x). `seatFrame` (engine) puts the avatar there and IK-places hands at the wheel rim at angle `SEAT69.st` and `+π`; `v97c` rotates the yoke to the same angle so hands stay on it.

## Modules (order matters)
- v89a–g, v90b/c, v91a–c: weapons, armour, character, editor and world systems (gun art style: bone-white / gunmetal / brass with neon).
- v96d: texture colour means. v96c: procedural trees (11 species). v96b: walkable crashed ships with mesh collision, sky ships. v96e: stability (async shader warm-up, incremental BVH, seat pre-compute). v96a: unified combat in every world, clear-glass optics, aim smoothing/assist, surface-specific impact effects.
- v97a: hover-car designs (`HVD97`), lofted bodies (`loft97`), cockpits, yoke. v97b: street props (`mpMake`), hover ships (`shipGroup`). v97c: wires the cars into the engine (CARDEF/SPAWN, modelRoot, seatCompute, makeAlfa, per-frame hover/yoke), merges car parts for draw-call savings.

## Art direction / rules
- One unified sci-fi style across guns, armour, world and vehicles: bone-white ceramic, gunmetal, brass, neon cyan/magenta/amber; steampunk variants in brass/copper/wood.
- All models and textures are generated in code or by `tools/texgen*.py`. Do not add third-party models/textures.
- No names, terms or text from other games.
- The owner prefers direct fixes over explanations, all features unlocked, and high visual fidelity.

## Testing
- `npm run serve` then `npm test` (Playwright). Software rendering is very slow; give long waits.
- `npm run preview` → `preview/vehicles.html` for quick model checks.
