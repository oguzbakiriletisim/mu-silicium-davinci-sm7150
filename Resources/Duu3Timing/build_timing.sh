#!/usr/bin/env bash
# PC-only phase isolation. No ADB/Fastboot/disk mutation.
set -euo pipefail
[[ $# -eq 5 ]] || { echo 'Usage: build_timing.sh boot_clean.zip NEW-out stop delay-us max-native-index' >&2; exit 2; }
BACKUP=$(python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$1")
OUT=$(python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).resolve())' "$2")
STOP_CODE=$3
DELAY_US=$4
MAX_NATIVE=$5
[[ "$DELAY_US" == 0 || "$DELAY_US" == 1000000 ]] || exit 2
[[ "$MAX_NATIVE" == 9 || "$MAX_NATIVE" == 10 || "$MAX_NATIVE" == 12 ]] || exit 2
if [[ "$MAX_NATIVE" == 12 ]]; then
  [[ "$STOP_CODE" == 0xB0C4 || "$STOP_CODE" == 0xB0C5 || "$STOP_CODE" == 0xB0C6 ]] || exit 2
fi
[[ ! -e "$OUT" ]] || { echo 'Output directory must be new' >&2; exit 2; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
python3 - <<'PY'
import hashlib,json,pathlib
for x in json.loads(pathlib.Path('Resources/PreFinal/native-lock.json').read_text()):
 assert hashlib.sha256(pathlib.Path(x['path']).read_bytes()).hexdigest()==x['sha256'],x['name']
PY
python3 Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG FD_BASE=0x9FC00000 FD_SIZE=0x00300000 FD_BLOCKS=0x300 \
 BLD_DEBUG_DAVINCI_PREFINAL=1 BLD_DEBUG_DAVINCI_FIRST_BOOT_HALT=0 BLD_DEBUG_DAVINCI_PHOTO_DIAG=1 \
 BLD_DEBUG_DAVINCI_PHOTO_STOP="$STOP_CODE" BLD_DEBUG_DAVINCI_PHOTO_DELAY_US="$DELAY_US" \
 BLD_DEBUG_DAVINCI_PHOTO_PHASE_TEST=1 BLD_DEBUG_DAVINCI_PHOTO_MAX_NATIVE="$MAX_NATIVE" \
 PE_VALIDATION_PATH="$PWD/Resources/UfsUnblock/pe_validation.yaml"
mkdir -- "$OUT"
clang --target=aarch64-linux-gnu -c BootShim/BootShim.S -o "$OUT/BootShim.elf" \
 -DCREATE_FDT_POINTER=0 -DFDT_POINTER_ADDRESS=0 -DUEFI_BASE=0x9FC00000 -DUEFI_SIZE=0x00300000
llvm-objcopy -O binary "$OUT/BootShim.elf" "$OUT/BootShim.bin"
cp Build/davinciPkg/DEBUG_CLANGPDB/FV/DAVINCI_UEFI.fd "$OUT/DAVINCI_PREFINAL.fd"
python3 Resources/BootTests/davinci_boot_image.py --profile prefinal --backup "$BACKUP" --shim "$OUT/BootShim.bin" \
 --fd "$OUT/DAVINCI_PREFINAL.fd" --output "$OUT/davinci-prefinal-experimental.img" > "$OUT/MANIFEST.json"
python3 - "$OUT/MANIFEST.json" "$STOP_CODE" "$DELAY_US" "$MAX_NATIVE" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);d=json.loads(p.read_text())
d.update(phase_test=True,stop=sys.argv[2],delay_us=int(sys.argv[3]),max_native=int(sys.argv[4]),
 expected_behavior='Controlled checkpoint halt; mandatory barrier forbids UFSDxe StartImage; no disk requests',
 fastboot_boot_support_verified_for_previous_duu2_on_this_phone=True,
 physical_boot_verified=False)
p.write_text(json.dumps(d,indent=2)+'\n')
PY
