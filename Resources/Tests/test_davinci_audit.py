import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('audit', ROOT / 'Resources/Scripts/davinci_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class OfflineAuditTests(unittest.TestCase):
    def test_timer_gic_offsets_and_low_polarity(self):
        dts = (ROOT / 'Resources/DTBs/davinci.dts').read_text()
        self.assertEqual(audit.timer_from_dts(dts), [(17, 2), (18, 2), (19, 2), (16, 2)])

    def test_timer_rejects_invalid_ppi(self):
        dts = 'compatible = "arm,armv8-timer"; interrupts = <1 17 8 1 2 8 1 3 8 1 0 8>;'
        with self.assertRaises(ValueError):
            audit.timer_from_dts(dts)

    def test_current_device_sources(self):
        self.assertEqual(audit.source_audit(ROOT)['regions'], 65)

    def test_reject_unmapped_resource(self):
        with self.assertRaises(ValueError):
            audit.require_coverage([('unrelated', 0x1000, 0x1000)], 0x1D84000, 0x3000)

    def test_exact_end_is_covered_but_one_byte_over_is_not(self):
        audit.require_coverage([('UFS', 0x1000, 0x2000)], 0x2000, 0x1000)
        with self.assertRaises(ValueError):
            audit.require_coverage([('UFS', 0x1000, 0x2000)], 0x2000, 0x1001)

    def test_reject_overlap_and_unaligned_regions(self):
        for items in [[('a', 0x1000, 0x2000), ('b', 0x2000, 0x1000)], [('a', 1, 0x1000)]]:
            with self.assertRaises(ValueError):
                audit.check_regions(items)

    def test_pe_rejects_truncated_offset(self):
        b = bytearray(64)
        b[:2] = b'MZ'
        struct.pack_into('<I', b, 60, 0x10000)
        with self.assertRaises(ValueError):
            audit.pe_machine(b)

    def test_madt_rejects_zero_length_record(self):
        b = bytearray(46)
        b[:4] = b'APIC'
        with self.assertRaises(ValueError):
            audit.gicc_topology(b)

    def test_cpu_topology_mismatch_is_not_accepted(self):
        dts = (ROOT / 'Resources/DTBs/davinci.dts').read_text()
        madt = bytearray((ROOT / 'Silicium-ACPI/SoCs/Qualcomm/Moorea/APIC.aml').read_bytes())
        struct.pack_into('<Q', madt, 44 + 68, 0xBAD)
        with self.assertRaises(ValueError):
            audit.check_cpu_topology(dts, madt)

    def test_acpi_rejects_mismatched_length(self):
        b = bytearray(36)
        b[:4] = b'DSDT'
        struct.pack_into('<I', b, 4, 37)
        with self.assertRaises(ValueError):
            audit.acpi_header(b)

if __name__ == '__main__':
    unittest.main()
