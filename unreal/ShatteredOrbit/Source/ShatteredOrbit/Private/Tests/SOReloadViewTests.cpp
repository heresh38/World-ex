// The reload is SEEN (the owner, 2026-11-24: "During reloads most guns are either not visible in the screen or they're
// facing the wrong way, the m4 for example should tilt more to the right so the reload clip is visible or player should
// raise the gun with one hand and then reload so change them so reload is visible and the player can see the magazine
// fully"). Every gun is reloaded from its holder's own eyes, at the ready, standing; through the part of the reload where
// the hands work the gun (a magazine out and in, a cell, a cylinder, a flap, a pump's loading port, a belt's cover), the
// place it is worked is in the picture and turned toward the eyes, and the part, while it is in the gun, is whole in it.

#include "SOTestWorld.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Camera/CameraComponent.h"
#include "Camera/CameraTypes.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "SOCharacter.h"
#include "SOGunRigComponent.h"
#include "SOInventoryComponent.h"
#include "SOLootLibrary.h"
#include "SOLootTypes.h"
#include "SOPlayerState.h"
#include "SOReload.h"
#include "SOViewmodelComponent.h"
#include "SOWeapon.h"
#include "SOWeaponData.h"

namespace SOTest
{
	/** The part of a gun a reload's hand anchor works (null: the hand is not at work on the gun). */
	const UStaticMeshComponent* WorkPart(const USOGunRigComponent* Rig, FName Anchor)
	{
		static const FName Fore(TEXT("fore")), Pouch(TEXT("pouch")), Free(TEXT("free")), Cur(TEXT("cur"));
		if (!Rig || Anchor.IsNone() || Anchor == Fore || Anchor == Pouch || Anchor == Free || Anchor == Cur)
		{
			return nullptr;
		}
		if (Anchor == TEXT("spare"))
		{
			return Rig->GetSpare();
		}
		static const TPair<const TCHAR*, const TCHAR*> Parts[] = { { TEXT("magbase"), TEXT("mag") }, { TEXT("cyl"), TEXT("cylinder") },
			{ TEXT("ejector"), TEXT("crane") }, { TEXT("loader"), TEXT("x_speedloader") }, { TEXT("shell"), TEXT("x_shell") }, { TEXT("round"), TEXT("x_round") } };
		for (const TPair<const TCHAR*, const TCHAR*>& P : Parts)
		{
			if (Anchor == P.Key)
			{
				return Rig->GetPart(P.Value);
			}
		}
		return Rig->GetPart(Anchor);   // mag, hatch, biomass, pump, bolt, charge, slide
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSOReloadInViewTest, "ShatteredOrbit.Reload.TheWorkInView", SOTest::Flags)
bool FSOReloadInViewTest::RunTest(const FString& Parameters)
{
	if (SOTest::PlayerBodyMissing(*this))
	{
		return true;
	}
	SOTest::FTestWorld W;
	W.AddBox(FVector(-20000, -20000, -100), FVector(20000, 20000, 0));
	ASOCharacter* Player = W.SpawnCharacter(FVector(0, 0, 0));
	const USOLootTables* Tables = USOLootLibrary::GetTables();
	if (!TestNotNull(TEXT("player"), Player) || !TestNotNull(TEXT("loot tables"), Tables) || !TestNotNull(TEXT("the hold"), Player->GetViewmodel()))
	{
		return false;
	}
	APlayerController* PC = W.World->SpawnActor<APlayerController>();
	PC->SetAsLocalPlayerController();
	FActorSpawnParameters StateParams;
	StateParams.bDeferConstruction = true;
	ASOPlayerState* PS = W.World->SpawnActor<ASOPlayerState>(ASOPlayerState::StaticClass(), FTransform::Identity, StateParams);
	PS->GetInventory()->bPersist = false;
	PS->FinishSpawning(FTransform::Identity);
	PC->PlayerState = PS;
	PC->Possess(Player);
	PC->SetControlRotation(FRotator::ZeroRotator);
	Player->GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Player->SetViewMode(ESOViewMode::FirstPerson);
	FString Only;
	FParse::Value(FCommandLine::Get(), TEXT("SOReloadOnly="), Only);      // (-SOReloadOnly=<arch>[,<arch>]: some guns)
	TArray<FString> OnlyList;
	Only.ParseIntoArray(OnlyList, TEXT(","));
	const bool bTrace = FParse::Param(FCommandLine::Get(), TEXT("SOReloadTrace"));
	auto Face = [&]() { Player->MarkCombat(); Player->FaceRotation(PC->GetControlRotation(), SOTest::Dt); };
	for (const FSOArchetypeEntry& Entry : Tables->Archetypes)
	{
		const FString Arch = Entry.Id.ToString();
		if (OnlyList.Num() > 0 && !OnlyList.Contains(Arch))
		{
			continue;
		}
		Player->SetActorLocation(FVector(0.0f, 0.0f, 92.0f));
		PC->SetControlRotation(FRotator::ZeroRotator);
		FRandomStream Rng(FCrc::StrCrc32(*Arch));
		FSOWeaponInstance Made = USOLootLibrary::MakeWeapon(Entry.Id, 2, 20, Rng);
		Made.Sight = TEXT("default");
		ASOWeapon* Gun = Player->EquipInstance(Made);
		W.Run(1.0f, Face);
		const USOGunRigComponent* Rig = Gun ? Gun->GetRig() : nullptr;
		if (!Gun || !Rig || !Rig->IsBuilt() || Gun->Condenses())
		{
			continue;     // (the Sarketh's guns never reload: their rounds condense)
		}
		const FName Style = SOReload::GetStyle(Entry.Id);
		Gun->SetAmmo(0, 200);
		Gun->StartReload();
		int32 Work = 0, WellIn = 0, Turned = 0, InPlace = 0, Whole = 0;
		float AcrossLo = 9.0f, AcrossHi = -9.0f, DownLo = 9.0f, DownHi = -9.0f, SideLo = 999.0f, SideHi = -999.0f;
		TSet<FName> Anchors;
		const float Seconds = FMath::Max(Gun->GetReloadDuration(), 0.5f) + 0.2f;
		W.Run(Seconds, [&]()
		{
			Face();
			const FSOReloadPose& Pose = Gun->GetPose();
			FName Anchor = !Pose.bHand ? NAME_None : (Pose.HandAlpha < 0.5f ? Pose.HandAnchorA : Pose.HandAnchorB);
			const UStaticMeshComponent* Part = SOTest::WorkPart(Rig, Anchor);
			if (!Part && Pose.Hatch > 0.05f)
			{
				Anchor = TEXT("hatch");                   // (a flap that opens by itself: the hands stay on the gun)
				Part = Rig->GetPart(Anchor);
			}
			if (!Gun->IsReloading() || !Part || !Part->IsVisible())
			{
				return;
			}
			++Work;
			Anchors.Add(Anchor);
			FMinimalViewInfo View;
			Player->GetCamera()->GetCameraView(SOTest::Dt, View);
			const FTransform Cam(View.Rotation, View.Location);
			const float TanX = FMath::Tan(FMath::DegreesToRadians(View.FOV * 0.5f)), TanY = TanX * 9.0f / 16.0f;
			auto InPicture = [&](const FVector& World, float& OutAcross, float& OutDown)
			{
				const FVector P = Cam.InverseTransformPosition(World);
				OutAcross = P.X > 1.0 ? 0.5f + 0.5f * static_cast<float>(P.Y / P.X) / TanX : -1.0f;
				OutDown = P.X > 1.0 ? 0.5f - 0.5f * static_cast<float>(P.Z / P.X) / TanY : 2.0f;
				return OutAcross >= 0.0f && OutAcross <= 1.0f && OutDown >= 0.0f && OutDown <= 1.0f;
			};
			// the place it is worked (the part's place at rest in the gun) in the picture, and from which side the eyes see
			// it, in the gun's own frame (+X barrel, +Y right, +Z up): 0 from straight above (the receiver between the eyes and
			// anything under it), 90 from its left flank, 180 from under it
			const FTransform RigT = Rig->GetComponentTransform();
			const FVector Well = RigT.TransformPosition(Player->GetViewmodel()->GetReloadWork());
			float Across, Down;
			const bool bWellIn = InPicture(Well, Across, Down) && Across >= 0.12f && Across <= 0.9f && Down >= 0.1f && Down <= (Rig->IsHandgun() ? 0.96f : 0.92f);
			const FVector ToEye = RigT.InverseTransformVectorNoScale(View.Location - Well).GetSafeNormal();
			const float Side = FMath::RadiansToDegrees(FMath::Atan2(-static_cast<float>(ToEye.Y), static_cast<float>(ToEye.Z)));
			// (turned toward the eyes: a part under the gun or on its left seen from its left, 40 degrees or more off the
			// gun's top (from straight above the receiver hides it); one on its top or its right seen from that side, within
			// 75 degrees of it)
			// (a bolt-action's bolt handle on its right: its action is worked from above, the top toward the eyes)
			FVector2D Out = Player->GetViewmodel()->GetReloadSide();
			// (the part the hand is on NOW: a handle or a slide is worked from the gun's top whatever the reload's main part
			// is, and the gun is turned again for it; a cover or a flap lies where it lies on this gun)
			static const FName NBolt(TEXT("bolt")), NCharge(TEXT("charge")), NSlide(TEXT("slide")), NHatch(TEXT("hatch")), NBiomass(TEXT("biomass"));
			if (Anchor == NBolt || Anchor == NCharge || Anchor == NSlide)
			{
				Out = FVector2D(0.0f, 1.0f);
			}
			else if ((Anchor == NHatch || Anchor == NBiomass) && Part->GetStaticMesh())
			{
				const FVector At = RigT.InverseTransformPosition(Part->GetComponentTransform().TransformPosition(Part->GetStaticMesh()->GetBoundingBox().GetCenter()));
				const FVector2D Lies(static_cast<float>(At.Y), static_cast<float>(At.Z - RigT.InverseTransformPosition(Rig->GetMuzzleLocation()).Z));
				if (Lies.Size() > 1.5f)
				{
					Out = Lies.GetSafeNormal();
				}
			}
			if (Out.X > 0.5f)
			{
				Out = FVector2D(0.0f, 1.0f);
			}
			const bool bTop = Out.Y > 0.5f;
			const FVector2D Eye2(static_cast<float>(ToEye.Y), static_cast<float>(ToEye.Z));
			const float OffItsSide = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector2D::DotProduct(Eye2.GetSafeNormal(), Out), -1.0f, 1.0f)));
			WellIn += bWellIn ? 1 : 0;
			Turned += (bTop ? OffItsSide <= 75.0f : Side >= 40.0f) ? 1 : 0;
			AcrossLo = FMath::Min(AcrossLo, Across); AcrossHi = FMath::Max(AcrossHi, Across);
			DownLo = FMath::Min(DownLo, Down); DownHi = FMath::Max(DownHi, Down);
			SideLo = FMath::Min(SideLo, Side); SideHi = FMath::Max(SideHi, Side);
			// the part itself while it is in the gun (a magazine not yet out, or home again): whole in the picture, its own
			// box's corners (a flap, often a whole flank of the gun swung open, or anything longer than 22 cm: its middle)
			const FBox Local = Part->GetStaticMesh() ? Part->GetStaticMesh()->GetBoundingBox() : FBox(FVector::ZeroVector, FVector::ZeroVector);
			const FTransform PartT = Part->GetComponentTransform();
			const FVector Centre = PartT.TransformPosition(Local.GetCenter());
			bool bAll = true;
			if (FVector::Dist(Centre, Well) < 6.0)
			{
				++InPlace;
				// (and a handgun's magazine, in its grip in the firing hand at the foot of the picture: its middle)
				// (and a part that slides along the gun, a bolt, a slide, a handle: what is worked is its handle, at its middle)
				if (Anchor == TEXT("hatch") || Anchor == TEXT("biomass") || Anchor == NBolt || Anchor == NCharge || Anchor == NSlide || Rig->IsHandgun()
					|| PartT.TransformVector(Local.GetSize()).GetAbsMax() > 22.0)
				{
					float A, D;
					bAll = InPicture(Centre, A, D);
				}
				else
				{
					for (int32 c = 0; c < 8; ++c)
					{
						float A, D;
						bAll = InPicture(PartT.TransformPosition(FVector((c & 1) ? Local.Max.X : Local.Min.X, (c & 2) ? Local.Max.Y : Local.Min.Y,
							(c & 4) ? Local.Max.Z : Local.Min.Z)), A, D) && bAll;
					}
				}
				Whole += bAll ? 1 : 0;
			}
			if (bTrace)
			{
				AddInfo(FString::Printf(TEXT("RELOADTRACE %s %s: the well %.0f %% across, %.0f %% down, seen from %.0f deg; the part in place %d, whole %d"),
					*Arch, *Anchor.ToString(), 100.0f * Across, 100.0f * Down, Side, FVector::Dist(Centre, Well) < 6.0 ? 1 : 0, bAll ? 1 : 0));
			}
		});
		W.Run(0.3f, Face);
		FString Names;
		for (const FName& A : Anchors)
		{
			Names += (Names.IsEmpty() ? TEXT("") : TEXT(" ")) + A.ToString();
		}
		const float WellShare = Work > 0 ? 100.0f * WellIn / Work : 0.0f, TurnedShare = Work > 0 ? 100.0f * Turned / Work : 0.0f;
		// (judged where the part is in the gun for a tenth of a second or more: a flap that swings open is "in place" for
		// two or three frames as it leaves and comes home, and one of three says nothing)
		const float WholeShare = InPlace >= 6 ? 100.0f * Whole / InPlace : 100.0f;
		const FVector2D Out = Player->GetViewmodel()->GetReloadSide();
		AddInfo(FString::Printf(TEXT("RELOADVIEW %s (%s; the hands at %s, %d frames; it lies %s): where it is worked in the picture %.0f %% of them (%.0f..%.0f %% across, %.0f..%.0f %% down), seen from %.0f..%.0f deg (0 above, 90 its left), turned to the eyes %.0f %%; the part whole in the picture while in the gun %.0f %% (%d frames)"),
			*Arch, *Style.ToString(), *Names, Work, Out.Y > 0.5f ? TEXT("on top") : Out.X > 0.5f ? TEXT("on the right") : Out.X < -0.5f ? TEXT("on the left") : TEXT("underneath"),
			WellShare, 100.0f * AcrossLo, 100.0f * AcrossHi, 100.0f * DownLo, 100.0f * DownHi, SideLo, SideHi, TurnedShare, WholeShare, InPlace));
		TestTrue(FString::Printf(TEXT("%s: the reload is worked where the eyes see it (%.0f %% of its frames in the picture)"), *Arch, WellShare), Work > 0 && WellShare >= 90.0f);
		TestTrue(FString::Printf(TEXT("%s: and turned toward them (seen from its side %.0f %% of its frames)"), *Arch, TurnedShare), Work > 0 && TurnedShare >= 80.0f);
		TestTrue(FString::Printf(TEXT("%s: the part it works whole in the picture while it is in the gun (%.0f %%)"), *Arch, WholeShare), WholeShare >= 80.0f);
	}
	return true;
}

#endif
