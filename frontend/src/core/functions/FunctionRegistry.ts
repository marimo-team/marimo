/* Copyright 2023 Marimo. All rights reserved. */

import { sendFunctionRequest } from "@/core/network/requests";
import { FunctionCallResultMessage } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { SendFunctionRequest } from "../network/types";

export const FUNCTIONS_REGISTRY = new DeferredRequestRegistry<
  Omit<SendFunctionRequest, "id">,
  FunctionCallResultMessage
>("function-call-result", async (requestId, req) => {
  await sendFunctionRequest({
    id: requestId,
    ...req,
  });
});
