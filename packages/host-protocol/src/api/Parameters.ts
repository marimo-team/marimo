/* Copyright 2026 Marimo. All rights reserved. */

/** The path, query, and header parameters that endpoints share. */

import { Schema } from "effect";
import * as S from "../model/Ids.ts";
import * as Runtime from "../model/Runtime.ts";

export const AttachmentIdentity = Runtime.AttachmentIdentity.annotateKey({
  description:
    "An opaque client identity, copied to the attachment's `identity`.\nClients can reuse it across streams and reconnects so consumers\ncan group their attachments within a host. It is descriptive data,\nnot an authentication credential or an idempotency key. Every\nstream still creates its own attachment. Invalid values receive\na 400 `invalid-request` response.\n",
});

export const AttachmentKind = Runtime.AttachmentKind.annotate({
  default: "client",
}).annotateKey({
  description:
    "What kind of client is attached, such as `browser`, `editor`, or\n`agent`. Copied to the attachment's `kind`; omitted means `client`.\nHosts accept kinds they do not recognize. Values must contain one\nor more lowercase ASCII letters, digits, or hyphens; invalid values\nreceive a 400 `invalid-request` response.\n",
});

export const AttachmentName = Runtime.AttachmentName.annotateKey({
  description:
    "A human-readable label copied to the attachment's `name`, such as\n`Notebook CLI`. Omitted or empty means the attachment's name is\nnull. The value must be at most 256 characters; longer values\nreceive a 400 `invalid-request` response.\n",
});

export const IdempotencyKey = Schema.String.annotateKey({
  description:
    "A key the client makes up for this request, such as a UUID. It\ndoes two jobs. If the client sends the same request again, for\nexample after a timeout, the host returns the original response\ninstead of doing the work twice. And the host puts the key on\nevery event about the object the request changed, as\n`request_id`, until that object reaches a final status, so the\nclient can tell which changes it caused. Sending the same key with\na different request is a `conflict`. Keys are scoped to the host,\nacross all mutation routes, for a host-documented retry window\nindependent of result and replay retention. Repeating a run request\nreturns its latest run record, even if its outputs have expired.\nOutside that window or after loss of host state, the key may execute\nagain. Error responses do not reserve a key. Clients use fresh keys\nfor new work and decision retries.\n",
});

export const NotebookId = S.NotebookId.annotateKey({
  description: "The notebook's id.",
});

export const RunId = S.RunId.annotateKey({
  description: "The run's id.",
});

export const InputId = S.ItemId.annotateKey({
  description: "The input's item id.",
});

export const RunFilter = S.RunId.annotateKey({
  description: "Narrows the notebook stream to one run.",
});

export const Types = Schema.String.annotateKey({
  description:
    "Which kinds to send, as a comma-separated list of kind names such as `runtime,project`. Omit it to receive every kind the stream carries.",
});

export const LastEventId = Schema.String.annotateKey({
  description:
    "The `id` of the last event the client received, when reconnecting.",
});

export const IfMatch = Schema.String.annotateKey({
  description:
    "The document etag the client last read, as a precondition. The host answers `precondition-failed` when the document's etag differs.",
});

/** The notebook a route names in its path. */
export const notebook = Schema.Struct({ notebookId: NotebookId }).pipe(
  Schema.encodeKeys({ notebookId: "notebook_id" }),
);

/** The key every mutation carries. */
export const idempotent = Schema.Struct({
  idempotencyKey: IdempotencyKey,
}).pipe(Schema.encodeKeys({ idempotencyKey: "idempotency-key" }));
