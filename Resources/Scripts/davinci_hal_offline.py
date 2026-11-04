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



def emulate_bank_choice(data, cbar_values, architecture=0):
    """Execute real bank-selection code with fixture IDR/CBAR/CBA2R services.

    Recorded 'writes' are intercepted callback arguments in the emulator. No
    actual register method, MMIO, DMA or hardware state is accessed.
    """
    if hashlib.sha256(data).hexdigest() != HAL_SHA256 or not 0 <= len(cbar_values) <= 255:
        raise ValueError('Unreviewed HAL image or invalid fixture bank count')
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
                                    UC_ARM64_REG_SP, UC_ARM64_REG_X30, UC_ARM64_REG_PC)
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(0, 0x600000); uc.mem_write(0, data)
    uc.mem_write(0x410000, struct.pack('<I', 0xffffffff))
    writes, stopped = [], []
    def hook(machine, address, size, context):
        if address == 0x5f0000:
            stopped.append(True); machine.emu_stop(); return
        if address not in [0x3b60, 0x3870, 0x38cc, 0x392c, 0x3988]:
            return
        args = [machine.reg_read(r) for r in [UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2]]
        if address == 0x3b60:
            machine.mem_write(args[1], struct.pack('<I', len(cbar_values)))
        elif address in [0x3870, 0x392c]:
            if args[1] >= len(cbar_values):
                raise ValueError('Bank read outside fixture range')
            value = cbar_values[args[1]] if address == 0x3870 else 0
            machine.mem_write(args[2], struct.pack('<I', value))
        else:
            writes.append({'register': 'CBAR' if address == 0x38cc else 'CBA2R',
                           'base': args[0], 'bank': args[1], 'value': args[2]})
        machine.reg_write(UC_ARM64_REG_X0, 0)
        machine.reg_write(UC_ARM64_REG_PC, machine.reg_read(UC_ARM64_REG_X30))
    uc.hook_add(UC_HOOK_CODE, hook)
    for register, value in [(UC_ARM64_REG_X0, 0x15000000), (UC_ARM64_REG_X1, architecture),
                            (UC_ARM64_REG_X2, 0x410000), (UC_ARM64_REG_SP, 0x500800),
                            (UC_ARM64_REG_X30, 0x5f0000)]:
        uc.reg_write(register, value)
    uc.emu_start(0x2278, 0x5f0004, count=20000)
    if not stopped:
        raise ValueError('Bank selector did not return within instruction budget')
    bank, = struct.unpack('<I', uc.mem_read(0x410000, 4))
    return {'selected_bank': None if bank == 0xffffffff else bank,
            'intercepted_write_arguments': writes, 'fixture_only': True,
            'actual_register_services_executed': False, 'physical_validation': False}


def main():
    root = Path(__file__).resolve().parents[2]
    path = root / 'Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.efi'
    data = path.read_bytes()
    result = emulate(data)
    result['context_bank_fixture_examples'] = {
        'por_bank_zero': emulate_bank_choice(data, [0, 0]),
        'first_two_busy': emulate_bank_choice(data, [0x10000, 0x10000, 0]),
        'all_busy': emulate_bank_choice(data, [0x10000, 0x10000])}
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
