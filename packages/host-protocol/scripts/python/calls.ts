/* Copyright 2026 Marimo. All rights reserved. */

/** Python operations, from the API's endpoints. */

import { type Schema, SchemaRepresentation } from "effect";
import { type HttpApi, OpenApi } from "effect/http-api";
import { referencePolicy } from "../../src/Host.ts";
import * as Problems from "../../src/Problems.ts";

type Representation = SchemaRepresentation.Representation;

/** The wire side of a schema, with named schemas left as references. */
const wire = (schema: Schema.Top): Representation =>
  SchemaRepresentation.toRepresentation(schema.ast, { referencePolicy })
    .representation;

/** The Python type for the few shapes a request part or a response takes. */
function type(representation: Representation): string {
  switch (representation._tag) {
    case "Reference":
      return `protocol.${representation.$ref}`;
    case "String":
      return "str";
    case "Null":
      return "None";
    default:
      throw new Error(`No Python type for ${representation._tag}`);
  }
}

interface Field {
  readonly name: string;
  readonly wire: string;
  readonly type: string;
  readonly optional: boolean;
}

/** The fields of a request part, required ones first as msgspec needs. */
function fields(schema: Schema.Top | undefined): ReadonlyArray<Field> {
  if (schema === undefined) {
    return [];
  }
  const representation = wire(schema);
  if (representation._tag !== "Objects") {
    throw new Error("A request part must be an object");
  }
  return representation.propertySignatures
    .map((signature) => {
      const name = String(signature.name);
      return {
        name: name.replaceAll("-", "_"),
        wire: name,
        type: type(signature.type),
        optional: signature.isOptional,
      };
    })
    .toSorted((a, b) => Number(a.optional) - Number(b.optional));
}

const problemName = (schema: Schema.Top): string =>
  type(wire(schema)).replace(/^protocol\./, "");

// Widest first, so an operation is described by the widest set it declares.
const problemSets = Object.entries({
  Common: Problems.Common,
  Mutation: Problems.Mutation,
})
  .map(([name, union]) => ({
    name: `${name}Problem`,
    members: union.members.map(problemName),
  }))
  .toSorted((a, b) => b.members.length - a.members.length);

/** Problems as the widest named set among them and the rest. */
function union(problems: ReadonlyArray<string>, except?: string): string {
  const within = problemSets.find(
    ({ name, members }) =>
      name !== except && members.every((member) => problems.includes(member)),
  );
  return [
    ...(within ? [within.name] : []),
    ...problems
      .filter((problem) => !within?.members.includes(problem))
      .map((problem) => `protocol.${problem}`),
  ].join(" | ");
}

interface Operation {
  readonly id: string;
  readonly group: string;
  readonly handler: string;
  readonly name: string;
  readonly summary: string;
  /** The one status the operation answers with, if it only has one. */
  readonly status: number | undefined;
  readonly method: string;
  readonly path: string;
  readonly params: ReadonlyArray<Field>;
  readonly headers: ReadonlyArray<Field>;
  readonly body: string | undefined;
  readonly success: string;
  readonly problems: string;
}

const title = (name: string) => name[0].toUpperCase() + name.slice(1);
const sentence = (text: string) => (text.endsWith(".") ? text : `${text}.`);

const indent = (text: string, depth: number) =>
  text
    .split("\n")
    .map((line) => (line === "" ? line : "    ".repeat(depth) + line))
    .join("\n");

function part(name: string, members: ReadonlyArray<Field>): string {
  const lines = members.map((field) => {
    if (field.name === field.wire && !field.optional) {
      return `${field.name}: ${field.type}`;
    }
    const options = [
      ...(field.name === field.wire ? [] : [`name="${field.wire}"`]),
      ...(field.optional ? ["default=None"] : []),
    ];
    return `${field.name}: ${field.type}${field.optional ? " | None" : ""} = msgspec.field(${options.join(", ")})`;
  });
  return `class ${name}(msgspec.Struct, frozen=True):\n${indent(lines.join("\n"), 1)}\n`;
}

function operation(op: Operation): string {
  const self = `${op.group}.${op.name}`;
  return [
    `class ${op.name}:`,
    indent(
      [
        `"""${op.summary}"""`,
        "",
        `ID: Final = "${op.id}"`,
        `METHOD: Final = "${op.method}"`,
        `PATH: Final = "${op.path}"`,
        "",
        ...(op.params.length > 0 ? [part("Params", op.params)] : []),
        ...(op.headers.length > 0 ? [part("Headers", op.headers)] : []),
        `class Call(msgspec.Struct, frozen=True, tag_field="operation", tag="${op.id}"):`,
        indent(
          [
            ...(op.params.length > 0 ? [`params: ${self}.Params`] : []),
            ...(op.headers.length > 0 ? [`headers: ${self}.Headers`] : []),
            ...(op.body === undefined ? [] : [`body: ${op.body}`]),
          ].join("\n"),
          1,
        ),
        "",
        `Result: TypeAlias = result.Result[${op.success}, ${op.problems}]`,
      ].join("\n"),
      1,
    ),
    "",
  ].join("\n");
}

/** Write the module for the endpoints that `reflect` visits. */
export function calls(
  reflect: (visit: Parameters<typeof HttpApi.reflect>[1]) => void,
  options: { readonly command: string },
): string {
  const { command } = options;
  const groups = new Map<string, Array<Operation>>();
  const collect: Parameters<typeof HttpApi.reflect>[1] = {
    onGroup: ({ group }) => {
      groups.set(group.identifier, []);
    },
    onEndpoint: ({ group, endpoint, mergedAnnotations, successes }) => {
      const annotation = (key: string): string => {
        const value = mergedAnnotations.mapUnsafe.get(key);
        if (typeof value !== "string") {
          throw new Error(`${endpoint.identifier} has no ${key}`);
        }
        return value;
      };
      // A reply with no status is a stream, which is not a single result.
      if (successes.size === 0) {
        return;
      }
      const bodies = [...endpoint.payload.values()].flatMap(({ schemas }) =>
        [...schemas].map((schema) => type(wire(schema))),
      );
      if (bodies.length > 1) {
        throw new Error(`${endpoint.identifier} takes more than one body`);
      }
      const replies = new Map<string, Array<number>>();
      for (const [status, schemas] of successes) {
        for (const schema of schemas) {
          const body = type(wire(schema));
          replies.set(body, [...(replies.get(body) ?? []), status]);
        }
      }
      const statuses = [...replies.values()].flat();
      groups.get(group.identifier)?.push({
        id: annotation(OpenApi.Identifier.key),
        group: group.identifier,
        handler: endpoint.identifier,
        name: title(endpoint.identifier),
        summary: sentence(annotation(OpenApi.Summary.key)),
        status: statuses.length === 1 ? statuses[0] : undefined,
        method: endpoint.method,
        path: endpoint.path.replaceAll(/:(\w+)/g, "{$1}"),
        params: fields(endpoint.params),
        headers: fields(endpoint.headers),
        body: bodies[0],
        // A handler names the status only where it has one to choose.
        success:
          statuses.length === 1
            ? [...replies.keys()][0]
            : [...replies]
                .map(
                  ([body, of]) =>
                    `tuple[Literal[${of.toSorted((a, b) => a - b).join(", ")}], ${body}]`,
                )
                .join(" | "),
        // The endpoint's own problems, without those its middleware answers with.
        problems: union([...endpoint.error].map(problemName)),
      });
    },
  };
  reflect(collect);

  const served = [...groups]
    .map(([name, operations]) => ({ name, operations }))
    .filter(({ operations }) => operations.length > 0);
  const all = served.flatMap(({ name, operations }) =>
    operations.map((op) => `${name}.${op.name}`),
  );

  return `# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from packages/host-protocol.
# Regenerate with \`${command}\`.
"""Calls, results, and handlers for each host operation."""

from __future__ import annotations

from typing import (
    Final,
    Literal,
    Protocol,
    TypeAlias,
    TypeVar,
    assert_never,
    final,
)

import msgspec

from marimo._core import protocol, result

${problemSets
  .toReversed()
  .map(({ name, members }) => `${name}: TypeAlias = ${union(members, name)}`)
  .join("\n")}

${served
  .map(({ name, operations }) =>
    [
      `class ${name}:`,
      indent(
        [
          ...operations.map(operation),
          "class Handlers(Protocol):",
          indent(
            operations
              .map((op) =>
                [
                  `async def ${op.handler}(self, call: ${name}.${op.name}.Call) -> ${name}.${op.name}.Result:`,
                  indent(`"""${op.summary}"""\n...`, 1),
                  "",
                ].join("\n"),
              )
              .join("\n"),
            1,
          ),
        ].join("\n"),
        1,
      ),
    ].join("\n"),
  )
  .join("\n\n")}

Operation: TypeAlias = ${all.map((name) => `type[${name}]`).join(" | ")}

OPERATIONS: tuple[Operation, ...] = (${all.join(", ")},)

Call: TypeAlias = ${all.map((name) => `${name}.Call`).join(" | ")}

Result: TypeAlias = result.Result[tuple[int, msgspec.Struct | None], protocol.Problem]

_T = TypeVar("_T")
_E = TypeVar("_E")


def _answered(
    status: int, outcome: result.Result[_T, _E]
) -> result.Result[tuple[int, _T], _E]:
    if outcome.ok:
        return result.Ok((status, outcome.value))
    return outcome


@final
class Api:
    """Serves each call with its group's handler."""

    def __init__(self, *, ${served.map(({ name }) => `${name.toLowerCase()}: ${name}.Handlers`).join(", ")}) -> None:
${indent(served.map(({ name }) => `self._${name.toLowerCase()} = ${name.toLowerCase()}`).join("\n"), 2)}

    async def handle(self, call: Call) -> Result:
        match call:
${indent(
  served
    .flatMap(({ name, operations }) =>
      operations.map(
        (op) =>
          `case ${name}.${op.name}.Call():\n    return ${
            op.status === undefined
              ? `await self._${name.toLowerCase()}.${op.handler}(call)`
              : `_answered(${op.status}, await self._${name.toLowerCase()}.${op.handler}(call))`
          }`,
      ),
    )
    .join("\n"),
  3,
)}
        assert_never(call)
`;
}
