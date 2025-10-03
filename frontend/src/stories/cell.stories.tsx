/* Copyright 2024 Marimo. All rights reserved. */

import type { Meta, StoryObj } from "@storybook/react-vite";
import { createStore, Provider } from "jotai";
import { createRef } from "react";
import { type NotebookState, notebookAtom } from "@/core/cells/cells";
import {
  type CellRuntimeState,
  createCellRuntimeState,
} from "@/core/cells/types";
import { defaultUserConfig } from "@/core/config/config-schema";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { resolveRequestClient } from "@/core/network/resolve";
import type { CellConfig } from "@/core/network/types";
import { WebSocketState } from "@/core/websocket/types";
import { MultiColumn } from "@/utils/id-tree";
import type { Milliseconds, Seconds } from "@/utils/time";
import { Cell as EditorCell } from "../components/editor/notebook-cell";
import { TooltipProvider } from "../components/ui/tooltip";
import type { CellId } from "../core/cells/ids";

type Story = StoryObj<typeof Cell>;

const Cell: React.FC<{
  overrides?: {
    runElapsedTimeMs?: Milliseconds;
    output?: CellRuntimeState["output"];
    edited?: boolean;
    interrupted?: boolean;
    errored?: boolean;
    status?: CellRuntimeState["status"];
    staleInputs?: boolean;
    config?: CellConfig;
  };
}> = ({ overrides = {} }) => {
  const cellId = "1" as CellId;
  const notebook: NotebookState = {
    cellData: {
      [cellId]: {
        id: cellId,
        name: "cell_1",
        code: "import marimo as mo",
        edited: overrides.edited ?? false,
        serializedEditorState: null,
        config: {
          hide_code: overrides.config?.hide_code ?? false,
          disabled: overrides.config?.disabled ?? false,
          column: null,
        },
        lastCodeRun: null,
        lastExecutionTime: null,
      },
    },
    cellIds: MultiColumn.from([[cellId]]),
    cellRuntime: {
      [cellId]: createCellRuntimeState({
        output: overrides.output ?? null,
        runElapsedTimeMs: overrides.runElapsedTimeMs ?? (10 as Milliseconds),
        status: overrides.status ?? "idle",
        consoleOutputs: [],
        interrupted: overrides.interrupted ?? false,
        errored: overrides.errored ?? false,
        stopped: false,
        staleInputs: overrides.staleInputs ?? false,
        runStartTimestamp: 0 as Seconds,
        lastRunStartTimestamp: 0 as Seconds,
        debuggerActive: false,
        outline: null,
      }),
    },
    cellHandles: {
      [cellId]: createRef(),
    },
    cellLogs: [],
    history: [],
    scrollKey: null,
    untouchedNewCells: new Set(),
  };

  const store = createStore();
  store.set(notebookAtom, notebook);
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(requestClientAtom, resolveRequestClient());
  return (
    <Provider store={store}>
      <TooltipProvider>
        <EditorCell
          cellId={cellId}
          theme={"light"}
          showPlaceholder={false}
          mode={"edit"}
          canDelete={true}
          isCollapsed={false}
          collapseCount={0}
          canMoveX={false}
          userConfig={defaultUserConfig()}
        />
      </TooltipProvider>
    </Provider>
  );
};

export default {
  title: "Cell",
  component: Cell,
  args: {},
} satisfies Meta<typeof Cell>;

export const Primary: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell />
    </div>
  ),
};

export const WithOutput: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          output: {
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const WithLargeOutput: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          output: {
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>".repeat(
              10,
            ),
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const UnsavedEditsOutput: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <Cell
          overrides={{
            runElapsedTimeMs: 20 as Milliseconds,
            edited: true,
            output: {
              channel: "output",
              data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
              mimetype: "text/html",
              timestamp: 1_686_863_688,
            },
          }}
        />
      </TooltipProvider>
    </div>
  ),
};

export const InterruptedOutput: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <Cell
          overrides={{
            runElapsedTimeMs: 20 as Milliseconds,
            interrupted: true,
            output: {
              channel: "output",
              data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
              mimetype: "text/html",
              timestamp: 1_686_863_688,
            },
          }}
        />
      </TooltipProvider>
    </div>
  ),
};

export const WithError: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          errored: true,
          output: {
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          config: {
            disabled: true,
            hide_code: false,
            column: null,
          },
          output: {
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const DisabledTransitively: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          status: "disabled-transitively",
          output: {
            channel: "output",
            data: "This data is stale because a parent is disabled",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const StaleStatus: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          status: "disabled-transitively",
          staleInputs: true,
          output: {
            channel: "output",
            data: "This data is stale because a parent is disabled",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const StaleAndEditedStatus: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          status: "disabled-transitively",
          staleInputs: true,
          edited: true,
          output: {
            channel: "output",
            data: "This data is stale because a parent is disabled, but this cell has been edited since.",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const DisabledAndStaleStatus: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          config: {
            column: null,
            disabled: true,
            hide_code: false,
          },
          status: "disabled-transitively",
          staleInputs: true,
          output: {
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};

export const Running: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <Cell
        overrides={{
          runElapsedTimeMs: 20 as Milliseconds,
          status: "running",
          output: {
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
            mimetype: "text/html",
            timestamp: 1_686_863_688,
          },
        }}
      />
    </div>
  ),
};
