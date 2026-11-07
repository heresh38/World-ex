"""Run in a SCRATCH Unreal project with the MetaHumanSDK and MetaHumanCharacter plugins enabled (never ours): exports
Epic's MetaHuman template head, archetype face and body to FBX for measuring only."""
import unreal
import os
out = os.environ["REF_OUT"]   # a scratch folder outside the repo: these files are Epic's and are never committed
for path in ["/MetaHumanSDK/TemplateAssets/SM_MH_Head", "/MetaHumanCharacter/Face/SKM_Face", "/MetaHumanCharacter/Body/IdentityTemplate/SKM_Body"]:
    a = unreal.load_asset(path)
    unreal.log("MHX loaded %s %s" % (path, a))
    if not a: continue
    t = unreal.AssetExportTask(); t.object = a; t.filename = out + "/MH_" + path.split("/")[-1] + ".fbx"; t.automated = True; t.replace_identical = True; t.prompt = False
    t.options = unreal.FbxExportOption()
    unreal.log("MHX export %s %s" % (path, unreal.Exporter.run_asset_export_task(t)))
unreal.SystemLibrary.quit_editor()
