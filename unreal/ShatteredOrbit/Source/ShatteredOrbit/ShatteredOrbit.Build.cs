using UnrealBuildTool;

public class ShatteredOrbit : ModuleRules
{
	public ShatteredOrbit(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput",
			"GameplayAbilities", "GameplayTags", "AIModule", "NavigationSystem", "RHI", "RenderCore",
			"SOCore", "SOCharacter", "SOCombat", "SOWorld", "SOUI", "SOAI" });
	}
}
