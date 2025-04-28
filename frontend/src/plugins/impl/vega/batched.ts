/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { batch } from "@/utils/batch-requests";
import { createLoader, type Loader } from "./vega-loader";
import { tableFromIPC } from "@uwdata/flechette";

export function createBatchedLoader(): Loader {
  const loader = withArrowSupport(createLoader());
  const toKey = (request: unknown) => JSON.stringify(request);
  return {
    load: batch(loader.load.bind(loader) as any, toKey),
    sanitize: batch(loader.sanitize.bind(loader) as any, toKey),
    http: batch(loader.http.bind(loader) as any, toKey),
    file: batch(loader.file.bind(loader), toKey),
  };
}

export function withArrowSupport(loader: Loader): Loader {
  return {
    ...loader,
    async load(uri: string, options?: unknown) {
      if (uri.endsWith(".arrow")) {
        const arrow = await batchedArrowLoader(uri);
        return tableFromIPC(arrow, {
          // useProxy=true makes aggregations like year(data) fail
          useProxy: false,
        }).toArray();
      }
      return loader.load(uri, options);
    },
  };
}

/**
 * Batch requests to the same URL returning the same promise for all calls with the same key.
 */
export const batchedArrowLoader = batch(
  (url: string) => fetch(url).then((r) => r.arrayBuffer()),
  (url: string) => url,
);
