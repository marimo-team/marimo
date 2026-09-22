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

export interface InstallingPackageAlert extends EnvironmentOperation {
  kind: "installing";
  restartRequired: boolean;
}

export interface StartupLogsAlert {
  content: string;
  status: "append" | "start" | "done";
}

export function isMissingPackageAlert(
  alert: MissingPackageAlert | InstallingPackageAlert,
): alert is MissingPackageAlert {
  return alert.kind === "missing";
}

export function isInstallingPackageAlert(
  alert: MissingPackageAlert | InstallingPackageAlert,
): alert is InstallingPackageAlert {
  return alert.kind === "installing";
}

interface AlertState {
  packageAlert:
    | Identified<MissingPackageAlert>
    | { kind: "installing"; id: string; source: EnvironmentSource }
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
  const operation =
    environment.operations.findLast((item) => item.status.kind === "running") ??
    operations.findLast((item) => item.status.kind === "running") ??
    environment.operations.at(-1) ??
    operations.at(-1);
  return {
    ...state,
    environments,
    packageAlert: operation
      ? {
          kind: "installing",
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
        update: NotificationMessageData<"installing-package-alert">,
      ) => {
        const source = update.source ?? "kernel";
        return setEnvironment(
          state,
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
): Identified<MissingPackageAlert | InstallingPackageAlert> | null {
  const alert = state.packageAlert;
  if (alert?.kind !== "installing") {
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
