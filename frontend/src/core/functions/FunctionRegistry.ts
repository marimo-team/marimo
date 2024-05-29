/* Copyright 2024 Marimo. All rights reserved. */

import { sendFunctionRequest } from "@/core/network/requests";
import type { FunctionCallResultMessage } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import type { SendFunctionRequest } from "../network/types";

export const FUNCTIONS_REGISTRY = new DeferredRequestRegistry<
  Omit<SendFunctionRequest, "functionCallId">,
  FunctionCallResultMessage
>("function-call-result", async (requestId, req) => {
  // RPC counts as a kernel invocation
  await sendFunctionRequest({
    functionCallId: requestId,
    ...req,
  }).catch((error) => {
    throw error;
  });
});
