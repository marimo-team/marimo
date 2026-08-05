/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import { isNotebookPage } from "../mode";
import { waitFor } from "../state/jotai";
import { type ConnectionStatus, WebSocketState } from "../websocket/types";

/**
 * Atom for storing the connection status.
 * Initialized to NOT_STARTED.
 */
export const connectionAtom = atom<ConnectionStatus>({
  state: WebSocketState.NOT_STARTED,
});

export function waitForConnectionOpen() {
  return waitFor(connectionAtom, (value) => {
    return value.state === WebSocketState.OPEN;
  });
}

/**
 * Waits for the kernel connection, but only on pages that open one. Non-notebook
 * pages (home, gallery) never connect, so waiting there would hang forever.
 *
 * Use for requests that the marimo server can serve without a session, but that
 * should still wait for the kernel when a notebook is open.
 */
export function waitForConnectionOpenIfNotebook() {
  if (!isNotebookPage()) {
    return Promise.resolve();
  }
  return waitForConnectionOpen();
}

export const isConnectingAtom = atom((get) => {
  const connection = get(connectionAtom);
  return connection.state === WebSocketState.CONNECTING;
});

export const isConnectedAtom = atom((get) => {
  const connection = get(connectionAtom);
  return connection.state === WebSocketState.OPEN;
});

export const canInteractWithAppAtom = atom((get) => {
  const connection = get(connectionAtom);
  return (
    connection.state === WebSocketState.OPEN ||
    connection.state === WebSocketState.NOT_STARTED
  );
});

export const isClosedAtom = atom((get) => {
  const connection = get(connectionAtom);
  return connection.state === WebSocketState.CLOSED;
});

export const isNotStartedAtom = atom((get) => {
  const connection = get(connectionAtom);
  return connection.state === WebSocketState.NOT_STARTED;
});
