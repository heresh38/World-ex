#include "SOWeapon.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOGunRigComponent.h"
#include "SOFxSubsystem.h"
#include "SOProjectileSubsystem.h"
#include "SOSound.h"
#include "SOWeaponData.h"

ASOWeapon::ASOWeapon()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	bReplicates = true;
	SetReplicatingMovement(false);
	SetNetUpdateFrequency(30.0f);

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	FirstPersonRig = CreateDefaultSubobject<USOGunRigComponent>(TEXT("FirstPersonRig"));
	FirstPersonRig->SetupAttachment(Root);
	ThirdPersonRig = CreateDefaultSubobject<USOGunRigComponent>(TEXT("ThirdPersonRig"));
	ThirdPersonRig->SetupAttachment(Root);
	SpreadStream.Initialize(0x5EED);
}

void ASOWeapon::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASOWeapon, Data);
	DOREPLIFETIME(ASOWeapon, Mag);
	DOREPLIFETIME(ASOWeapon, Reserve);
}

void ASOWeapon::SetData(USOWeaponData* InData)
{
	Data = InData;
	if (Data)
	{
		Mag = Data->MagazineSize;
		Reserve = Data->ReserveAmmo;
	}
}

void ASOWeapon::BeginPlay()
{
	Super::BeginPlay();
	BuildRigs();
	if (ASOCombatCharacter* Holder = GetHolder())
	{
		AttachToHolder(Holder);
	}
}

void ASOWeapon::OnRep_Data()
{
	if (HasActorBegunPlay())
	{
		BuildRigs();
		if (ASOCombatCharacter* Holder = GetHolder())
		{
			AttachToHolder(Holder);
		}
	}
}

void ASOWeapon::BuildRigs()
{
	if (!Data)
	{
		return;
	}
	FirstPersonRig->Build(Data, true);
	ThirdPersonRig->Build(Data, false);
}

ASOCombatCharacter* ASOWeapon::GetHolder() const
{
	return Cast<ASOCombatCharacter>(GetOwner());
}

void ASOWeapon::AttachToHolder(ASOCombatCharacter* Holder)
{
	if (!Holder)
	{
		return;
	}
	AttachToActor(Holder, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
	if (USceneComponent* Viewmodel = Holder->GetFirstPersonWeaponParent())
	{
		FirstPersonRig->AttachToComponent(Viewmodel, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
	}
	else
	{
		FirstPersonRig->SetVisibility(false, true);
	}
	const FName Socket = Holder->GetThirdPersonWeaponSocket();
	USkeletalMeshComponent* Body = Holder->GetMesh();
	if (Body && Body->GetSkeletalMeshAsset() && Socket != NAME_None && Body->DoesSocketExist(Socket))
	{
		// The grip follows the hand; the barrel follows the aim (no hand-to-grip calibration needed yet).
		ThirdPersonRig->AttachToComponent(Body, FAttachmentTransformRules::SnapToTargetNotIncludingScale, Socket);
		ThirdPersonRig->SetUsingAbsoluteRotation(true);
	}
}

void ASOWeapon::SetFirstPersonView(bool bFirstPerson)
{
	FirstPersonRig->SetVisibility(bFirstPerson, true);
	ThirdPersonRig->SetOwnerNoSeeAll(bFirstPerson);
}

// --- Trigger ---------------------------------------------------------------------------------

void ASOWeapon::StartFire()
{
	if (!HasAuthority())
	{
		ServerSetTrigger(true);
	}
	bTriggerHeld = true;
	bShotQueued = true;
	// Click on an empty gun with nothing left to load.
	UWorld* World = GetWorld();
	if (World && Mag <= 0 && Reserve <= 0 && World->GetTimeSeconds() - LastDryFireTime > 0.2f)
	{
		LastDryFireTime = World->GetTimeSeconds();
		USOSoundLibrary::PlayFor(GetHolder(), TEXT("dry_fire"), GetActorLocation(), 0.9f, ESOSoundRange::Near);
	}
}

void ASOWeapon::StopFire()
{
	if (!HasAuthority())
	{
		ServerSetTrigger(false);
	}
	bTriggerHeld = false;
}

void ASOWeapon::ServerSetTrigger_Implementation(bool bHeld)
{
	bTriggerHeld = bHeld;
	if (bHeld)
	{
		bShotQueued = true;
	}
}

void ASOWeapon::FireShot()
{
	ASOCombatCharacter* Holder = GetHolder();
	UWorld* World = GetWorld();
	if (!Holder || !Data || !World)
	{
		return;
	}
	--Mag;
	++ShotsFired;
	LastShotTime = World->GetTimeSeconds();

	const FVector Origin = Holder->GetAimOrigin();
	const FVector Aim = Holder->GetAimDirection().GetSafeNormal();
	const float HalfAngle = FMath::DegreesToRadians(Data->Spread * Holder->GetSpreadScale());
	const FVector Dir = HalfAngle > 0.0f ? SpreadStream.VRandCone(Aim, HalfAngle) : Aim;

	FSOProjectile Round;
	Round.Origin = Origin;
	Round.Position = Origin;
	Round.Velocity = Dir * Data->MuzzleVelocity * 100.0f;
	Round.Gravity = 980.0f * Data->GravityScale;
	Round.Damage = Data->Damage;
	Round.CritMultiplier = Data->CritMultiplier;
	Round.FalloffStart = Data->Range * 100.0f;
	Round.MinDamageScale = Data->MinDamageScale;
	Round.Instigator = Holder;
	if (USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>())
	{
		Rounds->Fire(Round);
	}
	USOCombatStatics::ReportNoise(this, Origin, Holder, 4500.0f);
	MulticastShotFired(Origin, Dir);
}

void ASOWeapon::MulticastShotFired_Implementation(FVector_NetQuantize Origin, FVector_NetQuantizeNormal Dir)
{
	Reload.NotifyShot();
	if (!HasAuthority())
	{
		LastShotTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	}
	if (ASOCombatCharacter* Holder = GetHolder())
	{
		Holder->OnWeaponFired(Data ? Data->Kick : 1.0f);
	}
	PlayShotEffects(Origin, Dir);
	OnWeaponEvent.Broadcast(TEXT("fired"));
}

void ASOWeapon::PlayShotEffects(const FVector& Origin, const FVector& Dir)
{
	UWorld* World = GetWorld();
	ASOCombatCharacter* Holder = GetHolder();
	if (!World || !Holder || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const bool bFirstPerson = Holder->IsFirstPersonView() && FirstPersonRig->IsBuilt();
	FVector Muzzle = Origin + Dir * 60.0f;
	if (bFirstPerson)
	{
		Muzzle = Holder->ViewmodelToWorld(FirstPersonRig->GetMuzzleLocation());
	}
	else if (ThirdPersonRig->IsBuilt() && ThirdPersonRig->GetAttachParent())
	{
		Muzzle = ThirdPersonRig->GetMuzzleLocation();
	}

	// Where the round lands (cosmetic: the same ray the server's round takes, without drop).
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOShotFx), true, Holder);
	Params.AddIgnoredActor(this);
	FHitResult Hit;
	const float Reach = 30000.0f;
	const bool bHit = World->LineTraceSingleByChannel(Hit, Origin, Origin + Dir * Reach, SO_TRACE_BULLET, Params);
	const FVector End = bHit ? FVector(Hit.ImpactPoint) : Origin + Dir * Reach;
	const float Speed = (Data ? Data->MuzzleVelocity : 700.0f) * 100.0f;

	if (USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>())
	{
		Fx->MuzzleFlash(Muzzle, (End - Muzzle).GetSafeNormal(), bFirstPerson ? 0.7f : 1.0f);
		Fx->Tracer(Muzzle, End, Speed);
		if (bHit)
		{
			const ASOCombatCharacter* Victim = Cast<ASOCombatCharacter>(Hit.GetActor());
			const UPrimitiveComponent* Comp = Hit.GetComponent();
			const bool bDecal = !Victim && Comp && Comp->Mobility != EComponentMobility::Movable;
			Fx->Impact(Hit.ImpactPoint, Hit.ImpactNormal, Victim != nullptr, Victim ? Victim->BloodColor : FLinearColor::Black,
				FVector::Dist(Origin, Hit.ImpactPoint) / Speed, bDecal || (Comp && Comp->GetCollisionObjectType() == ECC_WorldStatic));
		}
	}
	const FName Prefix = Data ? Data->SoundPrefix : FName(TEXT("rifle"));
	const bool bOwn = Holder->IsLocallyControlled() && Holder->IsPlayerControlled();
	const FName Sound(*FString::Printf(TEXT("%s_shot_%s"), *Prefix.ToString(), bOwn ? TEXT("fp") : TEXT("world")));
	USOSoundLibrary::PlayFor(Holder, Sound, Muzzle, bOwn ? 0.85f : 1.0f, ESOSoundRange::Far, 0.035f);
}

void ASOWeapon::PlayEventSound(FName Event)
{
	static const TMap<FName, FName> Sounds = {
		{ TEXT("reload"), TEXT("reload_start") }, { TEXT("magrelease"), TEXT("mag_release") }, { TEXT("drop"), TEXT("mag_out") },
		{ TEXT("pouch"), TEXT("pouch") }, { TEXT("magin"), TEXT("mag_in") }, { TEXT("slap"), TEXT("mag_slap") },
		{ TEXT("rackback"), TEXT("rack_back") }, { TEXT("rackfwd"), TEXT("rack_fwd") } };
	const FName* Sound = Sounds.Find(Event);
	ASOCombatCharacter* Holder = GetHolder();
	if (Sound && Holder)
	{
		USOSoundLibrary::PlayFor(Holder, *Sound, Holder->GetActorLocation(), 0.9f, ESOSoundRange::Near, 0.05f);
	}
}

// --- Reload ----------------------------------------------------------------------------------

bool ASOWeapon::CanReload() const
{
	return Data && !bReloading && Mag < Data->MagazineSize && Reserve > 0;
}

void ASOWeapon::StartReload()
{
	if (!HasAuthority())
	{
		ServerStartReload();
		return;
	}
	if (!CanReload())
	{
		return;
	}
	const ASOCombatCharacter* Holder = GetHolder();
	if (Holder && Holder->IsDead())
	{
		return;
	}
	bReloading = true;
	MulticastReload(true, Mag <= 0);
}

void ASOWeapon::ServerStartReload_Implementation()
{
	StartReload();
}

void ASOWeapon::CancelReload()
{
	if (!bReloading && !Reload.IsActive())
	{
		return;
	}
	if (!HasAuthority())
	{
		ServerCancelReload();
		return;
	}
	bReloading = false;
	MulticastReload(false, false);
}

void ASOWeapon::ServerCancelReload_Implementation()
{
	CancelReload();
}

void ASOWeapon::MulticastReload_Implementation(bool bStart, bool bEmpty)
{
	if (bStart)
	{
		BeginReloadLocal(bEmpty);
	}
	else
	{
		Reload.Cancel();
		bReloading = false;
	}
}

void ASOWeapon::BeginReloadLocal(bool bEmpty)
{
	if (!Data)
	{
		return;
	}
	bReloading = true;
	Reload.Start(SOReload::BuildMagReload(Data->Archetype, bEmpty, Data->ReloadTime));
	OnWeaponEvent.Broadcast(TEXT("reload"));
	PlayEventSound(TEXT("reload"));
}

void ASOWeapon::GrantAmmo()
{
	if (!Data)
	{
		return;
	}
	const int32 Take = FMath::Min(Data->MagazineSize - Mag, Reserve);
	Mag += Take;
	Reserve -= Take;
}

// --- Tick ------------------------------------------------------------------------------------

void ASOWeapon::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UWorld* World = GetWorld();
	ASOCombatCharacter* Holder = GetHolder();

	if (HasAuthority() && Data && World && Holder && !Holder->IsDead())
	{
		const float Now = World->GetTimeSeconds();
		if ((bTriggerHeld || bShotQueued) && !bReloading && Now >= NextShotTime && Holder->CanFireWeapon())
		{
			bShotQueued = false;
			if (Mag > 0)
			{
				FireShot();
				NextShotTime = Now + Data->GetShotInterval();
				if (!Data->bAutomatic)
				{
					bTriggerHeld = false;
				}
			}
			else if (CanReload())
			{
				StartReload(); // dry trigger on an empty mag reloads
			}
		}
	}

	TArray<FSOReloadEvent> Events;
	const bool bFinished = Reload.Update(DeltaSeconds, Events);
	for (const FSOReloadEvent& Event : Events)
	{
		if (Event.Name == TEXT("seat") && HasAuthority())
		{
			GrantAmmo();
		}
		const FName Name = Event.Name == TEXT("sfx") ? Event.Arg : Event.Name;
		OnWeaponEvent.Broadcast(Name);
		PlayEventSound(Name);
	}
	if (bFinished)
	{
		bReloading = false;
	}

	if (Holder && ThirdPersonRig->IsUsingAbsoluteRotation())
	{
		ThirdPersonRig->SetWorldRotation(Holder->GetAimDirection().Rotation());
	}

	const FSOReloadPose& Pose = Reload.GetPose();
	FirstPersonRig->ApplyPose(Pose);
	ThirdPersonRig->ApplyPose(Pose);
}
