/* Copyright 2026 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import type { PyProxy } from "pyodide/ffi";
import {
  createRPC,
  createRPCRequestHandler,
  createWorkerParentTransport,
  type RPCSchema,
} from "rpc-anywhere";
import type { NotificationPayload } from "@/core/kernel/messages";
import type { ParentSchema } from "@/core/wasm/rpc";
import { shouldLoadDuckDBPackages } from "@/core/wasm/utils";
import { TRANSPORT_ID } from "@/core/wasm/worker/constants";
import { getPyodideVersion } from "@/core/wasm/worker/getPyodideVersion";
import { MessageBuffer } from "@/core/wasm/worker/message-buffer";
import type { RawBridge, SerializedBridge } from "@/core/wasm/worker/types";
import type { JsonString } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { prettyError } from "../../../utils/errors";
import { invariant } from "../../../utils/invariant";
import { ReadonlyWasmController } from "./controller";

declare const self: Window & {
  pyodide: PyodideInterface;
  controller: ReadonlyWasmController;
};

// Initialize pyodide
async function loadPyodideAndPackages() {
  const marimoVersion = getMarimoVersion();
  const pyodideVersion = getPyodideVersion(marimoVersion);
  try {
    self.controller = new ReadonlyWasmController();
    self.pyodide = await self.controller.bootstrap({
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

const pyodideReadyPromise = loadPyodideAndPackages();
export interface IslandsKernelMessage {
  message: JsonString<NotificationPayload>;
  sessionGeneration: number;
}

const messageBuffer = new MessageBuffer<IslandsKernelMessage>((payload) => {
  rpc.send.kernelMessage(payload);
});
interface SessionRequest {
  code: string;
  appId: string;
  sessionGeneration: number;
}

let activeSession:
  | (Omit<SessionRequest, "code"> & { bridge: SerializedBridge })
  | undefined;
let sessionQueue = Promise.resolve();

async function startSession(
  opts: SessionRequest,
  replace: boolean,
): Promise<void> {
  await pyodideReadyPromise;

  try {
    invariant(self.controller, "Controller not loaded");
    if (replace) {
      await stopActiveSession();
    }
    const notebook = await self.controller.mountFilesystem({
      code: opts.code,
      filename: `app-${opts.appId}.py`,
    });
    const nextBridge = await self.controller.startSession({
      ...notebook,
      onMessage: (message) => {
        messageBuffer.push({
          message,
          sessionGeneration: opts.sessionGeneration,
        });
      },
    });
    if (activeSession) {
      (nextBridge as unknown as PyProxy).destroy();
    } else {
      activeSession = {
        appId: opts.appId,
        bridge: nextBridge,
        sessionGeneration: opts.sessionGeneration,
      };
    }
    rpc.send.initialized({});
  } catch (error) {
    rpc.send.initializedError({
      error: prettyError(error),
    });
    throw error;
  }
}

async function stopActiveSession(): Promise<void> {
  const session = activeSession;
  await self.controller.stopSession();
  activeSession = undefined;
  (session?.bridge as unknown as PyProxy | undefined)?.destroy();
}

function enqueueSession<T>(operation: () => Promise<T>): Promise<T> {
  const result = sessionQueue.then(operation);
  sessionQueue = result.then(
    () => undefined,
    () => undefined,
  );
  return result;
}

// Handle RPC requests
const requestHandler = createRPCRequestHandler({
  /**
   * Start the session
   */
  startSession: async (opts: SessionRequest) => {
    await enqueueSession(() => startSession(opts, false));
  },

  replaceSession: async (opts: SessionRequest) => {
    await enqueueSession(() => startSession(opts, true));
  },

  stopSession: async (opts: { appId: string; sessionGeneration: number }) => {
    await enqueueSession(async () => {
      if (
        activeSession?.appId !== opts.appId ||
        activeSession?.sessionGeneration !== opts.sessionGeneration
      ) {
        return;
      }
      invariant(self.controller, "Controller not loaded");
      await stopActiveSession();
    });
  },

  /**
   * Load packages
   */
  loadPackages: async (opts: {
    appId: string;
    code: string;
    sessionGeneration: number;
  }) => {
    await pyodideReadyPromise; // Make sure loading is done
    await enqueueSession(async () => {
      requireActiveBridge(opts);

      let { code } = opts;

      if (shouldLoadDuckDBPackages(code)) {
        // Add pandas and duckdb to the code for mo.sql and for remote duckdb sources
        code = `import pandas\n${code}`;
        code = `import duckdb\n${code}`;
        code = `import sqlglot\n${code}`;

        // Polars + SQL requires pyarrow, and installing
        // after notebook load does not work. As a heuristic,
        // if it appears that the notebook uses polars, add pyarrow.
        if (code.includes("polars")) {
          code = `import pyarrow\n${code}`;
        }
      }

      await self.pyodide.loadPackagesFromImports(code, {
        messageCallback: Logger.log,
        errorCallback: Logger.error,
      });
    });
  },

  /**
   * Call a function on the bridge
   */
  bridge: async (opts: {
    appId: string;
    functionName: keyof RawBridge;
    payload: {} | undefined | null;
    sessionGeneration: number;
  }) => {
    await pyodideReadyPromise; // Make sure loading is done

    const { functionName, payload } = opts;

    // Perform the function call to the Python bridge
    return enqueueSession(async () => {
      const bridge = requireActiveBridge(opts);

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
    });
  },
});

function requireActiveBridge(opts: {
  appId: string;
  sessionGeneration: number;
}): SerializedBridge {
  const session = activeSession;
  if (
    !session ||
    opts.appId !== session.appId ||
    opts.sessionGeneration !== session.sessionGeneration
  ) {
    throw new Error("The marimo app session is no longer active.");
  }
  return session.bridge;
}

// create the iframe's schema
export type WorkerSchema = RPCSchema<
  {
    messages: {
      // Emitted when the worker is ready
      ready: {};
      // Emitted when the kernel sends a message
      kernelMessage: IslandsKernelMessage;
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
