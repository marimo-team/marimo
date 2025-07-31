#!/bin/sh
#
# Builds the copilot lsp, then copies the generated dist/ folder to
# marimo/_lsp/copilot

# This script should fail if any intermediate step fails
set -e

if pnpm turbo build --filter @marimo-team/lsp; then
  echo "Removing old lsp files..."
  rm -rf marimo/_lsp/
  echo "Copying new lsp files..."
  mkdir -p marimo/_lsp
  cp packages/lsp/dist/index.cjs marimo/_lsp/
  # There seems to be a discrepancy between CI and mac for pnpm builds
  if [ -d packages/lsp/dist/copilot/dist ]; then
    echo "Copying dist/copilot to _lsp/copilot"
    cp -R packages/lsp/dist/copilot/dist/. marimo/_lsp/copilot/
  elif [ -d packages/lsp/dist/dist ]; then
    echo "Copying contents of dist/dist/. to _lsp/copilot"
    cp -R packages/lsp/dist/dist/. marimo/_lsp/copilot/
  else
    echo "Copying the contents of dist/. to _lsp/copilot"
    # Do NOT place dist as a subdirectory in copilot/, just copy its contents;
    # the period after dist/ is important here.
    cp -R packages/lsp/dist/. marimo/_lsp/copilot/
  fi
  echo "Compilation succeeded.\n"
else
  echo "LSP compilation failed.\n"
fi
