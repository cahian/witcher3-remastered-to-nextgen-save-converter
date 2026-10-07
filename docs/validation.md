# Validation record

One private checkpoint from a campaign created in Remastered was converted and reloaded in Steam Next-Gen 4.04 on Steam Deck / Proton. The save, extracted contents, account information, screenshots and remote-control material are not included in this repository.

## Recorded result

| Check | Result for the investigated checkpoint |
| --- | --- |
| Source build | Remastered `5.0.1044392` |
| Source header tuple | `(66,29,164)` |
| Target game | Steam Next-Gen `4.04` |
| Final tuple | `(64,27,163)` |
| Character rendering | Geralt's body and equipped clothing visible |
| Player inventory | 111 stacks; original quantities and equipment preserved |
| Currency | 232 crowns |
| Progression | Level 5, 64 XP |
| Skills | 102 Geralt entries; 4 free points; 0 purchased noncore skills |
| Quest state | Expected journal and active objective present |
| Final runtime step | Restart and load in 4.04 with the temporary mod removed |

The migration mod compiled in the real target installation. The public generator was also checked against the retained local game script: its output preserves the tested migration and diagnostic code. The migration script matches byte for byte; only a validation comment was updated in the diagnostic helper after testing. No game script is bundled with the source repository.

## Findings retained in the workflow

A header-only candidate failed the compatibility check or loaded with broken inventory/character appearance as additional headers were changed. Converting the inventory record layout was required.

The supported three Remastered skill purchases were removed and refunded without counting the core skill as a purchase. The resulting points were verified in the game. A native save was created using the guarded forced-checkpoint helper while paused during the existing combat, without defeating the quest enemy. A regular forced autosave request did not create a file in that situation.

Native loading regenerated four item IDs. The inventory comparison found unambiguous equivalent item contents; this was recorded as ID regeneration, not hidden as byte-for-byte identity. Diagnostic combat reduced the condition of four equipment items. Their original condition values were restored in the private investigation before final validation. That one-off restoration is not a feature of the public converter; users should avoid combat damage during conversion and review condition changes in the audit.

Inactive Ciri's saved skill data also required normalization from a separate native 4.04 reference. Its structure was verified, and the finalized file passed the final Geralt reload without the mod. **A playable Ciri quest and a complete campaign were not tested.**

## What the tests establish

Public automated tests use synthetic structures. They check parsing bounds, rejected unknown data, relocation integrity, narrow character-state invariants, local mod generation and output handling. Private integration checks were performed outside the repository against the actual save and target script.

The CLI emits `runtime_validated: false` even for files that have been tested by a person. It can inspect bytes but cannot infer whether a real game load, save and unmodified reload occurred. A successful `audit` invocation is a report to inspect, not a certificate that all gameplay is compatible.

## Scope of the claim

This is evidence for one checkpoint and its supported structural profile. It does not establish compatibility for all campaigns, every Remastered-only mechanic, altered game scripts, all platforms, future builds or an entire playthrough. Additional compatibility claims require additional saves, explicit structural support and recorded game checks.
