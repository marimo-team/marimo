/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable ssr-friendly/no-dom-globals-in-module-scope */

import { Logger } from "../Logger";
import { once } from "../once";
import { jsonParseWithSpecialChar } from "./json-parser";
import { Deferred } from "../Deferred";

const warnOnce = once(() => {
  Logger.warn(
    "Your browser doesn't support web workers. JSON will be parsed in main thread."
  );
});

// eslint-disable-next-line unicorn/relative-url-style
const jsonParsingWorker = new Worker(new URL("./worker.ts", import.meta.url), {
  type: "module",
});

/**
 * Parse JSON in a web worker.
 */
export function asyncJSONParse<T>(json: string): Promise<T> {
  // If web worker is not supported, parse in main thread
  if (!window.Worker) {
    warnOnce();
    return Promise.resolve(jsonParseWithSpecialChar(json));
  }

  const deferred = new Deferred<T>();

  // Send message to worker
  jsonParsingWorker.onmessage = ({ data }) => deferred.resolve(data);
  jsonParsingWorker.onerror = (e) => deferred.reject(e);
  jsonParsingWorker.postMessage(json);

  return deferred.promise;
}
