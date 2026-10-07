"""Explicit, no-clobber commands for the documented conversion workflow."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import sys

from . import __version__

SOURCE_VERSION = (66, 29, 164)
TARGET_VERSION = (64, 27, 163)
MAX_INPUT_BYTES = 256 * 1024 * 1024


def read_input(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError('input exceeds the 256 MiB safety limit')
    return data


def require_new_path(path):
    if os.path.lexists(path):
        raise ValueError('output already exists; choose a new path')


def write_new(path, data):
    """Exclusive creation also rejects an existing or dangling symlink."""
    with Path(path).open('xb') as stream:
        stream.write(data)


def version(raw):
    if len(raw) < 32 or raw[:8] != b'SNFHFZLC':
        raise ValueError('unrecognized decompressed save container')
    start = struct.unpack_from('<I', raw, 12)[0]
    if start + 16 > len(raw) or raw[start:start+4] != b'SAV3':
        raise ValueError('missing SAV3 header')
    return struct.unpack_from('<III', raw, start+4)


def nested_versions(raw):
    versions = Counter()
    start = 0
    while True:
        start = raw.find(b'SXAP', start)
        if start < 0:
            return {','.join(map(str, k)): v for k, v in sorted(versions.items())}
        if start + 16 > len(raw):
            raise ValueError('truncated nested SXAP header')
        versions[struct.unpack_from('<III', raw, start+4)] += 1
        start += 16


def rewrite_versions(raw):
    if version(raw) != SOURCE_VERSION:
        raise ValueError(f'prepare requires source version {SOURCE_VERSION}')
    versions = nested_versions(raw)
    if not versions or set(versions) != {'66,29,164'}:
        raise ValueError('mixed or unknown nested versions are outside the tested profile')
    result = bytearray(raw)
    start = struct.unpack_from('<I', result, 12)[0]
    struct.pack_into('<III', result, start+4, *TARGET_VERSION)
    needle = b'SXAP' + struct.pack('<III', *SOURCE_VERSION)
    replacement = b'SXAP' + struct.pack('<III', *TARGET_VERSION)
    return bytes(result).replace(needle, replacement), sum(versions.values())


def compare_facts(before, after):
    """Report all fact differences without interpreting their gameplay meaning."""
    missing = {name: before[name] for name in sorted(before.keys()-after.keys())}
    added = {name: after[name] for name in sorted(after.keys()-before.keys())}
    changed = {name: {'before': before[name], 'after': after[name]}
               for name in sorted(before.keys() & after.keys()) if before[name] != after[name]}
    available = bool(before) and bool(after)
    return {'original_count': len(before), 'candidate_count': len(after),
            'data_available': available,
            'all_original_records_unchanged': available and not missing and not changed,
            'missing': missing, 'added': added, 'changed': changed}


def build_parser():
    parser = argparse.ArgumentParser(
        description='Experimental Witcher 3 Remastered 5.0 to Next-Gen 4.04 save toolkit. '
                    'Prepared files require native-game validation; see README for the narrow supported profile.')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='read format, inventory and skill metadata')
    inspect.add_argument('input', type=Path)
    prepare = commands.add_parser('prepare', help='create a guarded inventory/header migration candidate')
    prepare.add_argument('input', type=Path)
    prepare.add_argument('--output', type=Path, required=True)
    mod = commands.add_parser('make-mod', help='generate a temporary mod from your own installed 4.04 script')
    mod.add_argument('--game-script', type=Path, required=True)
    mod.add_argument('--output-dir', type=Path, required=True)
    finalize = commands.add_parser('finalize', help='normalize inactive Ciri from your own native 4.04 reference')
    finalize.add_argument('input', type=Path)
    finalize.add_argument('--reference', type=Path, required=True)
    finalize.add_argument('--output', type=Path, required=True)
    audit = commands.add_parser('audit', help='compare item contents and serialized state; does not run the game')
    audit.add_argument('original', type=Path)
    audit.add_argument('candidate', type=Path)
    return parser


def execute(args):
    if args.command == 'make-mod':
        require_new_path(args.output_dir)
        from .mod import generate_mod
        files = generate_mod(read_input(args.game_script))
        for relative in files:
            p = PurePosixPath(relative)
            if p.is_absolute() or '..' in p.parts or '\\' in relative:
                raise ValueError('invalid generated mod path')
        args.output_dir.mkdir(mode=0o700)
        try:
            for relative, data in files.items():
                path = args.output_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                write_new(path, data)
        except Exception:
            shutil.rmtree(args.output_dir)
            raise
        return {'status': 'TEMPORARY_MOD_GENERATED', 'files': sorted(files),
                'runtime_validated': False}

    if args.command in ('prepare', 'finalize'):
        require_new_path(args.output)
    from .container import decode_save, encode_save
    from .skills import Snapshot, check_migration_profile
    from .inventory import scan_inventories, prepare_inventory, audit_inventory

    if args.command == 'audit':
        original = decode_save(read_input(args.original))
        candidate = decode_save(read_input(args.candidate))
        inventory = audit_inventory(original, candidate)
        source_state = Snapshot.from_bytes(original)
        candidate_state = Snapshot.from_bytes(candidate)
        return {'status': 'BINARY_AUDIT_ONLY', 'runtime_validated': False,
                'source_version': version(original), 'candidate_version': version(candidate),
                'inventory': inventory, 'facts': compare_facts(source_state.facts(), candidate_state.facts()),
                'source_state': source_state.summary(), 'candidate_state': candidate_state.summary()}

    raw = decode_save(read_input(args.input))
    if args.command == 'inspect':
        current = version(raw)
        if current not in (SOURCE_VERSION, TARGET_VERSION):
            raise ValueError(f'unsupported top-level version {current}')
        inventory = scan_inventories(raw, 2 if current == SOURCE_VERSION else 0)
        try:
            profile = check_migration_profile(raw)
        except ValueError as error:
            profile = {'supported_for_prepare': False, 'reason': str(error)}
        return {'status': 'INSPECTED', 'version': current, 'nested_versions': nested_versions(raw),
                'inventory_count': inventory['inventory_count'], 'item_count': inventory['item_count'],
                'migration_profile': profile, 'state': Snapshot.from_bytes(raw).summary(),
                'runtime_validated': False}

    if args.command == 'prepare':
        if version(raw) != SOURCE_VERSION:
            raise ValueError(f'prepare requires source version {SOURCE_VERSION}')
        profile = check_migration_profile(raw)
        converted, report = prepare_inventory(raw)
        converted, changed = rewrite_versions(converted)
        packed = encode_save(converted)
        write_new(args.output, packed)
        return {'status': 'CANDIDATE_REQUIRES_NATIVE_MIGRATION_AND_GAME_TEST',
                'sha256': hashlib.sha256(packed).hexdigest(), 'migration_profile': profile,
                'inventory_conversion': report, 'nested_headers_changed': changed,
                'runtime_validated': False}

    if args.command == 'finalize':
        from .normalize import normalize_ciri
        reference = decode_save(read_input(args.reference))
        converted, report = normalize_ciri(raw, reference)
        packed = encode_save(converted)
        write_new(args.output, packed)
        return {'status': 'FINALIZED_CANDIDATE_REQUIRES_UNMODIFIED_GAME_RELOAD',
                'sha256': hashlib.sha256(packed).hexdigest(), 'ciri_normalization': report,
                'runtime_validated': False}
    raise ValueError('unknown command')


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = execute(args)
    except (ValueError, OSError, UnicodeError, struct.error) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0
