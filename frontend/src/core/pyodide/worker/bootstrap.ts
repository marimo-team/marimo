/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { mountFilesystem } from "./fs";
import { Logger } from "../../../utils/Logger";
import { SerializedBridge, WasmController } from "./types";
import { invariant } from "../../../utils/invariant";
import { UserConfig } from "@/core/config/config-schema";
import { getMarimoWheel } from "./getMarimoWheel";
import { OperationMessage } from "@/core/kernel/messages";
import { JsonString } from "@/utils/json/base64";

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

  async bootstrap(opts: { version: string }): Promise<PyodideInterface> {
    const pyodide = await this.loadPyoideAndPackages();

    const { version } = opts;

    // If is a dev release, we need to install from test.pypi.org
    if (version.includes("dev")) {
      await this.installDevMarimo(pyodide, version);
    }

    await this.installMarimoAndDeps(pyodide, version);

    return pyodide;
  }

  private async loadPyoideAndPackages(): Promise<PyodideInterface> {
    if (!loadPyodide) {
      throw new Error("loadPyodide is not defined");
    }
    // Load pyodide and packages
    const pyodide = await loadPyodide({
      // Perf: These get loaded while pyodide is being bootstrapped
      // The packages can be found here: https://pyodide.org/en/stable/usage/packages-in-pyodide.html
      packages: ["micropip", "docutils", "Pygments", "jedi", "pyodide-http"],
      // Without this, this fails in Firefox with
      // `Could not extract indexURL path from pyodide module`
      // This fixes for Firefox and does not break Chrome/others
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/",
    });
    this.pyodide = pyodide;
    return pyodide;
  }

  private async installDevMarimo(pyodide: PyodideInterface, version: string) {
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
  }

  private async installMarimoAndDeps(
    pyodide: PyodideInterface,
    version: string,
  ) {
    await pyodide.runPythonAsync(`
      import micropip

      await micropip.install(
        [
          "${getMarimoWheel(version)}",
          "markdown",
          "pymdown-extensions",
        ],
        deps=False,
        );
      `);
  }

  protected mountFilesystem(opts: { code: string; filename: string | null }) {
    return mountFilesystem({
      pyodide: this.requirePyodide,
      ...opts,
    });
  }

  async startSession(opts: {
    queryParameters: Record<string, string | string[]>;
    code: string;
    filename: string | null;
    onMessage: (message: JsonString<OperationMessage>) => void;
    userConfig: UserConfig;
  }): Promise<SerializedBridge> {
    // Set up the filesystem
    const { filename, content } = await this.mountFilesystem({
      code: opts.code,
      filename: opts.filename,
    });

    // We pass down a messenger object to the code
    // This is used to have synchronous communication between the JS and Python code
    // Previously, we used a queue, but this would not properly flush the queue
    // during processing of a cell's code.
    //
    // This adds a messenger object to the global scope (import js; js.messenger.callback)
    self.messenger = {
      callback: opts.onMessage,
    };
    self.query_params = opts.queryParameters;
    self.user_config = opts.userConfig;

    // Load packages from the code
    await this.requirePyodide.loadPackagesFromImports(content, {
      messageCallback: Logger.log,
      errorCallback: Logger.error,
    });

    const bridge = await this.requirePyodide.runPythonAsync(
      `
      print("[py] Starting marimo...")
      import asyncio
      import js
      from marimo._pyodide.pyodide_session import create_session, instantiate

      assert js.messenger, "messenger is not defined"
      assert js.query_params, "query_params is not defined"

      session, bridge = create_session(
        filename="${filename}",
        query_params=js.query_params.to_py(),
        message_callback=js.messenger.callback,
        user_config=js.user_config.to_py(),
      )
      instantiate(session)
      asyncio.create_task(session.start())

      bridge`,
    );

    return bridge;
  }
}
