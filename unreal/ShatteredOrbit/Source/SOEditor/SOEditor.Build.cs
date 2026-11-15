using UnrealBuildTool;

// Editor-only tools the asset import calls (Content/Python/import_assets.py). Never in a game build.
public class SOEditor : ModuleRules
{
	public SOEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
		PrivateDependencyModuleNames.AddRange(new string[] { "UnrealEd", "PhysicsUtilities", "PhysicsCore" });
	}
}
