/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import NodeUrl from "node:url";
import type * as Protocol from "@marimo-team/client/protocol";
import { invariant } from "@/utils/invariant";
import { fixtureEvents } from "../../host/__tests__/fixtures";
import type { Document } from "../../host/resources/document";

export function protocolFixture(name: string): unknown {
  return JSON.parse(
    readFileSync(
      new NodeUrl.URL(
        `../../../../../protocols/host/fixtures/${name}`,
        import.meta.url,
      ),
      "utf8",
    ),
  );
}

export function initialDocument(): Document {
  const cells = new Map<Protocol.CellId, Protocol.Cell>();
  let revision: Protocol.Document | undefined;
  for (const event of fixtureEvents("notebook-events.sse")) {
    if (event.event === "ready") {
      break;
    }
    if (event.event === "cell") {
      cells.set(event.data.cell.id, event.data.cell);
    }
    if (event.event === "document") {
      revision = event.data.document;
    }
  }
  invariant(revision !== undefined, "Fixture has no document");
  return { revision, cells };
}
