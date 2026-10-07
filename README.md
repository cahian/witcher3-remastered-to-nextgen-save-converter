# The Witcher 3 Remastered to Next-Gen Save Converter

![The Witcher 3 Save Converter — Remastered 5.0 to Next-Gen 4.04](assets/repository-cover.png)

[![Tests](https://github.com/cahian/witcher3-remastered-to-nextgen-save-converter/actions/workflows/tests.yml/badge.svg)](https://github.com/cahian/witcher3-remastered-to-nextgen-save-converter/actions/workflows/tests.yml)

Convert a **The Witcher 3 Remastered 5.0 save to Steam Next-Gen 4.04**, including a campaign originally started in Remastered. This experimental Python toolkit repairs the supported inventory layout, generates a temporary skill migration mod from your installed game, and checks the resulting save.

**One real checkpoint has been converted and reloaded in unmodified 4.04 on Steam Deck. Support is deliberately narrow.** The current skill profile requires exactly the three purchased skills `sword_s22`, `sword_s23`, and `sword_s24`, each at level 1, with 1 free and 3 spent skill points and no researched mutations. Those purchases become **4 available points** in Next-Gen. Other profiles are refused.

[Português](README.pt-BR.md) · [Complete workflow](docs/workflow.md) · [Compatibility limits](docs/limitations.md) · [Validation evidence](docs/validation.md) · [Save format](docs/format.md)

## Why this exists

Changing only the save's version fields can produce a loadable but broken character: **missing body, missing inventory, or incompatible skills**. The investigated Remastered save contains extra inventory fields and a different skill array. This workflow migrates those structures and lets the older game create a native save before the final check.

The project is an independent community tool. It includes original conversion code and migration additions, with no game files or gameplay saves. Processing is local; the CLI does not upload your save or connect to Steam.

## Compatibility

| Component | Observed and supported scope |
| --- | --- |
| Source | Remastered build `5.0.1044392`, header tuple `(66, 29, 164)` |
| Target | Steam Next-Gen `4.04`, header tuple `(64, 27, 163)` |
| Inventories | Recognized components with the understood two-byte empty extensions |
| Geralt skills | The specific three-skill profile described above; 167 entries rebuilt as 102 |
| Inactive Ciri | Unspent supported state, normalized using your own native 4.04 reference save |
| Game script | Exact supported unmodified 4.04 `PlayerAbilityManager.ws` |
| Runtime validation | One checkpoint on Steam Deck / Proton; no full playthrough claim |

This does not target classic 1.32 or establish support for every 5.x build, character build, mod, or console save. Read the [complete guards and limits](docs/limitations.md) before using it.

## Install

Use Python 3.10 or newer. From a downloaded or cloned checkout:

```sh
git clone https://github.com/cahian/witcher3-remastered-to-nextgen-save-converter.git
cd witcher3-remastered-to-nextgen-save-converter
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m w3save --help
```

On Windows, create the environment with `py -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1` in PowerShell. Python portability is separate from game validation: the recorded game test used Steam Deck.

## Quick start

Keep your source save and backups outside this repository. These examples assume a separate `../conversion` directory containing `input.sav`; replace paths with your own. Output files must not already exist.

```sh
python -m w3save inspect ../conversion/input.sav
python -m w3save prepare ../conversion/input.sav --output ../conversion/candidate.sav
python -m w3save make-mod --game-script "/path/to/The Witcher 3/content/content0/scripts/game/gameplay/ability/PlayerAbilityManager.ws" --output-dir ../conversion/generated-mod
```

Then follow the [game steps](docs/workflow.md): isolate your test saves, install the generated temporary mod, load the candidate, verify the character and inventory, and create a native 4.04 save. You also need a separate native 4.04 reference containing an unspent Ciri state. The reference supplies Ciri's old skill definitions; it does not replace your campaign.

After obtaining `native.sav` and `reference-4.04.sav`:

```sh
python -m w3save finalize ../conversion/native.sav --reference ../conversion/reference-4.04.sav --output ../conversion/final.sav
python -m w3save audit ../conversion/input.sav ../conversion/final.sav
```

Remove the temporary mod, restart 4.04, and load `final.sav`. Check the body, equipment, inventory, level/XP, skill points, quest journal and active objective again. **Binary audit output alone does not prove the game works.** The CLI always reports `runtime_validated: false`, because it does not run the game.

## Commands

| Command | Result |
| --- | --- |
| `inspect INPUT` | JSON format, inventory and character-state summary |
| `prepare INPUT --output CANDIDATE` | A separate guarded inventory/header conversion candidate |
| `make-mod --game-script PATH --output-dir DIR` | A local mod generated from your own verified game script |
| `finalize NATIVE --reference REFERENCE --output FINAL` | Inactive Ciri normalization after native saving |
| `audit ORIGINAL CANDIDATE` | Item/state comparison, including reported item-ID regeneration |

The CLI refuses existing outputs and unsupported input. It does not write to your live saves automatically, change Steam Cloud settings, install the game, or remove mods. See [workflow and cleanup](docs/workflow.md) for those explicit steps.

## What was verified

The final investigated save loaded without the temporary mod in Next-Gen 4.04 with Geralt's body and equipment visible, 111 inventory stacks, 232 crowns, level 5, 64 XP, 4 available skill points, and the expected quest state. Inactive Ciri was structurally normalized and preserved through the final Geralt reload. A playable Ciri quest and a complete campaign were **not** tested. See the [validation record](docs/validation.md) for the distinction between byte checks and game observations.

## Development and reports

Run the synthetic tests with:

```sh
python -m unittest discover -s tests -v
```

Public tests contain constructed binary fixtures, not private saves. For a compatibility report, provide the tool version, source/target game versions, refused check or error, and a redacted diagnostic summary. Avoid attaching saves, gameplay screenshots, full logs or account paths by default. Unsupported cases need new evidence and tests; bypassing checks does not establish compatibility.

Research references: [W3SavegameEditor](https://github.com/Atvaark/W3SavegameEditor), [save format notes](https://github.com/dodojesuslol/w3-quest-tracker/blob/main/docs/save-format.md), and the [Remastered script comparison](https://github.com/ElementaryLewis/The-Witcher-3-Remastered-Changelog/commit/e026f253c8790ebcfe545188eb0ae77978dc1178). [W3 Save Repair](https://github.com/timrosenbach/w3-save-repair) addresses a separate damaged-facts problem; it is not a replacement for this downgrade workflow.
