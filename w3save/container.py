"""Bounded reader/writer for the observed SNFHFZLC LZ4 save container."""
import struct

import lz4.block

PREFIX_SIZE = 3084
CHUNK_SIZE = 1024 * 1024
MAX_CHUNKS = (PREFIX_SIZE-16)//12
MAX_RAW_SIZE = MAX_CHUNKS * CHUNK_SIZE


def _header(data):
    if len(data) < PREFIX_SIZE or data[:8] != b'SNFHFZLC':
        raise ValueError('Unsupported or truncated SNFHFZLC container')
    count, start = struct.unpack_from('<II', data, 8)
    if start != PREFIX_SIZE or not 1 <= count <= MAX_CHUNKS:
        raise ValueError('Unsupported container prefix or chunk count')
    return count


def decode_save(data: bytes) -> bytes:
    """Decode a compressed save; allocations are bounded before LZ4 is called."""
    count = _header(data)
    if len(data) > PREFIX_SIZE + MAX_RAW_SIZE + MAX_CHUNKS * 8192:
        raise ValueError('Compressed save exceeds supported size limit')
    position, total = PREFIX_SIZE, 0
    descriptors = []
    for index in range(count):
        compressed_size, raw_size, end = struct.unpack_from('<III', data, 16+12*index)
        if not 1 <= raw_size <= CHUNK_SIZE:
            raise ValueError('Chunk decompression size exceeds supported bound')
        if not 1 <= compressed_size <= raw_size + raw_size//255 + 32:
            raise ValueError('Invalid compressed chunk length')
        stop = position+compressed_size
        if stop > len(data):
            raise ValueError('Truncated compressed chunk')
        expected_end = stop if index+1 < count else 0
        if end != expected_end:
            raise ValueError('Invalid chunk chain offset')
        total += raw_size
        if total > MAX_RAW_SIZE:
            raise ValueError('Decompressed save exceeds supported bound')
        descriptors.append((position, stop, raw_size))
        position = stop
    if position != len(data):
        raise ValueError('Unexpected trailing container data')
    chunks = [data[:PREFIX_SIZE]]
    for start, stop, raw_size in descriptors:
        encoded = data[start:stop]
        if len(encoded) == raw_size:
            decoded = encoded
        else:
            try:
                decoded = lz4.block.decompress(encoded, uncompressed_size=raw_size)
            except (lz4.block.LZ4BlockError, OverflowError) as exc:
                raise ValueError('Invalid LZ4 chunk') from exc
        if len(decoded) != raw_size:
            raise ValueError('Decoded chunk length mismatch')
        chunks.append(decoded)
    result = b''.join(chunks)
    if result[PREFIX_SIZE:PREFIX_SIZE+4] != b'SAV3' or result[-2:] != b'SE':
        raise ValueError('Decoded data is not a supported SAV3 image')
    return result


def encode_save(data: bytes) -> bytes:
    """Encode a full decompressed image; does not change gameplay versions."""
    _header(data)
    if data[PREFIX_SIZE:PREFIX_SIZE+4] != b'SAV3' or data[-2:] != b'SE':
        raise ValueError('Expected a full decompressed SAV3 image')
    payload = data[PREFIX_SIZE:]
    if not 1 <= len(payload) <= MAX_RAW_SIZE:
        raise ValueError('Decompressed save exceeds supported bound')
    count = (len(payload)+CHUNK_SIZE-1)//CHUNK_SIZE
    result = bytearray(data[:PREFIX_SIZE])
    result[16:] = bytes(PREFIX_SIZE-16)
    struct.pack_into('<II', result, 8, count, PREFIX_SIZE)
    for index in range(count):
        raw = payload[index*CHUNK_SIZE:(index+1)*CHUNK_SIZE]
        compressed = lz4.block.compress(raw, mode='high_compression', store_size=False)
        encoded = compressed if len(compressed) < len(raw) else raw
        result.extend(encoded)
        struct.pack_into('<III', result, 16+12*index, len(encoded), len(raw),
                         len(result) if index+1 < count else 0)
    return bytes(result)
