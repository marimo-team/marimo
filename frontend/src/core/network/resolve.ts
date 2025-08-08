/* Copyright 2024 Marimo. All rights reserved. */
import { isStaticNotebook } from "../static/static-state";
import { PyodideBridge } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import { createNetworkRequests } from "./requests-network";
import { createStaticRequests } from "./requests-static";
import { createErrorToastingRequests } from "./requests-toasting";
import type { EditRequests, RunRequests } from "./types";

export function resolveRequestClient(): EditRequests & RunRequests {
  const base = isWasm()
    ? PyodideBridge.INSTANCE
    : isStaticNotebook()
      ? createStaticRequests()
      : createNetworkRequests();
  return createErrorToastingRequests(base);
}
