/* Copyright 2024 Marimo. All rights reserved. */

import { listSecretKeys } from "@/core/network/requests";
import type { SecretKeysResult } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";

export const SECRETS_REGISTRY = new DeferredRequestRegistry<
  {},
  SecretKeysResult
>("secrets-result", async (requestId, req) => {
  await listSecretKeys({
    requestId: requestId,
    ...req,
  });
});
