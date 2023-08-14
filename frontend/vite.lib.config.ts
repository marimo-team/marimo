import { defineConfig } from "vite";
import { resolve } from "path";
import react from "@vitejs/plugin-react-swc";
import tsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
/**
 * Vite config for building the Marimo library.
 */
export default defineConfig({
  build: {
    lib: {
      // Could also be a dictionary or array of multiple entry points
      entry: resolve(__dirname, "src/index.ts"),
      formats: ["cjs"],
      fileName: "marimo",
    },
    outDir: "lib",
    rollupOptions: {
      // Externalize deps that shouldn't be bundled into the library.
      external: ["react", "react-dom"],
    },
  },
  plugins: [react(), tsconfigPaths()],
});
