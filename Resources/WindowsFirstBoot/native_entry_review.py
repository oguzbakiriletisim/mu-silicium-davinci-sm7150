#!/usr/bin/env python3
"""Pinned native FFU branch in bounded RAM emulation. All external services mocked.

Never runs native firmware on the host CPU or hardware. No MMIO/DMA/disk access.
"""
import hashlib,json,struct
from pathlib import Path
SHA='0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1'
ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'Binaries/davinci/QcomPkg/Drivers/UFSDxe/UFSDxe.efi'
def emulate(vendor='MICRON',product='128GB-UFS-MT',revision='9QSQ',update_status=0):
 import pefile
 from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
 from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X30,UC_ARM64_REG_SP,UC_ARM64_REG_PC
 b=PATH.read_bytes();assert hashlib.sha256(b).hexdigest()==SHA
 p=pefile.PE(data=b);u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0,0x600000);u.mem_write(0,p.get_memory_mapped_image())
 assert p.get_data(0x2e70,4)==bytes.fromhex('09feff97') # BL2694 from main entry
 u.mem_write(0x200000,struct.pack('<Q',0x201000))
 u.mem_write(0x201418,vendor.encode().ljust(8,b' ')+product.encode().ljust(16,b' ')+revision.encode().ljust(4,b' '))
 regs=[UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3]
 calls=[];done=[]
 def cstr(a):return bytes(u.mem_read(a,256)).split(b'\0')[0]
 def hook(machine,a,size,data):
  if a==0x500000:done.append(True);machine.emu_stop();return
  if a not in (0x9074,0xc178,0x90ec,0x9148,0xd44c,0x13f8c,0x13e78,0x140f4):return
  args=[machine.reg_read(r) for r in regs];ret=0
  if a==0x90ec:ret=len(cstr(args[0]))
  if a==0x9148:
   left=bytes(machine.mem_read(args[0],args[2]));right=bytes(machine.mem_read(args[1],args[2]));ret=0 if left==right else 1
  if a==0xd44c:
   calls.append({'service':'FFU_UPDATE_MOCK_ONLY','device':hex(args[0]),'bytes':args[1],'payload':hex(args[3])});ret=update_status
  if a==0x13f8c:calls.append({'service':'RESET_INITIALIZE_MOCK_ONLY'})
  if a==0x13e78:calls.append({'service':'PRIVATE_RESET_MOCK_ONLY','reset_type':args[0]})
  if a==0x140f4:raise AssertionError('Unexpected stack-check failure')
  machine.reg_write(UC_ARM64_REG_X0,ret);machine.reg_write(UC_ARM64_REG_PC,machine.reg_read(UC_ARM64_REG_X30))
 u.hook_add(UC_HOOK_CODE,hook)
 for r,v in zip(regs,[0x200000,1,2,0]):u.reg_write(r,v)
 u.reg_write(UC_ARM64_REG_SP,0x400800);u.reg_write(UC_ARM64_REG_X30,0x500000)
 u.emu_start(0x2694,0x500004,count=30000);assert done,'Instruction budget exhausted'
 return {'inquiry_fixture':[vendor,product,revision],'calls':calls,'return':u.reg_read(UC_ARM64_REG_X0),'external_services_mocked':True,'physical_result':False}
def review():
 import pefile
 from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
 p=pefile.PE(data=PATH.read_bytes());m=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
 windows={hex(a):[(hex(i.address),i.mnemonic,i.op_str) for i in m.disasm(p.get_data(a,n),a)]
          for a,n in [(0x2e38,0x60),(0x29c0,0xe0),(0xd44c,0x54),(0x13f28,0x60)]}
 return {'sha256':SHA,'native_main_entry_rva':'0x2abc','conditional_ffu_call_rva':'0x2e70','ffu_entry_rva':'0x2694',
 'disassembly':windows,
 'cases':{'matching_old_revision':emulate(),
 'matching_samsung_fixture':emulate(vendor='SAMSUNG',product='KM8B8001JM-BC01',revision='0100'),
 'already_target_revision':emulate(revision='9QSV'),
 'unmatched_vendor':emulate(vendor='UNKNOWN'),'update_failure':emulate(update_status=1)},
 'conclusion':'Native StartImage is not a reviewed read-only operation. Fixture matches are NOT observations of this phone.'}
if __name__=='__main__':print(json.dumps(review(),indent=2))
