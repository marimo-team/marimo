/* Copyright 2026 Marimo. All rights reserved. */

import type { Execution } from "@marimo-team/client/protocol";
import type { Getter } from "jotai";
import type { ReducerCellActions } from "./cells";
import {
  itemsInOrder,
  type NotebookReplica,
  type Execution as ReplicaExecution,
  type Item,
} from "../notebook/replica";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import { activeNotebookReplicaAtom } from "../session/active-notebook";
import type { OutputMessage } from "../kernel/messages";
import {
  collapseConsoleBatch,
  collapseConsoleOutputs,
} from "./collapseConsoleOutputs";
import { getCellLogsForMessage } from "./logs";
import { EMBEDDED } from "./session";
import { SCRATCH_CELL_ID, type CellId } from "./ids";
import type {
  CellRuntimeState,
  CellRuntimeView,
  ConsoleOutputMessage,
} from "./types";

function consoleEntry(
  item: Item,
  fallback: number,
  code?: string,
): ConsoleOutputMessage {
  const timestamp =
    item.time === undefined ? fallback : Date.parse(item.time) / 1000;
  const id = item.seq + 1;
  switch (item.kind) {
    case "console":
      return {
        id,
        channel: item.name,
        data: item.text,
        mimetype: "text/plain",
        timestamp,
      };
    case "display":
      return {
        id,
        channel:
          item.content.mimetype === "application/vnd.marimo+traceback"
            ? "stderr"
            : "media",
        mimetype: item.content.mimetype as OutputMessage["mimetype"],
        data: item.content.data,
        code:
          item.content.mimetype === "application/vnd.marimo+traceback"
            ? code
            : undefined,
        timestamp,
      };
    case "input":
      return {
        id,
        channel: "stdin",
        mimetype: item.password ? "text/password" : "text/plain",
        input_id: item.id,
        data: item.prompt,
        timestamp,
        response: item.status === "pending" ? undefined : null,
      };
  }
}

/** Side effects of notebook events shared by the editor and islands. */
export function consoleObservers(
  actions: Pick<ReducerCellActions, "addLogs" | "startCellConsole">,
  onExecution?: (record: Execution) => void,
): Pick<Parameters<NotebookReplica["connect"]>[1], "onExecution" | "onItem"> {
  return {
    onExecution(record, changed) {
      VirtualFileTracker.INSTANCE.trackExecution(record);
      if (changed) {
        if (record.status === "running") {
          actions.startCellConsole({
            cellId: (record.cell_id ?? SCRATCH_CELL_ID) as CellId,
          });
        }
        onExecution?.(record);
      }
    },
    onItem(record, item, live) {
      const cellId = (record.cell_id ?? SCRATCH_CELL_ID) as CellId;
      const output = consoleEntry(
        item,
        record.started_at ? Date.parse(record.started_at) / 1000 : 0,
      );
      if (output.channel === "media") {
        VirtualFileTracker.INSTANCE.track({ cell_id: cellId, output });
      }
      if (live && (item.kind === "console" || output.channel === "stderr")) {
        actions.addLogs({
          logs: getCellLogsForMessage({ cell_id: cellId, console: output }),
        });
      }
    },
  };
}

export function consoleExecution(get: Getter, cellId: CellId) {
  const replica = get(activeNotebookReplicaAtom);
  if (!replica) {
    return;
  }
  const state = get(replica.executionsAtom);
  if (cellId === SCRATCH_CELL_ID) {
    return state.scratchConsole;
  }
  const id = state.latest.get(cellId);
  return id === undefined ? undefined : state.executions.get(id);
}

interface ConsoleInputs {
  local: CellRuntimeState;
  execution: ReplicaExecution | undefined;
  code: string | undefined;
}

interface ConsoleView extends ConsoleInputs {
  rendered: CellRuntimeView;
}

/** Project the retained items and the editor's local transcript onto visible rows. */
export function consoleView(
  inputs: ConsoleInputs,
  previous?: ConsoleView,
): ConsoleView {
  const { local, execution, code } = inputs;
  if (
    previous &&
    previous.local === local &&
    previous.code === code &&
    previous.execution?.items === execution?.items
  ) {
    return previous;
  }

  const record = execution?.record;
  const cleared = local.clearedConsole;
  const hidden = local.clearedConsoleInputs;
  const fallback = record?.started_at
    ? Date.parse(record.started_at) / 1000
    : 0;
  const project = (item: Item) => {
    if (
      cleared &&
      cleared.executionId === record?.id &&
      item.seq <= cleared.seq &&
      !(item.kind === "input" && cleared.prompts.has(item.id))
    ) {
      return;
    }
    if (
      item.kind === "input" &&
      hidden?.executionId === item.execution_id &&
      hidden.ids.has(item.id)
    ) {
      return;
    }
    const entry = consoleEntry(item, fallback, code);
    if (
      item.kind === "input" &&
      !item.password &&
      local.answers?.has(item.id)
    ) {
      entry.response = local.answers.get(item.id);
    }
    return entry;
  };
  const commands = local.commandConsole?.entries;
  const append = execution?.append;
  if (
    previous &&
    previous.local === local &&
    previous.code === code &&
    previous.execution &&
    append &&
    append.before.deref() === previous.execution.items &&
    (!commands?.length ||
      commands.every(
        (entry) =>
          entry.afterSeq !== undefined && entry.afterSeq < append.item.seq,
      ))
  ) {
    const added = project(append.item);
    const rows = previous.rendered.consoleOutputs;
    return {
      ...inputs,
      rendered: {
        serialization: local.serialization,
        consoleOutputs: added ? collapseConsoleOutputs([...rows, added]) : rows,
      },
    };
  }

  let entries =
    !execution || (record?.runtime_id === EMBEDDED && !execution.items.size)
      ? local.embeddedConsole
      : itemsInOrder(execution).flatMap((item) => project(item) ?? []);
  if (commands?.length) {
    const anchored =
      commands.every((entry) => entry.afterSeq !== undefined) &&
      entries.every((entry) => entry.id !== undefined);
    const position = (entry: ConsoleOutputMessage & { afterSeq?: number }) =>
      entry.afterSeq === undefined ? (entry.id ?? 0) : entry.afterSeq + 1.5;
    entries = [
      ...entries,
      ...commands.map((entry, index) => ({ ...entry, id: -1 - index })),
    ].toSorted(
      (a, b) =>
        (anchored ? position(a) - position(b) : 0) ||
        (a.timestamp ?? 0) - (b.timestamp ?? 0),
    );
  }
  return {
    ...inputs,
    rendered: {
      serialization: local.serialization,
      consoleOutputs: collapseConsoleBatch(entries),
    },
  };
}
