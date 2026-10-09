/* Copyright 2026 Marimo. All rights reserved. */
import { ConnectionState } from "./types";

/**
 * Check if the app is in a closed/disconnected state
 */
export function isAppClosed(state: ConnectionState): boolean {
  return state === ConnectionState.CLOSED;
}

/**
 * Check if the app is in a connecting state
 */
export function isAppConnecting(state: ConnectionState): boolean {
  return state === ConnectionState.CONNECTING;
}

/**
 * Check if the app is in an open/connected state
 */
export function isAppConnected(state: ConnectionState): boolean {
  return state === ConnectionState.OPEN;
}

/**
 * Check if the app is in a closing state
 */
export function isAppClosing(state: ConnectionState): boolean {
  return state === ConnectionState.CLOSING;
}

/**
 * Check if the app is in a not started state
 */
export function isAppNotStarted(state: ConnectionState): boolean {
  return state === ConnectionState.NOT_STARTED;
}

/**
 * Check if the app is in a state where user interactions should be disabled
 */
export function isAppInteractionDisabled(state: ConnectionState): boolean {
  return (
    state === ConnectionState.CLOSED ||
    state === ConnectionState.CLOSING ||
    state === ConnectionState.CONNECTING
  );
}

/**
 * Get a human-readable tooltip message for the connection state
 */
export function getConnectionTooltip(state: ConnectionState): string {
  switch (state) {
    case ConnectionState.CLOSED:
      return "App disconnected";
    case ConnectionState.CONNECTING:
      return "Connecting to a runtime ...";
    case ConnectionState.CLOSING:
      return "App disconnecting...";
    case ConnectionState.OPEN:
      return "";
    case ConnectionState.NOT_STARTED:
      return "Click to connect to a runtime";
    default:
      return "";
  }
}
