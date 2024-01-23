/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { ConnectionStatus, WebSocketState } from "../websocket/types";

/**
 * Atom for storing the connection status.
 * Initialized to CONNECTING.
 */
export const connectionAtom = atom<ConnectionStatus>({
  state: WebSocketState.CONNECTING,
});
