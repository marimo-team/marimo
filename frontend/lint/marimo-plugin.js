/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Custom oxlint plugin with marimo-specific lint rules.
 * Replaces the Biome Grit plugins.
 */

const addEventListenerObject = {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Require object options instead of boolean for addEventListener",
    },
    fixable: "code",
  },
  create(context) {
    return {
      CallExpression(node) {
        if (
          node.callee.type !== "MemberExpression" ||
          node.callee.property.name !== "addEventListener" ||
          node.arguments.length < 3
        ) {
          return;
        }
        const options = node.arguments[2];
        if (options.type === "Literal" && typeof options.value === "boolean") {
          context.report({
            node: options,
            message: `Use an object instead of a boolean for addEventListener options. Replace '${options.value}' with '{ capture: ${options.value} }'.`,
            fix(fixer) {
              return fixer.replaceText(
                options,
                `{ capture: ${options.value} }`,
              );
            },
          });
        }
      },
    };
  },
};

const removeEventListenerObject = {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Require object options instead of boolean for removeEventListener",
    },
    fixable: "code",
  },
  create(context) {
    return {
      CallExpression(node) {
        if (
          node.callee.type !== "MemberExpression" ||
          node.callee.property.name !== "removeEventListener" ||
          node.arguments.length < 3
        ) {
          return;
        }
        const options = node.arguments[2];
        if (options.type === "Literal" && typeof options.value === "boolean") {
          context.report({
            node: options,
            message: `Use an object instead of a boolean for removeEventListener options. Replace '${options.value}' with '{ capture: ${options.value} }'.`,
            fix(fixer) {
              return fixer.replaceText(
                options,
                `{ capture: ${options.value} }`,
              );
            },
          });
        }
      },
    };
  },
};

function isSimpleParam(param) {
  return param.type === "Identifier" || param.type === "AssignmentPattern";
}

const preferObjectParams = {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Prefer an options object instead of multiple positional arguments (3+)",
    },
  },
  create(context) {
    function check(node, nameNode) {
      const params = node.params;
      if (!params || params.length < 3) {
        return;
      }
      if (params.some((p) => p.type === "ObjectPattern")) {
        return;
      }
      if (!params.every(isSimpleParam)) {
        return;
      }
      context.report({
        node: nameNode || node,
        message:
          "Avoid multiple positional arguments. Prefer an options object instead, e.g., fn(options) or fn(arg, options).",
      });
    }

    return {
      FunctionDeclaration(node) {
        check(node, node.id);
      },
      FunctionExpression(node) {
        check(node, node.id || node);
      },
      ArrowFunctionExpression(node) {
        if (node.parent.type === "VariableDeclarator") {
          check(node, node.parent.id);
        } else {
          check(node, node);
        }
      },
    };
  },
};

const atomWithStorageArgs = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Require atomWithStorage to have at least 3 arguments (key, defaultValue, storage)",
    },
  },
  create(context) {
    return {
      CallExpression(node) {
        const callee = node.callee;
        const name = callee.type === "Identifier" ? callee.name : null;

        if (name !== "atomWithStorage") {
          return;
        }
        if (node.arguments.length < 3) {
          context.report({
            node,
            message:
              "atomWithStorage requires at least 3 arguments (key, defaultValue, storage). Provide the storage parameter explicitly.",
          });
        }
      },
    };
  },
};

const plugin = {
  meta: {
    name: "marimo",
  },
  rules: {
    "add-event-listener-object": addEventListenerObject,
    "remove-event-listener-object": removeEventListenerObject,
    "prefer-object-params": preferObjectParams,
    "atom-with-storage-args": atomWithStorageArgs,
  },
};

export default plugin;
