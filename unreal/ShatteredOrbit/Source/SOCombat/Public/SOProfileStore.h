#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "SOProfileStore.generated.h"

class USOSaveGame;

/**
 * Where a player's profile is kept. The ONE place that reads or writes it: gameplay hands over a snapshot
 * (Commit) or asks for the saved one (Load) and knows nothing about files. Today it is the local file the game has
 * always used (Saved/SaveGames/<Key>.sav, so existing saves load); an online service takes this class's place behind
 * the same three calls.
 *
 * A write never stalls the game and never leaves a broken file: the snapshot is serialised when it is committed,
 * written off the game thread to <file>.tmp, then the file in place is kept as <file>.bak and the new one moved in.
 * One write at a time; if more snapshots arrive meanwhile only the latest is written next. What is written is
 * sealed (a tag, the length and a checksum in front of the engine's save bytes): the engine's own reader asserts on
 * a damaged file, so a file is only handed to it once the seal checks out. A file that does not, falls back to its
 * .bak. Saves from before the seal (the engine's bare format) still load. Every load is brought to the current version (USOSaveGame::CurrentVersion); a file
 * written by a newer build is refused rather than misread.
 */
UCLASS()
class SOCOMBAT_API USOProfileStore : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** The saved profile, migrated to the current version; null if there is none or neither file can be read. */
	USOSaveGame* Load(const FString& Key);

	/** Records the profile as it is now. */
	void Commit(const FString& Key, USOSaveGame* Snapshot);

	/** Blocks until everything committed is on disk (leaving the game). */
	void Flush();

	//~ UGameInstanceSubsystem
	virtual void Deinitialize() override;

	static FString PathFor(const FString& Key);

	/** Path, or its .bak if Path cannot be read; migrated. */
	static USOSaveGame* LoadFile(const FString& Path);

	/** Bytes to Path by way of .tmp, the file in place kept as .bak. */
	static bool WriteSafely(const FString& Path, const TArray<uint8>& Bytes);

	/** The engine's save bytes with the seal in front. */
	static TArray<uint8> Seal(const TArray<uint8>& Payload);

	/** The save bytes out of a file's bytes: false if the seal is broken or the file is neither sealed nor a bare
	 *  engine save. */
	static bool Unseal(const TArray<uint8>& File, TArray<uint8>& OutPayload);

	/** Brings a loaded save to the current version; false if it cannot be used. */
	static bool Migrate(USOSaveGame* Save);

private:
	void StartNext();

	TMap<FString, TArray<uint8>> Pending; // by key: the latest snapshot not yet written
	TFuture<bool> InFlight;
	bool bWriting = false;
};
