import { defineConfig } from "tsup";

export default defineConfig({
  outExtension({ format }) {
    return {
      js: `.${format}`,
    };
  },
});
