/* Copyright 2026 Marimo. All rights reserved. */

import type { SecretKeysResult } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { getRequestClient } from "../network/requests";

export const SECRETS_REGISTRY = new DeferredRequestRegistry<
  {},
  SecretKeysResult
>("secrets-result", async (requestId, req) => {
  const client = getRequestClient();
  await client.listSecretKeys({
    requestId: requestId,
    ...req,
  });
});
