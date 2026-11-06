using UnrealBuildTool;

public class ShatteredOrbit : ModuleRules
{
	public ShatteredOrbit(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput",
			"SOCore", "SOCharacter", "SOCombat", "SOWorld", "SOUI" });
	}
}
