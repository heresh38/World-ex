#include "SOProfileStore.h"

#include "Async/Async.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "SOCombatTypes.h"
#include "SOInventoryComponent.h"

namespace
{
	const uint32 SealTag = 0x31504F53;  // "SOP1"
	const uint32 EngineTag = 0x53415647; // "GVAS": the engine's bare save, as written before the seal
	const int32 SealSize = 12;           // tag, length, checksum
}

TArray<uint8> USOProfileStore::Seal(const TArray<uint8>& Payload)
{
	TArray<uint8> File;
	File.SetNumUninitialized(SealSize + Payload.Num());
	const uint32 Length = Payload.Num();
	const uint32 Check = FCrc::MemCrc32(Payload.GetData(), Payload.Num());
	FMemory::Memcpy(File.GetData(), &SealTag, 4);
	FMemory::Memcpy(File.GetData() + 4, &Length, 4);
	FMemory::Memcpy(File.GetData() + 8, &Check, 4);
	FMemory::Memcpy(File.GetData() + SealSize, Payload.GetData(), Payload.Num());
	return File;
}

bool USOProfileStore::Unseal(const TArray<uint8>& File, TArray<uint8>& OutPayload)
{
	uint32 Tag = 0;
	if (File.Num() < 4)
	{
		return false;
	}
	FMemory::Memcpy(&Tag, File.GetData(), 4);
	if (Tag == SealTag && File.Num() >= SealSize)
	{
		uint32 Length = 0, Check = 0;
		FMemory::Memcpy(&Length, File.GetData() + 4, 4);
		FMemory::Memcpy(&Check, File.GetData() + 8, 4);
		if (static_cast<int64>(Length) != File.Num() - SealSize || FCrc::MemCrc32(File.GetData() + SealSize, Length) != Check)
		{
			return false; // cut short or damaged
		}
		OutPayload.SetNumUninitialized(Length);
		FMemory::Memcpy(OutPayload.GetData(), File.GetData() + SealSize, Length);
		return true;
	}
	if (Tag == EngineTag)
	{
		OutPayload = File;
		return true;
	}
	return false;
}

FString USOProfileStore::PathFor(const FString& Key)
{
	return FPaths::ProjectSavedDir() / TEXT("SaveGames") / (Key + TEXT(".sav"));
}

bool USOProfileStore::Migrate(USOSaveGame* Save)
{
	if (!Save)
	{
		return false;
	}
	if (Save->Version > USOSaveGame::CurrentVersion)
	{
		UE_LOG(LogSOCombat, Warning, TEXT("Profile: written by a newer build (version %d, this build knows %d): not used"), Save->Version, USOSaveGame::CurrentVersion);
		return false;
	}
	if (Save->Version < 2)
	{
		// version 1 had no armour and no body: the inventory hands out the wardrobe when it finds none
		Save->Armor.Reset();
		Save->Body = TEXT("male");
	}
	// version 2 -> 3: an armour piece carries its own roll; one without (0) takes it from its uid, so nothing to do
	// version 3 -> 4: what is worn is kept per body; a save without it wears what it wore, and the other body gets
	// its wardrobe's defaults the first time the player takes it, so nothing to do
	// version 4 -> 5: the blades owned (hand to hand); none before, nothing to do
	// version 5 -> 6: the melee slot; None (the fists) before, nothing to do
	Save->Version = USOSaveGame::CurrentVersion;
	return true;
}

USOSaveGame* USOProfileStore::LoadFile(const FString& Path)
{
	for (const FString& File : { Path, Path + TEXT(".bak") })
	{
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *File, FILEREAD_Silent) || Bytes.Num() == 0)
		{
			continue;
		}
		TArray<uint8> Payload;
		if (!Unseal(Bytes, Payload))
		{
			continue; // never hand the engine's reader bytes that are not a save: it asserts
		}
		USOSaveGame* Save = Cast<USOSaveGame>(UGameplayStatics::LoadGameFromMemory(Payload));
		if (Save && Migrate(Save))
		{
			if (File != Path)
			{
				UE_LOG(LogSOCombat, Warning, TEXT("Profile: %s could not be read, its backup was used"), *Path);
			}
			return Save;
		}
	}
	return nullptr;
}

bool USOProfileStore::WriteSafely(const FString& Path, const TArray<uint8>& Bytes)
{
	const FString Tmp = Path + TEXT(".tmp");
	if (!FFileHelper::SaveArrayToFile(Bytes, *Tmp))
	{
		return false;
	}
	IFileManager& Files = IFileManager::Get();
	if (Files.FileExists(*Path))
	{
		Files.Move(*(Path + TEXT(".bak")), *Path, true, true);
	}
	return Files.Move(*Path, *Tmp, true, true);
}

USOSaveGame* USOProfileStore::Load(const FString& Key)
{
	Flush(); // what was committed a moment ago is what is read
	return LoadFile(PathFor(Key));
}

void USOProfileStore::Commit(const FString& Key, USOSaveGame* Snapshot)
{
	if (!Snapshot)
	{
		return;
	}
	Snapshot->Version = USOSaveGame::CurrentVersion;
	TArray<uint8> Bytes;
	if (!UGameplayStatics::SaveGameToMemory(Snapshot, Bytes))
	{
		UE_LOG(LogSOCombat, Warning, TEXT("Profile: %s could not be serialised"), *Key);
		return;
	}
	Pending.Add(Key, Seal(Bytes));
	StartNext();
}

void USOProfileStore::StartNext()
{
	if (bWriting || Pending.Num() == 0)
	{
		return;
	}
	auto It = Pending.CreateIterator();
	const FString Path = PathFor(It.Key());
	TArray<uint8> Bytes = MoveTemp(It.Value());
	It.RemoveCurrent();
	bWriting = true;
	TWeakObjectPtr<USOProfileStore> Self(this);
	InFlight = Async(EAsyncExecution::ThreadPool, [Path, Bytes = MoveTemp(Bytes), Self]()
	{
		const bool bOk = WriteSafely(Path, Bytes);
		AsyncTask(ENamedThreads::GameThread, [Self, bOk, Path]()
		{
			if (!bOk)
			{
				UE_LOG(LogSOCombat, Warning, TEXT("Profile: %s could not be written"), *Path);
			}
			if (USOProfileStore* Store = Self.Get())
			{
				Store->bWriting = false;
				Store->StartNext();
			}
		});
		return bOk;
	});
}

void USOProfileStore::Flush()
{
	if (InFlight.IsValid())
	{
		InFlight.Wait();
	}
	bWriting = false;
	for (const TPair<FString, TArray<uint8>>& Left : Pending)
	{
		WriteSafely(PathFor(Left.Key), Left.Value);
	}
	Pending.Reset();
}

void USOProfileStore::Deinitialize()
{
	Flush();
	Super::Deinitialize();
}
