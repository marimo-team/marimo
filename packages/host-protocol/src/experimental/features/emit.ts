/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { HttpApiEndpoint, HttpApiSchema, OpenApi } from "effect/http-api";
import { Custom } from "../../model/Events.ts";
import * as P from "../../api/Parameters.ts";
import * as Problems from "../../Problems.ts";
import { defineFeature } from "../defineFeature.ts";

export const EmitRequest = Custom.annotate({
  description: "A custom event to publish on the notebook stream.",
  identifier: "EmitRequest",
});

export const Emit = HttpApiEndpoint.post(
  "emit",
  "/notebooks/:notebook_id/emit",
  {
    params: P.notebook,
    headers: P.idempotent,
    payload: EmitRequest,
    success: [
      Schema.Void.pipe(HttpApiSchema.status(204)).annotateKey({
        description: "The host published the custom event.",
      }),
    ],
    error: [...Problems.Mutation.members],
  },
)
  .annotate(OpenApi.Identifier, "notebook.emit")
  .annotate(OpenApi.Summary, "Publish a custom event")
  .annotate(
    OpenApi.Description,
    "Publishes the request's `type` and `data` as a custom event on the\nnotebook stream. The event carries the `Idempotency-Key` as\n`request_id`. Stream filters apply.\n\nReturns `204 No Content` after publication. The response does not\nconfirm that a client received or processed the event.\n",
  );

export default defineFeature({
  notebook: { endpoints: [Emit] },
});
