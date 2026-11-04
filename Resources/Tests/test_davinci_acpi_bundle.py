import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('audit', ROOT / 'Resources/Scripts/davinci_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def checksum(table):
    table = bytearray(table)
    table[9] = 0
    table[9] = -sum(table) & 255
    return table

def table(signature, size, revision):
    b = bytearray(size)
    struct.pack_into('<4sIBB6s8sIII', b, 0, signature.encode(), size, revision, 0,
                     b'DVNCI ', b'TESTONLY', 1, 0, 1)
    return b

def bundle():
    common = ROOT / 'Silicium-ACPI/SoCs/Qualcomm/Moorea'
    tables = [(common / (s + '.aml')).read_bytes() for s in ['APIC', 'PPTT']]
    fadt = table('FACP', 276, 6)
    struct.pack_into('<I', fadt, 112, 1 << 20)
    struct.pack_into('<H', fadt, 129, 1)
    gtdt = table('GTDT', 96, 2)
    for offset, intid in zip([48, 56, 64, 72], [17, 18, 19, 16]):
        struct.pack_into('<II', gtdt, offset, intid, 2)
    return tables + [checksum(fadt), checksum(gtdt), checksum(table('DSDT', 36, 2))]

class AcpiBundleTests(unittest.TestCase):
    timer = [(17, 2), (18, 2), (19, 2), (16, 2)]

    def check(self, tables):
        return audit.check_acpi_bundle(tables, True, self.timer)

    def test_consistent_tables_and_revision_one_id_resource(self):
        result = self.check(bundle())
        self.assertEqual(result['madt_pptt_cpu_ids'], list(range(8)))
        self.assertTrue(result['raw_checksums_valid'])

    def test_facs_has_no_description_header_checksum(self):
        facs = bytearray(64)
        struct.pack_into('<4sI', facs, 0, b'FACS', 64)
        facs[32] = 2
        self.assertFalse(audit.acpi_header(facs)['checksum_applicable'])
        self.check(bundle() + [facs])

    def test_missing_and_duplicate_tables_are_rejected(self):
        for tables in [bundle()[:-1], bundle() + [bundle()[0]]]:
            with self.assertRaises(ValueError):
                self.check(tables)

    def test_fadt_unverified_s0_hvc_reset_and_pointer_claims_fail(self):
        for offset, value in [(114, 0x30), (129, 3), (120, 1), (140, 1), (268, 1), (76, 1)]:
            with self.subTest(offset=offset):
                tables = bundle()
                bad = bytearray(tables[2]); bad[offset] = value
                tables[2] = checksum(bad)
                with self.assertRaises(ValueError):
                    self.check(tables)

    def test_checksum_failure_is_rejected(self):
        tables = bundle()
        bad = bytearray(tables[2]); bad[24] ^= 1; tables[2] = bad
        with self.assertRaises(ValueError):
            self.check(tables)

    def test_madt_pptt_uid_mismatch_is_rejected(self):
        tables = bundle()
        bad = bytearray(tables[1]); struct.pack_into('<I', bad, 0xbe + 12, 99)
        tables[1] = checksum(bad)
        with self.assertRaises(ValueError):
            self.check(tables)

    def test_pptt_parent_cycle_and_resource_pointer_are_rejected(self):
        for offset, value in [(0xbe + 8, 0xbe), (0xbe + 20, 0xBAD)]:
            bad = bytearray(bundle()[1]); struct.pack_into('<I', bad, offset, value)
            with self.assertRaises(ValueError):
                audit.pptt_topology(bad)

    def test_timer_polarity_change_is_rejected(self):
        tables = bundle()
        bad = bytearray(tables[3]); struct.pack_into('<I', bad, 52, 0)
        tables[3] = checksum(bad)
        with self.assertRaises(ValueError):
            self.check(tables)

    def test_peripheral_table_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check(bundle() + [checksum(table('IORT', 48, 1))])

if __name__ == '__main__':
    unittest.main()
