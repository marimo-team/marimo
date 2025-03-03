/* Copyright 2024 Marimo. All rights reserved. */

import {
  previewSQLTable,
  previewSQLTableList,
  sendFunctionRequest,
} from "@/core/network/requests";
import type {
  FunctionCallResultMessage,
  SQLTableListPreview,
  SQLTablePreview,
} from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import type {
  FunctionCallRequest,
  PreviewSQLTableListRequest,
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

// We make a request to the backend to preview the table, passing in Engine, DB, Schema, and Table
// The backend returns data tables, which could also exist in other engines, dbs, schemas
// Thus, we use the request ID pattern to match the response to the request
export const PreviewSQLTable = new DeferredRequestRegistry<
  Omit<PreviewSQLTableRequest, "requestId">,
  SQLTablePreview
>("sql-table-preview", async (requestId, req) => {
  await previewSQLTable({
    requestId: requestId,
    ...req,
  });
});

export const PreviewSQLTableList = new DeferredRequestRegistry<
  Omit<PreviewSQLTableListRequest, "requestId">,
  SQLTableListPreview
>("sql-table-list-preview", async (requestId, req) => {
  await previewSQLTableList({
    requestId: requestId,
    ...req,
  });
});
