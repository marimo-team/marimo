/* Copyright 2026 Marimo. All rights reserved. */
import type { Column } from "@tanstack/react-table";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { NumberFilterMenu, TextFilterMenu } from "../column-header";
import { Filter } from "../filters";

beforeAll(() => {
  global.HTMLElement.prototype.scrollIntoView = () => {
    // jsdom does not implement scrollIntoView; Radix calls it on open.
  };
  // Radix Select gates pointer interactions on hasPointerCapture; jsdom omits it.
  if (!global.HTMLElement.prototype.hasPointerCapture) {
    global.HTMLElement.prototype.hasPointerCapture = () => false;
  }
  if (!global.HTMLElement.prototype.releasePointerCapture) {
    global.HTMLElement.prototype.releasePointerCapture = () => {
      // no-op
    };
  }
});

function mockColumn(initial?: ReturnType<typeof Filter.number>): Column<
  unknown,
  unknown
> & {
  setFilterValue: ReturnType<typeof vi.fn>;
} {
  let filterValue = initial;
  const setFilterValue = vi.fn((next) => {
    filterValue = next;
  });
  return {
    id: "age",
    columnDef: { meta: { dataType: "number", filterType: "number" } },
    getFilterValue: () => filterValue,
    setFilterValue,
  } as unknown as Column<unknown, unknown> & {
    setFilterValue: ReturnType<typeof vi.fn>;
  };
}

describe("NumberFilterMenu", () => {
  it("shows all expected operators in the dropdown", () => {
    const column = mockColumn();
    render(<NumberFilterMenu column={column} />);
    const trigger = screen.getByRole("combobox");
    fireEvent.click(trigger);
    const listbox = screen.getByRole("listbox");
    const labels = within(listbox)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(labels).toEqual([
      "Between",
      "Equals",
      "Doesn't equal",
      "Greater than",
      "Greater than or equal",
      "Less than",
      "Less than or equal",
      "Is null",
      "Is not null",
    ]);
  });

  it("between mode disables Apply until both min and max are defined", () => {
    const column = mockColumn();
    render(<NumberFilterMenu column={column} />);
    const apply = screen.getByRole("button", { name: /apply/i });
    expect(apply).toBeDisabled();

    const min = screen.getByLabelText("min");
    fireEvent.change(min, { target: { value: "1" } });
    fireEvent.blur(min);
    expect(apply).toBeDisabled();

    const max = screen.getByLabelText("max");
    fireEvent.change(max, { target: { value: "10" } });
    fireEvent.blur(max);
    expect(apply).not.toBeDisabled();
  });

  it("comparison mode shows a single value field seeded from current filter", () => {
    const column = mockColumn(Filter.number({ operator: ">", value: 18 }));
    render(<NumberFilterMenu column={column} />);
    const value = screen.getByLabelText("value") as HTMLInputElement;
    expect(value).toBeInTheDocument();
    expect(value.value).toBe("18");
    expect(screen.queryByLabelText("min")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("max")).not.toBeInTheDocument();
  });

  it("selecting a nullish operator commits immediately and hides value inputs", () => {
    const column = mockColumn();
    render(<NumberFilterMenu column={column} />);
    fireEvent.click(screen.getByRole("combobox"));
    const listbox = screen.getByRole("listbox");
    fireEvent.click(within(listbox).getByText("Is null"));
    expect(column.setFilterValue).toHaveBeenCalledWith(
      Filter.number({ operator: "is_null" }),
    );
    expect(screen.queryByLabelText("min")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("max")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("value")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /apply/i }),
    ).not.toBeInTheDocument();
  });
});

function mockTextColumn(initial?: ReturnType<typeof Filter.text>): Column<
  unknown,
  unknown
> & {
  setFilterValue: ReturnType<typeof vi.fn>;
} {
  let filterValue = initial;
  const setFilterValue = vi.fn((next) => {
    filterValue = next;
  });
  return {
    id: "name",
    columnDef: { meta: { dataType: "string", filterType: "text" } },
    getFilterValue: () => filterValue,
    setFilterValue,
  } as unknown as Column<unknown, unknown> & {
    setFilterValue: ReturnType<typeof vi.fn>;
  };
}

describe("TextFilterMenu", () => {
  it("shows all 11 text operators in the dropdown", () => {
    const column = mockTextColumn();
    render(<TextFilterMenu column={column} />);
    fireEvent.click(screen.getByRole("combobox"));
    const listbox = screen.getByRole("listbox");
    const labels = within(listbox)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(labels).toEqual([
      "Contains",
      "Equals",
      "Doesn't equal",
      "Matches regex",
      "Starts with",
      "Ends with",
      "Is in",
      "Not in",
      "Is empty",
      "Is null",
      "Is not null",
    ]);
  });

  it("single-string operator renders a text input seeded from current filter", () => {
    const column = mockTextColumn(
      Filter.text({ operator: "equals", text: "alice" }),
    );
    render(<TextFilterMenu column={column} />);
    const input = screen.getByPlaceholderText("Text...") as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe("alice");
  });

  it("'in' operator renders the creatable values picker", async () => {
    const column = mockTextColumn(
      Filter.text({ operator: "in", values: ["a", "b"] }),
    );
    const calculateTopKRows = vi.fn(async () => ({
      data: [["a", 1] as [unknown, number]],
    }));
    render(
      <TextFilterMenu column={column} calculateTopKRows={calculateTopKRows} />,
    );
    expect(
      await screen.findByPlaceholderText(/Search or add a value/i),
    ).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Text...")).not.toBeInTheDocument();
  });

  it("selecting is_empty commits immediately and hides the value UI", () => {
    const column = mockTextColumn();
    render(<TextFilterMenu column={column} />);
    fireEvent.click(screen.getByRole("combobox"));
    const listbox = screen.getByRole("listbox");
    fireEvent.click(within(listbox).getByText("Is empty"));
    expect(column.setFilterValue).toHaveBeenCalledWith(
      Filter.text({ operator: "is_empty" }),
    );
    expect(screen.queryByPlaceholderText("Text...")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /apply/i }),
    ).not.toBeInTheDocument();
  });

  it("apply is disabled when scalar text is empty", () => {
    const column = mockTextColumn();
    render(<TextFilterMenu column={column} />);
    expect(screen.getByRole("button", { name: /apply/i })).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Text..."), {
      target: { value: "x" },
    });
    expect(screen.getByRole("button", { name: /apply/i })).not.toBeDisabled();
  });
});
