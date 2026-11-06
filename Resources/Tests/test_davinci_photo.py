"""Photo-mode renderer and fatal/reset interception with RAM-only services."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

class PhotoTests(unittest.TestCase):
    def test_actual_photo_hooks_checkpoint_stops_crc_and_no_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for n in ['Protocol/Cpu.h','Library/ArmLib.h','Library/PrintLib.h','Library/TimerLib.h']:
                h=p/n;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('// declarations in host harness\n')
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-I',str(p),
                '-I',str(ROOT/'Silicon/Silicium/SiliciumPkg/Include'),
                str(ROOT/'Resources/Tests/davinci_photo_host.c'),'-o',str(p/'photo')],check=True)
            subprocess.run([str(p/'photo')],check=True)

    def test_phase_ceiling_and_both_documented_delays(self):
        for delay in [0,1000000]:
            with self.subTest(delay=delay), tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)
                for n in ['Protocol/Cpu.h','Library/ArmLib.h','Library/PrintLib.h','Library/TimerLib.h']:
                    h=p/n;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('// host declarations\n')
                cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-I',str(p),
                  '-I',str(ROOT/'Silicon/Silicium/SiliciumPkg/Include'),'-DDAVINCI_PHOTO_PHASE_TEST=1',
                  '-DDAVINCI_PHOTO_MAX_NATIVE=0','-DDAVINCI_PHOTO_DELAY_US='+str(delay),
                  str(ROOT/'Resources/Tests/davinci_photo_host.c'),'-o',str(p/'photo')]
                subprocess.run(cmd,check=True);subprocess.run([str(p/'photo')],check=True)

    def test_phase_configuration_cannot_authorize_hal_or_unknown_delay(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for n in ['Protocol/Cpu.h','Library/ArmLib.h','Library/PrintLib.h','Library/TimerLib.h']:
                h=p/n;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('// host declarations\n')
            base=['cc','-std=c11','-I',str(p),'-I',str(ROOT/'Silicon/Silicium/SiliciumPkg/Include'),
                  '-DDAVINCI_PHOTO_PHASE_TEST=1',str(ROOT/'Resources/Tests/davinci_photo_host.c'),'-o',str(p/'bad')]
            for flags in [['-DDAVINCI_PHOTO_MAX_NATIVE=11'],['-DDAVINCI_PHOTO_MAX_NATIVE=13'],
                          ['-DDAVINCI_PHOTO_MAX_NATIVE=12'],
                          ['-DDAVINCI_PHOTO_MAX_NATIVE=9','-DDAVINCI_PHOTO_DELAY_US=30000000']]:
                result=subprocess.run(base+flags,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0);self.assertIn('DUU3',result.stderr)

    def test_raster_clips_invalid_coordinates_and_keeps_canaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);header=ROOT/'Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/PhotoRaster.h'
            (p/'r.c').write_text('#include <stdint.h>\n#include <stddef.h>\n#define STATIC\n#define VOID void\n#define CONST const\n#define TRUE 1\n#define FALSE 0\ntypedef size_t UINTN;typedef uint32_t UINT32;typedef uint8_t UINT8;typedef int BOOLEAN;\n#include "'+str(header)+'"\n')
            subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror',str(p/'r.c'),'-o',str(p/'r.so')],check=True)
            c=ctypes.CDLL(str(p/'r.so'));c.PhotoGlyph.argtypes=[ctypes.POINTER(ctypes.c_uint32),*[ctypes.c_size_t]*4,ctypes.c_uint8,ctypes.POINTER(ctypes.c_size_t),ctypes.c_uint32]
            c.PhotoRasterValid.argtypes=[ctypes.c_size_t]*3
            self.assertTrue(c.PhotoRasterValid(1080,2340,1080*2340*4));self.assertFalse(c.PhotoRasterValid(1080,2340,4))
            font=(ctypes.c_size_t*190)(*([0x3fffffff]*190))
            buf=(ctypes.c_uint32*(64*64+16))(*([0xdeadbeef]*(64*64+16)))
            pixels=ctypes.cast(ctypes.byref(buf,8*4),ctypes.POINTER(ctypes.c_uint32))
            c.PhotoGlyph(pixels,64,64,49,28,65,font,0xffffffff)
            self.assertEqual(pixels[63*64+63],0xffffffff)
            self.assertTrue(all(buf[i]==0xdeadbeef for i in list(range(8))+list(range(64*64+8,64*64+16))))
            before=bytes(buf)
            for x,y in [(50,28),(49,29),(65,0),(0,65),(2**64-1,0)]:c.PhotoGlyph(pixels,64,64,x,y,127,font,0)
            self.assertEqual(bytes(buf),before)

if __name__=='__main__':unittest.main()
