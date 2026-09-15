/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { afterEach, describe, expect, test } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId, variableName } from "@/__tests__/branded";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { HTMLCellId } from "@/core/cells/ids";
import { editorMountScheduler } from "@/core/codemirror/editor-mount-scheduler";
import { store } from "@/core/state/jotai";
import type { Variables } from "@/core/variables/types";
import { VariableTable } from "../variables-table";

async function tick(): Promise<void> {
  await new Promise((resolve) => requestAnimationFrame(resolve));
}

const views: EditorView[] = [];
const elements: HTMLElement[] = [];

afterEach(() => {
  for (const view of views.splice(0)) {
    view.destroy();
  }
  for (const element of elements.splice(0)) {
    element.remove();
  }
  store.set(notebookAtom, initialNotebookState());
});

describe("VariableTable cell links", () => {
  test("declared-by click builds the queued editor and highlights the variable", async () => {
    const usageCell = cellId("usage");
    const definingCell = cellId("defining");
    const definingCode = "y = 1\nx = 42";

    const definingView = new EditorView({
      state: EditorState.create({
        doc: definingCode,
        extensions: [python()],
      }),
    });
    views.push(definingView);

    const notebook = MockNotebook.notebookState({
      cellData: {
        [usageCell]: { name: "usage_cell" },
        [definingCell]: { name: "defining_cell" },
      },
    });
    // The defining cell's editor build still waits in the mount queue, the
    // state right after a large notebook opens.
    const handle: { current: CellHandle | null } = { current: null };
    notebook.cellHandles[definingCell] = handle;
    editorMountScheduler.request(definingCell, () => {
      handle.current = {
        editorView: definingView,
        editorViewOrNull: definingView,
      };
    });
    store.set(notebookAtom, notebook);

    // The link's click handler requires the target cell's element on the page.
    const cellElement = document.createElement("div");
    cellElement.id = HTMLCellId.create(definingCell);
    document.body.append(cellElement);
    elements.push(cellElement);

    const variables: Variables = {
      [variableName("x")]: {
        dataType: "int",
        declaredBy: [definingCell],
        name: variableName("x"),
        usedBy: [usageCell],
        value: "42",
      },
    };

    render(
      <Provider store={store}>
        <TooltipProvider>
          <VariableTable
            cellIds={[usageCell, definingCell]}
            variables={variables}
          />
        </TooltipProvider>
      </Provider>,
    );

    expect(handle.current).toBeNull();

    fireEvent.click(screen.getByText("defining_cell"));
    // First frame: the link's click callback runs and builds the queued
    // editor synchronously.
    await tick();
    expect(handle.current?.editorView).toBe(definingView);
    expect(cellElement.classList.contains("focus-outline")).toBe(true);
    // Second frame: the jump dispatches the selection.
    await tick();
    expect(definingView.state.selection.main.head).toBe(
      definingCode.indexOf("x = 42"),
    );
  });
});
