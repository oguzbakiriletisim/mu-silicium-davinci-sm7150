#!/usr/bin/env bash
# Computer-only build/package. Never invokes ADB, Fastboot or disk tools.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo 'Usage: build_davinci_first_boot.sh /path/boot_clean.zip /path/NEW-output-directory' >&2
  exit 2
fi
BACKUP_PATH=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$1")
OUTPUT_PATH=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$2")
if [[ -e "$OUTPUT_PATH" ]]; then
  echo 'Output directory must not already exist.' >&2
  exit 2
fi
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd -- "$REPO_ROOT"
# These are reviewed UEFI destination values, NOT inferred Android header fields.
source Resources/Configs/davinci.conf
python3 Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG \
  FD_BASE="$TARGET_FD_BASE" FD_SIZE="$TARGET_FD_SIZE" FD_BLOCKS="$TARGET_FD_BLOCKS" \
  BLD_DEBUG_DAVINCI_FIRST_BOOT_HALT=1
mkdir -- "$OUTPUT_PATH"
clang --target=aarch64-linux-gnu -c BootShim/BootShim.S -o "$OUTPUT_PATH/BootShim.elf" \
  -DCREATE_FDT_POINTER="$TARGET_CREATE_POINTER" -DFDT_POINTER_ADDRESS="$TARGET_POINTER_ADDRESS" \
  -DUEFI_BASE="$TARGET_FD_BASE" -DUEFI_SIZE="$TARGET_FD_SIZE"
llvm-objcopy -O binary "$OUTPUT_PATH/BootShim.elf" "$OUTPUT_PATH/BootShim.bin"
cp Build/davinciPkg/DEBUG_CLANGPDB/FV/DAVINCI_UEFI.fd "$OUTPUT_PATH/DAVINCI_FIRST_BOOT.fd"
python3 Resources/BootTests/davinci_boot_image.py --backup "$BACKUP_PATH" \
  --shim "$OUTPUT_PATH/BootShim.bin" --fd "$OUTPUT_PATH/DAVINCI_FIRST_BOOT.fd" \
  --output "$OUTPUT_PATH/davinci-prepi-halt-experimental.img" > "$OUTPUT_PATH/MANIFEST.json"
