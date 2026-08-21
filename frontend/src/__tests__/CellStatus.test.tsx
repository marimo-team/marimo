/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import {
  CellStatusComponent,
  type CellStatusDisplay,
  ElapsedTime,
} from "@/components/editor/cell/CellStatus";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CellId } from "@/core/cells/ids";
import { deriveCellSemanticState } from "@/core/cells/semantic-state";
import {
  createCell,
  createCellRuntimeState,
  type CellData,
  type CellRuntimeState,
} from "@/core/cells/types";
import { formatElapsedTime, type Milliseconds } from "@/utils/time";

const cellId = CellId.create();
const state = (
  data: Partial<CellData> = {},
  runtime: Partial<CellRuntimeState> = {},
) =>
  deriveCellSemanticState(
    createCell({ id: cellId, ...data }),
    createCellRuntimeState(runtime),
  );

const renderStatus = (
  semanticState: ReturnType<typeof deriveCellSemanticState>,
  editing = true,
  display: CellStatusDisplay = "full",
) =>
  render(
    <TooltipProvider>
      <CellStatusComponent
        editing={editing}
        state={semanticState}
        display={display}
      />
    </TooltipProvider>,
  );

describe("formatElapsedTime", () => {
  test("formats milliseconds, seconds, and minutes", () => {
    expect(formatElapsedTime(500)).toBe("500ms");
    expect(formatElapsedTime(2340)).toBe("2.34s");
    expect(formatElapsedTime(90 * 1000)).toBe("1m30s");
    expect(formatElapsedTime(null)).toBe("");
  });
});

describe("ElapsedTime", () => {
  test("renders elapsed time", () => {
    render(<ElapsedTime elapsedTime="1.50s" />);
    expect(screen.getByText("1.50s")).toBeInTheDocument();
  });
});

describe("CellStatusComponent", () => {
  test.each([
    ["not-run", state()],
    ["outdated", state({ edited: true, lastExecutionTime: 100 })],
    ["interrupted", state({}, { interrupted: true })],
    ["stopped", state({}, { stopped: true })],
    ["error", state({}, { errored: true })],
    ["running", state({}, { status: "running" })],
    ["queued", state({}, { status: "queued" })],
    [
      "paused",
      state({ config: { disabled: true, hide_code: false, column: null } }),
    ],
    ["blocked", state({}, { status: "disabled-transitively" })],
  ])("renders the %s semantic state", (expected, semanticState) => {
    renderStatus(semanticState);
    expect(screen.getByTestId("cell-status")).toHaveAttribute(
      "data-status",
      expected,
    );
  });

  test("exposes the semantic state to assistive technology", () => {
    renderStatus(state({}, { status: "queued" }));
    const indicator = screen.getByLabelText("Queued");
    expect(indicator).toHaveAttribute("role", "status");
  });

  test("communicates an error together with outdated output", () => {
    renderStatus(
      state({ edited: true, lastExecutionTime: 100 }, { errored: true }),
    );
    expect(screen.getByTestId("cell-status")).toHaveAttribute(
      "data-status",
      "error-outdated",
    );
    expect(screen.getByLabelText("Error · Outdated")).toBeInTheDocument();
  });

  test("communicates paused and outdated together", () => {
    renderStatus(
      state(
        {
          edited: true,
          lastExecutionTime: 100,
          config: { disabled: true, hide_code: false, column: null },
        },
        {},
      ),
    );
    expect(screen.getByLabelText("Paused · Outdated")).toBeInTheDocument();
  });

  test("does not render edit chrome outside edit mode", () => {
    const { container } = renderStatus(state(), false);
    expect(container).toBeEmptyDOMElement();
  });

  test("shows successful duration only as secondary information", () => {
    renderStatus(state({}, { runElapsedTimeMs: 1500 as Milliseconds }));
    expect(screen.getByText("1.50s").parentElement).toHaveClass("hover-action");
  });

  test("uses an icon-sized presentation in multi-column layouts", () => {
    renderStatus(state({}, { status: "running" }), true, "compact");
    expect(screen.getByTestId("cell-status")).toHaveAttribute(
      "data-display",
      "compact",
    );
  });

  test("keeps completed duration available on hover in multi-column layouts", () => {
    renderStatus(
      state({}, { runElapsedTimeMs: 1500 as Milliseconds }),
      true,
      "compact",
    );
    expect(screen.getByText("1.50s").parentElement).toHaveClass(
      "hover-action-stable",
    );
  });
});
