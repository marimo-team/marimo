/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, expectTypeOf, it, vi } from "vitest";
import { z } from "zod";
import { Client, NotebookClient } from "../index.ts";
import type * as Protocol from "../protocol.ts";
import { fixtureEvents } from "./fixtures.ts";

const record = fixtureEvents("events.sse").find(
  (event) => event.event === "notebook",
)!.data.notebook;

function connect(response: () => Response) {
  const fetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
    response(),
  );
  const client = new Client(
    "http://localhost/prefix/api/marimo/v1/?session_id=s1",
    {
      token: "secret",
      headers: { "X-Example": "1" },
      fetch,
    },
  );
  const sent = (index = 0) => new Request(...fetch.mock.calls[index]);
  return { client, fetch, sent };
}

describe("Client", () => {
  it("creates a notebook with the shared request conventions", async () => {
    const { client, sent } = connect(() =>
      Response.json(record, { status: 201 }),
    );
    const input = { project_id: "p1", path: "forecasts.py" };
    const result = await client.createNotebook(input, {
      idempotencyKey: "create-1",
    });
    expectTypeOf(result).toEqualTypeOf<
      | {
          readonly ok: true;
          readonly status: number;
          readonly data: Protocol.NotebookOutput;
        }
      | {
          readonly ok: false;
          readonly status: number;
          readonly problem: Protocol.ProblemOutput;
        }
    >();
    expect(result).toEqual({ ok: true, status: 201, data: record });
    const request = sent();
    expect(request.url).toBe(
      "http://localhost/prefix/api/marimo/v1/notebooks?session_id=s1",
    );
    expect(request.method).toBe("POST");
    expect(request.headers.get("Authorization")).toBe("Bearer secret");
    expect(request.headers.get("X-Example")).toBe("1");
    expect(request.headers.get("Idempotency-Key")).toBe("create-1");
    expect(await request.json()).toEqual(input);
  });

  it("constructs notebook clients without fetching or retaining their records", async () => {
    const { client, fetch, sent } = connect(
      () => new Response(null, { status: 204 }),
    );
    const entry = { ...record, id: "n/1?#%" };
    const notebook = client.notebook(entry);
    expect(notebook).toBeInstanceOf(NotebookClient);
    expect(fetch).not.toHaveBeenCalled();
    entry.id = "changed";
    client.url.host = "elsewhere.example";
    await notebook.delete();
    expect(sent().url).toBe(
      "http://localhost/prefix/api/marimo/v1/notebooks/n%2F1%3F%23%25?session_id=s1",
    );
    expect(sent().headers.get("Authorization")).toBe("Bearer secret");
    expect(sent().headers.get("X-Example")).toBe("1");
    expect(client.notebook("n1").url.href).toBe(
      client.notebook(record).url.href,
    );
  });

  it.each(["", ".", ".."])("rejects an invalid notebook id %j", (id) => {
    const { client, fetch } = connect(() => new Response());
    expect(() => client.notebook(id)).toThrow("valid notebook_id");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("validates creation requests and returns host problems", async () => {
    const problem = {
      type: "tag:marimo.io,2026:host/conflict",
      title: "Conflict",
      status: 409,
    };
    const { client, fetch } = connect(() =>
      Response.json(problem, {
        status: 409,
        headers: { "Content-Type": "application/problem+json" },
      }),
    );
    await expect(
      client.createNotebook({ project_id: "" }),
    ).rejects.toBeInstanceOf(z.ZodError);
    expect(fetch).not.toHaveBeenCalled();
    expect(
      await client.createNotebook({ project_id: "p1", path: "forecasts.py" }),
    ).toEqual({
      ok: false,
      status: 409,
      problem,
    });
  });

  it("opens independent catalog streams with inherited connection options", async () => {
    const { client, sent, fetch } = connect(
      () =>
        new Response("id: 41\nevent: ready\ndata: {}\n\n", {
          headers: { "Content-Type": "text/event-stream" },
        }),
    );
    const first = client.events({ types: ["notebook"], cursor: "40" });
    const second = client.events();
    await vi.waitFor(() => expect(second.cursor).toBe("41"));
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(sent().url).toBe(
      "http://localhost/prefix/api/marimo/v1/events?session_id=s1&types=notebook",
    );
    expect(sent().headers.get("Authorization")).toBe("Bearer secret");
    expect(sent().headers.get("X-Example")).toBe("1");
    expect(sent().headers.get("Last-Event-ID")).toBe("40");
    expect(sent(1).headers.get("Last-Event-ID")).toBeNull();
    first.close();
    expect(second.status).not.toBe("closed");
    second.close();
    await Promise.all([first.closed, second.closed]);
  });
});
