/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps, FC, PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { invariant } from "@/utils/invariant";
import { DataFrameComponent } from "../DataFramePlugin";
import type { TransformPanel } from "../panel";
import { type Transformations, TransformationsSchema } from "../schema";

const { panel } = vi.hoisted(() => ({
  panel: vi.fn<FC<ComponentProps<typeof TransformPanel>>>(),
}));

vi.mock("../panel", () => ({ TransformPanel: panel }));
vi.mock("../../DataTablePlugin", () => ({
  TableProviders: ({ children }: PropsWithChildren) => children,
  LoadingDataTableComponent: ({
    data,
    totalRows,
  }: {
    data: string;
    totalRows: number;
  }) => (
    <div data-testid="table">
      {data}: {totalRows} rows
    </div>
  ),
}));
vi.mock("@/components/editor/code/readonly-python-code", () => ({
  ReadonlyCode: () => null,
}));

type Props = ComponentProps<typeof DataFrameComponent>;
const RESPONSE: Awaited<ReturnType<Props["get_dataframe"]>> = {
  url: "table.json",
  total_rows: 3,
  row_headers: [],
  field_types: [],
  column_types_per_step: [],
};
const EMPTY: Transformations = { transforms: [] };
const BAD = TransformationsSchema.parse({
  transforms: [{ type: "sample_rows", n: 4 }],
});

function panelProps() {
  const call = panel.mock.lastCall;
  invariant(call, "Expected the transform panel to render");
  return call[0];
}

function props(value: Transformations = EMPTY): Props {
  return {
    columns: new Map(),
    pageSize: 5,
    showDownload: false,
    lazy: false,
    value,
    setValue: vi.fn(),
    host: document.createElement("div"),
    get_dataframe: vi.fn().mockResolvedValue(RESPONSE),
    get_column_values: vi.fn(),
    search: vi.fn(),
    download_as: vi.fn(),
    get_size_bytes: vi.fn(),
  };
}

beforeEach(() => {
  panel.mockReset();
  panel.mockReturnValue(null);
});

describe("dataframe value ownership", () => {
  it("does not send a pending draft when a data request finishes", async () => {
    const response = new Deferred<typeof RESPONSE>();
    const initialProps = { ...props(), get_dataframe: () => response.promise };
    render(<DataFrameComponent {...initialProps} />);
    const pending: Transformations = {
      transforms: [
        {
          type: "group_by",
          column_ids: [],
          aggregation_column_ids: [],
          aggregation: "count",
          drop_na: false,
        },
      ],
    };
    act(() => panelProps().onInvalidChange(pending));
    await act(async () => response.resolve(RESPONSE));
    expect(panelProps().initialValue).toEqual(pending);
    expect(initialProps.setValue).not.toHaveBeenCalled();
  });

  it("replaces an internal draft even when the valid value equals the plugin value", async () => {
    const initialProps = props();
    render(<DataFrameComponent {...initialProps} />);
    await screen.findByText("table.json: 3 rows");
    act(() => panelProps().onInvalidChange(BAD));
    act(() => panelProps().onChange(EMPTY));
    expect(panelProps().initialValue).toEqual(EMPTY);
    expect(initialProps.setValue).not.toHaveBeenCalled();
  });

  it("sends an identical payload once before the parent acknowledges it", async () => {
    const initialProps = props();
    render(<DataFrameComponent {...initialProps} />);
    await screen.findByText("table.json: 3 rows");
    act(() => {
      panelProps().onChange(BAD);
      panelProps().onChange(structuredClone(BAD));
    });
    expect(initialProps.setValue).toHaveBeenCalledExactlyOnceWith(BAD);
  });

  it("sends empty transforms when the user deletes a replayed bad step", async () => {
    const initialProps = props(BAD);
    render(<DataFrameComponent {...initialProps} />);
    await screen.findByText("table.json: 3 rows");
    act(() => panelProps().onChange(EMPTY));
    expect(initialProps.setValue).toHaveBeenCalledExactlyOnceWith(EMPTY);
  });

  it("permits a user submission after an external value reset", async () => {
    const initialProps = props(BAD);
    const { rerender } = render(<DataFrameComponent {...initialProps} />);
    await screen.findByText("table.json: 3 rows");
    rerender(<DataFrameComponent {...initialProps} value={EMPTY} />);
    expect(initialProps.setValue).not.toHaveBeenCalled();
    act(() => panelProps().onChange(BAD));
    expect(initialProps.setValue).toHaveBeenCalledExactlyOnceWith(BAD);
  });
});

it.each(["rpc", "transform"])(
  "keeps one %s error banner and the previous table through retries, then clears the error",
  async (kind) => {
    const error = new Error("Step 1 (Sample Rows): dataframe contains 3 rows");
    const retry = new Deferred<typeof RESPONSE>();
    const get_dataframe = vi
      .fn<Props["get_dataframe"]>()
      .mockResolvedValueOnce(RESPONSE);
    if (kind === "rpc") {
      get_dataframe.mockRejectedValueOnce(error);
    } else {
      get_dataframe.mockResolvedValueOnce({ error: error.message });
    }
    get_dataframe.mockReturnValueOnce(retry.promise);
    const initialProps = { ...props(), get_dataframe };
    const { rerender } = render(<DataFrameComponent {...initialProps} />);
    await screen.findByText("table.json: 3 rows");
    rerender(<DataFrameComponent {...initialProps} value={BAD} />);
    await screen.findByText(error.message);
    expect(screen.getAllByText(error.message)).toHaveLength(1);
    expect(screen.getByTestId("table")).toHaveTextContent("table.json: 3 rows");

    rerender(<DataFrameComponent {...initialProps} value={EMPTY} />);
    await waitFor(() => expect(get_dataframe).toHaveBeenCalledTimes(3));
    expect(screen.getAllByText(error.message)).toHaveLength(1);
    expect(screen.getByTestId("table")).toHaveTextContent("table.json: 3 rows");
    await act(async () =>
      retry.resolve({ ...RESPONSE, url: "recovered.json" }),
    );
    expect(screen.queryByText(error.message)).not.toBeInTheDocument();
    expect(screen.getByTestId("table")).toHaveTextContent(
      "recovered.json: 3 rows",
    );
  },
);
