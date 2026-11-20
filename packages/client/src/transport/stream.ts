/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import * as Protocol from "../protocol.ts";
import { type Frame, StreamStopped } from "./frame.ts";

/** An event the host sends for a kind outside the protocol, such as `marimo`. */
type ExtensionEvent<Name extends string> = Name extends unknown
  ? { readonly event: Name; readonly data: unknown; readonly id?: string }
  : never;

/**
 * An event a host stream delivers for the requested kinds.
 *
 * Each kind brings its record and removal events. `ready` and `reset` arrive
 * for every stream. A kind the protocol does not define arrives with its data
 * unvalidated.
 */
export type StreamEvent<K extends string = Protocol.ObjectTypeOutput> =
  | Extract<
      Protocol.EventOutput,
      { event: K | `${K}.removed` | "ready" | "reset" }
    >
  | ExtensionEvent<Exclude<K, Protocol.ObjectTypeOutput>>;

/** What an `EventStream` delivers and where it starts. */
export interface EventStreamOptions<
  K extends string = Protocol.ObjectTypeOutput,
> {
  /**
   * The kinds to deliver.
   *
   * Omit it to deliver every kind this stream carries. Name a kind the
   * protocol does not define, such as `marimo`, to deliver it as well.
   */
  readonly types?: readonly K[];
  /**
   * Resume after this event id instead of starting with a snapshot.
   *
   * The caller holds the state it built through that id.
   * Use the same host, stream, and type filter that produced that state.
   */
  readonly cursor?: string;
}

/** The events the protocol defines, by name. */
const PROTOCOL_EVENTS = new Set<string>(
  Protocol.Event.options.flatMap((schema) => schema.shape.event.options),
);

/** The envelope every stream event has, before its data is validated. */
const Envelope = z.object({
  event: z.string().min(1),
  data: z.unknown(),
  id: z.string().optional(),
});

/** Rethrow a listener's error without interrupting the stream. */
export function report(error: unknown): void {
  queueMicrotask(() => {
    throw error;
  });
}

/**
 * The protocol's rules for following a host stream, without a connection.
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
export class EventStream<const K extends string = Protocol.ObjectTypeOutput> {
  #cursor: string | null;
  /** Whether events since the last reset have no cursor to resume from. */
  #rebuilding = false;
  readonly #wanted: ReadonlySet<string>;
  readonly #listeners = new Set<(event: StreamEvent<K>) => void>();

  public constructor(init: EventStreamOptions<K>, kinds: readonly string[]) {
    this.#cursor = init.cursor ?? null;
    this.#wanted = new Set([
      "ready",
      "reset",
      ...(init.types ?? kinds).flatMap((kind) => {
        const removed = `${kind}.removed`;
        return PROTOCOL_EVENTS.has(removed) ? [kind, removed] : [kind];
      }),
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
  public subscribe(listener: (event: StreamEvent<K>) => void): () => void {
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
   * protocol defines is invalid. Its `cause` is the validation error. The
   * caller stops following the stream then.
   */
  public receive(message: unknown): void {
    const envelope = Envelope.safeParse(message);
    if (!envelope.success) {
      throw new StreamStopped("The host sent a message that is not an event", {
        cause: envelope.error,
      });
    }
    this.#accept(envelope.data);
  }

  #accept(frame: Frame) {
    let event: StreamEvent<string>;
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
    if (!this.#wanted.has(event.event)) {
      return;
    }
    for (const listener of this.#listeners) {
      try {
        listener(event as StreamEvent<K>);
      } catch (error) {
        report(error);
      }
    }
  }
}
