using UnrealBuildTool;

public class ShatteredOrbitEditorTarget : TargetRules
{
	public ShatteredOrbitEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "ShatteredOrbit", "SOCore", "SOCharacter", "SOCombat", "SOWorld", "SOUI", "SOAI", "SOOperation" });
	}
}
