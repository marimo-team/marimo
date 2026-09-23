/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { SetStateAction } from "react";
import type { EnvironmentOperation } from "@/core/alerts/environment";
import { alertAtom } from "@/core/alerts/state";
import type { SandboxResponse } from "@/core/network/types";
import { assertNever } from "@/utils/assertNever";

export const sandboxAtom = atom<SandboxResponse | null>(null);

export const preparationAtom = atom((get) =>
  get(alertAtom).environments.kernel.operations.findLast(
    (operation) => operation.action === "prepare",
  ),
);

interface SandboxSyncState {
  pending: boolean;
  error: string | null;
}

const sandboxSyncOperationAtom = atom((get) => {
  const operations = get(alertAtom).environments.kernel.operations;
  return (
    operations.findLast(
      (operation) =>
        operation.action === "sync" && operation.status.kind === "running",
    ) ?? operations.findLast((operation) => operation.action === "sync")
  );
});

const sandboxSyncRequestAtom = atom<{
  state: SandboxSyncState;
  operation: EnvironmentOperation | undefined;
} | null>(null);

export const sandboxSyncAtom = atom(
  (get): SandboxSyncState => {
    const operation = get(sandboxSyncOperationAtom);
    const request = get(sandboxSyncRequestAtom);
    // Local request status lasts until newer progress arrives from the server.
    if (
      request &&
      request.operation === operation &&
      operation?.status.kind !== "running"
    ) {
      return request.state;
    }
    const status = operation?.status;
    switch (status?.kind) {
      case "running":
        return { pending: true, error: null };
      case "failed":
        return { pending: false, error: status.error };
      case "restart-required":
        return { pending: false, error: status.reason };
      case "cancelled":
        return { pending: false, error: "Sandbox sync was interrupted." };
      case "succeeded":
      case undefined:
        return { pending: false, error: null };
      default:
        return assertNever(status);
    }
  },
  (get, set, update: SetStateAction<SandboxSyncState>) => {
    set(sandboxSyncRequestAtom, {
      state:
        typeof update === "function" ? update(get(sandboxSyncAtom)) : update,
      operation: get(sandboxSyncOperationAtom),
    });
  },
);
export const sandboxActionsAtom = atom<{
  sync: () => Promise<boolean>;
  editManifest: () => Promise<void>;
} | null>(null);
