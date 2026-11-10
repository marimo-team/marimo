/* Copyright 2026 Marimo. All rights reserved. */

interface Node {
  [key: string]: unknown;
}

const isNode = (value: unknown): value is Node =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const annotations = new Set([
  "description",
  "default",
  "examples",
  "format",
  "title",
  "additionalProperties",
]);

// Effect writes a literal as an enum with one member.
const literal = (schema: unknown) =>
  isNode(schema) && Array.isArray(schema.enum) ? schema.enum[0] : undefined;

const problemType = "urn:marimo:problem:";

function adjust(value: unknown, closes = false): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => adjust(item));
  }
  return isNode(value) ? adjustNode(value, closes) : value;
}

function adjustNode(value: Node, closes: boolean): Node {
  const node: Node = {};
  for (const [key, child] of Object.entries(value)) {
    // Effect closes every object by default, and clients ignore members they
    // do not recognize. A schema that closes itself says so inside `allOf`.
    if (key === "additionalProperties" && child === false && !closes) {
      continue;
    }
    node[key] =
      key === "allOf" && Array.isArray(child)
        ? child.map((member) => adjust(member, true))
        : adjust(child);
  }
  // Effect tolerates a problem without `status` or `title`. A host sends both,
  // and only `type` tells problems apart, so a client accepts any title. The
  // declared values are the defaults.
  if (
    isNode(node.properties) &&
    Array.isArray(node.required) &&
    String(literal(node.properties.type)).startsWith(problemType)
  ) {
    const status = literal(node.properties.status);
    node.required = [...node.required, "status", "title"];
    node.properties = {
      ...node.properties,
      status: { type: "integer", enum: [status], default: status },
      title: { type: "string", default: literal(node.properties.title) },
    };
  }
  if (!Array.isArray(node.allOf)) {
    return node;
  }
  // Effect nests a key's annotations and a schema's own checks in `allOf`.
  const kept: Array<unknown> = [];
  for (const member of node.allOf) {
    const mergeable =
      isNode(member) &&
      Object.entries(member).every(
        ([key, child]) =>
          annotations.has(key) ||
          key === "$ref" ||
          (key === "type" && child === node.type),
      ) &&
      (!("$ref" in member) || Object.keys(node).length === 1);
    if (mergeable) {
      Object.assign(node, member);
    } else {
      kept.push(member);
    }
  }
  if (kept.length > 0) {
    node.allOf = kept;
  } else {
    delete node.allOf;
  }
  return node;
}

/**
 * Adjust the document Effect generates for consumers in other languages.
 *
 * Objects stay open unless a schema closes itself, descriptions sit beside
 * the schema they describe, and each problem requires its `status` and
 * `title`.
 */
export function forGenerators(spec: Record<string, unknown>) {
  return adjustNode(spec, false);
}
