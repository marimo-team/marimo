/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { WasmFileSystem } from "./fs";
import { Logger } from "../../../utils/Logger";
import type { SerializedBridge, WasmController } from "./types";
import { invariant } from "../../../utils/invariant";
import type { UserConfig } from "@/core/config/config-schema";
import { getMarimoWheel } from "./getMarimoWheel";
import type { OperationMessage } from "@/core/kernel/messages";
import type { JsonString } from "@/utils/json/base64";
import { t } from "./tracer";

declare let loadPyodide: (opts: {
  packages: string[];
  indexURL: string;
}) => Promise<PyodideInterface>;

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

  get requirePyodide() {
    invariant(this.pyodide, "Pyodide not loaded");
    return this.pyodide;
  }

  async bootstrap(opts: {
    version: string;
    pyodideVersion: string;
  }): Promise<PyodideInterface> {
    const pyodide = await this.loadPyodideAndPackages(opts.pyodideVersion);

    const { version } = opts;

    // If is a dev release, we need to install from test.pypi.org
    if (version.includes("dev")) {
      await this.installDevMarimoAndDeps(pyodide, version);
      return pyodide;
    }

    await this.installMarimoAndDeps(pyodide, version);

    return pyodide;
  }

  private async loadPyodideAndPackages(
    pyodideVersion: string,
  ): Promise<PyodideInterface> {
    if (!loadPyodide) {
      throw new Error("loadPyodide is not defined");
    }
    // Load pyodide and packages
    const span = t.startSpan("loadPyodide");
    const pyodide = await loadPyodide({
      // Perf: These get loaded while pyodide is being bootstrapped
      // The packages can be found here: https://pyodide.org/en/stable/usage/packages-in-pyodide.html
      packages: ["micropip", "docutils", "Pygments", "jedi", "pyodide-http"],
      // Without this, this fails in Firefox with
      // `Could not extract indexURL path from pyodide module`
      // This fixes for Firefox and does not break Chrome/others
      indexURL: `https://cdn.jsdelivr.net/pyodide/${pyodideVersion}/full/`,
    });
    this.pyodide = pyodide;
    span.end("ok");
    return pyodide;
  }

  private async installDevMarimoAndDeps(
    pyodide: PyodideInterface,
    version: string,
  ) {
    const span = t.startSpan("installDevMarimoAndDeps");
    await Promise.all([
      pyodide.runPythonAsync(`
      import micropip
      await micropip.install(
        [
          "${getMarimoWheel(version)}",
        ],
        deps=False,
        index_urls="https://test.pypi.org/pypi/{package_name}/json"
        );
      `),
      pyodide.runPythonAsync(`
      import micropip
      await micropip.install(
        [
          "Markdown==3.6",
          "pymdown-extensions==10.8.1",
          "narwhals>=1.0.0",
        ],
        deps=False,
        );
      `),
    ]);
    span.end("ok");
  }

  private async installMarimoAndDeps(
    pyodide: PyodideInterface,
    version: string,
  ) {
    const span = t.startSpan("installMarimoAndDeps");
    await pyodide.runPythonAsync(`
      import micropip
      await micropip.install(
        [
          "${getMarimoWheel(version)}",
          "Markdown==3.6",
          "pymdown-extensions==10.8.1",
          "narwhals>=1.0.0",
        ],
        deps=False,
      );
    `);
    span.end("ok");
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
    onMessage: (message: JsonString<OperationMessage>) => void;
    userConfig: UserConfig;
  }): Promise<SerializedBridge> {
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
    const [bridge, init, imports] = this.requirePyodide.runPython(
      `
      print("[py] Starting marimo...")
      import asyncio
      import js
      from marimo._pyodide.bootstrap import create_session, instantiate

      assert js.messenger, "messenger is not defined"
      assert js.query_params, "query_params is not defined"

      session, bridge = create_session(
        filename="${nbFilename}",
        query_params=js.query_params.to_py(),
        message_callback=js.messenger.callback,
        user_config=js.user_config.to_py(),
      )

      def init(auto_instantiate=True):
        if auto_instantiate:
          instantiate(session)
        asyncio.create_task(session.start())

      # Load the imports
      import pyodide.code
      with open("${nbFilename}", "r") as f:
        imports = pyodide.code.find_imports(f.read())

      bridge, init, imports`,
    );
    span.end();

    const moduleImports = new Set<string>(imports.toJs());

    // Fire and forgot load packages and instantiation
    // We don't want to wait for this to finish,
    // as it blocks the initial code from being shown.
    void this.loadNotebookDeps(code, moduleImports).then(() => {
      return init(userConfig.runtime.auto_instantiate);
    });

    return bridge;
  }

  private async loadNotebookDeps(code: string, foundImports: Set<string>) {
    const pyodide = this.requirePyodide;

    if (code.includes("mo.sql")) {
      // We need pandas and duckdb for mo.sql
      code = `import pandas\n${code}`;
      code = `import duckdb\n${code}`;
    }

    const imports = [...foundImports];

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
        print("[py] Loading packages from micropip:", missing)
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
