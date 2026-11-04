import copy
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dal_iort', ROOT / 'Resources/Scripts/davinci_dal_iort.py')
dal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dal)

class DalIortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = (ROOT / 'Binaries/davinci/QcomPkg/Drivers/DALSYSDxe/DALSYSDxe.efi').read_bytes()
        cls.binding = dal.extract_binding(cls.image)
        p = cls.binding['iort_file_offset']
        cls.raw = cls.image[p:p + cls.binding['iort']['length']]

    def test_real_property_binding_and_ufs_mapping(self):
        b = self.binding
        self.assertEqual((b['props_info_offset'], b['struct_index'], b['iort_file_offset']), (0x7970, 16, 0x27688))
        self.assertTrue(b['matches_pinned_davinci_binary'])
        self.assertEqual(b['ufs_arid_zero']['sid_base'], 0x300)
        self.assertEqual(b['ufs_arid_zero']['smmu_base'], 0x15000000)
        self.assertIsNone(b['ufs_arid_zero']['context_bank'])
        self.assertFalse(b['safe_to_enable_dma'])

    @unittest.skipUnless(importlib.util.find_spec('unicorn'), 'Optional Unicorn package unavailable')
    def test_pinned_phase_zero_registration_uses_7150_props_info(self):
        result = dal.emulate_registration(self.image)
        self.assertEqual(result['phase_zero_props_info'], 0x7970)
        self.assertEqual(result['mock_allocations_payloads'], [0, 0x7970])
        self.assertEqual(result['next_phase'], 1)
        self.assertEqual(self.binding['target_registration_records'][0]['label'], '7150_xml')

    def test_usb_cross_check_and_table_anomalies_remain_visible(self):
        table = self.binding['iort']
        usb = next(n for n in table['nodes'] if n.get('name') == '\\_SB_.USB3-0')
        self.assertEqual(usb['mappings'][0]['output_base'], 0x540)
        self.assertEqual(table['checksum_mod256'], 27)
        self.assertEqual(table['unparsed_tail_bytes'], 101)
        self.assertFalse(self.binding['suitable_for_direct_os_acpi_publication'])

    def test_struct_pointer_corruption_is_rejected(self):
        b = bytearray(self.image)
        struct.pack_into('<Q', b, self.binding['struct_descriptor_offset'] + 8, 0xffffffffffffffff)
        with self.assertRaises(ValueError):
            dal.extract_binding(b)

    def test_compact_property_type_and_name_corruption_are_rejected(self):
        for value in [0x11800136, 0x12807fff]:
            b = bytearray(self.image)
            struct.pack_into('<I', b, self.binding['compact_property_offset'], value)
            with self.assertRaises(ValueError):
                dal.extract_binding(b)

    def test_truncated_and_invalid_pe_are_rejected(self):
        for data in [b'', self.image[:64], b'ELF' + bytes(100)]:
            with self.assertRaises(ValueError):
                dal.PeImage(data)
        pe = dal.PeImage(self.image)
        with self.assertRaises(ValueError):
            pe.offset(0xffffffffffffffff, 8)

    def test_iort_invalid_lengths_and_mapping_bounds(self):
        for offset, value in [(4, len(self.raw) + 1), (40, len(self.raw)), (48 + 8, 0xffff), (48 + 12, 0xffff)]:
            b = bytearray(self.raw)
            struct.pack_into('<I', b, offset, value)
            with self.assertRaises(ValueError):
                dal.decode_iort(b)

    def test_bad_named_reference_and_unterminated_name(self):
        # UFS node at 0x443, mapping array starts at node offset 0x3d.
        b = bytearray(self.raw)
        struct.pack_into('<I', b, 0x443 + 0x3d + 12, 0x123456)
        with self.assertRaises(ValueError):
            dal.decode_iort(b)
        b = bytearray(self.raw); b[0x443 + 29:0x443 + 0x3d] = b'A' * (0x3d - 29)
        with self.assertRaises(ValueError):
            dal.decode_iort(b)

    def test_smmu_interrupt_bounds_are_checked(self):
        b = bytearray(self.raw); struct.pack_into('<I', b, 48 + 44, 0xffff)
        with self.assertRaises(ValueError):
            dal.decode_iort(b)

if __name__ == '__main__':
    unittest.main()
