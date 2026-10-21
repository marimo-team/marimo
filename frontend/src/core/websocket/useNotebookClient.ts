/* Copyright 2026 Marimo. All rights reserved. */

import { StreamStopped } from "@marimo-team/client";
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
import {
  createNotebookTransport,
  type NotebookTransportOptions,
} from "./transports/notebook";

type Options = Omit<NotebookTransportOptions, "url"> & {
  /** The session route, read before each connection. */
  url: () => string;
  /** Wait until the host can accept a connection. */
  waitUntilReady: () => Promise<void>;
  checkHealth: () => Promise<boolean>;
  onNotification: (notification: NotificationPayload) => void;
};

export function useNotebookClient(options: Options): NotebookClient {
  const store = useStore();
  const { static: isStatic, transportType } = options;
  const controller = useMemo(() => createNotebookClient(store), [store]);
  const url = useEvent(options.url);
  const headers = useEvent(options.headers);
  const waitUntilReady = useEvent(options.waitUntilReady);
  const checkHealth = useEvent(options.checkHealth);
  const onNotification = useEvent(options.onNotification);

  useEffect(() => {
    const lifetime = new AbortController();
    store.set(notebookClientAtom, controller.client);
    controller.connect({
      transport: createNotebookTransport({
        static: isStatic,
        transportType,
        url: async () => {
          try {
            await waitUntilReady();
          } catch (error) {
            // Shown as a disconnected kernel, like a host that cannot be reached.
            throw new StreamStopped("Healthy connection never made", {
              cause: error,
            });
          }
          return url();
        },
        headers,
      }),
      signal: lifetime.signal,
      checkHealth,
      // The host validates the envelope, not the native notification contents.
      onNotification: (notification) =>
        onNotification({ data: notification as NotificationMessage }),
    });
    return () => {
      lifetime.abort();
      if (store.get(notebookClientAtom) === controller.client) {
        store.set(notebookClientAtom, null);
      }
    };
  }, [
    controller,
    store,
    isStatic,
    transportType,
    url,
    headers,
    waitUntilReady,
    checkHealth,
    onNotification,
  ]);

  return controller.client;
}
