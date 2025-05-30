#!/bin/sh
#
# Generates a license snapshot using nlf node package
# This script should fail if any intermediate step fails
set -e

echo "Generating license snapshot..."
rm -f third_party.txt
echo "The contents below were generated with 'make license-snapshot', using the nlf node package.\nSee third_party_licenses.txt for license texts.\n" >third_party.txt

echo "Scanning frontend dependencies..."
cd frontend && npx nlf -d >>../third_party.txt

echo "Scanning lsp dependencies..."
cd ../lsp && npx nlf -d >>../third_party.txt

cd ..
echo "License snapshot generated successfully."
