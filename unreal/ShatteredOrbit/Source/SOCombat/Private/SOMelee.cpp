#include "SOMelee.h"

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

int32 USOMeleeLibrary::Land(ASOCombatCharacter* User, const FSOMeleeBlow& Blow)
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
		const float Reach = Blow.Range + Other->GetSimpleCollisionRadius();
		if (To.Size() > Reach || FVector::DotProduct(Forward, To.GetSafeNormal()) < MinDot)
		{
			continue;
		}
		// not through a wall (the world's static geometry only: the user's own gun on its back is not in the way)
		if (World->LineTraceTestByObjectType(Origin, Near, FCollisionObjectQueryParams(ECC_WorldStatic), Params))
		{
			continue;
		}
		float Dealt = 0.0f;
		{
			const FSOHitScope Where(TEXT("chest"), Near, To.GetSafeNormal(), false);
			Dealt = USOCombatStatics::ApplyDamage(User, Other, Blow.Damage * User->GetAbilityDamageScale(), false);
		}
		if (Dealt <= 0.0f)
		{
			continue;
		}
		++Hits;
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
		if (Blow.Force > 0.0f)
		{
			const FVector Away = (Centre - User->GetActorLocation()).GetSafeNormal2D();
			Other->LaunchCharacter(Away * Blow.Force + FVector(0.0f, 0.0f, Blow.Force * 0.25f), true, true);
		}
	}
	return Hits;
}
