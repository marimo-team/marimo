# wasm-builder

This is a proxy for testing the wasm version of marimo. This allows us to serve
a very up to date version of marimo to the wasm frontend, while still being able
to use a stable backend for the rest of the app.

It has two primary functions and is, in general a bit hacky but it utilizes a
few things inherent in marimo's wasm setup. The two primary functions:

* Create and serve an updated wasm compatible marimo python wheel.
* Create an up to date pyodide lock file for the wasm frontend

## Usage

Since this is a proxy you will also need the frontend to be running. In one
terminal start the frontend. (All commands should be run from the root of the
project) 

```bash
cd frontend
# Start the frontend. You will want to set PYODIDE=true so that you can force the use of the 
# pyodide backend
PYODIDE=true pnpm dev
```


The frontend listens on port 3000 by default. In another terminal, you can start
the wasm-builder proxy. 

```bash
cd packages/wasm-builder
pnpm start 
```

The server will start listening on port 6008 by default.

If you happen to be developing, using a remote development setup you will want
to make sure you set the `PUBLIC_PACKAGES_HOST` to the correct host for your
remote setup.

To access the notebook now, you can navigate to `http://localhost:6008` in your
browser. Note: If you access the frontend without the proxy, you will not be
able to have a working wasm environment.