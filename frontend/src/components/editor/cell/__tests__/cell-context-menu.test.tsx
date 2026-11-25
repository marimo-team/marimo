/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { goToDefinitionWithLspFallback } from "@/core/codemirror/go-to-definition/utils";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  CellActionsContextMenu,
  NotebookContextMenu,
} from "../cell-context-menu";

vi.mock("@/core/codemirror/go-to-definition/utils", () => ({
  goToDefinitionWithLspFallback: vi.fn(),
}));

vi.mock("@/core/cells/cells", () => ({
  useCellData: () => ({ name: "cell", config: {} }),
  useCellRuntime: () => ({ consoleOutputs: [] }),
}));
vi.mock("@/core/executions", () => ({
  useCellExecution: () => ({ status: "idle", blocked: false }),
  useCellOutput: () => null,
}));
vi.mock("../../actions/useCellActionButton", () => ({
  useCellActionButtons: () => [],
}));

it("shares one closed menu and resolves plot actions for the cell that opens it", async () => {
  const add = vi.spyOn(document, "addEventListener");
  const { unmount } = render(
    <TooltipProvider>
      <NotebookContextMenu>
        <div data-testid="background" />
        {Array.from({ length: 20 }, (_, i) => (
          <CellActionsContextMenu
            key={i}
            cellId={cellId(`cell${i}`)}
            getEditorView={() => null}
            disabled={i === 19}
          >
            <div data-testid={`cell${i}`}>
              <img alt={`plot${i}`} />
              <button
                type="button"
                data-testid={`nested${i}`}
                onContextMenu={(event) => event.stopPropagation()}
              >
                Nested menu
              </button>
            </div>
          </CellActionsContextMenu>
        ))}
      </NotebookContextMenu>
    </TooltipProvider>,
  );
  expect(
    add.mock.calls.filter(
      ([name, , capture]) =>
        name === "keydown" &&
        (capture === true || (typeof capture === "object" && capture.capture)),
    ),
  ).toHaveLength(1);
  expect(fireEvent.contextMenu(screen.getByTestId("background"))).toBe(true);
  expect(fireEvent.contextMenu(screen.getByTestId("cell19"))).toBe(true);
  expect(screen.queryByRole("menu")).toBeNull();
  fireEvent.contextMenu(screen.getByTestId("nested0"));
  expect(screen.queryByRole("menu")).toBeNull();
  fireEvent.contextMenu(screen.getByAltText("plot0"));
  expect(
    await screen.findByRole("menuitem", { name: "Copy image" }),
  ).toBeTruthy();
  fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
  fireEvent.contextMenu(screen.getByTestId("cell1"));
  expect(await screen.findByRole("menuitem", { name: "Copy" })).toBeTruthy();
  expect(screen.queryByRole("menuitem", { name: "Copy image" })).toBeNull();
  fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
  const touch = new Event("pointerdown", { bubbles: true });
  Object.assign(touch, { pointerType: "touch", clientX: 10, clientY: 10 });
  fireEvent(screen.getByTestId("cell1"), touch);
  expect(await screen.findByRole("menu")).toBeTruthy();
  unmount();
  add.mockRestore();
});

it.each([false, true])(
  "restores focus unless go-to-definition navigates (navigated: %s)",
  async (navigated) => {
    const editor = new EditorView();
    const { unmount } = render(
      <TooltipProvider>
        <NotebookContextMenu>
          <CellActionsContextMenu
            cellId={cellId("cell")}
            getEditorView={() => editor}
          >
            <button type="button">Source cell</button>
          </CellActionsContextMenu>
          <button type="button">Destination cell</button>
        </NotebookContextMenu>
      </TooltipProvider>,
    );
    const source = screen.getByText("Source cell");
    const destination = screen.getByText("Destination cell");
    vi.mocked(goToDefinitionWithLspFallback).mockImplementation(() => {
      if (navigated) {
        destination.focus();
      }
      return navigated;
    });
    source.focus();
    fireEvent.contextMenu(source);
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Go to Definition" }),
    );
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
    await waitFor(() =>
      expect(document.activeElement).toBe(navigated ? destination : source),
    );
    expect(goToDefinitionWithLspFallback).toHaveBeenLastCalledWith(editor);
    unmount();
    editor.destroy();
  },
);
