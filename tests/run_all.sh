#!/usr/bin/env bash
# Runs every workflow test, one Slicer session each, and prints a summary.
here="$(cd "$(dirname "$0")" && pwd)"
pass=0; fail=0; failed=""
for t in "$here"/workflows/*.py; do
  name="$(basename "$t" .py)"
  if bash "$here/run.sh" "$t" >/dev/null 2>&1; then
    echo "PASS  $name"; pass=$((pass+1))
  elif grep -q "^RESULT: SKIP" "$here/out/$name/log.txt" 2>/dev/null; then
    echo "SKIP  $name"
  else
    echo "FAIL  $name"; fail=$((fail+1)); failed="$failed $name"
  fi
done
echo "$pass passed, $fail failed$failed"
[ "$fail" -eq 0 ]
