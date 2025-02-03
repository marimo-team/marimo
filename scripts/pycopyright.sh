#!/usr/bin/env bash

# Directories to scan
dir="marimo"

# Counter for updated files
count=0

skip_dirs=(
    "marimo/_smoke_tests"
)
# Iterate over each Python file and add copyright notice if it isn't there
while read file; do
    # Check if the file is in a directory to skip
    skip=false
    for skip_dir in "${skip_dirs[@]}"; do
        if [[ $file == $skip_dir* ]]; then
            skip=true
            break
        fi
    done

    # If the file is not in a directory to skip, process it
    if ! $skip; then
        # Check if the file does not start with "# Copyright"
        if ! grep -q '^# Copyright' "$file"; then
            # Create a temporary file
            tmp_file=$(mktemp)
            # Prepend "# Copyright" followed by two new lines to the temporary file
            echo -e "# Copyright 2025 Marimo. All rights reserved." >"$tmp_file"
            # Append the original file content to the temporary file
            cat "$file" >>"$tmp_file"
            # Replace the original file with the temporary file
            mv "$tmp_file" "$file"
            ((count++))
        fi
    fi
done < <(find "$dir" -type f -name "*.py" -print)

if ((count > 0)); then
    echo "$(tput bold)added copyright notices to $count files$(tput sgr0)"
fi
