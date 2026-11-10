/* Copyright 2026 Marimo. All rights reserved. */

/** The file a host writes so that clients can find it. */

import { Schema } from "effect";
import { Integer } from "../internal/schema.ts";
import { Timestamp } from "./Ids.ts";

export const Process = Schema.Struct({
  pid: Integer.check(Schema.isGreaterThanOrEqualTo(1)).annotateKey({
    description: "The process id.",
    format: "int64",
  }),
  started_at: Timestamp.annotateKey({
    description: "When the process started.",
  }),
}).annotate({
  description:
    "The process that wrote a record. A client checks that a process\nwith this `pid` that started at `started_at` still exists. If it\ndoes not, the record is stale and may be removed.\n",
  identifier: "Process",
});

export const HostRecord = Schema.Struct({
  version: Schema.Literal(1).annotateKey({
    description:
      "The version of this record's format. This document describes version 1.",
  }),
  process: Process,
  name: Schema.String.annotateKey({
    description:
      "A label for the host to show people, such as `VS Code` or `marimo`. Two hosts can share a name; the filename is the identity.",
    examples: ["marimo"],
  }),
  url: Schema.String.annotateKey({
    description:
      "Where the host's API is. The scheme is `http`, and the host part is `127.0.0.1` or `[::1]`, written exactly that way.",
    examples: ["http://127.0.0.1:2718/api/marimo/v1"],
  }),
  token: Schema.String.check(Schema.isMinCodePoints(1)).annotateKey({
    description: "The secret a client sends to prove it read the record.",
  }),
}).annotate({
  description:
    "A host record is the file a host writes so that clients can find\nit. A host writes `<marimo-state-dir>/hosts-v1/<id>.json` once its API\nis serving at `url`, where `<id>` is an identifier the host makes\nup each time it starts. The record does not change while the host\nruns, and the host removes it when it stops.\n\nA client reads `version` before anything else and skips any record\nit cannot parse or whose version it does not support. It also\nchecks that the file and its directory belong to the current user\nand cannot be read by others, and that `url` points at this\nmachine.\n",
  identifier: "HostRecord",
});
