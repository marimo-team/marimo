/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Selectors that should be replaced with the prefix rather than prepended.
 * e.g., `:root { --spacing: 0.25rem }` becomes `.marimo { --spacing: 0.25rem }`
 * so CSS custom properties are set directly on island container elements.
 */
const GLOBAL_SELECTORS = new Set([":root", ":host", "html", "body"]);

const config = {
  plugins: [
    require("@tailwindcss/postcss"),
    process.env.VITE_MARIMO_ISLANDS === "true"
      ? require("postcss-prefix-selector")({
          prefix: ".marimo",
          transform(prefix, selector) {
            // Global selectors → replace with prefix
            if (GLOBAL_SELECTORS.has(selector)) {
              return prefix;
            }
            // Radix scales must match the namespace root and dark host ancestors.
            if (selector === ".dark" || selector === ".dark-theme") {
              return `${prefix}${selector}, ${prefix}:is(${selector} *), ${prefix} ${selector}`;
            }
            // Already scoped under .marimo
            if (selector.startsWith(".marimo")) {
              return selector;
            }
            // Normal prefixing: .flex → .marimo .flex
            return `${prefix} ${selector}`;
          },
        })
      : undefined,
    process.env.NODE_ENV === "production" ? require("cssnano") : undefined,
    require("@csstools/postcss-light-dark-function"),
  ],
};

module.exports = config;
