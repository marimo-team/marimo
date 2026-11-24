/* Copyright 2026 Marimo. All rights reserved. */

/** The events each stream carries, derived from the object table. */

import { Schema } from "effect";
import { Cursor, event, message } from "../internal/events.ts";
import { Timestamp } from "./Ids.ts";
import type { ObjectDefinition, StreamName } from "../Objects.ts";

const list = new Intl.ListFormat("en", { type: "conjunction" });
const title = (kind: string) => kind[0].toUpperCase() + kind.slice(1);
const carriers = (streams: ReadonlyArray<StreamName>) =>
  `carried by the ${list.format(streams)} ${streams.length > 1 ? "streams" : "stream"}`;

function changed<
  const Kind extends string,
  S extends Schema.Constraint,
>(object: {
  readonly kind: Kind;
  readonly schema: S;
  readonly streams: ReadonlyArray<StreamName>;
}) {
  const { kind } = object;
  const data = message({ [kind]: object.schema } as {
    readonly [K in Kind]: S;
  }).annotate({
    description: `The data of the \`${kind}\` event. The ${kind} as it now is.`,
    identifier: `${title(kind)}Message`,
  });
  return event(kind, data, { id: Schema.optionalKey(Cursor) }).annotate({
    description: `The \`${kind}\` event, ${carriers(object.streams)}.`,
    identifier: `${title(kind)}Event`,
  });
}

const RemovedMessage = message({
  id: Schema.String.annotateKey({
    description: "The id of the object that was removed.",
  }),
}).annotate({
  description:
    "The data of an event ending in `.removed`. The event name identifies the kind of object to delete from the client's view. Removing a notebook also removes its document and cells, and removing an execution removes its inputs. Clients discard these child records when they receive the parent's removal event.",
  identifier: "RemovedMessage",
});

function removed<const Kind extends string>(object: {
  readonly kind: Kind;
  readonly streams: ReadonlyArray<StreamName>;
}) {
  const name = `${object.kind}.removed` as const;
  return event(name, RemovedMessage, {
    id: Schema.optionalKey(Cursor),
  }).annotate({
    description: `The \`${name}\` event, ${carriers(object.streams)}.`,
    identifier: `${title(object.kind)}RemovedEvent`,
  });
}

export const Custom = Schema.Struct({
  type: Schema.String.check(Schema.isMinCodePoints(1)).annotateKey({
    description:
      "A namespaced event type under a namespace the producer controls, such as `marimo.pair.agent-message`. Clients ignore types they do not recognize while retaining the stream cursor.",
  }),
  data: Schema.Json.annotateKey({
    description:
      "Any JSON value, including null. The producer defines its schema and consumers of the type validate it.",
  }),
}).annotate({
  description:
    "A notebook occurrence with a producer-defined payload. It is replayed\nwhile event history is retained. Delivery is limited to live events\nand replay on the notebook stream, with `run_id` omitted from the\nstream's filters. The notebook is identified by the stream.\n",
  identifier: "Custom",
});

const CustomMessage = Schema.Struct({
  custom: Custom,
  request_id: Schema.optionalKey(
    Schema.String.annotateKey({
      description:
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
    }),
  ),
  time: Timestamp.annotateKey({
    description: "When the host published this event. Preserved on replay.",
  }),
}).annotate({
  description:
    "The data of a `custom` event. This envelope is standardized; the custom type and payload are defined by their producer.",
  identifier: "CustomMessage",
});

const CustomEvent = event("custom", CustomMessage, {
  id: Schema.optionalKey(Cursor),
}).annotate({
  description: "The `custom` event, carried by the notebook stream.",
  identifier: "CustomEvent",
});

const ResetEvent = event("reset", Schema.Record(Schema.String, Schema.Never), {
  id: Schema.optionalKey(Cursor),
}).annotate({
  description: "The `reset` event, carried by every stream.",
  identifier: "ResetEvent",
});

const ReadyEvent = event("ready", Schema.Record(Schema.String, Schema.Never), {
  id: Cursor,
}).annotate({
  description: "The `ready` event, carried by every stream.",
  identifier: "ReadyEvent",
});

type Changed<O> = O extends ObjectDefinition
  ? ReturnType<typeof changed<O["kind"], O["schema"]>>
  : never;
type Removed<O> = O extends ObjectDefinition & { readonly removable: true }
  ? ReturnType<typeof removed<O["kind"]>>
  : never;
type CarriedBy<O, Stream extends StreamName> = O extends ObjectDefinition
  ? Stream extends O["streams"][number]
    ? O
    : never
  : never;

// One schema per object, so every union that carries it shares a definition.
const built = new WeakMap<
  ObjectDefinition,
  ReadonlyArray<Schema.Constraint | undefined>
>();
function build(object: ObjectDefinition) {
  let schemas = built.get(object);
  if (!schemas) {
    schemas = [changed(object), object.removable ? removed(object) : undefined];
    built.set(object, schemas);
  }
  return schemas;
}

function carriedBy<
  const Objects extends ReadonlyArray<ObjectDefinition>,
  const Stream extends StreamName,
>(objects: Objects, stream: Stream) {
  return objects.filter(
    (object): object is CarriedBy<Objects[number], Stream> =>
      object.streams.includes(stream),
  );
}

// Each object contributes its event and its `.removed` event when it has one.
function events<
  const Objects extends ReadonlyArray<ObjectDefinition>,
  const Others extends ReadonlyArray<Schema.Constraint> = readonly [],
>(objects: Objects, others?: Others) {
  const members = [
    ...objects.map((object) => build(object)[0]),
    ...(others ?? []),
    ...objects.flatMap((object) => build(object)[1] ?? []),
    ResetEvent,
    ReadyEvent,
  ] as unknown as ReadonlyArray<
    | Changed<Objects[number]>
    | Removed<Objects[number]>
    | Others[number]
    | typeof ResetEvent
    | typeof ReadyEvent
  >;
  return Schema.Union(members);
}

/** Derive the stream schemas from the published objects. */
export function derive<const Objects extends ReadonlyArray<ObjectDefinition>>(
  objects: Objects,
) {
  const kinds = (stream: StreamName) =>
    carriedBy(objects, stream).map((object) => object.kind);
  return {
    CatalogStreamEvent: events(carriedBy(objects, "catalog")).annotate({
      description: "Any event the catalog stream carries.",
      identifier: "CatalogStreamEvent",
    }),
    NotebookStreamEvent: events(carriedBy(objects, "notebook"), [
      CustomEvent,
    ]).annotate({
      description: "Any event a notebook stream carries.",
      identifier: "NotebookStreamEvent",
    }),
    Event: events(objects, [CustomEvent]).annotate({
      description:
        "A record, removal, or control message from a host stream. The data is decoded JSON. Snapshot records and reset events omit the cursor, and ready and live events carry it. Unknown event names belong to later versions or host extensions.",
      identifier: "Event",
    }),
    ObjectKind: Schema.Literals([
      ...objects.map((object) => object.kind),
      "custom",
    ]).annotate({
      description: `The kinds a stream carries, and the values \`kinds\` accepts. The catalog stream carries ${list.format(kinds("catalog"))}. A notebook's stream carries ${list.format([...kinds("notebook"), "custom"])}. Custom events describe occurrences rather than object state.`,
      identifier: "ObjectKind",
    }),
  };
}
