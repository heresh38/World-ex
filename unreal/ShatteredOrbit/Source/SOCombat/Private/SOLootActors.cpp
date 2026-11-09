#include "SOLootActors.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerState.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOFxSubsystem.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOSound.h"
#include "SOWeapon.h"

namespace
{
	const TCHAR* CoreMesh = TEXT("/Game/Props/Loot/SM_PR_core.SM_PR_core");
	const TCHAR* AmmoMesh = TEXT("/Game/Props/Loot/SM_PR_ammo.SM_PR_ammo");
	const TCHAR* ReliquaryMesh = TEXT("/Game/Props/Reliquary/SM_VX_reliquary.SM_VX_reliquary");

	FLinearColor RarityColor(int32 Rarity)
	{
		const USOLootTables* Tables = USOLootLibrary::GetTables();
		return Tables ? Tables->GetRarity(Rarity).Color : FLinearColor::White;
	}

	/** Recolours every slot whose material name starts with Prefix (material names are an API). */
	void TintSlots(UStaticMeshComponent* Mesh, const TCHAR* Prefix, const FLinearColor& Color, float Emissive)
	{
		const TArray<FName> Slots = Mesh->GetMaterialSlotNames();
		for (int32 i = 0; i < Slots.Num(); ++i)
		{
			if (!Slots[i].ToString().StartsWith(Prefix))
			{
				continue;
			}
			if (UMaterialInstanceDynamic* MID = Mesh->CreateDynamicMaterialInstance(i))
			{
				MID->SetVectorParameterValue(TEXT("BaseColorTint"), Color);
				MID->SetVectorParameterValue(TEXT("EmissiveColor"), Color);
				MID->SetScalarParameterValue(TEXT("EmissiveStrength"), Emissive);
			}
		}
	}
}

USOInventoryComponent* SOFindInventory(const AActor* Actor)
{
	const APawn* Pawn = Cast<APawn>(Actor);
	const AController* Controller = Pawn ? Pawn->GetController() : Cast<AController>(Actor);
	const APlayerState* PS = Pawn ? Pawn->GetPlayerState() : (Controller ? Controller->PlayerState.Get() : nullptr);
	return PS ? PS->FindComponentByClass<USOInventoryComponent>() : nullptr;
}

// --- Pickup ----------------------------------------------------------------------------------------

ASOLootPickup::ASOLootPickup()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = true;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetCastShadow(false);
	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(Mesh);
	Light->SetIntensityUnits(ELightUnits::Candelas);
	Light->SetIntensity(18.0f);
	Light->SetAttenuationRadius(260.0f);
	Light->SetCastShadows(false);
	InitialLifeSpan = 90.0f;
}

void ASOLootPickup::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASOLootPickup, Kind);
	DOREPLIFETIME(ASOLootPickup, Rarity);
}

void ASOLootPickup::Setup(ESOPickupKind InKind, int32 InRarity, int32 InLevel)
{
	Kind = InKind;
	Rarity = FMath::Clamp(InRarity, 0, 4);
	Level = InLevel;
}

void ASOLootPickup::BeginPlay()
{
	Super::BeginPlay();
	Base = GetActorLocation();
	ApplyLook();
	if (Kind == ESOPickupKind::Core)
	{
		USOSoundLibrary::PlayAt(this, TEXT("loot_drop"), Base, 0.5f + Rarity * 0.12f, 0.02f, ESOSoundRange::Mid);
	}
}

void ASOLootPickup::OnRep_Look()
{
	ApplyLook();
}

void ASOLootPickup::ApplyLook()
{
	const bool bCore = Kind == ESOPickupKind::Core;
	Mesh->SetStaticMesh(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(bCore ? CoreMesh : AmmoMesh)).LoadSynchronous());
	const FLinearColor Color = bCore ? RarityColor(Rarity) : FLinearColor::White;
	TintSlots(Mesh, bCore ? TEXT("core_glow") : TEXT("ammo_glow"), Color, bCore ? 9.0f : 4.0f);
	Light->SetLightColor(Color);
	Light->SetIntensity(bCore ? 14.0f + Rarity * 8.0f : 6.0f);
	Mesh->SetRelativeLocation(FVector(0, 0, bCore ? CoreRest : 0.0f));
}

void ASOLootPickup::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Age += DeltaSeconds;
	// it drops in from where the creature fell and settles with one small bounce, then lies on the ground
	const float Rest = Kind == ESOPickupKind::Core ? CoreRest : 0.0f;
	const float T = Age / 0.42f;
	const float Drop = T < 1.0f ? DropHeight * (1.0f - T * T) : (T < 1.5f ? 9.0f * FMath::Sin((T - 1.0f) * 2.0f * UE_PI) : 0.0f);
	Mesh->SetRelativeLocation(FVector(0, 0, Rest + FMath::Max(Drop, 0.0f)));
	UWorld* World = GetWorld();
	if (Kind == ESOPickupKind::Core)
	{
		Mesh->SetRelativeRotation(FRotator(0.0f, Age * 40.0f, 0.0f));
		// light shaft for Rare and up (VFX: rising streaks in the rarity colour)
		BeamTimer -= DeltaSeconds;
		if (Rarity >= 2 && BeamTimer <= 0.0f && World && World->GetNetMode() != NM_DedicatedServer)
		{
			BeamTimer = 0.12f;
			if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
			{
				FSOFxParticle P;
				P.Kind = ESOFxKind::Streak;
				P.Position = Mesh->GetComponentLocation() + FVector(FMath::FRandRange(-6.0f, 6.0f), FMath::FRandRange(-6.0f, 6.0f), 20.0f);
				P.Axis = FVector::UpVector;
				P.Velocity = FVector(0, 0, 500.0f);
				P.Life = 1.2f;
				P.Length = 260.0f;
				P.Size0 = 9.0f + Rarity * 2.0f;
				P.Size1 = 3.0f;
				P.Intensity0 = 6.0f + Rarity * 2.0f;
				P.Intensity1 = 0.0f;
				P.Color = RarityColor(Rarity);
				Fx->Spawn(P);
			}
		}
	}
	// collect (server): walk over it
	if (!HasAuthority() || bCollected || !World)
	{
		return;
	}
	for (TActorIterator<ASOCombatCharacter> It(World); It; ++It)
	{
		ASOCombatCharacter* Player = *It;
		if (Player->IsDead() || !Player->IsPlayerControlled())
		{
			continue;
		}
		const FVector D = Player->GetActorLocation() - GetActorLocation();
		if (D.Size2D() < 160.0f && FMath::Abs(D.Z) < 220.0f)
		{
			if (USOInventoryComponent* Inventory = SOFindInventory(Player))
			{
				Collect(Player, Inventory);
				return;
			}
		}
	}
}

void ASOLootPickup::Collect(ASOCombatCharacter* Player, USOInventoryComponent* Inventory)
{
	if (bCollected || !Inventory)
	{
		return;
	}
	bCollected = true;
	if (Kind == ESOPickupKind::Ammo)
	{
		ASOWeapon* Held = Player ? Player->GetWeapon() : nullptr;
		if (Held)
		{
			Inventory->StoreAmmo(Held->GetInstance().Uid, Held->GetMag(), Held->GetReserve());
		}
		Inventory->AddAmmoPickup();
		if (Held)
		{
			if (const FSOWeaponInstance* W = Inventory->Find(Held->GetInstance().Uid))
			{
				Held->SetAmmo(Held->GetMag(), W->Reserve);
			}
		}
		USOSoundLibrary::PlayFor(Player, TEXT("ammo_pickup"), GetActorLocation(), 0.8f, ESOSoundRange::Near);
	}
	else
	{
		// combat.js collect: power around the player's (+4 for Legendary and up), any archetype, rolled perks / sight
		FRandomStream Rng(FMath::Rand());
		const int32 Power = FMath::Max(1, Inventory->GetPower() + FMath::RoundToInt((Rng.FRand() - 0.3f) * 6.0f) + (Rarity >= 3 ? 4 : 0));
		FSORollOptions Options;
		Options.Rarity = Rarity;
		Inventory->AddWeapon(USOLootLibrary::RollWeapon(Power, Options, Rng));
		USOSoundLibrary::PlayFor(Player, *FString::Printf(TEXT("loot_pickup_%d"), Rarity), GetActorLocation(), 0.85f, ESOSoundRange::Near);
	}
	Destroy();
}

// --- Reliquary -------------------------------------------------------------------------------------

ASOReliquary::ASOReliquary()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = true;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	Mesh->SetCollisionProfileName(TEXT("BlockAll"));
	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(Mesh);
	Light->SetRelativeLocation(FVector(0, 0, 120.0f));
	Light->SetIntensityUnits(ELightUnits::Candelas);
	Light->SetAttenuationRadius(500.0f);
	Light->SetCastShadows(false);
	Light->SetLightColor(FLinearColor(1.0f, 0.62f, 0.25f));
}

void ASOReliquary::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASOReliquary, bOpen);
}

const TArray<FSOWeaponInstance>& ASOReliquary::GetLastRewards() const
{
	return LastRewards;
}

void ASOReliquary::BeginPlay()
{
	Super::BeginPlay();
	if (!Mesh->GetStaticMesh())
	{
		Mesh->SetStaticMesh(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(ReliquaryMesh)).LoadSynchronous());
	}
	OnRep_Open();
}

FText ASOReliquary::GetInteractPrompt(const APawn* User) const
{
	return bOpen ? NSLOCTEXT("SO", "ReliquaryOpen", "Emptied  ·  it reseals soon") : NSLOCTEXT("SO", "ReliquarySealed", "Open the reliquary");
}

bool ASOReliquary::CanInteract(const APawn* User) const
{
	return !bOpen;
}

void ASOReliquary::Interact(APawn* User)
{
	USOInventoryComponent* Inventory = SOFindInventory(User);
	if (!HasAuthority() || bOpen || !Inventory)
	{
		return;
	}
	bOpen = true;
	OpenedAt = GetWorld()->GetTimeSeconds();
	FRandomStream Rng(FMath::Rand());
	LastRewards = USOLootLibrary::RollReliquary(Inventory->GetPower(), Rng, SourceName);
	for (const FSOWeaponInstance& W : LastRewards)
	{
		Inventory->AddWeapon(W);
	}
	Inventory->AddCredits(900 + Inventory->GetLevel() * 30);
	Inventory->AddAlloy(10 + FMath::RandRange(0, 8));
	Inventory->AddXp(1800);
	OnRep_Open();
}

void ASOReliquary::OnRep_Open()
{
	if (bOpen && HasActorBegunPlay())
	{
		const FVector Top = GetActorLocation() + FVector(0, 0, 110.0f);
		USOSoundLibrary::PlayAt(this, TEXT("reliquary_open"), Top, 1.0f, 0.0f, ESOSoundRange::Mid);
		if (USOFxSubsystem* Fx = GetWorld()->GetSubsystem<USOFxSubsystem>())
		{
			Fx->Blast(Top, FVector::UpVector, 90.0f, USOFxSubsystem::EBlast::Zap, FLinearColor(1.0f, 0.7f, 0.3f));
		}
		Glow = 1.0f;
	}
}

void ASOReliquary::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	// the seal glows and breathes while sealed, flares when opened, goes dim while empty
	const float T = GetWorld()->GetTimeSeconds();
	Glow = FMath::Max(0.0f, Glow - DeltaSeconds * 0.5f);
	const float Breath = bOpen ? 0.15f : 0.6f + 0.25f * FMath::Sin(T * 1.6f);
	Light->SetIntensity(40.0f * Breath + 600.0f * Glow);
	if (HasAuthority() && bOpen && bRearm && T - OpenedAt > RearmTime)
	{
		bOpen = false;
	}
}

// --- Drops -----------------------------------------------------------------------------------------

bool USOLootSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void USOLootSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	Rng.GenerateNewSeed();
	DiedHandle = USOCombatStatics::OnCharacterDied().AddUObject(this, &USOLootSubsystem::OnDied);
}

void USOLootSubsystem::Deinitialize()
{
	USOCombatStatics::OnCharacterDied().Remove(DiedHandle);
	Super::Deinitialize();
}

ASOLootPickup* USOLootSubsystem::SpawnPickup(const FVector& Location, ESOPickupKind Kind, int32 Rarity, int32 Level)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return nullptr;
	}
	// on the ground under the spot, scattered a little: the world only (bodies, the dead included, and pickups are
	// not ground), traced far enough down from any height a creature can die at
	FVector At = Location + FVector(Rng.FRandRange(-50.0f, 50.0f), Rng.FRandRange(-50.0f, 50.0f), 0.0f);
	FHitResult Ground;
	FCollisionObjectQueryParams World3D;
	World3D.AddObjectTypesToQuery(ECC_WorldStatic);
	World3D.AddObjectTypesToQuery(ECC_WorldDynamic);
	const FCollisionQueryParams GroundParams(SCENE_QUERY_STAT(SOLootGround), true);
	if (World->LineTraceSingleByObjectType(Ground, At + FVector(0, 0, 60.0f), At - FVector(0, 0, 6000.0f), World3D, GroundParams))
	{
		At = Ground.ImpactPoint;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.bDeferConstruction = true;
	ASOLootPickup* Pickup = World->SpawnActor<ASOLootPickup>(ASOLootPickup::StaticClass(), FTransform(At), Params);
	if (Pickup)
	{
		Pickup->Setup(Kind, Rarity, Level);
		Pickup->FinishSpawning(FTransform(At));
	}
	return Pickup;
}

void USOLootSubsystem::OnDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World)
{
	if (World != GetWorld() || !Victim || Victim->Faction == ESOFaction::Player || !Victim->bDropsLoot || World->GetNetMode() == NM_Client)
	{
		return;
	}
	USOInventoryComponent* Inventory = SOFindInventory(Killer);
	if (!Inventory)
	{
		return;
	}
	const int32 Level = FMath::Max(1, Inventory->GetPower());
	Inventory->AddCredits(FMath::RoundToInt(8.0f + Rng.FRand() * 10.0f + Level * 2.0f));
	Inventory->AddXp(60);
	const FVector At = Victim->GetActorLocation();
	if (Rng.FRand() < AmmoChance)
	{
		SpawnPickup(At, ESOPickupKind::Ammo, 0, Level);
	}
	const int32 Rarity = USOLootLibrary::RollKillDrop(Level, false, Rng, CoreChance);
	if (Rarity >= 0)
	{
		SpawnPickup(At, ESOPickupKind::Core, Rarity, Level);
	}
}
