/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createCell, createCellRuntimeState } from "@/core/cells/types";
import { SlideCellReadOnlyView } from "../slide-cell-view";

beforeAll(() => {
  SetupMocks.resizeObserver();
});

describe("SlideCellReadOnlyView", () => {
  it("renders the cell's data-cell-id and data-cell-name so it can be targeted by custom CSS", () => {
    const id = cellId("test");
    const cell = {
      ...createCell({ id, name: "title", code: "x = 1" }),
      ...createCellRuntimeState(),
    };

    const { container } = render(
      <TooltipProvider>
        <SlideCellReadOnlyView cell={cell} />
      </TooltipProvider>,
    );

    const cellElement = container.querySelector(`[data-cell-id="${id}"]`);
    expect(cellElement).toBeTruthy();
    expect(cellElement?.getAttribute("data-cell-name")).toBe("title");
  });
});
