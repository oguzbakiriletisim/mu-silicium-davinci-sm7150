#!/usr/bin/env python3
"""Read-only static fingerprint/entry scan. No driver code is executed."""
import hashlib,json,re
from pathlib import Path
import pefile
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
ROOT=Path(__file__).resolve().parents[2]
def scan():
    results={}
    for name in ['PdcDxe','ClockDxe','RpmhDxe','NpaDxe','EnvDxe','UFSDxe']:
        p=ROOT/f'Binaries/davinci/QcomPkg/Drivers/{name}/{name}.efi';b=p.read_bytes();pe=pefile.PE(data=b)
        m=Cs(CS_ARCH_ARM64,CS_MODE_ARM);m.skipdata=True
        section=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text')
        ins=list(m.disasm(section.get_data(),section.VirtualAddress))
        at=b.find(b'Time out')
        row=dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),
                 machine=hex(pe.FILE_HEADER.Machine),entry_rva=hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
                 direct_smc_hvc_linear_scan=[hex(i.address) for i in ins if i.mnemonic in ('smc','hvc')],
                 timeout_text_neighborhood=b[max(0,at-105):at+100].decode('ascii',errors='replace') if at>=0 else None,
                 conclusion='Linear scan/text do not establish runtime call paths, reset absence, or a 30-second timer.')
        if name=='PdcDxe':
            guid=pe.get_data(0x7080,16)
            row['status_protocol_guid_at_7080']=__import__('uuid').UUID(bytes_le=guid).urn
            row['assert_and_service_evidence']={
              'assert_rva_1454':[(hex(i.address),i.mnemonic,i.op_str) for i in m.disasm(pe.get_data(0x1454,0x104),0x1454)],
              'status_wrapper_rva_2630':[(hex(i.address),i.mnemonic,i.op_str) for i in m.disasm(pe.get_data(0x2630,0xbc),0x2630)],
              'notes':'0x149c calls 0x2778: status-code type2/value0x03000007, not proof of a reset. Indirect callback behavior remains unknown. 0x1530 contains a software wait loop.'}
        if name=='UFSDxe':
            row['entry_evidence']={
              'wrapper':[(hex(i.address),i.mnemonic,i.op_str) for i in m.disasm(pe.get_data(0x1000,0x14c),0x1000)],
              'constructor_calls':[(hex(i.address),i.op_str) for i in m.disasm(pe.get_data(0x112c,0x294),0x112c) if i.mnemonic=='bl'],
              'module_entry_prefix':[(hex(i.address),i.mnemonic,i.op_str) for i in m.disasm(pe.get_data(0x13f0,0x50),0x13f0)],
              'existing_iommu_stub':[(hex(i.address),i.mnemonic,i.op_str) for i in m.disasm(pe.get_data(0x24f8,8),0x24f8)],
              'notes':'B0C6 precedes CoreStartImage including constructors, entry and callbacks. No inner native routine is identified by this checkpoint; the existing binary stub is unchanged.'}
        results[name]=row
    return results
if __name__=='__main__':print(json.dumps(scan(),indent=2))
