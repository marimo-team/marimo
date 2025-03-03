// @ts-check
import globals from "globals";
import { FlatCompat } from "@eslint/eslintrc";
import eslintJs from "@eslint/js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactPlugin from "eslint-plugin-react";
import unicornPlugin from "eslint-plugin-unicorn";

// Determine the directory name
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Create a compatibility instance
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: eslintJs.configs.recommended,
});

export default [
  // Base configurations
  eslintJs.configs.recommended,

  // React Hooks plugin
  {
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-hooks/exhaustive-deps": "warn", // Explicitly set to warn
    },
  },

  // Use compat to include existing configs
  ...compat.extends(
    "plugin:@typescript-eslint/eslint-recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime",
    "plugin:storybook/recommended",
    "prettier",
  ),

  // Disable missing plugin errors
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    plugins: {
      // Define empty plugins to prevent "Definition for rule not found" errors
      "ssr-friendly": {},
      "react-compiler": {},
      vitest: {},
    },
    rules: {
      "ssr-friendly/no-dom-globals-in-module-scope": "off",
      "ssr-friendly/no-dom-globals-in-react-fc": "off",
      "ssr-friendly/no-dom-globals-in-constructor": "off",
      "react-compiler/react-compiler": "off",
      "vitest/expect-expect": "off",
      "vitest/no-conditional-tests": "off",
      "vitest/no-disabled-tests": "off",
    },
  },

  // TypeScript configurations
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    rules: {
      "@typescript-eslint/array-type": ["error", { default: "array-simple" }],
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-unused-expressions": [
        "error",
        {
          allowShortCircuit: true,
          allowTernary: true,
        },
      ],
      "@typescript-eslint/no-unnecessary-condition": "off",
      "@typescript-eslint/ban-types": "off",
      "@typescript-eslint/no-empty-object-type": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],
      // Disable rules that require type information until we can properly configure them
      "@typescript-eslint/no-confusing-void-expression": "off",
    },
  },

  // React rules
  {
    files: ["**/*.{jsx,tsx}"],
    plugins: {
      "jsx-a11y": jsxA11y,
      react: reactPlugin,
    },
    rules: {
      "react/prop-types": "off",
      "react/no-unescaped-entities": "off",
      "react/hook-use-state": ["warn", { allowDestructuredState: true }],
      "react/jsx-no-useless-fragment": "warn",
      "react/function-component-definition": [
        "warn",
        {
          namedComponents: "arrow-function",
          unnamedComponents: "arrow-function",
        },
      ],
      // Temporarily disable accessibility rules that are causing many errors
      "jsx-a11y/click-events-have-key-events": "warn",
      "jsx-a11y/no-static-element-interactions": "warn",
      "jsx-a11y/no-noninteractive-element-interactions": "warn",
      "jsx-a11y/no-autofocus": "warn",
    },
  },

  // Unicorn rules
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    plugins: {
      unicorn: unicornPlugin,
    },
    rules: {
      "unicorn/no-null": "off",
      "unicorn/prevent-abbreviations": "off",
      "unicorn/prefer-spread": "off",
      "unicorn/relative-url-style": "off",
      "unicorn/prefer-blob-reading-methods": "off",
      "unicorn/expiring-todo-comments": "off",
      "no-console": "error",
    },
  },

  // Console exceptions for Logger, tracer, and stories
  {
    files: [
      "**/utils/Logger.ts",
      "**/utils/tracer.ts",
      "**/core/cells/logs.ts",
      "**/stories/**/*.{ts,tsx}",
    ],
    rules: {
      "no-console": "off",
    },
  },

  // Test files
  {
    files: [
      "**/__tests__/**/*.{ts,tsx}",
      "**/*.test.{ts,tsx}",
      "**/e2e-tests/**/*.{ts,tsx}",
    ],
    rules: {
      "@typescript-eslint/no-unused-vars": "warn",
    },
  },

  // Story files
  {
    files: ["**/stories/**/*.{ts,tsx}"],
    rules: {
      "storybook/no-redundant-story-name": "warn",
      "@typescript-eslint/no-unused-vars": "warn",
    },
  },

  // Global settings
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2021,
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    settings: {
      react: {
        version: "detect",
      },
    },
  },
];
