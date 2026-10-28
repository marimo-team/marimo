/* Copyright 2026 Marimo. All rights reserved. */

import {
  type NotebookTransport,
  sse,
  StreamStopped,
  type StreamUrl,
} from "@marimo-team/client";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { classifyCloseEvent } from "../connection-state";

/** The server can be slow to accept when many notebooks are open. */
const CONNECT_MS = 10_000;

/**
 * The error that ends a stream on this close, or none to retry.
 *
 * `cause` is the connection status the editor shows.
 */
function stopOn(close: { code?: number; reason?: string }) {
  const decision = classifyCloseEvent(close);
  if (decision.kind === "retry") {
    return undefined;
  }
  const reason = "reason" in decision.status ? decision.status.reason : "";
  return new StreamStopped(reason, { cause: decision.status });
}

/** Read a URL provider, stopping the stream when it gives up. */
async function resolve(url: StreamUrl): Promise<URL | undefined> {
  try {
    return new URL(typeof url === "function" ? await url() : url);
  } catch (error) {
    if (error instanceof StreamStopped) {
      throw error;
    }
    return undefined;
  }
}

/** Send each request with the runtime's headers, read before each request. */
export function withHeaders(
  headers: () => Record<string, string>,
): typeof globalThis.fetch {
  return (input, init) => {
    const sent = new Headers(init?.headers);
    for (const [name, value] of Object.entries(headers())) {
      sent.set(name, value);
    }
    return globalThis.fetch(input, { ...init, headers: sent });
  };
}

/** A resume cursor and replica belong to the session that produced them. */
function withSessionIdentity(
  url: StreamUrl,
  connect: (target: URL) => NotebookTransport,
): NotebookTransport {
  let previous: string | undefined;
  return async (attempt, handlers) => {
    const target = await resolve(url);
    if (target === undefined || attempt.signal.aborted) {
      return;
    }
    target.searchParams.delete("cursor");
    const identity = new URL(target);
    identity.searchParams.delete("access_token");
    identity.searchParams.sort();
    identity.hash = "";
    const key = identity.toString();
    let { cursor } = attempt;
    if (previous !== undefined && previous !== key) {
      // Reset both the stream's cursor and its subscribers' state.
      handlers.message({ event: "reset", data: {} });
      cursor = null;
    }
    previous = key;
    if (!attempt.signal.aborted) {
      return connect(target)({ ...attempt, cursor }, handlers);
    }
  };
}

/**
 * Follow a marimo session over its WebSocket route.
 *
 * Each attempt opens one socket with the cursor as a query parameter. The
 * editor's close policy decides which closes end the stream.
 *
 * TODO: Notice a connection that died without closing, such as after a laptop
 * sleeps. `/sse` sends a heartbeat that its silence limit relies on, and
 * `/ws` drops it. Sending it on `/ws` would let this transport close a
 * silent socket.
 */
export function websocket(url: StreamUrl): NotebookTransport {
  return withSessionIdentity(
    url,
    (target) =>
      async ({ cursor, signal }, { open, message }) => {
        if (cursor !== null) {
          target.searchParams.set("cursor", cursor);
        }
        await new Promise<void>((settle, reject) => {
          const socket = new WebSocket(target);
          const timeout = setTimeout(() => socket.close(), CONNECT_MS);
          const abort = () => socket.close();
          signal.addEventListener("abort", abort, { once: true });
          socket.addEventListener("open", () => {
            clearTimeout(timeout);
            open();
          });
          socket.addEventListener("message", ({ data }) =>
            // marimo's parser reads `NaN`. A message it cannot read arrives as an
            // empty object, which `NotebookEvents` rejects as not an event.
            message(jsonParseWithSpecialChar(String(data))),
          );
          socket.addEventListener("close", (event) => {
            clearTimeout(timeout);
            signal.removeEventListener("abort", abort);
            const stopped = signal.aborted ? undefined : stopOn(event);
            if (stopped === undefined) {
              settle();
            } else {
              reject(stopped);
            }
          });
        });
      },
  );
}

/**
 * Follow a marimo session over its server-sent events route.
 *
 * The session's `close` frames carry the same reasons as WebSocket closes.
 * marimo's parser decodes tagged bigints and non-finite numbers in every frame.
 */
export function sessionSse(
  url: StreamUrl,
  headers: () => Record<string, string>,
): NotebookTransport {
  return withSessionIdentity(url, (target) =>
    sse(target, {
      parseData: jsonParseWithSpecialChar,
      fetch: withHeaders(headers),
      stop: (frame) =>
        frame.event === "close"
          ? stopOn(frame.data as { code?: number; reason?: string })
          : undefined,
    }),
  );
}

/** A connection that opens and delivers nothing, for static notebooks. */
export const idle: NotebookTransport = ({ signal }, { open }) =>
  new Promise((settle) => {
    open();
    signal.addEventListener("abort", () => settle(), { once: true });
  });
