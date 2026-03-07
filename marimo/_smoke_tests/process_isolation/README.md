# Process Isolation Smoke Test

Tests that multiple notebooks served together get separate OS processes,
preventing `sys.modules` clashes.

## The Problem

When two notebooks both `import shared_module` but expect different
implementations (from different directories on `sys.path`), a shared
process means whichever loads first wins.

## Test Structure

```
process_isolation/
├── app1.py              # Notebook: sys.path += app1_modules, import shared_module
├── app2.py              # Notebook: sys.path += app2_modules, import shared_module
├── app1_modules/
│   └── shared_module.py # APP_NAME="app1", MAGIC_NUMBER=111
├── app2_modules/
│   └── shared_module.py # APP_NAME="app2", MAGIC_NUMBER=222
├── serve.py             # Serves both apps via create_asgi_app()
└── README.md
```

## How to Run

```bash
# Option A: create_asgi_app()
python marimo/_smoke_tests/process_isolation/serve.py

# Option B: marimo run (multi-file, auto-enables process isolation)
marimo run marimo/_smoke_tests/process_isolation/app1.py \
           marimo/_smoke_tests/process_isolation/app2.py
```

Open both apps in browser. Each should show a green "PASS" callout.

## Expected Results

- **With process isolation (this branch)**: Both apps show PASS.
- **Without process isolation (released marimo)**: One app shows FAIL — it got the other app's `shared_module`.
