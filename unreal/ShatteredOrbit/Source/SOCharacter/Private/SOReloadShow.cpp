#include "SOReloadShow.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOData.h"

namespace
{
	/** Six numbers; fewer (or a missing field) keep what Out already has, so an anchor's show need only be written whole
	 *  where it differs. */
	bool Six(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, FSOReloadShow& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
		if (!O.IsValid() || !O->TryGetArrayField(Field, A))
		{
			return false;
		}
		for (int32 i = 0; i < 6 && i < A->Num(); ++i)
		{
			Out.V[i] = static_cast<float>((*A)[i]->AsNumber());
		}
		return true;
	}

	FVector Three(const TSharedPtr<FJsonObject>& O, const TCHAR* Field)
	{
		const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
		if (O.IsValid() && O->TryGetArrayField(Field, A) && A->Num() >= 3)
		{
			return FVector((*A)[0]->AsNumber(), (*A)[1]->AsNumber(), (*A)[2]->AsNumber());
		}
		return FVector::ZeroVector;
	}

	void Num(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, float& Out)
	{
		double V = 0.0;
		if (O.IsValid() && O->TryGetNumberField(Field, V))
		{
			Out = static_cast<float>(V);
		}
	}

	void Style(const TSharedPtr<FJsonObject>& O, const FSOReloadStyleShow& From, FSOReloadStyleShow& Out)
	{
		Out = From;                                    // (what it does not say is the default's)
		Six(O, TEXT("show"), Out.Base);
		const TSharedPtr<FJsonObject>* Anchors = nullptr;
		if (O.IsValid() && O->TryGetObjectField(TEXT("anchors"), Anchors))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& A : (*Anchors)->Values)
			{
				// (an anchor's show starts from its style's base: written whole, or, its name begun with a plus, as what it adds
				// to the base: "+pouch": the gun sags and rolls a little further while the hand is away)
				FSOReloadShow Show = Out.Base;
				const bool bAdds = A.Key.StartsWith(TEXT("+"));
				const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
				if (A.Value.IsValid() && A.Value->TryGetArray(Values))
				{
					for (int32 i = 0; i < 6 && i < Values->Num(); ++i)
					{
						const float Value = static_cast<float>((*Values)[i]->AsNumber());
						Show.V[i] = bAdds ? Show.V[i] + Value : Value;
					}
					Out.Anchors.Add(FName(*(bAdds ? A.Key.Mid(1) : A.Key)), Show);
				}
			}
		}
	}

	FSOReloadShowData Load()
	{
		FSOReloadShowData Out;
		FString Text;
		TSharedPtr<FJsonObject> Root;
		if (!SOData::LoadText(TEXT("Data/reload_shows.json"), Text) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
		{
			return Out;
		}
		const TSharedPtr<FJsonObject>* Spring = nullptr;
		if (Root->TryGetObjectField(TEXT("spring"), Spring))
		{
			Num(*Spring, TEXT("omega"), Out.Omega);
			Num(*Spring, TEXT("zeta"), Out.Zeta);
			Num(*Spring, TEXT("joltOmega"), Out.JoltOmega);
			Num(*Spring, TEXT("joltZeta"), Out.JoltZeta);
			Num(*Spring, TEXT("gunMoves"), Out.GunMoves);
			Num(*Spring, TEXT("handleLead"), Out.HandleLead);
		}
		const TSharedPtr<FJsonObject>* Default = nullptr;
		if (Root->TryGetObjectField(TEXT("default"), Default))
		{
			Style(*Default, FSOReloadStyleShow(), Out.Default);
		}
		const TSharedPtr<FJsonObject>* Styles = nullptr;
		if (Root->TryGetObjectField(TEXT("styles"), Styles))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& S : (*Styles)->Values)
			{
				if (S.Value.IsValid() && S.Value->Type == EJson::Object)
				{
					Style(S.Value->AsObject(), Out.Default, Out.Styles.Add(FName(*S.Key)));
				}
			}
		}
		const TSharedPtr<FJsonObject>* Beats = nullptr;
		if (Root->TryGetObjectField(TEXT("beats"), Beats))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& B : (*Beats)->Values)
			{
				if (B.Value.IsValid() && B.Value->Type == EJson::Object)
				{
					const TSharedPtr<FJsonObject> O = B.Value->AsObject();
					FSOHandlingBeat& Beat = Out.Beats.Add(FName(*B.Key));
					Beat.GunMove = Three(O, TEXT("move"));
					Beat.GunTurn = Three(O, TEXT("turn"));
					Beat.View = Three(O, TEXT("view"));
				}
			}
		}
		return Out;
	}
}

const FSOReloadStyleShow& FSOReloadShowData::For(FName Archetype, FName Style) const
{
	if (const FSOReloadStyleShow* Own = Styles.Find(Archetype))
	{
		return *Own;
	}
	if (const FSOReloadStyleShow* Its = Styles.Find(Style))
	{
		return *Its;
	}
	return Default;
}

const FSOReloadShowData& FSOReloadShowData::Get()
{
	static const FSOReloadShowData Data = Load();
	return Data;
}
