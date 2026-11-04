#!/usr/bin/env python3
"""Pinned real HAL routines in RAM. Allocator/register services are mocked."""
import hashlib
import json
from pathlib import Path
import struct

SHA='72bdfde0fb278a2a5bbaa6eb8a6f72a36d3b3b3e61864f6e6aad6f59c6da52e5'

def probe(image, ioc=0, existing=False):
    if hashlib.sha256(image).hexdigest()!=SHA:raise ValueError('Unknown native HAL')
    from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
    from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_SP,UC_ARM64_REG_X30,UC_ARM64_REG_PC
    from pefile import PE
    u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x600000)
    u.mem_write(0,PE(data=image).get_memory_mapped_image())
    regs=[UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2]
    stopped=[];writes=[]
    smr=[0x800f0300 if existing else 0]+[0]*78
    def hook(m,a,size,c):
        if a==0x5f0000:stopped.append(True);m.emu_stop();return
        if a not in [0x3fa0,0x3b04,0x3aa8,0x3a48,0x39e8]:return
        args=[m.reg_read(r) for r in regs]
        result=0
        if a==0x3fa0:
            if args[0]!=0x38:raise ValueError('Unexpected native domain allocation')
            result=0x400000
        elif a==0x3b04:m.mem_write(args[1],struct.pack('<I',0x40017e4f))
        elif a==0x3aa8:m.mem_write(args[2],struct.pack('<I',smr[args[1]]))
        else:
            writes.append(dict(register='SMR' if a==0x3a48 else 'S2CR',index=args[1],value=args[2]))
        m.reg_write(UC_ARM64_REG_X0,result);m.reg_write(UC_ARM64_REG_PC,m.reg_read(UC_ARM64_REG_X30))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(a,x0=0,x1=0):
        stopped.clear();u.reg_write(UC_ARM64_REG_SP,0x500800)
        u.reg_write(UC_ARM64_REG_X0,x0);u.reg_write(UC_ARM64_REG_X1,x1);u.reg_write(UC_ARM64_REG_X30,0x5f0000)
        u.emu_start(a,0x5f0004,count=10000)
        if not stopped:raise ValueError('Instruction budget exceeded')
        return u.reg_read(UC_ARM64_REG_X0)
    created=call(0x1904,0x410000)
    domain=struct.unpack('<Q',u.mem_read(0x410000,8))[0]
    configured=call(0x3160,domain,ioc)
    domain_bytes=bytes(u.mem_read(domain,0x38))
    # Struct fixture only. CB2 is not selected/written on any phone.
    u.mem_write(0x420000,struct.pack('<4I',0x15000000,0,0,2))
    program=call(0x2648,0x420000,0x000f0300)
    return dict(binary_sha256=SHA,create_return=created,configure_return=configured,
                domain_sctlr=hex(struct.unpack_from('<I',domain_bytes,0x20)[0]),
                domain_tcr=hex(struct.unpack_from('<I',domain_bytes,0x24)[0]),
                programmer_return=program,register_service_arguments=writes,
                existing_mapping_fixture=existing,ram_only=True,physical_validation=False)

if __name__=='__main__':
    p=Path(__file__).resolve().parents[2]/'Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.efi'
    print(json.dumps({k:probe(p.read_bytes(),ioc=i,existing=e) for k,i,e in [('non_cca',0,False),('cca',1,False),('existing_smr',0,True)]},indent=2))
