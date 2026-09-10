/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { getDefaults, getUnionLiteral } from "@/components/forms/form-utils";
import { TooltipProvider } from "@/components/ui/tooltip";
import { invariant } from "@/utils/invariant";
import { TransformPanel as TransformPanelComponent } from "../panel";
import {
  type Transformations,
  TransformationsSchema,
  TransformTypeSchema,
} from "../schema";
import type { ColumnId } from "../types";

const TransformPanel = (
  props: ComponentProps<typeof TransformPanelComponent>,
) => (
  <TooltipProvider>
    <TransformPanelComponent {...props} />
  </TooltipProvider>
);

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const EMPTY: Transformations = { transforms: [] };

function props(
  initialValue: Transformations = EMPTY,
): ComponentProps<typeof TransformPanel> {
  return {
    initialValue,
    columns: new Map([
      ["a" as ColumnId, "integer"],
      ["b" as ColumnId, "integer"],
    ]),
    onChange: vi.fn(),
    onInvalidChange: vi.fn(),
    getColumnValues: vi
      .fn()
      .mockResolvedValue({ values: [], too_many_values: false }),
    lazy: false,
  };
}

async function addTransform(name: string) {
  fireEvent.keyDown(screen.getByRole("button", { name: "Add" }), {
    key: "ArrowDown",
  });
  fireEvent.click(await screen.findByRole("menuitem", { name }));
}

describe("pending transform steps", () => {
  it.each([
    "Group By",
    "Pivot",
    "Column Conversion",
    "Select Columns",
    "Aggregate",
    "Rename Column",
    "Sort Column",
    "Sample Rows",
    "Explode Columns",
    "Expand Dict",
    "Unique",
    "Filter Rows",
  ])("holds a new %s step without an error or submission", async (name) => {
    const callbacks = props();
    const { container } = render(<TransformPanel {...callbacks} />);
    await addTransform(name);
    await waitFor(() =>
      expect(callbacks.onInvalidChange).toHaveBeenCalledTimes(1),
    );
    expect(callbacks.onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Complete the required fields",
    );
    expect(container.querySelector('[aria-invalid="true"]')).toBeNull();
  });

  it("applies Group By only after selection and shows an error when the selection is cleared", async () => {
    const callbacks = props();
    render(<TransformPanel {...callbacks} />);
    await addTransform("Group By");
    fireEvent.click(screen.getByRole("button", { name: "Group by columns" }));
    fireEvent.click(await screen.findByRole("option", { name: /a/ }));
    await waitFor(() => expect(callbacks.onChange).toHaveBeenCalledTimes(1));
    expect(callbacks.onChange).toHaveBeenLastCalledWith({
      transforms: [
        {
          type: "group_by",
          column_ids: ["a"],
          aggregation_column_ids: [],
          aggregation: "count",
          drop_na: false,
        },
      ],
    });
    expect(screen.queryByText("Pending")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Group by columns" }));
    fireEvent.click(screen.getByRole("option", { name: /a/ }));
    await screen.findByText("At least one column is required");
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(callbacks.onChange).toHaveBeenCalledTimes(1);
  });

  it("holds Pivot with Columns only", async () => {
    const callbacks = props();
    render(<TransformPanel {...callbacks} />);
    await addTransform("Pivot");
    fireEvent.click(screen.getByRole("button", { name: "Columns" }));
    fireEvent.click(await screen.findByRole("option", { name: /a/ }));
    await screen.findByText("Select at least one column in Rows or Values");
    expect(callbacks.onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("leaves conversion type unset after the column is selected", async () => {
    const callbacks = props();
    render(<TransformPanel {...callbacks} />);
    await addTransform("Column Conversion");
    fireEvent.keyDown(screen.getAllByRole("combobox")[0], { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("option", { name: /a/ }));
    await waitFor(() =>
      expect(callbacks.onInvalidChange).toHaveBeenCalledTimes(2),
    );
    expect(callbacks.onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    fireEvent.keyDown(screen.getAllByRole("combobox")[1], { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("option", { name: "int64" }));
    await waitFor(() => expect(callbacks.onChange).toHaveBeenCalledTimes(1));
  });

  it("applies a configured step on Add and clears it on Delete", async () => {
    const callbacks = props();
    render(<TransformPanel {...callbacks} />);
    await addTransform("Shuffle Rows");
    await waitFor(() => expect(callbacks.onChange).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("Pending")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Delete Shuffle Rows" }),
    );
    await waitFor(() =>
      expect(callbacks.onChange).toHaveBeenLastCalledWith({ transforms: [] }),
    );
  });

  it("does not submit on mount or when column metadata changes", async () => {
    const callbacks = props(
      TransformationsSchema.parse({
        transforms: [
          {
            type: "filter_rows",
            where: [{ column_id: "a", operator: ">", value: 1 }],
          },
        ],
      }),
    );
    const { rerender } = render(<TransformPanel {...callbacks} />);
    await act(async () => {
      rerender(
        <TransformPanel
          {...callbacks}
          columns={new Map([["a" as ColumnId, "string"]])}
        />,
      );
    });
    expect(callbacks.onChange).not.toHaveBeenCalled();
    expect(callbacks.onInvalidChange).not.toHaveBeenCalled();
  });

  it("deletes an invalid stored step and submits an empty pipeline", async () => {
    const schema = TransformTypeSchema.options.find(
      (option) => getUnionLiteral(option).value === "group_by",
    );
    invariant(schema, "Expected Group By schema");
    const callbacks = props({ transforms: [getDefaults(schema)] });
    render(<TransformPanel {...callbacks} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete Group By" }));
    await waitFor(() =>
      expect(callbacks.onChange).toHaveBeenCalledExactlyOnceWith({
        transforms: [],
      }),
    );
  });

  it("keeps lazy changes local until Apply", async () => {
    const callbacks = { ...props(), lazy: true };
    render(<TransformPanel {...callbacks} />);
    await addTransform("Shuffle Rows");
    expect(callbacks.onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(callbacks.onChange).toHaveBeenCalledTimes(1));
  });

  it("applies deletion of a nested filter condition", async () => {
    const first = { column_id: "a", operator: ">", value: 0 };
    const second = { column_id: "a", operator: "<", value: 3 };
    const initialValue = TransformationsSchema.parse({
      transforms: [{ type: "filter_rows", where: [first, second] }],
    });
    const callbacks = props(initialValue);
    const { container } = render(<TransformPanel {...callbacks} />);
    const removeButtons = container.querySelectorAll(".lucide-trash-2");
    fireEvent.click(removeButtons[2]);
    await waitFor(() =>
      expect(callbacks.onChange).toHaveBeenCalledExactlyOnceWith(
        TransformationsSchema.parse({
          transforms: [{ type: "filter_rows", where: [first] }],
        }),
      ),
    );
  });
});
