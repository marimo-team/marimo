/* Copyright 2024 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import { Cell } from "../Cell";
import { OutputArea } from "../Output";
import type { CellId } from "@/core/cells/ids";
import type { OutputMessage } from "@/core/kernel/messages";
import { Functions } from "@/utils/functions";
import type { UserConfig } from "@/core/config/config-schema";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { AppMode } from "@/core/mode";

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
  it.each(["edit", "read", "present"])(
    "should render cell with data-cell-id and data-cell-name in %s mode",
    (mode) => {
      const cellId = "test" as CellId;
      const cellName = "test_cell";

      const userConfig: UserConfig = {
        display: {
          cell_output: "below",
          code_editor_font_size: 14,
          dataframes: "rich",
          default_width: "normal",
          theme: "light",
        },
        keymap: { preset: "default" },
        completion: {
          activate_on_typing: true,
          copilot: false,
        },
        formatting: { line_length: 88 },
        package_management: { manager: "pip" },
        runtime: {
          auto_instantiate: false,
          auto_reload: "off",
          on_cell_change: "lazy",
          watcher_on_save: "lazy",
          output_max_bytes: 1_000_000,
          std_stream_max_bytes: 1_000_000,
        },
        server: {
          browser: "default",
          follow_symlink: false,
        },
        save: { autosave: "off", autosave_delay: 1000, format_on_save: false },
        ai: {},
      };

      const { container } = render(
        <TooltipProvider>
          <Cell
            id={cellId}
            name={cellName}
            code=""
            output={null}
            consoleOutputs={[]}
            status="idle"
            edited={false}
            interrupted={false}
            errored={false}
            stopped={false}
            staleInputs={false}
            runStartTimestamp={null}
            lastRunStartTimestamp={null}
            runElapsedTimeMs={null}
            serializedEditorState={null}
            mode={mode as AppMode}
            debuggerActive={false}
            appClosed={false}
            canDelete={true}
            updateCellCode={Functions.NOOP}
            prepareForRun={Functions.NOOP}
            createNewCell={Functions.NOOP}
            deleteCell={Functions.NOOP}
            focusCell={Functions.NOOP}
            moveCell={Functions.NOOP}
            setStdinResponse={Functions.NOOP}
            moveToNextCell={Functions.NOOP}
            updateCellConfig={Functions.NOOP}
            clearSerializedEditorState={Functions.NOOP}
            sendToBottom={Functions.NOOP}
            sendToTop={Functions.NOOP}
            collapseCell={Functions.NOOP}
            expandCell={Functions.NOOP}
            userConfig={userConfig}
            outline={null}
            isCollapsed={false}
            collapseCount={0}
            config={{
              disabled: false,
              hide_code: false,
              column: null,
            }}
            canMoveX={false}
            theme="light"
            showPlaceholder={false}
            allowFocus={true}
          />
        </TooltipProvider>,
      );

      const cellElement = container.querySelector(`[data-cell-id="${cellId}"]`);
      expect(cellElement).toBeTruthy();
      expect(cellElement?.getAttribute("data-cell-name")).toBe(cellName);
    },
  );
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
          allowExpand={true}
          className="test-output"
        />
      </TooltipProvider>,
    );

    const outputElement = container.querySelector('[data-cell-role="output"]');
    expect(outputElement).toBeTruthy();
  });
});
