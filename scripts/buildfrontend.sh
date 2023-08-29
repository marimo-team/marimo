#!/bin/sh

cd frontend
if pnpm build; then
  echo "Removing old static files..."
  rm -rf ../marimo/_static/
  echo "Copying new static files..."
  mkdir -p ../marimo/_static/
  cp -R dist/* ../marimo/_static/
  echo "Copying copilot-node-server"
  cp -LR node_modules/copilot-node-server/copilot ../marimo/_static/
  echo "Compilation succeeded.\n"
else
  echo "Frontend compilation failed.\n"
fi
