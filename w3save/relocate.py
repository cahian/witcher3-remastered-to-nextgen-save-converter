"""Relocate validated two-byte inventory deletions without changing save versions."""
from bisect import bisect_right
from collections import Counter
import struct

from .metadata import parse_meta, require


def relocate_inventory_deletions(data, intervals):
    vt, nm, rb, names, roots, entries = parse_meta(data)
    intervals = sorted(intervals)
    require(bool(intervals), 'No inventory deletions provided')
    previous, starts, ends, prefix = 0, [], [], [0]
    for interval in intervals:
        require(len(interval) == 2 and all(isinstance(v, int) for v in interval), 'Invalid deletion interval')
        lo, hi = interval
        require(previous <= lo < hi < min(nm, rb) and hi-lo == 2, 'Overlapping or invalid deletion intervals')
        require(data[lo:hi] == b'\0\0', 'Only empty two-byte extensions may be removed')
        starts.append(lo)
        ends.append(hi)
        prefix.append(prefix[-1]+2)
        previous = hi

    def shift(position):
        index = bisect_right(starts, position)-1
        require(index < 0 or not starts[index] < position < ends[index], 'Pointer falls inside deleted data')
        return position-prefix[bisect_right(ends, position)]

    def removed(lo, hi):
        return hi-lo-(shift(hi)-shift(lo))

    # A byte-array property has its own element count in addition to enclosing
    # serializer sizes. This narrow converter does not rewrite those parents.
    # Detect both unmarked struct properties and marked PORP/AVAL properties.
    payload_end = min(nm, rb)
    for type_index, type_name in enumerate(names):
        if type_name != 'array:2,0,Uint8':
            continue
        needle, cursor = struct.pack('<H', type_index), 3102
        while True:
            found = data.find(needle, cursor, payload_end)
            if found < 0:
                break
            cursor, offset = found+2, found-2
            if offset < 3100 or offset+12 > payload_end:
                continue
            name_index = struct.unpack_from('<H', data, offset)[0]
            if not 0 < name_index < len(names):
                continue
            length, count = struct.unpack_from('<II', data, offset+4)
            marked = data[offset-4:offset] in (b'PORP', b'AVAL')
            if length != count+(4 if marked else 8):
                continue
            start, end = offset+12, offset+12+count
            if count and end <= payload_end and removed(start, end):
                raise ValueError(f'Unsupported enclosing byte-array property at {offset:#x}')

    patches, kinds = {}, Counter()

    def patch32(offset, before, after, kind):
        require(shift(offset+4)-shift(offset) == 4, 'A size field overlaps deleted data')
        require(struct.unpack_from('<I', data, offset)[0] == before and 0 <= after <= 0xffffffff,
                'Invalid serialized length adjustment')
        require(offset not in patches or patches[offset] == after, 'Conflicting length patches')
        if offset not in patches:
            patches[offset] = after
            kinds[kind] += 1

    affected = []
    covered_intervals = set()
    for offset, length in entries:
        loss = removed(offset, offset+length)
        if not loss:
            continue
        tag = data[offset:offset+2]
        affected.append({'offset': offset, 'length': length, 'tag': tag.decode('ascii', 'replace'), 'removed': loss})
        if tag == b'SS':
            inner = struct.unpack_from('<I', data, offset+2)[0]
            require(inner == length-6, 'Native serializer size disagrees with its variable entry')
            patch32(offset+2, inner, inner-loss, 'SS_size')
            first, last = bisect_right(ends, offset), bisect_right(ends, offset+length)
            covered_intervals.update(range(first, last))
        elif tag != b'BS':
            raise ValueError(f'Unsupported affected global block at {offset:#x}: {tag!r}')
    require(len(covered_intervals) == len(intervals), 'Inventory deletion outside a native serializer')

    wrappers = []
    for marker, header, size_at in ((b'BLCK', 10, 6), (b'AVAL', 12, 8),
                                  (b'PORP', 12, 8), (b'ROTS', 8, 4)):
        cursor = 3100
        while True:
            offset = data.find(marker, cursor, min(nm, rb))
            if offset < 0:
                break
            cursor = offset+1
            if offset+header > min(nm, rb):
                continue
            length = struct.unpack_from('<I', data, offset+size_at)[0]
            end = offset+header+length
            if not length or end > min(nm, rb):
                continue
            if marker == b'ROTS':
                if data[end:end+4] != b'STOR':
                    continue
            else:
                name = struct.unpack_from('<H', data, offset+4)[0]
                if not 0 < name < len(names):
                    continue
                if marker != b'BLCK':
                    type_index = struct.unpack_from('<H', data, offset+6)[0]
                    if not 0 < type_index < len(names):
                        continue
            loss = removed(offset+header, end)
            if loss:
                patch32(offset+size_at, length, length-loss, marker.decode()+'_size')
                wrappers.append({'tag': marker.decode(), 'offset': offset, 'before': length, 'removed': loss})

    chunks, cursor = [], 0
    for lo, hi in intervals:
        chunks.append(data[cursor:lo])
        cursor = hi
    chunks.append(data[cursor:])
    result = bytearray(b''.join(chunks))
    for offset, value in patches.items():
        struct.pack_into('<I', result, shift(offset), value)
    for index, (_, offset) in enumerate(roots):
        struct.pack_into('<I', result, shift(rb)+6+6*index+2, shift(offset))
    for index, (offset, length) in enumerate(entries):
        struct.pack_into('<II', result, shift(vt)+4+8*index, shift(offset), shift(offset+length)-shift(offset))
    struct.pack_into('<II', result, shift(vt)-10, shift(nm), shift(rb))
    struct.pack_into('<I', result, len(result)-6, shift(vt))
    checked = parse_meta(result)
    require(checked[:3] == (shift(vt), shift(nm), shift(rb)) and checked[3] == names,
            'Metadata changed unexpectedly during relocation')
    require(len(result) == len(data)-prefix[-1], 'Unexpected relocated image length')
    for (offset, length), (new_offset, new_length) in zip(entries, checked[5]):
        require(new_offset == shift(offset) and new_length == length-removed(offset, offset+length),
                'Relocated variable range mismatch')
        if length == new_length:
            require(result[new_offset:new_offset+new_length] == data[offset:offset+length],
                    'Unchanged variable contents were modified')
    return bytes(result), {
        'removed_bytes': prefix[-1], 'affected_entries': affected,
        'inner_size_patches': dict(kinds), 'serializer_wrappers': wrappers,
        'old_pointers': {'NM': nm, 'RB': rb, 'SC': vt},
        'new_pointers': {'NM': shift(nm), 'RB': shift(rb), 'SC': shift(vt)},
    }
