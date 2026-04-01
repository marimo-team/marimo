/* Copyright 2026 Marimo. All rights reserved. */
/** biome-ignore-all lint/suspicious/noConsole: for debugging */
// @ts-check
import * as fs from "node:fs";
import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";
import ts from "typescript";

/**
 * Map from OpenAPI `format` values (emitted by _enrich_branded_types in
 * commands.py) to the TypeScript brand tag used in TypedString<T>.
 *
 * When a new NewType is added to marimo/_types/ids.py *and* registered in
 * _enrich_branded_types (commands.py), add a corresponding entry here so
 * the generated TypeScript carries the branded type.
 */
const BRANDED_FORMATS = /** @type {const} */ ({
  base64: "Base64String",
  "cell-id": "CellId",
  "session-id": "SessionId",
  "variable-name": "VariableName",
  "request-id": "RequestId",
  "widget-model-id": "WidgetModelId",
});

/**
 * Injected at the top of the generated file so branded schemas can reference it.
 */
const TYPED_STRING_HELPER =
  "/** Branded string type — compile-time only. */\ntype TypedString<T extends string> = string & { __brand: T };\n";

/**
 * Apply post-generation string transforms to the TypeScript output.
 *
 * @param {string} content
 * @returns {string}
 */
function postTransform(content) {
  let result = content;

  // Record<string, never> → Record<string, any>
  result = result.replace(/Record<string, never>/g, "Record<string, any>");

  // Inject TypedString helper before the first export
  result = result.replace(/^(export )/m, `${TYPED_STRING_HELPER}\n$1`);

  // UIElementId is a template literal, not a simple branded string.
  result = result.replace(
    /\bUIElementId: string;/,
    // biome-ignore lint/suspicious/noTemplateCurlyInString: raw string, not a template
    'UIElementId: `${components["schemas"]["CellId"]}-${string}`;',
  );

  return result;
}

async function main() {
  const source = new URL("./api.yaml", import.meta.url);
  const dest = new URL("./src/api.ts", import.meta.url);

  const nodes = await openapiTS(source, {
    defaultNonNullable: false,
    transform(schemaObject) {
      if (
        schemaObject.type === "string" &&
        typeof schemaObject.format === "string" &&
        schemaObject.format in BRANDED_FORMATS
      ) {
        const brand =
          BRANDED_FORMATS[
            /** @type {keyof typeof BRANDED_FORMATS} */ (schemaObject.format)
          ];
        return ts.factory.createTypeReferenceNode("TypedString", [
          ts.factory.createLiteralTypeNode(
            ts.factory.createStringLiteral(brand),
          ),
        ]);
      }
    },
  });

  const content = postTransform(COMMENT_HEADER + astToString(nodes));
  fs.writeFileSync(dest, content);
  console.log("api.yaml → src/api.ts");
}

main();
