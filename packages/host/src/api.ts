/* Copyright 2026 Marimo. All rights reserved. */

import { Schema, SchemaTransformation } from "effect";
import {
  HttpApi,
  HttpApiEndpoint,
  HttpApiGroup,
  HttpApiMiddleware,
  HttpApiSchema,
  HttpApiSecurity,
  OpenApi,
} from "effect/http-api";
import {
  AttachmentIdentity,
  AttachmentKind,
  AttachmentName,
} from "./catalog.ts";
import { ItemId, NotebookId, RunId } from "./common.ts";
import { EditRequest, EditResponse, RunRequest, SaveRequest } from "./edits.ts";
import {
  Conflict,
  DecisionRequired,
  Forbidden,
  Internal,
  InvalidRequest,
  MethodNotAllowed,
  NoRuntime,
  NotAcceptable,
  NotFound,
  Unauthorized,
  UnsupportedOperation,
} from "./errors.ts";
import {
  AnalysisNotebookEvent,
  CatalogEvent,
  eventCodec,
  NotebookStreamEvent,
} from "./events.ts";
import {
  Input,
  InputReplyRequest,
  Run,
  Runtime,
  StartRuntimeRequest,
} from "./execution.ts";
import {
  CreateNotebookRequest,
  Notebook,
  OpenNotebookResponse,
  UpdateNotebookRequest,
} from "./notebook.ts";

export class HostAuthorization extends HttpApiMiddleware.Service<HostAuthorization>()(
  "@marimo-team/host/HostAuthorization",
  {
    security: { hostToken: HttpApiSecurity.bearer },
    error: [Unauthorized, Forbidden],
  },
) {}
export class HostProblems extends HttpApiMiddleware.Service<HostProblems>()(
  "@marimo-team/host/HostProblems",
  {
    error: [
      InvalidRequest,
      Internal,
      NotFound,
      MethodNotAllowed,
      NotAcceptable,
    ],
  },
) {}

const mutationHeaders = { "idempotency-key": Schema.String };
const notebookParams = { notebook_id: NotebookId };
const streamHeaders = { "last-event-id": Schema.optionalKey(Schema.String) };
const streamQuery = { types: Schema.optionalKey(Schema.String) };
const mutations = [Conflict, UnsupportedOperation] as const;
const runtimeMutations = [...mutations, NoRuntime] as const;

const runtimeResult = <const Created extends boolean>(
  created: Created,
  status: number,
) =>
  Runtime.pipe(
    Schema.decodeTo(
      Schema.Struct({ created: Schema.Literal(created), runtime: Runtime }),
      SchemaTransformation.transform({
        decode: (runtime) => ({ created, runtime }),
        encode: (result) => result.runtime,
      }),
    ),
    HttpApiSchema.status(status),
  );
const ExistingRuntime = runtimeResult(false, 200);
const CreatedRuntime = runtimeResult(true, 202);
export type RuntimeStartResult =
  | typeof ExistingRuntime.Type
  | typeof CreatedRuntime.Type;
export const RuntimeStart = {
  existing: (runtime: Runtime): typeof ExistingRuntime.Type => ({
    created: false,
    runtime,
  }),
  created: (runtime: Runtime): typeof CreatedRuntime.Type => ({
    created: true,
    runtime,
  }),
};

function makeApi<Events extends Schema.Top>(events: Events) {
  const host = HttpApiGroup.make("host")
    .add(
      HttpApiEndpoint.get("events", "/events", {
        query: streamQuery,
        headers: streamHeaders,
        success: HttpApiSchema.StreamSse({ events: eventCodec(CatalogEvent) }),
      })
        .annotate(OpenApi.Identifier, "events")
        .annotate(OpenApi.Summary, "Read the host catalog as a stream"),
      HttpApiEndpoint.post("notebook.create", "/notebooks", {
        headers: mutationHeaders,
        payload: CreateNotebookRequest,
        success: Notebook.pipe(HttpApiSchema.status(201)),
        error: mutations,
      })
        .annotate(OpenApi.Identifier, "notebook.create")
        .annotate(OpenApi.Summary, "Create a notebook"),
      HttpApiEndpoint.patch("notebook.update", "/notebooks/:notebook_id", {
        params: notebookParams,
        headers: mutationHeaders,
        payload: UpdateNotebookRequest,
        success: Notebook,
        error: mutations,
      })
        .annotate(OpenApi.Identifier, "notebook.update")
        .annotate(OpenApi.Summary, "Rename or move a notebook"),
      HttpApiEndpoint.delete("notebook.delete", "/notebooks/:notebook_id", {
        params: notebookParams,
        headers: mutationHeaders,
        success: HttpApiSchema.NoContent,
        error: mutations,
      })
        .annotate(OpenApi.Identifier, "notebook.delete")
        .annotate(OpenApi.Summary, "Delete a notebook"),
      HttpApiEndpoint.get("notebook.events", "/notebooks/:notebook_id/events", {
        params: notebookParams,
        query: { ...streamQuery, run_id: Schema.optionalKey(RunId) },
        headers: {
          ...streamHeaders,
          "marimo-attachment-identity": Schema.optionalKey(AttachmentIdentity),
          "marimo-attachment-kind": Schema.optionalKey(AttachmentKind),
          "marimo-attachment-name": Schema.optionalKey(AttachmentName),
        },
        success: HttpApiSchema.StreamSse({ events: eventCodec(events) }),
      })
        .annotate(OpenApi.Identifier, "notebook.events")
        .annotate(OpenApi.Summary, "Follow a notebook as a stream"),
      HttpApiEndpoint.post("notebook.edit", "/notebooks/:notebook_id/edits", {
        params: notebookParams,
        headers: mutationHeaders,
        payload: EditRequest,
        success: EditResponse,
        error: mutations,
      })
        .annotate(OpenApi.Identifier, "notebook.edit")
        .annotate(OpenApi.Summary, "Change parts of the document"),
      HttpApiEndpoint.post("notebook.save", "/notebooks/:notebook_id/save", {
        params: notebookParams,
        headers: {
          ...mutationHeaders,
          "if-match": Schema.optionalKey(Schema.String),
        },
        payload: SaveRequest,
        success: EditResponse,
        error: [...mutations, DecisionRequired],
      })
        .annotate(OpenApi.Identifier, "notebook.save")
        .annotate(OpenApi.Summary, "Write the document to the host store"),
      HttpApiEndpoint.post("notebook.open", "/notebooks/:notebook_id/open", {
        params: notebookParams,
        headers: mutationHeaders,
        success: OpenNotebookResponse,
        error: mutations,
      })
        .annotate(OpenApi.Identifier, "notebook.open")
        .annotate(OpenApi.Summary, "Show a notebook in the host interface"),
      HttpApiEndpoint.put("runtime.start", "/notebooks/:notebook_id/runtime", {
        params: notebookParams,
        headers: mutationHeaders,
        payload: StartRuntimeRequest,
        success: [ExistingRuntime, CreatedRuntime],
        error: [...mutations, DecisionRequired],
      })
        .annotate(OpenApi.Identifier, "runtime.start")
        .annotate(
          OpenApi.Summary,
          "Start the notebook runtime or find the one it has",
        ),
      HttpApiEndpoint.delete(
        "runtime.stop",
        "/notebooks/:notebook_id/runtime",
        {
          params: notebookParams,
          headers: mutationHeaders,
          success: Runtime.pipe(HttpApiSchema.status(202)),
          error: runtimeMutations,
        },
      )
        .annotate(OpenApi.Identifier, "runtime.stop")
        .annotate(OpenApi.Summary, "Stop the notebook runtime"),
      HttpApiEndpoint.post(
        "runtime.restart",
        "/notebooks/:notebook_id/runtime/restart",
        {
          params: notebookParams,
          headers: mutationHeaders,
          success: Runtime.pipe(HttpApiSchema.status(202)),
          error: runtimeMutations,
        },
      )
        .annotate(OpenApi.Identifier, "runtime.restart")
        .annotate(OpenApi.Summary, "Restart the notebook kernel"),
      HttpApiEndpoint.post(
        "runtime.run",
        "/notebooks/:notebook_id/runtime/runs",
        {
          params: notebookParams,
          headers: mutationHeaders,
          payload: RunRequest,
          success: Run.pipe(HttpApiSchema.status(202)),
          error: runtimeMutations,
        },
      )
        .annotate(OpenApi.Identifier, "runtime.run")
        .annotate(
          OpenApi.Summary,
          "Run code or cells against the notebook runtime",
        ),
      HttpApiEndpoint.post(
        "runtime.input",
        "/notebooks/:notebook_id/runtime/inputs/:input_id/reply",
        {
          params: { ...notebookParams, input_id: ItemId },
          headers: mutationHeaders,
          payload: InputReplyRequest,
          success: Input,
          error: mutations,
        },
      )
        .annotate(OpenApi.Identifier, "runtime.input")
        .annotate(OpenApi.Summary, "Answer an execution's pending input"),
      HttpApiEndpoint.delete(
        "runtime.interrupt",
        "/notebooks/:notebook_id/runtime/runs/:run_id",
        {
          params: { ...notebookParams, run_id: RunId },
          headers: mutationHeaders,
          success: Run.pipe(HttpApiSchema.status(202)),
          error: runtimeMutations,
        },
      )
        .annotate(OpenApi.Identifier, "runtime.interrupt")
        .annotate(OpenApi.Summary, "Interrupt a run"),
    )
    .middleware(HostAuthorization)
    .middleware(HostProblems);
  return HttpApi.make("marimo-host")
    .add(host)
    .annotate(OpenApi.Title, "marimo host protocol")
    .annotate(OpenApi.Version, "1.0.0");
}

export const HostApi = makeApi(NotebookStreamEvent);
export const AnalysisHostApi = makeApi(AnalysisNotebookEvent);
