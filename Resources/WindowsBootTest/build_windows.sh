#!/usr/bin/env bash
# PC development build only. No phone commands and no Microsoft binaries in Git.
set -euo pipefail
[[ $# -ge 2 ]] || { echo 'Usage: build_windows.sh NEW-output --fixture | --staging PATH [--bcd PATH]' >&2; exit 2; }
OUT=$(python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).resolve())' "$1");shift
[[ ! -e "$OUT" ]] || { echo 'Output directory must be new' >&2; exit 2; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
mkdir -- "$OUT"
python3 Resources/WindowsBootTest/fat32.py "$@" --output "$OUT/efi-fat32.img" > "$OUT/FAT_MANIFEST.json"
if command -v fallocate >/dev/null; then fallocate --dig-holes "$OUT/efi-fat32.img"; fi
python3 Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG \
 FD_BASE=0x9FC00000 FD_SIZE=0x00300000 FD_BLOCKS=0x300 \
 BLD_DEBUG_WINDOWS_BOOT_TEST=1 BLD_DEBUG_WINDOWS_FAT_IMAGE="$OUT/efi-fat32.img" \
 BLD_DEBUG_DAVINCI_ACPI_STORAGE_DEV=1 BLD_DEBUG_DAVINCI_CPU_ONLY_ACPI=1 \
 BLD_DEBUG_DAVINCI_PREFINAL=0 BLD_DEBUG_DAVINCI_PHOTO_DIAG=0 BLD_DEBUG_DAVINCI_FIRST_BOOT_HALT=0 \
 PE_VALIDATION_PATH="$PWD/Resources/UfsUnblock/pe_validation.yaml" > "$OUT/build.log" 2>&1
if command -v fallocate >/dev/null; then
  python3 - <<'PY'
from pathlib import Path
import subprocess
# Generated zero-filled FAT/FV intermediates only; hole punching preserves bytes.
for p in Path('Build/davinciPkg/DEBUG_CLANGPDB/FV').rglob('*'):
    if p.is_file() and p.stat().st_size>20*1024*1024:
        subprocess.run(['fallocate','--dig-holes',str(p)],check=True)
PY
fi
cp --sparse=always Build/davinciPkg/DEBUG_CLANGPDB/FV/DAVINCI_UEFI.fd "$OUT/WINDOWS_BOOT_TEST.fd"
cp --sparse=always Build/davinciPkg/DEBUG_CLANGPDB/FV/FVMAIN.Fv "$OUT/FVMAIN.Fv"
python3 Resources/WindowsBootTest/audit.py "$OUT" > "$OUT/AUDIT.json"
# Deliberately not Android-packed or advertised for physical use: real Microsoft
# payload, firmware contracts and phone behavior need review before delivery.
