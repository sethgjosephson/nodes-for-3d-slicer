#!/usr/bin/env bash
# Runs one workflow test inside Slicer: tests/run.sh tests/workflows/NAME.py Logs and screenshots go to tests/out/NAME/.
# SLICER can point at a different Slicer.exe.
# A test that needs installed extensions names them on a line of its own:
#   # extensions: SlicerDMRI UKFTractography
# Slicer's testing mode does not load installed extensions, so their module folders are passed in as additional module paths.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(dirname "$here")"
slicer="${SLICER:-$LOCALAPPDATA/slicer.org/3D Slicer 5.10.0/Slicer.exe}"
test="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
name="$(basename "$1" .py)"
out="$here/out/$name"
mkdir -p "$out"
rm -f "$out"/*.png "$out/log.txt"

paths=("$(cygpath -w "$repo/SlicerNodeEditor")")
root="$(dirname "$slicer")"
for ext in $(sed -n 's/^# extensions: *//p' "$test"); do
  found=0
  for extdir in "$root"/slicer.org/Extensions-*/"$ext"; do
    [ -d "$extdir" ] || continue
    for sub in "$extdir"/lib/Slicer-*/cli-modules \
               "$extdir"/lib/Slicer-*/qt-loadable-modules \
               "$extdir"/lib/Slicer-*/qt-scripted-modules; do
      [ -d "$sub" ] || continue
      paths+=("$(cygpath -w "$sub")")
      PATH="$sub:$PATH"
      found=1
    done
  done
  if [ "$found" -eq 0 ]; then
    echo "SKIP: extension $ext is not installed" | tee "$out/log.txt"
    echo "RESULT: SKIP" | tee -a "$out/log.txt"
    exit 0
  fi
done
export PATH

export NODE_EDITOR_TEST="$(cygpath -w "$test")"
export NODE_EDITOR_OUT="$(cygpath -w "$out/log.txt")"
export SLICER_NODE_EDITOR_DEBUG=1
"$slicer" --no-splash --testing \
  --additional-module-paths "${paths[@]}" \
  --python-script "$(cygpath -w "$here/slicer_bootstrap.py")" >/dev/null 2>&1
cat "$out/log.txt" 2>/dev/null
# Slicer's own exit code is not reliable in testing mode; the log decides.
grep -q "^RESULT: PASS" "$out/log.txt" 2>/dev/null
