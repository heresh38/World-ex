// The third-person combat stance (FSOStance, Data/stances.json; the owner, 2026-11-23): every gun's family has a class
// of its own, and at the ready the body is in a stance, not stood up straight: the hips lower than relaxed, standing the
// support foot ahead of the firing foot, neither elbow tucked in against the body.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOCharacter.h"
#include "SOData.h"
#include "SOStance.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

namespace
{
	USOWeaponData* StanceGun(const TCHAR* Name)
	{
		return LoadObject<USOWeaponData>(nullptr, *FString::Printf(TEXT("/Game/Weapons/%s/DA_%s.DA_%s"), Name, Name, Name));
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOStanceClassesTest, "ShatteredOrbit.Stance.EveryGunHasAClass", SOTest::Flags)
bool FSOStanceClassesTest::RunTest(const FString& Parameters)
{
	const FSOStanceData& D = FSOStanceData::Get();
	for (const TCHAR* C : { TEXT("smg"), TEXT("rifle"), TEXT("lmg"), TEXT("sniper"), TEXT("shotgun"), TEXT("pistol"), TEXT("heavy") })
	{
		TestTrue(FString::Printf(TEXT("the class %s is data"), C), D.Classes.Contains(C));
	}
	TestTrue(TEXT("the gun stays up a while after a fight"), D.CombatSeconds > 2.0f);
	TestTrue(TEXT("it comes up quickly and goes down slowly"), D.RaiseTime < D.LowerTime);
	// every archetype's family is a class's (no gun falls back on another's stance)
	FString Text;
	TSharedPtr<FJsonObject> Root;
	if (TestTrue(TEXT("the guns' data"), SOData::LoadText(TEXT("Data/game_data.json"), Text) && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) && Root.IsValid()))
	{
		const TSharedPtr<FJsonObject>* Arch = nullptr;
		if (Root->TryGetObjectField(TEXT("archetypes"), Arch))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& A : (*Arch)->Values)
			{
				const TSharedPtr<FJsonObject> O = A.Value->AsObject();
				FString Family;
				if (O.IsValid() && O->TryGetStringField(TEXT("family"), Family))
				{
					const FName* Class = D.Families.Find(FName(*Family));
					TestTrue(FString::Printf(TEXT("%s (%s) has a class"), *A.Key, *Family), Class && D.Classes.Contains(*Class));
				}
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOStanceBodyTest, "ShatteredOrbit.Stance.ReadyStance", SOTest::Flags)
bool FSOStanceBodyTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-800, -800, -20), FVector(800, 800, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector::ZeroVector);
	if (!TestNotNull(TEXT("player"), Player))
	{
		return false;
	}
	Player->SetViewMode(ESOViewMode::ThirdPerson);
	USkeletalMeshComponent* Body = Player->GetMesh();
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	for (const TCHAR* Name : { TEXT("Rifle"), TEXT("Hmg"), TEXT("Pistol") })
	{
		USOWeaponData* Data = StanceGun(Name);
		if (!TestNotNull(FString::Printf(TEXT("%s data"), Name), Data))
		{
			continue;
		}
		Player->EquipWeapon(Data);
		Player->CancelCombat();
		W.Run(1.5f);
		// actor space: X forward, Y right, Z up
		auto At = [&](const TCHAR* Bone) { return Player->GetActorTransform().InverseTransformPosition(Body->GetBoneLocation(Bone)); };
		const FVector HipsRelaxed = At(TEXT("hips"));
		TestTrue(FString::Printf(TEXT("%s: relaxed out of a fight"), Name), Player->GetCombatReady() < 0.05f);
		for (int32 k = 0; k < 6; ++k)
		{
			Player->MarkCombat();
			W.Run(0.25f);
		}
		TestTrue(FString::Printf(TEXT("%s: at the ready in a fight"), Name), Player->GetCombatReady() > 0.95f);
		const FVector Hips = At(TEXT("hips")), FootL = At(TEXT("foot_L")), FootR = At(TEXT("foot_R"));
		TestTrue(FString::Printf(TEXT("%s: the knees bent at the ready (hips %.1f cm lower)"), Name, HipsRelaxed.Z - Hips.Z), HipsRelaxed.Z - Hips.Z > 2.0f);
		TestTrue(FString::Printf(TEXT("%s: the support foot ahead of the firing foot (%.1f cm)"), Name, FootL.X - FootR.X), FootL.X - FootR.X > 6.0f);
		// an elbow out from its shoulder's line or nearly under it, never tucked in across the body
		const float OutR = static_cast<float>(At(TEXT("forearm_R")).Y - At(TEXT("upperarm_R")).Y);
		const float OutL = static_cast<float>(At(TEXT("upperarm_L")).Y - At(TEXT("forearm_L")).Y);
		TestTrue(FString::Printf(TEXT("%s: the firing elbow not across the body (%.1f cm out from the shoulder)"), Name, OutR), OutR > -7.0f);
		TestTrue(FString::Printf(TEXT("%s: the support elbow not tucked in (%.1f cm out from the shoulder)"), Name, OutL), OutL > -12.0f);
		AddInfo(FString::Printf(TEXT("Stance %s: hips -%.1f cm, stagger %.1f cm, elbows out R %.1f L %.1f"), Name, HipsRelaxed.Z - Hips.Z, FootL.X - FootR.X, OutR, OutL));
	}
	return true;
}

#endif
