#!/usr/bin/env python3
"""Verify delivered stop profile literals, native PE hashes and boot roundtrip."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from uefi_firmware.uefi import FirmwareVolume
ROOT=Path(__file__).resolve().parents[2]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
boot=module('boot',ROOT/'Resources/BootTests/davinci_boot_image.py')
audit=module('audit',ROOT/'Resources/PreFinal/audit_prefinal.py')
def verify(directory,stop,backup):
 image=(directory/'davinci-prefinal-experimental.img').read_bytes();fd=(directory/'DAVINCI_PREFINAL.fd').read_bytes()
 shim=(directory/'BootShim.bin').read_bytes()
 repacked,manifest=boot.package(backup,shim,fd,'prefinal')
 if repacked!=image:raise ValueError('Android image differs from exact repack')
 result=audit.audit(directory/'DAVINCI_PREFINAL.fd',ROOT)
 f=FirmwareVolume(fd);assert f.process()
 raw=[]
 def walk(nodes):
  for n in nodes:
   if n['type']=='FirmwareFileSystemSection' and n.get('guid','').lower()=='5b887735-83a6-4876-8741-96cc8fe39b9d' and n.get('attrs',{}).get('type')==16:
    raw.append(n['_self'].data)
   walk(n.get('objects',[]))
 walk(f.iterate_objects())
 if len(raw)!=1:raise ValueError('Photo coordinator not unique')
 literal=('DUU2_STOP='+stop).encode()
 if literal+b'\0' not in raw[0]:raise ValueError('Wrong compiled stop literal: '+repr(literal))
 for text in [b'RESET_SYSTEM REQUEST CAPTURED',b'EXCEPTION type=',b'IDR / CR0: UNREAD',b'SCTLR: UNREAD']:
  if text not in raw[0]:raise ValueError('Required photo diagnostic missing: '+repr(text))
 if bytes.fromhex('7f2003d5') not in raw[0]:raise ValueError('No AARCH64 WFI in coordinator')
 return dict(image_sha256=hashlib.sha256(image).hexdigest(),image_bytes=len(image),stop_literal=literal.decode(),
             profile='DUU2_PHOTO',exact_boot_repack=True,original_header_and_dtbs_preserved=True,
             fd_audit=result,physical_test_performed=False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--backup',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
 backup=boot.read_backup(a.backup)
 profiles={'baseline':'0xD010','auto':'0','before-hal':'0xB0B6','before-ufs':'0xB0C6'}
 print(json.dumps({n:verify(Path(str(a.root)+'-'+n),s,backup) for n,s in profiles.items()},indent=2))
