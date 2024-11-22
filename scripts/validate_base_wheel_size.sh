#!/bin/bash

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
