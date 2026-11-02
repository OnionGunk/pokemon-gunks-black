#!/bin/bash
# walk.sh <prefix> <cmd>... : run each cmd (a quoted command string, may contain several bridge commands separated by ';') then screenshot; montage the shots
p=$1; shift; n=0; files=()
for c in "$@"; do
  IFS=';' read -ra parts <<< "$c"
  py -3 step.py vanilla ${p}_$n "${parts[@]}" >/dev/null || exit 1
  files+=(suite/out/${p}_$n.png); n=$((n+1))
done
magick "${files[@]}" +append suite/out/${p}_sheet.png
echo suite/out/${p}_sheet.png
