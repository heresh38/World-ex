#include "SOCreator.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOData.h"

namespace
{
	FSOCreatorData Load()
	{
		FSOCreatorData Out;
		FString Text;
		TSharedPtr<FJsonObject> Root;
		if (!SOData::LoadText(TEXT("Data/creator.json"), Text) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
		{
			UE_LOG(LogTemp, Warning, TEXT("Character builder: Data/creator.json is missing or not json"));
			return Out;
		}
		const TArray<TSharedPtr<FJsonValue>>* Groups = nullptr;
		if (Root->TryGetArrayField(TEXT("groups"), Groups))
		{
			for (const TSharedPtr<FJsonValue>& V : *Groups)
			{
				const TSharedPtr<FJsonObject> G = V.IsValid() ? V->AsObject() : nullptr;
				if (!G.IsValid())
				{
					continue;
				}
				FSOCreatorGroup Group;
				Group.Id = FName(*G->GetStringField(TEXT("id")));
				Group.Name = G->GetStringField(TEXT("name"));
				G->TryGetStringField(TEXT("line"), Group.Line);
				const TArray<TSharedPtr<FJsonValue>>* Sliders = nullptr;
				if (G->TryGetArrayField(TEXT("sliders"), Sliders))
				{
					for (const TSharedPtr<FJsonValue>& S : *Sliders)
					{
						const TArray<TSharedPtr<FJsonValue>>* Pair = nullptr;
						if (S.IsValid() && S->TryGetArray(Pair) && Pair->Num() >= 2)
						{
							Group.Sliders.Emplace(FName(*(*Pair)[0]->AsString()), (*Pair)[1]->AsString());
						}
					}
				}
				Out.Groups.Add(MoveTemp(Group));
			}
		}
		auto Tones = [&Root](const TCHAR* Field, TArray<FSOCreatorTone>& To)
		{
			const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
			if (!Root->TryGetArrayField(Field, List))
			{
				return;
			}
			for (const TSharedPtr<FJsonValue>& V : *List)
			{
				const TSharedPtr<FJsonObject> T = V.IsValid() ? V->AsObject() : nullptr;
				const TArray<TSharedPtr<FJsonValue>>* Tint = nullptr;
				if (T.IsValid() && T->TryGetArrayField(TEXT("tint"), Tint) && Tint->Num() >= 3)
				{
					FSOCreatorTone Tone;
					Tone.Name = T->GetStringField(TEXT("name"));
					Tone.Tint = FLinearColor(static_cast<float>((*Tint)[0]->AsNumber()), static_cast<float>((*Tint)[1]->AsNumber()), static_cast<float>((*Tint)[2]->AsNumber()), 1.0f);
					To.Add(Tone);
				}
			}
		};
		Tones(TEXT("skinTones"), Out.SkinTones);
		Tones(TEXT("hairColours"), Out.HairColours);
		const TSharedPtr<FJsonObject>* Beards = nullptr;
		if (Root->TryGetObjectField(TEXT("beards"), Beards) && Beards->IsValid())
		{
			const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
			if ((*Beards)->TryGetArrayField(TEXT("styles"), List))
			{
				for (const TSharedPtr<FJsonValue>& V : *List)
				{
					const TSharedPtr<FJsonObject> B = V.IsValid() ? V->AsObject() : nullptr;
					if (B.IsValid())
					{
						Out.Beards.Add({ FName(*B->GetStringField(TEXT("id"))), B->GetStringField(TEXT("name")) });
					}
				}
			}
			if ((*Beards)->TryGetArrayField(TEXT("bodies"), List))
			{
				for (const TSharedPtr<FJsonValue>& V : *List)
				{
					Out.BeardBodies.Add(FName(*V->AsString()));
				}
			}
		}
		return Out;
	}
}

const FSOCreatorData& FSOCreatorData::Get()
{
	static const FSOCreatorData Data = Load();
	return Data;
}

const FSOCreatorGroup* FSOCreatorData::Find(FName Id) const
{
	return Groups.FindByPredicate([Id](const FSOCreatorGroup& G) { return G.Id == Id; });
}

TArray<FName> FSOCreatorData::AllKeys() const
{
	TArray<FName> Out;
	for (const FSOCreatorGroup& G : Groups)
	{
		for (const TPair<FName, FString>& S : G.Sliders)
		{
			Out.AddUnique(S.Key);
		}
	}
	return Out;
}
