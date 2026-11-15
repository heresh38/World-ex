#include "Modules/ModuleManager.h"
#include "SOCombatTypes.h"

DEFINE_LOG_CATEGORY(LogSOCombat);

namespace SOTags
{
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Damage, "SetByCaller.Damage", "Damage amount carried by the damage effect");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Crit, "SetByCaller.Crit", "1 when the hit was a precision hit");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Duration, "SetByCaller.Duration", "Seconds an effect lasts");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Magnitude, "SetByCaller.Magnitude", "The amount an effect adds or scales by");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Gear_Plating, "SetByCaller.Gear.Plating", "Points of Plating worn gear gives");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Gear_Mending, "SetByCaller.Gear.Mending", "Points of Mending worn gear gives");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Gear_Stride, "SetByCaller.Gear.Stride", "Points of Stride worn gear gives");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Gear_Ordnance, "SetByCaller.Gear.Ordnance", "Points of Ordnance worn gear gives");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Gear_Impact, "SetByCaller.Gear.Impact", "Points of Impact worn gear gives");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Gear_Focus, "SetByCaller.Gear.Focus", "Points of Focus worn gear gives");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(State_Dead, "State.Dead", "The character is dead");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(State_Aiming, "State.Aiming", "On the sights");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(State_Sprinting, "State.Sprinting", "Sprinting");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(State_Traversing, "State.Traversing", "In a vault, a mantle or a climb");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Status_Burn, "Status.Burn", "Taking damage over time (acid, fire, parasites)");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Status_Slow, "Status.Slow", "Moving slower");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Status_Stagger, "Status.Stagger", "Knocked out of what it was doing: cannot act");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Status_Guard, "Status.Guard", "Braced: takes a share of all damage and cannot be staggered");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Status_Jam, "Status.Jam", "Jammed: its abilities cannot be used");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Status_Haste, "Status.Haste", "Rallied: moving faster");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Status_Suppressed, "Status.Suppressed", "Under fire: rounds are passing close");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Cooldown_Grenade, "Cooldown.Grenade", "A grenade charge coming back");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Cooldown_Melee, "Cooldown.Melee", "A melee charge coming back");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Cooldown_Class, "Cooldown.Class", "The class ability coming back");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Cooldown_Movement, "Cooldown.Movement", "The movement ability coming back");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(Cooldown_Ultimate, "Cooldown.Ultimate", "The ultimate coming back");
}

IMPLEMENT_MODULE(FDefaultModuleImpl, SOCombat);
