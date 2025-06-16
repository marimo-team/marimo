/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { waitFor } from "../state/jotai";
import { type ConnectionStatus, WebSocketState } from "../websocket/types";

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

export const isConnectedAtom = atom((get) => {
  const connection = get(connectionAtom);
  return connection.state === WebSocketState.OPEN;
});
