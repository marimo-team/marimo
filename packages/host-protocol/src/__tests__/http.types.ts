/* Copyright 2026 Marimo. All rights reserved. */

import { Effect } from "effect";
import { HttpApiBuilder, type HttpApiClient } from "effect/http-api";
import { expectTypeOf } from "vitest";
import * as Host from "../Host.ts";
import * as S from "../Schemas.ts";

HttpApiBuilder.handler(
  Host.Api,
  "Notebook",
  "save",
  ({ params, headers, payload }) => {
    expectTypeOf(params.notebookId).toEqualTypeOf<typeof S.NotebookId.Type>();
    expectTypeOf(headers.expectedEtag).toEqualTypeOf<string | undefined>();
    expectTypeOf(headers.idempotencyKey).toEqualTypeOf<string>();
    expectTypeOf(payload).toEqualTypeOf<typeof S.SaveRequest.Type>();
    // @ts-expect-error Wire names are decoded before reaching the handler.
    void params.notebook_id;
    return Effect.die("Type check only");
  },
);

HttpApiBuilder.handler(Host.Api, "Notebook", "start", () =>
  // @ts-expect-error Starting must distinguish an existing runtime from an accepted start.
  Effect.succeed({ status: 201, body: {} }),
);
HttpApiBuilder.handler(Host.Api, "Notebook", "cancel", () =>
  // @ts-expect-error Cancelling returns a run record.
  Effect.succeed("cancelled"),
);

export function checkClient(client: HttpApiClient.ForApi<typeof Host.Api>) {
  const params = { notebookId: S.NotebookId.make("n") };
  const headers = { idempotencyKey: "key" };
  client.Notebook.save({
    params,
    headers: { ...headers, expectedEtag: "etag" },
    payload: {},
  });
  client.Notebook.execute({ params, headers, payload: { code: "1 + 1" } });
  client.Notebook.run({
    params,
    headers,
    payload: { cells: [{ id: S.CellId.make("c") }] },
  });
  // @ts-expect-error Mutations require an idempotency key.
  client.Notebook.save({ params, headers: {}, payload: {} });
  client.Notebook.run({
    params,
    headers,
    // @ts-expect-error Cell runs do not accept scratch code.
    payload: { code: "1 + 1", cells: [] },
  });
  // @ts-expect-error A cell run requires cells.
  client.Notebook.run({ params, headers, payload: {} });
}
