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

## What the owner said of our first try

On the first pictures (2026-11-27, with red marks on a pistol's and a pump shotgun's reload seen from beside): "the
player hands/guns need to be fully visible at all times, this means the entire gun and not 20% of it. have this as a
hard rule, the players hands can't bend in a way that is not posible for a real human, learn it once and apply it to
all guns and done"; "from your own images these hand positions are not possible for a human, humans have bones and
can't bend their hands/arms in such manner so mark where they are in the body and ensure these rules are always
followed at all times for everything"; and: "you have all the referecne images you can ask for from the video i send,
just compare where their arms are and how to fix yours".

What the comparison showed (a rifle's, a pistol's, two shotguns' and a sniper rifle's reload, stepped through): their
firing fist stays at the FOOT of the picture, 85 to 95 % down and 58 to 70 % across, the forearm behind it coming from
the lower right corner; the gun is turned UP about that fist (a rifle 30 to 45 degrees, a shotgun and a pistol 60 to
90) and rolled, so it stands up into the middle of the picture; the support forearm rises from the bottom edge, 30 to
48 % across, steeply, to a hand 55 to 85 % down; both wrists are straight. Ours had lifted the work, and so the hands,
to the chin. Both hard rules are in `CLAUDE.md`; the arm as bones is `SOArmBones.h`.

## Where ours stands (keep this honest)

| | state |
|---|---|
| 2, 3: reloads shown, sprung, jolted, the view nudged | built 2026-11-27, and rebuilt the same day about a low firing hand: `FSOReloadShow`, `Data/reload_shows.json`, `USOViewmodelComponent::ReloadPose / Handle`, `ASOCharacter::OnWeaponHandled` |
| the hand's way from one job to the next | flown in the body's space, from where it let go to where the part WILL be, the gun turned a little ahead of it for a handle (`USOGunRigComponent::SetShowLead`, `FSOReloadPlayer::PeekHand`): the hand goes up the near flank and the gun is rolled into it; before, it chased the handle across the top of the gun with the forearm over the picture |
| the fresh magazine brought up from the foot of the picture | in the hand, its fingers closed on it, from the pouch on the chest (`USOGunRigComponent::SeatCarried`; a speedloader, a shell, a round and biomass the same); before, it hung in the air beside the gun while the hand was still at the pouch |
| not yet in them | the old magazine is let fall, not carried off; no empty-well pause of its own; a tactical (not empty) reload keeps the same show; the reference's finer finger work (a thumb on a release, a magazine indexed by the forefinger) |
| the arms in them | every joint inside a human's range, measured (`ShatteredOrbit.Body.HumanRange`) |
| 4: each kind its own way | the choreography was already per kind (`SOReload.cpp`); every kind has its own shows |
| 1: large and near at the hip | not yet: the framing of 2026-11-23 holds (`Data/stances.json`): the rifle shows 58-62 % of itself, the sniper 62-66, the SMG 51-56, the shotgun 50-54, the pistol 92-94, the heavy machine gun 35-39; a shouldered long gun's butt is behind the picture's corner, as in the reference, but theirs is drawn larger (a separate, narrower view for the gun, which one body and one camera have not) |
| 5: a draw of its own | not yet (the inspect exists, mid-pass) |
| 6: firing felt | kick, view climb, flash, cases exist; not yet judged against the reference |
| 7: on the sights | holds (`ShatteredOrbit.Hold.SteadyInTheEyes`) |
