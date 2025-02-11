/* Copyright 2024 Marimo. All rights reserved. */

import { previewSQLTable, sendFunctionRequest } from "@/core/network/requests";
import type {
  FunctionCallResultMessage,
  SQLTablePreview,
} from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import type {
  FunctionCallRequest,
  PreviewSQLTableRequest,
} from "../network/types";

export const FUNCTIONS_REGISTRY = new DeferredRequestRegistry<
  Omit<FunctionCallRequest, "functionCallId">,
  FunctionCallResultMessage
>("function-call-result", async (requestId, req) => {
  // RPC counts as a kernel invocation
  await sendFunctionRequest({
    functionCallId: requestId,
    ...req,
  });
});

export const PreviewSQLTable = new DeferredRequestRegistry<
  Omit<PreviewSQLTableRequest, "requestId">,
  SQLTablePreview
>("sql-table-preview", async (requestId, req) => {
  await previewSQLTable({
    requestId: requestId,
    ...req,
  });
});
