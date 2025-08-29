#!/bin/bash

# This is an extension by the OSO team that isn't necessarily intended to go
# upstream (yet?). This creates a build of the marimo-base inside of a docker
# container so that the script to modify the pyproject.toml does not
# accidentally cause us to check the changes into git. This is mostly used for
# fast turn arounds on locally testing a fork in the wasm environment. This
# should be called from the root of the repository

set -euxo pipefail

# CHECK IF USE_OVERLAYFS is on it is off by default
USE_OVERLAYFS=${USE_OVERLAYFS:-false}

CURRENT_DIR=$(pwd)

cleanup() {
    echo "Cleaning up"
    # Usually this does nothing unless we are using the overlayfs
}

mkdir -p /container/workspace

if [ "$USE_OVERLAYFS" = true ]; then
    echo "Using overlayfs"

    # Unset the original cleanup function to override
    unset cleanup
    
    cleanup() {
        echo "Cleaning up"
        cd /
        umount /container/workspace/.pixi
        umount /container/workspace
        umount /tmp/overlay
    }

    always_unmount() {
        echo "unmounting after error"
        cleanup
    }

    trap 'always_unmount' ERR

    echo "Creating overlayfs for marimo-base build so we can modify pyproject.toml on the fly"
    # Create an overlayfs of the main repository
    mkdir -p /tmp/pixi
    mkdir -p /tmp/overlay
    mount -t tmpfs tmpfs /tmp/overlay
    mkdir -p /tmp/overlay/{upper,work}
    mount -t overlay overlay -o lowerdir=${CURRENT_DIR},upperdir=/tmp/overlay/upper,workdir=/tmp/overlay/work /container/workspace

    # Bind mount the pixi environment on top of the overlayfs so we can use pixi
    mount --bind /tmp/pixi /container/workspace/.pixi
else
    echo "Not using overlayfs copying files directly"

    cp -r ${CURRENT_DIR}/* /container/workspace/
fi

pushd /container/workspace

OUTPUT_DIR=${1}

mkdir -p ${OUTPUT_DIR}

pixi run python scripts/modify_pyproject_for_marimo_base.py
pixi run python scripts/modify_pyproject_for_marimo_base_wasm.py

# Ensure the dist directory is empty
rm -rf dist

# Build the marimo-base
pixi run uv build

ls

# Get the name of the built wheel file
pushd dist
wheel_file=$(ls marimo_base-*.whl | head -n 1)
echo "Built wheel file: ${wheel_file}"
popd

# Copy the built wheel file to the appropriate location
cp dist/*.whl ${OUTPUT_DIR}

popd

cleanup

echo "BUILD COMPLETE: ${wheel_file}"