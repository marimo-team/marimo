/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it } from "vitest";
import type { EnvironmentOperation } from "../environment";
import { alertAtom, getPackageAlert, useAlertActions } from "../state";

it.each(["kernel", "server"] as const)(
  "preserves the selected %s result across snapshots and follows new work",
  (source) => {
    const store = createStore();
    const { result } = renderHook(() => useAlertActions(), {
      wrapper: ({ children }) => <Provider store={store}>{children}</Provider>,
    });
    const selected: EnvironmentOperation = {
      operation_id: "selected",
      action: "install",
      source,
      status: { kind: "failed", error: "Network unavailable" },
      packages: { numpy: "failed" },
      logs: { numpy: "Selected logs\n" },
    };
    const other: EnvironmentOperation = {
      ...selected,
      operation_id: "other",
      source: source === "kernel" ? "server" : "kernel",
      status: { kind: "succeeded" },
      packages: { numpy: "succeeded" },
      logs: { numpy: "Other logs\n" },
    };
    const snapshot = (operation: EnvironmentOperation) =>
      result.current.setEnvironment({
        source: operation.source,
        state: { restart_required: false, operations: [operation] },
      });
    act(() => snapshot(selected));
    for (const operations of [
      [selected, other],
      [other, selected],
    ]) {
      act(() => operations.forEach(snapshot));
      expect(getPackageAlert(store.get(alertAtom))).toEqual({
        ...selected,
        id: selected.operation_id,
        kind: "environment",
        restartRequired: false,
      });
    }

    // Live work in the other environment should still take over the banner.
    const active: EnvironmentOperation = {
      ...other,
      operation_id: "new-work",
      status: { kind: "running" },
      packages: { numpy: "running" },
      logs: { numpy: "Installing\n" },
    };
    act(() =>
      result.current.updateEnvironment({ ...active, log_mode: "replace" }),
    );
    act(() => snapshot(selected));
    expect(getPackageAlert(store.get(alertAtom))?.id).toBe(active.operation_id);
    act(() =>
      result.current.updateEnvironment({
        ...active,
        status: { kind: "succeeded" },
        packages: { numpy: "succeeded" },
        logs: {},
        log_mode: "append",
      }),
    );
    act(() => snapshot(selected));
    expect(getPackageAlert(store.get(alertAtom))).toEqual({
      ...active,
      id: active.operation_id,
      kind: "environment",
      restartRequired: false,
      status: { kind: "succeeded" },
      packages: { numpy: "succeeded" },
    });

    // Replacing that environment with an empty snapshot removes its selection.
    act(() =>
      result.current.setEnvironment({
        source: active.source,
        state: { restart_required: false, operations: [] },
      }),
    );
    expect(getPackageAlert(store.get(alertAtom))?.id).toBe(
      selected.operation_id,
    );
    act(() =>
      result.current.updateEnvironment({
        ...other,
        operation_id: "latest-result",
        log_mode: "replace",
      }),
    );
    expect(getPackageAlert(store.get(alertAtom))?.id).toBe("latest-result");
  },
);
