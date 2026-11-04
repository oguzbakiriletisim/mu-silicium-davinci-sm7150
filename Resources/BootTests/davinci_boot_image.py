#!/usr/bin/env python3
"""Package a temporary-test Android image from the actual davinci boot backup.

No phone tools, flashing, AVB signing, or inferred Android header parameters.
Supports the examined v1 layout only; refuses different component layouts.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

PARTITION_SIZE = 128 * 1024 * 1024
HEADER_SIZE = 1648
FIELD_NAMES = ['kernel_size', 'kernel_addr', 'ramdisk_size', 'ramdisk_addr',
               'second_size', 'second_addr', 'tags_addr', 'page_size', 'header_version', 'os_version_raw']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def align(size, page):
    return (size + page - 1) // page * page


def read_backup(path):
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            members = [i for i in archive.infolist() if not i.is_dir()]
            if len(members) != 1 or Path(members[0].filename).name != 'boot_clean.img' or members[0].file_size != PARTITION_SIZE:
                raise ValueError('Expected ZIP containing only the 128 MiB boot_clean.img')
            return archive.read(members[0])
    if path.stat().st_size != PARTITION_SIZE:
        raise ValueError('Expected the actual 128 MiB partition backup')
    return path.read_bytes()


def fdt_blocks(data):
    blocks, pos = [], 0
    while pos < len(data):
        if pos + 40 > len(data):
            raise ValueError('Truncated appended FDT header')
        magic, size, structure, strings, reserve, version, last, cpu, string_size, structure_size = struct.unpack_from('>10I', data, pos)
        if magic != 0xd00dfeed or not 40 <= size <= len(data) - pos or version < 16 or last > version:
            raise ValueError('Invalid appended FDT')
        if strings + string_size > size or structure + structure_size > size or reserve >= size:
            raise ValueError('FDT section exceeds block')
        blocks.append({'offset': pos, 'size': size, 'sha256': digest(data[pos:pos + size])})
        pos += size
    if not blocks:
        raise ValueError('No original appended DTBs found')
    return blocks


def android_id(kernel):
    sha = hashlib.sha1()
    sha.update(kernel)
    sha.update(struct.pack('<I', len(kernel)))
    for _ in range(3):  # Empty ramdisk, second and v1 recovery_dtbo.
        sha.update(struct.pack('<I', 0))
    return sha.digest() + bytes(12)


def inspect(data):
    if len(data) != PARTITION_SIZE or data[:8] != b'ANDROID!':
        raise ValueError('Not the 128 MiB Android boot partition backup')
    header = dict(zip(FIELD_NAMES, struct.unpack_from('<10I', data, 8)))
    page = header['page_size']
    if header['header_version'] != 1 or not 2048 <= page <= 65536 or page & (page - 1):
        raise ValueError('Unsupported boot header/page size; do not infer parameters')
    dtbo_size, dtbo_offset, hdr_size = struct.unpack_from('<IQI', data, 1632)
    if hdr_size != HEADER_SIZE or header['ramdisk_size'] or header['second_size'] or dtbo_size or dtbo_offset:
        raise ValueError('Only the examined v1, empty ramdisk/second/recovery_dtbo layout is supported')
    end = page + header['kernel_size']
    if header['kernel_size'] == 0 or end > len(data):
        raise ValueError('Invalid kernel extent')
    kernel = data[page:end]
    if android_id(kernel) != data[576:608]:
        raise ValueError('Original Android SHA-1 image ID mismatch')
    decoder = zlib.decompressobj(31)
    raw = decoder.decompress(kernel, 128 * 1024 * 1024)
    if not decoder.eof or decoder.unconsumed_tail or len(raw) < 64 or raw[56:60] != b'ARMd':
        raise ValueError('Expected bounded gzip ARM64 kernel plus appended DTBs')
    tail = decoder.unused_data
    blocks = fdt_blocks(tail)
    footer = struct.unpack('>4sIIQQQ28s', data[-64:])
    if footer[0] != b'AVBf' or footer[1] != 1 or footer[3] != align(end, page):
        raise ValueError('Original AVB footer/data extent mismatch')
    vbmeta_offset, vbmeta_size = footer[4:6]
    if vbmeta_offset < footer[3] or vbmeta_offset + vbmeta_size > len(data) - 64:
        raise ValueError('Invalid original vbmeta extent')
    vbmeta = data[vbmeta_offset:vbmeta_offset + vbmeta_size]
    if len(vbmeta) < 256 or vbmeta[:4] != b'AVB0':
        raise ValueError('Missing original AVB0 metadata')
    auth, aux, algorithm = struct.unpack_from('>QQI', vbmeta, 12)
    desc_offset, desc_size = struct.unpack_from('>QQ', vbmeta, 96)
    pos = 256 + auth + desc_offset
    limit = pos + desc_size
    if 256 + auth + aux != len(vbmeta) or limit > len(vbmeta):
        raise ValueError('Invalid original AVB descriptor bounds')
    hash_descriptors = []
    while pos < limit:
        if pos + 16 > limit:
            raise ValueError('Truncated AVB descriptor')
        tag, following = struct.unpack_from('>QQ', vbmeta, pos)
        stop = pos + 16 + following
        if stop > limit or stop <= pos:
            raise ValueError('AVB descriptor extends outside metadata')
        if tag == 2:
            if following < 116:
                raise ValueError('Short AVB hash descriptor')
            length, = struct.unpack_from('>Q', vbmeta, pos + 16)
            alg = vbmeta[pos + 24:pos + 56].split(b'\0')[0]
            name_size, salt_size, hash_size, flags = struct.unpack_from('>4I', vbmeta, pos + 56)
            begin = pos + 132
            if begin + name_size + salt_size + hash_size > stop or length > footer[3]:
                raise ValueError('Invalid AVB hash descriptor payload')
            name = vbmeta[begin:begin + name_size].decode('ascii')
            salt = vbmeta[begin + name_size:begin + name_size + salt_size]
            expected = vbmeta[begin + name_size + salt_size:begin + name_size + salt_size + hash_size]
            if alg != b'sha256' or expected != hashlib.sha256(salt + data[:length]).digest():
                raise ValueError('Original AVB SHA-256 data digest mismatch')
            hash_descriptors.append({'partition_name': name, 'image_size': length, 'digest_verified': True})
        pos = stop
    if len(hash_descriptors) != 1 or hash_descriptors[0]['partition_name'] != 'boot':
        raise ValueError('Expected original boot hash descriptor')
    packed = header['os_version_raw']
    header.update(os_version='.'.join(str((packed >> shift) & 127) for shift in [25, 18, 11]),
                  os_patch_level=f'{2000 + ((packed & 2047) >> 4):04d}-{packed & 15:02d}',
                  header_size=hdr_size)
    report = {'original_size': len(data), 'original_sha256': digest(data), 'header': header,
              'original_kernel': {'gzip_member_size': len(kernel) - len(tail), 'decompressed_size': len(raw),
                                  'arm64_text_offset': struct.unpack_from('<Q', raw, 8)[0]},
              'appended_dtbs': blocks, 'appended_dtb_sha256': digest(tail),
              'avb': {'footer_present': True, 'original_image_size': footer[3], 'vbmeta_offset': vbmeta_offset,
                      'vbmeta_size': vbmeta_size, 'algorithm_type': algorithm, 'hash_descriptors': hash_descriptors},
              'physical_boot_verified': False}
    return report, tail


def package(backup, shim, fd):
    report, dtbs = inspect(backup)
    if len(shim) != 144 or shim[56:60] != b'ARMd' or struct.unpack_from('<QQ', shim, 8) != (0x9fc00000, 0x300000):
        raise ValueError('BootShim does not match the reviewed davinci configuration')
    if len(fd) != 0x300000 or fd[40:44] != b'_FVH':
        raise ValueError('Expected the reviewed 3 MiB davinci FD')
    instruction, = struct.unpack_from('<I', fd)
    displacement = instruction & 0x03ffffff
    if displacement & 0x02000000:
        displacement -= 0x04000000
    entry_offset = displacement * 4
    if instruction & 0xfc000000 != 0x14000000 or not 44 <= entry_offset < len(fd):
        raise ValueError('FD does not start with an in-range AARCH64 branch to SEC')
    # Required for this first test: stop in uncompressed SEC before DXE/UFS.
    if b'DAVINCI FIRST BOOT: PREPI REACHED' not in fd:
        raise ValueError('FD does not contain the explicit first-boot halt marker')
    member = bytearray(gzip.compress(shim + fd, compresslevel=9, mtime=0))
    member[9] = 255  # Fixed gzip OS byte, independent of the packaging host.
    payload = bytes(member) + dtbs
    page = report['header']['page_size']
    header = bytearray(backup[:page])
    struct.pack_into('<I', header, 8, len(payload))
    header[576:608] = android_id(payload)
    image = bytes(header) + payload
    image += bytes(align(len(image), page) - len(image))
    # Never carry the original, now-invalid AVB footer/hash into the new image.
    report.update(image_size=len(image), image_sha256=digest(image), kernel_payload_size=len(payload),
                  bootshim_sha256=digest(shim), fd_sha256=digest(fd), fd_entry_branch_offset=entry_offset,
                  preserved_header_bytes_except=['kernel_size [8:12]', 'image_id [576:608]'],
                  new_avb_footer_present=False, new_image_avb_signed=False,
                  purpose='TEMPORARY FASTBOOT BOOT EXPERIMENT ONLY; NO FLASH',
                  expected_behavior='PrePi marker then deliberate halt BEFORE DXE/storage',
                  fastboot_boot_support_verified=False)
    return image, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--shim', type=Path)
    parser.add_argument('--fd', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    backup = read_backup(args.backup)
    if args.output:
        if not args.shim or not args.fd:
            parser.error('--shim and --fd required with --output')
        image, report = package(backup, args.shim.read_bytes(), args.fd.read_bytes())
        # Exclusive creation, so even a mistaken input/output path cannot overwrite.
        with args.output.open('xb') as stream:
            stream.write(image)
    else:
        report, _ = inspect(backup)
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
