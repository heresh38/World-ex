#include "SOMelee.h"

#include "GameFramework/CharacterMovementComponent.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOCue.h"
#include "UObject/StrongObjectPtr.h"

const FSOMeleeStyle* USOMeleeTable::Find(FName Id) const
{
	return Styles.FindByPredicate([Id](const FSOMeleeStyle& S) { return S.Id == Id; });
}

const FSOMeleeBlow* USOMeleeTable::Blow(const FSOMeleeStyle& Style, int32 Index)
{
	const FSOMeleeBlow* B = nullptr;
	switch (Index)
	{
	case SOMeleeMove::Heavy: B = &Style.Heavy; break;
	case SOMeleeMove::Finisher: B = &Style.Finisher; break;
	case SOMeleeMove::Rush: B = &Style.Rush; break;
	case SOMeleeMove::Sweep: B = &Style.Sweep; break;
	case SOMeleeMove::Riser: B = &Style.Riser; break;
	case SOMeleeMove::Air: B = &Style.Air; break;
	default: B = Style.Light.IsValidIndex(Index) ? &Style.Light[Index] : nullptr; break;
	}
	return B && !B->Clip.IsNone() ? B : nullptr;
}

const USOMeleeTable* USOMeleeTable::Get()
{
	static TStrongObjectPtr<USOMeleeTable> Table;
	if (!Table.IsValid())
	{
		if (USOMeleeTable* Loaded = Cast<USOMeleeTable>(FSoftObjectPath(TEXT("/Game/Data/DA_Melee.DA_Melee")).TryLoad()))
		{
			Table.Reset(Loaded);
		}
	}
	return Table.Get();
}

int32 USOMeleeLibrary::Land(ASOCombatCharacter* User, const FSOMeleeBlow& Blow, float Scale, float Weight)
{
	UWorld* World = User ? User->GetWorld() : nullptr;
	if (!World || User->IsDead())
	{
		return 0;
	}
	FVector Forward = User->GetAimDirection();
	const FVector Origin = User->GetAimOrigin();
	const float MinDot = FMath::Cos(FMath::DegreesToRadians(FMath::Clamp(Blow.Angle, 1.0f, 180.0f)));
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOMelee), false, User);
	int32 Hits = 0;
	for (TActorIterator<ASOCombatCharacter> It(World); It; ++It)
	{
		ASOCombatCharacter* Other = *It;
		if (Other == User || Other->IsDead() || !USOCombatStatics::AreHostile(User, Other))
		{
			continue;
		}
		// the nearest point of the other's capsule along the line from the eye: a blow lands on the body, not its middle
		const FVector Centre = Other->GetActorLocation();
		const float Half = Other->GetSimpleCollisionHalfHeight();
		const FVector Near(Centre.X, Centre.Y, FMath::Clamp(Origin.Z, Centre.Z - Half, Centre.Z + Half));
		const FVector To = Near - Origin;
		if (Blow.Shock > 0.0f)
		{
			// into the ground: all round, within the ring
			if (FVector::Dist2D(Centre, User->GetActorLocation()) > Blow.Shock + Other->GetSimpleCollisionRadius() || FMath::Abs(Centre.Z - User->GetActorLocation().Z) > 220.0f)
			{
				continue;
			}
		}
		else
		{
			const float Reach = Blow.Range + Other->GetSimpleCollisionRadius();
			if (To.Size() > Reach || FVector::DotProduct(Forward, To.GetSafeNormal()) < MinDot)
			{
				continue;
			}
		}
		// not through a wall (the world's static geometry only: the user's own gun on its back is not in the way)
		if (World->LineTraceTestByObjectType(Origin, Near, FCollisionObjectQueryParams(ECC_WorldStatic), Params))
		{
			continue;
		}
		float Dealt = 0.0f;
		// a body already in the air takes more (a juggle)
		const bool bAirborne = Other->GetCharacterMovement() && Other->GetCharacterMovement()->IsFalling();
		{
			const FSOHitScope Where(TEXT("chest"), Near, To.GetSafeNormal(), false);
			Dealt = USOCombatStatics::ApplyDamage(User, Other, Blow.Damage * User->GetAbilityDamageScale() * Scale * (bAirborne ? 1.2f : 1.0f), false);
		}
		if (Dealt <= 0.0f)
		{
			continue;
		}
		++Hits;
		User->OnMeleeHit(Other, Near - To.GetSafeNormal() * Other->GetSimpleCollisionRadius() * 0.6f, Weight, Blow.HitStop);
		if (!Blow.HitSound.IsNone())
		{
			USOCue::Sound(User, Blow.HitSound, Near, 1.0f, 0.06f);
		}
		if (Other->IsDead())
		{
			continue;
		}
		if (Blow.Stagger > 0.0f)
		{
			USOCombatStatics::ApplyStatus(User, Other, SOTags::Status_Stagger, Blow.Stagger);
		}
		if (Blow.Force > 0.0f || Blow.Launch > 0.0f)
		{
			const FVector Away = (Centre - User->GetActorLocation()).GetSafeNormal2D();
			Other->LaunchCharacter(Away * Blow.Force + FVector(0.0f, 0.0f, Blow.Force * 0.25f + Blow.Launch), true, true);
		}
	}
	return Hits;
}
