/* Copyright 2024 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import type { RawBridge, SerializedBridge, WasmController } from "./types";
import { Deferred } from "../../../utils/Deferred";
import { WasmFileSystem } from "./fs";
import { MessageBuffer } from "./message-buffer";
import { prettyError } from "../../../utils/errors";
import {
  createWorkerParentTransport,
  createRPC,
  createRPCRequestHandler,
  type RPCSchema,
} from "rpc-anywhere";
import type { ParentSchema } from "../rpc";
import { Logger } from "../../../utils/Logger";
import { TRANSPORT_ID } from "./constants";
import { invariant } from "../../../utils/invariant";
import type { OperationMessage } from "@/core/kernel/messages";
import type { JsonString } from "@/utils/json/base64";
import type { UserConfig } from "@/core/config/config-schema";
import { getPyodideVersion } from "./getPyodideVersion";
import { t } from "./tracer";
import { once } from "@/utils/once";
import { getController } from "./getController";
import type {
  ListPackagesResponse,
  PackageOperationResponse,
  SaveNotebookRequest,
} from "@/core/network/types";
import { decodeUtf8 } from "@/utils/strings";

/**
 * Web worker responsible for running the notebook.
 */

declare const self: Window & {
  pyodide: PyodideInterface;
  controller: WasmController;
};

const workerInitSpan = t.startSpan("worker:init");

// Initialize pyodide
async function loadPyodideAndPackages() {
  try {
    const marimoVersion = getMarimoVersion();
    const pyodideVersion = getPyodideVersion(marimoVersion);
    const controller = await t.wrapAsync(getController)(marimoVersion);
    self.controller = controller;
    rpc.send.initializingMessage({
      message: "Loading marimo...",
    });
    self.pyodide = await t.wrapAsync(controller.bootstrap.bind(controller))({
      version: marimoVersion,
      pyodideVersion: pyodideVersion,
    });
  } catch (error) {
    Logger.error("Error bootstrapping", error);
    rpc.send.initializedError({
      error: prettyError(error),
    });
  }
}

const messageBuffer = new MessageBuffer(
  (message: JsonString<OperationMessage>) => {
    rpc.send.kernelMessage({ message });
  },
);
const bridgeReady = new Deferred<SerializedBridge>();
let started = false;

// Handle RPC requests
const requestHandler = createRPCRequestHandler({
  /**
   * Start the session
   */
  startSession: async (opts: {
    queryParameters: Record<string, string | string[]>;
    code: string;
    filename: string | null;
    userConfig: UserConfig;
  }) => {
    await pyodideReadyPromise; // Make sure loading is done

    if (started) {
      Logger.warn("Session already started");
      return;
    }

    started = true;
    try {
      invariant(self.controller, "Controller not loaded");
      await self.controller.mountFilesystem?.({
        code: opts.code,
        filename: opts.filename,
      });
      const startSession = t.wrapAsync(
        self.controller.startSession.bind(self.controller),
      );
      const initializeOnce = once(() => {
        rpc.send.initializingMessage({
          message: "Initializing notebook...",
        });
        rpc.send.initialized({});
      });
      rpc.send.initializingMessage({
        message: "Loading notebook and dependencies...",
      });
      const bridge = await startSession({
        code: opts.code,
        filename: opts.filename,
        queryParameters: opts.queryParameters,
        userConfig: opts.userConfig,
        onMessage: (msg) => {
          initializeOnce();
          messageBuffer.push(msg);
        },
      });
      bridgeReady.resolve(bridge);
      workerInitSpan.end("ok");
    } catch (error) {
      rpc.send.initializedError({
        error: prettyError(error),
      });
      workerInitSpan.end("error");
    }
    return;
  },

  /**
   * Load packages
   */
  loadPackages: async (code: string) => {
    const span = t.startSpan("loadPackages");
    await pyodideReadyPromise; // Make sure loading is done

    if (code.includes("mo.sql")) {
      // Add pandas and duckdb to the code
      code = `import pandas\n${code}`;
      code = `import duckdb\n${code}`;
      code = `import sqlglot\n${code}`;
    }

    await self.pyodide.loadPackagesFromImports(code, {
      messageCallback: Logger.log,
      errorCallback: Logger.error,
    });
    span.end();
  },

  /**
   * Read a file
   */
  readFile: async (filename: string) => {
    const span = t.startSpan("readFile");
    await pyodideReadyPromise; // Make sure loading is done

    const file = decodeUtf8(self.pyodide.FS.readFile(filename));
    span.end();
    return file;
  },

  /**
   * Set the interrupt buffer
   */
  setInterruptBuffer: async (payload: Uint8Array) => {
    await pyodideReadyPromise; // Make sure loading is done

    self.pyodide.setInterruptBuffer(payload);
  },

  addPackage: async (opts: {
    package: string;
  }): Promise<PackageOperationResponse> => {
    await pyodideReadyPromise; // Make sure loading is done

    const { package: packageName } = opts;
    const response = await self.pyodide.runPythonAsync(`
      import micropip
      import json
      response = None
      try:
        await micropip.install("${packageName}")
        response = {"success": True}
      except Exception as e:
        response = {"success": False, "error": str(e)}
      json.dumps(response)
    `);
    return JSON.parse(response) as PackageOperationResponse;
  },

  removePackage: async (opts: {
    package: string;
  }): Promise<PackageOperationResponse> => {
    await pyodideReadyPromise; // Make sure loading is done

    const { package: packageName } = opts;
    const response = await self.pyodide.runPythonAsync(`
        import micropip
        import json
        response = None
        try:
          micropip.uninstall("${packageName}")
          response = {"success": True}
        except Exception as e:
          response = {"success": False, "error": str(e)}
        json.dumps(response)
      `);
    return JSON.parse(response) as PackageOperationResponse;
  },

  listPackages: async (): Promise<ListPackagesResponse> => {
    const span = t.startSpan("listPackages");
    await pyodideReadyPromise; // Make sure loading is done

    const packages = await self.pyodide.runPythonAsync(`
      import json
      import micropip

      packages = micropip.list()
      packages = [
        {"name": p.name, "version": p.version}
        for p in packages.values()
      ]
      json.dumps(sorted(packages, key=lambda pkg: pkg["name"]))
    `);
    span.end();
    return {
      packages: JSON.parse(packages) as ListPackagesResponse["packages"],
    };
  },

  /**
   * Save the notebook
   */
  saveNotebook: async (opts: SaveNotebookRequest) => {
    // Partially duplicated from save-worker.ts
    await pyodideReadyPromise; // Make sure loading is done
    const saveFile = self.pyodide.runPython(`
      from marimo._pyodide.bootstrap import save_file
      save_file
    `);
    await saveFile(JSON.stringify(opts), WasmFileSystem.NOTEBOOK_FILENAME);
  },

  /**
   * Call a function on the bridge
   */
  bridge: async (opts: {
    functionName: keyof RawBridge;
    payload: {} | undefined | null;
  }) => {
    const span = t.startSpan("bridge", {
      functionName: opts.functionName,
    });
    await pyodideReadyPromise; // Make sure loading is done

    const { functionName, payload } = opts;

    // Special case to lazily install black on format
    // Don't return early; still need to ask the pyodide kernel to run
    // the formatter
    if (functionName === "format") {
      await self.pyodide.runPythonAsync(`
        import micropip

        try:
          import black
        except ModuleNotFoundError:
          await micropip.install("black")
        `);
    }

    // Special case to lazily install PyYAML on export_markdown
    if (functionName === "export_markdown") {
      await self.pyodide.runPythonAsync(`
        import micropip

        try:
          import yaml
        except ModuleNotFoundError:
          await micropip.install("pyyaml")
        `);
    }

    // Perform the function call to the Python bridge
    const bridge = await bridgeReady.promise;

    // Serialize the payload
    const payloadString =
      payload == null
        ? null
        : typeof payload === "string"
          ? payload
          : JSON.stringify(payload);

    // Make the request
    const response =
      payloadString == null
        ? // @ts-expect-error ehh TypeScript
          await bridge[functionName]()
        : // @ts-expect-error ehh TypeScript
          await bridge[functionName](payloadString);

    // Sync the filesystem if we're saving, creating, deleting, or renaming a file
    if (namesThatRequireSync.has(functionName)) {
      void WasmFileSystem.persistFilesToRemote(self.pyodide);
    }

    span.end();
    // Post the response back to the main thread
    return typeof response === "string" ? JSON.parse(response) : response;
  },
});

// create the iframe's schema
export type WorkerSchema = RPCSchema<
  {
    messages: {
      // Emitted when the worker is ready
      ready: {};
      // Emitted when the kernel sends a message
      kernelMessage: { message: JsonString<OperationMessage> };
      // Emitted when the Pyodide is initialized
      initialized: {};
      // Emitted when the Pyodide is initializing, with new messages
      initializingMessage: { message: string };
      // Emitted when the Pyodide fails to initialize
      initializedError: { error: string };
    };
  },
  typeof requestHandler
>;

const rpc = createRPC<WorkerSchema, ParentSchema>({
  transport: createWorkerParentTransport({
    transportId: TRANSPORT_ID,
  }),
  requestHandler,
});

rpc.send("ready", {});

/// Listeners
// When the consumer is ready, start the message buffer
rpc.addMessageListener("consumerReady", async () => {
  await pyodideReadyPromise; // Make sure loading is done
  messageBuffer.start();
});

const namesThatRequireSync = new Set<keyof RawBridge>([
  "save",
  "save_app_config",
  "rename_file",
  "create_file_or_directory",
  "delete_file_or_directory",
  "move_file_or_directory",
  "update_file",
]);

function getMarimoVersion() {
  return self.name; // We store the version in the worker name
}

const pyodideReadyPromise = t.wrapAsync(loadPyodideAndPackages)();
