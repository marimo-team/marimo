/* Copyright 2026 Marimo. All rights reserved. */

import { useStore } from "jotai";
import { useEffect, useMemo } from "react";
import useEvent from "react-use-event-hook";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import type {
  NotificationMessage,
  NotificationPayload,
} from "../kernel/messages";
import {
  createNotebookClient,
  type NotebookClient,
} from "../host/notebook-client";
import { classifyCloseEvent } from "./connection-state";
import { notebookClientAtom } from "./state";
import {
  createConnectionTransport,
  type ConnectionTransportOptions,
} from "./transports/create";

type Options = ConnectionTransportOptions & {
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
      createTransport: (url) =>
        createConnectionTransport({
          url,
          headers,
          static: isStatic,
          transportType,
        }),
      url,
      signal: lifetime.signal,
      waitUntilReady,
      checkHealth,
      // The host validates the envelope, not the native notification contents.
      onNotification: (notification) =>
        onNotification({ data: notification as NotificationMessage }),
      decodeJson: jsonParseWithSpecialChar,
      classifyClose: classifyCloseEvent,
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
