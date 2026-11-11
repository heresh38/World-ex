using UnrealBuildTool;

public class SOCore : ModuleRules
{
	public SOCore(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "Json", "MoviePlayer", "Slate", "SlateCore" });
	}
}
