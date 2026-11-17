/* Copyright 2026 Marimo. All rights reserved. */

import { getRuntimeManager } from "../runtime/config";
import { API, createClientWithRuntimeManager } from "./api";

export function listProviderModels(provider: string) {
  return createClientWithRuntimeManager(getRuntimeManager())
    .GET("/api/ai/models/{provider_name}", {
      params: { path: { provider_name: encodeURIComponent(provider) } },
    })
    .then(API.handleResponse);
}
