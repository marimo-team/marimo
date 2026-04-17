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

# Option C: marimo run --sandbox (multi-file, sandbox + process isolation)
marimo run --sandbox marimo/_smoke_tests/process_isolation/app1.py \
                     marimo/_smoke_tests/process_isolation/app2.py
```

Open both apps in browser. Each should show a green "PASS" callout.

## Expected Results

- **With app/process isolation**: Both apps show PASS for process isolation.
- **With `--sandbox`**: Both apps additionally show a green "Sandbox: PASS" callout —
  each app's unique dependency (`humanize` for app1, `pyfiglet` for app2) was installed
  in its own sandbox venv, and the other app's dependency is not present.

---

## Virtual File Smoke Test

Tests that virtual files (images, Arrow data for tables, etc.) created in
an isolated child process are accessible to the parent server process.

```bash
marimo run marimo/_smoke_tests/process_isolation/virtual_files.py \
           marimo/_smoke_tests/process_isolation/app1.py
```

Multi-file `marimo run` auto-enables process isolation. You should see a
blue square image, a green HTML heading, and a three-row table. If any of
those are broken, the cross-process virtual file storage handoff is not
working.
