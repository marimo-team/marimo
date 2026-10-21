/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "../protocol.ts";
import type { Kind } from "../reducer.ts";
import type { Connection } from "../request.ts";
import { type NotebookTransport, StreamStopped } from "../transport/frame.ts";
import { sse } from "../transport/sse.ts";
import {
  type NotebookEvent,
  NotebookStream,
  type NotebookStreamInit,
  report,
} from "./stream.ts";

/** Attempts in a row without an event before the stream gives up. */
const ATTEMPTS = 10;

/** The delay before reconnecting, which grows with each attempt in a row. */
function delay(attempt: number): number {
  return Math.min(1000 * 1.3 ** attempt, 10_000);
}

/** Whether a stream is receiving events. */
type Status = "connecting" | "connected" | "closed";

/** How a `NotebookEvents` reaches its host and what it follows. */
export interface NotebookEventsInit<K extends string = Kind>
  extends Connection, NotebookStreamInit<K> {
  /**
   * Follow one run instead of the whole notebook.
   *
   * Applies to a stream at a URL. A transport filters its own requests.
   */
  readonly runId?: Protocol.RunId;
  /** Aborting closes the stream. */
  readonly signal?: AbortSignal;
  /**
   * Called when `status` changes.
   *
   * Reconnecting shows as `connecting` after `connected`.
   */
  readonly onStatus?: (status: Status) => void;
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(done, ms);
    signal.addEventListener("abort", done, { once: true });
    function done() {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    }
  });
}

/**
 * A notebook stream, followed across reconnects.
 *
 * Given a URL, it follows the stream there over server-sent events. Given a
 * `NotebookTransport`, it follows whatever connection the transport opens.
 *
 * - It starts with a snapshot that ends in `ready`, then delivers changes.
 * - After a dropped connection it resumes from its cursor, backing off between
 *   attempts. It stops after ten attempts in a row without a message.
 * - When it cannot resume, it delivers `reset` and a fresh snapshot follows.
 *   The caller discards what it built on `reset`.
 */
export class NotebookEvents<
  const K extends string = Kind,
> implements AsyncIterable<NotebookEvent<K>> {
  /**
   * Settles when the stream closes.
   *
   * Resolves after `close()` or an abort. Rejects with `StreamStopped` when
   * the host refuses the stream, sends an invalid event, or cannot be reached.
   */
  public readonly closed: Promise<void>;
  readonly #stream: NotebookStream<K>;
  #status: Status = "connecting";
  readonly #controller = new AbortController();
  readonly #onStatus: ((status: Status) => void) | undefined;
  #settle: { resolve(): void; reject(error: unknown): void } | undefined;
  #release: (() => void) | undefined;

  public constructor(
    source: string | URL | NotebookTransport,
    init: NotebookEventsInit<K> = {},
  ) {
    let transport: NotebookTransport;
    if (typeof source === "function") {
      transport = source;
    } else {
      const url = new URL(source);
      if (init.types !== undefined) {
        url.searchParams.set("types", init.types.join(","));
      }
      if (init.runId !== undefined) {
        url.searchParams.set("run_id", init.runId);
      }
      transport = sse(url, init);
    }
    this.#stream = new NotebookStream<K>({
      types: init.types,
      cursor: init.cursor,
    });
    this.#onStatus = init.onStatus;
    this.closed = new Promise((resolve, reject) => {
      this.#settle = { resolve, reject };
    });
    // A caller that never awaits `closed` should not see an unhandled rejection.
    this.closed.catch(() => undefined);
    if (init.signal?.aborted) {
      this.close();
      return;
    }
    const signal = init.signal;
    if (signal !== undefined) {
      const abort = () => this.close();
      signal.addEventListener("abort", abort, { once: true });
      this.#release = () => signal.removeEventListener("abort", abort);
    }
    void this.#run(transport);
  }

  /** Whether the stream is receiving events. */
  public get status(): Status {
    return this.#status;
  }

  /**
   * The id of the last event the stream received.
   *
   * Null during a snapshot and after `reset`.
   */
  public get cursor(): string | null {
    return this.#stream.cursor;
  }

  /**
   * Call `listener` with each event, in order.
   *
   * Returns a function that stops calling it. A listener that throws does not
   * interrupt the stream.
   */
  public subscribe(listener: (event: NotebookEvent<K>) => void): () => void {
    return this.#stream.subscribe(listener);
  }

  /** Stop following the stream. */
  public close(): void {
    this.#finish()?.resolve();
  }

  /**
   * Iterate over events until the stream closes.
   *
   * Leaving the loop early closes the stream.
   */
  public [Symbol.asyncIterator](): AsyncIterator<NotebookEvent<K>> {
    const queue: NotebookEvent<K>[] = [];
    const waiting: (() => void)[] = [];
    const wake = () => waiting.splice(0).forEach((resolve) => resolve());
    let ended: { error?: unknown } | undefined;
    const unsubscribe = this.subscribe((event) => {
      queue.push(event);
      wake();
    });
    this.closed.then(
      () => {
        ended = {};
        wake();
      },
      (error: unknown) => {
        ended = { error };
        wake();
      },
    );
    const done = () => {
      unsubscribe();
      this.close();
      return { done: true as const, value: undefined };
    };
    return {
      next: async () => {
        for (;;) {
          const event = queue.shift();
          if (event !== undefined) {
            return { done: false, value: event };
          }
          if (ended !== undefined) {
            if (ended.error !== undefined) {
              unsubscribe();
              throw ended.error;
            }
            return done();
          }
          // Wait for the next event or for the stream to close.
          await new Promise<void>((resolve) => waiting.push(resolve));
        }
      },
      return: async () => done(),
    };
  }

  async #run(transport: NotebookTransport) {
    // Start after the constructor returns, so listeners added right after it
    // receive the first events.
    await Promise.resolve();
    const { signal } = this.#controller;
    let attempt = 0;
    while (!signal.aborted) {
      try {
        const cursor = this.#stream.resume();
        await transport(
          { cursor, signal },
          {
            open: () => {
              if (this.#settle !== undefined) {
                this.#setStatus("connected");
              }
            },
            message: (message) => {
              if (this.#settle === undefined) {
                return;
              }
              attempt = 0;
              try {
                this.#stream.receive(message);
              } catch (error) {
                // The transport may call this from its own event listener,
                // so stop here instead of relying on it to pass the error on.
                this.#finish()?.reject(error);
              }
            },
          },
        );
      } catch (error) {
        this.#finish()?.reject(error);
        return;
      }
      if (signal.aborted) {
        return;
      }
      this.#setStatus("connecting");
      attempt += 1;
      if (attempt > ATTEMPTS) {
        this.#finish()?.reject(
          new StreamStopped("The host could not be reached"),
        );
        return;
      }
      await sleep(delay(attempt), signal);
    }
  }

  #setStatus(status: Status) {
    if (this.#status === status) {
      return;
    }
    this.#status = status;
    try {
      this.#onStatus?.(status);
    } catch (error) {
      report(error);
    }
  }

  /** Close the stream once and return how to settle `closed`. */
  #finish() {
    const settle = this.#settle;
    if (settle === undefined) {
      return undefined;
    }
    this.#settle = undefined;
    this.#release?.();
    this.#controller.abort();
    this.#setStatus("closed");
    return settle;
  }
}
