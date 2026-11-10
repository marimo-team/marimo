/* Copyright 2026 Marimo. All rights reserved. */

/** A notebook's cells, their order, and its app configuration. */

import { Schema } from "effect";
import { Integer } from "../internal/schema.ts";
import { NotebookId, CellId, CodeFingerprint, Etag } from "./Ids.ts";

export const CellConfig = Schema.Struct({
  column: Schema.NullOr(Integer).annotateKey({
    description:
      "The column the cell sits in, for multi-column layouts. Null in a single column.",
  }),
  disabled: Schema.Boolean.annotateKey({
    description: "Whether the cell is kept from running.",
  }),
  hide_code: Schema.Boolean.annotateKey({
    description:
      "Whether clients hide the code by default. This is a presentation preference; source availability is represented by `Cell.code`.",
  }),
  expand_output: Schema.Boolean.annotateKey({
    description:
      "Whether clients show the full output rather than a scrolled box.",
  }),
}).annotate({
  description:
    "How a cell is laid out and whether it runs. Every field is always present, so a cell's etag is well defined.",
  identifier: "CellConfig",
});

export const Cell = Schema.Struct({
  id: CellId,
  notebook_id: NotebookId,
  code: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The cell's source code, with newline line endings, or null when the host does not expose source to this client. An empty string is an empty cell. A host normalizes other line endings when it loads a file. Source availability does not grant editing permission; see the notebook's operations.",
  }),
  name: Schema.String.annotateKey({
    description:
      "The cell's name. `_` for an anonymous cell; otherwise a Python identifier, unique within the notebook.",
  }),
  config: CellConfig,
  etag: Etag.annotateKey({
    description:
      "Precondition for edits and cell runs. Covers exact source, name, and config. Its text is the newline-joined sequence of the first 16 hex characters of SHA-256 of the UTF-8 source, `name`, and the config values `column`, `disabled`, `hide_code`, and `expand_output`, in that order. Config values are JSON scalars.",
  }),
  code_fingerprint: CodeFingerprint.annotateKey({
    description:
      "Fingerprint of the actual source, including when `code` is null. Formatting-only edits may preserve it. Independent of cell name, config, and source visibility.",
  }),
  version: Integer.check(Schema.isGreaterThanOrEqualTo(1)).annotateKey({
    description:
      "The document version at which the cell was created or last changed.",
  }),
}).annotate({
  description:
    "A unit of code and configuration in the document. A cell event\nfires when its code, name, or config changes. Markdown and SQL\ncells are code that calls `mo.md` or `mo.sql`; a client chooses\nthe editor to show.\n",
  identifier: "Cell",
});

export const Document = Schema.Struct({
  notebook_id: NotebookId.annotateKey({
    description: "The notebook this document belongs to.",
  }),
  order: Schema.Array(CellId).annotateKey({
    description:
      "Cell ids in display order. A permutation of the notebook's cells, each appearing exactly once.",
  }),
  app_config: Schema.Record(Schema.String, Schema.Json).annotateKey({
    description:
      "Notebook-level settings, the keyword arguments to `marimo.App` such as `width` and `app_title`. Informational for now; no change sets it over this protocol.",
  }),
  etag: Etag.annotateKey({
    description:
      "Identifies the document as currently applied. Its text is `order_etag`, `app_config_etag`, and every cell's `etag` in order, so it changes when any of them does.",
  }),
  saved_etag: Schema.NullOr(Etag).annotateKey({
    description:
      "Identifies the document as last written to the host's store, computed the same way over that state. Equal to `etag` when every accepted change has been persisted. Null when nothing has been persisted, which is the case for a scratch copy.",
  }),
  order_etag: Etag.annotateKey({
    description:
      "Identifies the order alone. Its text is the cell IDs in order as a JSON array, with no whitespace and strings carrying only the escapes JSON requires. Editing a cell does not change it.",
  }),
  app_config_etag: Etag.annotateKey({
    description:
      "Identifies the app config alone. Its text is the app config as canonical JSON, with keys sorted by code point, no whitespace, and strings carrying only the escapes JSON requires.",
  }),
  version: Integer.check(Schema.isGreaterThanOrEqualTo(1)).annotateKey({
    description:
      "Counts changes to the cells, the order, or the app config. A save does not advance it. Comparable only within one notebook while it is in the catalog.",
  }),
}).annotate({
  description:
    "The document as a whole, without its cells, which are their own\nobjects: the cell order and app config. One per notebook,\nand removed with it. The order and the app\nconfig carry their own etags, so an edit to one does not conflict\nwith an edit to the other, or with edits to cells.\n",
  identifier: "Document",
});
