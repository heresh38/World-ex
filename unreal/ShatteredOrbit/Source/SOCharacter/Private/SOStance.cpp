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
		double One = 0.0;
		if (O->TryGetArrayField(Field, A) && A->Num() >= 2)
		{
			Out[0] = static_cast<float>((*A)[0]->AsNumber());
			Out[1] = static_cast<float>((*A)[1]->AsNumber());
		}
		else if (O->TryGetNumberField(Field, One))
		{
			Out[0] = Out[1] = static_cast<float>(One);              // (one number: the same in both)
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
				Pair(O, TEXT("elbowSwing"), S.ElbowSwing);
				Pair(O, TEXT("elbowSwingAim"), S.ElbowSwingAim);
				Pair(O, TEXT("wristShare"), S.WristShare);
				Pair(O, TEXT("elbowLeast"), S.ElbowLeast);
				Pair(O, TEXT("elbowMost"), S.ElbowMost);
				Pair(O, TEXT("wristMax"), S.WristMax);
				Pair(O, TEXT("shoulders"), S.Shoulders);
				Pair(O, TEXT("blade"), S.Blade);
				Pair(O, TEXT("lean"), S.Lean);
				Pair(O, TEXT("hips"), S.Hips);
				Num(O, TEXT("headDown"), S.HeadDown);
				Pair(O, TEXT("knees"), S.Knees);
				Pair(O, TEXT("stagger"), S.Stagger);
				Pair(O, TEXT("width"), S.Width);
				Pair(O, TEXT("toeOut"), S.ToeOut);
				Num(O, TEXT("kneeOut"), S.KneeOut);
				Num(O, TEXT("turnStep"), S.TurnStep);
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
