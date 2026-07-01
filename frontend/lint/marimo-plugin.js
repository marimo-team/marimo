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
  createOnce(context) {
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
  createOnce(context) {
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
  createOnce(context) {
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
  createOnce(context) {
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

const TW_CLASS_ATTRS = new Set(["className", "class"]);
const TW_CLASS_FNS = new Set(["cn", "cva", "clsx", "cx", "twMerge", "twJoin"]);

// Renamed in Tailwind v4. The old names still compile as aliases, so they are
// deprecated rather than broken, and the replacement is a safe rename.
const TW_RENAMED = new Map([
  ["flex-shrink-0", "shrink-0"],
  ["flex-shrink", "shrink"],
  ["flex-grow-0", "grow-0"],
  ["flex-grow", "grow"],
  ["overflow-ellipsis", "text-ellipsis"],
  ["decoration-slice", "box-decoration-slice"],
  ["decoration-clone", "box-decoration-clone"],
]);

// Removed in Tailwind v4: these generate no CSS. The opacity modifier
// (e.g. `bg-black/50`) replaces them, but the rewrite needs the base color,
// so it cannot be applied mechanically.
const TW_REMOVED_OPACITY = /^(bg|text|border|ring|divide|placeholder)-opacity-\d+$/;

function splitClassToken(token) {
  const colon = token.lastIndexOf(":");
  const prefix = token.slice(0, colon + 1);
  let core = token.slice(colon + 1);
  let lead = "";
  let trail = "";
  if (core.startsWith("!")) {
    lead = "!";
    core = core.slice(1);
  }
  if (core.endsWith("!")) {
    trail = "!";
    core = core.slice(0, -1);
  }
  return { prefix, lead, core, trail };
}

function inClassContext(node) {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent.type === "JSXAttribute") {
      const name = parent.name;
      return name?.type === "JSXIdentifier" && TW_CLASS_ATTRS.has(name.name);
    }
    if (
      parent.type === "CallExpression" &&
      parent.callee.type === "Identifier" &&
      TW_CLASS_FNS.has(parent.callee.name)
    ) {
      return true;
    }
  }
  return false;
}

function classStringNodes(handlers) {
  return {
    Literal(node) {
      if (typeof node.value === "string" && inClassContext(node)) {
        handlers.literal(node, node.value);
      }
    },
    TemplateElement(node) {
      if (inClassContext(node)) {
        handlers.template(node, node.value.cooked ?? node.value.raw);
      }
    },
  };
}

const noDeprecatedTailwindClasses = {
  meta: {
    type: "suggestion",
    docs: {
      description: "Disallow Tailwind utility classes renamed in v4",
    },
    fixable: "code",
  },
  createOnce(context) {
    function renamesIn(value) {
      const renames = [];
      for (const token of value.split(/\s+/)) {
        if (!token) {
          continue;
        }
        const { core } = splitClassToken(token);
        const replacement = TW_RENAMED.get(core);
        if (replacement) {
          renames.push({ from: core, to: replacement });
        }
      }
      return renames;
    }

    function rebuild(value) {
      return value
        .split(/(\s+)/)
        .map((token) => {
          if (token.trim() === "") {
            return token;
          }
          const { prefix, lead, core, trail } = splitClassToken(token);
          const replacement = TW_RENAMED.get(core);
          return replacement ? prefix + lead + replacement + trail : token;
        })
        .join("");
    }

    function message(renames) {
      const list = renames.map((r) => `${r.from} -> ${r.to}`).join(", ");
      return `Tailwind v4 renamed this utility. Use the new name (${list}).`;
    }

    return classStringNodes({
      literal(node, value) {
        const renames = renamesIn(value);
        if (renames.length === 0) {
          return;
        }
        const quote = node.raw[0];
        context.report({
          node,
          message: message(renames),
          fix(fixer) {
            return fixer.replaceText(node, quote + rebuild(value) + quote);
          },
        });
      },
      template(node, value) {
        const renames = renamesIn(value);
        if (renames.length > 0) {
          context.report({ node, message: message(renames) });
        }
      },
    });
  },
};

const noRemovedTailwindClasses = {
  meta: {
    type: "problem",
    docs: {
      description: "Disallow Tailwind utility classes removed in v4",
    },
  },
  createOnce(context) {
    function check(node, value) {
      for (const token of value.split(/\s+/)) {
        if (!token) {
          continue;
        }
        const { core } = splitClassToken(token);
        if (TW_REMOVED_OPACITY.test(core)) {
          context.report({
            node,
            message: `'${core}' was removed in Tailwind v4 and generates no CSS. Use the opacity modifier instead, e.g. 'bg-black/50'.`,
          });
        }
      }
    }

    return classStringNodes({ literal: check, template: check });
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
    "no-deprecated-tailwind-classes": noDeprecatedTailwindClasses,
    "no-removed-tailwind-classes": noRemovedTailwindClasses,
  },
};

export default plugin;
