#!/usr/bin/env bash

# Usage: ./convert_types.sh <path>
# Replaces all occurrences of 'Record<string, never>' with 'Record<string, any>' in the given file or recursively in a directory.

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <file-or-directory>"
  exit 1
fi

TARGET="$1"

# Detect OS and set sed in-place flag accordingly
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS requires empty string for backup
  SED_INPLACE=(-i '')
else
  # Linux doesn't use backup extension
  SED_INPLACE=(-i)
fi

if [ -d "$TARGET" ]; then
  # Recursively find .ts files and replace in-place
  find "$TARGET" -type f -name "*.ts" -print0 | xargs -0 sed "${SED_INPLACE[@]}" -e 's/Record<string, never>/Record<string, any>/g'
elif [ -f "$TARGET" ]; then
  sed "${SED_INPLACE[@]}" -e 's/Record<string, never>/Record<string, any>/g' "$TARGET"
else
  echo "Error: $TARGET is not a file or directory"
  exit 1
fi

echo "Replacement complete."
