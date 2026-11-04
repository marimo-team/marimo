/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import { Effect, Layer, Redacted, Schema, Stream } from "effect";
import {
  HttpApiBuilder,
  type HttpApiEndpoint,
  type HttpApiGroup,
} from "effect/http-api";
import { HttpRouter, HttpServer } from "effect/http";
import { afterEach, describe, expect, it } from "vitest";
import {
  Conflict,
  DecisionRequired,
  EditResponse,
  HostEvent,
  catalogEvents,
  notebookEvents,
  RuntimeStart,
  toOpenApi,
  Host,
  Notebook,
  NotebookEvent,
  NotFound,
  ReadyEvent,
  Unauthorized,
} from "../index.ts";

type Endpoints = HttpApiGroup.Endpoints<typeof Host.api.groups.host>;
type Operations = {
  readonly [
    Name in Endpoints["identifier"]
  ]: HttpApiEndpoint.HandlerWithIdentifier<
    Endpoints,
    Name,
    HttpApiEndpoint.MiddlewareError<Endpoints>,
    never
  >;
};

const notebook: Notebook = {
  id: "n1",
  project_id: "p1",
  path: "analysis.py",
  name: "Analysis",
  operations: ["notebook.delete"],
  updated_at: null,
};

const disposers: Array<() => Promise<void>> = [];
afterEach(async () => {
  await Promise.all(disposers.splice(0).map((dispose) => dispose()));
});

function makeHost(
  onStreamClosed = () => {},
  overrides: Partial<Operations> = {},
  composition: "helper" | "layers" = "helper",
) {
  const runtime = {
    id: "rt1",
    notebook_id: "n1",
    status: "starting" as const,
    message: null,
    marimo_version: null,
    started_at: "2026-11-04T12:00:00Z",
  };
  const run = {
    id: "run1",
    notebook_id: "n1",
    caused_by: null,
    status: "queued" as const,
    outcome: null,
    started_at: null,
    completed_at: null,
  };
  const edit = Schema.decodeUnknownSync(EditResponse)(
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
  const operations: Operations = {
    events: () =>
      Effect.succeed(
        catalogEvents(
          Stream.make(
            HostEvent.make({ data: { host: { operations: [] } } }),
            ReadyEvent.make({ id: "1", data: {} }),
          ),
        ),
      ),
    "notebook.create": ({ payload }) =>
      payload.path === "exists.py"
        ? Effect.fail(new Conflict({ detail: "The file already exists." }))
        : Effect.succeed({ ...notebook, project_id: payload.project_id }),
    "notebook.update": ({ payload }) =>
      Effect.succeed({ ...notebook, ...payload }),
    "notebook.delete": ({ params }) =>
      params.notebook_id === notebook.id
        ? Effect.void
        : Effect.fail(new NotFound({ detail: params.notebook_id })),
    "notebook.events": () =>
      Effect.succeed(
        notebookEvents(
          Stream.make(
            NotebookEvent.make({ data: { notebook } }),
            ReadyEvent.make({ id: "cursor-1", data: {} }),
          ).pipe(
            Stream.concat(Stream.never),
            Stream.ensuring(Effect.sync(onStreamClosed)),
          ),
        ),
      ),
    "notebook.edit": () => Effect.succeed(edit),
    "notebook.save": ({ payload }) =>
      payload.decisions === undefined
        ? Effect.fail(
            new DecisionRequired({
              decisions: [
                {
                  id: "save",
                  prompt: "Overwrite?",
                  options: [{ id: "yes", label: "Yes" }],
                },
              ],
            }),
          )
        : Effect.succeed(edit),
    "notebook.open": () => Effect.succeed({ url: "http://localhost/notebook" }),
    "runtime.start": ({ payload }) =>
      Effect.succeed(
        payload.decisions?.existing
          ? RuntimeStart.existing(runtime)
          : RuntimeStart.created(runtime),
      ),
    "runtime.stop": () =>
      Effect.succeed({ ...runtime, status: "terminating" as const }),
    "runtime.restart": () => Effect.succeed(runtime),
    "runtime.run": () => Effect.succeed(run),
    "runtime.input": ({ params }) =>
      Effect.succeed({
        id: params.input_id,
        execution_id: "ex1",
        seq: 0,
        prompt: "Value?",
        password: false,
        status: "answered" as const,
      }),
    "runtime.interrupt": () =>
      Effect.succeed({
        ...run,
        status: "completed" as const,
        outcome: "interrupted" as const,
      }),
    ...overrides,
  };
  const handlers = HttpApiBuilder.group(Host.api, "host", (handlers) =>
    handlers
      .handle("events", operations.events)
      .handle("notebook.create", operations["notebook.create"])
      .handle("notebook.update", operations["notebook.update"])
      .handle("notebook.delete", operations["notebook.delete"])
      .handle("notebook.events", operations["notebook.events"])
      .handle("notebook.edit", operations["notebook.edit"])
      .handle("notebook.save", operations["notebook.save"])
      .handle("notebook.open", operations["notebook.open"])
      .handle("runtime.start", operations["runtime.start"])
      .handle("runtime.stop", operations["runtime.stop"])
      .handle("runtime.restart", operations["runtime.restart"])
      .handle("runtime.run", operations["runtime.run"])
      .handle("runtime.input", operations["runtime.input"])
      .handle("runtime.interrupt", operations["runtime.interrupt"]),
  );
  const authorization = Layer.succeed(Host.Authorization, {
    hostToken: (effect, { credential }) =>
      Redacted.value(credential) === "test-token"
        ? effect
        : Effect.fail(new Unauthorized({})),
  });
  const routes =
    composition === "helper"
      ? Host.layer(handlers)
      : HttpApiBuilder.layer(Host.api).pipe(
          Layer.provide(handlers),
          Layer.provideMerge(Host.problems),
        );
  const app = HttpRouter.toWebHandler(
    routes.pipe(
      Layer.provide(authorization),
      Layer.provide(HttpServer.layerServices),
    ),
    { disableLogger: true },
  );
  disposers.push(app.dispose);
  return (path: string, init?: RequestInit) =>
    app.handler(
      new Request(`http://localhost${path}`, {
        ...init,
        headers: {
          authorization: "Bearer test-token",
          "idempotency-key": "request-1",
          "content-type": "application/json",
          ...init?.headers,
        },
      }),
    );
}

describe("handwritten host contract", () => {
  it.each([
    ["PATCH", "/notebooks/n1", { name: "Renamed" }, 200],
    ["POST", "/notebooks/n1/edits", { changes: [] }, 200],
    ["POST", "/notebooks/n1/save", { decisions: { save: "yes" } }, 200],
    ["POST", "/notebooks/n1/open", undefined, 200],
    ["DELETE", "/notebooks/n1/runtime", undefined, 202],
    ["POST", "/notebooks/n1/runtime/restart", undefined, 202],
    ["POST", "/notebooks/n1/runtime/runs", { code: "1 + 1" }, 202],
    ["POST", "/notebooks/n1/runtime/inputs/i1/reply", { value: "answer" }, 200],
    ["DELETE", "/notebooks/n1/runtime/runs/run1", undefined, 202],
  ])("serves %s %s", async (method, path, body, status) => {
    const response = await makeHost()(path, {
      method,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    expect(response.status).toBe(status);
    expect(await response.json()).not.toHaveProperty("_tag");
  });

  it("distinguishes an existing runtime from a newly started one without a wire wrapper", async () => {
    const request = makeHost();
    for (const [body, status] of [
      [{}, 202],
      [{ decisions: { existing: "yes" } }, 200],
    ] as const) {
      const response = await request("/notebooks/n1/runtime", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      expect(response.status).toBe(status);
      expect(await response.json()).toEqual({
        id: "rt1",
        notebook_id: "n1",
        status: "starting",
        message: null,
        marimo_version: null,
        started_at: "2026-11-04T12:00:00Z",
      });
    }
  });

  it("preserves decision-required details for 409 responses", async () => {
    const response = await makeHost()("/notebooks/n1/save", {
      method: "POST",
      body: "{}",
    });
    expect(response.status).toBe(409);
    expect(await response.json()).toMatchObject({
      type: "tag:marimo.io,2026:host/decision-required",
      decisions: [{ id: "save" }],
    });
  });

  it.each(["helper", "layers"] as const)(
    "uses problem responses for routing and malformed requests (%s)",
    async (composition) => {
      const request = makeHost(undefined, {}, composition);
      const missing = await request("/missing");
      expect(missing.status).toBe(404);
      expect(await missing.json()).toMatchObject({
        status: 404,
        type: "tag:marimo.io,2026:host/not-found",
      });
      const method = await request("/notebooks/n1", { method: "PUT" });
      expect(method.status).toBe(405);
      expect(method.headers.get("allow")).toContain("DELETE");
      expect(await method.json()).toMatchObject({ status: 405 });
      const malformed = await request("/notebooks", {
        method: "POST",
        body: "{",
      });
      expect(malformed.status).toBe(400);
      expect(await malformed.json()).toMatchObject({ status: 400 });
      const invalidRun = await request("/notebooks/n1/runtime/runs", {
        method: "POST",
        body: JSON.stringify({ code: "1", cells: [{ id: "c1" }] }),
      });
      expect(invalidRun.status).toBe(400);
    },
  );

  it.each(["helper", "layers"] as const)(
    "redacts defects and serializes SSE failures with the protocol convention (%s)",
    async (composition) => {
      const request = makeHost(
        undefined,
        {
          "notebook.open": () => Effect.die("secret-token"),
          "notebook.events": () =>
            Effect.succeed(
              notebookEvents(
                Stream.fail(new Conflict({ detail: "Replay unavailable" })),
              ),
            ),
        },
        composition,
      );
      const response = await request("/notebooks/n1/open", { method: "POST" });
      expect(response.status).toBe(500);
      const body = await response.text();
      expect(body).not.toContain("secret-token");
      expect(JSON.parse(body)).toMatchObject({
        type: "tag:marimo.io,2026:host/internal",
      });
      const stream = await request("/notebooks/n1/events");
      const text = await stream.text();
      expect(text).toContain("event: effect/httpapi/stream/failure");
      expect(text).toContain('"detail":"Replay unavailable"');
      expect(text).not.toContain("_tag");
      expect(text).not.toContain("cause");
    },
  );

  it("finishes finite catalog streams without leaving a heartbeat running", async () => {
    const response = await makeHost()("/events");
    const text = await response.text();
    expect(text).toContain("event: host");
    expect(text).toContain("event: ready");
  });

  it("decodes requests and encodes the notebook with the declared status", async () => {
    const request = makeHost();
    const response = await request("/notebooks", {
      method: "POST",
      body: JSON.stringify({ project_id: "p2", name: "New notebook" }),
    });
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ ...notebook, project_id: "p2" });
    const invalid = await request("/notebooks", {
      method: "POST",
      body: JSON.stringify({ name: "Missing project" }),
    });
    expect(invalid.status).toBe(400);
    expect(await invalid.json()).toMatchObject({
      type: "tag:marimo.io,2026:host/invalid-request",
      status: 400,
    });
  });

  it("encodes named errors as problems without leaking the Effect tag", async () => {
    const request = makeHost();
    const response = await request("/notebooks", {
      method: "POST",
      body: JSON.stringify({ project_id: "p1", path: "exists.py" }),
    });
    expect(response.status).toBe(409);
    expect(response.headers.get("content-type")).toContain(
      "application/problem+json",
    );
    expect(await response.json()).toEqual({
      type: "tag:marimo.io,2026:host/conflict",
      title: "Conflict",
      status: 409,
      detail: "The file already exists.",
    });
    expect(JSON.parse(JSON.stringify(new Conflict({})))).not.toHaveProperty(
      "_tag",
    );
    const recovered = Effect.fail(new Conflict({})).pipe(
      Effect.catchTag("Conflict", () => Effect.succeed("handled")),
    );
    expect(await Effect.runPromise(recovered)).toBe("handled");
  });

  it.each(["helper", "layers"] as const)(
    "enforces authorization before running handlers (%s)",
    async (composition) => {
      let called = false;
      const request = makeHost(
        undefined,
        {
          "notebook.delete": () =>
            Effect.sync(() => {
              called = true;
            }),
        },
        composition,
      );
      const response = await request("/notebooks/n1", {
        method: "DELETE",
        headers: { authorization: "Bearer wrong" },
      });
      expect(response.status).toBe(401);
      expect(called).toBe(false);
      expect(await response.json()).toMatchObject({
        type: "tag:marimo.io,2026:host/unauthorized",
      });
    },
  );

  it("handles empty responses and typed not-found errors", async () => {
    const request = makeHost();
    const deleted = await request("/notebooks/n1", { method: "DELETE" });
    expect(deleted.status).toBe(204);
    expect(await deleted.text()).toBe("");
    const missing = await request("/notebooks/missing", { method: "DELETE" });
    expect(missing.status).toBe(404);
    expect(await missing.json()).toMatchObject({
      status: 404,
      detail: "missing",
    });
  });

  it("serializes named SSE events and releases the stream on disconnect", async () => {
    let closed = false;
    const response = await makeHost(() => {
      closed = true;
    })("/notebooks/n1/events");
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let text = "";
    while (!text.includes("cursor-1")) {
      const chunk = await reader.read();
      if (chunk.done) throw new Error("Stream ended before ready");
      text += decoder.decode(chunk.value);
    }
    expect(text).toContain(
      `event: notebook\ndata: ${JSON.stringify({ notebook })}\n\n`,
    );
    expect(text).toContain("id: cursor-1\nevent: ready\ndata: {}\n\n");
    expect(text.split("event: notebook")[0]).not.toContain("id:");
    await reader.cancel();
    await expect.poll(() => closed).toBe(true);
  });

  it("validates event payloads and requires the ready cursor", () => {
    expect(() =>
      Schema.decodeUnknownSync(ReadyEvent)({ event: "ready", data: {} }),
    ).toThrow();
    expect(() =>
      Schema.decodeUnknownSync(NotebookEvent)({
        event: "notebook",
        data: { notebook: { id: "n1" } },
      }),
    ).toThrow();
    expect(
      Schema.decodeUnknownSync(NotebookEvent)({
        event: "notebook",
        data: { notebook },
      }),
    ).toEqual({ event: "notebook", data: { notebook } });
  });

  it("exports dotted operations, security, and event models for other languages", () => {
    const spec = toOpenApi();
    expect(spec.paths["/notebooks"].post).toMatchObject({
      operationId: "notebook.create",
      security: [{ hostToken: [] }],
      responses: {
        "201": { content: { "application/json": expect.anything() } },
      },
    });
    expect(spec.paths["/notebooks/{notebook_id}"].delete!.operationId).toBe(
      "notebook.delete",
    );
    expect(spec.components.schemas).toHaveProperty("NotebookEvent");
    expect(spec.components.schemas).toHaveProperty("ReadyEvent");
    expect(spec.components.schemas.ReadyEvent).toMatchObject({
      required: expect.arrayContaining(["id", "event", "data"]),
    });
  });
});
