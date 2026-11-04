import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ufs', ROOT / 'Resources/Scripts/davinci_ufs_offline.py')
ufs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ufs)

@unittest.skipUnless(importlib.util.find_spec('unicorn') and importlib.util.find_spec('pefile'),
                     'Optional offline UFS emulation dependencies are not installed')
class UfsOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, cls.patched = ufs.load_images(ROOT)

    def test_original_default_is_non_cca_bypass_and_named_client(self):
        result = ufs.emulate(self.original)
        self.assertEqual(result['return'], '0x0')
        self.assertEqual(result['calls'], [
            {'service': 'create'}, {'service': 'get_config', 'key': 'EnableUfsIOC'},
            {'service': 'configure_bypass', 'type': 0},
            {'service': 'attach', 'client': '\\_SB_.UFS0', 'arid': 0, 'mask': 0}])

    def test_configured_cca_and_protocol_lookup(self):
        result = ufs.emulate(self.original, ioc=1, locate_protocol=True)
        self.assertEqual(result['return'], '0x0')
        self.assertEqual([c['service'] for c in result['calls']][:2], ['locate_protocol', 'protocol_init'])
        self.assertIn({'service': 'configure_bypass', 'type': 1}, result['calls'])

    def test_service_failures_stop_the_initialization_chain(self):
        for service in ['locate_protocol', 'create', 'configure_bypass', 'attach']:
            with self.subTest(service=service):
                result = ufs.emulate(self.original, failure=service, locate_protocol=True)
                self.assertTrue(int(result['return'], 16) & (1 << 63))
                self.assertEqual(result['calls'][-1]['service'], service)

    def test_existing_patch_calls_no_iommu_service(self):
        self.assertEqual(ufs.emulate(self.patched), {'return': '0x0', 'calls': []})

    def test_boot_predicate_does_not_mean_disk_discovery(self):
        for value, status, expected in [(8, 0, '0x1'), (1, 0, '0x0'), (None, ufs.NOT_FOUND, '0x0')]:
            with self.subTest(value=value):
                result = ufs.emulate(self.patched, 'boot', boot_type=value, boot_status=status)
                self.assertEqual(result['return'], expected)
                self.assertEqual(result['calls'], [{'service': 'boot_query'}])

if __name__ == '__main__':
    unittest.main()
