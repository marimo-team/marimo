/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CellOutputId } from "@/core/cells/ids";
import { createCell, createCellRuntimeState } from "@/core/cells/types";
import { CellOutputBlock } from "../reveal-component";

describe("CellOutputBlock", () => {
  it("renders the cell's data-cell-id and data-cell-name so it can be targeted by custom CSS", () => {
    const id = cellId("test");
    const cell = {
      ...createCell({ id, name: "title" }),
      ...createCellRuntimeState({
        output: {
          channel: "output",
          mimetype: "text/plain",
          data: "hello",
          timestamp: 0,
        },
      }),
    };

    const { container } = render(
      <TooltipProvider>
        <CellOutputBlock cell={cell} />
      </TooltipProvider>,
    );

    const cellElement = container.querySelector(`[data-cell-id="${id}"]`);
    expect(cellElement).toBeTruthy();
    expect(cellElement?.getAttribute("data-cell-name")).toBe("title");

    // The wrapper's `data-cell-id` must coexist with the output's own
    // `CellOutputId`-derived id, without colliding.
    expect(document.getElementById(CellOutputId.create(id))).toBeTruthy();
  });
});
