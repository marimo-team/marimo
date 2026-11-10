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

export const Etag = Schema.String.check(Schema.isMinCodePoints(1))
  .annotate({
    description:
      "An identifier a host derives from content, so the same content has the same etag. It is opaque to clients. They read etags from the stream and from responses, and send them back as preconditions.",
  })
  .pipe(Schema.brand("Etag"))
  .annotate({ identifier: "Etag" });

const rfc3339 =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/u;

export const Timestamp = Schema.String.annotate({
  description:
    "A date and time with its offset from UTC, as RFC 3339 writes it.",
  format: "date-time",
})
  .check(
    Schema.makeFilter((text: string) => rfc3339.test(text), {
      expected: "an RFC 3339 date-time",
    }),
  )
  .pipe(Schema.brand("Timestamp"))
  .annotate({ identifier: "Timestamp" });
