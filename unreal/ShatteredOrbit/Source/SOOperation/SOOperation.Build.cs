using UnrealBuildTool;

public class SOOperation : ModuleRules
{
	public SOOperation(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "AIModule", "NavigationSystem",
			"GameplayAbilities", "Json", "SOCore", "SOCombat", "SOCharacter", "SOAI", "SOWorld" });
	}
}
