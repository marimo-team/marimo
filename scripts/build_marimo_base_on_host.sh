#!/bin/bash

# Sets up a named docker container that we periodically use for building
# marimo-base. It mounts the current workspace as read-only
set -euxo pipefail

# Check for USE_OVERLAYFS
USE_OVERLAYFS=${USE_OVERLAYFS:-false}

rm -r .wasmbuilds
mkdir -p .wasmbuilds

# If the docker container is not running, start it
if [ ! "$(docker ps -a -q -f name=marimo-builder)" ]; then
    # Set the working directory to /workspace
    if [ "$USE_OVERLAYFS" = true ]; then
        docker run -d --privileged --cap-add=SYS_ADMIN -e USE_OVERLAYFS=true --name marimo-builder -v $(pwd):/workspace:ro -w /workspace -v $(pwd)/.wasmbuilds:/builds --workdir /workspace ghcr.io/prefix-dev/pixi:latest sleep 3600
    else
        docker run -d --name marimo-builder -v $(pwd):/workspace:ro -w /workspace -v $(pwd)/.wasmbuilds:/builds --workdir /workspace ghcr.io/prefix-dev/pixi:latest sleep 3600
    fi
fi
# Stop the container if it's running
docker stop marimo-builder || true
docker start marimo-builder
docker exec marimo-builder bash scripts/build_marimo_base_in_docker.sh /builds
# Kill the container we're done building
docker stop marimo-builder || true