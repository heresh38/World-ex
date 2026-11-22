// The journal (the armoury's JOURNAL tab; the owner's armoury reference: "a journal of what was learned"): its pages are
// data and whole, an operation's are its plan's own words, what a profile learns and reads is kept and saved, a kill
// teaches every player in the world and counts for the one who made it, a player's death is counted.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOCombatStatics.h"
#include "SOData.h"
#include "SOEnemy.h"
#include "SOInventoryComponent.h"
#include "SOJournal.h"
#include "SOPlayerState.h"
#include "SOProfileStore.h"
#include "SOSpecies.h"

namespace
{
	USOInventoryComponent* JournalInventory()
	{
		USOInventoryComponent* Inv = NewObject<USOInventoryComponent>();
		Inv->bPersist = false;
		Inv->NewProfile();
		return Inv;
	}

	ASOPlayerState* JournalPlayer(SOTest::FTestWorld& W, ASOCharacter* Body)
	{
		FActorSpawnParameters Params;
		Params.bDeferConstruction = true;
		ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, Params);
		PS->GetInventory()->bPersist = false;
		PS->FinishSpawning(FTransform::Identity);
		if (Body)
		{
			Body->SetPlayerState(PS);
		}
		return PS;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOJournalDataTest, "ShatteredOrbit.Journal.EveryPageIsWhole", SOTest::Flags)
bool FSOJournalDataTest::RunTest(const FString& Parameters)
{
	// every page is in a section, has a title and words, and is taught by a key the game teaches; every rank of the
	// Sarketh has its page and its portrait; Meridian Fall's pages are its plan's own (briefing, every stage the radio
	// speaks at, the outcome)
	const FSOJournalData& Journal = FSOJournalData::Get();
	TestTrue(TEXT("the journal has its sections (Data/journal.json)"), Journal.Sections.Num() >= 4);
	TestTrue(TEXT("and its pages"), Journal.Entries.Num() >= 30);
	TSet<FName> Ids;
	for (const FSOJournalEntry& E : Journal.Entries)
	{
		TestFalse(FString::Printf(TEXT("%s is one page"), *E.Id.ToString()), Ids.Contains(E.Id));
		Ids.Add(E.Id);
		TestNotNull(FString::Printf(TEXT("%s's section %s"), *E.Id.ToString(), *E.Section.ToString()), Journal.FindSection(E.Section));
		TestFalse(FString::Printf(TEXT("%s has a title"), *E.Id.ToString()), E.Title.IsEmpty());
		TestFalse(FString::Printf(TEXT("%s has words"), *E.Id.ToString()), E.Text.IsEmpty());
		const FString Key = E.Unlock.ToString();
		const bool bKnownKey = E.Unlock == SOJournal::StartKey() || Key.StartsWith(TEXT("met:")) || Key.StartsWith(TEXT("named:"))
			|| Key.StartsWith(TEXT("stage:")) || Key.StartsWith(TEXT("done:")) || Key.StartsWith(TEXT("origin:"));
		TestTrue(FString::Printf(TEXT("%s is taught by a key the game teaches (%s)"), *E.Id.ToString(), *Key), bKnownKey);
		if (!E.Picture.IsNone())
		{
			for (const TCHAR* Suffix : { TEXT(""), TEXT("_bust") })
			{
				const FString Name = FString::Printf(TEXT("T_Journal_%s%s"), *E.Picture.ToString(), Suffix);
				TestNotNull(FString::Printf(TEXT("%s's picture %s (SO_IMPORT_ONLY=journal)"), *E.Id.ToString(), *Name),
					Cast<UTexture2D>(FSoftObjectPath(FString::Printf(TEXT("/Game/UI/Journal/%s.%s"), *Name, *Name)).TryLoad()));
			}
		}
	}
	// every species that fights (the conduit is a machine) has a page taught by its dead
	for (const FName Species : { FName(TEXT("remnant")), FName(TEXT("stalker")), FName(TEXT("veilborn")), FName(TEXT("stalker_feral")), FName(TEXT("bulwark")), FName(TEXT("bearer")), FName(TEXT("colossus")) })
	{
		TestTrue(FString::Printf(TEXT("%s has its page"), *Species.ToString()), Journal.UnlockedBy(SOJournal::MetKey(Species)).Num() > 0);
		TestNotNull(FString::Printf(TEXT("%s is a species"), *Species.ToString()), USOSpeciesLibrary::Find(Species).Get());
	}
	// Meridian Fall: its briefing with its first stage, a page for every stage the radio speaks at, its outcome
	FString Text;
	TSharedPtr<FJsonObject> Plan;
	if (TestTrue(TEXT("op_meridian.json reads"), SOData::LoadText(TEXT("Data/op_meridian.json"), Text) && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Plan) && Plan.IsValid()))
	{
		const TArray<TSharedPtr<FJsonValue>>& Stages = Plan->GetArrayField(TEXT("stages"));
		const FName First(*Stages[0]->AsObject()->GetStringField(TEXT("id")));
		const FSOJournalEntry* Briefing = Journal.Find(TEXT("meridian_briefing"));
		TestTrue(TEXT("the briefing is a page, shown as the first stage begins"), Briefing && Briefing->Unlock == SOJournal::StageKey(TEXT("meridian"), First));
		int32 Spoken = 0;
		for (const TSharedPtr<FJsonValue>& V : Stages)
		{
			const TSharedPtr<FJsonObject> S = V->AsObject();
			if (S->HasField(TEXT("intel")))
			{
				++Spoken;
				const FName Id(*FString::Printf(TEXT("meridian_%s"), *S->GetStringField(TEXT("id"))));
				const FSOJournalEntry* Page = Journal.Find(Id);
				TestTrue(FString::Printf(TEXT("%s is a page with the radio's words"), *Id.ToString()), Page && Page->Text == S->GetObjectField(TEXT("intel"))->GetStringField(TEXT("text")));
			}
		}
		TestTrue(TEXT("the radio speaks at most stages"), Spoken >= 15);
		const FSOJournalEntry* Outcome = Journal.Find(TEXT("meridian_outcome"));
		TestTrue(TEXT("the outcome is a page, shown when it is done"), Outcome && Outcome->Unlock == SOJournal::DoneKey(TEXT("meridian")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOJournalLearnTest, "ShatteredOrbit.Journal.LearnedReadAndKept", SOTest::Flags)
bool FSOJournalLearnTest::RunTest(const FString& Parameters)
{
	USOInventoryComponent* Inv = JournalInventory();
	// a new profile knows the war and the makers of the guns it starts with, and none of the Sarketh
	TestTrue(TEXT("the war's first pages are open"), Inv->IsJournalOpen(TEXT("war_empire")));
	TestTrue(TEXT("unread"), Inv->IsJournalNew(TEXT("war_empire")));
	TestTrue(TEXT("so the tab is marked"), Inv->HasJournalNew());
	TestTrue(TEXT("the city's steel is known from the guns owned"), Inv->HasLearned(SOJournal::OriginKey(TEXT("nexus"))));
	TestFalse(TEXT("a Levy is not known before one is killed"), Inv->IsJournalOpen(TEXT("sarketh_levy")));
	TestFalse(TEXT("nor the end of an operation not finished"), Inv->IsJournalOpen(TEXT("war_fear")));
	// learned: open and new, a line in the feed; read: no longer new
	TArray<FString> Lines;
	Inv->OnFeed.AddLambda([&Lines](const FString& Line, const FLinearColor&) { Lines.Add(Line); });
	Inv->Learn(SOJournal::MetKey(TEXT("remnant")));
	TestTrue(TEXT("learned"), Inv->IsJournalOpen(TEXT("sarketh_levy")));
	TestTrue(TEXT("new"), Inv->IsJournalNew(TEXT("sarketh_levy")));
	TestTrue(TEXT("the feed says so"), Lines.ContainsByPredicate([](const FString& L) { return L.Contains(TEXT("JOURNAL")) && L.Contains(TEXT("Levy")); }));
	const int32 Said = Lines.Num();
	Inv->Learn(SOJournal::MetKey(TEXT("remnant")));
	TestEqual(TEXT("learned once"), Lines.Num(), Said);
	Inv->MarkJournalRead(TEXT("sarketh_levy"));
	TestFalse(TEXT("read"), Inv->IsJournalNew(TEXT("sarketh_levy")));
	Inv->MarkJournalRead(TEXT("sarketh_warden"));
	TestFalse(TEXT("a page not learned is not read"), Inv->IsJournalOpen(TEXT("sarketh_warden")) || Inv->IsJournalNew(TEXT("sarketh_warden")));
	// an operation's own pages come quietly (its banner and its radio say it)
	Lines.Reset();
	Inv->Learn(SOJournal::StageKey(TEXT("meridian"), TEXT("verge")));
	TestTrue(TEXT("its briefing is open"), Inv->IsJournalOpen(TEXT("meridian_briefing")));
	TestFalse(TEXT("without a line in the feed"), Lines.ContainsByPredicate([](const FString& L) { return L.Contains(TEXT("Meridian Fall")); }));
	TestTrue(TEXT("what it teaches beside them has its line (the Directorate)"), Lines.ContainsByPredicate([](const FString& L) { return L.Contains(TEXT("Rampart")); }));
	// tallies count
	Inv->Tally(SOJournal::KillTally(TEXT("remnant")));
	Inv->Tally(SOJournal::KillTally(TEXT("remnant")), 4);
	TestEqual(TEXT("five Levies"), Inv->GetTally(SOJournal::KillTally(TEXT("remnant"))), 5);
	// a new profile starts over
	Inv->NewProfile();
	TestFalse(TEXT("a new profile knows no Levy"), Inv->IsJournalOpen(TEXT("sarketh_levy")));
	TestEqual(TEXT("and has killed none"), Inv->GetTally(SOJournal::KillTally(TEXT("remnant"))), 0);
	// a save from before the journal is migrated with nothing learned
	USOSaveGame* Old = NewObject<USOSaveGame>();
	Old->Version = 9;
	TestTrue(TEXT("migrated"), USOProfileStore::Migrate(Old));
	TestEqual(TEXT("to this build's version"), Old->Version, USOSaveGame::CurrentVersion);
	TestEqual(TEXT("nothing learned"), Old->Learned.Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOJournalKillTest, "ShatteredOrbit.Journal.AKillTeachesEveryPlayer", SOTest::Flags)
bool FSOJournalKillTest::RunTest(const FString& Parameters)
{
	// two players in the world: the Levy one of them kills teaches both, counts for the killer only; a named one's
	// name is learned; a player's death is counted for that player
	SOTest::FTestWorld W;
	W.AddBox(FVector(-4000, -4000, -100), FVector(4000, 4000, 0));
	ASOCharacter* One = W.SpawnCharacter(FVector(0, 0, 0));
	ASOCharacter* Two = W.SpawnCharacter(FVector(0, 400, 0));
	ASOPlayerState* PS1 = JournalPlayer(W, One);
	ASOPlayerState* PS2 = JournalPlayer(W, Two);
	W.Run(0.2f);
	USOInventoryComponent* Inv1 = PS1->GetInventory();
	USOInventoryComponent* Inv2 = PS2->GetInventory();
	if (!TestNotNull(TEXT("inventories"), Inv1) || !TestNotNull(TEXT("inventories"), Inv2))
	{
		return false;
	}
	FSOSpeciesVariant V;
	V.Id = TEXT("remnant_captain");
	V.DisplayName = FText::FromString(TEXT("Levy Captain"));
	FSOSpawnOptions Options;
	Options.bOnNav = false;
	Options.Variant = &V;
	ASOEnemy* E = USOSpeciesLibrary::Spawn(W.World, TEXT("remnant"), FVector(800, 0, 0), 180.0f, Options);
	if (!TestNotNull(TEXT("a Levy (/Game/Characters/Sarketh imported)"), E))
	{
		return false;
	}
	if (AController* Brain = E->GetController())
	{
		Brain->UnPossess();
		Brain->Destroy();
	}
	W.Run(0.1f);
	USOCombatStatics::ApplyDamage(One, E, 100000.0f, false);
	W.Run(0.1f);
	TestTrue(TEXT("the Levy died"), E->IsDead());
	for (USOInventoryComponent* Inv : { Inv1, Inv2 })
	{
		TestTrue(TEXT("every player learned the Levy"), Inv->IsJournalOpen(TEXT("sarketh_levy")));
		TestTrue(TEXT("and the captain's name"), Inv->IsJournalOpen(TEXT("named_captain")));
	}
	TestEqual(TEXT("the killer counts it"), Inv1->GetTally(SOJournal::KillTally(TEXT("remnant"))), 1);
	TestEqual(TEXT("among all its kills"), Inv1->GetTally(SOJournal::KillsTally()), 1);
	TestEqual(TEXT("a named one"), Inv1->GetTally(SOJournal::NamedTally()), 1);
	TestEqual(TEXT("the other does not"), Inv2->GetTally(SOJournal::KillTally(TEXT("remnant"))), 0);
	// a player down is on that player's record
	Two->Die(One);
	W.Run(0.1f);
	TestEqual(TEXT("a death counted"), Inv2->GetTally(SOJournal::DeathsTally()), 1);
	TestEqual(TEXT("not the other's"), Inv1->GetTally(SOJournal::DeathsTally()), 0);
	return true;
}

#endif
