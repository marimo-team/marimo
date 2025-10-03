#!/bin/bash

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

if [ $size -gt 2097152 ]; then
  echo "Wheel file is larger than 2mb"
  echo "Size: $size bytes"
  exit 1
fi

echo "Wheel file is $size bytes"
