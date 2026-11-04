#!/usr/bin/env python3
"""Read-only PE/DAL/IORT extraction. Never loads firmware or programs hardware.

The compact DAL property and 64-bit structure layouts are inferred from the
pinned davinci binary and checked against the published DAL schema. An embedded
binding is evidence of linked data, not of runtime selection or hardware state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

DAL_SHA256 = '0542d91c859baf816f42438cc3472fed84897e7c5dec7cdfc05221e5ede40544'


def unpack(fmt, data, offset):
    if offset < 0 or offset + struct.calcsize(fmt) > len(data):
        raise ValueError('Truncated structure')
    return struct.unpack_from(fmt, data, offset)


def cstring(data, start, end):
    if not 0 <= start < end <= len(data):
        raise ValueError('Invalid string range')
    stop = data.find(b'\0', start, end)
    if stop < 0:
        raise ValueError('Unterminated string')
    return data[start:stop].decode('ascii')


class PeImage:
    def __init__(self, data):
        self.data = data
        if data[:2] != b'MZ':
            raise ValueError('Not PE')
        pe, = unpack('<I', data, 60)
        if data[pe:pe + 4] != b'PE\0\0':
            raise ValueError('Invalid PE signature')
        machine, count = unpack('<HH', data, pe + 4)
        optional_size, = unpack('<H', data, pe + 20)
        magic, = unpack('<H', data, pe + 24)
        if machine != 0xaa64 or magic != 0x20b or not 1 <= count <= 96 or optional_size < 64:
            raise ValueError('Expected bounded AARCH64 PE32+')
        self.base, = unpack('<Q', data, pe + 48)
        self.sections = []
        for i in range(count):
            virtual_size, rva, raw_size, raw = unpack('<IIII', data, pe + 24 + optional_size + 40 * i + 8)
            if raw + raw_size > len(data):
                raise ValueError('PE section extends beyond file')
            self.sections.append((rva, virtual_size, raw, raw_size))

    def offset(self, va, size=1):
        rva = va - self.base
        for start, virtual_size, raw, raw_size in self.sections:
            if size > 0 and start <= rva and rva + size <= start + min(virtual_size, raw_size):
                return raw + rva - start
        raise ValueError('VA is not backed by an initialized PE section')

    def va(self, offset):
        for rva, virtual_size, raw, raw_size in self.sections:
            if raw <= offset < raw + min(raw_size, virtual_size):
                return self.base + rva + offset - raw
        raise ValueError('File offset is not in a PE section')


def decode_iort(data):
    if len(data) < 48 or data[:4] != b'IORT':
        raise ValueError('Missing IORT header')
    length, = unpack('<I', data, 4)
    count, start = unpack('<II', data, 36)
    if length != len(data) or not 1 <= count <= 1024 or not 48 <= start < length:
        raise ValueError('Invalid IORT table bounds')
    nodes, pos = {}, start
    for _ in range(count):
        kind, size, revision, identifier, nmap, mapping_offset = unpack('<BH BIII', data, pos)
        if size < 16 or pos + size > length or nmap > size // 20:
            raise ValueError('Invalid IORT node bounds')
        if nmap and (mapping_offset < 16 or mapping_offset + nmap * 20 > size):
            raise ValueError('ID mapping array outside node')
        node = {'offset': pos, 'type': kind, 'revision': revision, 'length': size,
                'identifier': identifier, 'mappings': []}
        if kind == 1:
            if size < 30 or (nmap and mapping_offset < 30):
                raise ValueError('Short named component')
            node.update(name=cstring(data, pos + 29, pos + (mapping_offset if nmap else size)),
                        coherent=unpack('<I', data, pos + 20)[0], address_bits=data[pos + 28])
        elif kind == 3:
            if size < 60:
                raise ValueError('Short SMMUv1/v2 node')
            base, span, model, flags = unpack('<QQII', data, pos + 16)
            glob, nctx, ctxoff, npmu, pmuoff = unpack('<IIIII', data, pos + 40)
            for array_offset, entries in [(glob, 2), (ctxoff, nctx), (pmuoff, npmu)]:
                if entries and (array_offset < 60 or array_offset + entries * 8 > size):
                    raise ValueError('SMMU interrupt array outside node')
            node.update(base=base, span=span, model=model, flags=flags,
                        context_interrupts=nctx, pmu_interrupts=npmu)
        for i in range(nmap):
            a, number, out, reference, flags = unpack('<IIIII', data, pos + mapping_offset + 20 * i)
            node['mappings'].append({'input_base': a, 'number_raw': number, 'output_base': out,
                                     'output_reference': reference, 'flags': flags})
        nodes[pos] = node
        pos += size
    names = set()
    for node in nodes.values():
        if node['type'] == 1:
            if node['name'] in names:
                raise ValueError('Duplicate named component')
            names.add(node['name'])
            for mapping in node['mappings']:
                target = nodes.get(mapping['output_reference'])
                if not target or target['type'] != 3:
                    raise ValueError('Named mapping does not reference a declared SMMU node')
    return {'revision': data[8], 'length': length, 'declared_nodes': count,
            'checksum_mod256': sum(data) % 256, 'unparsed_tail_bytes': length - pos,
            'nodes': list(nodes.values())}


def djb2(text):
    value = 5381
    for byte in text.encode('ascii'):
        value = (value * 33 + byte) & 0xffffffff
    return value


def extract_binding(data):
    pe = PeImage(data)
    candidates = []
    # DALProps: property-bin pointer, struct table pointer, device count, padding,
    # string-device table pointer. Examine initialized file data only.
    for info in range(0, len(data) - 32, 8):
        prop_va, struct_va, count, device_va = unpack('<QQI4xQ', data, info)
        if not 1 <= count <= 256:
            continue
        try:
            prop = pe.offset(prop_va, 24)
            total, names, strings, byte, integers, ndevices = unpack('<6I', data, prop)
            if not 24 <= names <= strings <= byte <= integers <= total:
                continue
            pe.offset(prop_va, total)
            devices = pe.offset(device_va, count * 40)
            matches = []
            for index in range(count):
                entry = devices + index * 40
                name_va, name_hash, property_offset = unpack('<QII', data, entry)
                name_pos = pe.offset(name_va, 5)
                if data[name_pos:name_pos + 5] != b'SMMU\0':
                    continue
                if name_hash != djb2('SMMU') or property_offset + 12 > total:
                    raise ValueError('Invalid SMMU device entry')
                value_pos = prop + property_offset
                compact, struct_index, terminator = unpack('<III', data, value_pos)
                if compact >> 24 != 0x12 or not compact & 0x800000 or terminator != 0xff00ff00:
                    raise ValueError('Unsupported SMMU property encoding')
                name_offset = compact & 0x7fffff
                if names + name_offset >= strings or cstring(data, prop + names + name_offset, prop + strings) != 'IORT':
                    raise ValueError('SMMU property is not named IORT')
                descriptor = pe.offset(struct_va + struct_index * 16, 16)
                pointer_size, iort_va = unpack('<QQ', data, descriptor)
                if pointer_size != 8:
                    raise ValueError('Unexpected struct-pointer descriptor')
                iort_pos = pe.offset(iort_va, 48)
                length, = unpack('<I', data, iort_pos + 4)
                pe.offset(iort_va, length)
                table = decode_iort(data[iort_pos:iort_pos + length])
                matches.append({'props_info_offset': info, 'property_bin_offset': prop,
                                'string_device_offset': entry, 'compact_property_offset': value_pos,
                                'struct_index': struct_index, 'struct_descriptor_offset': descriptor,
                                'iort_file_offset': iort_pos, 'iort': table})
            candidates.extend(matches)
        except (ValueError, UnicodeDecodeError):
            continue
    if len(candidates) != 1:
        raise ValueError('Expected one unambiguous DAL SMMU/IORT binding; found ' + str(len(candidates)))
    result = candidates[0]
    owners = []
    info_va = pe.va(result['props_info_offset'])
    for offset in range(8, len(data) - 16, 8):
        pointer, = unpack('<Q', data, offset)
        if pointer != info_va:
            continue
        try:
            label_va, = unpack('<Q', data, offset - 8)
            label_offset = pe.offset(label_va, 1)
            label = cstring(data, label_offset, min(label_offset + 64, len(data)))
            if label == '7150_xml':
                owners.append({'target_record_offset': offset - 8, 'label': label,
                               'phase': unpack('<I', data, offset + 12)[0]})
        except (ValueError, UnicodeDecodeError):
            continue
    result['target_registration_records'] = owners
    nodes = {n['offset']: n for n in result['iort']['nodes']}
    ufs = [n for n in nodes.values() if n.get('name') == '\\_SB_.UFS0']
    if len(ufs) != 1:
        raise ValueError('Missing declared UFS0 component')
    mappings = [m for m in ufs[0]['mappings'] if m['input_base'] == 0]
    if len(mappings) != 1 or mappings[0]['number_raw'] == 0:
        raise ValueError('Missing usable UFS ARID zero mapping')
    mapping = mappings[0]
    smmu = nodes[mapping['output_reference']]
    result['ufs_arid_zero'] = {'sid_base': mapping['output_base'],
                              'firmware_number_raw': mapping['number_raw'],
                              'smmu_base': smmu['base'], 'smmu_span': smmu['span'],
                              'context_bank': None, 'context_bank_reason': 'Selected dynamically by HAL from hardware; not encoded as a fixed UFS bank.'}
    result.update(binary_sha256=hashlib.sha256(data).hexdigest(),
                  matches_pinned_davinci_binary=hashlib.sha256(data).hexdigest() == DAL_SHA256,
                  runtime_selection_verified=False, physical_validation=False,
                  safe_to_enable_dma=False, suitable_for_direct_os_acpi_publication=False)
    return result


def emulate_registration(data):
    """Run pinned DAL phase registration/getter with a RAM-only fake allocator."""
    if hashlib.sha256(data).hexdigest() != DAL_SHA256:
        raise ValueError('Unknown DAL binary; RVAs need a fresh review')
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC
    machine = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    machine.mem_map(0, 0x600000)
    machine.mem_write(0, data)  # Pinned file has identical RVA/raw section offsets.
    allocations, reached = [], []
    def hook(uc, address, size, context):
        if address == 0x5f0000:
            reached.append(True)
            uc.emu_stop()
        elif address == 0x37c8:
            payload = uc.reg_read(UC_ARM64_REG_X0)
            heap = 0x400000 + 0x100 * len(allocations)
            if len(allocations) >= 16:
                raise ValueError('Unexpected DAL allocator loop')
            allocations.append(payload)
            uc.mem_write(heap, struct.pack('<QI4xQ', payload, 0xffffffff, 0))
            uc.reg_write(UC_ARM64_REG_X0, heap)
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
    machine.hook_add(UC_HOOK_CODE, hook)
    def call(address, argument=0):
        reached.clear()
        machine.reg_write(UC_ARM64_REG_SP, 0x500800)
        machine.reg_write(UC_ARM64_REG_X0, argument)
        machine.reg_write(UC_ARM64_REG_X30, 0x5f0000)
        machine.emu_start(address, 0x5f0004, count=10000)
        if not reached:
            raise ValueError('DAL routine did not return within instruction budget')
        return machine.reg_read(UC_ARM64_REG_X0)
    call(0x3814)  # Root list initialization.
    call(0x38bc)  # Register target table entries for phase 0.
    selected = call(0x3888, 0)
    return {'mock_allocations_payloads': allocations, 'phase_zero_props_info': selected,
            'next_phase': struct.unpack('<I', machine.mem_read(0x3eb50, 4))[0],
            'ram_only_emulation': True, 'physical_validation': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=Path(__file__).resolve().parents[2] / 'Binaries/davinci/QcomPkg/Drivers/DALSYSDxe/DALSYSDxe.efi')
    parser.add_argument('--emulate-registration', action='store_true')
    args = parser.parse_args()
    data = args.file.read_bytes()
    result = extract_binding(data)
    if args.emulate_registration:
        result['registration_emulation'] = emulate_registration(data)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
