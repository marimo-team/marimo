/* Copyright 2026 Marimo. All rights reserved. */

import * as Protocol from "@marimo-team/client/protocol";
import { afterEach, expect, it, vi } from "vitest";
import { initialDocument, protocolFixture } from "./protocol-fixtures";
import { createTestHost } from "./test-host";

afterEach(() => vi.useRealTimers());

it("matches the portable host examples for accepted and conflicting edits", () => {
  const host = createTestHost(initialDocument());
  const accepted = host.process({
    notebookId: "n1",
    idempotencyKey: "accepted",
    changes: Protocol.EditRequest.parse(protocolFixture("edit.json")).changes,
  });
  const expected = Protocol.EditResponse.parse(
    protocolFixture("edit-response.json"),
  );
  expect(accepted.result).toEqual({ ok: true, status: 200, data: expected });
  expect(accepted.update).toEqual(host.document());

  const rejected = host.process({
    notebookId: "n1",
    idempotencyKey: "rejected",
    changes: Protocol.EditRequest.parse(
      protocolFixture("edit-conflict-request.json"),
    ).changes,
  });
  const problem = Protocol.Problem.parse(
    protocolFixture("problems/edit-conflict.json"),
  );
  expect(rejected).toEqual({
    result: {
      ok: false,
      status: 409,
      problem: { ...problem, detail: expect.any(String) },
    },
  });
  expect(host.document().revision).toEqual(expected.document);
});

it("rejects an entire batch when a later precondition is stale", () => {
  const initial = initialDocument();
  const host = createTestHost(initial);
  const result = host.apply([
    { kind: "put_cell", base_etag: null, cell: { id: "created", code: "new" } },
    { kind: "delete_cell", id: "c3", base_etag: "stale" },
  ]);
  expect(result).toMatchObject({
    result: { ok: false, status: 409, problem: { edit: { change: 1 } } },
  });
  expect(host.document()).toEqual(initial);
  expect(result.update).toBeUndefined();
});

it("keeps successful and rejected receipts tied to their original payload and revision", () => {
  vi.useFakeTimers({ now: 0 });
  const host = createTestHost(initialDocument());
  const request = {
    notebookId: "n1",
    idempotencyKey: "original",
    changes: Protocol.EditRequest.parse(protocolFixture("edit.json")).changes,
  };
  const accepted = host.process(request);
  const stale = {
    notebookId: "n1",
    idempotencyKey: "stale",
    changes: Protocol.EditRequest.parse(
      protocolFixture("edit-conflict-request.json"),
    ).changes,
  };
  const rejected = host.process(stale);
  host.apply([
    { kind: "put_cell", base_etag: "*", cell: { id: "c3", code: "later" } },
  ]);
  const latest = host.document();
  expect(host.process(request)).toEqual({ result: accepted.result });
  expect(host.process(stale)).toEqual({ result: rejected.result });
  expect(host.process({ ...request, changes: [] }).result).toMatchObject({
    ok: false,
    status: 409,
  });
  expect(host.document()).toEqual(latest);

  vi.advanceTimersByTime(300_000);
  expect(host.process(request).result).toMatchObject({
    ok: false,
    status: 409,
  });
  expect(host.document()).toEqual(latest);
});
