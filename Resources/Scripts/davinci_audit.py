#!/usr/bin/env python3
"""Offline checks only. Does not enumerate host disks or connect to devices."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import uuid

UFS_SHA256 = '0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1'
UFS_GUID = '0d35cd8e-97ea-4f9a-96af-0f0d89f76567'
AUDIT_GUID = '373cccf6-9a82-4fd9-ab08-0dac61afc9da'
AFTER_UFS_GUID = 'a856730a-dc76-49d8-bf79-82e62070c61a'
APRIORI_GUID = 'fc510ee7-ffdc-11d4-bd41-0080c73c8881'

def regions(text):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    return [(n, int(a, 16), int(z, 16)) for n, a, z in re.findall(
        r'\{"([^"]+)",\s*(0x[\da-fA-F]+),\s*(0x[\da-fA-F]+)', text)]

def check_regions(items):
    if not items or len(items) >= 128:
        raise ValueError('Missing map or no room for the MMU terminator')
    for n, a, size in items:
        if size == 0 or a % 4096 or size % 4096 or a + size > 2**64:
            raise ValueError('Unaligned/invalid region: ' + n)
    # Existing nested windows use identical CPU Device attributes. These are
    # aliases, not evidence of DMA/SMMU correctness. Other overlaps fail closed.
    aliases = {frozenset(pair) for pair in [
        ('IMEM Base', 'IMEM Cookie Base'), ('GPU_CC', 'GPU_CPR'),
        ('MDSS', 'DISP_CC'), ('QTIMER', 'APSS_WDT_TMR1')]}
    for i, (n, a, z) in enumerate(items):
        for m, b, w in items[i + 1:]:
            if max(a, b) < min(a + z, b + w):
                contained = (a <= b and b + w <= a + z) or (b <= a and a + z <= b + w)
                if frozenset((n, m)) not in aliases or not contained:
                    raise ValueError('Unexpected overlapping regions: ' + n + '/' + m)
    return len(items)

def require_coverage(items, base, size):
    if not any(a <= base and base + size <= a + length for _, a, length in items):
        raise ValueError(f'Unmapped resource: {base:#x}+{size:#x}')

def pe_machine(data):
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Not a PE image')
    off = struct.unpack_from('<I', data, 60)[0]
    if off + 24 > len(data) or data[off:off + 4] != b'PE\0\0':
        raise ValueError('Truncated/invalid PE header')
    return struct.unpack_from('<H', data, off + 4)[0]

def acpi_header(data):
    if len(data) < 36:
        raise ValueError('Truncated ACPI header')
    signature = data[:4].decode('ascii')
    length = struct.unpack_from('<I', data, 4)[0]
    if length != len(data):
        raise ValueError('ACPI length does not match raw section')
    if signature == 'FACS':
        if length < 64:
            raise ValueError('Short FACS')
        return {'signature': signature, 'length': length, 'checksum_mod256': None,
                'oem_id': None, 'checksum_applicable': False}
    return {'signature': signature, 'length': length,
            'checksum_mod256': sum(data) % 256,
            'oem_id': data[10:16].decode('ascii').strip()}

def pptt_topology(data):
    """Validate PPTT references and return processor IDs for valid leaf nodes."""
    if acpi_header(data)['signature'] != 'PPTT':
        raise ValueError('Missing PPTT')
    nodes, pos = {}, 36
    while pos < len(data):
        if pos + 4 > len(data):
            raise ValueError('Truncated PPTT node')
        kind, length = data[pos:pos + 2]
        if length < 4 or pos + length > len(data) or kind not in (0, 1, 2):
            raise ValueError('Invalid PPTT node')
        if (kind == 1 and length < 24) or (kind == 2 and length != 30):
            raise ValueError('Short cache/invalid ID PPTT resource')
        nodes[pos] = (kind, data[pos:pos + length])
        pos += length
    cpus = {}
    for offset, (kind, node) in nodes.items():
        if kind != 0:
            continue
        if len(node) < 20:
            raise ValueError('Short PPTT processor')
        flags, parent, uid, count = struct.unpack_from('<IIII', node, 4)
        if len(node) != 20 + count * 4:
            raise ValueError('PPTT private resource count/length mismatch')
        ancestor, visited = parent, {offset}
        while ancestor:
            if ancestor in visited or ancestor not in nodes or nodes[ancestor][0] != 0:
                raise ValueError('Invalid/cyclic PPTT parent')
            visited.add(ancestor)
            ancestor_node = nodes[ancestor][1]
            if len(ancestor_node) < 20:
                raise ValueError('Short PPTT parent')
            ancestor = struct.unpack_from('<I', ancestor_node, 8)[0]
        for i in range(count):
            resource = struct.unpack_from('<I', node, 20 + i * 4)[0]
            # Revision 1 (ACPI 6.2) permits both cache and ID resources.
            allowed = (1, 2) if data[8] == 1 else (1,)
            if resource not in nodes or nodes[resource][0] not in allowed:
                raise ValueError('Invalid PPTT private resource reference')
        if flags & 2:
            if uid in cpus:
                raise ValueError('Duplicate PPTT processor ID')
            cpus[uid] = offset
    return cpus


def check_acpi_bundle(tables, cpu_only=False, expected_timer=None):
    """Inspect pre-installation RAW tables, not live RSDP/XSDT pointers."""
    by_signature = {}
    for data in tables:
        info = acpi_header(data)
        signature = info['signature']
        if signature in by_signature:
            raise ValueError('Duplicate ACPI table: ' + signature)
        by_signature[signature] = data
        if cpu_only and info['checksum_mod256']:
            raise ValueError('Invalid research ACPI checksum: ' + signature)
    for required in ['APIC', 'GTDT', 'FACP', 'PPTT'] + (['DSDT'] if cpu_only else []):
        if required not in by_signature:
            raise ValueError('Missing ACPI table: ' + required)
    madt = gicc_topology(by_signature['APIC'])
    pptt = pptt_topology(by_signature['PPTT'])
    if set(madt) != set(pptt):
        raise ValueError('MADT/PPTT processor ID mismatch')
    fadt = by_signature['FACP']
    if len(fadt) < 276 or fadt[8] < 6:
        raise ValueError('Expected an ACPI 6 FADT')
    flags = struct.unpack_from('<I', fadt, 112)[0]
    arm = struct.unpack_from('<H', fadt, 129)[0]
    if cpu_only:
        if len(fadt) != 276 or fadt[10:16] != b'DVNCI ' or flags != 1 << 20 or arm != 1:
            raise ValueError('Research FADT must be HW-reduced PSCI/SMC without S0 claims')
        # AcpiTableDxe patches DSDT/FACS pointers and recalculates checksums.
        if any(fadt[a:a + n] != bytes(n) for a, n in [(36, 8), (46, 66), (116, 13), (132, 144)]):
            raise ValueError('Research FADT has premature pointers/reset/hypervisor fields')
        if any(s in by_signature for s in ['IORT', 'MCFG', 'CSRT']):
            raise ValueError('Unverified peripheral tables leaked into CPU-only profile')
        dsdt = acpi_header(by_signature['DSDT'])
        if dsdt['oem_id'] != 'DVNCI':
            raise ValueError('Unexpected research DSDT OEM')
        gtdt = by_signature['GTDT']
        if len(gtdt) != 96 or [struct.unpack_from('<II', gtdt, i) for i in [48, 56, 64, 72]] != expected_timer:
            raise ValueError('Research GTDT does not match DTS interrupts/trigger polarity')
    return {'madt_pptt_cpu_ids': sorted(madt), 'fadt_flags': hex(flags),
            'fadt_arm_boot_arch': arm, 'raw_checksums_valid': all(sum(t) % 256 == 0 for t in tables if t[:4] != b'FACS'),
            'pre_installation_only': True}


def gicc_topology(data):
    if data[:4] != b'APIC' or len(data) < 44:
        raise ValueError('Missing MADT')
    result = {}
    pos = 44
    while pos < len(data):
        if pos + 2 > len(data):
            raise ValueError('Truncated MADT record')
        kind, length = data[pos:pos + 2]
        if length < 2 or pos + length > len(data):
            raise ValueError('Invalid MADT record length')
        if kind == 11:
            if length < 80:
                raise ValueError('Short GICC')
            if not struct.unpack_from('<I', data, pos + 12)[0] & 1:
                raise ValueError('Disabled GICC CPU in the davinci topology')
            uid = struct.unpack_from('<I', data, pos + 8)[0]
            mpidr = struct.unpack_from('<Q', data, pos + 68)[0]
            if uid in result:
                raise ValueError('Duplicate CPU UID')
            result[uid] = mpidr
        pos += length
    return result

def check_cpu_topology(dts, madt):
    cpus = re.findall(r'cpu@[\da-f]+\s*\{.*?device_type\s*=\s*"cpu";.*?reg\s*=\s*<([^>]+)>;', dts, re.S)
    mpidrs = [(int(x.split()[0], 0) << 32) | int(x.split()[1], 0) for x in cpus]
    expected = dict(enumerate(mpidrs))
    actual = gicc_topology(madt)
    if len(expected) != 8 or expected != actual:
        raise ValueError(f'DTS/MADT CPU mismatch: {expected} != {actual}')
    return {str(k): hex(v) for k, v in actual.items()}

def timer_from_dts(dts):
    match = re.search(r'compatible\s*=\s*"arm,armv8-timer";\s*interrupts\s*=\s*<([^>]+)>;', dts)
    if not match:
        raise ValueError('Missing architected timer interrupts')
    cells = [int(x, 0) for x in match[1].split()]
    if len(cells) != 12:
        raise ValueError('Expected four architected timer interrupts')
    out = []
    for i in range(0, 12, 3):
        kind, number, flags = cells[i:i + 3]
        if kind != 1 or not 0 <= number < 16 or flags & 15 not in (1, 2, 4, 8):
            raise ValueError('Invalid PPI trigger specification')
        low = flags & 15
        out.append((number + 16, (1 if low in (1, 2) else 0) | (2 if low in (2, 8) else 0)))
    return out

def decode_depex(data):
    """Decode the boolean DXE subset used by the pinned storage providers."""
    stack, guids, pos = [], [], 0
    while pos < len(data):
        op = data[pos]
        pos += 1
        if op == 2:
            if pos + 16 > len(data):
                raise ValueError('Truncated DEPEX GUID')
            guid = str(uuid.UUID(bytes_le=data[pos:pos + 16]))
            guids.append(guid)
            stack.append(guid)
            pos += 16
        elif op in (6, 7):
            stack.append('TRUE' if op == 6 else 'FALSE')
        elif op in (3, 4):
            if len(stack) < 2:
                raise ValueError('DEPEX binary operator underflow')
            right, left = stack.pop(), stack.pop()
            stack.append('(' + left + (' AND ' if op == 3 else ' OR ') + right + ')')
        elif op == 5:
            if not stack:
                raise ValueError('DEPEX NOT underflow')
            stack.append('(NOT ' + stack.pop() + ')')
        elif op == 8:
            if pos != len(data) or len(stack) != 1:
                raise ValueError('Invalid DEPEX END/stack/trailing data')
            return {'expression': stack[0], 'protocol_guids': sorted(set(guids))}
        else:
            raise ValueError('Unsupported DEPEX opcode: ' + str(op))
    raise ValueError('Missing DEPEX END')


def source_audit(root):
    device = root / 'Platforms/Xiaomi/davinciPkg'
    dsc = (device / 'davinci.dsc').read_text()
    dts = (root / 'Resources/DTBs/davinci.dts').read_text()
    items = regions((device / 'Library/DeviceMemoryMapLib/DeviceMemoryMapLib.c').read_text())
    count = check_regions(items)
    if not re.search(r'psci\s*\{[^}]*compatible\s*=\s*"arm,psci-1.0";[^}]*method\s*=\s*"smc";', dts):
        raise ValueError('Research FADT PSCI/SMC no longer matches davinci DTS')
    resources = {}
    for node in ['ufshc@1d84000', 'ufsphy_mem@1d87000', 'ufsice@1d90000']:
        match = re.search(re.escape(node) + r'\s*\{.*?reg\s*=\s*<([^>]+)>;', dts, re.S)
        if not match:
            raise ValueError('Missing DTS resource: ' + node)
        cells = [int(x, 0) for x in match[1].split()]
        for offset in range(0, len(cells), 2):
            require_coverage(items, cells[offset], cells[offset + 1])
        resources[node] = [hex(x) for x in cells]
    if not re.search(r'SOC_TYPE\s*=\s*0\b', dsc):
        raise ValueError('Davinci must select SM7150-AA / Snapdragon 730')
    if 'PcdPrimaryFrameBufferWidth|1080' not in dsc or 'PcdPrimaryFrameBufferHeight|2340' not in dsc:
        raise ValueError('Unexpected GOP dimensions')
    display = next(x for x in items if x[0] == 'Display Reserved')
    if display[2] < 1080 * 2340 * 4:
        raise ValueError('Display reservation is too small')
    ufs_dir = root / 'Binaries/davinci/QcomPkg/Drivers/UFSDxe'
    ufs = (ufs_dir / 'UFSDxe.efi').read_bytes()
    digest = hashlib.sha256(ufs).hexdigest()
    if digest != UFS_SHA256 or pe_machine(ufs) != 0xAA64:
        raise ValueError('Unreviewed UFSDxe or wrong architecture')
    if ufs[0x24F8:0x2500] != bytes.fromhex('00008052c0035fd6'):
        raise ValueError('Unexpected UFS IOMMU function; re-audit required')
    depex = (ufs_dir / 'UFSDxe.depex').read_bytes()
    if depex != bytes.fromhex('02d0c7e5f439d2cb47aacd7f66ef76323808'):
        raise ValueError('Unreviewed UFS DEPEX')
    apriori = (device / 'Include/APRIORI.inc').read_text()
    if apriori.index('StorageAuditDxe.inf') > apriori.index('UFSDxe.inf'):
        raise ValueError('Storage audit must run before UFS')
    if not apriori.index('StorageAuditDxe.inf') < apriori.index('UFSDxe.inf') < apriori.index('StorageAuditAfterUfsDxe.inf'):
        raise ValueError('Missing source-level UFS dispatch bracket')
    dependency_expressions = {}
    for directory in ['UFSDxe', 'HALIOMMUDxe', 'ClockDxe', 'SmemDxe', 'TzDxe']:
        for path in (root / 'Binaries/davinci/QcomPkg/Drivers' / directory).glob('*.depex'):
            dependency_expressions[path.name] = decode_depex(path.read_bytes())
    topology = check_cpu_topology(dts, (root / 'Silicium-ACPI/SoCs/Qualcomm/Moorea/APIC.aml').read_bytes())
    return {'regions': count, 'ufs_resources': resources, 'cpu_topology': topology,
            'framebuffer': {'width': 1080, 'height': 2340, 'base': hex(display[1]), 'reserved_bytes': display[2]},
            'ufs_sha256': digest, 'ufs_iommu_bypass_retained': True,
            'architected_timer_from_dts': timer_from_dts(dts),
            'ufs_depex': 'SMEM', 'binary_dependency_expressions': dependency_expressions,
            'apriori_bypasses_depex': True, 'psci_conduit': 'smc', 'physical_validation': False}

def firmware_audit(path, cpu_only=False, expected_timer=None):
    from uefi_firmware.uefi import FirmwareVolume
    data = path.read_bytes()
    offset = data.find(b'_FVH') - 40
    if offset < 0:
        raise ValueError('Firmware volume header not found')
    volume = FirmwareVolume(data[offset:])
    if not volume.valid_header or not volume.process():
        raise ValueError('Could not parse firmware volume')
    found, tables, raw_tables, apriori, ufs_depex = {}, [], [], [], []
    def visit(nodes):
        for node in nodes:
            if node['type'] == 'FirmwareFileSystemSection':
                raw = getattr(node['_self'], 'data', b'')
                if node['attrs'].get('type') == 25 and node['guid'].lower() == APRIORI_GUID:
                    if len(raw) % 16:
                        raise ValueError('Truncated APRIORI GUID list')
                    apriori.extend(str(uuid.UUID(bytes_le=raw[i:i + 16])) for i in range(0, len(raw), 16))
                if node['attrs'].get('type') == 19 and node['guid'].lower() == UFS_GUID:
                    ufs_depex.append(raw)
                if node['attrs'].get('type') == 16 and node['guid'].lower() in [UFS_GUID, AUDIT_GUID, AFTER_UFS_GUID]:
                    if pe_machine(raw) != 0xAA64:
                        raise ValueError('Non-ARM64 EFI component')
                    found[node['guid'].lower()] = hashlib.sha256(raw).hexdigest()
                if node['attrs'].get('type') == 25 and raw[:4] in [b'DSDT', b'APIC', b'GTDT', b'FACP', b'FACS', b'PPTT', b'IORT', b'MCFG', b'CSRT', b'DBG2']:
                    tables.append(acpi_header(raw))
                    raw_tables.append(raw)
            visit(node.get('objects', []))
    visit(volume.iterate_objects())
    if found.get(UFS_GUID) != UFS_SHA256 or AUDIT_GUID not in found or AFTER_UFS_GUID not in found:
        raise ValueError('Firmware is missing the reviewed UFS or DEBUG audit driver')
    if ufs_depex != [bytes.fromhex('02d0c7e5f439d2cb47aacd7f66ef76323808')]:
        raise ValueError('Firmware UFS DEPEX differs from the reviewed SMEM dependency')
    if AUDIT_GUID not in apriori or UFS_GUID not in apriori or apriori.index(AUDIT_GUID) >= apriori.index(UFS_GUID):
        raise ValueError('Compiled APRIORI does not put the audit before UFS')
    if AFTER_UFS_GUID not in apriori or apriori.index(AFTER_UFS_GUID) != apriori.index(UFS_GUID) + 1:
        raise ValueError('Post-UFS audit must immediately follow UFS in compiled APRIORI')
    if apriori.index(AUDIT_GUID) + 1 != apriori.index(UFS_GUID):
        raise ValueError('Pre-UFS audit must immediately precede UFS')
    bundle = check_acpi_bundle(raw_tables, cpu_only, expected_timer)
    return {'fd_sha256': hashlib.sha256(data).hexdigest(), 'efi_components': found, 'acpi_raw_tables': tables,
            'apriori_audit_before_ufs': True, 'apriori_audit_after_ufs': True,
            'ufs_depex_smem_confirmed': True, 'acpi_consistency': bundle,
            'note': 'Raw ACPI checksums may be recalculated by InstallAcpiTable; no runtime evidence.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--fd', type=Path)
    parser.add_argument('--cpu-only', action='store_true')
    args = parser.parse_args()
    result = {'source': source_audit(args.root)}
    if args.fd:
        expected = timer_from_dts((args.root / 'Resources/DTBs/davinci.dts').read_text())
        result['firmware'] = firmware_audit(args.fd, args.cpu_only, expected)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
