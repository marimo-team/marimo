/* Copyright 2026 Marimo. All rights reserved. */
export type ConnectionEvent = "open" | "close" | "message" | "error";

export interface IConnectionTransportMap {
  open: WebSocketEventMap["open"];
  message: WebSocketEventMap["message"];
  close: WebSocketEventMap["close"];
  error: WebSocketEventMap["error"];
}

export type ConnectionTransportCallback<T extends ConnectionEvent> = (
  data: IConnectionTransportMap[T],
) => void;

export interface IConnectionTransport {
  reconnect(code?: number | undefined, reason?: string | undefined): void;
  close(): void;
  send(data: string | ArrayBuffer | Blob | ArrayBufferView): void;
  addEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void;
  removeEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void;
  readyState: WebSocket["readyState"];
}

export class ConnectionSubscriptions {
  private subscriptions = new Map<
    ConnectionEvent,
    Set<ConnectionTransportCallback<ConnectionEvent>>
  >();

  addSubscription(
    event: ConnectionEvent,
    callback: ConnectionTransportCallback<ConnectionEvent>,
  ): void {
    if (!this.subscriptions.has(event)) {
      this.subscriptions.set(event, new Set());
    }
    this.subscriptions.get(event)?.add(callback);
  }

  removeSubscription(
    event: ConnectionEvent,
    callback: ConnectionTransportCallback<ConnectionEvent>,
  ): void {
    this.subscriptions.get(event)?.delete(callback);
  }

  notify(
    event: ConnectionEvent,
    data: IConnectionTransportMap[ConnectionEvent],
  ): void {
    for (const callback of this.subscriptions.get(event) ?? []) {
      callback(data);
    }
  }
}
