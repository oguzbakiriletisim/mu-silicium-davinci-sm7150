#!/usr/bin/env python3
"""Real built FV/PE/DEPEX inventory and zero-copy C RAW locator check, PC only."""
import argparse,ctypes,hashlib,json,lzma,struct,subprocess,tempfile,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FAT_GUID='0713cb3b-ea2e-4aa0-98ce-2e69902794d3'
LAUNCHER='99b114cc-292f-413b-b556-6e7ae4866d91'
def expanded_from_fd(fd):
 assert len(fd)==0x300000 and fd[40:44]==b'_FVH'
 end=struct.unpack_from('<Q',fd,32)[0];o=struct.unpack_from('<H',fd,48)[0]
 assert o>=56 and o<=end<=len(fd)
 while o+24<=end:
  if fd[o:o+24]==b'\xff'*24:break
  n=int.from_bytes(fd[o+20:o+23],'little');h=24
  if fd[o+19]&1:
   assert n==0 and o+32<=end
   n=struct.unpack_from('<Q',fd,o+24)[0];h=32
  assert h<=n<=end-o
  if uuid.UUID(bytes_le=fd[o:o+16])==uuid.UUID('9e21fd93-9c72-4c15-8c4b-e77f1db2d792'):
   p=o+h;sz=int.from_bytes(fd[p:p+3],'little')
   assert fd[p+3]==2 and 24<=sz<=n-h
   assert fd[p+4:p+20]==uuid.UUID('ee4e5898-3914-4259-9d6e-dc7bd79403cf').bytes_le
   assert struct.unpack_from('<HH',fd,p+20)==(24,1)
   d=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE);raw=d.decompress(fd[p+24:p+sz],max_length=64*1024*1024+8)
   assert d.eof and not d.unused_data and raw[3]==0x17
   sh=8 if raw[:3]==b'\xff'*3 else 4
   declared=struct.unpack_from('<I',raw,4)[0] if sh==8 else int.from_bytes(raw[:3],'little')
   assert declared==len(raw)
   return raw[sh:]
  o=(o+n+7)&~7
 raise AssertionError('Missing compressed main FV in actual FD')

def audit(folder):
 fd=(folder/'WINDOWS_BOOT_TEST.fd').read_bytes();b=(folder/'FVMAIN.Fv').read_bytes();image=(folder/'efi-fat32.img').read_bytes()
 assert expanded_from_fd(fd)==b,'FD compressed FV does not match audited FVMAIN'
 raw=(folder/'ram-disk.img').read_bytes() if (folder/'ram-disk.img').exists() else image
 size=struct.unpack_from('<Q',b,32)[0];head=struct.unpack_from('<H',b,48)[0]
 assert b[40:44]==b'_FVH' and size==len(b)
 assert sum(struct.unpack('<'+'H'*(head//2),b[:head]))%65536==0
 files={};apriori=[];tables=[];o=head
 while o+24<=len(b):
  if b[o:o+24]==b'\xff'*24:break
  g=str(uuid.UUID(bytes_le=b[o:o+16]));length=int.from_bytes(b[o+20:o+23],'little');h=24
  if b[o+19]&1:
   assert length==0
   h=32;length=struct.unpack_from('<Q',b,o+24)[0]
  assert length>=h and o+length<=len(b),(g,o,length)
  row={'type':b[o+18],'bytes':length};s=o+h
  while row["type"] not in (0xf0,0x01) and s+4<=o+length:
   n=int.from_bytes(b[s:s+3],'little');sh=4;kind=b[s+3]
   if n==0xffffff:n=struct.unpack_from('<I',b,s+4)[0];sh=8
   assert n>=sh and s+n<=o+length,(g,s,n)
   data=b[s+sh:s+n]
   if kind==0x10:
    pe=struct.unpack_from('<I',data,60)[0];assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',data,pe+4)[0]==0xaa64
    row['pe_machine']='0xaa64';row['pe_sha256']=hashlib.sha256(data).hexdigest()
    if g==LAUNCHER:
     assert b'W\0B\0T\0' in data
   if kind==0x13:row['depex']=data.hex()
   if kind==0x19 and g=='fc510ee7-ffdc-11d4-bd41-0080c73c8881':apriori=[str(uuid.UUID(bytes_le=data[i:i+16])) for i in range(0,len(data),16)]
   if kind==0x19 and g==FAT_GUID:assert data==raw;row['raw_sha256']=hashlib.sha256(data).hexdigest()
   if kind==0x19 and data[:4] in (b'DSDT',b'SSDT',b'FACP',b'APIC',b'GTDT',b'PPTT',b'IORT',b'FACS'):
    ntable=struct.unpack_from('<I',data,4)[0];assert ntable==len(data)
    if data[:4]!=b'FACS':assert sum(data)%256==0
    if g=='1b1961de-831c-4699-a7a7-385efc4e7706':
     assert data[:4]==b'SSDT' and b'_STA\x00\xa4\x00' in data
     assert b'_HID' not in data and b'_CID' not in data and b'_CCA' not in data
    tables.append({'signature':data[:4].decode(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'file_guid':g})
   s=(s+n+3)&~3
  files[g]=row;o=(o+length+7)&~7
 lock=json.loads((ROOT/'Resources/PreFinal/native-lock.json').read_text())
 assert all(x['guid'].lower() not in files for x in lock),'Native dependency or UFS unexpectedly packaged'
 assert FAT_GUID in files and LAUNCHER in files and LAUNCHER==apriori[-1]
 assert {'DSDT','SSDT','FACP','APIC','GTDT','PPTT'}<={t['signature'] for t in tables}
 assert not any(t['signature']=='IORT' for t in tables),'No guessed IORT mapping in this CPU-only test profile'
 env='90a49afd-422f-08ae-9611-e788d3804845'
 assert files[env]['pe_sha256']==hashlib.sha256((ROOT/'Binaries/davinci/QcomPkg/Drivers/EnvDxe/EnvDxe.efi').read_bytes()).hexdigest()
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp);c='''#include <stdint.h>
#include <stddef.h>
#define STATIC
#define CONST const
#define TRUE 1
#define FALSE 0
typedef uint8_t UINT8;typedef uint32_t UINT32;typedef uint64_t UINT64;typedef size_t UINTN;typedef int BOOLEAN;
'''
  (p/'c.c').write_text(c+'#include "'+str(ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/RamChecks.h')+'"\n#include "'+str(ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/RamGpt.h')+'"\n')
  subprocess.run(['cc','-shared','-fPIC',str(p/'c.c'),'-o',str(p/'c.so')],check=True)
  lib=ctypes.CDLL(str(p/'c.so'));lib.WbtRawFromFv.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_size_t)]
  buf=ctypes.create_string_buffer(b);guid=ctypes.create_string_buffer(uuid.UUID(FAT_GUID).bytes_le);data=ctypes.c_void_p();n=ctypes.c_size_t()
  assert lib.WbtRawFromFv(buf,len(b),guid,ctypes.byref(data),ctypes.byref(n))
  assert ctypes.string_at(data,n.value)==raw,'Actual firmware C RAW locator disagrees with built RAW image'
  if raw!=image:
   lib.WbtGptValid.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_size_t)]
   fat=ctypes.c_void_p();nf=ctypes.c_size_t()
   assert lib.WbtGptValid(data,n.value,ctypes.byref(fat),ctypes.byref(nf))
   assert ctypes.string_at(fat,nf.value)==image
   data,n=fat,nf
  lib.WbtFatValid.argtypes=[ctypes.c_void_p,ctypes.c_size_t];assert lib.WbtFatValid(data,n.value)
 return {'fd_sha256':hashlib.sha256(fd).hexdigest(),'fd_bytes':len(fd),'expanded_fv_bytes':len(b),
 'fat32_sha256':hashlib.sha256(image).hexdigest(),'fat32_bytes':len(image),'ram_disk_bytes':len(raw),'ram_disk_sha256':hashlib.sha256(raw).hexdigest(),'fd_decompressed_fv_matches_audited_fv':True,'zero_copy_fat_locator_host_verified':True,
 'all_native_ufs_and_dependencies_absent':True,'env_binary_unchanged':True,'launcher_last_in_apriori':True,'files':files,'apriori':apriori,'acpi_tables':tables,
 'dxe_heap_bytes':0x4500000,'expanded_fv_fraction_of_dxe_heap':len(b)/0x4500000,
 'runtime_protocol_installation_tested':False,'microsoft_execution_measured_by_this_static_audit':False,'physical_test_ready':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('folder',type=Path);a=p.parse_args();print(json.dumps(audit(a.folder),indent=2))
