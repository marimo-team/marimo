/* Copyright 2024 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import { Deferred } from "../../../utils/Deferred";
import { prettyError } from "../../../utils/errors";
import {
  createWorkerParentTransport,
  createRPC,
  createRPCRequestHandler,
  type RPCSchema,
} from "rpc-anywhere";
import { invariant } from "../../../utils/invariant";
import { ParentSchema } from "@/core/pyodide/rpc";
import { TRANSPORT_ID } from "@/core/pyodide/worker/constants";
import { MessageBuffer } from "@/core/pyodide/worker/message-buffer";
import { SerializedBridge, RawBridge } from "@/core/pyodide/worker/types";
import { ReadonlyWasmController } from "./controller";
import { OperationMessage } from "@/core/kernel/messages";
import { JsonString } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";

declare const self: Window & {
  pyodide: PyodideInterface;
  controller: ReadonlyWasmController;
};

// Initialize pyodide
async function loadPyodideAndPackages() {
  // @ts-expect-error ehh TypeScript
  await import("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");
  try {
    self.controller = new ReadonlyWasmController();
    self.pyodide = await self.controller.bootstrap({
      version: getMarimoVersion(),
    });
  } catch (error) {
    console.error("Error bootstrapping", error);
    rpc.send.initializedError({
      error: prettyError(error),
    });
  }
}

const pyodideReadyPromise = loadPyodideAndPackages();
const messageBuffer = new MessageBuffer(
  (message: JsonString<OperationMessage>) => {
    rpc.send.kernelMessage({ message });
  },
);
const bridgeReady = new Deferred<SerializedBridge>();

// Handle RPC requests
const requestHandler = createRPCRequestHandler({
  /**
   * Start the session
   */
  startSession: async (opts: { code: string; appId: string }) => {
    await pyodideReadyPromise; // Make sure loading is done

    try {
      invariant(self.controller, "Controller not loaded");
      const bridge = await self.controller.startSession({
        code: opts.code,
        filename: `app-${opts.appId}.py`,
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
      messageCallback: Logger.log,
      errorCallback: Logger.error,
    });
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

function getMarimoVersion() {
  return self.name; // We store the version in the worker name
}
