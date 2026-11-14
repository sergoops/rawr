#!/usr/bin/env bash
set -u

if [ "${1:-}" = "shell" ] && [ "${2:-}" = "id" ]; then
  echo "uid=0(root) gid=0(root) groups=0(root)"
  exit 0
fi
exit 1
