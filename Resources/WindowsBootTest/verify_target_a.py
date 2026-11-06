# SPDX-License-Identifier: BSD-2-Clause-Patent
#!/usr/bin/env python3
"""Host-only inspection of Target A Windows EFI ZIP and its FAT32 filesystem.
No disk mounting, phone operation, registry change, or GitHub upload.
"""
import argparse,hashlib,json,struct,zipfile
if not __debug__: raise RuntimeError("Verification requires Python assertions enabled; do not use -O")
from pathlib import Path

def sha(x): return hashlib.sha256(x).hexdigest()
def u16(b,o):return struct.unpack_from('<H',b,o)[0]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]

def fat_files(img):
    assert len(img)==37748736, 'Unexpected FAT image size'
    bps=u16(img,11); spc=img[13]; reserved=u16(img,14); nfats=img[16]
    sectors=u32(img,32); fatsz=u32(img,36); root=u32(img,44)
    assert img[510:512]==b'\x55\xaa' and img[82:90]==b'FAT32   '
    assert bps==512 and spc==1 and reserved==32 and nfats==2 and sectors*bps==len(img)
    assert root==2 and fatsz>0
    fat=img[reserved*bps:(reserved+fatsz)*bps]
    assert fat==img[(reserved+fatsz)*bps:(reserved+2*fatsz)*bps], "FAT mirrors disagree"
    clusters=sectors-reserved-nfats*fatsz
    assert 65525<=clusters and (clusters+2)*4<=len(fat)
    base=(reserved+nfats*fatsz)*bps
    def chain(c):
        seen=set()
        while 2<=c<=clusters+1:
            assert c not in seen and len(seen)<sectors, 'Invalid/cyclic FAT'
            seen.add(c)
            off=base+(c-2)*bps*spc
            assert off>=base and off+bps*spc<=len(img), 'Cluster outside image'
            yield img[off:off+bps*spc]
            assert c*4+4<=len(fat)
            c=u32(fat,c*4)&0x0fffffff
        assert c>=0x0ffffff8, "Free/bad/reserved cluster terminator"
    found={}; seen_dirs=set(); folded=set()
    def walk(folder,prefix='',depth=0):
        assert depth<16 and folder not in seen_dirs, "Cyclic/shared directory"
        seen_dirs.add(folder)
        data=b''.join(chain(folder));lfn=[]
        for i in range(0,len(data),32):
            e=data[i:i+32]
            if len(e)<32 or e[0]==0:break
            if e[0]==0xe5:lfn=[];continue
            if e[11]==0x0f:
                ordinal=e[0]&0x1f
                assert lfn or e[0]&0x40, "LFN sequence missing initial entry"
                assert 1<=ordinal<=20 and e[12]==0 and u16(e,26)==0
                if e[0]&0x40:
                    assert not lfn
                    expected_ordinal=ordinal
                    lfn_checksum=e[13]
                assert ordinal==expected_ordinal and e[13]==lfn_checksum
                expected_ordinal-=1
                units=[u16(e,o) for o in (1,3,5,7,9,14,16,18,20,22,24,28,30)]
                lfn.insert(0,units);continue
            if e[11]&8:lfn=[];continue
            if lfn:
                checksum=0
                for value in e[:11]:checksum=(((checksum&1)<<7)+(checksum>>1)+value)&255
                assert expected_ordinal==0 and checksum==lfn_checksum, "Bad LFN checksum/order"
                flattened=[u for part in lfn for u in part]
                units=[]
                for c in flattened:
                    if c in (0,0xffff):break
                    units.append(c)
                name=b''.join(struct.pack('<H',c) for c in units).decode('utf-16le')
            else:
                name=e[:8].decode('ascii').rstrip()+('.'+e[8:11].decode('ascii').rstrip() if e[8:11].strip() else '')
            lfn=[]
            if name in ('.','..'):continue
            assert name and not any(x in name for x in ('/','\\',':','\x00')), 'Unsafe FAT filename'
            cl=(u16(e,20)<<16)|u16(e,26)
            path=prefix+name
            assert path.casefold() not in folded, 'Duplicate FAT name'
            folded.add(path.casefold())
            if e[11]&0x10:walk(cl,path+'/',depth+1)
            else:
                size=u32(e,28)
                content=b''.join(chain(cl)) if cl else b''
                assert size<=len(content), 'File shorter than declared size'
                found[path]=content[:size]
    walk(root)
    return found

def validate(archive):
    with zipfile.ZipFile(archive) as z:
        assert len(z.infolist())==3 and len({x.filename for x in z.infolist()})==3, 'Duplicate/unexpected ZIP entries'
        assert sum(x.file_size for x in z.infolist())<40*1024*1024, 'Oversized input ZIP'
        assert z.testzip() is None, 'ZIP CRC failed'
        assert set(z.namelist())=={'efi-fat32.img','FAT_MANIFEST.json','AUTHENTICODE.json'},'Unexpected ZIP entries'
        img=z.read('efi-fat32.img')
        manifest=json.loads(z.read('FAT_MANIFEST.json').decode('utf-8-sig'))
        auth=json.loads(z.read('AUTHENTICODE.json').decode('utf-8-sig'))
    assert len(img)==manifest['image_bytes']
    assert sha(img)==manifest['sha256'].lower(), 'Image SHA does not match manifest'
    assert manifest['fat32'] and manifest['microsoft_payload_present']
    found=fat_files(img)
    expected=manifest['files']
    assert set(found)==set(expected), f'File set mismatch: found {sorted(found)}, expected {sorted(expected)}'
    for name,value in found.items():
        assert sha(value)==expected[name].lower(),f'File SHA mismatch: {name}'
    pe=found['EFI/Microsoft/Boot/bootmgfw.efi']
    assert len(pe)>=64 and pe[:2]==b'MZ'; pos=u32(pe,0x3c)
    assert len(pe)>=64 and pos<=len(pe)-26
    assert u16(pe,pos+24)==0x20b, 'Not PE32+'
    assert pe[pos:pos+4]==b'PE\0\0' and u16(pe,pos+4)==0xaa64,'Not ARM64 Windows Boot Manager'
    assert sha(pe)==auth['bootmgfw_sha256'].lower()
    assert found['EFI/Boot/bootaa64.efi']==pe
    assert auth['signature_status']=='Valid' and 'Microsoft' in auth['signer_subject'], 'Host Authenticode report not valid'
    return {'zip_sha256':sha(Path(archive).read_bytes()),'fat32_sha256':sha(img),'image_bytes':len(img),'efi_file_count':len(found),'all_manifest_file_hashes_verified':True,'bootmgfw_sha256':sha(pe),'pe_machine':'0xAA64','authenticode_windows_report':auth['signature_status'],'authenticode_independent_trust_chain_verified':False,'bcd_present':'EFI/Microsoft/Boot/BCD' in found,'physical_boot_verified':False}, img

def main():
    p=argparse.ArgumentParser();p.add_argument('input_zip',type=Path);p.add_argument('--output',type=Path,help='New directory to extract verified FAT image and report')
    args=p.parse_args();report,img=validate(args.input_zip)
    if args.output:
        repo=Path(__file__).resolve().parents[2]
        if args.output.resolve().is_relative_to(repo):raise ValueError('Keep Microsoft input outside the Git working tree')
        args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'efi-fat32.img').write_bytes(img)
        (args.output/'VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
