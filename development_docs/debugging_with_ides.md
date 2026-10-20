# Debugging with IDEs


## VS Code

Normal mode and `--sandbox` mode need separate `launch.json` configurations, since
sandbox mode runs differently. Use the
"launch" config below for normal mode, and the "attach" config under [Debugging in
sandbox mode](#debugging-in-sandbox-mode) when running with `--sandbox`.

To debug the marimo server, create
`.vscode/launch.json` with:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Marimo api debugger",
            "type": "debugpy",
            "request": "launch",
            "module": "marimo",
            "args": [
                "edit",
                "--no-token",
                "--headless",
                "/tmp",
                "--port",
                "2718"
            ],
            "python": "${command:python.interpreterPath}",
            "console": "integratedTerminal"
        }
    ]
}
```

This requires the [Python Debugger
extension](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy)
for VS Code. Set breakpoints in the Python source and launch "Marimo api
debugger" from the Run and Debug panel to step through the server.

The frontend and marimo server must be run separately for this to
work. Run the frontend dev server (`pnpm dev`) on its own, then launch "Marimo api debugger" to start and debug the server.

With a breakpoint set in the Python source, you can step through the server like in the video below.

<video muted controls loop playsinline width="100%" align="center" src="../docs/_static/development-docs-debugging-with-vscode.webm" alt="Video showing debugging with VS Code hitting marimo server breakpoints">
</video>

### Debugging in sandbox mode

`marimo edit --sandbox` resolves the notebook's environment with `uv` and
then hands off to it: `NotebookSandbox.launch` (see
`marimo/_environments/environment.py`) runs the server as a child process
via `uv run --active --no-project --python <env>/bin/python ... -- python -m
marimo ...`. That child process runs in the sandbox's own isolated
interpreter, not the interpreter VS Code launched, so the "launch"
configuration above will attach to the outer `marimo` process but will never
hit breakpoints in code that actually executes inside the sandbox.

To debug code running inside the sandbox, attach to it with `debugpy`
instead of launching it. The sandbox environment is its own isolated venv
(see `marimo/_environments/environment.py`), so `debugpy` needs to be
installed into it directly:

1. [Install `debugpy`](https://github.com/microsoft/debugpy#installation)
   into the server environment.

2. Add the `debugpy.listen()` call at the top of `start()` in
   `marimo/_server/start.py`, which is the function that actually boots
   the kernel/session and is only ever reached in the one process that
   runs it:

   ```python
   # Right where MARIMO_ANCESTOR_PID is read, in start()
   if os.environ.get("MARIMO_ANCESTOR_PID"):
       import debugpy

       debugpy.listen(5678)
       debugpy.wait_for_client()
   ```

   The `MARIMO_ANCESTOR_PID` check limits this to sandboxed launches, so
   it's a no-op for a normal (non-sandboxed) `marimo edit`. Remove this
   edit once you're done debugging.

   Don't put this call in the `edit()` CLI command instead. `edit()` runs
   twice: once in the outer process that resolves the sandbox and exits
   via `sys.exit(run_in_sandbox(...))`, and again in the inner sandboxed
   child process it spawns. The outer process's call would bind the port
   and block on `wait_for_client()` before the inner process — the one
   actually running the code you want to debug — ever gets there.

3. Add an "attach" configuration to `.vscode/launch.json`:

   ```json
   {
       "name": "Marimo sandbox attach",
       "type": "debugpy",
       "request": "attach",
       "connect": {
           "host": "localhost",
           "port": 5678
       }
   }
   ```

4. Run `marimo edit --sandbox notebook.py --headless --no-token` from a
   terminal (not from VS Code's debugger). The sandboxed process will block
   on `debugpy.wait_for_client()`; launch "Marimo sandbox attach" from the
   Run and Debug panel to connect, then set breakpoints and continue.
