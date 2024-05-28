#!/bin/sh

# If NODE_ENV is development, then we build the frontend in development mode.
# Otherwise, we build the frontend in production mode.
if [ "$NODE_ENV" = "development" ]; then
  cmd="pnpm turbo build -- --mode development"
else
  cmd="NODE_ENV=production pnpm turbo build"
fi

cd frontend
if $cmd; then
  echo "Removing old static files..."
  rm -rf ../marimo/_static/
  echo "Copying new static files..."
  mkdir -p ../marimo/_static/
  cp -R dist/* ../marimo/_static/
  rm -rf ../marimo/_static/files/wasm-intro.py
  echo "Compilation succeeded.\n"
else
  echo "Frontend compilation failed.\n"
fi
