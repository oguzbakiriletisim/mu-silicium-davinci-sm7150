#!/usr/bin/env python3
"""Validate existing Windows files and prepare an ESP directory on the PC only.

No disk enumeration on Linux, no formatting, mounting, deployment, ADB or
Fastboot. The default commands inspect/plan only. prepare-efi writes a new
folder under the Windows user's profile and a new OFFLINE BCD store there.
It never writes to either selected target partition or the host system BCD.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import uuid

ESP_TYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
BASIC_TYPE = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
LOADER = '8af49d28-d85c-11f1-8157-f0038c0eb282'


def guid(value):
    try:
        result = uuid.UUID(str(value).strip('{}'))
    except (ValueError, AttributeError) as error:
        raise ValueError('Missing/invalid GPT GUID') from error
    if result.int == 0:
        raise ValueError('Zero GUID is not an identity')
    return str(result)


def contained_file(root, relative):
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('File escapes staging directory: ' + relative)
    return path


def arm64_pe(path):
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b'MZ':
            raise ValueError('Not a PE file: ' + str(path))
        offset, = struct.unpack_from('<I', header, 60)
        if offset > path.stat().st_size - 26:
            raise ValueError('Invalid PE offset: ' + str(path))
        stream.seek(offset)
        pe = stream.read(26)
        optional_size = struct.unpack_from('<H', pe, 20)[0]
        if optional_size < 112 or offset + 24 + optional_size > path.stat().st_size:
            raise ValueError('Truncated PE32+ optional header: ' + str(path))
        if pe[:4] != b'PE\0\0' or struct.unpack_from('<H', pe, 4)[0] != 0xaa64 or struct.unpack_from('<H', pe, 24)[0] != 0x20b:
            raise ValueError('Expected ARM64 PE32+: ' + str(path))
    return {'machine': 'AARCH64', 'size': path.stat().st_size}


def hive_header(path):
    with path.open('rb') as stream:
        b = stream.read(4096)
    if len(b) < 4096 or b[:4] != b'regf':
        raise ValueError('Missing registry base block: ' + str(path))
    first, second = struct.unpack_from('<II', b, 4)
    bins, = struct.unpack_from('<I', b, 40)
    checksum = 0
    for word in struct.unpack_from('<127I', b):
        checksum ^= word
    if checksum == 0xffffffff:
        checksum = 0xfffffffe
    elif checksum == 0:
        checksum = 1
    if first != second or bins == 0 or bins % 4096 or path.stat().st_size < 4096 + bins or checksum != struct.unpack_from('<I', b, 508)[0]:
        raise ValueError('Dirty/truncated/invalid registry base block: ' + str(path))
    return {'base_block_valid': True, 'sequence': first,
            'note': 'HBIN contents and Windows installation completeness are not validated.'}


def inspect_staging(root):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Staging is not a directory')
    components = {}
    for name, relative in [('boot_manager', 'Windows/Boot/EFI/bootmgfw.efi'),
                           ('winload', 'Windows/System32/winload.efi'),
                           ('kernel', 'Windows/System32/ntoskrnl.exe')]:
        path = contained_file(root, relative)
        components[name] = dict(relative_path=relative, **arm64_pe(path))
    hives = {}
    for name in ['SYSTEM', 'SOFTWARE', 'SAM', 'SECURITY', 'DEFAULT']:
        path = contained_file(root, 'Windows/System32/config/' + name)
        hives[name] = hive_header(path)
    return {'staging_root': str(root), 'components': components, 'registry_hives': hives,
            'windows_11_version_verified': False, 'acls_hardlinks_and_reparse_metadata_verified': False,
            'complete_windows_installation_verified': False, 'physical_boot_verified': False}


def validate_layout(inventory, disk_guid, esp_guid, windows_guid):
    disk_guid, esp_guid, windows_guid = map(guid, [disk_guid, esp_guid, windows_guid])
    if inventory.get('schema_version') != 1 or esp_guid == windows_guid:
        raise ValueError('Invalid inventory schema or identical target partitions')
    disks = [d for d in inventory.get('disks', []) if d.get('partition_style') == 'GPT' and guid(d.get('guid')) == disk_guid]
    if len(disks) != 1:
        raise ValueError('Select exactly one disk by its actual GPT GUID')
    disk = disks[0]
    if disk.get('partition_error'):
        raise ValueError('Selected disk could not be inventoried completely')
    if disk.get('is_boot') is not False or disk.get('is_system') is not False:
        raise ValueError('Host boot/system disk cannot be a target')
    if disk.get('logical_sector_size') not in (512, 4096) or not isinstance(disk.get('size'), int) or disk['size'] <= 0:
        raise ValueError('Invalid disk geometry')
    parts, intervals, letters = {}, [], set()
    for p in disk.get('partitions', []):
        key = guid(p.get('guid'))
        if key in parts:
            raise ValueError('Duplicate partition GUID')
        parts[key] = p
        offset, size = p.get('offset'), p.get('size')
        if not isinstance(offset, int) or not isinstance(size, int) or offset <= 0 or size <= 0 or offset % disk['logical_sector_size'] or size % disk['logical_sector_size'] or offset + size > disk['size']:
            raise ValueError('Invalid/out-of-bounds partition extent')
        for start, end in intervals:
            if max(start, offset) < min(end, offset + size):
                raise ValueError('Overlapping partition extents')
        intervals.append((offset, offset + size))
        letter = p.get('drive_letter')
        if letter:
            if len(letter) != 1 or letter.upper() not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or letter.upper() in letters:
                raise ValueError('Invalid/duplicate drive letter')
            letters.add(letter.upper())
    try:
        esp, windows = parts[esp_guid], parts[windows_guid]
    except KeyError as error:
        raise ValueError('Selected partition GUID is absent') from error
    for part, fs, expected_type in [(esp, 'FAT32', ESP_TYPE), (windows, 'NTFS', BASIC_TYPE)]:
        if part.get('is_boot') is not False or part.get('is_system') is not False:
            raise ValueError('Host boot/system partition cannot be a target')
        if guid(part.get('gpt_type')) != expected_type or str(part.get('file_system') or '').upper() != fs:
            raise ValueError('Requires an existing ' + fs + ' partition of the correct GPT type; no formatting is performed')
        if not part.get('drive_letter'):
            raise ValueError('Target needs an already assigned drive letter; this tool does not mount it')
    return {'disk_guid': disk_guid, 'esp_guid': esp_guid, 'windows_guid': windows_guid,
            'esp_letter': esp['drive_letter'].upper(), 'windows_letter': windows['drive_letter'].upper(),
            'disk_size': disk['size'], 'esp_extent': [esp['offset'], esp['size']],
            'windows_extent': [windows['offset'], windows['size']]}


def bcd_commands(store, target, loader=LOADER):
    loader = '{' + guid(loader) + '}'
    esp = 'partition=' + target['esp_letter'] + ':'
    windows = 'partition=' + target['windows_letter'] + ':'
    commands = [['/createstore', str(store)]]
    def command(*args):
        commands.append(['/store', str(store), *args])
    command('/create', '{bootmgr}', '/d', 'Windows Boot Manager')
    command('/set', '{bootmgr}', 'device', esp)
    command('/set', '{bootmgr}', 'path', r'\EFI\Microsoft\Boot\bootmgfw.efi')
    command('/create', loader, '/d', 'Windows 11 ARM64 (davinci research)', '/application', 'osloader')
    command('/set', loader, 'device', windows)
    command('/set', loader, 'osdevice', windows)
    command('/set', loader, 'path', r'\Windows\System32\winload.efi')
    command('/set', loader, 'systemroot', r'\Windows')
    command('/default', loader)
    command('/displayorder', loader)
    command('/timeout', '5')
    command('/enum', 'all')
    return commands


def plan(root, inventory, disk_guid, esp_guid, windows_guid, output, loader=LOADER):
    inspected = inspect_staging(root)
    target = validate_layout(inventory, disk_guid, esp_guid, windows_guid)
    return {'schema_version': 1, 'staging': inspected, 'target': target,
            'output_directory': str(output), 'loader_guid': guid(loader),
            'efi_files': ['EFI/Boot/bootaa64.efi', 'EFI/Microsoft/Boot/bootmgfw.efi', 'EFI/Microsoft/Boot/BCD'],
            'bcdedit_argument_arrays': bcd_commands(output / 'EFI/Microsoft/Boot/BCD', target, loader),
            'phone_writes_authorized_by_this_plan': False, 'ufs_block_io_verified': False,
            'windows_boot_start_drivers_verified': False,
            'deployment_status': 'BLOCKED: UFS/Block I/O, actual target layout, Windows drivers and installation metadata require independent validation.'}


def copy_efi_files(root, output):
    """Small PC staging copy only; BCD is created separately by Windows bcdedit."""
    root, output = root.resolve(strict=True), output.resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Source and output directories must be separate')
    if output.exists():
        raise ValueError('Output must be a new directory; existing files will not be overwritten')
    source = contained_file(root, 'Windows/Boot/EFI/bootmgfw.efi')
    arm64_pe(source)
    if source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Unexpectedly large boot manager')
    output.mkdir(parents=True, exist_ok=False)
    for relative in ['EFI/Boot/bootaa64.efi', 'EFI/Microsoft/Boot/bootmgfw.efi']:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # Only small boot helpers, never Windows/Program Files or driver packages.
    efi = root / 'Windows/Boot/EFI'
    total = 2 * source.stat().st_size
    for candidate in efi.rglob('*'):
        if not candidate.is_file() or candidate.name.lower() in ['bootmgfw.efi', 'bcd']:
            continue
        if candidate.suffix.lower() not in ['.efi', '.mui', '.p7b', '.stl', '.dll']:
            continue
        resolved = contained_file(root, str(candidate.relative_to(root)))
        size = resolved.stat().st_size
        total += size
        if size > 32 * 1024 * 1024 or total > 256 * 1024 * 1024:
            raise ValueError('Unexpectedly large boot helper set')
        if resolved.suffix.lower() == '.efi':
            arm64_pe(resolved)
        target = output / 'EFI/Microsoft/Boot' / candidate.relative_to(efi)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(resolved, target)
    fonts = root / 'Windows/Boot/Fonts'
    if fonts.is_dir():
        font_output = output / 'EFI/Microsoft/Boot/Fonts'
        for font in fonts.iterdir():
            if font.suffix.lower() == '.ttf':
                resolved = contained_file(root, str(font.relative_to(root)))
                if resolved.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError('Unexpectedly large boot font')
                font_output.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(resolved, font_output / font.name)
    for relative in ['Windows/Boot/Resources/bootres.dll']:
        if (root / relative).is_file():
            source = contained_file(root, relative)
            if source.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('Unexpectedly large boot resource')
            target = output / 'EFI/Microsoft/Boot/Resources/bootres.dll'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def prepare_on_windows(args):
    if platform.system() != 'Windows':
        raise ValueError('BCD preparation requires Windows; inspect/plan work offline on other hosts')
    output = args.output.resolve()
    profile = Path(os.environ['USERPROFILE']).resolve(strict=True)
    if not output.is_relative_to(profile) or output.drive.upper() != profile.drive.upper():
        raise ValueError('Output must be a new PC folder under USERPROFILE')
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    bcdedit = Path(os.environ['SystemRoot']) / 'System32/bcdedit.exe'
    inventory_script = Path(__file__).with_name('Collect-DiskInventory.ps1')
    # Refresh real mounted partition identities immediately before BCD creation.
    fresh = subprocess.check_output([str(powershell), '-NoProfile', '-NonInteractive', '-File', str(inventory_script)], encoding='utf-8-sig')
    inventory = json.loads(fresh)
    result = plan(args.staging, inventory, args.disk_guid, args.esp_guid, args.windows_guid, output, args.loader_guid)
    copy_efi_files(args.staging, output)
    (output / 'PLAN.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    log = []
    try:
        for command in result['bcdedit_argument_arrays']:
            completed = subprocess.run([str(bcdedit), *command], check=True, capture_output=True)
            log.append({'arguments': command, 'stdout': completed.stdout.decode(errors='replace'),
                        'stderr': completed.stderr.decode(errors='replace')})
    except subprocess.CalledProcessError as error:
        log.append({'arguments': command, 'exit_code': error.returncode,
                    'stdout': (error.stdout or b'').decode(errors='replace'),
                    'stderr': (error.stderr or b'').decode(errors='replace'), 'status': 'FAILED; partial output retained'})
        raise
    finally:
        (output / 'BCD-CREATION.json').write_text(json.dumps(log, indent=2), encoding='utf-8')
    result['offline_bcd_header'] = hive_header(output / 'EFI/Microsoft/Boot/BCD')
    result['pc_preparation_status'] = 'EFI_AND_OFFLINE_BCD_PREPARED_ON_PC_ONLY'
    (output / 'PLAN.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'stage-efi', 'plan', 'prepare-efi'])
    parser.add_argument('--staging', type=Path, required=True)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--disk-guid')
    parser.add_argument('--esp-guid')
    parser.add_argument('--windows-guid')
    parser.add_argument('--loader-guid', default=LOADER)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'inspect':
        result = inspect_staging(args.staging)
    else:
        if not args.output:
            parser.error('--output is required')
        if args.action == 'stage-efi':
            output = args.output.resolve()
            profile = Path.home().resolve(strict=True)
            if not output.is_relative_to(profile):
                raise ValueError('Staged EFI output must be a new PC directory under the user profile')
            result = inspect_staging(args.staging)
            copy_efi_files(args.staging, output)
            result.update(output_directory=str(output), status='EFI_FILES_ONLY_NO_BCD', phone_deployment_verified=False)
            (output / 'STAGING.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        elif args.action == 'prepare-efi':
            result = prepare_on_windows(args)
        else:
            if not args.inventory:
                parser.error('--inventory is required for plan')
            result = plan(args.staging, json.loads(args.inventory.read_text(encoding='utf-8-sig')),
                          args.disk_guid, args.esp_guid, args.windows_guid, args.output, args.loader_guid)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
