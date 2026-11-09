"""Creates the Enhanced Input assets used by ASOCharacter / ASOPlayerController.

/Game/Input/IA_*.uasset (one per action) and /Game/Input/IMC_Default.uasset with keyboard/mouse and
gamepad mappings. Safe to re-run: existing assets are updated in place and the mapping list is rebuilt.

Headless:
    UnrealEditor-Cmd.exe <path>/ShatteredOrbit.uproject -run=pythonscript -script="<path>/Content/Python/setup_input.py" -unattended -nullrhi
In the editor: Tools > Execute Python Script, or `py setup_input.py` in the console.
"""

import unreal

FOLDER = "/Game/Input"

# name -> value type
ACTIONS = {
    "IA_Move": unreal.InputActionValueType.AXIS2D,
    "IA_Look": unreal.InputActionValueType.AXIS2D,          # mouse counts
    "IA_LookGamepad": unreal.InputActionValueType.AXIS2D,   # right stick (rate)
    "IA_Jump": unreal.InputActionValueType.BOOLEAN,
    "IA_Sprint": unreal.InputActionValueType.BOOLEAN,
    "IA_Crouch": unreal.InputActionValueType.BOOLEAN,
    "IA_ToggleView": unreal.InputActionValueType.BOOLEAN,
    "IA_Interact": unreal.InputActionValueType.BOOLEAN,
    "IA_Fire": unreal.InputActionValueType.BOOLEAN,
    "IA_Aim": unreal.InputActionValueType.BOOLEAN,
    "IA_Reload": unreal.InputActionValueType.BOOLEAN,
    "IA_Weapon1": unreal.InputActionValueType.BOOLEAN,
    "IA_Weapon2": unreal.InputActionValueType.BOOLEAN,
    "IA_Weapon3": unreal.InputActionValueType.BOOLEAN,
    "IA_NextWeapon": unreal.InputActionValueType.BOOLEAN,
    "IA_PrevWeapon": unreal.InputActionValueType.BOOLEAN,
    "IA_Inventory": unreal.InputActionValueType.BOOLEAN,
    "IA_Map": unreal.InputActionValueType.BOOLEAN,
    "IA_Flashlight": unreal.InputActionValueType.BOOLEAN,
}

# (action, key, modifiers) - modifiers: "neg" negate, "swz" swizzle YXZ (so a 1D key drives Y), "dz" radial dead zone
MAPPINGS = [
    # Move: X = right, Y = forward
    ("IA_Move", "W", ["swz"]),
    ("IA_Move", "S", ["swz", "neg"]),
    ("IA_Move", "D", []),
    ("IA_Move", "A", ["neg"]),
    ("IA_Move", "Gamepad_Left2D", ["dz"]),
    ("IA_Look", "Mouse2D", []),
    ("IA_LookGamepad", "Gamepad_Right2D", ["dz"]),
    ("IA_Jump", "SpaceBar", []),
    ("IA_Jump", "Gamepad_FaceButton_Bottom", []),
    ("IA_Sprint", "LeftShift", []),
    ("IA_Sprint", "Gamepad_LeftThumbstick", []),
    ("IA_Crouch", "C", []),
    ("IA_Crouch", "LeftControl", []),
    ("IA_Crouch", "Gamepad_FaceButton_Right", []),
    ("IA_ToggleView", "T", []),
    ("IA_ToggleView", "Gamepad_DPad_Up", []),
    ("IA_Interact", "E", []),
    ("IA_Interact", "Gamepad_FaceButton_Top", []),
    ("IA_Fire", "LeftMouseButton", []),
    ("IA_Fire", "Gamepad_RightTrigger", []),
    ("IA_Aim", "RightMouseButton", []),
    ("IA_Aim", "Gamepad_LeftTrigger", []),
    ("IA_Reload", "R", []),
    ("IA_Reload", "Gamepad_FaceButton_Left", []),
    ("IA_Weapon1", "One", []),
    ("IA_Weapon2", "Two", []),
    ("IA_Weapon3", "Three", []),
    ("IA_NextWeapon", "MouseScrollDown", []),
    ("IA_NextWeapon", "Gamepad_DPad_Right", []),
    ("IA_PrevWeapon", "MouseScrollUp", []),
    ("IA_PrevWeapon", "Gamepad_DPad_Left", []),
    ("IA_Inventory", "I", []),
    ("IA_Inventory", "Tab", []),
    ("IA_Inventory", "Gamepad_Special_Left", []),
    ("IA_Map", "M", []),
    ("IA_Map", "Gamepad_DPad_Down", []),
    ("IA_Flashlight", "F", []),
    ("IA_Flashlight", "Gamepad_RightThumbstick", []),
]


def log(msg):
    unreal.log("[setup_input] " + msg)


def load_or_create(name, asset_class, factory):
    path = f"{FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, FOLDER, asset_class, factory)
    if asset is None:
        raise RuntimeError(f"could not create {path}")
    log(f"created {path}")
    return asset


def make_key(name):
    key = unreal.Key()
    key.import_text(name)  # FKey imports its plain name
    if not unreal.InputLibrary.key_is_valid(key):
        raise RuntimeError(f"unknown key {name}")
    return key


def make_modifier(kind, outer):
    if kind == "neg":
        return unreal.new_object(unreal.InputModifierNegate, outer)
    if kind == "swz":
        mod = unreal.new_object(unreal.InputModifierSwizzleAxis, outer)
        mod.set_editor_property("order", unreal.InputAxisSwizzle.YXZ)
        return mod
    if kind == "dz":
        mod = unreal.new_object(unreal.InputModifierDeadZone, outer)
        mod.set_editor_property("lower_threshold", 0.15)
        mod.set_editor_property("upper_threshold", 1.0)
        mod.set_editor_property("type", unreal.DeadZoneType.RADIAL)
        return mod
    raise ValueError(kind)


def main():
    if not unreal.EditorAssetLibrary.does_directory_exist(FOLDER):
        unreal.EditorAssetLibrary.make_directory(FOLDER)

    actions = {}
    for name, value_type in ACTIONS.items():
        action = load_or_create(name, unreal.InputAction, unreal.InputAction_Factory())
        action.set_editor_property("value_type", value_type)
        actions[name] = action

    imc = load_or_create("IMC_Default", unreal.InputMappingContext, unreal.InputMappingContext_Factory())
    imc.unmap_all()
    for action_name, key_name, _ in MAPPINGS:
        imc.map_key(actions[action_name], make_key(key_name))

    # map_key returns a copy in Python, so the modifiers are set on the stored array and written back.
    data = imc.get_editor_property("default_key_mappings")
    mappings = list(data.get_editor_property("mappings"))
    if len(mappings) != len(MAPPINGS):
        raise RuntimeError(f"expected {len(MAPPINGS)} mappings, IMC has {len(mappings)}")
    for mapping, (_, _, mods) in zip(mappings, MAPPINGS):
        mapping.set_editor_property("modifiers", [make_modifier(m, imc) for m in mods])
    data.set_editor_property("mappings", mappings)
    imc.set_editor_property("default_key_mappings", data)
    imc.set_editor_property("context_description", unreal.Text("Shattered Orbit default controls (keyboard/mouse + gamepad)"))

    for asset in list(actions.values()) + [imc]:
        unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    log(f"{len(actions)} input actions, IMC_Default with {len(mappings)} mappings saved")


main()
