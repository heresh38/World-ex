#pragma once

#include "CoreMinimal.h"

/**
 * Where the game's own data files are (areas.json, an operation's plan, the city's plan and instances).
 * In development they are read from the project's Data folder, where the tools write them. A packaged game has no
 * project folder: tools/package.sh copies them to Content/Staged/Data, which is staged into the package, and
 * they are read from there. Every runtime read of a loose file goes through here.
 */
namespace SOData
{
	/** Full path of a file given relative to the project ("Data/areas.json"). */
	SOCORE_API FString Path(const FString& Relative);

	SOCORE_API bool LoadText(const FString& Relative, FString& OutText);
	SOCORE_API bool LoadBytes(const FString& Relative, TArray<uint8>& OutBytes);
}
