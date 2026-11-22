#include "SOJournal.h"

#include "Dom/JsonObject.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOData.h"

namespace
{
	TSharedPtr<FJsonObject> ReadJson(const FString& Relative)
	{
		FString Text;
		TSharedPtr<FJsonObject> Root;
		if (!SOData::LoadText(Relative, Text) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
		{
			return nullptr;
		}
		return Root;
	}

	FString Field(const TSharedPtr<FJsonObject>& O, const TCHAR* Name)
	{
		FString Out;
		O->TryGetStringField(Name, Out);
		return Out;
	}

	/** An operation's own words as entries of the journal's operations section: the briefing (shown as its first stage
	 *  begins), what the radio says as each stage begins (and what the stage asks), the outcome (shown when it is done). */
	void AddOperation(FSOJournalData& Out, FName Op, const TSharedPtr<FJsonObject>& Plan)
	{
		const FString Name = Field(Plan, TEXT("name"));
		const TArray<TSharedPtr<FJsonValue>>* Stages = nullptr;
		if (!Plan->TryGetArrayField(TEXT("stages"), Stages) || Stages->Num() == 0)
		{
			return;
		}
		const FName First = FName(*Field((*Stages)[0]->AsObject(), TEXT("id")));
		{
			FSOJournalEntry E;
			E.Id = FName(*FString::Printf(TEXT("%s_briefing"), *Op.ToString()));
			E.Section = TEXT("operations");
			E.Title = Name;
			E.Sub = TEXT("BRIEFING");
			TArray<FString> Lines;
			const FString Tagline = Field(Plan, TEXT("tagline"));
			if (!Tagline.IsEmpty())
			{
				Lines.Add(Tagline);
			}
			const TArray<TSharedPtr<FJsonValue>>* Briefing = nullptr;
			if (Plan->TryGetArrayField(TEXT("briefing"), Briefing))
			{
				for (const TSharedPtr<FJsonValue>& L : *Briefing)
				{
					Lines.Add(L->AsString());
				}
			}
			E.Text = FString::Join(Lines, TEXT("\n\n"));
			E.Unlock = SOJournal::StageKey(Op, First);
			E.Tally = SOJournal::DoneTally(Op);
			E.TallyLabel = TEXT("FINISHED");
			Out.Entries.Add(MoveTemp(E));
		}
		int32 Number = 0;
		for (const TSharedPtr<FJsonValue>& V : *Stages)
		{
			const TSharedPtr<FJsonObject> S = V->AsObject();
			++Number;
			const TSharedPtr<FJsonObject>* Intel = nullptr;
			if (!S.IsValid() || !S->TryGetObjectField(TEXT("intel"), Intel))
			{
				continue;
			}
			FSOJournalEntry E;
			const FString Id = Field(S, TEXT("id"));
			E.Id = FName(*FString::Printf(TEXT("%s_%s"), *Op.ToString(), *Id));
			E.Section = TEXT("operations");
			E.Title = Field(S, TEXT("title"));
			E.Sub = FString::Printf(TEXT("%s  ·  STAGE %d"), *Field(*Intel, TEXT("who")).ToUpper(), Number);
			E.Text = Field(*Intel, TEXT("text"));
			E.Note = Field(S, TEXT("objective"));
			E.Unlock = SOJournal::StageKey(Op, FName(*Id));
			Out.Entries.Add(MoveTemp(E));
		}
		const FString Outcome = Field(Plan, TEXT("outcome"));
		if (!Outcome.IsEmpty())
		{
			FSOJournalEntry E;
			E.Id = FName(*FString::Printf(TEXT("%s_outcome"), *Op.ToString()));
			E.Section = TEXT("operations");
			E.Title = Name;
			E.Sub = TEXT("OUTCOME");
			E.Text = Outcome;
			E.Unlock = SOJournal::DoneKey(Op);
			E.Tally = SOJournal::DoneTally(Op);
			E.TallyLabel = TEXT("FINISHED");
			Out.Entries.Add(MoveTemp(E));
		}
	}

	FSOJournalData Load()
	{
		FSOJournalData Out;
		const TSharedPtr<FJsonObject> Root = ReadJson(TEXT("Data/journal.json"));
		if (!Root.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("Journal: Data/journal.json is missing or not json"));
			return Out;
		}
		const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
		if (Root->TryGetArrayField(TEXT("sections"), List))
		{
			for (const TSharedPtr<FJsonValue>& V : *List)
			{
				const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
				if (!O.IsValid() || !O->HasField(TEXT("id")))
				{
					continue;
				}
				FSOJournalSection S;
				S.Id = FName(*Field(O, TEXT("id")));
				S.Name = Field(O, TEXT("name"));
				S.Line = Field(O, TEXT("line"));
				O->TryGetNumberField(TEXT("glyph"), S.Glyph);
				const TArray<TSharedPtr<FJsonValue>>* Color = nullptr;
				if (O->TryGetArrayField(TEXT("color"), Color) && Color->Num() >= 3)
				{
					S.Color = FLinearColor(static_cast<float>((*Color)[0]->AsNumber()), static_cast<float>((*Color)[1]->AsNumber()), static_cast<float>((*Color)[2]->AsNumber()), 1.0f);
				}
				Out.Sections.Add(MoveTemp(S));
			}
		}
		if (Root->TryGetArrayField(TEXT("entries"), List))
		{
			for (const TSharedPtr<FJsonValue>& V : *List)
			{
				const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr;
				if (!O.IsValid() || !O->HasField(TEXT("id")))
				{
					continue;
				}
				FSOJournalEntry E;
				E.Id = FName(*Field(O, TEXT("id")));
				E.Section = FName(*Field(O, TEXT("section")));
				E.Title = Field(O, TEXT("title"));
				E.Sub = Field(O, TEXT("sub"));
				E.Text = Field(O, TEXT("text"));
				E.Note = Field(O, TEXT("note"));
				const FString Unlock = Field(O, TEXT("unlock"));
				E.Unlock = Unlock.IsEmpty() ? SOJournal::StartKey() : FName(*Unlock);
				const FString Picture = Field(O, TEXT("picture"));
				E.Picture = Picture.IsEmpty() ? NAME_None : FName(*Picture);
				const FString Tally = Field(O, TEXT("tally"));
				E.Tally = Tally.IsEmpty() ? NAME_None : FName(*Tally);
				E.TallyLabel = Field(O, TEXT("tallyLabel"));
				Out.Entries.Add(MoveTemp(E));
			}
		}
		// every operation's own words (an area of kind "operation" names its plan)
		if (const TSharedPtr<FJsonObject> Areas = ReadJson(TEXT("Data/areas.json")))
		{
			if (Areas->TryGetArrayField(TEXT("areas"), List))
			{
				for (const TSharedPtr<FJsonValue>& V : *List)
				{
					const TSharedPtr<FJsonObject> A = V.IsValid() ? V->AsObject() : nullptr;
					if (!A.IsValid() || Field(A, TEXT("kind")) != TEXT("operation") || Field(A, TEXT("plan")).IsEmpty())
					{
						continue;
					}
					if (const TSharedPtr<FJsonObject> Plan = ReadJson(Field(A, TEXT("plan"))))
					{
						AddOperation(Out, FName(*Field(A, TEXT("id"))), Plan);
					}
				}
			}
		}
		return Out;
	}
}

const FSOJournalData& FSOJournalData::Get()
{
	static const FSOJournalData Data = Load();
	return Data;
}

const FSOJournalSection* FSOJournalData::FindSection(FName Id) const
{
	return Sections.FindByPredicate([Id](const FSOJournalSection& S) { return S.Id == Id; });
}

const FSOJournalEntry* FSOJournalData::Find(FName Id) const
{
	return Entries.FindByPredicate([Id](const FSOJournalEntry& E) { return E.Id == Id; });
}

TArray<const FSOJournalEntry*> FSOJournalData::UnlockedBy(FName Key) const
{
	TArray<const FSOJournalEntry*> Out;
	for (const FSOJournalEntry& E : Entries)
	{
		if (E.Unlock == Key)
		{
			Out.Add(&E);
		}
	}
	return Out;
}

namespace SOJournal
{
	FName StartKey() { return TEXT("start"); }
	FName MetKey(FName Species) { return FName(*FString::Printf(TEXT("met:%s"), *Species.ToString())); }
	FName NamedKey(FName Variant) { return FName(*FString::Printf(TEXT("named:%s"), *Variant.ToString())); }
	FName StageKey(FName Operation, FName Stage) { return FName(*FString::Printf(TEXT("stage:%s:%s"), *Operation.ToString(), *Stage.ToString())); }
	FName DoneKey(FName Operation) { return FName(*FString::Printf(TEXT("done:%s"), *Operation.ToString())); }
	FName OriginKey(FName Origin) { return FName(*FString::Printf(TEXT("origin:%s"), *Origin.ToString())); }
	FName KillTally(FName Species) { return FName(*FString::Printf(TEXT("kill:%s"), *Species.ToString())); }
	FName KillsTally() { return TEXT("kills"); }
	FName NamedTally() { return TEXT("named"); }
	FName DoneTally(FName Operation) { return FName(*FString::Printf(TEXT("op:%s"), *Operation.ToString())); }
	FName DeathsTally() { return TEXT("deaths"); }

	FName OperationOf(const FString& PlanFile)
	{
		FString Base = FPaths::GetBaseFilename(PlanFile);
		Base.RemoveFromStart(TEXT("op_"));
		return FName(*Base);
	}
}
