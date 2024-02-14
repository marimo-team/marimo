/* Copyright 2024 Marimo. All rights reserved. */

import { bootstrap, startSession } from "./bootstrap";
import type { PyodideInterface } from "pyodide";
import {
  SerializedBridge,
  WorkerClientPayload,
  WorkerServerPayload,
} from "./types";
import { invariant } from "../../../utils/invariant";
import { Deferred } from "../../../utils/Deferred";

declare const self: Window & {
  pyodide: PyodideInterface;
};

// Initialize pyodide
async function loadPyodideAndPackages() {
  // @ts-expect-error ehh TypeScript
  await import("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");
  self.pyodide = await bootstrap();
}
const pyodideReadyPromise = loadPyodideAndPackages();

// Initialize the session
const bridgeReady = new Deferred<SerializedBridge>();
let started = false;
function startSessionWithCode(code: string) {
  if (started) {
    return;
  }
  started = true;
  startSession(self.pyodide, code).then((bridge) => {
    bridgeReady.resolve(bridge);
    postMessage({ type: "initialized" });
  });
}
async function getBridge() {
  return bridgeReady.promise;
}

self.onmessage = async (event: MessageEvent<WorkerServerPayload>) => {
  // make sure loading is done
  await pyodideReadyPromise;

  // Start the session
  if (event.data.type === "set-code") {
    startSessionWithCode(event.data.code);
    return;
  }

  // Run forever, waiting for messages from the Python bridge
  if (event.data.type === "start-messages") {
    const done = false;

    while (!done) {
      const bridge = await getBridge();
      for await (const message of bridge) {
        postMessage({ type: "message", message });
      }
    }

    return;
  }

  const { id, functionName, payload } = event.data;
  try {
    // Special case for loading packages
    if (functionName === "load_packages") {
      invariant(
        typeof payload === "string",
        "Expected a string payload for load_packages",
      );
      await self.pyodide.loadPackagesFromImports(payload, {
        messageCallback: console.log,
        errorCallback: console.error,
      });

      postMessage({ type: "response", response: null, id });
      return;
    }

    // Perform the function call to the Python bridge
    const bridge = await getBridge();
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
    postMessage({
      type: "response",
      response: typeof response === "string" ? JSON.parse(response) : response,
      id,
    });
  } catch (error) {
    console.error("Error in worker", error);
    if (error instanceof Error) {
      postMessage({ type: "error", error: error.message, id });
    } else {
      postMessage({ type: "error", error: String(error), id });
    }
  }
};

function postMessage(message: WorkerClientPayload) {
  self.postMessage(message);
}

postMessage({ type: "ready" });
