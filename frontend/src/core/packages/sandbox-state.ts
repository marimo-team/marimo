/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { EnvironmentOperation } from "@/core/alerts/environment";
import { alertAtom } from "@/core/alerts/state";
import type { SandboxResponse } from "@/core/network/types";

export const sandboxAtom = atom<SandboxResponse | null>(null);

export const preparationAtom = atom((get) =>
  get(alertAtom).environments.kernel.operations.findLast(
    (operation) => operation.action === "prepare",
  ),
);

type SandboxSyncState = EnvironmentOperation["status"] | { kind: "idle" };

export const sandboxSyncOperationAtom = atom((get) => {
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
    const state: SandboxSyncState =
      request &&
      request.operation === operation &&
      operation?.status.kind !== "running"
        ? request.state
        : (operation?.status ?? { kind: "idle" });
    // Later package operations can replace the sync result, but only a new
    // environment snapshot can clear an outstanding restart.
    if (
      get(alertAtom).environments.kernel.restart_required &&
      (state.kind === "idle" || state.kind === "succeeded")
    ) {
      return {
        kind: "restart-required",
        reason:
          "Dependency changes are saved; restart the kernel to apply them.",
      };
    }
    return state;
  },
  (get, set, state: SandboxSyncState) => {
    set(sandboxSyncRequestAtom, {
      state,
      operation: get(sandboxSyncOperationAtom),
    });
  },
);
export const sandboxActionsAtom = atom<{
  sync: () => Promise<boolean>;
  editManifest: () => Promise<void>;
} | null>(null);
