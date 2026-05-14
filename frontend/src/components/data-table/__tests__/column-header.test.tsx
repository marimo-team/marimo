/* Copyright 2026 Marimo. All rights reserved. */
import type { Column } from "@tanstack/react-table";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
// NumberFilterMenu does not exist yet — Task 5 introduces it.
// These tests are expected to fail until that change lands.
import { NumberFilterMenu } from "../column-header";
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

function mockColumn(
  initial?: ReturnType<typeof Filter.number>,
): Column<unknown, unknown> & {
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
