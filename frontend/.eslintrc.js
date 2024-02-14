/* Copyright 2024 Marimo. All rights reserved. */
/**
 * @type {import('eslint').Linter.Config}
 */
module.exports = {
  root: true,
  extends: [
    "eslint:recommended",
    // This ruleset is meant to be used after extending eslint:recommended.
    // It disables core ESLint rules that are already checked by the TypeScript compiler.
    "plugin:@typescript-eslint/eslint-recommended",
    // TS ESLint
    "plugin:@typescript-eslint/recommended-type-checked",
    "plugin:@typescript-eslint/stylistic-type-checked",
    "plugin:@typescript-eslint/strict-type-checked",
    // Accessibility
    "plugin:jsx-a11y/strict",
    // React
    "plugin:react-hooks/recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime",
    "plugin:ssr-friendly/recommended",
    // Storybook
    "plugin:storybook/recommended",
    // Unicorn
    "plugin:unicorn/all",
    // Testing
    "plugin:vitest/recommended",
    // This removes rules that conflict with prettier.
    "prettier",
  ],
  settings: {
    react: {
      version: "detect",
    },
  },
  parser: "@typescript-eslint/parser",
  parserOptions: {
    project: require.resolve("./tsconfig.json"),
  },
  plugins: ["@typescript-eslint", "header"],
  rules: {
    "header/header": [
      "error",
      "block",
      " Copyright 2024 Marimo. All rights reserved. ",
    ],

    // These rules don't require type information and have autofixes
    "@typescript-eslint/array-type": ["error", { default: "array-simple" }],
    "@typescript-eslint/consistent-generic-constructors": "error",
    "@typescript-eslint/consistent-type-definitions": "error",
    "@typescript-eslint/no-confusing-non-null-assertion": "error",
    "@typescript-eslint/no-dynamic-delete": "error",
    "@typescript-eslint/prefer-ts-expect-error": "error",
    curly: "error",

    // Turn off recommended we don't want
    "ssr-friendly/no-dom-globals-in-react-fc": "off",
    "ssr-friendly/no-dom-globals-in-constructor": "off",
    "react/prop-types": "off",
    "react/no-unescaped-entities": "off",
    "@typescript-eslint/no-unnecessary-condition": "off",
    "@typescript-eslint/ban-types": [
      "error",
      {
        types: {
          // un-ban {}
          "{}": false,
        },
        extendDefaults: true,
      },
    ],
    "@typescript-eslint/no-confusing-void-expression": [
      "error",
      { ignoreArrowShorthand: true },
    ],
    "@typescript-eslint/prefer-nullish-coalescing": "off", // Throws an error: TypeError: Cannot read properties of undefined (reading 'some')
    "@typescript-eslint/no-unused-vars": "off",
    "@typescript-eslint/consistent-indexed-object-style": "off",
    "@typescript-eslint/require-await": "off",
    "@typescript-eslint/restrict-template-expressions": "off",
    "jsx-a11y/no-autofocus": "off",
    "jsx-a11y/no-static-element-interactions": "off",
    "jsx-a11y/no-noninteractive-element-interactions": "off",
    "jsx-a11y/click-events-have-key-events": "off",
    // Turn of unicorn rules that don't have autofixes or that we don't want
    "unicorn/consistent-function-scoping": "off",
    "unicorn/expiring-todo-comments": "off",
    "unicorn/filename-case": "off",
    "unicorn/no-array-callback-reference": "off",
    "unicorn/no-array-for-each": "off",
    "unicorn/no-array-method-this-argument": "off", // false positives
    "unicorn/no-array-reduce": "off",
    "unicorn/no-await-expression-member": "off",
    "unicorn/no-null": "off",
    "unicorn/no-keyword-prefix": "off",
    "unicorn/no-useless-undefined": "off",
    "unicorn/prefer-add-event-listener": "off",
    "unicorn/require-post-message-target-origin": "off",
    "unicorn/prefer-at": "off",
    "unicorn/prefer-code-point": "off",
    "unicorn/prefer-module": "off",
    "unicorn/prefer-query-selector": "off",
    "unicorn/prefer-dom-node-text-content": "off",
    "unicorn/prefer-top-level-await": "off",
    "unicorn/prevent-abbreviations": "off",

    // Would like to turn on, but too many existing errors
    "@typescript-eslint/no-floating-promises": "off",
    "@typescript-eslint/no-misused-promises": "off",
    "@typescript-eslint/no-unsafe-argument": "off",
    "@typescript-eslint/no-unsafe-assignment": "off",
    "@typescript-eslint/no-unsafe-call": "off",
    "@typescript-eslint/no-unsafe-member-access": "off",
    "@typescript-eslint/no-unsafe-return": "off",

    // These rules aim to reduce bikeshedding during code reviews
    // Often there are multiple ways to do something and this forces consistency
    "prefer-template": "error", // Use template literals instead of string concatenation
    "unicorn/switch-case-braces": ["error", "avoid"], // Only braces when necessary
    "unicorn/consistent-destructuring": "error",
    "unicorn/prefer-logical-operator-over-ternary": "error",
    "unicorn/prefer-spread": "error",
    "unicorn/no-object-as-default-parameter": "error",
    "unicorn/prefer-number-properties": "error",
    "unicorn/prefer-ternary": "error",
    "unicorn/prefer-array-some": "error",
    "react/jsx-boolean-value": ["error", "always"], // Force `={true}` or `={false}` as it's more explicit
    "react/hook-use-state": "error",
    "react/jsx-no-useless-fragment": "error",
    "react/jsx-pascal-case": "error",
    "react/self-closing-comp": "error",
    "react/function-component-definition": [
      "error",
      {
        namedComponents: "arrow-function",
        unnamedComponents: "arrow-function",
      },
    ],
  },
  overrides: [
    {
      files: ["**/e2e-tests/**"],
      parserOptions: {
        project: require.resolve("./e2e-tests/tsconfig.json"),
      },
      rules: {
        "testing-library/prefer-screen-queries": "off",
        "@typescript-eslint/no-unsafe-argument": "off",
        "@typescript-eslint/await-thenable": "off",
        "@typescript-eslint/no-unsafe-assignment": "off",
        "@typescript-eslint/no-unsafe-call": "off",
        "@typescript-eslint/require-await": "off",
        "@typescript-eslint/no-unsafe-member-access": "off",
        "@typescript-eslint/no-unsafe-return": "off",
      },
    },
    {
      files: ["**/__tests__/**"],
      rules: {
        "@typescript-eslint/no-non-null-assertion": "off",
        "@typescript-eslint/no-unsafe-argument": "off",
        "@typescript-eslint/no-unsafe-assignment": "off",
        "@typescript-eslint/no-unsafe-call": "off",
        "@typescript-eslint/require-await": "off",
        "@typescript-eslint/no-unsafe-member-access": "off",
        "typescript-eslint/no-unsafe-return": "off",
      },
    },
  ],
};
