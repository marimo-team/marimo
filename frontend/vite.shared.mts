/* Copyright 2026 Marimo. All rights reserved. */

import type { ReactCompilerOptions } from "@vitejs/plugin-react";
import { createLogger, type Logger } from "vite";

/**
 * React Compiler options shared by the app and islands builds.
 * The compiler is run by `@vitejs/plugin-react` through `oxc-transform-react`.
 */
export const reactCompilerConfig: ReactCompilerOptions = {
  target: "19",
};

/**
 * Creates the Vite logger used by the app and islands builds.
 *
 * The Oxc-backed React Compiler reports every component or hook it skips
 * (`try`/`finally`, ref access during render, incompatible libraries, ...)
 * as a warning; there are ~100 of them in this codebase, and the Babel
 * plugin it replaced was silent. Hide them by default so real warnings stay
 * visible, and set `REACT_COMPILER_DIAGNOSTICS=true` to see them.
 */
export function createViteLogger(): Logger {
  const logger = createLogger();
  if (process.env.REACT_COMPILER_DIAGNOSTICS === "true") {
    return logger;
  }
  const warn = logger.warn;
  logger.warn = (msg, options) => {
    if (msg.includes("react-compiler(")) {
      return;
    }
    warn.call(logger, msg, options);
  };
  return logger;
}
