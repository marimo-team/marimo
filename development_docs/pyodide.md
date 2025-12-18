# marimo + pyodide

## Running the frontend against the latest deploy on PyPi

```bash
cd frontend
PYODIDE=true VITE_WASM_MARIMO_PREBUILT_WHEEL=true pnpm dev
```

## Running the frontend against a local backend

```bash
# build once
hatch build
# server and watch for changes
uv run pyodide/build_and_serve.py
# in another terminal
cd frontend
PYODIDE=true pnpm dev
```
