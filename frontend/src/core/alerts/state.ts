/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { NotificationMessageData } from "@/core/kernel/messages";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { generateUUID } from "@/utils/uuid";
import {
  emptyEnvironmentState,
  type EnvironmentOperation,
  type EnvironmentSource,
  type EnvironmentState,
  reduceEnvironmentState,
} from "./environment";

type Identified<T> = { id: string } & T;

export interface MissingPackageAlert {
  kind: "missing";
  packages: string[];
  isolated: boolean;
  source?: "kernel" | "server";
}

export interface EnvironmentOperationAlert extends EnvironmentOperation {
  action: "install" | "remove";
  kind: "environment";
  restartRequired: boolean;
}

function isPackageOperation(
  operation: EnvironmentOperation,
): operation is EnvironmentOperation & {
  action: EnvironmentOperationAlert["action"];
} {
  return operation.action === "install" || operation.action === "remove";
}

export interface StartupLogsAlert {
  content: string;
  status: "append" | "start" | "done";
}

export function isMissingPackageAlert(
  alert: MissingPackageAlert | EnvironmentOperationAlert,
): alert is MissingPackageAlert {
  return alert.kind === "missing";
}

export function isEnvironmentOperationAlert(
  alert: MissingPackageAlert | EnvironmentOperationAlert,
): alert is EnvironmentOperationAlert {
  return alert.kind === "environment";
}

interface AlertState {
  packageAlert:
    | Identified<MissingPackageAlert>
    | { kind: "environment"; id: string; source: EnvironmentSource }
    | null;
  environments: Record<EnvironmentSource, EnvironmentState>;
  startupLogsAlert: StartupLogsAlert | null;
}

function setEnvironment(
  state: AlertState,
  source: EnvironmentSource,
  environment: EnvironmentState,
): AlertState {
  // Sandbox preparation and sync use the existing sandbox UI.
  const environments = { ...state.environments, [source]: environment };
  const operations = Object.values(environments)
    .flatMap((item) => item.operations)
    .filter(isPackageOperation);
  const incoming = environment.operations.filter(isPackageOperation);
  const alert = state.packageAlert;
  const selected =
    alert?.kind === "environment"
      ? operations.find(
          (item) =>
            item.operation_id === alert.id && item.source === alert.source,
        )
      : undefined;
  // A snapshot restores work and unresolved issues, not old success banners.
  const needsAttention = (operation: EnvironmentOperation) =>
    operation.status.kind !== "succeeded" ||
    environments[operation.source].restart_required;
  const operation =
    (selected?.status.kind === "running" ? selected : undefined) ??
    incoming.findLast((item) => item.status.kind === "running") ??
    operations.findLast((item) => item.status.kind === "running") ??
    selected ??
    incoming.findLast(needsAttention) ??
    operations.findLast(needsAttention);
  return {
    ...state,
    environments,
    packageAlert: operation
      ? {
          kind: "environment",
          id: operation.operation_id,
          source: operation.source,
        }
      : state.packageAlert?.kind === "missing"
        ? state.packageAlert
        : null,
  };
}

export const { valueAtom: alertAtom, useActions: useAlertActions } =
  createReducerAndAtoms(
    (): AlertState => ({
      packageAlert: null,
      startupLogsAlert: null,
      environments: {
        kernel: emptyEnvironmentState(),
        server: emptyEnvironmentState(),
      },
    }),
    {
      addMissingPackageAlert: (state, alert: MissingPackageAlert) => ({
        ...state,
        packageAlert: { id: generateUUID(), ...alert },
      }),

      updateEnvironment: (
        state,
        update: NotificationMessageData<"environment-operation">,
      ) => {
        const source = update.source;
        const environment = reduceEnvironmentState(
          state.environments[source],
          update,
        );
        if (!isPackageOperation(update)) {
          return {
            ...state,
            environments: { ...state.environments, [source]: environment },
          };
        }
        return setEnvironment(
          {
            ...state,
            packageAlert: {
              kind: "environment",
              id: update.operation_id,
              source,
            },
          },
          source,
          environment,
        );
      },

      setEnvironment: (
        state,
        snapshot: NotificationMessageData<"environment-state">,
      ) => setEnvironment(state, snapshot.source, snapshot.state),

      clearPackageAlert: (state, id: string) =>
        state.packageAlert?.id === id
          ? { ...state, packageAlert: null }
          : state,

      addStartupLog: (
        state,
        logData: { content: string; status: "append" | "start" | "done" },
      ) => ({
        ...state,
        startupLogsAlert: {
          content: (state.startupLogsAlert?.content ?? "") + logData.content,
          status: logData.status,
        },
      }),

      clearStartupLogsAlert: (state) => ({ ...state, startupLogsAlert: null }),
    },
  );

export function getPackageAlert(
  state: AlertState,
): Identified<MissingPackageAlert | EnvironmentOperationAlert> | null {
  const alert = state.packageAlert;
  if (alert?.kind !== "environment") {
    return alert;
  }
  const environment = state.environments[alert.source];
  const operation = environment.operations.find(
    (item) => item.operation_id === alert.id,
  );
  return operation && isPackageOperation(operation)
    ? { ...operation, ...alert, restartRequired: environment.restart_required }
    : null;
}

export function useAlerts() {
  const state = useAtomValue(alertAtom);
  return {
    packageAlert: getPackageAlert(state),
    startupLogsAlert: state.startupLogsAlert,
  };
}
