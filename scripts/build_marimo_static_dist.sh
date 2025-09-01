#!/bin/bash

set -euxo pipefail

# oso specific build script for marimo wasm environment

NODE_ENV=${NODE_ENV:-production}
PYODIDE="true"

export NODE_ENV
export PYODIDE="true"

build_dir=$1
public_packages_host=$2
public_packages_port=${3:-443}

repo_dir=$(pwd)

build_path="${repo_dir}/${build_dir}"

wasm_base_path="/wasm"

# Delete the build_path if it isn't empty
if [ -d "${build_path}" ] && [ "$(ls -A "${build_path}")" ]; then
  rm -rf "${build_path}"
fi

# Build the frontend
pushd frontend
PYODIDE=true NODE_OPTIONS=--max-old-space-size=${NODE_HEAP_SIZE:-6144} pnpm vite build --config oso.viteconfig.mts

# Move files to the build directory
mv dist "${build_path}"

# Build the pyodide lock and marimo whl
popd
pushd packages/wasm-builder
# If we are not on production node env
if [ "${NODE_ENV}" != "production" ]; then
  echo "Building for development..."
  pnpm cli build --output-dir \
      "${build_path}${wasm_base_path}" \
      --public-packages-host "${public_packages_host}" \
      --public-packages-port "${public_packages_port}" \
      --public-packages-base-path "${wasm_base_path}"
else
  echo "Building for production..."
  pnpm cli build --output-dir \
      "${build_path}${wasm_base_path}" \
      --is-production \
      --public-packages-host "${public_packages_host}" \
      --public-packages-port "${public_packages_port}" \
      --public-packages-base-path "${wasm_base_path}"
fi