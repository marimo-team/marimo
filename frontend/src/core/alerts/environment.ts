/* Copyright 2026 Marimo. All rights reserved. */

import type { NotificationMessageData, schemas } from "@/core/kernel/messages";

export type EnvironmentState = schemas["EnvironmentState"];
export type EnvironmentOperation = schemas["EnvironmentOperation"];
export type EnvironmentSource = EnvironmentOperation["source"];

export function emptyEnvironmentState(): EnvironmentState {
  return { restart_required: false, operations: [] };
}

/** Apply a live delta after the connection's authoritative snapshot. */
export function reduceEnvironmentState(
  state: EnvironmentState,
  update: NotificationMessageData<"environment-operation">,
): EnvironmentState {
  const previous = state.operations.find(
    (operation) => operation.operation_id === update.operation_id,
  );
  const logs = { ...previous?.logs };
  for (const [name, content] of Object.entries(update.logs)) {
    logs[name] =
      update.log_mode === "replace" ? content : (logs[name] ?? "") + content;
  }

  const operation: EnvironmentOperation = {
    operation_id: update.operation_id,
    action: update.action,
    status: update.status,
    packages: update.packages,
    logs,
    source: update.source,
  };
  const operations = state.operations.filter(
    (item) =>
      (previous && update.status.kind === "running") ||
      item.status.kind === "running",
  );
  const index = operations.findIndex(
    (item) => item.operation_id === update.operation_id,
  );
  if (index === -1) {
    operations.push(operation);
  } else {
    operations[index] = operation;
  }

  return {
    restart_required:
      state.restart_required ||
      update.status.kind === "restart-required" ||
      Object.values(update.packages).includes("restart-required"),
    operations,
  };
}
