/* Copyright 2026 Marimo. All rights reserved. */

/** Python adapters that wrap a record in its event. */

interface Node {
  readonly [key: string]: unknown;
}

const isNode = (value: unknown): value is Node =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const PREFIX = "#/components/schemas/";

interface RecordEvent {
  readonly event: string;
  readonly message: string;
  readonly body: string;
  readonly field: string;
  /** Whether the event describes an occurrence, which has a time. */
  readonly timed: boolean;
}

/** Write the module for the document's `Event` union. */
export function events(
  document: unknown,
  options: { readonly command: string },
): string {
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

  const removals = removed.map(([kind, event, message]): RecordEvent => {
    const record = records.get(kind);
    if (record === undefined) {
      throw new Error(`${event} has no corresponding record event`);
    }
    return { ...record, event, message };
  });

  const all = [...records.values()];
  const union = (names: ReadonlyArray<string>) =>
    names.map((name) => `protocol.${name}`).join(" | ");

  return `# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from packages/host-protocol.
# Regenerate with \`${options.command}\`.
"""Wrap records in their events."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, overload

from msgspec import UNSET, UnsetType

from marimo._core import protocol

if TYPE_CHECKING:
    from datetime import datetime

Body: TypeAlias = ${union(all.map((record) => record.body))}
SnapshotBody: TypeAlias = ${union(all.filter((record) => !record.timed).map((record) => record.body))}
RecordEvent: TypeAlias = ${union(all.map((record) => record.event))}
RemovableBody: TypeAlias = ${union(removals.map((removal) => removal.body))}
RemovalEvent: TypeAlias = ${union(removals.map((removal) => removal.event))}

${all
  .map(
    (record) => `@overload
def record(
    value: protocol.${record.body}, *,
    request_id: str | UnsetType = UNSET,
    time: datetime${record.timed ? "" : " | UnsetType = UNSET"},
) -> protocol.${record.event}: ...
`,
  )
  .join("\n")}

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

${all
  .map(
    (record) => `@overload
def body(event: protocol.${record.event}) -> protocol.${record.body}: ...
`,
  )
  .join("\n")}

def body(event: RecordEvent) -> Body:
    """Read a record payload without copying it."""
    match event:
${all
  .map(
    (record) => `        case protocol.${record.event}(data=data):
            return data.${record.field}`,
  )
  .join("\n")}
    raise TypeError(f"Not a record event: {type(event)}")

${removals
  .map(
    (removal) => `@overload
def removed(
    record_type: type[protocol.${removal.body}], object_id: str, *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.${removal.event}: ...
`,
  )
  .join("\n")}

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
            protocol.${removal.message}(id=object_id, request_id=request_id, time=time)
        )`,
  )
  .join("\n")}
    raise TypeError(f"No removal event for {record_type}")
`;
}
