#!/usr/bin/env bash
# Computer-only: no phone access or flashing.
set -euo pipefail
[[ $# -eq 3 ]] || { echo 'Usage: build_photo.sh boot_clean.zip NEW-output stop-code' >&2; exit 2; }
BACKUP=$(python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$1")
OUT=$(python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).resolve())' "$2")
STOP_CODE=$3
[[ ! -e "$OUT" ]] || { echo 'Output directory must be new' >&2; exit 2; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
python3 - <<'PY'
import hashlib,json,pathlib
for x in json.loads(pathlib.Path('Resources/PreFinal/native-lock.json').read_text()):
 assert hashlib.sha256(pathlib.Path(x['path']).read_bytes()).hexdigest()==x['sha256'],x['name']
PY
python3 Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG FD_BASE=0x9FC00000 FD_SIZE=0x00300000 FD_BLOCKS=0x300 \
 BLD_DEBUG_DAVINCI_PREFINAL=1 BLD_DEBUG_DAVINCI_FIRST_BOOT_HALT=0 \
 BLD_DEBUG_DAVINCI_PHOTO_DIAG=1 BLD_DEBUG_DAVINCI_PHOTO_STOP="$STOP_CODE" \
 PE_VALIDATION_PATH="$PWD/Resources/UfsUnblock/pe_validation.yaml"
mkdir -- "$OUT"
clang --target=aarch64-linux-gnu -c BootShim/BootShim.S -o "$OUT/BootShim.elf" \
 -DCREATE_FDT_POINTER=0 -DFDT_POINTER_ADDRESS=0 -DUEFI_BASE=0x9FC00000 -DUEFI_SIZE=0x00300000
llvm-objcopy -O binary "$OUT/BootShim.elf" "$OUT/BootShim.bin"
cp Build/davinciPkg/DEBUG_CLANGPDB/FV/DAVINCI_UEFI.fd "$OUT/DAVINCI_PREFINAL.fd"
python3 Resources/BootTests/davinci_boot_image.py --profile prefinal --backup "$BACKUP" --shim "$OUT/BootShim.bin" \
 --fd "$OUT/DAVINCI_PREFINAL.fd" --output "$OUT/davinci-prefinal-experimental.img" > "$OUT/MANIFEST.json"
