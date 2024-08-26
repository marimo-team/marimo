#!/bin/sh

# Validate
# - no process.env variables in any of the js files
# - version does not equal 0.0.0-placeholder
# - typescript data uris are not converted to data:video/mp2t
# - files dist/main.js, dist/init.js, and dist/style.css exist

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

echo "[validate: data uri does not convert data:video/mp2t]"
grep -R "data:video/mp2t" $(pwd)/dist
if [ $? -eq 0 ]; then
  echo "mininification misencoded typescript data uri."
  echo "Try naming the file with a .tsx extension."
  exit 1
fi

files=("init.js" "style.css" "main.js")
for FILE in ${files[@]}; do
  echo "[validate: file $FILE is in dist/]"
  if [ ! -f "$OUT_DIR/$FILE" ]; then
    echo "dist/$FILE does not exist"
    exit 1
  fi
done

echo "validation passed"
