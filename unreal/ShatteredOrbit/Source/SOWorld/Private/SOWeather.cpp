#include "SOWeather.h"

#include "SOAreaSubsystem.h"

#include "SONexusCity.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "Sound/SoundWave.h"

static TAutoConsoleVariable<int32> CVarWeatherAir(TEXT("so.Weather.Air"), 1, TEXT("Life in the air round the camera (motes, debris, rain, steam, smoke)."));
static TAutoConsoleVariable<int32> CVarWeatherClouds(TEXT("so.Weather.Clouds"), 1, TEXT("Weather drives the volumetric cloud material."));

namespace
{
	FSOWeatherLook Lerp(const FSOWeatherLook& A, const FSOWeatherLook& B, float T)
	{
		FSOWeatherLook R;
		R.Cloud = FMath::Lerp(A.Cloud, B.Cloud, T);
		R.Fog = FMath::Lerp(A.Fog, B.Fog, T);
		R.Rain = FMath::Lerp(A.Rain, B.Rain, T);
		R.Wind = FMath::Lerp(A.Wind, B.Wind, T);
		R.Dust = FMath::Lerp(A.Dust, B.Dust, T);
		R.Gusts = FMath::Lerp(A.Gusts, B.Gusts, T);
		return R;
	}

	/** smooth 1D value noise in 0..1 */
	float Smooth(float X, int32 Seed)
	{
		const int32 I = FMath::FloorToInt(X);
		const float F = X - I;
		auto H = [Seed](int32 N) { uint32 V = uint32(N) * 374761393u + uint32(Seed) * 668265263u; V = (V ^ (V >> 13)) * 1274126177u; return ((V ^ (V >> 16)) & 0xffff) / 65535.0f; };
		const float S = F * F * (3.0f - 2.0f * F);
		return FMath::Lerp(H(I), H(I + 1), S);
	}

	/** Fixed-size instance sets for the air: the same number of instances every frame (unused ones hidden far
	 *  below), transforms updated in place; rebuilding the set each frame faulted the GPU scene. */
	void Sync(UInstancedStaticMeshComponent* ISM, TArray<FTransform>& X, const TArray<float>* Custom, int32 Capacity)
	{
		const int32 Used = FMath::Min(X.Num(), Capacity);
		X.SetNum(Capacity);
		for (int32 i = Used; i < Capacity; ++i)
		{
			X[i] = FTransform(FQuat::Identity, FVector(0.0, 0.0, -1.0e6), FVector(0.001));
		}
		if (ISM->GetInstanceCount() != Capacity)
		{
			ISM->ClearInstances();
			ISM->AddInstances(X, false, true, false);
		}
		else
		{
			ISM->BatchUpdateInstancesTransforms(0, X, true, false, false);
		}
		if (Custom && ISM->NumCustomDataFloats == 4)
		{
			for (int32 i = 0; i < Capacity; ++i)
			{
				static const float Zero[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
				ISM->SetCustomData(i, i < Used ? MakeArrayView(Custom->GetData() + i * 4, 4) : MakeArrayView(Zero, 4), false);
			}
		}
		ISM->MarkRenderStateDirty();
	}

	USoundBase* LoadSound(const TCHAR* Name)
	{
		return LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/%s.%s"), Name, Name), nullptr, LOAD_Quiet | LOAD_NoWarn);
	}

	// how likely each weather follows each other (rows: from, columns: to)
	const float Next[7][7] = {
		//  Clear Cloudy Overc Rain Storm  Fog  Windy
		{ 0.15f, 0.40f, 0.10f, 0.05f, 0.00f, 0.15f, 0.15f },   // Clear
		{ 0.30f, 0.15f, 0.25f, 0.10f, 0.02f, 0.08f, 0.10f },   // Cloudy
		{ 0.05f, 0.25f, 0.10f, 0.35f, 0.10f, 0.10f, 0.05f },   // Overcast
		{ 0.05f, 0.20f, 0.30f, 0.10f, 0.20f, 0.15f, 0.00f },   // Rain
		{ 0.00f, 0.10f, 0.30f, 0.55f, 0.00f, 0.05f, 0.00f },   // Storm
		{ 0.35f, 0.35f, 0.15f, 0.05f, 0.00f, 0.05f, 0.05f },   // Fog
		{ 0.30f, 0.35f, 0.15f, 0.05f, 0.05f, 0.00f, 0.10f },   // Windy
	};
}

FSOWeatherLook USOWeatherSubsystem::LookOf(ESOWeather Weather)
{
	FSOWeatherLook L;
	switch (Weather)
	{
	case ESOWeather::Clear:    L.Cloud = 0.08f; L.Fog = 0.6f; L.Rain = 0.0f; L.Wind = 2.5f; L.Dust = 0.25f; L.Gusts = 0.2f; break;
	case ESOWeather::Cloudy:   L.Cloud = 0.45f; L.Fog = 0.9f; L.Rain = 0.0f; L.Wind = 4.0f; L.Dust = 0.25f; L.Gusts = 0.35f; break;
	case ESOWeather::Overcast: L.Cloud = 0.85f; L.Fog = 2.0f; L.Rain = 0.0f; L.Wind = 5.0f; L.Dust = 0.15f; L.Gusts = 0.4f; break;
	case ESOWeather::Rain:     L.Cloud = 0.95f; L.Fog = 3.0f; L.Rain = 0.6f; L.Wind = 6.0f; L.Dust = 0.0f; L.Gusts = 0.45f; break;
	case ESOWeather::Storm:    L.Cloud = 1.0f;  L.Fog = 4.0f; L.Rain = 1.0f; L.Wind = 11.0f; L.Dust = 0.0f; L.Gusts = 0.9f; break;
	case ESOWeather::Fog:      L.Cloud = 0.6f;  L.Fog = 16.0f; L.Rain = 0.0f; L.Wind = 1.0f; L.Dust = 0.05f; L.Gusts = 0.05f; break;
	case ESOWeather::Windy:    L.Cloud = 0.3f;  L.Fog = 1.1f; L.Rain = 0.0f; L.Wind = 10.0f; L.Dust = 1.0f; L.Gusts = 1.0f; break;
	}
	return L;
}

bool USOWeatherSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId USOWeatherSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USOWeatherSubsystem, STATGROUP_Tickables);
}

void USOWeatherSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	Random.Initialize(int32(FPlatformTime::Cycles() & 0x7fffffff));
	Target = Random.FRand() < 0.5f ? ESOWeather::Clear : ESOWeather::Cloudy;
	From = To = Look = LookOf(Target);
	Blend = 1.0f;
	NextChange = Random.FRandRange(MinutesPerWeather.X, MinutesPerWeather.Y) * 60.0f;
	WindAngle = Random.FRandRange(0.0f, UE_TWO_PI);
	Params = LoadObject<UMaterialParameterCollection>(nullptr, TEXT("/Game/Environments/MPC_SOWeather.MPC_SOWeather"), nullptr, LOAD_Quiet | LOAD_NoWarn);
}

void USOWeatherSubsystem::Deinitialize()
{
	if (AActor* H = Host.Get())
	{
		H->Destroy();
	}
	Super::Deinitialize();
}

void USOWeatherSubsystem::SetWeather(ESOWeather NewWeather, float BlendSeconds)
{
	From = Look;
	To = LookOf(NewWeather);
	Target = NewWeather;
	Blend = BlendSeconds <= 0.0f ? 1.0f : 0.0f;
	BlendTime = FMath::Max(BlendSeconds, 0.01f);
	NextChange = Random.FRandRange(MinutesPerWeather.X, MinutesPerWeather.Y) * 60.0f;
	if (Blend >= 1.0f)
	{
		Look = To;
	}
}

void USOWeatherSubsystem::Tick(float DeltaTime)
{
	DeltaTime = FMath::Min(DeltaTime, 0.1f);
	Time += DeltaTime;

	// the weather's course
	if (bAutomatic)
	{
		NextChange -= DeltaTime;
		if (NextChange <= 0.0f)
		{
			const int32 Row = int32(Target);
			float R = Random.FRand(), Acc = 0.0f;
			int32 Pick = Row;
			for (int32 k = 0; k < 7; ++k)
			{
				Acc += Next[Row][k];
				if (R <= Acc)
				{
					Pick = k;
					break;
				}
			}
			SetWeather(ESOWeather(Pick), 75.0f);
		}
	}
	if (Blend < 1.0f)
	{
		Blend = FMath::Min(1.0f, Blend + DeltaTime / BlendTime);
		const float S = Blend * Blend * (3.0f - 2.0f * Blend);
		Look = Lerp(From, To, S);
	}

	// wind: a slowly wandering direction, gusts that come and go
	WindAngle += (Smooth(Time * 0.01f, 7) - 0.5f) * DeltaTime * 0.08f;
	const float GustRaw = Smooth(Time * (0.18f + Look.Gusts * 0.3f), 11) * 0.7f + Smooth(Time * 0.9f, 13) * 0.3f;
	Gust = FMath::Clamp((GustRaw - (1.0f - Look.Gusts) * 0.55f) * 2.2f, 0.0f, 1.0f);
	const float Speed = Look.Wind * (0.7f + 0.3f * Smooth(Time * 0.05f, 17) + Gust * (0.6f + Look.Gusts));
	WindVelocity = FVector(FMath::Cos(WindAngle), FMath::Sin(WindAngle), 0.0f) * Speed * 100.0f;

	// wet streets: soak in the rain (~1 min), dry over ~6 min
	Wetness = Look.Rain > 0.05f ? FMath::Min(1.0f, Wetness + DeltaTime * Look.Rain / 60.0f) : FMath::Max(0.0f, Wetness - DeltaTime / 360.0f);

	EnvTimer -= DeltaTime;
	if (EnvTimer <= 0.0f || Flash > 0.0f)
	{
		ApplyEnvironment(FMath::Max(0.2f, DeltaTime));
		EnvTimer = 0.2f;
	}
	TickAir(DeltaTime);
}

void USOWeatherSubsystem::ApplyEnvironment(float DeltaTime)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (Params)
	{
		UKismetMaterialLibrary::SetScalarParameterValue(World, Params, TEXT("WindX"), WindVelocity.X / 100.0f);
		UKismetMaterialLibrary::SetScalarParameterValue(World, Params, TEXT("WindY"), WindVelocity.Y / 100.0f);
		UKismetMaterialLibrary::SetScalarParameterValue(World, Params, TEXT("Wind"), WindVelocity.Size() / 100.0f);
		UKismetMaterialLibrary::SetScalarParameterValue(World, Params, TEXT("Gust"), Gust);
		UKismetMaterialLibrary::SetScalarParameterValue(World, Params, TEXT("Wetness"), Wetness);
		UKismetMaterialLibrary::SetScalarParameterValue(World, Params, TEXT("Rain"), Look.Rain);
	}

	// lightning in storms: a flicker of the sky, thunder a little after
	if (Target == ESOWeather::Storm && Look.Rain > 0.6f)
	{
		LightningTimer -= DeltaTime;
		if (LightningTimer <= 0.0f)
		{
			Flash = 1.0f;
			LightningTimer = Random.FRandRange(7.0f, 24.0f);
			// (the sound is looked up when the thunder comes: nothing holds it until then, so a pointer taken now
			// could be collected before the timer fires)
			FTimerHandle H;
			TWeakObjectPtr<UWorld> W(World);
			World->GetTimerManager().SetTimer(H, [W]()
			{
				if (USoundBase* Thunder = W.IsValid() ? LoadSound(TEXT("S_amb_thunder")) : nullptr)
				{
					UGameplayStatics::PlaySound2D(W.Get(), Thunder, 0.9f);
				}
			}, Random.FRandRange(0.6f, 3.5f), false);
		}
	}
	Flash = FMath::Max(0.0f, Flash - DeltaTime * 3.0f);
	const float Flicker = Flash > 0.0f ? Flash * (0.6f + 0.4f * FMath::Abs(FMath::Sin(Time * 47.0f))) : 0.0f;

	for (TActorIterator<AExponentialHeightFog> It(World); It; ++It)
	{
		UExponentialHeightFogComponent* Fog = It->GetComponent();
		if (BaseFog < 0.0f)
		{
			BaseFog = Fog->FogDensity;
		}
		Fog->SetFogDensity(BaseFog * Look.Fog);
		break;
	}
	for (TActorIterator<ADirectionalLight> It(World); It; ++It)
	{
		if (!It->ActorHasTag(TEXT("Sun")))
		{
			continue;
		}
		UDirectionalLightComponent* Sun = Cast<UDirectionalLightComponent>(It->GetLightComponent());
		if (BaseSun < 0.0f)
		{
			BaseSun = Sun->Intensity;
		}
		// past half cover the sun is hidden: no hard shadows under an overcast or rain sky
		const float Hidden = FMath::SmoothStep(0.35f, 0.92f, Look.Cloud);
		Sun->SetIntensity(BaseSun * FMath::Lerp(1.0f, 0.05f, Hidden) + Flicker * 12.0f);
		break;
	}
	for (TActorIterator<ASkyLight> It(World); It; ++It)
	{
		USkyLightComponent* Sky = It->GetLightComponent();
		if (BaseSky < 0.0f)
		{
			BaseSky = Sky->Intensity;
		}
		Sky->SetIntensity(BaseSky * (1.0f - 0.45f * Look.Cloud) + Flicker * 4.0f);
		break;
	}
	for (TActorIterator<AVolumetricCloud> It(World); It && CVarWeatherClouds.GetValueOnGameThread() != 0; ++It)
	{
		UVolumetricCloudComponent* Cloud = It->FindComponentByClass<UVolumetricCloudComponent>();
		if (!Cloud)
		{
			break;
		}
		if (!CloudMID)
		{
			if (UMaterialInterface* Base = Cloud->Material.LoadSynchronous())
			{
				CloudMID = UMaterialInstanceDynamic::Create(Base, this);
				Cloud->SetMaterial(CloudMID);
			}
		}
		if (CloudMID && !bCloudChecked)
		{
			bCloudChecked = true;
			float V = 0.0f;
			const bool bCoverage = CloudMID->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("Cloud_GlobalCoverage")), V);
			const bool bDensity = CloudMID->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("Cloud_GlobalDensity")), V);
			UE_LOG(LogTemp, Log, TEXT("USOWeatherSubsystem: cloud material %s coverage %d density %d"), *CloudMID->Parent->GetName(), bCoverage, bDensity);
		}
		if (CloudMID)
		{
			// the engine cloud's own scale: coverage -0.2 / density 0.008 is its default broken sky
			// never thinner than the default (thinner coverage stalled the GPU on this build): clear = the default sky
			const float Over = FMath::Clamp((Look.Cloud - 0.2f) / 0.8f, 0.0f, 1.0f);
			CloudMID->SetScalarParameterValue(TEXT("Cloud_GlobalCoverage"), FMath::Lerp(-0.2f, 0.45f, Over));
			CloudMID->SetScalarParameterValue(TEXT("Cloud_GlobalDensity"), FMath::Lerp(0.008f, 0.025f, Over));
			CloudMID->SetScalarParameterValue(TEXT("StormClouds"), Target == ESOWeather::Storm ? Look.Rain : 0.0f);
			CloudMID->SetScalarParameterValue(TEXT("WindMultiplier"), 0.5f + WindVelocity.Size() / 400.0f);
			const float Grey = FMath::Lerp(1.0f, 0.42f, FMath::Clamp((Look.Cloud - 0.5f) * 2.0f, 0.0f, 1.0f) * FMath::Max(Look.Rain, 0.5f));
			CloudMID->SetVectorParameterValue(TEXT("Cloud_AlbedoColor"), FLinearColor(Grey, Grey, Grey * 1.02f));
		}
		break;
	}

	// the sound of it
	auto Loop = [World](TObjectPtr<UAudioComponent>& Comp, const TCHAR* Name)
	{
		if (!Comp)
		{
			if (USoundWave* Sound = Cast<USoundWave>(LoadSound(Name)))
			{
				Sound->bLooping = true;
				Comp = UGameplayStatics::CreateSound2D(World, Sound, 0.0f, 1.0f, 0.0f, nullptr, false, false);
				if (Comp)
				{
					Comp->Play(FMath::FRand() * 8.0f);
				}
			}
		}
		return Comp.Get();
	};
	const float WindMs = WindVelocity.Size() / 100.0f;
	if (UAudioComponent* W = Loop(WindLoop, TEXT("S_amb_wind")))
	{
		W->SetVolumeMultiplier(FMath::Clamp(0.08f + WindMs / 14.0f, 0.0f, 0.9f));
		W->SetPitchMultiplier(0.85f + FMath::Min(WindMs / 30.0f, 0.4f));
	}
	if (UAudioComponent* R = Loop(RainLoop, TEXT("S_amb_rain")))
	{
		R->SetVolumeMultiplier(FMath::Clamp(Look.Rain * 0.9f * (1.0f - 0.8f * Shelter), 0.0f, 0.9f));
	}
	GustSoundTimer -= DeltaTime;
	if (GustSoundTimer <= 0.0f)
	{
		GustSoundTimer = Random.FRandRange(4.0f, 12.0f);
		if (Gust > 0.5f && WindMs > 5.0f)
		{
			if (USoundBase* G = LoadSound(TEXT("S_amb_gust")))
			{
				UGameplayStatics::PlaySound2D(World, G, FMath::Clamp(Gust * WindMs / 14.0f, 0.1f, 0.8f), Random.FRandRange(0.85f, 1.15f));
			}
		}
	}
}

UInstancedStaticMeshComponent* USOWeatherSubsystem::MakeISM(const TCHAR* Mesh, const TCHAR* Material, bool bTranslucent, int32 CustomFloats)
{
	UStaticMesh* M = LoadObject<UStaticMesh>(nullptr, Mesh, nullptr, LOAD_Quiet | LOAD_NoWarn);
	if (!M || !Host.IsValid())
	{
		return nullptr;
	}
	UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(Host.Get());
	ISM->SetupAttachment(Host->GetRootComponent());
	ISM->SetStaticMesh(M);
	if (Material)
	{
		ISM->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr, Material, nullptr, LOAD_Quiet | LOAD_NoWarn));
	}
	ISM->NumCustomDataFloats = CustomFloats;
	ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	ISM->SetCastShadow(!bTranslucent);
	ISM->bAffectDistanceFieldLighting = false;
	ISM->SetMobility(EComponentMobility::Movable);
	ISM->bDisallowNanite = true;                 // small, rewritten every frame: plain instancing
	ISM->RegisterComponent();
	return ISM;
}

bool USOWeatherSubsystem::EnsureHost()
{
	if (Host.IsValid())
	{
		return true;
	}
	UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}
	FActorSpawnParameters P;
	P.Name = MakeUniqueObjectName(World, AActor::StaticClass(), TEXT("SOAirHost"));
	P.ObjectFlags = RF_Transient;
	AActor* A = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, P);
	if (!A)
	{
		return false;
	}
	USceneComponent* Root = NewObject<USceneComponent>(A, TEXT("Root"));
	A->SetRootComponent(Root);
	Root->RegisterComponent();
	Host = A;
	Motes = MakeISM(TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/MI_FxGlow.MI_FxGlow"), true, 4);
	RainStreaks = MakeISM(TEXT("/Game/FX/SM_FX_Streak.SM_FX_Streak"), TEXT("/Game/FX/MI_FxStreak.MI_FxStreak"), true, 4);
	Steam = MakeISM(TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/MI_FxSmoke.MI_FxSmoke"), true, 4);
	Smoke = MakeISM(TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/MI_FxSmoke.MI_FxSmoke"), true, 4);
	SplashRings = MakeISM(TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/MI_FxGlow.MI_FxGlow"), true, 4);
	SplashDrops = MakeISM(TEXT("/Game/FX/SM_FX_Streak.SM_FX_Streak"), TEXT("/Game/FX/MI_FxStreak.MI_FxStreak"), true, 4);
	Curtains = MakeISM(TEXT("/Game/FX/SM_FX_Quad.SM_FX_Quad"), TEXT("/Game/FX/MI_FxSmoke.MI_FxSmoke"), true, 4);
	// the city's airborne debris: only where the city is the area being played (other areas load none of it)
	const USOAreaSubsystem* Areas = USOAreaSubsystem::Get(World);
	const FSOArea* Area = Areas ? Areas->GetCurrent() : nullptr;
	const bool bCity = Area && Area->Content.Contains(TEXT("/Game/Environments/NexusCity"));
	for (const TCHAR* Name : { TEXT("NCK_leaf_dry"), TEXT("NCK_leaf_red"), TEXT("NCK_paper"), TEXT("NCK_wrapper") })
	{
		if (!bCity)
		{
			break;
		}
		Litter.Add(MakeISM(*FString::Printf(TEXT("/Game/Environments/NexusCity/SM_%s.SM_%s"), Name, Name), nullptr, false, 0));
	}
	return true;
}

void USOWeatherSubsystem::TickAir(float DeltaTime)
{
	if (CVarWeatherAir.GetValueOnGameThread() == 0)
	{
		return;
	}
	UWorld* World = GetWorld();
	APlayerCameraManager* Camera = World ? UGameplayStatics::GetPlayerCameraManager(World, 0) : nullptr;
	if (!Camera || !EnsureHost())
	{
		return;
	}
	const FVector Eye = Camera->GetCameraLocation();
	const FVector Up = Camera->GetCameraRotation().Quaternion().GetUpVector();
	const bool bJumped = FVector::DistSquared(Eye, LastEye) > FMath::Square(3000.0f);   // a teleport: reseed everything
	LastEye = Eye;
	const FVector Wind = WindVelocity;
	auto Facing = [&Eye, &Up](const FVector& P, float Size)
	{
		const FVector ToEye = (Eye - P).GetSafeNormal();
		return FTransform(FRotationMatrix::MakeFromYZ(ToEye, Up).ToQuat(), P, FVector(Size / 100.0f));
	};
	auto Ground = [World](const FVector& P, float& Z)
	{
		FHitResult Hit;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(SOAirGround), false);
		if (World->LineTraceSingleByChannel(Hit, P + FVector(0, 0, 400.0f), P - FVector(0, 0, 2500.0f), ECC_Visibility, Q))
		{
			Z = Hit.ImpactPoint.Z;
			return true;
		}
		return false;
	};

	// ---- dust motes, catching the light near the eye
	if (UInstancedStaticMeshComponent* ISM = Motes.Get())
	{
		const int32 Want = FMath::RoundToInt(70.0f + 160.0f * Look.Dust * (1.0f - Look.Rain));
		while (MoteState.Num() < Want)
		{
			MoteState.Add({ Eye + Random.GetUnitVector() * Random.FRandRange(150.0f, 1100.0f), FVector::ZeroVector, Random.FRand() * 10.0f });
		}
		MoteState.SetNum(Want);
		TArray<FTransform> X;
		TArray<float> C;
		for (FMote& M : MoteState)
		{
			M.Phase += DeltaTime;
			const FVector Drift(FMath::Sin(M.Phase * 0.7f), FMath::Cos(M.Phase * 0.53f), FMath::Sin(M.Phase * 0.41f) * 0.6f);
			M.P += (Wind * 0.25f + Drift * 18.0f) * DeltaTime;
			const FVector D = M.P - Eye;
			if (bJumped || D.SizeSquared() > FMath::Square(1200.0f))
			{
				M.P = Eye - Wind.GetSafeNormal() * Random.FRandRange(300.0f, 1000.0f) + Random.GetUnitVector() * 500.0f;
			}
			X.Add(Facing(M.P, 1.6f + 1.4f * FMath::Frac(M.Phase * 0.13f)));
			C.Append({ 1.0f, 0.95f, 0.85f, 0.25f + 0.15f * FMath::Sin(M.Phase * 2.3f) });
		}
		Sync(ISM, X, &C, 400);
	}

	// ---- rain streaks in a box round the eye, slanted by the wind
	if (UInstancedStaticMeshComponent* ISM = RainStreaks.Get())
	{
		// (under a roof there is no rain: a mall, a tunnel)
		FHitResult Roof;
		const bool bRoof = GetWorld()->LineTraceSingleByChannel(Roof, Eye + FVector(0, 0, 40.0f), Eye + FVector(0, 0, 6000.0f), ECC_Visibility,
			FCollisionQueryParams(SCENE_QUERY_STAT(SOWeatherRoof), false));
		Shelter = FMath::FInterpTo(Shelter, bRoof ? 1.0f : 0.0f, DeltaTime, 2.5f);
		const int32 Want = FMath::RoundToInt(1600.0f * Look.Rain * (1.0f - Shelter));
		const float Box = 2200.0f;
		while (DropState.Num() < Want)
		{
			DropState.Add({ Eye + FVector(Random.FRandRange(-Box, Box), Random.FRandRange(-Box, Box), Random.FRandRange(-600.0f, 1400.0f)) });
		}
		DropState.SetNum(Want);
		const FVector Fall = FVector(Wind.X * 0.8f, Wind.Y * 0.8f, -950.0f);
		const FVector Dir = Fall.GetSafeNormal();
		TArray<FTransform> X;
		TArray<float> C;
		for (FDrop& D : DropState)
		{
			D.P += Fall * DeltaTime;
			FVector Rel = D.P - Eye;
			if (bJumped || Rel.Z < -700.0f || FMath::Abs(Rel.X) > Box || FMath::Abs(Rel.Y) > Box)
			{
				D.P = Eye + FVector(Random.FRandRange(-Box, Box), Random.FRandRange(-Box, Box), Random.FRandRange(900.0f, 1500.0f)) - Wind * 0.6f;
				Rel = D.P - Eye;
			}
			const float Len = 55.0f;
			const FVector ToEye = (Eye - D.P).GetSafeNormal();
			X.Add(FTransform(FRotationMatrix::MakeFromYX(Dir, ToEye).ToQuat(), D.P - Dir * Len, FVector(1.0f, Len / 100.0f, 0.025f)));
			C.Append({ 0.75f, 0.8f, 0.88f, float(FMath::Clamp((D.P - Eye).Size() / 600.0, 0.15, 0.6)) });
		}
		Sync(ISM, X, &C, 1700);
	}

	// ---- where the rain lands (the owner's effects guide: "weather: rain, wind, atmospheric"): a ring opening on the
	// ground and two drops thrown up, many a second round the eye; none where it does not fall (under a roof)
	const float RainHere = Look.Rain * (1.0f - Shelter);
	if (UInstancedStaticMeshComponent* Rings = SplashRings.Get())
	{
		// the top surface round the eye, a metre a cell, found a few cells a frame (it moves with the eye)
		constexpr int32 G = 40;
		const FIntPoint Cell(FMath::FloorToInt(Eye.X / 100.0f), FMath::FloorToInt(Eye.Y / 100.0f));
		if (bJumped || RainGround.Num() != G * G || FMath::Abs(Cell.X - RainGroundOrigin.X) > 8 || FMath::Abs(Cell.Y - RainGroundOrigin.Y) > 8)
		{
			RainGroundOrigin = Cell;
			RainGround.Init(-1.0e9f, G * G);
			RainGroundFill = 0;
		}
		if (RainHere > 0.01f)
		{
			FCollisionQueryParams Q(SCENE_QUERY_STAT(SORainGround), false);
			if (APawn* Viewer = Camera->GetViewTargetPawn())
			{
				Q.AddIgnoredActor(Viewer);
			}
			for (int32 Traced = 0, Tries = 0; Traced < 28 && Tries < G * G; ++Tries)
			{
				const int32 i = RainGroundFill;
				RainGroundFill = (RainGroundFill + 1) % (G * G);
				if (RainGround[i] > -0.9e9f)
				{
					continue;
				}
				const FVector At((RainGroundOrigin.X - G / 2 + i % G + 0.5f) * 100.0f, (RainGroundOrigin.Y - G / 2 + i / G + 0.5f) * 100.0f, Eye.Z);
				FHitResult Hit;
				RainGround[i] = World->LineTraceSingleByChannel(Hit, At + FVector(0, 0, 1500.0f), At - FVector(0, 0, 1500.0f), ECC_Visibility, Q)
					&& Hit.ImpactNormal.Z > 0.5f ? static_cast<float>(Hit.ImpactPoint.Z) : -2.0e9f;
				++Traced;
			}
		}
		SplashDue += DeltaTime * 340.0f * RainHere;
		for (; SplashDue >= 1.0f; SplashDue -= 1.0f)
		{
			// nearer the eye more of them (most of what is seen of the ground is near it)
			const float R = 1400.0f * FMath::Square(Random.FRand()) + 80.0f;
			const float A = Random.FRandRange(0.0f, UE_TWO_PI);
			const FVector P(Eye.X + FMath::Cos(A) * R, Eye.Y + FMath::Sin(A) * R, 0.0f);
			const int32 cx = FMath::FloorToInt(P.X / 100.0f) - RainGroundOrigin.X + G / 2;
			const int32 cy = FMath::FloorToInt(P.Y / 100.0f) - RainGroundOrigin.Y + G / 2;
			if (cx < 0 || cy < 0 || cx >= G || cy >= G || RainGround[cy * G + cx] < -0.9e8f)
			{
				continue;
			}
			const FVector On(P.X, P.Y, RainGround[cy * G + cx] + 0.6f);
			Splashes.Add({ On, 0.0f, static_cast<float>(Random.FRandRange(0.22f, 0.34f)), static_cast<float>(Random.FRandRange(12.0f, 24.0f)) });
			for (int32 k = 0; k < 2; ++k)
			{
				const float B = Random.FRandRange(0.0f, UE_TWO_PI);
				Droplets.Add({ On, FVector(FMath::Cos(B), FMath::Sin(B), 0.0f) * Random.FRandRange(35.0f, 85.0f) + FVector(0, 0, Random.FRandRange(110.0f, 190.0f)),
					0.0f, static_cast<float>(Random.FRandRange(0.18f, 0.28f)) });
			}
		}
		for (int32 i = Splashes.Num() - 1; i >= 0; --i)
		{
			Splashes[i].Age += DeltaTime;
			if (Splashes[i].Age >= Splashes[i].Life)
			{
				Splashes.RemoveAtSwap(i, 1, EAllowShrinking::No);
			}
		}
		for (int32 i = Droplets.Num() - 1; i >= 0; --i)
		{
			FDroplet& D = Droplets[i];
			D.Age += DeltaTime;
			D.V.Z -= 980.0f * DeltaTime;
			D.P += D.V * DeltaTime;
			if (D.Age >= D.Life)
			{
				Droplets.RemoveAtSwap(i, 1, EAllowShrinking::No);
			}
		}
		if (Splashes.Num() > 700)
		{
			Splashes.RemoveAt(0, Splashes.Num() - 700, EAllowShrinking::No);
		}
		if (Droplets.Num() > 1400)
		{
			Droplets.RemoveAt(0, Droplets.Num() - 1400, EAllowShrinking::No);
		}
		TArray<FTransform> X;
		TArray<float> C;
		const FQuat Flat = FRotationMatrix::MakeFromYZ(FVector::UpVector, FVector::ForwardVector).ToQuat();
		for (const FSplash& S : Splashes)
		{
			// a crown: six beads on a ring opening out from where the drop landed, fading as it opens (one soft dot read
			// as a white spot on the street)
			const float T = S.Age / S.Life;
			const float R = S.Size * 0.5f * (0.2f + 0.8f * FMath::Sqrt(T));
			const float Turn = (S.P.X * 0.37f + S.P.Y * 0.11f);
			for (int32 k = 0; k < 6; ++k)
			{
				const float A = Turn + UE_TWO_PI * k / 6.0f;
				X.Add(FTransform(Flat, S.P + FVector(FMath::Cos(A) * R, FMath::Sin(A) * R, 0.0f), FVector(1.3f / 100.0f)));
				C.Append({ 0.80f, 0.86f, 0.94f, 0.9f * (1.0f - T) * (1.0f - T) });
			}
		}
		Sync(Rings, X, &C, 4200);
		if (UInstancedStaticMeshComponent* Drops = SplashDrops.Get())
		{
			X.Reset();
			C.Reset();
			for (const FDroplet& D : Droplets)
			{
				const FVector Dir = D.V.GetSafeNormal();
				const float Len = FMath::Clamp(D.V.Size() * 0.02f, 1.0f, 4.0f);
				const FVector ToEye = (Eye - D.P).GetSafeNormal();
				X.Add(FTransform(FRotationMatrix::MakeFromYX(Dir, ToEye).ToQuat(), D.P - Dir * Len, FVector(1.0f, Len / 100.0f, 0.006f)));
				C.Append({ 0.8f, 0.86f, 0.94f, 1.1f * (1.0f - D.Age / D.Life) });
			}
			Sync(Drops, X, &C, 1500);
		}
	}

	// ---- a storm's sheets of rain: tall, faint veils drifting across the distance on the wind
	if (UInstancedStaticMeshComponent* Veils = Curtains.Get())
	{
		const int32 Want = Look.Rain > 0.55f ? FMath::RoundToInt(12.0f * FMath::Clamp((Look.Rain - 0.55f) / 0.45f, 0.0f, 1.0f) * (1.0f - Shelter)) : 0;
		auto Place = [this, &Eye, &Wind](FCurtain& V, bool bUpwind)
		{
			const float A = Random.FRandRange(0.0f, UE_TWO_PI);
			const float R = Random.FRandRange(1800.0f, 4500.0f);
			V.P = Eye + FVector(FMath::Cos(A) * R, FMath::Sin(A) * R, 0.0f) - (bUpwind ? Wind.GetSafeNormal() * 1500.0f : FVector::ZeroVector);
			V.Width = Random.FRandRange(600.0f, 1100.0f);
			V.Height = Random.FRandRange(1400.0f, 2400.0f);
			V.Alpha = Random.FRandRange(0.14f, 0.24f);
			V.Phase = Random.FRandRange(0.0f, 10.0f);
		};
		while (CurtainState.Num() < Want)
		{
			FCurtain V;
			Place(V, false);
			CurtainState.Add(V);
		}
		CurtainState.SetNum(Want);
		TArray<FTransform> X;
		TArray<float> C;
		for (FCurtain& V : CurtainState)
		{
			V.Phase += DeltaTime;
			V.P += Wind * 1.1f * DeltaTime;
			const float D = FVector::Dist2D(V.P, Eye);
			if (bJumped || D > 5200.0f || D < 1200.0f)
			{
				Place(V, true);
			}
			// facing the eye about the vertical (a sheet, not a ball): the quad's Y toward the eye, Z up
			FVector ToEye = Eye - V.P;
			ToEye.Z = 0.0f;
			ToEye = ToEye.GetSafeNormal(1e-4f, FVector::ForwardVector);
			const FVector Mid = V.P + FVector(0, 0, V.Height * 0.35f);
			X.Add(FTransform(FRotationMatrix::MakeFromYZ(ToEye, FVector::UpVector).ToQuat(), Mid, FVector(V.Width / 100.0f, 1.0f, V.Height / 100.0f)));
			const float Breath = 0.75f + 0.25f * FMath::Sin(V.Phase * 0.7f);
			C.Append({ 0.56f, 0.61f, 0.70f, V.Alpha * Breath * Look.Rain });
		}
		Sync(Veils, X, &C, 16);
	}

	// ---- leaves, paper and wrappers: skitter along the ground on the wind, lift and tumble on gusts
	const int32 Kinds = Litter.Num();
	if (Kinds > 0 && Litter[0].IsValid())
	{
		const float WindMs = Wind.Size() / 100.0f;
		const int32 Want = Look.Rain > 0.5f ? 25 : FMath::RoundToInt(30.0f + 70.0f * FMath::Clamp(Look.Dust + WindMs / 14.0f, 0.0f, 1.5f));
		while (Bits.Num() < Want)
		{
			FBit B;
			B.Kind = Random.RandRange(0, Kinds - 1);
			B.P = Eye + FVector(Random.FRandRange(-2500.0f, 2500.0f), Random.FRandRange(-2500.0f, 2500.0f), 0.0f);
			B.Ground = Eye.Z - 170.0f;
			Ground(B.P, B.Ground);
			B.P.Z = B.Ground + 1.0f;
			B.V = FVector::ZeroVector;
			B.R = FRotator(0.0f, Random.FRandRange(0.0f, 360.0f), 0.0f);
			B.Spin = FRotator(Random.FRandRange(-200.0f, 200.0f), Random.FRandRange(-300.0f, 300.0f), Random.FRandRange(-200.0f, 200.0f));
			B.bAir = false;
			Bits.Add(B);
		}
		Bits.SetNum(Want);
		TArray<TArray<FTransform>> X;
		X.SetNum(Kinds);
		for (FBit& B : Bits)
		{
			const float Light = B.Kind <= 1 ? 1.0f : (B.Kind == 2 ? 0.8f : 0.5f);    // leaves catch the wind best
			if (!B.bAir)
			{
				// sliding: the wind pushes once it beats friction
				const float Push = FMath::Max(0.0f, WindMs - 2.5f) * 18.0f * Light * (0.6f + Gust);
				B.V = FMath::VInterpTo(B.V, Wind.GetSafeNormal() * Push, DeltaTime, 2.0f);
				B.P += B.V * DeltaTime;
				B.R.Yaw += B.V.Size() * DeltaTime * 2.0f;
				if (Gust > 0.65f && WindMs > 5.0f && Random.FRand() < DeltaTime * 0.8f * Light)
				{
					B.bAir = true;
					B.V += FVector(0, 0, Random.FRandRange(200.0f, 480.0f) * Light);
				}
			}
			else
			{
				// tumbling through the air: drag toward the wind, light gravity, a flutter
				const FVector Rel = Wind * (0.75f + 0.25f * Gust) - B.V;
				B.V += Rel * DeltaTime * 1.8f * Light;
				B.V.Z -= 320.0f * DeltaTime;
				B.V.Z += FMath::Sin(Time * 6.0f + B.P.X * 0.01f) * 120.0f * DeltaTime * Light;
				B.P += B.V * DeltaTime;
				B.R += B.Spin * DeltaTime;
				if (B.P.Z <= B.Ground + 1.0f)
				{
					B.P.Z = B.Ground + 1.0f;
					B.bAir = false;
					B.R.Pitch = B.R.Roll = 0.0f;
					B.V *= 0.3f;
				}
			}
			const FVector D = B.P - Eye;
			if (bJumped || D.Size2D() > 3000.0f)
			{
				// re-enter upwind of the eye
				const FVector In = -Wind.GetSafeNormal2D();
				const FVector Side(-In.Y, In.X, 0.0f);
				B.P = Eye + (In.IsNearlyZero() ? FVector(1, 0, 0) : In) * Random.FRandRange(1200.0f, 2600.0f) + Side * Random.FRandRange(-2000.0f, 2000.0f);
				B.Ground = Eye.Z - 170.0f;
				Ground(B.P, B.Ground);
				B.P.Z = B.Ground + 1.0f;
				B.bAir = false;
				B.V = FVector::ZeroVector;
			}
			X[B.Kind].Add(FTransform(B.R, B.P));
		}
		for (int32 k = 0; k < Kinds; ++k)
		{
			if (UInstancedStaticMeshComponent* ISM = Litter[k].Get())
			{
				Sync(ISM, X[k], nullptr, 160);
			}
		}
	}

	// ---- steam from roof vents and open manholes, smoke from exhaust stacks (the city's emitters)
	const ASONexusCity* City = nullptr;
	for (TActorIterator<ASONexusCity> It(World); It; ++It)
	{
		City = *It;
		break;
	}
	auto Emit = [this, &Eye](const TArray<FVector>& Points, float Range, int32 MaxSources, float Every, float& Timer, TArray<FPuff>& Out,
		float Rise, float S0, float S1, float Life, const FLinearColor& Color, float Alpha)
	{
		Timer -= GetWorld()->GetDeltaSeconds();
		if (Timer > 0.0f || Points.Num() == 0)
		{
			return;
		}
		Timer = Every;
		TArray<TPair<float, int32>> Near;
		for (int32 i = 0; i < Points.Num(); ++i)
		{
			const float D = FVector::DistSquared(Points[i], Eye);
			if (D < Range * Range)
			{
				Near.Add({ D, i });
			}
		}
		Near.Sort([](const TPair<float, int32>& A, const TPair<float, int32>& B) { return A.Key < B.Key; });
		for (int32 k = 0; k < FMath::Min(MaxSources, Near.Num()); ++k)
		{
			if (Out.Num() > 700)
			{
				break;
			}
			const FVector P = Points[Near[k].Value] + FVector(Random.FRandRange(-30.0f, 30.0f), Random.FRandRange(-30.0f, 30.0f), 0.0f);
			Out.Add({ P, FVector(0, 0, Rise * Random.FRandRange(0.8f, 1.2f)), 0.0f, float(Life * Random.FRandRange(0.8f, 1.2f)), S0, float(S1 * Random.FRandRange(0.8f, 1.2f)), Color, Alpha });
		}
	};
	if (City)
	{
		// warm air shows more in the cold and the wet
		const float SteamAlpha = 0.45f + 0.3f * FMath::Max(Look.Rain, Look.Fog > 3.0f ? 1.0f : 0.0f);
		Emit(City->SteamPoints, 9000.0f, 14, 0.18f, SteamTimer, SteamPuffs, 110.0f, 40.0f, 320.0f, 4.0f, FLinearColor(0.82f, 0.83f, 0.85f), SteamAlpha);
		Emit(City->SmokePoints, 70000.0f, 8, 0.35f, SmokeTimer, SmokePuffs, 260.0f, 160.0f, 1400.0f, 9.0f, FLinearColor(0.14f, 0.14f, 0.15f), 0.85f);
	}
	auto DrawPuffs = [&Facing, &Wind, DeltaTime](TArray<FPuff>& Puffs, UInstancedStaticMeshComponent* ISM, float WindCarry)
	{
		if (!ISM)
		{
			return;
		}
		TArray<FTransform> X;
		TArray<float> C;
		for (int32 i = Puffs.Num() - 1; i >= 0; --i)
		{
			FPuff& P = Puffs[i];
			P.Age += DeltaTime;
			if (P.Age >= P.Life)
			{
				Puffs.RemoveAtSwap(i, 1, EAllowShrinking::No);
				continue;
			}
			P.V = FMath::VInterpTo(P.V, FVector(Wind.X * WindCarry, Wind.Y * WindCarry, P.V.Z), DeltaTime, 0.8f);
			P.V.Z *= FMath::Exp(-0.25f * DeltaTime);
			P.P += P.V * DeltaTime;
		}
		for (const FPuff& P : Puffs)
		{
			const float A = P.Age / P.Life;
			X.Add(Facing(P.P, FMath::Lerp(P.Size0, P.Size1, FMath::Sqrt(A))));
			C.Append({ P.Color.R, P.Color.G, P.Color.B, P.Alpha * FMath::Min(1.0f, A * 6.0f) * (1.0f - A) });
		}
		Sync(ISM, X, &C, 760);
	};
	DrawPuffs(SteamPuffs, Steam.Get(), 0.6f);
	DrawPuffs(SmokePuffs, Smoke.Get(), 0.8f);
}
