#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "UObject/Interface.h"
#include "SOLootActors.generated.h"

class APawn;
class UPointLightComponent;
class UStaticMeshComponent;
class USOInventoryComponent;
class ASOCombatCharacter;

UINTERFACE(MinimalAPI)
class USOInteractable : public UInterface
{
	GENERATED_BODY()
};

/** Something the player can use with Interact (E / Y) when close and facing it. */
class SOCOMBAT_API ISOInteractable
{
	GENERATED_BODY()

public:
	/** The prompt line ("Open the Warden's reliquary", "Sealed"). */
	virtual FText GetInteractPrompt(const APawn* User) const = 0;
	virtual bool CanInteract(const APawn* User) const = 0;
	/** Server. */
	virtual void Interact(APawn* User) = 0;
	/** Interaction reach (cm). */
	virtual float GetInteractRange() const { return 260.0f; }
};

UENUM()
enum class ESOPickupKind : uint8
{
	Core, // a loot core: becomes a rolled weapon of its rarity
	Ammo
};

/**
 * A pickup on the ground (combat.js spawnPickup): a loot core glowing in its rarity colour (a light shaft for Rare and
 * up) or an ammo canister. Walking over it collects it (server): a core rolls a weapon of its rarity around the
 * player's power into the inventory, ammo tops up the equipped weapons. Gone after 90 s.
 */
UCLASS()
class SOCOMBAT_API ASOLootPickup : public AActor
{
	GENERATED_BODY()

public:
	ASOLootPickup();

	/** Server, before FinishSpawning. */
	void Setup(ESOPickupKind InKind, int32 InRarity, int32 InLevel);

	ESOPickupKind GetKind() const { return Kind; }
	int32 GetRarity() const { return Rarity; }

	/** Collects into this player's inventory (server). */
	void Collect(ASOCombatCharacter* Player, USOInventoryComponent* Inventory);

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	UFUNCTION()
	void OnRep_Look();
	void ApplyLook();

	UPROPERTY(ReplicatedUsing = OnRep_Look)
	ESOPickupKind Kind = ESOPickupKind::Core;

	UPROPERTY(ReplicatedUsing = OnRep_Look)
	int32 Rarity = 0;

	int32 Level = 10;

	UPROPERTY(VisibleAnywhere, Category = "SO|Loot")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, Category = "SO|Loot")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, Category = "SO|Loot")
	TObjectPtr<UPointLightComponent> Light;

	float Age = 0.0f;
	float BeamTimer = 0.0f;
	FVector Base = FVector::ZeroVector;
	bool bCollected = false;
};

/**
 * The VANTHOS reward pool in a box (operation.js openReliquary): sealed until opened with Interact, it then rolls
 * 2-3 weapons (Uncommon 22 / Rare 40 / Legendary 29 / Exotic 9, around the player's power) plus credits, alloy and
 * xp. bRearm reseals it after RearmTime (test range); in the operation it stays open.
 */
UCLASS()
class SOCOMBAT_API ASOReliquary : public AActor, public ISOInteractable
{
	GENERATED_BODY()

public:
	ASOReliquary();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Loot")
	bool bRearm = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Loot", meta = (Units = "s"))
	float RearmTime = 30.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SO|Loot")
	FString SourceName = TEXT("Spire reliquary");

	bool IsOpen() const { return bOpen; }
	/** The last roll (server). */
	const TArray<struct FSOWeaponInstance>& GetLastRewards() const;

	//~ ISOInteractable
	virtual FText GetInteractPrompt(const APawn* User) const override;
	virtual bool CanInteract(const APawn* User) const override;
	virtual void Interact(APawn* User) override;

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	UFUNCTION()
	void OnRep_Open();

	UPROPERTY(ReplicatedUsing = OnRep_Open)
	bool bOpen = false;

	UPROPERTY(VisibleAnywhere, Category = "SO|Loot")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, Category = "SO|Loot")
	TObjectPtr<UPointLightComponent> Light;

	float OpenedAt = -100.0f;
	float Glow = 0.0f;
	TArray<struct FSOWeaponInstance> LastRewards;
};

/**
 * Enemy drops (combat.js drop): when a hostile dies to a player, the killer earns credits and xp; 35 % of kills leave
 * ammo and 15 % a loot core (rarity rolled with the level). Server only.
 */
UCLASS()
class SOCOMBAT_API USOLootSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** Tests: force the next drops (-1 = roll). */
	float CoreChance = 0.15f;
	float AmmoChance = 0.35f;

	ASOLootPickup* SpawnPickup(const FVector& Location, ESOPickupKind Kind, int32 Rarity, int32 Level);

	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
	void OnDied(ASOCombatCharacter* Victim, AActor* Killer, UWorld* World);

	FDelegateHandle DiedHandle;
	FRandomStream Rng;
};

/** The inventory of the player controlling Pawn (on its player state), or null. */
SOCOMBAT_API USOInventoryComponent* SOFindInventory(const AActor* PawnOrController);
