#include "SOEditorLibrary.h"

#include "Engine/SkeletalMesh.h"
#include "Engine/Texture.h"
#include "Materials/MaterialInterface.h"
#include "PhysicsAssetUtils.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

int32 USOEditorLibrary::FitBodies(USkeletalMesh* Mesh, float MinBoneSize, int32 Hulls, int32 MaxHullVerts)
{
	UPhysicsAsset* Asset = Mesh ? Mesh->GetPhysicsAsset() : nullptr;
	if (!Asset || !Mesh->GetResourceForRendering())
	{
		return 0;
	}
	FPhysAssetCreateParams Params;
	Params.MinBoneSize = FMath::Max(MinBoneSize, 1.0f);
	Params.GeomType = Hulls > 1 ? EFG_MultiConvexHull : EFG_SingleConvexHull;
	Params.HullCount = FMath::Max(Hulls, 1);
	Params.MaxHullVerts = FMath::Clamp(MaxHullVerts, 8, 32);
	Params.VertWeight = EVW_DominantWeight;
	Params.bWalkPastSmall = false;       // a small bone's part goes to its parent's body, it is not left out
	Params.bCreateConstraints = false;
	Params.bBodyForAll = false;

	Asset->Modify();
	Asset->SkeletalBodySetups.Empty();
	Asset->ConstraintSetup.Empty();
	Asset->CollisionDisableTable.Empty();
	Asset->UpdateBodySetupIndexMap();
	Asset->UpdateBoundsBodiesArray();

	FText Error;
	if (!FPhysicsAssetUtils::CreateFromSkeletalMesh(Asset, Mesh, Params, Error, true, false))
	{
		UE_LOG(LogTemp, Warning, TEXT("FitBodies: %s: %s"), *Mesh->GetName(), *Error.ToString());
	}
	Asset->UpdateBodySetupIndexMap();
	Asset->UpdateBoundsBodiesArray();
	Asset->MarkPackageDirty();
	return Asset->SkeletalBodySetups.Num();
}

bool USOEditorLibrary::SetTextureSampling(UMaterialInterface* Material, UTexture* Texture, int32 UVChannel, float Scale)
{
	if (!Material || !Texture || UVChannel < 0 || UVChannel > 3 || Scale <= KINDA_SMALL_NUMBER)
	{
		return false;
	}
	TArray<FMaterialTextureInfo> Data = Material->GetTextureStreamingData();
	const FName Name = Texture->GetFName();
	Data.RemoveAll([Name](const FMaterialTextureInfo& Info) { return Info.TextureName == Name; });
	FMaterialTextureInfo Info;
	Info.SamplingScale = Scale;
	Info.UVChannelIndex = UVChannel;
	Info.TextureName = Name;
#if WITH_EDITORONLY_DATA
	Info.TextureReference = FSoftObjectPath(Texture);
#endif
	Data.Add(Info);
	Material->SetTextureStreamingData(Data);
	Material->MarkPackageDirty();
	return true;
}
