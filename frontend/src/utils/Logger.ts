/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable no-console */

import { Functions } from "./functions";

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
  trace: (typeof console)["trace"];
  get: (namespace: string) => ILogger;
  disabled: (disabled?: boolean) => ILogger;
}

const createNamespacedLogger = (
  namespace: string,
  baseLogger: ILogger,
): ILogger => {
  const prefix = `[${namespace}]`;
  return {
    debug: (...args) => baseLogger.debug(prefix, ...args),
    log: (...args) => baseLogger.log(prefix, ...args),
    warn: (...args) => baseLogger.warn(prefix, ...args),
    error: (...args) => baseLogger.error(prefix, ...args),
    trace: (...args) => baseLogger.trace(prefix, ...args),
    get: (subNamespace: string) =>
      createNamespacedLogger(`${namespace}.${subNamespace}`, baseLogger),
    disabled: (disabled = true) => {
      if (disabled) {
        return DisabledLogger;
      }
      return baseLogger;
    },
  };
};

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
  trace: (...args) => {
    console.trace(...args);
  },
  get: (namespace: string) => createNamespacedLogger(namespace, ConsoleLogger),
  disabled: (disabled = true) => {
    if (disabled) {
      return DisabledLogger;
    }
    return ConsoleLogger;
  },
};

const DisabledLogger: ILogger = {
  debug: () => Functions.NOOP,
  log: () => Functions.NOOP,
  warn: () => Functions.NOOP,
  error: () => Functions.NOOP,
  trace: () => Functions.NOOP,
  get: () => DisabledLogger,
  disabled: () => DisabledLogger,
};

function getLogger(): ILogger {
  if (globalThis.window !== undefined) {
    return globalThis.Logger || ConsoleLogger;
  }
  return ConsoleLogger;
}

export const Logger = getLogger();
