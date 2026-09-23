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
  kind: "environment";
  restartRequired: boolean;
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
  // The banner shows active work first; logs stay scoped to each operation.
  const environments = { ...state.environments, [source]: environment };
  const operations = Object.values(environments).flatMap(
    (item) => item.operations,
  );
  const alert = state.packageAlert;
  const selected =
    alert?.kind === "environment"
      ? operations.find(
          (item) =>
            item.operation_id === alert.id && item.source === alert.source,
        )
      : undefined;
  const operation =
    (selected?.status.kind === "running" ? selected : undefined) ??
    environment.operations.findLast((item) => item.status.kind === "running") ??
    operations.findLast((item) => item.status.kind === "running") ??
    selected ??
    environment.operations.at(-1) ??
    operations.at(-1);
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
          reduceEnvironmentState(state.environments[source], update),
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
  return operation
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
