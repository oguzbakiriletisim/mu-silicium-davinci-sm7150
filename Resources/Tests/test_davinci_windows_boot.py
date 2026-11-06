"""Actual RAM/FV/GOP C checks and independent FAT32 reader integration."""
import ctypes,importlib.util,os,struct,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('wbt_fat',ROOT/'Resources/WindowsBootTest/fat32.py');fat=importlib.util.module_from_spec(s);s.loader.exec_module(fat)
TYPES='''#include <stdint.h>
#include <stddef.h>
#define STATIC
#define CONST const
#define TRUE 1
#define FALSE 0
typedef uint8_t UINT8;typedef uint32_t UINT32;typedef uint64_t UINT64;typedef size_t UINTN;typedef int BOOLEAN;
'''
class WindowsRamChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name)
  (p/'c.c').write_text(TYPES+'\n#include "'+str(ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/RamChecks.h')+'"\n')
  subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror',str(p/'c.c'),'-o',str(p/'c.so')],check=True)
  cls.c=ctypes.CDLL(str(p/'c.so'));cls.c.WbtFatValid.argtypes=[ctypes.c_void_p,ctypes.c_size_t];cls.c.WbtReadRange.argtypes=[ctypes.c_uint64,ctypes.c_size_t,ctypes.c_size_t];cls.c.WbtArmPe.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
  cls.c.WbtRawFromFv.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_size_t)]
  cls.c.WbtMapValid.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_size_t]
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_real_fat32_geometry_and_malformed_lengths(self):
  image=fat.create({'README.TXT':b'fixture'});b=(ctypes.c_uint8*len(image)).from_buffer(image)
  self.assertTrue(self.c.WbtFatValid(b,len(image)))
  for offset,value in [(32,1),(36,0xffffffff),(44,0)]:
   old=image[offset:offset+4];struct.pack_into('<I',image,offset,value)
   self.assertFalse(self.c.WbtFatValid(b,len(image)));image[offset:offset+4]=old
  self.assertFalse(self.c.WbtFatValid(b,len(image)-512))
 def test_read_bounds_and_overflow(self):
  self.assertTrue(self.c.WbtReadRange(7,512,4096));self.assertTrue(self.c.WbtReadRange(8,0,4096))
  for l,n in [(8,512),(0,513),(2**64-1,512),(2**64-1,0)]:self.assertFalse(self.c.WbtReadRange(l,n,4096))
 def test_memory_map_overlap_overflow_and_runtime_attributes(self):
  b=bytearray(80);struct.pack_into('<I4xQQQQ',b,0,4,0x1000,0,2,0);struct.pack_into('<I4xQQQQ',b,40,5,0x4000,0,1,1<<63)
  p=(ctypes.c_uint8*len(b)).from_buffer(b)
  self.assertTrue(self.c.WbtMapValid(p,len(b),40))
  struct.pack_into('<Q',b,48,0x2000);self.assertFalse(self.c.WbtMapValid(p,len(b),40))
  struct.pack_into('<Q',b,48,0x4000);struct.pack_into('<Q',b,72,0);self.assertFalse(self.c.WbtMapValid(p,len(b),40))
  struct.pack_into('<Q',b,72,1<<63);struct.pack_into('<Q',b,64,2**64-1);self.assertFalse(self.c.WbtMapValid(p,len(b),40))
  self.assertFalse(self.c.WbtMapValid(p,len(b),39))
 def test_arm64_pe_rejects_other_machine_and_bad_offset(self):
  b=bytearray(128);b[:2]=b'MZ';struct.pack_into('<I',b,60,64);b[64:68]=b'PE\0\0';struct.pack_into('<H',b,68,0xaa64);struct.pack_into('<H',b,88,0x20b)
  p=(ctypes.c_uint8*len(b)).from_buffer(b);self.assertTrue(self.c.WbtArmPe(p,len(b)))
  b[69]=0x86;self.assertFalse(self.c.WbtArmPe(p,len(b)));struct.pack_into('<I',b,60,0xffffffff);self.assertFalse(self.c.WbtArmPe(p,len(b)))
 def test_fv_raw_bounds_and_missing_guid(self):
  b=bytearray(4096);struct.pack_into('<Q',b,32,len(b));b[40:44]=b'_FVH';struct.pack_into('<H',b,48,72)
  guid=bytes(range(16));b[72:88]=guid;b[90]=2;b[92:95]=(32).to_bytes(3,'little');b[96:99]=(8).to_bytes(3,'little');b[99]=0x19;b[100:104]=b'DATA'
  p=(ctypes.c_uint8*len(b)).from_buffer(b);g=ctypes.create_string_buffer(guid);data=ctypes.c_void_p();size=ctypes.c_size_t()
  self.assertTrue(self.c.WbtRawFromFv(p,len(b),g,ctypes.byref(data),ctypes.byref(size)));self.assertEqual(ctypes.string_at(data,size.value),b'DATA')
  b[96:99]=b'\0\0\0';self.assertFalse(self.c.WbtRawFromFv(p,len(b),g,ctypes.byref(data),ctypes.byref(size)))
 def test_mtools_reads_long_names_and_multiple_clusters(self):
  tools=os.environ.get('DAVINCI_MTOOLS_DIR')
  if not tools:self.skipTest('Independent mtools path not configured')
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'fat.img';expected=bytes(range(256))*13
   p.write_bytes(fat.create({'EFI/Microsoft/Boot/Fonts/wgl4_boot.ttf':expected,'EFI/Boot/bootaa64.efi':b'NOT A PE - HOST FIXTURE'}))
   actual=subprocess.check_output([str(Path(tools)/'mtype'),'-i',str(p),'::/EFI/Microsoft/Boot/Fonts/wgl4_boot.ttf'])
   self.assertEqual(actual,expected)
   self.assertEqual(subprocess.check_output([str(Path(tools)/'mtype'),'-i',str(p),'::/EFI/Boot/bootaa64.efi']),b'NOT A PE - HOST FIXTURE')
 def test_pi_large_file_uses_zero_size_and_extended_section_marker(self):
  b=bytearray(4096);struct.pack_into('<Q',b,32,len(b));b[40:44]=b'_FVH';struct.pack_into('<H',b,48,72)
  guid=bytes(range(16));b[72:88]=guid;b[90]=2;b[91]=1;struct.pack_into('<Q',b,96,44)
  b[104:107]=b'\xff'*3;b[107]=0x19;struct.pack_into('<I',b,108,12);b[112:116]=b'DATA'
  p=(ctypes.c_uint8*len(b)).from_buffer(b);g=ctypes.create_string_buffer(guid);data=ctypes.c_void_p();size=ctypes.c_size_t()
  self.assertTrue(self.c.WbtRawFromFv(p,len(b),g,ctypes.byref(data),ctypes.byref(size)));self.assertEqual(ctypes.string_at(data,size.value),b'DATA')
  b[92:95]=b'\xff'*3;self.assertFalse(self.c.WbtRawFromFv(p,len(b),g,ctypes.byref(data),ctypes.byref(size)))

class RamDiskContract(unittest.TestCase):
 def test_actual_block_callbacks_and_runtime_refusals(self):
  text=(ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/WindowsBootTestDxe.c').read_text()
  callbacks=text[text.index('STATIC EFI_STATUS EFIAPI ResetDisk'):text.index('STATIC EFI_BLOCK_IO_PROTOCOL mBlock')]
  runtime=text[text.index('STATIC VOID EFIAPI TrapReset'):text.index('STATIC EFI_STATUS RuntimeStubs')]
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   (p/'c.c').write_text(TYPES+'''\n#include <assert.h>
#include <string.h>
#include <setjmp.h>
#define VOID void
#define EFIAPI
#undef STATIC
#define STATIC static
#define EFI_SUCCESS 0
#define EFI_INVALID_PARAMETER 2
#define EFI_UNSUPPORTED 3
#define EFI_BAD_BUFFER_SIZE 4
#define EFI_WRITE_PROTECTED 8
#define EFI_NO_MEDIA 12
#define EFI_MEDIA_CHANGED 13
typedef int EFI_STATUS;typedef UINT64 EFI_LBA,EFI_PHYSICAL_ADDRESS;typedef int EFI_RESET_TYPE;
typedef struct {int x;} EFI_TIME,EFI_TIME_CAPABILITIES,EFI_CAPSULE_HEADER,EFI_BLOCK_IO_PROTOCOL;
static struct {UINT32 MediaId;BOOLEAN MediaPresent;} mMedia={7,1};
static UINT8 data[1024],*mDisk=data;static UINTN mBytes=sizeof(data),mReads;
#define CopyMem memcpy
static jmp_buf Stop;static int Wfi;
static void ArmCallWFI(void){Wfi++;longjmp(Stop,1);}
#include "'''+str(ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/RamChecks.h')+'"\n#include "'+str(ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/RamGpt.h')+'"\n'+callbacks+runtime+'''\nint main(void){EFI_BLOCK_IO_PROTOCOL io={0};UINT8 out[514];memset(out,0xA5,sizeof out);data[512]=42;
assert(ResetDisk(&io,0)==0&&FlushDisk(&io)==0);assert(ReadDisk(&io,7,1,512,out+1)==0);assert(out[1]==42&&out[0]==0xA5&&out[513]==0xA5&&mReads==1);
assert(ReadDisk(&io,8,0,512,out)==13);assert(ReadDisk(&io,7,2,512,out)==2);assert(ReadDisk(&io,7,0,513,out)==4);assert(ReadDisk(&io,7,0,512,NULL)==2);assert(ReadDisk(&io,7,0,0,NULL)==0);
mMedia.MediaPresent=0;assert(ReadDisk(&io,7,0,512,out)==12);assert(WriteDisk(&io,7,0,512,out)==8);assert(data[512]==42);
EFI_TIME time={123};assert(NoTime(&time,NULL)==3&&time.x==123);assert(NoTime(NULL,NULL)==2);assert(NoSetTime(&time)==3);assert(NoSetTime(NULL)==2);assert(NoWake(NULL,NULL,NULL)==3);assert(NoSetWake(0,NULL)==3);assert(NoCapsule(NULL,0,0)==3);assert(NoCapsuleQuery(NULL,0,NULL,NULL)==3);
if(setjmp(Stop)==0){TrapReset(0,0,0,NULL);assert(0);}assert(Wfi==1);return 0;}\n''')
   subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-function',str(p/'c.c'),'-o',str(p/'c')],check=True);subprocess.run([str(p/'c')],check=True)
