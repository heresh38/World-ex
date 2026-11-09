#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SOOperationBarrier.generated.h"

class UBoxComponent;
class UPointLightComponent;
class UStaticMeshComponent;

/**
 * An energy wall that keeps an operation's route linear: it blocks the way until the stage OpensAt begins (or the
 * operation is complete), then falls. Every machine decides from the operation's replicated stage, so it needs no
 * replication of its own. The panel is the 1 x 1 m MRK_barrier piece scaled to Width x Height.
 */
UCLASS()
class SOOPERATION_API ASOOperationBarrier : public AActor
{
	GENERATED_BODY()

public:
	ASOOperationBarrier();

	/** The stage (its id in the plan) that opens it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation")
	FName OpensAt;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation", meta = (Units = "cm"))
	float Width = 1400.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SO|Operation", meta = (Units = "cm"))
	float Height = 800.0f;

	bool IsOpen() const { return bOpen; }

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	void ApplySize();
	void SetOpen(bool bNewOpen);

	UPROPERTY(VisibleAnywhere, Category = "SO|Operation")
	TObjectPtr<UBoxComponent> Block;

	UPROPERTY(VisibleAnywhere, Category = "SO|Operation")
	TObjectPtr<UStaticMeshComponent> Panel;

	UPROPERTY(VisibleAnywhere, Category = "SO|Operation")
	TObjectPtr<UPointLightComponent> Light;

	bool bOpen = false;
	float Fade = 1.0f;
};
