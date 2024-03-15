/* Copyright 2024 Marimo. All rights reserved. */

import { createReducer } from "@/utils/createReducer";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { useMemo } from "react";

interface PackageAlert {
  id: string;
  packages: string[];
}

/** * Alerts with actions.
 *
 * Right now we only have one type of alert, for missing packages
 * with an option to install them; at most one such alert is ever stored.
 *
 * If in the future we have other kinds of alerts, we can generalize
 * this interface.
 */
interface PackageAlertState {
  alert: PackageAlert | null;
}

const { reducer, createActions } = createReducer(
  () => ({ alert: null }) as PackageAlertState,
  {
    addAlert: (state, alert: PackageAlert) => {
      return { alert: alert };
    },
    clearAlert: () => {
      return { alert: null };
    },
  }
);

const packageAlertAtom = atom<PackageAlertState>({ alert: null });

/**
 * React hook to get the Alert state.
 */
export const usePackageAlert = () => useAtomValue(packageAlertAtom);

/**
 * React hook to get the Alerts actions.
 */
export function usePackageAlertActions() {
  const setState = useSetAtom(packageAlertAtom);
  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
}
