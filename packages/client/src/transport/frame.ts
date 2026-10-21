/* Copyright 2026 Marimo. All rights reserved. */

/** One event of a host stream, before validation. */
export interface Frame {
  readonly event: string;
  readonly data: unknown;
  readonly id?: string;
}

/** Whether a decoded message has the shape of a stream event. */
export function isFrame(value: unknown): value is Frame {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const { event, id } = value as Record<string, unknown>;
  return (
    typeof event === "string" &&
    event !== "" &&
    (id === undefined || typeof id === "string")
  );
}

/**
 * A stream stopped and will not reconnect.
 *
 * `cause` says why when there is more to say.
 *
 * - The host refused the stream. `cause` is the `Problem` it answered with.
 * - The host sent an invalid event. `cause` is the validation error.
 * - The host could not be reached after repeated attempts. `cause` is
 *   undefined.
 * - A custom transport decided to stop. `cause` is whatever it passed.
 */
export class StreamStopped extends Error {
  public override readonly name = "StreamStopped";
}

/** Where one connection of a host stream starts. */
export interface Attempt {
  /** Where to resume, or null to start with a snapshot. */
  readonly cursor: string | null;
  /** Aborted when the stream closes. The transport closes its connection. */
  readonly signal: AbortSignal;
}

/** What a transport reports while its connection is open. */
export interface Handlers {
  /** The connection is established. */
  open(): void;
  /** One decoded message, not yet validated. */
  message(message: unknown): void;
}

/**
 * Open one connection to a host stream and report it until it ends.
 *
 * The event stream calls it again for each attempt. It resolves when the
 * connection ended and another attempt makes sense. It rejects when the
 * stream should stop, preferably with a `StreamStopped` that says why, and
 * `closed` rejects with the same error. It sends the cursor however its host
 * expects, and leaves reconnecting, validation, and the cursor's value to
 * the event stream.
 */
export type Transport = (attempt: Attempt, handlers: Handlers) => Promise<void>;

/** A custom transport for a notebook stream. */
export type NotebookTransport = Transport;
