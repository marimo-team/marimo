/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { useController, useFormContext } from "react-hook-form";
import { afterEach, expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import { TablePanel } from "../charts";
import { getChartTabName, tabsStorageAtom } from "../storage";
import { ChartPanel } from "../chart-panel";
import { type ChartSchemaType, getChartDefaults } from "../schemas";
import { ChartType } from "../types";

vi.mock("../lazy-chart", () => ({
  LazyChart: () => <div>Rendered chart</div>,
}));

vi.mock("../forms/common-chart", () => ({
  CommonChartForm: () => {
    const form = useFormContext<ChartSchemaType>();
    const { field } = useController({
      control: form.control,
      name: "general.title",
    });
    return (
      <button
        type="button"
        onClick={() => {
          form.setValue("general.xColumn", { field: "x", type: "number" });
          form.setValue("color.range", ["#123456"]);
          form.setValue("xAxis.bin.binned", true);
          field.onChange("Updated chart");
        }}
      >
        Change chart controls
      </button>
    );
  },
  StyleForm: () => null,
}));

const tableData = [{ x: 1 }];
const defaultProps = {
  tableData,
  chartConfig: getChartDefaults(),
  chartType: ChartType.BAR,
  saveChart: vi.fn(),
  saveChartType: vi.fn(),
  isLargeDataset: false,
  totalRows: 1,
  columns: 1,
};

afterEach(() => {
  vi.useRealTimers();
});

it("requires approval when a mounted table becomes large or changes size", async () => {
  const getDataUrl = vi.fn().mockResolvedValue({ data_url: tableData });
  const { rerender } = render(
    <ChartPanel {...defaultProps} getDataUrl={getDataUrl} />,
  );
  await screen.findByText("Rendered chart");
  expect(getDataUrl).toHaveBeenCalledOnce();

  const largeProps = {
    ...defaultProps,
    getDataUrl,
    isLargeDataset: true,
    totalRows: 60_000,
  };
  rerender(<ChartPanel {...largeProps} />);
  await screen.findByRole("button", { name: "Proceed" });
  expect(getDataUrl).toHaveBeenCalledOnce();
  expect(screen.queryByText("Rendered chart")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
  await waitFor(() => expect(getDataUrl).toHaveBeenCalledTimes(2));

  // A fresh page with the same dimensions should retain approval.
  rerender(<ChartPanel {...largeProps} tableData={[{ x: 2 }]} />);
  await screen.findByText("Rendered chart");
  await waitFor(() => expect(getDataUrl).toHaveBeenCalledTimes(3));

  rerender(<ChartPanel {...largeProps} columns={2} />);
  await screen.findByRole("button", { name: "Proceed" });
  expect(getDataUrl).toHaveBeenCalledTimes(3);

  rerender(<ChartPanel {...defaultProps} getDataUrl={getDataUrl} />);
  await screen.findByText("Rendered chart");
  await waitFor(() => expect(getDataUrl).toHaveBeenCalledTimes(4));

  rerender(<ChartPanel {...largeProps} />);
  await screen.findByRole("button", { name: "Proceed" });
  expect(getDataUrl).toHaveBeenCalledTimes(4);
});

it("saves programmatic and custom control changes after the debounce", async () => {
  vi.useFakeTimers();
  const saveChart = vi.fn();
  render(<ChartPanel {...defaultProps} saveChart={saveChart} />);
  fireEvent.click(
    screen.getByRole("button", { name: "Change chart controls" }),
  );
  expect(saveChart).not.toHaveBeenCalled();
  await act(() => vi.advanceTimersByTimeAsync(300));
  expect(saveChart).toHaveBeenCalledOnce();
  expect(saveChart).toHaveBeenCalledWith(
    expect.objectContaining({
      general: expect.objectContaining({
        xColumn: { field: "x", type: "number" },
        title: "Updated chart",
      }),
      color: expect.objectContaining({ range: ["#123456"] }),
      xAxis: { bin: { binned: true } },
    }),
  );
});

it("flushes pending changes when the chart panel unmounts", async () => {
  vi.useFakeTimers();
  const saveChart = vi.fn();
  const { unmount } = render(
    <ChartPanel {...defaultProps} saveChart={saveChart} />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Change chart controls" }),
  );
  unmount();
  expect(saveChart).toHaveBeenCalledOnce();
  expect(saveChart.mock.lastCall?.[0].general.title).toBe("Updated chart");
  await act(() => vi.advanceTimersByTimeAsync(300));
  expect(saveChart).toHaveBeenCalledOnce();
});

it("keeps edits across tab switches without restoring a deleted chart", async () => {
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
        data={tableData}
        dataTable={<div>Table data</div>}
        totalRows={1}
        columns={1}
        fieldTypes={[]}
        displayHeader={true}
      />
    </Provider>,
  );
  fireEvent.click(screen.getByRole("tab", { name: tabName }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Change chart controls" }),
  );
  fireEvent.click(screen.getByRole("tab", { name: "Table" }));
  expect(
    store.get(tabsStorageAtom).get(cellId)?.[0].config.general?.title,
  ).toBe("Updated chart");

  const chartTab = screen.getByRole("tab", { name: tabName });
  fireEvent.click(chartTab);
  fireEvent.click(
    await screen.findByRole("button", { name: "Change chart controls" }),
  );
  const deleteIcon = chartTab.querySelector("svg");
  expect(deleteIcon).not.toBeNull();
  fireEvent.click(deleteIcon!);
  expect(store.get(tabsStorageAtom).get(cellId)).toEqual([]);
});
