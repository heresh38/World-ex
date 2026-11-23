// The third-person combat stance (FSOStance, Data/stances.json; the owner, 2026-11-23): every gun's family has a class
// of its own, and at the ready the body is in a stance, not stood up straight: the hips lower than relaxed, standing the
// support foot well ahead of the firing foot and the feet apart, the knees over the feet (never in), the firing elbow
// out at the side, the support elbow under the gun, a long gun's butt in front of the shoulder joint; turned on the
// spot, still a stance.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SOCharacter.h"
#include "SOData.h"
#include "SOGunRigComponent.h"
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
		TestTrue(FString::Printf(TEXT("%s: the support foot ahead of the firing foot (%.1f cm)"), Name, FootL.X - FootR.X), FootL.X - FootR.X > 20.0f);
		TestTrue(FString::Printf(TEXT("%s: the feet apart, not crossed (%.1f cm)"), Name, FootR.Y - FootL.Y), FootR.Y - FootL.Y > 18.0f);
		// the knees over the feet, never in toward each other: each knee on or outside the line from its hip to its ankle
		// (the owner, 2026-11-23: "the player legs are completely wrong and crossed": the stance's bend carried the clip's
		// knees in, an X from behind)
		for (int32 Side = 0; Side < 2; ++Side)
		{
			const FVector Hip = At(Side == 0 ? TEXT("thigh_L") : TEXT("thigh_R")), Knee = At(Side == 0 ? TEXT("shin_L") : TEXT("shin_R"));
			const FVector Ankle = Side == 0 ? FootL : FootR;
			const float T = static_cast<float>(FMath::Clamp((Hip.Z - Knee.Z) / FMath::Max(Hip.Z - Ankle.Z, 1.0), 0.0, 1.0));
			const float LineY = static_cast<float>(FMath::Lerp(Hip.Y, Ankle.Y, T));
			const float In = Side == 0 ? static_cast<float>(Knee.Y) - LineY : LineY - static_cast<float>(Knee.Y);   // + toward the other leg
			TestTrue(FString::Printf(TEXT("%s: the %s knee not in toward the other leg (%.1f cm in)"), Name, Side == 0 ? TEXT("left") : TEXT("right"), In), In < 1.5f);
		}
		// the elbows out at the sides, as the owner's reference has them (seen from behind the arms show; "arm not showing"
		// was a firing elbow hung under the gun in front of the chest), the support elbow under the gun, not up level with
		// its shoulder
		const FVector ShoulderR = At(TEXT("upperarm_R")), ElbowR = At(TEXT("forearm_R")), HandR = At(TEXT("hand_R"));
		const float OutR = static_cast<float>(ElbowR.Y - ShoulderR.Y);
		const float DropL = static_cast<float>(At(TEXT("upperarm_L")).Z - At(TEXT("forearm_L")).Z);
		const bool bLong = FCString::Strcmp(Name, TEXT("Pistol")) != 0;
		// (a handgun is held out in both hands toward the body's middle: its firing elbow lies along the arm, a little in
		// from the shoulder, never folded in across the line from the shoulder to the hand)
		const float T = static_cast<float>(FMath::Clamp((ElbowR.X - ShoulderR.X) / FMath::Max(HandR.X - ShoulderR.X, 1.0), 0.0, 1.0));
		const float OffLine = static_cast<float>(ElbowR.Y - FMath::Lerp(ShoulderR.Y, HandR.Y, T));
		TestTrue(FString::Printf(TEXT("%s: the firing elbow not across the body (%.1f cm out from its shoulder-to-hand line)"), Name, OffLine), OffLine > -1.0f);
		if (bLong)
		{
			TestTrue(FString::Printf(TEXT("%s: the firing elbow out at the side (%.1f cm out from the shoulder)"), Name, OutR), OutR > 8.0f);
		}
		TestTrue(FString::Printf(TEXT("%s: the support elbow under the gun (%.1f cm below its shoulder)"), Name, DropL), DropL > 8.0f);
		// a long gun's butt in front of the shoulder joint, in the pocket ("the gun is in the players shoulder": a reach
		// rule pulled the gun back 12 cm, the butt 3 cm behind the joint)
		if (bLong)
		{
			const ASOWeapon* Gun = Player->GetWeapon();
			const USOGunRigComponent* Rig = Gun ? Gun->GetRig() : nullptr;
			if (TestTrue(FString::Printf(TEXT("%s: the gun's rig"), Name), Rig && Rig->IsBuilt()))
			{
				const FVector Butt = Player->GetActorTransform().InverseTransformPosition(Rig->GetComponentTransform().TransformPosition(FVector(Rig->GetRigBounds().Min.X, 0.0f, 1.5f)));
				const float Ahead = static_cast<float>(Butt.X - At(TEXT("upperarm_R")).X);
				TestTrue(FString::Printf(TEXT("%s: the butt in front of the shoulder joint (%.1f cm)"), Name, Ahead), Ahead > 1.0f);
			}
		}
		AddInfo(FString::Printf(TEXT("Stance %s: hips -%.1f cm, stagger %.1f cm, apart %.1f cm, firing elbow out %.1f (%.1f off its line), support elbow down %.1f"), Name,
			HipsRelaxed.Z - Hips.Z, FootL.X - FootR.X, FootR.Y - FootL.Y, OutR, OffLine, DropL));
		// turned on the spot at the ready: the feet step round under the aim and the stance stays a stance (left planted
		// under an aim that turned 30 degrees, the feet stood in line with it and from behind the legs read as crossed)
		Player->SetActorRotation(FRotator(0.0f, 30.0f, 0.0f));
		for (int32 k = 0; k < 6; ++k)
		{
			Player->MarkCombat();
			W.Run(0.25f);
		}
		const FVector TurnedL = At(TEXT("foot_L")), TurnedR = At(TEXT("foot_R"));
		TestTrue(FString::Printf(TEXT("%s: turned 30 degrees, the feet still apart (%.1f cm)"), Name, TurnedR.Y - TurnedL.Y), TurnedR.Y - TurnedL.Y > 18.0f);
		TestTrue(FString::Printf(TEXT("%s: turned 30 degrees, still the support foot forward (%.1f cm)"), Name, TurnedL.X - TurnedR.X), TurnedL.X - TurnedR.X > 15.0f);
		Player->SetActorRotation(FRotator::ZeroRotator);
	}
	return true;
}

#endif
