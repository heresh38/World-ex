// What is drawn is what collides: a Nanite mesh's own complex collision is built from its simplified fallback (the
// Crown kept 3 % of its triangles, and shots, creatures and the nav mesh went through what was drawn), so every Nanite
// mesh that is collided with takes its collision from an exact twin (import_assets._nanite_solid).

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "AssetRegistry/AssetRegistryModule.h"
#include "Chaos/TriangleMeshImplicitObject.h"
#include "Engine/StaticMesh.h"
#include "PhysicsEngine/BodySetup.h"
#include "StaticMeshResources.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSONaniteCollisionTest, "ShatteredOrbit.World.NaniteCollidesExactly", SOTest::Flags)
bool FSONaniteCollisionTest::RunTest(const FString& Parameters)
{
	// every Nanite mesh with complex collision of Nexus Prime's kit and tiles and of the operations' shared pieces
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	Registry.ScanPathsSynchronous({ TEXT("/Game/Environments/NexusCity"), TEXT("/Game/Shared/Operation") });
	TArray<FAssetData> Found;
	for (const TCHAR* Path : { TEXT("/Game/Environments/NexusCity"), TEXT("/Game/Shared/Operation") })
	{
		Registry.GetAssetsByPath(FName(Path), Found, true);
	}
	int32 Checked = 0, Finer = 0;
	for (const FAssetData& Asset : Found)
	{
		if (Asset.AssetClassPath != UStaticMesh::StaticClass()->GetClassPathName())
		{
			continue;
		}
		UStaticMesh* Mesh = Cast<UStaticMesh>(Asset.GetAsset());
		UBodySetup* Body = Mesh ? Mesh->GetBodySetup() : nullptr;
		if (!Mesh || !Mesh->IsNaniteEnabled() || !Body || Body->CollisionTraceFlag != CTF_UseComplexAsSimple)
		{
			continue;                                                // (drawn only: trees, a level's detail)
		}
		++Checked;
		UStaticMesh* Twin = Mesh->ComplexCollisionMesh;
		if (!TestNotNull(FString::Printf(TEXT("%s collides with an exact twin"), *Mesh->GetName()), Twin))
		{
			continue;
		}
		TestFalse(FString::Printf(TEXT("%s's twin is not Nanite"), *Mesh->GetName()), Twin->IsNaniteEnabled());
		TestEqual(FString::Printf(TEXT("%s's twin has its slots"), *Mesh->GetName()), Twin->GetStaticMaterials().Num(), Mesh->GetStaticMaterials().Num());
		const int32 TwinTris = Twin->GetRenderData() && Twin->GetRenderData()->LODResources.Num() > 0 ? Twin->GetRenderData()->LODResources[0].GetNumTriangles() : 0;
		const int32 Fallback = Mesh->GetRenderData() && Mesh->GetRenderData()->LODResources.Num() > 0 ? Mesh->GetRenderData()->LODResources[0].GetNumTriangles() : 0;
		Body->CreatePhysicsMeshes();
		int32 BodyTris = 0;
		for (const Chaos::FTriangleMeshImplicitObjectPtr& Tri : Body->TriMeshGeometries)
		{
			BodyTris += Tri ? Tri->Elements().GetNumTriangles() : 0;
		}
		// (the physics cook drops what has no area)
		TestTrue(FString::Printf(TEXT("%s collides with every triangle of its twin (%d of %d; the fallback has %d)"), *Mesh->GetName(), BodyTris, TwinTris, Fallback),
			TwinTris > 0 && BodyTris >= FMath::FloorToInt(TwinTris * 0.97f));
		Finer += BodyTris > Fallback ? 1 : 0;
	}
	TestTrue(FString::Printf(TEXT("the city's kit and the operations' pieces were looked at (%d)"), Checked), Checked >= 100);
	AddInfo(FString::Printf(TEXT("%d of %d collide more finely than their fallback would have"), Finer, Checked));
	return true;
}

#endif
