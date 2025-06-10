/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketState } from "./types";

/**
 * Check if the app is in a closed/disconnected state
 */
export function isAppClosed(state: WebSocketState): boolean {
  return state === WebSocketState.CLOSED;
}

/**
 * Check if the app is in a connecting state
 */
export function isAppConnecting(state: WebSocketState): boolean {
  return state === WebSocketState.CONNECTING;
}

/**
 * Check if the app is in an open/connected state
 */
export function isAppConnected(state: WebSocketState): boolean {
  return state === WebSocketState.OPEN;
}

/**
 * Check if the app is in a closing state
 */
export function isAppClosing(state: WebSocketState): boolean {
  return state === WebSocketState.CLOSING;
}

/**
 * Check if the app is in a state where user interactions should be disabled
 */
export function isAppInteractionDisabled(state: WebSocketState): boolean {
  return (
    state === WebSocketState.CLOSED ||
    state === WebSocketState.CLOSING ||
    state === WebSocketState.CONNECTING
  );
}

/**
 * Get a human-readable tooltip message for the connection state
 */
export function getConnectionTooltip(state: WebSocketState): string {
  switch (state) {
    case WebSocketState.CLOSED:
      return "App disconnected";
    case WebSocketState.CONNECTING:
      return "App connecting...";
    case WebSocketState.CLOSING:
      return "App disconnecting...";
    case WebSocketState.OPEN:
      return "";
    default:
      return "";
  }
}
