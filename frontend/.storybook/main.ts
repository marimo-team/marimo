import * as mod from "node:module";
import * as path from "node:path";
import type { StorybookConfig } from "@storybook/react-vite";

function absolutePath(value: string) {
  const require = mod.createRequire(import.meta.url);
  return path.dirname(require.resolve(path.join(value, "package.json")));
}

export default {
  stories: ["../src/**/*.mdx", "../src/**/*.@(mdx|stories.@(js|jsx|ts|tsx))"],
  addons: [
    absolutePath("@storybook/addon-links"),
    absolutePath("@storybook/addon-docs"),
  ],
  framework: {
    name: absolutePath("@storybook/react-vite"),
    options: {},
  },
  docs: {
    docsMode: false,
  },
  viteFinal: (config) => {
    // `resolve.tsconfigPaths` only applies to files matched by tsconfig's
    // `include`, which does not cover `.mdx` stories, so alias `@` explicitly.
    config.resolve ??= {};
    config.resolve.alias = {
      ...config.resolve.alias,
      "@": path.resolve(import.meta.dirname, "../src"),
    };
    return config;
  },
} satisfies StorybookConfig;
