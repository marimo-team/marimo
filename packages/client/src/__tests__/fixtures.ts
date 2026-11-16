/* Copyright 2026 Marimo. All rights reserved. */

import NodeFs from "node:fs";
import NodeUrl from "node:url";
import * as Protocol from "../protocol.ts";

/** Read one of the protocol's portable SSE examples as decoded events. */
export function fixtureEvents(name: string): Protocol.EventOutput[] {
  const path = new NodeUrl.URL(
    `../../../../protocols/host/fixtures/${name}`,
    import.meta.url,
  );
  return NodeFs.readFileSync(path, "utf8")
    .split(/\r?\n\r?\n/)
    .flatMap((frame) => {
      const event = /^event: (.+)$/m.exec(frame)?.[1];
      if (!event) {
        return [];
      }
      const data = frame
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      const id = /^id: (.+)$/m.exec(frame)?.[1];
      return [
        Protocol.Event.parse({
          event,
          data: JSON.parse(data),
          ...(id ? { id } : {}),
        }),
      ];
    });
}
