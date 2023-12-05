/* Copyright 2023 Marimo. All rights reserved. */

import { RuntimeState } from "@/core/kernel/RuntimeState";
import { sendFunctionRequest } from "@/core/network/requests";
import { FunctionCallResultMessage } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { SendFunctionRequest } from "../network/types";

export const FUNCTIONS_REGISTRY = new DeferredRequestRegistry<
  Omit<SendFunctionRequest, "functionCallId">,
  FunctionCallResultMessage
>("function-call-result", async (requestId, req) => {
  // RPC counts as a kernel invocation
  RuntimeState.INSTANCE.registerRunStart();
  await sendFunctionRequest({
    functionCallId: requestId,
    ...req,
  });
});
