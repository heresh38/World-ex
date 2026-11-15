#include "SODifficulty.h"

#include "Engine/World.h"
#include "SOLog.h"

const FSODifficulty* USODifficultyTable::Find(FName Id) const
{
	return Levels.FindByPredicate([Id](const FSODifficulty& L) { return L.Id == Id; });
}

void USODifficultySubsystem::Load()
{
	if (bLoaded)
	{
		return;
	}
	bLoaded = true; // once per world, as the first creature asks: never in a tick after that
	Table = Cast<USODifficultyTable>(FSoftObjectPath(TEXT("/Game/Data/DA_Difficulty.DA_Difficulty")).TryLoad());
	if (const FSODifficulty* Level = Table ? Table->Find(Table->Default) : nullptr)
	{
		Current = *Level;
	}
}

const FSODifficulty& USODifficultySubsystem::GetLevel()
{
	Load();
	return Current;
}

bool USODifficultySubsystem::SetLevel(FName Id)
{
	Load();
	const FSODifficulty* Level = Table ? Table->Find(Id) : nullptr;
	if (!Level)
	{
		UE_LOG(LogShatteredOrbit, Warning, TEXT("Difficulty: no level '%s' (Data/game_data.json \"difficulty\"; import with SO_IMPORT_ONLY=difficulty)"), *Id.ToString());
		return false;
	}
	Current = *Level;
	UE_LOG(LogShatteredOrbit, Log, TEXT("Difficulty: %s"), *Id.ToString());
	return true;
}

const FSODifficulty& USODifficultySubsystem::Get(const UObject* WorldContext)
{
	static const FSODifficulty AsWritten;
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	USODifficultySubsystem* Levels = World ? World->GetSubsystem<USODifficultySubsystem>() : nullptr;
	return Levels ? Levels->GetLevel() : AsWritten;
}
