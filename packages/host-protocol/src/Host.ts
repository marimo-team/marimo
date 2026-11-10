/* Copyright 2026 Marimo. All rights reserved. */

import { Schema, type SchemaRepresentation } from "effect";
import {
  HttpApi,
  HttpApiEndpoint,
  HttpApiGroup,
  HttpApiMiddleware,
  HttpApiSchema,
  HttpApiSecurity,
  OpenApi,
} from "effect/http-api";
import * as S from "./Schemas.ts";
import * as Problems from "./Problems.ts";
import * as P from "./api/Parameters.ts";
import { sseEvents } from "./internal/http.ts";
import { forGenerators } from "./internal/openapi.ts";
import { CatalogEvent, derive } from "./Events.ts";
import { objects, type ObjectKind } from "./Objects.ts";
import * as Notebook from "./Notebook.ts";

export const Event = CatalogEvent;
export type Event = typeof Event.Type;

/** Admits requests that carry the host record's token from this machine. */
export class HostToken extends HttpApiMiddleware.Service<HostToken>()(
  "@marimo-team/host-protocol/Host/HostToken",
  {
    security: {
      hostToken: HttpApiSecurity.bearer.pipe(
        HttpApiSecurity.annotate(
          OpenApi.Description,
          "The `token` from a host record, sent as `Authorization: Bearer\n<token>` on every request. Hosts accept the token only in that\nheader and omit CORS headers. Hosts answer only requests that arrive\nover the machine's own loopback interface. Clients disable redirects\nto keep authenticated requests on that interface.\n",
        ),
      ),
    },
    error: [Problems.UnauthorizedProblem, Problems.ForbiddenProblem],
  },
) {}

export const Create = HttpApiEndpoint.post("create", "/notebooks", {
  headers: P.idempotent,
  payload: S.CreateNotebookRequest,
  success: [
    S.Notebook.pipe(HttpApiSchema.status(201)).annotateKey({
      description: "The notebook was created.",
    }),
  ],
  error: [...Problems.Mutation.members],
})
  .annotate(OpenApi.Identifier, "notebook.create")
  .annotate(OpenApi.Summary, "Create a notebook")
  .annotate(
    OpenApi.Description,
    "Adds an empty notebook to the project. The request carries the\nnotebook's own fields, and the host fills in what it owns. In a\nproject with a `root`, `path` is required and `name` defaults to\nthe filename; if a file already exists at `path`, the host\nanswers `conflict` and leaves it alone. In a project without a\nroot, `name` is required, the host chooses storage, and `path` is\nnull. A request missing the required field is `invalid-request`.\nThe new notebook appears on the catalog stream with this\nrequest's key.\n",
  );

const makeEvents = <E extends Schema.Constraint>(events: E) =>
  HttpApiEndpoint.get("events", "/events", {
    query: Schema.Struct({ types: Schema.optionalKey(P.Types) }).pipe(
      Schema.encodeKeys({ types: "types" }),
    ),
    headers: Schema.Struct({
      cursor: Schema.optionalKey(P.LastEventId),
    }).pipe(Schema.encodeKeys({ cursor: "last-event-id" })),
    success: [
      HttpApiSchema.StreamSse({ events: sseEvents(events) })
        .pipe(HttpApiSchema.status(200))
        .annotateKey({
          description: "The catalog, then changes, as server-sent events.",
        }),
    ],
    error: [...Problems.Common.members],
  })
    .annotate(OpenApi.Identifier, "events")
    .annotate(OpenApi.Summary, "Read the host's catalog as a stream")
    .annotate(
      OpenApi.Description,
      "Sends everything the host has, then every change as it happens.\nThe response is a stream of server-sent events, so it stays open\nand the host appends one event at a time. The catalog is the host\nobject, its projects, notebooks, runtimes, and attachments.\n\nA new connection starts with one event per object the host knows\nabout, parents before children, followed by a `ready` event.\nSnapshot events have no `id`; `ready` and live events have an `id`\nline. The most recent `id` a client has seen is its position in\nthe stream. When a connection drops, the client reconnects and\nsends that position in the `Last-Event-ID` header. If the host\nstill has the events after that point, it sends them with their\noriginal ids and timestamps, even before the new `ready`, and then\n`ready`. If it does not, or the cursor predates a loss of host\nstate, it sends `reset`, and the client discards what it holds and\nreceives the full state again. A client also\ndiscards an incomplete snapshot before reconnecting without a\ncursor. On `reset` it clears its cursor until the next `ready`.\n\n`types` limits the stream to some kinds of object without changing\nids or positions. It also filters the host object; `ready` and\n`reset` are always sent. Keep the same filter when resuming a\ncursor. The host writes a `: ping` comment every fifteen seconds\nwhen nothing else is happening. A client that hears nothing for 45\nseconds treats the connection as lost and reconnects.\n",
    );

export const group = <E extends Schema.Constraint>(events: E) =>
  HttpApiGroup.make("Host").add(Create, makeEvents(events));

/**
 * The API for a table of objects.
 *
 * An extension passes the table with its own rows appended.
 */
export const make = <const Objects extends ReadonlyArray<ObjectKind>>(
  objects: Objects,
) => {
  const derived = derive(objects);
  return HttpApi.make("Host")
    .add(group(derived.CatalogEvent), Notebook.group(derived.NotebookEvent))
    .middleware(HostToken)
    .annotate(HttpApi.AdditionalSchemas, [
      derived.Event,
      derived.ObjectType,
      S.HostRecord,
      Problems.Problem,
      Problems.UnknownProblem,
    ])
    .annotate(OpenApi.Title, "marimo host protocol")
    .annotate(OpenApi.Version, "1.0.0")
    .annotate(
      OpenApi.Description,
      "The contract a marimo host serves so that other programs on the same\nmachine can find it, see what it has, and work with its notebooks. A\nhost is a program that runs marimo notebooks, such as the marimo CLI\nor the VS Code extension. A client is a program that talks to a host\nfrom the outside, such as Pair.\n\nA host writes a small file, the host record, that says where its API\nis and how to authenticate. A client reads that file, opens the host's\nevent stream to learn what it has, and calls the operations the host\nlists. There are two streams: `/events` carries the catalog, and\n`/notebooks/{notebook_id}/events` carries one notebook: its cells and\ndocument, its runtime, and the runs of code against it. Clients ignore\nfields, operation names, event\nnames, and problem types they do not recognize. A change that would\nbreak an existing client requires a new record version and a new base\npath.\n",
    )
    .annotate(OpenApi.Transform, forGenerators);
};

export const Api = make(objects);
export const Group = Api.groups.Host;
export const Events = Group.endpoints.events;

/**
 * How `OpenApi.fromApi` names the schemas of this protocol.
 *
 * Effect calls the wire schema of a class `<Class>Encoded`, so a problem would
 * be published as `NotFoundProblemEncoded`. With this policy it is published
 * as `NotFoundProblem`, the name of its class.
 *
 * ```ts
 * OpenApi.fromApi(Host.Api, { referencePolicy: Host.referencePolicy });
 * ```
 */
export const referencePolicy: SchemaRepresentation.ReferencePolicy = ({
  identifier,
}) => identifier?.replace(/Encoded$/, "");
