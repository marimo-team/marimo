/* Copyright 2026 Marimo. All rights reserved. */

/** Python adapters that wrap a record in its event. */

interface Node {
  readonly [key: string]: unknown;
}

const isNode = (value: unknown): value is Node =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const PREFIX = "#/components/schemas/";

export interface RecordEvent {
  readonly event: string;
  readonly message: string;
  readonly body: string;
  readonly field: string;
  /** Whether the event describes an occurrence, which has a time. */
  readonly timed: boolean;
}

export interface Removal extends RecordEvent {
  readonly id: string;
}

/**
 * The events of the document's `Event` union that carry a record, and those
 * that say one was removed.
 */
export function carried(document: unknown): {
  readonly records: ReadonlyArray<RecordEvent>;
  readonly removals: ReadonlyArray<Removal>;
  /** One message for every removal, when they differ only in their id. */
  readonly removed:
    | { readonly name: string; readonly like: string }
    | undefined;
} {
  const components = isNode(document) ? document.components : undefined;
  const schemas = isNode(components) ? components.schemas : undefined;
  if (!isNode(schemas)) {
    throw new Error("The document has no component schemas");
  }
  const schema = (name: string): Node => {
    const found = schemas[name];
    if (!isNode(found)) {
      throw new Error(`The document has no schema named ${name}`);
    }
    return found;
  };
  const properties = (name: string): Node => {
    const found = schema(name).properties;
    if (!isNode(found)) {
      throw new Error(`${name} has no properties`);
    }
    return found;
  };
  const reference = (value: unknown): string | undefined =>
    isNode(value) && typeof value.$ref === "string"
      ? value.$ref.slice(PREFIX.length)
      : undefined;
  const required = (name: string): ReadonlyArray<unknown> => {
    const found = schema(name).required;
    return Array.isArray(found) ? found : [];
  };

  const members = schema("Event").anyOf;
  const named = new Map<string, string>();
  for (const member of Array.isArray(members) ? members : []) {
    const name = reference(member);
    if (name === undefined) {
      throw new Error("Each event must be a named schema");
    }
    const tag = properties(name).event;
    const tags = isNode(tag) && Array.isArray(tag.enum) ? tag.enum : [];
    if (tags.length !== 1) {
      throw new Error(`${name} must name one event`);
    }
    named.set(String(tags[0]), name);
  }

  const records = new Map<string, RecordEvent>();
  const removed: Array<
    readonly [kind: string, event: string, message: string]
  > = [];
  for (const [tag, event] of [...named].toSorted(([a], [b]) =>
    a < b ? -1 : 1,
  )) {
    const message = reference(properties(event).data);
    if (message === undefined) {
      continue; // Control events have no record.
    }
    if (tag.endsWith(".removed")) {
      removed.push([tag.slice(0, -".removed".length), event, message]);
      continue;
    }
    const fields = Object.entries(properties(message)).flatMap(
      ([field, value]) => {
        const body = reference(value);
        return body !== undefined &&
          schema(body).type === "object" &&
          required(message).includes(field)
          ? [[field, body] as const]
          : [];
      },
    );
    if (fields.length !== 1) {
      throw new Error(`${message} must contain one required record`);
    }
    const [[field, body]] = fields;
    const others = Object.keys(properties(message)).filter(
      (key) => key !== field,
    );
    if (others.toSorted().join() !== "request_id,time") {
      throw new Error(`Unsupported event metadata in ${message}`);
    }
    records.set(tag, {
      event,
      message,
      body,
      field,
      timed: required(message).includes("time"),
    });
  }

  const removals = removed.map(([kind, event, message]): Removal => {
    const record = records.get(kind);
    const id = reference(properties(message).id);
    if (record === undefined || id === undefined) {
      throw new Error(`${event} has no corresponding record event`);
    }
    return { ...record, event, message, id };
  });
  const shape = (message: string) =>
    JSON.stringify({
      ...schema(message),
      description: undefined,
      properties: { ...properties(message), id: undefined },
    });
  const alike =
    removals.length > 1 &&
    !("RemovedMessage" in schemas) &&
    removals.every(
      (removal) => shape(removal.message) === shape(removals[0].message),
    );
  return {
    records: [...records.values()],
    removals,
    removed: alike
      ? { name: "RemovedMessage", like: removals[0].message }
      : undefined,
  };
}

/** Write the module for the document's `Event` union. */
export function events(
  document: unknown,
  options: { readonly command: string },
): string {
  const { records: all, removals, removed } = carried(document);
  const union = (names: ReadonlyArray<string>) =>
    names.map((name) => `protocol.${name}`).join(" | ");

  return `# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from packages/host-protocol.
# Regenerate with \`${options.command}\`.
"""Wrap records in their events."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from msgspec import UNSET, UnsetType

from marimo._core import protocol

if TYPE_CHECKING:
    from datetime import datetime

Body: TypeAlias = ${union(all.map((record) => record.body))}
SnapshotBody: TypeAlias = ${union(all.filter((record) => !record.timed).map((record) => record.body))}
RecordEvent: TypeAlias = ${union(all.map((record) => record.event))}
RemovableBody: TypeAlias = ${union(removals.map((removal) => removal.body))}
RemovalEvent: TypeAlias = ${union(removals.map((removal) => removal.event))}

def record(
    value: Body, *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> RecordEvent:
    """Wrap a record without copying it; occurrences require a timestamp."""
    match value:
${all
  .map(
    (record) => `        case protocol.${record.body}():${
      record.timed
        ? `
            if isinstance(time, UnsetType):
                raise ValueError("${record.event} requires an emission time")`
        : ""
    }
            return protocol.${record.event}(
                protocol.${record.message}(${record.field}=value, request_id=request_id, time=time)
            )`,
  )
  .join("\n")}
    raise TypeError(f"Unsupported record type: {type(value)}")

def removed(
    record_type: type[RemovableBody], object_id: str, *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> RemovalEvent:
    """Construct the removal envelope for a supported record type."""
${removals
  .map(
    (removal) => `    if record_type is protocol.${removal.body}:
        return protocol.${removal.event}(
            protocol.${removed?.name ?? removal.message}(
                id=protocol.${removal.id}(object_id), request_id=request_id, time=time
            )
        )`,
  )
  .join("\n")}
    raise TypeError(f"No removal event for {record_type}")
`;
}
