import gzip
import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('boot_image', ROOT/'Resources/BootTests/davinci_boot_image.py')
boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)


def fixture():
    # Small synthetic container; real 128 MiB input is separately round-tripped.
    raw=bytearray(64); raw[56:60]=b'ARMd'; struct.pack_into('<Q',raw,8,0x80000)
    fdt=struct.pack('>10I',0xd00dfeed,72,56,72,40,17,16,0,0,16)+bytes(16)+struct.pack('>4I',1,0,2,9)
    kernel=gzip.compress(raw,mtime=0)+fdt
    page=4096; body=bytearray(8192)
    body[:8]=b'ANDROID!'; struct.pack_into('<10I',body,8,len(kernel),0x8000,0,0x1000000,0,0xf00000,0x100,page,1,0x14000155)
    struct.pack_into('<IQI',body,1632,0,0,1648)
    body[576:608]=boot.android_id(kernel);body[4096:4096+len(kernel)]=kernel
    salt=bytes(32);h=hashlib.sha256(salt+body).digest()
    desc=struct.pack('>QQQ32s4I60s',2,184,len(body),b'sha256',4,32,32,0,bytes(60))+b'boot'+salt+h
    assert len(desc)==200
    vb=bytearray(512);vb[:4]=b'AVB0';struct.pack_into('>IIQQI',vb,4,1,0,0,256,0);struct.pack_into('>QQ',vb,96,0,200);vb[256:456]=desc
    image=bytes(body)+vb+bytes(32768-len(body)-len(vb)-64)+struct.pack('>4sIIQQQ28s',b'AVBf',1,0,len(body),len(body),len(vb),bytes(28))
    shim=bytearray(144);shim[56:60]=b'ARMd';struct.pack_into('<QQ',shim,8,0x9fc00000,0x300000)
    fd=bytearray(0x300000);struct.pack_into('<I',fd,0,0x14000040);fd[40:44]=b'_FVH';fd[100:134]=b'DAVINCI FIRST BOOT: PREPI REACHED'.ljust(34,b'\0')
    return image,bytes(shim),bytes(fd),fdt


class BootImageTests(unittest.TestCase):
    def setUp(self):
        self.patch=mock.patch.object(boot,'PARTITION_SIZE',32768);self.patch.start();self.addCleanup(self.patch.stop)
        self.original,self.shim,self.fd,self.fdt=fixture()

    def test_preserves_all_observed_header_fields_except_kernel_size_and_id(self):
        before=hashlib.sha256(self.original).digest()
        image,report=boot.package(self.original,self.shim,self.fd)
        a=bytearray(self.original[:4096]);b=bytearray(image[:4096])
        for buf in [a,b]:buf[8:12]=bytes(4);buf[576:608]=bytes(32)
        self.assertEqual(a,b);self.assertEqual(hashlib.sha256(self.original).digest(),before)
        self.assertEqual(struct.unpack_from('<I',image,20)[0],0x1000000)
        self.assertEqual(struct.unpack_from('<I',image,28)[0],0xf00000)
        self.assertFalse(report['new_avb_footer_present'])

    def test_generated_kernel_round_trips_shim_fd_and_original_dtb(self):
        image,report=boot.package(self.original,self.shim,self.fd)
        size=struct.unpack_from('<I',image,8)[0];kernel=image[4096:4096+size]
        d=__import__('zlib').decompressobj(31)
        self.assertEqual(d.decompress(kernel)+d.flush(),self.shim+self.fd)
        self.assertEqual(d.unused_data,self.fdt)
        self.assertEqual(image[576:608],boot.android_id(kernel))
        self.assertEqual(len(image)%4096,0)

    def test_rejects_bad_original_header_id_and_avb_hash(self):
        for offset in [576,8192+256+168]:
            b=bytearray(self.original);b[offset]^=1
            with self.assertRaises(ValueError):boot.inspect(b)

    def test_rejects_unreviewed_layout_or_shim(self):
        for offset,value in [(36,2048),(40,2),(16,1)]:
            b=bytearray(self.original);struct.pack_into('<I',b,offset,value)
            with self.assertRaises(ValueError):boot.inspect(b)
        shim=bytearray(self.shim);struct.pack_into('<Q',shim,8,0x80000)
        with self.assertRaises(ValueError):boot.package(self.original,shim,self.fd)

    def test_full_debug_fd_without_halt_marker_is_rejected(self):
        fd=bytearray(self.fd);fd[100:134]=bytes(34)
        with self.assertRaises(ValueError):boot.package(self.original,self.shim,fd)

    def test_windows_profile_requires_built_private_evidence(self):
        with self.assertRaisesRegex(ValueError, "matching built private evidence"):
            boot.package(self.original,self.shim,self.fd,"windows-boot-test")

    def test_fd_without_a_valid_entry_branch_is_rejected(self):
        for instruction in [0,0x14000000,0x15ffffff]:
            fd=bytearray(self.fd);struct.pack_into('<I',fd,0,instruction)
            with self.assertRaises(ValueError):boot.package(self.original,self.shim,fd)

    def test_fdt_extent_and_truncation_are_rejected(self):
        for data in [b'',self.fdt[:20],self.fdt[:4]+struct.pack('>I',1000)+self.fdt[8:]]:
            with self.assertRaises(ValueError):boot.fdt_blocks(data)


@unittest.skipUnless(importlib.util.find_spec('unicorn') and os.environ.get('DAVINCI_BOOTSHIM'), 'Actual compiled BootShim and optional Unicorn required')
class BootShimExecutionTests(unittest.TestCase):
    def test_actual_shim_relocates_payload_and_preserves_dtb_register(self):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn.arm64_const import UC_ARM64_REG_X0
        shim=Path(os.environ['DAVINCI_BOOTSHIM']).read_bytes()
        payload=bytes(range(256))*(0x300000//256)
        uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM);uc.mem_map(0x81000000,0x301000);uc.mem_map(0x9fc00000,0x300000)
        uc.mem_write(0x81000000,shim+payload);uc.reg_write(UC_ARM64_REG_X0,0x90000000)
        stopped=[]
        def hook(machine,address,size,context):stopped.append(True);machine.emu_stop()
        uc.hook_add(UC_HOOK_CODE,hook,begin=0x9fc00000,end=0x9fc00004)
        uc.emu_start(0x81000000,0x9fc00004,count=1000000)
        self.assertTrue(stopped);self.assertEqual(bytes(uc.mem_read(0x9fc00000,len(payload))),payload)
        self.assertEqual(uc.reg_read(UC_ARM64_REG_X0),0x90000000)

@unittest.skipUnless(importlib.util.find_spec('capstone') and importlib.util.find_spec('pefile') and os.environ.get('DAVINCI_PREPI_HALT_DLL'), 'Actual compiled halt SEC and optional disassembly tools required')
class FirstBootHaltCodeTests(unittest.TestCase):
    def test_compiled_entry_ends_in_unconditional_deadloop_cycle(self):
        import re
        import pefile
        from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
        dll=Path(os.environ['DAVINCI_PREPI_HALT_DLL'])
        text=dll.with_suffix('.map').read_text()
        symbols={name:int(address,16) for address,name in re.findall(r'^([0-9a-fA-F]{8}) 00000000\s+0\s+(\S+)\s*$',text,re.M)}
        start=symbols['CEntryPoint']; dead=symbols['CpuDeadLoop']
        end=min(value for value in symbols.values() if value>start)
        image=pefile.PE(data=dll.read_bytes())
        ops=list(Cs(CS_ARCH_ARM64,CS_MODE_ARM).disasm(image.get_data(start,end-start),start))
        self.assertEqual((ops[-2].mnemonic,ops[-2].op_str),('bl','#'+hex(dead)))
        self.assertEqual((ops[-1].mnemonic,ops[-1].op_str),('b','#'+hex(ops[-2].address)))

if __name__=='__main__':unittest.main()
