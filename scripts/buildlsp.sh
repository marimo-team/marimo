#!/bin/sh

cd lsp
if pnpm build; then
  echo "Removing old lsp files..."
  rm -rf ../marimo/_lsp/
  echo "Copying new lsp files..."
  mkdir ../marimo/_lsp
  cp dist/index.cjs ../marimo/_lsp/
  # There seems to be a discrepancy between CI and mac for pnpm builds
  if [ -d dist/copilot ]; then
    cp -R dist/copilot ../marimo/_lsp/copilot
  else
    mkdir ../marimo/_lsp
    cp -R dist ../marimo/_lsp/copilot
  fi
  echo "Compilation succeeded.\n"
else
  echo "LSP compilation failed.\n"
fi
