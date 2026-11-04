#!/usr/bin/env python3
"""Bounded ARM64 emulation of pinned UFS routines, with all services mocked.

Never executes a driver on the host or a phone. No DMA, MMIO or disk access.
Requires the optional requirements-offline-ufs.txt packages.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ORIGINAL_COMMIT = 'ffa8933a6ae7688fcbe3693b698833efdaa3536f'
ORIGINAL_SHA256 = '7549f618b3e511a5cedca84c6e76870062961add72753b37d0221a87ba5802dc'
PATCHED_SHA256 = '0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1'
UFS_PATH = 'Binaries/davinci/QcomPkg/Drivers/UFSDxe/UFSDxe.efi'
NOT_FOUND = 0x800000000000000e


def load_images(root):
    original = subprocess.check_output(['git', 'show', ORIGINAL_COMMIT + ':' + UFS_PATH], cwd=root)
    patched = (root / UFS_PATH).read_bytes()
    for image, digest in [(original, ORIGINAL_SHA256), (patched, PATCHED_SHA256)]:
        if hashlib.sha256(image).hexdigest() != digest:
            raise ValueError('Unknown UFS image; RVAs require a new review')
    return original, patched


def emulate(image, routine='iommu', failure=None, ioc=None, boot_type=8, boot_status=0,
            locate_protocol=False):
    import pefile
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1,
                                    UC_ARM64_REG_X2, UC_ARM64_REG_X3,
                                    UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC)
    pe = pefile.PE(data=image)
    if pe.FILE_HEADER.Machine != 0xaa64 or pe.OPTIONAL_HEADER.ImageBase != 0:
        raise ValueError('Expected pinned zero-base AARCH64 PE')
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(0, 0x600000)
    uc.mem_write(0, pe.get_memory_mapped_image())
    def put64(address, value):
        uc.mem_write(address, struct.pack('<Q', value))
    put64(0x11d1f8, 0 if locate_protocol else 0x200000)
    for offset, target in [(0, 0x300000), (0x40, 0x300100), (0x10, 0x300200)]:
        put64(0x200000 + offset, target)
    put64(0x11d500, 0x201000)
    put64(0x201140, 0x300300)  # EFI_BOOT_SERVICES.LocateProtocol
    put64(0x200808, 0x300400)  # HAL protocol initialization callback
    services = {0x300000: 'create', 0x300100: 'configure_bypass', 0x300200: 'attach',
                0x300300: 'locate_protocol', 0x300400: 'protocol_init',
                0x6fbc: 'get_config', 0x540c: 'boot_query', 0x7020: 'debug'}
    calls, stopped = [], []
    regs = [UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3]
    def hook(machine, address, size, context):
        if address == 0x500000:
            stopped.append(True)
            machine.emu_stop()
            return
        if address not in services:
            return
        name = services[address]
        args = [machine.reg_read(r) for r in regs]
        result = 0
        if name != 'debug':
            item = {'service': name}
            if name == 'create':
                put64(args[0], 0x200100)
            elif name == 'configure_bypass':
                item['type'] = args[1]
                if args[1] not in (0, 1):
                    result = 1
            elif name == 'attach':
                item.update(client=bytes(machine.mem_read(args[1], 32)).split(b'\0')[0].decode('ascii'),
                            arid=args[2], mask=args[3])
            elif name == 'get_config':
                item['key'] = bytes(machine.mem_read(args[0], 32)).split(b'\0')[0].decode('ascii')
                result = NOT_FOUND if ioc is None else 0
                if ioc is not None:
                    machine.mem_write(args[1], struct.pack('<I', ioc))
            elif name == 'locate_protocol':
                put64(args[2], 0x200800)
            elif name == 'protocol_init':
                put64(args[0], 0x200000)
            elif name == 'boot_query':
                result = boot_status
                if boot_type is not None:
                    machine.mem_write(args[0], struct.pack('<I', boot_type))
            calls.append(item)
        if name == failure:
            result = NOT_FOUND if name == 'locate_protocol' else 1
        machine.reg_write(UC_ARM64_REG_X0, result)
        machine.reg_write(UC_ARM64_REG_PC, machine.reg_read(UC_ARM64_REG_X30))
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.reg_write(UC_ARM64_REG_SP, 0x400800)
    uc.reg_write(UC_ARM64_REG_X30, 0x500000)
    uc.emu_start(0x24f8 if routine == 'iommu' else 0x5304, 0x500004, count=2000)
    if not stopped:
        raise ValueError('Routine did not return within instruction budget')
    return {'return': hex(uc.reg_read(UC_ARM64_REG_X0)), 'calls': calls}


def main():
    root = Path(__file__).resolve().parents[2]
    original, patched = load_images(root)
    cases = {'original_default': emulate(original),
             'original_ioc_1': emulate(original, ioc=1),
             'original_protocol_lookup': emulate(original, locate_protocol=True),
             'patched': emulate(patched)}
    for name in ['create', 'configure_bypass', 'attach', 'locate_protocol']:
        cases['failure_' + name] = emulate(original, failure=name, locate_protocol=True)
    for value, status in [(8, 0), (1, 0), (None, NOT_FOUND)]:
        cases['boot_' + str(value)] = emulate(patched, 'boot', boot_type=value, boot_status=status)
    print(json.dumps({'original_commit': ORIGINAL_COMMIT, 'original_sha256': ORIGINAL_SHA256,
                      'patched_sha256': PATCHED_SHA256, 'cases': cases,
                      'mocked_services_only': True, 'physical_validation': False}, indent=2))

if __name__ == '__main__':
    main()
