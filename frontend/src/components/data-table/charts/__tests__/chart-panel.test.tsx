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
  it("uses column types to parse numeric CSV values without coercing text", async () => {
    vi.spyOn(vegaLoader, "load").mockResolvedValue(
      "a.b,n,label,day,timestamp,active,duration\ninf,1,inf,2024-01-01,2024-01-01T12:00:00Z,True,1 days\n-inf,2,001,2024-01-02,2024-01-02T12:00:00Z,False,2 days\n2.5,3,2024-01-03,2024-01-03,2024-01-03T12:00:00Z,True,3 days\n,4,,,,,\n",
    );

    render(
      <Tooltip.Provider>
        <ChartPanel
          tableData={[{ "a.b": 1, n: 1 }]}
          chartConfig={{
            general: {
              xColumn: { field: "a.b", type: "number" },
              yColumn: { field: "n", type: "integer", aggregate: NONE_VALUE },
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
            ["label", ["string", "object"]],
            ["day", ["date", "date"]],
            ["timestamp", ["datetime", "datetime64[ns]"]],
            ["active", ["boolean", "bool"]],
            ["duration", ["unknown", "timedelta64[ns]"]],
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
              {
                "a.b": Infinity,
                n: 1,
                label: "inf",
                day: new Date("2024-01-01"),
                timestamp: new Date("2024-01-01T12:00:00Z"),
                active: true,
                duration: "1 days",
              },
              {
                "a.b": -Infinity,
                n: 2,
                label: "001",
                day: new Date("2024-01-02"),
                timestamp: new Date("2024-01-02T12:00:00Z"),
                active: false,
                duration: "2 days",
              },
              {
                "a.b": 2.5,
                n: 3,
                label: "2024-01-03",
                day: new Date("2024-01-03"),
                timestamp: new Date("2024-01-03T12:00:00Z"),
                active: true,
                duration: "3 days",
              },
              {
                "a.b": null,
                n: 4,
                label: null,
                day: "",
                timestamp: "",
                active: null,
                duration: "",
              },
            ],
          },
        }),
      );
    });
  });

  it.each([true, false])(
    "keeps dotted CSV columns aligned with the chart encodings (schema: %s)",
    async (hasSchema) => {
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
            fieldTypes={
              hasSchema
                ? [
                    ["a.b", ["number", "float64"]],
                    ["n", ["integer", "int64"]],
                  ]
                : undefined
            }
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
    },
  );
});
