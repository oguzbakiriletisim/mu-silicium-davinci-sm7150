"""Execute the production C safety/GPT checks against adversarial fixtures."""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import uuid
import zlib
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Resources/PreFinal'))
import preflight


def fixture(sector=4096):
    size=64*1024*1024
    last=size//sector-1
    disk, win, esp = [uuid.uuid4() for _ in range(3)]
    entries=bytearray(128*128)
    def part(i, kind, identity, start, end, name):
        o=i*128
        entries[o:o+16]=uuid.UUID(kind).bytes_le
        entries[o+16:o+32]=identity.bytes_le
        struct.pack_into('<3Q',entries,o+32,start,end,0)
        entries[o+56:o+56+len(name)*2]=name.encode('utf-16-le')
    part(0,preflight.windows.BASIC_TYPE,win,1024,4095,'win')
    part(1,preflight.windows.ESP_TYPE,esp,4096,8191,'esp')
    def hdr(lba,other,array):
        h=bytearray(sector);h[:8]=b'EFI PART'
        struct.pack_into('<4I4Q',h,8,0x10000,92,0,0,lba,other,256,last-256)
        h[56:72]=disk.bytes_le
        struct.pack_into('<Q3I',h,72,array,128,128,zlib.crc32(entries))
        struct.pack_into('<I',h,16,zlib.crc32(h[:92]))
        return h
    a,b=bytearray(1048576),bytearray(1048576)
    a[sector:2*sector]=hdr(1,last,2)
    a[2*sector:2*sector+len(entries)]=entries
    array=last-len(entries)//sector
    pos=array*sector-(size-len(b))
    b[pos:pos+len(entries)]=entries
    b[-sector:]=hdr(last,1,array)
    return a,b,sector,size,str(disk),str(win),str(esp),entries


class PreFinalCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); root=Path(cls.tmp.name)
        source=root/'checks.c'
        header=ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/ReadOnlyChecks.h'
        source.write_text('''#include <stdint.h>
#include <stddef.h>
#define STATIC
#define CONST const
#define TRUE 1
#define FALSE 0
typedef uint8_t UINT8; typedef uint32_t UINT32; typedef uint64_t UINT64;
typedef size_t UINTN; typedef int BOOLEAN;
#include "'''+str(header)+'"\n')
        subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',str(source),'-o',str(root/'checks.so')],check=True)
        cls.c=ctypes.CDLL(str(root/'checks.so'))
        cls.c.StreamsBypass.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint32),ctypes.c_size_t]
        cls.c.ValidGptHeader.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint64,ctypes.c_uint64]
        cls.c.ValidEntries.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint64,ctypes.c_uint64]
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def bypass(self,smr=None,s2cr=None,idr=None,cr0=0,count=16):
        smr=smr or [0x80000300+i for i in range(16)]
        s2cr=s2cr or [0x10000]*16
        return bool(self.c.StreamsBypass(idr if idr is not None else (1<<27)|count,cr0,(ctypes.c_uint32*len(smr))(*smr),(ctypes.c_uint32*len(s2cr))(*s2cr),count))
    def test_unique_explicit_inherited_bypass_passes(self): self.assertTrue(self.bypass())
    def test_mask_covering_whole_range_passes(self): self.assertTrue(self.bypass([0x800f0300],[0x10000],count=1))
    def test_translation_fault_and_unknown_types_are_rejected(self):
        for kind in [0,2,3]: self.assertFalse(self.bypass(s2cr=[kind<<16]*16))
    def test_unmatched_duplicate_disabled_and_exids_are_rejected(self):
        self.assertFalse(self.bypass(smr=[0]*16))
        self.assertFalse(self.bypass(smr=[0x800f0300]*16))
        self.assertFalse(self.bypass(cr0=1))
        self.assertFalse(self.bypass(idr=(1<<27)|(1<<8)|16))
        self.assertFalse(self.bypass(idr=16))
        self.assertFalse(self.bypass(idr=(1<<27)|1))
    def test_header_crc_geometry_and_restore(self):
        a,b,s,size,*_=fixture();h=bytes(a[s:2*s]);buf=ctypes.create_string_buffer(h)
        self.assertTrue(self.c.ValidGptHeader(buf,s,1,size//s-1));self.assertEqual(buf.raw[:s],h)
        for offset in [0,8,12,16,20,24,32,40,72,80,84,88]:
            bad=bytearray(h);bad[offset]^=1
            self.assertFalse(self.c.ValidGptHeader(ctypes.create_string_buffer(bytes(bad)),s,1,size//s-1))
    def test_entries_reject_overlap_zero_guid_and_duplicate(self):
        *_,entries=fixture()
        def check(b):return self.c.ValidEntries(ctypes.create_string_buffer(bytes(b)),128,128,256,16000)
        self.assertTrue(check(entries))
        for mutate in ['overlap','zero','duplicate','extent']:
            b=bytearray(entries)
            if mutate=='overlap':struct.pack_into('<Q',b,128+32,3000)
            if mutate=='zero':b[16:32]=bytes(16)
            if mutate=='duplicate':b[144:160]=b[16:32]
            if mutate=='extent':struct.pack_into('<Q',b,32,0)
            self.assertFalse(check(b),mutate)


class PreflightTests(unittest.TestCase):
    def test_dual_backup_512_and_4096_and_target_guid(self):
        for sector in [512,4096]:
            a,b,s,size,d,w,e,_=fixture(sector)
            layout=preflight.parse_backups(a,b,s,size)
            self.assertEqual(preflight.select(layout,d,w,e)['windows']['name'],'win')
            self.assertFalse(layout['backups_current_on_phone'])
    def test_header_and_array_corruption_are_rejected(self):
        a,b,s,size,*_=fixture()
        for offset in [s, s+16, 2*s+40]:
            bad=bytearray(a);bad[offset]^=1
            with self.assertRaises(ValueError):preflight.parse_backups(bad,b,s,size)
        with self.assertRaises(ValueError):preflight.parse_backups(a,b,s,size+s)
    def test_wrong_disk_guid_missing_esp_and_win_esp_swap_fail(self):
        a,b,s,size,d,w,e,_=fixture();layout=preflight.parse_backups(a,b,s,size)
        for ids in [(str(uuid.uuid4()),w,e),(d,w,str(uuid.uuid4())),(d,e,w),(d,w,w)]:
            with self.assertRaises(ValueError):preflight.select(layout,*ids)
    def test_no_driver_is_not_invented_as_supported(self):
        self.assertFalse(preflight.drivers(None)['compatible_boot_start_ufs_verified'])
    def test_deployment_switch_never_enables_a_write_path(self):
        code=(ROOT/'Resources/PreFinal/Deploy-AfterApproval.ps1').read_text()
        self.assertIn('throw ',code);self.assertIn('$ApproveDeployment',code)
        for forbidden in ['Format-Volume','Clear-Disk','Initialize-Disk','dism.exe','WriteAllBytes','Copy-Item']:
            self.assertNotIn(forbidden,code)


class PreFinalProfileTests(unittest.TestCase):
    def test_native_binary_locks_and_no_hal_auto_dispatch(self):
        locks=json.loads((ROOT/'Resources/PreFinal/native-lock.json').read_text())
        for x in locks:self.assertEqual(hashlib.sha256((ROOT/x['path']).read_bytes()).hexdigest(),x['sha256'])
        fdf=(ROOT/'Platforms/Xiaomi/davinciPkg/Include/PREFINAL.inc').read_text()
        for name in ['HALIOMMUDxe.inf','PartitionDxe.inf','BdsDxe.inf','ScmDxeLA.inf','Fat.inf']:
            self.assertNotIn(name,fdf)
        for x in locks:self.assertIn('FILE FREEFORM = '+x['guid'],fdf)
    def test_packaging_requires_explicit_correct_profile(self):
        sys.path.insert(0,str(ROOT/'Resources/Tests'))
        from test_davinci_boot_image import fixture,boot
        from unittest.mock import patch
        backup,shim,fd,dtb=fixture();fd=bytearray(fd);fd[100:134]=bytes(34)
        marker=b'PREPI: PASS; NEXT DXE (NOT YET VERIFIED)';fd[200:200+len(marker)]=marker
        with patch.object(boot,'PARTITION_SIZE',32768):
            image,report=boot.package(backup,shim,bytes(fd),'prefinal')
            self.assertEqual(report['profile'],'prefinal')
            with self.assertRaises(ValueError):boot.package(backup,shim,bytes(fd))
            with self.assertRaises(ValueError):boot.package(backup,shim,bytes(fd),'unknown')


# Native PowerShell syntax and denial paths; no Storage cmdlets are invoked.
import os
@unittest.skipUnless(os.environ.get('DAVINCI_PWSH'), 'Optional PowerShell runtime unavailable')
class PreFinalPowerShellTests(unittest.TestCase):
    def test_approval_and_forged_json_never_authorize_missing_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'preflight.json';d,w,e=[str(uuid.uuid4()) for _ in range(3)]
            p.write_text(json.dumps(dict(schema_version=1,deployment_allowed=True,layout=dict(disk_guid=d),
                         selected=dict(windows=dict(guid=w),esp=dict(guid=e)))))
            before=p.read_bytes()
            common=[os.environ['DAVINCI_PWSH'],'-NoProfile','-NonInteractive','-File',
                    str(ROOT/'Resources/PreFinal/Deploy-AfterApproval.ps1'),'-PreflightJson',str(p),
                    '-DiskGuid',d,'-WindowsPartitionGuid',w,'-EspPartitionGuid',e]
            for extra,match in [([], 'Ayri dagitim onayi'), (['-ApproveDeployment'], 'DAGITIM ENGELLI')]:
                result=subprocess.run(common+extra,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(match,result.stderr)
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual([f.name for f in Path(tmp).iterdir()],['preflight.json'])

if __name__=='__main__':unittest.main()
