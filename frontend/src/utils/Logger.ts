/* Copyright 2023 Marimo. All rights reserved. */
interface ILogger {
  debug: (typeof console)["debug"];
  log: (typeof console)["log"];
  warn: (typeof console)["warn"];
  error: (typeof console)["error"];
}

/**
 * Wrapper around console.log that can be used to disable logging in production or add additional logging.
 */
export const Logger: ILogger = {
  debug: (...args) => {
    console.debug(...args);
  },
  log: (...args) => {
    console.log(...args);
  },
  warn: (...args) => {
    console.warn(...args);
  },
  error: (...args) => {
    console.error(...args);
  },
};
