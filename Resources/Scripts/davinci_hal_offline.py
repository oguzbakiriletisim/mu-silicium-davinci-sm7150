#!/usr/bin/env python3
"""Pinned HAL protocol/dummy-client emulation, no real firmware services/MMIO."""
import hashlib
import json
from pathlib import Path
import struct

HAL_SHA256 = '72bdfde0fb278a2a5bbaa6eb8a6f72a36d3b3b3e61864f6e6aad6f59c6da52e5'


def emulate(data, fail=None):
    if hashlib.sha256(data).hexdigest() != HAL_SHA256:
        raise ValueError('Unreviewed HAL binary; fixed RVAs cannot be used')
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
                                    UC_ARM64_REG_X3, UC_ARM64_REG_SP, UC_ARM64_REG_X30, UC_ARM64_REG_PC)
    machine = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    machine.mem_map(0, 0x600000)
    machine.mem_write(0, data)
    reached, calls, debug_calls = [], [], []
    services = {0x1904: 'create', 0x2ed8: 'configure', 0x1b70: 'attach'}
    def hook(uc, address, size, context):
        if address == 0x5f0000:
            reached.append(True)
            uc.emu_stop()
            return
        if address == 0x4008:
            # Debug output only. No firmware console/service is executed.
            debug_calls.append(True)
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
            return
        if address not in services:
            return
        name = services[address]
        args = [uc.reg_read(r) for r in [UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3]]
        item = {'call': name}
        if name == 'create':
            uc.mem_write(args[0], struct.pack('<Q', 0x400000 + len(calls) * 0x100))
        elif name == 'attach':
            item.update(client=bytes(uc.mem_read(args[1], 32)).split(b'\0')[0].decode('ascii'),
                        arid=args[2], mask=args[3])
        calls.append(item)
        uc.reg_write(UC_ARM64_REG_X0, 1 if name == fail else 0)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
    machine.hook_add(UC_HOOK_CODE, hook)
    def call(rva, argument=0):
        reached.clear()
        machine.reg_write(UC_ARM64_REG_SP, 0x500800)
        machine.reg_write(UC_ARM64_REG_X0, argument)
        machine.reg_write(UC_ARM64_REG_X30, 0x5f0000)
        machine.emu_start(rva, 0x5f0004, count=5000)
        if not reached:
            raise ValueError('HAL routine did not return within instruction budget')
        return machine.reg_read(UC_ARM64_REG_X0)
    call(0x13bc, 0x410000)  # Protocol init: stores the real function table pointer.
    pointer, = struct.unpack('<Q', machine.mem_read(0x410000, 8))
    slots = list(struct.unpack('<10Q', machine.mem_read(pointer, 80)))
    status = call(0x1490)  # Dummy client only; all domain services are mocked.
    return {'binary_sha256': HAL_SHA256, 'function_table_rva': pointer,
            'function_slots': slots, 'dummy_return': hex(status), 'dummy_calls': calls,
            'debug_notifications': len(debug_calls),
            'dummy_initializes_ufs': any(c.get('client') == '\\_SB_.UFS0' for c in calls),
            'ram_only_emulation': True, 'actual_domain_services_executed': False,
            'physical_validation': False}


def main():
    root = Path(__file__).resolve().parents[2]
    path = root / 'Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.efi'
    print(json.dumps(emulate(path.read_bytes()), indent=2))

if __name__ == '__main__':
    main()
