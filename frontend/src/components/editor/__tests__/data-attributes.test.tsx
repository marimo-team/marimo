/* Copyright 2024 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeAll, describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { createCellRuntimeState } from "@/core/cells/types";
import type { UserConfig } from "@/core/config/config-schema";
import type { OutputMessage } from "@/core/kernel/messages";
import type { AppMode } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { Cell } from "../notebook-cell";
import { OutputArea } from "../Output";

function createTestWrapper() {
  const store = createStore();
  store.set(requestClientAtom, MockRequestClient.create());
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return { wrapper, store };
}

beforeAll(() => {
  global.ResizeObserver = class ResizeObserver {
    observe() {
      // do nothing
    }
    unobserve() {
      // do nothing
    }
    disconnect() {
      // do nothing
    }
  };
  global.HTMLDivElement.prototype.scrollIntoView = () => {
    // do nothing
  };
});

describe("Cell data attributes", () => {
  it.each([
    "edit",
    "read",
    "present",
  ])("should render cell with data-cell-id and data-cell-name in %s mode", (mode) => {
    const { store, wrapper } = createTestWrapper();
    const cellId = "test" as CellId;
    const cellName = "test_cell";

    const userConfig: UserConfig = {
      display: {
        cell_output: "below",
        code_editor_font_size: 14,
        dataframes: "rich",
        default_table_page_size: 10,
        default_table_max_columns: 10,
        default_width: "normal",
        theme: "light",
        reference_highlighting: false,
      },
      keymap: { preset: "default" },
      completion: {
        activate_on_typing: true,
        signature_hint_on_typing: false,
        copilot: false,
      },
      formatting: { line_length: 88 },
      package_management: { manager: "pip" },
      runtime: {
        auto_instantiate: false,
        default_sql_output: "native",
        auto_reload: "off",
        on_cell_change: "lazy",
        watcher_on_save: "lazy",
        reactive_tests: true,
        output_max_bytes: 1_000_000,
        std_stream_max_bytes: 1_000_000,
        pythonpath: [],
        dotenv: [".env"],
      },
      server: {
        browser: "default",
        follow_symlink: false,
      },
      save: { autosave: "off", autosave_delay: 1000, format_on_save: false },
      ai: {},
    } as UserConfig;

    const notebook = MockNotebook.notebookState({
      cellData: {
        [cellId]: {
          code: "",
          name: cellName,
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

    notebook.cellRuntime[cellId] = createCellRuntimeState({
      status: "idle",
      output: null,
      consoleOutputs: [],
      interrupted: false,
      errored: false,
      stopped: false,
      staleInputs: false,
      runStartTimestamp: null,
      lastRunStartTimestamp: null,
      runElapsedTimeMs: null,
      debuggerActive: false,
      outline: null,
    });

    store.set(notebookAtom, notebook);

    const { container } = render(
      <TooltipProvider>
        <Cell
          cellId={cellId}
          mode={mode as AppMode}
          canDelete={true}
          userConfig={userConfig}
          isCollapsed={false}
          collapseCount={0}
          canMoveX={false}
          theme="light"
          showPlaceholder={false}
        />
      </TooltipProvider>,
      { wrapper },
    );

    const cellElement = container.querySelector(`[data-cell-id="${cellId}"]`);
    expect(cellElement).toBeTruthy();
    expect(cellElement?.getAttribute("data-cell-name")).toBe(cellName);
  });
});

describe("Output data attributes", () => {
  it("should render output with data-cell-role", () => {
    const cellId = "test" as CellId;
    const output: OutputMessage = {
      channel: "output",
      mimetype: "text/plain",
      data: "test output",
      timestamp: 0,
    };

    const { container } = render(
      <TooltipProvider>
        <OutputArea
          output={output}
          cellId={cellId}
          stale={false}
          loading={false}
          allowExpand={true}
          className="test-output"
        />
      </TooltipProvider>,
    );

    const outputElement = container.querySelector('[data-cell-role="output"]');
    expect(outputElement).toBeTruthy();
  });
});
