/* Copyright 2023 Marimo. All rights reserved. */
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

import { useEffect } from "react";
import { bind } from "./bridge/jotai";
import { notebookAtom } from "../cells/cells";
import { store } from "../state/jotai";

/**
 * The Yjs document, used to store the shared state of the document.
 */
export const ydoc = new Y.Doc();

function createWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  return process.env.NODE_ENV === "production"
    ? `${protocol}://${window.location.host}`
    : `ws://localhost:1234`;
}

export const provider = new WebsocketProvider(createWsUrl(), "rtc", ydoc, {
  connect: false,
});

/**
 * React to enable real-time collaboration.
 */
export function useRealTimeCollaboration(opts: { enabled: boolean }) {
  useEffect(() => {
    if (!opts.enabled) {
      return;
    }

    provider.connect();
    const unbind = bind(ydoc, store, notebookAtom, ["cellIds", "cellData"]);

    return () => {
      provider.disconnect();
      unbind();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
