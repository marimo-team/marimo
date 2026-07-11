/* Copyright 2026 Marimo. All rights reserved. */
import { loadPyodide, type PyodideInterface } from "pyodide";
import type { PyCallable, PyProxy } from "pyodide/ffi";
import type { UserConfig } from "@/core/config/config-schema";
import type { NotificationPayload } from "@/core/kernel/messages";
import type { JsonString } from "@/utils/json/base64";
import { invariant } from "../../../utils/invariant";
import { Logger } from "../../../utils/Logger";
import { WasmFileSystem } from "./fs";
import { getMarimoWheel } from "./getMarimoWheel";
import { t } from "./tracer";
import type { SerializedBridge, WasmController } from "./types";
import { shouldLoadDuckDBPackages } from "../utils";

const MAKE_SNAPSHOT = false;
type SessionResources = [PyProxy, PyCallable, PyProxy, PyCallable];

// This class initializes the wasm environment
// We would like this initialization to be parallelizable
// however, there is some waterfall in the initialization process
// 1. Load Pyodide
// 2. Install marimo and its required dependencies
// 3. Install the dependencies from the notebook
//   3.a Install from pyodide supported wheels
//   3.b Install from micropip
// 4. Initialize the notebook

export class DefaultWasmController implements WasmController {
  protected pyodide: PyodideInterface | null = null;
  private packageLoadQueue = Promise.resolve();
  private sessionGeneration = 0;
  private stopCurrentSession: PyCallable | undefined;

  get requirePyodide() {
    invariant(this.pyodide, "Pyodide not loaded");
    return this.pyodide;
  }

  async bootstrap(opts: {
    version: string;
    pyodideVersion: string;
  }): Promise<PyodideInterface> {
    const pyodide = await this.loadPyodideAndPackages(opts);

    if (MAKE_SNAPSHOT) {
      const snapshot = pyodide.makeMemorySnapshot();
      Logger.log("Snapshot size (mb):", snapshot.byteLength / 1024 / 1024);
    }

    return pyodide;
  }

  private async loadPyodideAndPackages(opts: {
    version: string;
    pyodideVersion: string;
  }): Promise<PyodideInterface> {
    if (!loadPyodide) {
      throw new Error("loadPyodide is not defined");
    }
    // Load pyodide and packages
    const span = t.startSpan("loadPyodide");
    try {
      // Without this, this fails in Firefox with
      // `Could not extract indexURL path from pyodide module`
      // This fixes for Firefox and does not break Chrome/others
      const indexURL = `https://cdn.jsdelivr.net/pyodide/${opts.pyodideVersion}/full/`;
      const pyodide = await loadPyodide({
        // Perf: These get loaded while pyodide is being bootstrapped
        packages: [
          "micropip",
          "msgspec",
          getMarimoWheel(opts.version),
          "Markdown",
          "pymdown-extensions",
          "narwhals",
          "packaging",
        ],
        _makeSnapshot: MAKE_SNAPSHOT,
        lockFileURL: `https://wasm.marimo.app/pyodide-lock.json?v=${opts.version}&pyodide=${opts.pyodideVersion}`,
        indexURL,
        // Since Pyodide 0.28.0, when lockFileURL is set, the package base URL
        // defaults to the lockfile's URL (wasm.marimo.app) instead of indexURL.
        // Unlike Node, browsers get no CDN fallback on a failed fetch, so we
        // should pin packageBaseUrl back to the jsDelivr CDN  to restore
        // the resolution akin to pre-0.28.
        packageBaseUrl: indexURL,
        convertNullToNone: true,
      });
      this.pyodide = pyodide;
      span.end("ok");
      return pyodide;
    } catch (error) {
      Logger.error("Failed to load Pyodide", error);
      throw error;
    }
  }

  async mountFilesystem(opts: { code: string; filename: string | null }) {
    const span = t.startSpan("mountFilesystem");
    // Set up the filesystem
    WasmFileSystem.createHomeDir(this.requirePyodide);
    WasmFileSystem.mountFS(this.requirePyodide);
    await WasmFileSystem.populateFilesToMemory(this.requirePyodide);
    span.end("ok");
    return WasmFileSystem.initNotebookCode({
      pyodide: this.requirePyodide,
      code: opts.code,
      filename: opts.filename,
    });
  }

  async startSession(opts: {
    queryParameters: Record<string, string | string[]>;
    code: string;
    filename: string | null;
    onMessage: (message: JsonString<NotificationPayload>) => void;
    userConfig: UserConfig;
  }): Promise<SerializedBridge> {
    const sessionGeneration = this.sessionGeneration;
    const { code, filename, onMessage, queryParameters, userConfig } = opts;
    // We pass down a messenger object to the code
    // This is used to have synchronous communication between the JS and Python code
    // Previously, we used a queue, but this would not properly flush the queue
    // during processing of a cell's code.
    //
    // This adds a messenger object to the global scope (import js; js.messenger.callback)
    self.messenger = {
      callback: onMessage,
    };
    self.query_params = queryParameters;
    self.user_config = userConfig;

    const span = t.startSpan("startSession.runPython");
    const nbFilename = filename || WasmFileSystem.NOTEBOOK_FILENAME;
    const sessionResources = this.requirePyodide.runPython(
      `
      print("[py] Starting marimo...")
      import asyncio
      import gc
      import js
      from marimo._pyodide.bootstrap import create_session, instantiate

      assert js.messenger, "messenger is not defined"
      assert js.query_params, "query_params is not defined"

      def create_session_resources():
        session, bridge = create_session(
          filename="${nbFilename}",
          query_params=js.query_params.to_py(),
          message_callback=js.messenger.callback,
          user_config=js.user_config.to_py(),
        )
        session_task = None

        def init(auto_instantiate=True):
          nonlocal session_task
          instantiate(session, auto_instantiate)
          session_task = asyncio.create_task(session.start())

        async def stop():
          nonlocal bridge, session, session_task
          task = session_task
          try:
            kernel_task = getattr(session, "kernel_task", None)
            if kernel_task is None:
              if task is not None:
                task.cancel()
            else:
              kernel_task.stop()
            if task is not None:
              try:
                await task
              except asyncio.CancelledError:
                pass
          finally:
            session_task = None
            session = None
            bridge = None
            gc.collect()

        with open("${nbFilename}", "r") as f:
          packages = session.find_packages(f.read())

        return bridge, init, packages, stop

      create_session_resources()`,
    ) as PyProxy;
    span.end();
    let bridgeProxy!: PyProxy;
    let initSession!: PyCallable;
    let packagesProxy!: PyProxy;
    let stopSession!: PyCallable;
    try {
      [bridgeProxy, initSession, packagesProxy, stopSession] =
        sessionResources as unknown as SessionResources;
    } finally {
      sessionResources.destroy();
    }
    let foundPackages: Set<string>;
    try {
      foundPackages = new Set<string>(packagesProxy.toJs());
    } catch (error) {
      bridgeProxy.destroy();
      initSession.destroy();
      stopSession.destroy();
      throw error;
    } finally {
      packagesProxy.destroy();
    }
    this.stopCurrentSession?.destroy();
    this.stopCurrentSession = stopSession;

    // Fire and forget:
    // Load notebook dependencies and instantiate the session
    // We don't want to wait for this to finish,
    // so we can show the initial code immediately giving
    // a sense of responsiveness.
    const dependenciesReady = this.packageLoadQueue.then(() => {
      if (sessionGeneration !== this.sessionGeneration) {
        return;
      }
      return this.loadNotebookDeps(code, foundPackages);
    });
    this.packageLoadQueue = dependenciesReady.catch(() => undefined);
    void dependenciesReady
      .then(() => {
        if (sessionGeneration !== this.sessionGeneration) {
          return;
        }
        return initSession(userConfig.runtime.auto_instantiate);
      })
      .catch((error: unknown) => {
        Logger.error("Failed to load notebook dependencies", error);
      })
      .finally(() => initSession.destroy());

    return bridgeProxy as unknown as SerializedBridge;
  }

  async stopSession(): Promise<void> {
    this.sessionGeneration += 1;
    const stop = this.stopCurrentSession;
    this.stopCurrentSession = undefined;
    try {
      await stop?.();
    } finally {
      stop?.destroy();
    }
  }

  private async loadNotebookDeps(code: string, foundPackages: Set<string>) {
    const pyodide = this.requirePyodide;

    if (shouldLoadDuckDBPackages(code, foundPackages)) {
      // We need pandas and duckdb for mo.sql and for remote duckdb sources
      code = `import pandas\n${code}`;
      code = `import duckdb\n${code}`;
      code = `import sqlglot\n${code}`;

      // Polars + SQL requires pyarrow, and installing
      // after notebook load does not work. As a heuristic,
      // if it appears that the notebook uses polars, add pyarrow.
      if (code.includes("polars")) {
        code = `import pyarrow\n${code}`;
      }
    }

    // Add:
    // 1. additional dependencies of marimo that are lazily loaded.
    // 2. pyodide-http, a patch to make basic http requests work in pyodide
    //
    // These packages are included with Pyodide, which is why we don't add them
    // to `foundPackages`:
    // https://pyodide.org/en/stable/usage/packages-in-pyodide.html
    code = `import docutils\n${code}`;
    code = `import pygments\n${code}`;
    code = `import jedi\n${code}`;
    code = `import pyodide_http\n${code}`;

    const imports = [...foundPackages];

    // Load from pyodide
    let loadSpan = t.startSpan("pyodide.loadPackage");
    await pyodide.loadPackagesFromImports(code, {
      errorCallback: Logger.error,
      messageCallback: Logger.log,
    });
    loadSpan.end();

    // Load from micropip
    loadSpan = t.startSpan("micropip.install");
    const missingPackages = imports.filter(
      (pkg) => !pyodide.loadedPackages[pkg],
    );
    if (missingPackages.length > 0) {
      await pyodide
        .runPythonAsync(`
        import micropip
        import sys
        # Filter out builtins
        missing = [p for p in ${JSON.stringify(missingPackages)} if p not in sys.modules]
        if len(missing) > 0:
          print("Loading from micropip:", missing)
          await micropip.install(missing)
      `)
        .catch((error) => {
          // Don't let micropip loading failures stop the notebook from loading
          Logger.error("Failed to load packages from micropip", error);
        });
    }
    loadSpan.end();
  }
}
