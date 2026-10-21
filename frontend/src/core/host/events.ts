/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import * as Protocol from "@marimo-team/client/protocol";

/**
 * Notebook stream events, including native marimo notifications.
 *
 * Known events follow the generated protocol. Unknown events retain their name
 * and cursor so clients can skip them without losing their place in the stream.
 */

/** Event kinds requested by the client; removals and controls are implicit. */
export const NOTEBOOK_EVENT_TYPES = [
  "notebook",
  "document",
  "cell",
  "attachment",
  "marimo",
] as const satisfies readonly (Protocol.ObjectType | "marimo")[];

const envelope = z.object({
  event: z.string().min(1),
  data: z.unknown(),
  id: z.string().min(1).optional(),
});

const knownNames = new Set<string>(
  Protocol.Event.options.flatMap((schema) => schema.shape.event.options),
);

/**
 * A native marimo message carried by a host stream.
 *
 * The protocol leaves extension events to their producer. The payload is
 * passed through for the session handler to interpret.
 */
const MarimoEvent = z.object({
  event: z.literal("marimo"),
  id: z.string().min(1).optional(),
  data: z.object({ marimo: z.unknown() }),
});

/** A decoded event, or the name and cursor of an unrecognized event. */
export type NotebookEvent =
  | Protocol.EventOutput
  | z.output<typeof MarimoEvent>
  | {
      readonly event: "unknown";
      readonly name: string;
      readonly id?: string;
    };

const sessionEnvelope = z.object({ data: z.unknown() });

/**
 * Decode a host event or a legacy `{ data: notification }` session message.
 *
 * Throws if the envelope or a known event is malformed. Native notification
 * payloads are passed through for the session handler to interpret.
 */
export function parseNotebookEvent(value: unknown): NotebookEvent {
  if (typeof value === "object" && value !== null && !("event" in value)) {
    return {
      event: "marimo",
      data: { marimo: sessionEnvelope.parse(value).data },
    };
  }
  const parsed = envelope.parse(value);
  if (parsed.event === "marimo") {
    return MarimoEvent.parse(parsed);
  }
  if (knownNames.has(parsed.event)) {
    return Protocol.Event.parse(parsed);
  }
  return { event: "unknown", name: parsed.event, id: parsed.id };
}
