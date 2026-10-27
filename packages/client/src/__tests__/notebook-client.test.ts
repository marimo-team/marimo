/* Copyright 2026 Marimo. All rights reserved. */

import NodeFs from "node:fs";
import NodeUrl from "node:url";
import { afterEach, describe, expect, expectTypeOf, it, vi } from "vitest";
import { z } from "zod";
import { NotebookClient } from "../notebook/client.ts";
import type { OperationsBelow } from "../request.ts";
import type * as Protocol from "../protocol.ts";

const fixtures = new NodeUrl.URL(
  "../../../../protocols/host/fixtures/",
  import.meta.url,
);

function readFixture(name: string): unknown {
  return JSON.parse(
    NodeFs.readFileSync(new NodeUrl.URL(name, fixtures), "utf8"),
  );
}

function json(status: number, body: unknown, type = "application/json") {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": type },
  });
}

/** A notebook client whose requests are answered by `answer`. */
function connect(
  answer: (request: Request) => Response,
  url = "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1",
) {
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    answer(new Request(input, init)),
  );
  const notebook = new NotebookClient(url, {
    token: "secret",
    fetch,
  });
  const sent = () => new Request(...fetch.mock.calls[0]);
  return { notebook, fetch, sent };
}

type NotebookOperationId = OperationsBelow<"/notebooks/{notebook_id}">;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NotebookClient", () => {
  it("sends an edit below the notebook's URL and returns the validated response", async () => {
    const response = readFixture("edit-response.json");
    const { notebook, sent } = connect(() => json(200, response));
    const { changes } = readFixture("edit.json") as Protocol.EditRequest;

    const result = await notebook.edit(changes);

    expect(result).toEqual({ ok: true, status: 200, data: response });
    const request = sent();
    expect(request.method).toBe("POST");
    expect(request.url).toBe(
      "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/edits",
    );
    expect(request.headers.get("Authorization")).toBe("Bearer secret");
    expect(request.headers.get("Idempotency-Key")).toMatch(/^[\da-f-]{36}$/);
    expect(await request.json()).toEqual({ changes });
  });

  it("keeps the notebook URL's query string and ignores a trailing slash", async () => {
    const problem = readFixture("problems/not-found.json");
    const { notebook, fetch } = connect(
      () => json(404, problem, "application/problem+json"),
      "http://localhost/api/marimo/v1/notebooks/n1/?session_id=s1",
    );
    await notebook.delete();
    await notebook.interrupt("r/1");
    expect(fetch.mock.calls.map(([url]) => String(url))).toMatchInlineSnapshot(`
      [
        "http://localhost/api/marimo/v1/notebooks/n1?session_id=s1",
        "http://localhost/api/marimo/v1/notebooks/n1/runtime/runs/r%2F1?session_id=s1",
      ]
    `);
  });

  it("accepts problems and reads their media type without regard to case", async () => {
    const problem = readFixture("problems/not-found.json");
    const { notebook, sent } = connect(() =>
      json(404, problem, "Application/Problem+JSON; charset=utf-8"),
    );
    expect(await notebook.open()).toEqual({ ok: false, status: 404, problem });
    expect(sent().headers.get("Accept")).toBe(
      "application/json, application/problem+json",
    );
  });

  it.each(["", ".", ".."])(
    "rejects the run id %j before sending",
    async (runId) => {
      const { notebook, fetch } = connect(() => json(202, {}));
      await expect(notebook.interrupt(runId)).rejects.toThrow("valid run_id");
      expect(fetch).not.toHaveBeenCalled();
    },
  );

  it("keeps its URL when a caller changes the copy it reads", async () => {
    const { notebook, fetch } = connect(
      () => new Response(null, { status: 204 }),
    );
    notebook.url.host = "attacker.example";
    await notebook.delete();
    expect(String(fetch.mock.calls[0][0])).toBe(
      "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1",
    );
  });

  it("makes idempotency keys outside secure contexts", async () => {
    const { getRandomValues } = globalThis.crypto;
    vi.stubGlobal("crypto", {
      getRandomValues: getRandomValues.bind(globalThis.crypto),
    });
    const { notebook, sent } = connect(() => json(202, {}));
    await notebook.stop().catch(() => undefined);
    expect(sent().headers.get("Idempotency-Key")).toMatch(
      /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/,
    );
  });

  it("returns problems as values", async () => {
    const problem = readFixture("problems/edit-conflict.json");
    const { notebook } = connect(() =>
      json(409, problem, "application/problem+json"),
    );
    expect(await notebook.edit([])).toEqual({
      ok: false,
      status: 409,
      problem,
    });
  });

  it("sends preconditions, decisions, and the caller's idempotency key", async () => {
    const { notebook, sent } = connect(() =>
      json(200, readFixture("edit-response.json")),
    );
    await notebook.save({
      ifMatch: "etag-1",
      decisions: { environment: "keep" },
      idempotencyKey: "retry-1",
    });
    const request = sent();
    expect(request.url).toBe(
      "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/save",
    );
    expect(request.headers.get("If-Match")).toBe("etag-1");
    expect(request.headers.get("Idempotency-Key")).toBe("retry-1");
    expect(await request.json()).toEqual({
      decisions: { environment: "keep" },
    });
  });

  it("accepts empty responses", async () => {
    const { notebook } = connect(() => new Response(null, { status: 204 }));
    expect(await notebook.delete()).toEqual({
      ok: true,
      status: 204,
      data: undefined,
    });
  });

  it("validates requests before sending them", async () => {
    const { notebook, fetch } = connect(() => json(202, {}));
    await expect(notebook.run({ cells: [] })).rejects.toBeInstanceOf(
      z.ZodError,
    );
    expect(fetch).not.toHaveBeenCalled();
  });

  it("throws on answers the protocol does not describe", async () => {
    const { notebook } = connect(() => json(200, { unexpected: true }));
    await expect(notebook.open()).rejects.toBeInstanceOf(z.ZodError);
    const html = connect(() => new Response("<html>", { status: 502 }));
    await expect(html.notebook.open()).rejects.toThrow(
      "Unexpected 502 response to notebook.open",
    );
  });

  it("has a method for each request below a notebook", () => {
    // A new operation below a notebook fails this until it has a method.
    expectTypeOf({
      "notebook.update": "update",
      "notebook.delete": "delete",
      "notebook.open": "open",
      "notebook.edit": "edit",
      "notebook.save": "save",
      "runtime.start": "start",
      "runtime.stop": "stop",
      "runtime.restart": "restart",
      "runtime.run": "run",
      "runtime.interrupt": "interrupt",
    } as const).toExtend<Record<NotebookOperationId, keyof NotebookClient>>();
  });
});
