/* Copyright 2026 Marimo. All rights reserved. */

import type {
  ListPackagesResult,
  PackagesDependencyTreeResult,
} from "../kernel/messages";
import { DeferredRequestRegistry } from "../network/DeferredRequestRegistry";
import { getRequestClient } from "../network/requests";

/**
 * Registry for list packages requests.
 *
 * Sends request via HTTP, receives response via WebSocket notification.
 * Uses kernel's Python environment instead of server's.
 */
export const PACKAGES_REGISTRY = new DeferredRequestRegistry<
  {},
  ListPackagesResult
>("list-packages-result", async (requestId, _req) => {
  const client = getRequestClient();
  await client.kernelListPackages({
    requestId: requestId,
  });
});

/**
 * Registry for dependency tree requests.
 *
 * Sends request via HTTP, receives response via WebSocket notification.
 * Uses kernel's Python environment instead of server's.
 */
export const DEPENDENCY_TREE_REGISTRY = new DeferredRequestRegistry<
  { filename?: string },
  PackagesDependencyTreeResult
>("packages-dependency-tree-result", async (requestId, req) => {
  const client = getRequestClient();
  await client.kernelPackagesTree({
    requestId: requestId,
    ...req,
  });
});
