import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hal_offline', ROOT / 'Resources/Scripts/davinci_hal_offline.py')
hal = importlib.util.module_from_spec(spec); spec.loader.exec_module(hal)

@unittest.skipUnless(importlib.util.find_spec('unicorn'), 'Optional Unicorn package unavailable')
class HalOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = (ROOT/'Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.efi').read_bytes()

    def test_real_protocol_layout_and_absent_ufs_dummy_client(self):
        r=hal.emulate(self.image)
        self.assertEqual(r['function_table_rva'],0x90a8)
        self.assertEqual((r['function_slots'][0],r['function_slots'][2],r['function_slots'][8]),(0x1904,0x1b70,0x3160))
        self.assertEqual(r['dummy_return'],'0x0')
        self.assertEqual([c['client'] for c in r['dummy_calls'] if c['call']=='attach'],
                         ['\\_SB_.SDC1','\\_SB_.SDC2','\\_SB_.SDC4','\\_SB_.USB3-0'])
        self.assertFalse(r['dummy_initializes_ufs'])
        self.assertFalse(r['actual_domain_services_executed'])

    def test_dummy_client_stops_on_mocked_errors(self):
        for service in ['create','configure']:
            with self.subTest(service=service):
                result=hal.emulate(self.image,fail=service)
                self.assertTrue(int(result['dummy_return'],16)&(1<<63))
                self.assertEqual(result['dummy_calls'][-1]['call'],service)

    def test_attach_errors_are_logged_but_not_propagated_by_this_binary(self):
        result=hal.emulate(self.image,fail='attach')
        self.assertEqual(result['dummy_return'],'0x0')
        self.assertEqual(result['debug_notifications'],4)
        self.assertEqual(len([c for c in result['dummy_calls'] if c['call']=='attach']),4)

    def test_bank_choice_depends_on_fixture_hardware_state(self):
        self.assertEqual(hal.emulate_bank_choice(self.image,[0,0])['selected_bank'],0)
        result=hal.emulate_bank_choice(self.image,[0x10000,0x10000,0])
        self.assertEqual(result['selected_bank'],2)
        self.assertEqual([x['register'] for x in result['intercepted_write_arguments']],['CBAR','CBA2R'])
        self.assertEqual(result['intercepted_write_arguments'][1]['value'],1)
        self.assertFalse(result['actual_register_services_executed'])

    def test_bank_exhaustion_and_zero_bank_fixture_do_not_write(self):
        for values in [[],[0x10000,0x10000]]:
            result=hal.emulate_bank_choice(self.image,values)
            self.assertIsNone(result['selected_bank'])
            self.assertEqual(result['intercepted_write_arguments'],[])

    def test_unused_vmid_bank_is_selected(self):
        self.assertEqual(hal.emulate_bank_choice(self.image,[0x100ff])['selected_bank'],0)

    def test_unknown_image_is_rejected_before_emulation(self):
        with self.assertRaises(ValueError): hal.emulate(b'unknown')

if __name__=='__main__':unittest.main()
