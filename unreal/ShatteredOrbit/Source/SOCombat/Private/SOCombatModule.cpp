#include "Modules/ModuleManager.h"
#include "SOCombatTypes.h"

DEFINE_LOG_CATEGORY(LogSOCombat);

namespace SOTags
{
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Damage, "SetByCaller.Damage", "Damage amount carried by the damage effect");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(SetByCaller_Crit, "SetByCaller.Crit", "1 when the hit was a precision hit");
	UE_DEFINE_GAMEPLAY_TAG_COMMENT(State_Dead, "State.Dead", "The character is dead");
}

IMPLEMENT_MODULE(FDefaultModuleImpl, SOCombat);
