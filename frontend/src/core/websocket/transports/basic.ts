/* Copyright 2026 Marimo. All rights reserved. */

import {
  type ConnectionEvent,
  ConnectionSubscriptions,
  type ConnectionTransportCallback,
  type IConnectionTransport,
} from "./transport";

type MessageProducer = (callback: (message: MessageEvent) => void) => void;

export class BasicTransport implements IConnectionTransport {
  private subscriptions = new ConnectionSubscriptions();
  private producer?: MessageProducer;

  static withProducerCallback(producer: MessageProducer): IConnectionTransport {
    return new BasicTransport(producer);
  }

  static empty(): IConnectionTransport {
    return new BasicTransport();
  }

  private constructor(producer?: MessageProducer) {
    this.producer = producer;
  }

  private startProducer() {
    if (this.producer) {
      this.producer((message) => {
        this.subscriptions.notify("message", message);
      });
    }
  }

  private connect(): Promise<void> {
    return new Promise<void>((resolve) => setTimeout(resolve, 0)).then(() => {
      this.subscriptions.notify("open", new Event("open"));
    });
  }

  get readyState(): WebSocket["readyState"] {
    return WebSocket.OPEN;
  }

  reconnect(code?: number | undefined, reason?: string | undefined): void {
    this.close();
    this.connect();
    return;
  }

  close(): void {
    this.subscriptions.notify("close", new Event("close"));
  }

  send(data: string | ArrayBuffer | Blob | ArrayBufferView): Promise<void> {
    this.subscriptions.notify(
      "message",
      new MessageEvent("message", {
        data,
      }),
    );
    return Promise.resolve();
  }

  addEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void {
    this.subscriptions.addSubscription(
      event,
      callback as ConnectionTransportCallback<ConnectionEvent>,
    );

    // Call open right away
    if (event === "open") {
      (callback as ConnectionTransportCallback<"open">)(new Event("open"));
    }

    // Start the producer when we have one consumer
    if (event === "message") {
      this.startProducer();
    }
  }

  removeEventListener<T extends ConnectionEvent>(
    event: T,
    callback: ConnectionTransportCallback<T>,
  ): void {
    this.subscriptions.removeSubscription(
      event,
      callback as ConnectionTransportCallback<ConnectionEvent>,
    );
  }
}
