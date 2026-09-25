/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import { TablePanel } from "../charts";
import { getChartDefaults } from "../schemas";
import { getChartTabName, tabsStorageAtom } from "../storage";
import { ChartType } from "../types";

vi.mock("../chart-panel", () => ({
  ChartPanel: () => <div>Chart editor</div>,
}));

vi.mock("@/utils/lazy", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/utils/lazy")>();
  return {
    reactLazyWithPreload: (
      factory: Parameters<typeof actual.reactLazyWithPreload>[0],
    ) =>
      actual.reactLazyWithPreload(
        vi
          .fn(factory)
          .mockRejectedValueOnce(new Error("Chunk download failed")),
      ),
  };
});

it("keeps table tabs usable after a chunk failure and retries the chart", async () => {
  // React reports errors caught by an error boundary to the console.
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => {
    // Expected chunk download failure is caught by the chart boundary.
  });
  const store = createStore();
  const cellId = CellId.create();
  const tabName = getChartTabName(0, ChartType.BAR);
  store.set(
    tabsStorageAtom,
    new Map([
      [
        cellId,
        [
          {
            tabName,
            chartType: ChartType.BAR,
            config: getChartDefaults(),
          },
        ],
      ],
    ]),
  );

  render(
    <Provider store={store}>
      <TablePanel
        cellId={cellId}
        data={[]}
        dataTable={<div>Table data</div>}
        fieldTypes={[]}
        totalRows={0}
        columns={0}
        displayHeader={true}
      />
    </Provider>,
  );

  fireEvent.click(screen.getByRole("tab", { name: tabName }));
  expect(await screen.findByText("Could not load the chart.")).toBeVisible();
  expect(screen.getByRole("tab", { name: "Table" })).toBeVisible();
  fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
  expect(await screen.findByText("Chart editor")).toBeVisible();
  fireEvent.click(screen.getByRole("tab", { name: "Table" }));
  expect(screen.getByText("Table data")).toBeVisible();
  consoleError.mockRestore();
});
