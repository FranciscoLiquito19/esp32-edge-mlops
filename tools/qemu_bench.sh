#!/usr/bin/env bash
# Run the firmware's bench mode in the QEMU emulator and compare it with the PC.
#
# Checks, with no board attached, that the firmware loads a model package from
# the model partition, decodes the test JPEGs, runs the model, and gets the
# same answers as the same model on the PC.
#
#   tools/qemu_bench.sh path/to/model.bin
#
# Needs: an ESP-IDF v5.5 shell (idf.py, esptool.py), qemu-system-xtensa
# (python $IDF_PATH/tools/idf_tools.py install qemu-xtensa), and the Python
# packages from training/requirements.txt and server/requirements.txt.
#
# The emulator has no PSRAM, camera or Wi-Fi and does not model timing, so the
# "PSRAM self-test: FAIL" line is expected and the latencies mean nothing.
set -euo pipefail

MODEL=${1:?usage: tools/qemu_bench.sh path/to/model.bin}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BUILD=${BUILD_DIR:-$ROOT/firmware/build_qemu}
PYTHON=${PYTHON:-python3}
LOG=$BUILD/qemu_bench.log
MODEL_OFFSET=0x520000   # `model` partition in firmware/partitions.csv

if [ -z "${SKIP_BUILD:-}" ]; then
    (cd "$ROOT/firmware" && idf.py -B "$BUILD" -D SDKCONFIG="$BUILD/sdkconfig" \
        -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.qemu" build)
fi

# One 8 MB flash image: bootloader, partition table, app, then the model package.
(cd "$BUILD" && esptool.py --chip esp32s3 merge_bin --fill-flash-size 8MB -o qemu_flash.bin @flash_args >/dev/null)
dd if="$MODEL" of="$BUILD/qemu_flash.bin" bs=4096 seek=$((MODEL_OFFSET / 4096)) conv=notrunc status=none

# The firmware idles after the bench, so stop the emulator once the summary is out.
: > "$LOG"
qemu-system-xtensa -M esp32s3 -nographic -no-reboot \
    -drive "file=$BUILD/qemu_flash.bin,if=mtd,format=raw" \
    -global driver=timer.esp32s3.timg,property=wdt_disable,value=true \
    -serial "file:$LOG" -monitor none >/dev/null 2>&1 &
QEMU_PID=$!
trap 'kill $QEMU_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do
    grep -aq "^META \|BENCH_DONE {\"ok\":false" "$LOG" && break
    kill -0 $QEMU_PID 2>/dev/null || break
    sleep 1
done
kill $QEMU_PID 2>/dev/null || true

grep -a "^BENCH" "$LOG" || { echo "the bench did not run; see $LOG" >&2; exit 1; }

(cd "$ROOT/training" && "$PYTHON" -m edgeml.bench_compare --log "$LOG" --package "$MODEL" \
    --golden "$ROOT/firmware/main/golden")
"$PYTHON" "$ROOT/tools/check_meta.py" "$LOG"
