"""Compile/execute the production HAL ABI chain with mock methods, not MMIO."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

class NativeHalBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();p=Path(cls.temp.name)
        h=ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/HalUfsBridge.h'
        (p/'bridge.c').write_text('''#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define STATIC
#define VOID void
#define CONST const
#define EFIAPI
#define FALSE 0
#define TRUE 1
#define EFI_SUCCESS 0
#define EFI_INVALID_PARAMETER 2
#define EFI_UNSUPPORTED 3
#define EFI_DEVICE_ERROR 7
#define EFI_NOT_STARTED 19
typedef uint32_t UINT32; typedef uint64_t UINT64;
typedef int BOOLEAN; typedef char CHAR8; typedef uint64_t EFI_STATUS;
#include "'''+str(h)+'''"
static int Mode, Calls, Bad;
static UINT32 Create(VOID **D) { Calls++; *D=Mode==4?NULL:(VOID *)0x1234;return Mode==1?19:0; }
static UINT32 Bypass(VOID *D,UINT32 Type) { Calls++;Bad|=D!=(VOID *)0x1234 || Type>1;return Mode==2?24:0; }
static UINT32 Attach(VOID *D,VOID *C,UINT32 A,UINT32 M) {
 Calls++;Bad|=D!=(VOID *)0x1234 || strcmp(C,"\\\\_SB_.UFS0") || A!=0 || M!=0;return Mode==3?20:0;
}
static void Trace(CHAR8 *S,BOOLEAN Returned,UINT32 Raw) {(void)S;(void)Returned;(void)Raw;}
UINT64 Fixture(int ModeArg,UINT32 Ioc,DAVINCI_UFS_DOMAIN *Out,int *Count,int *Invalid) {
 Mode=ModeArg; Calls=Bad=0;
 DAVINCI_HAL_TABLE T={0};T.Create=Create;T.Attach=Attach;T.ConfigureBypass=Bypass;
 UINT64 S=RunUfsDomainChain(&T,Ioc,Out,Trace);*Count=Calls;*Invalid=Bad;return S;
}
int Offsets(void) {return offsetof(DAVINCI_HAL_TABLE,Create)==0 && offsetof(DAVINCI_HAL_TABLE,Attach)==16 && offsetof(DAVINCI_HAL_TABLE,ConfigureBypass)==64 && sizeof(DAVINCI_HAL_TABLE)==80 && offsetof(DAVINCI_HAL_PROTOCOL,Init)==8;}
''')
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',str(p/'bridge.c'),'-o',str(p/'bridge.so')],check=True)
        cls.c=ctypes.CDLL(str(p/'bridge.so'))
        class Domain(ctypes.Structure):_fields_=[('pointer',ctypes.c_void_p),('create',ctypes.c_uint32),('configure',ctypes.c_uint32),('attach',ctypes.c_uint32),('completed',ctypes.c_uint32)]
        cls.Domain=Domain
        cls.c.Fixture.argtypes=[ctypes.c_int,ctypes.c_uint32,ctypes.POINTER(Domain),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
        cls.c.Fixture.restype=ctypes.c_uint64
        cls.c.NativeLayoutSupported.argtypes=[ctypes.c_uint32,ctypes.c_uint32]
        cls.c.NativeBankBypass.argtypes=[ctypes.c_uint32]*6
        cls.c.ContextWindow.argtypes=[ctypes.c_uint32,ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_uint32)]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def run_chain(self,mode,ioc=0):
        d=self.Domain();n=ctypes.c_int();bad=ctypes.c_int()
        s=self.c.Fixture(mode,ioc,ctypes.byref(d),ctypes.byref(n),ctypes.byref(bad));self.assertEqual(bad.value,0)
        return s,d,n.value
    def test_exact_native_abi_offsets_and_success_both_coherency_modes(self):
        self.assertTrue(self.c.Offsets())
        for ioc in [0,1]:
            s,d,n=self.run_chain(0,ioc);self.assertEqual((s,n,d.completed),(0,3,3))
            self.assertEqual((d.create,d.configure,d.attach),(0,0,0))
    def test_create_configure_attach_failures_stop_and_preserve_raw(self):
        for mode,status,calls,completed in [(1,19,1,0),(2,3,2,1),(3,7,3,2),(4,19,1,0)]:
            s,d,n=self.run_chain(mode);self.assertEqual((s,n,d.completed),(status,calls,completed))
        s,d,n=self.run_chain(0,2);self.assertEqual((s,n),(2,0))
    def test_reported_s2cr_two_is_translation_context_bank_two(self):
        self.assertEqual(((2>>16)&3,2&255),(0,2))
        self.assertTrue(self.c.NativeBankBypass(2,0x1f000,1,0xe0,0,61))
        self.assertFalse(self.c.NativeBankBypass(0x20002,0x1f000,1,0xe0,0,61))
    def test_identity_needs_cbar_cba2r_m_zero_and_cache_policy(self):
        for args in [(2,0x1f000,1,0xe1,0,61),(2,0x2f000,1,0xe0,0,61),
                     (2,0x1f001,1,0xe0,0,61),(2,0x1f000,0,0xe0,0,61),
                     (2,0x1f000,1,0x9f00e0,0,61),(61,0x1f000,1,0xe0,0,61)]:
            self.assertFalse(self.c.NativeBankBypass(*args))
        self.assertTrue(self.c.NativeBankBypass(2,0x1f000,1,0x9f00e0,1,61))
    def test_reported_hardware_layout_and_memory_bounds(self):
        self.assertTrue(self.c.NativeLayoutSupported(0x40017e4f,0x6000003d))
        self.assertFalse(self.c.NativeLayoutSupported(0x40017e4f,0x6000003e))
        o=ctypes.c_uint64();b=ctypes.c_uint32()
        self.assertTrue(self.c.ContextWindow(0x6000003d,0xd0000,ctypes.byref(o),ctypes.byref(b)))
        self.assertEqual((o.value,b.value),(0x80000,61))
        for ident,length in [(0xe000003d,0xd0000),(0x60000000,0xd0000),(0x6000003d,0x90000)]:
            self.assertFalse(self.c.ContextWindow(ident,length,ctypes.byref(o),ctypes.byref(b)))


class NativeCoordinatorHostTests(unittest.TestCase):
    def test_actual_snapshot_ownership_and_readback_paths(self):
        names=['Uefi.h','Pi/PiFirmwareFile.h','Protocol/BlockIo.h','Protocol/LoadedImage.h',
          'Library/ConfigurationMapHelperLib.h','Library/BaseLib.h','Library/BaseMemoryLib.h',
          'Library/CacheMaintenanceLib.h','Library/DebugLib.h','Library/DxeServicesLib.h',
          'Library/IoLib.h','Library/MemoryAllocationLib.h','Library/MemoryMapHelperLib.h',
          'Library/SerialPortLib.h','Library/UefiBootServicesTableLib.h']
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name in names:
                f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('// fake declarations in harness\n')
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-parameter',
                            '-Wno-misleading-indentation','-I',str(p),
                            str(ROOT/'Resources/Tests/davinci_ufs_unblock_host.c'),'-o',str(p/'host')],check=True)
            subprocess.run([str(p/'host')],check=True)

class ActualNativeHalRamTests(unittest.TestCase):
    def test_real_create_bypass_and_programmer_bitfields_and_duplicate_hazard(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('native_probe',ROOT/'Resources/UfsUnblock/native_hal_probe.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        image=(ROOT/'Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.efi').read_bytes()
        for ioc,ctl in [(0,'0xe0'),(1,'0x9f00e0')]:
            r=mod.probe(image,ioc=ioc)
            self.assertEqual((r['create_return'],r['configure_return'],r['domain_sctlr'],r['domain_tcr']),(0,0,ctl,'0x0'))
            self.assertEqual(r['register_service_arguments'],[{'register':'SMR','index':0,'value':0x800f0300},{'register':'S2CR','index':0,'value':2}])
        r=mod.probe(image,existing=True)
        self.assertEqual(r['register_service_arguments'][0],{'register':'SMR','index':1,'value':0x800f0300})
        self.assertFalse(r['physical_validation'])

if __name__=='__main__':unittest.main()
