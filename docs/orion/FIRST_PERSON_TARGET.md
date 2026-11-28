# The first-person target

The owner, 2026-11-27, with a video (https://www.youtube.com/watch?v=a1YQjgwYezM, an hour-long showcase of every
first-person weapon of another game; a quality target only, nothing of its names, guns or look is used):

> "take a look at this video, this is how my first person must look and feel, this level of detail, visual look, feel,
> this style, these reloads, these animations, this is the level i want. do this now and i don't care how you do it,
> just do it and don't ask me for anything"

and, as it was being watched: "the video is very long so you don't have to watch it all, just watch like one or 2
pistol/shotgun/assult rifle/sniper etc so it can be done fast".

This is what was seen in it (a pistol, an assault rifle, a shotgun and a sniper rifle, each through its draw, its hip
and aimed fire, its reload and its inspect, stepped through a few frames a second), written as what OURS must do. It
sits under the hard rules: one body and one camera, the hands always on the gun, every joint in a human's range.

## What the reference does

1. **The gun is large and near.** At the hip a rifle runs from the middle of the picture to its lower right corner,
   its stock cut off by the corner; a sniper rifle fills the right half. The hands and forearms are in the picture.
2. **A reload is a show.** The gun swings UP into the middle of the picture, 35 to 45 degrees muzzle-up, rolled so
   that its side and its magazine well face the eyes, and it fills half the picture. The firing hand stays low and
   right and the gun turns about it. Every step is seen: the old magazine drawn out and carried off, the well left
   empty a moment, the fresh one brought up from the foot of the picture, pushed home, slapped; a handle or a slide
   racked with the gun turned again for it (a pistol goes muzzle-up, the hand over its slide).
3. **It never holds still and never moves on rails.** The gun turns from one presentation to the next as the hand
   goes from one job to the next; it overshoots a little and settles; it jolts as a part strikes home; the view
   itself is nudged a degree or less by each of those blows.
4. **Each kind of gun reloads its own way** and takes its own time (a pistol about three seconds from empty, a rifle
   two and a half).
5. **Drawing a gun is a small act** (a handle racked, a chamber checked), and looking a gun over is another.
6. **Firing is felt**: the gun kicks back and up, the view climbs, smoke hangs at the muzzle, cases fly.
7. **On the sights** the gun is dead centre and still; only the shot moves it.

## Where ours stands (keep this honest)

| | state |
|---|---|
| 2, 3: reloads shown, sprung, jolted, the view nudged | built 2026-11-27: `FSOReloadShow`, `Data/reload_shows.json`, `USOViewmodelComponent::ReloadPose / Handle`, `ASOCharacter::OnWeaponHandled` |
| 4: each kind its own way | the choreography was already per kind (`SOReload.cpp`); every kind now has its own shows |
| 1: large and near at the hip | not yet: the framing of 2026-11-23 holds (`Data/stances.json`) |
| 5: a draw of its own | not yet (the inspect exists, mid-pass) |
| 6: firing felt | kick, view climb, flash, cases exist; not yet judged against the reference |
| 7: on the sights | holds (`ShatteredOrbit.Hold.SteadyInTheEyes`) |
