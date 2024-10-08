# Dagger

This directory contains Dagger scripts for building and testing marimo in a
containerized environment. This allows for running tests and builds in an
environment that is similar to CI.

To run a Dagger script, you need to have the Dagger CLI installed. You can install
it by following the instructions [here](https://docs.dagger.io/install).

To run a Dagger script, you can use the following command:

```bash
dagger functions                           # see what functions are available in the module
dagger call make <any make task>           # run make task in a dev environment
dagger call frontend test                  # run frontend tests
dagger call backend test                   # run backend tests
# run frontend tests on a remote pull request
dagger call --src https://github.com/marimo-team/marimo\#pull/2542/head frontend test
```
