/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import { Effect, Layer, Schema, Stream } from "effect";
import { HttpApiBuilder, HttpApiClient } from "effect/http-api";
import { FetchHttpClient, HttpRouter, HttpServer } from "effect/http";
import { afterAll, describe, expect, it, vi } from "vitest";
import * as Host from "../Host.ts";
import * as Notebook from "../Notebook.ts";
import * as S from "../Schemas.ts";
import * as Problems from "../Problems.ts";

const edit = Schema.decodeUnknownSync(S.EditResponse)(
  JSON.parse(
    readFileSync(
      new URL(
        "../../../../protocols/host/fixtures/edit-response.json",
        import.meta.url,
      ),
      "utf8",
    ),
  ),
);
const runtime = Schema.decodeUnknownSync(S.Runtime)({
  id: "r",
  notebook_id: "n",
  status: "running",
  message: null,
  marimo_version: "0.1.0",
  started_at: "2026-01-01T00:00:00Z",
});
const unavailable = () =>
  Effect.fail(new Problems.UnsupportedOperationProblem());
const save = vi.fn(
  HttpApiBuilder.handler(Host.Api, "Notebook", "save", ({ headers }) =>
    headers.expectedEtag === "stale"
      ? Effect.fail(new Problems.ConflictProblem({ detail: "Stale" }))
      : Effect.succeed(edit),
  ),
);
const events = vi.fn(
  HttpApiBuilder.handler(Host.Api, "Notebook", "events", () =>
    Effect.succeed(
      Stream.make(Notebook.Event.make({ event: "ready", id: "98", data: {} })),
    ),
  ),
);
const host = HttpApiBuilder.group(Host.Api, "Host", (handlers) =>
  handlers
    .handle("create", unavailable)
    .handle("events", () => Effect.succeed(Stream.empty)),
);
const notebook = HttpApiBuilder.group(Host.Api, "Notebook", (handlers) =>
  handlers.handleAll({
    delete: () => Effect.void,
    edit: unavailable,
    events,
    open: unavailable,
    reply: unavailable,
    interrupt: unavailable,
    cancel: unavailable,
    restart: unavailable,
    run: unavailable,
    execute: unavailable,
    start: ({ headers }) =>
      Effect.succeed(
        headers.idempotencyKey === "existing"
          ? { status: 200 as const, body: runtime }
          : { status: 202 as const, body: runtime },
      ),
    stop: unavailable,
    save,
    update: unavailable,
  }),
);
const admit = Layer.succeed(
  Host.HostToken,
  Host.HostToken.of({ hostToken: (httpEffect) => httpEffect }),
);
const app = HttpRouter.toWebHandler(
  HttpApiBuilder.layer(Host.Api).pipe(
    Layer.provide(
      Layer.mergeAll(host, notebook).pipe(Layer.provideMerge(admit)),
    ),
    Layer.provide(HttpServer.layerServices),
  ),
  { disableLogger: true },
);
afterAll(() => app.dispose());

function request(path: string, init?: RequestInit) {
  return app.handler(new Request(`http://localhost${path}`, init));
}

describe("native HTTP implementation", () => {
  it("decodes path, headers and body into the typed save handler", async () => {
    const response = await request("/notebooks/n/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "save",
        "If-Match": "etag",
      },
      body: "{}",
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(edit);
    expect(save.mock.lastCall?.[0]).toMatchObject({
      params: { notebookId: "n" },
      headers: { idempotencyKey: "save", expectedEtag: "etag" },
      payload: {},
    });
  });

  it.each([
    { cells: [{ id: "c" }], future: true },
    { cells: [{ id: "c", future: true }] },
  ])("rejects a request body with an unknown member: %j", async (body) => {
    const response = await request("/notebooks/n/runtime/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": "run" },
      body: JSON.stringify(body),
    });
    expect(response.status).toBe(400);
  });

  it("encodes a tagged error with its problem status, content type and wire fields", async () => {
    const response = await request("/notebooks/n/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "save",
        "If-Match": "stale",
      },
      body: "{}",
    });
    expect(response.status).toBe(409);
    expect(response.headers.get("content-type")).toContain(
      "application/problem+json",
    );
    expect(await response.json()).toEqual({
      type: "urn:marimo:problem:conflict",
      status: 409,
      title: "Conflict",
      detail: "Stale",
    });
  });

  it("rejects a missing idempotency key before calling the handler", async () => {
    const calls = save.mock.calls.length;
    const response = await request("/notebooks/n/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    expect(response.status).toBe(400);
    expect(save).toHaveBeenCalledTimes(calls);
  });

  it("returns no body for deletion", async () => {
    const response = await request("/notebooks/n", {
      method: "DELETE",
      headers: { "Idempotency-Key": "delete" },
    });
    expect(response.status).toBe(204);
    expect(await response.text()).toBe("");
  });

  it.each([
    ["existing", 200],
    ["new", 202],
  ] as const)(
    "selects runtime start status for %s without wrapping the wire body",
    async (key, status) => {
      const response = await request("/notebooks/n/runtime", {
        method: "PUT",
        headers: { "Content-Type": "application/json", "Idempotency-Key": key },
        body: "{}",
      });
      expect(response.status).toBe(status);
      expect(await response.json()).toEqual(runtime);
    },
  );

  it("decodes event selection and encodes the protocol SSE envelope", async () => {
    const response = await request(
      "/notebooks/n/events?types=ready&run_id=run",
      {
        headers: { "Last-Event-ID": "97", "Marimo-Attachment-Name": "Test" },
      },
    );
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    expect(await response.text()).toBe("id: 98\nevent: ready\ndata: {}\n\n");
    expect(events.mock.lastCall?.[0]).toMatchObject({
      params: { notebookId: "n" },
      query: { types: "ready", runId: "run" },
      headers: { cursor: "97", attachmentName: "Test" },
    });
  });

  it("uses the same API for a typed HTTP client", async () => {
    const result = await Effect.runPromise(
      Effect.gen(function* () {
        const client = yield* HttpApiClient.make(Host.Api, {
          baseUrl: "http://localhost",
        });
        const result = yield* client.Notebook.start({
          params: { notebookId: S.NotebookId.make("n") },
          headers: { idempotencyKey: "new" },
          payload: {},
        });
        const stream = yield* client.Notebook.events({
          params: { notebookId: S.NotebookId.make("n") },
          query: {},
          headers: {},
        });
        const events = yield* Stream.runCollect(stream);
        return { result, events };
      }).pipe(
        Effect.provide(FetchHttpClient.layer),
        Effect.provideService(FetchHttpClient.Fetch, (input, init) =>
          app.handler(new Request(input, init)),
        ),
      ),
    );
    expect(result.result).toEqual({ status: 202, body: runtime });
    expect(result.events).toEqual([{ event: "ready", id: "98", data: {} }]);
  });
});
