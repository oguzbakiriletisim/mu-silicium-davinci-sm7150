#!/usr/bin/env python3
"""PC-only roundtrip of the actual backup, shim, FD and Android image."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('davinci_boot',ROOT/'Resources/BootTests/davinci_boot_image.py')
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)


def validate(backup_path, directory):
    original_zip_sha=hashlib.sha256(backup_path.read_bytes()).hexdigest()
    backup=boot.read_backup(backup_path)
    original_report,dtbs=boot.inspect(backup)
    shim=(directory/'BootShim.bin').read_bytes();fd=(directory/'DAVINCI_PREFINAL.fd').read_bytes()
    img=(directory/'davinci-prefinal-experimental.img').read_bytes()
    rebuilt,report=boot.package(backup,shim,fd,'prefinal')
    assert rebuilt==img,'Repack differs'
    page=original_report['header']['page_size'];size=struct.unpack_from('<I',img,8)[0]
    d=zlib.decompressobj(31);raw=d.decompress(img[page:page+size])+d.flush()
    assert raw==shim+fd and d.unused_data==dtbs
    before=bytearray(backup[:page]);after=bytearray(img[:page])
    for b in (before,after): b[8:12]=bytes(4);b[576:608]=bytes(32)
    assert before==after
    assert img[576:608]==boot.android_id(img[page:page+size])
    assert b'DAVINCI FIRST BOOT: PREPI REACHED' not in fd
    assert b'PREPI: PASS; NEXT DXE (NOT YET VERIFIED)' in fd
    assert original_zip_sha==hashlib.sha256(backup_path.read_bytes()).hexdigest()
    return dict(image_sha256=hashlib.sha256(img).hexdigest(),image_size=len(img),
                fd_sha256=hashlib.sha256(fd).hexdigest(),
                exact_repack_matches=True,shim_and_fd_roundtrip=True,original_dtbs_byte_exact=True,
                original_header_preserved_except_kernel_size_and_id=True,
                original_zip_unchanged=True,android_image_id_valid=True,
                original_header=original_report['header'],
                previous_transport_success='USER_REPORTED: previous first-entry image booted on davinci',
                new_image_physical_validation=False,
                hal_iommu_native_initialization_enabled=False,
                ufs_enabled_only_on_strict_inherited_explicit_bypass=True,
                windows_deployment_allowed=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backup',type=Path,required=True);p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    print(json.dumps(validate(a.backup,a.directory),indent=2))
