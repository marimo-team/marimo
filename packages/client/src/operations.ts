/* Copyright 2026 Marimo. All rights reserved. */
// Generated from packages/host-protocol. Do not edit.
// Regenerate with: pnpm --dir packages/client codegen

import * as Protocol from "./protocol.ts";

/**
 * The host API's operations by id.
 *
 * Path parameters are the placeholders in `path`. `query` and `headers`
 * map each parameter to whether it is required. `responses` maps each
 * success status to its schema, `null` for no content, or an event stream.
 * `problems` maps each error status to the problems it can carry.
 */
export const operations = {
  /** Create a notebook. */
  "notebook.create": {
    method: "POST",
    path: "/notebooks",
    query: {},
    headers: { "idempotency-key": true },
    body: Protocol.CreateNotebookRequest,
    responses: { 201: Protocol.Notebook },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Read the host's catalog as a stream. */
  events: {
    method: "GET",
    path: "/events",
    query: { types: false },
    headers: { "last-event-id": false },
    body: null,
    responses: { 200: "text/event-stream" },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      500: [Protocol.InternalProblem],
    },
  },
  /** Delete a notebook. */
  "notebook.delete": {
    method: "DELETE",
    path: "/notebooks/{notebook_id}",
    query: {},
    headers: { "idempotency-key": true },
    body: null,
    responses: { 204: null },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Rename or move a notebook. */
  "notebook.update": {
    method: "PATCH",
    path: "/notebooks/{notebook_id}",
    query: {},
    headers: { "idempotency-key": true },
    body: Protocol.UpdateNotebookRequest,
    responses: { 200: Protocol.Notebook },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Change parts of the document. */
  "notebook.edit": {
    method: "POST",
    path: "/notebooks/{notebook_id}/edits",
    query: {},
    headers: { "idempotency-key": true },
    body: Protocol.EditRequest,
    responses: { 200: Protocol.EditResponse },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem],
      412: [Protocol.PreconditionFailedProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Follow one notebook as a stream. */
  "notebook.events": {
    method: "GET",
    path: "/notebooks/{notebook_id}/events",
    query: { types: false, run_id: false },
    headers: {
      "last-event-id": false,
      "marimo-attachment-identity": false,
      "marimo-attachment-kind": false,
      "marimo-attachment-name": false,
    },
    body: null,
    responses: { 200: "text/event-stream" },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      500: [Protocol.InternalProblem],
    },
  },
  /** Show a notebook in the host's own interface. */
  "notebook.open": {
    method: "POST",
    path: "/notebooks/{notebook_id}/open",
    query: {},
    headers: { "idempotency-key": true },
    body: null,
    responses: { 200: Protocol.OpenNotebookResponse },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Answer an execution's pending input. */
  "runtime.input": {
    method: "POST",
    path: "/notebooks/{notebook_id}/runtime/inputs/{input_id}/reply",
    query: {},
    headers: { "idempotency-key": true },
    body: Protocol.InputReplyRequest,
    responses: { 200: Protocol.Input },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Interrupt the notebook's runtime. */
  "runtime.interrupt": {
    method: "POST",
    path: "/notebooks/{notebook_id}/runtime/interrupt",
    query: {},
    headers: { "idempotency-key": true },
    body: null,
    responses: { 202: Protocol.Runtime },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem, Protocol.NoRuntimeProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Cancel a run. */
  "runtime.cancel": {
    method: "DELETE",
    path: "/notebooks/{notebook_id}/runtime/runs/{run_id}",
    query: {},
    headers: { "idempotency-key": true },
    body: null,
    responses: { 202: Protocol.Run },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Restart the notebook's kernel. */
  "runtime.restart": {
    method: "POST",
    path: "/notebooks/{notebook_id}/runtime/restart",
    query: {},
    headers: { "idempotency-key": true },
    body: null,
    responses: { 202: Protocol.Runtime },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem, Protocol.NoRuntimeProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Run notebook cells. */
  "runtime.run": {
    method: "POST",
    path: "/notebooks/{notebook_id}/runtime/runs",
    query: {},
    headers: { "idempotency-key": true },
    body: Protocol.RunRequest,
    responses: { 202: Protocol.Run },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem, Protocol.NoRuntimeProblem],
      412: [Protocol.PreconditionFailedProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Execute Python with notebook values. */
  "runtime.execute": {
    method: "POST",
    path: "/notebooks/{notebook_id}/runtime/execute",
    query: {},
    headers: { "idempotency-key": true },
    body: Protocol.ExecuteRequest,
    responses: { 202: Protocol.Run },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem, Protocol.NoRuntimeProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Start the notebook's runtime, or find the one it has. */
  "runtime.start": {
    method: "PUT",
    path: "/notebooks/{notebook_id}/runtime",
    query: {},
    headers: { "idempotency-key": true },
    body: Protocol.StartRuntimeRequest,
    responses: { 200: Protocol.Runtime, 202: Protocol.Runtime },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem, Protocol.DecisionRequiredProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Stop the notebook's runtime. */
  "runtime.stop": {
    method: "DELETE",
    path: "/notebooks/{notebook_id}/runtime",
    query: {},
    headers: { "idempotency-key": true },
    body: null,
    responses: { 202: Protocol.Runtime },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem, Protocol.NoRuntimeProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
  /** Write the document to the host's store. */
  "notebook.save": {
    method: "POST",
    path: "/notebooks/{notebook_id}/save",
    query: {},
    headers: { "idempotency-key": true, "if-match": false },
    body: Protocol.SaveRequest,
    responses: { 200: Protocol.EditResponse },
    problems: {
      400: [Protocol.InvalidRequestProblem],
      401: [Protocol.UnauthorizedProblem],
      403: [Protocol.ForbiddenProblem],
      404: [Protocol.NotFoundProblem],
      409: [Protocol.ConflictProblem, Protocol.DecisionRequiredProblem],
      412: [Protocol.PreconditionFailedProblem],
      500: [Protocol.InternalProblem],
      501: [Protocol.UnsupportedOperationProblem],
    },
  },
} as const;

/** An operation id, such as `notebook.edit`. */
export type OperationId = keyof typeof operations;
