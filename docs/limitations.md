# Compatibility limits and refusal conditions

The current tool extracts a reusable workflow from one completed conversion. It intentionally accepts a narrow observed profile. `prepare`, a generated mod or a native header tuple does not by itself establish complete gameplay compatibility.

## Versions and layout

The source must match the supported Remastered tuple `(66,29,164)` and recognized nested source serializers. The observed source build was `5.0.1044392`. The target is Next-Gen 4.04 with `(64,27,163)`. Classic 1.32, console save containers, future builds and modified base scripts are outside the initial verified scope.

Inventory conversion understands only the recognized item/component layout with empty two-byte source extensions. Nonzero new fields, ambiguous player/component selection, malformed tables, unsupported names, overlapping edits, unknown affected record shapes or out-of-range values require refusal. Do not treat an unknown field as disposable padding.

## Exact Geralt skill profile

The supported Remastered manager has 167 skill entries. Its purchased noncore skills are exactly `sword_s22`, `sword_s23`, and `sword_s24`, each level 1/cost 1 and not temporary. The point balance is 1 free and 3 used. The 13 mutation records must be unresearched, with no used skill points or colored mutagens. The four mutagen slots must have the expected ordered equipment slots and group IDs; the nine synergy-bonus records must be empty.

The temporary migration rebuilds 102 entries from native definitions and leaves 4 points available, with the purchases removed. It preserves mutagen item references. It is a narrow respec, not a mapping that recreates every Remastered combat ability in Next-Gen. Core skills do not receive a refund.

A second manager initialization may see the already-refunded 4-free/0-used balance; it must not add another refund. Other learned skill sets, point totals or advanced systems require a separate implementation and validation. The CLI's accepted profile may be stricter than individual runtime checks.

A failing mod guard returns false from ability-manager initialization; the engine may still show a loaded world. Verify the actual skill count and points before saving. Do not equate a visible scene with a successful migration.

## Ciri and reference saves

Before normalizing Ciri, finalization verifies that Geralt already has the native 102-entry skill order, no purchased noncore skills, and 4 free / 0 used points. Merely rewriting a source save's headers cannot satisfy this check. The target and reference ability-manager classes must also match the supported layout.

Finalization is limited to the recognized inactive, unspent Ciri state. It uses a native 4.04 reference containing Ciri's own skill definitions. It does not substitute Geralt definitions or copy an entire player object. Ciri is identified independently by a typed player marker and supported `ciri_player` or `ciri_winter` appearance. Both Ciri states require the 16 recognized core skills at level 1 and no learned noncore skills or altered core state. The native reference has 102 skill entries; the target has 167 entries, or 102 for an already-normalized no-op. Both top-level headers must be `(64,27,163)`. The target Ciri serializer must also be `(64,27,163)`; the reference accepts that tuple or the observed legacy `(57,10,162)` serializer used by the validated native winter-Ciri reference. Learned or unrecognized Ciri state and unsuitable references must be refused.

Use your own reference from the target installation. The recorded reference was a fresh Hearts of Stone-only campaign. This does not mean every reference save will pass. Structural checks and the final Geralt reload passed; later playable Ciri sequences remain untested.

## Preserved state and runtime checks

The intended conversion preserves inventory contents, currency, progression and campaign state apart from the documented skill reset and required serializer changes. It does not intentionally add equipment, heal the player, repair gear, advance quests or alter difficulty.

Native loading can regenerate item IDs. The audit reports identity changes separately from content comparisons. Combat during testing can consume items, change condition or otherwise modify state; pause promptly and inspect differences. The public tool does not include the private investigation's one-off equipment-condition restoration.

Do not weaken checks or use broad save-lock removal, enemy-kill commands, teleportation or character switching to manufacture a successful save. The guarded native checkpoint helper is documented for the tested combat case, and actual file creation still needs confirmation.

## Operational boundaries

The CLI performs local file operations. It does not install Steam, contact a server, manage Steam Cloud, authenticate accounts, control a desktop or copy files into live game directories automatically. It refuses existing outputs. Generated mods contain a locally read game script and should remain local.

Retain backups, isolate test saves and follow the documented cleanup. Required downloadable content must be installed on the target game. A successful binary audit cannot establish animation, quest-transition, world or full-playthrough compatibility.
