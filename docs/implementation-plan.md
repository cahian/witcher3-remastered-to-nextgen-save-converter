# Public converter toolkit implementation plan

**Goal:** Publish the original, locally validated conversion workflow as a searchable experimental toolkit, with no private saves or game assets.

**Architecture:** Reuse the verified binary algorithms behind explicit commands. Inventory preparation produces a candidate; the native game performs the narrow Geralt skill migration and saving; finalization normalizes inactive Ciri using a user-provided native reference. Reports distinguish binary checks from runtime validation.

**Scope:** Observed source `(66,29,164)`, target `(64,27,163)`; empty two-byte inventory extensions; the documented three-skill early-game Geralt migration profile; unspent inactive Ciri. No universal compatibility claim, remote access, Steam installation, or automatic live-save writes.

## Interfaces and ownership

- Binary worker owns `w3save/container.py`, `metadata.py`, `inventory.py`, `relocate.py`, and corresponding tests. `decode_save(bytes)->bytes` returns the full decompressed image with the 3084-byte prefix; `encode_save(bytes)->bytes` round-trips it. `parse_meta(data)` retains the verified tuple interface. `scan_inventories(data, extra_size)` returns inventory descriptions and removal ranges; `prepare_inventory(data)->(bytes, report)` validates and relocates the source without version edits. `audit_inventory(original, native)->dict` compares player item content and reports regenerated IDs explicitly.
- Skills worker owns `w3save/skills.py`, `normalize.py` and tests. `Snapshot.from_bytes(data)` parses skill/point/fact state without filesystem assumptions; `Snapshot.summary()` returns the established structure. `normalize_ciri(target, reference)->(bytes, report)` validates native target/reference headers, independently identifies Ciri, translates dictionary indices and changes only its skill property plus relocation fields.
- Documentation/mod worker owns English/Portuguese READMEs, format/workflow/validation documentation, `w3save/mod.py`, original `.ws` snippets and tests. `generate_mod(source_script: bytes)->dict[str,bytes]` verifies the observed installed 4.04 script and inserts our additions; it does not bundle that script. Runtime helper commands and exact support guards are documented.
- Root owns package/configuration/CLI, integration, final review, and publication. All workers use synthetic fixtures in public tests and private integration samples only outside the repository.

## CLI deliverables

`python -m w3save inspect INPUT`: bounded parsing, version/state/count summary.

`python -m w3save prepare INPUT --output CANDIDATE`: reject unknown source profile/layout, convert inventories and version headers, preserve input, refuse existing output.

`python -m w3save make-mod --game-script PATH --output-dir DIR`: create temporary local migration mod from the user's own script; refuse modified scripts and existing output.

`python -m w3save finalize NATIVE --reference REFERENCE --output FINAL`: normalize inactive Ciri only, using the caller's 4.04 reference; refuse learned/unrecognized Ciri state.

`python -m w3save audit ORIGINAL CANDIDATE`: JSON comparison of item contents, skill state and format. Never declares in-game validation based on bytes alone.

## Verification and release steps

- [x] Write failing synthetic tests for truncated/bounded LZ4 containers, nonzero inventory extensions, invalid pointers, overlapping edits, Ciri name remapping/state preservation, mismatched scripts and output non-overwrite.
- [x] Implement public functions and run each owning test module, then the complete suite.
- [x] Run CLI commands against the retained private source/reference/native saves and compare with the verified conversion artifacts. Keep outputs outside this repository.
- [x] Verify README commands from a fresh virtual environment; scan tracked content for personal paths, secrets, saves, images and full game scripts. Only the deliberately public generated cover is included.
- [x] Review all code and compatibility claims independently; fix concrete findings.
- [ ] Create the explicitly requested public repository only after the original conversion succeeds. Push reviewed source, documentation and synthetic tests; verify visibility, remote HEAD and CI.

## Review focus

1. A malicious/truncated chunk table must not allocate unbounded decompression buffers.
2. A parser occurrence inside another item must not become a false inventory conversion.
3. Native item ID regeneration must be reported without hiding actual item loss.
4. Ciri must use Ciri definitions and preserve learned/core state; never transplant Geralt wholesale.
5. An existing output, symlink or source/output collision must not destroy a user's save.

The real save has already passed a 4.04 load without the temporary mod. That demonstrates one checkpoint, not an entire playthrough or every Remastered save.
