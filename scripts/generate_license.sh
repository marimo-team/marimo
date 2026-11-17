#!/bin/sh
#
# Generates a license snapshot using nlf node package
# This script should fail if any intermediate step fails
set -e

cd "$(dirname "$0")/.."
snapshot=$(mktemp)
trap 'rm -f "$snapshot"' EXIT

echo "Generating license snapshot..."
printf "%s\n%s\n\n" "The contents below were generated with 'make license-snapshot', using the nlf node package." "See third_party_licenses.txt for license texts." >"$snapshot"

echo "Scanning frontend dependencies..."
(cd frontend && npx nlf -d) >>"$snapshot"

echo "Scanning lsp dependencies..."
(cd packages/lsp && npx nlf -d) >>"$snapshot"

cp "$snapshot" marimo/third_party.txt
echo "License snapshot generated successfully."
