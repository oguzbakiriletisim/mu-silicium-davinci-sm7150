"""Run actual DEBUG driver entry points with a minimal fake UEFI interface."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class StorageDriverHostTests(unittest.TestCase):
    def test_real_driver_success_and_failure_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # All declarations come from the host harness, not production UEFI.
            for name in ['Uefi.h', 'Guid/EventGroup.h', 'Protocol/BlockIo.h',
                         'Protocol/EFIClock.h', 'Protocol/EFISmem.h', 'Protocol/EFIScm.h',
                         'Library/ConfigurationMapHelperLib.h', 'Library/DebugLib.h',
                         'Library/IoLib.h', 'Library/MemoryAllocationLib.h',
                         'Library/MemoryMapHelperLib.h', 'Library/UefiBootServicesTableLib.h']:
                header = tmp / name
                header.parent.mkdir(parents=True, exist_ok=True)
                header.write_text('// Host declarations provided by the harness.\n')
            executable = tmp / 'storage-host-test'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                            '-Werror', '-Wno-unused-parameter', '-I', str(tmp),
                            str(ROOT / 'Resources/Tests/davinci_storage_driver_host.c'),
                            '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

if __name__ == '__main__':
    unittest.main()
