#!/usr/bin/env bash

# Check if marimo/_static/index.html exists
if [ ! -f "marimo/_static/index.html" ]; then
  echo "Error: marimo/_static/index.html does not exist"
  exit 1
fi

wheel_file=$(ls dist/*.whl)
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  size=$(stat -f%z "$wheel_file")
else
  # Linux
  size=$(stat -c%s "$wheel_file")
fi

# TODO: Restore the 2 MiB limit after the host-protocol migration removes
# the superseded code.
max_size=2359296 # 2.25 MiB
if [ "$size" -gt "$max_size" ]; then
  echo "Wheel file exceeds the size limit ($max_size bytes)"
  echo "Size: $size bytes"
  exit 1
fi

echo "Wheel file is $size bytes"
