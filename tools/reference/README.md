# Reference checks against Epic's engine content (measure only)

The players and guns are checked against Epic's engine references:

- Manny / Quinn;
- the MetaHuman template head;
- the MetaHuman archetype face and body.

Epic's files are **never** imported into our project or committed. The scripts here run in a separate scratch Unreal
project, and every export goes to a scratch folder outside the repo.

1. Make a scratch project.
   - It is an empty `.uproject` with the PythonScriptPlugin, EditorScriptingUtilities, MetaHumanSDK and
     MetaHumanCharacter plugins enabled.
   - Copy `Templates/TemplateResources/High/Characters/Content/Mannequins` into its `Content/Characters` if you
     want Manny / Quinn too.
2. Export the references.
   - Run `export_epic_reference.py` with `REF_OUT=<scratch folder>`, using
     `UnrealEditor.exe Scratch.uproject -ExecutePythonScript=...`.
3. Render the same-scene comparison.
   - Run `compare_heads_unreal.py` with `CMP_OUT=<scratch>/cmp` and `CMP_SRC=` pointing at the folders that hold
     `player_<sex>__Body.fbx`.
   - It renders Epic's head and both of ours with the same clay material, light and 30° lens, eye lines aligned,
     from eight angles.
4. Compose the sheet.
   - Run `python compare_heads_sheet.py <scratch> out.jpg`.
   - The rows are Epic, ours and the overlays (cyan Epic, orange ours).

The numbers and the decisions taken from them are in `tools/blender/proportions.md`.
