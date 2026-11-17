/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { parseAppConfig } from "@/core/config/config-schema";
import { GridLayoutRenderer } from "../grid-layout";
import type { GridLayout } from "../types";

vi.mock("@/components/editor/Output", () => ({
  OutputArea: ({ cellId }: { cellId: string }) => (
    <div data-testid={`output-${cellId}`} />
  ),
}));

const ERRORED = cellId("errored");

function renderErroredCell(cells: GridLayout["cells"]) {
  const store = createStore();
  MockExecutions.seed(store, [MockExecutions.errored(ERRORED)]);
  const notebook = MockNotebook.notebookState({
    cellData: { [ERRORED]: { code: "raise ValueError('boom')" } },
  });
  render(
    <Provider store={store}>
      <GridLayoutRenderer
        appConfig={parseAppConfig({})}
        mode="edit"
        layout={{
          columns: 12,
          rowHeight: 20,
          cells,
          scrollableCells: new Set(),
          cellSide: new Map(),
        }}
        setLayout={vi.fn()}
        cells={[
          {
            ...notebook.cellData[ERRORED],
            ...notebook.cellRuntime[ERRORED],
            output: null,
          },
        ]}
      />
    </Provider>,
  );
  return screen.getAllByTestId(`output-${ERRORED}`);
}

describe("GridLayoutRenderer", () => {
  it("hides an errored cell placed in the grid", () => {
    const [placed] = renderErroredCell([
      { i: ERRORED, x: 0, y: 0, w: 4, h: 4 },
    ]);
    expect(placed.closest(".invisible")).not.toBeNull();
  });

  it("keeps an errored cell visible in the Outputs tray", () => {
    const outputs = renderErroredCell([]);
    expect(screen.getByText("Outputs")).toBeTruthy();
    expect(outputs.length).toBeGreaterThan(0);
    for (const output of outputs) {
      expect(output.closest(".invisible")).toBeNull();
    }
  });
});
