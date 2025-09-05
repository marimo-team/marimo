/* Copyright 2024 Marimo. All rights reserved. */

import type { Meta } from "@storybook/react-vite";
import { createStore, Provider } from "jotai";
import { createRef } from "react";
import { type NotebookState, notebookAtom } from "@/core/cells/cells";
import { createCellRuntimeState } from "@/core/cells/types";
import { defaultUserConfig, parseAppConfig } from "@/core/config/config-schema";
import { showCodeInRunModeAtom } from "@/core/meta/state";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { resolveRequestClient } from "@/core/network/resolve.ts";
import { WebSocketState } from "@/core/websocket/types";
import { MultiColumn } from "@/utils/id-tree";
import type { Milliseconds, Seconds } from "@/utils/time";
import { CellArray } from "../../../components/editor/renderers/CellArray";
import { CellsRenderer } from "../../../components/editor/renderers/cells-renderer";
import { TooltipProvider } from "../../../components/ui/tooltip";
import type { CellId } from "../../../core/cells/ids";

const createLongReprNotebook = (
  cellId: CellId,
  hideCode = false,
): NotebookState => ({
  cellData: {
    [cellId]: {
      id: cellId,
      name: "_",
      code: `class LongReprA:
    def __repr__(self):
        return "<dlt.Relation(dataset='" + ("jaffle_ingest_dataset_" * 80) + \\
            "', destination='<dlt.destinations.duckdb(destination_type=\\'duckdb\\'," + \\
            " credentials=\\'local_jaffle.duckdb\\')>')>"

print('hello')
LongReprA()`,
      edited: false,
      serializedEditorState: null,
      config: {
        hide_code: hideCode,
        disabled: false,
        column: null,
      },
      lastCodeRun: `class LongReprA:
    def __repr__(self):
        return "<dlt.Relation(dataset='" + ("jaffle_ingest_dataset_" * 80) + \\
            "', destination='<dlt.destinations.duckdb(destination_type=\\'duckdb\\'," + \\
            " credentials=\\'local_jaffle.duckdb\\')>')>"

print('hello')
LongReprA()`,
      lastExecutionTime: null,
    },
  },
  cellIds: MultiColumn.from([[cellId]]),
  cellRuntime: {
    [cellId]: createCellRuntimeState({
      output: {
        channel: "output",
        data: "<dlt.Relation(dataset='jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_jaffle_ingest_dataset_', destination='<dlt.destinations.duckdb(destination_type='duckdb', credentials='local_jaffle.duckdb')>')>",
        mimetype: "text/plain",
        timestamp: 1_686_863_710,
      },
      runElapsedTimeMs: 8 as Milliseconds,
      status: "idle",
      consoleOutputs: [
        {
          channel: "stdout",
          mimetype: "text/plain",
          data: "hello",
          timestamp: 1_686_863_705,
        },
      ],
      interrupted: false,
      errored: false,
      stopped: false,
      staleInputs: false,
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
});

export default {
  title: "Layout/Vertical/One Column",
  component: CellsRenderer,
  args: {},
} satisfies Meta<typeof CellsRenderer>;

type W = Window & { __MARIMO_STATIC__?: { files: Record<string, unknown> } };

const EditModeCodeShown = () => {
  const cellId = "Hbol" as CellId;
  const notebook = createLongReprNotebook(cellId);

  const store = createStore();
  store.set(notebookAtom, notebook);
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(requestClientAtom, resolveRequestClient());
  store.set(showCodeInRunModeAtom, true);

  return (
    <Provider store={store}>
      <TooltipProvider>
        <CellsRenderer appConfig={parseAppConfig({})} mode="edit">
          <CellArray
            mode="edit"
            userConfig={defaultUserConfig()}
            appConfig={parseAppConfig({})}
          />
        </CellsRenderer>
      </TooltipProvider>
    </Provider>
  );
};

const EditModeCodeHidden = () => {
  const cellId = "Hbol" as CellId;
  const notebook = createLongReprNotebook(cellId, true);

  const store = createStore();
  store.set(notebookAtom, notebook);
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(requestClientAtom, resolveRequestClient());
  store.set(showCodeInRunModeAtom, true);

  return (
    <Provider store={store}>
      <TooltipProvider>
        <CellsRenderer appConfig={parseAppConfig({})} mode="edit">
          <CellArray
            mode="edit"
            userConfig={defaultUserConfig()}
            appConfig={parseAppConfig({})}
          />
        </CellsRenderer>
      </TooltipProvider>
    </Provider>
  );
};

const ReadModeCodeShown = () => {
  const cellId = "Hbol" as CellId;
  const notebook = createLongReprNotebook(cellId);

  const store = createStore();
  store.set(notebookAtom, notebook);
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(requestClientAtom, resolveRequestClient());
  store.set(showCodeInRunModeAtom, true);

  return (
    <Provider store={store}>
      <TooltipProvider>
        <CellsRenderer appConfig={parseAppConfig({})} mode="read" />
      </TooltipProvider>
    </Provider>
  );
};

const ReadModeCodeHidden = () => {
  const cellId = "Hbol" as CellId;
  const notebook = createLongReprNotebook(cellId);

  const store = createStore();
  store.set(notebookAtom, notebook);
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(requestClientAtom, resolveRequestClient());
  store.set(showCodeInRunModeAtom, true);

  return (
    <Provider store={store}>
      <TooltipProvider>
        <CellsRenderer appConfig={parseAppConfig({})} mode="read" />
      </TooltipProvider>
    </Provider>
  );
};

export const EditModeCodeShownStory = {
  render: () => <EditModeCodeShown />,
  name: "Edit Mode - Code Shown",
};
export const EditModeCodeHiddenStory = {
  render: () => <EditModeCodeHidden />,
  name: "Edit Mode - Code Hidden",
};
export const ReadModeCodeShownStory = {
  render: () => {
    if (typeof window !== "undefined") {
      (window as W).__MARIMO_STATIC__ = { files: {} };
    }

    return <ReadModeCodeShown />;
  },
  name: "Read Mode - Code Shown",
};
export const ReadModeCodeHiddenStory = {
  render: () => {
    if (typeof window !== "undefined") {
      delete (window as W).__MARIMO_STATIC__;
    }
    return <ReadModeCodeHidden />;
  },
  name: "Read Mode - Code Hidden",
};
