import copy
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare_windows', ROOT / 'Resources/Windows/davinci/prepare_windows.py')
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


def fake_pe(machine=0xaa64):
    b = bytearray(512); b[:2] = b'MZ'
    struct.pack_into('<I', b, 60, 128); b[128:132] = b'PE\0\0'
    struct.pack_into('<H', b, 132, machine); struct.pack_into('<H', b, 148, 240)
    struct.pack_into('<H', b, 152, 0x20b)
    return b


def fake_hive():
    b = bytearray(8192); b[:4] = b'regf'
    struct.pack_into('<II', b, 4, 1, 1); struct.pack_into('<I', b, 40, 4096)
    checksum = 0
    for word in struct.unpack_from('<127I', b):
        checksum ^= word
    struct.pack_into('<I', b, 508, checksum)
    return b


def staged(root):
    for relative in ['Windows/Boot/EFI/bootmgfw.efi', 'Windows/System32/winload.efi', 'Windows/System32/ntoskrnl.exe']:
        p = root / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(fake_pe())
    for name in ['SYSTEM', 'SOFTWARE', 'SAM', 'SECURITY', 'DEFAULT']:
        p = root / 'Windows/System32/config' / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(fake_hive())
    return root


def inventory():
    disk, esp, windows = [str(uuid.uuid4()) for _ in range(3)]
    common = {'is_boot': False, 'is_system': False}
    data = {'schema_version': 1, 'disks': [dict(common, guid=disk, number=7, size=64*1024**3,
            logical_sector_size=4096, partition_style='GPT', partitions=[
                dict(common, guid=esp, number=1, gpt_type=prep.ESP_TYPE, offset=1048576,
                     size=260*1024**2, file_system='FAT32', drive_letter='S'),
                dict(common, guid=windows, number=3, gpt_type=prep.BASIC_TYPE, offset=300*1024**2,
                     size=60*1024**3, file_system='NTFS', drive_letter='W')])]}
    return data, disk, esp, windows


class WindowsPrepareTests(unittest.TestCase):
    def test_valid_staging_is_not_claimed_to_be_installed_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prep.inspect_staging(staged(Path(tmp)))
            self.assertEqual(result['components']['kernel']['machine'], 'AARCH64')
            self.assertFalse(result['complete_windows_installation_verified'])

    def test_reject_x64_loader_and_missing_hive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = staged(Path(tmp))
            loader = root/'Windows/System32/winload.efi'; loader.write_bytes(fake_pe(0x8664))
            with self.assertRaises(ValueError): prep.inspect_staging(root)
            loader.write_bytes(fake_pe()); (root/'Windows/System32/config/SYSTEM').unlink()
            with self.assertRaises(FileNotFoundError): prep.inspect_staging(root)

    def test_dirty_or_bad_checksum_registry_hive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'SYSTEM'
            for offset in [4, 40, 508]:
                data = fake_hive(); data[offset] ^= 1; p.write_bytes(data)
                with self.assertRaises(ValueError): prep.hive_header(p)

    def test_pe_truncation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'boot.efi'; p.write_bytes(fake_pe()[:154])
            with self.assertRaises(ValueError): prep.arm64_pe(p)

    def test_dynamic_guids_and_existing_partition_letters(self):
        data,d,e,w=inventory(); result=prep.validate_layout(data,d,e,w)
        self.assertEqual(result['disk_guid'],d)
        self.assertEqual(result['windows_letter'],'W')

    def test_ext4_wrong_esp_missing_file_system_and_host_disk_are_blocked(self):
        for mutation in ['ext4','host','wrong_type','missing_fs']:
            data,d,e,w=inventory()
            if mutation=='ext4': data['disks'][0]['partitions'][1]['file_system']='ext4'
            if mutation=='host': data['disks'][0]['is_system']=True
            if mutation=='wrong_type': data['disks'][0]['partitions'][0]['gpt_type']=prep.BASIC_TYPE
            if mutation=='missing_fs': data['disks'][0]['partitions'][1]['file_system']=None
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                prep.validate_layout(data,d,e,w)

    def test_overlaps_duplicate_guids_and_letters_are_rejected(self):
        for mutation in ['overlap','guid','letter','bounds']:
            data,d,e,w=inventory(); p=data['disks'][0]['partitions'][1]
            if mutation=='overlap':p['offset']=1048576
            if mutation=='guid':p['guid']=e
            if mutation=='letter':p['drive_letter']='S'
            if mutation=='bounds':p['size']=128*1024**3
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                prep.validate_layout(data,d,e,w)

    def test_bcd_commands_always_use_new_explicit_offline_store(self):
        data,d,e,w=inventory(); target=prep.validate_layout(data,d,e,w)
        store=Path('PC staging')/'EFI/Microsoft/Boot/BCD'; commands=prep.bcd_commands(store,target)
        self.assertEqual(commands[0],['/createstore',str(store)])
        self.assertTrue(all(c[:2]==['/store',str(store)] for c in commands[1:]))
        self.assertIn(['/store',str(store),'/set','{'+prep.LOADER+'}','osdevice','partition=W:'],commands)
        self.assertFalse(any('/sysstore' in c or '/import' in c for c in commands))

    def test_copy_only_small_efi_helpers_and_never_overwrite_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=staged(Path(tmp)/'source'); output=Path(tmp)/'new-esp'
            helper=root/'Windows/Boot/EFI/winsipolicy.p7b'; helper.write_bytes(b'policy')
            (root/'Windows/huge-user-data.txt').write_text('must not copy')
            prep.copy_efi_files(root,output)
            self.assertEqual((output/'EFI/Boot/bootaa64.efi').read_bytes(),fake_pe())
            self.assertEqual((output/'EFI/Microsoft/Boot/winsipolicy.p7b').read_bytes(),b'policy')
            self.assertFalse((output/'Windows').exists())
            with self.assertRaises(ValueError):prep.copy_efi_files(root,output)

    def test_staging_symlink_escape_and_nested_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=staged(Path(tmp)/'source'); outside=Path(tmp)/'outside'; outside.write_bytes(fake_pe())
            p=root/'Windows/System32/winload.efi'; p.unlink(); p.symlink_to(outside)
            with self.assertRaises(ValueError):prep.inspect_staging(root)
            with self.assertRaises(ValueError):prep.copy_efi_files(root,root/'nested')

    def test_windows_orchestration_refreshes_layout_and_writes_only_offline_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=Path(tmp); root=staged(profile/'source'); output=profile/'new-esp'; data,d,e,w=inventory()
            args=SimpleNamespace(staging=root,output=output,disk_guid=d,esp_guid=e,windows_guid=w,loader_guid=prep.LOADER)
            invoked=[]
            def fake_run(command, **kwargs):
                invoked.append(command)
                if command[1]=='/createstore': Path(command[2]).write_bytes(fake_hive())
                return subprocess.CompletedProcess(command,0,stdout=b'ok',stderr=b'')
            with mock.patch.object(prep.platform,'system',return_value='Windows'), \
                 mock.patch.dict(prep.os.environ,{'USERPROFILE':str(profile),'SystemRoot':str(profile/'sysroot')}), \
                 mock.patch.object(prep.subprocess,'check_output',return_value=json.dumps(data)) as refreshed, \
                 mock.patch.object(prep.subprocess,'run',side_effect=fake_run):
                result=prep.prepare_on_windows(args)
            self.assertEqual(refreshed.call_count,1)
            self.assertTrue(result['offline_bcd_header']['base_block_valid'])
            self.assertTrue(all(str(output) in command[2] for command in invoked))
            self.assertFalse(result['phone_writes_authorized_by_this_plan'])

    def test_bcd_tool_failure_keeps_a_failure_log_and_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=Path(tmp); root=staged(profile/'source'); output=profile/'new-esp'; data,d,e,w=inventory()
            args=SimpleNamespace(staging=root,output=output,disk_guid=d,esp_guid=e,windows_guid=w,loader_guid=prep.LOADER)
            failure=subprocess.CalledProcessError(1,['bcdedit'],output=b'failed output',stderr=b'failure reason')
            with mock.patch.object(prep.platform,'system',return_value='Windows'), \
                 mock.patch.dict(prep.os.environ,{'USERPROFILE':str(profile),'SystemRoot':str(profile/'sysroot')}), \
                 mock.patch.object(prep.subprocess,'check_output',return_value=json.dumps(data)), \
                 mock.patch.object(prep.subprocess,'run',side_effect=failure), \
                 self.assertRaises(subprocess.CalledProcessError):
                prep.prepare_on_windows(args)
            log=json.loads((output/'BCD-CREATION.json').read_text())
            self.assertEqual(log[-1]['exit_code'],1)
            self.assertEqual(log[-1]['stderr'],'failure reason')

    def test_plan_does_not_write_or_authorize_phone_deployment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=staged(Path(tmp)/'source'); output=Path(tmp)/'new-esp'; data,d,e,w=inventory()
            result=prep.plan(root,data,d,e,w,output)
            self.assertFalse(output.exists())
            self.assertFalse(result['phone_writes_authorized_by_this_plan'])
            self.assertIn('BLOCKED',result['deployment_status'])

if __name__=='__main__': unittest.main()
