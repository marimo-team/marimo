/* Copyright 2026 Marimo. All rights reserved. */

import NodeFs from "node:fs";
import NodeUrl from "node:url";
import * as Protocol from "@marimo-team/client/protocol";

/** Read the protocol's portable examples as transport messages. */
export function fixtureMessages(name: string) {
  const path = new NodeUrl.URL(
    `../../../../../protocols/host/fixtures/${name}`,
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
      const payload: unknown = JSON.parse(data);
      return [
        {
          event,
          id: /^id: (.+)$/m.exec(frame)?.[1],
          data: payload,
        },
      ];
    });
}

/** Read the protocol's portable examples as decoded protocol events. */
export function fixtureEvents(name: string): Protocol.EventOutput[] {
  return fixtureMessages(name).map(({ id, ...message }) =>
    Protocol.Event.parse(id === undefined ? message : { ...message, id }),
  );
}
