/* Copyright 2024 Marimo. All rights reserved. */

/**
 * A buffer for messages that are received before the worker is ready to process them.
 * Once the worker is ready, the buffer is flushed.
 */
export class MessageBuffer<T> {
  private buffer: T[];
  private started = false;

  constructor(private onMessage: (data: T) => void) {
    this.buffer = [];
  }

  push = (data: T) => {
    if (this.started) {
      this.onMessage(data);
    } else {
      this.buffer.push(data);
    }
  };

  /**
   * Start processing messages
   */
  start = () => {
    this.started = true;
    // Flush the buffer
    this.buffer.forEach((data) => this.onMessage(data));
    this.buffer = [];
  };
}
