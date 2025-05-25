#!/bin/sh
#
# Builds the copilot lsp, then copies the generated dist/ folder to
# marimo/_lsp/copilot

# This script should fail if any intermediate step fails
set -e

cd lsp
if pnpm build; then
  echo "Removing old lsp files..."
  rm -rf ../marimo/_lsp/
  echo "Copying new lsp files..."
  mkdir -p ../marimo/_lsp
  cp dist/index.cjs ../marimo/_lsp/
  # There seems to be a discrepancy between CI and mac for pnpm builds
  if [ -d dist/copilot ]; then
    echo "branch 1"
    cp -R dist/copilot ../marimo/_lsp/copilot
  else
    echo "branch 2"
    cp -R dist ../marimo/_lsp/copilot
  fi
  echo "Compilation succeeded.\n"
else
  echo "LSP compilation failed.\n"
fi
