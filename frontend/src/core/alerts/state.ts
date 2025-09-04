/* Copyright 2024 Marimo. All rights reserved. */

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
}

const { valueAtom: alertAtom, useActions } = createReducerAndAtoms(
  () => ({ packageAlert: null, startupLogsAlert: null }) as AlertState,
  {
    addPackageAlert: (
      state,
      alert: MissingPackageAlert | InstallingPackageAlert,
    ) => {
      return {
        ...state,
        packageAlert: { id: generateUUID(), ...alert },
      };
    },

    clearPackageAlert: (state, id: string) => {
      return state.packageAlert !== null && state.packageAlert.id === id
        ? { ...state, packageAlert: null }
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
