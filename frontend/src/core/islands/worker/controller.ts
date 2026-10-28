/* Copyright 2026 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { defaultUserConfig } from "@/core/config/config-schema";
import { DefaultWasmController } from "@/core/wasm/worker/bootstrap";
import { WasmFileSystem } from "@/core/wasm/worker/fs";
import type { WasmSession } from "@/core/wasm/worker/types";
import { Logger } from "../../../utils/Logger";

export class ReadonlyWasmController extends DefaultWasmController {
  public override async bootstrap(opts: {
    version: string;
    pyodideVersion: string;
  }): Promise<PyodideInterface> {
    const pyodide = await super.bootstrap(opts);
    return pyodide;
  }

  public override async mountFilesystem(opts: {
    code: string;
    filename: string;
  }) {
    const { code, filename } = opts;
    // Write file
    try {
      WasmFileSystem.createHomeDir(this.requirePyodide);
      return WasmFileSystem.initNotebookCode({
        pyodide: this.requirePyodide,
        code,
        filename,
      });
    } catch (error) {
      Logger.error(error);
    }

    return { code, filename };
  }

  public override async prepareSession(opts: {
    code: string;
    filename: string | null;
  }): Promise<WasmSession> {
    return super.prepareSession({
      queryParameters: {},
      code: opts.code,
      filename: opts.filename,
      userConfig: defaultUserConfig(),
    });
  }
}
