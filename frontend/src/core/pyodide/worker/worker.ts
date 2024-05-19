/* Copyright 2024 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import { RawBridge, SerializedBridge, WasmController } from "./types";
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
import { ParentSchema } from "../rpc";
import { Logger } from "../../../utils/Logger";
import { TRANSPORT_ID } from "./constants";
import { invariant } from "../../../utils/invariant";
import { OperationMessage } from "@/core/kernel/messages";
import { JsonString } from "@/utils/json/base64";
import { UserConfig } from "@/core/config/config-schema";
import { getPyodideVersion, importPyodide } from "./getPyodideVersion";
import { t } from "./tracer";
import { once } from "@/utils/once";
import { getController } from "./getController";

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
    await t.wrapAsync(importPyodide)(marimoVersion);
    const controller = await t.wrapAsync(getController)(marimoVersion);
    self.controller = controller;
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

const pyodideReadyPromise = t.wrapAsync(loadPyodideAndPackages)();
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
        rpc.send.initialized({});
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
  loadPackages: async (packages: string) => {
    const span = t.startSpan("loadPackages");
    await pyodideReadyPromise; // Make sure loading is done

    await self.pyodide.loadPackagesFromImports(packages, {
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

    const file = self.pyodide.FS.readFile(filename, { encoding: "utf8" });
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
