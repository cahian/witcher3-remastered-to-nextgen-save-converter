# Observed save format and migration

These notes describe structures observed in the investigated Remastered and Next-Gen saves. They are not a complete REDengine save specification. The implementation refuses structures it cannot validate.

## Container and offsets

The outer signature is `SNFHFZLC`. At byte 8 is a little-endian 32-bit chunk count; at byte 12 is the header/payload-start offset. Each chunk-table record contains three little-endian 32-bit values: compressed size, decompressed size and cumulative absolute chunk end. The final chunk uses end value zero in the observed layout.

The payload consists of raw LZ4 blocks. The observed prefix length is 3084 bytes, and full chunks expand to 1 MiB. The decompressed image used by the tooling retains that prefix. Internal offsets therefore refer to positions in the full decompressed image, not a payload sliced to begin at zero.

`SAV3` begins the main payload, followed by the observed version tuple. Nested serializer headers use `SXAP` and another tuple. The source profile is `(66,29,164)`; the target is `(64,27,163)`. The target can also contain older nested serializer versions after native saving. The prepare command accepts the specific known source profile, not arbitrary mixed headers.

An `SE` marker ends the decompressed image; the four bytes immediately before it point to the variable table. That table records offsets and lengths. Its preceding metadata points to the name table (`NMMANU`) and root-block table (`RB`). Changing a record's length requires updating all affected references, not just recompressing the file.

## Inventory difference

The recognized `CInventoryComponent` records contain item identity, flags, quantity, condition, attributes, tags and optional mounted-slot information. In the observed Remastered layout, each item has two additional bytes after those fields. The supported case requires both bytes to be zero.

Removing those extensions recovers the observed older layout. The relocation step updates affected variable lengths, root and metadata pointers, and supported enclosing wrappers such as `SS`, `BLCK`, `AVAL`, `PORP` and `ROTS`/`STOR`. Unsupported enclosing byte-array properties are refused because their element counts also require migration. Unaffected data must remain byte-identical under relocation.

A byte pattern matching an inventory class index is insufficient evidence of an inventory. The parser must also validate bounds, item/name indices, IDs, tags, counts, optional fields and the terminal marker. Ambiguous or unrecognized records cannot be safely accepted merely because another inventory parsed successfully.

An output with corrected header values but unconverted inventory bytes can load with missing body/equipment or empty inventory. That is why the workflow treats successful loading as one check among several.

## Geralt skill migration

Remastered stores 167 skill entries in the investigated profile; native 4.04 uses 102. Skill enum names occur through the name dictionary, but the skill array is also indexed by enum order. Keeping the original array with older version numbers does not restore the older indexing.

The temporary mod runs after the base ability manager initializes and before skill-slot/post-initialization code consumes the array. It validates the narrow supported source profile, rebuilds skills from the installed 4.04 definitions, removes the replaced skill abilities, reconstructs skill/mutagen slots and preserves the referenced mutagen item IDs.

The supported purchased skills are `sword_s22`, `sword_s23`, and `sword_s24`, each at level/cost 1. Three used points and one free point become four free points and zero used. A learned core skill does not count as a purchase and does not earn a refund. The reconstructed array size and absolute point assignment prevent repeated initialization from duplicating the refund.

The mod is generated from an exact fingerprint of the user's installed script. Only the original additions are distributed; the full game script is never a repository asset.

## Inactive Ciri

Native saving after Geralt's migration can retain Remastered data for an inactive Ciri object. Finalization locates Ciri independently, validates the supported unspent state, obtains Ciri's native skill definition property from a separate 4.04 reference, and translates name/type/enum references into the target's dictionary.

Both the target and reference Ciri must have the 16 recognized core skills at level 1, with no learned noncore skills or altered core state. The reference supplies 102 entries; the supported target has 167 entries or is already normalized to 102. Ciri is identified by a typed player marker and supported appearance (`ciri_player` or `ciri_winter`) in the enclosing serialized entity, not by assuming it is the second skill array. The native reference used in validation had a global `(64,27,163)` header but a legacy `(57,10,162)` Ciri serializer with the winter appearance. That observed reference layout is accepted alongside native `(64,27,163)` Ciri; the target Ciri serializer must be `(64,27,163)`.

The operation changes Ciri's supported skill property and necessary enclosing lengths/offsets. It does not transplant the reference's full player, Geralt, inventory, world or quest state. Unsupported learned or otherwise unrecognized Ciri state is refused. A structural replacement still needs the final unmodified game reload; a complete Ciri quest was not part of the recorded test.

## Audit semantics

Byte identity, item identity and gameplay content are different checks. Native 4.04 can recreate an item under a different ID. The audit retains that difference and reports unambiguous content-equivalent matches separately. Names, quantities, slots, condition and other parsed item fields must be examined; a matching stack count alone is weak evidence.

Version tuples and a successful LZ4 round trip establish format properties. They do not establish that a quest, animation, world transition or later Ciri sequence works. Reports therefore distinguish binary checks from runtime observations.

## References

Research used [W3SavegameEditor](https://github.com/Atvaark/W3SavegameEditor), [save format notes](https://github.com/dodojesuslol/w3-quest-tracker/blob/main/docs/save-format.md), [a Python save-parser experiment](https://github.com/pxwxnvermx/witcher3-save-edit), and the [4.04/Remastered script comparison](https://github.com/ElementaryLewis/The-Witcher-3-Remastered-Changelog/commit/e026f253c8790ebcfe545188eb0ae77978dc1178). These references informed investigation; public visibility of game scripts is not a reason to bundle them in this project.
