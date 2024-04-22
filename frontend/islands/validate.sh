#!/bin/sh

# Validate
# - no process.env variables in any of the js files
# - version does not equal 0.0.0-placeholder
# - files dist/main.js and dist/style.css exist

OUT_DIR=$(pwd)/dist
echo "validating $OUT_DIR"

echo "[validate: no process.env variables in any of the js files]"
grep -R "process.env" $(pwd)/dist
if [ $? -eq 0 ]; then
  echo "process.env variables found in js files"
  exit 1
fi

echo "[validate: version does not equal 0.0.0-placeholder]"
grep -R "0.0.0-placeholder" $(pwd)/dist
if [ $? -eq 0 ]; then
  echo "version is 0.0.0-placeholder"
  exit 1
fi

echo "[validate: files dist/main.js and dist/style.css exist]"
if [ ! -f "$OUT_DIR/main.js" ] || [ ! -f "$OUT_DIR/style.css" ]; then
  echo "dist/main.js or dist/style.css does not exist"
  exit 1
fi

echo "validation passed"
