/* Copyright 2026 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { type ComponentProps, useEffect, useRef } from "react";
import { expect, it, vi } from "vitest";
import type { CellEditor } from "@/components/editor/cell/code/cell-editor";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ScratchPad } from "./scratchpad";
import {
  historyVisibleAtom,
  scratchpadHistoryAtom,
} from "./scratchpad-history";
import { scratchpadCodeAtom } from "./state";

const state = vi.hoisted(() => ({
  editor: null as EditorView | null,
}));

vi.mock("@/core/cells/cells", () => ({
  useNotebook: () => ({ cellRuntime: {}, cellData: {} }),
}));
vi.mock("@/core/cells/actions", () => ({
  useCellActions: () => ({ createCell: vi.fn() }),
}));
vi.mock("@/core/cells/focus", () => ({ useLastFocusedCellId: () => null }));
vi.mock("@/core/network/requests", () => ({
  useRequestClient: () => ({ sendRunScratchpad: vi.fn() }),
}));
vi.mock("@/components/editor/chrome/panels/panel-context", () => ({
  usePanelOrientation: () => "vertical",
  usePanelSection: () => "sidebar",
}));
vi.mock("@/components/editor/Output", () => ({ OutputArea: () => null }));
vi.mock("@/components/editor/output/console/ConsoleOutput", () => ({
  ConsoleOutput: () => null,
}));
vi.mock("@/plugins/impl/code/LazyAnyLanguageCodeMirror", () => ({
  LazyAnyLanguageCodeMirror: () => null,
}));
vi.mock("@/components/shortcuts/renderShortcut", () => ({
  renderShortcut: () => "",
}));
vi.mock("@/components/editor/cell/code/cell-editor", () => ({
  CellEditor: ({ setEditorView }: ComponentProps<typeof CellEditor>) => {
    const parent = useRef<HTMLDivElement>(null);
    const setView = useRef(setEditorView);
    useEffect(() => {
      const view = new EditorView({
        parent: parent.current ?? undefined,
        extensions: [
          EditorView.contentAttributes.of({
            "aria-label": "Scratchpad editor",
          }),
        ],
      });
      state.editor = view;
      setView.current(view);
      return () => {
        view.destroy();
        state.editor = null;
      };
    }, []);
    return <div ref={parent} />;
  },
}));

it("focuses the editor after recalling history", () => {
  const store = createStore();
  store.set(scratchpadHistoryAtom, ["print(42)"]);
  store.set(historyVisibleAtom, true);
  render(
    <Provider store={store}>
      <TooltipProvider>
        <ScratchPad />
      </TooltipProvider>
    </Provider>,
  );
  const recall = screen.getByRole("button", { name: "Recall code" });
  act(() => recall.focus());
  fireEvent.click(recall, { detail: 0 });
  expect(recall).not.toBeInTheDocument();
  expect(
    screen.getByRole("textbox", { name: "Scratchpad editor" }),
  ).toHaveFocus();
  expect(state.editor?.state.doc.toString()).toBe("print(42)");
  expect(store.get(scratchpadCodeAtom)).toBe("print(42)");
});
