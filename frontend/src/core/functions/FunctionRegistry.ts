/* Copyright 2026 Marimo. All rights reserved. */

import type { FunctionCallResultMessage } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { getRequestClient } from "../network/requests";
import type { InvokeFunctionRequest } from "../network/types";

export const FUNCTIONS_REGISTRY = new DeferredRequestRegistry<
  Omit<InvokeFunctionRequest, "functionCallId">,
  FunctionCallResultMessage
>("function-call-result", async (requestId, req) => {
  const client = getRequestClient();
  // RPC counts as a kernel invocation
  await client.sendFunctionRequest({
    functionCallId: requestId,
    ...req,
  });
});
