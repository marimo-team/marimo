/**
 * Runs the WASM concurrency matrix in Node Pyodide with JSPI.
 *
 * The harness loads a built marimo wheel, executes the shared matrix cell
 * through a marimo Pyodide session, and checks every expected runtime row,
 * including the process-shaped WASM validation phase.
 *
 * Usage:
 *   node --experimental-wasm-jspi tests/_pyodide/test_wasm_concurrency_matrix.mjs \
 *     "$(ls -t dist/marimo_base-*-py3-none-any.whl | head -n 1)"
 *
 */

import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { pathToFileURL } from "node:url";

const MATRIX_FIXTURE_DIR = "tests/_pyodide/fixtures/wasm_concurrency";
const MATRIX_CELL_PATH = `${MATRIX_FIXTURE_DIR}/matrix_cell.py`;
const MATRIX_SUPPORT_PATHS = [
  `${MATRIX_FIXTURE_DIR}/wasm_concurrency_matrix_cases/_shared.py`,
  `${MATRIX_FIXTURE_DIR}/wasm_concurrency_matrix_cases/threading_cases.py`,
  `${MATRIX_FIXTURE_DIR}/wasm_concurrency_matrix_cases/marimo_thread_cases.py`,
  `${MATRIX_FIXTURE_DIR}/wasm_concurrency_matrix_cases/futures_cases.py`,
  `${MATRIX_FIXTURE_DIR}/wasm_concurrency_matrix_cases/process_cases.py`,
  `${MATRIX_FIXTURE_DIR}/wasm_concurrency_matrix_cases/stress_cases.py`,
];

const REQUIRED_DEFAULT_WASM_CONCURRENCY_MATRIX_ROWS = new Map([
  ["runtime.jspi_run_sync_in_cell_task", "api-compatible"],
  ["install.process_shaped_bootstrapped", "serialized"],
  ["install.shim_before_user_cell", "api-compatible"],
  ["install.stdlib_imports_after_patch", "api-compatible"],
  ["threading.main_thread_instance_check", "api-compatible"],
  ["threading.event_negative_timeout_immediate", "api-compatible"],
  ["threading.thread_join_negative_timeout_immediate", "api-compatible"],
  ["threading.event_wait_delayed_thread", "cooperative-only"],
  ["queue.bounded_simplequeue_immediate", "api-compatible"],
  ["threading.local_isolation", "api-compatible"],
  ["threading.identity_enumerate_active_count", "api-compatible"],
  ["threading.thread_run_direct_identity", "api-compatible"],
  ["threading.local_subclass_init_per_thread", "api-compatible"],
  ["threading.local_subclass_defaults", "api-compatible"],
  ["threading.local_subclass_descriptors", "api-compatible"],
  ["threading.contextvars_not_inherited", "api-compatible"],
  ["threading.excepthook", "api-compatible"],
  ["marimo_thread.bootstrap_current_thread", "api-compatible"],
  ["marimo_thread.current_thread_should_exit", "api-compatible"],
  ["marimo_thread.shared_output_progress", "api-compatible"],
  ["marimo_thread.print_routes_console", "api-compatible"],
  ["marimo_thread.ui_ids_use_cell_provider", "api-compatible"],
  ["marimo_thread.child_app_embed_parent_ownership", "api-compatible"],
  ["marimo_thread.async_context_isolation", "api-compatible"],
  ["futures.thread_pool_result_exception_cancel", "serialized"],
  ["futures.thread_pool_contextvars_not_inherited", "serialized"],
  ["futures.thread_pool_current_thread_surface", "api-compatible"],
  ["futures.thread_pool_awaitable_return_value", "api-compatible"],
  ["asyncio.to_thread_result", "serialized"],
  ["asyncio.to_thread_contextvars_inherited", "serialized"],
  ["asyncio.run_in_executor_default", "serialized"],
  ["asyncio.run_in_executor_thread_pool", "serialized"],
  ["futures.executor_callback_cooperative_wait", "cooperative-only"],
  ["futures.thread_pool_map_ordered", "serialized"],
  ["futures.callback_once", "api-compatible"],
  ["futures.callback_once_exception", "api-compatible"],
  ["futures.thread_pool_initializer_chunksize", "serialized"],
  ["futures.wait_all_completed", "api-compatible"],
  ["futures.wait_first_completed", "cooperative-only"],
  ["futures.wait_first_exception", "cooperative-only"],
  ["futures.future_result_negative_timeout_immediate", "api-compatible"],
  ["futures.future_exception_negative_timeout_immediate", "api-compatible"],
  ["futures.wait_negative_timeout_immediate", "api-compatible"],
  ["futures.as_completed", "api-compatible"],
  ["futures.as_completed_negative_timeout_immediate", "api-compatible"],
  ["futures.as_completed_timeout_zero_done", "api-compatible"],
  ["futures.shutdown_cancel_futures", "cooperative-only"],
  ["threading.daemon_loop_run_to_completion", "api-compatible"],
  ["stress.thread_pool_queue_primitives", "serialized"],
]);

const REQUIRED_PROCESS_SHAPED_WASM_CONCURRENCY_MATRIX_ROWS = new Map([
  ["asyncio.run_in_executor_process_pool", "serialized"],
  ["process_pool.result_exception_map", "serialized"],
  ["process_pool.lambda_runs_in_local_interpreter", "serialized"],
  ["process_pool.contextvars_not_inherited", "serialized"],
  ["process_pool.initializer_state", "serialized"],
  ["process_pool.initializer_failure", "serialized"],
  ["process_pool.parameter_validation", "api-compatible"],
  ["multiprocessing.cpu_count_start_methods", "serialized"],
  ["multiprocessing.blocked_factories", "blocked"],
  ["multiprocessing.context_spawn_factories", "serialized"],
  ["multiprocessing.context_blocked_factories", "blocked"],
  ["multiprocessing.queues_exception_aliases", "api-compatible"],
  ["multiprocessing.queue_negative_timeout_immediate", "api-compatible"],
  ["multiprocessing.simple_queue_factories", "serialized"],
  ["multiprocessing.queue_close", "api-compatible"],
  ["multiprocessing.submodule_ctx_factories", "serialized"],
  ["process_pool.max_workers_serialized_lane", "serialized"],
  ["process_pool.reference_semantics", "serialized"],
  ["multiprocessing.pool_apply_map_starmap", "serialized"],
  ["multiprocessing.pool_reference_semantics", "serialized"],
  ["multiprocessing.pool_invalid_chunksize", "api-compatible"],
  ["multiprocessing.pool_imap_lifecycle_knobs", "serialized"],
  ["multiprocessing.pool_imap_lazy", "serialized"],
  ["multiprocessing.pool_async_callbacks", "serialized"],
  ["multiprocessing.pool_async_timeout_error", "cooperative-only"],
  ["multiprocessing.pool_user_timeout_error", "serialized"],
  ["multiprocessing.pool_terminate_cancels_queued", "cooperative-only"],
  ["multiprocessing.pool_terminate_rejects_active", "cooperative-only"],
  ["multiprocessing.pool_thread_pool_unsupported", "blocked"],
  ["multiprocessing.active_children", "serialized"],
  ["process.submodule_import_entrypoints", "serialized"],
  ["multiprocessing.process_queue", "serialized"],
  ["multiprocessing.process_contextvars_not_inherited", "serialized"],
  ["multiprocessing.process_queue_reference_semantics", "serialized"],
  ["multiprocessing.process_current_process_survives_await", "serialized"],
  ["multiprocessing.process_parent_metadata", "serialized"],
  ["multiprocessing.process_child_thread_identity", "serialized"],
  ["multiprocessing.process_kill_cooperative", "cooperative-only"],
  ["multiprocessing.process_exception_exitcode", "serialized"],
  ["stress.process_shaped_primitives", "serialized"],
]);

const REQUIRED_WASM_CONCURRENCY_MATRIX_ROWS = new Map([
  ...REQUIRED_DEFAULT_WASM_CONCURRENCY_MATRIX_ROWS,
  ...REQUIRED_PROCESS_SHAPED_WASM_CONCURRENCY_MATRIX_ROWS,
]);

function readMatrixSupportFiles() {
  return MATRIX_SUPPORT_PATHS.map((filename) => ({
    path: filename.replace(
      `${MATRIX_FIXTURE_DIR}/wasm_concurrency_matrix_cases/`,
      "wasm_concurrency_matrix_cases/",
    ),
    code: fs.readFileSync(filename, "utf8"),
  }));
}

function assertMatrix(result, requiredRows, label = "Matrix") {
  const rows = JSON.parse(result);
  const byId = new Map(rows.map((row) => [row.id, row]));
  if (byId.size !== rows.length) {
    throw new Error(`${label} contains duplicate row ids`);
  }
  const missingRows = [...requiredRows.keys()].filter((id) => !byId.has(id));
  if (missingRows.length > 0) {
    throw new Error(
      [
        `${label} missing required rows: required ${requiredRows.size}, got ${rows.length}`,
        `Missing rows: ${missingRows.join(", ") || "(none)"}`,
      ].join("\n"),
    );
  }
  for (const [id, tier] of requiredRows) {
    const row = byId.get(id);
    if (!row) {
      throw new Error(`Missing ${label.toLowerCase()} row: ${id}`);
    }
    if (row.tier !== tier) {
      throw new Error(
        `${label} row ${id} emitted tier ${row.tier}, expected ${tier}`,
      );
    }
  }
  return rows;
}

function parseArgs() {
  const args = process.argv.slice(2);
  const wheelPath = args[0];
  const flags = args.slice(1);
  const allowedFlags = new Set(["--verbose"]);
  const unknownFlags = flags.filter((flag) => !allowedFlags.has(flag));
  if (unknownFlags.length > 0) {
    console.error(`Unknown flag(s): ${unknownFlags.join(", ")}`);
    process.exit(1);
  }
  const verbose = flags.includes("--verbose");

  if (!wheelPath) {
    console.error(
      "Usage: node test_wasm_concurrency_matrix.mjs <wheel-path> [--verbose]",
    );
    process.exit(1);
  }

  return {
    wheelPath: path.resolve(wheelPath),
    verbose,
  };
}

function timeoutMs(name, fallback) {
  const rawValue = process.env[name];
  if (rawValue === undefined) {
    return fallback;
  }
  const value = Number(rawValue);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name} must be a positive number of milliseconds`);
  }
  return value;
}

async function importPyodide() {
  try {
    return await import("pyodide");
  } catch (error) {
    const candidates = [
      path.resolve(process.cwd(), "node_modules/pyodide/pyodide.mjs"),
      path.resolve(process.cwd(), "frontend/node_modules/pyodide/pyodide.mjs"),
    ];
    const found = candidates.find((candidate) => fs.existsSync(candidate));
    if (!found) {
      throw error;
    }
    return import(pathToFileURL(found).href);
  }
}

async function loadDependencies(pyodide) {
  await pyodide.loadPackage([
    "micropip",
    "msgspec",
    "packaging",
    "pyodide_http",
    "docutils",
    "pygments",
    "jedi",
  ]);
  await pyodide.runPythonAsync(`
import micropip
await micropip.install(["Markdown", "pymdown-extensions", "narwhals>=2.0.0"])
`);
}

function startWheelServer(wheelPath) {
  const wheelFilename = path.basename(wheelPath);

  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type");

      if (req.method === "OPTIONS") {
        res.writeHead(200);
        res.end();
        return;
      }

      const requestedFile = decodeURIComponent(
        (req.url ?? "").split("?")[0].slice(1),
      );
      if (req.method !== "GET" || requestedFile !== wheelFilename) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }

      fs.readFile(wheelPath, (error, data) => {
        if (error) {
          res.writeHead(404);
          res.end("File not found");
          return;
        }
        res.setHeader("Content-Type", "application/zip");
        res.setHeader("Content-Length", String(data.byteLength));
        res.writeHead(200);
        res.end(data);
      });
    });

    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address !== "object") {
        reject(new Error("wheel server did not bind to a TCP port"));
        return;
      }
      server.unref();
      resolve({
        wheelUrl: `http://127.0.0.1:${address.port}/${wheelFilename}`,
      });
    });
    server.on("error", reject);
  });
}

function writeMatrixSupportFiles(pyodide, supportFiles) {
  pyodide.runPython(`
import os
os.makedirs("/home/pyodide/wasm_concurrency_matrix_cases", exist_ok=True)
`);
  for (const file of supportFiles) {
    pyodide.FS.writeFile(`/home/pyodide/${file.path}`, file.code);
  }
}

function assertMatrixSupportFilesCompile(pyodide, supportFiles) {
  pyodide.runPython(`
import py_compile
for path in ${JSON.stringify(supportFiles.map((file) => file.path))}:
    py_compile.compile("/home/pyodide/" + path, doraise=True)
`);
}

function installSessionFactory(pyodide) {
  pyodide.runPython(`
import asyncio
import os
import js

from marimo._pyodide.bootstrap import create_session, instantiate

WASM_CONCURRENCY_NOTEBOOK = """
import marimo
__generated_with = "0.0.0"
app = marimo.App()

@app.cell
def _():
    return

if __name__ == "__main__":
    app.run()
"""

def create_wasm_concurrency_session(notebook_path, callback_name):
    os.makedirs(os.path.dirname(notebook_path), exist_ok=True)
    with open(notebook_path, "w") as f:
        f.write(WASM_CONCURRENCY_NOTEBOOK)

    session, bridge = create_session(
        notebook_path,
        {},
        getattr(js, callback_name),
        {},
    )
    session_task = None

    def init(auto_instantiate=True):
        nonlocal session_task
        instantiate(session, auto_instantiate)
        session_task = asyncio.create_task(session.start())

    def stop_session():
        if session_task is None:
            return None
        session.kernel_task.stop()
        return session_task

    return bridge, init, stop_session
`);
}

function createSession(pyodide, notebookPath, callbackName) {
  return pyodide.runPython(`
create_wasm_concurrency_session(
    ${JSON.stringify(notebookPath)},
    ${JSON.stringify(callbackName)},
)
`);
}

async function waitUntil(condition, label, timeoutName, fallback) {
  const deadline = Date.now() + timeoutMs(timeoutName, fallback);
  while (!condition()) {
    if (Date.now() > deadline) {
      throw new Error(label);
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

function sessionNotification(message) {
  // Pyodide session callbacks receive an envelope with the notification payload
  // in `data`.
  return JSON.parse(message).data;
}

async function waitForKernelReady(messages, label) {
  await waitUntil(
    () =>
      messages.some(
        (message) => sessionNotification(message).op === "kernel-ready",
      ),
    label,
    "MARIMO_WASM_SESSION_TIMEOUT_MS",
    30_000,
  );
}

function pythonFileExists(pyodide, filePath) {
  return pyodide.runPython(`
import os
os.path.exists(${JSON.stringify(filePath)})
`);
}

async function waitForFile(pyodide, filePath, label) {
  await waitUntil(
    () => pythonFileExists(pyodide, filePath),
    label,
    "MARIMO_WASM_MATRIX_TIMEOUT_MS",
    120_000,
  );
}

function readPythonFile(pyodide, filePath) {
  return pyodide.runPython(`
with open(${JSON.stringify(filePath)}) as f:
    result = f.read()
result
`);
}

function removePythonFiles(pyodide, filePaths) {
  pyodide.runPython(`
import os
for path in ${JSON.stringify(filePaths)}:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
`);
}

async function stopSessionAndWait(pyodide, stopSession) {
  pyodide.globals.set("_wasm_concurrency_stop_session", stopSession);
  await pyodide.runPythonAsync(`
task = _wasm_concurrency_stop_session()
if task is not None:
    await task

from marimo._runtime._wasm import wait_for_wasm_runtime_work_async
assert await wait_for_wasm_runtime_work_async(timeout=1)
`);
}

async function main() {
  const { wheelPath, verbose } = parseArgs();
  if (!fs.existsSync(wheelPath)) {
    throw new Error(`Wheel file not found: ${wheelPath}`);
  }
  const matrixCellCode = fs.readFileSync(
    path.resolve(MATRIX_CELL_PATH),
    "utf8",
  );
  const matrixSupportFiles = readMatrixSupportFiles();
  const requiredRows = REQUIRED_WASM_CONCURRENCY_MATRIX_ROWS;

  console.log(`Testing wheel: ${wheelPath}`);
  const { loadPyodide, version } = await importPyodide();
  console.log(`Pyodide version: ${version}`);

  globalThis.marimoWasmConcurrencyDelay = (value, ms) =>
    new Promise((resolve) => setTimeout(() => resolve(value), ms));
  globalThis.marimoWasmConcurrencyMessages = [];
  globalThis.marimoWasmConcurrencyMessageCallback = (message) => {
    globalThis.marimoWasmConcurrencyMessages.push(message);
  };

  const pyodide = await loadPyodide();
  await loadDependencies(pyodide);
  const wheelServer = await startWheelServer(wheelPath);
  await pyodide.loadPackage(wheelServer.wheelUrl);
  writeMatrixSupportFiles(pyodide, matrixSupportFiles);
  assertMatrixSupportFilesCompile(pyodide, matrixSupportFiles);
  installSessionFactory(pyodide);

  const [bridge, init, stopSession] = createSession(
    pyodide,
    "/home/pyodide/wasm_concurrency_matrix_notebook.py",
    "marimoWasmConcurrencyMessageCallback",
  );

  init(true);
  await waitForKernelReady(
    globalThis.marimoWasmConcurrencyMessages,
    `timed out waiting for kernel-ready: ${globalThis.marimoWasmConcurrencyMessages.slice(-10).join("\n")}`,
  );

  await bridge.put_control_request(
    JSON.stringify({
      type: "execute-cells",
      cellIds: ["wasm-concurrency-matrix"],
      codes: [matrixCellCode],
    }),
  );

  const resultPath = "/home/pyodide/wasm_concurrency_matrix_result.json";
  const failurePath = "/home/pyodide/wasm_concurrency_matrix_failure.json";
  await waitUntil(
    () =>
      pythonFileExists(pyodide, resultPath) ||
      pythonFileExists(pyodide, failurePath),
    `wasm concurrency matrix did not produce a result: ${globalThis.marimoWasmConcurrencyMessages.slice(-10).join("\n")}`,
    "MARIMO_WASM_MATRIX_TIMEOUT_MS",
    120_000,
  );
  if (pythonFileExists(pyodide, failurePath)) {
    const failure = readPythonFile(pyodide, failurePath);
    throw new Error(`wasm concurrency matrix failed:\n${failure}`);
  }
  const result = readPythonFile(pyodide, resultPath);

  if (verbose) {
    console.log("Matrix result:");
    console.log(result);
  }
  const rows = assertMatrix(result, requiredRows, "Matrix");
  await stopSessionAndWait(pyodide, stopSession);
  await pyodide.runPythonAsync(`
import concurrent.futures
import multiprocessing
import threading

post_stop_thread_records = []

def post_stop_thread_probe():
    post_stop_thread_records.append(threading.current_thread().name)

post_stop_thread = threading.Thread(
    target=post_stop_thread_probe,
    name="post-stop-thread",
)
post_stop_thread.start()
post_stop_thread.join(timeout=1)
assert not post_stop_thread.is_alive()
assert post_stop_thread_records == ["post-stop-thread"]

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    assert executor.submit(str, "post-stop-thread-pool").result(
        timeout=1
    ) == "post-stop-thread-pool"

def assert_process_shape_runs():
    process = None
    try:
        values = multiprocessing.Queue()

        def process_shape_probe(output):
            output.put("process-shaped")

        process = multiprocessing.Process(
            target=process_shape_probe,
            args=(values,),
        )
        process.start()
        process.join(timeout=1)
        assert not process.is_alive()
        assert process.exitcode == 0
        assert values.get(timeout=1) == "process-shaped"
    finally:
        if process is not None and process.is_alive():
            process.kill()
            process.join(timeout=1)

assert_process_shape_runs()

post_stop_queue = multiprocessing.Queue()

def post_stop_worker(output):
    output.put(("process", multiprocessing.current_process().name))

post_stop_process = multiprocessing.Process(
    target=post_stop_worker,
    args=(post_stop_queue,),
)
post_stop_process.start()
post_stop_process.join(timeout=1)
assert post_stop_process.exitcode == 0
assert post_stop_queue.get(timeout=1)[0] == "process"

with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
    assert executor.submit(lambda value: value + 1, 41).result(
        timeout=1
    ) == 42
`);
  globalThis.marimoWasmConcurrencyLiveStopMessages = [];
  globalThis.marimoWasmConcurrencyLiveStopMessageCallback = (message) => {
    globalThis.marimoWasmConcurrencyLiveStopMessages.push(message);
  };
  const liveStopStartedPath =
    "/home/pyodide/wasm_concurrency_live_stop_started.json";
  const liveStopExitedPath =
    "/home/pyodide/wasm_concurrency_live_stop_exited.json";
  removePythonFiles(pyodide, [liveStopStartedPath, liveStopExitedPath]);
  const [liveStopBridge, liveStopInit, liveStopSessionStop] = createSession(
    pyodide,
    "/home/pyodide/wasm_concurrency_live_stop_notebook.py",
    "marimoWasmConcurrencyLiveStopMessageCallback",
  );
  liveStopInit(true);
  await waitForKernelReady(
    globalThis.marimoWasmConcurrencyLiveStopMessages,
    `timed out waiting for live-stop kernel-ready: ${globalThis.marimoWasmConcurrencyLiveStopMessages.slice(-10).join("\n")}`,
  );
  const liveStopCellCode = `
import json
import threading
import marimo as mo

wait_tick = threading.Event()

def live_worker():
    current = mo.current_thread()
    with open(${JSON.stringify(liveStopStartedPath)}, "w") as f:
        json.dump(
            {
                "thread": current.name,
                "initial_should_exit": current.should_exit,
            },
            f,
        )
    while not current.should_exit:
        wait_tick.wait(0.01)
    with open(${JSON.stringify(liveStopExitedPath)}, "w") as f:
        json.dump(
            {
                "thread": current.name,
                "saw_should_exit": current.should_exit,
            },
            f,
        )

live_thread = mo.Thread(target=live_worker, name="live-stop-thread")
live_thread.start()
`;
  await liveStopBridge.put_control_request(
    JSON.stringify({
      type: "execute-cells",
      cellIds: ["live-stop-context"],
      codes: [liveStopCellCode],
    }),
  );
  await waitForFile(
    pyodide,
    liveStopStartedPath,
    `live-stop worker did not start: ${globalThis.marimoWasmConcurrencyLiveStopMessages.slice(-10).join("\n")}`,
  );
  await stopSessionAndWait(pyodide, liveStopSessionStop);
  await waitForFile(
    pyodide,
    liveStopExitedPath,
    `live-stop worker did not observe teardown: ${globalThis.marimoWasmConcurrencyLiveStopMessages.slice(-10).join("\n")}`,
  );
  const liveStopExited = JSON.parse(
    readPythonFile(pyodide, liveStopExitedPath),
  );
  if (
    liveStopExited.thread !== "live-stop-thread" ||
    liveStopExited.saw_should_exit !== true
  ) {
    throw new Error(
      `unexpected live-stop teardown result: ${JSON.stringify(liveStopExited)}`,
    );
  }

  globalThis.marimoWasmConcurrencyPostStopMessages = [];
  globalThis.marimoWasmConcurrencyPostStopMessageCallback = (message) => {
    globalThis.marimoWasmConcurrencyPostStopMessages.push(message);
  };
  const postStopResultPath =
    "/home/pyodide/wasm_concurrency_post_stop_context.json";
  removePythonFiles(pyodide, [postStopResultPath]);
  const [postStopBridge, postStopInit, postStopSessionStop] = createSession(
    pyodide,
    "/home/pyodide/wasm_concurrency_post_stop_notebook.py",
    "marimoWasmConcurrencyPostStopMessageCallback",
  );
  postStopInit(true);
  try {
    await waitForKernelReady(
      globalThis.marimoWasmConcurrencyPostStopMessages,
      `timed out waiting for post-stop kernel-ready: ${globalThis.marimoWasmConcurrencyPostStopMessages.slice(-10).join("\n")}`,
    );

    const postStopCellCode = `
import json
import marimo as mo

thread_records = []

def target():
    context = mo._runtime.context.get_context()
    mo.output.append("post-stop thread output")
    thread_records.append(
        {
            "thread": mo.current_thread().name,
            "has_execution_context": context.execution_context is not None,
        }
    )

thread = mo.Thread(target=target, name="post-stop-context-thread")
thread.start()
thread.join(timeout=1)
assert not thread.is_alive()
assert thread_records == [
    {
        "thread": "post-stop-context-thread",
        "has_execution_context": True,
    }
]
with open(${JSON.stringify(postStopResultPath)}, "w") as f:
    json.dump(thread_records, f)
`;
    await postStopBridge.put_control_request(
      JSON.stringify({
        type: "execute-cells",
        cellIds: ["post-stop-context"],
        codes: [postStopCellCode],
      }),
    );
    await waitForFile(
      pyodide,
      postStopResultPath,
      `post-stop marimo context cell did not finish: ${globalThis.marimoWasmConcurrencyPostStopMessages.slice(-10).join("\n")}`,
    );
    const postStopContext = JSON.parse(
      readPythonFile(pyodide, postStopResultPath),
    );
    if (
      postStopContext.length !== 1 ||
      postStopContext[0].thread !== "post-stop-context-thread" ||
      postStopContext[0].has_execution_context !== true
    ) {
      throw new Error(
        `unexpected post-stop marimo context result: ${JSON.stringify(postStopContext)}`,
      );
    }
    const sawPostStopOutput =
      globalThis.marimoWasmConcurrencyPostStopMessages.some((message) => {
        const notification = sessionNotification(message);
        return (
          notification.op === "cell-op" &&
          notification.cell_id === "post-stop-context" &&
          JSON.stringify(notification.output ?? "").includes(
            "post-stop thread output",
          )
        );
      });
    if (!sawPostStopOutput) {
      throw new Error(
        `post-stop thread output was not routed: ${globalThis.marimoWasmConcurrencyPostStopMessages.slice(-10).join("\n")}`,
      );
    }
  } finally {
    await stopSessionAndWait(pyodide, postStopSessionStop);
  }
  const processRows =
    REQUIRED_PROCESS_SHAPED_WASM_CONCURRENCY_MATRIX_ROWS.size;
  console.log(
    [
      `Verified ${rows.length} matrix rows`,
      `default rows: ${REQUIRED_DEFAULT_WASM_CONCURRENCY_MATRIX_ROWS.size}`,
      `process-shaped rows: ${processRows}`,
    ].join(" | "),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
