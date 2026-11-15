// Phase 3 of Project Orion: a boss is a species with a table. Its phases by health, the shield between them, its weak
// point, and its attacks as abilities that warn before they land. All single-machine (the server's side).

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Abilities/SOAbilitySet.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "SOAltered.h"
#include "SOBoss.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOFxSubsystem.h"
#include "SOProjectileSubsystem.h"
#include "SOSpecies.h"

namespace
{
	/** The Colossus at the origin, facing -X (toward a player standing at negative X), without its brain: the test
	 *  decides what it does. */
	ASOColossus* SpawnStillColossus(SOTest::FTestWorld& W)
	{
		FActorSpawnParameters P;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		const float Half = GetDefault<ASOColossus>()->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		ASOColossus* C = W.World->SpawnActor<ASOColossus>(FVector(0, 0, Half + 2.0f), FRotator(0, 180, 0), P);
		if (AController* Brain = C ? C->GetController() : nullptr)
		{
			Brain->UnPossess();
			Brain->Destroy();
		}
		return C;
	}

	float Life(const ASOCharacter* Player)
	{
		return Player->GetHealth() + Player->GetShield();
	}

	void KillConduits(ASOColossus* C, AActor* By)
	{
		const TArray<TWeakObjectPtr<ASOConduit>> Conduits = C->GetConduits();
		for (const TWeakObjectPtr<ASOConduit>& K : Conduits)
		{
			if (K.IsValid())
			{
				USOCombatStatics::ApplyDamage(By, K.Get(), 50000.0f, false);
			}
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBossPhasesTest, "ShatteredOrbit.Boss.PhasesByHealth", SOTest::Flags)
bool FSOBossPhasesTest::RunTest(const FString& Parameters)
{
	// The Colossus fights by its table: three phases, each with its own kit; the second and third begin behind a
	// shield; the opening after a shield breaks is not cut short by the next phase.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-3000, 0, 0));
	ASOColossus* C = SpawnStillColossus(W);
	if (!TestNotNull(TEXT("colossus"), C))
	{
		return false;
	}
	W.Run(0.3f);
	C->SetAlert(true); // (it knows there is a fight on: a blow on one that does not is an ambush and counts double)
	USOBossComponent* Fight = C->GetBoss();
	if (!TestNotNull(TEXT("the Colossus fights by a boss table (run the import with SO_IMPORT_ONLY=bosses,kits)"), Fight))
	{
		return false;
	}
	TestEqual(TEXT("three phases"), Fight->NumPhases(), 3);
	TestEqual(TEXT("it begins in the first"), Fight->GetPhase(), 0);
	TestEqual(TEXT("with its own kit"), C->GetAbilitySet() ? C->GetAbilitySet()->KitId : NAME_None, FName(TEXT("colossus")));
	TestNull(TEXT("no ground-breaking yet"), C->GetAbilitySet() ? C->GetAbilitySet()->Find(ESOAbilitySlot::Ultimate) : nullptr);
	const float Cooldown0 = C->GetAbilityCooldownScale(ESOAbilitySlot::Class);

	// one blow across both thresholds: the second phase and its shield come first
	USOCombatStatics::ApplyDamage(Player, C, C->GetMaxHealth() * 0.8f, false);
	W.Run(0.3f);
	TestEqual(TEXT("second phase"), Fight->GetPhase(), 1);
	TestTrue(TEXT("behind its shield"), C->IsShielded() && C->IsImmune());
	TestEqual(TEXT("the second phase's kit"), C->GetAbilitySet() ? C->GetAbilitySet()->KitId : NAME_None, FName(TEXT("colossus_choir")));
	TestNotNull(TEXT("which breaks the ground open"), C->GetAbilitySet() ? C->GetAbilitySet()->Find(ESOAbilitySlot::Ultimate) : nullptr);

	KillConduits(C, Player);
	W.Run(0.3f);
	TestTrue(TEXT("the shield breaks and it reels"), !C->IsImmune() && C->IsStaggered());
	TestEqual(TEXT("still the second phase while it reels: the opening is the players'"), Fight->GetPhase(), 1);
	TestEqual(TEXT("reeling, it takes half again"), USOCombatStatics::ApplyDamage(Player, C, 100.0f, false), 150.0f);

	W.Run(5.5f);
	TestEqual(TEXT("then the third phase"), Fight->GetPhase(), 2);
	TestTrue(TEXT("behind a shield again"), C->IsShielded() && C->IsImmune());
	TestEqual(TEXT("the third phase's kit"), C->GetAbilitySet() ? C->GetAbilitySet()->KitId : NAME_None, FName(TEXT("colossus_root")));
	TestEqual(TEXT("its moves come back sooner"), C->GetAbilityCooldownScale(ESOAbilitySlot::Class), Cooldown0 * 0.8f, 0.001f);
	const FSOAbilityGrant* Sundering = C->GetAbilitySet() ? C->GetAbilitySet()->Find(ESOAbilitySlot::Class) : nullptr;
	TestTrue(TEXT("its heavy attack warns for longer"), Sundering && Sundering->WindUp >= 1.5f && Sundering->WindUp <= 2.2f);

	C->Die(Player);
	W.Run(0.2f);
	int32 Standing = 0;
	for (TActorIterator<ASOConduit> It(W.World); It; ++It)
	{
		Standing += !It->IsDead();
	}
	TestEqual(TEXT("its conduits go with it"), Standing, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBossWeakPointTest, "ShatteredOrbit.Boss.WeakPoint", SOTest::Flags)
bool FSOBossWeakPointTest::RunTest(const FString& Parameters)
{
	// The heart in the hollow chest: a round into it from the front is worth more than a precision hit, one from
	// behind is not; enough on it breaks it, the Colossus reels and the heart is shut until the next phase.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-1500, 0, 0));
	ASOColossus* C = SpawnStillColossus(W);
	if (!TestNotNull(TEXT("colossus"), C))
	{
		return false;
	}
	W.Run(0.5f);
	C->SetAlert(true);
	USOBossComponent* Fight = C->GetBoss();
	if (!TestNotNull(TEXT("boss table"), Fight) || !TestTrue(TEXT("it has a weak point"), Fight->GetData()->WeakPoints.Num() > 0))
	{
		return false;
	}
	const FSOWeakPoint& Heart = Fight->GetData()->WeakPoints[0];
	const FVector At = Fight->GetWeakPointLocation(0);
	const FVector Fwd = C->GetActorForwardVector();
	AddInfo(FString::Printf(TEXT("heart at %s (body at %s, half height %.0f)"), *At.ToString(), *C->GetActorLocation().ToString(), C->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()));
	auto Shot = [&](const FVector& From, const FVector& To, FHitResult& Hit)
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(SOTest), true, Player);
		return W.World->LineTraceSingleByChannel(Hit, From, To, SO_TRACE_BULLET, Params) && Hit.GetActor() == C;
	};
	FHitResult Front, Back, Leg;
	if (!TestTrue(TEXT("a shot at the heart from the front lands on the body"), Shot(At + Fwd * 800.0f, At - Fwd * 200.0f, Front)))
	{
		return false;
	}
	AddInfo(FString::Printf(TEXT("front hit on bone '%s', %.0f cm from the heart"), *Front.BoneName.ToString(), FVector::Dist(Front.ImpactPoint, At)));
	// what a round from the front lands on, by height (for the record: how far the bodies stand off the drawn surface)
	const FVector Feet = C->GetActorLocation() - FVector(0, 0, C->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
	for (float Z = 20.0f; Z < 300.0f; Z += 40.0f)
	{
		FString Row;
		for (const float Side : { -60.0f, -30.0f, 0.0f, 30.0f, 60.0f })
		{
			FHitResult Probe;
			const FVector P = Feet + FVector(0, 0, Z) + C->GetActorRightVector() * Side;
			Row += Shot(P + Fwd * 800.0f, P - Fwd * 300.0f, Probe)
				? FString::Printf(TEXT(" %s@%.0f"), *Probe.BoneName.ToString(), FVector::DotProduct(Probe.ImpactPoint - Feet, Fwd)) : TEXT(" -");
		}
		AddInfo(FString::Printf(TEXT("z %3.0f:%s"), Z, *Row));
	}
	TestEqual(TEXT("that is the heart"), Fight->WeakPointAt(Front), 0);
	TestEqual(TEXT("worth more than a precision hit"), C->PrecisionAt(Front), Heart.Scale);
	if (TestTrue(TEXT("a shot from behind lands too"), Shot(At - Fwd * 800.0f, At + Fwd * 200.0f, Back)))
	{
		TestEqual(TEXT("but from behind it is plate"), C->PrecisionAt(Back), 0.0f);
	}
	const FVector Shin = C->GetActorLocation() - FVector(0, 0, C->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() * 0.6f);
	for (const float Side : { 0.0f, 18.0f, -18.0f, 30.0f, -30.0f })
	{
		const FVector P = Shin + C->GetActorRightVector() * Side;
		if (Shot(P + Fwd * 800.0f, P - Fwd * 200.0f, Leg))
		{
			break;
		}
	}
	if (TestTrue(TEXT("a shot at the legs lands"), Leg.GetActor() == C))
	{
		TestEqual(TEXT("and is no precision hit"), C->PrecisionAt(Leg), 0.0f);
	}

	// a real round into the heart: the gun's precision multiplier and the heart's on top
	USOProjectileSubsystem* Rounds = W.World->GetSubsystem<USOProjectileSubsystem>();
	float Applied = 0.0f;
	const FDelegateHandle Handle = Rounds->OnHit.AddLambda([&](const FSOProjectile&, const FHitResult& Hit, float Damage)
	{
		Applied += Hit.GetActor() == C ? Damage : 0.0f;
	});
	FSOProjectile Round;
	Round.Origin = Round.Position = At + Fwd * 800.0f;
	Round.Velocity = -Fwd * 71500.0f;
	Round.Gravity = 0.0f;
	Round.Damage = 100.0f;
	Round.CritMultiplier = 2.0f;
	Round.Instigator = Player;
	Rounds->Fire(Round);
	W.Run(0.2f);
	Rounds->OnHit.Remove(Handle);
	TestEqual(TEXT("the round does its damage x precision x the heart"), Applied, 100.0f * 2.0f * Heart.Scale, 0.5f);
	TestEqual(TEXT("and is counted against the heart"), Fight->GetWeakPointDamage(0), Applied, 0.5f);

	// broken
	TestFalse(TEXT("not reeling yet"), C->IsStaggered());
	Fight->HitWeakPoint(0, Heart.BreakDamage);
	TestTrue(TEXT("the heart breaks: it reels"), C->IsStaggered());
	TestFalse(TEXT("and is shut"), Fight->IsWeakPointOpen(0));
	TestEqual(TEXT("a hit there is an ordinary hit now"), C->PrecisionAt(Front), 0.0f);
	W.Run(Heart.BreakStagger + 0.3f);
	TestFalse(TEXT("it comes round"), C->IsStaggered());
	TestFalse(TEXT("the heart stays shut for the phase"), Fight->IsWeakPointOpen(0));

	// the next phase: whole again
	USOCombatStatics::ApplyDamage(Player, C, C->GetHealth() - C->GetMaxHealth() * 0.6f, false);
	W.Run(0.3f);
	TestEqual(TEXT("second phase"), Fight->GetPhase(), 1);
	TestFalse(TEXT("nothing is open behind the shield"), Fight->IsWeakPointOpen(0));
	KillConduits(C, Player);
	W.Run(0.3f);
	TestTrue(TEXT("open again in the new phase"), Fight->IsWeakPointOpen(0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBossAttacksWarnTest, "ShatteredOrbit.Boss.AttacksWarnFirst", SOTest::Flags)
bool FSOBossAttacksWarnTest::RunTest(const FString& Parameters)
{
	// The Colossus's slam and sweep are abilities from its kit: a warning on the ground for the whole wind-up, the
	// kit's damage when it ends, the sweep only across its front and throwing sideways.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-300, 0, 0));
	ASOColossus* C = SpawnStillColossus(W);
	if (!TestNotNull(TEXT("colossus"), C))
	{
		return false;
	}
	W.Run(0.4f);
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	const USOAbilitySet* Kit = C->GetAbilitySet();
	const FSOAbilityGrant* Slam = Kit ? Kit->Find(ESOAbilitySlot::Class) : nullptr;
	const FSOAbilityGrant* Sweep = Kit ? Kit->Find(ESOAbilitySlot::Melee) : nullptr;
	if (!TestNotNull(TEXT("fx"), Fx) || !TestNotNull(TEXT("the kit has the slam (SO_IMPORT_ONLY=kits)"), Slam) || !TestNotNull(TEXT("and the sweep"), Sweep))
	{
		return false;
	}
	TestTrue(TEXT("the slam is a standard attack: 0.9 to 1.4 s of warning"), Slam->WindUp >= 0.9f && Slam->WindUp <= 1.4f);
	TestTrue(TEXT("so is the sweep"), Sweep->WindUp >= 0.9f && Sweep->WindUp <= 1.4f);

	const float Before = Life(Player);
	C->SetAbilityTarget(Player);
	TestEqual(TEXT("no warning before it moves"), Fx->GetNumWarnings(), 0);
	TestTrue(TEXT("slam begun"), C->ActivateSlot(ESOAbilitySlot::Class));
	TestEqual(TEXT("its reach is drawn on the ground at once"), Fx->GetNumWarnings(), 1);
	W.Run(Slam->WindUp * 0.7f);
	TestEqual(TEXT("still drawn"), Fx->GetNumWarnings(), 1);
	TestEqual(TEXT("nothing lands during the warning"), Life(Player), Before);
	W.Run(Slam->WindUp * 0.3f + 0.1f);
	TestEqual(TEXT("then it lands for the kit's damage"), Life(Player), Before - Slam->Damage, 0.5f);
	W.Run(0.5f);
	TestEqual(TEXT("and the warning is gone"), Fx->GetNumWarnings(), 0);

	// the sweep: across the front, thrown sideways
	W.Run(1.0f);
	Player->SetActorLocation(FVector(-300, 0, 93));
	Player->GetCharacterMovement()->Velocity = FVector::ZeroVector;
	W.Run(0.3f);
	const float Mid = Life(Player);
	TestTrue(TEXT("sweep begun"), C->ActivateSlot(ESOAbilitySlot::Melee));
	W.Run(Sweep->WindUp + 0.05f);
	TestEqual(TEXT("the sweep lands on what is in front"), Life(Player), Mid - Sweep->Damage, 0.5f);
	const FVector Thrown = Player->GetVelocity();
	TestTrue(FString::Printf(TEXT("and throws sideways more than away (%s)"), *Thrown.ToString()), FMath::Abs(Thrown.Y) > FMath::Abs(Thrown.X) && FMath::Abs(Thrown.Y) > 300.0f);

	// behind it: the sweep is drawn in front and that is where it lands
	W.Run(Sweep->Cooldown + 0.5f);
	Player->SetActorLocation(FVector(300, 0, 93));
	Player->GetCharacterMovement()->Velocity = FVector::ZeroVector;
	W.Run(0.3f);
	const float Behind = Life(Player);
	TestTrue(TEXT("second sweep begun"), C->ActivateSlot(ESOAbilitySlot::Melee));
	W.Run(Sweep->WindUp + 0.2f);
	TestTrue(TEXT("nothing behind it is touched"), Life(Player) >= Behind);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBossBarrageTest, "ShatteredOrbit.Boss.BarrageLasts", SOTest::Flags)
bool FSOBossBarrageTest::RunTest(const FString& Parameters)
{
	// A volley is an ability that lasts: in use from the wind-up to the last bolt, and its bolts hurt.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-6000, -6000, -100), FVector(6000, 6000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-1800, 0, 0));
	ASOColossus* C = SpawnStillColossus(W);
	if (!TestNotNull(TEXT("colossus"), C))
	{
		return false;
	}
	W.Run(0.4f);
	const FSOAbilityGrant* Barrage = C->GetAbilitySet() ? C->GetAbilitySet()->Find(ESOAbilitySlot::Grenade) : nullptr;
	if (!TestNotNull(TEXT("the kit has the barrage (SO_IMPORT_ONLY=kits)"), Barrage))
	{
		return false;
	}
	const float Before = Life(Player);
	C->SetAbilityTarget(Player);
	TestTrue(TEXT("barrage begun"), C->ActivateSlot(ESOAbilitySlot::Grenade));
	W.Run(Barrage->WindUp * 0.8f);
	TestEqual(TEXT("nothing during the wind-up"), Life(Player), Before);
	W.Run(Barrage->WindUp * 0.2f + Barrage->Duration * 0.5f);
	TestTrue(TEXT("still at it half way through the volley"), C->IsAbilityActive(ESOAbilitySlot::Grenade) && C->IsUsingAbility());
	W.Run(Barrage->Duration * 0.5f + 0.3f);
	TestFalse(TEXT("over when the volley is"), C->IsAbilityActive(ESOAbilitySlot::Grenade));
	W.Run(1.5f);
	TestTrue(FString::Printf(TEXT("its bolts hurt (%.0f of %.0f left)"), Life(Player), Before), Life(Player) < Before);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBossMarksTest, "ShatteredOrbit.Boss.MarksBurstWhereDrawn", SOTest::Flags)
bool FSOBossMarksTest::RunTest(const FString& Parameters)
{
	// The ground breaking open: marks under those it fights (and more round them), drawn for the fuse, then they
	// burst. Whoever stays in one is hurt; whoever has left is not.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-9000, -9000, -100), FVector(9000, 9000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-1500, 0, 0));
	ASOColossus* C = SpawnStillColossus(W);
	if (!TestNotNull(TEXT("colossus"), C))
	{
		return false;
	}
	W.Run(0.4f);
	C->GrantAbilitySet(USOAbilitySet::Load(TEXT("colossus_choir")));
	const FSOAbilityGrant* Marks = C->GetAbilitySet() ? C->GetAbilitySet()->Find(ESOAbilitySlot::Ultimate) : nullptr;
	USOFxSubsystem* Fx = W.World->GetSubsystem<USOFxSubsystem>();
	if (!TestNotNull(TEXT("the second phase's kit has the marks (SO_IMPORT_ONLY=kits)"), Marks) || !TestNotNull(TEXT("fx"), Fx))
	{
		return false;
	}
	TestTrue(TEXT("a heavy attack: 1.5 to 2.2 s of warning on the ground"), Marks->Duration >= 1.5f && Marks->Duration <= 2.2f);

	// stays in it
	const float Before = Life(Player);
	C->SetAbilityTarget(Player);
	TestTrue(TEXT("begun"), C->ActivateSlot(ESOAbilitySlot::Ultimate));
	W.Run(Marks->WindUp + 0.1f);
	TestEqual(TEXT("a mark under the player and the extra ones"), Fx->GetNumWarnings(), 1 + FMath::RoundToInt(Marks->Magnitude));
	W.Run(Marks->Duration * 0.8f);
	TestEqual(TEXT("nothing until the fuse is up"), Life(Player), Before);
	W.Run(Marks->Duration * 0.2f + 0.1f);
	TestEqual(TEXT("then it bursts for the kit's damage"), Life(Player), Before - Marks->Damage, 0.5f);

	// leaves it
	W.Run(Marks->Cooldown + 0.5f);
	Player->SetActorLocation(FVector(-1500, 0, 93));
	Player->GetCharacterMovement()->Velocity = FVector::ZeroVector;
	W.Run(0.3f);
	const float Again = Life(Player);
	TestTrue(TEXT("begun again"), C->ActivateSlot(ESOAbilitySlot::Ultimate));
	W.Run(Marks->WindUp + 0.2f);
	Player->SetActorLocation(FVector(-1500, 2500, 93)); // well clear of the mark and of the extra ones round it
	W.Run(Marks->Duration + 0.3f);
	TestTrue(TEXT("out of the ring, untouched"), Life(Player) >= Again);

	// whoever called them up dies first: they come to nothing
	W.Run(Marks->Cooldown + 0.5f);
	Player->GetCharacterMovement()->Velocity = FVector::ZeroVector;
	W.Run(0.3f);
	const float Last = Life(Player);
	TestTrue(TEXT("begun a third time"), C->ActivateSlot(ESOAbilitySlot::Ultimate));
	W.Run(Marks->WindUp + 0.2f);
	C->Die(nullptr);
	W.Run(Marks->Duration + 0.3f);
	TestTrue(TEXT("its marks die with it"), Life(Player) >= Last);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOBossVariantTest, "ShatteredOrbit.Boss.AVariantCanBeABoss", SOTest::Flags)
bool FSOBossVariantTest::RunTest(const FString& Parameters)
{
	// A level makes a boss out of a species with data alone: a Bulwark given the table "warden" fights in two phases.
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(-2500, 0, 0));
	FSOSpeciesVariant Warden;
	Warden.Id = TEXT("warden");
	Warden.Species = TEXT("bulwark");
	Warden.Health = 5.0f;
	Warden.Boss = TEXT("warden");
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	Options.Variant = &Warden;
	ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("bulwark"), FVector(0, 0, 0), 0.0f, Options); // (its back to the player: its shield turns blows from the front)
	if (!TestNotNull(TEXT("the warden"), E))
	{
		return false;
	}
	W.Run(0.3f);
	E->SetAlert(true);
	const USOBossComponent* Fight = E->GetBoss();
	if (!TestNotNull(TEXT("a variant with a boss table is a boss (SO_IMPORT_ONLY=bosses)"), Fight))
	{
		return false;
	}
	TestEqual(TEXT("two phases"), Fight->NumPhases(), 2);
	TestEqual(TEXT("the first with the species' own kit"), E->GetAbilitySet() ? E->GetAbilitySet()->KitId : NAME_None, FName(TEXT("bulwark")));
	const float Cooldown0 = E->GetAbilityCooldownScale(ESOAbilitySlot::Class);
	const float Speed0 = E->GetCharacterMovement()->MaxWalkSpeed;
	TestNull(TEXT("an ordinary bulwark is no boss"), GetDefault<ASOBulwark>()->GetBoss());

	USOCombatStatics::ApplyDamage(Player, E, E->GetMaxHealth() * 0.55f, false);
	W.Run(0.3f);
	TestEqual(TEXT("second phase at half"), Fight->GetPhase(), 1);
	TestEqual(TEXT("with the phase's kit"), E->GetAbilitySet() ? E->GetAbilitySet()->KitId : NAME_None, FName(TEXT("warden_fury")));
	TestEqual(TEXT("its moves come back sooner"), E->GetAbilityCooldownScale(ESOAbilitySlot::Class), Cooldown0 * 0.7f, 0.001f);
	E->SetRunning(false);
	const float Walk1 = E->GetCharacterMovement()->MaxWalkSpeed;
	E->SetRunning(true);
	TestTrue(FString::Printf(TEXT("and it is faster (walk %.0f, was %.0f at the start)"), Walk1, Speed0), Walk1 > E->WalkSpeed * 1.25f);
	TestFalse(TEXT("no shield in this table"), E->IsImmune());
	return true;
}

#endif
