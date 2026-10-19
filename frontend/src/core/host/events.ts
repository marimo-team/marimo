/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import * as Protocol from "./protocol";

const envelope = z.object({
  event: z.string().min(1),
  data: z.unknown(),
  id: z.string().min(1).optional(),
});

const events = z.discriminatedUnion("event", [
  Protocol.NotebookEvent,
  Protocol.DocumentEvent,
  Protocol.CellEvent,
  Protocol.NotebookRemovedEvent,
  Protocol.CellRemovedEvent,
  Protocol.MarimoEvent,
  Protocol.ResetEvent,
  Protocol.ReadyEvent,
]);

const names = new Set<string>(
  events.options.flatMap((schema) => schema.shape.event.options),
);

/** The object kinds consumed by a notebook client. Controls and removals follow automatically. */
export const NOTEBOOK_EVENT_TYPES = [...names].filter(
  (name) => name !== "ready" && name !== "reset" && !name.endsWith(".removed"),
);

/**
 * A record, notification, or control message from a notebook stream.
 *
 * Unknown events carry their cursor without interpreting their contents.
 * The older session envelope is normalized to a marimo event.
 */
export type NotebookEvent =
  | z.output<typeof events>
  | {
      readonly event: "unknown";
      readonly name: string;
      readonly id?: string;
    };

const sessionEnvelope = z.object({ data: Protocol.MarimoNotification });

/** Decode a notebook message, rejecting malformed events of known kinds. */
export function parseNotebookEvent(value: unknown): NotebookEvent {
  if (typeof value === "object" && value !== null && !("event" in value)) {
    return {
      event: "marimo",
      data: { marimo: sessionEnvelope.parse(value).data },
    };
  }
  const parsed = envelope.parse(value);
  if (names.has(parsed.event)) {
    return events.parse(parsed);
  }
  return { event: "unknown", name: parsed.event, id: parsed.id };
}
