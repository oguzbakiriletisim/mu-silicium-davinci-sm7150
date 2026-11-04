import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PWSH = os.environ.get('DAVINCI_PWSH') or shutil.which('pwsh') or shutil.which('powershell')

@unittest.skipUnless(PWSH, 'Optional PowerShell runtime unavailable; native Windows disk/BCD testing is separate')
class PowerShellScriptTests(unittest.TestCase):
    def run_action(self, action):
        completed = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-File',
                                    str(ROOT/'Resources/Tests/davinci_windows_scripts_test.ps1'),
                                    '-ToolsRoot', str(ROOT/'Resources/Windows/davinci'),
                                    '-Action', action], capture_output=True, text=True, check=True)
        self.assertIn('PASS: ' + action, completed.stdout)

    def test_script_syntax(self): self.run_action('Parse')
    def test_mocked_storage_inventory(self): self.run_action('Inventory')
    def test_lab_disk_default_or_platform_guard(self): self.run_action('LabGuard')

if __name__ == '__main__': unittest.main()
