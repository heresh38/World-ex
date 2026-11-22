#include "SOWeapon.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "SOCombatCharacter.h"
#include "SOAbilitySystemComponent.h"
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
	// (a gun rolled before the optics had rules can carry one its kind no longer takes: a long scope on an assault
	// rifle. It gets its factory sight back.)
	if (Data && !Data->Sights.Contains(Instance.Sight))
	{
		Instance.Sight = Data->DefaultSight;
	}
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
	if (Stats.Perks.FireRateShieldDown != 1.0f)
	{
		if (const ASOCombatCharacter* Holder = GetHolder(); Holder && Holder->GetShield() <= 0.0f)
		{
			Rpm *= Stats.Perks.FireRateShieldDown; // (Overclock: faster while the shield is down)
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
	// (Shrapnel Rounds: a precision hit bursts for a share of the damage round the target. A precision hit is the
	// victim's call: the head, or a boss's weak point.)
	const bool bPrecise = Victim ? Victim->PrecisionAt(Hit) > 0.0f : USOProjectileSubsystem::IsPrecisionBone(Hit.BoneName);
	if (Stats.Perks.PrecisionSplash > 0.0f && bPrecise)
	{
		if (USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>())
		{
			Rounds->ApplySplash(Holder, Hit.ImpactPoint, Stats.Perks.PrecisionSplashRadius, Stats.Damage * Stats.Perks.PrecisionSplash, Hit.GetActor());
		}
	}
	if (Stats.Perks.PrecisionBurn > 0.0f && bPrecise && Victim && !Victim->IsDead())
	{
		// (Tracer Core: a precision hit sets it burning)
		USOCombatStatics::ApplyStatus(Holder, Hit.GetActor(), SOTags::Status_Burn, FMath::Max(Stats.Perks.PrecisionBurnTime, 0.5f), Stats.Damage * Stats.Perks.PrecisionBurn);
	}
	if (Victim && Victim->IsDead())
	{
		LastKillTime = World->GetTimeSeconds();
		if (Stats.Perks.KillMagazine > 0.0f)
		{
			RefillFromReserve(Stats.Perks.KillMagazine); // (Spoils)
		}
		if (Stats.Perks.bKillShield)
		{
			if (USOAbilitySystemComponent* Abilities = Holder->GetSOAbilitySystem())
			{
				Abilities->RefillShieldNow(); // (Second Skin)
			}
		}
		if (Stats.Perks.KillDamage > 0.0f)
		{
			RampageStacks = FMath::Min(FMath::Max(Stats.Perks.KillDamageStacks, 1), GetRampageStacks() + 1); // (Rampage)
			RampageUntil = World->GetTimeSeconds() + Stats.Perks.KillDamageTime;
		}
		if (Stats.Perks.KillHeal > 0.0f)
		{
			Holder->Heal(Holder->GetMaxHealth() * Stats.Perks.KillHeal); // (Siphon)
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
	const FSOPerkInfo& Perk = Stats.Perks;
	// (Cold Bore: the first shot after a quiet spell hits harder and flies true)
	const bool bOpening = Perk.OpeningDamage != 1.0f && World->GetTimeSeconds() - LastShotTime >= Perk.OpeningAfter;
	--Mag;
	++ShotsFired;
	LastShotTime = World->GetTimeSeconds();

	const FVector Origin = Holder->GetAimOrigin();
	const FVector Aim = Holder->GetAimDirection().GetSafeNormal();
	const float HalfAngle = FMath::DegreesToRadians(Stats.Spread * Holder->GetSpreadScale() * (Holder->IsAimingDownSights() ? 1.0f : Perk.HipSpread)
		* (bOpening ? 0.1f : 1.0f));
	const int32 Seed = SpreadStream.RandHelper(0x7fffffff);
	TArray<FVector, TInlineAllocator<16>> Dirs;
	{
		TArray<FVector> Tmp;
		ShotDirections(Aim, Seed, HalfAngle, Tmp);
		Dirs.Append(Tmp);
	}
	float Rampage = (1.0f + Stats.Perks.KillDamage * GetRampageStacks()) * Holder->GetOutgoingDamageScale();
	Rampage *= bOpening ? Perk.OpeningDamage : 1.0f;
	Rampage *= Perk.LowMagDamage != 1.0f && Mag < Stats.Mag * Perk.LowMagShare ? Perk.LowMagDamage : 1.0f; // (Last Third: the rounds at the bottom)
	USOProjectileSubsystem* Rounds = World->GetSubsystem<USOProjectileSubsystem>();
	ShotHeat = Heat;                                                      // (a hot crystal throws its rounds faster)
	const float SpeedScale = HeatSpeedScale(ShotHeat);
	for (const FVector& Dir : Dirs)
	{
		FSOProjectile Round;
		Round.Origin = Origin;
		Round.Position = Origin;
		Round.Velocity = Dir * Data->MuzzleVelocity * 100.0f * SpeedScale;
		Round.Gravity = 980.0f * Data->GravityScale;
		Round.Damage = Stats.Damage * Rampage;
		Round.CritMultiplier = Stats.Crit;
		Round.FalloffStart = Stats.Range * 100.0f;
		Round.MinDamageScale = Perk.bNoFalloff ? 1.0f : Data->MinDamageScale;
		Round.ShieldScale = Perk.ShieldDamage;
		Round.HealthScale = Perk.HealthDamage;
		if (Perk.HitSlow < 1.0f && Perk.HitSlowTime > 0.0f)
		{
			Round.Status = SOTags::Status_Slow;
			Round.StatusDuration = Perk.HitSlowTime;
			Round.StatusMagnitude = Perk.HitSlow;
		}
		Round.Instigator = Holder;
		Round.Weapon = this;
		Round.Splash = Data->Splash * 100.0f;
		Round.Dot = Data->Dot;
		Round.Swarm = Data->Swarm;
		const bool bGoo = Data->Projectile == ESOProjectileKind::Spit || Data->Projectile == ESOProjectileKind::Bile || Data->Projectile == ESOProjectileKind::Brood;
		Round.Pool = bGoo ? USOProjectileSubsystem::PoolSeconds : 0.0f;
		const bool bFast = Data->Projectile == ESOProjectileKind::Round || Data->Projectile == ESOProjectileKind::Bolt || Data->Projectile == ESOProjectileKind::Slug;
		Round.Life = bFast ? 3.0f : 8.0f;
		if (Data->Projectile == ESOProjectileKind::Slug)
		{
			Round.Pierce = Data->Pierce;                                  // (its crystal goes on into the body)
			Round.PierceKeep = Data->PierceKeep;
		}
		if (Rounds)
		{
			Rounds->Fire(Round);
		}
	}
	USOCombatStatics::ReportNoise(this, Origin, Holder, 4500.0f * Perk.Noise);
	MulticastShotFired(Origin, Aim, Seed, HalfAngle);
	AddHeat();
}

bool ASOWeapon::HasHeat() const
{
	return Data && Data->HeatPerShot > 0.0f;
}

bool ASOWeapon::IsVenting() const
{
	return HasHeat() && GetWorld() && GetWorld()->GetTimeSeconds() < VentUntil;
}

float ASOWeapon::HeatSpeedScale(float H) const
{
	if (!HasHeat() || H < HeatHigh)
	{
		return 1.0f;
	}
	return FMath::Lerp(1.0f, Data->HeatSpeed, FMath::Clamp((H - HeatHigh) / (1.0f - HeatHigh), 0.0f, 1.0f));
}

float ASOWeapon::HeatBright(float H)
{
	return 1.0f + 0.8f * FMath::Clamp((H - HeatMedium) / (1.0f - HeatMedium), 0.0f, 1.0f);
}

void ASOWeapon::AddHeat()
{
	UWorld* World = GetWorld();
	if (!HasHeat() || !World)
	{
		return;
	}
	const float Now = World->GetTimeSeconds();
	Heat = FMath::Min(1.0f, Heat + Data->HeatPerShot);
	LastHeatTime = Now;
	if (Heat >= 1.0f && Now >= VentUntil)
	{
		// full: the crystal vents by itself (the gun cannot fire until it has); the heat runs out of it meanwhile
		StartVent();
	}
}

bool ASOWeapon::Condenses() const
{
	return Data && Data->RefillTime > 0.0f;
}

bool ASOWeapon::IsCondensing() const
{
	const UWorld* World = GetWorld();
	return Condenses() && World && Heat <= 0.0f && !IsVenting() && !bTriggerHeld && World->GetTimeSeconds() - LastShotTime > 0.25f
		&& Mag < Stats.Mag && Reserve > 0;
}

void ASOWeapon::StartVent()
{
	UWorld* World = GetWorld();
	if (!HasHeat() || !World)
	{
		return;
	}
	const float Now = World->GetTimeSeconds();
	if (Heat <= 0.02f || Now < VentUntil)
	{
		return;
	}
	// as long as the heat in it asks (a crystal half hot vents in half the time), never a blink
	VentFrom = Heat;
	VentLength = Data->VentTime * FMath::Clamp(Heat, 0.35f, 1.0f);
	VentUntil = Now + VentLength;
	PlayReloadFx(TEXT("vent"), VentLength);
	PlayEventSound(TEXT("vent"));
	OnWeaponEvent.Broadcast(TEXT("vent"));
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

void ASOWeapon::PredictShot()
{
	UWorld* World = GetWorld();
	ASOCombatCharacter* Holder = GetHolder();
	if (!Holder || !Data || !World)
	{
		return;
	}
	const bool bOpening = Stats.Perks.OpeningDamage != 1.0f && World->GetTimeSeconds() - LastShotTime >= Stats.Perks.OpeningAfter;
	--Mag; // (the server's count replaces it as it arrives)
	++ShotsFired;
	LastShotTime = World->GetTimeSeconds();
	const FVector Origin = Holder->GetAimOrigin();
	const FVector Aim = Holder->GetAimDirection().GetSafeNormal();
	const float HalfAngle = FMath::DegreesToRadians(Stats.Spread * Holder->GetSpreadScale() * (Holder->IsAimingDownSights() ? 1.0f : Stats.Perks.HipSpread)
		* (bOpening ? 0.1f : 1.0f));
	Reload.NotifyShot(Data->Archetype);
	Holder->OnWeaponFired(Data->Kick * Stats.Recoil);
	ShotHeat = Heat;
	PlayShotEffects(Origin, Aim, FMath::Rand(), HalfAngle); // its own draw of the spread: where the round went is the server's
	AddHeat();
	OnWeaponEvent.Broadcast(TEXT("fired"));
}

void ASOWeapon::MulticastShotFired_Implementation(FVector_NetQuantize Origin, FVector_NetQuantizeNormal Aim, int32 Seed, float HalfAngle)
{
	if (!HasAuthority())
	{
		if (const ASOCombatCharacter* Shooter = GetHolder(); Shooter && Shooter->IsLocallyControlled())
		{
			return; // shown when the trigger broke (PredictShot)
		}
	}
	Reload.NotifyShot(Data ? Data->Archetype : NAME_None);
	if (!HasAuthority())
	{
		LastShotTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	}
	if (ASOCombatCharacter* Holder = GetHolder())
	{
		Holder->OnWeaponFired((Data ? Data->Kick : 1.0f) * Stats.Recoil);
	}
	if (!HasAuthority())
	{
		ShotHeat = Heat; // (the server set its own as it fired)
	}
	PlayShotEffects(Origin, Aim, Seed, HalfAngle);
	if (!HasAuthority())
	{
		AddHeat();
	}
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
		// in the gun's own colour: a kinetic round burns orange, a bolt of light flashes the colour it flies in
		const bool bLight = Data->WeaponClass == ESOWeaponClass::Energy || Data->WeaponClass == ESOWeaponClass::Horror;
		const FLinearColor FlashColor = bLight ? FMath::Lerp(Data->TracerColor, FLinearColor::White, 0.25f) : FLinearColor(1.0f, 0.74f, 0.4f);
		const bool bThroughScope = bFirstPerson && IsScoped() && Holder->IsAimingDownSights();
		if (Data->Projectile == ESOProjectileKind::Slug)
		{
			// (the rails throw it: a hard white-gold flash, the amber field tearing off, nothing burning)
			Fx->SlugFlash(Muzzle, Aim, bFirstPerson ? 0.6f : 1.0f, bFirstPerson, HeatBright(ShotHeat), bThroughScope);
		}
		else if (Data->Projectile == ESOProjectileKind::Bolt)
		{
			// (a light gun burns nothing: no flame, no smoke: a bloom of its own light)
			Fx->PlasmaFlash(Muzzle, Aim, bFirstPerson ? 0.6f : 1.0f, bFirstPerson, FlashColor, bThroughScope);
		}
		else
		{
			// the flash of its kind of gun (the owner's guide: each kind its own)
			const FString Arch = Data->Archetype.ToString().ToLower();
			USOFxSubsystem::EFlash Style = USOFxSubsystem::EFlash::Rifle;
			if (Arch.Contains(TEXT("shotgun"))) { Style = USOFxSubsystem::EFlash::Shotgun; }
			else if (Arch.Contains(TEXT("rocket")) || Arch.Contains(TEXT("launcher")) || Arch.Contains(TEXT("cannon")) && !Arch.Contains(TEXT("handcannon"))) { Style = USOFxSubsystem::EFlash::Launcher; }
			else if (Arch.Contains(TEXT("sniper")) || Arch.Contains(TEXT("scout")) || Arch.Contains(TEXT("bolt")) || Arch.Contains(TEXT("lance"))) { Style = USOFxSubsystem::EFlash::Long; }
			else if (Arch.Contains(TEXT("hmg")) || Arch.Contains(TEXT("lmg")) || Arch.Contains(TEXT("heavy"))) { Style = USOFxSubsystem::EFlash::Heavy; }
			else if (Arch.Contains(TEXT("smg")) || Arch.Contains(TEXT("sidearm")) || Arch.Contains(TEXT("pistol")) || Arch.Contains(TEXT("handcannon")) || Arch.Contains(TEXT("revolver"))) { Style = USOFxSubsystem::EFlash::Short; }
			Fx->MuzzleFlash(Muzzle, Aim, (bFirstPerson ? 0.6f : 1.0f) * (Data->Projectile == ESOProjectileKind::Rocket ? 1.8f : 1.0f), bFirstPerson,
				FlashColor, bThroughScope, Style);
		}
		if (Data->Projectile == ESOProjectileKind::Round && Data->WeaponClass == ESOWeaponClass::Kinetic)
		{
			// the spent casing out of the ejection port on the receiver's right (found on the gun's own bounds: ahead
			// of the grip, on its right flank, high), landing on whatever floor is under it
			const USOGunRigComponent* R = bFirstPerson ? FirstPersonRig : ThirdPersonRig;
			const FBox B = R && R->IsBuilt() ? R->GetRigBounds() : FBox(FVector(-20.0f, -3.0f, -12.0f), FVector(40.0f, 3.0f, 10.0f));
			const FVector Local(B.Min.X + (B.Max.X - B.Min.X) * 0.42f, B.Max.Y + 0.5f, B.Min.Z + (B.Max.Z - B.Min.Z) * 0.62f);
			const FVector Port = RigPointToWorld(Local, bFirstPerson);
			const FVector Out = (RigPointToWorld(Local + FVector(0.0f, 1.0f, 0.0f), bFirstPerson) - Port).GetSafeNormal();
			const FVector Up = (RigPointToWorld(Local + FVector(0.0f, 0.0f, 1.0f), bFirstPerson) - Port).GetSafeNormal();
			FHitResult Floor;
			FCollisionQueryParams FloorParams(SCENE_QUERY_STAT(SOCasingFloor), false, Holder);
			FloorParams.AddIgnoredActor(this);
			const float FloorZ = World->LineTraceSingleByChannel(Floor, Port, Port - FVector(0.0f, 0.0f, 400.0f), ECC_Visibility, FloorParams)
				? static_cast<float>(Floor.ImpactPoint.Z) + 0.8f : static_cast<float>(Port.Z) - 400.0f;
			Fx->Casing(Port, Out, Up, Holder->GetVelocity(), FMath::Clamp(FMath::Sqrt(Data->Damage / 25.0f), 0.7f, 1.6f), FloorZ);
		}
	}

	FCollisionQueryParams Params(SCENE_QUERY_STAT(SOShotFx), true, Holder);
	Params.AddIgnoredActor(this);
	const float Speed = Data->MuzzleVelocity * 100.0f * HeatSpeedScale(ShotHeat);
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
		if (Kind == ESOProjectileKind::Round || Kind == ESOProjectileKind::Bolt || Kind == ESOProjectileKind::Slug)
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
			if (bEnergy)
			{
				// A light gun fires plasma: a bolt that is seen to fly, heavier guns throwing bigger ones, pellets small.
				const float BoltSize = FMath::Clamp(FMath::Sqrt(Data->Damage / 20.0f), 0.6f, 2.4f);
				Fx->PlasmaBolt(Muzzle, End, Speed, Data->TracerColor, BoltSize, Holder->GetVelocity());
				if (Pellet == 0)
				{
					++HeatShots;
					LastBoltTime = World->GetTimeSeconds();
				}
				if (bHit)
				{
					const bool bBody = Victim != nullptr;
					if (bBody && !Victim->TurnsBlow(Muzzle))
					{
						Fx->Impact(Hit.ImpactPoint, Hit.ImpactNormal, true, Victim->BloodColor, Flight, false); // (it burns its way in: the body bleeds)
					}
					Fx->PlasmaImpact(Hit.ImpactPoint, Hit.ImpactNormal, Data->TracerColor, BoltSize, Flight, bBody && !Victim->TurnsBlow(Muzzle));
					if (Pellet == 0 && !bBody)
					{
						USOSoundLibrary::PlayAt(this, TEXT("bolt_impact"), Hit.ImpactPoint, 0.7f, 0.08f, ESOSoundRange::Near);
					}
				}
				break;
			}
			if (Pellet < 4 || Pellet % 2 == 0) // shotguns: not every pellet needs its own tracer
			{
				// (a round is a thin short line)
				Fx->Tracer(Muzzle, End, Speed, Data->TracerColor, 2.0f, 340.0f, false);
			}
			if (bHit)
			{
				// (a blow that armour turns sparks and rings; one that goes in bleeds)
				Fx->Impact(Hit.ImpactPoint, Hit.ImpactNormal, Victim != nullptr && !Victim->TurnsBlow(Muzzle), Victim ? Victim->BloodColor : FLinearColor::Black, Flight, bDecal,
					USOFxSubsystem::SurfaceOf(Hit));
			}
			break;
		}
		case ESOProjectileKind::Slug:
		{
			// The Sarketh's: a slug seen to fly in its amber field; its shell ruptures where it lands and, in a body,
			// the crystal goes on through (the server's round does: Pierce) and out the far side
			const float Size = Data->RoundSize > 0.0f ? Data->RoundSize : FMath::Clamp(FMath::Sqrt(Data->Damage / 17.0f), 0.5f, 2.4f);
			const float Bright = HeatBright(ShotHeat);
			Fx->SlugRound(Muzzle, End, Speed, Size, Bright, Holder->GetVelocity());
			if (bHit)
			{
				const bool bBody = Victim != nullptr;
				const bool bIn = bBody && !Victim->TurnsBlow(Muzzle);
				if (bIn)
				{
					Fx->Impact(Hit.ImpactPoint, Hit.ImpactNormal, true, Victim->BloodColor, Flight, false);
				}
				Fx->SlugImpact(Hit.ImpactPoint, Hit.ImpactNormal, Size, Flight, bIn, Data->Splash * 100.0f);
				if (Pellet == 0)
				{
					USOSoundLibrary::PlayAt(this, TEXT("slug_impact"), Hit.ImpactPoint, 0.75f, 0.08f, ESOSoundRange::Near);
				}
				if (bIn && Data->Pierce > 0)
				{
					FCollisionQueryParams On(SCENE_QUERY_STAT(SOSlugOn), true, Holder);
					On.AddIgnoredActor(this);
					On.AddIgnoredActor(Victim);
					FHitResult Out;
					const FVector From = FVector(Hit.ImpactPoint) + Dir * 3.0f;
					FVector To = From + Dir * 20000.0f;
					const bool bOut = World->LineTraceSingleByChannel(Out, From, To, SO_TRACE_BULLET, On);
					To = bOut ? FVector(Out.ImpactPoint) : To;
					const float Later = Flight + FVector::Dist(From, To) / FMath::Max(Speed, 1.0f);
					Fx->SlugRound(From, To, Speed, Size * 0.7f, Bright, FVector::ZeroVector, Flight);
					if (bOut)
					{
						const ASOCombatCharacter* Next = Cast<ASOCombatCharacter>(Out.GetActor());
						Fx->SlugImpact(Out.ImpactPoint, Out.ImpactNormal, Size * 0.7f, Later, Next && !Next->TurnsBlow(Muzzle), 0.0f);
					}
				}
			}
			break;
		}
		case ESOProjectileKind::Rocket:
			// (in the set's colour: a light launcher's rocket burns its set's light, not a kinetic orange)
			Fx->Trail(Muzzle, (End - Muzzle).GetSafeNormal() * Speed, 0.0f, FVector::Dist(Muzzle, End) / FMath::Max(Speed, 1.0f), USOFxSubsystem::ETrail::Rocket, Data->TracerColor);
			Fx->Blast(End, bHit ? FVector(Hit.ImpactNormal) : FVector::UpVector, Data->Splash * 100.0f, USOFxSubsystem::EBlast::Fire, Data->TracerColor, Flight);
			if (bHit)
			{
				Fx->Impact(End, Hit.ImpactNormal, false, FLinearColor::Black, Flight, bDecal, USOFxSubsystem::SurfaceOf(Hit));
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

FVector ASOWeapon::RigPointToWorld(const FVector& RigLocal, bool bFirstPerson) const
{
	const USOGunRigComponent* Rig = bFirstPerson ? FirstPersonRig.Get() : ThirdPersonRig.Get();
	if (!Rig)
	{
		return RigLocal;
	}
	const FVector P = Rig->GetComponentTransform().TransformPosition(RigLocal);
	const ASOCombatCharacter* Holder = GetHolder();
	return bFirstPerson && Holder ? Holder->ViewmodelToWorld(P) : P;
}

void ASOWeapon::PlayReloadFx(FName Kind, float Seconds)
{
	UWorld* World = GetWorld();
	ASOCombatCharacter* Holder = GetHolder();
	USOFxSubsystem* Fx = World ? World->GetSubsystem<USOFxSubsystem>() : nullptr;
	if (!Fx || !Holder || !Data || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const bool bFirstPerson = Holder->IsFirstPersonView() && FirstPersonRig->IsBuilt();
	const USOGunRigComponent* Rig = bFirstPerson ? FirstPersonRig.Get() : ThirdPersonRig.Get();
	if (!Rig || !Rig->IsBuilt())
	{
		return;
	}
	auto ToWorld = [&](const FVector& P) { return bFirstPerson ? Holder->ViewmodelToWorld(P) : P; };
	const FTransform Frame = Rig->GetComponentTransform();
	const FVector Centre = ToWorld(Frame.TransformPosition(Rig->GetRigBounds().GetCenter()));
	// the flap faces out of the gun's LEFT flank (rig -Y), a little up
	const FVector Out = Frame.TransformVectorNoScale(FVector(0.0f, -1.0f, 0.3f)).GetSafeNormal();
	const UStaticMeshComponent* Flap = Rig->GetPart(TEXT("hatch"));
	const UStaticMeshComponent* Cell = Rig->GetPart(TEXT("mag"));
	const FVector AtFlap = Flap ? ToWorld(Flap->Bounds.Origin) + Out * 1.5f : Centre + Out * 3.0f;
	// the whole effect is HELD to the gun (FSOFxAnchor: the rig's centre, followed every frame), not sent off with the
	// holder's velocity of this moment: a turn, a stop or the viewmodel's sway left it hanging where the reload began
	const FVector Carry = FVector::ZeroVector;
	FSOFxAnchor Anchor;
	Anchor.Gun = this;
	Anchor.Local = Rig->GetRigBounds().GetCenter();
	Anchor.Last = Centre;
	Anchor.bViewmodel = bFirstPerson;
	const FLinearColor Color = Data->TracerColor;
	if (Kind == TEXT("vent"))
	{
		Fx->ReloadVent(AtFlap, Out, Color, Seconds, 1.0f, Carry, bFirstPerson, Anchor);
	}
	else if (Kind == TEXT("overheat"))
	{
		// (a gun without a flap breathes it out of its muzzle end)
		const FVector At = Flap ? AtFlap : ToWorld(Rig->GetMuzzleLocation());
		Fx->ReloadVent(At, Flap ? Out : Frame.GetUnitAxis(EAxis::X), Color, Seconds, 0.35f, Carry, bFirstPerson, Anchor);
	}
	else if (Kind == TEXT("intake"))
	{
		Fx->ReloadIntake(AtFlap, Out, Color, Seconds, Carry, bFirstPerson, Anchor);
	}
	else if (Kind == TEXT("cellpop"))
	{
		Fx->ReloadCellPop(Cell ? ToWorld(Cell->Bounds.Origin) : Centre, Color, Carry, bFirstPerson, Anchor);
	}
	else if (Kind == TEXT("charge"))
	{
		Fx->ReloadCharge(Centre, Color, Seconds, Carry, bFirstPerson, Anchor);
	}
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
		{ TEXT("cellout"), TEXT("cell_out") }, { TEXT("cellin"), TEXT("cell_in") },
		{ TEXT("cellpop"), TEXT("cell_pop") }, { TEXT("celllock"), TEXT("cell_lock") }, { TEXT("charge"), TEXT("light_charge") },
		{ TEXT("flapopen"), TEXT("flap_open") }, { TEXT("flapclose"), TEXT("flap_close") }, { TEXT("vent"), TEXT("light_vent") },
		{ TEXT("intake"), TEXT("light_intake") }, { TEXT("overheat"), TEXT("light_vent_small") } };
	// the carbine and the compact SMG rack a charging handle, not a bolt
	const FName Style = Data ? SOReload::GetStyle(Data->Archetype) : NAME_None;
	const bool bCharge = Style == TEXT("carbine") || Style == TEXT("ksmg");
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
		// The Void Requiem set has its own foley (crystal and void under the steel): vr_<sound> where one was made.
		FName Play = *Sound;
		if (Data && Data->SetId == TEXT("void_requiem"))
		{
			const FName Own(*(TEXT("vr_") + Play.ToString()));
			if (USOSoundLibrary::Find(Own))
			{
				Play = Own;
			}
		}
		USOSoundLibrary::PlayFor(Holder, Play, Holder->GetActorLocation(), 0.9f, ESOSoundRange::Near, 0.05f);
	}
}

// --- Reload ----------------------------------------------------------------------------------

bool ASOWeapon::CanReload() const
{
	return Data && !bReloading && Mag < Stats.Mag && Reserve > 0;
}

void ASOWeapon::StartReload()
{
	if (Condenses())
	{
		// nothing to load by hand: the key vents the crystal (here at once, on the server too), and the rounds
		// condense once it is cold
		StartVent();
		if (!HasAuthority())
		{
			ServerStartReload();
		}
		return;
	}
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
	// (Hot Hands: begun just after a kill, it is quicker)
	const bool bAfterKill = Stats.Perks.KillReload != 1.0f && GetWorld() && GetWorld()->GetTimeSeconds() - LastKillTime <= Stats.Perks.KillReloadTime;
	MulticastReload(true, Mag <= 0, FMath::Min(Stats.Mag - Mag, Reserve), bAfterKill ? Stats.Perks.KillReload : 1.0f);
}

int32 ASOWeapon::RefillFromReserve(float Share)
{
	if (!HasAuthority())
	{
		return 0;
	}
	const int32 Want = FMath::Max(1, FMath::RoundToInt(Stats.Mag * FMath::Clamp(Share, 0.0f, 1.0f)));
	const int32 In = FMath::Clamp(FMath::Min(Want, Stats.Mag - Mag), 0, FMath::Max(Reserve, 0));
	if (In <= 0)
	{
		return 0;
	}
	if (bReloading && Mag + In >= Stats.Mag)
	{
		CancelReload(); // (nothing left to load)
	}
	Mag += In;
	Reserve -= In;
	return In;
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
	MulticastReload(false, false, 0, 1.0f);
}

void ASOWeapon::ServerCancelReload_Implementation()
{
	CancelReload();
}

void ASOWeapon::MulticastReload_Implementation(bool bStart, bool bEmpty, int32 Rounds, float TimeScale)
{
	if (bStart)
	{
		BeginReloadLocal(bEmpty, Rounds, TimeScale);
	}
	else
	{
		Reload.Cancel();
		bReloading = false;
	}
}

void ASOWeapon::BeginReloadLocal(bool bEmpty, int32 Rounds, float TimeScale)
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
		Data->WeaponClass == ESOWeaponClass::Horror, bEmpty, Stats.Reload * FMath::Clamp(TimeScale, 0.2f, 2.0f), Rounds, LoopFrom, LoopTo);
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

	// The server fires. A joined player's own machine runs the same clock beside it, only to SHOW its shots at once
	// (PredictShot): waiting for the server's echo put every flash and kick a ping late, or lost it with a packet.
	const bool bPredict = !HasAuthority() && Holder && Holder->IsLocallyControlled();
	if ((HasAuthority() || bPredict) && Data && World && Holder && !Holder->IsDead())
	{
		const float Now = World->GetTimeSeconds();
		if (bShotQueued && Now > ShotQueuedUntil)
		{
			bShotQueued = false; // a click is a request for now, not for whenever the gun is ready again
		}
		const bool bBurstRunning = BurstLeft > 0;
		if ((bTriggerHeld || bShotQueued || bBurstRunning) && !bReloading && !IsVenting() && Now >= NextShotTime && Holder->CanFireWeapon())
		{
			bShotQueued = false;
			if (Mag > 0)
			{
				if (HasAuthority())
				{
					FireShot();
				}
				else
				{
					PredictShot();
				}
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
			else if (Condenses())
			{
				StartVent(); // (empty: vent, so the rounds can condense)
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
	const FName ReloadStyle = Data ? SOReload::GetStyle(Data->Archetype) : NAME_None;
	const bool bPerRound = ReloadStyle == TEXT("pump") || ReloadStyle == TEXT("bolt");
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
		else if (Event.Name == TEXT("fx"))
		{
			PlayReloadFx(Event.Arg, Event.Count / 1000.0f);
		}
		const FName Name = Event.Name == TEXT("sfx") ? Event.Arg : Event.Name;
		OnWeaponEvent.Broadcast(Name);
		PlayEventSound(Name);
	}
	if (bFinished)
	{
		bReloading = false;
	}

	// Thermal accumulation: while it vents the heat runs out of it; otherwise it cools once the trigger has rested.
	if (World && HasHeat())
	{
		const float Now = World->GetTimeSeconds();
		if (Now < VentUntil)
		{
			Heat = FMath::Clamp(VentFrom * (VentUntil - Now) / FMath::Max(VentLength, 0.01f), 0.0f, 1.0f);
		}
		else if (VentUntil > -50.0f && Now - VentUntil < 0.1f)
		{
			Heat = 0.0f;                                     // (a vent ends cold)
		}
		else if (Now - LastHeatTime > Data->HeatCoolDelay)
		{
			Heat = FMath::Max(0.0f, Heat - Data->HeatCool * DeltaSeconds);
		}
	}

	// The Sarketh's guns condense their rounds (the server's count is the one that counts; the others are told)
	if (World && HasAuthority() && Condenses())
	{
		if (IsCondensing())
		{
			RefillCarry += DeltaSeconds * Stats.Mag / FMath::Max(Data->RefillTime, 0.05f);
			const int32 In = FMath::Min3(FMath::FloorToInt(RefillCarry), Stats.Mag - Mag, Reserve);
			if (In > 0)
			{
				Mag += In;
				Reserve -= In;
				RefillCarry -= In;
			}
		}
		else
		{
			RefillCarry = 0.0f;
		}
	}

	// A light gun's heat: a long burst (half a cell, at least 8 bolts, never more than 40) vents by itself as the
	// trigger is let go (the owner, 2026-11-15: "some venting on overheating"); a short one cools unseen.
	if (World && HeatShots > 0 && World->GetTimeSeconds() - LastBoltTime > 0.22f)
	{
		if (HeatShots >= FMath::Clamp(Stats.Mag / 2, 8, 40) && !bReloading)
		{
			PlayReloadFx(TEXT("overheat"), 0.55f);
			PlayEventSound(TEXT("overheat"));
		}
		HeatShots = 0;
	}

	// A gun with a cluster of barrels (a part named `spin`) turns it while it fires: up to speed in a few shots, and
	// it runs down on its own afterwards.
	if (World)
	{
		const bool bFiring = World->GetTimeSeconds() - LastShotTime < 0.14f;
		BarrelSpinRate = FMath::FInterpTo(BarrelSpinRate, bFiring ? 26.0f : 0.0f, DeltaSeconds, bFiring ? 9.0f : 1.6f);
		BarrelSpin = FMath::Fmod(BarrelSpin + BarrelSpinRate * DeltaSeconds, UE_TWO_PI);
	}
	const FSOReloadPose& Pose = Reload.GetPose();
	for (USOGunRigComponent* Rig : { FirstPersonRig.Get(), ThirdPersonRig.Get() })
	{
		Rig->SetBarrelSpin(BarrelSpin);
		Rig->ApplyPose(Pose);
	}
}

void ASOWeapon::DropOnDeath(const FVector& HolderVelocity)
{
	if (bDropped)
	{
		return;
	}
	bDropped = true;
	UWorld* World = GetWorld();
	USceneComponent* Space = ThirdPersonRig->IsBuilt() ? ThirdPersonRig->GetGunSpace() : nullptr;
	if (World && Space && World->GetNetMode() != NM_DedicatedServer)
	{
		TArray<USceneComponent*> RigParts;
		Space->GetChildrenComponents(true, RigParts);
		TArray<UStaticMeshComponent*> Meshes;
		FBox Local(ForceInit);
		const FTransform Frame = ThirdPersonRig->GetComponentTransform();
		for (USceneComponent* Child : RigParts)
		{
			UStaticMeshComponent* Mesh = Cast<UStaticMeshComponent>(Child);
			if (Mesh && Mesh->GetStaticMesh() && Mesh->IsVisible())
			{
				Meshes.Add(Mesh);
				Local += Mesh->GetStaticMesh()->GetBoundingBox().TransformBy(Mesh->GetComponentTransform().GetRelativeTransform(Frame));
			}
		}
		if (Meshes.Num() > 0 && Local.IsValid)
		{
			// One body the size of the gun carrying copies of its visible parts; it tumbles out of the hands and rests.
			FActorSpawnParameters Params;
			Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			const FTransform At(Frame.GetRotation(), Frame.TransformPosition(Local.GetCenter()));
			AActor* Drop = World->SpawnActor<AActor>(AActor::StaticClass(), At, Params);
			if (Drop)
			{
				UBoxComponent* Body = NewObject<UBoxComponent>(Drop);
				Body->SetBoxExtent(Local.GetExtent().ComponentMax(FVector(1.5f)));
				Body->SetCollisionProfileName(TEXT("PhysicsActor"));
				Body->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
				Body->SetCollisionResponseToChannel(SO_TRACE_BULLET, ECR_Ignore);
				// (nor does it hide anything: falling out of the hands in front of the chest it stood between a dead
				// creature and the mate watching it go down, who then never saw it fall)
				Body->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
				Body->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
				Drop->SetRootComponent(Body);
				Body->RegisterComponent();
				Body->SetWorldTransform(At);
				const FTransform BodyFrame = Body->GetComponentTransform();
				for (UStaticMeshComponent* Source : Meshes)
				{
					UStaticMeshComponent* Copy = NewObject<UStaticMeshComponent>(Drop);
					Copy->SetStaticMesh(Source->GetStaticMesh());
					for (int32 i = 0; i < Source->GetNumMaterials(); ++i)
					{
						Copy->SetMaterial(i, Source->GetMaterial(i));
					}
					Copy->SetCollisionEnabled(ECollisionEnabled::NoCollision);
					Copy->SetCastShadow(true);
					Copy->SetupAttachment(Body);
					Copy->SetRelativeTransform(Source->GetComponentTransform().GetRelativeTransform(BodyFrame));
					Copy->RegisterComponent();
				}
				Body->SetSimulatePhysics(true);
				Body->SetMassOverrideInKg(NAME_None, 3.5f, true);
				Body->SetPhysicsLinearVelocity(HolderVelocity * 0.6f + FVector(0, 0, 60.0f) + FMath::VRand() * 60.0f);
				Body->SetPhysicsAngularVelocityInDegrees(FMath::VRand() * 180.0f);
				Drop->SetLifeSpan(30.0f);
			}
		}
	}
	FirstPersonRig->SetShown(false);
	ThirdPersonRig->SetShown(false);
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
