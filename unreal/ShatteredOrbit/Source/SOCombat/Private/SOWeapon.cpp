#include "SOWeapon.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatCharacter.h"
#include "SOCombatStatics.h"
#include "SOCombatTypes.h"
#include "SOGunRigComponent.h"
#include "SOFxSubsystem.h"
#include "SOLootLibrary.h"
#include "SOProjectileSubsystem.h"
#include "SOSound.h"
#include "SOWeaponData.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "TimerManager.h"

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
	DOREPLIFETIME(ASOWeapon, Instance);
	DOREPLIFETIME(ASOWeapon, Mag);
	DOREPLIFETIME(ASOWeapon, Reserve);
}

void ASOWeapon::SetData(USOWeaponData* InData)
{
	FSOWeaponInstance Plain;
	Plain.Uid = TEXT("plain");
	Plain.Archetype = InData ? InData->Archetype : NAME_None;
	Plain.Power = 0;
	Plain.Sight = InData ? InData->DefaultSight : FName(TEXT("default"));
	Data = InData;
	Instance = Plain;
	Stats = USOLootLibrary::ComputeStatsFor(Data, Instance);
	if (Data)
	{
		Mag = Stats.Mag;
		Reserve = Stats.Reserve;
	}
}

void ASOWeapon::SetInstance(const FSOWeaponInstance& InInstance)
{
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	Data = Tables ? Tables->LoadArchetype(InInstance.Archetype) : nullptr;
	Instance = InInstance;
	Stats = USOLootLibrary::ComputeStatsFor(Data, Instance);
	Mag = Instance.Mag >= 0 ? FMath::Min(Instance.Mag, Stats.Mag) : Stats.Mag;
	Reserve = Instance.Reserve >= 0 ? Instance.Reserve : Stats.Reserve;
}

void ASOWeapon::OnRep_Instance()
{
	Stats = USOLootLibrary::ComputeStatsFor(Data, Instance);
	if (HasActorBegunPlay())
	{
		BuildRigs();
	}
}

FVector ASOWeapon::GetSightLocation() const
{
	if (!Data)
	{
		return FVector::ZeroVector;
	}
	if (Data->bHasRail && Instance.Sight != TEXT("default") && !Instance.Sight.IsNone())
	{
		if (const USOLootTables* Tables = USOLootLibrary::GetTables())
		{
			if (const FSOSightInfo* Sight = Tables->FindSight(Instance.Sight); Sight && !Sight->Mesh.IsNull())
			{
				return Data->RailLocation + Sight->EyePoint;
			}
		}
	}
	return Data->SightLocation;
}

bool ASOWeapon::IsScoped() const
{
	if (!Data)
	{
		return false;
	}
	if (Instance.Sight == TEXT("default") || Instance.Sight.IsNone() || !Data->bHasRail)
	{
		return Data->bBuiltInScope;
	}
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	const FSOSightInfo* Sight = Tables ? Tables->FindSight(Instance.Sight) : nullptr;
	return Sight && Sight->bScope;
}

float ASOWeapon::GetShotInterval() const
{
	float Rpm = Stats.Rpm > 0.0f ? Stats.Rpm : (Data ? Data->RoundsPerMinute : 600.0f);
	if (Instance.HasPerk(TEXT("frenzy")))
	{
		if (const ASOCombatCharacter* Holder = GetHolder(); Holder && Holder->GetShield() <= 0.0f)
		{
			Rpm *= 1.2f; // Overclock: +20 % while the shield is down
		}
	}
	return 60.0f / FMath::Max(Rpm, 1.0f);
}

int32 ASOWeapon::GetRampageStacks() const
{
	const UWorld* World = GetWorld();
	return World && World->GetTimeSeconds() < RampageUntil ? RampageStacks : 0;
}

void ASOWeapon::BeginPlay()
{
	Super::BeginPlay();
	if (Stats.Mag <= 0)
	{
		Stats = USOLootLibrary::ComputeStatsFor(Data, Instance);
	}
	if (USOProjectileSubsystem* Rounds = GetWorld()->GetSubsystem<USOProjectileSubsystem>(); Rounds && HasAuthority())
	{
		HitHandle = Rounds->OnHit.AddUObject(this, &ASOWeapon::OnRoundHit);
	}
	BuildRigs();
	if (ASOCombatCharacter* Holder = GetHolder())
	{
		AttachToHolder(Holder);
	}
}

void ASOWeapon::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		if (USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>())
		{
			Rounds->OnHit.Remove(HitHandle);
		}
	}
	Super::EndPlay(EndPlayReason);
}

void ASOWeapon::OnRoundHit(const FSOProjectile& Round, const FHitResult& Hit, float Damage)
{
	ASOCombatCharacter* Holder = GetHolder();
	if (Round.Weapon.Get() != this || !Holder || Damage <= 0.0f)
	{
		return;
	}
	UWorld* World = GetWorld();
	const ASOCombatCharacter* Victim = Cast<ASOCombatCharacter>(Hit.GetActor());
	// Shrapnel Rounds: precision hits burst for 35 % of the damage around the target
	if (Instance.HasPerk(TEXT("explosive")) && USOProjectileSubsystem::IsPrecisionBone(Hit.BoneName))
	{
		if (USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>())
		{
			Rounds->ApplySplash(Holder, Hit.ImpactPoint, 250.0f, Stats.Damage * 0.35f, Hit.GetActor());
		}
	}
	if (Victim && Victim->IsDead())
	{
		if (Instance.HasPerk(TEXT("rampage")))
		{
			RampageStacks = FMath::Min(3, GetRampageStacks() + 1);
			RampageUntil = World->GetTimeSeconds() + 4.0f;
		}
		if (Instance.HasPerk(TEXT("vampire")))
		{
			Holder->Heal(Holder->GetMaxHealth() * 0.25f); // Siphon
		}
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
	FirstPersonRig->Dress(Instance);
	ThirdPersonRig->Dress(Instance);
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
		FirstPersonRig->SetShown(false);
	}
	if (USceneComponent* Hold = Holder->GetThirdPersonWeaponParent())
	{
		// Held guns: the holder places the gun and its body's arm IK reaches for the rig's grips.
		ThirdPersonRig->AttachToComponent(Hold, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
		return;
	}
	const FName Socket = Holder->GetThirdPersonWeaponSocket();
	USkeletalMeshComponent* Body = Holder->GetMesh();
	if (Body && Body->GetSkeletalMeshAsset() && Socket != NAME_None && Body->DoesSocketExist(Socket))
	{
		ThirdPersonRig->AttachToComponent(Body, FAttachmentTransformRules::SnapToTargetNotIncludingScale, Socket);
	}
}

void ASOWeapon::SetFirstPersonView(bool bFirstPerson)
{
	FirstPersonRig->SetShown(bFirstPerson);
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
	QueueShot(0.25f);
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
		QueueShot(0.25f);
	}
}

void ASOWeapon::QueueShot(float Window)
{
	const UWorld* World = GetWorld();
	const float Now = World ? World->GetTimeSeconds() : 0.0f;
	if (bReloading && !(Mag > 0 && Reload.IsInterruptible()))
	{
		return; // a click during a reload is not kept for after it (per-round reloads: it cuts the reload short)
	}
	bShotQueued = true;
	ShotQueuedUntil = Now + Window;
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
	const float HalfAngle = FMath::DegreesToRadians(Stats.Spread * Holder->GetSpreadScale());
	const int32 Seed = SpreadStream.RandHelper(0x7fffffff);
	TArray<FVector, TInlineAllocator<16>> Dirs;
	{
		TArray<FVector> Tmp;
		ShotDirections(Aim, Seed, HalfAngle, Tmp);
		Dirs.Append(Tmp);
	}
	const float Rampage = 1.0f + 0.15f * GetRampageStacks();
	USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>();
	for (const FVector& Dir : Dirs)
	{
		FSOProjectile Round;
		Round.Origin = Origin;
		Round.Position = Origin;
		Round.Velocity = Dir * Data->MuzzleVelocity * 100.0f;
		Round.Gravity = 980.0f * Data->GravityScale;
		Round.Damage = Stats.Damage * Rampage;
		Round.CritMultiplier = Stats.Crit;
		Round.FalloffStart = Stats.Range * 100.0f;
		Round.MinDamageScale = Data->MinDamageScale;
		Round.Instigator = Holder;
		Round.Weapon = this;
		Round.Splash = Data->Splash * 100.0f;
		Round.Dot = Data->Dot;
		Round.Swarm = Data->Swarm;
		const bool bGoo = Data->Projectile == ESOProjectileKind::Spit || Data->Projectile == ESOProjectileKind::Bile || Data->Projectile == ESOProjectileKind::Brood;
		Round.Pool = bGoo ? USOProjectileSubsystem::PoolSeconds : 0.0f;
		Round.Life = Data->Projectile == ESOProjectileKind::Round || Data->Projectile == ESOProjectileKind::Bolt ? 3.0f : 8.0f;
		if (Rounds)
		{
			Rounds->Fire(Round);
		}
	}
	USOCombatStatics::ReportNoise(this, Origin, Holder, 4500.0f);
	MulticastShotFired(Origin, Aim, Seed, HalfAngle);
}

void ASOWeapon::ShotDirections(const FVector& Aim, int32 Seed, float HalfAngle, TArray<FVector>& Out) const
{
	FRandomStream Rng(Seed);
	const int32 Pellets = Data ? FMath::Max(1, Data->Pellets) : 1;
	for (int32 i = 0; i < Pellets; ++i)
	{
		Out.Add(HalfAngle > 0.0f ? Rng.VRandCone(Aim, HalfAngle) : Aim);
	}
}

void ASOWeapon::MulticastShotFired_Implementation(FVector_NetQuantize Origin, FVector_NetQuantizeNormal Aim, int32 Seed, float HalfAngle)
{
	Reload.NotifyShot(Data ? Data->Archetype : NAME_None);
	if (!HasAuthority())
	{
		LastShotTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	}
	if (ASOCombatCharacter* Holder = GetHolder())
	{
		Holder->OnWeaponFired((Data ? Data->Kick : 1.0f) * Stats.Recoil);
	}
	PlayShotEffects(Origin, Aim, Seed, HalfAngle);
	OnWeaponEvent.Broadcast(TEXT("fired"));
}

void ASOWeapon::PlayShotEffects(const FVector& Origin, const FVector& Aim, int32 Seed, float HalfAngle)
{
	UWorld* World = GetWorld();
	ASOCombatCharacter* Holder = GetHolder();
	if (!World || !Holder || !Data || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const bool bFirstPerson = Holder->IsFirstPersonView() && FirstPersonRig->IsBuilt();
	FVector Muzzle = Origin + Aim * 60.0f;
	if (bFirstPerson)
	{
		Muzzle = Holder->ViewmodelToWorld(FirstPersonRig->GetMuzzleLocation());
	}
	else if (ThirdPersonRig->IsBuilt() && ThirdPersonRig->GetAttachParent())
	{
		Muzzle = ThirdPersonRig->GetMuzzleLocation();
	}
	USOFxSubsystem* Fx = World->GetSubsystem<USOFxSubsystem>();
	if (Fx)
	{
		Fx->MuzzleFlash(Muzzle, Aim, (bFirstPerson ? 0.7f : 1.0f) * (Data->Projectile == ESOProjectileKind::Rocket ? 1.8f : 1.0f));
	}

	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOShotFx), true, Holder);
	Params.AddIgnoredActor(this);
	const float Speed = Data->MuzzleVelocity * 100.0f;
	const float Gravity = 980.0f * Data->GravityScale;
	const ESOProjectileKind Kind = Data->Projectile;
	TArray<FVector> Dirs;
	ShotDirections(Aim, Seed, HalfAngle, Dirs);
	for (int32 Pellet = 0; Pellet < Dirs.Num(); ++Pellet)
	{
		const FVector Dir = Dirs[Pellet];
		// Where it lands (cosmetic: the same path the server's projectile takes; fast rounds without drop).
		FHitResult Hit;
		bool bHit = false;
		float Flight = 0.0f;
		FVector End = Origin + Dir * 30000.0f;
		if (Kind == ESOProjectileKind::Round || Kind == ESOProjectileKind::Bolt)
		{
			bHit = World->LineTraceSingleByChannel(Hit, Origin, End, SO_TRACE_BULLET, Params);
			End = bHit ? FVector(Hit.ImpactPoint) : End;
			Flight = FVector::Dist(Origin, End) / FMath::Max(Speed, 1.0f);
		}
		else
		{
			FVector P = Origin, V = Dir * Speed;
			for (float T = 0.0f; T < 8.0f; T += 0.02f)
			{
				const FVector Next = P + V * 0.02f + FVector(0, 0, -0.5f * Gravity * 0.0004f);
				V.Z -= Gravity * 0.02f;
				if (World->LineTraceSingleByChannel(Hit, P, Next, SO_TRACE_BULLET, Params))
				{
					bHit = true;
					End = Hit.ImpactPoint;
					Flight = T + 0.02f * (Hit.Distance / FMath::Max(FVector::Dist(P, Next), 1.0f));
					break;
				}
				P = Next;
				End = P;
				Flight = T;
			}
		}
		if (!Fx)
		{
			continue;
		}
		const ASOCombatCharacter* Victim = bHit ? Cast<ASOCombatCharacter>(Hit.GetActor()) : nullptr;
		const UPrimitiveComponent* Comp = bHit ? Hit.GetComponent() : nullptr;
		const bool bDecal = bHit && !Victim && Comp && (Comp->Mobility != EComponentMobility::Movable || Comp->GetCollisionObjectType() == ECC_WorldStatic);
		switch (Kind)
		{
		case ESOProjectileKind::Round:
		case ESOProjectileKind::Bolt:
		{
			const bool bEnergy = Kind == ESOProjectileKind::Bolt;
			if (Pellet < 4 || Pellet % 2 == 0) // shotguns: not every pellet needs its own tracer
			{
				Fx->Tracer(Muzzle, End, Speed, Data->TracerColor, bEnergy ? 3.2f : 2.2f);
			}
			if (bHit)
			{
				Fx->Impact(Hit.ImpactPoint, Hit.ImpactNormal, Victim != nullptr, Victim ? Victim->BloodColor : FLinearColor::Black, Flight, bDecal);
				if (bEnergy && !Victim)
				{
					Fx->Blast(Hit.ImpactPoint, Hit.ImpactNormal, 25.0f, USOFxSubsystem::EBlast::Zap, Data->TracerColor, Flight);
					if (Pellet == 0)
					{
						USOSoundLibrary::PlayAt(this, TEXT("bolt_impact"), Hit.ImpactPoint, 0.7f, 0.08f, ESOSoundRange::Near);
					}
				}
			}
			break;
		}
		case ESOProjectileKind::Rocket:
			Fx->Trail(Muzzle, (End - Muzzle).GetSafeNormal() * Speed, 0.0f, FVector::Dist(Muzzle, End) / FMath::Max(Speed, 1.0f), USOFxSubsystem::ETrail::Rocket, FLinearColor(1.0f, 0.6f, 0.25f));
			Fx->Blast(End, bHit ? FVector(Hit.ImpactNormal) : FVector::UpVector, Data->Splash * 100.0f, USOFxSubsystem::EBlast::Fire, FLinearColor(1.0f, 0.55f, 0.2f), Flight);
			if (bHit)
			{
				Fx->Impact(End, Hit.ImpactNormal, false, FLinearColor::Black, Flight, bDecal);
			}
			{
				TWeakObjectPtr<ASOWeapon> Self(this);
				FTimerHandle Boom;
				World->GetTimerManager().SetTimer(Boom, FTimerDelegate::CreateWeakLambda(this, [Self, End]()
				{
					if (Self.IsValid())
					{
						USOSoundLibrary::PlayAt(Self.Get(), TEXT("rocket_explode"), End, 1.0f, 0.05f, ESOSoundRange::Far);
					}
				}), FMath::Max(Flight, 0.01f), false);
			}
			break;
		default: // horror goo: arcs, splashes acid
		{
			const bool bBrood = Kind == ESOProjectileKind::Brood;
			const USOFxSubsystem::ETrail Trail = bBrood ? USOFxSubsystem::ETrail::Brood : (Kind == ESOProjectileKind::Bile ? USOFxSubsystem::ETrail::Bile : USOFxSubsystem::ETrail::Acid);
			Fx->Trail(Muzzle, Dir * Speed, Gravity, Flight, Trail, Data->TracerColor);
			if (bHit || Flight > 0.0f)
			{
				Fx->Blast(End, bHit ? FVector(Hit.ImpactNormal) : FVector::UpVector, FMath::Max(Data->Splash * 100.0f, 40.0f), USOFxSubsystem::EBlast::Acid, Data->TracerColor, Flight);
				FVector Floor, FloorNormal;
				if (USOProjectileSubsystem::FindFloor(World, End + (bHit ? FVector(Hit.ImpactNormal) * 5.0f : FVector::ZeroVector), Floor, FloorNormal))
				{
					Fx->Pool(Floor, FloorNormal, USOProjectileSubsystem::PoolRadius(Data->Splash * 100.0f), Data->TracerColor, Flight, USOProjectileSubsystem::PoolSeconds);
				}
			}
			if (Pellet == 0)
			{
				const FName Splat = bBrood ? FName(TEXT("brood_burst")) : FName(TEXT("goo_splat"));
				TWeakObjectPtr<ASOWeapon> Self(this);
				FTimerHandle Splash;
				World->GetTimerManager().SetTimer(Splash, FTimerDelegate::CreateWeakLambda(this, [Self, End, Splat]()
				{
					if (Self.IsValid())
					{
						USOSoundLibrary::PlayAt(Self.Get(), Splat, End, 0.9f, 0.08f, ESOSoundRange::Mid);
					}
				}), FMath::Max(Flight, 0.01f), false);
			}
			break;
		}
		}
	}
	const FName Prefix = Data->SoundPrefix;
	const bool bOwn = Holder->IsLocallyControlled() && Holder->IsPlayerControlled();
	const FName Sound(*FString::Printf(TEXT("%s_shot_%s"), *Prefix.ToString(), bOwn ? TEXT("fp") : TEXT("world")));
	USOSoundLibrary::PlayFor(Holder, Sound, Muzzle, bOwn ? 0.85f : 1.0f, ESOSoundRange::Far, 0.035f);
}

void ASOWeapon::PlayEventSound(FName Event)
{
	// reload.js sfx kinds -> sfx_synth.py sounds
	static const TMap<FName, FName> Sounds = {
		{ TEXT("reload"), TEXT("reload_start") }, { TEXT("magrelease"), TEXT("mag_release") }, { TEXT("drop"), TEXT("mag_out") },
		{ TEXT("pouch"), TEXT("pouch") }, { TEXT("magin"), TEXT("mag_in") }, { TEXT("slap"), TEXT("mag_slap") }, { TEXT("tap"), TEXT("mag_tap") },
		{ TEXT("magclatter"), TEXT("mag_clatter") }, { TEXT("rackback"), TEXT("rack_back") }, { TEXT("rackfwd"), TEXT("rack_fwd") },
		{ TEXT("slideback"), TEXT("slide_back") }, { TEXT("slidefwd"), TEXT("slide_fwd") }, { TEXT("latch"), TEXT("latch") },
		{ TEXT("cylopen"), TEXT("cyl_open") }, { TEXT("cylclose"), TEXT("cyl_close") }, { TEXT("eject"), TEXT("eject") },
		{ TEXT("speedload"), TEXT("speedload") }, { TEXT("shellin"), TEXT("shell_in") }, { TEXT("pumpback"), TEXT("pump_back") },
		{ TEXT("pumpfwd"), TEXT("pump_fwd") }, { TEXT("boltup"), TEXT("bolt_up") }, { TEXT("boltback"), TEXT("bolt_back") },
		{ TEXT("boltfwd"), TEXT("bolt_fwd") }, { TEXT("boltdown"), TEXT("bolt_down") }, { TEXT("roundin"), TEXT("round_in") },
		{ TEXT("hatchopen"), TEXT("hatch_open") }, { TEXT("hatchclose"), TEXT("hatch_close") }, { TEXT("bioin"), TEXT("bio_in") },
		{ TEXT("cellout"), TEXT("cell_out") }, { TEXT("cellin"), TEXT("cell_in") } };
	// the carbine and the compact SMG rack a charging handle, not a bolt
	const bool bCharge = Data && (Data->Archetype == TEXT("carbine") || Data->Archetype == TEXT("ksmg"));
	if (bCharge && (Event == TEXT("rackback") || Event == TEXT("rackfwd")))
	{
		Event = Event == TEXT("rackback") ? FName(TEXT("chargeback")) : FName(TEXT("chargefwd"));
	}
	static const TMap<FName, FName> Charge = { { TEXT("chargeback"), TEXT("charge_back") }, { TEXT("chargefwd"), TEXT("charge_fwd") } };
	const FName* Sound = Sounds.Find(Event);
	if (!Sound)
	{
		Sound = Charge.Find(Event);
	}
	ASOCombatCharacter* Holder = GetHolder();
	if (Sound && Holder)
	{
		USOSoundLibrary::PlayFor(Holder, *Sound, Holder->GetActorLocation(), 0.9f, ESOSoundRange::Near, 0.05f);
	}
}

// --- Reload ----------------------------------------------------------------------------------

bool ASOWeapon::CanReload() const
{
	return Data && !bReloading && Mag < Stats.Mag && Reserve > 0;
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
	MulticastReload(true, Mag <= 0, FMath::Min(Stats.Mag - Mag, Reserve));
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
	MulticastReload(false, false, 0);
}

void ASOWeapon::ServerCancelReload_Implementation()
{
	CancelReload();
}

void ASOWeapon::MulticastReload_Implementation(bool bStart, bool bEmpty, int32 Rounds)
{
	if (bStart)
	{
		BeginReloadLocal(bEmpty, Rounds);
	}
	else
	{
		Reload.Cancel();
		bReloading = false;
	}
}

void ASOWeapon::BeginReloadLocal(bool bEmpty, int32 Rounds)
{
	if (!Data)
	{
		return;
	}
	bReloading = true;
	// Whatever the trigger did before the reload is done with: no shot comes out of the gun after it unless the
	// trigger is pressed again.
	bShotQueued = false;
	bTriggerHeld = false;
	BurstLeft = 0;
	int32 LoopFrom, LoopTo;
	TArray<FSOReloadSegment> Segments = SOReload::BuildReload(Data->Archetype, Data->WeaponClass == ESOWeaponClass::Energy,
		Data->WeaponClass == ESOWeaponClass::Horror, bEmpty, Stats.Reload, Rounds, LoopFrom, LoopTo);
	Reload.Start(MoveTemp(Segments), LoopFrom, LoopTo);
	OnWeaponEvent.Broadcast(TEXT("reload"));
	PlayEventSound(TEXT("reload"));
}

void ASOWeapon::GrantAmmo()
{
	if (!Data)
	{
		return;
	}
	const int32 Take = FMath::Min(Stats.Mag - Mag, Reserve);
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
		if (bShotQueued && Now > ShotQueuedUntil)
		{
			bShotQueued = false; // a click is a request for now, not for whenever the gun is ready again
		}
		const bool bBurstRunning = BurstLeft > 0;
		if ((bTriggerHeld || bShotQueued || bBurstRunning) && !bReloading && Now >= NextShotTime && Holder->CanFireWeapon())
		{
			bShotQueued = false;
			if (Mag > 0)
			{
				FireShot();
				if (Data->Burst > 1)
				{
					// bursts: N rounds at the burst rate, then the trigger rate between bursts (data.js pulse)
					BurstLeft = bBurstRunning ? BurstLeft - 1 : Data->Burst - 1;
					NextShotTime = Now + (BurstLeft > 0 ? 60.0f / FMath::Max(Data->BurstRpm, 1.0f) : GetShotInterval());
				}
				else
				{
					NextShotTime = Now + GetShotInterval();
				}
				if (!Data->bAutomatic && BurstLeft <= 0)
				{
					bTriggerHeld = false;
				}
			}
			else if (bBurstRunning)
			{
				BurstLeft = 0;
			}
			else if (CanReload())
			{
				StartReload(); // dry trigger on an empty mag reloads
			}
		}
	}

	// Firing during a per-round reload (pump, bolt-action) cuts it short: the closing segment, then the shot.
	if (bReloading && (bTriggerHeld || bShotQueued) && Mag > 0 && Reload.IsInterruptible())
	{
		Reload.Interrupt();
		// the shot that cut the reload short comes right after the closing segment
		bShotQueued = true;
		ShotQueuedUntil = (World ? World->GetTimeSeconds() : 0.0f) + FMath::Max(0.0f, Reload.GetDuration() - Reload.GetElapsed()) + 0.2f;
	}
	Reload.SetSlideLock(Mag <= 0);

	TArray<FSOReloadEvent> Events;
	const bool bFinished = Reload.Update(DeltaSeconds, Events);
	const bool bPerRound = Data && (Data->Archetype == TEXT("pump") || Data->Archetype == TEXT("bolt"));
	for (const FSOReloadEvent& Event : Events)
	{
		if (Event.Name == TEXT("seat") && HasAuthority() && !bPerRound)
		{
			GrantAmmo();
		}
		else if (Event.Name == TEXT("grant") && HasAuthority() && Reserve > 0 && Mag < Stats.Mag)
		{
			++Mag;
			--Reserve;
		}
		else if (Event.Name == TEXT("drop"))
		{
			DropPart(Event.Arg == TEXT("loader") ? FName(TEXT("x_speedloader")) : FName(TEXT("mag")));
		}
		else if (Event.Name == TEXT("husk"))
		{
			DropPart(TEXT("biomass"));
		}
		const FName Name = Event.Name == TEXT("sfx") ? Event.Arg : Event.Name;
		OnWeaponEvent.Broadcast(Name);
		PlayEventSound(Name);
	}
	if (bFinished)
	{
		bReloading = false;
	}

	const FSOReloadPose& Pose = Reload.GetPose();
	FirstPersonRig->ApplyPose(Pose);
	ThirdPersonRig->ApplyPose(Pose);
}

void ASOWeapon::DropPart(FName Part)
{
	UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_DedicatedServer || !ThirdPersonRig->IsBuilt())
	{
		return;
	}
	const UStaticMeshComponent* Source = ThirdPersonRig->GetPart(Part);
	UStaticMesh* Mesh = Source ? Source->GetStaticMesh() : nullptr;
	if (!Mesh)
	{
		return;
	}
	// A small physics body the size of the part, carrying a copy of it; it falls, tumbles, rests and goes after 20 s.
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* Drop = World->SpawnActor<AActor>(AActor::StaticClass(), Source->GetComponentTransform(), Params);
	if (!Drop)
	{
		return;
	}
	const FBox Box = Mesh->GetBoundingBox();
	UBoxComponent* Body = NewObject<UBoxComponent>(Drop);
	Body->SetBoxExtent(Box.GetExtent().ComponentMax(FVector(0.6f)));
	Body->SetCollisionProfileName(TEXT("PhysicsActor"));
	Body->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Body->SetCollisionResponseToChannel(SO_TRACE_BULLET, ECR_Ignore);
	Drop->SetRootComponent(Body);
	Body->RegisterComponent();
	Body->SetWorldLocationAndRotation(Source->GetComponentTransform().TransformPosition(Box.GetCenter()), Source->GetComponentQuat());
	UStaticMeshComponent* Copy = NewObject<UStaticMeshComponent>(Drop);
	Copy->SetStaticMesh(Mesh);
	for (int32 i = 0; i < Source->GetNumMaterials(); ++i)
	{
		Copy->SetMaterial(i, Source->GetMaterial(i));
	}
	Copy->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Copy->SetupAttachment(Body);
	Copy->SetRelativeLocation(-Box.GetCenter());
	Copy->RegisterComponent();
	Body->SetSimulatePhysics(true);
	Body->SetMassOverrideInKg(NAME_None, 0.4f, true);
	const FVector Down = -Source->GetUpVector() * 120.0f + FVector(0, 0, -50.0f);
	Body->SetPhysicsLinearVelocity(Down + FMath::VRand() * 40.0f);
	Body->SetPhysicsAngularVelocityInDegrees(FMath::VRand() * 300.0f);
	Drop->SetLifeSpan(20.0f);
}
