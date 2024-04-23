/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { Logger } from "../../../utils/Logger";
import { defaultUserConfig } from "@/core/config/config-schema";
import { getFS } from "@/core/pyodide/worker/getFS";
import { SerializedBridge } from "@/core/pyodide/worker/types";
import { OperationMessage } from "@/core/kernel/messages";
import { JsonString } from "@/utils/json/base64";
import { DefaultWasmController } from "@/core/pyodide/worker/bootstrap";
import { invariant } from "@/utils/invariant";

export class ReadonlyWasmController extends DefaultWasmController {
  private MOUNT_POINT = "/marimo";

  override async bootstrap(opts: {
    version: string;
  }): Promise<PyodideInterface> {
    const pyodide = await super.bootstrap(opts);

    // Make dir and change to it
    const fs = getFS(pyodide);
    fs.mkdir(this.MOUNT_POINT);
    fs.chdir(this.MOUNT_POINT);

    return pyodide;
  }

  protected override mountFilesystem(opts: {
    code: string;
    filename: string | null;
  }) {
    const { code, filename } = opts;
    invariant(filename, "Filename is required");

    // Write file
    try {
      const fs = getFS(this.requirePyodide);
      fs.writeFile(`${this.MOUNT_POINT}/${filename}`, code);
    } catch (error) {
      Logger.error(error);
    }

    return Promise.resolve({ content: code, filename });
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
