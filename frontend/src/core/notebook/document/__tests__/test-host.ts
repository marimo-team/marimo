/* Copyright 2026 Marimo. All rights reserved. */

import { createHash } from "node:crypto";
import type { Result } from "@marimo-team/client";
import * as Protocol from "@marimo-team/client/protocol";
import type { Document } from "../../replica/resources/document";

export interface EditRequest {
  readonly notebookId: Protocol.NotebookId;
  readonly changes: readonly Protocol.Change[];
  readonly idempotencyKey: string;
}

interface Outcome {
  readonly result: Result<Protocol.EditResponseOutput>;
  /** Only a new commit produces a stream update; replaying a receipt does not. */
  readonly update?: Document;
}

const hash = (text: string) =>
  createHash("sha256").update(text).digest("hex").slice(0, 16);

function record(
  input: Protocol.CellInput,
  notebookId: Protocol.NotebookId,
  version: number,
): Protocol.Cell {
  const cell = Protocol.CellInput.parse(input);
  const config = Protocol.CellConfigInput.parse(cell.config ?? {});
  const code = cell.code.replace(/\r\n?/g, "\n");
  const codeHash = hash(code);
  return {
    id: cell.id,
    notebook_id: notebookId,
    name: cell.name,
    code,
    config,
    code_hash: codeHash,
    etag: hash(
      [
        codeHash,
        cell.name,
        ...[
          config.column,
          config.disabled,
          config.hide_code,
          config.expand_output,
        ].map((value) => JSON.stringify(value)),
      ].join("\n"),
    ),
    version,
  };
}

function rejected(
  status: number,
  kind: string,
  detail: string,
  edit?: Protocol.Problem["edit"],
): Outcome {
  return {
    result: {
      ok: false,
      status,
      problem: {
        type: `tag:marimo.io,2026:host/${kind}`,
        title: kind === "conflict" ? "Conflict" : "Invalid request",
        detail,
        status,
        ...(edit === undefined ? {} : { edit }),
      },
    },
  };
}

/** An independent implementation of the document edit protocol, without client draft logic. */
export function createTestHost(initial: Document) {
  let current = initial;
  const receipts = new Map<
    string,
    {
      fingerprint: string;
      result: Result<Protocol.EditResponseOutput>;
      expiresAt: number;
    }
  >();

  function apply(changes: readonly Protocol.Change[]): Outcome {
    const cells = new Map(current.cells);
    let order = [...current.revision.order];
    const touched = new Set<Protocol.CellId>();
    const version = current.revision.version + 1;
    const matches = (id: Protocol.CellId, etag: string) =>
      etag === "*" || current.cells.get(id)?.etag === etag;
    const conflict = (change: number, id?: Protocol.CellId) =>
      rejected(409, "conflict", `Edit conflict at change ${change}`, {
        change,
        cell: id === undefined ? null : (current.cells.get(id) ?? null),
        document: current.revision,
      });

    for (const [index, change] of changes.entries()) {
      switch (change.kind) {
        case "put_cell": {
          const { id } = change.cell;
          if (change.base_etag === null) {
            if (current.cells.has(id) || cells.has(id)) {
              return conflict(index, id);
            }
            if (change.after !== undefined && change.before !== undefined) {
              return rejected(
                400,
                "invalid-request",
                "A cell cannot name both before and after",
              );
            }
            const anchor = change.after ?? change.before;
            if (anchor !== undefined && !order.includes(anchor)) {
              return rejected(
                400,
                "invalid-request",
                "The placement anchor does not exist",
              );
            }
            const position =
              anchor === undefined
                ? order.length
                : order.indexOf(anchor) + (change.after === undefined ? 0 : 1);
            order.splice(position, 0, id);
          } else if (!cells.has(id) || !matches(id, change.base_etag)) {
            return conflict(index, id);
          }
          cells.set(
            id,
            record(change.cell, current.revision.notebook_id, version),
          );
          touched.add(id);
          break;
        }
        case "delete_cell":
          if (!cells.has(change.id) || !matches(change.id, change.base_etag)) {
            return conflict(index, change.id);
          }
          cells.delete(change.id);
          order = order.filter((id) => id !== change.id);
          touched.add(change.id);
          break;
        case "set_order":
          if (
            change.base_etag !== "*" &&
            change.base_etag !== current.revision.order_etag
          ) {
            return conflict(index);
          }
          if (
            change.order.length !== cells.size ||
            new Set(change.order).size !== cells.size ||
            change.order.some((id) => !cells.has(id))
          ) {
            return rejected(
              400,
              "invalid-request",
              "Order must name every cell exactly once",
            );
          }
          order = [...change.order];
          break;
      }
    }

    for (const [id, cell] of cells) {
      const previous = current.cells.get(id);
      if (previous?.etag === cell.etag) {
        cells.set(id, previous);
      }
    }
    const orderEtag = hash(JSON.stringify(order));
    const etag = hash(
      [
        orderEtag,
        current.revision.app_config_etag,
        ...order.map((id) => cells.get(id)!.etag),
      ].join("\n"),
    );
    const changed = etag !== current.revision.etag;
    if (changed) {
      current = {
        revision: {
          ...current.revision,
          order,
          order_etag: orderEtag,
          etag,
          version,
        },
        cells,
      };
    }
    const versions: Protocol.EditResponseOutput["cells"] = {};
    for (const id of touched) {
      const cell = current.cells.get(id);
      versions[id] =
        cell === undefined
          ? null
          : {
              etag: cell.etag,
              code_hash: cell.code_hash,
              version: cell.version,
            };
    }
    return {
      result: {
        ok: true,
        status: 200,
        data: { document: current.revision, cells: versions },
      },
      ...(changed ? { update: current } : {}),
    };
  }

  return {
    document: () => current,
    apply,
    process(request: EditRequest): Outcome {
      const fingerprint = JSON.stringify([request.notebookId, request.changes]);
      const receipt = receipts.get(request.idempotencyKey);
      if (receipt !== undefined && Date.now() < receipt.expiresAt) {
        return receipt.fingerprint === fingerprint
          ? { result: receipt.result }
          : rejected(
              409,
              "conflict",
              "Idempotency key was used for another request",
            );
      }
      const outcome =
        request.notebookId === current.revision.notebook_id
          ? apply(request.changes)
          : rejected(404, "not-found", "Notebook does not exist");
      receipts.set(request.idempotencyKey, {
        fingerprint,
        result: outcome.result,
        expiresAt: Date.now() + 300_000,
      });
      return outcome;
    },
  };
}
