#!/usr/bin/env python3
"""Offline checks only. Does not enumerate host disks or connect to devices."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

UFS_SHA256 = '0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1'
UFS_GUID = '0d35cd8e-97ea-4f9a-96af-0f0d89f76567'
AUDIT_GUID = '373cccf6-9a82-4fd9-ab08-0dac61afc9da'

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
    return {'signature': signature, 'length': length,
            'checksum_mod256': sum(data) % 256,
            'oem_id': data[10:16].decode('ascii').strip()}

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

def source_audit(root):
    device = root / 'Platforms/Xiaomi/davinciPkg'
    dsc = (device / 'davinci.dsc').read_text()
    dts = (root / 'Resources/DTBs/davinci.dts').read_text()
    items = regions((device / 'Library/DeviceMemoryMapLib/DeviceMemoryMapLib.c').read_text())
    count = check_regions(items)
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
    topology = check_cpu_topology(dts, (root / 'Silicium-ACPI/SoCs/Qualcomm/Moorea/APIC.aml').read_bytes())
    return {'regions': count, 'ufs_resources': resources, 'cpu_topology': topology,
            'framebuffer': {'width': 1080, 'height': 2340, 'base': hex(display[1]), 'reserved_bytes': display[2]},
            'ufs_sha256': digest, 'ufs_iommu_bypass_retained': True,
            'architected_timer_from_dts': timer_from_dts(dts),
            'ufs_depex': 'SMEM', 'physical_validation': False}

def firmware_audit(path, cpu_only=False, expected_timer=None):
    from uefi_firmware.uefi import FirmwareVolume
    data = path.read_bytes()
    offset = data.find(b'_FVH') - 40
    if offset < 0:
        raise ValueError('Firmware volume header not found')
    volume = FirmwareVolume(data[offset:])
    if not volume.valid_header or not volume.process():
        raise ValueError('Could not parse firmware volume')
    found, tables, timer_tables = {}, [], []
    def visit(nodes):
        for node in nodes:
            if node['type'] == 'FirmwareFileSystemSection':
                raw = getattr(node['_self'], 'data', b'')
                if node['attrs'].get('type') == 16 and node['guid'].lower() in [UFS_GUID, AUDIT_GUID]:
                    if pe_machine(raw) != 0xAA64:
                        raise ValueError('Non-ARM64 EFI component')
                    found[node['guid'].lower()] = hashlib.sha256(raw).hexdigest()
                if node['attrs'].get('type') == 25 and raw[:4] in [b'DSDT', b'APIC', b'GTDT', b'FACP', b'PPTT', b'IORT', b'MCFG', b'CSRT']:
                    tables.append(acpi_header(raw))
                    if raw[:4] == b'GTDT':
                        if len(raw) < 80:
                            raise ValueError('Truncated GTDT')
                        timer_tables.append([struct.unpack_from('<II', raw, i) for i in [48, 56, 64, 72]])
            visit(node.get('objects', []))
    visit(volume.iterate_objects())
    if found.get(UFS_GUID) != UFS_SHA256 or AUDIT_GUID not in found:
        raise ValueError('Firmware is missing the reviewed UFS or DEBUG audit driver')
    if cpu_only:
        dsdt = [t for t in tables if t['signature'] == 'DSDT']
        if len(dsdt) != 1 or dsdt[0]['oem_id'] != 'DVNCI' or dsdt[0]['checksum_mod256']:
            raise ValueError('CPU-only research DSDT was not packaged correctly')
        if any(t['signature'] in ['IORT', 'MCFG', 'CSRT'] for t in tables):
            raise ValueError('Unverified peripheral tables leaked into CPU-only profile')
        if len(timer_tables) != 1 or timer_tables[0] != expected_timer:
            raise ValueError('Research GTDT does not match DTS interrupts/trigger polarity')
        if any(t['checksum_mod256'] for t in tables if t['signature'] == 'GTDT'):
            raise ValueError('Research GTDT checksum is invalid')
    return {'fd_sha256': hashlib.sha256(data).hexdigest(), 'efi_components': found, 'acpi_raw_tables': tables,
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
