/* Copyright 2026 Marimo. All rights reserved. */

/** The editor session's replica, following its backend while mounted. */

import type { Execution } from "@marimo-team/client/protocol";
import { consoleObservers } from "../cells/execution-console";
import { useReducerActions } from "../cells/cells";
import { useStore } from "jotai";
import { useEffect, useMemo } from "react";
import useEvent from "react-use-event-hook";
import type {
  NotificationMessage,
  NotificationPayload,
} from "../kernel/messages";
import {
  createNotebookReplica,
  type NotebookReplica,
} from "../notebook/replica";
import { activeNotebookReplicaAtom } from "./active-notebook";
import { createEditorBackend, type EditorBackendOptions } from "./backend";

type Options = EditorBackendOptions & {
  onExecution: (execution: Execution) => void;
  onNotification: (notification: NotificationPayload) => void;
};

export function useNotebookReplica(options: Options): NotebookReplica {
  const store = useStore();
  const { addLogs, startCellConsole } = useReducerActions();
  const { static: isStatic, snapshot, transportType } = options;
  const replica = useMemo(() => createNotebookReplica(store), [store]);
  const url = useEvent(options.url);
  const headers = useEvent(options.headers);
  const notebookUrl = useEvent(options.notebookUrl);
  const waitUntilReady = useEvent(options.waitUntilReady);
  const checkHealth = useEvent(options.checkHealth);
  const onExecution = useEvent(options.onExecution);
  const onNotification = useEvent(options.onNotification);
  // Opens nothing until the replica follows it.
  const backend = useMemo(
    () =>
      createEditorBackend({
        static: isStatic,
        snapshot,
        transportType,
        url,
        headers,
        notebookUrl,
        waitUntilReady,
        checkHealth,
      }),
    [
      isStatic,
      snapshot,
      transportType,
      url,
      headers,
      notebookUrl,
      waitUntilReady,
      checkHealth,
    ],
  );

  useEffect(() => {
    store.set(activeNotebookReplicaAtom, replica);
    const disconnect = replica.connect(backend, {
      ...consoleObservers({ addLogs, startCellConsole }, onExecution),
      // The host validates the envelope, not the native notification contents.
      onNotification: (notification) => {
        const data = notification as NotificationMessage;
        onNotification({ data });
      },
    });
    return () => {
      disconnect();
      if (store.get(activeNotebookReplicaAtom) === replica) {
        store.set(activeNotebookReplicaAtom, null);
      }
    };
  }, [
    replica,
    backend,
    store,
    onNotification,
    onExecution,
    addLogs,
    startCellConsole,
  ]);

  return replica;
}
