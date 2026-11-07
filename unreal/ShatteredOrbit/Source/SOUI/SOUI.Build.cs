using UnrealBuildTool;

public class SOUI : ModuleRules
{
	public SOUI(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "UMG", "CommonUI", "GameplayAbilities", "SOCore", "SOCombat", "SOCharacter" });
		PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore", "InputCore", "RenderCore" });
	}
}
