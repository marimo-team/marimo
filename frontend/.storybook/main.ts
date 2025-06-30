import * as mod from "node:module";
import * as path from "node:path";
import type { StorybookConfig } from "@storybook/react-vite";

function absolutePath(value: string): any {
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
} satisfies StorybookConfig;
