"""Exercise pinned FFU matching branch with all external I/O mocked."""
import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'WindowsFirstBoot/native_entry_review.py'
s=importlib.util.spec_from_file_location('entry_review',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class NativeEntryTests(unittest.TestCase):
 def test_matching_fixture_reaches_update_and_private_reset(self):
  for args in [{},{'vendor':'SAMSUNG','product':'KM8B8001JM-BC01','revision':'0100'}]:
   with self.subTest(args=args):
    r=m.emulate(**args);self.assertEqual([c['service'] for c in r['calls']],['FFU_UPDATE_MOCK_ONLY','RESET_INITIALIZE_MOCK_ONLY','PRIVATE_RESET_MOCK_ONLY'])
    self.assertGreater(r['calls'][0]['bytes'],0);self.assertFalse(r['physical_result'])
 def test_nonmatching_and_updated_device_do_not_update(self):
  self.assertEqual(m.emulate(revision='9QSV')['calls'],[])
  self.assertEqual(m.emulate(vendor='UNKNOWN')['calls'],[])
 def test_update_failure_does_not_enter_reset_branch(self):
  self.assertEqual([c['service'] for c in m.emulate(update_status=1)['calls']],['FFU_UPDATE_MOCK_ONLY'])
