/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { Logger } from "../../../utils/Logger";
import { defaultUserConfig } from "@/core/config/config-schema";
import type { SerializedBridge } from "@/core/wasm/worker/types";
import type { OperationMessage } from "@/core/kernel/messages";
import type { JsonString } from "@/utils/json/base64";
import { DefaultWasmController } from "@/core/wasm/worker/bootstrap";
import { WasmFileSystem } from "@/core/wasm/worker/fs";

export class ReadonlyWasmController extends DefaultWasmController {
  override async bootstrap(opts: {
    version: string;
    pyodideVersion: string;
  }): Promise<PyodideInterface> {
    const pyodide = await super.bootstrap(opts);
    return pyodide;
  }

  override async mountFilesystem(opts: { code: string; filename: string }) {
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

  override async startSession(opts: {
    code: string;
    filename: string | null;
    onMessage: (message: JsonString<OperationMessage>) => void;
  }): Promise<SerializedBridge> {
    const bridge = super.startSession({
      queryParameters: {},
      code: opts.code,
      filename: opts.filename,
      onMessage: opts.onMessage,
      userConfig: defaultUserConfig(),
    });

    return bridge;
  }
}
