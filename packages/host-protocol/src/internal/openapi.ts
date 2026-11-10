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

const componentPrefix = "#/components/schemas/";

/** The names of the component schemas that `value` refers to. */
function references(value: unknown, found = new Set<string>()) {
  if (Array.isArray(value)) {
    for (const item of value) {
      references(item, found);
    }
  } else if (isNode(value)) {
    for (const [key, child] of Object.entries(value)) {
      if (key !== "$ref") {
        references(child, found);
      } else if (typeof child === "string") {
        found.add(child.slice(componentPrefix.length));
      }
    }
  }
  return found;
}

/** The names of the component schemas that request bodies are made of. */
function requestSchemas(paths: unknown, schemas: Node) {
  const found = new Set<string>();
  for (const item of Object.values(isNode(paths) ? paths : {})) {
    for (const operation of Object.values(isNode(item) ? item : {})) {
      references(isNode(operation) ? operation.requestBody : undefined, found);
    }
  }
  // A set visits the members added while it is iterated.
  for (const name of found) {
    references(schemas[name], found);
  }
  return found;
}

function adjust(value: unknown, closed: boolean): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => adjust(item, closed));
  }
  return isNode(value) ? adjustNode(value, closed) : value;
}

function adjustNode(value: Node, closed: boolean): Node {
  const node: Node = {};
  for (const [key, child] of Object.entries(value)) {
    // Effect closes every object. A host rejects members of a request body it
    // does not recognize, and a client ignores them everywhere else. An object
    // that declares no properties is empty on purpose.
    if (
      key === "additionalProperties" &&
      child === false &&
      !closed &&
      "properties" in value
    ) {
      continue;
    }
    node[key] = adjust(child, closed || key === "requestBody");
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
 * Request bodies stay closed and other objects are open, descriptions sit
 * beside the schema they describe, and each problem requires its `status` and
 * `title`.
 */
export function forGenerators(spec: Record<string, unknown>) {
  const components = isNode(spec.components) ? spec.components : {};
  const schemas = isNode(components.schemas) ? components.schemas : {};
  const requests = requestSchemas(spec.paths, schemas);
  return {
    ...adjustNode(spec, false),
    components: {
      ...adjustNode(components, false),
      schemas: Object.fromEntries(
        Object.entries(schemas).map(([name, schema]) => [
          name,
          adjust(schema, requests.has(name)),
        ]),
      ),
    },
  };
}
