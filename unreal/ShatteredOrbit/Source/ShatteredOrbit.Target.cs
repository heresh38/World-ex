using UnrealBuildTool;

public class ShatteredOrbitTarget : TargetRules
{
	public ShatteredOrbitTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "ShatteredOrbit", "SOCore", "SOCharacter", "SOCombat", "SOWorld", "SOUI", "SOAI" });
	}
}
