using UnrealBuildTool;

public class SOAI : ModuleRules
{
	public SOAI(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "AIModule", "NavigationSystem", "GameplayTasks",
			"GameplayAbilities", "GameplayTags", "Json", "SOCore", "SOCombat", "SOCharacter" });
	}
}
