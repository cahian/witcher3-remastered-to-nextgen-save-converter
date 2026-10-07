"""Observed native inventory layouts, semantic player selection and comparison."""
from bisect import bisect_right
from collections import Counter
import math
import struct

from .metadata import parse_meta, require

COMPONENT_HASHES = {bytes.fromhex(s) for s in (
    '0c586a71', '0d586a71', '5c199087', '616cf35e', '814c81e7', 'a21535b6')}
SOURCE_VERSION = (66, 29, 164)
TARGET_VERSION = (64, 27, 163)


class _UnsupportedInventoryLayout(ValueError):
    """A structurally decoded item supplied evidence beyond a class-index hit."""


def _parse_inventory(data, start, names, extra_size, limit):
    items = []

    def check(condition, message):
        if not condition:
            error = _UnsupportedInventoryLayout if items else ValueError
            raise error(message)

    def need(pos, size):
        check(start <= pos <= limit and 0 <= size <= limit-pos, 'Truncated inventory record')

    def name(pos, allow_zero=False):
        need(pos, 2)
        index = struct.unpack_from('<H', data, pos)[0]
        check((0 if allow_zero else 1) <= index < len(names), 'Invalid inventory name index')
        return names[index]

    need(start, 6)
    next_id, count = struct.unpack_from('<HH', data, start+2)
    check(count <= min(next_id, 10000), 'Unsupported inventory count')
    pos, items, ids = start+6, [], set()
    for index in range(count):
        item_start = pos
        need(pos, 24)
        item_name = name(pos)
        flags = struct.unpack_from('<I', data, pos+2)[0]
        fixed = data[pos+6:pos+13].hex()
        dyes = [name(pos+13, True), name(pos+15, True)]
        quantity = struct.unpack_from('<H', data, pos+17)[0]
        durability = struct.unpack_from('<f', data, pos+19)[0]
        attribute_count = data[pos+23]
        check(quantity > 0 and attribute_count <= 32 and math.isfinite(durability),
                'Unsupported item quantity, attributes or durability')
        pos += 24
        attributes = []
        for _ in range(attribute_count):
            need(pos, 7)
            attributes.append({'name': name(pos), 'raw_value': data[pos+2:pos+6].hex(),
                               'type': data[pos+6]})
            pos += 7
        need(pos, 4)
        unique_id = int.from_bytes(data[pos:pos+3], 'little')
        tag_count = data[pos+3]
        check(0 < unique_id <= next_id and unique_id not in ids and tag_count <= 128,
                'Unsupported item ID or tag count')
        ids.add(unique_id)
        pos += 4
        tags = []
        for _ in range(tag_count):
            tags.append(name(pos))
            pos += 2
        mounted_slot = None
        if flags & 0x200000:
            mounted_slot = name(pos)
            pos += 2
        extra_offset = pos
        need(pos, extra_size)
        extra = data[pos:pos+extra_size]
        if extra != bytes(extra_size):
            raise _UnsupportedInventoryLayout('Nonzero inventory extension is unsupported')
        pos += extra_size
        items.append({'index': index, 'offset': item_start, 'end': pos, 'name': item_name,
                      'quantity': quantity, 'unique_id': unique_id, 'flags': flags,
                      'durability': durability, 'attributes': attributes, 'tags': tags,
                      'mounted_slot': mounted_slot, 'extra_offset': extra_offset,
                      'extra_size': extra_size, 'extra_hex': extra.hex(),
                      'raw_prefix_fields': fixed, 'dye_names': dyes})
    need(pos, 5)
    check(data[pos:pos+5] == b'\x01\0\0\0\0', 'Unsupported inventory terminal marker')
    return {'offset': start, 'item_start': start+6, 'item_end': pos, 'end': pos+5,
            'next_id': next_id, 'item_count': count, 'items': items}


def scan_inventories(data, extra_size):
    """Scan verified serializer regions; recognized unsupported records fail closed."""
    require(extra_size in (0, 2), 'Only observed inventory extension sizes are supported')
    _, nm, rb, names, _, entries = parse_meta(data)
    require(names.count('CInventoryComponent') == 1, 'Missing or ambiguous inventory class')
    index = names.index('CInventoryComponent')
    owners = sorted((offset, offset+length) for offset, length in entries
                    if data[offset:offset+2] == b'SS')
    starts, owner_ends, owner_starts = [], [], []
    maximum, maximum_start = 0, 0
    for lo, hi in owners:
        starts.append(lo)
        if hi > maximum:
            maximum, maximum_start = hi, lo
        owner_ends.append(maximum)
        owner_starts.append(maximum_start)
    inventories, rejected, legacy = [], [], []
    pos, last_end, limit = 3100, 0, min(nm, rb)
    needle = struct.pack('<H', index)
    while True:
        offset = data.find(needle, pos, limit)
        if offset < 0:
            break
        pos = offset+2
        if offset < last_end:
            continue
        owner = bisect_right(starts, offset)-1
        if owner < 0 or offset >= owner_ends[owner]:
            rejected.append({'offset': offset, 'reason': 'Outside native serializer'})
            continue
        owner_start = owner_starts[owner]
        serializer_start = owner_start+6
        nested_start = data.rfind(b'SXAP', serializer_start, offset)
        if nested_start >= serializer_start+8 and data[nested_start-8:nested_start-4] == b'ROTS':
            nested_size = struct.unpack_from('<I', data, nested_start-4)[0]
            nested_end = nested_start+nested_size
            if offset < nested_end <= owner_ends[owner] and data[nested_end:nested_end+4] == b'STOR':
                serializer_start = nested_start
        if data[serializer_start:serializer_start+4] == b'SXAP':
            version = struct.unpack_from('<III', data, serializer_start+4)
            if extra_size == 0 and version in ((57, 10, 162), (57, 11, 162)):
                legacy.append({'offset': offset, 'serializer_version': list(version)})
                continue
        known_prefix = offset >= 5 and data[offset-4:offset] in COMPONENT_HASHES
        try:
            inventory = _parse_inventory(data, offset, names, extra_size, owner_ends[owner])
        except ValueError as exc:
            if known_prefix or isinstance(exc, _UnsupportedInventoryLayout):
                raise ValueError(f'Unsupported inventory at {offset:#x}: {exc}') from exc
            rejected.append({'offset': offset, 'reason': str(exc)})
            continue
        require(known_prefix, f'Unrecognized inventory component hash at {offset:#x}')
        inventory['prefix_hex'] = data[offset-5:offset].hex()
        inventories.append(inventory)
        last_end = inventory['end']
    ranges = [[item['extra_offset'], item['extra_offset']+extra_size]
              for inv in inventories for item in inv['items'] if extra_size]
    require(all(a[1] <= b[0] for a, b in zip(ranges, ranges[1:])), 'Overlapping inventory records')
    return {'inventory_class_index': index, 'inventories': inventories, 'removal_ranges': ranges,
            'inventory_count': len(inventories), 'item_count': sum(i['item_count'] for i in inventories),
            'rejected_occurrences': rejected, 'skipped_legacy_occurrences': legacy}


def find_player_inventory(inventories):
    """Require one inventory with both observed Geralt body-item names."""
    matches = []
    for inv in inventories:
        names = {item['name'] for item in inv['items']}
        if 'Body torso medalion' in names and any(n.startswith('Body underwear ') for n in names):
            matches.append(inv)
    require(len(matches) == 1, 'Expected one unambiguous Geralt inventory signature')
    return matches[0]


def _compare_items(before, after):
    old = {i['unique_id']: i for i in before['items']}
    new = {i['unique_id']: i for i in after['items']}
    missing = [old[k] for k in sorted(old.keys()-new.keys())]
    added = [new[k] for k in sorted(new.keys()-old.keys())]
    required, additional, durability = [], [], []
    identity_fields = ('name', 'quantity', 'mounted_slot')
    extra_fields = ('flags', 'attributes', 'tags', 'raw_prefix_fields', 'dye_names')
    for key in sorted(old.keys() & new.keys()):
        for field in identity_fields + extra_fields + ('durability',):
            a, b = old[key][field], new[key][field]
            if a == b:
                continue
            change = {'unique_id': key, 'original_name': old[key]['name'],
                      'field': field, 'before': a, 'after': b}
            if field == 'durability':
                change['delta'] = b-a
                durability.append(change)
            elif field in identity_fields:
                required.append(change)
            else:
                additional.append(change)
    old_totals, new_totals = Counter(), Counter()
    for item in old.values():
        old_totals[item['name']] += item['quantity']
    for item in new.values():
        new_totals[item['name']] += item['quantity']
    total_changes = [{'name': name, 'before': old_totals[name], 'after': new_totals[name]}
                     for name in sorted(old_totals.keys() | new_totals.keys())
                     if old_totals[name] != new_totals[name]]
    # Do not silently erase identity differences: pair only unique, equivalent
    # records and retain both IDs plus the independently changing low flag bits.
    replacements, unmatched_missing, unmatched_added = [], [], list(added)
    fields = ('name', 'quantity', 'mounted_slot', 'attributes', 'tags', 'raw_prefix_fields', 'dye_names')
    for item in missing:
        candidates = [n for n in unmatched_added if all(item[k] == n[k] for k in fields)
                      and item['flags'] >> 16 == n['flags'] >> 16]
        if len(candidates) != 1:
            unmatched_missing.append(item)
            continue
        replacement = candidates[0]
        unmatched_added.remove(replacement)
        replacements.append({'name': item['name'], 'quantity': item['quantity'],
                             'slot': item['mounted_slot'], 'original_id': item['unique_id'],
                             'native_id': replacement['unique_id'], 'original_flags': item['flags'],
                             'native_flags': replacement['flags']})
        if item['durability'] != replacement['durability']:
            durability.append({'unique_id': item['unique_id'], 'native_id': replacement['unique_id'],
                               'original_name': item['name'], 'field': 'durability',
                               'before': item['durability'], 'after': replacement['durability'],
                               'delta': replacement['durability']-item['durability']})
    strict = not (missing or added or required or total_changes)
    equivalent = not (unmatched_missing or unmatched_added or required or total_changes)
    return {
        'original_count': len(old), 'native_count': len(new),
        'original_next_id': before['next_id'], 'native_next_id': after['next_id'],
        'identity_quantity_equipment_preserved': strict,
        'content_quantity_equipment_preserved_with_id_reassignments': equivalent,
        'all_semantic_fields_preserved_except_durability': strict and not additional,
        'missing_items': missing, 'added_items': added, 'required_field_changes': required,
        'quantity_totals_changes': total_changes, 'additional_field_changes': additional,
        'durability_changes': durability, 'content_equivalent_items_with_new_ids': replacements,
        'unmatched_missing_items': unmatched_missing, 'unmatched_added_items': unmatched_added,
        'currencies': {name: {'before': old_totals[name], 'after': new_totals[name]}
                       for name in ('Crowns', 'Orens', 'Florens')},
    }


def audit_inventory(original, native):
    """Report byte-derived state comparisons, never assert in-game compatibility."""
    def player(data):
        parse_meta(data)
        version = struct.unpack_from('<III', data, 3088)
        require(version in (SOURCE_VERSION, TARGET_VERSION), 'Unsupported inventory save version')
        extra = 2 if version == SOURCE_VERSION else 0
        return find_player_inventory(scan_inventories(data, extra)['inventories'])
    return _compare_items(player(original), player(native))


def prepare_inventory(data):
    """Remove the observed empty extensions and relocate; leave all versions intact."""
    parse_meta(data)
    require(struct.unpack_from('<III', data, 3088) == SOURCE_VERSION, 'Unsupported source save profile')
    original = scan_inventories(data, 2)
    find_player_inventory(original['inventories'])
    require(bool(original['removal_ranges']), 'No inventory extensions to convert')
    from .relocate import relocate_inventory_deletions
    converted, report = relocate_inventory_deletions(data, original['removal_ranges'])
    checked = scan_inventories(converted, 0)
    require(len(checked['inventories']) == len(original['inventories']), 'Inventory count changed')
    for before, after in zip(original['inventories'], checked['inventories']):
        comparison = _compare_items(before, after)
        require(comparison['all_semantic_fields_preserved_except_durability']
                and not comparison['durability_changes'], 'Inventory contents changed during relocation')
    report.update({'inventory_count': original['inventory_count'], 'item_count': original['item_count'],
                   'versions_unchanged': True, 'runtime_validation': 'NOT_PERFORMED'})
    return converted, report
