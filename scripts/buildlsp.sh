#!/bin/sh

cd lsp
if pnpm build; then
  echo "Removing old lsp files..."
  rm -rf ../marimo/_lsp/
  echo "Copying new lsp files..."
  mkdir -p ../marimo/_lsp/
  cp -R dist/* ../marimo/_lsp/
  echo "Compilation succeeded.\n"
else
  echo "LSP compilation failed.\n"
fi
