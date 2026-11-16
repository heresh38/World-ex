// The AI gaps closed on 2026-11-13 (the owner's enemy AI brief): being shot at pins players and creatures, a
// suppressor keeps a hidden target's place under fire, a marksman aims in the open before it shoots, a hit knocks a
// body about, explosions are heard, and a squad does not all pick the same player. All single-machine.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Abilities/SOAbilitySet.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "SOAbilitySystemComponent.h"
#include "SOAbility_Bolt.h"
#include "SOAltered.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SODifficulty.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOFxSubsystem.h"
#include "SOGunRigComponent.h"
#include "SOLocomotionAnimInstance.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOWeaponData.h"
#include "SOOperation.h"
#include "SOProjectileSubsystem.h"
#include "SOSpecies.h"
#include "SOWeapon.h"

namespace
{
	void NoBrain(ASOEnemy* E)
	{
		if (AController* Brain = E ? E->GetController() : nullptr)
		{
			Brain->UnPossess();
			Brain->Destroy();
		}
	}

	/** A round from Shooter that flies along +X through Point. */
	void RoundPast(SOTest::FTestWorld& W, AActor* Shooter, const FVector& Point)
	{
		FSOProjectile Round;
		Round.Origin = Round.Position = Point - FVector(600.0f, 0.0f, 0.0f);
		Round.Velocity = FVector(60000.0f, 0.0f, 0.0f);
		Round.Gravity = 0.0f;
		Round.Damage = 10.0f;
		Round.Instigator = Shooter;
		W.World->GetSubsystem<USOProjectileSubsystem>()->Fire(Round);
		W.Run(0.1f);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSONearMissTest, "ShatteredOrbit.AI.NearMissesPin", SOTest::Flags)
bool FSONearMissTest::RunTest(const FString& Parameters)
{
	// Being shot at counts, not only being hit: a hostile round that passes close puts whoever it passed under fire.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* Remnant = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(0, 2500, 0), 0.0f, Options);
	ASOEnemy* Bulwark = USOSpeciesLibrary::Spawn(W.World, TEXT("bulwark"), FVector(0, -2500, 0), 0.0f, Options);
	if (!TestNotNull(TEXT("remnant"), Remnant) || !TestNotNull(TEXT("bulwark"), Bulwark))
	{
		return false;
	}
	NoBrain(Remnant);
	NoBrain(Bulwark);
	W.Run(0.5f);
	const FVector Chest = Player->GetActorLocation();

	// a round the player's own side fired, and one that passes well clear: nothing
	RoundPast(W, Player, Chest + FVector(0, 80, 0));
	TestFalse(TEXT("its own round passing close does not pin it"), Player->HasStatus(SOTags::Status_Suppressed));
	RoundPast(W, Remnant, Chest + FVector(0, USOProjectileSubsystem::NearMissRadius + 120.0f, 0));
	TestFalse(TEXT("a hostile round that passes well clear does not either"), Player->HasStatus(SOTags::Status_Suppressed));

	// a hostile round close by: under fire, the shield's wait starts over, the aim is less steady
	const float Life = Player->GetHealth() + Player->GetShield();
	const float Steady = Player->GetSpreadScale();
	USOCombatStatics::ApplyDamage(Remnant, Player, 20.0f, false);
	W.Run(Player->GetSOAbilitySystem()->ShieldRegenDelay - 0.6f);
	RoundPast(W, Remnant, Chest + FVector(0, 80, 0));
	TestTrue(TEXT("a hostile round passing close puts it under fire"), Player->HasStatus(SOTags::Status_Suppressed));
	TestEqual(TEXT("without touching it"), Player->GetHealth() + Player->GetShield(), Life - 20.0f, 0.01f);
	TestTrue(TEXT("its aim is less steady meanwhile"), Player->GetSpreadScale() > Steady * 1.2f);
	W.Run(1.2f);
	TestEqual(TEXT("and its shield, about to refill, waits again"), Player->GetHealth() + Player->GetShield(), Life - 20.0f, 0.01f);
	W.Run(1.0f);
	TestFalse(TEXT("it passes when the rounds stop"), Player->HasStatus(SOTags::Status_Suppressed));

	// creatures too; a Bulwark behind its plate is not pinned
	RoundPast(W, Player, Remnant->GetActorLocation() + FVector(0, 80, 0));
	TestTrue(TEXT("a creature is pinned by rounds passing close"), Remnant->HasStatus(SOTags::Status_Suppressed));
	RoundPast(W, Player, Bulwark->GetActorLocation() + FVector(0, 100, 60.0f));
	TestFalse(TEXT("a Bulwark is not"), Bulwark->HasStatus(SOTags::Status_Suppressed));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSuppressorTest, "ShatteredOrbit.AI.SuppressorKeepsItUnderFire", SOTest::Flags)
bool FSOSuppressorTest::RunTest(const FString& Parameters)
{
	// A suppressor (a variant's flag: data) keeps the place its target went to ground under fire; an ordinary one of
	// the same species holds its fire until it sees the target again.
	auto ShotsWhileHidden = [this](bool bSuppressor, bool& bSuppressing)
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
		W.AddBox(FVector(300, -260, 0), FVector(340, 260, 320)); // a wall to go to ground behind
		ASOCharacter* Player = W.SpawnCharacter(FVector(0, 900, 0));
		FSOSpeciesVariant Variant;
		Variant.Id = TEXT("test_gunner");
		Variant.Species = TEXT("remnant");
		Variant.bSuppressor = bSuppressor;
		Variant.Burst = 3.0f;
		FSOSpawnOptions Options;
		Options.bOnNav = false;
		Options.bHunter = true;
		Options.Variant = &Variant;
		ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(2200, 0, 0), 180.0f, Options);
		if (!E)
		{
			return -1;
		}
		auto Mend = [&]() { Player->Heal(100.0f); };
		W.Run(4.0f, Mend); // in the open: it sees the player and fights
		const bool bFought = E->GetShotsFired() > 0;
		Player->SetActorLocation(FVector(0, 0, 93));
		Player->GetCharacterMovement()->Velocity = FVector::ZeroVector;
		W.Run(1.2f, Mend); // (rounds in the air land, the brain notices the target is gone)
		const int32 Before = E->GetShotsFired();
		bSuppressing = false;
		W.Run(4.0f, [&]() { Mend(); bSuppressing |= E->IsSuppressing(); });
		return bFought ? E->GetShotsFired() - Before : -1;
	};
	bool bSuppressing = false, bPlainSuppressing = false;
	const int32 Suppressor = ShotsWhileHidden(true, bSuppressing);
	const int32 Plain = ShotsWhileHidden(false, bPlainSuppressing);
	AddInfo(FString::Printf(TEXT("shots at a target gone to ground, in 4 s: the suppressor %d, an ordinary one %d"), Suppressor, Plain));
	TestTrue(TEXT("both fought while the player was in the open"), Suppressor >= 0 && Plain >= 0);
	TestTrue(TEXT("the suppressor keeps the place under fire"), bSuppressing && Suppressor >= 8);
	TestTrue(TEXT("an ordinary one holds its fire at what it cannot see"), !bPlainSuppressing && Plain <= 2);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOMarksmanTest, "ShatteredOrbit.AI.MarksmanAimsThenShoots", SOTest::Flags)
bool FSOMarksmanTest::RunTest(const FString& Parameters)
{
	// The marksman's shot: a line of light for the whole aim, nothing until it ends, a hard hit on whoever stood
	// still, a miss on whoever kept moving; not used up close.
	USOAbilitySet* Kit = USOAbilitySet::Load(TEXT("marksman"));
	const FSOAbilityGrant* Shot = Kit ? Kit->Find(ESOAbilitySlot::Class) : nullptr;
	if (!TestNotNull(TEXT("the marksman's kit (SO_IMPORT_ONLY=kits)"), Shot))
	{
		return false;
	}
	TestTrue(TEXT("the aim is a warning one can read: 0.9 to 2.2 s"), Shot->WindUp >= 0.9f && Shot->WindUp <= 2.2f);
	SOTest::FTestWorld W;
	W.AddBox(FVector(-8000, -8000, -100), FVector(8000, 8000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpeciesVariant Variant;
	Variant.Id = TEXT("test_marksman");
	Variant.Species = TEXT("veilborn");
	Variant.Kit = TEXT("marksman");
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	Options.Variant = &Variant;
	ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("veilborn"), FVector(3000, 0, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("marksman"), E))
	{
		return false;
	}
	NoBrain(E);
	W.Run(0.5f);
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	const USOGameplayAbility* Rule = Shot->Ability.GetDefaultObject();
	TestTrue(TEXT("it would take the shot at range"), Rule->WantsUse(E, Player, *Shot, true));
	ASOCharacter* Close = W.SpawnCharacter(E->GetActorLocation() + FVector(-Shot->Radius * 0.5f, 400.0f, -90.0f));
	TestFalse(TEXT("but not at one who has got close to it"), Rule->WantsUse(E, Close, *Shot, true));
	Close->Destroy();

	// stands still: hit
	float Life = Player->GetHealth() + Player->GetShield();
	E->SetAbilityTarget(Player);
	TestTrue(TEXT("it takes aim"), E->ActivateSlot(ESOAbilitySlot::Class));
	TestEqual(TEXT("its line of sight is drawn"), Fx->GetNumAimLines(), 1);
	W.Run(Shot->WindUp - 0.15f);
	TestEqual(TEXT("still drawn near the end"), Fx->GetNumAimLines(), 1);
	TestEqual(TEXT("nothing lands during the aim"), Player->GetHealth() + Player->GetShield(), Life);
	W.Run(0.5f);
	TestEqual(TEXT("then the shot: the kit's damage on one who stood still"), Player->GetHealth() + Player->GetShield(), Life - Shot->Damage, 0.5f);
	TestEqual(TEXT("and the line is gone"), Fx->GetNumAimLines(), 0);

	// keeps moving across the line: missed
	W.Run(Shot->Cooldown + 0.5f, [&]() { Player->Heal(100.0f); });
	W.Run(8.0f); // (shield back)
	Life = Player->GetHealth() + Player->GetShield();
	TestTrue(TEXT("it takes aim again"), E->ActivateSlot(ESOAbilitySlot::Class));
	W.Run(Shot->WindUp + 0.5f, [&]() { Player->AddMovementInput(FVector(0, 1, 0), 1.0f); });
	TestTrue(FString::Printf(TEXT("the player ran %.0f cm across it"), FMath::Abs(Player->GetActorLocation().Y)), FMath::Abs(Player->GetActorLocation().Y) > 300.0f);
	TestEqual(TEXT("and the shot went where they had been"), Player->GetHealth() + Player->GetShield(), Life);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHitReactTest, "ShatteredOrbit.AI.HitsKnockTheBody", SOTest::Flags)
bool FSOHitReactTest::RunTest(const FString& Parameters)
{
	// A hit shows on the body: the trunk is knocked away from where it came from and comes back; a heavy body
	// barely moves; reeling is a pose, not a creature standing as if nothing had happened.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-3000, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* Remnant = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(0, 0, 0), 180.0f, Options);   // facing the player
	ASOEnemy* Bulwark = USOSpeciesLibrary::Spawn(W.World, TEXT("bulwark"), FVector(0, 1500, 0), 0.0f, Options); // its back to the player
	if (!TestNotNull(TEXT("remnant"), Remnant) || !TestNotNull(TEXT("bulwark"), Bulwark))
	{
		return false;
	}
	// (nothing is drawn here, and a creature nobody sees does not animate)
	Remnant->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Bulwark->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	W.Run(0.3f);
	USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(Remnant->GetMesh()->GetAnimInstance());
	USOLocomotionAnimInstance* Heavy = Cast<USOLocomotionAnimInstance>(Bulwark->GetMesh()->GetAnimInstance());
	if (!TestNotNull(TEXT("anim"), Anim) || !TestNotNull(TEXT("heavy anim"), Heavy))
	{
		return false;
	}
	Remnant->SetAlert(true);
	Bulwark->SetAlert(true);
	TestEqual(TEXT("unhurt, the trunk is where the clip puts it"), Anim->FlinchPitch, 0.0f);
	USOCombatStatics::ApplyDamage(Player, Remnant, Remnant->GetMaxHealth() * 0.15f, false); // (not enough to make it stumble)
	const float Knock = Anim->FlinchPitch;
	TestTrue(FString::Printf(TEXT("hit from the front, it is knocked back (%.1f degrees)"), Knock), Knock > 6.0f);
	USOCombatStatics::ApplyDamage(Player, Remnant, 2.0f, false);
	TestEqual(TEXT("a scratch straight after does not knock it again"), Anim->FlinchPitch, Knock, 0.01f);
	W.Run(1.2f, [&]() { Player->Heal(100.0f); });
	TestTrue(TEXT("and it comes back"), FMath::Abs(Anim->FlinchPitch) < 0.5f);
	USOCombatStatics::ApplyDamage(Player, Bulwark, Bulwark->GetMaxHealth() * 0.2f, false);
	TestTrue(FString::Printf(TEXT("a heavy body is knocked far less by the same share (%.1f against %.1f)"), FMath::Abs(Heavy->FlinchPitch) + FMath::Abs(Heavy->FlinchRoll), Knock),
		FMath::Abs(Heavy->FlinchPitch) + FMath::Abs(Heavy->FlinchRoll) < Knock * 0.6f && FMath::Abs(Heavy->FlinchPitch) + FMath::Abs(Heavy->FlinchRoll) > 0.5f);

	TestTrue(TEXT("staggered"), USOCombatStatics::ApplyStatus(Player, Remnant, SOTags::Status_Stagger, 2.0f));
	W.Run(0.6f, [&]() { Player->Heal(100.0f); });
	TestTrue(TEXT("reeling is a pose the body holds"), Anim->bReeling && Anim->ReelBlend > 0.7f);
	W.Run(2.2f, [&]() { Player->Heal(100.0f); });
	TestTrue(TEXT("and lets go of when it is over"), !Anim->bReeling && Anim->ReelBlend < 0.2f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSpreadAndHearTest, "ShatteredOrbit.AI.TargetsSpreadAndBlastsAreHeard", SOTest::Flags)
bool FSOSpreadAndHearTest::RunTest(const FString& Parameters)
{
	SOTest::FTestWorld W;
	W.AddBox(FVector(-8000, -8000, -100), FVector(8000, 8000, 0));
	// a blast is heard by one that saw nothing
	{
		ASOCharacter* Player = W.SpawnCharacter(FVector(-5000, -5000, 0));
		FSOSpawnOptions Options;
		Options.bOnNav = false;
		ASOEnemy* Sentry = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(5000, 5000, 0), 45.0f, Options); // looking away
		const ASOEnemyAIController* Brain = Sentry ? Cast<ASOEnemyAIController>(Sentry->GetController()) : nullptr;
		if (TestNotNull(TEXT("sentry"), Brain))
		{
			W.Run(1.0f);
			TestTrue(TEXT("a sentry far from the player knows of nothing"), Brain->GetAwareness() < 0.05f && !Brain->IsInCombat());
			W.World->GetSubsystem<USOProjectileSubsystem>()->ApplySplash(Player, Sentry->GetActorLocation() + FVector(-2500, -2500, 50), 400.0f, 10.0f);
			W.Run(0.5f);
			TestTrue(TEXT("a blast 35 m off is heard"), Brain->GetState() == ESOEnemyState::Suspicious || Brain->IsInCombat() || Brain->GetAwareness() > 0.2f);
			Sentry->Destroy();
		}
		Player->Destroy();
	}
	// four of a squad and two players: they do not all take the same one
	ASOCharacter* A = W.SpawnCharacter(FVector(0, -150, 0));
	ASOCharacter* B = W.SpawnCharacter(FVector(0, 150, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	Options.bHunter = true;
	TArray<ASOEnemyAIController*> Brains;
	for (int32 i = 0; i < 4; ++i)
	{
		// (all a little nearer to A: by distance alone every one of them would pick A)
		Options.Index = i;
		if (ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(1700.0f, -700.0f - i * 60.0f, 0), 180.0f, Options))
		{
			Brains.Add(Cast<ASOEnemyAIController>(E->GetController()));
		}
	}
	if (!TestEqual(TEXT("four of a squad"), Brains.Num(), 4))
	{
		return false;
	}
	int32 OnA = 0, OnB = 0;
	W.Run(8.0f, [&]() { A->Heal(100.0f); B->Heal(100.0f); });
	for (const ASOEnemyAIController* Brain : Brains)
	{
		OnA += Brain && Brain->GetTarget() == A;
		OnB += Brain && Brain->GetTarget() == B;
	}
	AddInfo(FString::Printf(TEXT("after 8 s: %d on the nearer player, %d on the other"), OnA, OnB));
	TestTrue(TEXT("the squad is on both players, not all on the nearer one"), OnA >= 1 && OnB >= 1);
	return true;
}

#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSpawnUnseenTest, "ShatteredOrbit.Operation.ReinforcementsArriveUnseen", SOTest::Flags)
bool FSOSpawnUnseenTest::RunTest(const FString& Parameters)
{
	// A reinforcement does not appear in front of a player's eyes: of its group's points it takes one nobody has in
	// view (behind them, or behind a wall); a garrison stands where the plan says.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-8000, -8000, -100), FVector(8000, 8000, 0));
	W.AddBox(FVector(1500, 500, 0), FVector(1560, 2100, 500));              // a wall, across the way to the third point
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));              // looks along +X
	ASOOperation* Op = W.World->SpawnActor<ASOOperation>();
	if (!TestNotNull(TEXT("operation"), Op) || !TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	W.Run(0.3f);
	const FVector InFront(2000, 0, 0), Behind(-2000, 0, 0), BehindWall(2600, 1500, 0), FarOff(12000, 0, 0);
	TestTrue(TEXT("open ground in front of the player is in view"), Op->SeenByAPlayer(InFront));
	TestFalse(TEXT("behind them is not"), Op->SeenByAPlayer(Behind));
	TestFalse(TEXT("nor is a place behind a wall"), Op->SeenByAPlayer(BehindWall));
	TestFalse(TEXT("nor one too far off to matter"), Op->SeenByAPlayer(FarOff));

	FSOSpawnGroup Group;
	Group.Points = { InFront, FVector(2000, 300, 0), BehindWall, Behind };
	TestEqual(TEXT("a garrison stands where the plan says"), Op->SpawnPointFor(Group, 0, false), 0);
	TestEqual(TEXT("the first reinforcement takes the first point out of view"), Op->SpawnPointFor(Group, 0, true), 2);
	TestEqual(TEXT("one whose own point is out of view keeps it"), Op->SpawnPointFor(Group, 3, true), 3);
	FSOSpawnGroup Open;
	Open.Points = { InFront, FVector(2000, 300, 0) };
	TestEqual(TEXT("seen everywhere, it takes the one it would have had"), Op->SpawnPointFor(Open, 1, true), 1);
	// a second player who looks the other way sees what the first does not
	ASOCharacter* Other = W.SpawnCharacter(FVector(0, 600, 0));
	Other->SetActorRotation(FRotator(0, 180, 0));
	W.Run(0.2f);
	TestTrue(TEXT("what one player has behind them another may be looking at"), Op->SeenByAPlayer(Behind));
	TestEqual(TEXT("and then only the wall hides one"), Op->SpawnPointFor(Group, 0, true), 2);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOPackScattersTest, "ShatteredOrbit.AI.ThePackBreaksOffAndTakesAnOpening", SOTest::Flags)
bool FSOPackScattersTest::RunTest(const FString& Parameters)
{
	auto Hunters = [](SOTest::FTestWorld& W, const TArray<FVector>& At)
	{
		FSOSpawnOptions Options;
		Options.bHunter = true;
		Options.bOnNav = false;
		TArray<ASOEnemy*> Pack;
		for (const FVector& Feet : At)
		{
			Pack.Add(USOSpeciesLibrary::Spawn(W.World, TEXT("stalker_feral"), Feet, 180.0f, Options));
		}
		return Pack;
	};
	// Two of a pack cut down within a moment: the rest break off (run out and away), then come back.
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-9000, -9000, -100), FVector(9000, 9000, 0));
		ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
		TArray<ASOEnemy*> Pack = Hunters(W, { FVector(1300, -500, 0), FVector(1300, 500, 0), FVector(1500, -150, 0), FVector(1500, 150, 0) });
		if (!TestTrue(TEXT("pack spawned"), Pack.Num() == 4 && !Pack.Contains(nullptr)))
		{
			return false;
		}
		W.Run(1.2f, [&]() { Player->Heal(100.0f); }); // (they are in the fight)
		USOCombatStatics::ApplyDamage(Player, Pack[2], 100000.0f, false);
		W.Run(0.4f, [&]() { Player->Heal(100.0f); });
		USOCombatStatics::ApplyDamage(Player, Pack[3], 100000.0f, false);
		TestTrue(TEXT("two of the pack are dead"), Pack[2]->IsDead() && Pack[3]->IsDead());
		const float Before[2] = { static_cast<float>(FVector::Dist2D(Pack[0]->GetActorLocation(), Player->GetActorLocation())),
			static_cast<float>(FVector::Dist2D(Pack[1]->GetActorLocation(), Player->GetActorLocation())) };
		W.Run(1.8f, [&]() { Player->Heal(100.0f); });
		for (int32 i = 0; i < 2; ++i)
		{
			const float Then = static_cast<float>(FVector::Dist2D(Pack[i]->GetActorLocation(), Player->GetActorLocation()));
			TestTrue(FString::Printf(TEXT("survivor %d broke off (%.0f cm from the player, then %.0f)"), i, Before[i], Then), Then > Before[i] + 150.0f); // (one that was in a lunge when the second fell starts later)
		}
		float Nearest = 100000.0f;
		const float Full = Player->GetHealth() + Player->GetShield();
		bool bStruck = false;
		W.Run(14.0f, [&]()
		{
			for (int32 i = 0; i < 2; ++i)
			{
				Nearest = FMath::Min(Nearest, static_cast<float>(FVector::Dist2D(Pack[i]->GetActorLocation(), Player->GetActorLocation())));
			}
			bStruck |= Player->GetHealth() + Player->GetShield() < Full - 0.5f;
			Player->Heal(100.0f);
		});
		TestTrue(FString::Printf(TEXT("and they came back (nearest %.0f cm, struck %d)"), Nearest, bStruck ? 1 : 0), Nearest < 400.0f || bStruck);
	}
	// A pack that is still waiting for the rest of it goes in when its target starts to load its gun.
	for (const bool bReload : { false, true })
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-9000, -9000, -100), FVector(9000, 9000, 0));
		ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
		// two on the ring already, two a long way off (the pack waits for them)
		TArray<ASOEnemy*> Pack = Hunters(W, { FVector(1000, -350, 0), FVector(1000, 350, 0), FVector(4700, -200, 0), FVector(4700, 200, 0) });
		if (!TestTrue(TEXT("pack spawned"), Pack.Num() == 4 && !Pack.Contains(nullptr)))
		{
			return false;
		}
		W.Run(1.0f);
		ASOWeapon* Gun = Player->GetWeapon();
		if (!TestNotNull(TEXT("the player's gun"), Gun))
		{
			return false;
		}
		if (bReload)
		{
			Gun->StartFire();
			W.Run(0.25f);
			Gun->StopFire();
			Gun->StartReload();
			TestTrue(TEXT("the player is loading"), Gun->IsReloading());
		}
		else
		{
			W.Run(0.25f);
		}
		float Nearest = 100000.0f;
		W.Run(1.6f, [&]()
		{
			for (int32 i = 0; i < 2; ++i)
			{
				Nearest = FMath::Min(Nearest, static_cast<float>(FVector::Dist2D(Pack[i]->GetActorLocation(), Player->GetActorLocation())));
			}
		});
		if (bReload)
		{
			TestTrue(FString::Printf(TEXT("the target loading its gun, the two in place went in (nearest %.0f cm)"), Nearest), Nearest < 650.0f);
		}
		else
		{
			TestTrue(FString::Printf(TEXT("the target ready, the two in place held off (nearest %.0f cm)"), Nearest), Nearest > 750.0f);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSpeciesNumbersTest, "ShatteredOrbit.Species.NumbersAreData", SOTest::Flags)
bool FSOSpeciesNumbersTest::RunTest(const FString& Parameters)
{
	// A species' numbers come from the table (Data/species.json): every species has an entry, a creature made any way
	// has the table's numbers, and a number that is changed changes the creature.
	const USOSpeciesTable& Table = USOSpeciesTable::Get();
	if (Table.Species.Num() == 0)
	{
		AddWarning(TEXT("no species table imported (SO_IMPORT_ONLY=species): numbers as data were not checked"));
		return true;
	}
	for (const FName Id : USOSpeciesLibrary::GetSpecies())
	{
		const TMap<FName, float>* Numbers = Table.Find(Id);
		TestTrue(FString::Printf(TEXT("'%s' has its numbers in the table, health among them"), *Id.ToString()), Numbers && Numbers->Contains(TEXT("health")));
		// what the table says is what the class knows how to take (no stale or misspelt key)
		const TMap<FName, float> Class = USOSpeciesLibrary::GetClassNumbers(Id);
		for (const TPair<FName, float>& Pair : Numbers ? *Numbers : TMap<FName, float>())
		{
			TestTrue(FString::Printf(TEXT("'%s': '%s' is a number the species has"), *Id.ToString(), *Pair.Key.ToString()), Class.Contains(Pair.Key));
		}
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(0, 0, 0), 0.0f, Options);
	const TMap<FName, float>* Numbers = Table.Find(TEXT("remnant"));
	if (!TestNotNull(TEXT("remnant"), E) || !TestNotNull(TEXT("its numbers"), Numbers))
	{
		return false;
	}
	W.Run(0.2f);
	TestEqual(TEXT("its health is the table's"), E->GetMaxHealth(), (*Numbers)[TEXT("health")], 0.01f);
	TestEqual(TEXT("its run is the table's"), E->RunSpeed, (*Numbers)[TEXT("runSpeed")], 0.01f);
	TestEqual(TEXT("its sight is the table's"), E->SightRange, (*Numbers)[TEXT("sightRange")], 0.01f);
	const ASOEnemyAIController* Brain = Cast<ASOEnemyAIController>(E->GetController());
	if (TestNotNull(TEXT("its brain"), Brain) && TestTrue(TEXT("the table has its brain's senses"), Numbers->Contains(TEXT("viewHalfAngle"))))
	{
		TestEqual(TEXT("its brain's view is the table's"), Brain->ViewHalfAngle, (*Numbers)[TEXT("viewHalfAngle")], 0.01f);
		TestEqual(TEXT("and how long it searches"), Brain->SearchTime, (*Numbers)[TEXT("searchTime")], 0.01f);
	}

	TMap<FName, float> Mine;
	Mine.Add(TEXT("health"), 55.0f);
	Mine.Add(TEXT("runSpeed"), 777.0f);
	Mine.Add(TEXT("usesCover"), 0.0f);
	Mine.Add(TEXT("burstTimeMax"), 3.0f);
	Mine.Add(TEXT("noSuchNumber"), 1.0f);
	TestEqual(TEXT("four of five are numbers it has"), E->ApplyNumbers(Mine), 4);
	TestEqual(TEXT("health set, on a living creature too"), E->GetMaxHealth(), 55.0f, 0.01f);
	TestEqual(TEXT("a speed set"), E->RunSpeed, 777.0f);
	TestFalse(TEXT("a switch set"), E->bUsesCover);
	TestEqual(TEXT("one end of a range set"), static_cast<float>(E->BurstTime.Y), 3.0f);

	// a level's variant scales what the table gave
	FSOSpeciesVariant Variant;
	Variant.Id = TEXT("test_tough");
	Variant.Species = TEXT("remnant");
	Variant.Health = 2.0f;
	Options.Variant = &Variant;
	ASOEnemy* Tough = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(600, 0, 0), 0.0f, Options);
	W.Run(0.2f);
	if (TestNotNull(TEXT("variant"), Tough))
	{
		TestEqual(TEXT("a variant scales the table's health"), Tough->GetMaxHealth(), (*Numbers)[TEXT("health")] * 2.0f * USODifficultySubsystem::Get(W.World).Health, 0.01f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOFireBreaksAChargeTest, "ShatteredOrbit.AI.FireBreaksACharge", SOTest::Flags)
bool FSOFireBreaksAChargeTest::RunTest(const FString& Parameters)
{
	// A creature that is shot as it comes does not arrive as if nothing had happened: every hit checks it, enough of
	// them make it stumble (staggered, knocked a step back), and it covers far less ground than one left alone.
	auto Charge = [this](bool bShoot, float& OutCovered, int32& OutStumbles, bool& bOutChecked, bool& bOutStaggered, float& OutBack)
	{
		SOTest::FTestWorld W;
		W.AddBox(FVector(-9000, -9000, -100), FVector(9000, 9000, 0));
		ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
		FSOSpawnOptions Options;
		Options.bHunter = true;
		Options.bOnNav = false;
		ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("stalker_feral"), FVector(3000, 0, 0), 180.0f, Options);
		if (!TestNotNull(TEXT("stalker"), E))
		{
			return;
		}
		E->SetAlert(true);
		W.Run(0.8f);                                             // (it is on its way)
		const float From = static_cast<float>(FVector::Dist2D(E->GetActorLocation(), Player->GetActorLocation()));
		float Clock = 0.0f, NextShot = 0.0f;
		OutBack = 0.0f;
		W.Run(1.6f, [&]()
		{
			Clock += SOTest::Dt;
			if (bShoot && Clock >= NextShot && !E->IsDead())
			{
				NextShot = Clock + 0.12f;
				E->Heal(1000.0f);                                // (kept alive: this is about its legs, not its life)
				const FVector Dir = (E->GetActorLocation() - Player->GetActorLocation()).GetSafeNormal();
				const FSOHitScope Where(TEXT("chest"), E->GetActorLocation(), Dir, false);
				USOCombatStatics::ApplyDamage(Player, E, E->GetMaxHealth() * 0.06f, false);
				bOutChecked |= E->IsChecked();
			}
			if (E->HasStatus(SOTags::Status_Stagger))
			{
				bOutStaggered = true;
				// (toward the player is -X here: a positive X speed is away from them)
				OutBack = FMath::Max(OutBack, static_cast<float>(E->GetVelocity().X));
			}
		});
		OutCovered = From - static_cast<float>(FVector::Dist2D(E->GetActorLocation(), Player->GetActorLocation()));
		OutStumbles = E->GetStumbles();
	};
	float Free = 0.0f, Shot = 0.0f, Back = 0.0f, NoBack = 0.0f;
	int32 FreeStumbles = 0, ShotStumbles = 0;
	bool bFreeChecked = false, bChecked = false, bFreeStaggered = false, bStaggered = false;
	Charge(false, Free, FreeStumbles, bFreeChecked, bFreeStaggered, NoBack);
	Charge(true, Shot, ShotStumbles, bChecked, bStaggered, Back);
	TestTrue(FString::Printf(TEXT("left alone it covers ground (%.0f cm in 1.6 s) and never stumbles"), Free), Free > 500.0f && FreeStumbles == 0 && !bFreeStaggered);
	TestTrue(TEXT("a hit checks it"), bChecked);
	TestTrue(FString::Printf(TEXT("enough hits make it stumble (%d times in 1.6 s)"), ShotStumbles), bStaggered && ShotStumbles >= 1);
	TestTrue(FString::Printf(TEXT("and no more than its rest allows (%d)"), ShotStumbles), ShotStumbles <= 1);
	TestTrue(FString::Printf(TEXT("stumbling, it is knocked back (%.0f cm/s away)"), Back), Back > 40.0f);
	TestTrue(FString::Printf(TEXT("shot, it covers far less ground (%.0f cm against %.0f)"), Shot, Free), Shot < Free * 0.62f);

	SOTest::FTestWorld W;
	W.AddBox(FVector(-9000, -9000, -100), FVector(9000, 9000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	auto Still = [&](FName Species, const FVector& Feet) -> ASOEnemy*
	{
		ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, Species, Feet, 180.0f, Options);
		if (E)
		{
			if (AController* Brain = E->GetController())
			{
				Brain->UnPossess();
				Brain->Destroy();
			}
			E->SetAlert(true);
		}
		return E;
	};
	ASOEnemy* Body = Still(TEXT("stalker_feral"), FVector(2000, -600, 0));
	ASOEnemy* Head = Still(TEXT("stalker_feral"), FVector(2000, 600, 0));
	ASOEnemy* Giant = Still(TEXT("colossus"), FVector(2600, 2400, 0));
	if (!TestNotNull(TEXT("body"), Body) || !TestNotNull(TEXT("head"), Head) || !TestNotNull(TEXT("giant"), Giant))
	{
		return false;
	}
	W.Run(0.3f);
	// the same damage, to the trunk and to the head: a precise hit unsteadies twice as much
	{
		const FSOHitScope Where(TEXT("chest"), Body->GetActorLocation(), FVector(1, 0, 0), false);
		USOCombatStatics::ApplyDamage(Player, Body, Body->GetMaxHealth() * 0.13f, false);
	}
	{
		const FSOHitScope Where(TEXT("head"), Head->GetActorLocation(), FVector(1, 0, 0), true);
		USOCombatStatics::ApplyDamage(Player, Head, Head->GetMaxHealth() * 0.13f, true);
	}
	TestTrue(TEXT("a hit to the trunk for an eighth of its health does not make it stumble"), Body->GetStumbles() == 0 && !Body->HasStatus(SOTags::Status_Stagger));
	TestTrue(TEXT("the same to the head does"), Head->GetStumbles() == 1 && Head->HasStatus(SOTags::Status_Stagger));
	// it steadies again if it is left alone
	const float Unsteady = Body->GetPoiseDamage();
	W.Run(0.8f);
	TestTrue(FString::Printf(TEXT("left alone it steadies (%.3f, then %.3f)"), Unsteady, Body->GetPoiseDamage()), Unsteady > 0.1f && Body->GetPoiseDamage() < Unsteady - 0.05f);
	// a boss is not checked or stumbled by fire: it reels by its own table
	USOCombatStatics::ApplyDamage(Player, Giant, Giant->GetMaxHealth() * 0.3f, false);
	TestTrue(TEXT("a boss is not stumbled or checked by fire"), Giant->GetStumbles() == 0 && !Giant->IsChecked() && !Giant->HasStatus(SOTags::Status_Stagger));

	// a blow that is being wound up is lost when the creature stumbles
	for (const bool bShoot : { false, true })
	{
		SOTest::FTestWorld W2;
		W2.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
		ASOCharacter* Victim = W2.SpawnCharacter(FVector(0, 0, 0));
		ASOEnemy* E = USOSpeciesLibrary::Spawn(W2.World, TEXT("stalker_feral"), FVector(170, 0, 0), 180.0f, Options);
		if (!TestNotNull(TEXT("attacker"), E))
		{
			return false;
		}
		if (AController* Brain = E->GetController())
		{
			Brain->UnPossess();
			Brain->Destroy();
		}
		E->SetAlert(true);
		W2.Run(0.3f);
		const float Life = Victim->GetHealth() + Victim->GetShield();
		TestTrue(TEXT("it starts its blow"), E->TryAttack(Victim));
		W2.Run(0.1f);
		if (bShoot)
		{
			USOCombatStatics::ApplyDamage(Victim, E, E->GetMaxHealth() * 0.3f, false);
			TestTrue(TEXT("hit hard in its wind-up, it stumbles"), E->HasStatus(SOTags::Status_Stagger));
		}
		W2.Run(0.8f);
		if (bShoot)
		{
			TestEqual(TEXT("and the blow never lands"), Victim->GetHealth() + Victim->GetShield(), Life);
		}
		else
		{
			TestTrue(TEXT("left alone, its blow lands"), Victim->GetHealth() + Victim->GetShield() < Life - 1.0f);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOHitShowsWhereTest, "ShatteredOrbit.AI.AHitShowsWhereItLands", SOTest::Flags)
bool FSOHitShowsWhereTest::RunTest(const FString& Parameters)
{
	// The body shows a hit where it landed: the head is thrown back, a shoulder driven back turns the chest (one way
	// for the left, the other for the right), a leg gives and the hips drop, the trunk is knocked away.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-2000, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(0, 0, 0), 180.0f, Options); // facing the player
	if (!TestNotNull(TEXT("creature"), E))
	{
		return false;
	}
	if (AController* Brain = E->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	E->SetAlert(true);
	E->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	W.Run(0.3f);
	USOLocomotionAnimInstance* Anim = Cast<USOLocomotionAnimInstance>(E->GetMesh()->GetAnimInstance());
	if (!TestNotNull(TEXT("anim"), Anim))
	{
		return false;
	}
	// (from the front: the blow travels from the player to it; small hits, so it never stumbles here)
	const FVector Along = (E->GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D();
	auto Hit = [&](const TCHAR* Bone)
	{
		W.Run(1.4f); // (the last one is over)
		const FSOHitScope Where(Bone, E->GetActorLocation(), Along, false);
		USOCombatStatics::ApplyDamage(Player, E, E->GetMaxHealth() * 0.03f, false);
	};
	Hit(TEXT("head"));
	TestTrue(FString::Printf(TEXT("a hit to the head from the front throws it back (%.1f degrees), the trunk far less (%.1f)"), Anim->HeadKickPitch, Anim->FlinchPitch),
		Anim->HeadKickPitch > 4.0f && FMath::Abs(Anim->FlinchPitch) < FMath::Abs(Anim->HeadKickPitch) * 0.5f);
	Hit(TEXT("upperarm_L"));
	const float Left = Anim->FlinchTwist;
	Hit(TEXT("upperarm_R"));
	const float Right = Anim->FlinchTwist;
	TestTrue(FString::Printf(TEXT("a shoulder driven back turns the chest: one way for the left (%.1f), the other for the right (%.1f)"), Left, Right),
		FMath::Abs(Left) > 2.0f && FMath::Abs(Right) > 2.0f && Left * Right < 0.0f);
	TestTrue(TEXT("and the head is left alone by it"), FMath::Abs(Anim->HeadKickPitch) < 0.5f);
	Hit(TEXT("shin_L"));
	TestTrue(FString::Printf(TEXT("a leg gives: the hips drop (%.1f cm)"), Anim->FlinchDip), Anim->FlinchDip > 1.5f && FMath::Abs(Anim->FlinchTwist) < 0.5f);
	TestTrue(TEXT("and a leg hit checks it for longer"), E->IsChecked());
	Hit(TEXT("chest"));
	TestTrue(FString::Printf(TEXT("the trunk is knocked the way the blow went (%.1f degrees back)"), Anim->FlinchPitch), Anim->FlinchPitch > 2.0f && Anim->FlinchDip < 0.5f);
	W.Run(1.5f);
	TestTrue(TEXT("and all of it comes back"), FMath::Abs(Anim->FlinchPitch) + FMath::Abs(Anim->FlinchTwist) + FMath::Abs(Anim->HeadKickPitch) + Anim->FlinchDip < 0.5f);

	// And it is on the body, not only in the numbers behind it: the bones themselves move.
	{
		auto Turned = [&](const TCHAR* Bone, const FQuat& Before)
		{
			return FMath::RadiansToDegrees(static_cast<float>(Before.AngularDistance(E->GetMesh()->GetBoneQuaternion(Bone, EBoneSpaces::ComponentSpace))));
		};
		auto Blow = [&](const TCHAR* Bone)
		{
			const FSOHitScope Where(Bone, E->GetActorLocation(), Along, false);
			USOCombatStatics::ApplyDamage(Player, E, E->GetMaxHealth() * 0.03f, false);
		};
		W.Run(1.5f);
		// (how much the clip alone moves these in the same time: the creature twitches by itself)
		FQuat Head = E->GetMesh()->GetBoneQuaternion(TEXT("head"), EBoneSpaces::ComponentSpace);
		FQuat Chest = E->GetMesh()->GetBoneQuaternion(TEXT("chest"), EBoneSpaces::ComponentSpace);
		float Hips = static_cast<float>(E->GetMesh()->GetBoneLocation(TEXT("hips"), EBoneSpaces::ComponentSpace).Z);
		W.Run(0.06f);
		const float HeadIdle = Turned(TEXT("head"), Head), ChestIdle = Turned(TEXT("chest"), Chest);
		const float HipsIdle = FMath::Abs(Hips - static_cast<float>(E->GetMesh()->GetBoneLocation(TEXT("hips"), EBoneSpaces::ComponentSpace).Z));

		Head = E->GetMesh()->GetBoneQuaternion(TEXT("head"), EBoneSpaces::ComponentSpace);
		Blow(TEXT("head"));
		W.Run(0.06f);
		const float HeadHit = Turned(TEXT("head"), Head);
		TestTrue(FString::Printf(TEXT("the head bone turns %.1f degrees in the moment after a hit to it (%.1f by itself)"), HeadHit, HeadIdle), HeadHit > HeadIdle + 6.0f);
		W.Run(1.5f);
		Chest = E->GetMesh()->GetBoneQuaternion(TEXT("chest"), EBoneSpaces::ComponentSpace);
		Blow(TEXT("chest"));
		W.Run(0.06f);
		const float ChestHit = Turned(TEXT("chest"), Chest);
		TestTrue(FString::Printf(TEXT("the chest bone turns %.1f degrees after a hit to the trunk (%.1f by itself)"), ChestHit, ChestIdle), ChestHit > ChestIdle + 4.0f);
		W.Run(1.5f);
		Hips = static_cast<float>(E->GetMesh()->GetBoneLocation(TEXT("hips"), EBoneSpaces::ComponentSpace).Z);
		Blow(TEXT("thigh_L"));
		W.Run(0.06f);
		const float HipsHit = Hips - static_cast<float>(E->GetMesh()->GetBoneLocation(TEXT("hips"), EBoneSpaces::ComponentSpace).Z);
		TestTrue(FString::Printf(TEXT("the hips drop %.1f cm after a hit to a leg (%.1f by themselves)"), HipsHit, HipsIdle), HipsHit > HipsIdle + 2.0f);
		W.Run(1.5f);

		// the same on a body with no gun in its hands (the gun-hold pass sets an armed one's neck and head afresh)
		ASOEnemy* Clawed = USOSpeciesLibrary::Spawn(W.World, TEXT("stalker_feral"), FVector(0, 900, 0), 180.0f, Options);
		if (TestNotNull(TEXT("clawed"), Clawed))
		{
			if (AController* Brain = Clawed->GetController())
			{
				Brain->UnPossess();
				Brain->Destroy();
			}
			Clawed->SetAlert(true);
			Clawed->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
			W.Run(0.5f);
			const FQuat Before = Clawed->GetMesh()->GetBoneQuaternion(TEXT("head"), EBoneSpaces::ComponentSpace);
			{
				const FSOHitScope Where(TEXT("head"), Clawed->GetActorLocation(), Along, false);
				USOCombatStatics::ApplyDamage(Player, Clawed, Clawed->GetMaxHealth() * 0.03f, false);
			}
			W.Run(0.06f);
			const float Thrown = FMath::RadiansToDegrees(static_cast<float>(Before.AngularDistance(Clawed->GetMesh()->GetBoneQuaternion(TEXT("head"), EBoneSpaces::ComponentSpace))));
			TestTrue(FString::Printf(TEXT("a clawed creature's head bone turns %.1f degrees after a hit to it"), Thrown), Thrown > 8.0f);
		}
	}

	// a real round finds the part by itself: one at the head is a head hit
	const FVector HeadAt = E->GetMesh()->GetBoneLocation(TEXT("head"));
	FSOProjectile Round;
	Round.Origin = Round.Position = HeadAt - Along * 800.0f;
	Round.Velocity = Along * 60000.0f;
	Round.Gravity = 0.0f;
	Round.Damage = 20.0f;
	Round.Instigator = Player;
	W.World->GetSubsystem<USOProjectileSubsystem>()->Fire(Round);
	W.Run(0.1f);
	TestTrue(FString::Printf(TEXT("a round at the head throws the head back (%.1f degrees)"), Anim->HeadKickPitch), Anim->HeadKickPitch > 3.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOPlateGivesWayTest, "ShatteredOrbit.AI.ThePlateGivesWay", SOTest::Flags)
bool FSOPlateGivesWayTest::RunTest(const FString& Parameters)
{
	// Fire on a Bulwark's plate is not wasted: the plate turns most of each blow (and shows it: sparks, not blood), but
	// what it turns still shakes the creature; enough of it and the Bulwark reels, and while it reels the plate is down.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-1500, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOBulwark* E = Cast<ASOBulwark>(USOSpeciesLibrary::Spawn(W.World, TEXT("bulwark"), FVector(0, 0, 0), 180.0f, Options)); // facing the player
	if (!TestNotNull(TEXT("bulwark"), E))
	{
		return false;
	}
	if (AController* Brain = E->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	E->SetAlert(true);
	W.Run(0.3f);
	const float Blow = E->GetMaxHealth() * 0.1f;
	const FVector Behind = E->GetActorLocation() - E->GetActorForwardVector() * 500.0f;
	TestTrue(TEXT("from the front the plate turns a blow, from behind it does not"), E->TurnsBlow(Player->GetActorLocation()) && !E->TurnsBlow(Behind));
	const float First = USOCombatStatics::ApplyDamage(Player, E, Blow, false);
	TestEqual(TEXT("the plate lets its share through"), First, Blow * E->FrontDamageScale, 0.5f);
	TestTrue(FString::Printf(TEXT("and what it turned still shook it (unsteady %.3f, more than the %.3f that went in)"), E->GetPoiseDamage(), First / E->GetMaxHealth()),
		E->GetPoiseDamage() > First / E->GetMaxHealth() + 0.03f);
	int32 Blows = 1;
	while (!E->HasStatus(SOTags::Status_Stagger) && Blows < 12)
	{
		W.Run(0.15f);
		USOCombatStatics::ApplyDamage(Player, E, Blow, false);
		++Blows;
	}
	TestTrue(FString::Printf(TEXT("blows on the plate make it reel (after %d)"), Blows), E->HasStatus(SOTags::Status_Stagger) && Blows <= 6);
	TestFalse(TEXT("reeling, its plate is down"), E->TurnsBlow(Player->GetActorLocation()));
	const float Open = USOCombatStatics::ApplyDamage(Player, E, Blow, false);
	TestEqual(TEXT("and the same blow from the front goes in whole"), Open, Blow, 0.5f);
	W.Run(E->StumbleTime + 0.3f);
	TestTrue(TEXT("on its feet again, the plate is up"), !E->HasStatus(SOTags::Status_Stagger) && E->TurnsBlow(Player->GetActorLocation()));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBearerTest, "ShatteredOrbit.Altered.TheBearer", SOTest::Flags)
bool FSOBearerTest::RunTest(const FString& Parameters)
{
	// The gun carrier: a species of its own with a body of its own, the heavy gun carried low at the right hip in
	// BOTH hands (each hand's place on the gun within its arm's reach, carried and on a target), plates that turn
	// half a blow from the front and are down while it reels, and its numbers in the species table.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-1500, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOBearer* E = Cast<ASOBearer>(USOSpeciesLibrary::Spawn(W.World, TEXT("bearer"), FVector(0, 0, 0), 180.0f, Options)); // facing the player
	if (!TestNotNull(TEXT("the species 'bearer'"), E))
	{
		return false;
	}
	if (AController* Brain = E->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	E->SetAlert(true);
	E->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	W.Run(0.6f);
	if (!E->GetMesh()->GetSkeletalMeshAsset() || E->GetMesh()->GetBoneIndex(TEXT("thigh_R")) == INDEX_NONE)
	{
		AddWarning(TEXT("the Bearer's body is not imported (altered.py bearer, export, SO_IMPORT_ONLY=altered): its hold was not checked"));
		return true;
	}
	const ASOWeapon* Gun = E->GetWeapon();
	if (!TestNotNull(TEXT("its gun"), Gun) || !TestTrue(TEXT("the gun's rig is built"), Gun->GetThirdPersonRig() && Gun->GetThirdPersonRig()->IsBuilt()))
	{
		return false;
	}
	TestTrue(TEXT("it carries the gun at the hip, in both hands"), E->HoldsAtHip() && !E->HoldsWithOneHand());
	const float Arm = static_cast<float>(FVector::Dist(E->GetMesh()->GetBoneLocation(TEXT("upperarm_R")), E->GetMesh()->GetBoneLocation(TEXT("forearm_R")))
		+ FVector::Dist(E->GetMesh()->GetBoneLocation(TEXT("forearm_R")), E->GetMesh()->GetBoneLocation(TEXT("hand_R"))));
	auto Reach = [&](const TCHAR* When)
	{
		FTransform Right, Left;
		if (!TestTrue(TEXT("hand targets"), Gun->GetThirdPersonRig()->GetHandTargets(Right, Left)))
		{
			return;
		}
		const float R = static_cast<float>(FVector::Dist(E->GetMesh()->GetBoneLocation(TEXT("upperarm_R")), Right.GetLocation()));
		const float L = static_cast<float>(FVector::Dist(E->GetMesh()->GetBoneLocation(TEXT("upperarm_L")), Left.GetLocation()));
		const float Hip = static_cast<float>(FVector::Dist(E->GetMesh()->GetBoneLocation(TEXT("thigh_R")), Right.GetLocation()));
		const float Under = static_cast<float>(E->GetMesh()->GetBoneLocation(TEXT("chest")).Z - Right.GetLocation().Z);
		TestTrue(FString::Printf(TEXT("%s: the right hand's place is in reach (%.0f cm from the shoulder, the arm is %.0f)"), When, R, Arm), R < Arm * 1.02f && R > Arm * 0.35f);
		TestTrue(FString::Printf(TEXT("%s: so is the left hand's (%.0f cm, the arm is %.0f)"), When, L, Arm), L < Arm * 1.02f && L > Arm * 0.35f);
		TestTrue(FString::Printf(TEXT("%s: the rear grip is by the right hip (%.0f cm from the hip joint, %.0f under the chest)"), When, Hip, Under), Hip < 50.0f && Under > 15.0f);
	};
	Reach(TEXT("carried"));
	E->SetAimTarget(Player);
	W.Run(1.2f);
	Reach(TEXT("on a target"));
	const FVector Muzzle = Gun->GetThirdPersonRig()->GetMuzzleLocation();
	const FVector ToPlayer = (Player->GetActorLocation() - E->GetActorLocation()).GetSafeNormal2D();
	TestTrue(TEXT("on a target the muzzle is out in front of it"), FVector::DotProduct(Muzzle - E->GetActorLocation(), ToPlayer) > 40.0f);
	E->SetAimTarget(nullptr);

	// its plates
	const float Blow = E->GetMaxHealth() * 0.05f;
	TestTrue(TEXT("its plates turn a blow from the front"), E->TurnsBlow(Player->GetActorLocation()));
	TestEqual(TEXT("half of it goes in"), USOCombatStatics::ApplyDamage(Player, E, Blow, false), Blow * E->FrontDamageScale, 0.5f);
	TestTrue(TEXT("staggered"), USOCombatStatics::ApplyStatus(Player, E, SOTags::Status_Stagger, 1.0f));
	TestFalse(TEXT("reeling, its plates are down"), E->TurnsBlow(Player->GetActorLocation()));
	TestEqual(TEXT("and the blow goes in whole"), USOCombatStatics::ApplyDamage(Player, E, Blow, false), Blow, 0.5f);

	// its numbers are data
	const TMap<FName, float>* Numbers = USOSpeciesTable::Get().Find(TEXT("bearer"));
	if (TestNotNull(TEXT("its numbers in the species table"), Numbers))
	{
		TestEqual(TEXT("its health is the table's"), E->GetMaxHealth(), (*Numbers)[TEXT("health")], 0.01f);
		TestTrue(TEXT("it is a suppressor by its numbers"), E->bSuppressor && !E->bUsesCover);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOPlasmaTest, "ShatteredOrbit.Weapon.LightGunsFirePlasma", SOTest::Flags)
bool FSOPlasmaTest::RunTest(const FString& Parameters)
{
	// A light gun does not fire a bullet: it throws a bolt of plasma that is seen to fly and takes time to arrive, and
	// what shoots one at a moving target aims where the target will be.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-9000, -9000, -100), FVector(9000, 9000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* Mark = USOSpeciesLibrary::Spawn(W.World, TEXT("stalker_feral"), FVector(1500, 0, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("target"), Mark))
	{
		return false;
	}
	if (AController* Brain = Mark->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	Mark->SetAlert(true);
	W.Run(0.3f);
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	FRandomStream Rng(7);
	Player->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("auto"), 2, 20, Rng));
	W.Run(0.3f);
	ASOWeapon* Light = Player->GetWeapon();
	if (!TestNotNull(TEXT("the light rifle"), Light) || !TestNotNull(TEXT("its data"), Light->GetData()) || !TestNotNull(TEXT("effects"), Fx))
	{
		return false;
	}
	const float LightSpeed = Light->GetData()->MuzzleVelocity;
	TestTrue(FString::Printf(TEXT("a bolt of plasma flies at %.0f m/s: slow enough to be seen"), LightSpeed), LightSpeed > 100.0f && LightSpeed < 420.0f);
	const int32 Before = Fx->GetPlasmaBolts();
	const float Full = Mark->GetHealth();
	Light->StartFire();
	W.Run(0.035f);
	TestTrue(TEXT("the shot is drawn as plasma"), Fx->GetPlasmaBolts() > Before);
	TestEqual(TEXT("and has not arrived yet, 15 m away, a thirtieth of a second on"), Mark->GetHealth(), Full);
	W.Run(0.7f);
	Light->StopFire();
	TestTrue(TEXT("then it lands"), Mark->GetHealth() < Full);

	// a human rifle fires a bullet: faster by far, and never drawn as plasma
	Player->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("rifle"), 2, 20, Rng));
	W.Run(0.3f);
	ASOWeapon* Rifle = Player->GetWeapon();
	if (TestNotNull(TEXT("the rifle"), Rifle) && TestNotNull(TEXT("its data"), Rifle->GetData()))
	{
		TestTrue(FString::Printf(TEXT("a bullet is far faster (%.0f m/s against %.0f)"), Rifle->GetData()->MuzzleVelocity, LightSpeed),
			Rifle->GetData()->MuzzleVelocity > LightSpeed * 2.0f);
		const int32 Bolts = Fx->GetPlasmaBolts();
		Rifle->StartFire();
		W.Run(0.2f);
		Rifle->StopFire();
		TestEqual(TEXT("and is not plasma"), Fx->GetPlasmaBolts(), Bolts);
	}

	// one that shoots plasma at a moving target aims ahead of it
	ASOEnemy* Shooter = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(0, 2500, 0), -90.0f, Options);
	ASOCharacter* Runner = W.SpawnCharacter(FVector(-600, 500, 0));
	if (!TestNotNull(TEXT("shooter"), Shooter) || !TestNotNull(TEXT("runner"), Runner))
	{
		return false;
	}
	if (AController* Brain = Shooter->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	Shooter->AimError = 0.5f;                                    // (no scatter: this is about where it means to hit)
	Shooter->SetAimTarget(Runner);
	W.Run(4.0f, [&]() { Runner->AddMovementInput(FVector(1, 0, 0), 1.0f); });   // (long enough to have tracked it)
	const FVector Speed = Runner->GetVelocity();
	const FVector Chest = Runner->GetActorLocation() + FVector(0, 0, 25.0f);
	const FVector From = Shooter->GetAimOrigin();
	const FVector Dir = Shooter->GetAimDirection();
	const float Range = static_cast<float>(FVector::Dist(From, Chest));
	const float Ahead = static_cast<float>(FVector::DotProduct(From + Dir * Range - Chest, Speed.GetSafeNormal2D()));
	TestTrue(FString::Printf(TEXT("the target runs at %.0f cm/s"), Speed.Size2D()), Speed.Size2D() > 250.0f);
	TestTrue(FString::Printf(TEXT("it aims %.0f cm ahead of a target %.0f cm away"), Ahead, Range), Ahead > 8.0f);
	Shooter->ShotLead = 0.0f;
	const float NoLead = static_cast<float>(FVector::DotProduct(From + Shooter->GetAimDirection() * Range - Chest, Speed.GetSafeNormal2D()));
	TestTrue(FString::Printf(TEXT("with no lead it aims at where the target is (%.0f cm ahead)"), NoLead), FMath::Abs(NoLead) < 6.0f);
	return true;
}


IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOSarkethSlugTest, "ShatteredOrbit.Weapon.SarkethSlugs", SOTest::Flags)
bool FSOSarkethSlugTest::RunTest(const FString& Parameters)
{
	// The Sarketh's guns (docs/orion/SARKETH_WEAPONS.md): a crystalline slug seen to fly, whose crystal goes on through
	// the body it ruptures on; and thermal accumulation: the crystal heats with every shot, its rounds burn brighter and
	// then fly faster, and at full heat it vents by itself and cannot fire until it has.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-9000, -9000, -100), FVector(9000, 9000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	ASOEnemy* Front = USOSpeciesLibrary::Spawn(W.World, TEXT("stalker_feral"), FVector(1500, 0, 0), 180.0f, Options);
	ASOEnemy* Behind = USOSpeciesLibrary::Spawn(W.World, TEXT("stalker_feral"), FVector(1800, 0, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("a body in front"), Front) || !TestNotNull(TEXT("a body behind it"), Behind))
	{
		return false;
	}
	for (ASOEnemy* Mark : { Front, Behind })
	{
		if (AController* Brain = Mark->GetController())
		{
			Brain->UnPossess();
			Brain->Destroy();
		}
		Mark->SetAlert(true);
	}
	W.Run(0.3f);
	auto Life = [](const ASOCombatCharacter* C) { return C->GetHealth() + C->GetShield(); };

	// a slug passes through the first body into the second; a round that does not pierce stops in the first
	USOProjectileSubsystem* Rounds = W.World->GetSubsystem<USOProjectileSubsystem>();
	if (!TestNotNull(TEXT("rounds"), Rounds))
	{
		return false;
	}
	const float Z = Front->GetActorLocation().Z;
	auto Throw = [&](int32 Pierce)
	{
		FSOProjectile Slug;
		Slug.Origin = Slug.Position = FVector(900.0f, 0.0f, Z);
		Slug.Velocity = FVector(30000.0f, 0.0f, 0.0f);
		Slug.Damage = 10.0f;
		Slug.CritMultiplier = 1.0f;
		Slug.FalloffStart = 1.0e6f;
		Slug.MinDamageScale = 1.0f;
		Slug.Life = 3.0f;
		Slug.Instigator = Player;
		Slug.Pierce = Pierce;
		Slug.PierceKeep = 0.5f;
		Rounds->Fire(Slug);
		W.Run(0.3f);
	};
	float F0 = Life(Front), B0 = Life(Behind);
	Throw(0);
	TestTrue(TEXT("a round that does not pierce hurts the body in front"), Life(Front) < F0);
	TestEqual(TEXT("and stops in it"), Life(Behind), B0);
	F0 = Life(Front);
	B0 = Life(Behind);
	Throw(1);
	const float FrontLost = F0 - Life(Front), BehindLost = B0 - Life(Behind);
	TestTrue(TEXT("a slug hurts the body in front"), FrontLost > 0.0f);
	TestTrue(FString::Printf(TEXT("and goes on into the body behind it (%.1f, then %.1f)"), FrontLost, BehindLost), BehindLost > 0.0f);
	TestTrue(TEXT("with what it has left"), BehindLost < FrontLost);

	// the rifle: it fires slugs, seen to fly
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	FRandomStream Rng(11);
	Player->EquipInstance(USOLootLibrary::MakeWeapon(TEXT("skr_rifle"), 2, 20, Rng));
	W.Run(0.3f);
	ASOWeapon* Gun = Player->GetWeapon();
	if (!TestNotNull(TEXT("the Sarketh rifle (skr_rifle imported)"), Gun) || !TestNotNull(TEXT("its data"), Gun->GetData()) || !TestNotNull(TEXT("effects"), Fx))
	{
		return false;
	}
	const USOWeaponData* Data = Gun->GetData();
	TestEqual(TEXT("it fires slugs"), Data->Projectile, ESOProjectileKind::Slug);
	TestTrue(TEXT("its slug pierces"), Data->Pierce > 0);
	TestTrue(TEXT("its crystal heats"), Gun->HasHeat());
	TestTrue(FString::Printf(TEXT("a slug flies at %.0f m/s: seen, as a light gun's bolt is, far slower than a bullet"), Data->MuzzleVelocity),
		Data->MuzzleVelocity > 150.0f && Data->MuzzleVelocity < 500.0f);
	const int32 Before = Fx->GetSlugs();
	const int32 Bolts = Fx->GetPlasmaBolts();
	Gun->StartFire();
	W.Run(0.02f);
	Gun->StopFire();
	TestTrue(TEXT("the shot is drawn as a slug"), Fx->GetSlugs() > Before);
	TestEqual(TEXT("never as a plasma bolt"), Fx->GetPlasmaBolts(), Bolts);
	TestTrue(TEXT("one shot warms the crystal"), Gun->GetHeat() > 0.0f);
	W.Run(2.5f);
	TestTrue(FString::Printf(TEXT("and it cools at rest (%.2f)"), Gun->GetHeat()), Gun->GetHeat() < 0.01f);

	// held down: brighter, then faster, then it vents by itself and holds its fire
	TestTrue(TEXT("medium heat burns brighter"), ASOWeapon::HeatBright(0.9f) > ASOWeapon::HeatBright(0.2f));
	TestTrue(TEXT("high heat throws faster"), Gun->HeatSpeedScale(0.95f) > 1.05f && Gun->HeatSpeedScale(0.3f) == 1.0f);
	Gun->StartFire();
	float Most = 0.0f;
	bool bVented = false;
	for (int32 i = 0; i < 120 && !bVented; ++i)
	{
		W.Run(0.05f);
		Most = FMath::Max(Most, Gun->GetHeat());
		bVented = Gun->IsVenting();
	}
	TestTrue(FString::Printf(TEXT("held down, the crystal reaches full heat (%.2f) and vents"), Most), bVented);
	TestTrue(TEXT("before the cell runs dry"), Gun->GetMag() > 0);
	const int32 Held = Gun->GetMag();
	W.Run(0.5f);
	TestEqual(TEXT("venting, it does not fire though the trigger is held"), Gun->GetMag(), Held);
	W.Run(Data->VentTime);
	TestFalse(TEXT("then the vent is over"), Gun->IsVenting());
	W.Run(0.3f);
	TestTrue(TEXT("and it fires again"), Gun->GetMag() < Held);
	Gun->StopFire();
	return true;
}
