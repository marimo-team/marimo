/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable ssr-friendly/no-dom-globals-in-module-scope */

import { Logger } from "../Logger";
import { once } from "../once";
import { jsonParseWithSpecialChar } from "./json-parser";
import { Deferred } from "../Deferred";
import { isStaticNotebook } from "@/core/static/static-state";

const warnOnce = once(() => {
  Logger.warn(
    "Your browser doesn't support web workers. JSON will be parsed in main thread."
  );
});

// Shared worker, so messages are processed in order
// eslint-disable-next-line unicorn/relative-url-style
const jsonParsingWorker = new Worker(new URL("./worker.ts", import.meta.url), {
  type: "module",
});

/**
 * Parse JSON in a web worker, if supported.
 * Otherwise, parse in main thread.
 */
export async function asyncJSONParse<T>(json: string): Promise<T> {
  // If web worker is not supported, parse in main thread
  if (!window.Worker) {
    warnOnce();
    return jsonParseWithSpecialChar(json);
  }

  // If static notebook, parse in main thread
  if (isStaticNotebook()) {
    return jsonParseWithSpecialChar(json);
  }

  const deferred = new Deferred<T>();

  // Send message to worker
  jsonParsingWorker.onmessage = ({ data }) => deferred.resolve(data);
  jsonParsingWorker.onerror = (e) => deferred.reject(e);
  jsonParsingWorker.postMessage(json);

  return await deferred.promise.catch((error) => {
    Logger.log("Failed to parse JSON in web worker.", error);
    return jsonParseWithSpecialChar(json);
  });
}
