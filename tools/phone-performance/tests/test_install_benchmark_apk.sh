#!/usr/bin/env bash
# Fake-device test for install_benchmark_apk.sh.
set -euo pipefail

root=$(cd "$(dirname "$0")/../../.." && pwd)
helper="$root/tools/phone-performance/install_benchmark_apk.sh"
test_root="$root/tmp/stage0/install-test"
rm -rf "$test_root"
mkdir -p "$test_root/bin" "$test_root/state"

apk="$test_root/app.apk"
printf 'fake benchmark apk\n' > "$apk"
cp "$apk" "$test_root/state/apk"

cat > "$test_root/bin/adb" <<'FAKE'
#!/usr/bin/env bash
set -euo pipefail
state=${FAKE_ADB_STATE:?}
log="$state/log"
echo "$*" >> "$log"
case "${1:-}" in
  shell)
    shift
    case "$*" in
      am\ force-stop\ *) exit 0 ;;
      pm\ path\ *)
        if [ -f "$state/installed" ]; then
          echo "package:/data/app/test/base.apk"
        fi
        ;;
      pm\ uninstall\ *)
        rm -f "$state/installed"
        echo "Success"
        ;;
      pm\ grant\ *) exit 0 ;;
      dumpsys\ package\ *)
        echo "    versionCode=32 minSdk=33 targetSdk=36"
        echo "    versionName=0.5.1"
        ;;
      sha256sum\ *)
        if [ -f "$state/installed" ]; then
          if [ "${FAKE_ADB_BAD_SHA:-0}" = 1 ]; then
            echo "0000000000000000000000000000000000000000000000000000000000000000  /data/app/test/base.apk"
          else
            sha256sum "$state/apk" | sed 's#  .*#  /data/app/test/base.apk#'
          fi
        fi
        ;;
      *) echo "unexpected adb shell: $*" >&2; exit 2 ;;
    esac
    ;;
  install)
    touch "$state/installed"
    echo "Success"
    ;;
  *) echo "unexpected adb: $*" >&2; exit 2 ;;
esac
FAKE
chmod +x "$test_root/bin/adb"

[ -x "$helper" ] || { echo "RED: helper does not exist: $helper" >&2; exit 1; }

run_helper() {
  FAKE_ADB_STATE="$test_root/state" PATH="$test_root/bin:$PATH" \
    "$helper" "$apk" >"$test_root/out.txt" 2>&1
}

touch "$test_root/state/installed"
run_helper
grep -q 'pm uninstall com.rawr.camera.benchmark' "$test_root/state/log"
grep -q 'install .*app.apk' "$test_root/state/log"
grep -q 'sha256sum /data/app/test/base.apk' "$test_root/state/log"

if FAKE_ADB_BAD_SHA=1 run_helper; then
  echo "expected helper to reject a device SHA mismatch" >&2
  exit 1
fi

echo "PASS: install helper order and SHA verification"
