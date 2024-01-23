/* Copyright 2024 Marimo. All rights reserved. */
/**
 * @type {import('eslint').Linter.Config}
 */
module.exports = {
  root: true,
  extends: [
    "react-app",
    "react-app/jest",
    "eslint:recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime",
    "plugin:@typescript-eslint/recommended",
    "plugin:ssr-friendly/recommended",
    "plugin:storybook/recommended",
    "plugin:unicorn/recommended",
    // This removes rules that conflict with prettier.
    "prettier",
  ],
  parser: "@typescript-eslint/parser",
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
    "unicorn/no-useless-undefined": "off",
    "unicorn/prefer-add-event-listener": "off",
    "unicorn/prefer-at": "off",
    "unicorn/prefer-code-point": "off",
    "unicorn/prefer-module": "off",
    "unicorn/prefer-query-selector": "off",
    "unicorn/prefer-dom-node-text-content": "off",
    "unicorn/prefer-top-level-await": "off",
    "unicorn/prevent-abbreviations": "off",

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
      rules: {
        "testing-library/prefer-screen-queries": "off",
      },
    },
    {
      files: ["**/*.test.tsx", "**/*.test.ts"],
      rules: {
        "@typescript-eslint/no-non-null-assertion": "off",
      },
    },
  ],
};
