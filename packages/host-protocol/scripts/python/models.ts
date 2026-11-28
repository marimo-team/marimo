/* Copyright 2026 Marimo. All rights reserved. */

/** Python records, from the OpenAPI document's schemas. */

type Json =
  | null
  | boolean
  | number
  | string
  | ReadonlyArray<Json>
  | { readonly [key: string]: Json };

/** A JSON Schema. */
interface Node {
  readonly [key: string]: Json;
}

const isNode = (value: unknown): value is Node =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const nodes = (value: Json | undefined): ReadonlyArray<Node> =>
  Array.isArray(value) ? value.filter(isNode) : [];

const PREFIX = "#/components/schemas/";

const referenced = (node: Node): string => {
  const reference = String(node.$ref);
  if (!reference.startsWith(PREFIX)) {
    throw new Error(`Expected a reference to a component: ${reference}`);
  }
  return reference.slice(PREFIX.length);
};

/** A JSON value as Python writes it. */
function literal(value: Json): string {
  if (value === null) {
    return "None";
  }
  if (typeof value === "boolean") {
    return value ? "True" : "False";
  }
  if (typeof value === "number" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(literal).join(", ")}]`;
  }
  return `{${Object.entries(value)
    .map(([key, member]) => `${JSON.stringify(key)}: ${literal(member)}`)
    .join(", ")}}`;
}

/** What msgspec's `Meta` says about a schema, by JSON Schema keyword. */
const META: ReadonlyArray<readonly [keyword: string, argument: string]> = [
  ["description", "description"],
  ["examples", "examples"],
  ["minimum", "ge"],
  ["maximum", "le"],
  ["maxLength", "max_length"],
  ["minLength", "min_length"],
  ["minItems", "min_length"],
  ["pattern", "pattern"],
];

/** Attach a schema's description and limits to the type that carries them. */
function annotated(type: string, node: Node): string {
  const meta = META.flatMap(([keyword, argument]) =>
    node[keyword] === undefined
      ? []
      : [`${argument}=${literal(node[keyword])}`],
  );
  return meta.length === 0
    ? type
    : `Annotated[${type}, Meta(${meta.join(", ")})]`;
}

/** The Python type of a schema. */
function type(node: Node): string {
  if ("$ref" in node) {
    return annotated(referenced(node), node);
  }
  if ("anyOf" in node) {
    const members = nodes(node.anyOf);
    const present = members.filter((member) => member.type !== "null");
    // What is said of a value that may be null is said of the value.
    const { description, examples } = node;
    const said = {
      ...(description === undefined ? {} : { description }),
      ...(examples === undefined ? {} : { examples }),
    };
    const union =
      present.length === 1
        ? type({ ...said, ...present[0] })
        : annotated(present.map(type).join(" | "), said);
    return present.length < members.length ? `${union} | None` : union;
  }
  if (Array.isArray(node.enum)) {
    return annotated(`Literal[${node.enum.map(literal).join(", ")}]`, node);
  }
  switch (node.type) {
    case "string":
      return annotated(node.format === "date-time" ? "datetime" : "str", node);
    case "integer":
      return annotated("int", node);
    case "number":
      return annotated("float", node);
    case "boolean":
      return annotated("bool", node);
    case "null":
      return "None";
    case "array":
      if (!isNode(node.items)) {
        throw new Error("An array must say what it holds");
      }
      // msgspec decodes a tuple from a JSON array, and a tuple cannot change.
      return annotated(`tuple[${type(node.items)}, ...]`, node);
    case "object": {
      const members = node.additionalProperties;
      const mapping = `dict[str, ${isNode(members) ? type(members) : "Any"}]`;
      // An object that admits no members is always empty.
      return members === false
        ? `Annotated[${mapping}, Meta(max_length=0)]`
        : annotated(mapping, node);
    }
    default:
      throw new Error(`No Python type for ${JSON.stringify(node)}`);
  }
}

/** The one value of a property that only ever has one, if it is such. */
function constant(node: Json | undefined): string | undefined {
  return isNode(node) &&
    node.type === "string" &&
    Array.isArray(node.enum) &&
    node.enum.length === 1 &&
    node.default === undefined
    ? String(node.enum[0])
    : undefined;
}

const isStruct = (node: Node | undefined): boolean =>
  node !== undefined && node.type === "object" && isNode(node.properties);

/**
 * Find the property that tells the members of each union of structs apart.
 *
 * msgspec decodes such a union by one tag field, so every member names it in
 * its class definition instead of carrying it as a field.
 */
function tags(schemas: Readonly<Record<string, Node>>) {
  const found = new Map<string, { field: string; tag: string }>();
  const visit = (value: Json) => {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (!isNode(value)) {
      return;
    }
    Object.values(value).forEach(visit);
    const members = nodes(value.anyOf)
      .filter((member) => member.type !== "null")
      .map((member) => ("$ref" in member ? referenced(member) : undefined));
    if (
      members.length < 2 ||
      !members.every(
        (member): member is string =>
          member !== undefined && isStruct(schemas[member]),
      )
    ) {
      return;
    }
    const properties = (member: string) => schemas[member].properties as Node;
    const fields = Object.keys(properties(members[0])).filter((field) => {
      const values = members.map((member) =>
        constant(properties(member)[field]),
      );
      return (
        values.every((tag) => tag !== undefined) &&
        new Set(values).size === values.length
      );
    });
    if (fields.length !== 1) {
      throw new Error(
        `Expected one field to tell ${members.join(", ")} apart, found ${fields.length}`,
      );
    }
    const [field] = fields;
    for (const member of members) {
      const tag = String(constant(properties(member)[field]));
      const known = found.get(member);
      if (known !== undefined && known.field !== field) {
        throw new Error(`${member} is told apart by two different fields`);
      }
      found.set(member, { field, tag });
    }
  };
  visit(schemas);
  return found;
}

function struct(
  name: string,
  node: Node,
  tag: { field: string; tag: string } | undefined,
): string {
  const properties = node.properties as Node;
  const required = new Set<string>();
  for (const key of Array.isArray(node.required) ? node.required : []) {
    required.add(String(key));
  }
  const fields = Object.keys(properties)
    .toSorted()
    .filter((field) => field !== tag?.field)
    .map((field) => {
      const { default: preset, ...property } = properties[field] as Node;
      if (!/^[a-z_][a-z0-9_]*$/i.test(field)) {
        throw new Error(`${name}.${field} is not a Python name`);
      }
      const optional = !required.has(field);
      // A member that may be left out is `UNSET` unless the schema gives it
      // a value, and a default of null is the same as leaving it out.
      const value =
        preset === undefined || preset === null
          ? optional
            ? "UNSET"
            : undefined
          : literal(preset);
      return {
        value,
        // A union reads best with `None` last.
        line: `${field}: ${
          optional
            ? type(property).replace(/( \| None)?$/, " | UnsetType$1")
            : type(property)
        }${value === undefined ? "" : ` = ${value}`}`,
      };
    })
    // msgspec takes the fields without a default first.
    .toSorted(
      (a, b) => Number(a.value !== undefined) - Number(b.value !== undefined),
    );
  const options = [
    "Struct",
    "frozen=True",
    ...(node.additionalProperties === false
      ? ["forbid_unknown_fields=True"]
      : []),
    ...(tag === undefined
      ? []
      : [`tag_field=${literal(tag.field)}`, `tag=${literal(tag.tag)}`]),
  ];
  return [
    `class ${name}(${options.join(", ")}):`,
    ...(fields.length === 0
      ? ["    pass"]
      : fields.map(({ line }) => `    ${line}`)),
  ].join("\n");
}

const JSON_VALUE = `if TYPE_CHECKING:
    JsonValue: TypeAlias = (
        str
        | int
        | float
        | bool
        | list["JsonValue"]
        | dict[str, "JsonValue"]
        | None
    )
else:
    # msgspec cannot decode recursive aliases. Its JSON decoder returns JSON values.
    JsonValue = object`;

/** The names a schema needs defined before it, which a struct never does. */
function needs(node: Node): ReadonlyArray<string> {
  if (isStruct(node)) {
    return [];
  }
  const found = new Set<string>();
  const visit = (value: Json) => {
    if (Array.isArray(value)) {
      value.forEach(visit);
    } else if (isNode(value)) {
      if ("$ref" in value) {
        found.add(referenced(value));
      }
      Object.values(value).forEach(visit);
    }
  };
  visit(node);
  return [...found];
}

/** Write the module for the document's component schemas. */
export function models(
  document: unknown,
  options: { readonly command: string },
): string {
  const components = isNode(document) ? document.components : undefined;
  const schemas = isNode(components) ? components.schemas : undefined;
  if (!isNode(schemas)) {
    throw new Error("The document has no component schemas");
  }
  const all = schemas as Readonly<Record<string, Node>>;
  const told = tags(all);

  const definition = (name: string): string => {
    const node = all[name];
    if (Object.keys(node).length === 0) {
      if (name !== "JsonValue") {
        throw new Error(`${name} says nothing about its values`);
      }
      return JSON_VALUE;
    }
    if (isStruct(node)) {
      return struct(name, node, told.get(name));
    }
    // An id is a string that only its own kind of object may be named by.
    if (
      node.type === "string" &&
      node.enum === undefined &&
      node.format === undefined
    ) {
      return [
        "if TYPE_CHECKING:",
        `    ${name} = NewType("${name}", str)`,
        "else:",
        `    ${name} = NewType("${name}", ${type(node)})`,
      ].join("\n");
    }
    return `${name}: TypeAlias = ${type(node)}`;
  };

  // Each name comes after the names its definition evaluates.
  const pending = new Set(Object.keys(all).toSorted());
  const definitions: Array<string> = [];
  while (pending.size > 0) {
    const ready = [...pending].find((name) =>
      needs(all[name]).every((need) => !pending.has(need)),
    );
    if (ready === undefined) {
      throw new Error(`These schemas refer to each other: ${[...pending]}`);
    }
    pending.delete(ready);
    definitions.push(definition(ready));
  }
  const body = definitions.join("\n\n\n");

  return `# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from packages/host-protocol.
# Regenerate with \`${options.command}\`.
# ruff: noqa: TC003 - msgspec resolves annotations at runtime

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated${/\bAny\b/.test(body) ? ", Any" : ""}, Literal, NewType, TypeAlias

from msgspec import UNSET, Meta, Struct, UnsetType

${body}
`;
}
