/* Copyright 2024 Marimo. All rights reserved. */

import { PackageInstallationStatus } from "@/core/kernel/messages";
import { createReducer } from "@/utils/createReducer";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { useMemo } from "react";

export interface MissingPackageAlert {
  id: string;
  kind: "missing";
  packages: string[];
  isolated: boolean;
}

export interface InstallingPackageAlert {
  id: string;
  kind: "installing";
  packages: PackageInstallationStatus;
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
  packageAlert: MissingPackageAlert | InstallingPackageAlert | null;
}

const { reducer, createActions } = createReducer(
  () => ({ packageAlert: null }) as AlertState,
  {
    addPackageAlert: (
      state,
      alert: MissingPackageAlert | InstallingPackageAlert,
    ) => {
      return {
        ...state,
        packageAlert: alert,
      };
    },

    clearPackageAlert: (state, id: string) => {
      return state.packageAlert !== null && state.packageAlert.id === id
        ? { ...state, packageAlert: null }
        : state;
    },
  },
);

const alertAtom = atom<AlertState>({
  packageAlert: null,
});

/**
 * React hook to get the Alert state.
 */
export const useAlerts = () => useAtomValue(alertAtom);

/**
 * React hook to get the Alerts actions.
 */
export function useAlertActions() {
  const setState = useSetAtom(alertAtom);
  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
}
