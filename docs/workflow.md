# Conversion workflow

This procedure covers the supported Remastered profile described in the [README](../README.md). Keep the original save throughout. The Python commands create candidates; the game provides the necessary runtime check and native serialization.

## 1. Prepare an isolated test

Exit The Witcher 3. In Steam's game properties, turn off Steam Cloud for the game while preparing and testing the conversion. Back up the complete `The Witcher 3` Documents directory, including `gamesaves` and settings, somewhere outside the live save directory.

On Windows, the save directory is normally `Documents/The Witcher 3/gamesaves`, including any Documents redirection configured on your machine.

On Steam Deck, locate the Steam library's `steamapps/compatdata/292030` prefix. The path inside it is:

```text
pfx/drive_c/users/steamuser/Documents/The Witcher 3/gamesaves
```

The library may be on internal storage or another drive. Do not assume a particular mount point. Move the original `gamesaves` directory to the backup location and create an empty replacement for the test. Keep both versions until the result is checked. The CLI does not change these directories or Steam settings for you.

Create a separate conversion working directory outside the repository. Put a copy of the source save there as `input.sav`. All example commands below run from the project checkout with the virtual environment activated.

## 2. Inspect and prepare

```sh
python -m w3save inspect ../conversion/input.sav
python -m w3save prepare ../conversion/input.sav --output ../conversion/candidate.sav
```

Review the inspection result. `prepare` requires the source tuple `(66,29,164)` and the known migration profile. A refusal means that this tool has not established how to convert that data. Do not remove its checks to force a file through.

The output status says the candidate requires native migration and a game test. The command repairs understood inventory records and rewrites supported version headers; it does not finish Geralt's skill migration or normalize inactive Ciri.

When installing the candidate in the isolated `gamesaves` directory, retain the original save's recognized `.sav` basename. The generic names `input.sav` and `candidate.sav` are convenient working names outside the game's directory. Keep the untouched original elsewhere. A matching `.png` thumbnail is optional. The successful final 4.04 reload used `.sav` plus `.png` and no `.json`; the tool does not require a Remastered JSON sidecar.

## 3. Generate and install the temporary mod

The source must be the installed **Next-Gen 4.04** script, normally under:

```text
The Witcher 3/content/content0/scripts/game/gameplay/ability/PlayerAbilityManager.ws
```

```sh
python -m w3save make-mod --game-script "/path/to/The Witcher 3/content/content0/scripts/game/gameplay/ability/PlayerAbilityManager.ws" --output-dir ../conversion/generated-mod
```

The generator recognizes this source SHA-256:

```text
2aa887f7767db04e26978d91d62799181305ed421cde0e293e33d73d9f8403ff
```

It preserves the original file's UTF-16LE encoding and CRLF line endings and inserts the original migration additions. It refuses a modified file, another version, or duplicate migration. The repository does not contain the full game script; the generated local output does. Do not upload that output with a bug report.

Copy `generated-mod/modCheckpointRemasterTo404` to the game's `mods` directory while the game is closed. The final layout is:

```text
The Witcher 3/mods/modCheckpointRemasterTo404/content/scripts/
  checkpointDiagnostics.ws
  game/gameplay/ability/PlayerAbilityManager.ws
```

Do not merge it into another mod or overwrite an existing folder of that name. Other mods and modified base scripts are outside the tested configuration. Start 4.04 and allow script compilation. If compilation fails, stop and retain the error text; loading without the migration does not satisfy the workflow.

## 4. Load and verify Geralt

Load the prepared candidate explicitly. Before moving or fighting, pause and inspect the character. The supported migration must produce:

- 102 skill entries with no purchased noncore skills;
- 4 free skill points and 0 used points;
- the original level, experience and inventory contents;
- visible body/equipment, the expected quest journal and active objective.

The script checks the original narrow profile before changing skills. A failed `Init` return is **not a guaranteed engine loading abort**. Seeing the scene load is therefore insufficient; check the actual points and state.

The optional debug helper exposes `chrpopup()` for a persistent state summary, `chrstatus()` for a notification and log entry, and `chritems(page)` for pages of eight inventory stacks with quantities and equipment slots. To use the console, back up `bin/config/base/general.ini`, enable `DBGConsoleOn=true` under `[General]`, and open the console using the key appropriate to your keyboard layout, commonly `~`. See [CD PROJEKT RED's console instructions](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/36208717/WS%3A%2BEnable%2Bdebug%2Bconsole%2Bin-game).

`chrpopup()` includes `skills`, `learned`, `free`, `used`, inventory stack count, equipment count, combat and save-lock state. Compare item contents as well as counts: the right number of entries alone does not establish inventory preservation.

## 5. Create a native save

Use a new normal manual slot when the game allows it. Do not overwrite the original checkpoint. Copy the newly created native `.sav` to the working directory as `native.sav`.

For the tested checkpoint, combat prevented ordinary saving. The included helper supports:

```text
chrsave(EXPECTED_STACK_COUNT,true)
```

Replace `EXPECTED_STACK_COUNT` with the verified native player inventory stack count. It was 111 in the recorded case. The helper checks the skill profile and stack count, then calls the game's `SaveGame(SGT_ForcedCheckPoint,-1)` API. In the recorded test, invoking `chrsave(111,true)` with the pause menu active and the console open produced a native checkpoint without defeating the quest enemy.

This option is for the already verified state, not a substitute for checking inventory or quests. Confirm a new file actually appeared. `chrsave(111)` uses an autosave request; that request produced **no file** during the tested combat. Neither a command returning nor a notification proves a save completed.

Avoid `savefix`, manually invoking combat-end events, killing enemies, teleporting or switching characters merely to enable saving. Those operations can change campaign state. Diagnostic combat can also consume items or reduce equipment condition; compare the audit results and restart from the untouched candidate if necessary.

## 6. Obtain a native reference and normalize inactive Ciri

Keep the converted native save safe outside `gamesaves`. Obtain a separate save created directly by unmodified 4.04 with the required unspent Ciri state. The recorded investigation used a newly started Hearts of Stone-only reference campaign, saved in its own isolated test directory. Creating that reference does not replace the converted campaign.

Use a reference from the target installation and required DLC configuration. The finalizer validates its Ciri data; not every arbitrary 4.04 save is a suitable reference. Copy it to the working directory as `reference-4.04.sav`.

```sh
python -m w3save finalize ../conversion/native.sav --reference ../conversion/reference-4.04.sav --output ../conversion/final.sav
python -m w3save audit ../conversion/input.sav ../conversion/final.sav
```

Finalization normalizes the supported inactive Ciri skill property and adjusts enclosing sizes/offsets. It remaps names into the target save's dictionary. It does not copy the reference's quest history, inventory, position or Geralt state. See [format notes](format.md) and [limits](limitations.md).

The audit compares serialized state and item contents. Native loading may regenerate item IDs; these are reported separately from genuine item loss or changes. The `facts` section reports missing, added and changed records, including their values and timestamps; it does not infer whether a change is harmless. Review quantities, equipment, currency, condition, skills and quest/fact evidence. `runtime_validated: false` remains correct: the CLI cannot observe your game. Exit code 0 means that the report was produced, even when differences are present; input/parsing errors return 2.

## 7. Reload without the mod and clean up

Exit the game. Remove only the generated `modCheckpointRemasterTo404` folder. Put the finalized save in the isolated save directory under a recognized save basename, restart 4.04, and load it explicitly.

Repeat the body, equipment, inventory, level/XP, skill-point and quest checks. This is the necessary confirmation that the output no longer depends on the temporary mod. Keep a copy of that checked save outside the game directory.

After verification, exit again, restore the original save directory from your backup, and add the converted save under a distinct recognized basename that does not overwrite an existing file. Remove reference/test saves from the live directory, restore the console setting if you changed it, and re-enable Steam Cloud when the intended local save set is in place. If Steam asks which files to synchronize, inspect the local/cloud dates and contents against your retained backup before choosing.

## Logs

The helper's visible popup is sufficient for its state summary. For additional logging, `-debugscripts` was used with the game and `scriptslog.txt` was collected from the game's Documents directory. Copy useful logs before restarting because they can be recreated. Logs can contain detailed gameplay state; redact them before sharing.
