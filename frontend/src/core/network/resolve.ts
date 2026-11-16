/* Copyright 2026 Marimo. All rights reserved. */
import { withPackageInvalidation } from "../packages/package-data";
import { isStaticNotebook } from "../static/static-state";
import { PyodideBridge } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import { createNetworkRequests } from "./requests-network";
import { createStaticRequests } from "./requests-static";
import { createErrorToastingRequests } from "./requests-toasting";
import type { EditRequests, RunRequests } from "./types";

export function resolveRequestClient(): EditRequests & RunRequests {
  let base: EditRequests & RunRequests;
  if (isWasm()) {
    base = PyodideBridge.INSTANCE;
  } else if (isStaticNotebook()) {
    base = createStaticRequests();
  } else {
    base = createNetworkRequests();
  }
  return withPackageInvalidation(createErrorToastingRequests(base));
}
