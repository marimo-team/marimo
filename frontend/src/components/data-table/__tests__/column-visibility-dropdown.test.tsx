/* Copyright 2026 Marimo. All rights reserved. */

import {
  type ColumnDef,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ColumnVisibilityDropdown } from "../column-visibility-dropdown";
import { INDEX_COLUMN_NAME, SELECT_COLUMN_ID } from "../types";

beforeAll(() => {
  global.HTMLElement.prototype.scrollIntoView = () => {
    // jsdom does not implement scrollIntoView; cmdk calls it on selection.
  };
  if (!global.HTMLElement.prototype.hasPointerCapture) {
    global.HTMLElement.prototype.hasPointerCapture = () => false;
  }
});

type Row = Record<string, unknown>;
const EMPTY_COLUMN_IDS: readonly string[] = [];

// Select, index, and nameless columns are non-hideable in production
// (see columns.tsx), so the harness mirrors that to keep visibility counts
// aligned with the real table.
const TEST_COLUMNS: ColumnDef<Row>[] = [
  { id: SELECT_COLUMN_ID, accessorKey: SELECT_COLUMN_ID, enableHiding: false },
  {
    id: INDEX_COLUMN_NAME,
    accessorKey: INDEX_COLUMN_NAME,
    enableHiding: false,
  },
  { id: "__m_column__0", accessorKey: "__m_column__0", enableHiding: false },
  {
    id: "customer_name",
    accessorKey: "customer_name",
    meta: { dataType: "string" },
  },
  { id: "cust_age", accessorKey: "cust_age", meta: { dataType: "integer" } },
  {
    id: "order_total",
    accessorKey: "order_total",
    meta: { dataType: "number" },
  },
];

interface HarnessProps {
  initiallyHidden?: readonly string[];
  nonHideable?: readonly string[];
}

function Harness({
  initiallyHidden = EMPTY_COLUMN_IDS,
  nonHideable = EMPTY_COLUMN_IDS,
}: HarnessProps) {
  const table = useReactTable<Row>({
    data: [],
    columns: TEST_COLUMNS.map((column) =>
      nonHideable.includes(column.id as string)
        ? { ...column, enableHiding: false }
        : column,
    ),
    getCoreRowModel: getCoreRowModel(),
    locale: "en-US",
    initialState: {
      columnVisibility: Object.fromEntries(
        initiallyHidden.map((id) => [id, false]),
      ),
    },
  });
  return <ColumnVisibilityDropdown table={table} />;
}

function renderAndOpen(props?: HarnessProps) {
  const result = render(
    <TooltipProvider>
      <Harness {...(props ?? {})} />
    </TooltipProvider>,
  );
  fireEvent.click(screen.getByTestId("column-visibility-trigger"));
  return result;
}

function getShowOnlyButton(columnName: string): HTMLElement {
  const button = getColumnOption(columnName).querySelector(
    '[aria-label="Show only this column"]',
  );
  if (!button) {
    throw new Error(`No show-only button for column ${columnName}`);
  }
  return button as HTMLElement;
}

function getOptionTexts(): string[] {
  return screen.getAllByRole("option").map((el) => el.textContent ?? "");
}

function getColumnOption(name: string): HTMLElement {
  const option = screen
    .getAllByRole("option")
    .find((el) => el.textContent === name);
  if (!option) {
    throw new Error(`No option for column ${name}`);
  }
  return option;
}

function getSearchInput() {
  return screen.getByPlaceholderText("Search columns...");
}

describe("ColumnVisibilityDropdown", () => {
  it("renders user columns and excludes select/index/nameless columns", () => {
    renderAndOpen();
    expect(screen.getByText("customer_name")).toBeInTheDocument();
    expect(screen.getByText("cust_age")).toBeInTheDocument();
    expect(screen.getByText("order_total")).toBeInTheDocument();
    expect(screen.queryByText(SELECT_COLUMN_ID)).not.toBeInTheDocument();
    expect(screen.queryByText(INDEX_COLUMN_NAME)).not.toBeInTheDocument();
    expect(screen.queryByText("__m_column__0")).not.toBeInTheDocument();
  });

  it("lists hidden columns before shown columns", () => {
    renderAndOpen({ initiallyHidden: ["cust_age"] });
    expect(getOptionTexts()).toEqual([
      "Show all",
      "Hide all",
      "cust_age",
      "customer_name",
      "order_total",
    ]);
  });

  it("toggling a hidden column flips the icon without moving the row", () => {
    renderAndOpen({ initiallyHidden: ["cust_age"] });
    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).not.toBeNull();

    fireEvent.click(getColumnOption("cust_age"));

    expect(getOptionTexts()).toEqual([
      "Show all",
      "Hide all",
      "cust_age",
      "customer_name",
      "order_total",
    ]);
    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).toBeNull();
  });

  it("re-sorts on reopen after a toggle", () => {
    renderAndOpen({ initiallyHidden: ["cust_age"] });
    // Hide customer_name: it stays in the shown section until reopen.
    fireEvent.click(getColumnOption("customer_name"));
    expect(getOptionTexts()).toEqual([
      "Show all",
      "Hide all",
      "cust_age",
      "customer_name",
      "order_total",
    ]);

    const trigger = screen.getByTestId("column-visibility-trigger");
    fireEvent.click(trigger);
    fireEvent.click(trigger);

    // Reopen sorts both hidden columns first, preserving table order.
    expect(getOptionTexts()).toEqual([
      "Show all",
      "Hide all",
      "customer_name",
      "cust_age",
      "order_total",
    ]);
  });

  it("filters columns with smartMatch", () => {
    renderAndOpen();
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    expect(screen.getByText("customer_name")).toBeInTheDocument();
    expect(screen.getByText("cust_age")).toBeInTheDocument();
    expect(screen.queryByText("order_total")).not.toBeInTheDocument();
  });

  it("shows 'No results.' when nothing matches", () => {
    renderAndOpen();
    fireEvent.change(getSearchInput(), { target: { value: "xyz" } });
    expect(screen.getByText("No results.")).toBeInTheDocument();
    expect(screen.queryByText("customer_name")).not.toBeInTheDocument();
  });

  it("disables 'Show all' when no columns are hidden", () => {
    renderAndOpen();
    expect(getColumnOption("Show all")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("'Show all' restores hidden columns", () => {
    renderAndOpen({ initiallyHidden: ["cust_age", "order_total"] });
    fireEvent.click(getColumnOption("Show all"));

    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).toBeNull();
    expect(
      getColumnOption("order_total").querySelector(".lucide-eye-off"),
    ).toBeNull();
    expect(getColumnOption("Show all")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("'Hide all' hides every hideable column", () => {
    renderAndOpen();
    fireEvent.click(getColumnOption("Hide all"));

    expect(
      getColumnOption("customer_name").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    expect(
      getColumnOption("order_total").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    expect(getColumnOption("Hide all")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("disables 'Hide all' when every column is already hidden", () => {
    renderAndOpen({
      initiallyHidden: ["customer_name", "cust_age", "order_total"],
    });
    expect(getColumnOption("Hide all")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("'Hide all' leaves non-hideable columns visible", () => {
    renderAndOpen({ nonHideable: ["customer_name"] });
    fireEvent.click(getColumnOption("Hide all"));

    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    const nonHideable = getColumnOption("customer_name");
    expect(nonHideable).toHaveAttribute("aria-disabled", "true");
    expect(nonHideable.querySelector(".lucide-eye-off")).toBeNull();
    // Every hideable column is now hidden, so the action gates off.
    expect(getColumnOption("Hide all")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("hides and shows matching columns via bulk actions while searching", () => {
    renderAndOpen();
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    expect(screen.queryByText(/Show all/)).not.toBeInTheDocument();

    fireEvent.click(getColumnOption("Hide 2 matching"));
    expect(
      getColumnOption("customer_name").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    expect(screen.queryByText(/Hide \d+ matching/)).not.toBeInTheDocument();

    fireEvent.click(getColumnOption("Show 2 matching"));
    expect(
      getColumnOption("customer_name").querySelector(".lucide-eye-off"),
    ).toBeNull();
    expect(screen.queryByText(/Show \d+ matching/)).not.toBeInTheDocument();
  });

  it("offers both bulk actions when matches are mixed", () => {
    renderAndOpen({ initiallyHidden: ["cust_age"] });
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    expect(screen.getByText(/Show only 2 matching/)).toBeInTheDocument();
    expect(screen.getByText(/Hide 1 matching/)).toBeInTheDocument();
    expect(screen.getByText(/Show 1 matching/)).toBeInTheDocument();
  });

  it("lists show-only before hide and show bulk actions while searching", () => {
    renderAndOpen({ initiallyHidden: ["cust_age"] });
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    expect(getOptionTexts().slice(0, 3)).toEqual([
      "Show only 2 matching",
      "Hide 1 matching",
      "Show 1 matching",
    ]);
  });

  it("'Show only N matching' isolates matching columns", () => {
    renderAndOpen({ initiallyHidden: ["cust_age"] });
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    fireEvent.click(getColumnOption("Show only 2 matching"));
    fireEvent.change(getSearchInput(), { target: { value: "" } });

    expect(
      getColumnOption("customer_name").querySelector(".lucide-eye-off"),
    ).toBeNull();
    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).toBeNull();
    expect(
      getColumnOption("order_total").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    expect(getColumnOption("Show only 2 matching")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("disables 'Show only N matching' when already showing only matches", () => {
    renderAndOpen({
      initiallyHidden: ["order_total"],
    });
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    expect(getColumnOption("Show only 2 matching")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("omits 'Show only N matching' without search text", () => {
    renderAndOpen();
    expect(
      screen.queryByText(/Show only \d+ matching/),
    ).not.toBeInTheDocument();
  });

  it("omits search bulk actions when only non-hideable columns match", () => {
    renderAndOpen({ nonHideable: ["customer_name"] });
    fireEvent.change(getSearchInput(), { target: { value: "customer" } });
    expect(screen.getByText("customer_name")).toBeInTheDocument();
    expect(
      screen.queryByText(/Show only \d+ matching/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Hide \d+ matching/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Show \d+ matching/)).not.toBeInTheDocument();
  });

  it("show-only icon isolates one column without clearing search", () => {
    renderAndOpen();
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    fireEvent.click(getShowOnlyButton("customer_name"));
    expect(getSearchInput()).toHaveValue("cust");
    fireEvent.change(getSearchInput(), { target: { value: "" } });

    expect(
      getColumnOption("customer_name").querySelector(".lucide-eye-off"),
    ).toBeNull();
    expect(
      getColumnOption("cust_age").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
    expect(
      getColumnOption("order_total").querySelector(".lucide-eye-off"),
    ).not.toBeNull();
  });

  it("show-only icon does not toggle the row visibility", () => {
    renderAndOpen();
    fireEvent.click(getShowOnlyButton("customer_name"));

    expect(
      getColumnOption("customer_name").querySelector(".lucide-eye-off"),
    ).toBeNull();
  });

  it("disables show-only icon when the column is already alone", () => {
    renderAndOpen({
      initiallyHidden: ["cust_age", "order_total"],
    });
    expect(getShowOnlyButton("customer_name")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("disabled show-only icon blocks pointer activation of the row", () => {
    renderAndOpen({
      initiallyHidden: ["cust_age", "order_total"],
    });
    const button = getShowOnlyButton("customer_name");
    expect(button).toHaveAttribute("aria-disabled", "true");

    fireEvent.pointerDown(button, { pointerId: 1, bubbles: true });
    fireEvent.click(button, { bubbles: true });

    expect(
      getColumnOption("customer_name").querySelector(".lucide-eye-off"),
    ).toBeNull();
  });

  it("renders non-hideable columns disabled and without an eye toggle", () => {
    renderAndOpen({ nonHideable: ["customer_name"] });
    const option = getColumnOption("customer_name");
    expect(option).toHaveAttribute("aria-disabled", "true");
    expect(option.querySelector(".lucide-eye")).toBeNull();
    expect(option.querySelector(".lucide-eye-off")).toBeNull();
  });
});
