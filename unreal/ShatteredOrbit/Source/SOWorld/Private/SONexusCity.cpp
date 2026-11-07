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
	NumBuildings = NumLamps = 0;
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

	// ---- the baked plan: tiles and the land
	for (const TSharedPtr<FJsonValue>& V : City->GetArrayField(TEXT("tiles")))
	{
		const TSharedPtr<FJsonObject> T = V->AsObject();
		AddMesh(LoadMesh(T->GetStringField(TEXT("name")), true), FTransform::Identity);    // tiles keep world coordinates
	}
	AddMesh(LoadMesh(City->GetStringField(TEXT("land")), true), FTransform::Identity);

	// ---- road graph (for traffic and people later; also the lamps)
	const TSharedPtr<FJsonObject> Roads = Plan->GetObjectField(TEXT("roads"));
	const TSharedPtr<FJsonObject> Lanes = City->GetObjectField(TEXT("lanes"));
	for (const TSharedPtr<FJsonValue>& V : Roads->GetArrayField(TEXT("nodes")))
	{
		const FVector2D P = Pt(V);
		RoadNodes.Add(PlanToWorld(P.X, P.Y));
	}
	TArray<int32> Degree;
	TArray<double> WidthAt;
	Degree.SetNumZeroed(RoadNodes.Num());
	WidthAt.SetNumZeroed(RoadNodes.Num());
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
		for (int32 N : { R.A, R.B })
		{
			if (RoadNodes.IsValidIndex(N))
			{
				Degree[N]++;
				WidthAt[N] = FMath::Max(WidthAt[N], (double)R.Width);
			}
		}
		RoadEdges.Add(MoveTemp(R));
	}

	// ---- street lamps on both kerbs (not on the access lanes), clear of the junctions
	UStaticMesh* Lamp = LoadMesh(TEXT("NCK_lamp"));
	for (const FSORoadEdge& R : RoadEdges)
	{
		if (R.Class == TEXT("access") || R.Points.Num() < 2)
		{
			continue;
		}
		auto Gap = [&](int32 N) { return RoadNodes.IsValidIndex(N) && Degree[N] >= 3 ? WidthAt[N] * 0.5 + 900.0 : 300.0; };
		double S = 0.0;
		const double Start = Gap(R.A);
		double Total = 0.0;
		for (int32 i = 1; i < R.Points.Num(); ++i)
		{
			Total += FVector::Dist2D(R.Points[i - 1], R.Points[i]);
		}
		const double End = Total - Gap(R.B);
		double Next = Start;
		for (int32 i = 1; i < R.Points.Num() && Next <= End; ++i)
		{
			const FVector A = R.Points[i - 1], B = R.Points[i];
			const double L = FVector::Dist2D(A, B);
			const FVector Dir = (B - A).GetSafeNormal2D();
			const FVector Left(-Dir.Y, Dir.X, 0.0);       // world: X = N, Y = E (left-handed); either side works
			while (Next <= S + L && Next <= End)
			{
				const FVector P = A + Dir * (Next - S);
				for (int32 Side : { -1, 1 })
				{
					const FVector At = P + Left * Side * (R.Width * 0.5 + 120.0) + FVector(0, 0, Kerb * 100.0);
					const FVector Toward = -Left * Side;      // the lamp's arm reaches along its local +Y (Blender -y)
					const double Yaw = FMath::RadiansToDegrees(FMath::Atan2(-Toward.X, Toward.Y));
					Queue(Lamp, FTransform(FRotator(0.0, Yaw, 0.0), At), {}, true);
					NumLamps++;
				}
				Next += LampSpacing * 100.0;
			}
			S += L;
		}
	}

	// ---- buildings on the lots
	const TSharedPtr<FJsonObject> Designs = City->GetObjectField(TEXT("designs"));
	const TSharedPtr<FJsonObject> Kinds = City->GetObjectField(TEXT("kinds"));
	const TSharedPtr<FJsonObject> Props = City->GetObjectField(TEXT("props"));
	TArray<UStaticMesh*> RoofProps;
	for (const TSharedPtr<FJsonValue>& V : Props->GetArrayField(TEXT("roof")))
	{
		RoofProps.Add(LoadMesh(V->AsString()));
	}
	struct FDesign { UStaticMesh* Mesh = nullptr; double MinH = 0, MaxH = 1e9; bool bTall = false; bool bRoof = false; double Roof[5] = {}; };
	TMap<FString, FDesign> DesignInfo;
	for (const auto& Pair : Designs->Values)
	{
		const TSharedPtr<FJsonObject> D = Pair.Value->AsObject();
		FDesign Info;
		Info.Mesh = LoadMesh(FString(Pair.Key));
		Info.MinH = D->GetNumberField(TEXT("min_h"));
		Info.MaxH = D->GetNumberField(TEXT("max_h"));
		Info.bTall = D->GetBoolField(TEXT("tall"));
		const FJsonArray* Roof = nullptr;
		if (D->TryGetArrayField(TEXT("roof"), Roof) && Roof->Num() == 5)
		{
			Info.bRoof = true;
			for (int32 k = 0; k < 5; ++k)
			{
				Info.Roof[k] = (*Roof)[k]->AsNumber();
			}
		}
		DesignInfo.Add(FString(Pair.Key), Info);
	}
	const FJsonArray& Lots = Plan->GetArrayField(TEXT("lots"));
	for (int32 Li = 0; Li < Lots.Num(); ++Li)
	{
		const TSharedPtr<FJsonObject> Lot = Lots[Li]->AsObject();
		const TArray<FVector2D> P = Poly(Lot->GetArrayField(TEXT("poly")));
		if (P.Num() < 3)
		{
			continue;
		}
		FRect R = MinRect(P);
		// shrink until the rectangle sits inside the lot (clipped lots at the block edges)
		const FVector2D N(-R.A.Y, R.A.X);
		bool bFits = false;
		for (int32 Try = 0; Try < 7 && !bFits; ++Try)
		{
			bFits = true;
			for (int32 sa : { -1, 1 })
			{
				for (int32 sn : { -1, 1 })
				{
					const FVector2D Corner = R.C + R.A * (sa * (R.W * 0.5 - 0.3)) + N * (sn * (R.D * 0.5 - 0.3));
					bFits &= Inside(Corner, P);
				}
			}
			if (!bFits)
			{
				R.W *= 0.9;
				R.D *= 0.9;
			}
		}
		if (!bFits || R.W < MinLotSize || R.D < MinLotSize)
		{
			continue;
		}
		const FString Kind = Lot->GetStringField(TEXT("kind"));
		const FJsonArray* List = nullptr;
		if (!Kinds->TryGetArrayField(Kind, List) || List->Num() == 0)
		{
			continue;
		}
		const double H0 = Lot->GetNumberField(TEXT("h"));
		const uint32 Seed = Hash(Li * 2654435761U + 17U);
		const FDesign* Pick = nullptr;
		for (int32 k = 0; k < List->Num() && !Pick; ++k)
		{
			const FDesign* D = DesignInfo.Find((*List)[(Seed + k) % List->Num()]->AsString());
			if (D && D->Mesh && H0 >= D->MinH && (!D->bTall || (H0 >= 30.0 && FMath::Min(R.W, R.D) >= 14.0)))
			{
				Pick = D;
			}
		}
		if (!Pick)
		{
			continue;
		}
		const double H = FMath::Min(H0, Pick->MaxH);
		const FVector Centre = PlanToWorld(R.C.X, R.C.Y, Kerb);
		const FRotator Rot(0.0, YawAlong(R.A), 0.0);
		const FTransform Xf(Rot, Centre, FVector(R.W, R.D, H));
		const float S = Rand01(Seed ^ 0x5bd1e995U) * 100.0f;
		Queue(Pick->Mesh, Xf, { (float)R.W, (float)R.D, (float)H, S }, true);
		NumBuildings++;
		// roof clutter (real size) on the flat roof
		if (Pick->bRoof && RoofProps.Num())
		{
			const double* Rf = Pick->Roof;
			const double Area = (Rf[1] - Rf[0]) * R.W * (Rf[3] - Rf[2]) * R.D;
			const int32 Count = FMath::Min(3, (int32)(Area / 180.0 * Rand01(Seed + 3)));
			for (int32 k = 0; k < Count; ++k)
			{
				const double bx = FMath::Lerp(Rf[0], Rf[1], 0.15 + 0.7 * Rand01(Seed + 11 * k + 5));
				const double by = FMath::Lerp(Rf[2], Rf[3], 0.15 + 0.7 * Rand01(Seed + 13 * k + 7));
				const FVector Local(bx * 100.0, -by * 100.0, Rf[4] * 100.0);     // Blender unit (x, y, z) -> mesh cm
				const FVector At = Xf.TransformPosition(Local);
				int32 Which = (int32)(Rand01(Seed + 17 * k) * RoofProps.Num()) % RoofProps.Num();
				if (Which == RoofProps.Num() - 1 && H < 60.0)
				{
					Which = 0;                                            // masts only on the tall ones
				}
				Queue(RoofProps[Which], FTransform(FRotator(0.0, Rot.Yaw + 90.0 * (int32)(Rand01(Seed + k) * 4), 0.0), At), {}, false);
			}
		}
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
	UE_LOG(LogTemp, Log, TEXT("ASONexusCity: %d buildings, %d lamps, %d roads, %d stations, %d components"),
		NumBuildings, NumLamps, RoadEdges.Num(), Stations.Num(), Built.Num());
}
