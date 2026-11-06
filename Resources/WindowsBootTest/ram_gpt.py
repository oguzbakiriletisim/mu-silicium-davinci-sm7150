#!/usr/bin/env python3
"""PC-only contiguous virtual GPT around unmodified FAT bytes. No phone disk operations."""
import hashlib,struct,uuid,zlib
def virtual_gpt(image):
    """Synthetic RAM disk container; never a phone partition template."""
    sectors=81920;first=2048;last=first+len(image)//512-1
    disk=bytearray(sectors*512);disk[first*512:(last+1)*512]=image
    entry=bytearray(128*128)
    entry[:16]=uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le
    entry[16:32]=uuid.uuid5(uuid.NAMESPACE_OID,hashlib.sha256(image).hexdigest()).bytes_le
    struct.pack_into('<QQQ',entry,32,first,last,0)
    name='HOST REFERENCE ONLY'.encode('utf-16le');entry[56:56+len(name)]=name
    disk[2*512:2*512+len(entry)]=entry;disk[(sectors-33)*512:(sectors-1)*512]=entry
    for lba,backup,table in ((1,sectors-1,2),(sectors-1,1,sectors-33)):
        h=bytearray(512);h[:8]=b'EFI PART'
        struct.pack_into('<IIIIQQQQ',h,8,0x10000,92,0,0,lba,backup,34,sectors-34)
        h[56:72]=uuid.uuid5(uuid.NAMESPACE_OID,'host-reference-'+hashlib.sha256(image).hexdigest()).bytes_le
        struct.pack_into('<QIII',h,72,table,128,128,zlib.crc32(entry))
        struct.pack_into('<I',h,16,zlib.crc32(h[:92]));disk[lba*512:(lba+1)*512]=h
    disk[446:462]=struct.pack('<B3sB3sII',0,b'\x00\x02\x00',0xee,b'\xff'*3,1,sectors-1)
    disk[510:512]=b'\x55\xaa'
    return disk


if __name__=="__main__":
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("fat",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    data=a.fat.read_bytes()
    if len(data)!=36*1024*1024:raise ValueError("Expected verified 36 MiB FAT")
    if a.output.resolve().is_relative_to(Path(__file__).resolve().parents[2]):raise ValueError("Keep Microsoft files outside Git")
    with a.output.open("xb") as f:f.write(virtual_gpt(data))
