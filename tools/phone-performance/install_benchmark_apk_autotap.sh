#!/usr/bin/env bash
# Install the benchmark APK on the vivo test device, auto-acknowledging vivo's
# Security Care screen.  This is a test-device helper only: it taps the
# "I have understood..." checkbox and "Continue installing" button when the
# package installer shows them.  Everything else is the same verification as
# install_benchmark_apk.sh: full uninstall, versionCode/versionName check,
# installed base.apk SHA check, and benchmark permission grants.
set -euo pipefail

apk=${1:?usage: $0 <app-benchmark.apk>}
pkg=com.rawr.camera.benchmark

[ -f "$apk" ] || { echo "no such APK: $apk" >&2; exit 2; }

node_coords() {
  local rid=$1
  local want_unchecked=${2:-0}
  python3 -c '
import re, sys, xml.etree.ElementTree as ET
rid = sys.argv[1]
want_unchecked = sys.argv[2] == "1"
try:
    root = ET.fromstring(sys.stdin.read())
except Exception:
    raise SystemExit(0)
for node in root.iter():
    if node.get("resource-id") != rid:
        continue
    if want_unchecked and node.get("checked") != "false":
        continue
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    if match:
        left, top, right, bottom = map(int, match.groups())
        print((left + right) // 2, (top + bottom) // 2)
        break
' "$rid" "$want_unchecked"
}

tap_node() {
  local rid=$1
  local want_unchecked=${2:-0}
  local coords
  coords=$(adb shell uiautomator dump /sdcard/rawr-installer.xml >/dev/null 2>&1 && \
           adb shell cat /sdcard/rawr-installer.xml | node_coords "$rid" "$want_unchecked") || true
  if [ -n "$coords" ]; then
    # shellcheck disable=SC2086
    adb shell input tap $coords >/dev/null 2>&1 || true
    return 0
  fi
  return 1
}

adb shell am force-stop "$pkg" >/dev/null 2>&1 || true

if adb shell pm path "$pkg" | tr -d '\r' | grep -q .; then
  adb shell pm uninstall "$pkg" >/dev/null
fi

for _ in $(seq 1 40); do
  adb shell pm path "$pkg" | tr -d '\r' | grep -q . || break
  sleep 0.5
done

install_log=$(mktemp)
timeout 180 adb install "$apk" >"$install_log" 2>&1 &
install_pid=$!

# The installer dialog blocks adb install until it is acknowledged.  Poll the
# package and the installer UI while the host-side install process is alive.
for _ in $(seq 1 90); do
  if ! kill -0 "$install_pid" 2>/dev/null; then
    break
  fi
  if adb shell pm path "$pkg" | tr -d '\r' | grep -q .; then
    break
  fi
  top=$(adb shell dumpsys activity activities | grep -m1 topResumedActivity || true)
  if printf '%s' "$top" | grep -q packageinstaller; then
    tap_node com.android.packageinstaller:id/deleted_file_state_cb 1 || true
    sleep 0.4
    tap_node android:id/button1 || true
  fi
  sleep 2
done

install_rc=0
wait "$install_pid" || install_rc=$?
cat "$install_log"
rm -f "$install_log"
if [ "$install_rc" -ne 0 ]; then
  echo "adb install returned $install_rc; verifying package state anyway" >&2
fi

for _ in $(seq 1 30); do
  device_path=$(adb shell pm path "$pkg" | tr -d '\r' | sed -n 's/^package://p' | head -1)
  [ -n "$device_path" ] && break
  sleep 1
done
[ -n "${device_path:-}" ] || { echo "package not installed: $pkg" >&2; exit 1; }

package_dump=$(adb shell dumpsys package "$pkg" | tr -d '\r')
printf '%s\n' "$package_dump" | grep -E 'versionCode=|versionName=' | head -2

device_sha=$(adb shell sha256sum "$device_path" | tr -d '\r' | awk '{print $1}')
local_sha=$(sha256sum "$apk" | awk '{print $1}')
echo "device : $device_sha  $device_path"
echo "local  : $local_sha  $apk"
[ "$device_sha" = "$local_sha" ] || {
  echo "installed APK SHA mismatch" >&2
  exit 1
}

for perm in \
  android.permission.CAMERA \
  android.permission.RECORD_AUDIO \
  android.permission.ACCESS_FINE_LOCATION \
  android.permission.ACCESS_COARSE_LOCATION \
  android.permission.POST_NOTIFICATIONS \
  android.permission.READ_MEDIA_IMAGES; do
  adb shell pm grant "$pkg" "$perm" >/dev/null 2>&1 || true
done

echo "installed $pkg $device_sha"
