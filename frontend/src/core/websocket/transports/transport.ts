/* Copyright 2026 Marimo. All rights reserved. */

import type {
  NotebookTransport,
  ConnectionEvent,
  ConnectionTransportCallback,
  IConnectionTransportMap,
} from "../../host/connection";
export type {
  ConnectionEvent,
  ConnectionTransportCallback,
  IConnectionTransportMap,
} from "../../host/connection";

export interface IConnectionTransport extends NotebookTransport {
  send(data: string | ArrayBuffer | Blob | ArrayBufferView<ArrayBuffer>): void;
}

export class ConnectionSubscriptions {
  private subscriptions = new Map<
    ConnectionEvent,
    Set<ConnectionTransportCallback<ConnectionEvent>>
  >();

  public addSubscription(
    event: ConnectionEvent,
    callback: ConnectionTransportCallback<ConnectionEvent>,
  ): void {
    if (!this.subscriptions.has(event)) {
      this.subscriptions.set(event, new Set());
    }
    this.subscriptions.get(event)?.add(callback);
  }

  public removeSubscription(
    event: ConnectionEvent,
    callback: ConnectionTransportCallback<ConnectionEvent>,
  ): void {
    this.subscriptions.get(event)?.delete(callback);
  }

  public notify(
    event: ConnectionEvent,
    data: IConnectionTransportMap[ConnectionEvent],
  ): void {
    for (const callback of this.subscriptions.get(event) ?? []) {
      callback(data);
    }
  }
}
