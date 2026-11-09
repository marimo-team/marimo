/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeAll, describe, expect, it } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { mockDocumentModel } from "@/__mocks__/document";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { notebookAtom } from "@/core/cells/cells";
import { DocumentProvider } from "@/core/notebook/document";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { defaultUserConfig } from "@/core/config/config-schema";
import type { AppMode } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { Cell } from "../notebook-cell";

const cid = cellId("test");
const PERSIST = { mimetype: "text/html", data: "<span>persist me</span>" };

function createTestWrapper() {
  const store = createStore();
  const { model } = mockDocumentModel(store, null);
  store.set(requestClientAtom, MockRequestClient.create());
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <DocumentProvider model={model}>{children}</DocumentProvider>
    </Provider>
  );
  return { wrapper, store };
}

function seedNotebook(store: ReturnType<typeof createStore>) {
  const notebook = MockNotebook.notebookState({
    cellData: {
      [cid]: {
        code: "1 + 1",
        name: "test_cell",
        config: {
          disabled: false,
          hide_code: false,
          column: null,
        },
      },
    },
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
    MockExecutions.seed(store, [MockExecutions.shown(cid, PERSIST)]);
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
    MockExecutions.seed(store, [MockExecutions.shown(cid, PERSIST)]);
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
    // The host holds newer source than the cell last ran with
    MockExecutions.seed(
      store,
      [MockExecutions.shown(cid, PERSIST, { code_fingerprint: "ran" })],
      null,
      withCells(
        documentOf(),
        {
          c1: null,
          c2: null,
          [cid]: cell(cid, "1 + 1", { code_fingerprint: "edited" }),
        },
        [cid],
      ),
    );
    seedNotebook(store);

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
    MockExecutions.seed(store, [MockExecutions.errored(cid)]);
    seedNotebook(store);

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
