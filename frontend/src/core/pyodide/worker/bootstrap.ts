/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { WasmFileSystem } from "./fs";
import { Logger } from "../../../utils/Logger";
import { SerializedBridge, WasmController } from "./types";
import { invariant } from "../../../utils/invariant";
import { UserConfig } from "@/core/config/config-schema";
import { getMarimoWheel } from "./getMarimoWheel";
import { OperationMessage } from "@/core/kernel/messages";
import { JsonString } from "@/utils/json/base64";
import { t } from "./tracer";

declare let loadPyodide: (opts: {
  packages: string[];
  indexURL: string;
}) => Promise<PyodideInterface>;

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
    const pyodide = await this.loadPyoideAndPackages(opts.pyodideVersion);

    const { version } = opts;

    // If is a dev release, we need to install from test.pypi.org
    if (version.includes("dev")) {
      await this.installDevMarimo(pyodide, version);
    }

    await this.installMarimoAndDeps(pyodide, version);

    return pyodide;
  }

  private async loadPyoideAndPackages(
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

  private async installDevMarimo(pyodide: PyodideInterface, version: string) {
    const span = t.startSpan("installDevMarimo");
    await pyodide.runPythonAsync(`
      import micropip

      await micropip.install(
        [
          "${getMarimoWheel(version)}",
        ],
        deps=False,
        index_urls="https://test.pypi.org/pypi/{package_name}/json"
        );
      `);
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
          "pymdown-extensions==10.8.1"
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
    const [bridge, init] = this.requirePyodide.runPython(
      `
      print("[py] Starting marimo...")
      import asyncio
      import js
      from marimo._pyodide.bootstrap import create_session, instantiate

      assert js.messenger, "messenger is not defined"
      assert js.query_params, "query_params is not defined"

      session, bridge = create_session(
        filename="${filename || WasmFileSystem.NOTEBOOK_FILENAME}",
        query_params=js.query_params.to_py(),
        message_callback=js.messenger.callback,
        user_config=js.user_config.to_py(),
      )

      def init():
        instantiate(session)
        asyncio.create_task(session.start())

      bridge, init`,
    );
    span.end();

    // Fire and forgot load packages and instantiation
    // We don't want to wait for this to finish,
    // as it blocks the initial code from being shown.
    const loadSpan = t.startSpan("loadPackagesFromImports");
    void this.requirePyodide
      .loadPackagesFromImports(code, {
        messageCallback: Logger.log,
        errorCallback: Logger.error,
      })
      .then(() => {
        loadSpan.end();
        init();
      });

    return bridge;
  }
}
