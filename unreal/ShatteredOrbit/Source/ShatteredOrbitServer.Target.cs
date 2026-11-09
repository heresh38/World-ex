using UnrealBuildTool;

// Dedicated server. Building it needs a source build of the engine (the launcher build ships no server binaries).
public class ShatteredOrbitServerTarget : TargetRules
{
	public ShatteredOrbitServerTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Server;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "ShatteredOrbit", "SOCore", "SOCharacter", "SOCombat", "SOWorld", "SOUI", "SOAI", "SOOperation" });
	}
}
