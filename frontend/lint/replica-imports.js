/* Copyright 2026 Marimo. All rights reserved. */

import NodePath from "node:path";

export function isTest(path) {
  return (
    path.includes(`${NodePath.sep}__tests__${NodePath.sep}`) ||
    /\.(test|spec)(\.[cm]?[jt]sx?)?$/.test(path)
  );
}

/** Keep the notebook replica independent of application implementations. */
export const replicaImports = {
  meta: {
    type: "problem",
    docs: { description: "Restrict dependencies of the notebook replica" },
  },
  createOnce(context) {
    function check(source, node) {
      const filename = context.filename;
      const marker = `${NodePath.sep}src${NodePath.sep}core${NodePath.sep}notebook${NodePath.sep}replica${NodePath.sep}`;
      const index = filename.lastIndexOf(marker);
      if (index === -1 || isTest(filename.slice(index))) {
        return;
      }
      const root = filename.slice(0, index + marker.length);
      const name = source?.value;
      if (typeof name === "string") {
        if (
          name === "jotai/vanilla" ||
          name === "zod" ||
          name === "@marimo-team/client" ||
          name.startsWith("@marimo-team/client/")
        ) {
          return;
        }
        const target = name.startsWith(".")
          ? NodePath.resolve(NodePath.dirname(filename), name)
          : name.startsWith("@/")
            ? NodePath.resolve(root, "../../..", name.slice(2))
            : null;
        if (target?.startsWith(root) && !isTest(target)) {
          return;
        }
        if (target === NodePath.resolve(root, "../../../utils/Logger")) {
          return;
        }
      }
      context.report({
        node: source ?? node,
        message:
          "Replica code may import only replica modules, @marimo-team/client, jotai/vanilla, zod, and Logger.",
      });
    }
    return importVisitors(check);
  },
};

/** Call `check` with the source of every import, export from, and require. */
export function importVisitors(check) {
  return {
    ImportDeclaration(node) {
      check(node.source, node);
    },
    ExportNamedDeclaration(node) {
      if (node.source) {
        check(node.source, node);
      }
    },
    ExportAllDeclaration(node) {
      check(node.source, node);
    },
    ImportExpression(node) {
      check(node.source, node);
    },
    TSImportType(node) {
      check(node.source, node);
    },
    TSImportEqualsDeclaration(node) {
      if (node.moduleReference.type === "TSExternalModuleReference") {
        check(node.moduleReference.expression, node);
      }
    },
    CallExpression(node) {
      if (node.callee.type === "Identifier" && node.callee.name === "require") {
        check(node.arguments[0], node);
      }
    },
  };
}
