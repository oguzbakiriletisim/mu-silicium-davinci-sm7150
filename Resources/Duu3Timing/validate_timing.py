#!/usr/bin/env python3
"""Audit exact boot repacks and the compiled DUU3 stop/delay/module ceiling."""
import argparse,json,hashlib,importlib.util
from pathlib import Path
from uefi_firmware.uefi import FirmwareVolume
ROOT=Path(__file__).resolve().parents[2]
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
boot=mod('boot',ROOT/'Resources/BootTests/davinci_boot_image.py')
audit=mod('audit',ROOT/'Resources/PreFinal/audit_prefinal.py')
PROFILES={
 'ufs-before-slow':('0xB0C6',1000000,12),
 'ufs-before-fast':('0xB0C6',0,12),
 'ufs-loaded':('0xB0C5',1000000,12)}
def verify(folder,profile,backup):
 stop,delay,ceiling=profile
 fd=(folder/'DAVINCI_PREFINAL.fd').read_bytes();image=(folder/'davinci-prefinal-experimental.img').read_bytes()
 repack,_=boot.package(backup,(folder/'BootShim.bin').read_bytes(),fd,'prefinal')
 assert repack==image
 f=FirmwareVolume(fd);assert f.process();raw=[]
 def walk(ns):
  for n in ns:
   if n['type']=='FirmwareFileSystemSection' and n.get('guid','').lower()=='5b887735-83a6-4876-8741-96cc8fe39b9d' and n.get('attrs',{}).get('type')==16:raw.append(n['_self'].data)
   walk(n.get('objects',[]))
 walk(f.iterate_objects());assert len(raw)==1
 literal=f'DUU3_STOP={stop}_DELAY={delay}_MAX={ceiling}'
 assert literal.encode()+b'\0' in raw[0],literal
 # At max12 all valid indices fit, so the compiler removes the generic
 # ceiling branch. The mandatory UFS entry barrier must remain instead.
 if ceiling<12:assert b'MODULE CEILING / HAL-UFS DISALLOWED' in raw[0]
 else:assert b'UFSDxe START FORBIDDEN / CONTROLLED STOP' in raw[0]
 return dict(stop=stop,delay_us=delay,max_native=ceiling,compiled_literal=literal,
             image_sha256=hashlib.sha256(image).hexdigest(),image_bytes=len(image),exact_repack=True,
             fd_audit=audit.audit(folder/'DAVINCI_PREFINAL.fd',ROOT),physical_validation=False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--backup',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True)
 p.add_argument('--profiles',nargs='+',choices=PROFILES,default=list(PROFILES));a=p.parse_args()
 backup=boot.read_backup(a.backup)
 print(json.dumps({n:verify(Path(str(a.prefix)+'-'+n),PROFILES[n],backup) for n in a.profiles},indent=2))
