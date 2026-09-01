import * as mod from "node:module";
import * as path from "node:path";
import type { StorybookConfig } from "@storybook/react-vite";
import { mergeConfig } from "vite";

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
  // `resolve.tsconfigPaths` only applies to files matched by tsconfig's
  // `include`, which does not cover `.mdx` stories, so alias `@` explicitly.
  // `mergeConfig` handles both the array and object forms of `resolve.alias`.
  viteFinal: (config) =>
    mergeConfig(config, {
      resolve: {
        alias: { "@": path.resolve(import.meta.dirname, "../src") },
      },
    }),
} satisfies StorybookConfig;
