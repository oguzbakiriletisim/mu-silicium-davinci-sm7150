#!/usr/bin/env python3
"""PC-only original GPT/staging checks. Never opens a raw device or deploys."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import uuid
import zlib

# The delivery kit keeps these two scripts together.
sys.path.insert(0, str(Path(__file__).resolve().parent))
canonical = Path(__file__).resolve().parent.parent / 'Windows/davinci'
if not Path(__file__).with_name('prepare_windows.py').exists() and canonical.is_dir():
    sys.path.insert(0, str(canonical))
import prepare_windows as windows


def header(blob, offset, sector, lba, last):
    if offset < 0 or offset + sector > len(blob):
        raise ValueError('GPT header outside supplied backup')
    b = bytearray(blob[offset:offset + sector])
    if b[:8] != b'EFI PART':
        raise ValueError('GPT signature missing at required LBA')
    revision, size, crc, reserved = struct.unpack_from('<4I', b, 8)
    if revision != 0x10000 or not 92 <= size <= sector or reserved:
        raise ValueError('Unsupported GPT header')
    b[16:20] = bytes(4)
    if zlib.crc32(b[:size]) != crc:
        raise ValueError('GPT header CRC mismatch; no repair is performed')
    current, backup, first, end = struct.unpack_from('<4Q', b, 24)
    if current != lba or backup != (last if lba == 1 else 1) or not 1 < first <= end < last:
        raise ValueError('GPT header geometry mismatch')
    disk = str(uuid.UUID(bytes_le=bytes(b[56:72])))
    if uuid.UUID(disk).int == 0:
        raise ValueError('Zero disk GUID')
    entries, count, entry_size, array_crc = struct.unpack_from('<Q3I', b, 72)
    if not 1 <= count <= 4096 or not 128 <= entry_size <= 1024 or entry_size & (entry_size - 1):
        raise ValueError('Unbounded/unsupported GPT array')
    sectors = (count * entry_size + sector - 1) // sector
    if lba == 1:
        if entries < 2 or entries + sectors > first:
            raise ValueError('Primary GPT array overlaps usable area')
    elif entries <= end or entries + sectors > last:
        raise ValueError('Secondary GPT array overlaps usable area/header')
    return dict(disk_guid=disk, first=first, last=end, array_lba=entries,
                count=count, entry_size=entry_size, array_crc=array_crc)


def parse_backups(primary, secondary, sector, disk_bytes):
    if sector not in (512, 4096) or disk_bytes <= 2 * 1024 * 1024 or disk_bytes % sector:
        raise ValueError('Actual sector size and exact whole-LUN byte size are required')
    if len(primary) != 1048576 or len(secondary) != 1048576:
        raise ValueError('Requires exact first/last 1 MiB backups of the SAME LUN')
    last = disk_bytes // sector - 1
    a = header(primary, sector, sector, 1, last)
    b = header(secondary, len(secondary) - sector, sector, last, last)
    for key in ('disk_guid', 'first', 'last', 'count', 'entry_size', 'array_crc'):
        if a[key] != b[key]:
            raise ValueError('Primary/secondary GPT identity mismatch: ' + key)
    total = a['count'] * a['entry_size']
    begin = a['array_lba'] * sector
    end_begin = b['array_lba'] * sector - (disk_bytes - len(secondary))
    if begin + total > len(primary) or end_begin < 0 or end_begin + total > len(secondary):
        raise ValueError('GPT array is not fully contained in backup; acquire a correct existing backup')
    entries = primary[begin:begin + total]
    if entries != secondary[end_begin:end_begin + total] or zlib.crc32(entries) != a['array_crc']:
        raise ValueError('GPT entry array/CRC mismatch; no repair is performed')
    parts, identities, ranges = [], set(), []
    for index in range(a['count']):
        e = entries[index * a['entry_size']:(index + 1) * a['entry_size']]
        if e[:16] == bytes(16):
            continue
        kind = str(uuid.UUID(bytes_le=bytes(e[:16])))
        identity = str(uuid.UUID(bytes_le=bytes(e[16:32])))
        start, end, attributes = struct.unpack_from('<3Q', e, 32)
        if identity in identities or uuid.UUID(identity).int == 0 or not a['first'] <= start <= end <= a['last']:
            raise ValueError('Duplicate/invalid partition GUID or extent')
        if any(start <= other_end and other_start <= end for other_start, other_end in ranges):
            raise ValueError('Overlapping partitions')
        identities.add(identity)
        ranges.append((start, end))
        name = e[56:128].decode('utf-16-le').split('\0', 1)[0]
        parts.append(dict(number=index + 1, guid=identity, type_guid=kind, name=name,
                          first_lba=start, last_lba=end, offset_bytes=start * sector,
                          size_bytes=(end - start + 1) * sector, attributes=attributes,
                          filesystem='UNVERIFIED_FROM_GPT_BACKUPS'))
    return dict(disk_guid=a['disk_guid'], disk_size_bytes=disk_bytes, sector_size=sector,
                primary_and_secondary_crc_valid=True, partitions=parts,
                backups_current_on_phone=False)


def select(layout, disk, win, esp=None):
    if windows.guid(disk) != layout['disk_guid']:
        raise ValueError('Disk GUID does not match the real backup')
    ids = [windows.guid(win)] + ([windows.guid(esp)] if esp else [])
    if len(ids) != len(set(ids)):
        raise ValueError('Windows and ESP must be different partitions')
    result = {}
    for name, identity in zip(('windows', 'esp'), ids):
        found = [p for p in layout['partitions'] if p['guid'] == identity]
        if len(found) != 1:
            raise ValueError('Target partition GUID absent: ' + name)
        result[name] = found[0]
    if result['windows']['name'] != 'win':
        raise ValueError('Selected Windows GUID is not the existing win partition')
    if 'esp' in result and result['esp']['type_guid'] != windows.ESP_TYPE:
        raise ValueError('ESP GUID does not identify an EFI System Partition')
    return result


def drivers(root):
    if root is None:
        return dict(status='MISSING', compatible_boot_start_ufs_verified=False, files=[])
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Driver directory is absent or a link')
    files = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in ('.inf', '.cat', '.sys'):
            continue
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):
            raise ValueError('Driver file escapes directory')
        entry = dict(path=str(p.relative_to(root)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        if p.suffix.lower() == '.sys':
            entry['pe'] = windows.arm64_pe(p)  # Reject x64 rather than treating as a candidate.
        files.append(entry)
    return dict(status='INVENTORIED_ONLY', files=files,
                compatible_boot_start_ufs_verified=False,
                reason='ARM64/INF/CAT presence does not establish SM7150-AA compatibility, catalog membership, boot-start service configuration, ACPI resources or kernel handover.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['gpt', 'check'], nargs='?', default='check')
    parser.add_argument('--staging', type=Path)
    parser.add_argument('--primary-gpt', type=Path, required=True)
    parser.add_argument('--secondary-gpt', type=Path, required=True)
    parser.add_argument('--sector-size', type=int, required=True)
    parser.add_argument('--disk-size-bytes', type=int, required=True)
    parser.add_argument('--disk-guid')
    parser.add_argument('--windows-guid')
    parser.add_argument('--esp-guid')
    parser.add_argument('--drivers', type=Path)
    args = parser.parse_args()
    try:
        layout = parse_backups(args.primary_gpt.read_bytes(), args.secondary_gpt.read_bytes(),
                               args.sector_size, args.disk_size_bytes)
        if args.action == 'gpt':
            print(json.dumps(dict(layout=layout, deployment_allowed=False), indent=2, ensure_ascii=False))
            return 0
        if not args.staging or not args.disk_guid or not args.windows_guid:
            raise ValueError('check requires --staging, --disk-guid and --windows-guid')
        chosen = select(layout, args.disk_guid, args.windows_guid, args.esp_guid)
        report = dict(schema_version=1, device='davinci / SM7150-AA',
                      staging=windows.inspect_staging(args.staging), layout=layout, selected=chosen,
                      drivers=drivers(args.drivers), deployment_allowed=False,
                      blockers=['Live UFS/Block I/O and both GPT copies on the phone must be independently verified.',
                                'win is reported ext4; GPT backups do not prove NTFS or FAT32.',
                                'A PC ESP VHD is not a phone ESP and must not be written as a whole-disk image.',
                                'No verified SM7150-AA ARM64 boot-start UFS driver supplied.',
                                'Default ACPI is incomplete; UFS/PEP/DMA resource contracts are not validated.',
                                'A tested target transfer path and metadata-preserving Windows apply source are missing.'])
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 3  # A valid preflight is deliberately not a deployment authorization.
    except (ValueError, OSError) as error:
        print(json.dumps(dict(deployment_allowed=False, error=str(error)), ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
