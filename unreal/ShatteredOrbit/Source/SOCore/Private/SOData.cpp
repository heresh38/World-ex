#include "SOData.h"

#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

FString SOData::Path(const FString& Relative)
{
	const FString InProject = FPaths::ProjectDir() / Relative;
	if (IFileManager::Get().FileExists(*InProject))
	{
		return InProject;
	}
	// a packaged game: the copy staged with the content
	return FPaths::ProjectContentDir() / TEXT("Staged") / Relative;
}

bool SOData::LoadText(const FString& Relative, FString& OutText)
{
	return FFileHelper::LoadFileToString(OutText, *Path(Relative));
}

bool SOData::LoadBytes(const FString& Relative, TArray<uint8>& OutBytes)
{
	return FFileHelper::LoadFileToArray(OutBytes, *Path(Relative));
}
