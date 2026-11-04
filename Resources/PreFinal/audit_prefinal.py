#!/usr/bin/env python3
"""Inspect the real generated FV; not a hardware test."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid
from uefi_firmware.uefi import FirmwareVolume


def audit(fd, root):
    data=fd.read_bytes();offset=data.find(b'_FVH')-40
    if offset < 0: raise ValueError('No FV')
    fv=FirmwareVolume(data[offset:])
    if not fv.valid_header or not fv.process():raise ValueError('FV parse failed')
    lock=json.loads((root/'Resources/PreFinal/native-lock.json').read_text())
    expected={x['guid'].lower():x for x in lock}
    apriori=[];files={};pe={};depex={}
    def walk(nodes):
        for node in nodes:
            g=node.get('guid','').lower();kind=node.get('attrs',{}).get('type')
            if node['type']=='FirmwareFile':files[g]=kind
            if node['type']=='FirmwareFileSystemSection':
                raw=getattr(node['_self'],'data',b'')
                if g=='fc510ee7-ffdc-11d4-bd41-0080c73c8881' and kind==25:
                    if len(raw)%16:raise ValueError('Bad APRIORI')
                    apriori.extend(str(uuid.UUID(bytes_le=raw[i:i+16])) for i in range(0,len(raw),16))
                if kind==16:
                    pos=struct.unpack_from('<I',raw,60)[0]
                    if raw[:2]!=b'MZ' or raw[pos:pos+4]!=b'PE\0\0' or struct.unpack_from('<H',raw,pos+4)[0]!=0xaa64:
                        raise ValueError('Non-ARM64 PE')
                    pe[g]=hashlib.sha256(raw).hexdigest()
                if kind==19:depex[g]=raw.hex()
            walk(node.get('objects',[]))
    walk(fv.iterate_objects())
    for g,x in expected.items():
        if files.get(g)!=2 or pe.get(g)!=x['sha256']:raise ValueError('Native PE not unchanged FREEFORM: '+x['name'])
        # INF basename sometimes differs from EFI basename; use actual adjacent DEPEX.
        matches=list((root/x['path']).parent.glob('*.depex'))
        if len(matches)!=1 or depex.get(g)!=matches[0].read_bytes().hex():raise ValueError('DEPEX mismatch')
        if g in apriori:raise ValueError('Native PE automatically dispatched')
    coordinator='5b887735-83a6-4876-8741-96cc8fe39b9d'
    if coordinator not in apriori or coordinator not in pe:raise ValueError('Coordinator missing')
    forbidden={'HALIOMMU':'9a00771f-36d4-4dd5-8916-c48ed9b16b86',
               'UefiBds':'6d33944a-ec75-4855-a54d-809c75241f6c',
               'PartitionDxe':'1fa1f39e-feff-4aae-bd7b-38a070a3b609'}
    for name,g in forbidden.items():
        if g in files:raise ValueError('Forbidden profile component '+name)
    return dict(fd_sha256=hashlib.sha256(data).hexdigest(),arm64_pe_count=len(pe),
                unchanged_manual_native_images=len(expected),apriori=apriori,files=files,
                native_pe_sha256=pe,native_depex=depex,
                coordinator_in_apriori=True,native_images_not_auto_dispatched=True,
                hal_dummy_driver_absent=True,physical_validation=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('fd',type=Path);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);a=p.parse_args()
    print(json.dumps(audit(a.fd,a.root),indent=2))
