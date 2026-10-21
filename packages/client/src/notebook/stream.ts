/* Copyright 2026 Marimo. All rights reserved. */

import * as Protocol from "../protocol.ts";
import type { Kind } from "../reducer.ts";
import { type Frame, isFrame, StreamStopped } from "../transport/frame.ts";

/** An event the host sends for a kind outside the protocol, such as `marimo`. */
type ExtensionEvent<Name extends string> = Name extends unknown
  ? { readonly event: Name; readonly data: unknown; readonly id?: string }
  : never;

/**
 * An event a notebook stream delivers for the requested kinds.
 *
 * Each kind brings its record and removal events. `ready` and `reset` arrive
 * for every stream. A kind the protocol does not define arrives with its data
 * unvalidated.
 */
export type NotebookEvent<K extends string = Kind> =
  | Extract<
      Protocol.EventOutput,
      { event: K | `${K}.removed` | "ready" | "reset" }
    >
  | ExtensionEvent<Exclude<K, Protocol.ObjectTypeOutput>>;

/** What a `NotebookStream` delivers and where it starts. */
export interface NotebookStreamInit<K extends string = Kind> {
  /**
   * The kinds to deliver.
   *
   * Omit it to deliver every kind the protocol defines. Name a kind the
   * protocol does not define, such as `marimo`, to deliver it as well.
   */
  readonly types?: readonly K[];
  /**
   * Resume after this event id instead of starting with a snapshot.
   *
   * The caller holds the state it built through that id.
   */
  readonly cursor?: string;
}

/** The events the protocol defines, by name. */
const PROTOCOL_EVENTS = new Set<string>(
  Protocol.Event.options.flatMap((schema) => schema.shape.event.options),
);

/** Rethrow a listener's error without interrupting the stream. */
export function report(error: unknown): void {
  queueMicrotask(() => {
    throw error;
  });
}

/**
 * The protocol's rules for following a notebook stream, without a connection.
 *
 * A connection calls `resume()` when it starts, to learn the cursor to send,
 * and `receive()` with each message. The stream validates events, tracks the
 * cursor, and delivers the requested kinds in order.
 *
 * - A stream starts with a snapshot that ends in `ready`, then delivers
 *   changes.
 * - `reset` means the caller discards what it built. A fresh snapshot follows.
 *   The stream delivers `reset` itself when a snapshot was cut short, because
 *   a new snapshot replaces the incomplete one.
 * - Kinds that were not requested keep their place in the stream without
 *   being delivered.
 */
export class NotebookStream<const K extends string = Kind> {
  #cursor: string | null;
  /** Whether events since the last reset have no cursor to resume from. */
  #rebuilding = false;
  readonly #wanted: ReadonlySet<string> | null;
  readonly #listeners = new Set<(event: NotebookEvent<K>) => void>();

  public constructor(init: NotebookStreamInit<K> = {}) {
    this.#cursor = init.cursor ?? null;
    this.#wanted =
      init.types === undefined
        ? null
        : new Set([
            "ready",
            "reset",
            ...init.types.flatMap((kind) => [kind, `${kind}.removed`]),
          ]);
  }

  /**
   * The id of the last event the stream received.
   *
   * Null during a snapshot and after `reset`.
   */
  public get cursor(): string | null {
    return this.#cursor;
  }

  /**
   * Call `listener` with each event, in order.
   *
   * Returns a function that stops calling it. A listener that throws does not
   * interrupt the stream.
   */
  public subscribe(listener: (event: NotebookEvent<K>) => void): () => void {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }

  /**
   * Prepare for a new connection and return the cursor to send.
   *
   * Delivers `reset` first when the last snapshot was cut short.
   */
  public resume(): string | null {
    if (this.#cursor === null && this.#rebuilding) {
      this.#accept({ event: "reset", data: {} });
    }
    return this.#cursor;
  }

  /**
   * Accept one message from the connection.
   *
   * Throws `StreamStopped` when the message is not an event or an event the
   * protocol defines is invalid. The caller stops following the stream then.
   */
  public receive(message: unknown): void {
    if (!isFrame(message)) {
      throw new StreamStopped("The host sent a message that is not an event");
    }
    this.#accept(message);
  }

  #accept(frame: Frame) {
    let event: NotebookEvent<string>;
    if (PROTOCOL_EVENTS.has(frame.event)) {
      const parsed = Protocol.Event.safeParse(frame);
      if (!parsed.success) {
        throw new StreamStopped(
          `The host sent an invalid ${frame.event} event`,
          { cause: parsed.error },
        );
      }
      event = parsed.data;
    } else {
      event = frame as ExtensionEvent<string>;
    }
    if (frame.id !== undefined) {
      this.#cursor = frame.id;
    }
    if (event.event === "reset") {
      this.#cursor = null;
      this.#rebuilding = false;
    } else if (this.#cursor === null) {
      this.#rebuilding = true;
    }
    const wanted =
      this.#wanted === null
        ? PROTOCOL_EVENTS.has(event.event)
        : this.#wanted.has(event.event);
    if (!wanted) {
      return;
    }
    for (const listener of this.#listeners) {
      try {
        listener(event as NotebookEvent<K>);
      } catch (error) {
        report(error);
      }
    }
  }
}
