/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CellStateSummary } from "@/core/cells/semantic-state";
import type { CellColumnId } from "@/utils/id-tree";
import { Column } from "../cell-column";

const columnId = "col-1" as CellColumnId;

function renderColumn({
  width,
  presenting,
  statusSummary,
}: {
  width: "compact" | "columns";
  presenting: boolean;
  statusSummary?: CellStateSummary;
}) {
  const store = createStore();
  return render(
    <Provider store={store}>
      <TooltipProvider>
        <Column
          columnId={columnId}
          index={0}
          width={width}
          canDelete={false}
          canMoveLeft={false}
          canMoveRight={false}
          presenting={presenting}
          statusSummary={statusSummary}
        >
          <div data-testid="column-children" />
        </Column>
      </TooltipProvider>
    </Provider>,
  );
}

describe("Column (single-column notebook)", () => {
  it("spaces cells with the --notebook-cell-gap variable", () => {
    const { getByTestId } = renderColumn({
      width: "compact",
      presenting: false,
    });
    const column = getByTestId("cell-column");
    expect(column.classList.contains("gap-(--notebook-cell-gap)")).toBe(true);
    expect(column.classList.contains("[--notebook-cell-gap:0px]")).toBe(false);
  });

  it("zeroes the cell gap while presenting", () => {
    const { getByTestId } = renderColumn({
      width: "compact",
      presenting: true,
    });
    const column = getByTestId("cell-column");
    expect(column.classList.contains("gap-(--notebook-cell-gap)")).toBe(true);
    expect(column.classList.contains("[--notebook-cell-gap:0px]")).toBe(true);
  });
});

describe("Column (multi-column notebook)", () => {
  it("shows column chrome when not presenting", () => {
    const { getByTestId, getAllByTestId } = renderColumn({
      width: "columns",
      presenting: false,
    });

    expect(getByTestId("column-header").hidden).toBe(false);
    expect(getByTestId("column-frame").classList.contains("border")).toBe(true);
    for (const handle of getAllByTestId("column-resize-handle")) {
      expect(handle.hidden).toBe(false);
    }
  });

  it("summarizes actionable cell states in the column header", () => {
    const { getByRole } = renderColumn({
      width: "columns",
      presenting: false,
      statusSummary: {
        running: 1,
        queued: 2,
        pending: 3,
        unavailableOutdated: 1,
        failed: 1,
      },
    });

    expect(getByRole("status")).toHaveAccessibleName(
      "Column status: 1 running, 2 queued, 3 need execution, 1 failed, 1 outdated but unavailable",
    );
  });

  it("hides column chrome while presenting, without unmounting it", () => {
    const { getByTestId, getAllByTestId } = renderColumn({
      width: "columns",
      presenting: true,
    });

    // Header (drag handle, move/delete/add buttons) is hidden but mounted
    expect(getByTestId("column-header").hidden).toBe(true);
    // No border around the column
    expect(getByTestId("column-frame").classList.contains("border")).toBe(
      false,
    );
    // Resize handles are hidden
    const handles = getAllByTestId("column-resize-handle");
    expect(handles.length).toBeGreaterThan(0);
    for (const handle of handles) {
      expect(handle.hidden).toBe(true);
    }
    // Cell gap is zeroed on the column root (cascades to descendants)
    const columnRoot = getByTestId("column-frame").parentElement;
    expect(columnRoot?.classList.contains("[--notebook-cell-gap:0px]")).toBe(
      true,
    );
    // Editor geometry (saved widths, min-width, gutters) is replaced by the
    // published content width
    const inner = getByTestId("column-children").parentElement;
    expect(inner?.classList.contains("min-w-[500px]")).toBe(false);
    expect(inner?.classList.contains("w-(--content-width)")).toBe(true);
    // Children stay mounted
    expect(getByTestId("column-children")).toBeTruthy();
  });
});
