/* Copyright 2026 Marimo. All rights reserved. */

import type { Meta, StoryObj } from "@storybook/react-vite";
import { createStore, Provider } from "jotai";
import { createRef } from "react";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { type NotebookState, notebookAtom } from "@/core/cells/cells";
import { createCellRuntimeState } from "@/core/cells/types";
import { defaultUserConfig } from "@/core/config/config-schema";
import type { CellOutput } from "@/core/executions";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { resolveRequestClient } from "@/core/network/resolve";
import type { CellConfig } from "@/core/network/types";
import { ConnectionState } from "@/core/session/types";
import { Cell as EditorCell } from "../components/editor/notebook-cell";
import { TooltipProvider } from "../components/ui/tooltip";

type Story = StoryObj<typeof Cell>;

interface CellOverrides {
  output?: CellOutput | null;
  /** How the cell's result is outdated, as the host would report it. */
  freshness?: "edited" | "replaced" | "both";
  config?: CellConfig;
}

const EMPTY_OVERRIDES: Readonly<CellOverrides> = {};

/**
 * Give the replica a completed execution that showed `output`, and whose
 * source was edited since, whose input a newer execution replaced, or both.
 */
function seedResult(
  store: ReturnType<typeof createStore>,
  cid: CellId,
  output: CellOutput | null,
  freshness: CellOverrides["freshness"],
) {
  const ran = MockExecutions.completed(cid, {
    code_fingerprint: "ran",
    depends_on:
      freshness === undefined || freshness === "edited"
        ? {}
        : { x: { execution: "gone", update: 0 } },
    outcome: {
      kind: "value",
      display:
        output === null
          ? null
          : {
              mimetype: output.mimetype,
              data:
                typeof output.data === "string"
                  ? output.data
                  : JSON.stringify(output.data),
            },
    },
  });
  const document =
    freshness === undefined
      ? null
      : withCells(
          documentOf(),
          {
            c1: null,
            c2: null,
            [cid]: cell(cid, "import marimo as mo", {
              code_fingerprint: freshness === "replaced" ? "ran" : "edited",
            }),
          },
          [cid],
        );
  MockExecutions.seed(store, [ran], null, document);
}

const Cell: React.FC<{
  overrides?: CellOverrides;
}> = ({ overrides = EMPTY_OVERRIDES }) => {
  const cid = cellId("1");
  const notebook: NotebookState = {
    cellData: {
      [cid]: {
        id: cid,
        name: "cell_1",
        code: "import marimo as mo",
        config: {
          hide_code: overrides.config?.hide_code ?? false,
          disabled: overrides.config?.disabled ?? false,
          column: null,
        },
      },
    },
    cellIds: [cid],
    cellRuntime: {
      [cid]: createCellRuntimeState(),
    },
    cellHandles: {
      [cid]: createRef(),
    },
    cellLogs: [],
    history: [],
    scrollKey: null,
  };

  const store = createStore();
  store.set(notebookAtom, notebook);
  seedResult(store, cid, overrides.output ?? null, overrides.freshness);
  store.set(connectionAtom, { state: ConnectionState.OPEN });
  store.set(requestClientAtom, resolveRequestClient());
  return (
    <Provider store={store}>
      <TooltipProvider>
        <EditorCell
          cellId={cid}
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
            freshness: "edited",
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
          freshness: "replaced",
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
          freshness: "both",
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
          config: {
            column: null,
            disabled: true,
            hide_code: false,
          },
          freshness: "replaced",
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
