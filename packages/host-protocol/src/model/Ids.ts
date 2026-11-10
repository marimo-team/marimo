/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";

export const ProjectId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "Identifies a project. Unique within the host and unchanged while the project exists.",
  })
  .pipe(Schema.brand("ProjectId"))
  .annotate({ identifier: "ProjectId" });

export const NotebookId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "Identifies a notebook. Unique within the host and unchanged while the notebook exists.",
  })
  .pipe(Schema.brand("NotebookId"))
  .annotate({ identifier: "NotebookId" });

export const RuntimeId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "Identifies a runtime. Unique within the host; every start and restart creates a new id.",
  })
  .pipe(Schema.brand("RuntimeId"))
  .annotate({ identifier: "RuntimeId" });

export const AttachmentId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description: "Identifies an attachment. Unique within the host.",
  })
  .pipe(Schema.brand("AttachmentId"))
  .annotate({ identifier: "AttachmentId" });

export const RunId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "Identifies a run independently of the request's `Idempotency-Key`. Events carry the key in `request_id`.",
  })
  .pipe(Schema.brand("RunId"))
  .annotate({ identifier: "RunId" });

export const ExecutionId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({ description: "Identifies an execution. Unique within the host." })
  .pipe(Schema.brand("ExecutionId"))
  .annotate({ identifier: "ExecutionId" });

export const ItemId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "Identifies a console, display, input, or variable item uniquely within the host. Sending an item again with the same id replaces it.",
  })
  .pipe(Schema.brand("ItemId"))
  .annotate({ identifier: "ItemId" });

export const CellId = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "Identifies a cell within its notebook. Stable while the host serves the notebook; whether it survives a reload of the store depends on the format. `setup` is the setup cell.",
  })
  .pipe(Schema.brand("CellId"))
  .annotate({ identifier: "CellId" });

export const CodeFingerprint = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "Opaque code identity assigned by the host. Clients compare cell and execution fingerprints for freshness. Incompatible schemes MUST produce distinct fingerprints.",
  })
  .pipe(Schema.brand("CodeFingerprint"))
  .annotate({ identifier: "CodeFingerprint" });

export const Etag = Schema.String.annotate({
  description:
    "An identifier derived from content, so that every host, kernel,\nand store computes the same value for the same state. It is the\nfirst 16 hexadecimal characters, in lower case, of SHA-256 over\nthe UTF-8 encoding of a canonical text. Each etag says what its\ntext is; a text made of several values is those values joined by\nnewlines. Clients do not compute etags. They read them from the\nstream and from responses, and send them back as preconditions.\n",
})
  .pipe(Schema.brand("Etag"))
  .annotate({ identifier: "Etag" });
