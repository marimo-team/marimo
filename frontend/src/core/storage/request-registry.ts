/* Copyright 2026 Marimo. All rights reserved. */

import type { NotificationMessageData } from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { getRequestClient } from "../network/requests";
import type {
  StorageDownloadRequest,
  StorageListEntriesRequest,
} from "../network/types";

export type StorageEntriesResult = NotificationMessageData<"storage-entries">;

export type StorageDownloadReadyResult =
  NotificationMessageData<"storage-download-ready">;

export const ListStorageEntries = new DeferredRequestRegistry<
  Omit<StorageListEntriesRequest, "requestId">,
  StorageEntriesResult
>("storage-list-entries", async (requestId, req) => {
  const client = getRequestClient();
  await client.listStorageEntries({
    requestId: requestId,
    ...req,
  });
});

export const DownloadStorage = new DeferredRequestRegistry<
  Omit<StorageDownloadRequest, "requestId">,
  StorageDownloadReadyResult
>("storage-download", async (requestId, req) => {
  const client = getRequestClient();
  await client.downloadStorage({
    requestId: requestId,
    ...req,
  });
});
