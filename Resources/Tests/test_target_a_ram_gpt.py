"""Cross-check Python GPT construction with firmware C validation and corruptions."""
import ctypes, importlib.util, struct, subprocess, tempfile, unittest, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'Resources/WindowsBootTest'/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class RamGpt(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name);h=ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe'
  (p/'g.c').write_text('''#include <stdint.h>
#include <stddef.h>
#define STATIC
#define CONST const
#define TRUE 1
#define FALSE 0
typedef uint8_t UINT8;typedef uint32_t UINT32;typedef uint64_t UINT64;typedef size_t UINTN;typedef int BOOLEAN;
#include "'''+str(h/'RamChecks.h')+'"\n#include "'+str(h/'RamGpt.h')+'"\n')
  subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror',str(p/'g.c'),'-o',str(p/'g.so')],check=True)
  cls.c=ctypes.CDLL(str(p/'g.so'));cls.c.WbtGptValid.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_size_t)]
  cls.fat=load('fat32').create({'EFI/Microsoft/Boot/README.TXT':b'not an EFI image'})
  cls.image=load('ram_gpt').virtual_gpt(cls.fat)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def valid(self,image):
  buf=(ctypes.c_uint8*len(image)).from_buffer(image);p=ctypes.c_void_p();n=ctypes.c_size_t()
  ok=self.c.WbtGptValid(buf,len(image),ctypes.byref(p),ctypes.byref(n))
  if ok:self.assertEqual(ctypes.string_at(p,n.value),self.fat)
  return ok
 def test_valid_primary_backup_crc_and_original_fat_bytes(self):
  self.assertTrue(self.valid(self.image))
  for lba in (1,len(self.image)//512-1):
   h=bytearray(self.image[lba*512:lba*512+92]);expected=struct.unpack_from('<I',h,16)[0];struct.pack_into('<I',h,16,0)
   self.assertEqual(expected,zlib.crc32(h))
 def test_corrupt_mbr_header_entries_backup_and_fat_rejected(self):
  for offset in (450,512+16,1024+32,len(self.image)-512+88,2048*512+510):
   with self.subTest(offset=offset):
    self.image[offset]^=1
    try:self.assertFalse(self.valid(self.image))
    finally:self.image[offset]^=1
 def test_truncated_or_plain_fat_rejected(self):
  self.assertFalse(self.valid(self.fat));self.assertFalse(self.valid(self.image[:-512]))
if __name__=='__main__':unittest.main()
