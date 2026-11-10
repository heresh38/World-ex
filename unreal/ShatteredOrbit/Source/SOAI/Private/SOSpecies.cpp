#include "SOSpecies.h"

#include "Components/CapsuleComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "NavigationSystem.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOLog.h"
#include "UObject/UObjectIterator.h"

namespace
{
	/** Every class that names itself a species. Built once: the classes are native and all there once the module is. */
	const TMap<FName, TSubclassOf<ASOEnemy>>& Registry()
	{
		static TMap<FName, TSubclassOf<ASOEnemy>> Map;
		static bool bBuilt = false;
		if (!bBuilt)
		{
			bBuilt = true;
			for (TObjectIterator<UClass> It; It; ++It)
			{
				UClass* Class = *It;
				if (!Class->IsChildOf(ASOEnemy::StaticClass()) || Class->HasAnyClassFlags(CLASS_Abstract | CLASS_NewerVersionExists))
				{
					continue;
				}
				const FName Id = Class->GetDefaultObject<ASOEnemy>()->SpeciesId;
				const UClass* Parent = Class->GetSuperClass();
				const bool bInherited = Parent && Parent->IsChildOf(ASOEnemy::StaticClass()) && Parent->GetDefaultObject<ASOEnemy>()->SpeciesId == Id;
				if (Id.IsNone() || bInherited)
				{
					continue;
				}
				if (const TSubclassOf<ASOEnemy>* Other = Map.Find(Id))
				{
					UE_LOG(LogShatteredOrbit, Error, TEXT("Species '%s' is claimed by %s and %s"), *Id.ToString(), *(*Other)->GetName(), *Class->GetName());
					continue;
				}
				Map.Add(Id, Class);
			}
		}
		return Map;
	}
}

FSOSpeciesVariant FSOSpeciesVariant::Over(const FSOSpeciesVariant& Base) const
{
	FSOSpeciesVariant Out = *this;
	Out.Health *= Base.Health;
	Out.Damage *= Base.Damage;
	Out.Speed *= Base.Speed;
	Out.AimError *= Base.AimError;
	Out.Sight *= Base.Sight;
	if (Out.Weapon.IsNone())
	{
		Out.Weapon = Base.Weapon;
	}
	if (Out.DisplayName.IsEmpty())
	{
		Out.DisplayName = Base.DisplayName;
	}
	return Out;
}

FSOSpeciesVariant FSOSpeciesVariant::FromJson(FName Id, const TSharedPtr<FJsonObject>& Object)
{
	FSOSpeciesVariant V;
	V.Id = Id;
	if (!Object)
	{
		return V;
	}
	FString Text;
	if (Object->TryGetStringField(TEXT("species"), Text))
	{
		V.Species = FName(Text);
	}
	if (Object->TryGetStringField(TEXT("name"), Text))
	{
		V.DisplayName = FText::FromString(Text);
	}
	if (Object->TryGetStringField(TEXT("weapon"), Text))
	{
		V.Weapon = FName(Text);
	}
	Object->TryGetNumberField(TEXT("health"), V.Health);
	Object->TryGetNumberField(TEXT("damage"), V.Damage);
	Object->TryGetNumberField(TEXT("speed"), V.Speed);
	Object->TryGetNumberField(TEXT("aim"), V.AimError);
	Object->TryGetNumberField(TEXT("sight"), V.Sight);
	return V;
}

TSubclassOf<ASOEnemy> USOSpeciesLibrary::Find(FName Species)
{
	const TSubclassOf<ASOEnemy>* Class = Registry().Find(Species);
	return Class ? *Class : nullptr;
}

TArray<FName> USOSpeciesLibrary::GetSpecies()
{
	TArray<FName> Out;
	Registry().GetKeys(Out);
	Out.Sort(FNameLexicalLess());
	return Out;
}

FSOOnEnemySpawned& USOSpeciesLibrary::OnSpawned()
{
	static FSOOnEnemySpawned Delegate;
	return Delegate;
}

ASOEnemy* USOSpeciesLibrary::Spawn(UWorld* World, FName Species, const FVector& Feet, float Yaw, const FSOSpawnOptions& Options)
{
	const TSubclassOf<ASOEnemy> Class = Find(Species);
	if (!World || !Class)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("Species: there is no '%s'"), *Species.ToString());
		return nullptr;
	}
	const ASOEnemy* Cdo = Class->GetDefaultObject<ASOEnemy>();
	const float Half = Cdo->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	const float Radius = Cdo->GetCapsuleComponent()->GetScaledCapsuleRadius();
	UNavigationSystemV1* Nav = Options.bOnNav ? FNavigationSystem::GetCurrent<UNavigationSystemV1>(World) : nullptr;
	const bool bNav = Nav && Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate);
	// Each try lands on the nav mesh (a floor it can walk from, never inside a wall or a heap) and only where its
	// capsule fits; later tries step out round the point.
	const int32 Tries = Options.bNeedsRoom ? 10 : 1;
	for (int32 Try = 0; Try < Tries; ++Try)
	{
		const float Angle = Options.Index * 2.39996f + Try * 1.1f;
		FVector At = Feet + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * (Try * Radius * 2.2f);
		if (bNav)
		{
			FNavLocation OnNav;
			if (!Nav->ProjectPointToNavigation(At, OnNav, FVector(300.0f, 300.0f, 500.0f)))
			{
				continue;
			}
			At = OnNav.Location;
		}
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = Options.bNeedsRoom ? ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding
			: ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
		Params.bDeferConstruction = true;
		const FTransform Where(FRotator(0.0f, Yaw, 0.0f), At + FVector(0.0f, 0.0f, Half + 5.0f));
		ASOEnemy* Enemy = World->SpawnActor<ASOEnemy>(*Class, Where, Params);
		if (!Enemy)
		{
			continue;
		}
		if (Options.Variant)
		{
			Enemy->ApplyVariant(*Options.Variant);                    // before it begins play: it arms itself with the variant's gun
		}
		Enemy->FinishSpawning(Where);
		if (!Enemy->GetController())
		{
			Enemy->SpawnDefaultController();
		}
		if (ASOEnemyAIController* AI = Cast<ASOEnemyAIController>(Enemy->GetController()))
		{
			AI->bHunter = Options.bHunter;
		}
		OnSpawned().Broadcast(Enemy);
		return Enemy;
	}
	return nullptr;
}

void USOSpeciesLibrary::Preload(FName Species, const FSOSpeciesVariant* Variant, TArray<UObject*>& OutHeld)
{
	if (const TSubclassOf<ASOEnemy> Class = Find(Species))
	{
		Class->GetDefaultObject<ASOEnemy>()->LoadSpeciesContent(Variant ? Variant->Weapon : FName(), OutHeld);
	}
}
