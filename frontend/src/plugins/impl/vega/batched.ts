/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { batch } from "@/utils/batch-requests";
import { createLoader, type Loader } from "./vega-loader";

export function createBatchedLoader(): Loader {
  const loader = createLoader();
  const toKey = (request: unknown) => JSON.stringify(request);
  return {
    load: batch(loader.load.bind(loader) as any, toKey),
    sanitize: batch(loader.sanitize.bind(loader) as any, toKey),
    http: batch(loader.http.bind(loader) as any, toKey),
    file: batch(loader.file.bind(loader), toKey),
  };
}
