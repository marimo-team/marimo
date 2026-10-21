/* Copyright 2026 Marimo. All rights reserved. */
// Generated from protocols/host/openapi.yaml. Do not edit.
// Regenerate with: pnpm --dir packages/client codegen

import * as Protocol from "./protocol.ts";

/**
 * The host API's operations by id.
 *
 * Path parameters are the placeholders in `path`. `query` and `headers`
 * map each parameter to whether it is required. `responses` maps each
 * success status to its schema, `null` for no content, or an event stream.
 * `problems` lists the statuses that answer with a `Problem`.
 */
export const operations = {
  /** Read the host's catalog as a stream. */
  events: {
    method: "GET",
    path: "/events",
    query: { types: false },
    headers: { "Last-Event-ID": false },
    body: null,
    responses: { 200: "text/event-stream" },
    problems: [400, 401, 403, 404, 405, 500],
  },
  /** Create a notebook. */
  "notebook.create": {
    method: "POST",
    path: "/notebooks",
    query: {},
    headers: { "Idempotency-Key": true },
    body: Protocol.CreateNotebookRequest,
    responses: { 201: Protocol.Notebook },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Rename or move a notebook. */
  "notebook.update": {
    method: "PATCH",
    path: "/notebooks/{notebook_id}",
    query: {},
    headers: { "Idempotency-Key": true },
    body: Protocol.UpdateNotebookRequest,
    responses: { 200: Protocol.Notebook },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Delete a notebook. */
  "notebook.delete": {
    method: "DELETE",
    path: "/notebooks/{notebook_id}",
    query: {},
    headers: { "Idempotency-Key": true },
    body: null,
    responses: { 204: null },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Follow one notebook as a stream. */
  "notebook.events": {
    method: "GET",
    path: "/notebooks/{notebook_id}/events",
    query: { types: false, run_id: false },
    headers: {
      "Last-Event-ID": false,
      "Marimo-Attachment-Identity": false,
      "Marimo-Attachment-Kind": false,
      "Marimo-Attachment-Name": false,
    },
    body: null,
    responses: { 200: "text/event-stream" },
    problems: [400, 401, 403, 404, 405, 500],
  },
  /** Change parts of the document. */
  "notebook.edit": {
    method: "POST",
    path: "/notebooks/{notebook_id}/edits",
    query: {},
    headers: { "Idempotency-Key": true },
    body: Protocol.EditRequest,
    responses: { 200: Protocol.EditResponse },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Write the document to the host's store. */
  "notebook.save": {
    method: "POST",
    path: "/notebooks/{notebook_id}/save",
    query: {},
    headers: { "Idempotency-Key": true, "If-Match": false },
    body: Protocol.SaveRequest,
    responses: { 200: Protocol.EditResponse },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Show a notebook in the host's own interface. */
  "notebook.open": {
    method: "POST",
    path: "/notebooks/{notebook_id}/open",
    query: {},
    headers: { "Idempotency-Key": true },
    body: null,
    responses: { 200: Protocol.OpenNotebookResponse },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Start the notebook's runtime, or find the one it has. */
  "runtime.start": {
    method: "PUT",
    path: "/notebooks/{notebook_id}/runtime",
    query: {},
    headers: { "Idempotency-Key": true },
    body: Protocol.StartRuntimeRequest,
    responses: { 200: Protocol.Runtime, 202: Protocol.Runtime },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Stop the notebook's runtime. */
  "runtime.stop": {
    method: "DELETE",
    path: "/notebooks/{notebook_id}/runtime",
    query: {},
    headers: { "Idempotency-Key": true },
    body: null,
    responses: { 202: Protocol.Runtime },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Restart the notebook's kernel. */
  "runtime.restart": {
    method: "POST",
    path: "/notebooks/{notebook_id}/runtime/restart",
    query: {},
    headers: { "Idempotency-Key": true },
    body: null,
    responses: { 202: Protocol.Runtime },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Run code or cells against the notebook's runtime. */
  "runtime.run": {
    method: "POST",
    path: "/notebooks/{notebook_id}/runtime/runs",
    query: {},
    headers: { "Idempotency-Key": true },
    body: Protocol.RunRequest,
    responses: { 202: Protocol.Run },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
  /** Interrupt a run. */
  "runtime.interrupt": {
    method: "DELETE",
    path: "/notebooks/{notebook_id}/runtime/runs/{run_id}",
    query: {},
    headers: { "Idempotency-Key": true },
    body: null,
    responses: { 202: Protocol.Run },
    problems: [400, 401, 403, 404, 405, 409, 500, 501],
  },
} as const;

/** An operation id, such as `notebook.edit`. */
export type OperationId = keyof typeof operations;
