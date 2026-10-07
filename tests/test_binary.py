"""Synthetic binary fixtures only; no game saves or private player data."""
import importlib
import importlib.util
import struct
import unittest


def api(module):
    name = 'w3save.' + module
    if importlib.util.find_spec(name) is None:
        raise AssertionError('Binary API has not been implemented: ' + name)
    return importlib.import_module(name)


NAMES = ['', 'entity', 'version', 'Int32', 'CInventoryComponent',
         'Body underwear 01', 'Body torso medalion', 'Crowns',
         'Dye Default', 'dye_default', 'inventory_slot', 'array:2,0,Uint8']


def item(name=7, item_id=3, quantity=17, extra=b'\0\0', mounted=False, flags_low=3):
    flags = 0x210000 if mounted else 0x10000
    result = struct.pack('<HI', name, flags | flags_low)
    result += b'\x01' + bytes(6) + struct.pack('<HHHfB', 8, 9, quantity, 100.0, 0)
    result += item_id.to_bytes(3, 'little') + b'\0'
    if mounted:
        result += struct.pack('<H', 10)
    return result + extra


def fixture(extra=b'\0\0', version=(66, 29, 164), body_items=None, extra_blob=b''):
    if body_items is None:
        body_items = [item(5, 1, 1, extra), item(6, 2, 1, extra), item(extra=extra)]
    ids = [int.from_bytes(i[24:27], 'little') for i in body_items]
    inventory = b'\0\x0c\x58\x6a\x71' + struct.pack('<HHH', 4, max(ids, default=0), len(body_items))
    inventory += b''.join(body_items) + b'\x01\0\0\0\0'
    block = b'BLCK' + struct.pack('<HI', 1, len(inventory)) + inventory + extra_blob
    serialized = b'SXAP' + struct.pack('<III', *version) + block
    ss = b'SS' + struct.pack('<I', len(serialized)) + serialized
    prefix = bytearray(3084)
    prefix[:8] = b'SNFHFZLC'
    struct.pack_into('<II', prefix, 8, 1, 3084)
    data = prefix + b'SAV3' + struct.pack('<III', *version)
    root = len(data)
    data += b'BS\x01\0' + ss
    ss_offset = root+4
    nm = len(data)
    data += b'NMMANU' + struct.pack('<II', len(NAMES)-1, 0)
    for name in NAMES[1:]:
        encoded = name.encode()
        data += bytes([len(encoded)]) + encoded
    rb = len(data)
    data += b'RB' + struct.pack('<IHI', 1, 1, root)
    data += struct.pack('<II', nm, rb) + b'SC'
    vt = len(data)
    entries = [(ss_offset, len(ss)), (root, len(ss)+4)]
    data += struct.pack('<I', len(entries))
    for offset, length in entries:
        data += struct.pack('<II', offset, length)
    data += struct.pack('<I', vt) + b'SE'
    return bytes(data), {'nm': nm, 'rb': rb, 'vt': vt, 'ss': ss_offset,
                         'inventory': ss_offset+6+16+10+5,
                         'block': ss_offset+6+16}


class ContainerTests(unittest.TestCase):
    def test_roundtrip_preserves_full_payload_and_supports_multiple_chunks(self):
        module = api('container')
        data, _ = fixture(extra_blob=b'z' * 1_100_000)
        encoded = module.encode_save(data)
        decoded = module.decode_save(encoded)
        self.assertEqual(decoded[3084:], data[3084:])
        self.assertEqual(struct.unpack_from('<I', encoded, 8)[0], 2)

    def test_truncated_chunk_is_rejected(self):
        module = api('container')
        encoded = module.encode_save(fixture()[0])
        with self.assertRaises(ValueError):
            module.decode_save(encoded[:-1])

    def test_claimed_unbounded_decompression_is_rejected(self):
        module = api('container')
        encoded = bytearray(module.encode_save(fixture()[0]))
        struct.pack_into('<I', encoded, 20, 0xffffffff)
        with self.assertRaises(ValueError):
            module.decode_save(bytes(encoded))

    def test_invalid_chain_offset_and_trailing_bytes_are_rejected(self):
        module = api('container')
        encoded = bytearray(module.encode_save(fixture()[0]))
        struct.pack_into('<I', encoded, 24, 123)
        with self.assertRaises(ValueError):
            module.decode_save(bytes(encoded))
        with self.assertRaises(ValueError):
            module.decode_save(module.encode_save(fixture()[0])+b'extra')


class MetadataTests(unittest.TestCase):
    def test_name_table_variable_is_valid_metadata_not_payload(self):
        data, loc = fixture()
        mutable = bytearray(data[:-6])
        struct.pack_into('<I', mutable, loc['vt'], 3)
        mutable += struct.pack('<II', loc['nm']+2, loc['rb']-loc['nm']-2) + data[-6:]
        entries = api('metadata').parse_meta(bytes(mutable))[-1]
        self.assertEqual(entries[-1], (loc['nm']+2, loc['rb']-loc['nm']-2))

    def test_metadata_returns_actual_root_and_variable_ranges(self):
        data, loc = fixture()
        vt, nm, rb, names, roots, entries = api('metadata').parse_meta(data)
        self.assertEqual((vt, nm, rb), (loc['vt'], loc['nm'], loc['rb']))
        self.assertEqual(names[7], 'Crowns')
        self.assertEqual(roots, [(1, 3100)])
        self.assertEqual(entries[0][0], 3104)

    def test_invalid_footer_and_variable_pointers_are_rejected(self):
        module = api('metadata')
        data, loc = fixture()
        bad = bytearray(data)
        struct.pack_into('<I', bad, len(bad)-6, len(bad)+10)
        with self.assertRaises(ValueError):
            module.parse_meta(bytes(bad))
        bad = bytearray(data)
        struct.pack_into('<I', bad, loc['vt']+4, loc['nm']+1)
        with self.assertRaises(ValueError):
            module.parse_meta(bytes(bad))


class InventoryTests(unittest.TestCase):
    def test_old_serializer_inventory_is_reported_and_not_misparsed_as_current(self):
        data, loc = fixture(extra=b'\x01\0', version=(64, 27, 163))
        changed = bytearray(data)
        struct.pack_into('<III', changed, loc['ss']+10, 57, 11, 162)
        result = api('inventory').scan_inventories(bytes(changed), 0)
        self.assertEqual(result['inventory_count'], 0)
        self.assertEqual(len(result['skipped_legacy_occurrences']), 1)

    def test_nested_legacy_serializer_is_not_misparsed_as_current(self):
        nested, loc = fixture(extra=b'\x01\0', version=(57, 10, 162))
        size = struct.unpack_from('<I', nested, loc['ss']+2)[0]
        payload = nested[loc['ss']+6:loc['ss']+6+size]
        wrapper = b'ROTS'+struct.pack('<I', len(payload))+payload+b'STOR'
        data, _ = fixture(extra=b'', version=(64, 27, 163), extra_blob=wrapper)
        result = api('inventory').scan_inventories(data, 0)
        self.assertEqual(result['inventory_count'], 1)
        self.assertEqual(len(result['skipped_legacy_occurrences']), 1)

    def test_inventory_decodes_semantic_player_and_item_contents(self):
        module = api('inventory')
        result = module.scan_inventories(fixture()[0], 2)
        player = module.find_player_inventory(result['inventories'])
        self.assertEqual(result['item_count'], 3)
        self.assertEqual(len(result['removal_ranges']), 3)
        self.assertEqual(player['items'][2]['quantity'], 17)
        self.assertEqual(player['items'][2]['unique_id'], 3)

    def test_recognized_component_with_nonzero_extension_fails_closed(self):
        data, _ = fixture(extra=b'\x01\0')
        with self.assertRaises(ValueError):
            api('inventory').scan_inventories(data, 2)

    def test_unknown_component_with_decoded_item_and_bad_extension_fails_closed(self):
        unknown = b'\0\x11\x22\x33\x44' + struct.pack('<HHH', 4, 3, 1)
        unknown += item(extra=b'\x01\0') + b'\x01\0\0\0\0'
        data, _ = fixture(extra_blob=unknown)
        with self.assertRaises(ValueError):
            api('inventory').prepare_inventory(data)

    def test_class_index_inside_item_is_not_another_inventory(self):
        # Low flag bytes contain the same two-byte class index as the component.
        data, _ = fixture(body_items=[item(5, 1, 1), item(6, 2, 1), item(flags_low=4)])
        result = api('inventory').scan_inventories(data, 2)
        self.assertEqual(result['inventory_count'], 1)
        self.assertEqual(result['item_count'], 3)

    def test_player_identification_rejects_missing_and_duplicate_signatures(self):
        module = api('inventory')
        values = module.scan_inventories(fixture()[0], 2)['inventories']
        with self.assertRaises(ValueError):
            module.find_player_inventory([])
        with self.assertRaises(ValueError):
            module.find_player_inventory(values+values)

    def test_audit_reports_equivalent_regenerated_ids_without_hiding_item_loss(self):
        module = api('inventory')
        original, _ = fixture()
        native, _ = fixture(extra=b'', version=(64, 27, 163), body_items=[
            item(5, 1, 1, b''), item(6, 2, 1, b''), item(item_id=4, extra=b'', flags_low=9)])
        audit = module.audit_inventory(original, native)
        self.assertTrue(audit['content_quantity_equipment_preserved_with_id_reassignments'])
        self.assertFalse(audit['identity_quantity_equipment_preserved'])
        self.assertEqual(len(audit['content_equivalent_items_with_new_ids']), 1)
        lost, _ = fixture(extra=b'', version=(64, 27, 163), body_items=[
            item(5, 1, 1, b''), item(6, 2, 1, b'')])
        self.assertFalse(module.audit_inventory(original, lost)['content_quantity_equipment_preserved_with_id_reassignments'])


class RelocationTests(unittest.TestCase):
    def test_unsupported_enclosing_byte_arrays_are_refused_before_relocation(self):
        module = api('inventory')
        for marker in (b'', b'PORP', b'AVAL'):
            with self.subTest(marker=marker):
                raw, loc = fixture()
                position = loc['block']+10
                payload = raw[position:loc['nm']]
                length = len(payload)+(4 if marker else 8)
                header = marker+struct.pack('<HHII', 10, 11, length, len(payload))
                delta = len(header)
                changed = bytearray(raw[:position]+header+raw[position:])
                struct.pack_into('<I', changed, loc['block']+6, len(payload)+delta)
                struct.pack_into('<I', changed, loc['ss']+2,
                                 struct.unpack_from('<I', raw, loc['ss']+2)[0]+delta)
                vt, nm, rb, _, _, entries = api('metadata').parse_meta(raw)
                struct.pack_into('<II', changed, vt+delta-10, nm+delta, rb+delta)
                for index, (offset, size) in enumerate(entries):
                    struct.pack_into('<II', changed, vt+delta+4+8*index, offset, size+delta)
                struct.pack_into('<I', changed, len(changed)-6, vt+delta)
                with self.assertRaises(ValueError):
                    module.prepare_inventory(bytes(changed))

    def test_prepare_relocates_all_pointers_sizes_and_keeps_versions(self):
        data, loc = fixture()
        changed, report = api('inventory').prepare_inventory(data)
        self.assertEqual(len(changed), len(data)-6)
        self.assertEqual(changed[3084:3100], data[3084:3100])
        self.assertEqual(changed[loc['ss']+6:loc['ss']+22], data[loc['ss']+6:loc['ss']+22])
        self.assertEqual(struct.unpack_from('<I', changed, loc['ss']+2)[0],
                         struct.unpack_from('<I', data, loc['ss']+2)[0]-6)
        self.assertEqual(struct.unpack_from('<I', changed, loc['block']+6)[0],
                         struct.unpack_from('<I', data, loc['block']+6)[0]-6)
        new_meta = api('metadata').parse_meta(changed)
        self.assertEqual(new_meta[:3], (loc['vt']-6, loc['nm']-6, loc['rb']-6))
        self.assertEqual(api('inventory').scan_inventories(changed, 0)['item_count'], 3)
        self.assertEqual(report['removed_bytes'], 6)

    def test_overlapping_or_nonzero_deletion_ranges_are_rejected(self):
        data, _ = fixture()
        ranges = api('inventory').scan_inventories(data, 2)['removal_ranges']
        module = api('relocate')
        with self.assertRaises(ValueError):
            module.relocate_inventory_deletions(data, [ranges[0], ranges[0]])
        with self.assertRaises(ValueError):
            module.relocate_inventory_deletions(data, [[3084, 3086]])

    def test_unknown_source_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            api('inventory').prepare_inventory(fixture(version=(65, 28, 164))[0])


if __name__ == '__main__':
    unittest.main()
