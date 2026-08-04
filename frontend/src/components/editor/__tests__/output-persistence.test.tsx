/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeAll, describe, expect, it } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { notebookAtom } from "@/core/cells/cells";
import type { CellRuntimeState } from "@/core/cells/types";
import { createCellRuntimeState } from "@/core/cells/types";
import { defaultUserConfig } from "@/core/config/config-schema";
import type { AppMode } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { Cell } from "../notebook-cell";

const cid = cellId("test");

function createTestWrapper() {
  const store = createStore();
  store.set(requestClientAtom, MockRequestClient.create());
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return { wrapper, store };
}

function seedNotebook(
  store: ReturnType<typeof createStore>,
  runtimeOverrides: Partial<CellRuntimeState> = {},
) {
  const notebook = MockNotebook.notebookState({
    cellData: {
      [cid]: {
        code: "1 + 1",
        name: "test_cell",
        edited: false,
        serializedEditorState: null,
        config: {
          disabled: false,
          hide_code: false,
          column: null,
        },
      },
    },
  });
  notebook.cellRuntime[cid] = createCellRuntimeState({
    status: "idle",
    output: {
      channel: "output",
      mimetype: "text/html",
      data: "<span>persist me</span>",
      timestamp: 0,
    },
    ...runtimeOverrides,
  });
  store.set(notebookAtom, notebook);
}

function renderCell(mode: AppMode) {
  return (
    <TooltipProvider>
      <Cell
        cellId={cid}
        mode={mode}
        canDelete={true}
        userConfig={defaultUserConfig()}
        isCollapsed={false}
        collapseCount={0}
        canMoveX={false}
        theme="light"
        showPlaceholder={false}
      />
    </TooltipProvider>
  );
}

beforeAll(() => {
  SetupMocks.resizeObserver();
  global.HTMLDivElement.prototype.scrollIntoView = () => {
    // do nothing
  };
});

describe("output persistence across mode changes", () => {
  it("preserves the output DOM node when toggling edit <-> present", () => {
    const { store, wrapper } = createTestWrapper();
    seedNotebook(store);

    const { container, rerender } = render(renderCell("edit"), { wrapper });

    const outputNode = container.querySelector<HTMLElement>(
      '[data-cell-role="output"]',
    );
    expect(outputNode).toBeTruthy();
    // A property survives only if the exact DOM node instance survives.
    (outputNode as HTMLElement & { __sentinel?: string }).__sentinel = "alive";

    rerender(renderCell("present"));
    const presentNode = container.querySelector<HTMLElement>(
      '[data-cell-role="output"]',
    );
    expect(presentNode).toBe(outputNode);
    expect(presentNode?.isConnected).toBe(true);
    expect(
      (presentNode as HTMLElement & { __sentinel?: string }).__sentinel,
    ).toBe("alive");

    // Edit chrome is hidden but stays mounted while presenting
    const tray = container.querySelector<HTMLElement>(
      "[data-testid='cell-tray']",
    );
    expect(tray).toBeTruthy();
    expect(tray?.hidden).toBe(true);
    // Present styling is applied
    expect(
      container
        .querySelector(`[data-cell-id="${cid}"]`)
        ?.classList.contains("published"),
    ).toBe(true);

    rerender(renderCell("edit"));
    expect(container.querySelector('[data-cell-role="output"]')).toBe(
      outputNode,
    );
    expect(
      container.querySelector<HTMLElement>("[data-testid='cell-tray']")?.hidden,
    ).toBe(false);
    expect(
      container
        .querySelector(`[data-cell-id="${cid}"]`)
        ?.classList.contains("published"),
    ).toBe(false);
  });

  it("hides all edit chrome while presenting", () => {
    const { store, wrapper } = createTestWrapper();
    seedNotebook(store);

    const { container, rerender } = render(renderCell("edit"), { wrapper });

    // Returns true when the element is not visible: either gone from the DOM or
    // inside a `hidden` ancestor. Edit chrome may unmount while presenting (only
    // the cell *output* is contractually kept mounted — see the DOM-node test
    // above); either way it must not be visible.
    const isHidden = (testId: string) => {
      const el = container.querySelector(`[data-testid='${testId}']`);
      return el === null || el.closest("[hidden]") !== null;
    };

    // Everything visible in edit mode
    const editChrome = [
      "cell-tray",
      "drag-button",
      "cell-actions-button",
      "delete-button",
      "create-cell-button",
      "console-output-area",
    ];
    for (const testId of editChrome) {
      expect({ testId, hidden: isHidden(testId) }).toEqual({
        testId,
        hidden: false,
      });
    }

    rerender(renderCell("present"));
    for (const testId of editChrome) {
      expect({ testId, hidden: isHidden(testId) }).toEqual({
        testId,
        hidden: true,
      });
    }

    rerender(renderCell("edit"));
    for (const testId of editChrome) {
      expect({ testId, hidden: isHidden(testId) }).toEqual({
        testId,
        hidden: false,
      });
    }
  });

  it("does not dim edited-but-not-run outputs as stale while presenting", () => {
    const { store, wrapper } = createTestWrapper();
    seedNotebook(store);
    // Mark the cell as edited without re-running it
    const notebook = store.get(notebookAtom);
    notebook.cellData[cid] = { ...notebook.cellData[cid], edited: true };
    store.set(notebookAtom, { ...notebook });

    const { container, rerender } = render(renderCell("edit"), { wrapper });
    expect(container.querySelector(".marimo-output-stale")).toBeTruthy();

    // The read view never dims pending edits; present mode matches it
    rerender(renderCell("present"));
    expect(container.querySelector(".marimo-output-stale")).toBeFalsy();

    rerender(renderCell("edit"));
    expect(container.querySelector(".marimo-output-stale")).toBeTruthy();
  });

  it("hides errored cells while presenting without unmounting them", () => {
    const { store, wrapper } = createTestWrapper();
    seedNotebook(store, {
      errored: true,
      output: {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: [{ type: "exception", exception_type: "ValueError", msg: "!" }],
        timestamp: 0,
      },
    });

    const { container, rerender } = render(renderCell("edit"), { wrapper });

    const outputNode = container.querySelector<HTMLElement>(
      '[data-cell-role="output"]',
    );
    expect(outputNode).toBeTruthy();

    const getSortableWrapper = () =>
      container.querySelector<HTMLElement>(`[data-cell-id="${cid}"]`)
        ?.parentElement;
    expect(getSortableWrapper()?.hidden).toBe(false);

    rerender(renderCell("present"));
    // Still mounted, but hidden
    expect(container.querySelector('[data-cell-role="output"]')).toBe(
      outputNode,
    );
    expect(getSortableWrapper()?.hidden).toBe(true);

    rerender(renderCell("edit"));
    expect(container.querySelector('[data-cell-role="output"]')).toBe(
      outputNode,
    );
    expect(getSortableWrapper()?.hidden).toBe(false);
  });
});
