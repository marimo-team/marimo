#!/bin/bash

# Directory to scan
dir="marimo"

# Counter for updated files
count=0

# Check if directory exists
if [[ ! -d "$dir" ]]; then
    echo "Directory does not exist."
    exit 1
fi

# Iterate over each Python file excluding "_test_utils" subdirectory, which
# contains data files for tests
while read file
do
    # Check if the file does not start with "# Copyright"
    if ! grep -q '^# Copyright' "$file"; then
        # Create a temporary file
        tmp_file=$(mktemp)
        # Prepend "# Copyright" followed by two new lines to the temporary file
        echo -e "# Copyright 2023 Marimo. All rights reserved." > "$tmp_file"
        # Append the original file content to the temporary file
        cat "$file" >> "$tmp_file"
        # Replace the original file with the temporary file
        mv "$tmp_file" "$file"
        ((count++))
    fi
done < <(find "$dir" -name "_test_utils" -prune -o -type f -name "*.py" -print) 

if (( count > 0 )); then
    echo "$(tput bold)added copyright notices to $count files$(tput sgr0)"
fi
