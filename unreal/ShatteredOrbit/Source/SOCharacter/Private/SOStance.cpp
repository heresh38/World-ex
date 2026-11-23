#include "SOStance.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOData.h"

namespace
{
	FVector Vec(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, const FVector& Default)
	{
		const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
		if (O->TryGetArrayField(Field, A) && A->Num() >= 3)
		{
			return FVector((*A)[0]->AsNumber(), (*A)[1]->AsNumber(), (*A)[2]->AsNumber());
		}
		return Default;
	}

	FRotator Rot(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, const FRotator& Default)
	{
		const FVector V = Vec(O, Field, FVector(Default.Pitch, Default.Yaw, Default.Roll));
		return FRotator(V.X, V.Y, V.Z);
	}

	void Pair(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, float (&Out)[2])
	{
		const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
		if (O->TryGetArrayField(Field, A) && A->Num() >= 2)
		{
			Out[0] = static_cast<float>((*A)[0]->AsNumber());
			Out[1] = static_cast<float>((*A)[1]->AsNumber());
		}
	}

	void Num(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, float& Out)
	{
		double V = 0.0;
		if (O->TryGetNumberField(Field, V))
		{
			Out = static_cast<float>(V);
		}
	}

	FSOStanceData Load()
	{
		FSOStanceData Out;
		FString Text;
		TSharedPtr<FJsonObject> Root;
		if (!SOData::LoadText(TEXT("Data/stances.json"), Text) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
		{
			Out.Classes.Add(TEXT("rifle"), FSOStance());
			return Out;
		}
		Num(Root, TEXT("combatSeconds"), Out.CombatSeconds);
		Num(Root, TEXT("raiseTime"), Out.RaiseTime);
		Num(Root, TEXT("lowerTime"), Out.LowerTime);
		const TSharedPtr<FJsonObject>* Families = nullptr;
		if (Root->TryGetObjectField(TEXT("families"), Families))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& F : (*Families)->Values)
			{
				Out.Families.Add(FName(*F.Key), FName(*F.Value->AsString()));
			}
		}
		const TSharedPtr<FJsonObject>* Classes = nullptr;
		if (Root->TryGetObjectField(TEXT("classes"), Classes))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& C : (*Classes)->Values)
			{
				const TSharedPtr<FJsonObject> O = C.Value->AsObject();
				if (!O.IsValid())
				{
					continue;
				}
				FSOStance S;
				S.Id = FName(*C.Key);
				S.ReadyShift = Vec(O, TEXT("readyShift"), S.ReadyShift);
				S.AimShift = Vec(O, TEXT("aimShift"), S.AimShift);
				Num(O, TEXT("readyDip"), S.ReadyDip);
				S.HandHold = Vec(O, TEXT("handHold"), S.HandHold);
				S.HandAimHold = Vec(O, TEXT("handAimHold"), S.HandAimHold);
				S.RelaxOffset = Vec(O, TEXT("relaxOffset"), S.RelaxOffset);
				S.RelaxRot = Rot(O, TEXT("relaxRot"), S.RelaxRot);
				Pair(O, TEXT("elbowOut"), S.ElbowOut);
				Pair(O, TEXT("elbowLeast"), S.ElbowLeast);
				Pair(O, TEXT("elbowMost"), S.ElbowMost);
				Num(O, TEXT("shoulders"), S.Shoulders);
				Pair(O, TEXT("blade"), S.Blade);
				Pair(O, TEXT("lean"), S.Lean);
				Num(O, TEXT("headDown"), S.HeadDown);
				Num(O, TEXT("knees"), S.Knees);
				Num(O, TEXT("stagger"), S.Stagger);
				Num(O, TEXT("width"), S.Width);
				Out.Classes.Add(S.Id, S);
			}
		}
		if (!Out.Classes.Contains(TEXT("rifle")))
		{
			Out.Classes.Add(TEXT("rifle"), FSOStance());
		}
		return Out;
	}
}

const FSOStance& FSOStanceData::For(FName Family) const
{
	const FName* Class = Families.Find(Family);
	if (const FSOStance* S = Class ? Classes.Find(*Class) : nullptr)
	{
		return *S;
	}
	return Classes.FindChecked(TEXT("rifle"));
}

const FSOStanceData& FSOStanceData::Get()
{
	static const FSOStanceData Data = Load();
	return Data;
}
