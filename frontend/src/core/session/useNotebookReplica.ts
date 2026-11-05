/* Copyright 2026 Marimo. All rights reserved. */

/** The editor session's replica, following its backend while mounted. */

import { useStore } from "jotai";
import { useEffect, useMemo } from "react";
import useEvent from "react-use-event-hook";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { createUIElementModel } from "../notebook/ui-elements";
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
  onNotification: (notification: NotificationPayload) => void;
};

export function useNotebookReplica(options: Options): NotebookReplica {
  const store = useStore();
  const { static: isStatic, snapshot, transportType } = options;
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
    const lifetime = new AbortController();
    const elements = createUIElementModel({ store, replica });
    elements.start({ signal: lifetime.signal });
    const disconnectFunctions = UI_ELEMENT_REGISTRY.connectFunctions((id) =>
      elements.functionRequest(id),
    );
    const disconnectElements = UI_ELEMENT_REGISTRY.connectHost({
      values: () => store.get(elements.valuesAtom),
      subscribe: (listener) => store.sub(elements.valuesAtom, listener),
      update: (id, value) => elements.update(id, value),
    });
    const disconnect = replica.connect(backend, {
      // The host validates the envelope, not the native notification contents.
      onNotification: (notification) =>
        onNotification({ data: notification as NotificationMessage }),
    });
    return () => {
      disconnectFunctions();
      disconnectElements();
      lifetime.abort();
      disconnect();
      if (store.get(activeNotebookReplicaAtom) === replica) {
        store.set(activeNotebookReplicaAtom, null);
      }
    };
  }, [replica, backend, store, onNotification]);

  return replica;
}
