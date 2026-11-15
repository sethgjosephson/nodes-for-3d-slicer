#!/usr/bin/env bash
# Runs one workflow test inside Slicer: tests/run.sh tests/workflows/NAME.py
# Logs and screenshots go to tests/out/NAME/.
# SLICER can point at a different Slicer.exe.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(dirname "$here")"
slicer="${SLICER:-$LOCALAPPDATA/slicer.org/3D Slicer 5.10.0/Slicer.exe}"
test="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
name="$(basename "$1" .py)"
out="$here/out/$name"
mkdir -p "$out"
rm -f "$out"/*.png "$out/log.txt"
export NODE_EDITOR_TEST="$(cygpath -w "$test")"
export NODE_EDITOR_OUT="$(cygpath -w "$out/log.txt")"
export SLICER_NODE_EDITOR_DEBUG=1
"$slicer" --no-splash --testing \
  --additional-module-paths "$(cygpath -w "$repo/SlicerNodeEditor")" \
  --python-script "$(cygpath -w "$here/slicer_bootstrap.py")" >/dev/null 2>&1
cat "$out/log.txt" 2>/dev/null
# Slicer's own exit code is not reliable in testing mode; the log decides.
grep -q "^RESULT: PASS" "$out/log.txt" 2>/dev/null
