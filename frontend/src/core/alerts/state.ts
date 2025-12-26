/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { PackageInstallationStatus } from "@/core/kernel/messages";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { generateUUID } from "@/utils/uuid";

type Identified<T> = { id: string } & T;

export interface MissingPackageAlert {
  kind: "missing";
  packages: string[];
  isolated: boolean;
}

export interface InstallingPackageAlert {
  kind: "installing";
  packages: PackageInstallationStatus;
  logs?: { [key: string]: string } | null;
  log_status?: "append" | "start" | "done" | null;
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

/** Prominent alerts.
 *
 * Right now we only have one type of alert.
 */
interface AlertState {
  packageAlert:
    | Identified<MissingPackageAlert>
    | Identified<InstallingPackageAlert>
    | null;
  startupLogsAlert: StartupLogsAlert | null;
  packageLogs: { [packageName: string]: string };
}

const { valueAtom: alertAtom, useActions } = createReducerAndAtoms(
  () =>
    ({
      packageAlert: null,
      startupLogsAlert: null,
      packageLogs: {},
    }) as AlertState,
  {
    addPackageAlert: (
      state,
      alert: MissingPackageAlert | InstallingPackageAlert,
    ) => {
      const newPackageLogs = { ...state.packageLogs };

      // Handle streaming logs for installing package alerts
      if (isInstallingPackageAlert(alert) && alert.logs && alert.log_status) {
        for (const [packageName, newContent] of Object.entries(alert.logs)) {
          switch (alert.log_status) {
            case "start":
              // Start new log for this package
              newPackageLogs[packageName] = newContent;

              break;

            case "append": {
              // Append to existing log
              const prevContent = newPackageLogs[packageName] || "";
              newPackageLogs[packageName] = prevContent + newContent;

              break;
            }
            case "done": {
              // Append final content and mark as done
              const prevContent = newPackageLogs[packageName] || "";
              newPackageLogs[packageName] = prevContent + newContent;

              break;
            }
            // No default
          }
        }
      }

      const existingAlert = state.packageAlert;
      const alertId = existingAlert?.id || generateUUID();

      return {
        ...state,
        packageAlert: { id: alertId, ...alert },
        packageLogs: newPackageLogs,
      };
    },

    clearPackageAlert: (state, id: string) => {
      return state.packageAlert !== null && state.packageAlert.id === id
        ? { ...state, packageAlert: null, packageLogs: {} }
        : state;
    },

    addStartupLog: (
      state,
      logData: { content: string; status: "append" | "start" | "done" },
    ) => {
      const prevContent = state.startupLogsAlert?.content || "";
      return {
        ...state,
        startupLogsAlert: {
          ...state.startupLogsAlert,
          content: prevContent + logData.content,
          status: logData.status,
        },
      };
    },

    clearStartupLogsAlert: (state) => {
      return { ...state, startupLogsAlert: null };
    },
  },
);

/**
 * React hook to get the Alert state.
 */
export const useAlerts = () => useAtomValue(alertAtom);

/**
 * React hook to get the Alerts actions.
 */
export function useAlertActions() {
  return useActions();
}
