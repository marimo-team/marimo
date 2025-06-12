/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { type ConnectionStatus, WebSocketState } from "../websocket/types";
import { waitFor } from "../state/jotai";

/**
 * Atom for storing the connection status.
 * Initialized to CONNECTING.
 */
export const connectionAtom = atom<ConnectionStatus>({
  state: WebSocketState.CONNECTING,
});

export function waitForConnectionOpen() {
  return waitFor(connectionAtom, (value) => {
    return value.state === WebSocketState.OPEN;
  });
}

export const isConnectingAtom = atom((get) => {
  const connection = get(connectionAtom);
  return connection.state === WebSocketState.CONNECTING;
});
