#pragma once

#include "CoreMinimal.h"

/** One of the journal's sections (Data/journal.json "sections"): the armoury's JOURNAL tab lists them down its column. */
struct FSOJournalSection
{
	FName Id;
	FString Name;
	FString Line;
	/** M_UI_Glyph's index for an entry with no picture */
	int32 Glyph = 0;
	/** the light its rows are lit with */
	FLinearColor Color = FLinearColor(0.25f, 0.85f, 1.0f);
};

/**
 * One thing the player can learn. It is shown once its key is learned ("start" = from the first moment): what the
 * keys are is SOJournal's (a kind of creature killed, a named one, a stage of an operation begun, an operation
 * finished, a maker's gun carried). An operation's entries are not written in the journal's file: they are its plan's
 * own words (the briefing, what the radio says as each stage begins, the outcome), so they are never written twice.
 */
struct FSOJournalEntry
{
	FName Id;
	FName Section;
	FString Title;
	/** the small line over the title (who said it, what it is) */
	FString Sub;
	/** paragraphs, a blank line between */
	FString Text;
	/** a line under the text in its own head (an operation's stage: what it asked) */
	FString Note;
	FName Unlock;
	/** /Game/UI/Journal/T_Journal_<Picture> (none: the section's glyph) */
	FName Picture;
	/** a count shown with it (SOJournal::KillTally of a species: how many of them this player has killed) */
	FName Tally;
	/** what the tally counts ("KILLED") */
	FString TallyLabel;
};

/**
 * The journal (the owner's armoury reference: "a journal of what was learned"): Data/journal.json (sections, and the
 * entries that are not an operation's) and every operation's plan (Data/areas.json: its kind and plan), read once
 * (SOData: in a package from the staged data). The inventory keeps what was learned, what was read and the tallies
 * (USOInventoryComponent::Learn, MarkJournalRead, Tally); the armoury's JOURNAL tab shows it.
 */
struct SOCOMBAT_API FSOJournalData
{
	TArray<FSOJournalSection> Sections;
	TArray<FSOJournalEntry> Entries;

	static const FSOJournalData& Get();
	const FSOJournalSection* FindSection(FName Id) const;
	const FSOJournalEntry* Find(FName Id) const;
	/** The entries a key shows (in the journal's order). */
	TArray<const FSOJournalEntry*> UnlockedBy(FName Key) const;
};

/** The keys the journal learns and the tallies it counts: one place that knows how they are spelled. */
namespace SOJournal
{
	/** shown from the first moment */
	SOCOMBAT_API FName StartKey();
	/** a creature of this species was killed where the player was (every player of the world learns it) */
	SOCOMBAT_API FName MetKey(FName Species);
	/** a named creature (an operation's variant) was killed */
	SOCOMBAT_API FName NamedKey(FName Variant);
	/** a stage of an operation began (the operation's area id, the stage's id) */
	SOCOMBAT_API FName StageKey(FName Operation, FName Stage);
	/** an operation was finished */
	SOCOMBAT_API FName DoneKey(FName Operation);
	/** a gun of this maker came in (USOWeaponData::Origin) */
	SOCOMBAT_API FName OriginKey(FName Origin);
	/** tallies: creatures of a species this player killed, all its kills, named ones, operations finished, deaths */
	SOCOMBAT_API FName KillTally(FName Species);
	SOCOMBAT_API FName KillsTally();
	SOCOMBAT_API FName NamedTally();
	SOCOMBAT_API FName DoneTally(FName Operation);
	SOCOMBAT_API FName DeathsTally();
	/** An operation's area id from its plan's file ("Data/op_meridian.json" -> meridian). */
	SOCOMBAT_API FName OperationOf(const FString& PlanFile);
}
