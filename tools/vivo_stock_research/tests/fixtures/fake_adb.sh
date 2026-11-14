#!/usr/bin/env bash
set -u

cmd=${1:-}
case "$cmd" in
  shell)
    shift
    sub=${1:-}
    shift || true
    case "$sub" in
      id)
        echo "uid=2000(shell) gid=2000(shell) groups=2000(shell)"
        ;;
      getenforce)
        echo "Enforcing"
        ;;
      getprop)
        echo "google/raven/raven:16/BP1A.250505.005/1234567:user/release-keys"
        ;;
      pm)
        echo "package:/system/priv-app/VivoCamera/VivoCamera.apk=com.android.camera"
        ;;
      ls)
        while [[ ${1:-} == -* ]]; do shift; done
        path=${1:-}
        if [[ "$path" == /data/data/* ]]; then
          echo "ls: $path: Permission denied" >&2
          exit 1
        fi
        echo "-rw-r--r-- 1 root root u:object_r:vendor_configs_file:s0 1234 2026-11-14 10:00 $path"
        ;;
      test)
        while [[ ${1:-} == -* ]]; do shift; done
        path=${1:-}
        if [[ "$path" == /data/data/* ]]; then
          exit 1
        fi
        exit 0
        ;;
      *)
        exit 1
        ;;
    esac
    ;;
  pull)
    remote=${2:-}
    local=${3:-}
    mkdir -p "$(dirname "$local")"
    printf 'fixture:%s\n' "$remote" > "$local"
    ;;
  *)
    exit 1
    ;;
esac
