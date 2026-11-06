"""Reject malformed untrusted FAT/ZIP input; no Microsoft payload required."""
import importlib.util
import struct
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'Resources/WindowsBootTest' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
fat = load('target_fat', 'fat32.py')
verify = load('target_verify', 'verify_target_a.py')
class TargetInput(unittest.TestCase):
    def test_long_names_and_exact_file_bytes(self):
        files = {'EFI/Microsoft/Boot/long resource name.bin': b'not Microsoft', 'EMPTY.TXT': b''}
        self.assertEqual(verify.fat_files(fat.create(files)), files)
    def test_fat_mirror_disagreement(self):
        image = fat.create({'TEST.TXT': b'content'})
        image[32*512+8] ^= 1
        with self.assertRaisesRegex(AssertionError, 'mirrors'):
            verify.fat_files(image)
    def test_cyclic_directory_chain(self):
        image = fat.create({'TEST.TXT': b'content'})
        fatsz = verify.u32(image,36)
        for offset in (32*512, (32+fatsz)*512):
            struct.pack_into('<I', image, offset+8, 2)
        with self.assertRaisesRegex(AssertionError, 'cyclic'):
            verify.fat_files(image)
    def test_lfn_checksum_rejected(self):
        image = fat.create({'very long filename.bin': b'content'})
        base=(32+2*verify.u32(image,36))*512
        self.assertEqual(image[base+11], 15)
        image[base+13] ^= 1
        with self.assertRaises(AssertionError):
            verify.fat_files(image)
    def test_lfn_missing_initial_rejected(self):
        image=fat.create({'very long filename.bin': b'content'})
        base=(32+2*verify.u32(image,36))*512
        image[base] &= ~0x40
        with self.assertRaisesRegex(AssertionError, 'initial'):
            verify.fat_files(image)
    def test_truncated_declared_file_size_rejected(self):
        image=fat.create({'TEST.TXT': b'content'})
        base=(32+2*verify.u32(image,36))*512
        offset=base
        while image[offset+11]==15: offset+=32
        struct.pack_into('<I',image,offset+28,513)
        with self.assertRaisesRegex(AssertionError, 'shorter'):
            verify.fat_files(image)
if __name__ == '__main__': unittest.main()
