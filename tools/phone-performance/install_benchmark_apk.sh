#!/usr/bin/env bash
# Install the benchmark APK unattended on the vivo test device.
#
# Same-version `adb install -r` opens a Reinstall dialog; a version-code bump
# still opens vivo Security Care on updates. A full `pm uninstall` followed by
# a fresh install completes without taps in testing. Full uninstall also resets
# version history, which avoids INSTALL_FAILED_VERSION_DOWNGRADE, and restores
# the benchmark defaults.
# Never trust the adb exit code alone: verify the installed versionCode and
# the SHA-256 of the installed base.apk.
set -euo pipefail

apk=${1:?usage: $0 <app-benchmark.apk>}
pkg=com.rawr.camera.benchmark

[ -f "$apk" ] || { echo "no such APK: $apk" >&2; exit 2; }

adb shell am force-stop "$pkg" >/dev/null 2>&1 || true

if adb shell pm path "$pkg" | tr -d '\r' | grep -q .; then
  # `-k` leaves version history and rejects a lower benchmark versionCode.
  # Benchmark data is disposable; a full uninstall restores defaults too.
  adb shell pm uninstall "$pkg" >/dev/null
fi

for _ in $(seq 1 40); do
  adb shell pm path "$pkg" | tr -d '\r' | grep -q . || break
  sleep 0.5
done

install_rc=0
timeout 120 adb install "$apk" || install_rc=$?
if [ "$install_rc" -ne 0 ]; then
  echo "adb install returned $install_rc; verifying package state anyway" >&2
fi

package_dump=$(adb shell dumpsys package "$pkg" | tr -d '\r')
printf '%s\n' "$package_dump" | grep -E 'versionCode=|versionName=' | head -2

device_path=$(adb shell pm path "$pkg" | tr -d '\r' | sed -n 's/^package://p' | head -1)
[ -n "$device_path" ] || { echo "package not installed: $pkg" >&2; exit 1; }

device_sha=$(adb shell sha256sum "$device_path" | tr -d '\r' | awk '{print $1}')
local_sha=$(sha256sum "$apk" | awk '{print $1}')

echo "device : $device_sha  $device_path"
echo "local  : $local_sha  $apk"

[ "$device_sha" = "$local_sha" ] || {
  echo "installed APK SHA mismatch" >&2
  exit 1
}

# A full uninstall drops runtime permissions; restore the benchmark set.
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
