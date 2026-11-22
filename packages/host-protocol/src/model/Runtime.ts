/* Copyright 2026 Marimo. All rights reserved. */

/** A notebook's kernel and the consumers attached to the notebook. */

import { Schema } from "effect";
import { NotebookId, RuntimeId, AttachmentId, Timestamp } from "./Ids.ts";

export const RuntimeStarting = Schema.Struct({
  status: Schema.Literal("starting"),
  message: Schema.NullOr(Schema.String).annotateKey({
    description:
      "A note about progress, such as the packages being installed. Null when the host has nothing to report.",
  }),
}).annotate({ identifier: "RuntimeStarting" });

export const RuntimeReady = Schema.Struct({
  status: Schema.Literal("ready"),
}).annotate({ identifier: "RuntimeReady" });

export const RuntimeStopping = Schema.Struct({
  status: Schema.Literal("stopping"),
}).annotate({ identifier: "RuntimeStopping" });

export const RuntimeStoppedOutcome = Schema.Struct({
  kind: Schema.Literal("stopped"),
}).annotate({ identifier: "RuntimeStoppedOutcome" });

export const RuntimeFailedOutcome = Schema.Struct({
  kind: Schema.Literal("failed"),
  message: Schema.NullOr(Schema.String).annotateKey({
    description:
      "Why the kernel could not start or why it exited, to show people. Null when the host does not know.",
  }),
}).annotate({ identifier: "RuntimeFailedOutcome" });

export const RuntimeOutcome = Schema.Union([
  RuntimeStoppedOutcome,
  RuntimeFailedOutcome,
]).annotate({
  description:
    "How a runtime ended, tagged on `kind`. A `stopped` runtime was\nended by a client or the host. A `failed` runtime could not start,\nor its kernel exited unexpectedly.\n",
  identifier: "RuntimeOutcome",
});

export const RuntimeEnded = Schema.Struct({
  status: Schema.Literal("ended"),
  ended_at: Timestamp.annotateKey({
    description: "When the runtime ended.",
  }),
  outcome: RuntimeOutcome,
}).annotate({ identifier: "RuntimeEnded" });

export const RuntimeState = Schema.Union([
  RuntimeStarting,
  RuntimeReady,
  RuntimeStopping,
  RuntimeEnded,
]).annotate({
  description:
    "Where a runtime is in its life, tagged on `status`. A `starting`\nruntime is bringing its kernel up. A `ready` runtime accepts work.\nA `stopping` runtime is shutting its kernel down. An `ended`\nruntime has no kernel and does not change again.\n",
  identifier: "RuntimeState",
});

export const Runtime = Schema.Struct({
  id: RuntimeId,
  notebook_id: NotebookId,
  marimo_version: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The version of marimo running the kernel. Null until the host knows it.",
  }),
  created_at: Timestamp.annotateKey({
    description: "When the host created this runtime and began starting it.",
  }),
  state: RuntimeState,
}).annotate({
  description:
    "A runtime is a kernel attached to one notebook, and a notebook has\nat most one. It ends when a client or the host stops it or its\nprocess exits. The notebook keeps the ended runtime, so clients can\nsee how it ended, until another one starts or the notebook closes.\nThe host then sends `runtime.removed`. Every start and restart\ncreates a new runtime with a new id. Executions carry their producer's\nruntime id, and their results are live while that runtime has not ended.\n",
  identifier: "Runtime",
});

export const AttachmentIdentity = Schema.String.check(
  Schema.isMinCodePoints(1),
  Schema.isMaxCodePoints(128),
  Schema.isPattern(/^[!-~]+$/u),
);

export const AttachmentKind = Schema.String.check(
  Schema.isPattern(/^[a-z0-9-]+$/u),
);

export const AttachmentName = Schema.String.check(Schema.isMaxCodePoints(256));

export const Attachment = Schema.Struct({
  id: AttachmentId,
  notebook_id: NotebookId,
  identity: Schema.NullOr(AttachmentIdentity).annotateKey({
    description:
      "The opaque client identity supplied by `Marimo-Attachment-Identity`.\nNull when none was supplied. Consumers can group attachments\nwith the same identity within a host. It does not identify an\nindividual connection or change its lifetime.\n",
  }),
  kind: AttachmentKind.annotateKey({
    description:
      "What kind of thing is attached, supplied by `Marimo-Attachment-Kind`, such as `browser`, `editor`, or `agent`. Defaults to `client` when the header is omitted. Clients accept kinds they do not recognize.",
  }),
  name: Schema.NullOr(AttachmentName).annotateKey({
    description:
      "A label to show people, supplied by `Marimo-Attachment-Name`, such as the browser or editor's name. Null when the header is omitted or empty.",
  }),
  created_at: Timestamp.annotateKey({
    description: "When it attached.",
  }),
}).annotate({
  description:
    "An attachment is a consumer connected to a notebook, such as a\nbrowser tab, an editor, or an agent. Opening the notebook's stream\ncreates one. It is removed when that connection closes, and not\nwhen the notebook's runtime stops or restarts. Each stream has its\nown attachment, even when several share a client identity.\n",
  identifier: "Attachment",
});
