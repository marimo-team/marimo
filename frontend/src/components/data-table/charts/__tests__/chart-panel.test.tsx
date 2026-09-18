/* Copyright 2026 Marimo. All rights reserved. */

import { render, waitFor } from "@testing-library/react";
import { Tooltip } from "radix-ui";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { LazyVegaEmbed } from "@/components/charts/lazy";
import { vegaLoader } from "@/plugins/impl/vega/loader";
import { ChartPanel } from "../charts";
import { ChartType, NONE_VALUE } from "../types";

vi.mock("@/components/charts/lazy", () => ({
  LazyVegaEmbed: vi.fn(() => null),
}));

beforeAll(() => {
  SetupMocks.resizeObserver();
});

describe("ChartPanel", () => {
  it("keeps dotted CSV columns aligned with the chart encodings", async () => {
    vi.spyOn(vegaLoader, "load").mockResolvedValue("a.b,n\n1,1\n2,2\n3,3\n");

    render(
      <Tooltip.Provider>
        <ChartPanel
          tableData={[{ "a.b": 1, n: 1 }]}
          chartConfig={{
            general: {
              xColumn: { field: "a.b", type: "number" },
              yColumn: {
                field: "n",
                type: "number",
                aggregate: NONE_VALUE,
              },
            },
          }}
          chartType={ChartType.BAR}
          saveChart={vi.fn()}
          saveChartType={vi.fn()}
          getDataUrl={vi.fn().mockResolvedValue({
            data_url: "chart.csv",
            format: "csv",
          })}
          fieldTypes={[
            ["a.b", ["number", "float64"]],
            ["n", ["integer", "int64"]],
          ]}
          isLargeDataset={false}
        />
      </Tooltip.Provider>,
    );

    await waitFor(() => {
      expect(vi.mocked(LazyVegaEmbed).mock.lastCall?.[0].spec).toEqual(
        expect.objectContaining({
          data: {
            values: [
              { "a.b": 1, n: 1 },
              { "a.b": 2, n: 2 },
              { "a.b": 3, n: 3 },
            ],
          },
          encoding: expect.objectContaining({
            x: expect.objectContaining({ field: "a\\.b" }),
            y: expect.objectContaining({ field: "n" }),
          }),
        }),
      );
    });
  });
});
