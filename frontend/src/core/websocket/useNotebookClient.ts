/* Copyright 2026 Marimo. All rights reserved. */

import { useStore } from "jotai";
import { useEffect, useMemo } from "react";
import useEvent from "react-use-event-hook";
import type {
  NotificationMessage,
  NotificationPayload,
} from "../kernel/messages";
import {
  createNotebookClient,
  type NotebookClient,
} from "../host/notebook-client";
import { notebookClientAtom } from "./state";
import { createEditorBackend, type EditorBackendOptions } from "./backend";

type Options = EditorBackendOptions & {
  onNotification: (notification: NotificationPayload) => void;
};

export function useNotebookClient(options: Options): NotebookClient {
  const store = useStore();
  const { static: isStatic, transportType } = options;
  const client = useMemo(() => createNotebookClient(store), [store]);
  const url = useEvent(options.url);
  const headers = useEvent(options.headers);
  const notebookUrl = useEvent(options.notebookUrl);
  const waitUntilReady = useEvent(options.waitUntilReady);
  const checkHealth = useEvent(options.checkHealth);
  const onNotification = useEvent(options.onNotification);
  // Opens nothing until the client follows it.
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
    store.set(notebookClientAtom, client);
    const disconnect = client.connect(backend, {
      // The host validates the envelope, not the native notification contents.
      onNotification: (notification) =>
        onNotification({ data: notification as NotificationMessage }),
    });
    return () => {
      disconnect();
      if (store.get(notebookClientAtom) === client) {
        store.set(notebookClientAtom, null);
      }
    };
  }, [client, backend, store, onNotification]);

  return client;
}
