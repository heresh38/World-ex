#include "SOOperationBarrier.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Engine/World.h"
#include "SOOperation.h"
#include "SOSound.h"

ASOOperationBarrier::ASOOperationBarrier()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.05f;
	Block = CreateDefaultSubobject<UBoxComponent>(TEXT("Block"));
	Block->SetCollisionProfileName(TEXT("BlockAll"));
	Block->SetCanEverAffectNavigation(true);
	RootComponent = Block;
	Panel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Panel"));
	Panel->SetupAttachment(Block);
	Panel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Panel->SetCastShadow(false);
	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(Block);
	Light->SetLightColor(FLinearColor(0.6f, 0.35f, 1.0f));
	Light->SetIntensity(40.0f);
	Light->SetAttenuationRadius(1600.0f);
	Light->SetCastShadows(false);
}

void ASOOperationBarrier::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	ApplySize();
}

void ASOOperationBarrier::ApplySize()
{
	// loaded here, not in the constructor: a mesh the class default loads would pin its materials for the session
	if (!Panel->GetStaticMesh())
	{
		Panel->SetStaticMesh(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Shared/Operation/SM_MRK_barrier.SM_MRK_barrier"))).LoadSynchronous());
		if (UMaterialInterface* Energy = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/Shared/Operation/MI_SOEnergy_Barrier.MI_SOEnergy_Barrier"))).LoadSynchronous())
		{
			Panel->SetMaterial(0, Energy);
		}
	}
	// the actor sits at the barrier's middle; the panel rises from the box's foot
	Block->SetBoxExtent(FVector(40.0f, Width * 0.5f, Height * 0.5f));
	Panel->SetRelativeLocation(FVector(0.0f, 0.0f, -Height * 0.5f));
	Panel->SetRelativeScale3D(FVector(1.0f, Width / 100.0f, Height / 100.0f));
	Light->SetRelativeLocation(FVector(-150.0f, 0.0f, 0.0f));
}

void ASOOperationBarrier::SetOpen(bool bNewOpen)
{
	if (bOpen == bNewOpen)
	{
		return;
	}
	bOpen = bNewOpen;
	Block->SetCollisionEnabled(bOpen ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryAndPhysics);
	if (bOpen && HasActorBegunPlay())
	{
		USOSoundLibrary::PlayAt(this, TEXT("reliquary_open"), GetActorLocation(), 1.0f, 0.05f, ESOSoundRange::Far);
	}
}

void ASOOperationBarrier::BeginPlay()
{
	Super::BeginPlay();
	ApplySize();
}

void ASOOperationBarrier::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const ASOOperation* Op = ASOOperation::Get(this);
	bool bShouldOpen = false;
	if (Op)
	{
		const int32 At = Op->Stages.IndexOfByPredicate([this](const FSOStage& S) { return S.Id == OpensAt; });
		bShouldOpen = Op->GetState() == ESOOperationState::Complete || (At != INDEX_NONE && Op->GetStageIndex() >= At);
	}
	SetOpen(bShouldOpen);
	// the wall shimmers while it stands, and shrinks away into the ground when it falls
	Fade = FMath::FInterpTo(Fade, bOpen ? 0.0f : 1.0f, DeltaSeconds, 2.5f);
	const float T = GetWorld()->GetTimeSeconds();
	Panel->SetVisibility(Fade > 0.01f);
	Panel->SetRelativeScale3D(FVector(1.0f, Width / 100.0f, FMath::Max(Height / 100.0f * Fade, 0.01f)));
	Light->SetIntensity(Fade * (35.0f + 12.0f * FMath::Sin(T * 3.1f) + 6.0f * FMath::Sin(T * 7.7f)));
}
