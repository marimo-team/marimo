/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import {
  HttpApiEndpoint,
  HttpApiGroup,
  HttpApiSchema,
  OpenApi,
} from "effect/http-api";
import * as S from "./Schemas.ts";
import * as Problems from "./Problems.ts";
import * as P from "./api/Parameters.ts";
import { sseEvents, response } from "./internal/http.ts";
import { NotebookEvent } from "./Events.ts";

export const Event = NotebookEvent;
export type Event = typeof Event.Type;

export const Delete = HttpApiEndpoint.delete(
  "delete",
  "/notebooks/:notebook_id",
  {
    params: P.notebook,
    headers: P.idempotent,
    success: [
      Schema.Void.pipe(HttpApiSchema.status(204)).annotateKey({
        description: "The notebook was deleted.",
      }),
    ],
    error: [...Problems.Mutation.members],
  },
)
  .annotate(OpenApi.Identifier, "notebook.delete")
  .annotate(OpenApi.Summary, "Delete a notebook")
  .annotate(
    OpenApi.Description,
    "Deletes the file. While the notebook has a runtime, the host\nanswers `conflict` instead.\n",
  );

export const Edit = HttpApiEndpoint.post(
  "edit",
  "/notebooks/:notebook_id/edits",
  {
    params: P.notebook,
    headers: P.idempotent,
    payload: S.EditRequest,
    success: [
      S.EditResponse.pipe(HttpApiSchema.status(200)).annotateKey({
        description: "The changes were applied.",
      }),
    ],
    error: [...Problems.Mutation.members, Problems.PreconditionFailedProblem],
  },
)
  .annotate(OpenApi.Identifier, "notebook.edit")
  .annotate(OpenApi.Summary, "Change parts of the document")
  .annotate(
    OpenApi.Description,
    "Applies an ordered list of changes to the document as one unit.\nEach change says what it replaces and carries the etag that state\nhad when the client read it, so the host can detect competing\nedits to that state. Every etag is compared with the document as\nit was when the request arrived, so one request can create a cell\nand then place it with the order etag the client read. Cells and\nthe order each have their own etag, so writers can update different\nparts independently. An etag of `*` skips the check. A `put_cell`\nwith a null etag creates the cell, after or before an existing cell\nor at the end; placement has no precondition, so two clients\ninserting at once both succeed.\n\nIf any precondition is stale, nothing is applied and the host\nanswers `precondition-failed`. Its `index` names the first stale\nchange, and it carries the cell and the document as they now\nare. A change that could not apply to any state, such as an\norder that leaves out a cell or names one twice, is\n`invalid-request`.\n\nOn success the document has changed, and every attachment sees\nthe effects on the notebook's stream with this request's key: the\ncells that changed, `cell.removed` for each deleted cell, and then\nthe document, with nothing in between. The response carries the new\netags, as of this edit or a later revision, so a client keeps editing without reading again. A\nchange that changes nothing keeps its etags and sends no events.\nWhether the result has reached the store shows in the document's\n`saved_etag`.\n",
  );

const makeEvents = <E extends Schema.Constraint>(events: E) =>
  HttpApiEndpoint.get("events", "/notebooks/:notebook_id/events", {
    params: P.notebook,
    query: Schema.Struct({
      types: Schema.optionalKey(P.Types),
      runId: Schema.optionalKey(P.RunFilter),
    }).pipe(Schema.encodeKeys({ types: "types", runId: "run_id" })),
    headers: Schema.Struct({
      cursor: Schema.optionalKey(P.LastEventId),
      attachmentIdentity: Schema.optionalKey(P.AttachmentIdentity),
      attachmentKind: Schema.optionalKey(P.AttachmentKind),
      attachmentName: Schema.optionalKey(P.AttachmentName),
    }).pipe(
      Schema.encodeKeys({
        cursor: "last-event-id",
        attachmentIdentity: "marimo-attachment-identity",
        attachmentKind: "marimo-attachment-kind",
        attachmentName: "marimo-attachment-name",
      }),
    ),
    success: [
      HttpApiSchema.StreamSse({ events: sseEvents(events) })
        .pipe(HttpApiSchema.status(200))
        .annotateKey({
          description: "The notebook, then changes, as server-sent events.",
        }),
    ],
    error: [...Problems.Common.members],
  })
    .annotate(OpenApi.Identifier, "notebook.events")
    .annotate(OpenApi.Summary, "Follow one notebook as a stream")
    .annotate(
      OpenApi.Description,
      "Sends the notebook, its cells and document, its runtime, its\nattachments, its runs, their executions, and their items, then\nevery change as it happens. The\nstream follows the same rules as `/events`: a snapshot that ends\nin `ready`, ids as positions, `Last-Event-ID` to resume, `reset`\nwhen the host cannot, a `: ping` comment every fifteen seconds,\nand `types` to limit the kinds sent. The optional `run_id` query\nnarrows the stream to one run. A cursor belongs to the stream it\ncame from.\n\nOpening this stream attaches the client to the notebook. An\nattachment appears on both streams while the connection is open\nand is removed when it closes. Every opening, including a reconnect,\ncreates a separate attachment. The optional\n`Marimo-Attachment-Identity` header supplies its `identity` so\nconsumers can group connections from the same client. A shared\nidentity does not merge attachments or extend their lifetimes.\nThe snapshot includes every run that is not yet completed, with\nits executions and items, plus\nany completed results the host retains. Result retention is\nindependent of replay history. Removed objects are absent from\nsnapshots; a resumable stream carries their removal events.\n\nThe stream may also carry `custom` events: namespaced JSON payloads\nthat describe occurrences rather than object state. These have\ncursors and timestamps and appear only in live delivery and replay.\nA reset cannot recover custom events whose history\nhas expired. `types=custom` selects them. They do not belong to a\nrun and are excluded by `run_id`.\n\nThe opening phase is one consistent cut of the notebook, taken\nunder the lock that changes to the document take, so reading to\n`ready` and closing is a snapshot, and `types=cell,document` is a\nsnapshot of the document alone. Cells arrive before the document\nthat orders them, in the opening phase and after every change, so\neach cell named in `order` is already available to the client.\nThe effects of one change to the document arrive\ntogether, with no other event between them.\n",
    );

export const Open = HttpApiEndpoint.post(
  "open",
  "/notebooks/:notebook_id/open",
  {
    params: P.notebook,
    headers: P.idempotent,
    success: [
      S.OpenNotebookResponse.pipe(HttpApiSchema.status(200)).annotateKey({
        description: "The notebook is being shown.",
      }),
    ],
    error: [...Problems.Mutation.members],
  },
)
  .annotate(OpenApi.Identifier, "notebook.open")
  .annotate(OpenApi.Summary, "Show a notebook in the host's own interface")
  .annotate(
    OpenApi.Description,
    "Opens the notebook where the host normally shows notebooks, such\nas a browser tab or an editor, and returns the URL it used.\nOpening may start a runtime. The host omits its token from the URL,\nand a client opens it exactly as given. If the notebook\ncannot be shown, for example because its file is gone, the host\nanswers `conflict`.\n",
  );

export const Reply = HttpApiEndpoint.post(
  "reply",
  "/notebooks/:notebook_id/runtime/inputs/:input_id/reply",
  {
    params: Schema.Struct({
      notebookId: P.NotebookId,
      inputId: P.InputId,
    }).pipe(
      Schema.encodeKeys({ notebookId: "notebook_id", inputId: "input_id" }),
    ),
    headers: P.idempotent,
    payload: S.InputReplyRequest,
    success: [
      S.Input.pipe(HttpApiSchema.status(200)).annotateKey({
        description:
          "The input is now answered because the host accepted the reply for delivery.",
      }),
    ],
    error: [...Problems.Mutation.members],
  },
)
  .annotate(OpenApi.Identifier, "runtime.input")
  .annotate(OpenApi.Summary, "Answer an execution's pending input")
  .annotate(
    OpenApi.Description,
    "Accepts an answer for delivery to the identified input and returns\nidentity, metadata, and updated status `answered`. Any client\npermitted this operation may answer, regardless of who started\nthe run. The first accepted reply determines the answer.\n\nThe host returns `conflict` for a new request to an answered or\ncancelled input, or `not-found` if the input is unknown, removed,\nor belongs to another notebook. Retrying an accepted request with\nthe same key within the retry window returns the original response,\neven after the execution is removed, under the protocol's\nidempotency rules.\n\nHosts offering `runtime.run` or `runtime.execute` implement this\noperation. See [Answering input](spec.md#answering-input) for delivery semantics.\n",
  );

export const Interrupt = HttpApiEndpoint.post(
  "interrupt",
  "/notebooks/:notebook_id/runtime/interrupt",
  {
    params: P.notebook,
    headers: P.idempotent,
    success: [
      S.Runtime.pipe(HttpApiSchema.status(202)).annotateKey({
        description: "Interruption was requested for the notebook's runtime.",
      }),
    ],
    error: [...Problems.Mutation.members, Problems.NoRuntimeProblem],
  },
)
  .annotate(OpenApi.Identifier, "runtime.interrupt")
  .annotate(OpenApi.Summary, "Interrupt the notebook's runtime")
  .annotate(
    OpenApi.Description,
    "Requests interruption of active work in the notebook's current runtime,\nincluding work with no run or execution record. Queued runs complete\ninterrupted without executing. The runtime stays alive. Interruption\ndoes not roll back work already performed. Pending inputs belonging\nto interrupted work are cancelled.\n\nIf the notebook has no runtime, the host answers `no-runtime`. If its\nruntime is not `running`, the host answers `conflict`. An idle running\nruntime accepts the request as a no-op and does not arm an interrupt\nfor future work.\n\nThe response contains the current runtime and acknowledges the request,\nnot that the work has stopped. Runs and executions report their actual\noutcomes on the stream once they settle; acceptance alone does not\nmark them interrupted. Work without a run record need not acquire one.\nWithin the retry window, repeating the same request returns the original\nacknowledgement without interrupting again, including after new work\nstarts or the runtime is replaced. Hosts offering `runtime.run` or\n`runtime.execute` support this operation.\n",
  );

export const Cancel = HttpApiEndpoint.delete(
  "cancel",
  "/notebooks/:notebook_id/runtime/runs/:run_id",
  {
    params: Schema.Struct({
      notebookId: P.NotebookId,
      runId: P.RunId,
    }).pipe(Schema.encodeKeys({ notebookId: "notebook_id", runId: "run_id" })),
    headers: P.idempotent,
    success: [
      S.Run.pipe(HttpApiSchema.status(202)).annotateKey({
        description: "Cancellation was requested for the run.",
      }),
    ],
    error: [...Problems.Mutation.members],
  },
)
  .annotate(OpenApi.Identifier, "runtime.cancel")
  .annotate(OpenApi.Summary, "Cancel a run")
  .annotate(
    OpenApi.Description,
    "Cancels one queued or running run, leaving other runs untouched.\nA queued run is removed from the queue and completes interrupted\nwithout executing. For a running run, the host interrupts only if\nthat run is still active; its remaining executions end interrupted.\nThe host must not interrupt a successor if the target finishes before\nthe cancellation takes effect. A completed run receives `conflict`.\nPending inputs belonging to cancelled work are cancelled.\n\nThe response acknowledges the request, not completion. The notebook\nstream carries the run and execution outcomes once they settle.\nThe runtime stays alive. A host that lists `runtime.run` or\n`runtime.execute` supports this operation.\n",
  );

export const Restart = HttpApiEndpoint.post(
  "restart",
  "/notebooks/:notebook_id/runtime/restart",
  {
    params: P.notebook,
    headers: P.idempotent,
    success: [
      S.Runtime.pipe(HttpApiSchema.status(202)).annotateKey({
        description:
          "The replacement runtime is starting. Follow its id on a stream.",
      }),
    ],
    error: [...Problems.Mutation.members, Problems.NoRuntimeProblem],
  },
)
  .annotate(OpenApi.Identifier, "runtime.restart")
  .annotate(OpenApi.Summary, "Restart the notebook's kernel")
  .annotate(
    OpenApi.Description,
    "Stops the runtime and starts a new one with a new id. The stream\nshows the old runtime `terminating`, then `runtime.removed`, then\nthe new runtime `starting`, keeping one runtime attached to the\nnotebook at a time. Active and queued runs and their unfinished\nexecutions complete with outcome `interrupted`. Retained\nresults stay and are no longer live. The response carries the replacement\nruntime in its `starting` state. The client follows that id until\nit is `running` or has `failed`. If the notebook has no runtime,\nthe host answers `no-runtime`.\n",
  );

export const Run = HttpApiEndpoint.post(
  "run",
  "/notebooks/:notebook_id/runtime/runs",
  {
    params: P.notebook,
    headers: P.idempotent,
    payload: S.RunRequest,
    success: [
      S.Run.pipe(HttpApiSchema.status(202)).annotateKey({
        description:
          "The run was accepted. Follow it on the notebook's stream.",
      }),
    ],
    error: [
      ...Problems.Mutation.members,
      Problems.NoRuntimeProblem,
      Problems.PreconditionFailedProblem,
    ],
  },
)
  .annotate(OpenApi.Identifier, "runtime.run")
  .annotate(OpenApi.Summary, "Run notebook cells")
  .annotate(
    OpenApi.Description,
    "Runs the cells named in `cells` under the notebook's execution settings,\nwhich determine whether dependent cells run too. Each execution names\nits cell through `cell_id`.\n\nInclude a cell's `etag` to run it only if it still matches what the\nclient read. A missing or changed cell is `precondition-failed` and\nnothing runs. The problem's `index` is the position of that cell\nin `cells`.\n\nReturns a `Run` with status `queued` or `running`. Cell runs and scratch\nexecutions share one queue in acceptance order. Open the notebook\nstream before submitting work to receive its progress and results.\nRun and execution events carry the request's `Idempotency-Key` as\n`request_id`.\n\nA notebook without a runtime returns `no-runtime`. Within the host's\nretry window, repeating the request returns its latest run record\nwithout executing again, even if its outputs have expired.\n",
  );

export const Execute = HttpApiEndpoint.post(
  "execute",
  "/notebooks/:notebook_id/runtime/execute",
  {
    params: P.notebook,
    headers: P.idempotent,
    payload: S.ExecuteRequest,
    success: [
      S.Run.pipe(HttpApiSchema.status(202)).annotateKey({
        description:
          "The run was accepted. Follow it on the notebook's stream.",
      }),
    ],
    error: [...Problems.Mutation.members, Problems.NoRuntimeProblem],
  },
)
  .annotate(OpenApi.Identifier, "runtime.execute")
  .annotate(OpenApi.Summary, "Execute Python with notebook values")
  .annotate(
    OpenApi.Description,
    "Executes Python with access to the notebook's current values without\nadding a cell. New variables and assignments stay within this call.\nObjects are shared with the notebook, so changing a list or dataframe\ncan affect it.\n\nOn marimo hosts, the internal `marimo._code_mode.get_context()` API\nprovides access to notebook cells and captured outputs, along with\nmethods for editing and running cells. The outputs are captured when\nexecution begins.\n\nReturns a `Run` with status `queued` or `running`. Scratch executions\nand cell runs share one queue in acceptance order. Open the notebook\nstream before submitting work to receive its progress and results.\nThe execution includes the submitted code. Run and execution events\ncarry the request's `Idempotency-Key` as `request_id`.\n\nA notebook without a runtime returns `no-runtime`. Within the host's\nretry window, repeating the request returns its latest run record\nwithout executing again, even if its outputs have expired.\n",
  );

export const Start = HttpApiEndpoint.put(
  "start",
  "/notebooks/:notebook_id/runtime",
  {
    params: P.notebook,
    headers: P.idempotent,
    payload: S.StartRuntimeRequest,
    success: [
      response(S.Runtime, 200).annotateKey({
        description: "The notebook already has a runtime.",
      }),
      response(S.Runtime, 202).annotateKey({
        description: "A runtime is starting. Follow it on a stream.",
      }),
    ],
    error: [...Problems.Mutation.members, Problems.DecisionRequiredProblem],
  },
)
  .annotate(OpenApi.Identifier, "runtime.start")
  .annotate(
    OpenApi.Summary,
    "Start the notebook's runtime, or find the one it has",
  )
  .annotate(
    OpenApi.Description,
    "Makes sure the notebook has a running runtime. If it has none, the\nhost starts one and answers `202` with the runtime `starting`. The\nclient then follows `runtime` events for that runtime, on either\nstream, until its status is `running` or `failed`. If the notebook\nalready has a runtime, the host answers `200` with it and starts\nnothing.\n\nSometimes the host needs a choice the client did not make, such as\nwhich environment the kernel should run in. It then answers `409`\nwith a problem of type `decision-required` that lists the options,\nand the client repeats the request with a new `Idempotency-Key`\nand `decisions` filled in. A client that already knows its choice\ncan include `decisions` the first time.\n",
  );

export const Stop = HttpApiEndpoint.delete(
  "stop",
  "/notebooks/:notebook_id/runtime",
  {
    params: P.notebook,
    headers: P.idempotent,
    success: [
      S.Runtime.pipe(HttpApiSchema.status(202)).annotateKey({
        description: "The runtime is shutting down.",
      }),
    ],
    error: [...Problems.Mutation.members, Problems.NoRuntimeProblem],
  },
)
  .annotate(OpenApi.Identifier, "runtime.stop")
  .annotate(OpenApi.Summary, "Stop the notebook's runtime")
  .annotate(
    OpenApi.Description,
    "Ends the runtime for everyone attached to the notebook. A runtime\nthat is still starting is cancelled; a running kernel is shut\ndown. Active and queued runs and their unfinished executions complete\nwith outcome `interrupted`. Retained results stay\nand are no longer live. The notebook and its attachments stay,\nbut Python state is lost. The client follows the\nruntime on a stream until `runtime.removed`. If the notebook has\nno runtime, the host answers `no-runtime`.\n",
  );

export const Save = HttpApiEndpoint.post(
  "save",
  "/notebooks/:notebook_id/save",
  {
    params: P.notebook,
    headers: Schema.Struct({
      idempotencyKey: P.IdempotencyKey,
      expectedEtag: Schema.optionalKey(P.IfMatch),
    }).pipe(
      Schema.encodeKeys({
        idempotencyKey: "idempotency-key",
        expectedEtag: "if-match",
      }),
    ),
    payload: S.SaveRequest,
    success: [
      S.EditResponse.pipe(HttpApiSchema.status(200)).annotateKey({
        description: "The document is in the store.",
      }),
    ],
    error: [
      ...Problems.Mutation.members,
      Problems.PreconditionFailedProblem,
      Problems.DecisionRequiredProblem,
    ],
  },
)
  .annotate(OpenApi.Identifier, "notebook.save")
  .annotate(OpenApi.Summary, "Write the document to the host's store")
  .annotate(
    OpenApi.Description,
    "Writes the document as currently applied, after which `saved_etag`\nequals `etag`. The client sends an empty request body because the\nhost already holds the state. A host that persists every change as\nit applies it need not offer this operation. A client shows a save control\nwhen the notebook lists it, and reads whether anything is unsaved\nfrom the two etags either way.\n\nThe response is an edit response, because a host may rewrite code\nas it saves, for example to format it. Such changes reach the\nstream like any other and the response carries the new etags.\n`If-Match` makes the document etag the client last read a\nprecondition, and the host answers `precondition-failed` when the\ndocument has moved on. If the store has changed since the host\nlast read or wrote it, the host answers `decision-required`,\noffering to overwrite the store or to reload from it, and the\nclient repeats the request with its decision and a new key.\n",
  );

export const Update = HttpApiEndpoint.patch(
  "update",
  "/notebooks/:notebook_id",
  {
    params: P.notebook,
    headers: P.idempotent,
    payload: S.UpdateNotebookRequest,
    success: [
      S.Notebook.pipe(HttpApiSchema.status(200)).annotateKey({
        description: "The notebook as it now is.",
      }),
    ],
    error: [...Problems.Mutation.members],
  },
)
  .annotate(OpenApi.Identifier, "notebook.update")
  .annotate(OpenApi.Summary, "Rename or move a notebook")
  .annotate(
    OpenApi.Description,
    "Changes `path`, `name`, or both. A new `path` moves the file\nunder the same project root, and an attached runtime follows it.\nA new `name` changes the label shown to people. What the file\ncontains is content, which this protocol does not write. If a\nfile already exists at `path`, the host answers `conflict`.\n",
  );

export const group = <E extends Schema.Constraint>(events: E) =>
  HttpApiGroup.make("Notebook").add(
    Delete,
    Edit,
    makeEvents(events),
    Open,
    Reply,
    Interrupt,
    Cancel,
    Restart,
    Run,
    Execute,
    Start,
    Stop,
    Save,
    Update,
  );

export const Events = makeEvents(Event);
export const Group = group(Event);
