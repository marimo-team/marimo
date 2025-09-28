/* Copyright 2025 Marimo. All rights reserved. */

/** biome-ignore-all lint/suspicious/noConsole: For logging */

declare global {
  interface Window {
    SimpleLogger?: SimpleLogger;
  }
}

class SimpleLogger {
  name: string;

  constructor(name = "LLM Info") {
    this.name = name;
  }

  _log(
    level: "info" | "warn" | "error" | "debug",
    message: string,
    ...args: any[]
  ) {
    const timestamp = new Date().toISOString();
    const topMessage = `${timestamp} [${this.name}] [${level.toUpperCase()}] ${message}`;

    switch (level) {
      case "info":
        console.info(topMessage, ...args);
        break;
      case "warn":
        console.warn(topMessage, ...args);
        break;
      case "error":
        console.error(topMessage, ...args);
        break;
      case "debug":
        console.debug(topMessage, ...args);
        break;
    }
  }

  info(message: string, ...args: any[]) {
    this._log("info", message, ...args);
  }

  warn(message: string, ...args: any[]) {
    this._log("warn", message, ...args);
  }

  error(message: string, ...args: any[]) {
    this._log("error", message, ...args);
  }

  debug(message: string, ...args: any[]) {
    this._log("debug", message, ...args);
  }
}

function getLogger(): SimpleLogger {
  if (typeof window !== "undefined") {
    return window.SimpleLogger || new SimpleLogger();
  }
  return new SimpleLogger();
}

export const Logger = getLogger();
