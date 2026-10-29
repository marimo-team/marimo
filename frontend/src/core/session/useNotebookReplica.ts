/* Copyright 2026 Marimo. All rights reserved. */

/** The editor session's replica, following its backend while mounted. */

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
import { notebookReplicaAtom } from "./state";
import { createEditorBackend, type EditorBackendOptions } from "./backend";

type Options = EditorBackendOptions & {
  onNotification: (notification: NotificationPayload) => void;
};

export function useNotebookReplica(options: Options): NotebookReplica {
  const store = useStore();
  const { static: isStatic, transportType } = options;
  const replica = useMemo(() => createNotebookReplica(store), [store]);
  const url = useEvent(options.url);
  const headers = useEvent(options.headers);
  const notebookUrl = useEvent(options.notebookUrl);
  const waitUntilReady = useEvent(options.waitUntilReady);
  const checkHealth = useEvent(options.checkHealth);
  const onNotification = useEvent(options.onNotification);
  // Opens nothing until the replica follows it.
  const backend = useMemo(
    () =>
      createEditorBackend({
        static: isStatic,
        transportType,
        url,
        headers,
        notebookUrl,
        waitUntilReady,
        checkHealth,
      }),
    [
      isStatic,
      transportType,
      url,
      headers,
      notebookUrl,
      waitUntilReady,
      checkHealth,
    ],
  );

  useEffect(() => {
    store.set(notebookReplicaAtom, replica);
    const disconnect = replica.connect(backend, {
      // The host validates the envelope, not the native notification contents.
      onNotification: (notification) =>
        onNotification({ data: notification as NotificationMessage }),
    });
    return () => {
      disconnect();
      if (store.get(notebookReplicaAtom) === replica) {
        store.set(notebookReplicaAtom, null);
      }
    };
  }, [replica, backend, store, onNotification]);

  return replica;
}
