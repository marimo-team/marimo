/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import { TablePanel } from "../charts";
import { getChartDefaults } from "../schemas";
import { getChartTabName, tabsStorageAtom } from "../storage";
import { ChartType } from "../types";

const chartModule = vi.hoisted(() => ({
  requested: vi.fn(),
  ready: Promise.withResolvers<undefined>(),
}));

vi.mock("../chart-panel", async () => {
  chartModule.requested();
  await chartModule.ready.promise;
  return { ChartPanel: () => <div>Chart editor</div> };
});

it("preloads charts on hover without replacing the table and keeps tabs usable while loading", async () => {
  const store = createStore();
  const cellId = CellId.create();
  const tabName = getChartTabName(0, ChartType.BAR);
  store.set(
    tabsStorageAtom,
    new Map([
      [
        cellId,
        [{ tabName, chartType: ChartType.BAR, config: getChartDefaults() }],
      ],
    ]),
  );

  render(
    <Provider store={store}>
      <TablePanel
        cellId={cellId}
        data={[]}
        dataTable={<input aria-label="Table filter" />}
        fieldTypes={[]}
        totalRows={0}
        columns={0}
        displayHeader={true}
      />
    </Provider>,
  );

  const filter = screen.getByRole("textbox", { name: "Table filter" });
  fireEvent.change(filter, { target: { value: "keep me" } });
  expect(chartModule.requested).not.toHaveBeenCalled();

  const chartTab = screen.getByRole("tab", { name: tabName });
  fireEvent.mouseEnter(chartTab);
  await waitFor(() => expect(chartModule.requested).toHaveBeenCalledOnce());
  expect(screen.getByRole("textbox", { name: "Table filter" })).toBe(filter);
  expect(filter).toHaveValue("keep me");

  fireEvent.click(chartTab);
  expect(await screen.findByText("Loading chart...")).toBeVisible();
  fireEvent.click(screen.getByRole("tab", { name: "Table" }));
  expect(screen.getByRole("textbox", { name: "Table filter" })).toBeVisible();

  await act(async () => chartModule.ready.resolve(undefined));
  fireEvent.click(chartTab);
  expect(await screen.findByText("Chart editor")).toBeVisible();
  expect(chartModule.requested).toHaveBeenCalledOnce();
});
