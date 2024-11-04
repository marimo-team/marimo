#!/bin/sh

# Python build tools generally only allow building one project
# per Python project. This modifies the pyproject.toml
# to build marimo-base, a slimmed down marimo distribution with
# no static artifacts.
#
# Adapted from https://github.com/cvxpy/cvxpy/blob/297278e2a88db3c0084750052a16e60672074da3/.github/workflows/build.yml#L169C1-L180C1
#
# Mac has a different syntax for sed -i, this works across oses
sed -i.bak -e 's/name = "marimo"/name = "marimo-base"/g' pyproject.toml
# Replace static artifacts with just index.html
sed -i.bak 's/artifacts = \[.*\]/artifacts = ["marimo\/_static\/index.html"]/' pyproject.toml
rm -rf pyproject.toml.bak
