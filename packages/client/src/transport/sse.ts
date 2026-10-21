/* Copyright 2026 Marimo. All rights reserved. */

import * as Protocol from "../protocol.ts";
import { type Connection, isType } from "../request.ts";
import { type Frame, type NotebookTransport, StreamStopped } from "./frame.ts";

/** Hosts send a comment every fifteen seconds while nothing else happens. */
const SILENCE_MS = 45_000;

/** Parse server-sent events from decoded text. */
export class ServerSentEventStream extends TransformStream<string, Frame> {
  public constructor() {
    let buffer = "";
    let event = "";
    let data: string[] = [];
    let id: string | undefined;
    const dispatch = (controller: TransformStreamDefaultController<Frame>) => {
      if (data.length > 0) {
        const text = data.join("\n");
        let value: unknown = text;
        try {
          value = JSON.parse(text);
        } catch {
          // Unknown events need not carry JSON.
        }
        // Unlike `EventSource`, an id does not carry over to later events.
        // Snapshot events have no id, and they have no position to resume from.
        controller.enqueue({
          event: event || "message",
          data: value,
          ...(id === undefined ? {} : { id }),
        });
      }
      event = "";
      data = [];
      id = undefined;
    };
    super({
      transform(chunk, controller) {
        buffer += chunk;
        // A carriage return at the end may be half of a CRLF in the next chunk.
        const held = buffer.endsWith("\r") ? "\r" : "";
        const lines = buffer
          .slice(0, buffer.length - held.length)
          .split(/\r\n|\r|\n/);
        buffer = (lines.pop() ?? "") + held;
        for (const line of lines) {
          if (line === "") {
            dispatch(controller);
            continue;
          }
          if (line.startsWith(":")) {
            continue;
          }
          const colon = line.indexOf(":");
          const field = colon === -1 ? line : line.slice(0, colon);
          let value = colon === -1 ? "" : line.slice(colon + 1);
          if (value.startsWith(" ")) {
            value = value.slice(1);
          }
          if (field === "event") {
            event = value;
          } else if (field === "data") {
            data.push(value);
          } else if (field === "id" && !value.includes("\0")) {
            id = value;
          }
        }
      },
    });
  }
}

/** Statuses a host answers when it may accept the stream later. */
const RETRY_STATUSES = new Set([408, 429]);

/**
 * Follow a stream over server-sent events, as the protocol defines.
 *
 * The cursor travels in `Last-Event-ID`. A refusal stops the stream with its
 * `Problem`, except for statuses that ask the client to try again. Other
 * failures and 45 seconds of silence are retried.
 */
export function sse(url: URL, connection: Connection): NotebookTransport {
  return async ({ cursor, signal }, { open, message }) => {
    const headers = new Headers(connection.headers);
    headers.set("Accept", "text/event-stream");
    if (connection.token !== undefined) {
      headers.set("Authorization", `Bearer ${connection.token}`);
    }
    if (cursor !== null) {
      headers.set("Last-Event-ID", cursor);
    }
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal.addEventListener("abort", abort, { once: true });
    let silence: ReturnType<typeof setTimeout> | undefined;
    const listen = () => {
      clearTimeout(silence);
      silence = setTimeout(abort, SILENCE_MS);
    };
    try {
      const fetch = connection.fetch ?? globalThis.fetch;
      // A host that accepts the request but never answers counts as silence.
      listen();
      const response = await fetch(url, {
        headers,
        signal: controller.signal,
      });
      const { status } = response;
      if (status >= 400 && status < 500 && !RETRY_STATUSES.has(status)) {
        const problem = Protocol.Problem.safeParse(
          await response.json().catch(() => undefined),
        );
        throw new StreamStopped(`The host refused the stream (${status})`, {
          cause: problem.success ? problem.data : undefined,
        });
      }
      if (!response.ok || response.body === null) {
        await response.body?.cancel();
        return;
      }
      if (!isType(response.headers.get("Content-Type"), "text/event-stream")) {
        await response.body.cancel();
        throw new StreamStopped("The host did not answer with an event stream");
      }
      open();
      // Any bytes count as activity, including the host's ping comments.
      const heard = new TransformStream<
        Uint8Array<ArrayBuffer>,
        Uint8Array<ArrayBuffer>
      >({
        transform(chunk, stream) {
          listen();
          stream.enqueue(chunk);
        },
      });
      const reader = response.body
        .pipeThrough(heard)
        .pipeThrough(new TextDecoderStream())
        .pipeThrough(new ServerSentEventStream())
        .getReader();
      controller.signal.addEventListener("abort", () => void reader.cancel(), {
        once: true,
      });
      // Reading by hand works where streams are not async iterable.
      for (;;) {
        const { done, value } = await reader.read();
        if (done) {
          return;
        }
        message(value);
      }
    } catch (error) {
      if (error instanceof StreamStopped) {
        throw error;
      }
    } finally {
      clearTimeout(silence);
      signal.removeEventListener("abort", abort);
    }
  };
}
