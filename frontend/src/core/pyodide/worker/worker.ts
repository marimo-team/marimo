/* Copyright 2024 Marimo. All rights reserved. */

import { DefaultWasmController } from "./bootstrap";
import type { PyodideInterface } from "pyodide";
import { RawBridge, SerializedBridge, WasmController } from "./types";
import { Deferred } from "../../../utils/Deferred";
import { syncFileSystem } from "./fs";
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

declare const self: Window & {
  pyodide: PyodideInterface;
  controller: WasmController;
  rpc: ReturnType<typeof createRPC>;
};

// Initialize pyodide
async function loadPyodideAndPackages() {
  // @ts-expect-error ehh TypeScript
  await import("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");
  try {
    const version = getMarimoVersion();
    const controller = await getController(version);
    self.controller = controller;
    self.pyodide = await controller.bootstrap({
      version,
    });
  } catch (error) {
    console.error("Error bootstrapping", error);
    rpc.send.initializedError({
      error: prettyError(error),
    });
  }
}

// Load the controller
// Falls back to the default controller
async function getController(version: string) {
  try {
    const controller = await import(
      /* @vite-ignore */ `/wasm/controller.js?version=${version}`
    );
    return controller;
  } catch {
    return new DefaultWasmController();
  }
}

const pyodideReadyPromise = loadPyodideAndPackages();
const messageBuffer = new MessageBuffer((message: string) => {
  rpc.send.kernelMessage({ message });
});
const bridgeReady = new Deferred<SerializedBridge>();
let started = false;

// Handle RPC requests
const requestHandler = createRPCRequestHandler({
  /**
   * Start the session
   */
  startSession: async (opts: {
    queryParameters: Record<string, string | string[]>;
    code: string | null;
    fallbackCode: string;
    filename: string | null;
  }) => {
    await pyodideReadyPromise; // Make sure loading is done

    if (started) {
      Logger.warn("Session already started");
      return;
    }

    started = true;
    try {
      invariant(self.controller, "Controller not loaded");
      const bridge = await self.controller.startSession({
        ...opts,
        onMessage: messageBuffer.push,
      });
      bridgeReady.resolve(bridge);
      rpc.send.initialized({});
    } catch (error) {
      rpc.send.initializedError({
        error: prettyError(error),
      });
    }
    return;
  },

  /**
   * Load packages
   */
  loadPackages: async (packages: string) => {
    await pyodideReadyPromise; // Make sure loading is done

    await self.pyodide.loadPackagesFromImports(packages, {
      messageCallback: console.log,
      errorCallback: console.error,
    });
  },

  /**
   * Read a file
   */
  readFile: async (filename: string) => {
    await pyodideReadyPromise; // Make sure loading is done

    const file = self.pyodide.FS.readFile(filename, { encoding: "utf8" });
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
      void syncFileSystem(self.pyodide, false);
    }

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
      kernelMessage: { message: string };
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

self.rpc = rpc;
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
