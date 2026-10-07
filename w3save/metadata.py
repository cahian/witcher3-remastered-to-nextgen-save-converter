"""Validate SAV3 name, root and variable tables before interpreting pointers."""
import struct

PREFIX_SIZE = 3084
MAX_IMAGE_SIZE = 256 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_meta(data):
    """Return (variable_table, names_offset, roots_offset, names, roots, entries)."""
    require(PREFIX_SIZE+32 <= len(data) <= MAX_IMAGE_SIZE, 'Invalid decompressed image size')
    require(data[:8] == b'SNFHFZLC' and data[PREFIX_SIZE:PREFIX_SIZE+4] == b'SAV3',
            'Expected a full decompressed SNFHFZLC/SAV3 image')
    require(data[-2:] == b'SE', 'Missing save footer')
    vt = struct.unpack_from('<I', data, len(data)-6)[0]
    require(PREFIX_SIZE+26 <= vt <= len(data)-10, 'Variable table pointer outside image')
    require(data[vt-2:vt] == b'SC', 'Missing variable table marker')
    nm, rb = struct.unpack_from('<II', data, vt-10)
    require(PREFIX_SIZE+16 <= nm <= vt-24, 'Name table pointer outside image')
    require(PREFIX_SIZE+16 <= rb <= vt-16, 'Root table pointer outside image')
    require(data[nm:nm+6] == b'NMMANU' and data[rb:rb+2] == b'RB', 'Invalid metadata marker')
    count = struct.unpack_from('<I', data, nm+6)[0]
    require(0 < count <= 65535, 'Invalid name count')
    names = ['']
    pos = nm+14
    for _ in range(count):
        require(pos < vt-10, 'Truncated name length')
        length = data[pos]
        pos += 1
        require(pos+length <= vt-10, 'Truncated name string')
        try:
            name = data[pos:pos+length].decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('Invalid UTF-8 name') from exc
        names.append(name)
        pos += length
    root_count = struct.unpack_from('<I', data, rb+2)[0]
    root_end = rb+6+6*root_count
    require(root_count <= 65535 and root_end <= vt-10, 'Invalid root table length')
    require(root_end <= nm or rb >= pos, 'Overlapping root and name tables')
    payload_end = min(nm, rb)
    roots = []
    for index in range(root_count):
        name, offset = struct.unpack_from('<HI', data, rb+6+6*index)
        require(0 < name < len(names), 'Invalid root name index')
        require(PREFIX_SIZE+16 <= offset < payload_end, 'Root pointer outside payload')
        roots.append((name, offset))
    entry_count = struct.unpack_from('<I', data, vt)[0]
    require(0 < entry_count <= 2_000_000 and vt+4+8*entry_count == len(data)-6,
            'Invalid variable table length')
    entries = []
    for index in range(entry_count):
        offset, length = struct.unpack_from('<II', data, vt+4+8*index)
        payload_variable = PREFIX_SIZE+16 <= offset < payload_end and 0 < length <= payload_end-offset
        name_variable = (offset == nm+2 and pos <= offset+length <= min(pos+8, vt-10))
        require(payload_variable or name_variable,
                'Variable range outside payload')
        entries.append((offset, length))
    entry_offsets = {offset for offset, _ in entries}
    require(all(offset in entry_offsets for _, offset in roots), 'Root does not refer to a variable')
    return vt, nm, rb, names, roots, entries
