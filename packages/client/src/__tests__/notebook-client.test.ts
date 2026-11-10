/* Copyright 2026 Marimo. All rights reserved. */

import NodeFs from "node:fs";
import NodeUrl from "node:url";
import { afterEach, describe, expect, expectTypeOf, it, vi } from "vitest";
import { z } from "zod";
import {
  NotebookClient,
  type unstable_NotebookCall,
} from "../notebook/client.ts";
import type { OperationsBelow, ProblemOf } from "../request.ts";
import * as Protocol from "../protocol.ts";

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
  it("narrows a failed edit by its problem type", async () => {
    const problem = readFixture("problems/precondition-failed.json");
    const { notebook } = connect(() =>
      json(412, problem, "application/problem+json"),
    );
    const result = await notebook.edit([]);
    if (
      result.ok ||
      result.problem.type !== "urn:marimo:problem:precondition-failed"
    ) {
      throw new Error("Expected a failed precondition");
    }
    expectTypeOf(
      result.problem.document,
    ).toEqualTypeOf<Protocol.DocumentOutput>();
    expectTypeOf(
      result.problem.cell,
    ).toEqualTypeOf<Protocol.CellOutput | null>();
    expectTypeOf(result.problem.index).toEqualTypeOf<number>();
    expectTypeOf(result.problem.status).toEqualTypeOf<412>();
    expect(result.problem).toEqual(problem);
    expectTypeOf<
      Extract<
        ProblemOf<"notebook.delete">,
        { type: "urn:marimo:problem:precondition-failed" }
      >
    >().toEqualTypeOf<never>();
  });

  it.each(["index", "cell", "document"])(
    "rejects a known problem missing %s",
    async (field) => {
      const problem = Protocol.PreconditionFailedProblem.parse(
        readFixture("problems/precondition-failed.json"),
      );
      const incomplete = Object.fromEntries(
        Object.entries(problem).filter(([key]) => key !== field),
      );
      const { notebook } = connect(() =>
        json(412, incomplete, "application/problem+json"),
      );
      await expect(notebook.edit([])).rejects.toBeInstanceOf(z.ZodError);
      await expect(
        over(() => ({ status: 412, body: incomplete })).notebook.edit([]),
      ).rejects.toBeInstanceOf(z.ZodError);
    },
  );

  it("keeps future problem types separate from known variants", async () => {
    const problem = {
      type: "urn:example:quota",
      status: 429,
      title: "Quota exceeded",
      detail: "Retry later",
    };
    const { notebook } = connect(() =>
      json(429, problem, "application/problem+json"),
    );
    const expected = {
      ok: false,
      status: 429,
      problem: {
        type: "unknown",
        uri: problem.type,
        status: 429,
        title: problem.title,
        detail: problem.detail,
      },
    };
    expect(await notebook.edit([])).toEqual(expected);
    expect(
      await over(() => ({ status: 429, body: problem })).notebook.edit([]),
    ).toEqual(expected);
  });

  it("rejects a defined problem that the operation does not declare", async () => {
    const problem = readFixture("problems/precondition-failed.json");
    const { notebook } = connect(() =>
      json(412, problem, "application/problem+json"),
    );
    await expect(notebook.delete()).rejects.toThrow("Unexpected problem");
  });

  it("rejects a problem whose status disagrees with the response", async () => {
    const problem = readFixture("problems/precondition-failed.json");
    const { notebook } = connect(() =>
      json(409, problem, "application/problem+json"),
    );
    await expect(notebook.edit([])).rejects.toThrow(
      "does not match HTTP status",
    );
  });

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

  it("addresses an input and preserves its reply key and empty answer", async () => {
    const response = readFixture("input-reply-response.json");
    const { notebook, sent } = connect(() => json(200, response));

    expect(
      await notebook.input(
        "i/1",
        { value: "" },
        {
          idempotencyKey: "reply-1",
        },
      ),
    ).toEqual({ ok: true, status: 200, data: response });
    const request = sent();
    expect(request.method).toBe("POST");
    expect(request.url).toBe(
      "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/runtime/inputs/i%2F1/reply",
    );
    expect(request.headers.get("Idempotency-Key")).toBe("reply-1");
    expect(await request.json()).toEqual({ value: "" });
  });

  it("keeps the notebook URL's query string and ignores a trailing slash", async () => {
    const problem = readFixture("problems/not-found.json");
    const { notebook, fetch } = connect(
      () => json(404, problem, "application/problem+json"),
      "http://localhost/api/marimo/v1/notebooks/n1/?session_id=s1",
    );
    await notebook.delete();
    await notebook.interrupt();
    expect(fetch.mock.calls.map(([url]) => String(url))).toMatchInlineSnapshot(`
      [
        "http://localhost/api/marimo/v1/notebooks/n1?session_id=s1",
        "http://localhost/api/marimo/v1/notebooks/n1/runtime/interrupt?session_id=s1",
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
      await expect(notebook.cancel({ runId })).rejects.toThrow("valid run_id");
      expect(fetch).not.toHaveBeenCalled();
    },
  );

  it("interrupts without a body and returns the runtime acknowledgement", async () => {
    const receipt = readFixture("interrupt-runtime-response.json");
    const { notebook, sent } = connect(() => json(202, receipt));

    expect(await notebook.interrupt({ idempotencyKey: "interrupt-1" })).toEqual(
      {
        ok: true,
        status: 202,
        data: receipt,
      },
    );
    const request = sent();
    expect(request.method).toBe("POST");
    expect(request.url).toBe(
      "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/runtime/interrupt",
    );
    expect(request.headers.get("Idempotency-Key")).toBe("interrupt-1");
    expect(request.body).toBeNull();
  });

  it("cancels a run by id and returns its record", async () => {
    const run: Protocol.Run = {
      id: "r/1",
      notebook_id: "n1",
      runtime_id: "rt-1",
      cells: [],
      status: "running",
      started_at: "2026-10-01T09:20:01Z",
      completed_at: null,
      outcome: null,
    };
    const { notebook, sent } = connect(() => json(202, run));
    expect(
      await notebook.cancel({ runId: run.id, idempotencyKey: "cancel-1" }),
    ).toEqual({ ok: true, status: 202, data: run });
    const request = sent();
    expect(request.method).toBe("DELETE");
    expect(request.url).toBe(
      "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/runtime/runs/r%2F1",
    );
    expect(request.headers.get("Idempotency-Key")).toBe("cancel-1");
    expect(request.body).toBeNull();
  });

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
    const problem = readFixture("problems/precondition-failed.json");
    const { notebook } = connect(() =>
      json(412, problem, "application/problem+json"),
    );
    expect(await notebook.edit([])).toEqual({
      ok: false,
      status: 412,
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

  it.each(["run", "execute"] as const)(
    "%s submits its payload with request options",
    async (method) => {
      const cells = [{ id: "c1", etag: "etag-1" }];
      const code = "print('hi')";
      const run: Protocol.Run = {
        id: "run-1",
        notebook_id: "n1",
        runtime_id: "rt-1",
        cells: method === "run" ? ["c1"] : [],
        status: "queued",
        started_at: null,
        completed_at: null,
        outcome: null,
      };
      const { notebook, sent } = connect(() => json(202, run));
      const controller = new AbortController();
      const options = { signal: controller.signal, idempotencyKey: "run-key" };
      const result =
        method === "run"
          ? await notebook.run({ cells, ...options })
          : await notebook.execute({ code, ...options });

      expect(result).toEqual({ ok: true, status: 202, data: run });
      const request = sent();
      expect(request.method).toBe("POST");
      expect(request.url).toBe(
        `http://127.0.0.1:2718/api/marimo/v1/notebooks/n1/runtime/${method === "run" ? "runs" : "execute"}`,
      );
      expect(request.headers.get("Idempotency-Key")).toBe("run-key");
      expect(await request.json()).toEqual(
        method === "run" ? { cells } : { code },
      );
      controller.abort();
      expect(request.signal.aborted).toBe(true);
    },
  );

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
      "runtime.execute": "execute",
      "runtime.input": "input",
      "runtime.interrupt": "interrupt",
      "runtime.cancel": "cancel",
    } as const).toExtend<Record<NotebookOperationId, keyof NotebookClient>>();
  });
});

/** A notebook client whose calls `reply` answers. */
function over(reply: (call: unstable_NotebookCall) => unknown) {
  const send = vi.fn(async (call: unstable_NotebookCall) => reply(call));
  const notebook = NotebookClient.unstable_over(send, { notebookId: "n1" });
  return { notebook, send };
}

describe("NotebookClient.unstable_over", () => {
  it("sends each method as its call", async () => {
    const response = readFixture("edit-response.json");
    const { notebook, send } = over(() => ({ status: 200, body: response }));
    const { changes } = readFixture("edit.json") as Protocol.EditRequest;

    expect(await notebook.edit(changes)).toEqual({
      ok: true,
      status: 200,
      data: response,
    });
    expect(send).toHaveBeenLastCalledWith({
      operation: "notebook.edit",
      params: { notebook_id: "n1" },
      headers: { "idempotency-key": expect.stringMatching(/^[\da-f-]{36}$/) },
      body: { changes },
    });

    await notebook.save({
      ifMatch: "etag-1",
      decisions: { environment: "keep" },
      idempotencyKey: "retry-1",
    });
    expect(send).toHaveBeenLastCalledWith({
      operation: "notebook.save",
      params: { notebook_id: "n1" },
      headers: { "idempotency-key": "retry-1", "if-match": "etag-1" },
      body: { decisions: { environment: "keep" } },
    });
  });

  it("names every path parameter and returns problems as values", async () => {
    const problem = {
      type: "urn:marimo:problem:not-found",
      title: "Not found",
      status: 404,
    };
    const { notebook, send } = over(() => ({ status: 404, body: problem }));
    expect(await notebook.cancel({ runId: "r1", idempotencyKey: "k" })).toEqual(
      {
        ok: false,
        status: 404,
        problem,
      },
    );
    expect(send).toHaveBeenCalledWith({
      operation: "runtime.cancel",
      params: { notebook_id: "n1", run_id: "r1" },
      headers: { "idempotency-key": "k" },
      body: undefined,
    });
  });

  it("throws on replies the protocol does not describe", async () => {
    await expect(over(() => ({})).notebook.open()).rejects.toBeInstanceOf(
      z.ZodError,
    );
    await expect(
      over(() => ({ status: 200, body: { unexpected: true } })).notebook.open(),
    ).rejects.toBeInstanceOf(z.ZodError);
  });

  it("stops waiting on abort without sending again", async () => {
    let answer!: (reply: unknown) => void;
    const { notebook, send } = over(
      () => new Promise((resolve) => (answer = resolve)),
    );
    const controller = new AbortController();
    const editing = notebook.edit([], { signal: controller.signal });
    controller.abort();
    await expect(editing).rejects.toBe(controller.signal.reason);
    answer({ status: 200, body: readFixture("edit-response.json") });
    await expect(notebook.edit([], { signal: controller.signal })).rejects.toBe(
      controller.signal.reason,
    );
    expect(send).toHaveBeenCalledOnce();
  });

  it("types each call from the operations table", () => {
    expectTypeOf<unstable_NotebookCall["operation"]>().toEqualTypeOf<
      OperationsBelow<"/notebooks/{notebook_id}">
    >();
    expectTypeOf<
      unstable_NotebookCall<"runtime.interrupt">["params"]
    >().toEqualTypeOf<{
      readonly notebook_id: string;
    }>();
    expectTypeOf<
      unstable_NotebookCall<"runtime.interrupt">["body"]
    >().toEqualTypeOf<undefined>();
    expectTypeOf<
      unstable_NotebookCall<"runtime.cancel">["params"]
    >().toEqualTypeOf<{
      readonly notebook_id: string;
      readonly run_id: string;
    }>();
    expectTypeOf<
      unstable_NotebookCall<"runtime.cancel">["body"]
    >().toEqualTypeOf<undefined>();
    expectTypeOf<unstable_NotebookCall<"notebook.save">["headers"]>().toExtend<{
      readonly "idempotency-key": string;
      readonly "if-match"?: string;
    }>();
    expectTypeOf<
      unstable_NotebookCall<"runtime.stop">["body"]
    >().toEqualTypeOf<undefined>();
    expectTypeOf(over(() => ({})).notebook).not.toHaveProperty("url");
  });
});
