#include "SONexusCity.h"

#include "SOTimeOfDaySubsystem.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

static TAutoConsoleVariable<int32> CVarCityTrees(TEXT("so.City.Trees"), 1, TEXT("Place the city's trees and shrubs (CT_*)."));
static TAutoConsoleVariable<int32> CVarCityTreeSway(TEXT("so.City.TreeSway"), 1, TEXT("Evaluate the trees' wind sway (world position offset)."));

namespace
{
	using FJsonArray = TArray<TSharedPtr<FJsonValue>>;

	TSharedPtr<FJsonObject> LoadJson(const FString& Relative)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectDir() / Relative)))
		{
			return nullptr;
		}
		TSharedPtr<FJsonObject> Obj;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
		return FJsonSerializer::Deserialize(Reader, Obj) ? Obj : nullptr;
	}

	/** (E, N) metres */
	FVector2D Pt(const TSharedPtr<FJsonValue>& V)
	{
		const FJsonArray& A = V->AsArray();
		return FVector2D(A[0]->AsNumber(), A[1]->AsNumber());
	}

	FVector2D PtField(const TSharedPtr<FJsonObject>& O, const TCHAR* Key)
	{
		const FJsonArray& A = O->GetArrayField(Key);
		return A.Num() >= 2 ? FVector2D(A[0]->AsNumber(), A[1]->AsNumber()) : FVector2D::ZeroVector;
	}

	TArray<FVector2D> Poly(const FJsonArray& A)
	{
		TArray<FVector2D> Out;
		Out.Reserve(A.Num());
		for (const TSharedPtr<FJsonValue>& V : A)
		{
			const FVector2D P = Pt(V);
			if (Out.Num() == 0 || FVector2D::DistSquared(Out.Last(), P) > 1e-4)
			{
				Out.Add(P);
			}
		}
		if (Out.Num() > 2 && FVector2D::DistSquared(Out[0], Out.Last()) < 1e-4)
		{
			Out.Pop();
		}
		return Out;
	}

	bool Inside(const FVector2D& P, const TArray<FVector2D>& Poly)
	{
		bool bIn = false;
		for (int32 i = 0, j = Poly.Num() - 1; i < Poly.Num(); j = i++)
		{
			const FVector2D& A = Poly[i];
			const FVector2D& B = Poly[j];
			if ((A.Y > P.Y) != (B.Y > P.Y) && P.X < (B.X - A.X) * (P.Y - A.Y) / (B.Y - A.Y + 1e-12) + A.X)
			{
				bIn = !bIn;
			}
		}
		return bIn;
	}

	uint32 Hash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return X;
	}

	float Rand01(uint32 Seed) { return (Hash(Seed) & 0xffffff) / float(0xffffff); }

	/** Minimum-area rectangle over the polygon's edge directions: centre, unit axis A, extent W along A, D across. */
	struct FRect { FVector2D C, A; double W = 0.0, D = 0.0; };

	FRect MinRect(const TArray<FVector2D>& P)
	{
		FRect Best;
		double BestArea = DBL_MAX;
		for (int32 i = 0; i < P.Num(); ++i)
		{
			const FVector2D E = P[(i + 1) % P.Num()] - P[i];
			const double L = E.Size();
			if (L < 0.5)
			{
				continue;
			}
			const FVector2D A = E / L;
			const FVector2D N(-A.Y, A.X);
			double A0 = DBL_MAX, A1 = -DBL_MAX, N0 = DBL_MAX, N1 = -DBL_MAX;
			for (const FVector2D& Q : P)
			{
				const double a = FVector2D::DotProduct(Q, A), n = FVector2D::DotProduct(Q, N);
				A0 = FMath::Min(A0, a); A1 = FMath::Max(A1, a); N0 = FMath::Min(N0, n); N1 = FMath::Max(N1, n);
			}
			const double Area = (A1 - A0) * (N1 - N0);
			if (Area < BestArea)
			{
				BestArea = Area;
				Best.A = A;
				Best.C = A * (A0 + A1) * 0.5 + N * (N0 + N1) * 0.5;
				Best.W = A1 - A0;
				Best.D = N1 - N0;
			}
		}
		return Best;
	}

	/** World yaw (deg) that turns a kit mesh's local +X (Blender +x: the width / "along" axis) onto plan direction Dir (E, N). */
	double YawAlong(const FVector2D& Dir) { return FMath::RadiansToDegrees(FMath::Atan2(Dir.X, Dir.Y)); }

	struct FPending
	{
		TArray<FTransform> Xf;
		TArray<float> Custom;
		int32 Floats = 0;
		bool bCollide = true;
		float CullCm = 0.0f;
	};
}

ASONexusCity::ASONexusCity()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 2.0f;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent->SetMobility(EComponentMobility::Static);
}

void ASONexusCity::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (bBuildInEditor && GetWorld() && !GetWorld()->IsGameWorld())
	{
		Build();
	}
}

void ASONexusCity::BeginPlay()
{
	Super::BeginPlay();
	if (Built.Num() == 0)
	{
		Build();
	}
}

void ASONexusCity::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const USOTimeOfDaySubsystem* Time = GetWorld() ? GetWorld()->GetSubsystem<USOTimeOfDaySubsystem>() : nullptr;
	const float Night = Time ? FMath::Clamp((1.0f - Time->GetDaylight()) * 1.25f - 0.1f, 0.0f, 1.0f) : 0.5f;
	if (FMath::Abs(Night - NightApplied) > 0.01f)
	{
		NightApplied = Night;
		for (const auto& Pair : FacadeMIDs)
		{
			Pair.Value->SetScalarParameterValue(TEXT("Night"), Night);
		}
	}
}

UStaticMesh* ASONexusCity::LoadMesh(const FString& Name, bool bTiles) const
{
	const FString Folder = bTiles ? MeshFolder / TEXT("Tiles") : MeshFolder;
	const FString Path = FString::Printf(TEXT("%s/SM_%s.SM_%s"), *Folder, *Name, *Name);
	return LoadObject<UStaticMesh>(nullptr, *Path, nullptr, LOAD_Quiet | LOAD_NoWarn);
}

UInstancedStaticMeshComponent* ASONexusCity::Instancer(UStaticMesh* Mesh, int32 CustomFloats, bool bCollide)
{
	if (TObjectPtr<UInstancedStaticMeshComponent>* Found = Instancers.Find(Mesh))
	{
		return *Found;
	}
	UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this, NAME_None, RF_Transient);
	C->SetStaticMesh(Mesh);
	C->SetMobility(EComponentMobility::Static);
	C->SetupAttachment(RootComponent);
	C->SetCollisionEnabled(bCollide ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
	C->SetNumCustomDataFloats(CustomFloats);
	if (Mesh->GetName().StartsWith(TEXT("SM_CT_")) && CVarCityTreeSway.GetValueOnGameThread() != 0)
	{
		C->SetEvaluateWorldPositionOffset(true);           // M_SOFoliage sways the trees on the weather's wind
		C->SetWorldPositionOffsetDisableDistance(25000);
		C->SetCastShadow(true);
	}
	// facade materials get their own dynamic instance (one per material, shared by every design) for "Night"
	for (int32 i = 0; i < Mesh->GetStaticMaterials().Num(); ++i)
	{
		UMaterialInterface* M = Mesh->GetMaterial(i);
		const UMaterial* Base = M ? M->GetMaterial() : nullptr;
		if (Base && Base->GetName() == TEXT("M_SOFacade"))
		{
			TObjectPtr<UMaterialInstanceDynamic>& MID = FacadeMIDs.FindOrAdd(M);
			if (!MID)
			{
				MID = UMaterialInstanceDynamic::Create(M, this);
			}
			C->SetMaterial(i, MID);
		}
	}
	C->RegisterComponent();
	Built.Add(C);
	Instancers.Add(Mesh, C);
	return C;
}

void ASONexusCity::AddMesh(UStaticMesh* Mesh, const FTransform& Transform, bool bCollide)
{
	if (!Mesh)
	{
		return;
	}
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this, NAME_None, RF_Transient);
	C->SetStaticMesh(Mesh);
	C->SetMobility(EComponentMobility::Static);
	C->SetupAttachment(RootComponent);
	C->SetCollisionEnabled(bCollide ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
	C->SetWorldTransform(Transform);
	C->RegisterComponent();
	Built.Add(C);
}

void ASONexusCity::Clear()
{
	for (UActorComponent* C : Built)
	{
		if (C)
		{
			C->DestroyComponent();
		}
	}
	Built.Reset();
	Instancers.Reset();
	FacadeMIDs.Reset();
	RoadNodes.Reset();
	RoadEdges.Reset();
	Stations.Reset();
	SteamPoints.Reset();
	SmokePoints.Reset();
	NumBuildings = NumInstances = MissingMeshes = 0;
	NightApplied = -1.0f;
}

int32 ASONexusCity::NearestRoadNode(const FVector& World) const
{
	int32 Best = INDEX_NONE;
	double BestD = DBL_MAX;
	for (int32 i = 0; i < RoadNodes.Num(); ++i)
	{
		const double D = FVector::DistSquared2D(RoadNodes[i], World);
		if (D < BestD)
		{
			BestD = D;
			Best = i;
		}
	}
	return Best;
}

void ASONexusCity::Build()
{
	Clear();
	const TSharedPtr<FJsonObject> Plan = LoadJson(PlanFile);
	const TSharedPtr<FJsonObject> City = LoadJson(CityFile);
	if (!Plan || !City)
	{
		UE_LOG(LogTemp, Warning, TEXT("ASONexusCity: missing %s or %s"), *PlanFile, *CityFile);
		return;
	}
	const double Kerb = City->GetNumberField(TEXT("kerb"));
	TMap<UStaticMesh*, FPending> Pending;
	auto Queue = [&Pending](UStaticMesh* Mesh, const FTransform& Xf, TConstArrayView<float> Custom, bool bCollide)
	{
		if (!Mesh)
		{
			return;
		}
		FPending& P = Pending.FindOrAdd(Mesh);
		P.Xf.Add(Xf);
		P.Floats = Custom.Num();
		P.Custom.Append(Custom.GetData(), Custom.Num());
		P.bCollide = bCollide;
	};

	// ---- the baked plan: tiles (world coordinates) and the land
	for (const TSharedPtr<FJsonValue>& V : City->GetArrayField(TEXT("tiles")))
	{
		AddMesh(LoadMesh(V->AsObject()->GetStringField(TEXT("name")), true), FTransform::Identity);
	}
	AddMesh(LoadMesh(City->GetStringField(TEXT("land")), true), FTransform::Identity);

	// ---- road graph (for traffic and people)
	const TSharedPtr<FJsonObject> Roads = Plan->GetObjectField(TEXT("roads"));
	const TSharedPtr<FJsonObject> Lanes = City->GetObjectField(TEXT("lanes"));
	for (const TSharedPtr<FJsonValue>& V : Roads->GetArrayField(TEXT("nodes")))
	{
		const FVector2D P = Pt(V);
		RoadNodes.Add(PlanToWorld(P.X, P.Y));
	}
	for (const TSharedPtr<FJsonValue>& V : Roads->GetArrayField(TEXT("edges")))
	{
		const TSharedPtr<FJsonObject> E = V->AsObject();
		FSORoadEdge R;
		R.A = E->GetIntegerField(TEXT("a"));
		R.B = E->GetIntegerField(TEXT("b"));
		R.Class = FName(*E->GetStringField(TEXT("cls")));
		R.Width = E->GetNumberField(TEXT("w")) * 100.0f;
		const TSharedPtr<FJsonObject>* LO = nullptr;
		if (Lanes->TryGetObjectField(R.Class.ToString(), LO))
		{
			R.LanesEachWay = (*LO)->GetIntegerField(TEXT("n"));
			R.LaneWidth = (*LO)->GetNumberField(TEXT("w")) * 100.0f;
			R.Median = (*LO)->GetNumberField(TEXT("med")) * 100.0f;
		}
		for (const TSharedPtr<FJsonValue>& Q : E->GetArrayField(TEXT("pts")))
		{
			const FVector2D P = Pt(Q);
			R.Points.Add(PlanToWorld(P.X, P.Y));
		}
		RoadEdges.Add(MoveTemp(R));
	}

	// ---- everything placed by tools/city/nexus_dress.py: buildings, doors, roofs, yards, trees, cars, street life
	TArray<uint8> Bytes;
	if (FFileHelper::LoadFileToArray(Bytes, *(FPaths::ProjectDir() / InstanceFile)) && Bytes.Num() > 8 && FMemory::Memcmp(Bytes.GetData(), "NXI1", 4) == 0)
	{
		uint32 HeadLen = 0;
		FMemory::Memcpy(&HeadLen, Bytes.GetData() + 4, 4);
		const FString Head = FString(FUTF8ToTCHAR(reinterpret_cast<const ANSICHAR*>(Bytes.GetData() + 8), HeadLen).Length(), FUTF8ToTCHAR(reinterpret_cast<const ANSICHAR*>(Bytes.GetData() + 8), HeadLen).Get());
		TSharedPtr<FJsonObject> Header;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Head);
		if (FJsonSerializer::Deserialize(Reader, Header) && Header)
		{
			int64 Offset = 8 + HeadLen;
			for (const TSharedPtr<FJsonValue>& V : Header->GetArrayField(TEXT("meshes")))
			{
				const TSharedPtr<FJsonObject> M = V->AsObject();
				const int32 Count = M->GetIntegerField(TEXT("count"));
				const int32 Custom = M->GetIntegerField(TEXT("custom"));
				const int32 Stride = 7 + Custom;
				const float* Rec = reinterpret_cast<const float*>(Bytes.GetData() + Offset);
				Offset += int64(Count) * Stride * sizeof(float);
				if (Offset > Bytes.Num())
				{
					UE_LOG(LogTemp, Warning, TEXT("ASONexusCity: %s is truncated"), *InstanceFile);
					break;
				}
				const FString Path = M->GetStringField(TEXT("path"));
				UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("%s.%s"), *Path, *FPaths::GetBaseFilename(Path)), nullptr, LOAD_Quiet | LOAD_NoWarn);
				if (!Mesh)
				{
					MissingMeshes++;
					continue;
				}
				if (CVarCityTrees.GetValueOnGameThread() == 0 && FPaths::GetBaseFilename(Path).StartsWith(TEXT("SM_CT_")))
				{
					continue;
				}
				FPending& P = Pending.FindOrAdd(Mesh);
				P.Floats = Custom;
				P.bCollide = M->GetBoolField(TEXT("collide"));
				P.CullCm = float(M->GetNumberField(TEXT("cull"))) * 100.0f;
				P.Xf.Reserve(P.Xf.Num() + Count);
				const FString Base = FPaths::GetBaseFilename(Path);
				TArray<FVector>* Emitters = Base == TEXT("SM_NCK_exhaust_stack") ? &SmokePoints
					: (Base == TEXT("SM_NCK_roof_vents") || Base == TEXT("SM_NCK_manhole_open")) ? &SteamPoints : nullptr;
				const double OutletZ = Base == TEXT("SM_NCK_exhaust_stack") ? 900.0 : Base == TEXT("SM_NCK_roof_vents") ? 120.0 : 10.0;
				for (int32 i = 0; i < Count; ++i, Rec += Stride)
				{
					P.Xf.Add(FTransform(FRotator(0.0, Rec[3], 0.0), FVector(Rec[0], Rec[1], Rec[2]), FVector(Rec[4], Rec[5], Rec[6])));
					P.Custom.Append(Rec + 7, Custom);
					if (Emitters)
					{
						Emitters->Add(FVector(Rec[0], Rec[1], Rec[2] + OutletZ * Rec[6]));
					}
				}
				NumInstances += Count;
				if (FPaths::GetBaseFilename(Path).StartsWith(TEXT("SM_NCB_")) && !FPaths::GetBaseFilename(Path).StartsWith(TEXT("SM_NCB_gf_")))
				{
					NumBuildings += Count;
				}
			}
		}
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("ASONexusCity: no instance file %s (run tools/city/nexus_dress.py)"), *InstanceFile);
	}

	// ---- stations on the viaducts
	UStaticMesh* StationMesh = LoadMesh(TEXT("NCK_station"));
	for (const TSharedPtr<FJsonValue>& V : City->GetArrayField(TEXT("stations")))
	{
		const TSharedPtr<FJsonObject> St = V->AsObject();
		const FVector2D Pos = PtField(St, TEXT("pos"));
		const FVector2D Dir = PtField(St, TEXT("dir"));
		FSOCityStation S;
		S.Name = St->GetStringField(TEXT("name"));
		S.Line = FName(*St->GetStringField(TEXT("line")));
		S.Transform = FTransform(FRotator(0.0, YawAlong(Dir), 0.0), PlanToWorld(Pos.X, Pos.Y, St->GetNumberField(TEXT("h"))));
		AddMesh(StationMesh, S.Transform);
		Stations.Add(S);
	}

	// ---- landmarks from the Nexus hub kit, scaled to the plan's sites
	auto NX = [](const TCHAR* Name) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Environments/Nexus/SM_%s.SM_%s"), Name, Name), nullptr, LOAD_Quiet | LOAD_NoWarn); };
	const FTransform SpireXf(FRotator::ZeroRotator, PlanToWorld(0, 0, Kerb), FVector(SpireScale));
	AddMesh(NX(TEXT("NX_spire")), SpireXf);
	AddMesh(NX(TEXT("NX_spire_ring_low")), SpireXf, false);
	AddMesh(NX(TEXT("NX_spire_ring_high")), SpireXf, false);
	TArray<UStaticMesh*> Crystals = { NX(TEXT("NX_crystal_a")), NX(TEXT("NX_crystal_b")), NX(TEXT("NX_crystal_c")) };
	const TSharedPtr<FJsonObject> Landmarks = Plan->GetObjectField(TEXT("landmarks"));
	for (const auto& Pair : Landmarks->Values)
	{
		const TSharedPtr<FJsonObject> L = Pair.Value->AsObject();
		const FString Kind = L->GetStringField(TEXT("kind"));
		const FVector2D C = PtField(L, TEXT("centre"));
		const FVector2D Rad = PtField(L, TEXT("radius"));   // (E, N) radii
		const double Z = Kerb + 0.02;
		if (Kind == TEXT("arena"))
		{
			AddMesh(NX(TEXT("NX_arena")), FTransform(FRotator::ZeroRotator, PlanToWorld(C.X, C.Y, Z), FVector(Rad.Y * 0.8 / 64.0, Rad.X * 0.8 / 64.0, 2.6)));
		}
		else if (Kind == TEXT("dome"))
		{
			AddMesh(NX(TEXT("NX_dome_e")), FTransform(FRotator::ZeroRotator, PlanToWorld(C.X, C.Y, Z), FVector(Rad.Y * 0.8 / 16.0, Rad.X * 0.8 / 16.0, 7.0)));
		}
		else if (Kind == TEXT("dock_ring"))
		{
			UStaticMesh* Pad = NX(TEXT("NX_pad"));
			for (double x = -Rad.X; x <= Rad.X; x += 150.0)
			{
				for (double y = -Rad.Y; y <= Rad.Y; y += 150.0)
				{
					if (FMath::Square(x / Rad.X) + FMath::Square(y / Rad.Y) < 0.72)
					{
						Queue(Pad, FTransform(FRotator::ZeroRotator, PlanToWorld(C.X + x, C.Y + y, Z), FVector(2.8)), {}, true);
					}
				}
			}
		}
		else if (Kind == TEXT("park") || Kind == TEXT("plaza"))
		{
			const int32 Count = Kind == TEXT("park") ? 48 : 16;
			for (int32 k = 0; k < Count; ++k)
			{
				const uint32 H = Hash(k * 977U + (Kind == TEXT("park") ? 1U : 2U));
				const double A = Rand01(H) * UE_DOUBLE_TWO_PI;
				const double Rr = Kind == TEXT("park") ? FMath::Sqrt(Rand01(H + 1)) * 0.85 : 0.82;
				const double Ang = Kind == TEXT("park") ? A : UE_DOUBLE_TWO_PI * k / Count;
				Queue(Crystals[k % 3], FTransform(FRotator(0.0, Rand01(H + 2) * 360.0, 0.0),
					PlanToWorld(C.X + FMath::Cos(Ang) * Rad.X * Rr, C.Y + FMath::Sin(Ang) * Rad.Y * Rr, Z), FVector(2.5 + 2.0 * Rand01(H + 3))), {}, true);
			}
		}
	}

	// ---- flush the instances (one batch per mesh)
	for (auto& Pair : Pending)
	{
		UInstancedStaticMeshComponent* C = Instancer(Pair.Key, Pair.Value.Floats, Pair.Value.bCollide);
		if (Pair.Value.CullCm > 0.0f)
		{
			C->SetCullDistances(int32(Pair.Value.CullCm * 0.8f), int32(Pair.Value.CullCm));
		}
		C->AddInstances(Pair.Value.Xf, false, true);
		if (Pair.Value.Floats > 0)
		{
			for (int32 i = 0; i < Pair.Value.Xf.Num(); ++i)
			{
				C->SetCustomData(i, TArrayView<const float>(Pair.Value.Custom.GetData() + i * Pair.Value.Floats, Pair.Value.Floats), false);
			}
			C->MarkRenderStateDirty();
		}
	}
	NightApplied = -1.0f;
	Tick(0.0f);                                   // the windows match the time of day from the first frame
	UE_LOG(LogTemp, Log, TEXT("ASONexusCity: %d instances (%d buildings) of %d meshes (%d missing), %d roads, %d stations, %d steam / %d smoke outlets, %d components"),
		NumInstances, NumBuildings, Pending.Num(), MissingMeshes, RoadEdges.Num(), Stations.Num(), SteamPoints.Num(), SmokePoints.Num(), Built.Num());
}
