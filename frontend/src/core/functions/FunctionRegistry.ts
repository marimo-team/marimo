/* Copyright 2024 Marimo. All rights reserved. */

import {
  previewSQLTableInfo,
  previewSQLTables,
  sendFunctionRequest,
} from "@/core/network/requests";
import type {
  FunctionCallResultMessage,
  SQLTableInfoPreview,
  SQLTablesPreview,
} from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import type {
  PreviewSQLTablesRequest,
  FunctionCallRequest,
  PreviewSQLTableInfoRequest,
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

export const PreviewSQLTables = new DeferredRequestRegistry<
  Omit<PreviewSQLTablesRequest, "requestId">,
  SQLTablesPreview
>("sql-tables-preview", async (requestId, req) => {
  await previewSQLTables({
    requestId: requestId,
    ...req,
  });
});

export const PreviewSQLTableInfo = new DeferredRequestRegistry<
  Omit<PreviewSQLTableInfoRequest, "requestId">,
  SQLTableInfoPreview
>("sql-table-info-preview", async (requestId, req) => {
  await previewSQLTableInfo({
    requestId: requestId,
    ...req,
  });
});
