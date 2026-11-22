#include "SOAltered.h"

#include "SOAlteredCommon.h"

#include "Engine/World.h"
#include "SOCombatTypes.h"

// The Bearer.
ASOBearer::ASOBearer(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// (its numbers are data: Data/species.json. These stand in for whatever that file does not name.)
	SpeciesId = TEXT("bearer");
	SOAltered::Configure(this, TEXT("SarkethHeavy"), 40.0f, 104.0f, 1.06f);   // (a Bearer: the heavy Sarketh)
	VoicePrefix = TEXT("bearer");
	// the Bearer's colours: bronze plates, a brown-black lacquer, orange lights (heavy weapons)
	PlateTint = FLinearColor(1.16f, 0.82f, 0.52f);
	LacquerTint = FLinearColor(1.24f, 0.98f, 0.74f);
	LightTint = FLinearColor(1.00f, 0.50f, 0.15f);
	DisplayName = NSLOCTEXT("SO", "Bearer", "Bearer");
	WeaponArchetype = TEXT("hmg");
	WeaponDamageScale = 0.2f;
	AimError = 88.0f;
	PreferredRange = 1500.0f;
	bUsesCover = false;
	bSuppressor = true;
	bPack = false;
	BurstTime = FVector2D(1.2f, 2.2f);
	BurstPause = FVector2D(0.8f, 1.4f);
	StartMaxHealth = 800.0f;
	WalkSpeed = 130.0f;
	RunSpeed = 250.0f;
	MeleeDamage = 30.0f;
	MeleeRange = 220.0f;
	MeleeCooldown = 1.8f;
	MeleeWindup = 0.5f;
	LungeSpeed = 200.0f;
	FlinchScale = 0.5f;
	Poise = 0.32f;
	PoiseRecover = 0.06f;
	StumbleTime = 1.0f;
	HitSlow = 0.8f;
	ActionClips = { TEXT("Brace") };
}

bool ASOBearer::PlateFaces(const FVector& From) const
{
	const FVector To = (From - GetActorLocation()).GetSafeNormal2D();
	return FVector::DotProduct(GetActorForwardVector().GetSafeNormal2D(), To) > 0.4f && !IsFiring() && !HasStatus(SOTags::Status_Stagger);
}

float ASOBearer::ScaleIncomingDamage(float Amount, const AActor* Source, bool bCrit) const
{
	if (!Source)
	{
		return Amount;
	}
	const float Through = PlateFaces(Source->GetActorLocation()) ? Amount * FrontDamageScale : Amount;
	AbsorbedByArmour = Amount - Through; // (what the plates took still shakes it: ASOEnemy::HitReact)
	return Super::ScaleIncomingDamage(Through, Source, bCrit);
}

void ASOBearer::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	// As it opens fire it sets itself behind the gun (its Brace clip), not more often than every few seconds.
	const bool bFiringNow = IsFiring();
	const UWorld* World = GetWorld();
	if (HasAuthority() && World && bFiringNow && !bWasFiring && !IsDead() && World->GetTimeSeconds() >= NextBrace && GetVelocity().SizeSquared2D() < FMath::Square(60.0f))
	{
		NextBrace = World->GetTimeSeconds() + 5.0f;
		PlayAction(TEXT("Brace"), 1.0f);
	}
	bWasFiring = bFiringNow;
}
