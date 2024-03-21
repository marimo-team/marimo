/* Copyright 2024 Marimo. All rights reserved. */

declare global {
  interface Window {
    Logger?: ILogger;
  }
}

interface ILogger {
  debug: (typeof console)["debug"];
  log: (typeof console)["log"];
  warn: (typeof console)["warn"];
  error: (typeof console)["error"];
}

/**
 * Wrapper around console.log that can be used to disable logging in production or add additional logging.
 */
const ConsoleLogger: ILogger = {
  debug: (...args) => {
    if (process.env.NODE_ENV !== "production") {
      console.debug(...args);
    }
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

function getLogger(): ILogger {
  if (typeof window !== "undefined") {
    return window.Logger || ConsoleLogger;
  }
  return ConsoleLogger;
}

export const Logger = getLogger();
