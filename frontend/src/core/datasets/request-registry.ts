/* Copyright 2024 Marimo. All rights reserved. */
import type { SQLTableListPreview, SQLTablePreview } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { getRequestClient } from "../network/requests";
import type {
  PreviewSQLTableListRequest,
  PreviewSQLTableRequest,
} from "../network/types";

// We make a request to the backend to preview the table, passing in Engine, DB, Schema, and Table
// The backend returns data tables, which could also exist in other engines, dbs, schemas
// Thus, we use the request ID pattern to match the response to the request

export const PreviewSQLTable = new DeferredRequestRegistry<
  Omit<PreviewSQLTableRequest, "requestId">,
  SQLTablePreview
>("sql-table-preview", async (requestId, req) => {
  const client = getRequestClient();
  await client.previewSQLTable({
    requestId: requestId,
    ...req,
  });
});

export const PreviewSQLTableList = new DeferredRequestRegistry<
  Omit<PreviewSQLTableListRequest, "requestId">,
  SQLTableListPreview
>("sql-table-list-preview", async (requestId, req) => {
  const client = getRequestClient();
  await client.previewSQLTableList({
    requestId: requestId,
    ...req,
  });
});
