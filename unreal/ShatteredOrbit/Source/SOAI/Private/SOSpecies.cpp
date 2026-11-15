#include "SOSpecies.h"

#include "Components/CapsuleComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "NavigationSystem.h"
#include "SOEnemy.h"
#include "SOEnemyAIController.h"
#include "SOLog.h"
#include "SODifficulty.h"
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
	if (Out.Kit.IsNone())
	{
		Out.Kit = Base.Kit;
	}
	if (Out.Boss.IsNone())
	{
		Out.Boss = Base.Boss;
	}
	Out.Burst *= Base.Burst;
	Out.BurstPause *= Base.BurstPause;
	Out.Range *= Base.Range;
	Out.bSuppressor |= Base.bSuppressor;
	Out.bLikesHigh |= Base.bLikesHigh;
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
	if (Object->TryGetStringField(TEXT("kit"), Text))
	{
		V.Kit = FName(Text);
	}
	if (Object->TryGetStringField(TEXT("boss"), Text))
	{
		V.Boss = FName(Text);
	}
	Object->TryGetNumberField(TEXT("health"), V.Health);
	Object->TryGetNumberField(TEXT("damage"), V.Damage);
	Object->TryGetNumberField(TEXT("speed"), V.Speed);
	Object->TryGetNumberField(TEXT("aim"), V.AimError);
	Object->TryGetNumberField(TEXT("sight"), V.Sight);
	Object->TryGetNumberField(TEXT("burst"), V.Burst);
	Object->TryGetNumberField(TEXT("burstPause"), V.BurstPause);
	Object->TryGetNumberField(TEXT("range"), V.Range);
	Object->TryGetBoolField(TEXT("suppressor"), V.bSuppressor);
	Object->TryGetBoolField(TEXT("high"), V.bLikesHigh);
	return V;
}

bool FSONumbers::Key(const FProperty* Property, const UClass* Base, FString& OutKey)
{
	const UClass* Owner = Property->GetOwnerClass();
	if (!Owner || !Owner->IsChildOf(Base) || !Property->HasAnyPropertyFlags(CPF_Edit))
	{
		return false;
	}
	OutKey = Property->GetName();
	if (CastField<FBoolProperty>(Property) && OutKey.Len() > 1 && OutKey[0] == TEXT('b') && FChar::IsUpper(OutKey[1]))
	{
		OutKey.RightChopInline(1);
	}
	OutKey[0] = FChar::ToLower(OutKey[0]);
	return true;
}

void FSONumbers::Get(const UObject* Object, const UClass* Base, TMap<FName, float>& Out)
{
	for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
	{
		const FProperty* Property = *It;
		FString Name;
		if (!Key(Property, Base, Name))
		{
			continue;
		}
		if (const FFloatProperty* Float = CastField<FFloatProperty>(Property))
		{
			Out.Add(*Name, Float->GetPropertyValue_InContainer(Object));
		}
		else if (const FBoolProperty* Bool = CastField<FBoolProperty>(Property))
		{
			Out.Add(*Name, Bool->GetPropertyValue_InContainer(Object) ? 1.0f : 0.0f);
		}
		else if (const FIntProperty* Int = CastField<FIntProperty>(Property))
		{
			Out.Add(*Name, static_cast<float>(Int->GetPropertyValue_InContainer(Object)));
		}
		else if (const FStructProperty* Struct = CastField<FStructProperty>(Property); Struct && Struct->Struct == TBaseStructure<FVector2D>::Get())
		{
			const FVector2D* Range = Struct->ContainerPtrToValuePtr<FVector2D>(Object);
			Out.Add(*(Name + TEXT("Min")), static_cast<float>(Range->X));
			Out.Add(*(Name + TEXT("Max")), static_cast<float>(Range->Y));
		}
	}
}

int32 FSONumbers::Apply(UObject* Object, const UClass* Base, const TMap<FName, float>& Numbers)
{
	int32 Set = 0;
	for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
	{
		FProperty* Property = *It;
		FString Name;
		if (!Key(Property, Base, Name))
		{
			continue;
		}
		if (FStructProperty* Struct = CastField<FStructProperty>(Property))
		{
			if (Struct->Struct == TBaseStructure<FVector2D>::Get())
			{
				FVector2D* Range = Struct->ContainerPtrToValuePtr<FVector2D>(Object);
				if (const float* Min = Numbers.Find(*(Name + TEXT("Min"))))
				{
					Range->X = *Min;
					++Set;
				}
				if (const float* Max = Numbers.Find(*(Name + TEXT("Max"))))
				{
					Range->Y = *Max;
					++Set;
				}
			}
			continue;
		}
		const float* Value = Numbers.Find(*Name);
		if (!Value)
		{
			continue;
		}
		if (FFloatProperty* Float = CastField<FFloatProperty>(Property))
		{
			Float->SetPropertyValue_InContainer(Object, *Value);
			++Set;
		}
		else if (FBoolProperty* Bool = CastField<FBoolProperty>(Property))
		{
			Bool->SetPropertyValue_InContainer(Object, *Value > 0.5f);
			++Set;
		}
		else if (FIntProperty* Int = CastField<FIntProperty>(Property))
		{
			Int->SetPropertyValue_InContainer(Object, FMath::RoundToInt(*Value));
			++Set;
		}
	}
	return Set;
}

const TMap<FName, float>* USOSpeciesTable::Find(FName Id) const
{
	for (const FSOSpeciesNumbers& Entry : Species)
	{
		if (Entry.Species == Id)
		{
			return &Entry.Numbers;
		}
	}
	return nullptr;
}

const USOSpeciesTable& USOSpeciesTable::Get()
{
	static TWeakObjectPtr<const USOSpeciesTable> Loaded;
	if (!Loaded.IsValid())
	{
		// (kept for good: a small table read at every spawn)
		if (USOSpeciesTable* Table = Cast<USOSpeciesTable>(FSoftObjectPath(TEXT("/Game/Data/DA_Species.DA_Species")).TryLoad()))
		{
			Table->AddToRoot();
			Loaded = Table;
		}
	}
	return Loaded.IsValid() ? *Loaded : *GetDefault<USOSpeciesTable>();
}

TMap<FName, float> USOSpeciesLibrary::GetClassNumbers(FName Species)
{
	TMap<FName, float> Out;
	if (const TSubclassOf<ASOEnemy> Class = Find(Species))
	{
		const ASOEnemy* Creature = Class->GetDefaultObject<ASOEnemy>();
		Creature->GetNumbers(Out);
		// and its brain's senses (not "hunter": that is a spawn's choice)
		if (const UClass* BrainClass = Creature->AIControllerClass; BrainClass && BrainClass->IsChildOf(ASOEnemyAIController::StaticClass()))
		{
			FSONumbers::Get(BrainClass->GetDefaultObject(), ASOEnemyAIController::StaticClass(), Out);
			Out.Remove(TEXT("hunter"));
		}
	}
	return Out;
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
		// the level's dressing, and the difficulty level's share of health and damage on top of it
		const FSODifficulty& Level = USODifficultySubsystem::Get(World);
		const bool bLevelScales = !FMath::IsNearlyEqual(Level.Health, 1.0f) || !FMath::IsNearlyEqual(Level.Damage, 1.0f);
		if (Options.Variant || bLevelScales)
		{
			FSOSpeciesVariant Dressed = Options.Variant ? *Options.Variant : FSOSpeciesVariant();
			Dressed.Health *= Level.Health;
			Dressed.Damage *= Level.Damage;
			Enemy->ApplyVariant(Dressed);                             // before it begins play: it arms itself with the variant's gun
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
