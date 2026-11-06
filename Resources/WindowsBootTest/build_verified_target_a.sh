#!/usr/bin/env bash
# Host only. Never commits Microsoft input or an FD containing Microsoft bytes.
set -euo pipefail
[[ $# == 2 ]] || { echo 'Usage: build_verified_target_a.sh INPUT.zip NEW-private-output' >&2; exit 2; }
INPUT=$(realpath -- "$1")
OUT=$(realpath -m -- "$2")
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
python3 Resources/WindowsBootTest/verify_target_a.py "$INPUT" --output "$OUT"
python3 Resources/WindowsBootTest/ram_gpt.py "$OUT/efi-fat32.img" "$OUT/ram-disk.img"
fallocate --dig-holes "$OUT/efi-fat32.img"
fallocate --dig-holes "$OUT/ram-disk.img"
python3 Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG \
 FD_BASE=0x9FC00000 FD_SIZE=0x00300000 FD_BLOCKS=0x300 \
 BLD_DEBUG_WINDOWS_BOOT_TEST=1 BLD_DEBUG_WINDOWS_BOOT_SMOKE=1 \
 BLD_DEBUG_WINDOWS_FAT_IMAGE="$OUT/ram-disk.img" \
 BLD_DEBUG_DAVINCI_ACPI_STORAGE_DEV=1 BLD_DEBUG_DAVINCI_CPU_ONLY_ACPI=1 \
 BLD_DEBUG_DAVINCI_PREFINAL=0 BLD_DEBUG_DAVINCI_PHOTO_DIAG=0 BLD_DEBUG_DAVINCI_FIRST_BOOT_HALT=0 \
 PE_VALIDATION_PATH="$PWD/Resources/UfsUnblock/pe_validation.yaml" > "$OUT/build.log" 2>&1
python3 - <<'PY'
from pathlib import Path
import subprocess
for p in Path('Build/davinciPkg/DEBUG_CLANGPDB/FV').rglob('*'):
    if p.is_file() and p.stat().st_size>20*1024*1024:
        subprocess.run(['fallocate','--dig-holes',str(p)],check=True)
PY
cp --sparse=always Build/davinciPkg/DEBUG_CLANGPDB/FV/DAVINCI_UEFI.fd "$OUT/WINDOWS_BOOT_TEST.fd"
cp --sparse=always Build/davinciPkg/DEBUG_CLANGPDB/FV/FVMAIN.Fv "$OUT/FVMAIN.Fv"
cp Build/davinciPkg/DEBUG_CLANGPDB/AARCH64/DavinciWindowsBootSmoke.efi "$OUT/DavinciWindowsBootSmoke.efi"
python3 Resources/WindowsBootTest/audit.py "$OUT" > "$OUT/AUDIT.json"
# No Android boot packaging: host execution is evaluated separately.
