/* Copyright 2026 Marimo. All rights reserved. */

import NodePath from "node:path";
import { importVisitors, isTest } from "./replica-imports.js";

/** Directories under `src/` that other code imports only through `index.ts`. */
const MODULES = [
  "core/notebook",
  "core/notebook/replica",
  "core/notebook/document",
];

/** Keep each module's files private to it, behind its entry point. */
export const moduleEntry = {
  meta: {
    type: "problem",
    docs: { description: "Import a module through its entry point" },
  },
  createOnce(context) {
    function check(source, node) {
      const filename = context.filename;
      const marker = `${NodePath.sep}src${NodePath.sep}`;
      const index = filename.lastIndexOf(marker);
      const name = source?.value;
      if (index === -1 || isTest(filename) || typeof name !== "string") {
        return;
      }
      const src = filename.slice(0, index + marker.length);
      const target = name.startsWith(".")
        ? NodePath.resolve(NodePath.dirname(filename), name)
        : name.startsWith("@/")
          ? NodePath.resolve(src, name.slice(2))
          : null;
      if (
        target === null ||
        isTest(target) ||
        MODULES.some((module) => target === NodePath.resolve(src, module))
      ) {
        return;
      }
      for (const module of MODULES) {
        const root = NodePath.resolve(src, module);
        const inside = (path) => path.startsWith(root + NodePath.sep);
        if (inside(target) && !inside(filename)) {
          context.report({
            node: source ?? node,
            message: `Import ${module} through its entry point, @/${module}.`,
          });
        }
      }
    }
    return importVisitors(check);
  },
};
