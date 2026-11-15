#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "SOEditorLibrary.generated.h"

class USkeletalMesh;
class UMaterialInterface;
class UTexture;

/** What the import script needs from the editor that its Python cannot reach. */
UCLASS()
class SOEDITOR_API USOEditorLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Fits a skeletal mesh's physics bodies to what is drawn: one convex hull per bone round the vertices that bone
	 * moves most (Hulls > 1: that many, for a hollow or forked part), bones shorter than MinBoneSize cm folded into
	 * their parent. They replace whatever bodies its physics asset had (the engine's automatic ones are a few fat
	 * capsules: on a creature with a shell or spikes they stood a metre off its surface, and small bones such as a
	 * head got none). No constraints: these bodies are only what a round, a blow or a line of sight lands on.
	 * Returns how many bodies it made (0: nothing changed).
	 */
	UFUNCTION(BlueprintCallable, Category = "SO|Editor")
	static int32 FitBodies(USkeletalMesh* Mesh, float MinBoneSize = 10.0f, int32 Hulls = 1, int32 MaxHullVerts = 24);

	/**
	 * Tells the texture streamer how a material reads one of its textures: through which UV set, and how many times
	 * it repeats across a unit of it. The engine works this out only in its own editor build step, which the import
	 * (a commandlet with no renderer) never runs; without it every texture is taken to lie once across UV 0. An
	 * asset's own baked maps lie on UV 1 across the whole asset, so the streamer held them several mips too small
	 * (a gun's markings were a smudge with the full-size map sitting on the disk). Replaces any entry for the
	 * same texture; the instances made from this material inherit it.
	 */
	UFUNCTION(BlueprintCallable, Category = "SO|Editor")
	static bool SetTextureSampling(UMaterialInterface* Material, UTexture* Texture, int32 UVChannel = 0, float Scale = 1.0f);
};
