/* Copyright 2026 Marimo. All rights reserved. */

import type { NotificationMessage, OutputMessage } from "../kernel/messages";

export type CommandOutputMessage = Extract<
  NotificationMessage,
  { op: "pdb-output" | "callback-output" }
>;

/** Each producer can replace its own entries when the editor reconnects. */
export interface CommandConsole {
  /** Keep the original chunks so a replay can interleave both producers before merging text. */
  entries: (OutputMessage & {
    source: CommandOutputMessage["op"];
    afterSeq?: number;
  })[];
}

/** Merge a producer's snapshot or append its latest writes to the cell console. */
export function updateCommandConsole(
  previous: CommandConsole | undefined,
  { op, entries, replace, after_seq }: CommandOutputMessage,
): CommandConsole {
  if (op === "callback-output" && !replace && entries.length === 0) {
    // A live callback's clear_console() clears the entire cell transcript.
    return { entries: [] };
  }
  const reset = replace || entries.length === 0;
  const retained = previous?.entries ?? [];
  const incoming = entries.map((entry, index) => ({
    ...entry,
    source: op,
    afterSeq: after_seq?.[index],
  }));
  return {
    entries: [
      ...(reset ? retained.filter((entry) => entry.source !== op) : retained),
      ...incoming,
    ],
  };
}
