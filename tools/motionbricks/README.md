# MotionBricks trial

A trial of NVIDIA's MotionBricks (https://github.com/NVlabs/motionbricks, SIGGRAPH 2026) on our male body (the owner,
2026-11-23: "can we use it for our animation", then "Yes, trial it"). MotionBricks fills in the motion between four
recent poses and up to four target poses. Here both come from OUR clips, so it only makes the transitions between our
own motion. Nothing of it is in the game.

Licences: code Apache 2.0; the pretrained models under the NVIDIA Open Model Agreement (commercial use allowed; NVIDIA
claims no ownership of what they generate; shipping the model itself needs the agreement and its notice); the SOMA rig
file Apache 2.0. Its sample motion clips (`assets/motions`) are for evaluation only and are used nowhere here.

Setup (once, outside this repository; about 8 GB with its models and environment; it needs an NVIDIA card):

```
git clone https://github.com/NVlabs/motionbricks.git C:/Dev/motionbricks
cd C:/Dev/motionbricks
uv sync
```

The steps (Blender 5.2, our own Python, and MotionBricks' environment run from its folder):

1. `blender -b --factory-startup -P tools/motionbricks/dump_body.py -- <SourceArt/Characters/src/orion_male.glb> <clips.npz> --fps=30`:
   our skeleton and every clip, sampled at 30 frames a second.
2. `uv run python <repo>/tools/motionbricks/mb_generate.py --dump-skeleton <soma_skel.npz>` (in `C:/Dev/motionbricks`):
   MotionBricks' own SOMA rig (77 joints, a T-pose).
3. `python tools/motionbricks/retarget.py <clips.npz> <soma_skel.npz> <out_dir> --clips=Idle,Stroll,Walk,Run,...`: our
   clips as SOMA BVH files (each bone carried across through its anatomical frame; the looping clips moved on at the
   speed their planted feet move back), and `alignment.npz` for the way back.
4. `uv run python <repo>/tools/motionbricks/mb_generate.py --clips <out_dir> --jobs <jobs.json> --out <generated.npz>`:
   the transitions (a job: the context clip and time, the target clip and time, where the target stands: forward, left,
   turn).
5. `blender -b --factory-startup -P tools/motionbricks/apply_body.py -- <orion_male.glb> <generated.npz> <out_dir>/alignment.npz <clips.npz> <render_dir>`:
   back onto our bones, the planted feet held where the model says they are down, measured (`MBMEASURE`) and rendered
   beside the body and from the front.

The trial's jobs: start (idle to the walk), stop (walk to idle), turn180 (on the spot), walk_turn90, stroll_to_run,
run_stop, crouch_down. Each generation took 3.4 ms on an RTX 4070 Ti. Pictures in
`unreal/ShatteredOrbit/Saved/MotionBricksTrial`.
