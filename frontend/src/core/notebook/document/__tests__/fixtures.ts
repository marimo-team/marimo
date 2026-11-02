/* Copyright 2026 Marimo. All rights reserved. */

import type { Document } from "../../replica/resources/document";
import type * as Protocol from "@marimo-team/client/protocol";

export const CONFIG: Protocol.CellConfig = {
  column: null,
  disabled: false,
  hide_code: false,
  expand_output: false,
};

export function cell(
  id: Protocol.CellId,
  code: string,
  overrides: Partial<Protocol.Cell> = {},
): Protocol.Cell {
  return {
    id,
    notebook_id: "n1",
    code,
    name: "_",
    config: CONFIG,
    etag: `${id}-etag`,
    code_hash: `${id}-hash`,
    version: 1,
    ...overrides,
  };
}

/** A two-cell document, `c1` then `c2`. */
export function document(notebookId: Protocol.NotebookId = "n1"): Document {
  const cells = [
    cell("c1", "x = 1", { notebook_id: notebookId }),
    cell("c2", "y = 2", { notebook_id: notebookId }),
  ];
  return {
    revision: {
      notebook_id: notebookId,
      order: cells.map((c) => c.id),
      app_config: { width: "medium" },
      etag: "document-1",
      saved_etag: "document-1",
      order_etag: "order-1",
      app_config_etag: "config-1",
      version: 1,
    },
    cells: new Map(cells.map((c) => [c.id, c])),
  };
}

/** The document with some cells replaced or removed and the order updated. */
export function withCells(
  base: Document,
  changes: Record<Protocol.CellId, Protocol.Cell | null>,
  order?: readonly Protocol.CellId[],
): Document {
  const cells = new Map(base.cells);
  for (const [id, next] of Object.entries(changes)) {
    if (next === null) {
      cells.delete(id);
    } else {
      cells.set(id, next);
    }
  }
  const nextOrder = order
    ? [...order]
    : [
        ...base.revision.order.filter((id) => cells.has(id)),
        ...[...cells.keys()].filter((id) => !base.cells.has(id)),
      ];
  const orderChanged =
    nextOrder.length !== base.revision.order.length ||
    nextOrder.some((id, index) => id !== base.revision.order[index]);
  const orderEtag = orderChanged
    ? `order:${JSON.stringify(nextOrder)}`
    : base.revision.order_etag;
  return {
    revision: {
      ...base.revision,
      order: nextOrder,
      order_etag: orderEtag,
      version: base.revision.version + 1,
      etag: JSON.stringify([
        orderEtag,
        base.revision.app_config_etag,
        ...nextOrder.map((id) => cells.get(id)?.etag),
      ]),
    },
    cells,
  };
}
